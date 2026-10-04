"""The person's own invoice: drawn from the registrar's figures in their own format and number series, and signed in
the same pass.

The registrar supplies the figures and the fund house; the person supplies the format, their details and the number.
What must agree with the portal (the fund house's GSTIN, the invoice date, the taxable value, the GST split) is the
registrar's own, to the paisa: a rounding difference is a rejection.

One file per invoice: it is named for the fund house and the registrar's own reference, not for the number in it, so
drawing it again replaces it.

IGST has no layout yet (no Tally IGST invoice has been seen, and none is invented), so an invoice charged IGST is not
drawn: `drawable` says why, and the run sets it aside.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from client.automation import words
from client.automation.invoices import layout
from client.automation.invoices.money import money
from client.automation.invoices.sample import particulars
from client.automation.invoices.templates import TEMPLATES


def file_name(key: str, fund_house: str) -> str:
    """'BM/26-27/E/5', 'Aditya Birla Sun Life' -> 'Aditya_Birla_Sun_Life_BM26-27E5.pdf': safe in a zip and in CAMS's
    Excel, and the same for every drawing of that invoice, whatever number it carries."""
    safe = lambda s: re.sub(r"[^A-Za-z0-9-]+", "_", s).strip("_")  # noqa: E731
    return f"{safe(fund_house)}_{safe(key.replace('/', ''))}.pdf".lstrip("_")


def drawable(item: dict) -> str:
    """Why this invoice cannot be drawn as the person's own, or '' when it can."""
    if money(item["igst"] or 0):
        return "Charged IGST, which your own invoice doesn't do yet"
    if not item.get("party") or not item.get("date"):
        return "Its fund house or date couldn't be read"
    return ""


def draw(host, item: dict, number: str, period: str, folder: Path) -> Path:
    """Draw one invoice with this number, signed the person's way. It replaces any earlier drawing of itself."""
    p = host.profile
    s = p["invoices"]["settings"]
    me = layout.Seller(name=p["name"], gstin=p["gstin"],
                       address=[str(a).strip() for a in s.get("address") or [] if str(a).strip()][:8],
                       phone=str(s.get("phone") or ""), email=str(s.get("email") or ""),
                       website=str(s.get("website") or ""), remarks=str(s.get("remarks") or ""))
    template = TEMPLATES.get(s.get("template") or "tally", TEMPLATES["tally"])
    page_w, page_h = template["page"]
    inv = layout.Invoice(number=number, date=date.fromisoformat(item["date"]), party=item["party"],
                         period_label=words.commission_label(period),
                         particulars=particulars(str(s.get("particulars") or ""), bool(s.get("particularsAmc", True)),
                                                 item["house"]),
                         taxable=money(item["taxable"]), cgst=money(item["cgst"] or 0), sgst=money(item["sgst"] or 0),
                         igst=money(item["igst"] or 0))
    ops = layout.sign(layout.draw(template, inv, me), host.signature(), page_w, page_h)
    out = folder / file_name(item["key"], item["house"])
    host.draw(out, page_w, page_h, ops)
    return out
