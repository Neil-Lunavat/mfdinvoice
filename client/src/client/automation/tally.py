"""The month's invoices into the person's Tally, through Tally's own server on this PC (port 9000 unless moved).

What Tally does from outside was found on a paid TallyPrime 7.1 (`labs/15_tally`, 3 Oct 2026). What came out of it,
all kept here:

- An empty answer is never trusted: a company that is not open reads back empty with no error, so the company must be
  in Tally's own list of open companies first.
- A fund house is found by its GSTIN, never by its name. Its sales ledger is the one on its latest invoice. The tax
  ledgers are the ones the books already use. What cannot be told is asked once and remembered (`tally.json`).
- Whose number: on a Sales type numbered Automatic, Tally ignores any number sent and gives its own next one; on
  Manual (and Automatic with manual override) it keeps the one sent. So on Automatic the numbers Tally will give are
  worked out before anything is written, and read back after.
- Never twice: every invoice carries our own id, `MFDInvoice/<ARN>/<registrar>/<reference>`, which Tally shows back
  as `RemoteGUID`. One already in the books is skipped and named.
- An invoice that looks typed by hand (same fund house, same month, within a rupee) is held back; on the person's yes
  it is changed to the registrar's figures by Tally's own id, with our id inside it, keeping its number.
- One invoice per request, so a refusal is tied to its invoice, in Tally's own words.
- Never ask Tally for a single object (`<TYPE>Object</TYPE>`): it crashes TallyPrime 7.1. A date must say
  `TYPE="Date"`, or Tally uses the period its own screen is on.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from xml.sax.saxutils import escape as e

from client.automation import files, numbering, words
from client.automation.invoices.layout import state_name
from client.automation.month import Month
from client.automation.words import CAMS, NAMES

log = logging.getLogger(__name__)

URL = "http://127.0.0.1:9000"
# The start of our id on every invoice we put in. It never changes, whatever the product is called.
OURS = "MFDInvoice/"
KEEPS_OUR_NUMBER = ("Manual", "Automatic (Manual Override)")
SUBMITTED = ("Submitted", "Waiting approval", "Approved")
GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")
# Tally's own spelling, where it differs from the one printed on an invoice
TALLY_STATE = {"01": "Jammu & Kashmir", "26": "Dadra & Nagar Haveli and Daman & Diu", "35": "Andaman & Nicobar Islands"}
D = Decimal


class Off(Exception):
    """Tally gave no answer."""


# --- one request ------------------------------------------------------------------------------------------------

def _post(name: str, body: str = "", timeout: float = 60) -> str:
    data = body.encode("utf-8")
    req = urllib.request.Request(URL, data=data if body else None, method="POST" if body else "GET",
                                 headers={"Content-Type": "text/xml; charset=utf-8"})
    started = datetime.now()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:          # Tally, on this PC
            raw = r.read()
    except urllib.error.HTTPError as err:
        raw = err.read()
    except (urllib.error.URLError, OSError) as err:
        log.info("tally %s: no answer (%s)", name, err)
        raise Off(str(err)) from err
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or (len(raw) > 3 and raw[1:2] == b"\x00" and raw[3:4] == b"\x00"):
        text = raw.decode("utf-16", "replace")
    else:
        text = raw.decode("utf-8", "replace")
    log.debug("tally %s: %d chars in %.1fs", name, len(text), (datetime.now() - started).total_seconds())
    return text


def _listening() -> int:
    """The port a running Tally listens on, as Windows tells it, or 0. The person may have moved it off 9000."""
    import psutil
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() != "tally.exe":
            continue
        try:
            ports = [c.laddr.port for c in p.net_connections("tcp") if c.status == psutil.CONN_LISTEN]
        except psutil.Error:
            continue
        if ports:
            return ports[0]
    return 0


def alive() -> bool:
    global URL
    try:
        return "Running" in _post("alive", timeout=3)
    except Off:
        pass
    port = _listening()
    if not port or URL.endswith(f":{port}"):
        return False
    log.info("tally: nothing on %s; Tally listens on port %d", URL, port)
    URL = f"http://127.0.0.1:{port}"
    try:
        return "Running" in _post("alive", timeout=3)
    except Off:
        return False


def _static(company: str = "", **more) -> str:
    v = {"SVEXPORTFORMAT": "$$SysName:XML", **({"SVCURRENTCOMPANY": company} if company else {}), **more}
    typed = {"SVFROMDATE": ' TYPE="Date"', "SVTODATE": ' TYPE="Date"'}
    return ("<STATICVARIABLES>" + "".join(f"<{k}{typed.get(k, '')}>{e(str(x))}</{k}>" for k, x in v.items())
            + "</STATICVARIABLES>")


def _collection(of: str, fetch: str, company: str = "", filters: dict | None = None, **variables) -> str:
    parts = f"<TYPE>{e(of)}</TYPE><FETCH>{e(fetch)}</FETCH>"
    if filters:
        parts += f"<FILTER>{','.join(filters)}</FILTER>"
    systems = "".join(f'<SYSTEM TYPE="Formulae" NAME="{k}">{e(v)}</SYSTEM>' for k, v in (filters or {}).items())
    return ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE>"
            f"<ID>MFDList</ID></HEADER><BODY><DESC>{_static(company, **variables)}<TDL><TDLMESSAGE>"
            f'<COLLECTION NAME="MFDList" ISMODIFY="No">{parts}</COLLECTION>{systems}'
            "</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>")


def _import(messages: str, what: str, company: str) -> str:
    return ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE>"
            f"<ID>{e(what)}</ID></HEADER><BODY><DESC><STATICVARIABLES><SVCURRENTCOMPANY>{e(company)}"
            "</SVCURRENTCOMPANY></STATICVARIABLES></DESC><DATA>"
            f'<TALLYMESSAGE xmlns:UDF="TallyUDF">{messages}</TALLYMESSAGE></DATA></BODY></ENVELOPE>')


def _g(body: str, tag: str) -> str:
    m = re.search(rf"<{tag}(?: [^>]*)?>([^<]*)</{tag}>", body)
    return _unxml(m.group(1).strip()) if m else ""


def _unxml(s: str) -> str:
    return (s.replace("&apos;", "'").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
            .replace("&amp;", "&"))


def _said(text: str) -> tuple[bool, str]:
    """An import's answer: did one thing go in (made or changed), and Tally's own words when it did not."""
    made = _g(text, "CREATED") == "1" or _g(text, "ALTERED") == "1"
    errors = [_unxml(x.strip()) for x in re.findall(r"<LINEERROR>(.*?)</LINEERROR>", text, re.DOTALL)]
    if made and not errors:
        return True, ""
    return False, "; ".join(errors) or re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()[:300] or "no answer"


# --- reading the books ------------------------------------------------------------------------------------------

def companies() -> list[dict]:
    """The companies open in Tally now."""
    text = _post("companies", _collection("Company", "Name,BooksFrom,GUID"))
    return [{"name": _unxml(n), "guid": _g(b, "GUID"), "booksFrom": _g(b, "BOOKSFROM")}
            for n, b in re.findall(r'<COMPANY NAME="([^"]*)"[^>]*>(.*?)</COMPANY>', text, re.DOTALL)]


def read(company: str, fy_from: str, fy_to: str) -> dict:
    """Everything an import needs to know about this company's books, as Tally says it."""
    text = _post("gstin", _collection("TaxUnit", "Name,GSTRegNumber", company))
    gstin = next(iter(re.findall(r"<GSTREGNUMBER[^>]*>([^<]+)<", text)), "").strip().upper()

    text = _post("groups", _collection("Group", "Name,Parent", company))
    groups = {_unxml(n): (_g(b, "PARENT"), _unxml(res))
              for n, res, b in re.findall(r'<GROUP NAME="([^"]*)" RESERVEDNAME="([^"]*)">(.*?)</GROUP>', text, re.DOTALL)}

    text = _post("ledgers", _collection(
        "Ledger", "Name,Parent,PartyGSTIN,LedGSTRegDetails.*,GSTDutyHead,RateOfTaxCalculation,IsBillWiseOn", company))
    ledgers = {}
    for n, b in re.findall(r'<LEDGER NAME="([^"]*)"[^>]*>(.*?)</LEDGER>', text, re.DOTALL):
        found = re.findall(r"<GSTIN[^>]*>([^<]+)</GSTIN>", b) + re.findall(r"<PARTYGSTIN[^>]*>([^<]+)<", b)
        ledgers[_unxml(n)] = {"parent": _g(b, "PARENT"), "gstin": found[-1].strip().upper() if found else "",
                              "duty": _g(b, "GSTDUTYHEAD"), "rate": _g(b, "RATEOFTAXCALCULATION").strip(),
                              "billwise": _g(b, "ISBILLWISEON") == "Yes"}

    text = _post("voucher types", _collection("Voucher Type", "*", company))
    vtypes = {}
    for n, res, b in re.findall(r'<VOUCHERTYPE NAME="([^"]*)" RESERVEDNAME="([^"]*)">(.*?)</VOUCHERTYPE>', text, re.DOTALL):
        series = re.findall(r"<VOUCHERNUMBERSERIES.LIST>(.*?)</VOUCHERNUMBERSERIES.LIST>", b, re.DOTALL)
        vtypes[_unxml(n)] = {"parent": _g(b, "PARENT"), "reserved": _unxml(res),
                             "method": _g(series[0], "NUMBERINGMETHOD") if series else _g(b, "NUMBERINGMETHOD")}

    text = _post("sales invoices", _collection(
        "Voucher", "Date,VoucherNumber,VoucherTypeName,PartyLedgerName,Amount,MasterID,IsCancelled,IsOptional,"
                   "RemoteGUID,AllLedgerEntries.LedgerName,AllLedgerEntries.Amount,"
                   "AllLedgerEntries.BillAllocations.Name,LedgerEntries.BillAllocations.Name", company,
        filters={"MFDSales": "$$IsSales:$VoucherTypeName"}, SVFROMDATE=fy_from, SVTODATE=fy_to), timeout=180)
    return {"gstin": gstin, "groups": groups, "ledgers": ledgers, "vtypes": vtypes, "vouchers": _vouchers(text)}


