"""The error taxonomy. Every failure anywhere in the system is exactly one of four kinds.

The kind decides what the person sees and what we do about it, so it is decided here rather than in a logging
helper:

  user    something only the person can fix (a wrong password, a mailbox that will not connect). We say what, in the
          portal's own words, and offer the fix in place.
  portal  the registrar is down, slow, or has locked the login. Not our fault and not theirs. **We never retry by
          ourselves** - the person picks when to try again.
  ours    our bug, or a portal change we have not caught up with. The person is told it is on us and that we have been
          alerted; we get an alarm.
  person  not an error at all: nothing to do, or the person said no, or pressed Stop. Ends the run cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

USER, PORTAL, OURS, PERSON = "user", "portal", "ours", "person"
KINDS = (USER, PORTAL, OURS, PERSON)


@dataclass(frozen=True)
class Code:
    code: str
    kind: str
    doc: str
    resumable: bool          # can this run continue once the cause is gone, instead of starting over?
    alarm: bool = False      # does this page us?


CODES: dict[str, Code] = {}


def _c(code: str, kind: str, doc: str, resumable: bool, alarm: bool = False) -> Code:
    c = Code(code, kind, doc, resumable, alarm)
    CODES[code] = c
    return c


# --- the person, not a failure ---------------------------------------------------------------------------------
NOTHING_TO_DO = _c("nothing_to_do", PERSON, "Every invoice for this month is already submitted or approved.", False)
STOPPED = _c("stopped", PERSON, "The person pressed Stop after this step.", True)
NOT_CONFIRMED = _c("not_confirmed", PERSON, "Your check was not confirmed; nothing was submitted.", True)
CANCELLED = _c("cancelled", PERSON, "The person closed the question we asked.", True)

# --- the person can fix it -------------------------------------------------------------------------------------
BAD_CREDENTIALS = _c("bad_credentials", USER, "The portal rejected the username or password.", True)
MAILBOX_UNREACHABLE = _c("mailbox_unreachable", USER, "We could not sign in to the mailbox.", True)
NO_SIGNATURE = _c("no_signature", USER, "No signature is set up on this PC.", True)
# Signing with a USB token. Both are the person's to fix, and the run carries on from Sign.
TOKEN_NOT_FOUND = _c("token_not_found", USER, "The signing token is not plugged in.", True)
SIGNING_REFUSED = _c("signing_refused", USER, "The token did not sign: the PIN box was closed, the PIN was wrong or "
                     "locked, the certificate has expired, or its software said no.", True)
ARN_MISMATCH = _c("arn_mismatch", USER, "The portal login belongs to a different ARN than the one on this plan.", False)
NO_BROWSER = _c("no_browser", USER, "No usable browser on this PC and none could be installed.", True)
ANOTHER_COPY = _c("another_copy", USER, "Another copy of the software is already running on this PC.", True)
BROWSER_DOWNLOAD = _c("browser_download", USER, "A browser had to be downloaded and the download failed.", True)
SETUP_INCOMPLETE = _c("setup_incomplete", USER, "Something this run needs was never set up.", True)

# --- the portal -------------------------------------------------------------------------------------------------
PORTAL_DOWN = _c("portal_down", PORTAL, "The portal did not respond.", True)
PORTAL_SLOW = _c("portal_slow", PORTAL, "The portal responded too slowly for this step.", True)
ACCOUNT_LOCKED = _c("account_locked", PORTAL, "The portal has locked this login for a while.", True)
PORTAL_REFUSED = _c("portal_refused", PORTAL, "The portal refused the submit and gave a reason.", True)
PORTAL_VALIDATION = _c("portal_validation", PORTAL, "The portal's own validation failed some invoices.", True)
MAILBACK_LATE = _c("mailback_late", PORTAL, "The registrar's email has not arrived in time.", True)
CAPTCHA_WRONG = _c("captcha_wrong", PORTAL, "The portal did not accept the captcha.", True)
PORTAL_EMPTY = _c("portal_empty", PORTAL, "The portal shows no invoices for this month yet.", True)

# --- ours -------------------------------------------------------------------------------------------------------
SELECTOR_MISSING = _c("selector_missing", OURS, "A page element we rely on is not there any more.", True, True)
FIGURES_MISMATCH = _c("figures_mismatch", OURS, "Our figures and the portal's do not agree.", True, True)
INTERNAL = _c("internal", OURS, "An unexpected failure.", True, True)
IGST_NOT_DRAWN = _c("igst_not_drawn", OURS, "An own invoice charged IGST: there is no layout for one yet, so none is "
                    "drawn.", False)


@dataclass
class Detail:
    """What we may attach to a failure. Nothing here may ever hold a secret or a file's contents."""

    portal_said: str = ""            # the portal's own words, quoted to the person unchanged
    step: str = ""
    stage: str = ""
    registrar: str = ""
    invoice_keys: list[str] = field(default_factory=list)
    retry_after_s: int | None = None
    extra: dict = field(default_factory=dict)

    def wire(self) -> dict:
        d = {"portal_said": self.portal_said, "step": self.step, "stage": self.stage, "registrar": self.registrar,
             "invoice_keys": self.invoice_keys, "retry_after_s": self.retry_after_s}
        return {k: v for k, v in {**d, **self.extra}.items() if v not in (None, "", [], {})}


class Failure(Exception):
    """A failure with its code and, where we have it, the portal's own words."""

    def __init__(self, code: str, message: str = "", detail: Detail | None = None):
        if code not in CODES:
            raise KeyError(f"{code!r} is not an error code")
        self.code = CODES[code]
        self.message = message or self.code.doc
        self.detail = detail or Detail()
        super().__init__(f"[{self.code.kind}/{code}] {self.message}")

    @property
    def kind(self) -> str:
        return self.code.kind

    def wire(self) -> dict:
        return {"code": self.code.code, "kind": self.code.kind, "msg": self.message,
                "resumable": self.code.resumable, "detail": self.detail.wire()}


def of_kind(kind: str) -> list[Code]:
    return [c for c in CODES.values() if c.kind == kind]
