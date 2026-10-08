"""The month's invoices into the person's Zoho Books, over Zoho's own API. What Zoho does from outside was found on a
Zoho Books organisation of ours (`labs/zoho-results.md`, 7 Oct 2026). What came out of it, all kept here:

- The software is let in by the person's browser (`hands/zoho.py`); the steps are handed an access token and nothing
  else. Zoho in India only (www.zohoapis.in).
- A fund house is a customer found by its GSTIN (exact), never by its name; made when missing. Two customers can share
  a GSTIN: that is a question, remembered.
- Whose number: if the person's invoices are numbered by Zoho's own series (the latest ones are prefix + digits and
  automatic numbering is on), no number is sent and Zoho's is read back. Otherwise the number is ours: the highest of
  the person's own shape this financial year + 1, sent with `ignore_auto_number_generation=true`. A number Zoho
  already holds is refused (code 1001): the highest is read again and the write retried.
- Never twice: every invoice carries our id in `reference_number`, `MFDInvoice/<ARN>/<registrar>/<reference>`, and is
  found by it before anything is written. It is shown as "P.O.#" in Zoho.
- An invoice that looks typed by hand (same customer, same month, within a rupee, no reference) is changed to the
  registrar's figures by PUT with our reference on it, keeping its number.
- One invoice per request, so a refusal is tied to its invoice, in Zoho's own words ({code, message}).
- Created as a draft; nothing is ever emailed. The signed PDF is attached after Sign; it is marked sent only once the
  registrar has taken it (`after_submit`).
- Limits: 100 calls a minute, a day's worth by plan (X-Rate-Limit-Remaining). Calls are paced; few left stops.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from client.automation import numbering, words
from client.automation.month import Month
from client.automation.tally import (OURS, SUBMITTED, D, Off, Refused, _load, _money, _now, _when, _write, gstin_ok)
from client.automation.words import CAMS, NAMES

log = logging.getLogger(__name__)

GST_STATE = {
    "01": "JK", "02": "HP", "03": "PB", "04": "CH", "05": "UK", "06": "HR", "07": "DL", "08": "RJ", "09": "UP",
    "10": "BR", "11": "SK", "12": "AR", "13": "NL", "14": "MN", "15": "MZ", "16": "TR", "17": "ML", "18": "AS",
    "19": "WB", "20": "JH", "21": "OD", "22": "CG", "23": "MP", "24": "GJ", "26": "DN", "27": "MH", "29": "KA",
    "30": "GA", "31": "LD", "32": "KL", "33": "TN", "34": "PY", "35": "AN", "36": "TS", "37": "AP", "38": "LA"}
SAC = "997152"
PACE_S = 0.3                      # at least this long between two calls (Zoho allows 100 a minute)
LOW = 5                           # this few calls left for the day: stop, with words
GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")
NAME = "Zoho Books"


class Said(Refused):
    """Zoho's refusal: its own `code` and `message`."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


# --- one request ------------------------------------------------------------------------------------------------

class Api:
    """Zoho Books' API for one organisation. `token(fresh=False)` is handed by the software: {token, api}, or {gone:
    words} (the grant is revoked or missing), or {off: words}."""

    def __init__(self, token, org: str = ""):
        self.token, self.org = token, org
        self.remaining: int | None = None
        self.reset = 0
        self._last = 0.0

    def call(self, method: str, path: str, params: dict | None = None, body: dict | None = None,
             files: dict | None = None, _again: bool = True) -> dict:
        got = self.token(not _again)
        if "gone" in got:
            raise Off("zoho: no grant", said=got["gone"])
        if "off" in got:
            raise Off("zoho: no token", said=got["off"])
        if self.remaining is not None and self.remaining <= LOW:
            raise Said(f"{NAME} allows only so many calls a day to one organisation, and today's are used up. "
                       f"Try again in {max(1, round(self.reset / 3600))} hour(s).")
        q = dict(params or {})
        if self.org:
            q["organization_id"] = self.org
        url = f"{got['api']}{path}" + (f"?{urllib.parse.urlencode(q)}" if q else "")
        headers = {"Authorization": f"Zoho-oauthtoken {got['token']}"}
        data = None
        if files:
            boundary = "----" + uuid.uuid4().hex
            parts = []
            for field, (name, content, ctype) in files.items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\n'
                             f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n")
            data = b"".join(parts) + f"--{boundary}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        wait = PACE_S - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        started = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers),
                                        timeout=60) as r:                      # noqa: S310 - Zoho
                status, head, raw = r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            status, head, raw = e.code, e.headers, e.read()
        except (urllib.error.URLError, OSError) as e:
            log.info("zoho %s %s: no answer (%s)", method, path, e)
            raise Off(str(e), said=f"{NAME} isn't answering.") from e
        self._last = time.monotonic()
        try:
            self.remaining = int(head.get("X-Rate-Limit-Remaining"))
            self.reset = int(head.get("X-Rate-Limit-Reset") or 0)
        except (TypeError, ValueError):
            pass
        try:
            out = json.loads(raw.decode("utf-8", "replace") or "{}")
        except ValueError:
            out = {}
        log.debug("zoho %s %s: %s in %.1fs (left today: %s)", method, path, status, self._last - started, self.remaining)
        if status == 401 and _again:
            return self.call(method, path, params, body, files, _again=False)
        if status == 401:
            raise Off("zoho: not allowed", said="Connect Zoho Books again in Settings.")
        if status == 429:
            if _again:
                time.sleep(min(60, max(5, self.reset if 0 < self.reset <= 60 else 30)))
                return self.call(method, path, params, body, files, _again=False)
            raise Said(f"{NAME} is busy with too many calls. Try again in a minute.")
        if out.get("code", 0) != 0 or status >= 400:
            raise Said(str(out.get("message") or f"{NAME} said no ({status})"), out.get("code"))
        return out

    def get(self, path: str, **params) -> dict:
        return self.call("GET", path, params)

    def pages(self, path: str, key: str, **params) -> list[dict]:
        out, page = [], 1
        while True:
            got = self.call("GET", path, {**params, "page": page, "per_page": 200})
            out += got.get(key) or []
            if not (got.get("page_context") or {}).get("has_more_page") or page > 50:
                return out
            page += 1