def _vouchers(text: str) -> list[dict]:
    out = []
    for body in re.findall(r"<VOUCHER [^>]*>(.*?)</VOUCHER>", text, re.DOTALL):
        head = body.split("<ALLLEDGERENTRIES.LIST>")[0]
        lines = [_unxml(n) for n in re.findall(r"<LEDGERNAME[^>]*>([^<]*)</LEDGERNAME>", body)]
        bills = re.findall(r"<BILLALLOCATIONS.LIST>.*?<NAME[^>]*>([^<]*)</NAME>", body, re.DOTALL)
        out.append({"remote": _g(head, "REMOTEGUID"), "type": _g(head, "VOUCHERTYPENAME"),
                    "number": _g(head, "VOUCHERNUMBER"), "date": _g(head, "DATE"),
                    "party": _g(head, "PARTYLEDGERNAME"), "amount": D(_g(head, "AMOUNT") or 0),
                    "mid": int(_g(head, "MASTERID") or 0),
                    "off": _g(head, "ISCANCELLED") == "Yes" or _g(head, "ISOPTIONAL") == "Yes", "lines": lines,
                    "bill": _unxml(bills[0]) if bills else ""})
    return out


def gstin_ok(g: str) -> bool:
    """Is its last character the one the GST network's rule gives the first fourteen?"""
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if len(g) != 15 or any(c not in chars for c in g):
        return False
    total = 0
    for i, c in enumerate(g[:14]):
        p = chars.index(c) * (1 if i % 2 == 0 else 2)
        total += p // 36 + p % 36
    return chars[(36 - total % 36) % 36] == g[14]


