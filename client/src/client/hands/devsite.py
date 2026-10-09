"""DEV ONLY, a checkout (`uv run app`): the website, answered on this PC. It is never called, never shipped
(`packaging/app.spec` leaves this module out and `packaging/build.py` fails the build if it is in).

`shell.install` puts these in the place of `site`'s functions, and makes `server.report` say "not sent". Everything
else (portals, mailbox forwarding through the software's server, Tally) is real.

    test@mfdinvoice.co.in with 000000 signs in; the plan is on for good; no ARN is bound; no update; no survey.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

log = logging.getLogger(__name__)

EMAIL = "test@mfdinvoice.co.in"
CODE = "000000"
TOKEN = "dev"

arns: Callable[[], list[str]] = lambda: []          # the ARNs set up on this PC, set by the shell


def send_code(email: str) -> dict:
    if email.strip().lower() == EMAIL:
        return {"ok": True}
    return {"ok": False, "reason": "no_account", "wait": 0}


def verify(email: str, code: str, version: str, device: str, replace: bool = False) -> dict:
    gone = {"ok": False, "left": 0, "deleteAfter": "", "device": "", "lastSeen": ""}
    if email.strip().lower() != EMAIL:
        return {**gone, "reason": "wrong", "left": 2}
    if code.strip() != CODE:
        return {**gone, "reason": "wrong", "left": 2}
    return {"ok": True, "token": TOKEN, "email": EMAIL}


def me(token: str) -> dict:
    if token != TOKEN:
        return {"ok": False, "reason": "bad_token"}
    return {"ok": True, "active": True, "source": "plan", "paid_until": "2099-12-31", "slots": 6,
            "arns": [{"arn": a.removeprefix("ARN-")} for a in arns()], "trial_used": False, "app": None, "survey": None}


def bind(token: str, arn: str, holder: str) -> dict:
    log.info("dev: %s not bound (no website)", arn)
    return {"ok": True, "already": False, "trial_until": ""}


def sign_out(token: str) -> bool:
    return True


def survey_reply(token: str, survey_id: int, answers: dict | None) -> bool:
    return True


def report(what: dict, record: bytes | None = None) -> bool:
    """In the place of `server.report`: nothing leaves this PC."""
    log.info("dev: not sent (%s: %s)", what.get("kind"), str(what.get("message", ""))[:80])
    return True
