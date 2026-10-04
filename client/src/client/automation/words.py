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

# Words that mean an invoice is already with KFintech. Matched as substrings: the portal writes sentences
# ("Accepted & Payment pending"), and an exact-match list would miss one and send the invoice again.
KFIN_DONE = ("ACCEPT", "PAID", "PROCESSED", "APPROVED", "SUBMITTED", "UPLOADED")

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


def is_final(registrar: str, status: str | None) -> bool:
    """Is this invoice already with its registrar, so that sending it again would be a duplicate?

    CAMS: anything its Invoice Status page lists at all, except a rejection. That page lists an invoice only once it
    has been uploaded, so "PENDING" there means "we have it, waiting on approval".
    KFintech: the words in KFIN_DONE, as substrings. Its own pending and rejected are open.
    A rejection is never final on either: that is the invoice coming back to be sent again.
    """
    s = (status or "").strip().upper()
    if not s or "REJECT" in s:
        return False
    if registrar == CAMS:
        return True
    return any(word in s for word in KFIN_DONE)


def status_of(row: dict) -> str:
    """One invoice's status in the window's words. The registrar's own word is kept beside it (`said`)."""
    said = str(row.get("said") or "").strip()
    s = said.upper()
    if "REJECT" in s:
        return "Rejected"
    if row["registrar"] == CAMS and s:
        return "Paid" if "PAID" in s else "Approved" if "APPROV" in s else "Waiting approval"
    if row["registrar"] == KFIN and s:
        if re.search(r"\bPAID\b|PROCESSED", s):
            return "Paid"
        if "ACCEPT" in s or "APPROV" in s:
            return "Approved"
        if is_final(KFIN, said):
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
