"""An example invoice, for the preview in setup and Settings: a made-up fund house and figures, in the person's own
format, before anything has been fetched."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from client.automation.invoices import layout
from client.automation.invoices.money import money
from client.automation.invoices.templates import TEMPLATES


def particulars(wording: str, with_fund_house: bool, fund_house: str) -> str:
    wording = (wording or "Commission").strip()
    return f"{fund_house} {wording}".strip() if with_fund_house and fund_house else wording


def sample(settings: dict, number: str, name: str, gstin: str) -> tuple[dict, layout.Invoice, layout.Seller]:
    """(template, invoice, seller) for the preview. `settings` is the window's InvoiceSettings."""
    me = layout.Seller(name=name or "Your name", gstin=gstin or "27ABCPM1234F1Z3",
                       address=[str(a).strip() for a in settings.get("address") or [] if str(a).strip()][:8],
                       phone=str(settings.get("phone") or ""), email=str(settings.get("email") or ""),
                       website=str(settings.get("website") or ""), remarks=str(settings.get("remarks") or ""))
    party = layout.Party(name="Aditya Birla Sun Life Mutual Fund", gstin="27AAATB0102C1ZR",
                         address=["One World Center, Tower 1", "17th Floor, Jupiter Mill Compound",
                                  "841, Senapati Bapat Marg, Elphinstone Road", "Mumbai - 400013"])
    taxable = Decimal("18740.00")
    half = money(taxable * Decimal("0.09"))
    inv = layout.Invoice(number=number or "1", date=date.today(), party=party, period_label="Commission",
                         particulars=particulars(str(settings.get("particulars") or ""),
                                                 bool(settings.get("particularsAmc", True)), "Aditya Birla Sun Life"),
                         taxable=taxable, cgst=half, sgst=half)
    return TEMPLATES.get(settings.get("template") or "tally", TEMPLATES["tally"]), inv, me
