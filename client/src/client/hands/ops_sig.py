"""Signature intake: a photo of a handwritten signature in, a clean stamp out. All of it on this PC.

Ported from the signature lab, unchanged in what it does:

  1. rotate by 90° steps: photos arrive sideways with no EXIF, so the person turns it
  2. alpha from thresholds set per photo: paper = median grey, ink = the 1st percentile; fully opaque up to 35% of the
     way from ink to paper, fully transparent from 75% (this is what removed the grey haze box on dim photos)
  3. drop specks: ink blobs smaller than 1% of the biggest AND farther than 3% of the image's width from every big
     blob (keeps i-dots and flourishes beside the signature, drops paper noise)
  4. crop to what is left, and shrink to 400 px wide (lab D1: no visible difference against full size, ~10× smaller)

It returns the image and the ink's alpha-weighted centre as fractions of its width and height. Placing it needs
those two numbers (`sig.info`: the aspect ratio and that centre).

`prepare_signature`, at the foot, is the cleaning from before this intake existed. `sign_image` falls back to it for a
signature file that is still a plain photo.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

WIDTH = 400


class NoInk(ValueError):
    """The photo has no signature in it that can be told from the paper."""


def prepare(photo: bytes, quarter_turns: int = 0) -> tuple[Image.Image, float, float]:
    """Clean one photo. The same arithmetic as the lab's `prepare_v2`, so the same photo gives the same stamp."""
    try:
        im = Image.open(io.BytesIO(photo)).convert("RGB")
    except Exception as e:                       # not an image PIL can read
        raise NoInk(f"that file is not a photo: {e}") from e
    if quarter_turns % 4:
        im = im.rotate(90 * (quarter_turns % 4), expand=True)
    g = np.asarray(im.convert("L"), dtype=np.float32)
    paper, ink = np.median(g), np.percentile(g, 1)
    if paper - ink < 1:
        raise NoInk("the photo is one flat colour")
    lo, hi = ink + 0.35 * (paper - ink), ink + 0.75 * (paper - ink)
    a = np.clip((hi - g) / (hi - lo), 0, 1)
    mask = a > 0.5
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n == 0:
        raise NoInk("no ink found")
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    big = sizes >= 0.01 * sizes.max()
    big_mask = np.isin(lab, np.flatnonzero(big) + 1)
    dist = ndimage.distance_transform_edt(~big_mask)
    near = 0.03 * g.shape[1]
    keep = big.copy()
    for i in np.flatnonzero(~big):
        keep[i] = dist[lab == i + 1].min() <= near
    keep_mask = np.isin(lab, np.flatnonzero(keep) + 1)
    # alpha: everything inside the dilated kept blobs (so anti-aliased edges survive), nothing elsewhere
    a = a * ndimage.binary_dilation(keep_mask, iterations=3)
    ys, xs = np.nonzero(a > 0.05)
    if not len(ys):
        raise NoInk("no ink left after the paper was removed")
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgba = np.dstack([np.asarray(im), (a * 255).astype(np.uint8)])[y0:y1, x0:x1]
    out = Image.fromarray(rgba, "RGBA")
    w = a[y0:y1, x0:x1]
    cy, cx = ndimage.center_of_mass(w)
    cx, cy = cx / out.width, cy / out.height
    if out.width > WIDTH:
        out = out.resize((WIDTH, round(out.height * WIDTH / out.width)), Image.LANCZOS)
    return out, float(cx), float(cy)


def png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def data_url(png_bytes: bytes) -> str:
    """For the window only: the picture shown on this PC's own screen."""
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode()


# --- a photo that never went through the intake ----------------------------------------------------------------

# Grey levels: darker than INK is fully opaque, lighter than PAPER fully transparent, linear in between.
INK, PAPER = 120, 190


def prepare_signature(path: Path) -> Image.Image:
    """Photo of a signature -> RGBA with the paper made transparent, cropped to the main ink band.

    Stray specks separated from the signature by blank rows are dropped (keeps the largest band).
    """
    im = Image.open(path).convert("RGBA")
    gray = im.convert("L")
    alpha = gray.point(lambda v: 255 if v <= INK else 0 if v >= PAPER else (PAPER - v) * 255 // (PAPER - INK))
    im.putalpha(alpha)

    w, h = alpha.size
    px = alpha.load()
    row_ink = [sum(1 for x in range(0, w, 2) if px[x, y] > 128) for y in range(h)]
    # contiguous row bands with ink (gaps up to 8px bridged), keep the heaviest
    bands, start, gap = [], None, 0
    for y, n in enumerate(row_ink + [0] * 9):
        if n:
            start = y if start is None else start
            gap = 0
        elif start is not None:
            gap += 1
            if gap > 8:
                bands.append((start, y - gap + 1))
                start, gap = None, 0
    top, bottom = max(bands, key=lambda b: sum(row_ink[b[0]:b[1]]))
    band = alpha.crop((0, top, w, bottom))
    left, _, right, _ = band.point(lambda v: 255 if v > 128 else 0).getbbox()
    return im.crop((left, top, right, bottom))
