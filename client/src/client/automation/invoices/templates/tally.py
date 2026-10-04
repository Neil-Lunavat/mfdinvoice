"""The Tally "Tax Invoice" standard print, as data.

Every coordinate here was measured from a distributor's Tally-exported PDFs (US Letter, Arial, top-origin points; text
placed by its top edge, as pdfplumber reports it) and is exactly what the first desktop app's `client/invoice/render.py`
drew, checked against seventeen real Tally invoices. Tally's own rules, which the engine carries out:

  - an address block prints at 9.96 pt on 11.40 pt lines; more lines than fit are squeezed vertically into the box
    while keeping their width; no address still takes one blank line
  - a value too wide for its column is compressed horizontally (the item name, the total amount)
  - the bottom of the page is fixed: when the amount or the tax in words wraps, everything above it moves up and the
    item table gets shorter (the shifts `s` and `s_tax` below)

Only intra-state invoices (CGST + SGST) have ever been seen from Tally. There is no IGST layout, and none is invented:
an IGST invoice is refused before it is drawn (`layout.IgstNotDrawn`).

A vertical coordinate is either a number or `Y(base, var=coef, ...)`: base plus each shift times its coefficient.
Text is `{placeholder}` filled from the invoice's facts (`layout.facts`).
"""

from __future__ import annotations

from client.automation.invoices.layout import ASCENT, BIG, BOLD, ITAL, LINE, REG, B, L, T, W, Y

THIN = 0.24
PARTY_RIGHT = 271.5            # Tally squeezes a long party line to end here (the column rule is at 274.1)
COLS = (50.16, 242.04, 289.20, 320.52, 367.68, 414.84, 435.60)


def _party(dy: float, block: str) -> list:
    """Consignee (dy=0) or Buyer (dy=98.04): the fund house's name, its address block, its GSTIN and state."""
    after = 9.42 - ASCENT * BIG
    return [
        T("{amc}", 38.76, 144.30 + dy, BOLD, BIG, maxw=PARTY_RIGHT - 38.76),
        B("amc_address", 38.76, 154.26 + dy, 49.68, id=block, right=PARTY_RIGHT),
        T("GSTIN/UIN", 38.76, after, REG, BIG, after=block),
        T(":", 116.55, after, REG, BIG, after=block),
        T("{amc_gstin}", 124.22, after, REG, BIG, after=block),
        T("State Name ", 38.76, after + LINE, REG, BIG, after=block),
        T(":", 116.55, after + LINE, REG, BIG, after=block),
        T("{amc_state}, Code : {amc_state_code}", 124.22, after + LINE, REG, BIG, after=block),
    ]


def _hsn_row(font: str, top: float, total: bool) -> list:
    at = Y(top, s_tax=-1)
    row = [T("{taxable}", 281.61, at, font, 9, "right"), T("{cgst}", 365.36, at, font, 9, "right"),
           T("{sgst}", 449.12, at, font, 9, "right"), T("{tax}", 501.59, at, font, 9, "right")]
    if total:
        return [T("Total", 229.17, at, font, 9, "right"), *row]
    return [T("{hsn}", 38.76, at, font, 9), T("{half}%", 312.92, at, font, 9, "right"),
            T("{half}%", 396.68, at, font, 9, "right"), *row]


def _t(dy: float) -> Y:
    """A line of the HSN summary table, which sits `s_tax` higher when the tax in words wraps."""
    return Y(513.12 + dy, s_tax=-1)


