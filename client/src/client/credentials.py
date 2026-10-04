"""What the vault holds, by name, and how a credential is shown.

PASSWORDS never appear anywhere: not on screen, not in a log, not in what is sent to support. CREDENTIALS are the
sign-ins that are not passwords (the CAMS email, which is the whole of that sign-in, and the KFintech username); they
live in the vault too, and the window is shown only their masked form.
"""

from __future__ import annotations

PASSWORDS = ("kfintech_password", "gmail_app_password")
CREDENTIALS = ("cams_email", "kfintech_username")


def shown(value: str) -> str:
    """The form of a credential that may be shown: 'priya.m@gmail.com' -> 'p***@gmail.com', 'rkmehta01' -> 'rkm***'.
    Never reversible, and never more than a few characters of the value."""
    value = (value or "").strip()
    if not value:
        return ""
    name, at, domain = value.partition("@")
    if at:
        return f"{name[:1]}***@{domain}"
    return f"{value[:min(3, max(1, len(value) // 3))]}***"
