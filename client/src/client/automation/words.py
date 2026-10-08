"""Months, names, amounts and statuses, in the words a person uses.

A month is named by CAMS's payment month, "OCT-2026": the month the commission is paid in. KFintech lists the same
invoices under the month before (its trail month, "September 2026").
"""

from __future__ import annotations

import re
from datetime import date, datetime

CAMS, KFIN = "CAMS", "KFINTECH"
NAMES = {CAMS: "CAMS", KFIN: "KFintech"}

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
        "November", "December"]

# The status words the two registrars wrote on 7 Oct 2026, compared after `norm`, whole, never as substrings. What each
# means: "open" the registrar does not have it, so it can be sent; "with" it has it and has not decided, so it must not
# be sent again; "done" approved; "rejected" it came back, to be sent again. A word not listed is unknown, and a run
# that meets one stops and shows it (`Month.read_status`): a guess could send an invoice twice or never.
CAMS_WORDS = {"FILE NOT UPLOADED": "open", "APPROVED": "done", "REJECTED": "rejected"}
KFIN_WORDS = {"SIGNED INVOICE UPLOAD PENDING": "open", "UPLOADED & VERIFICATION PENDING": "with",
              "PAYMENT PROCESSED": "done"}

# The fund houses CAMS names by a code, for when neither its report nor the invoice gives the name. Read off the
# September 2026 mailback: the code in each PDF's file name against the name printed on that invoice.
CAMS_CODES = {
    "B": "Aditya Birla Sun Life", "FTI": "Franklin Templeton", "H": "HDFC", "K": "Kotak Mahindra", "L": "SBI",
    "MM": "Mahindra Manulife", "P": "ICICI Prudential", "PP": "PPFAS", "T": "Tata", "Y": "WhiteOak Capital",
}


def this_period(today: date | None = None) -> str:
    d = today or date.today()
    return f"{MONTHS[d.month - 1]}-{d.year}"


def labels(period: str) -> tuple[str, str]:
    """'SEP-2026' -> ('September 2026', 'August 2026'): CAMS's month, and KFintech's name for the same invoices."""
    m, y = period.split("-")
    i = MONTHS.index(m.upper())
    return f"{LONG[i]} {y}", f"{LONG[i - 1]} {int(y) - (1 if i == 0 else 0)}"


def month_name(period: str) -> str:
    return labels(period)[0].split(" ")[0]


def commission_label(period: str) -> str:
    """What the month's commission is called on the person's own invoice: 'SEP-2026' -> 'Aug Commission'."""
    m, _ = period.split("-")
    return f"{MONTHS[MONTHS.index(m.upper()) - 1].title()} Commission"


def norm(said: str | None) -> str:
    """A registrar's words, ready to compare: case, runs of spaces and a closing full stop do not matter."""
    return re.sub(r"\s+", " ", (said or "").strip().rstrip(".").strip().upper())


def meaning(registrar: str, said: str | None) -> str:
    """'open', 'with', 'done', 'rejected' or 'unknown': what the registrar's status words mean (see CAMS_WORDS)."""
    s = norm(said)
    # only the exact known words count: KFintech's rejection word has not been seen, so it is unknown until it is
    return (CAMS_WORDS if registrar == CAMS else KFIN_WORDS).get(s) or "unknown"


def is_final(registrar: str, status: str | None) -> bool:
    """Is this invoice already with its registrar, so that sending it again would be a duplicate? A rejection is not:
    that is the invoice coming back to be sent again. An unknown word is not either; the run stops on it first."""
    return meaning(registrar, status) in ("with", "done")


def status_of(row: dict) -> str:
    """One invoice's status in the window's words. The registrar's own word is kept beside it (`said`). The final
    state of both registrars is "Approved"."""
    said = str(row.get("said") or "").strip()
    got = meaning(row["registrar"], said) if said else ""
    if got == "rejected":
        return "Rejected"
    if got == "done":
        return "Approved"
    if got == "with":
        return "Waiting approval"
    if row.get("sentAt"):
        return "Submitted"
    if row.get("signedAt"):
        return "Signed"
    return "Fetched"


def fund_house(name: str | None, code: str | None = "", registrar: str = CAMS) -> str:
    """The fund house as the person knows it: 'Aditya Birla Sun Life Mutual Fund' -> 'Aditya Birla Sun Life'."""
    n = re.sub(r"\s+", " ", str(name or "")).strip()
    n = re.sub(r"\s+mutual\s+fund\s*$", "", n, flags=re.I).strip(" -,")
    if n:
        return n
    c = str(code or "").strip()
    if registrar == CAMS and c.upper() in CAMS_CODES:
        return CAMS_CODES[c.upper()]
    return c


def _lines(items: list[dict]) -> list[str]:
    """A PDF's first page as lines of text, top to bottom, each read left to right. The text layer lists words in the
    order the PDF holds them, which on a CAMS invoice interleaves the label column with the values."""
    rows: dict[int, list[dict]] = {}
    for w in items:
        if int(w.get("page", 1)) == 1:
            rows.setdefault(round(float(w["y"])), []).append(w)
    return [" ".join(w["text"] for w in sorted(ws, key=lambda w: float(w["x"])))
            for _y, ws in sorted(rows.items(), key=lambda kv: -kv[0])]


def name_on_invoice(items: list[dict]) -> str:
    """The fund house's name as a CAMS invoice prints it: the line under 'Invoice No', ending in its GSTIN."""
    below = False
    for text in _lines(items):
        if text.startswith("Invoice No"):
            below = True
            continue
        if below and "GSTIN" in text:
            return text.split("GSTIN")[0].strip()
    return ""


def date_on_invoice(items: list[dict]) -> str:
    """'Invoice Date :September 07, 2026' -> '2026-09-07'."""
    found = re.search(r"Invoice Date\s*:\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", "\n".join(_lines(items)))
    if not found:
        return ""
    try:
        return datetime.strptime(" ".join(found.groups()), "%B %d %Y").date().isoformat()
    except ValueError:
        return ""


def iso_date(text: str) -> str:
    """A date as a KFintech sheet prints it, as ISO. Unknown spellings are left out."""
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%Y-%m-%d", "%d %b %Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(str(text).strip()[:11], fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def inr(amount: float) -> str:
    """₹1,23,456.78, the way the person writes it."""
    neg, amount = amount < 0, abs(round(float(amount), 2))
    whole, paise = f"{amount:.2f}".split(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    body = ",".join(groups + [tail]) if groups else tail
    return f"{'-' if neg else ''}₹{body}.{paise}"


def amount(v) -> float:
    try:
        return float(str(v).replace(",", "").replace("₹", "").strip() or 0)
    except ValueError:
        return 0.0


def plural(n: int, one: str, many: str = "") -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"
