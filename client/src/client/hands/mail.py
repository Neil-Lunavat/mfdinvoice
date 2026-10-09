"""Collect mailback attachments from the mailbox into the inbox folder. Read-only.

We look for mails from donotreply@camsonline.com (directly or forwarded) with GST_REPORT_* attachments,
save each such attachment once, and `inbox.scan` pairs the zip + xls by confirmation number.

The mailbox is Gmail: IMAP + app password (Google Account > Security > 2-Step Verification > App passwords). Search
runs server-side with Gmail's own query language (X-GM-RAW). The other choice in the store (settings mail_provider)
is `folder`: no mailbox, and the person chooses CAMS's two files by hand.
"""

from __future__ import annotations

import email
import imaplib
import logging
from email.header import decode_header, make_header
from pathlib import Path

from client.hands import inbox
from client.store.db import Store

log = logging.getLogger(__name__)
SENDER = "donotreply@camsonline.com"
GMAIL_HOST = "imap.gmail.com"
# from: matches direct and auto-forwarded mail; the bare address also matches a manual forward's quoted header.
# Subject is "WBR106. GST invoice, Request Id:224793670R106". (Gmail's filename: only matches whole names or
# extensions, so filename:GST_REPORT finds nothing; attachment names are checked after download instead.)
QUERY = f"has:attachment newer_than:{{days}}d subject:(GST invoice) {{{{from:{SENDER} {SENDER}}}}}"  # {a b} = OR


class MailError(RuntimeError):
    """Login/connection problem; message is shown to the person."""


def provider(store: Store) -> str:
    return store.get("mail_provider") or "gmail"


def user(store: Store) -> str | None:
    return store.get("gmail_user")


def configured(store: Store) -> bool:
    return bool(store.get("gmail_user") and store.get_secret("gmail_app_password"))


# --- Gmail ---------------------------------------------------------------------------------------------

def _gmail(user_: str, password: str) -> imaplib.IMAP4_SSL:
    try:
        m = imaplib.IMAP4_SSL(GMAIL_HOST, timeout=30)
        m.login(user_, password)
    except imaplib.IMAP4.error as e:
        raise MailError(f"Gmail refused the login for {user_}: {e}. Use an app password, not the account password.") from e
    except OSError as e:
        raise MailError(f"cannot reach {GMAIL_HOST}: {e}") from e
    return m


def test_login(user_: str, password: str) -> None:
    _gmail(user_, password).logout()


def _all_mail(m: imaplib.IMAP4_SSL) -> str:
    """The folder flagged \\All ("[Gmail]/All Mail", localised names vary); INBOX if none."""
    typ, boxes = m.list()
    for line in boxes if typ == "OK" else []:
        text = line.decode(errors="replace")
        if "\\All" in text:
            return text[text.rindex(' "/" ') + 5:] if ' "/" ' in text else text.split()[-1]
    return "INBOX"


def _gmail_uids(m: imaplib.IMAP4_SSL, days: int) -> list[bytes]:
    m.select(_all_mail(m), readonly=True)
    typ, data = m.uid("SEARCH", "X-GM-RAW", f'"{QUERY.format(days=days)}"')
    if typ != "OK":
        raise MailError(f"Gmail search failed: {data}")
    return data[0].split()


# --- shared -----------------------------------------------------------------------------------------------

def _save_attachments(raw: bytes, folder: Path) -> list[Path]:
    saved = []
    for part in email.message_from_bytes(raw).walk():
        name = part.get_filename()
        if not name:
            continue
        name = str(make_header(decode_header(name)))
        if not inbox.NAME.match(name):
            continue
        dst = folder / name
        payload = part.get_payload(decode=True)
        if dst.exists() or not payload:
            continue
        tmp = dst.with_suffix(dst.suffix + ".part")
        tmp.write_bytes(payload)
        tmp.replace(dst)  # atomic: scan never sees half a file
        saved.append(dst)
        log.info("saved %s from the mailbox", name)
    return saved


# CAMS's emails older than this aren't looked at: in three days a month gains a couple of invoices at most, so an older
# mailback is behind what CAMS lists and CAMS is asked for a new one instead (Neil, 9 Oct).
LOOK_BACK_DAYS = 3


def fetch(store: Store, folder: Path, days: int | None = None) -> list[Path]:
    """Save new mailback attachments into `folder`, from the last `LOOK_BACK_DAYS`. Returns the files written this call."""
    if not configured(store):
        return []
    days = days or LOOK_BACK_DAYS
    folder.mkdir(parents=True, exist_ok=True)
    m = _gmail(store.get("gmail_user"), store.get_secret("gmail_app_password"))
    saved: list[Path] = []
    try:
        for uid in _gmail_uids(m, days):
            typ, msg_data = m.uid("FETCH", uid, "(BODY.PEEK[])")
            if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            raw = msg_data[0][1]
            if SENDER.encode() not in raw.lower():
                log.warning("skipped a GST_REPORT mail not from %s", SENDER)
                continue
            saved += _save_attachments(raw, folder)
    finally:
        try:
            m.logout()
        except (imaplib.IMAP4.error, OSError):
            pass
    if saved:
        store.audit("mail_fetched", None, files=[p.name for p in saved])
    return saved
