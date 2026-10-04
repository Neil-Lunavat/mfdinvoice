"""What the window reads: this PC's own record, turned into the window's `Snapshot`.

Everything here comes off this PC's disk. Each ARN has a folder, `workspace/arns/<ARN>/`, with a folder per month in
it; a run writes the month's record there (`month.json`, `invoices.json`: `client.automation.month`), already in the
window's shapes. The app keeps its own details (the ARNs set up here, the bell, the run it is in) in its settings.
So the window opens, and shows everything already known, with no internet at all.

The shapes are `client/window/src/bridge/types.ts`. Nothing here decides anything about a portal.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from client.store.db import Store

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
         "November", "December"]
SENT = {"Submitted", "Waiting approval", "Approved", "Paid", "Rejected"}
PERIOD = re.compile(r"^[A-Z]{3}-\d{4}$")


# --- settings kept as JSON ---------------------------------------------------------------------------------------

def get(store: Store, key: str, default=None):
    raw = store.get(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return default


def put(store: Store, key: str, value) -> None:
    store.put(key, None if value is None else json.dumps(value))


# --- months ------------------------------------------------------------------------------------------------------

def current_period(today: date | None = None) -> str:
    d = today or date.today()
    return f"{MONTHS[d.month - 1]}-{d.year}"


def labels(period: str) -> tuple[str, str]:
    m, y = period.split("-")
    i = MONTHS.index(m)
    return f"{NAMES[i]} {y}", f"{NAMES[i - 1]} {int(y) - (1 if i == 0 else 0)}"


def _read(base: Path, period: str, what: str, default):
    try:
        return json.loads((base / period / f"{what}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def periods(base: Path) -> list[str]:
    """The months this ARN has a record of, newest first."""
    if not base.exists():
        return []
    return sorted((p.name for p in base.iterdir() if p.is_dir() and PERIOD.match(p.name)
                   and (p / "month.json").exists()), key=_order, reverse=True)


def _order(period: str) -> tuple[int, int]:
    m, y = period.split("-")
    return int(y), MONTHS.index(m)


def month(base: Path, period: str) -> dict:
    """One month of one ARN, in the window's `Month` shape."""
    m = _read(base, period, "month", {})
    m = m if isinstance(m, dict) else {}
    label, kf_label = labels(period)
    y = int(period.split("-")[1])
    listed_now = m.get("listedNow") if isinstance(m.get("listedNow"), dict) else {}
    return {
        "period": period, "label": label, "kfLabel": kf_label,
        "deadline": date(y, MONTHS.index(period.split("-")[0]) + 1, 15).isoformat(),
        "checkedAt": m.get("checkedAt", ""), "listed": bool(m.get("listed")) or any(listed_now.values()),
        "notListed": [r for r in ("CAMS", "KFINTECH") if listed_now.get(r) is False],
        "everRun": any(_read(base, p, "month", {}).get("lastRun") for p in periods(base)),
        "submittedOn": m.get("submittedOn", ""), "lastRun": m.get("lastRun") or None,
        "invoices": [_invoice(i) for i in _read(base, period, "invoices", []) if isinstance(i, dict) and "key" in i],
    }


def tally_kept(base: Path) -> dict:
    """The Tally company this ARN imports into, and how many fund houses are matched to its ledgers: what the
    steps remembered in `tally.json`."""
    try:
        kept = json.loads((base / "tally.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        kept = {}
    kept = kept if isinstance(kept, dict) else {}
    return {"company": str(kept.get("company") or ""), "ledgers": len(kept.get("party") or {})}


def file_of(base: Path, key: str) -> Path | None:
    """The PDF of one invoice (signed, once it has been), wherever its month is."""
    for period in periods(base):
        for i in _read(base, period, "invoices", []):
            if isinstance(i, dict) and i.get("key") == key and i.get("file"):
                path = base / i["file"]
                return path if path.is_file() else None
    return None


def _invoice(i: dict) -> dict:
    keys = ("key", "registrar", "amc", "number", "date", "taxable", "cgst", "sgst", "igst", "status", "said",
            "rejection", "timeline", "gstin", "tally")
    base = {"key": "", "registrar": "CAMS", "amc": "", "number": "", "date": "", "taxable": 0.0, "cgst": 0.0,
            "sgst": 0.0, "igst": 0.0, "status": "Not submitted", "said": "", "rejection": "", "timeline": [],
            "gstin": "", "tally": ""}
    return {**base, **{k: i[k] for k in keys if k in i}}


def total(invoice: dict) -> float:
    return round(invoice["taxable"] + invoice["cgst"] + invoice["sgst"] + invoice["igst"], 2)


def month_status(invoices: list[dict]) -> tuple[str, int]:
    rejected = sum(1 for i in invoices if i["status"] == "Rejected")
    if rejected:
        return "Rejected", rejected
    sent = [i for i in invoices if i["status"] in SENT]
    if not sent:
        return "Not submitted", 0
    if all(i["status"] in ("Approved", "Paid") for i in invoices):
        return "Approved", 0
    return "Submitted", 0


def year(base: Path, now: str) -> list[dict]:
    """The financial year's months that have anything, newest first (`MonthRow`)."""
    m, y = now.split("-")
    fy_start = int(y) if MONTHS.index(m) >= 3 else int(y) - 1
    out = []
    for p in sorted({*periods(base), now}, key=_order, reverse=True):
        pm, py = p.split("-")
        if (int(py) == fy_start and MONTHS.index(pm) >= 3) or (int(py) == fy_start + 1 and MONTHS.index(pm) < 3):
            one = month(base, p)
            if not one["invoices"] and p != now:
                continue
            status, rejected = month_status(one["invoices"])
            out.append({"period": p, "label": one["label"], "count": len(one["invoices"]),
                        "total": round(sum(total(i) for i in one["invoices"]), 2), "status": status,
                        "rejected": rejected})
    return out


def financial_year(now: str) -> str:
    """The financial year the month `now` is in: "2026-27"."""
    m, y = now.split("-")
    fy_start = int(y) if MONTHS.index(m) >= 3 else int(y) - 1
    return f"{fy_start}-{str(fy_start + 1)[2:]}"


def activity(store: Store) -> list[dict]:
    """The permanent record, newest first: what was done on this PC, by the person and by a run."""
    return sorted(get(store, "local_activity", []), key=lambda a: a.get("at", ""), reverse=True)[:500]


def note_now() -> str:
    return datetime.now().isoformat(timespec="seconds")