# --- reading the books ------------------------------------------------------------------------------------------

def _zoho_shaped(number: str, prefix: str) -> bool:
    """Is this number prefix + digits, the way Zoho's own series makes them?"""
    return number.startswith(prefix) and number[len(prefix):].isdigit() and bool(number[len(prefix):])


def organisations(api: Api) -> list[dict]:
    got = api.get("/organizations").get("organizations") or []
    return [{"id": str(o["organization_id"]), "name": o.get("name", ""), "state": o.get("state", "")} for o in got]


def org_gstin(api: Api, org_id: str) -> str:
    o = api.call("GET", f"/organizations/{org_id}", {}).get("organization") or {}
    return str((o.get("tax_settings") or {}).get("tax_reg_no") or "").strip().upper()


def _fy_of(date: str) -> int:
    y, m = int(date[:4]), int(date[5:7])
    return y if m >= 4 else y - 1


def _invoices(api: Api, fy: int) -> list[dict]:
    return api.pages("/invoices", "invoices", date_start=f"{fy}-04-01", date_end=f"{fy + 1}-03-31")


def _placed(i: dict, fresh: bool, adopted: bool = False) -> dict:
    return {"number": i.get("invoice_number", ""), "mid": str(i.get("invoice_id", "")), "date": i.get("date", ""),
            "fresh": fresh, "adopted": adopted}


# --- one look at a month, and the import --------------------------------------------------------------------------

