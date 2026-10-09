"""One month of one ARN, as this PC knows it: its files, and the record the window reads.

    <ARN>/<OCT-2026>/
        month.json       what is known about the month (below)
        invoices.json    one row per invoice whose files are on this PC, in the window's own shape
        cams/fetched/    CAMS's zip and Excel, as they came (the latest pair only)
        cams/invoices/   the PDFs out of the zip
        cams/signed/     each invoice signed, or the person's own invoice drawn for it. One file per invoice: signing
                         again replaces it, so nothing is ever there twice
        cams/upload/     the zip and the Excel built for CAMS's upload page
        kfintech/…       the same, without upload/ (KFintech takes the signed PDFs one by one)

month.json:
    checkedAt            when the registrars' status was last read
    status   {REG: [{key, status, remarks}]}     that reading, in the registrar's own words
    listedNow {REG: bool}                        the registrar lists the month at all
    fetched  {REG: {at, listed}}                 the files on this PC, and what the registrar listed when they were got
    asked    {ref, at, listed}                   CAMS has been asked to email the month and the email is not in yet
    pressed  {REG: {at, keys}}                   Submit was pressed and the registrar never answered
    leftOut  [key]                               unticked at Your check, so they start unticked next time
    lastRun  {how, at, said, portal, code}       how the month's latest run ended
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from client.automation import words
from client.automation.words import CAMS, KFIN

log = logging.getLogger(__name__)

FOLDER = {CAMS: "cams", KFIN: "kfintech"}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


class Month:
    def __init__(self, base: Path, period: str):
        self.base, self.period = base, period
        self.dir = base / period
        self.facts: dict = _load(self.dir / "month.json", {})
        self.rows: dict[str, dict] = {r["key"]: r for r in _load(self.dir / "invoices.json", []) if "key" in r}

    # --- files ------------------------------------------------------------------------------------------------------

    def folder(self, registrar: str, kind: str, empty: bool = False) -> Path:
        path = self.dir / FOLDER[registrar] / kind
        if empty and path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def rel(self, path: Path) -> str:
        return path.relative_to(self.base).as_posix()

    def path(self, rel: str) -> Path:
        return self.base / rel

    # --- the record ---------------------------------------------------------------------------------------------------

    def save(self) -> None:
        label, kf_label = words.labels(self.period)
        sent = sorted(r["sentAt"] for r in self.rows.values() if r.get("sentAt"))
        self.facts.update({"period": self.period, "label": label, "kfLabel": kf_label,
                           "listed": bool(self.rows), "submittedOn": sent[0][:10] if sent else ""})
        for r in self.rows.values():
            r["status"] = words.status_of(r)
            r["words"] = str(r.get("said") or "").strip() if words.meaning(r["registrar"], r.get("said")) == "unknown" else ""
            r["rejection"] =(r.get("remarks") or r.get("said") or "") if r["status"] == "Rejected" else ""
            r["timeline"] = _timeline(r)
        _write(self.dir / "month.json", self.facts)
        order = sorted(self.rows.values(), key=lambda r: (r["registrar"], str(r.get("amc", "")).lower()))
        _write(self.dir / "invoices.json", order)

    def put(self, registrar: str, key: str, **facts) -> dict:
        """An invoice whose files are on this PC: its row, made or brought up to date."""
        row = self.rows.setdefault(key, {"key": key, "registrar": registrar, "amc": "", "number": "", "date": "",
                                         "taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "said": "",
                                         "remarks": "", "listedAt": now(), "signedAt": "", "sentAt": "",
                                         "statusAt": "", "file": ""})
        row.update(facts)
        return row

    def read_status(self, registrar: str, reading: list[dict], after_press: bool = False) -> str:
        """The registrar's status page was read: its words are the truth about what it has. Never raises. A word never
        seen means the registrar has the invoice: it is logged, shown in the registrar's own words and never sent
        again. The unknown words are returned as "key: word; ..." ("" when none) for the caller to note.
        `after_press` is kept for callers; it changes nothing."""
        strange = [r for r in reading if words.meaning(registrar, r.get("status")) == "unknown"]
        for r in strange:
            log.warning("unknown status word from %s: %r on %s", registrar, r.get("status"), r.get("key"))
        said_strange = "; ".join(sorted({f"{r['key']}: {(r.get('status') or '').strip() or '(empty)'}" for r in strange}))
        at = now()
        self.facts.setdefault("status", {})[registrar] = reading
        self.facts["checkedAt"] = at
        by_key = latest(reading, registrar)
        for row in self.rows.values():
            if row["registrar"] != registrar:
                continue
            got = by_key.get(row["key"])
            said = (got or {}).get("status", "")
            if said != row.get("said"):
                row["statusAt"] = at
            row["said"], row["remarks"] = said, (got or {}).get("remarks", "")
            if not words.is_final(registrar, said):
                row["sentAt"] = ""                # the registrar does not have it, whatever was pressed
        self.facts.get("pressed", {}).pop(registrar, None)      # a status reading settles a Submit nobody answered
        return said_strange

    def with_registrar(self, registrar: str) -> set[str]:
        """The invoices the registrar already has, by its last status reading."""
        return {k for k, r in latest(self.facts.get("status", {}).get(registrar, []), registrar).items()
                if words.is_final(registrar, r.get("status"))}

    def said_about(self, registrar: str, key: str) -> dict:
        """The registrar's latest words about one invoice."""
        return latest(self.facts.get("status", {}).get(registrar, []), registrar).get(key, {})

    def of(self, registrar: str) -> list[dict]:
        return [r for r in self.rows.values() if r["registrar"] == registrar]

    def ended(self, how: str, said: str = "", portal: str = "", code: str = "") -> None:
        self.facts["lastRun"] = {"how": how, "at": now(), "said": said, "portal": portal[:300], "code": code}
        self.save()


RANK = {"done": 4, "with": 3, "unknown": 3, "rejected": 2, "open": 1}


def latest(reading: list[dict], registrar: str = "") -> dict[str, dict]:
    """A status reading by invoice. CAMS lists an invoice once for every time it was sent (REJECTED, then APPROVED
    after the resend), with no date on the row, so the order says nothing: the row that wins is the furthest along
    (approved, then with the registrar, then rejected, then open). Equal rows: the last listed."""
    out: dict[str, dict] = {}
    for r in reading:
        have = out.get(r["key"])
        if have is None or (RANK[words.meaning(registrar, r.get("status"))]
                            >= RANK[words.meaning(registrar, have.get("status"))]):
            out[r["key"]] = r
    return out


def _timeline(r: dict) -> list[dict]:
    who = words.NAMES.get(r["registrar"], r["registrar"])
    out = [{"what": f"Listed by {who}", "when": r.get("listedAt") or ""}]
    if r.get("signedAt"):
        out.append({"what": "Made and signed" if r.get("own") else "Signed", "when": r["signedAt"]})
    if r.get("sentAt"):
        out.append({"what": f"Submitted to {who}", "when": r["sentAt"]})
    if r.get("said"):
        out.append({"what": {"Rejected": "Rejected", "Waiting approval": "Waiting approval", "Approved": "Approved"}.get(
            words.status_of(r), f"{who}: {r['said']}"), "when": r.get("statusAt") or ""})
    return out
