"""An example of each registrar's own invoice, for showing where the signature goes before any real one is fetched.

`registrars/cams.json` and `registrars/kfintech.json` are one real invoice of each, turned into a draw-list: every word
and rule where the registrar puts it, the fund house's details as they are, the figures and references made up, and
the distributor's own details as placeholders, filled here with the person's.
"""

from __future__ import annotations

import json
from pathlib import Path

from client.automation.invoices import fonts

KINDS = ("cams", "kfintech")


def example(kind: str, name: str, gstin: str, arn: str) -> tuple[list[dict], float, float]:
    """(draw-list, page width, page height) for this registrar's invoice, made out to this person."""
    raw = json.loads((Path(__file__).parent / "registrars" / f"{kind}.json").read_text("utf-8"))
    gstin = gstin or "27ABCPM1234F1Z3"
    mine = {"{name}": name or "Your name", "{gstin}": gstin, "{pan}": gstin[2:12], "{arn}": arn or "ARN-000000"}
    ops = []
    for op in raw["ops"]:
        op = dict(op)
        if op["op"] == "text":
            for mark, value in mine.items():
                op["text"] = op["text"].replace(mark, value)
            if "cx" in op:                    # centred on the page: its left edge follows its new width
                op["x"] = op.pop("cx") - fonts.string_width(op["text"], op["font"], op["size"]) / 2
        ops.append(op)
    page_w, page_h = raw["page"]
    return ops, page_w, page_h
