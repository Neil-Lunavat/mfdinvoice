"""The software's own server, as the app calls it (`server/`): which portal steps are current, the steps themselves,
and what is sent to support. It is separate from the website, which knows accounts and plans and nothing about this.

    GET  /automation/latest.json     {version, file, sha256, signature}
    GET  /automation/<file>          the steps, as one zip
    POST /report                     what is sent to support: words, where, this app, this PC, the log's last lines
    PUT  /report/<id>/record         the run's record, as one zip (pictures of the invoice pages, a page's HTML)
"""

from __future__ import annotations

import json
import logging
import urllib.error

from client.brand import NAME, SERVER, SERVER_FALLBACK
from client.hands.hands import APP_VERSION
from client.hands.reach import Reach

log = logging.getLogger(__name__)

TIMEOUT_S = 20.0
USER_AGENT = f"{NAME}-App/{APP_VERSION}"
LARGEST_RECORD = 20 * 1024 * 1024


reach = Reach("software's server", "SERVER", SERVER, SERVER_FALLBACK)


def base() -> str:
    return reach.base()


def _get(path: str, timeout: float = TIMEOUT_S) -> bytes | None:
    try:
        with reach.open(path, headers={"User-Agent": USER_AGENT}, timeout=timeout) as r:
            return r.read()
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.info("the software's server: %s %s", path, e)
        return None


def manifest() -> dict | None:
    """Which steps are current, or None when the server gives no answer."""
    raw = _get("/automation/latest.json")
    try:
        got = json.loads(raw or b"")
    except ValueError:
        return None
    return got if isinstance(got, dict) and all(got.get(k) for k in ("version", "file", "sha256", "signature")) \
        else None


def download(file: str) -> bytes | None:
    if "/" in file or ".." in file:
        return None
    return _get(f"/automation/{file}", timeout=120.0)


def report(what: dict, record: bytes | None = None) -> bool:
    """Send to support. True when the server took the words; the run's record follows, best effort."""
    try:
        with reach.open("/report", data=json.dumps(what).encode(), method="POST", timeout=TIMEOUT_S, headers={
                "Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT}) as r:
            got = json.loads(r.read() or b"{}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.info("send to support: %s", e)
        return False
    if not got.get("ok"):
        return False
    if record and got.get("id") and len(record) <= LARGEST_RECORD:
        try:
            reach.open(f"/report/{got['id']}/record?key={got.get('key', '')}", data=record, method="PUT",
                       timeout=120.0, headers={"Content-Type": "application/zip", "User-Agent": USER_AGENT}).close()
        except (urllib.error.URLError, OSError) as e:
            log.info("the run's record was not sent: %s", e)
    return True