LABELS = (
    ("Invoice No.", 276.84, 55.30), ("Dated", 391.44, 55.30),
    ("Delivery Note", 276.84, 80.74), ("Mode/Terms of Payment", 391.44, 80.74),
    ("Reference No. & Date.", 276.84, 106.18), ("Other References", 391.44, 106.18),
    ("Buyer's Order No.", 276.84, 131.62), ("Dated", 391.44, 131.62),
    ("Dispatch Doc No.", 276.84, 157.06), ("Delivery Note Date", 391.44, 157.06),
    ("Dispatched through", 276.84, 182.50), ("Destination", 391.44, 182.50),
    ("Terms of Delivery", 276.84, 207.94),
)
ITEM_HEADS = (
    ("Particulars", 122.28, 327.46), ("HSN/SAC", 245.76, 327.46), ("GST", 295.80, 327.46),
    ("Rate", 295.44, 338.86), ("Quantity", 327.48, 327.46), ("Rate", 381.84, 327.46),
    ("per", 418.80, 327.46), ("Amount", 454.29, 327.46),
)
HSN_HEADS = (
    ("HSN/SAC", 111.24, 514.18), ("Taxable", 241.68, 514.18), ("CGST", 313.32, 514.18),
    ("SGST/UTGST", 381.12, 514.18), ("Total", 467.73, 514.18), ("Value", 246.24, 524.50),
    ("Rate", 290.16, 524.50), ("Amount", 326.04, 524.50), ("Rate", 373.92, 524.50),
    ("Amount", 409.80, 524.50), ("Tax Amount", 454.08, 524.50),
)

