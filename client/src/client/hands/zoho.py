"""Zoho Books, the software's half: letting it in, and the access token the steps are handed.

The person connects in their own browser (Zoho's Accept page, a client named MFDInvoice). Zoho sends the browser back
to a door on 127.0.0.1 that this PC opens for the moment, with a code; the code is swapped for a refresh token, kept in
the vault (`zoho_refresh:<ARN>`, readable by this Windows user only). The steps (`automation/zoho.py`) never see the
client secret or the refresh token: they ask `token(arn)` for an hour's access token and use it.

The client id and secret ship inside the software (Neil's decision, 7 Oct 2026): `zoho.json` beside `brand.json`, put
there by the build from `~/.mfdinvoice/zoho.json`; in a checkout it is read from there. Only Zoho in India
(accounts.zoho.in, www.zohoapis.in) is supported for now.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from client.brand import NAME

log = logging.getLogger(__name__)

ACCOUNTS = "https://accounts.zoho.in"
API = "https://www.zohoapis.in/books/v3"
SCOPE = "ZohoBooks.fullaccess.all"
WAIT_S = 5 * 60                     # how long the browser is waited for
ONLY_INDIA = "Only Zoho Books in India is supported for now."
GONE = "Connect Zoho Books again in Settings."
NOT_SETUP = f"{NAME} can't connect to Zoho Books on this PC."

_lock = threading.Lock()
_access: dict[str, dict] = {}       # arn -> {token, until}
_cancel = threading.Event()


def vault_key(arn: str) -> str:
    return f"zoho_refresh:{arn}"


def _config() -> dict:
    for path in (Path(__file__).parent.parent / "zoho.json", Path.home() / ".mfdinvoice" / "zoho.json"):
        try:
            got = json.loads(path.read_text(encoding="utf-8"))
            if got.get("client_id") and got.get("client_secret"):
                return got
        except (OSError, ValueError):
            continue
    return {}


def _post(url: str, fields: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:                    # noqa: S310 - Zoho
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b"{}")
        except ValueError:
            return {"error": f"http_{e.code}"}


# --- letting it in ------------------------------------------------------------------------------------------------

def cancel() -> None:
    _cancel.set()


def connect(store, arn: str) -> dict:
    """Open the person's browser at Zoho's Accept page and wait for them. Blocking: run it in a thread.
    {ok: True} with the refresh token kept in the vault, or {ok: False, state: cancelled | denied | timeout | off,
    said}."""
    cfg = _config()
    if not cfg:
        return {"ok": False, "state": "off", "said": NOT_SETUP}
    _cancel.clear()
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(12)
    got: dict = {}
    done = threading.Event()

    class Door(http.server.BaseHTTPRequestHandler):
        def do_GET(self):                                                      # noqa: N802
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            mine = q.get("state") == state and ("code" in q or "error" in q)
            if mine:
                got.update(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write((f"<html><body style='font-family:sans-serif;padding:40px'><h2>{NAME}</h2>"
                              "<p>You can close this tab and go back to the software.</p></body></html>").encode()
                             if mine else b"")
            if mine:
                done.set()

        def log_message(self, *a):
            pass

    try:
        door = http.server.HTTPServer(("127.0.0.1", 0), Door)
    except OSError:
        log.exception("zoho: no door could be opened on this PC")
        return {"ok": False, "state": "off", "said": NOT_SETUP}
    redirect = f"http://127.0.0.1:{door.server_port}/callback"
    door.timeout = 0.5
    url = ACCOUNTS + "/oauth/v2/auth?" + urllib.parse.urlencode({
        "client_id": cfg["client_id"], "response_type": "code", "scope": SCOPE, "access_type": "offline",
        "prompt": "consent", "redirect_uri": redirect, "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256"})
    log.info("zoho: waiting for the browser on port %s", door.server_port)
    webbrowser.open(url)
    until = time.monotonic() + WAIT_S
    try:
        while not done.is_set():
            if _cancel.is_set():
                return {"ok": False, "state": "cancelled", "said": ""}
            if time.monotonic() > until:
                return {"ok": False, "state": "timeout", "said": "Zoho Books wasn't accepted in time. Try again."}
            door.handle_request()
    finally:
        door.server_close()
    if "error" in got:
        return {"ok": False, "state": "denied", "said": "Zoho Books wasn't allowed in. Try again, and press Accept."}
    where = (got.get("location") or "in").lower()
    server = got.get("accounts-server") or ACCOUNTS
    if where != "in" or not server.rstrip("/").endswith("zoho.in"):
        log.info("zoho: the callback named %s / %s", where, server)
        return {"ok": False, "state": "off", "said": ONLY_INDIA}
    try:
        reply = _post(ACCOUNTS + "/oauth/v2/token", {
            "grant_type": "authorization_code", "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
            "code": got["code"], "redirect_uri": redirect, "code_verifier": verifier})
    except (urllib.error.URLError, ValueError, OSError) as e:
        log.info("zoho: no answer swapping the code (%s)", e)
        return {"ok": False, "state": "off", "said": "Zoho Books isn't answering. Try again."}
    if not reply.get("refresh_token"):
        log.info("zoho: the code was not swapped: %s", reply.get("error"))
        return {"ok": False, "state": "off", "said": "Zoho Books didn't finish letting the software in. Try again."}
    old = store.get_secret(vault_key(arn))
    if old and old != reply["refresh_token"]:
        _revoke(old)                                # a reconnect lets the grant it replaces go
    with _lock:
        store.put_secret(vault_key(arn), reply["refresh_token"])
        _access[arn] = {"token": reply.get("access_token", ""),
                        "until": time.time() + int(reply.get("expires_in", 3600)) - 60}
    return {"ok": True}


def connected(store, arn: str) -> bool:
    return bool(store.get_secret(vault_key(arn)))


def token(store, arn: str, fresh: bool = False) -> dict:
    """An access token for this ARN's Zoho Books, thread-safe: {token, api}, or {gone: words} when the grant is
    not there or Zoho no longer honours it, or {off: words} when Zoho could not be reached."""
    with _lock:
        have = None if fresh else _access.get(arn)
        if have and have["token"] and have["until"] > time.time():
            return {"token": have["token"], "api": API}
        refresh, cfg = store.get_secret(vault_key(arn)), _config()
        if not refresh:
            return {"gone": GONE}
        if not cfg:
            return {"gone": NOT_SETUP}
        try:
            reply = _post(ACCOUNTS + "/oauth/v2/token", {
                "grant_type": "refresh_token", "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
                "refresh_token": refresh})
        except (urllib.error.URLError, ValueError, OSError) as e:
            log.info("zoho: no answer refreshing (%s)", e)
            return {"off": "Zoho Books isn't answering."}
        if not reply.get("access_token"):
            log.info("zoho: the refresh was refused: %s", reply.get("error"))
            if reply.get("error") in ("invalid_code", "invalid_grant", "invalid_client", "access_denied"):
                return {"gone": GONE}
            return {"off": "Zoho Books isn't answering."}
        _access[arn] = {"token": reply["access_token"], "until": time.time() + int(reply.get("expires_in", 3600)) - 60}
        return {"token": reply["access_token"], "api": API}


def disconnect(store, arn: str) -> None:
    """Revoke the grant at Zoho (best effort: it is gone from this PC either way)."""
    refresh = store.get_secret(vault_key(arn))
    with _lock:
        _access.pop(arn, None)
        store.put_secret(vault_key(arn), None)
    if refresh:
        _revoke(refresh)


def _revoke(refresh: str) -> None:
    """Revoke a grant at Zoho, best effort."""
    try:
        _post(ACCOUNTS + "/oauth/v2/token/revoke?" + urllib.parse.urlencode({"token": refresh}), {})
    except (urllib.error.URLError, ValueError, OSError) as e:
        log.info("zoho: the grant could not be revoked (%s)", e)
