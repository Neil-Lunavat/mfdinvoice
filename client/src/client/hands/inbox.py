"""CAMS mailback files land in the inbox folder (saved from the mailbox by mail.py, or dropped there by hand);
the run then takes the pair for its request from there (`host.py`).

CAMS names them after the request's confirmation number: confirmation '224793670 WBR106' ->
GST_REPORT_224793670R106_<timestamp>.zip  (one PDF per invoice)
GST_REPORT_224793670R106_<timestamp>.xls  (the prefilled upload sheet)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

NAME = re.compile(r"^GST_REPORT_(\d+)R\d+_\d+\.(zip|xls)$", re.I)


@dataclass(frozen=True)
class Mailback:
    ref: str   # numeric part of the confirmation
    zip: Path
    xls: Path


def ref_of(confirmation: str) -> str:
    m = re.match(r"\s*(\d+)", confirmation)
    if not m:
        raise ValueError(f"unexpected confirmation number {confirmation!r}")
    return m.group(1)


def scan(folder: Path) -> dict[str, Mailback]:
    """Complete zip+xls pairs in the folder, keyed by confirmation ref. Newest file wins on duplicates."""
    found: dict[str, dict[str, Path]] = {}
    for p in sorted(folder.glob("GST_REPORT_*"), key=lambda p: p.stat().st_mtime) if folder.exists() else []:
        m = NAME.match(p.name)
        if m:
            found.setdefault(m.group(1), {})[m.group(2).lower()] = p
    return {ref: Mailback(ref, f["zip"], f["xls"]) for ref, f in found.items() if "zip" in f and "xls" in f}


def find(folder: Path, confirmation: str) -> Mailback | None:
    return scan(folder).get(ref_of(confirmation))