# --- the voucher --------------------------------------------------------------------------------------------------

def _money(x) -> D:
    return D(str(x)).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def _voucher(*, vtype: str, date: str, party: str, party_gstin: str, state: str, sales: str, taxable: D, taxes: list,
             number: str, rid: str, reference: str, narration: str, bill: str = "", accept: bool = False,
             alter: dict | None = None) -> str:
    """One Sales invoice as Tally's accounting invoice. `taxes`: [(ledger, amount)], the zero ones left out.
    `alter`: the invoice typed by hand that this one replaces, {mid, date}: changed by Tally's own id, with our id
    inside it (putting our id on the tag would make a second invoice instead)."""
    total = taxable + sum(a for _n, a in taxes)
    L = "LEDGERENTRIES.LIST"
    bill_xml = (f"<BILLALLOCATIONS.LIST><NAME>{e(bill)}</NAME><BILLTYPE>New Ref</BILLTYPE><AMOUNT>-{total}</AMOUNT>"
                "</BILLALLOCATIONS.LIST>") if bill else ""
    lines = (f"<{L}><LEDGERNAME>{e(party)}</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>"
             f"<ISPARTYLEDGER>Yes</ISPARTYLEDGER><AMOUNT>-{total}</AMOUNT>{bill_xml}</{L}>"
             f"<{L}><LEDGERNAME>{e(sales)}</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
             f"<AMOUNT>{taxable}</AMOUNT></{L}>"
             + "".join(f"<{L}><LEDGERNAME>{e(n)}</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
                       f"<AMOUNT>{a}</AMOUNT></{L}>" for n, a in taxes))
    if alter:
        tag = (f'<VOUCHER VCHTYPE="{e(vtype)}" ACTION="Alter" OBJVIEW="Accounting Voucher View" '
               f'DATE="{alter["date"]}" TAGNAME="MASTERID" TAGVALUE="{alter["mid"]}">')
    else:
        tag = f'<VOUCHER VCHTYPE="{e(vtype)}" ACTION="Create" OBJVIEW="Accounting Voucher View" REMOTEID="{e(rid)}">'
    return (tag + f"<DATE>{date}</DATE><VOUCHERTYPENAME>{e(vtype)}</VOUCHERTYPENAME>"
            + (f"<VOUCHERNUMBER>{e(number)}</VOUCHERNUMBER>" if number else "")
            + f"<REFERENCE>{e(reference)}</REFERENCE><REFERENCEDATE>{date}</REFERENCEDATE>"
            + f"<PARTYLEDGERNAME>{e(party)}</PARTYLEDGERNAME><PARTYNAME>{e(party)}</PARTYNAME>"
            + f"<BASICBUYERNAME>{e(party)}</BASICBUYERNAME><PARTYMAILINGNAME>{e(party)}</PARTYMAILINGNAME>"
            + f"<PARTYGSTIN>{party_gstin}</PARTYGSTIN>"
            + (f"<STATENAME>{e(state)}</STATENAME><PLACEOFSUPPLY>{e(state)}</PLACEOFSUPPLY>"
               "<COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>" if state else "")
            + "<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>"
            + "<VCHENTRYMODE>Accounting Invoice</VCHENTRYMODE><ISINVOICE>Yes</ISINVOICE>"
            + f"<EFFECTIVEDATE>{date}</EFFECTIVEDATE><NARRATION>{e(narration)}</NARRATION>"
            + ("<ISGSTOVERRIDDEN>Yes</ISGSTOVERRIDDEN>" if accept else "")
            + (f"<REMOTEGUID>{e(rid)}</REMOTEGUID>" if alter else "")
            + lines + "</VOUCHER>")


def _state(gstin: str) -> str:
    return TALLY_STATE.get(gstin[:2]) or state_name(gstin[:2])


# --- one look at a month, and the import ---------------------------------------------------------------------------

