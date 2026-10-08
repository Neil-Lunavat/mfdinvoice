"""The window's side of the app: every `App` method the window calls, and every push it hears.

This is the Python half of the one boundary written as types in `client/window/src/bridge/types.ts`. It is also what
asks the person a run's questions: each goes to the window as a push and comes back as the window's answer.

There is no GUI in this module. It is handed one function, `send`, that delivers a push to the window; the shell
(`shell.py`) passes pywebview's.

What stays on this PC: every credential (the CAMS email, the KFintech username and password), the mailbox's app
password, the signature, and every invoice. The credentials live in the vault; the window is shown masked forms.

Two servers, kept apart. The website (`site`) knows accounts: the app signs in with it (the token is kept in the
vault as `app_token`), reads what the plan says, and binds an ARN to the account. The software's own server
(`server`, `loader`) knows the software: it holds the current portal steps, and takes what is sent to support.

Everything else happens here. A run, Check status and Download invoices are the portal steps (`client.automation`),
fetched fresh and run on this PC in the hidden browser the app owns, one at a time (`_drive`). They are given a `Host`
and nothing else. A run is never resumed: Stop, a stop of its own, or closing the app ends it, and the next one starts
from the top with the files already on this PC.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import os
import platform
import re
import shutil
import socket
import subprocess
import threading
import time
import uuid
import webbrowser
import zipfile
import io
from datetime import date, datetime
from pathlib import Path

from playwright.async_api import Error as PWError

from client import errors
from client.credentials import CREDENTIALS, shown
from client.hands import certstore, loader, local, ops_export, ops_pdf, ops_sig, ops_sign, server, sign_image, site, update, zoho
from client.brand import NAME, SITE
from client.hands.browser import min_spec
from client.hands.hands import APP_VERSION, Hands
from client.hands.host import Host
from client.store.db import Store

log = logging.getLogger(__name__)

LINKS = {"site": SITE, "signup": f"{SITE}/signin?from=app", "status": f"{SITE}/support", "billing": f"{SITE}/account", "help": f"{SITE}/setup"}
PLAN_EVERY_S = 5 * 60          # the plan is read again this often while the app is open
PICKUP_EVERY_S = 90            # a month waiting for CAMS's email looks for it this often
RETRY_EVERY_S = 15             # ... and this often while the website could not be reached
UNREACHABLE = f"{NAME} can't reach its website right now. Try again in a minute."
NO_STEPS = f"{NAME} can't reach its server right now, so it can't be sure it is up to date with the portals."
RUNS_KEPT_DAYS = 30            # a run's record (pictures of the invoice pages) stays on this PC this long
# Why the website would not bind an ARN, in the window's words.
BIND_SAID = {
    "arn_taken": "Another account has this ARN. Send it to support and we'll sort it out.",
    "no_free_slot": "Every ARN slot on your plan is in use. More ARNs are added on the website.",
    "no_active_plan": "Your plan has ended. It is renewed on the website.",
    "trial_used": "This email has had its free trial. Buy a plan on the website, and the ARN goes on it.",
    "bad_token": "You've been signed out. Sign in again.",
}
LOG_TAIL = 60_000              # how much of the app's log goes with Send to support
TOKEN = "app_token"            # the vault key of the app's sign-in token: not a portal secret, never masked
# What signing out may also take off this PC: every credential and the signature, for every ARN set up here.
ON_THIS_PC = ("kfintech_password", "gmail_app_password", "cams_email", "kfintech_username", "forward_key",
              "forward_secret")


class Window:
    """The app, as the window sees it. `send(push)` delivers one push; every public coroutine is an `App` method."""

    def __init__(self, hands: Hands, store: Store, send):
        self.hands = hands
        self.store = store
        self.send = send
        self._portal = asyncio.Lock()                        # one piece of portal work at a time
        self._odd: dict[str, int] = {}                       # a portal's sign-in test that misbehaved, times in a row
        self.workspace = hands.cfg.paths.workspace
        self.started = time.monotonic()
        self.condition = "normal"
        self._seq = 0
        self._pending: dict[str, asyncio.Future] = {}        # ask id -> the answer
        self._task: asyncio.Task | None = None               # the run, check or download going now
        self._hold = False                                   # a Submit was pressed: Stop waits for its answer
        self._stop_wanted = False
        self._skip_cams = False                              # Skip CAMS was pressed while its email was awaited
        self.submit = True                                   # the shell turns it off in a checkout (config.toml)
        self._photo: bytes | None = None                     # the signature photo, in memory only, during intake
        self._turns = 0
        self._cleaned: tuple[bytes, float, float] | None = None
        self._found: dict[str, tuple[certstore.Cert, str]] = {}   # thumbprint -> a certificate just listed, its route
        self._testing_token = False
        self._ticks: asyncio.Task | None = None
        self.place: dict = {}                                # where the window is, so an update comes back there
        self.exit = None                                     # the shell's way to close the app, for an update
        self.choose_file = None                              # the shell's Open box: (title, types) -> a path or ""
        self._picked: dict[str, str] = {}                    # CAMS's two files, chosen by hand: zip, xls -> a path
        self.updated_from = ""                               # this start follows an update from that version
        self.update_failed_to = ""                           # ... or an update to that version that did not start
        self._updating = False
        self._books_busy = False
        self.online = True                                   # the network watcher's last answer
        self.retry_at = 0                                    # epoch ms of its next try while offline, else 0
        self._net_wake = asyncio.Event()                     # reconnect pressed: check now
        self._net_done: list[asyncio.Future] = []            # reconnect calls waiting for that check
        self._books_wake = asyncio.Event()                   # Refresh pressed while a run waits for the books
        hands.arn = lambda: self.selected()
        hands.signature_path = lambda: self.signature_file(self.selected())
        hands.asker = self
        self._credentials_to_the_vault()

    # --- the plumbing ---------------------------------------------------------------------------------------------

    def start(self) -> None:
        """Background upkeep: what the plan says, read when the app opens and again every few minutes."""
        local.put(self.store, "run_in_progress", None)       # closing the app ends a run: none carries over
        self._ticks = asyncio.create_task(self._tick())
        self._net = asyncio.create_task(self._watch_network())
        self._pickups = asyncio.create_task(self._pickup_loop())
        asyncio.get_running_loop().run_in_executor(None, self._tidy_runs)

    def _tidy_runs(self) -> None:
        old = time.time() - RUNS_KEPT_DAYS * 86400
        for d in (self.workspace / "runs").glob("*"):
            with contextlib.suppress(OSError):
                if d.is_dir() and d.stat().st_mtime < old:
                    shutil.rmtree(d)

    async def _pickup_loop(self) -> None:
        """While the software is open: CAMS's email for a month whose run went on without it is read in when it comes
        (Neil, 7 Oct). Only while some month waits for one; never while something else is running."""
        while True:
            await asyncio.sleep(PICKUP_EVERY_S)
            try:
                await self._pickup()
            except Exception:
                log.exception("picking up CAMS's email")

    async def _pickup(self) -> None:
        waiting = [(arn, period) for arn in self.profiles() for period in local.cams_waiting(self.base(arn))]
        if not waiting or self._task is not None:
            return
        auto = await loader.latest()
        if not hasattr(auto, "pickup"):
            return
        async with self._portal:
            for arn, period in waiting:
                host = Host(self, arn, "")
                try:
                    got = await auto.pickup(host, period)
                except Exception as e:
                    log.info("CAMS's email for %s %s couldn't be read in: %r", arn, period, e)
                    continue
                finally:
                    await host.close()
                if got.get("got"):
                    label = local.labels(period)[0]
                    self._log(f"CAMS's email for {label} came: its invoices are on this PC", registrar="CAMS",
                              tone="plain", who="")
                    self._note("cams_came", f"CAMS's invoices for {label} are in", "overview",
                               f"{got['got']} invoices, read from CAMS's email")
        await self.changed()

    async def _tick(self) -> None:
        while True:
            try:
                await self.read_plan()
            except Exception:
                log.exception("window upkeep")
            await asyncio.sleep(PLAN_EVERY_S if self.condition == "normal" else RETRY_EVERY_S)

    async def _watch_network(self) -> None:
        """The network toast's source: checked every 10 s while online; while offline retried after 1, 5, 10, 30 s, then
        every 2 min. Reconnect cuts the wait short."""
        waits = [1, 5, 10, 30, 120]
        failed = 0
        while True:
            try:
                wait = 10 if self.online else waits[min(failed, len(waits) - 1)]
                self.retry_at = 0 if self.online else int((time.time() + wait) * 1000)
                if not self.online:
                    await self.changed()
                try:
                    await asyncio.wait_for(self._net_wake.wait(), wait)
                except asyncio.TimeoutError:
                    pass
                self._net_wake.clear()
                now = await asyncio.to_thread(_internet)
                was = self.online
                self.online = now
                if now:
                    failed = 0
                    self.retry_at = 0
                    if not was:
                        await self.read_plan()
                else:
                    failed = failed + 1 if not was else 0
                    if was:
                        self.condition = "offline"
                if now != was or not now:
                    await self.changed()
            except Exception:
                log.exception("watching the network")
                await asyncio.sleep(5)
            finally:
                done, self._net_done = self._net_done, []
                for f in done:
                    if not f.done():
                        f.set_result(None)

    async def reconnect(self) -> dict:
        """Check the network now; answers once that check is done."""
        f = asyncio.get_running_loop().create_future()
        self._net_done.append(f)
        self._net_wake.set()
        await f
        return {"online": self.online}

    async def read_plan(self) -> None:
        """Ask the website what the account's plan says and which version of the app is current. No answer is its own
        state ("unknown", with the offline or trouble banner), never "no plan"; a sign-in the website no longer knows
        signs this PC out."""
        token = self.token()
        if not token:
            self.condition = "normal"
            return
        got = await asyncio.to_thread(site.me, token)
        if got["ok"]:
            self.condition = "normal"
            local.put(self.store, "licence", {
                "state": "active" if got["active"] else "ended" if got.get("paid_until") else "none",
                "source": got.get("source") or "", "until": got.get("paid_until") or "",
                "slots": int(got.get("slots") or 0), "arns": [f"ARN-{a['arn']}" for a in got.get("arns") or []],
                "trialUsed": bool(got.get("trial_used")), "checkedAt": local.note_now()})
            local.put(self.store, "release", got.get("app") or None)
            local.put(self.store, "survey", got.get("survey") or None)      # the live survey, asked on Overview
        elif got["reason"] == "bad_token":
            self.condition = "normal"
            self._signed_out()
        else:
            self.condition = "down" if await asyncio.to_thread(_internet) else "offline"
            local.put(self.store, "licence", {"state": "unknown", "checkedAt": local.note_now()})
        await self.changed()

    def _push(self, push: dict) -> None:
        try:
            self.send(push)
        except Exception:
            log.exception("a push to the window failed")

    async def changed(self) -> None:
        """The local store changed: the window redraws from a fresh snapshot."""
        self._push({"type": "snapshot", "snapshot": await self.load()})

    def _id(self) -> str:
        self._seq += 1
        return f"q{self._seq}-{uuid.uuid4().hex[:4]}"

    # --- the local store: accounts, ARNs, profiles ----------------------------------------------------------------

    def account(self) -> dict | None:
        """Signed in on this PC: the email, and whether to stay signed in. Only with a token in the vault."""
        acct = local.get(self.store, "account")
        return acct if acct and self.token() else None

    def token(self) -> str:
        return self.store.get_secret(TOKEN) or ""

    def profiles(self) -> dict[str, dict]:
        return local.get(self.store, "profiles", {})

    def selected(self) -> str:
        arn = self.store.get("selected_arn") or ""
        return arn if arn in self.profiles() else next(iter(self.profiles()), "")

    def profile(self) -> dict | None:
        return self.profiles().get(self.selected())

    def base(self, arn: str = "") -> Path:
        """This ARN's own folder: its months, each with its files and its record."""
        return self.workspace / "arns" / (re.sub(r"[^A-Za-z0-9-]", "", arn or self.selected()) or "none")

    def registrars(self, p: dict | None = None) -> list[str]:
        """The registrars this ARN uses, CAMS first."""
        p = p or self.profile() or {}
        return [r for r, used in (("CAMS", p.get("camsUsed", True)),
                                  ("KFINTECH", p.get("kfintech", {}).get("used", True))) if used]

    invoices_of = staticmethod(lambda p: invoices_of(p))

    def _save_profile(self, p: dict) -> None:
        all_ = self.profiles()
        all_[p["arn"]] = p
        local.put(self.store, "profiles", all_)

    def credential(self, arn: str, name: str) -> str:
        """One of this ARN's credentials, from the vault (`client.credentials.CREDENTIALS`)."""
        return self.store.get_secret(f"{name}:{arn}") or ""

    def _credentials_to_the_vault(self) -> None:
        """The CAMS email and the KFintech username are credentials, so they live in the vault with the
        password, and the window is shown only a masked form. A profile saved before kept them in plain
        settings; they move once, and the profile keeps neither."""
        all_, moved = self.profiles(), False
        for arn, p in all_.items():
            email = (p.get("camsEmail") or "").strip()
            user = ((p.get("kfintech") or {}).get("username") or "").strip()
            if email:
                self.store.put_secret(f"cams_email:{arn}", email)
                p["camsEmail"], moved = "", True
            if user:
                self.store.put_secret(f"kfintech_username:{arn}", user)
                p["kfintech"]["username"], moved = "", True
        if moved:
            local.put(self.store, "profiles", all_)
            if self.selected():
                self._activate(self.selected())
            log.info("the CAMS email and KFintech username moved into the vault")

    def signature_file(self, arn: str) -> Path:
        if not arn:
            return self.hands.cfg.paths.signature
        return self.workspace / "signatures" / f"{re.sub(r'[^A-Za-z0-9-]', '', arn)}.png"

    def _log(self, text: str, tone: str = "setting", registrar: str | None = None, who: str = "you, on this PC") -> None:
        rows = local.get(self.store, "local_activity", [])
        rows.append({"at": local.note_now(), "text": text, "registrar": registrar, "who": who, "tone": tone})
        local.put(self.store, "local_activity", rows[-2000:])      # nothing is purged by choice; this caps a runaway

    log_activity = _log

    def _note(self, kind: str, text: str, opens: str, detail: str = "") -> None:
        notes = local.get(self.store, "notes", [])
        notes.insert(0, {"id": "n" + uuid.uuid4().hex[:8], "kind": kind, "text": text, "detail": detail,
                         "opens": opens, "when": local.note_now(), "read": False})
        local.put(self.store, "notes", notes[:200])

    def _activate(self, arn: str) -> None:
        """The vault holds one set of credentials and one mailbox for the ARN being worked on; each ARN's own are
        kept beside them and copied in when it is picked."""
        for key in ("kfintech_password", "gmail_app_password", "forward_key", "forward_secret", *CREDENTIALS):
            mine = self.store.get_secret(f"{key}:{arn}")
            if mine:
                self.store.put_secret(key, mine)
        for key in ("mail_provider", "gmail_user", "forward_email"):
            mine = self.store.get(f"{key}:{arn}")
            if mine is not None:
                self.store.put(key, mine)

    def _keep_for(self, arn: str) -> None:
        for key in ("kfintech_password", "gmail_app_password", "forward_key", "forward_secret", *CREDENTIALS):
            v = self.store.get_secret(key)
            if v:
                self.store.put_secret(f"{key}:{arn}", v)
        for key in ("mail_provider", "gmail_user", "forward_email"):
            v = self.store.get(key)
            if v is not None:
                self.store.put(f"{key}:{arn}", v)

    # =============================================================================================================
    # App: what the window asks
    # =============================================================================================================

    async def load(self) -> dict:
        """The snapshot, from disk. Never waits on the network."""
        now = local.current_period()
        p = self.profile()
        m = local.month(self.base(), now) if p else None
        rows = local.year(self.base(), now) if p else []
        acct = self.account()
        run = local.get(self.store, "run_in_progress")
        status, rejected = local.month_status(m["invoices"]) if m else ("Not submitted", 0)
        return {
            "version": APP_VERSION,
            "condition": self.condition,
            "network": {"online": self.online, "retryAt": self.retry_at},
            "update": self._update_view(),
            "account": {"email": acct["email"], "maxArns": 6} if acct else None,
            "plan": self._plan_view() if acct else None,
            "survey": (local.get(self.store, "survey") or None) if acct else None,
            "deleting": "" if acct else (local.get(self.store, "deleting") or ""),
            "arns": [{"arn": a, "name": q.get("name", ""), "status": status if a == self.selected() else
                      "Not submitted", "rejected": rejected if a == self.selected() else 0}
                     for a, q in self.profiles().items()],
            "arn": self.selected(),
            "today": date.today().isoformat(),
            "profile": self._profile_view(p) if p else None,
            "month": m,
            "year": rows,
            "notes": local.get(self.store, "notes", []),
            "activity": local.activity(self.store),
            "fy": local.financial_year(now),
            "run": {"run": run["run"], "registrars": run["registrars"], "startedAt": run["startedAt"],
                    "what": run.get("what", "run"), "period": run.get("period", now)}
                   if run and run.get("arn") == self.selected() else None,
            "clash": local.get(self.store, "clash"),
        }

    def _update_view(self) -> dict | None:
        """The update screen, when it shows: the website's current version is newer than this app, no run is going on
        this PC (it finishes first), and the plan has not ended (the plan screen first: an ended plan cannot
        download)."""
        r = local.get(self.store, "release") or {}
        if not self.account() or not _older(APP_VERSION, str(r.get("version") or "")):
            return None
        if local.get(self.store, "run_in_progress") or (self._plan_view() or {}).get("state") == "ended":
            return None
        return {"version": r["version"], "why": r.get("note") or "",
                "failed": local.get(self.store, "update_failed") == r["version"]}

    def _profile_view(self, p: dict) -> dict:
        return {"arn": p["arn"], "name": p.get("name", ""), "gstin": p.get("gstin", ""),
                "arnConfirmed": bool(p.get("arnConfirmed")),
                "bindOnRun": bool(p.get("bindOnRun")), "bindAsked": bool(p.get("bindAsked")),
                "camsUsed": bool(p.get("camsUsed", True)),
                "camsEmail": shown(self.credential(p["arn"], "cams_email")),
                "camsArn": p.get("camsArn", ""),
                "mailbox": p.get("mailbox", {"provider": "gmail", "address": "", "connected": False}),
                "kfintech": {"arn": "", **p.get("kfintech", {"used": True, "username": "", "loggedInAs": ""}),
                             "username": shown(self.credential(p["arn"], "kfintech_username"))},
                "signature": self._signature_view(p["arn"]),
                "invoices": invoices_of(p),
                "books": local.books_kept(self.base(p["arn"]))["kind"],
                "usedTop": local.issued_top(self.base(p["arn"])),
                "lastLogin": p.get("lastLogin", {"CAMS": "", "KFINTECH": ""}),
                "kept": local.books_kept(self.base(p["arn"])),
                "consent": p.get("consent") or None}

    def _signing(self, arn: str) -> dict:
        """How this ARN signs, as kept beside its signature: what the door reads (`ops_sign`)."""
        return {**(local.get(self.store, f"signature:{arn}") or {}), **sign_image.meta_of(self.signature_file(arn))}

    def _signature_view(self, arn: str) -> dict:
        """The person's way of signing, for the window: the image (made on this PC, shown on this PC), or which
        certificate was picked. `present`: the chosen way is set up."""
        sig, meta = self.signature_file(arn), self._signing(arn)
        way = ops_sign.DSC if meta.get("way") == ops_sign.DSC else ops_sign.IMAGE
        cert = meta.get("cert") if isinstance(meta.get("cert"), dict) else None
        if cert:
            cert = {"thumbprint": cert.get("thumbprint", ""), "name": cert.get("name", ""),
                    "issuer": cert.get("issuer", ""), "expires": cert.get("expires", ""),
                    "route": meta.get("route") or ops_sign.WINDOWS, "tested": True}
        return {"way": way, "present": bool(cert) if way == ops_sign.DSC else sig.exists(),
                "image": ops_sig.data_url(sig.read_bytes()) if sig.exists() else "",
                "size": int(meta.get("size", 100)), "cert": cert}

    def _plan_view(self) -> dict | None:
        """What the plan says, as the website last said it (`read_plan`); None before it has."""
        got = local.get(self.store, "licence")
        if not got:
            return None
        return {"state": got.get("state", "unknown"), "source": got.get("source") or "",
                "until": got.get("until") or "", "slots": int(got.get("slots") or 0), "arns": list(got.get("arns") or []),
                "checkedAt": got.get("checkedAt") or ""}

    # --- signing in and out, with the website --------------------------------------------------

    async def send_code(self, email: str) -> dict:
        return await asyncio.to_thread(site.send_code, email.strip())

    async def verify_code(self, email: str, code: str) -> dict:
        got = await asyncio.to_thread(site.verify, email.strip(), code.strip(), APP_VERSION, platform.node()[:60])
        if not got["ok"]:
            return got
        self.store.put_secret(TOKEN, got["token"])
        local.put(self.store, "account", {"email": got["email"]})
        local.put(self.store, "licence", None)
        local.put(self.store, "deleting", None)
        self._log(f"Signed in as {got['email']}")
        await self.read_plan()
        return {"ok": True}

    async def answer_survey(self, survey_id: int, answers: dict | None = None) -> dict:
        """The survey on Overview: its answers, or its X (`answers` None). Either way it is not asked again."""
        token = self.token()
        sent = bool(token) and await asyncio.to_thread(site.survey_reply, token, int(survey_id), answers)
        if sent:
            local.put(self.store, "survey", None)
            await self.changed()
        return {"sent": sent}

    async def sign_out(self, remove: bool = False) -> None:
        """Settings › Account & plan › Sign out. The token ends on the website and is forgotten here; the invoice files
        stay, and the logins and signature stay too unless the person asked for them to go."""
        token = self.token()
        if token:
            await asyncio.to_thread(site.sign_out, token)
        self._signed_out()
        if remove:
            for arn in list(self.profiles()) + [""]:
                for key in ON_THIS_PC:
                    self.store.put_secret(f"{key}:{arn}" if arn else key, None)
                sig = self.signature_file(arn)
                for f in (sig, sig.with_suffix(".json")):          # the image, and which certificate was picked
                    if arn and f.exists():
                        f.unlink()
                if arn:
                    local.put(self.store, f"signature:{arn}", None)
            self.hands.door.release()
        self._log("Signed out of this PC" + (", and removed the passwords and signature" if remove else ""))
        await self.changed()

    def _signed_out(self) -> None:
        self.store.put_secret(TOKEN, None)
        local.put(self.store, "account", None)
        local.put(self.store, "licence", None)

    async def activate_trial(self) -> dict:
        """Bind the ARN on screen to the account. On an account that has never had a plan this is Activate free
        trial: the 15 days start now. On one with a plan it takes a free slot."""
        p = self.profile()
        if not p:
            return {"ok": False, "said": "No ARN is set up."}
        if p.get("bindOnRun"):
            # CAMS alone can't prove the ARN at setup: the first run binds it, once CAMS's emailed files are read
            p["bindAsked"] = True
            self._save_profile(p)
            self._log(f"{p['arn']} will be added when its first run reads CAMS's files")
            await self.changed()
            return {"ok": True}
        got = await asyncio.to_thread(site.bind, self.token(), p["arn"], p.get("name") or p["arn"])
        if not got["ok"]:
            return {"ok": False, "said": BIND_SAID.get(got["reason"], UNREACHABLE)}
        self._log(f"Activated the free trial for {p['arn']}" if got["trial_until"] else f"Added {p['arn']} to the plan")
        await self.read_plan()
        return {"ok": True}

    async def confirm_arn(self, arn: str) -> dict:
        """A run's CAMS files for this ARN have been read: the proof the person gets its mail. Bind it now (the free
        trial starts, or it takes a slot). Only for an ARN set up without KFintech, whose setup bound nothing."""
        p = self.profiles().get(arn)
        if not p or not p.get("bindOnRun"):
            return {"ok": True}
        got = await asyncio.to_thread(site.bind, self.token(), arn, p.get("name") or arn)
        if not got["ok"]:
            return {"ok": False, "said": BIND_SAID.get(got["reason"], UNREACHABLE)}
        p.pop("bindOnRun", None)
        p.pop("bindAsked", None)
        self._save_profile(p)
        self._log(f"Activated the free trial for {arn}" if got.get("trial_until") else f"Added {arn} to the plan")
        await self.read_plan()
        return {"ok": True}

    async def check_plan(self) -> None:
        """Try again, on "We couldn't check your plan just now"."""
        await self.read_plan()

    async def agree(self, consent: dict) -> dict:
        """The authority sentence, ticked again for the ARN on screen (a new wording, or a profile from before it)."""
        p = self.profile()
        if not p:
            return {"ok": False, "said": "No ARN is set up."}
        p["consent"] = _consent(consent)
        self._save_profile(p)
        self._log(f"Authorised {NAME} to act on CAMS and KFintech for {p['arn']}")
        await self.changed()
        return {"ok": True}

    # --- setup, and every Change -----------------------------------------------------------------------------

    async def forward_start(self, email: str) -> dict:
        """Forwarding CAMS's mailbacks to us: a code is emailed to the CAMS email (hands/forward.py)."""
        from client.hands import forward
        return await asyncio.to_thread(forward.start, self.store, email)

    async def forward_verify(self, email: str, code: str) -> dict:
        from client.hands import forward
        return await asyncio.to_thread(forward.verify, self.store, email, code)

    async def forward_gmail_code(self) -> str:
        from client.hands import forward
        return await asyncio.to_thread(forward.gmail_code, self.store)

    async def test_mailbox(self, provider: str, address: str, appPassword: str) -> dict:  # noqa: N803
        from client.hands import inbox, mail
        if provider == "folder":
            self.store.put("mail_provider", "folder")
            found = len(inbox.scan(self.hands.cfg.paths.inbox))
            return {"ok": True, "found": found, "as": ""}
        try:
            password = appPassword or self.store.get_secret("gmail_app_password") or ""
            found = await asyncio.to_thread(_count_gmail, address.strip(), password)
        except mail.MailError as e:
            return {"ok": False, "said": str(e)}
        except Exception as e:                                   # a network we cannot reach, say
            return {"ok": False, "said": f"Couldn't reach the mailbox: {e}"}
        # A pass saves it, on this PC only.
        self.store.put("mail_provider", "gmail")
        self.store.put("gmail_user", address.strip())
        self.store.put_secret("gmail_app_password", password)
        return {"ok": True, "found": found, "as": address.strip()}

    async def test_cams(self, email: str, arn: str = "") -> dict:
        """Sign in to CAMS with this email, once, and say which ARN CAMS shows (and the holder's name beside it); then
        sign out, so the first run's sign-in is one press and not two. Setup never types the ARN: the window compares
        what CAMS shows with the other login's. CAMS saying no comes back in its own words (`said`); anything else that
        goes wrong is ours (`ours`), in a sentence of our own, with the detail in the log."""
        if self._task is not None:
            return {"ok": False, "said": "A run is going. Verify once it has ended.", "ours": True}
        try:
            auto = await loader.latest()
        except (loader.Unreachable, loader.NotOurs):
            return {"ok": False, "said": NO_STEPS, "ours": True}
        host = Host(self, arn.strip().upper(), "")
        async with self._portal:
            page = None
            try:
                page = await host.fresh_page()
                found = await auto.cams.arn_of(page, email.strip())
                if len(found) != 1:                          # one ARN per login: never a pick among several
                    log.info("the CAMS test: the page showed %d ARNs: %s", len(found), sorted(found))
                    return {"ok": False, "ours": True,
                            "said": "CAMS showed no ARN." if not found
                            else "CAMS showed more than one ARN: " + ", ".join(sorted(found)) + "."}
                cams_arn = next(iter(found))
                name = await auto.cams.name_of(page, cams_arn) if hasattr(auto.cams, "name_of") else ""
                await auto.cams.sign_out(page)
            except auto.page.Refused as e:
                log.info("the CAMS test: CAMS said %r", e.said)
                return {"ok": False, "said": e.said}
            except auto.page.Stop as e:
                return {"ok": False, "said": e.said or e.title, **({"ours": True} if e.kind == "ours" else {})}
            except (auto.page.Changed, PWError, errors.Failure) as e:
                return await self._ours("CAMS", e)
            finally:
                with contextlib.suppress(Exception):
                    if page is not None:
                        await page.close()
                await host.close()
        self._odd.pop("CAMS", None)
        self._log("Verified the CAMS email", registrar="CAMS")
        return {"ok": True, "arn": cams_arn, "name": name}

    async def _ours(self, portal: str, e: Exception) -> dict:
        """A portal test that failed for a reason of ours, or of this PC's: said in our own sentence, never as the
        portal's words. The detail goes in the log, which Send to support carries. No internet says so. A page that
        misbehaves once is a try-again; twice in a row, the portal has likely changed (`changed`: the window offers
        skipping this portal for now, or Send to support)."""
        log.warning("the %s test: %s: %s", portal, type(e).__name__, e)
        if isinstance(e, errors.Failure):
            return {"ok": False, "said": e.message, "ours": True}
        if not await asyncio.to_thread(_internet):
            return {"ok": False, "ours": True, "said": "No internet connection. Check it, then verify again."}
        self._odd[portal] = self._odd.get(portal, 0) + 1
        if self._odd[portal] >= 2:
            return {"ok": False, "ours": True, "changed": True, "said": f"Something on the {portal} portal seems to have changed."}
        return {"ok": False, "ours": True, "said": f"{portal} portal behaved unexpectedly, try again."}

    async def test_kfintech(self, username: str, password: str, expect: str = "") -> dict:
        """A test login, with the captcha asked in the window; `arn` in the answer is the ARN KFintech's dashboard
        shows (one ARN per login: none or several is a stop). `expect` is the ARN the other login showed, '' if none:
        the profile is read only when it is the same. A pass keeps the username and the password in this PC's vault; what the window is told it logged in
        as is the username's masked form, never the username itself."""
        username = username.strip()
        if self._task is not None:
            return {"ok": False, "said": "A run is going. Verify once it has ended.", "ours": True}
        try:
            auto = await loader.latest()
        except (loader.Unreachable, loader.NotOurs):
            return {"ok": False, "said": NO_STEPS, "ours": True}
        host = Host(self, expect.strip().upper(), "")
        async with self._portal:
            page = None
            try:
                page = await host.fresh_page()
                found = await auto.kfin.arn_of(page, username, password, host.captcha)
                if len(found) != 1:
                    log.info("the KFintech test: the page showed %d ARNs: %s", len(found), sorted(found))
                    return {"ok": False, "ours": True,
                            "said": "KFintech showed no ARN." if not found
                            else "KFintech showed more than one ARN: " + ", ".join(sorted(found)) + "."}
                kf_arn = next(iter(found))
                seen = {"name": "", "gstin": ""}
                if hasattr(auto.kfin, "profile_of") and (not expect or kf_arn == expect.strip().upper()):
                    seen = await auto.kfin.profile_of(page)          # only for the ARN already read: never another's name
            except auto.kfin.Cancelled:
                return {"ok": False, "said": "", "ours": True}
            except auto.page.Refused as e:
                log.info("the KFintech test: KFintech said %r", e.said)
                return {"ok": False, "said": e.said}
            except auto.page.Stop as e:                  # no words of KFintech's: the title is ours
                return {"ok": False, "said": e.said or e.title, **({"ours": True} if not e.said else {})}
            except (auto.page.Changed, PWError, errors.Failure) as e:
                return await self._ours("KFintech", e)
            finally:
                with contextlib.suppress(Exception):
                    if page is not None:
                        await page.close()
                await host.close()
        self._odd.pop("KFintech", None)
        self.store.put_secret("kfintech_password", password)
        self.store.put_secret("kfintech_username", username)
        self._log("Verified the KFintech login", registrar="KFINTECH")
        return {"ok": True, "as": shown(username), "arn": kf_arn,
                "name": seen["name"], "gstin": seen["gstin"]}

    async def prepare_signature(self, bytes: str) -> dict:  # noqa: A002 - the window's own name for it
        try:
            self._photo = base64.b64decode(bytes)
        except ValueError:
            return {"ok": False, "said": "That file couldn't be read."}
        self._turns = 0
        return await self._clean()

    async def rotate_signature(self) -> dict:
        if not self._photo:
            return {"image": ""}
        self._turns = (self._turns + 1) % 4
        got = await self._clean()
        return {"image": got.get("image", "")}

    async def drop_signature_draft(self) -> None:
        """A photo that was prepared and then not kept: forget it, so the previews draw the saved signature again."""
        self._photo = self._cleaned = None
        self._turns = 0

    async def _clean(self) -> dict:
        try:
            im, cx, cy = await asyncio.to_thread(ops_sig.prepare, self._photo, self._turns)
        except ops_sig.NoInk:
            self._cleaned = None
            return {"ok": False, "said": "No signature could be found in this photo. Sign on plain white paper and "
                                         "take the photo in daylight."}
        png = ops_sig.png(im)
        self._cleaned = (png, cx, cy)
        return {"ok": True, "image": ops_sig.data_url(png)}

    # --- a USB token -------------------------------------------------------------------------

    async def find_certificates(self) -> dict:
        """The signing certificates on the tokens plugged in now. Through Windows' certificate store; only when it
        lists none, through the token's own driver, where the PIN is typed in the window (`route`: pin)."""
        certs, route = await asyncio.to_thread(certstore.certificates), ops_sign.WINDOWS
        if not certs:
            from client.hands import tokenpin
            certs, route = await asyncio.to_thread(tokenpin.certificates), ops_sign.PIN
        self._found = {c.thumbprint: (c, route) for c in certs}
        return {"certs": [{**c.view(), "route": route, "tested": False} for c in certs]}

    async def test_certificate(self, thumbprint: str, route: str = ops_sign.WINDOWS) -> dict:
        """A test signature with the certificate picked, so setup knows the token signs on this PC before a run needs
        it. The token's own software asks for its PIN; on the second route the window does (an Ask arrives meanwhile).
        `other`: it did not sign through Windows, and its driver can reach it: try with the PIN typed here."""
        from client.hands import tokenpin
        found = self._found.get(thumbprint)
        if route == ops_sign.PIN and (not found or found[1] != ops_sign.PIN):
            other = next((c for c in await asyncio.to_thread(tokenpin.certificates) if c.thumbprint == thumbprint),
                         None)
            if other is None:
                return {"ok": False, "said": "Your token couldn't be reached that way either.", "other": False}
            found = self._found[thumbprint] = (other, ops_sign.PIN)
        driver = found[0].provider if found and route == ops_sign.PIN else ""
        self._testing_token = True
        try:
            key = await ops_sign.open_token(route, driver, thumbprint, self.hands.hwnd(), self.pin)
            await asyncio.to_thread(key.close)
        except certstore.StoreError as e:
            other = route == ops_sign.WINDOWS and e.why == "failed" and any(
                c.thumbprint == thumbprint for c in await asyncio.to_thread(tokenpin.certificates))
            return {"ok": False, "said": ops_sign.failure(e).message, "other": other}
        finally:
            self._testing_token = False
        return {"ok": True}

    async def token_here(self) -> bool:
        """Check your details: is the token this ARN signs with plugged in? True for the image, and whenever it
        cannot be told."""
        return await asyncio.to_thread(self.hands.door.here)

    async def pin(self, said: str) -> str | None:
        """A token's PIN, typed in the window: only for a token Windows cannot reach. It goes back to the token and
        is kept nowhere."""
        run = (local.get(self.store, "run_in_progress") or {}).get("run", "")
        a = await self._ask("setup" if self._testing_token else run,
                            {"type": "pin", "said": said, "during": "setup" if self._testing_token else "run"})
        return a.get("value") or None

    def _keep_signature(self, arn: str, sig: dict) -> str:
        """How this ARN signs, on this PC only. The image way: the cleaned signature, as a PNG with alpha, and the two
        numbers measured on it. A token: which certificate was picked and the route that reached it, never a key or a
        PIN. Each way's setup is kept when the other is chosen. Returns the activity line."""
        path = self.signature_file(arn)
        meta = self._signing(arn)
        was = meta.get("way")
        if sig.get("way") == ops_sign.DSC:
            cert = sig.get("cert") or {}
            found = self._found.get(cert.get("thumbprint", ""))
            route = cert.get("route") or (found[1] if found else meta.get("route")) or ops_sign.WINDOWS
            meta.update({"way": ops_sign.DSC, "route": route,
                         "cert": {k: str(cert.get(k) or "") for k in ("thumbprint", "name", "issuer", "expires")}})
            if route == ops_sign.PIN and found:
                meta["driver"] = found[0].provider
            what = ("Signature: your USB token's certificate changed" if was == ops_sign.DSC
                    else "Signature: now your USB token")
        else:
            size = int(sig.get("size") or 100)
            if self._cleaned:
                png, cx, cy = self._cleaned
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png)
                meta.update({"cx": cx, "cy": cy})
                self._cleaned = self._photo = None
            meta.update({"way": ops_sign.IMAGE, "size": size})
            what = "Signature: now your signature's photo" if was == ops_sign.DSC else "Signature replaced"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
        local.put(self.store, f"signature:{arn}", meta)
        self.hands.door.release()                         # a token opened under the old choice is let go
        return what

    async def finish_setup(self, draft: dict, adding: bool) -> dict:
        arn = draft["arn"].strip().upper()
        if arn in self.profiles():
            return {"ok": False, "said": f"{arn} is already on this account."}
        if refused := await self._rule_46(invoices_of(draft)["last"]):
            return {"ok": False, "said": refused}
        if len(self.profiles()) >= 6:
            return {"ok": False, "said": "One account holds up to 6 ARNs. For more, talk to us."}
        if not (draft.get("consent") or {}).get("version"):
            return {"ok": False, "said": f"Tick that you authorise {NAME} to act for you on each registrar you use."}
        # Finishing binds the ARN to the account, now that KFintech's sign-in (a password) has shown it. An account
        # with a plan takes a slot here; one that has never had a plan is bound when it activates its free trial.
        # Without KFintech, CAMS's sign-in proves too little: the first run binds the ARN once it has read CAMS's
        # emailed files for it (`confirm_arn`). Nothing is kept on this PC until the website has said yes.
        bind_on_run = not draft["kfintech"].get("used")
        await self.read_plan()
        state = (self._plan_view() or {}).get("state", "unknown")
        if state == "unknown":
            return {"ok": False, "said": UNREACHABLE}
        if state == "active" and not bind_on_run:
            got = await asyncio.to_thread(site.bind, self.token(), arn, draft["name"].strip() or arn)
            if not got["ok"]:
                return {"ok": False, "said": BIND_SAID.get(got["reason"], UNREACHABLE)}
        self._keep_signature(arn, draft["signature"])
        # The credentials go into the vault, as the ones being worked on (the KFintech pair is already there from the
        # test login); `_keep_for` then keeps this ARN's own copies. The profile holds none of them.
        cams_used = bool(draft.get("camsUsed", True))
        self.store.put_secret("cams_email", (draft["camsEmail"].strip() or None) if cams_used else None)
        if not draft["kfintech"].get("used"):
            for key in ("kfintech_username", "kfintech_password"):
                self.store.put_secret(key, None)
        p = {"arn": arn, "name": draft["name"].strip(), "gstin": draft["gstin"].strip().upper(),
             "camsUsed": cams_used,
             "camsEmail": "", "camsArn": draft.get("camsArn", "") if cams_used else "", "mailbox": draft["mailbox"],
             "kfintech": {**draft["kfintech"], "username": ""},
             # the window finishes setup only once a portal's sign-in has shown this ARN
             "invoices": invoices_of(draft), "arnConfirmed": True, "lastLogin": {"CAMS": "", "KFINTECH": ""},
             "consent": _consent(draft["consent"])}
        if bind_on_run:
            p["bindOnRun"] = True
        self._save_profile(p)
        self._keep_for(arn)
        # the books chosen at setup: one per ARN, so the other kind's choices and grant go
        tpick, zpick = draft.get("tally") or {}, draft.get("zoho") or {}
        try:
            books = await self._books()
            if zpick.get("orgId"):
                books.keep("zoho", self.base(arn), zpick)
            elif tpick.get("company") and tpick.get("guid"):
                books.keep("tally", self.base(arn), tpick)
            else:
                books.forget(self.base(arn))
            if not zpick.get("orgId") and zoho.connected(self.store, arn):
                await asyncio.to_thread(zoho.disconnect, self.store, arn)
        except Exception:
            log.exception("the books chosen at setup could not be kept")        # the Books tab asks again
        self.store.put("selected_arn", arn)
        self._log(f"Set up {arn}")
        await self.read_plan()
        return {"ok": True}

    async def save_details(self, patch: dict) -> dict:
        p = self.profile()
        if not p:
            return {"ok": False, "said": "No ARN is set up."}
        what = "Details changed"
        old_email = self.credential(p["arn"], "cams_email")
        new_email = (patch.get("camsEmail") or "").strip()
        if "camsUsed" in patch and bool(patch["camsUsed"]) != bool(p.get("camsUsed", True)):
            p["camsUsed"] = bool(patch["camsUsed"])
            what = "CAMS turned on for this ARN" if p["camsUsed"] else "CAMS turned off for this ARN"
            if not p["camsUsed"]:
                p["camsArn"] = ""
        if new_email and (new_email.lower() != old_email.lower() or patch.get("camsArn")):
            mailbox = p.get("mailbox", {}).get("address", "")
            if mailbox and old_email and mailbox.strip().lower() == old_email.strip().lower():
                # CAMS mails go to the CAMS email; the run waits until the person picks a mailbox (§8). Kept here, so
                # it survives the app closing - with the new email masked, because it is a credential.
                local.put(self.store, "clash", {"mailbox": mailbox, "camsEmail": shown(new_email)})
            self.store.put_secret("cams_email", new_email)             # `_keep_for` below keeps this ARN's copy
            p["camsArn"] = patch.get("camsArn", "")
            what = f"CAMS email changed to {shown(new_email)}"
        if "mailbox" in patch:
            p["mailbox"] = patch["mailbox"]
            local.put(self.store, "clash", None)
            what = f"Mailbox changed to {patch['mailbox'].get('address') or 'a folder'}"
        if "kfintech" in patch:
            # the username went into the vault with the test login that unlocked Save; the profile never keeps it
            p["kfintech"] = {**patch["kfintech"], "username": ""}
            what = "KFintech login changed" if patch["kfintech"].get("used") else "KFintech turned off for this ARN"
        if "signature" in patch:
            what = self._keep_signature(p["arn"], patch["signature"])
        for key in ("name", "gstin"):
            if key in patch:
                p[key] = patch[key].strip()
                what = "Your details changed"
        if "invoices" in patch:
            if refused := await self._rule_46(invoices_of({"invoices": patch["invoices"]})["last"]):
                return {"ok": False, "said": refused}
            before = invoices_of(p)
            p["invoices"] = invoices_of({"invoices": patch["invoices"]})
            what = ("Invoices: your own, in your number series" if p["invoices"]["source"] == "own"
                    else "Invoices: the registrar's, signed") if before["source"] != p["invoices"]["source"]                 else "Your invoice's details changed"
        self._save_profile(p)
        self._keep_for(p["arn"])
        self._log(what)
        await self.changed()
        return {"ok": True}

    async def switch_arn(self, arn: str) -> None:
        if arn not in self.profiles() or arn == self.selected() or self._task is not None:
            return
        self._keep_for(self.selected())
        self.store.put("selected_arn", arn)
        self._activate(arn)
        await self.changed()

    # --- the month ---------------------------------------------------------------------------------------------

    async def month(self, period: str) -> dict:
        return local.month(self.base(), period)

    async def preview_invoice(self, settings: dict, number: str) -> str:
        """The person's own invoice with the settings on screen, laid out and drawn exactly as a run draws it, with an
        example fund house and their signature where it will go: its first page, as a data URL. `settings` also
        carries the name and GSTIN on screen, and `signatureSize`. '' when it cannot be drawn (a preview is never
        worth an error; the reason is in the log)."""
        try:
            auto = await loader.current()
            return await asyncio.to_thread(self._draw_preview, auto, settings or {}, number or "")
        except Exception:
            log.exception("the invoice preview could not be drawn")
            return ""

    def _draw_preview(self, auto, settings: dict, number: str) -> str:
        p = self.profile() or {}
        template, inv, me = auto.sample({**BLANK_SETTINGS, **settings}, number,
                                        settings.get("name") or p.get("name") or "",
                                        settings.get("gstin") or p.get("gstin") or "")
        page_w, page_h = template["page"]
        return self._signed_page(auto, auto.layout.draw(template, inv, me), page_w, page_h,
                                 settings.get("signatureSize"), "invoice-preview.pdf")

    async def preview_registrar(self, kind: str, name: str = "", gstin: str = "", arn: str = "",
                                signatureSize: int = 100) -> str:  # noqa: N803
        """An example of a registrar's own invoice (`kind`: cams or kfintech), made out to this person, with their
        signature where a run puts it: its first page, as a data URL. '' when it cannot be drawn."""
        p = self.profile() or {}
        try:
            auto = await loader.current()
            if kind not in auto.registrar.KINDS:
                return ""
            ops, page_w, page_h = auto.registrar.example(kind, name or p.get("name") or "",
                                                         gstin or p.get("gstin") or "", arn or p.get("arn") or "")
            return await asyncio.to_thread(self._signed_page, auto, ops, page_w, page_h, signatureSize,
                                           f"{kind}-preview.pdf")
        except Exception:
            log.exception("the %s preview could not be drawn", kind)
            return ""

    def _signed_page(self, auto, ops: list[dict], page_w: float, page_h: float, size, name: str) -> str:
        """Draw this draw-list with the signature on screen placed by the run's own rule, and return its first page.
        One at a time: the previews share the signature's draft file, and two drawn at once (CAMS's and KFintech's,
        after the size slider is let go) read it half-written (8 Oct)."""
        with _DRAWING:
            door = ops_sign.Door(lambda: self._signature_on_screen(size))
            sig = door.info()
            if sig.get("present"):
                ops = auto.layout.sign(ops, sig, page_w, page_h)
            out = self.workspace / "previews" / name
            ops_pdf.render_to(door, out, page_w, page_h, ops)
            return ops_export.first_page(out)

    def _signature_on_screen(self, size) -> Path:
        """The signature a preview draws: the photo being set up right now, if there is one (it is saved only when
        setup or the Change is), else this ARN's own, in either case at the size on screen. Drawn from a copy kept
        beside the others, as `_draft`."""
        saved = self.signature_file(self.selected())
        if self._cleaned:
            png, cx, cy = self._cleaned
        elif saved.exists() and sign_image.meta_of(saved).get("way") != ops_sign.DSC:
            meta = sign_image.meta_of(saved)
            png, cx, cy = saved.read_bytes(), meta.get("cx"), meta.get("cy")
        else:
            return saved
        draft = self.workspace / "signatures" / "_draft.png"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_bytes(png)
        meta = {"way": ops_sign.IMAGE, "size": int(size or 100)}
        if cx is not None and cy is not None:
            meta.update({"cx": cx, "cy": cy})
        draft.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
        return draft

    def _file_of(self, key: str) -> Path | None:
        """The PDF of one invoice: signed, once it has been."""
        return local.file_of(self.base(), key)

    async def preview(self, key: str) -> str:
        path = self._file_of(key)
        if not path:
            return ""
        try:
            return await asyncio.to_thread(ops_export.first_page, path)
        except Exception as e:
            log.warning("no preview for %s: %s", key, e)
            return ""

    async def export_month(self, period: str) -> dict:
        m = local.month(self.base(), period)
        if not m["invoices"]:
            return {"ok": False, "said": "Nothing to export for this month yet."}
        files = {i["key"]: self._file_of(i["key"]) for i in m["invoices"]}
        try:
            out = await asyncio.to_thread(ops_export.export, m, files, ops_export.downloads(self.workspace))
        except OSError as e:
            return {"ok": False, "said": f"Couldn't write the file: {e}"}
        self._log(f"Exported {m['label']}", tone="plain")
        await self.changed()
        return {"ok": True, "name": out.name}

    # --- the person's books: Tally or Zoho Books, one per ARN -------------------------------------------------------

    async def _rule_46(self, text: str) -> str:
        """"" when this invoice number may be stored, else why not: GST Rule 46 allows at most 16 characters, only
        letters, digits, - and / (the same rule as the window's `logic/numbering.ts`)."""
        text = (text or "").strip()
        if not text or re.fullmatch(r"[A-Za-z0-9/-]{1,16}", text):
            return ""
        return "GST allows up to 16 characters: letters, digits, - and / only."

    async def _books(self):
        """The steps' books half. Steps kept from before Zoho Books existed are replaced by the current ones."""
        auto = await loader.current()
        if not hasattr(getattr(auto, "books", None), "open"):
            auto = await loader.latest()
        return auto.books

    def zoho_token(self, arn: str, fresh: bool = False) -> dict:
        """Zoho Books' access token for this ARN, for the steps: {token, api}, {gone: words} or {off: words}."""
        return zoho.token(self.store, arn, fresh)

    def _token_of(self, arn: str):
        return lambda fresh=False: self.zoho_token(arn, fresh)

    def _kind(self, kind: str = "", arn: str = "") -> str:
        return kind or local.books_kept(self.base(arn))["kind"]

    async def books_look(self, period: str = "", company: str = "", which: str = "submitted", last: str = "",
                         answers: dict | None = None, kind: str = "", orgId: str = "") -> dict:
        """What importing this month into the person's books would do. Nothing in the books changes. `state`: none
        (no books chosen yet), connect (Zoho Books needs letting in), off (the books give no answer), closed (Tally:
        no company is open), pick (which company or organisation?), ready."""
        p = self.profile()
        if not p:
            return {"state": "off", "said": "No ARN is set up.", "rows": []}
        kind = self._kind(kind)
        if not kind:
            return {"state": "none", "kind": "", "rows": []}
        if kind == "zoho" and not zoho.connected(self.store, p["arn"]):
            return {"state": "connect", "kind": "zoho", "rows": [], "said": ""}
        name = "Zoho Books" if kind == "zoho" else "Tally"
        try:
            books = await self._books()
            session = books.open(kind, self.base(), period or local.current_period(), p, self._token_of(p["arn"]),
                                 company=company, org_id=orgId, which=which, last=last,
                                 answers=answers or {})
            got = await asyncio.to_thread(session.look)
        except (loader.Unreachable, loader.NotOurs):
            return {"state": "off", "said": f"{NAME} couldn't get its latest steps just now. Try again in a minute.",
                    "rows": []}
        except Exception as e:
            log.exception("the look at %s failed", name)
            return {"state": "off", "said": f"{name}'s answer couldn't be read ({type(e).__name__}).", "rows": []}
        return {**got, "remembered": local.books_kept(self.base())}

    async def books_import(self, period: str, company: str, which: str = "submitted", last: str = "",
                           answers: dict | None = None, adopt: list[str] | None = None, kind: str = "",
                           orgId: str = "") -> dict:
        """Put the month into the books. Answers with the look afterwards and `done`: what went in. Only the
        registrar's invoices: the person's own go into the books during their run, where they are numbered."""
        p = self.profile()
        if not p or self._books_busy:
            return {"state": "off", "said": "An import is already going." if p else "No ARN is set up.", "rows": []}
        if self._task is not None:
            return {"state": "off", "said": "A run is going. Import once it has ended.", "rows": []}
        kind = self._kind(kind)
        name = "Zoho Books" if kind == "zoho" else "Tally"
        self._books_busy = True
        try:
            books = await self._books()
            session = books.open(kind, self.base(), period, p, self._token_of(p["arn"]), company=company,
                                 org_id=orgId, which=which, last=last, answers=answers or {})
            got = await asyncio.to_thread(session.bring_in, adopt or [])
        except (loader.Unreachable, loader.NotOurs):
            return {"state": "off", "said": f"{NAME} couldn't get its latest steps just now. Try again in a minute.",
                    "rows": []}
        except Exception as e:
            log.exception("the import into %s failed", name)
            return {"state": "off", "rows": [],
                    "said": f"The import stopped ({type(e).__name__}). Look again to see what went in."}
        finally:
            self._books_busy = False
        done = got.get("done") or {}
        went = len(done.get("imported") or []) + len(done.get("adopted") or [])
        if went:
            numbers = done.get("numbers") or []
            span = f" ({numbers[0]} to {numbers[-1]})" if len(numbers) > 1 else f" ({numbers[0]})" if numbers else ""
            self._log(f"Imported {went} invoice{'' if went == 1 else 's'} for {got.get('label') or period} into {name}"
                      f"{span}", tone="plain")
        await self.changed()
        return {**got, "remembered": local.books_kept(self.base())}

    async def books_next(self, company: str = "", arn: str = "", kind: str = "", orgId: str = "") -> dict:
        """Where the person's own invoice numbers continue from, in their books: {state, company, last, next, at,
        method}. `company`, `arn` and `kind`: at setup, before the ARN's choice is kept. `state` is off, closed or pick
        when the books cannot say. Reads only."""
        empty = {"state": "off", "company": "", "last": "", "next": "", "at": -1, "method": ""}
        if not (company or self.profile()):
            return empty
        kind = self._kind(kind, arn) or "tally"
        try:
            books = await self._books()
            return await asyncio.to_thread(books.books_next, kind, self._token_of(arn or self.selected()),
                                           self.base(arn), company, orgId)
        except Exception:
            log.exception("the next invoice number could not be read from the books")
            return empty

    async def books_setup(self, kind: str, gstin: str, arn: str = "") -> dict:
        """Setup's Books step: what the books say, with each company's or organisation's GSTIN beside this ARN's."""
        try:
            books = await self._books()
            got = await asyncio.to_thread(books.setup_look, kind, self._token_of(arn or self.selected()), gstin)
            return {"said": "", "companies": [], "orgs": [], **got}
        except Exception:
            log.exception("the books could not be read at setup")
            return {"state": "off", "said": "", "companies": [], "orgs": []}

    async def books_use(self, kind: str, pick: dict) -> dict:
        """Use these books for this ARN from now on: the other kind's choices and grant are let go of. Tally:
        {company, guid, gstin, sure}. Zoho Books: {orgId, org, gstin, sure}."""
        arn = self.selected()
        books = await self._books()
        books.keep(kind, self.base(arn), pick)
        if kind != "zoho" and zoho.connected(self.store, arn):
            await asyncio.to_thread(zoho.disconnect, self.store, arn)
        self._log(f"Using {'Zoho Books' if kind == 'zoho' else 'Tally'} for this ARN")
        await self.changed()
        return {"ok": True}

    async def books_forget(self) -> dict:
        """Forget the books chosen for this ARN: the next look asks again. Zoho Books is also let go of."""
        arn, kind = self.selected(), self._kind()
        books = await self._books()
        if kind == "zoho":
            await asyncio.to_thread(zoho.disconnect, self.store, arn)
        books.forget(self.base())
        self._log("Let go of Zoho Books for this ARN" if kind == "zoho" else
                  "Forgot which Tally company and ledgers this ARN uses")
        await self.changed()
        return {"ok": True}

    async def zoho_connect(self, arn: str = "") -> dict:
        """Open Zoho's Accept page in the person's browser and wait for them: {ok}, or {ok: False, state, said}."""
        return await asyncio.to_thread(zoho.connect, self.store, arn or self.selected())

    async def zoho_cancel(self) -> None:
        zoho.cancel()

    async def zoho_disconnect(self, arn: str = "") -> dict:
        """Let go of Zoho Books for this ARN (the grant is revoked at Zoho), at setup or in Settings."""
        arn = arn or self.selected()
        await asyncio.to_thread(zoho.disconnect, self.store, arn)
        if arn in self.profiles():
            (self.base(arn) / "zoho.json").unlink(missing_ok=True)
            self._log("Let go of Zoho Books for this ARN")
            await self.changed()
        return {"ok": True}

    async def open_pdf(self, key: str) -> None:
        path = self._file_of(key)
        if path:
            os.startfile(path)  # noqa: S606 - the person's own PDF viewer

    async def show_in_folder(self, key: str) -> None:
        path = self._file_of(key)
        if path:
            subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603,S607

    async def uninstall(self) -> str:
        """Settings › Uninstall: start the uninstaller the installer left beside the program, then close so it can
        remove it. It asks to confirm itself, and removes the program only: the person's data stays. '' when it
        started; 'not_installed' from a checkout."""
        app = update.installed()
        exe = app / "unins000.exe" if app else None
        if exe is None or not exe.exists():
            return "not_installed"
        self._log(f"Uninstalling {NAME}")
        subprocess.Popen([str(exe)], close_fds=True)  # noqa: S603
        if self.exit is not None:
            self.exit()
        return ""

    async def open_folder(self, what: str, period: str = "") -> None:
        """A registrar's folder for the month on screen, or everything this ARN has."""
        where = self.base()
        if what in ("CAMS", "KFINTECH"):
            month = where / (period or local.current_period()) / ("cams" if what == "CAMS" else "kfintech")
            where = month if month.is_dir() else where
        where.mkdir(parents=True, exist_ok=True)
        os.startfile(where)  # noqa: S606

    # --- the run --------------------------------------------------------------------------------------------------

    async def start_run(self, registrars: list[str], period: str = "", what: str = "run", last: dict | None = None,
                        periods: list[str] | None = None) -> dict:
        """Start a run of the month (`what`: run), a look at what the registrars have (check), or a download of the
        month's invoices (download; `periods`: several months, one after another, from the Downloads tab). `last`: the
        last invoice number in the person's books, confirmed just now."""
        if self._task is not None:
            return {"run": "", "said": "Something is already running."}
        p = self.profile()
        if not p:
            return {"run": "", "said": "No ARN is set up."}
        if self._books_busy:
            return {"run": "", "said": "An import into your books is going. Try again when it has ended."}
        books = bool(local.books_kept(self.base(p["arn"]))["kind"])
        if last and last.get("text") and invoices_of(p)["source"] == "own" and not books:
            # the number may skip ahead, never go below the highest this software has used this financial year
            if refused := await self._rule_46(str(last["text"])):
                return {"run": "", "said": refused}
            top = local.issued_top(self.base(p["arn"]))
            if top and local.below(str(last["text"]).strip(), int(last.get("at", -1)), top):
                return {"run": "", "said": f"{top} has already been used this financial year, so your last invoice "
                                           "number can't be lower than that."}
            self.set_last_number(p["arn"], str(last["text"]).strip(), int(last.get("at", -1)))
        registrars = [r for r in self.registrars(p) if r in registrars] or self.registrars(p)
        period = period or local.current_period()
        run = uuid.uuid4().hex[:12]
        local.put(self.store, "run_in_progress", {"run": run, "registrars": registrars, "arn": p["arn"], "what": what,
                                                  "period": period,
                                                  "startedAt": datetime.now().astimezone().isoformat()})
        self._stop_wanted = self._hold = self._skip_cams = False
        periods = [x for x in (periods or []) if isinstance(x, str) and x] if what == "download" else []
        self._task = asyncio.create_task(self._drive(run, what, period, registrars, p["arn"], periods))
        await self.changed()
        return {"run": run}

    async def _drive(self, run: str, what: str, period: str, registrars: list[str], arn: str,
                     periods: list[str] | None = None) -> None:
        """One run, check or download, start to finish, and however it ends told to the window."""
        host = Host(self, arn, run, submit=self.submit)
        started = time.monotonic()
        host.record.mkdir(parents=True, exist_ok=True)
        own_log = logging.FileHandler(host.record / "log.txt", encoding="utf-8")     # this run's part of the log
        own_log.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logging.getLogger("client").addHandler(own_log)
        out: dict
        try:
            auto = await loader.latest()
            async with self._portal:
                many = len(periods or []) > 1
                self._log({"run": "Started a run", "check": "Checked with the registrars",
                           "download": "Started a download"}[what]
                          + (f" of {len(periods)} months" if many else f" for {local.labels(period)[0]}"), tone="plain")
                if many:
                    out = await self._downloads(auto, host, run, periods, registrars)
                else:
                    out = await {"run": auto.run, "check": auto.check, "download": auto.download}[what](
                        host, period, registrars)
        except asyncio.CancelledError:
            out = {"how": "stopped"}                       # the person pressed Stop, or closed the app
        except errors.Failure as e:                        # this PC's own trouble: no browser, no signature
            ours = e.kind == errors.OURS
            out = {"how": "stopped", "stop": {"kind": "ours" if ours else "setup", "title": e.message,
                                              "lines": ["Nothing was submitted."], "said": "", "registrar": "",
                                              "so_far": ""}}
        except (loader.Unreachable, loader.NotOurs) as e:
            log.warning("the steps could not be had: %r", e)
            out = {"how": "stopped", "stop": {"kind": "unreachable", "title": f"{NAME} can't reach its server",
                                              "lines": [NO_STEPS, "Nothing was done. Try again in a few minutes."],
                                              "said": "", "registrar": "", "so_far": ""}}
        except Exception as e:                             # nothing may leave a run window open with no ending
            log.exception("the %s ended on something nobody expected", what)
            with contextlib.suppress(Exception):
                (host.record / "what-happened.txt").parent.mkdir(parents=True, exist_ok=True)
                (host.record / "what-happened.txt").open("a", encoding="utf-8").write(f"{type(e).__name__}: {e}\n")
            out = {"how": "stopped", "stop": {"kind": "ours", "title": f"Something in {NAME} went wrong",
                                              "lines": ["This one is ours to fix, and it has been sent to us."],
                                              "said": "", "registrar": "", "so_far": ""}}
        finally:
            await host.close()
            self.hands.door.release()
            self._task = None
            logging.getLogger("client").removeHandler(own_log)
            own_log.close()
        seconds = int(time.monotonic() - started)
        log.info("the %s for %s ended after %ss: %s", what, period, seconds,
                 {k: v for k, v in out.items() if k != "stop"} | {"stop": (out.get("stop") or {}).get("kind")})
        await self._ended(run, what, period, out, host, seconds)

    async def _downloads(self, auto, host: Host, run: str, periods: list[str], registrars: list[str]) -> dict:
        """Several months' downloads in one go, one after another: the portals stay signed in between them. A month
        not listed yet is noted and the next goes on; any other stop ends it there, saying which months came."""
        came, unlisted = [], []
        for i, period in enumerate(periods):
            self._push({"type": "run_month", "run": run, "period": period, "index": i})
            out = await auto.download(host, period, registrars)
            name = local.labels(period)[0].split(" ")[0]
            stop = out.get("stop")
            if stop and stop.get("kind") in ("not_listed", "nothing_to_do"):
                unlisted.append(name)
                continue
            if stop:
                so_far = f"Downloaded before it stopped: {', '.join(came)}." if came else ""
                return {**out, "stop": {**stop, "title": f"{name}: {stop['title']}", "so_far": so_far}}
            came.append(name)
        summary = (f"Downloaded {', '.join(came)}." if came else "Nothing was downloaded.") +             (f" Not listed yet: {', '.join(unlisted)}." if unlisted else "")
        return {"how": "done", "summary": summary, "used": "", "counts": {}, "total": 0, "downloaded": True}

    async def _ended(self, run: str, what: str, period: str, out: dict, host: Host, seconds: int) -> None:
        stop = out.get("stop")
        # We hear how every run went without being told, with its own log. One that stopped on something of ours
        # also brings the portals' pages as they were; while the app is new (PICTURES_WITH_EVERY_RUN) every run does,
        # because the pages nobody has seen yet show on the runs that go well too.
        ours = bool(stop) and stop["kind"] == "ours"
        said = stop["title"] if stop else out.get("summary") or out.get("news") or out.get("how") or ""
        # how it ended, for the admin panel's colour: the stop's kind, or 'stopped' (the person's Stop), or 'well'
        ended = stop["kind"] if stop else "stopped" if out.get("how") == "stopped" else "well"
        asyncio.ensure_future(self._report("ours" if ours else "run", said, f"{what} · {period}", host.record,
                                           pictures=ours or PICTURES_WITH_EVERY_RUN,
                                           about={"run": run, "ended": ended, "seconds": seconds}))
        if stop:
            self._log(f"The {'run' if what == 'run' else what} stopped: {stop['title']}",
                      tone="plain" if stop["kind"] in ("nothing_to_do", "not_listed") else "bad",
                      registrar=stop.get("registrar") or None, who="")
        local.put(self.store, "run_in_progress", None)
        if out.get("how") == "done" and what == "run":
            self._note("run_done", out.get("summary") or "", "overview", out.get("used") or "")
        if out.get("how") != "closed":                     # "Not now" at Your check closed the run window itself
            # a stop is how the run ended: the window shows it until the person closes it
            self._push({"type": "run_ended", "run": run, "how": out.get("how") or "stopped", "what": what,
                        "used": out.get("used") or "", "summary": out.get("summary") or out.get("news") or "",
                        "enter": out.get("enter") or [], "left": out.get("left") or [],
                        "counts": out.get("counts") or {}, "total": out.get("total") or 0,
                        "stop": {"kind": stop["kind"], "title": stop["title"], "said": stop.get("said") or "",
                                 "lines": list(stop.get("lines") or []), "so_far": stop.get("so_far") or "",
                                 "registrar": stop.get("registrar") or None} if stop else None})
        await self.changed()

    def answer(self, id: str, a: dict) -> None:  # noqa: A002
        fut = self._pending.get(id)
        if fut is not None and not fut.done():
            fut.set_result(a)

    async def stop_run(self, run: str) -> None:
        """Stop: the run ends now. While a Submit's answer is being read it waits for that, and ends right after."""
        if self._task is None:
            return
        if self._hold:
            self._stop_wanted = True
        else:
            self._task.cancel()

    def hold_stop(self, on: bool) -> None:
        self._hold = on
        if not on and self._stop_wanted and self._task is not None:
            self._task.cancel()

    async def close_run(self, run: str) -> None:
        """The person closed the app mid-run and confirmed. Closing ends the run."""
        if self._task is not None:
            self._task.cancel()

    # --- the rest -----------------------------------------------------------------------------------------------

    async def mark_notes_read(self) -> None:
        notes = local.get(self.store, "notes", [])
        for n in notes:
            n["read"] = True
        local.put(self.store, "notes", notes)
        await self.changed()

    # --- support --------------------------------------------------------------------------------

    async def send_support(self, text: str, where: str) -> dict:
        """Send to support: the software's server keeps it. What goes is what the popup lists: these words, where they
        were written, this app's version, this PC, the app's last log lines with every password blanked, and the
        latest run's record, whatever its age. There is no ticket and no reply: a problem is fixed for
        everyone."""
        runs = sorted((d for d in (self.workspace / "runs").glob("*") if d.is_dir() and not d.name.startswith("_")),
                      key=lambda d: d.stat().st_mtime)
        recent = runs[-1] if runs else None
        return {"sent": await self._report("problem", text, where, recent,
                                         about={"run": recent.name} if recent else None)}

    async def send_idea(self, text: str, picture: dict | None = None) -> dict:
        """Settings › Send an idea: the words, and the picture the person chose, kept by the software's server as an
        idea. The picture goes as the report's record (one file in a zip)."""
        if not text.strip():
            return {"sent": False}
        folder = None
        if picture and picture.get("data"):
            raw = base64.b64decode(str(picture["data"]).split(",")[-1], validate=False)
            ext = Path(str(picture.get("name") or "")).suffix.lower()
            if len(raw) <= 5 * 1024 * 1024 and ext in (".png", ".jpg", ".jpeg", ".webp"):
                folder = self.workspace / "runs" / f"_idea-{uuid.uuid4().hex[:8]}"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"picture{ext}").write_bytes(raw)
        try:
            return {"sent": await self._report("idea", text, "Settings › Send an idea", folder)}
        finally:
            if folder:
                shutil.rmtree(folder, ignore_errors=True)

    async def _report(self, kind: str, text: str, where: str, record: Path | None = None,
                      pictures: bool = True, about: dict | None = None) -> bool:
        """`about`: the run it is about (its id, how it ended, how many seconds it took), so the admin panel reads a
        run and what a person said of it together."""
        if record:
            self._blank(record / "log.txt")
        spec = await asyncio.to_thread(min_spec)
        pc = f"{platform.node()[:60]} · Windows {spec['windows']} · {spec['ram_gb']} GB · {spec['free_disk_gb']} GB free"
        acct = self.account() or {}
        sent = await asyncio.to_thread(server.report, {
            "kind": kind, "message": text.strip()[:4000], "where": where[:200], "arn": self.selected(),
            "email": acct.get("email", ""), "version": APP_VERSION, "steps": loader.version(), "pc": pc,
            "log": self._log_tail()} | (about or {}), _zipped(record, pictures) if record else None)
        if sent and kind not in ("ours", "run"):
            self._log("Sent an idea" if kind == "idea" else "Sent to support", tone="plain")
        return sent

    def _log_tail(self) -> str:
        """The end of the app's own log, with every password this PC holds blanked."""
        try:
            raw = (self.workspace / "logs" / "app.log").read_bytes()[-LOG_TAIL:].decode("utf-8", "replace")
        except OSError:
            return ""
        for secret in self._never_sent():
            raw = raw.replace(secret, "********")
        return raw

    def _blank(self, path: Path) -> None:
        """A run's own log, with every password this PC holds blanked, before it goes anywhere."""
        with contextlib.suppress(OSError):
            raw = was = path.read_text(encoding="utf-8", errors="replace")
            for secret in self._never_sent():
                raw = raw.replace(secret, "********")
            if raw != was:
                path.write_text(raw, encoding="utf-8")

    def _never_sent(self) -> list[str]:
        """Every password this PC holds, for every ARN: blanked out of whatever is sent to support."""
        keys = [k for k in ("kfintech_password", "gmail_app_password", "forward_secret")]
        keys += [f"{k}:{arn}" for k in list(keys) for arn in self.profiles()]
        return [v for v in (self.store.get_secret(k) for k in keys) if v]

    async def open(self, link: str) -> None:
        webbrowser.open(LINKS.get(link, LINKS["site"]))

    # --- updates -------------------------------------------------------------------------------

    async def check_for_updates(self) -> dict:
        """Settings' Check for updates: ask the website again which version is current."""
        await self.read_plan()
        return {"upToDate": self._update_view() is None}

    async def update_now(self) -> None:
        """[Update now]: download, check against the website's SHA-256, hand over to the installer, and quit. The old
        version comes back if the new one does not start (`update`)."""
        want = local.get(self.store, "release")
        if not want or self._updating or self._update_view() is None:
            return
        if update.installed() is None:
            self._push({"type": "update_failed", "reason": "not_installed"})
            return
        self._updating = True
        try:
            dest = update.installer_for(want["version"])
            why = await asyncio.to_thread(update.download, self.token(), dest, want["sha256"],
                                          lambda pct: self._push({"type": "update_progress", "pct": pct}))
            if why:
                if why == "mismatch":
                    self._log(f"The download of {NAME} {want['version']} didn't match what we sent, so it was "
                              "deleted and not run", tone="bad")
                self._push({"type": "update_failed", "reason": why})
                return
            self._log(f"Updating {NAME} from {APP_VERSION} to {want['version']}")
            local.put(self.store, "update_place", self.place or None)
            await asyncio.to_thread(update.begin, dest, want["version"], want["sha256"], APP_VERSION)
        except Exception:
            log.exception("the update could not start")
            self._push({"type": "update_failed", "reason": "failed"})
            return
        finally:
            self._updating = False
        if self.exit is not None:
            self.exit()

    async def here(self, place: dict) -> None:
        """Where the window is (its page, Settings' section, the month open in Invoices), for coming back after an
        update."""
        self.place = {k: str(v) for k, v in (place or {}).items() if k in ("page", "section", "month") and v}

    async def opened(self) -> None:
        """The window loaded. After an update, the copy that installed it is told it is up, and the person is put
        back where they were; after one that did not start, it is remembered and said."""
        if self.updated_from:
            update.started(APP_VERSION)
            self._log(f"Updated {NAME} from {self.updated_from} to {APP_VERSION}")
            local.put(self.store, "update_failed", None)
            place = local.get(self.store, "update_place")
            local.put(self.store, "update_place", None)
            if place:
                self._push({"type": "go", "place": place})
            self._push({"type": "notify", "kind": "updated", "text": f"Updated to v{APP_VERSION}", "opens": "",
                        "toast": True})
            asyncio.get_running_loop().run_in_executor(None, update.tidy)
        elif self.update_failed_to:
            local.put(self.store, "update_failed", self.update_failed_to)
            self._log(f"The update to {self.update_failed_to} didn't start, so this PC went back to {APP_VERSION}",
                      tone="bad")
            await self.changed()

    # =============================================================================================================
    # What a run asks of the person, and tells the window (`Host` calls these)
    # =============================================================================================================

    async def _ask(self, run: str, ask: dict) -> dict:
        """Put one question on the window and wait for the answer, however long it takes (a person may be at lunch).
        If whoever asked is stopped meanwhile, the question is taken down."""
        rid = self._id()
        self._push({"type": "ask", "ask": {**ask, "id": rid, "run": run}})
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        try:
            return await fut
        except asyncio.CancelledError:
            self._push({"type": "ask_withdrawn", "id": rid})
            raise
        finally:
            self._pending.pop(rid, None)

    def steps(self, run: str, steps: list[dict]) -> None:
        self._push({"type": "steps", "run": run, "steps": steps})

    async def captcha(self, png: bytes, attempt: int, message: str, run: str = "") -> dict:
        a = await self._ask(run or "setup", {
            "type": "captcha", "image": "data:image/png;base64," + base64.b64encode(png).decode(),
            "attempt": attempt, "message": message, "during": "run" if run else "setup"})
        return {"text": a.get("text", ""), "refresh": bool(a.get("refresh"))}

    async def signature_check(self, run: str, key: str, amc: str) -> dict:
        """The first run for an ARN: one signed invoice, "Does this look right?" A fix is made in the window (Change
        signature, in place) before it answers, so the same invoice is signed again the new way."""
        a = await self._ask(run, {"type": "signature", "key": key, "amc": amc})
        return {"looks_right": bool(a.get("looksRight")), "fixed": bool(a.get("fixed"))}

    async def pick_files(self, run: str, month: str, skip: bool = False) -> dict:
        """CAMS's zip and Excel, from the person: each chosen with Windows' own Open box (`pick_file`) or dropped on
        the window (`drop_file`). Answers when both are in, with where they are on this PC, or {skip: True} when the
        person was offered Skip CAMS (`skip`) and took it."""
        self._picked = {}
        p = self.profile() or {}
        answer = await self._ask(run, {"type": "pick_files", "month": month, "skip": skip,
                                       "sentTo": shown(self.credential(p.get("arn", ""), "cams_email"))})
        got, self._picked = dict(self._picked), {}
        return {"skip": True} if answer.get("skip") else got

    async def pick_file(self, kind: str) -> dict:
        """One of the two files, from the person's own Open box. Only the name goes back to the window; the path stays
        on this PC. Cancelling leaves what was chosen before."""
        title, types = (("CAMS's invoice zip", ("Zip files (*.zip)",)) if kind == "zip"
                        else ("CAMS's Excel report", ("Excel files (*.xls;*.xlsx)",)))
        path = await asyncio.to_thread(self.choose_file, title, types)
        if path:
            self._picked[kind] = path
        return {"kind": kind, "name": Path(self._picked[kind]).name if kind in self._picked else ""}

    async def drop_file(self, name: str, bytes: str) -> dict:  # noqa: A002 - the window's own name for it
        """A file dropped on the window: a zip is CAMS's invoices, an .xls or .xlsx its report. Anything else is not
        taken. It is kept in this PC's own folder until the run copies it into the month."""
        suffix = Path(name).suffix.lower()
        kind = "zip" if suffix == ".zip" else "xls" if suffix in (".xls", ".xlsx") else ""
        if not kind:
            return {"kind": "", "name": ""}
        try:
            data = base64.b64decode(bytes)
        except ValueError:
            return {"kind": "", "name": ""}
        folder = self.workspace / "dropped"
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob(f"*{'.zip' if kind == 'zip' else '.xls*'}"):
            old.unlink(missing_ok=True)
        out = folder / re.sub(r"[^A-Za-z0-9._ -]", "_", Path(name).name)
        out.write_bytes(data)
        self._picked[kind] = str(out)
        return {"kind": kind, "name": Path(name).name}

    async def your_check(self, run: str, rows: list[dict], notes: list[str], books: dict | None = None) -> dict:
        a = await self._ask(run, {"type": "your_check", "rows": rows, "notes": notes, "books": books})
        return {"confirmed": bool(a.get("confirmed")), "included": list(a.get("included") or []),
                "first": str(a.get("first") or ""),
                "dated": list(a.get("dated") or [])}

    def books_waiting(self, run: str, on: bool, company: str, said: str, kind: str = "tally") -> None:
        """The run is waiting for the person's books: the window shows a red line with a Refresh button."""
        self._push({"type": "books_waiting", "run": run, "on": on, "company": company, "said": said, "kind": kind})

    async def books_nap(self, seconds: float) -> None:
        """Wait for Refresh, or this long, before the books are asked again."""
        self._books_wake.clear()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._books_wake.wait(), seconds)

    async def refresh_books(self, run: str) -> None:
        self._books_wake.set()

    async def books_ask(self, run: str, asks: list[dict]) -> dict:
        """The books' questions (`asks`: id, question, options): {id: the option chosen}."""
        a = await self._ask(run, {"type": "books_ask", "asks": asks})
        return {str(k): str(v) for k, v in (a.get("answers") or {}).items()}

    def waiting_email(self, run: str, since: str, ref: str, skip: bool = False) -> None:
        self._push({"type": "waiting_email", "run": run, "since": since, "ref": ref, "skip": skip})

    async def skip_cams(self, run: str) -> None:
        """Skip CAMS while its email is awaited: the run carries on with KFintech; the email is read when it comes."""
        self._skip_cams = True

    def submitted(self, run: str, registrar: str, count: int) -> None:
        self._push({"type": "submitted", "run": run, "registrar": registrar, "count": count})

    def note_sign_in(self, arn: str, registrar: str) -> None:
        """A portal let this ARN in today and showed its ARN: CAMS is verified by that, if it was not."""
        p = self.profiles().get(arn)
        if not p:
            return
        p.setdefault("lastLogin", {"CAMS": "", "KFINTECH": ""})[registrar] = date.today().isoformat()
        if registrar == "CAMS" and not p.get("camsArn"):
            p["camsArn"] = arn
        self._save_profile(p)

    def set_last_number(self, arn: str, text: str, at: int) -> None:
        """The last invoice number in the person's books, as they confirmed it or as a run just moved it on."""
        p = self.profiles().get(arn)
        if not p:
            return
        p["invoices"] = {**invoices_of(p), "last": text, "at": at}
        self._save_profile(p)


