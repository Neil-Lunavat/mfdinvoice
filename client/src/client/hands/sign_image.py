"""Signing with the stamped image: the cleaned photo of the person's handwritten signature, drawn where the
steps worked out it goes. One of the two ways behind the door (`ops_sign`).

The image is made by the intake (`ops_sig`) and never leaves this PC. Placing it (`automation/signature.py`) needs
two numbers about it (`info`).
"""

from __future__ import annotations

import io
import json
from functools import lru_cache
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from client import errors


@lru_cache(maxsize=4)
def _signature(path: str, mtime: float) -> Image.Image:
    """The signature, cached against the file's timestamp so a re-uploaded one is picked up.

    It was made by the window's intake (`ops_sig`), so it is already clean: a PNG whose paper is transparent."""
    return Image.open(path).copy()


def meta_of(signature_path: Path) -> dict:
    """What is kept beside the image: the ink's centre and the size the person chose, and which way they sign."""
    try:
        return json.loads(signature_path.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def image(signature_path: Path) -> Image.Image:
    if not signature_path.exists():
        raise errors.Failure(errors.NO_SIGNATURE.code, "No signature has been set up on this PC yet.")
    return _signature(str(signature_path), signature_path.stat().st_mtime)


def info(signature_path: Path) -> dict:
    """Two numbers and a shape. Never the image.

    Placing the signature in the gap on the invoice needs how wide it is against its height, and where the ink
    actually sits inside it.
    """
    if not signature_path.exists():
        return {"present": False, "aspect": None, "ink_cx": None, "ink_cy": None}
    im = image(signature_path)
    w, h = im.size
    meta = meta_of(signature_path)
    scale = round(float(meta.get("size", 100)) / 100, 3)
    if "cx" in meta and "cy" in meta:
        return {"present": True, "aspect": round(w / h, 4), "ink_cx": round(float(meta["cx"]), 4),
                "ink_cy": round(float(meta["cy"]), 4), "scale": scale}
    alpha = im.getchannel("A")
    px = alpha.load()
    total = sx = sy = 0
    step = max(1, min(w, h) // 200)                          # sampling: exact enough for a centre of mass
    for y in range(0, h, step):
        for x in range(0, w, step):
            v = px[x, y]
            if v > 128:
                total += v
                sx += x * v
                sy += y * v
    if not total:
        return {"present": True, "aspect": round(w / h, 4), "ink_cx": 0.5, "ink_cy": 0.5, "scale": scale}
    return {"present": True, "aspect": round(w / h, 4),
            "ink_cx": round(sx / total / w, 4), "ink_cy": round(sy / total / h, 4), "scale": scale}


def stamp(signature_path: Path, src: Path, out: Path, places: list[dict]) -> None:
    """Put the signature where the steps worked out it goes. Coordinates are bottom-left origin, in points."""
    sig = image(signature_path)
    buf = io.BytesIO()
    sig.save(buf, "PNG")
    picture = ImageReader(io.BytesIO(buf.getvalue()))

    by_page: dict[int, list[dict]] = {}
    for p in places:
        by_page.setdefault(int(p["page"]), []).append(p)

    reader, writer = PdfReader(src), PdfWriter()
    for i, page in enumerate(reader.pages, start=1):
        here = by_page.get(i)
        if here:
            pw, ph = float(page.mediabox.width), float(page.mediabox.height)
            overlay = io.BytesIO()
            c = canvas.Canvas(overlay, pagesize=(pw, ph))
            for p in here:
                c.drawImage(picture, float(p["x"]), float(p["y"]),
                            width=float(p["w"]), height=float(p["h"]), mask="auto")
            c.save()
            page.merge_page(PdfReader(overlay).pages[0])
        writer.add_page(page)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        writer.write(f)


def draw(c: canvas.Canvas, signature_path: Path, op: dict) -> None:
    """The signature inside an invoice being drawn (`ops_pdf.render`), exactly as `stamp` draws it."""
    buf = io.BytesIO()
    image(signature_path).save(buf, "PNG")
    c.drawImage(ImageReader(io.BytesIO(buf.getvalue())), float(op["x"]), float(op["y"]),
                width=float(op.get("w") or 0), height=float(op.get("h") or 0), mask="auto")