class Session:
    """One month of one ARN against the company open in Tally: what an import would do (`look`), and doing it
    (`bring_in`). Nothing is written to Tally by `look`."""

    def __init__(self, base: Path, period: str, profile: dict, *, company: str = "", which: str = "submitted",
                 last: str = "", answers: dict | None = None):
        self.base, self.period, self.profile = base, period, profile
        self.arn = str(profile.get("arn") or base.name)
        self.month = Month(base, period)
        inv = profile.get("invoices") or {}
        self.own = inv.get("source") == "own"
        self.books_of_ours = numbering.Books(base / "books.json", str(inv.get("last") or ""),
                                             int(inv.get("at") if inv.get("at") is not None else -1))
        self.which = "all" if which == "all" else "submitted"
        self.asked_company, self.said_last, self.answers = company, (last or "").strip(), dict(answers or {})
        self.remember: dict = _load(base / "tally.json")
        self.company = ""
        self.books: dict = {}
        self.rows: list[dict] = []
        self.creates: list[dict] = []
        self.asks: list[dict] = []
        self.warn: list[str] = []
        self.vtype = self.method = self.last = ""
        self.tax: dict[str, tuple[str, bool]] = {}
        self.read_now = False
        self.order: list[str] = []

    # --- which company -------------------------------------------------------------------------------------------

    def connect(self) -> dict | None:
        """The company to work in, or the answer to give when there is none yet."""
        if not alive():
            return {"state": "off"}
        open_now = companies()
        if not open_now:
            return {"state": "closed"}
        names = [c["name"] for c in open_now]
        want = self.asked_company or next((c["name"] for c in open_now if c["guid"] == self.remember.get("guid")), "")
        if want not in names:
            want = names[0] if len(names) == 1 and not self.asked_company else ""
        if not want:
            return {"state": "pick", "companies": names,
                    "said": (f"{self.remember['company']} isn't open in Tally." if self.remember.get("company")
                             and self.remember["company"] not in names else "")}
        chosen = next(c for c in open_now if c["name"] == want)
        self.company, self.guid, self.open_names = want, chosen["guid"], names
        if self.remember.get("guid") != self.guid:
            self.remember = {}                    # what was remembered belongs to another company's books
        return None

    # --- the plan --------------------------------------------------------------------------------------------------

    def look(self) -> dict:
        stopped = self.connect()
        if stopped:
            return self._answer(**stopped)
        rows = sorted(self.month.rows.values(), key=lambda r: (r["registrar"] != CAMS, str(r.get("amc", "")).lower()))
        dates = sorted(str(r.get("date") or "")[:10] for r in rows if r.get("date"))
        y, m = (int(dates[0][:4]), int(dates[0][5:7])) if dates else (datetime.now().year, datetime.now().month)
        fy = y if m >= 4 else y - 1
        self.books = read(self.company, f"{fy}0401", f"{fy + 1}0331")
        self._numbering()
        self._taxes()
        mine = str(self.profile.get("gstin") or "").strip().upper()
        if not self.books["gstin"]:
            self.warn.append(f"{self.company} has no GSTIN in Tally, so GSTR-1 will list every invoice as uncertain.")
        elif mine and self.books["gstin"] != mine and self.answers.get("gstin") != "yes"                 and self.remember.get("gstin_ok") != self.books["gstin"]:
            # a question, not a warning: Import waits for it, and the yes is remembered for this company's GSTIN
            self.asks.append({"id": "gstin", "options": ["yes"],
                              "question": f"{self.company}'s GSTIN in Tally is {self.books['gstin']}. "
                                          f"Yours here is {mine}. Is this the right company?"})
        if self.method == "None":
            self.warn.append(f"'{self.vtype}' invoices have no numbers in this company (its numbering is None).")
        used_by_hand: set[int] = set()
        for r in rows:
            self.rows.append(self._plan_one(r, mine, used_by_hand))
        self._numbers()
        if self.read_now:
            self.month.save()                          # a fund house's GSTIN read off its PDF just now is kept
        return self._answer(state="ready")

    def _numbering(self) -> None:
        vouchers, vtypes = self.books["vouchers"], self.books["vtypes"]
        live = sorted((v for v in vouchers if not v["off"]), key=lambda v: v["mid"])
        # which kind of sales voucher: Sales when it is the only one; asked once when the company has more (Neil,
        # 7 Oct: never guessed from the last voucher entered, which picked a lab's own type)
        sales = sales_types(vtypes)
        said, kept = self.answers.get("vtype"), self.remember.get("vtype")
        if said in sales or kept in sales:
            self.vtype = said if said in sales else kept
        else:
            self.vtype = next((n for n in sales if vtypes[n]["reserved"] == "Sales"), sales[0] if sales else "Sales")
            if len(sales) > 1:
                self.asks.append({"id": "vtype", "options": sales,
                                  "question": f"{self.company} has {len(sales)} kinds of sales voucher. Which one do "
                                              "these invoices go in as?"})
        self.method = vtypes.get(self.vtype, {}).get("method", "")
        self.sends = self.method in KEEPS_OUR_NUMBER
        of_type = [v for v in live if v["type"] == self.vtype and v["number"]]
        self.last = of_type[-1]["number"] if of_type else ""       # the latest entered, not the latest dated

    def _taxes(self) -> None:
        ledgers = self.books["ledgers"]
        used: dict[str, str] = {}
        for v in sorted(self.books["vouchers"], key=lambda v: -v["mid"]):
            for n in v["lines"]:
                duty = ledgers.get(n, {}).get("duty")
                if duty:
                    used.setdefault(duty, n)
        for key, duty, rate in (("cgst", "CGST", "9"), ("sgst", "SGST/UTGST", "9"), ("igst", "IGST", "18")):
            kept = (self.remember.get("tax") or {}).get(key)
            fit = [n for n, led in ledgers.items() if led["duty"] == duty and led["rate"] in (rate, "")]
            exact = [n for n in fit if ledgers[n]["rate"] == rate]
            if kept in ledgers:
                self.tax[key] = (kept, False)
            elif duty in used:
                self.tax[key] = (used[duty], False)
            elif len(exact) == 1 or len(fit) == 1:
                self.tax[key] = ((exact or fit)[0], False)
            else:
                self.tax[key] = (f"Output {duty.split('/')[0]} @ {rate}%", True)

    def _under(self, ledger: str, reserved: str) -> bool:
        """Is this ledger under Tally's own group of this name, whatever the person renamed it to?"""
        group, seen = self.books["ledgers"].get(ledger, {}).get("parent", ""), set()
        while group and group not in seen:
            parent, res = self.books["groups"].get(group, ("", ""))
            if res == reserved or group == reserved:
                return True
            seen.add(group)
            group = parent
        return False

    def _plan_one(self, r: dict, mine: str, used_by_hand: set[int]) -> dict:
        ledgers, vouchers = self.books["ledgers"], self.books["vouchers"]
        key, reg = r["key"], r["registrar"]
        taxable, cgst, sgst, igst = (_money(r.get(k) or 0) for k in ("taxable", "cgst", "sgst", "igst"))
        total = taxable + cgst + sgst + igst
        gstin = self._gstin_of(r, mine)
        submitted = words.status_of(r) in SUBMITTED
        p = {"key": key, "registrar": reg, "amc": r.get("amc") or key, "date": str(r.get("date") or "")[:10],
             "total": float(total), "submitted": submitted, "gstin": gstin, "ours": "", "number": "", "will": "",
             "party": "", "partyNew": False, "sales": "", "action": "import", "note": "",
             "rid": f"{OURS}{self.arn}/{reg}/{key}",
             "_": {"taxable": taxable, "cgst": cgst, "sgst": sgst, "igst": igst}}
        done = next((v for v in vouchers if v["remote"] == p["rid"] and not v["off"]), None)
        if done:
            p.update(action="in_books", number=done["number"], party=done["party"],
                     note=f"Already in your books as {done['number']}" if done["number"] else "Already in your books")
            return p
        if self.which == "submitted" and not submitted:
            return {**p, "action": "later", "note": "Not submitted yet"}
        if not gstin:
            return {**p, "action": "stop", "note": "The fund house's GSTIN couldn't be read off this invoice."}
        if not gstin_ok(gstin):
            return {**p, "action": "stop", "note": f"The fund house's GSTIN {gstin} fails its own check digit."}
        if not p["date"]:
            return {**p, "action": "stop", "note": "This invoice has no date."}
        if self.own and igst:
            return {**p, "action": "stop", "note": "It charges IGST, and your own invoice for IGST isn't made yet."}

        # the fund house: by GSTIN only
        with_gstin = [n for n, led in ledgers.items() if led["gstin"] == gstin]
        debtors = [n for n in with_gstin if self._under(n, "Sundry Debtors")] or with_gstin
        kept = (self.remember.get("party") or {}).get(gstin)
        said = self.answers.get(f"party:{gstin}")
        if said in ledgers:
            p["party"] = said
        elif kept in ledgers:
            p["party"] = kept
        elif len(debtors) == 1:
            p["party"] = debtors[0]
        elif len(debtors) > 1:
            busy = [c for c in debtors if any(v["party"] == c for v in vouchers)]
            if len(busy) == 1:
                p["party"] = busy[0]
            else:
                self._ask(f"party:{gstin}",
                          f"{len(debtors)} of your ledgers carry {p['amc']}'s GSTIN. Which one is it?", debtors)
                p.update(action="ask", note="Which ledger is this fund house?")
        else:
            name = str(r.get("party") or p["amc"]).strip()
            if name in ledgers:                      # a ledger of that name with another GSTIN, or none
                self._ask(f"party:{gstin}", f"No ledger carries {p['amc']}'s GSTIN ({gstin}). Which one is it?",
                          sorted(n for n in ledgers if self._under(n, "Sundry Debtors")))
                p.update(action="ask", note="Which ledger is this fund house?")
            else:
                p.update(party=name, partyNew=True)
                if not any(c["name"] == name for c in self.creates):
                    self.creates.append({"kind": "party", "name": name, "gstin": gstin})

        # its sales ledger: the one on its latest invoice
        if p["party"]:
            history = sorted((v for v in vouchers if v["party"] == p["party"] and not v["off"]),
                             key=lambda v: (v["date"], v["mid"]))
            from_last = [n for n in history[-1]["lines"] if self._under(n, "Sales Accounts")] if history else []
            kept = (self.remember.get("sales") or {}).get(gstin)
            said = self.answers.get(f"sales:{gstin}")
            if said in ledgers:
                p["sales"] = said
            elif kept in ledgers:
                p["sales"] = kept
            elif from_last:
                p["sales"] = from_last[0]
            else:
                options = sorted(n for n in ledgers if self._under(n, "Sales Accounts"))
                if len(options) == 1:
                    p["sales"] = options[0]
                elif options:
                    self._ask(f"sales:{gstin}", f"Which sales ledger does {p['amc']}'s commission go under?", options)
                    p.update(action="ask", note="Which sales ledger?")
                else:
                    return {**p, "action": "stop",
                            "note": "This company has no sales ledger. Make one in Tally, under Sales Accounts."}
        if p["action"] == "ask":
            return p

        if igst and self.tax["igst"][1] and not any(c["kind"] == "tax" for c in self.creates):
            self.creates.append({"kind": "tax", "name": self.tax["igst"][0], "gstin": ""})
        if (cgst or sgst) and (self.tax["cgst"][1] or self.tax["sgst"][1]):
            return {**p, "action": "stop", "note": "No CGST and SGST ledgers were found in this company."}

        # typed by hand already? the same fund house, the same month, within a rupee
        hand = next((v for v in vouchers if v["party"] == p["party"] and v["date"][:6] == p["date"].replace("-", "")[:6]
                     and abs(-v["amount"] - total) <= 1 and not v["remote"].startswith(OURS) and not v["off"]
                     and v["mid"] not in used_by_hand), None)
        if hand and not p["partyNew"]:
            used_by_hand.add(hand["mid"])
            p["_"]["hand"] = hand
            p.update(action="by_hand", number=hand["number"],
                     note=f"Looks typed by hand already: {hand['number']} on {_day(hand['date'])}, "
                          f"{words.inr(float(-hand['amount']))}")
        return p

    def _ask(self, id_: str, question: str, options: list[str]) -> None:
        if not any(a["id"] == id_ for a in self.asks):
            self.asks.append({"id": id_, "question": question, "options": options})

    def _gstin_of(self, r: dict, mine: str) -> str:
        """The fund house's GSTIN: kept on the invoice's row by the run that read it, else read off its PDF now. Both
        registrars' invoices, and the person's own, print two: the person's first, then the fund house's."""
        if r.get("gstin"):
            return str(r["gstin"]).upper()
        try:
            path = self.month.path(r.get("file") or "")
            text = " ".join(w["text"] for w in files.text_layer(path)["items"]) if path.is_file() else ""
        except Exception as err:                       # noqa: BLE001 - a PDF that will not open has no GSTIN to give
            log.info("tally: %s could not be read for its GSTIN: %s", r.get("key"), err)
            text = ""
        printed = list(dict.fromkeys(GSTIN.findall(text.upper())))
        others = [g for g in printed if g != mine]
        if len(others) == 1 or (len(others) == 2 and mine not in printed):
            r["gstin"] = others[-1]
            self.read_now = True
            return r["gstin"]
        return ""

    def _numbers(self) -> None:
        """The number each invoice will carry in Tally, worked out before anything is written."""
        # the submitted ones first: the rest take the numbers after them
        going = sorted((p for p in self.rows if p["action"] == "import"), key=lambda p: not p["submitted"])
        if self.own:
            # Tally is the truth (Neil, 7 Oct): an own invoice already in the books, typed by hand, has the number it
            # has there. It is kept as that invoice's number, so the series never gives it another.
            truth = {p["key"]: p["number"] for p in self.rows if p["action"] == "by_hand" and p["number"]
                     and self.books_of_ours.number_of(p["key"]) != p["number"]}
            if truth:
                self.books_of_ours.lock(truth)
                for key, n in truth.items():
                    row = next(p for p in self.rows if p["key"] == key)
                    self.month.put(row["registrar"], key, number=n)
                self.read_now = True                   # the month is saved with them
            held = {p["key"]: self.books_of_ours.number_of(p["key"]) for p in self.rows}
            for p in self.rows:
                p["ours"] = held.get(p["key"], "")
            new = [p["key"] for p in going if not p["ours"]]
            if new and self.books_of_ours.ready:
                given = self.books_of_ours.hand_out(new)
                for p in going:
                    p["ours"] = p["ours"] or given.get(p["key"], "")
            going.sort(key=lambda p: self._count(p["ours"]))
        self.order = [p["key"] for p in going]
        start = self.last if (self.own or not self.sends) else (self.said_last or self.last)
        try:
            at = numbering.default_counter(start) if start else -1
            nexts = [numbering.bump(start, at, i + 1) for i in range(len(going))] if at >= 0 else []
        except numbering.NumberError:
            nexts = []
        taken = {v["number"] for v in self.books["vouchers"]
                 if v["type"] == self.vtype and not v["off"] and v["number"]}
        for i, p in enumerate(going):
            if self.sends:
                p["will"] = p["ours"] if self.own else (nexts[i] if nexts else "")
                if p["will"] and p["will"] in taken:
                    p.update(action="stop", note=f"{p['will']} is already another invoice in Tally.")
                elif not p["will"]:
                    p.update(action="stop", note="Your last invoice number is needed first." if not self.own
                             else "This invoice has no number yet.")
            else:
                p["will"] = nexts[i] if nexts else ""
                if self.own and p["will"] and p["ours"] and p["will"] != p["ours"]:
                    p["note"] = f"Tally will give {p['will']}; your invoice says {p['ours']}"
                    p["clash"] = True

    def _count(self, number: str) -> int:
        try:
            return numbering.count(number, self.books_of_ours.at)
        except numbering.NumberError:
            return 10 ** 9

    def _answer(self, state: str, **more) -> dict:
        public = [{k: v for k, v in p.items() if k not in ("_", "rid")} for p in self.rows]
        counts = {"submitted": sum(1 for p in self.rows if p["submitted"]), "all": len(self.rows),
                  "going": sum(1 for p in self.rows if p["action"] == "import"),
                  "byHand": sum(1 for p in self.rows if p["action"] == "by_hand"),
                  "inBooks": sum(1 for p in self.rows if p["action"] == "in_books")}
        return {"state": state, "said": "", "companies": getattr(self, "open_names", []), "company": self.company,
                "period": self.period, "label": words.labels(self.period)[0], "own": self.own, "which": self.which,
                "vtype": self.vtype, "method": self.method, "tallyNumbers": bool(self.method) and not self.sends,
                "last": self.last, "askLast": bool(self.company) and self.sends and not self.own,
                "rows": public, "creates": self.creates, "asks": self.asks, "warn": self.warn, "counts": counts,
                **more}

    # --- the import ------------------------------------------------------------------------------------------------

    def bring_in(self, adopt: list[str] | None = None) -> dict:
        """Put the month in. `adopt`: the invoices typed by hand that the person said to change to the registrar's
        figures. Returns the look afterwards, with `done`: what happened."""
        before = self.look()
        if before["state"] != "ready":
            return before
        adopt_keys = set(adopt or [])
        plan = {p["key"]: p for p in self.rows}
        done = {"imported": [], "adopted": [], "refused": [], "numbers": [], "stoppedAt": "", "top": "", "at": -1}
        try:
            for c in self.creates:
                ok, said = self._create(c)
                if not ok:
                    done["stoppedAt"] = f"Tally didn't make the ledger '{c['name']}': {said}"
                    return self._after(done)
            sending = ([plan[k] for k in self.order if plan[k]["action"] == "import"]
                       + [p for p in self.rows if p["action"] == "by_hand" and p["key"] in adopt_keys])
            for p in sending:
                hand = p["_"].get("hand") if p["action"] == "by_hand" else None
                number = p["number"] if hand else (p["will"] if self.sends else "")
                # an invoice typed by hand keeps the bill it had: a receipt may already be settled against it
                bill = (hand["bill"] or (number if self._billwise(p) else "")) if hand else ""
                ok, said = _said(_post(f"invoice {p['key']}", _import(self._xml(p, number, hand, bill), "Vouchers",
                                                                      self.company)))
                if ok:
                    done["adopted" if hand else "imported"].append(p["key"])
                else:
                    done["refused"].append({"key": p["key"], "amc": p["amc"], "said": said})
                    if self.own and not self.sends:
                        # the ones after it would take its number: nothing more goes in until this is looked at
                        done["stoppedAt"] = f"Tally refused {p['amc']}'s invoice, so the rest were not sent."
                        break
            went = set(done["imported"]) | set(done["adopted"])
            back = self._read_back()
            for p in sending:
                if p["key"] not in went:
                    continue
                got = back.get(p["rid"], "")
                if got and self._billwise(p) and p["action"] == "import":
                    ok, said = _said(_post(f"bill {p['key']}", _import(self._xml(p, got, None, bill=got), "Vouchers",
                                                                       self.company)))
                    if not ok:
                        log.warning("tally: the bill for %s was not added: %s", p["key"], said)
                self.month.put(p["registrar"], p["key"], tally=got or "in", tallyAt=_now())
                if got and p["action"] == "import":
                    done["numbers"].append(got)
                if self.own and p["ours"] and got and got != p["ours"]:
                    done["refused"].append({"key": p["key"], "amc": p["amc"], "differs": True,
                                            "said": f"Tally gave {got}; the invoice says {p['ours']}"})
            if self.own:
                mine = {p["key"]: p["ours"] for p in sending if p["key"] in went and p["ours"]}
                if mine:                                # these numbers are their invoices' for good from here
                    done["top"], done["at"] = self.books_of_ours.lock(mine), self.books_of_ours.at
                    for key, n in mine.items():
                        self.month.put(plan[key]["registrar"], key, number=n)
            self.month.save()
            self._remember(sending, went)
        except Off:
            done["stoppedAt"] = "Tally stopped answering part-way. Look again to see what went in."
            self.month.save()
            return {**before, "done": done}
        return self._after(done)

    def _billwise(self, p: dict) -> bool:
        return bool(self.books["ledgers"].get(p["party"], {}).get("billwise"))

    def _after(self, done: dict) -> dict:
        again = Session(self.base, self.period, self.profile, company=self.company, which=self.which,
                        last=self.said_last, answers=self.answers)
        out = again.look()
        if done["refused"]:                               # Tally's own words stay beside the invoice they are about
            said = {x["key"]: x["said"] for x in done["refused"]}
            for row in out.get("rows", []):
                if row["key"] in said:
                    row["refused"] = said[row["key"]]
        return {**out, "done": done}

    def _xml(self, p: dict, number: str, hand: dict | None, bill: str = "") -> str:
        f = p["_"]
        taxes = [(self.tax[k][0], f[k]) for k in ("cgst", "sgst", "igst") if f[k]]
        nine = (f["taxable"] * D("0.09")).quantize(D("0.01"), rounding=ROUND_HALF_UP)
        eighteen = (f["taxable"] * D("0.18")).quantize(D("0.01"), rounding=ROUND_HALF_UP)
        exact = (f["cgst"] in (0, nine)) and (f["sgst"] in (0, nine)) and (f["igst"] in (0, eighteen))
        label = words.labels(self.period)[0]
        narration = (f"Invoice {p['ours']} ({NAMES.get(p['registrar'], p['registrar'])} {p['key']}), {label}"
                     if self.own and p["ours"] else f"{NAMES.get(p['registrar'], p['registrar'])} {p['key']}, {label}")
        return _voucher(vtype=hand["type"] if hand else self.vtype, date=p["date"].replace("-", ""),
                        party=p["party"], party_gstin=p["gstin"], state=_state(p["gstin"]), sales=p["sales"],
                        taxable=f["taxable"], taxes=taxes, number=number, rid=p["rid"], reference=p["key"],
                        narration=narration, bill=bill, accept=not exact,
                        alter={"mid": hand["mid"], "date": hand["date"]} if hand else None)

    def _create(self, c: dict) -> tuple[bool, str]:
        name = c["name"]
        if c["kind"] == "party":
            from_ = next((x["booksFrom"] for x in companies() if x["name"] == self.company), "") or "20170701"
            xml = (f'<LEDGER NAME="{e(name)}" ACTION="Create"><NAME>{e(name)}</NAME><PARENT>Sundry Debtors</PARENT>'
                   f"<ISBILLWISEON>Yes</ISBILLWISEON><LEDGSTREGDETAILS.LIST><APPLICABLEFROM>{from_}</APPLICABLEFROM>"
                   "<GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>"
                   f"<PLACEOFSUPPLY>{e(_state(c['gstin']))}</PLACEOFSUPPLY><GSTIN>{c['gstin']}</GSTIN>"
                   "</LEDGSTREGDETAILS.LIST></LEDGER>")
        else:
            xml = (f'<LEDGER NAME="{e(name)}" ACTION="Create"><NAME>{e(name)}</NAME><PARENT>Duties &amp; Taxes</PARENT>'
                   "<TAXTYPE>GST</TAXTYPE><GSTDUTYHEAD>IGST</GSTDUTYHEAD><RATEOFTAXCALCULATION>18"
                   "</RATEOFTAXCALCULATION></LEDGER>")
        ok, said = _said(_post(f"ledger {name}", _import(xml, "All Masters", self.company)))
        log.info("tally: the ledger %r: %s", name, "made" if ok else said)
        if ok and c["kind"] == "party":
            self.books["ledgers"][name] = {"parent": "Sundry Debtors", "gstin": c["gstin"], "duty": "", "rate": "",
                                           "billwise": True}
        return ok, said

    def _read_back(self) -> dict[str, str]:
        dates = [p["date"].replace("-", "") for p in self.rows if p["date"]]
        y, m = int(min(dates)[:4]), int(min(dates)[4:6])
        fy = y if m >= 4 else y - 1
        text = _post("read back", _collection("Voucher", "VoucherNumber,RemoteGUID", self.company,
                                              filters={"MFDOurs": f'$RemoteGUID Starting With "{OURS}"'},
                                              SVFROMDATE=f"{fy}0401", SVTODATE=f"{fy + 1}0331"), timeout=180)
        return {_g(b, "REMOTEGUID"): _g(b, "VOUCHERNUMBER") for b in re.findall(r"<VOUCHER [^>]*>(.*?)</VOUCHER>",
                                                                                 text, re.DOTALL)}

    def _remember(self, sent: list[dict], went: set[str]) -> None:
        sure = self.answers.get("gstin") == "yes" or self.remember.get("gstin_ok") == self.books.get("gstin")
        keep = {"company": self.company, "guid": self.guid, "vtype": self.vtype, "gstin": self.books.get("gstin", ""),
                **({"gstin_ok": self.books.get("gstin", "")} if sure else {}),
                "tax": {k: v[0] for k, v in self.tax.items() if not v[1] or k == "igst"},
                "party": dict(self.remember.get("party") or {}), "sales": dict(self.remember.get("sales") or {})}
        for p in sent:
            if p["key"] in went:
                keep["party"][p["gstin"]], keep["sales"][p["gstin"]] = p["party"], p["sales"]
        _write(self.base / "tally.json", keep)


