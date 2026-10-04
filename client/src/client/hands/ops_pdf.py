"""Drawing a PDF from a draw-list: the person's own invoice, and the previews in setup and Settings.

The list is deliberately dumb and already measured (`client.automation.invoices.layout`): a text's left edge, baseline
and horizontal scale, a line's ends, the signature's box. The signature is the door's (`ops_sign`): the person's image
drawn here exactly as a stamp draws it, or their token signing the finished file.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from client import errors
from client.hands.ops_sign import Door

FONT_DIR = Path(r"C:\Windows\Fonts")
FONT_FILES = {"Arial": "arial.ttf", "Arial-Bold": "arialbd.ttf", "Arial-Italic": "ariali.ttf"}
FALLBACK = {"Arial": "Helvetica", "Arial-Bold": "Helvetica-Bold", "Arial-Italic": "Helvetica-Oblique"}


def _font(name: str) -> str:
    """Arial comes from Windows, never from us. The layout was measured with Arial's widths; only on a Windows without
    Arial (none seen) does this fall back, and the text then sits slightly off its measured place."""
    if name not in pdfmetrics.getRegisteredFontNames():
        path = FONT_DIR / FONT_FILES.get(name, "")
        if not path.is_file():
            return FALLBACK.get(name, "Helvetica")
        pdfmetrics.registerFont(TTFont(name, str(path)))
    return name


def render_to(door: Door, out: Path, page_w: float, page_h: float, ops: list[dict]) -> str:
    """Draw a draw-list into this file. Returns the way it was signed, '' when the list had no signature."""
    out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out), pagesize=(page_w, page_h), pageCompression=1)
    c.setLineWidth(0.375)
    page = 1
    signed, boxes = False, []
    for op in sorted(ops, key=lambda o: int(o["page"])):
        while int(op["page"]) > page:
            c.showPage()
            page += 1
        if op["op"] == "image":
            if op.get("image") != "signature":
                raise errors.Failure(errors.INTERNAL.code, "the signature is the only image this app draws")
            box = door.draws(c, op)
            signed, boxes = True, boxes + ([box] if box else [])
        else:
            _draw(c, op)
    c.showPage()
    c.save()
    return door.finish(out, boxes) if signed else ""


def _draw(c: canvas.Canvas, op: dict) -> None:
    kind = op["op"]
    if kind == "text":
        t = c.beginText()
        t.setFont(_font(op.get("font") or "Arial"), float(op.get("size") or 9.0))
        t.setHorizScale(float(op.get("hscale") or 100.0))
        t.setTextOrigin(float(op["x"]), float(op["y"]))
        t.textOut(op.get("text") or "")
        c.drawText(t)
    elif kind == "line":
        x, y = float(op["x"]), float(op["y"])
        c.setLineWidth(float(op.get("thickness") or 0.375))
        # The layout gives a line's start (`y`, bottom-origin) and `h` = its top-origin y0 - y1, so its end is at y + h.
        # Drawing to y - h sent every vertical rule up the page from its start instead of down to its end (2 Oct).
        c.line(x, y, x + float(op.get("w") or 0), y + float(op.get("h") or 0))
