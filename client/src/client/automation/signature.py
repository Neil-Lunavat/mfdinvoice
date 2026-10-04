"""Where the signature goes on an invoice, worked out from the page's own words.

Two layouts:
  - CAMS, and the person's own invoice: the blank area between the left-aligned "For <name>" and "Authorised
    Signatory", out to the page's edge. The signature sits at the top-left of it.
  - KFintech: no "Authorised"; the gap is between "Designation / Status" and the "Signature" label under the line.
    The ink's centre goes above the centre of "Signature" (not the image's centre: a signature's ink is rarely in the
    middle of its picture), kept clear of any text to its left, and the image is centred vertically in the gap.

The signature keeps its own shape: its height is the gap's, its width follows from its aspect ratio, capped at 220 pt.
"""

from __future__ import annotations

PAD = 4.0          # pt kept clear above and below the signature inside the gap
MAX_WIDTH = 220.0  # pt

def _words(items: list[dict], page: int, page_h: float) -> list[dict]:
    """The text layer's words in the old code's terms: top-origin, with x0/x1/top/bottom."""
    out = []
    for i in items:
        if int(i.get("page", 1)) != page:
            continue
        x, y, w, h = float(i["x"]), float(i["y"]), float(i["w"]), float(i["h"])
        out.append({"text": i["text"], "x0": x, "x1": x + w, "top": page_h - y - h, "bottom": page_h - y})
    return out


def gap(items: list[dict], page_w: float, page_h: float) -> dict:
    """The blank area the signature goes in, on the last page: {page, x0, x1, top, bottom}, top-origin points, plus,
    on KFintech, where the "Signature" label's centre is and how far left the signature may go.

    With no anchor at all it falls back to the bottom right, inside the margin: a signature roughly in the right place
    beats no invoice at all, and the person sees every invoice at Your check.
    """
    last = max((int(i.get("page", 1)) for i in items), default=1)
    words = _words(items, last, page_h)
    auth = next((w for w in words if w["text"] == "Authorised"), None)
    if auth is not None:
        fors = [w for w in words if w["text"].lower() == "for" and w["top"] < auth["top"]]
        if fors:
            f = max(fors, key=lambda w: w["top"])
            if f["x0"] < page_w / 2:                   # left-aligned block (CAMS): room to the right
                x1 = page_w
            else:                                      # right-aligned block: stay inside the block
                x1 = max(w["x1"] for w in words
                         if abs(w["top"] - f["top"]) < 1 or abs(w["top"] - auth["top"]) < 1)
            return {"page": last, "x0": f["x0"], "x1": x1, "top": f["bottom"] + PAD, "bottom": auth["top"] - PAD}
    sig = [w for w in words if w["text"] == "Signature"]
    desig = [w for w in words if w["text"] == "Designation"]
    if sig and desig:                                  # KFintech
        s = max(sig, key=lambda w: w["top"])
        above = [w for w in desig if w["top"] < s["top"]]
        if above:
            d = max(above, key=lambda w: w["top"])
            top, bottom = d["bottom"] + PAD, s["top"] - PAD
            centre = (s["x0"] + s["x1"]) / 2
            # the nearest text on the gap's lines to the left of the label, else the page margin
            left = [w["x1"] for w in words if w["bottom"] > top and w["top"] < bottom and w["x1"] < centre]
            return {"page": last, "x0": d["x0"] - 40, "x1": page_w - 25, "top": top, "bottom": bottom,
                    "centre": centre, "left": (max(left) + 10) if left else 36.0}
    return {"page": last, "x0": page_w - 200.0, "x1": page_w - 25.0, "top": page_h - 150.0, "bottom": page_h - 95.0}


def place(g: dict, sig: dict, page_h: float) -> dict:
    """The signature's rectangle inside a gap, as `pdf.stamp` wants it (bottom-left origin). `sig` is `sig.info`'s
    answer: the image's aspect ratio and where the ink's centre sits across it."""
    aspect = float(sig.get("aspect") or 3.0)
    scale = min(max(float(sig.get("scale") or 1.0), 0.6), 1.4)   # the size the person chose at setup, 60-140%
    gh = g["bottom"] - g["top"]
    w = min(gh * aspect, MAX_WIDTH) * scale
    h = w / aspect
    if "centre" in g:                                  # KFintech: the ink above "Signature", centred in the gap
        cx = sig.get("ink_cx")
        cx = 0.5 if cx is None else float(cx)
        x = min(max(g["centre"] - cx * w, g["left"]), g["x1"] - w)
        y_top = g["top"] + (gh - h) / 2
    else:
        x = max(min(g["x0"], g["x1"] - w), 0)
        y_top = g["top"]
    return {"page": g["page"], "x": x, "y": page_h - y_top - h, "w": w, "h": h}
