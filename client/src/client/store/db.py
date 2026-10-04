"""The app's local store: settings, the DPAPI vault, and an append-only activity log.

The month itself (its invoices, their statuses and what was done) is kept by the steps in
`workspace/arns/<ARN>/<period>/` (`automation/month.py`, read by `client.hands.local`), not here.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from client.store.dpapi import protect, unprotect

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT,
    secret BLOB             -- DPAPI-encrypted, never plain text
);

CREATE TABLE IF NOT EXISTS audit (
    id     INTEGER PRIMARY KEY,
    at     TEXT NOT NULL,
    period TEXT,
    event  TEXT NOT NULL,
    detail TEXT
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        # check_same_thread=False: the UI thread reads while the worker thread writes (sqlite serialises).
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        # Decrypted secrets, keyed by their encrypted bytes. The masking pass reads the vault for every frame the
        # browser channel carries, and DPAPI costs about half a millisecond a call; a changed secret has new bytes,
        # so this can never hand back a stale one.
        self._plain: dict[bytes, str] = {}

    def close(self) -> None:
        self.db.close()

    # --- settings ---------------------------------------------------------------------------------
    def get(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row and row[0] is not None else default

    def put(self, key: str, value: str | None) -> None:
        self.db.execute("INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, value))

    def get_secret(self, key: str) -> str | None:
        row = self.db.execute("SELECT secret FROM settings WHERE key=?", (key,)).fetchone()
        if not row or not row[0]:
            return None
        blob = bytes(row[0])
        if blob not in self._plain:
            self._plain[blob] = unprotect(blob)
        return self._plain[blob]

    def put_secret(self, key: str, plain: str | None) -> None:
        blob = protect(plain) if plain else None
        self.db.execute("INSERT INTO settings(key, secret) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET secret=excluded.secret",
                        (key, blob))

    # --- audit -----------------------------------------------------------------------------------
    def audit(self, event: str, period: str | None = None, **detail) -> None:
        self.db.execute("INSERT INTO audit(at, period, event, detail) VALUES (?,?,?,?)",
                        (now(), period, event, json.dumps(detail, default=str, ensure_ascii=False)))

    def audit_log(self, period: str | None = None, limit: int = 200) -> list[sqlite3.Row]:
        q, args = "SELECT * FROM audit", []
        if period:
            q, args = q + " WHERE period = ?", [period]
        return self.db.execute(q + " ORDER BY id DESC LIMIT ?", [*args, limit]).fetchall()
