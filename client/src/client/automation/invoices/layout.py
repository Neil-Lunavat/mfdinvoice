"""A template plus one invoice's facts, turned into a draw-list the PC draws (`pdf.render`).

The engine knows a handful of shapes and nothing about any one format; the formats are data (`templates/`):

    T   a text: a `{placeholder}` string at a place, in a font, left/right/centre, squeezed to `maxw` if too wide
    L   a line, top-origin like the measurements it was taken from
    B   an address block: lines at 11.40 pt, squeezed vertically when more than fit (Tally's rule); later texts can
        sit relative to where it ended (`after=`)
    W   a wrapped text: one line per step, wrapped at the width the template names for it
    Y   a vertical position that moves with the template's shifts (`Y(471.00, s=-1)`)

Everything is measured here with Arial's widths (`fonts`), so the PC only draws what it is told: a text op carries its
left edge, its baseline and its horizontal scale, already worked out. That is what makes a layout change a deploy.

The signature's box is found the way every other invoice's is (`flow.signature.gap`): from the text the draw-list puts
on the page, the gap between "for <name>" and "Authorised Signatory". So the person's own invoice is signed exactly as
the registrar's would be.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from client.automation import signature
from client.automation.invoices import fonts
from client.automation.invoices.money import inr, money, rupees_words

REG, BOLD, ITAL = "Arial", "Arial-Bold", "Arial-Italic"
ASCENT = 0.789          # Arial: baseline = top + 0.789 * size
LINE = 11.40            # 9.96 pt line pitch
BIG = 9.96
LW = 0.375

# One HSN/SAC for everyone, decided 23 Sep 2026: 997152, what CAMS and KFintech print on their own invoices.
HSN = "997152"


class IgstNotDrawn(Exception):
    """An IGST (inter-state) invoice: no Tally sample has ever shown its layout, so none is drawn."""


# --- the template's shapes -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Y:
    base: float
    shifts: dict = field(default_factory=dict)

    def __init__(self, base: float, **shifts: float):
        object.__setattr__(self, "base", base)
        object.__setattr__(self, "shifts", shifts)

    def at(self, vars_: dict[str, float]) -> float:
        return self.base + sum(c * vars_[k] for k, c in self.shifts.items())


def _y(v, vars_: dict[str, float]) -> float:
    return v.at(vars_) if isinstance(v, Y) else float(v)


@dataclass(frozen=True)
class T:
    text: str
    x: float
    top: float | Y
    font: str = REG
    size: float = 9.0
    align: str = "left"
    hscale: float = 100.0
    maxw: float | None = None
    after: str = ""          # measured from the end of this block
    when: str = ""           # drawn only when this fact is true


@dataclass(frozen=True)
class L:
    x0: float
    y0: float | Y
    x1: float
    y1: float | Y
    lw: float = LW


@dataclass(frozen=True)
class B:
    field: str
    x: float
    start: float
    height: float
    id: str = ""
    right: float = 0.0       # a long line is squeezed to end here


@dataclass(frozen=True)
class W:
    field: str
    x: float
    top: float | Y
    step: float


# --- the invoice's facts ---------------------------------------------------------------------------------------

@dataclass
class Seller:
    """The distributor, as they print themselves. Name, GSTIN, PAN and state are theirs from setup; the address,
    phone, email, website and remarks are what Settings calls their own."""
    name: str
    gstin: str
    address: list[str] = field(default_factory=list)
    phone: str = ""
    email: str = ""
    website: str = ""
    remarks: str = ""

    @property
    def pan(self) -> str:
        return self.gstin[2:12] if len(self.gstin) >= 12 else ""

    @property
    def state(self) -> str:
        return state_name(self.gstin[:2])

    def block_lines(self) -> list[str]:
        """The small lines under the name, exactly as Tally prints them."""
        lines = [*self.address, f"GSTIN/UIN: {self.gstin}", f"State Name :  {self.state}, Code : {self.gstin[:2]}"]
        if self.phone:
            lines.append(f"Contact : {self.phone}")
        if self.email:
            lines.append(f"E-Mail : {self.email}")
        if self.website:
            lines.append(self.website)
        return lines


@dataclass
class Party:
    """The fund house, as the registrar's own invoice names it every month."""
    name: str
    gstin: str
    address: list[str] = field(default_factory=list)

    @property
    def state_code(self) -> str:
        return self.gstin[:2]

    @property
    def state(self) -> str:
        return state_name(self.state_code)


