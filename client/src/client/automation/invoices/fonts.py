"""Measuring text the way the PC's Arial will draw it.

Text is wrapped and squeezed by these measurements before it is drawn, so one that differs from the PC's Arial is an
invoice that differs from Tally's. The widths come from Windows' own Arial, read once into `arial.json`; the font
itself is never shipped.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

FACES = ("Arial", "Arial-Bold", "Arial-Italic")


@lru_cache(maxsize=1)
def _table() -> dict[str, dict[str, float]]:
    raw = json.loads((Path(__file__).with_name("arial.json")).read_text(encoding="utf-8"))
    chars = raw["chars"]
    return {face: dict(zip(chars, raw[face])) for face in FACES}


def known(ch: str) -> bool:
    return ch in _table()["Arial"]


def string_width(text: str, font: str, size: float) -> float:
    """Width in points, as reportlab's `stringWidth` gives it for the same font: the sum of the advance widths.

    A character outside the table is measured as the widest digit and logged: it can only come from text the person or
    a registrar typed, and a slightly wide guess squeezes a line rather than letting it overflow its column."""
    widths = _table()[font]
    total = 0.0
    for ch in text:
        w = widths.get(ch)
        if w is None:
            log.warning("no Arial width for %r (U+%04X); measured as a digit", ch, ord(ch))
            w = max(widths[d] for d in "0123456789")
        total += w
    return total * size / 1000.0
