"""CAMS's email, the first way: the person's Gmail forwards CAMS's mailbacks, by a filter, to our address
(`brand.json` "forward"), and the software's server keeps each one locked for this PC (server/src/forward.ts). This
PC fetches them, opens each with its own private key, and saves the zip and the Excel into the inbox folder, as
`mail.py` does from Gmail. The private key and the box's secret never leave this PC's vault.

Setting up: a code to the CAMS email proves it is the person's (`start`, `verify`); then Gmail's own forwarding
confirmation comes to us, and its code is shown in the software to be typed in Gmail (`gmail_code`).
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from client.hands import server
from client.hands.mail import MailError, _save_attachments
from client.store.db import Store

log = logging.getLogger(__name__)
KEY, SECRET, EMAIL, SEEN = "forward_key", "forward_secret", "forward_email", "forward_seen"
TIMEOUT_S = 30.0
SAID = {
    "bad_email": "That email doesn't look right.",
    "too_many": "Too many codes for this email just now. Try again in an hour.",
    "no_code": "Ask for a code first.",
    "expired": "That code has expired. Ask for a new one.",
    "wrong_code": "That code isn't right.",
}


def configured(store: Store) -> bool:
    return bool(store.get_secret(SECRET) and store.get_secret(KEY))


def _call(method: str, path: str, body: dict | None = None, secret: str = "") -> tuple[int, bytes]:
    req = urllib.request.Request(server.base() + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": server.USER_AGENT,
                                          **({"Authorization": f"Bearer {secret}"} if secret else {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:        # noqa: S310 - our own server
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _said(raw: bytes) -> str:
    try:
        code = json.loads(raw or b"{}").get("error", "")
    except ValueError:
        code = ""
    return SAID.get(code, "MFDInvoice's server didn't answer as expected. Try again in a minute.")


def start(store: Store, email: str) -> dict:
    """A code to this email, and this PC's key made (once) for what will be forwarded to it."""
    pem = store.get_secret(KEY)
    if pem:
        key = serialization.load_pem_private_key(pem.encode(), password=None)
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        store.put_secret(KEY, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                serialization.NoEncryption()).decode())
    pub = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.DER,
                                                         serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
    try:
        status, raw = _call("POST", "/forward/start", {"email": email.strip(), "pub": pub})
    except (urllib.error.URLError, OSError) as e:
        log.info("forwarding: the server could not be reached: %s", e)
        return {"ok": False, "said": "Couldn't reach MFDInvoice's server. Check the internet connection."}
    return {"ok": True} if status == 200 else {"ok": False, "said": _said(raw)}


def verify(store: Store, email: str, code: str) -> dict:
    try:
        status, raw = _call("POST", "/forward/verify", {"email": email.strip(), "code": code.strip()})
    except (urllib.error.URLError, OSError):
        return {"ok": False, "said": "Couldn't reach MFDInvoice's server. Check the internet connection."}
    if status != 200:
        return {"ok": False, "said": _said(raw)}
    store.put_secret(SECRET, json.loads(raw)["secret"])
    store.put(EMAIL, email.strip().lower())
    store.put("mail_provider", "forward")
    return {"ok": True}


def _waiting(store: Store) -> list[dict]:
    status, raw = _call("GET", "/forward/mail", secret=store.get_secret(SECRET) or "")
    if status == 401:
        raise MailError("Forwarding to MFDInvoice isn't set up on this PC any more. Set it up again in Settings.")
    if status != 200:
        raise MailError("MFDInvoice's server didn't answer about your forwarded emails.")
    return list(json.loads(raw).get("mails") or [])


def is_gmail_link(text: str) -> bool:
    """Gmail's confirmation link (https, on google.com), as the server read it from Gmail's mail."""
    if not text.startswith("https://"):
        return False
    host = urllib.parse.urlsplit(text).hostname or ""
    return host == "google.com" or host.endswith(".google.com")


def gmail_code(store: Store) -> str:
    """Gmail's forwarding confirmation, once Gmail has sent it to our address: its code, or its link (Gmail sends
    only a link today); '' until then."""
    if not configured(store):
        return ""
    try:
        codes = [m["code"] for m in _waiting(store) if m.get("kind") == "confirm" and m.get("code")]
    except (MailError, urllib.error.URLError, OSError, ValueError):
        return ""
    return codes[-1] if codes else ""


def _open(store: Store, sealed: bytes) -> bytes:
    """[2 bytes: n][the AES key, wrapped with this PC's RSA key: n bytes][12 bytes: iv][the mail, AES-GCM]."""
    key = serialization.load_pem_private_key((store.get_secret(KEY) or "").encode(), password=None)
    n = int.from_bytes(sealed[:2], "big")
    raw = key.decrypt(sealed[2:2 + n], padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(),
                                                    label=None))
    return AESGCM(raw).decrypt(sealed[2 + n:14 + n], sealed[14 + n:], None)


def fetch(store: Store, folder: Path) -> list[Path]:
    """Save the mailbacks waiting for this PC into `folder`, each once. Returns the files written."""
    if not configured(store):
        return []
    folder.mkdir(parents=True, exist_ok=True)
    seen = set(json.loads(store.get(SEEN) or "[]"))
    saved: list[Path] = []
    for m in _waiting(store):
        if m.get("kind") != "mailback" or m["id"] in seen:
            continue
        status, sealed = _call("GET", f"/forward/mail/{m['id']}", secret=store.get_secret(SECRET) or "")
        if status != 200:
            continue
        try:
            saved += _save_attachments(_open(store, sealed), folder)
        except Exception:                                          # one that won't open is left; the rest go on
            log.exception("forwarding: mail %s couldn't be opened", m["id"])
            continue
        seen.add(m["id"])
    store.put(SEEN, json.dumps(sorted(seen)[-500:]))
    if saved:
        store.audit("mail_fetched", None, files=[p.name for p in saved], via="forward")
    return saved
