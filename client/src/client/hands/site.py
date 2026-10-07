"""The website, as the app calls it: signing in and signing out (`website/site/API.md`, "For the app").

The app signs in with the website directly, never through the browser that holds the portal sessions. Every answer
is turned into one the window words for itself (`SignIn.svelte`):
the website's own code, or `unreachable` when no definite answer came back.

Every call names us in its `User-Agent` (Cloudflare refuses Python's default) and never sends an `Origin`.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from client.brand import NAME, SITE
from client.hands.hands import APP_VERSION

log = logging.getLogger(__name__)

TIMEOUT_S = 15.0
USER_AGENT = f"{NAME}-App/{APP_VERSION}"

SEND_CODES = ("bad_email", "no_account", "wait", "locked", "too_many_codes", "send_failed")
VERIFY_CODES = ("bad_email", "bad_code", "wrong", "locked", "expired", "pending_deletion")


def base() -> str:
    """The website's address: the app's one setting (`brand.json`), or `SITE` when a developer points it elsewhere."""
    return (os.environ.get("SITE") or SITE).rstrip("/")


def _post(path: str, body: dict, token: str = "") -> tuple[int, dict]:
    req = urllib.request.Request(base() + path, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT,
        **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:          # noqa: S310 - our own site
            return r.status, _json(r.read())
    except urllib.error.HTTPError as e:
        return e.code, _json(e.read())


def survey_reply(token: str, survey_id: int, answers: dict | None) -> bool:
    """A survey's answers, or its X (`answers` None: never asked again). True when the website took it, or the survey
    is no longer open (nothing more to do either way)."""
    body = {"id": survey_id, **({"answers": answers} if answers is not None else {"closed": True})}
    try:
        status, b = _post("/api/app/survey", body, token)
    except Exception as e:
        log.info("the survey: the website could not be reached: %s", e)
        return False
    return status == 200 or b.get("error") == "not_open"


def _json(raw: bytes) -> dict:
    try:
        got = json.loads(raw or b"{}")
    except ValueError:
        return {}
    return got if isinstance(got, dict) else {}


def send_code(email: str) -> dict:
    """Step 1: a 6-digit code to this email. {ok: true} or {ok: false, reason, wait}."""
    try:
        status, b = _post("/api/app/code", {"email": email})
    except Exception as e:                       # no connection, a timeout, a name that does not resolve
        log.info("sign-in: the website could not be reached: %s", e)
        return {"ok": False, "reason": "unreachable", "wait": 0}
    if status == 200 and b.get("ok") is True:
        return {"ok": True}
    if b.get("error") in SEND_CODES:
        return {"ok": False, "reason": b["error"], "wait": int(b.get("wait") or 0)}
    log.info("sign-in: the website answered %s %s", status, b.get("error") or "")
    return {"ok": False, "reason": "unreachable", "wait": 0}


def verify(email: str, code: str, version: str, device: str) -> dict:
    """Step 2: the code. {ok: true, token, email} or {ok: false, reason, left, deleteAfter}."""
    try:
        status, b = _post("/api/app/verify", {"email": email, "code": code, "version": version, "device": device})
    except Exception as e:
        log.info("sign-in: the website could not be reached: %s", e)
        return {"ok": False, "reason": "unreachable", "left": 0, "deleteAfter": ""}
    if status == 200 and isinstance(b.get("token"), str) and b["token"]:
        return {"ok": True, "token": b["token"], "email": b.get("email") or email}
    if b.get("error") in VERIFY_CODES:
        return {"ok": False, "reason": b["error"], "left": int(b.get("tries_left") or 0),
                "deleteAfter": str(b.get("delete_after") or "")}
    log.info("sign-in: the website answered %s %s", status, b.get("error") or "")
    return {"ok": False, "reason": "unreachable", "left": 0, "deleteAfter": ""}


def me(token: str) -> dict:
    """What the account's plan says, and the app's current version. {ok: true, active, paid_until, source, slots,
    arns, app} or {ok: false, reason}: `bad_token` (the website no longer knows this sign-in) or `unreachable` (no
    definite answer, which is never read as "no plan")."""
    req = urllib.request.Request(base() + "/api/app/me", headers={
        "Accept": "application/json", "User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:          # noqa: S310 - our own site
            b = _json(r.read())
        if isinstance(b.get("active"), bool):
            return {"ok": True, **b}
        status = 200
    except urllib.error.HTTPError as e:
        status, b = e.code, _json(e.read())
        if status == 401 and b.get("error") == "bad_token":
            return {"ok": False, "reason": "bad_token"}
    except Exception as e:
        log.info("the plan: the website could not be reached: %s", e)
        return {"ok": False, "reason": "unreachable"}
    log.info("the plan: the website answered %s %s", status, b.get("error") or "")
    return {"ok": False, "reason": "unreachable"}


BIND_CODES = ("arn_taken", "no_free_slot", "no_active_plan", "bad_arn", "no_holder", "bad_token")


def bind(token: str, arn: str, holder: str) -> dict:
    """Bind this ARN to the account: a free slot on a plan, or, on an account that has never had one, the start of
    its free trial. {ok: true, already, trial_until} or {ok: false, reason}: one of BIND_CODES, or `unreachable`."""
    try:
        status, b = _post("/api/app/bind", {"arn": arn, "holder": holder}, token)
    except Exception as e:
        log.info("binding %s: the website could not be reached: %s", arn, e)
        return {"ok": False, "reason": "unreachable"}
    if status == 200 and b.get("ok") is True:
        return {"ok": True, "already": bool(b.get("already")), "trial_until": str(b.get("trial_until") or "")}
    if b.get("error") in BIND_CODES:
        used = b["error"] == "no_active_plan" and b.get("trial_used") is True   # one free trial per email
        return {"ok": False, "reason": "trial_used" if used else b["error"]}
    log.info("binding %s: the website answered %s %s", arn, status, b.get("error") or "")
    return {"ok": False, "reason": "unreachable"}


def sign_out(token: str) -> bool:
    """End this PC's token on the website. The app forgets it whatever the answer: signing out never waits on us."""
    try:
        status, _ = _post("/api/app/signout", {}, token)
        return status == 200
    except Exception as e:
        log.info("sign-out: the website could not be reached (the token is forgotten here anyway): %s", e)
        return False