class Session:
    """One month of one ARN against the organisation connected in Zoho Books: what an import would do (`look`), doing it
    (`bring_in`), and a run's glance and place. Nothing is written by `look`."""

    def __init__(self, base: Path, period: str, profile: dict, token, *, company: str = "", org_id: str = "", which: str = "submitted",
                 last: str = "", answers: dict | None = None):
        # `company` is the organisation's name for display only; the organisation is chosen by `org_id`
        self.base, self.period, self.profile = base, period, profile
        self.arn = str(profile.get("arn") or base.name)
        self.month = Month(base, period) if period else None
        self.own = (profile.get("invoices") or {}).get("source") == "own"
        self.which = "all" if which == "all" else "submitted"
        self.asked_org, self.answers = org_id, dict(answers or {})
        self.remember: dict = _load(base / "zoho.json")
        self.api = Api(token)
        self.company = self.org_id = self.books_gstin = ""
        self.org_names: list[str] = []
        self.orgs: list[dict] = []
        self.rows: list[dict] = []
        self.creates: list[dict] = []
        self.asks: list[dict] = []
        self.warn: list[str] = []
        self.plan: dict[str, dict] = {}
        self.ids: dict[str, str] = {}              # key -> the invoice's id in Zoho, once placed or found
        self.run_mode = self.read_now = False
        self.fy = 0
        self.auto = False
        self.prefix = ""
        self.next_auto = ""
        self.invoices: list[dict] = []
        self.contacts: dict[str, list[dict]] = {}
        self.tax: dict[str, str] = {}

    # --- which organisation ----------------------------------------------------------------------------------------

    def connect(self) -> dict | None:
        """The organisation to work in, or the answer to give when there is none."""
        try:
            orgs = organisations(self.api)
        except Off as e:
            return {"state": "off", "said": e.said or f"{NAME} isn't answering."}
        except Said as e:
            return {"state": "off", "said": str(e)}
        self.org_names = [o["name"] for o in orgs]
        self.orgs = [{"id": o["id"], "name": o["name"]} for o in orgs]
        kept = (self.remember.get("org") or {})
        want = next((o for o in orgs if o["id"] == (self.asked_org or kept.get("id"))), None)
        if want is None and len(orgs) == 1 and not self.asked_org and not kept.get("id"):
            want = orgs[0]
        if want is None:
            return {"state": "pick", "companies": self.org_names,
                    "said": (f"{kept['name']} isn't one of your organisations in {NAME} any more." if kept.get("id") else "")}
        self.company, self.org_id = want["name"], want["id"]
        self.api.org = self.org_id
        if kept.get("id") != self.org_id:
            self.remember = {}                    # what was remembered belongs to another organisation's books
        try:
            self.books_gstin = org_gstin(self.api, self.org_id)
        except Off as e:
            return {"state": "off", "said": e.said or f"{NAME} isn't answering."}
        return None

    # --- the plan --------------------------------------------------------------------------------------------------

    def look(self) -> dict:
        stopped = self._guard(self.connect)
        if stopped:
            return self._answer(**stopped)
        rows = sorted(self.month.rows.values(), key=lambda r: (r["registrar"] != CAMS, str(r.get("amc", "")).lower()))
        out = self._guard(lambda: self._plan_all(rows))
        if out:
            return self._answer(**out)
        if self.read_now:
            self.month.save()
        return self._answer(state="ready")

    def _guard(self, call):
        """Run a step; a Zoho that stops answering is `off` with its words, a refusal of a read is `off` too."""
        try:
            return call()
        except Off as e:
            return {"state": "off", "said": e.said or f"{NAME} isn't answering."}
        except Said as e:
            return {"state": "off", "said": str(e)}

    def _plan_all(self, rows: list[dict]) -> None:
        mine = self._prepare(rows)
        used_by_hand: set[str] = set()
        for r in rows:
            self.rows.append(self._plan_one(r, mine, used_by_hand))
        self.plan = {p["key"]: p for p in self.rows}

    def _prepare(self, rows: list[dict]) -> str:
        dates = sorted(_when(r) for r in rows if _when(r))
        y, m = (int(dates[0][:4]), int(dates[0][5:7])) if dates else (datetime.now().year, datetime.now().month)
        self.fy = y if m >= 4 else y - 1
        s = self.api.get("/settings/invoices").get("invoice_settings") or {}
        self.prefix = str(s.get("ph_replaced_prefix") or s.get("prefix_string") or "")
        self.next_auto = f"{self.prefix}{s.get('next_number', '')}"
        self.invoices = _invoices(self.api, self.fy)
        latest = sorted(self.invoices, key=lambda i: i.get("created_time", ""))[-5:]
        self.auto = bool(s.get("auto_generate")) and all(_zoho_shaped(str(i.get("invoice_number", "")), self.prefix)
                                                         for i in latest)
        taxes = self.remember.get("tax") or {}
        if not taxes.get("gst18") or not taxes.get("igst18"):
            found = {t["tax_name"]: str(t["tax_id"]) for t in self.api.get("/settings/taxes").get("taxes") or []
                     if t.get("status", "Active") == "Active"}
            taxes = {"gst18": found.get("GST18", ""), "igst18": found.get("IGST18", "")}
        self.tax = taxes
        mine = str(self.profile.get("gstin") or "").strip().upper()
        if not self.books_gstin:
            self.warn.append(f"{self.company} has no GSTIN in {NAME}, so the tax on an invoice can't be worked out.")
        elif (mine and self.books_gstin != mine and self.answers.get("gstin") != "yes"
              and self.remember.get("gstin_ok") != self.books_gstin):
            self.asks.append({"id": "gstin", "options": ["yes"],
                              "question": f"{self.company}'s GSTIN in {NAME} is {self.books_gstin}. "
                                          f"Yours here is {mine}. Is this the right organisation?"})
        return mine

    def _gstin_of(self, r: dict, mine: str) -> str:
        """The fund house's GSTIN: kept on the invoice's row by the run that read it, else read off its PDF now."""
        if r.get("gstin"):
            return str(r["gstin"]).upper()
        from client.automation import files
        try:
            path = self.month.path(r.get("file") or "")
            text = " ".join(w["text"] for w in files.text_layer(path)["items"]) if path.is_file() else ""
        except Exception as err:                       # noqa: BLE001 - a PDF that will not open has no GSTIN to give
            log.info("zoho: %s could not be read for its GSTIN: %s", r.get("key"), err)
            text = ""
        printed = list(dict.fromkeys(GSTIN.findall(text.upper())))
        others = [g for g in printed if g != mine]
        if len(others) == 1 or (len(others) == 2 and mine not in printed):
            r["gstin"] = others[-1]
            self.read_now = True
            return r["gstin"]
        return ""

    def _customers(self, gstin: str) -> list[dict]:
        if gstin not in self.contacts:
            got = self.api.get("/contacts", gst_no=gstin).get("contacts") or []
            self.contacts[gstin] = [c for c in got if str(c.get("gst_no", "")).upper() == gstin
                                    and c.get("contact_type", "customer") == "customer"]
        return self.contacts[gstin]

    def _plan_one(self, r: dict, mine: str, used_by_hand: set[str]) -> dict:
        key, reg = r["key"], r["registrar"]
        taxable, cgst, sgst, igst = (_money(r.get(k) or 0) for k in ("taxable", "cgst", "sgst", "igst"))
        total = taxable + cgst + sgst + igst
        gstin = self._gstin_of(r, mine)
        submitted = words.status_of(r) in SUBMITTED
        number = "" if self.own else str(r.get("number") or key).strip()
        p = {"key": key, "registrar": reg, "amc": r.get("amc") or key, "date": _when(r), "total": float(total),
             "submitted": submitted, "gstin": gstin, "number": "", "will": number, "party": "", "partyNew": False,
             "sales": "", "action": "import", "note": "", "rid": f"{OURS}{self.arn}/{reg}/{key}",
             "_": {"taxable": taxable, "cgst": cgst, "sgst": sgst, "igst": igst, "total": total}}
        live = [i for i in self.invoices if i.get("status") != "void"]
        done = next((i for i in live if i.get("reference_number") == p["rid"]), None)
        if done:
            p.update(action="in_books", number=done.get("invoice_number", ""), party=done.get("customer_name", ""),
                     note=f"Already in your books as {done.get('invoice_number')}" if done.get("invoice_number")
                     else "Already in your books")
            p["_"]["invoice"] = done
            return p
        if self.own and not self.run_mode:
            return {**p, "action": "past" if submitted else "run", "will": "",
                    "note": "Already sent with its invoice number" if submitted else f"Goes into {NAME} when you run it"}
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
        if gstin[:2] not in GST_STATE:
            return {**p, "action": "stop", "note": f"{NAME} has no state for the GSTIN {gstin}."}
        if not (self.tax.get("gst18") and self.tax.get("igst18")):
            return {**p, "action": "stop", "note": f"{NAME} has no GST18 and IGST18 taxes in this organisation."}
        if not self.books_gstin:
            return {**p, "action": "stop", "note": f"{self.company} has no GSTIN in {NAME}."}
        if not self.own:
            if why := numbering.rule_46(number) or ("" if number else "It has no invoice number."):
                return {**p, "action": "stop", "note": f"{number or key}: {why}"}
            if any(i.get("invoice_number") == number for i in self.invoices):
                return {**p, "action": "stop", "note": f"{number} is already another invoice in {NAME}."}

        # the fund house: by GSTIN only
        found = self._customers(gstin)
        kept = (self.remember.get("party") or {}).get(gstin)
        said = self.answers.get(f"party:{gstin}")
        names = [c["contact_name"] for c in found]
        if said in names:
            p["party"] = said
        elif kept in names:
            p["party"] = kept
        elif len(found) == 1:
            p["party"] = names[0]
        elif len(found) > 1:
            if not any(a["id"] == f"party:{gstin}" for a in self.asks):
                self.asks.append({"id": f"party:{gstin}", "options": names,
                                  "question": f"{len(found)} of your customers carry {p['amc']}'s GSTIN. Which one is it?"})
            p.update(action="ask", note="Which customer is this fund house?")
            return p
        else:
            name = str(r.get("party") or p["amc"]).strip()
            p.update(party=name, partyNew=True)
            if not any(c["gstin"] == gstin for c in self.creates):
                self.creates.append({"kind": "party", "name": name, "gstin": gstin})
        contact = next((c for c in found if c["contact_name"] == p["party"]), None)
        p["_"]["contact"] = contact["contact_id"] if contact else ""

        # typed by hand already? the same customer, the same month, within a rupee, no reference
        if contact:
            hand = next((i for i in live if i.get("customer_id") == contact["contact_id"]
                         and str(i.get("date", ""))[:7] == p["date"][:7] and not i.get("reference_number")
                         and abs(D(str(i.get("total", 0))) - total) <= 1 and str(i["invoice_id"]) not in used_by_hand), None)
            if hand:
                used_by_hand.add(str(hand["invoice_id"]))
                p["_"]["hand"] = hand
                p.update(action="by_hand", number=hand.get("invoice_number", ""),
                         note=f"Looks typed by hand already: {hand.get('invoice_number')} on {hand.get('date')}, "
                              f"{words.inr(float(D(str(hand.get('total', 0)))))}")
        return p

    def _answer(self, state: str, **more) -> dict:
        public = [{k: v for k, v in p.items() if k not in ("_", "rid")} for p in self.rows]
        counts = {"submitted": sum(1 for p in self.rows if p["submitted"]), "all": len(self.rows),
                  "going": sum(1 for p in self.rows if p["action"] == "import"),
                  "byHand": sum(1 for p in self.rows if p["action"] == "by_hand"),
                  "inBooks": sum(1 for p in self.rows if p["action"] == "in_books")}
        label = words.labels(self.period)[0] if self.period else ""
        return {"kind": "zoho", "state": state, "said": "", "companies": self.org_names, "orgs": self.orgs, "orgId": self.org_id,
                "company": self.company, "period": self.period, "label": label, "own": self.own, "which": self.which, "vtype": "",
                "method": "", "tallyNumbers": False, "last": "", "askLast": False, "rows": public,
                "creates": self.creates, "asks": self.asks, "warn": self.warn, "counts": counts, **more}

    # --- a run: glance (reads only), place (writes one invoice), then attach and mark sent -------------------------

    def glance(self, keys: list[str]) -> dict:
        """What putting these open invoices of a run into Zoho Books would do. Nothing changes there. `state` is ready
        or what `connect` said (off, pick). When ready: `rows` (each with `action`, `note`, `block`), `asks`, `first`
        (no invoice yet this financial year, in the person's own series: the first invoice number is theirs to
        type), `after` and `renumbers` (never here), `peek` (the next invoice number, to be shown, not given)."""
        self.run_mode, self.which = True, "all"
        stopped = self._guard(self.connect)
        if stopped:
            return self._answer(**{**stopped, "company": self.remember.get("org", {}).get("name", "")})
        want = set(keys)
        rows = sorted((r for r in self.month.rows.values() if r["key"] in want),
                      key=lambda r: (_when(r), r["registrar"] != CAMS, str(r.get("amc", "")).lower()))
        out = self._guard(lambda: self._plan_all(rows))
        if out:
            return self._answer(**out)
        if self.read_now:
            self.month.save()
        for p in self.rows:
            if p["action"] in ("ask", "stop"):
                p["block"] = p["note"]
        first, peek = None, ""
        try:
            if self.auto:
                peek = self.next_auto
            else:
                top = self._top(self.invoices)
                if top:
                    peek = numbering.bump(top, numbering.default_counter(top))
                elif any(p["action"] == "import" for p in self.rows):
                    first = {"fy": numbering.fy_of(f"{self.fy}-04-01"), "proposed": self._first_of_year()}
                    peek = first["proposed"]
        except Off as e:
            return self._answer("off", said=e.said or f"{NAME} isn't answering.")
        return {**self._answer("ready"), "first": first, "after": self._after_month(), "peek": peek, "renumbers": False}

    def _after_month(self) -> str:
        """The name of the month of the newest invoice in the person's own series this financial year, when an invoice
        going in is dated before it (it takes the numbers after that month's); else ''."""
        live = sorted((i for i in self.invoices if i.get("invoice_number") and i.get("status") != "void"),
                      key=lambda i: i.get("created_time", ""))
        dates = [p["date"] for p in self.rows if p["action"] == "import" and not p.get("block") and p.get("date")]
        if not live or not dates:
            return ""
        sample = str(live[-1]["invoice_number"])
        at = numbering.default_counter(sample)
        if at < 0:
            return ""
        series = []
        for i in live:
            try:
                if numbering.shape(str(i["invoice_number"]), at) == numbering.shape(sample, at):
                    series.append(str(i.get("date", "")))
            except numbering.NumberError:
                continue
        newest = max(series, default="")
        if newest[:7] > max(dates)[:7]:
            return datetime.strptime(newest[:10], "%Y-%m-%d").strftime("%B")
        return ""

    def _top(self, invoices: list[dict]) -> str:
        """The highest invoice number of the person's own shape: the shape of their newest invoice."""
        live = sorted((i for i in invoices if i.get("invoice_number")), key=lambda i: i.get("created_time", ""))
        if not live:
            return ""
        sample = str(live[-1]["invoice_number"])
        at = numbering.default_counter(sample)
        return numbering.highest([str(i["invoice_number"]) for i in live], sample, at) if at >= 0 else ""

    def _first_of_year(self) -> str:
        prev = sorted((i for i in _invoices(self.api, self.fy - 1) if i.get("invoice_number")),
                      key=lambda i: i.get("created_time", ""))
        if not prev:
            return ""
        at = numbering.default_counter(str(prev[-1]["invoice_number"]))
        return numbering.next_year(str(prev[-1]["invoice_number"]), at) if at >= 0 else ""

    def place(self, key: str, first: str = "") -> dict:
        """Put one invoice into Zoho Books and read its number back: {number, mid, date, fresh, adopted}. Already there
        (found by our id): its number, nothing written. Typed by hand: changed to the registrar's figures, keeping its
        number. Raises `Refused` with Zoho's words, and `Off` when Zoho stops answering (ask again: nothing is written
        twice). The customer used is remembered for the next time."""
        got = self._place(key, first)
        self.ids[key] = got["mid"]
        if got["fresh"]:
            self._remember([self.plan[key]], {key})
        return got

    def _by_ref(self, rid: str) -> dict | None:
        got = self.api.get("/invoices", reference_number=rid).get("invoices") or []
        return next((i for i in got if i.get("reference_number") == rid and i.get("status") != "void"), None)

    def _place(self, key: str, first: str) -> dict:
        p = self.plan.get(key)
        if not p:
            raise Refused(f"This invoice wasn't part of the look at {NAME}.")
        if p.get("block"):
            raise Refused(p["block"])
        have = self._by_ref(p["rid"])
        if have:
            return _placed(have, fresh=False)
        contact = p["_"].get("contact") or self._customer_now(p)
        hand = p["_"].get("hand") if p["action"] == "by_hand" else None
        if hand:
            now = self.api.get(f"/invoices/{hand['invoice_id']}").get("invoice") or {}
            if now.get("reference_number"):
                hand = None                                             # someone gave it a reference since the look
        if hand:
            got = self.api.call("PUT", f"/invoices/{hand['invoice_id']}", body=self._body(p, contact, ""))
            return _placed(got.get("invoice") or hand, fresh=True, adopted=True)
        send = not self.auto if self.own else True
        number = ""
        for _try in range(6):
            number = self._next(first) if (self.own and send) else (p["will"] if not self.own else "")
            try:
                got = self.api.call("POST", "/invoices", {"ignore_auto_number_generation": "true"} if number else {},
                                    self._body(p, contact, number))
                break
            except Said as e:
                if e.code == 1001 and number and self.own:
                    continue                                          # taken between our look and our write
                raise
        else:
            raise Refused(f"{NAME} refused the invoice number {number}.")
        invoice = got.get("invoice") or {}
        if abs(D(str(invoice.get("total", 0))) - p["_"]["total"]) > D("0.01"):
            log.warning("zoho: %s came to %s there and %s here", key, invoice.get("total"), p["_"]["total"])
        return _placed(invoice, fresh=True)

    def _next(self, first: str) -> str:
        """The invoice number after the highest of the person's own series this year, or `first`."""
        top = self._top(_invoices(self.api, self.fy))
        number = numbering.bump(top, numbering.default_counter(top)) if top else (first or "").strip()
        if not number:
            raise Refused(f"Your {NAME} has no invoice yet this financial year. Type the first invoice number.")
        if why := numbering.rule_46(number):
            raise Refused(f"{number}: {why}")
        return number

    def _customer_now(self, p: dict) -> str:
        """The customer for a fund house the look found none for: one made by an invoice just before this one is
        used (two new invoices of one fund house make one customer), else made now."""
        self.contacts.pop(p["gstin"], None)
        found = self._customers(p["gstin"])
        kept = (self.remember.get("party") or {}).get(p["gstin"])
        mine = next((c for c in found if c["contact_name"] == kept), None) if len(found) > 1 else None
        if len(found) == 1 or mine:
            c = mine or found[0]
            p["party"] = c["contact_name"]
            return str(c["contact_id"])
        if found:
            raise Refused(f"{len(found)} of your customers carry {p['amc']}'s GSTIN. Which one is it?")
        return self._make_customer(p)

    def _make_customer(self, p: dict) -> str:
        name = p["party"]
        for tried in (name, f"{name} ({p['gstin']})"):
            try:
                got = self.api.call("POST", "/contacts", body={
                    "contact_name": tried, "company_name": tried, "contact_type": "customer", "gst_no": p["gstin"],
                    "gst_treatment": "business_gst", "place_of_contact": GST_STATE[p["gstin"][:2]]})
            except Said as e:
                if e.code == 3062 and tried == name:
                    continue                                              # that name is taken by another customer
                raise Refused(f"{NAME} didn't make the customer '{tried}': {e}") from e
            c = got.get("contact") or {}
            self.contacts.pop(p["gstin"], None)
            p["party"] = tried
            return str(c.get("contact_id"))
        raise Refused(f"{NAME} didn't make the customer '{name}'.")

    def _body(self, p: dict, contact: str, number: str) -> dict:
        f = p["_"]
        state = GST_STATE[p["gstin"][:2]]
        tax = self.tax["igst18"] if f["igst"] else self.tax["gst18"]
        label = words.labels(self.period)[0]
        body = {"customer_id": contact, "date": p["date"], "place_of_supply": state, "gst_treatment": "business_gst",
                "reference_number": p["rid"],
                "line_items": [{"name": "Commission", "description": f"Commission for {label} ({NAMES.get(p['registrar'], p['registrar'])})",
                                "rate": float(f["taxable"]), "quantity": 1, "tax_id": tax, "hsn_or_sac": SAC}]}
        if number:
            body["invoice_number"] = number
        return body

    def _invoice_id(self, key: str) -> str:
        if key not in self.ids:
            p = self.plan.get(key)
            have = self._by_ref(p["rid"]) if p else None
            if not have:
                raise Refused("This invoice isn't in Zoho Books.")
            self.ids[key] = str(have["invoice_id"])
        return self.ids[key]

    def after_sign(self, key: str, pdf: Path) -> dict:
        """The signed PDF onto the invoice in Zoho Books (once: a file of that name already there is left)."""
        iid = self._invoice_id(key)
        have = self.api.get(f"/invoices/{iid}").get("invoice") or {}
        if any(d.get("file_name") == pdf.name for d in have.get("documents") or []):
            return {"done": True}
        self.api.call("POST", f"/invoices/{iid}/attachment", files={"attachment": (pdf.name, pdf.read_bytes(), "application/pdf")})
        return {"done": True}

    def after_submit(self, key: str) -> dict:
        """The registrar has taken the invoice: marked sent in Zoho Books (never emailed). A draft only."""
        iid = self._invoice_id(key)
        have = self.api.get(f"/invoices/{iid}").get("invoice") or {}
        if have.get("status") == "draft":
            self.api.call("POST", f"/invoices/{iid}/status/sent")
        return {"done": True}

    def answer(self, answers: dict[str, str]) -> None:
        self.answers.update(answers)
        keep_answers(self.base, answers, self.books_gstin)

    # --- the import (the registrar's invoices) -----------------------------------------------------------------------

    def bring_in(self, adopt: list[str] | None = None) -> dict:
        """Put the month in. `adopt`: the invoices typed by hand that the person said to change to the registrar's
        figures. Returns the look afterwards, with `done`: what happened."""
        before = self.look()
        if before["state"] != "ready":
            return before
        adopt_keys = set(adopt or [])
        done = {"imported": [], "adopted": [], "refused": [], "numbers": [], "stoppedAt": ""}
        sending = [p for p in self.rows if p["action"] == "import"] \
            + [p for p in self.rows if p["action"] == "by_hand" and p["key"] in adopt_keys]
        went = set()
        try:
            for p in sending:
                hand = p["action"] == "by_hand"
                try:
                    got = self.place(p["key"])
                    row = self.month.rows.get(p["key"]) or {}
                    pdf = self.month.path(row.get("file") or "") if row.get("file") else None
                    if pdf and pdf.is_file():
                        self.after_sign(p["key"], pdf)
                    if p["submitted"]:
                        self.after_submit(p["key"])
                except Refused as e:
                    done["refused"].append({"key": p["key"], "amc": p["amc"], "said": str(e)})
                    continue
                went.add(p["key"])
                done["adopted" if hand else "imported"].append(p["key"])
                self.month.put(p["registrar"], p["key"], books=got["number"] or "in", booksAt=_now())
                if got["number"] and not hand:
                    done["numbers"].append(got["number"])
            self.month.save()
            self._remember([p for p in sending if p["key"] in went], went)
        except Off as e:
            done["stoppedAt"] = (e.said or f"{NAME} isn't answering") + " Look again to see what went in."
            self.month.save()
            return {**before, "done": done}
        again = Session(self.base, self.period, self.profile, self.api.token, org_id=self.org_id, which=self.which,
                        answers=self.answers)
        out = again.look()
        said = {x["key"]: x["said"] for x in done["refused"]}
        for row in out.get("rows", []):
            if row["key"] in said:
                row["refused"] = said[row["key"]]
        return {**out, "done": done}

    def _remember(self, sent: list[dict], went: set[str]) -> None:
        sure = self.answers.get("gstin") == "yes" or self.remember.get("gstin_ok") == self.books_gstin
        keep = {"org": {"id": self.org_id, "name": self.company, "gstin": self.books_gstin},
                **({"gstin_ok": self.books_gstin} if sure else {}), "tax": self.tax,
                "party": dict(self.remember.get("party") or {})}
        for p in sent:
            if p["key"] in went and p["party"]:
                keep["party"][p["gstin"]] = p["party"]
        _write(self.base / "zoho.json", keep)
        self.remember = keep