@dataclass
class Invoice:
    number: str             # "74/26-27": the person's own series
    date: date              # the registrar's invoice date
    party: Party
    period_label: str       # the line under the item, e.g. "Aug Commission"
    particulars: str        # the item line, e.g. "Aditya Birla Sun Life Commission"
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal = Decimal("0")
    gst_rate: int = 18
    reference: bool = True  # "Reference No. & Date." = "<number>  dt. <date>"

    @property
    def tax(self) -> Decimal:
        return money(self.cgst) + money(self.sgst) + money(self.igst)

    @property
    def total(self) -> Decimal:
        return money(self.taxable) + self.tax


def tally_date(d: date) -> str:
    return f"{d.day}-{d:%b}-{d:%y}"


def facts(inv: Invoice, seller: Seller) -> dict:
    """Every `{placeholder}` a template may use, as the strings it prints."""
    return {
        "number": inv.number, "date": tally_date(inv.date), "month_year": f"{inv.date:%b %Y}",
        "seller": seller.name, "pan": seller.pan, "remarks": seller.remarks,
        "amc": inv.party.name, "amc_gstin": inv.party.gstin, "amc_state": inv.party.state,
        "amc_state_code": inv.party.state_code,
        "particulars": inv.particulars, "period_label": inv.period_label, "hsn": HSN,
        "rate": str(inv.gst_rate), "half": f"{inv.gst_rate / 2:g}",
        "taxable": inr(inv.taxable), "cgst": inr(inv.cgst), "sgst": inr(inv.sgst), "tax": inr(inv.tax),
        "total": inr(inv.total),
        "reference": inv.reference,
        # the texts that wrap, and the blocks
        "amount_words": rupees_words(inv.total), "tax_words": rupees_words(inv.tax),
        "seller_block": seller.block_lines(), "amc_address": list(inv.party.address),
    }


# --- the engine --------------------------------------------------------------------------------------------------

class _Page:
    def __init__(self, page_h: float):
        self.h = page_h
        self.ops: list[dict] = []

    def text(self, s: str, x: float, top: float, font: str = REG, size: float = 9.0, align: str = "left",
             hscale: float = 100.0, maxw: float | None = None) -> None:
        if not s:
            return
        w = fonts.string_width(s, font, size) * hscale / 100
        if maxw and w > maxw:
            hscale *= maxw / w
            w = maxw
        x0 = x - w if align == "right" else x - w / 2 if align == "center" else x
        self.ops.append({"op": "text", "page": 1, "x": round(x0, 4), "y": round(self.h - (top + ASCENT * size), 4),
                         "w": round(w, 4), "h": size, "text": s, "font": font, "size": size,
                         "hscale": round(hscale, 4)})

    def line(self, x0: float, y0: float, x1: float, y1: float, lw: float = LW) -> None:
        self.ops.append({"op": "line", "page": 1, "x": x0, "y": round(self.h - y0, 4), "w": round(x1 - x0, 4),
                         "h": round(y0 - y1, 4), "thickness": lw})


def wrap(s: str, font: str, size: float, width: float) -> list[str]:
    """Tally's wrap: whole words, and a wrapped line keeps its trailing space."""
    lines, cur = [], ""
    for word in s.split(" "):
        trial = f"{cur} {word}" if cur else word
        if fonts.string_width(trial, font, size) <= width or not cur:
            cur = trial
        else:
            lines.append(cur + " ")
            cur = word
    return lines + [cur]