def _zipped(folder: Path, pictures: bool = True) -> bytes | None:
    """A run's record as one zip, for sending: all of it, or only its log."""
    try:
        files = [f for f in sorted(folder.glob("*")) if f.is_file() and (pictures or f.name == "log.txt")]
        if not files:
            return None
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.write(f, f.name)
        return buf.getvalue()
    except OSError:
        return None


# October 2026, the first round with real distributors: every run sends the pictures of the portals' pages with its
# log. Turn it off once those pages are known; the website's Privacy and Security pages say which it is.
PICTURES_WITH_EVERY_RUN = True
_DRAWING = threading.Lock()      # previews are drawn one at a time (`_signed_page`)
BLANK_SETTINGS = {"template": "tally", "address": [], "phone": "", "email": "", "website": "",
                  "particulars": "Commission", "particularsAmc": True, "remarks": ""}


def _consent(c: dict) -> dict:
    """The consent record as this PC keeps it: the wording's version and text as shown, when, and on which PC."""
    return {"version": int(c.get("version") or 0), "text": str(c.get("text") or "")[:600],
            "at": str(c.get("at") or local.note_now())[:40], "device": platform.node()[:60]}


def invoices_of(p: dict) -> dict:
    """The invoice choice as the window keeps it: {source, last, at, settings}. A profile with no choice uploads the
    registrar's invoices."""
    got = p.get("invoices") or {}
    return {"source": "own" if got.get("source") == "own" else "registrar", "last": str(got.get("last") or ""),
            "at": int(got.get("at") if got.get("at") is not None else -1),
            "settings": {**BLANK_SETTINGS, **(got.get("settings") or {})}}


def _older(version: str, current: str) -> bool:
    """Is this app behind the current version? "0.10.2" comes after "0.9". Anything unreadable is not behind."""
    def parts(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in v.strip().split("."))
        except ValueError:
            return ()
    return bool(parts(current)) and parts(version) < parts(current)


def _internet() -> bool:
    """Is there an internet at all, or just no us? A plain connection to a portal's door, nothing sent."""
    for host in ("www.camsonline.com", "dss.kfintech.com"):
        try:
            socket.create_connection((host, 443), timeout=3).close()
            return True
        except OSError:
            continue
    return False


def _count_gmail(user: str, password: str) -> int:
    """Sign in to Gmail and count CAMS's invoice mails of the last 30 days. Read-only."""
    from client.hands import mail
    m = mail._gmail(user, password)
    try:
        return len(mail._gmail_uids(m, 30))
    finally:
        try:
            m.logout()
        except Exception:
            pass