# --- setup, Settings -----------------------------------------------------------------------------------------------

def setup_look(token, gstin: str) -> dict:
    """Setup's Books step: is Zoho Books answering, which organisations the person has, each one's GSTIN beside this
    ARN's. Reads only."""
    api = Api(token)
    try:
        orgs = organisations(api)
        mine, out = gstin.strip().upper(), []
        for o in orgs:
            theirs = org_gstin(api, o["id"])
            out.append({"id": o["id"], "name": o["name"], "gstin": theirs, "same": bool(mine) and theirs == mine})
    except Off as e:
        return {"state": "off", "said": e.said or f"{NAME} isn't answering.", "orgs": []}
    except Said as e:
        return {"state": "off", "said": str(e), "orgs": []}
    return {"state": "ready", "said": "", "orgs": out}


def books_next(token, base: Path, org_id: str = "") -> dict:
    """Where the person's own invoice numbers continue from, for setup's line: {state, company, last, next, at,
    method}. Reads only."""
    s = Session(base, "", {"arn": base.name}, token, org_id=org_id)
    stopped = s.connect()
    if stopped:
        return {"state": stopped["state"], "company": "", "last": "", "next": "", "at": -1, "method": ""}
    now = datetime.now()
    s.fy = now.year if now.month >= 4 else now.year - 1
    try:
        st = s.api.get("/settings/invoices").get("invoice_settings") or {}
        prefix = str(st.get("ph_replaced_prefix") or st.get("prefix_string") or "")
        invoices = _invoices(s.api, s.fy)
        latest = sorted(invoices, key=lambda i: i.get("created_time", ""))[-5:]
        auto = bool(st.get("auto_generate")) and all(_zoho_shaped(str(i.get("invoice_number", "")), prefix) for i in latest)
        if auto:
            nxt = f"{prefix}{st.get('next_number', '')}"
            return {"state": "ready", "company": s.company, "last": "", "next": nxt, "at": numbering.default_counter(nxt),
                    "method": "automatic"}
        last = s._top(invoices)
        nxt = numbering.bump(last, numbering.default_counter(last)) if last else s._first_of_year()
    except (Off, Said):
        return {"state": "off", "company": "", "last": "", "next": "", "at": -1, "method": ""}
    return {"state": "ready", "company": s.company, "last": last, "next": nxt,
            "at": numbering.default_counter(nxt or last) if (nxt or last) else -1, "method": "own"}