def last_number(base: Path) -> dict:
    """The last Sales invoice number in the company this ARN imports into, for the question before a run. Quick: it
    reads only the company list, the Sales type and the year's invoice numbers."""
    s = Session(base, "", {"arn": base.name})
    stopped = s.connect()
    if stopped:
        return {"state": stopped["state"], "company": "", "last": ""}
    now = datetime.now()
    fy = now.year if now.month >= 4 else now.year - 1
    text = _post("last number", _collection(
        "Voucher", "VoucherNumber,VoucherTypeName,MasterID,IsCancelled,IsOptional", s.company,
        filters={"MFDSales": "$$IsSales:$VoucherTypeName"}, SVFROMDATE=f"{fy}0401", SVTODATE=f"{fy + 1}0331"),
        timeout=120)
    live = sorted((v for v in _vouchers(text) if not v["off"] and v["number"]), key=lambda v: v["mid"])
    want = s.remember.get("vtype") or "Sales"
    of_type = [v for v in live if v["type"] == want]
    return {"state": "ready", "company": s.company, "last": of_type[-1]["number"] if of_type else ""}


def sales_types(vtypes: dict) -> list[str]:
    """The company's kinds of sales voucher: Tally's own Sales, and every type made under it, however deep."""
    def sales(name: str, seen: frozenset = frozenset()) -> bool:
        t = vtypes.get(name)
        if not t or name in seen:
            return False
        return t["reserved"] == "Sales" or sales(t["parent"], seen | {name})
    return [n for n in vtypes if sales(n)]


