"""CAMS's email, the first way: the person's Gmail forwards CAMS's mailbacks, by a filter, to our address
(`brand.json` "forward"), and the software's server keeps each one locked for this PC (server/src/forward.ts). This
PC fetches them, opens each with its own private key, and saves the zip and the Excel into the inbox folder, as
`mail.py` does from Gmail. The private key and the box's secret never leave this PC's vault.

Setting up needs no code of ours: this PC claims the Gmail (`claim`), and Gmail's own forwarding confirmation for it,
or the first CAMS mailback that came through it, proves it is the person's. `state` says whether that has happened
and carries Gmail's confirmation link or code, to open or type in Gmail.
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.parse
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
    "too_many": "Too many tries for this Gmail just now. Try again in an hour.",
    "busy": "This Gmail is being set up on another PC just now. Try again in 30 minutes.",
}


def configured(store: Store) -> bool:
    return bool(store.get_secret(SECRET) and store.get_secret(KEY))


def _call(method: str, path: str, body: dict | None = None, secret: str = "") -> tuple[int, bytes]:
    try:
        with server.reach.open(path, method=method, timeout=TIMEOUT_S,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={"Content-Type": "application/json", "User-Agent": server.USER_AGENT,
                                        **({"Authorization": f"Bearer {secret}"} if secret else {})}) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _said(raw: bytes) -> str:
    try:
        code = json.loads(raw or b"{}").get("error", "")
    except ValueError:
        code = ""
    return SAID.get(code, "MFDInvoice's server didn't answer as expected. Try again in a minute.")


def claim(store: Store, email: str) -> dict:
    """This PC asks for the Gmail's box (its key made once); the box is ours once the proof arrives (`state`)."""
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
        status, raw = _call("POST", "/forward/claim", {"email": email.strip(), "pub": pub})
    except (urllib.error.URLError, OSError) as e:
        log.info("forwarding: the server could not be reached: %s", e)
        return {"ok": False, "said": "Couldn't reach MFDInvoice's server. Check the internet connection."}
    if status != 200:
        return {"ok": False, "said": _said(raw)}
    store.put_secret(SECRET, json.loads(raw)["secret"])
    store.put(EMAIL, email.strip().lower())
    store.put("mail_provider", "forward")
    return {"ok": True}


def _waiting(store: Store) -> tuple[bool, list[dict]]:
    status, raw = _call("GET", "/forward/mail", secret=store.get_secret(SECRET) or "")
    if status == 401:
        raise MailError("Forwarding to MFDInvoice isn't set up on this PC any more. Set it up again in Settings.")
    if status != 200:
        raise MailError("MFDInvoice's server didn't answer about your forwarded emails.")
    body = json.loads(raw)
    return bool(body.get("proved")), list(body.get("mails") or [])


def is_gmail_link(text: str) -> bool:
    """Gmail's confirmation link (https, on google.com), as the server read it from Gmail's mail."""
    if not text.startswith("https://"):
        return False
    host = urllib.parse.urlsplit(text).hostname or ""
    return host == "google.com" or host.endswith(".google.com")


def state(store: Store) -> dict:
    """Where setting up stands: `proved` (the Gmail is this PC's), and `confirm`, Gmail's forwarding confirmation once
    Gmail has sent it to our address: its link (Gmail sends only a link today) or code; '' until then."""
    if not configured(store):
        return {"proved": False, "confirm": ""}
    try:
        proved, mails = _waiting(store)
    except (MailError, urllib.error.URLError, OSError, ValueError) as e:
        log.info("forwarding: state not read: %s", e)
        return {"proved": False, "confirm": "", "said": "Couldn't reach MFDInvoice's server."}
    codes = [m["code"] for m in mails if m.get("kind") == "confirm" and m.get("code")]
    return {"proved": proved, "confirm": codes[-1] if codes else ""}


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
    proved, mails = _waiting(store)
    if not proved:
        return []
    for m in mails:
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