def keep_org(base: Path, org_id: str, name: str, gstin: str = "", sure: bool = False) -> None:
    """The organisation chosen at setup: the first look goes straight to it. What was kept for another is dropped.
    `sure`: the person ticked "This is the right organisation" for a GSTIN that isn't theirs."""
    kept = _load(base / "zoho.json")
    if (kept.get("org") or {}).get("id") != org_id:
        kept = {}
    _write(base / "zoho.json", {**kept, "org": {"id": org_id, "name": name, "gstin": gstin.strip().upper()},
                                **({"gstin_ok": gstin.strip().upper()} if sure else {})})


def keep_answers(base: Path, answers: dict, books_gstin: str = "") -> None:
    """The person's answers to Zoho Books' questions in a run (which customer, that the organisation is theirs),
    remembered at once, so they are never asked twice."""
    kept = _load(base / "zoho.json")
    for id_, value in answers.items():
        if id_.startswith("party:"):
            kept.setdefault("party", {})[id_[6:]] = value
        elif id_ == "gstin" and value == "yes" and books_gstin:
            kept["gstin_ok"] = books_gstin
    _write(base / "zoho.json", kept)


def forget(base: Path) -> None:
    (base / "zoho.json").unlink(missing_ok=True)


def remembered(base: Path) -> dict:
    kept = _load(base / "zoho.json")
    org = kept.get("org") or {}
    return {"company": org.get("name", ""), "gstin": org.get("gstin", ""), "ledgers": len(kept.get("party") or {})}