def _block(p: _Page, lines: list[str], start: float, height: float, x: float, right: float) -> float:
    """Tally's address block. Returns where it ends (top-origin). Long lines are squeezed, never overflow."""
    if not lines:
        return start + LINE                                   # Tally keeps one empty line
    n = len(lines)
    step = LINE if n * LINE <= height else height / n
    size = BIG if step == LINE else step * 0.8659
    hscale = BIG / size * 100
    drop = 2.00 - (LINE - step) * 0.2372                      # the baseline sits this far above the line's bottom
    for i, s in enumerate(lines):
        baseline = start + (i + 1) * step - drop
        p.text(s, x, baseline - ASCENT * size, REG, size, hscale=hscale, maxw=right - x)
    return start + n * step


_FIELD = re.compile(r"\{([a-z_]+)\}")


def _fill(text: str, f: dict) -> str:
    return _FIELD.sub(lambda m: str(f[m.group(1)]), text)


def draw(template: dict, inv: Invoice, seller: Seller) -> list[dict]:
    """The draw-list for one invoice: texts and lines, page 1. The signature's op is added by `sign`."""
    if money(inv.igst):
        raise IgstNotDrawn(inv.party.name)
    page_w, page_h = template["page"]
    f = facts(inv, seller)
    wrapped = {name: wrap(f[name], font, size, width) for name, (font, size, width) in template["wraps"].items()}
    vars_ = {name: sum(coef * (len(wrapped[w]) - 1) for w, coef in parts.items())
             for name, parts in template["shifts"].items()}
    p = _Page(page_h)
    ends: dict[str, float] = {}
    for el in template["elements"]:
        if isinstance(el, T):
            if el.when and not f.get(el.when):
                continue
            top = _y(el.top, vars_) + (ends[el.after] if el.after else 0.0)
            p.text(_fill(el.text, f), el.x, top, el.font, el.size, el.align, el.hscale, el.maxw)
        elif isinstance(el, L):
            p.line(el.x0, _y(el.y0, vars_), el.x1, _y(el.y1, vars_), el.lw)
        elif isinstance(el, B):
            end = _block(p, f[el.field], el.start, el.height, el.x, el.right or page_w)
            if el.id:
                ends[el.id] = end
        elif isinstance(el, W):
            top = _y(el.top, vars_)
            for i, s in enumerate(wrapped[el.field]):
                p.text(s, el.x, top + i * el.step, BOLD, BIG)
        else:
            raise TypeError(f"not a template shape: {el!r}")
    return p.ops


def text_items(ops: list[dict]) -> list[dict]:
    """The draw-list's words as a text layer (`pdf.text_layer`'s shape), so the signature is placed by the same rule
    as on a registrar's invoice. pdfplumber reports a word's box as its top to top + size."""
    items = []
    for op in ops:
        if op["op"] != "text":
            continue
        scale = op["hscale"] / 100
        x = op["x"]
        top_h = op["y"] + ASCENT * op["size"]                 # bottom-origin top of the text
        for word in op["text"].split(" "):
            w = fonts.string_width(word, op["font"], op["size"]) * scale
            if word:
                items.append({"page": op["page"], "text": word, "x": x, "y": top_h - op["size"], "w": w,
                              "h": op["size"]})
            x += w + fonts.string_width(" ", op["font"], op["size"]) * scale
    return items


def sign(ops: list[dict], sig: dict, page_w: float, page_h: float) -> list[dict]:
    """Add the signature's op: its box worked out from the page's own words, sized from `sig.info`."""
    at = signature.place(signature.gap(text_items(ops), page_w, page_h), sig, page_h)
    return [*ops, {"op": "image", "page": at["page"], "x": at["x"], "y": at["y"], "w": at["w"], "h": at["h"],
                   "image": "signature"}]


# --- states, as the GSTIN's first two digits name them ------------------------------------------------------------

STATES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand",
    "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura", "17": "Meghalaya",
    "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh",
    "23": "Madhya Pradesh", "24": "Gujarat", "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
}


def state_name(code: str) -> str:
    return STATES.get(code, "")