def setup_look(gstin: str) -> dict:
    """Setup's Tally step: is Tally answering, which companies are open, and each one's GSTIN beside this ARN's.
    Reads only the company list and each company's tax unit; nothing in Tally changes."""
    if not alive():
        return {"state": "off", "companies": []}
    open_now = companies()
    if not open_now:
        return {"state": "closed", "companies": []}
    mine, out = gstin.strip().upper(), []
    for c in open_now:
        text = _post("gstin", _collection("TaxUnit", "Name,GSTRegNumber", c["name"]))
        theirs = next(iter(re.findall(r"<GSTREGNUMBER[^>]*>([^<]+)<", text)), "").strip().upper()
        out.append({"name": c["name"], "guid": c["guid"], "gstin": theirs, "same": bool(mine) and theirs == mine})
    return {"state": "ready", "companies": out}


def keep_company(base: Path, name: str, guid: str, gstin: str = "", sure: bool = False) -> None:
    """The company chosen at setup: the first look goes straight to it. Ledgers kept for another company go. `sure`:
    the person ticked "This is the right company" for a GSTIN that isn't theirs, so the Tally tab doesn't ask again."""
    kept = _load(base / "tally.json")
    if kept.get("guid") != guid:
        kept = {}
    _write(base / "tally.json", {**kept, "company": name, "guid": guid, "gstin": gstin.strip().upper(),
                                 **({"gstin_ok": gstin.strip().upper()} if sure else {})})


def forget(base: Path) -> None:
    (base / "tally.json").unlink(missing_ok=True)


def remembered(base: Path) -> dict:
    kept = _load(base / "tally.json")
    return {"company": kept.get("company", ""), "gstin": kept.get("gstin", ""), "ledgers": len(kept.get("party") or {})}


def _load(path: Path) -> dict:
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _day(yyyymmdd: str) -> str:
    try:
        return datetime.strptime(yyyymmdd, "%Y%m%d").strftime("%d %b").lstrip("0")
    except ValueError:
        return yyyymmdd