TEMPLATE = {
    "page": (612.0, 792.0),
    # the text that may wrap, and how wide it may run
    "wraps": {"amount_words": (BOLD, BIG, 463.0), "tax_words": (BOLD, BIG, 371.4)},
    # how far things move up when a text wraps: coefficient times (its lines - 1)
    "shifts": {"s_tax": {"tax_words": 11.88}, "s": {"tax_words": 11.88, "amount_words": 11.88},
               "tax_up": {"tax_words": 11.87}},
    "elements": [
        # title
        T("Tax Invoice", 267.5, 19.69, BOLD, 12, "center"),
        T("{month_year}", 267.5, 33.10, REG, 9, "center"),

        # frame and the right-hand header grid
        L(36.00, 54.24, 504.00, 54.24), L(36.00, 54.24, 36.00, 326.16), L(503.88, 54.24, 503.88, 326.16),
        L(274.08, 54.36, 274.08, 326.04), L(388.80, 54.36, 388.80, 207.00),
        *[seg for y in (79.68, 105.12, 130.56, 156.00, 181.44, 206.88)
          for seg in (L(274.32, y, 388.80, y), L(388.92, y, 503.52, y))],
        L(36.12, 129.84, 273.96, 129.84), L(36.12, 227.88, 273.96, 227.88), L(36.00, 326.04, 504.00, 326.04),
        *[T(label, x, top, REG, 9) for label, x, top in LABELS],
        T("{number}", 276.84, 69.18, BOLD, BIG),
        T("{date}", 391.44, 69.18, BOLD, BIG),
        T("{number}  dt. {date}", 276.84, 120.06, BOLD, BIG, when="reference"),

        # the seller (the distributor), then the consignee and the buyer (the fund house, twice)
        T("{seller}", 38.76, 58.50, BOLD, BIG),
        B("seller_block", 38.76, 68.40, 60.48, id="seller", right=PARTY_RIGHT),
        T("Consignee (Ship to)", 38.76, 130.90, REG, 9),
        *_party(0.0, "consignee"),
        T("Buyer (Bill to)", 38.76, 228.94, REG, 9),
        *_party(98.04, "buyer"),

        # the item table
        L(36.00, 326.16, 36.00, 355.08), L(36.12, 326.16, 503.88, 326.16),
        *[L(x, 326.16, x, 355.08) for x in (*COLS, 503.88)],
        L(36.12, 326.40, 503.88, 326.40), L(36.12, 349.32, 503.88, 349.32),
        *[L(x, 355.08, x, Y(471.00, s=-1)) for x in (36.00, *COLS, 503.88)],
        T("Sl", 38.76, 327.54, REG, BIG),
        T("No.", 38.76, 338.94, REG, BIG, hscale=60),
        *[T(label, x, top, REG, 9) for label, x, top in ITEM_HEADS],
        T("1", 38.76, 356.10, REG, BIG),
        T("{particulars}", 78.96, 356.46, BOLD, BIG, maxw=158.6),
        T("{hsn}", 244.68, 356.02, REG, 9),
        T("{rate} %", 297.60, 356.02, REG, 9),
        T("{taxable}", 501.66, 356.46, BOLD, BIG, "right"),
        T("{period_label}", 78.96, 367.90, ITAL, 9),
        T("Output CGST @ {half}%", 239.87, 380.22, BOLD, BIG, "right"),
        T("{cgst}", 501.58, 380.22, BOLD, BIG, "right"),
        T("Output SGST @ {half}%", 239.87, 392.10, BOLD, BIG, "right"),
        T("{sgst}", 501.58, 392.10, BOLD, BIG, "right"),

        # the total row
        L(36.00, Y(471.00, s=-1), 504.00, Y(471.00, s=-1)),
        L(36.00, Y(471.00, s=-1), 36.00, Y(485.40, s=-1)),
        L(503.88, Y(471.00, s=-1), 503.88, Y(485.40, s=-1)),
        *[L(x, Y(471.12, s=-1), x, Y(485.28, s=-1)) for x in COLS],
        L(36.00, Y(485.28, s=-1), 504.00, Y(485.28, s=-1)),
        T("Total", 239.72, Y(472.06, s=-1), REG, 9, "right"),
        T("₹ {total}", 501.55, Y(472.81, s=-1), BOLD, 12, "right", maxw=62.4),

        # the amount chargeable, in words
        L(36.00, Y(485.40, s=-1), 36.00, Y(513.12, s_tax=-1)),
        L(503.88, Y(485.40, s=-1), 503.88, Y(513.12, s_tax=-1)),
        T("Amount Chargeable (in words)", 38.76, Y(486.34, s=-1), REG, 9, hscale=88),
        T("E. & O.E", 501.62, Y(486.34, s=-1), ITAL, 9, "right"),
        W("amount_words", 38.76, Y(499.86, s=-1), 11.88),

        # the HSN / tax summary table
        L(36.00, _t(0), 504.00, _t(0)),
        *[L(x, _t(0), x, _t(42.24)) for x in (36.00, 231.24, 283.68, 367.56, 451.44, 503.88)],
        L(283.68, _t(10.32), 367.56, _t(10.32)), L(367.56, _t(10.32), 451.44, _t(10.32)),
        L(315.24, _t(10.32), 315.24, _t(42.24)), L(399.00, _t(10.32), 399.00, _t(42.24)),
        L(36.12, _t(20.64), 503.76, _t(20.76), THIN), L(36.12, _t(31.08), 503.76, _t(31.20), THIN),
        L(36.00, _t(42.12), 504.00, _t(42.12)),
        *[T(label, x, Y(top, s_tax=-1), REG, 9, hscale=98 if label == "Tax Amount" else 100)
          for label, x, top in HSN_HEADS],
        *_hsn_row(REG, 534.94, total=False),
        *_hsn_row(BOLD, 545.74, total=True),

        # the tax amount in words, whose bottom is fixed at 572.88
        L(36.00, Y(555.36, s=-1), 36.00, 572.88),
        L(503.88, Y(555.36, s=-1), 503.88, 572.88),
        T("Tax Amount (in words)  :", 38.76, Y(562.37 - 0.43, tax_up=-1), REG, 9, hscale=88),
        W("tax_words", 130.08, Y(562.37, tax_up=-1), 11.87),

        # the footer
        L(36.00, 572.88, 36.00, 686.04), L(503.88, 572.88, 503.88, 686.04),
        T("Remarks:", 38.76, 607.41, ITAL, 9, hscale=87),
        T("{remarks}", 38.76, 617.74, REG, 9),
        T("Company's PAN", 38.76, 630.70, REG, 9),
        T(":", 141.99, 630.70, REG, 9),
        T("{pan}", 149.40, 631.06, BOLD, 9),
        L(270.00, 643.44, 503.88, 643.44), L(270.00, 643.44, 270.00, 685.92),
        T("for {seller}", 500.80, 644.86, BOLD, 9, "right", hscale=87),
        T("Authorised Signatory", 501.59, 676.89, REG, 7.48, "right", hscale=104.7),
        L(36.00, 685.92, 504.00, 685.92),
        T("This is a Computer Generated Invoice", 267.57, 692.62, REG, 9, "center"),
    ],
}
