"""Rupees as Tally prints them. Ported unchanged from the first desktop app's `client/invoice/words.py`."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
        "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def money(v) -> Decimal:
    """Round half up to paise (CAMS raw values like 1325.33706608 -> 1325.34)."""
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def inr(v) -> str:
    """1325.34 -> '1,325.34'; 5649071.5 -> '56,49,071.50' (Indian grouping)."""
    d = money(v)
    sign = "-" if d < 0 else ""
    whole, frac = f"{abs(d):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{whole}.{frac}"


def _below_100(n: int) -> str:
    return ONES[n] if n < 20 else (TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else ""))


def _below_1000(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(f"{ONES[n // 100]} Hundred")
    if n % 100:
        parts.append(_below_100(n % 100))
    return " ".join(parts)


def number_words(n: int) -> str:
    if n == 0:
        return "Zero"
    parts = []
    for unit, size in (("Crore", 10_000_000), ("Lakh", 100_000), ("Thousand", 1000)):
        if n >= size:
            # crores above 99 keep counting in lakh/thousand words (Tally: "One Hundred Twenty Crore")
            parts.append(f"{number_words(n // size) if unit == 'Crore' else _below_100(n // size)} {unit}")
            n %= size
    if n:
        parts.append(_below_1000(n))
    return " ".join(parts)


def rupees_words(v) -> str:
    d = money(v)
    rupees, paise = int(d), int((d - int(d)) * 100)
    text = f"Indian Rupees {number_words(rupees)}"
    if paise:
        text += f" and {_below_100(paise)} paise"
    return text + " Only"
