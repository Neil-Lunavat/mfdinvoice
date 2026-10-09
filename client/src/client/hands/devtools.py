"""DEV ONLY, a checkout (`uv run app`): what the dev panel in the window calls. Never shipped: `packaging/app.spec`
leaves this module out and `packaging/build.py` fails the build if it is in.

`devstart.Bench.install` registers these into the window's METHODS and puts them on the `Window`; each answers a plain dict.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import math
import re
import shutil
import sqlite3
import tomllib
from pathlib import Path

from client.brand import DATA, NAME
from client.credentials import shown
from client.hands import browser, forward, local, ops_sig
from client.hands import window as window_mod

log = logging.getLogger(__name__)

STATES = DATA.parent / f"{DATA.name}-states"
# What a saved state leaves out: the browser (and its sign-ins), the window's own cache, the logs, the runs' records.
LEFT_OUT = {"browser-profile", "webview", "logs", "runs", "__pycache__"}
NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}$")
KEYS = ("arn", "name", "gstin", "cams_email", "kfintech_username", "kfintech_password", "invoices", "last_number",
        "tally_company")
NEEDED = ("arn", "name", "gstin", "cams_email", "kfintech_username", "kfintech_password", "invoices")
CONSENT_TS = Path(__file__).resolve().parents[3] / "window" / "src" / "logic" / "consent.ts"


def _dev_config() -> dict:
    """`[dev]` of config.toml in the folder `uv run app` was started from (the same file `devstart._submits` reads)."""
    try:
        return tomllib.loads(Path("config.toml").read_text(encoding="utf-8-sig")).get("dev", {})
    except (OSError, ValueError):
        return {}


def _consent_version() -> int:
    """The wording's version the window asks for now (`logic/consent.ts`)."""
    try:
        return int(re.search(r"CONSENT_VERSION\s*=\s*(\d+)", CONSENT_TS.read_text(encoding="utf-8")).group(1))
    except (OSError, AttributeError, ValueError):
        return 1


def _scribble() -> bytes:
    """A signature-like scribble on white paper, as a photo would be, for `ops_sig.prepare` to clean."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (900, 360), "white")
    d = ImageDraw.Draw(im)
    ink = (25, 30, 90)
    d.line([(60 + t * 7.5, 190 + 70 * math.sin(t / 6.0) * math.cos(t / 17.0) - t * 0.35) for t in range(110)],
           fill=ink, width=7, joint="curve")
    d.line([(250, 270), (420, 240), (620, 262), (800, 215)], fill=ink, width=5)
    d.line([(140, 120), (200, 250)], fill=ink, width=6)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


class DevTools:
    def __init__(self, win, hands, store, states: Path = STATES):
        self.win, self.hands, self.store, self.states = win, hands, store, states
        self.workspace: Path = win.workspace

    # --- switches ---------------------------------------------------------------------------------------------

    async def dev_state(self) -> dict:
        return {"submit": bool(self.win.submit), "showBrowser": bool(browser.SHOWN), "states": self._names(),
                "configured": [k for k in KEYS if _dev_config().get(k) not in (None, "")]}

    async def dev_set(self, submit: bool | None = None, showBrowser: bool | None = None) -> dict:  # noqa: N803
        if submit is not None:
            self.win.submit = bool(submit)
            log.info("dev: a run %s", "presses Submit" if submit else "stops just before Submit")
        if showBrowser is not None and bool(showBrowser) != browser.SHOWN:
            browser.SHOWN = bool(showBrowser)
            if self.win._task is None:
                self.hands.browser.close()           # it starts again, the other way, at the next run
            log.info("dev: the browser a run drives is %s", "shown" if showBrowser else "hidden")
        return await self.dev_state()

    # --- back to setup, fill everything -----------------------------------------------------------------------

    async def dev_back_to_setup(self) -> dict:
        if self.win._task is not None:
            return {"ok": False, "said": "A run is going."}
        local.put(self.store, "profiles", {})
        self.store.put("selected_arn", None)
        await self.win.drop_setup()
        await self.win.read_plan()
        log.info("dev: back to setup (months and files stay)")
        return {"ok": True}

    async def dev_fill(self) -> dict:
        cfg = _dev_config()
        missing = [k for k in NEEDED if not str(cfg.get(k) or "").strip()]
        if str(cfg.get("invoices") or "") not in ("", "own", "registrar"):
            missing.append('invoices ("own" or "registrar")')
        if str(cfg.get("invoices")) == "own" and not str(cfg.get("last_number") or "").strip():
            missing.append("last_number")
        if missing:
            return {"ok": False, "said": "client/config.toml [dev] lacks: " + ", ".join(missing)}
        win = self.win
        arn = str(cfg["arn"]).strip().upper()
        if not arn.startswith("ARN-"):
            arn = "ARN-" + arn
        if arn in win.profiles():
            return {"ok": False, "said": f"{arn} is already set up here."}
        if win._task is not None:
            return {"ok": False, "said": "A run is going."}

        win._cleaned = None
        im, cx, cy = await asyncio.to_thread(ops_sig.prepare, _scribble(), 0)
        win._cleaned = (ops_sig.png(im), cx, cy)
        win._keep_signature(arn, {"way": "image", "size": 100})

        email, user, password = (str(cfg[k]).strip() for k in ("cams_email", "kfintech_username", "kfintech_password"))
        self.store.put_secret("cams_email", email)
        self.store.put_secret("kfintech_username", user)
        self.store.put_secret("kfintech_password", password)

        if forward.configured(self.store):
            mailbox = {"provider": "forward", "address": self.store.get(forward.EMAIL) or "", "connected": True}
            self.store.put("mail_provider", "forward")
        else:
            mailbox = {"provider": "folder", "address": "", "connected": True}
            self.store.put("mail_provider", "folder")

        own = str(cfg["invoices"]) == "own"
        gstin = str(cfg["gstin"]).strip().upper()
        settings = {"address": ["Dev address, line 1", "Dev city 400001"], "phone": "9000000000"} if own else {}
        consent = {"version": _consent_version(), "at": local.note_now(),
                   "text": f"I authorise {NAME} to sign in and act for me on CAMS and KFintech."}
        invoices = {"source": "own" if own else "registrar", "last": str(cfg.get("last_number") or "") if own else "",
                    "at": -1, "settings": settings}
        p = {"arn": arn, "name": str(cfg["name"]).strip(), "gstin": gstin, "camsUsed": True, "camsEmail": "",
             "camsArn": arn, "mailbox": mailbox,
             "kfintech": {"used": True, "username": "", "loggedInAs": shown(user), "arn": arn},
             "invoices": window_mod.invoices_of({"invoices": invoices}),
             "arnConfirmed": True, "lastLogin": {"CAMS": "", "KFINTECH": ""}, "consent": window_mod._consent(consent)}
        win._save_profile(p)
        win._keep_for(arn)

        said = ""
        company = str(cfg.get("tally_company") or "").strip()
        if company:
            said = await self._tally(arn, gstin, company)
        self.store.put("selected_arn", arn)
        win._log(f"Set up {arn} (dev fill)")
        await win.drop_setup()
        await win.read_plan()
        return {"ok": True, "said": said}

    async def dev_draft(self) -> dict:
        """Setup's draft as if every step had been done and verified, from [dev]; nothing is finished here. The
        verify steps' Python side is done too (the vault, the cleaned signature), so Finish setup works as it is."""
        cfg = _dev_config()
        missing = [k for k in NEEDED if not str(cfg.get(k) or "").strip()]
        if str(cfg.get("invoices") or "") not in ("", "own", "registrar"):
            missing.append('invoices ("own" or "registrar")')
        if str(cfg.get("invoices")) == "own" and not str(cfg.get("last_number") or "").strip():
            missing.append("last_number")
        if missing:
            return {"ok": False, "said": "client/config.toml [dev] lacks: " + ", ".join(missing)}
        if self.win._task is not None:
            return {"ok": False, "said": "A run is going."}
        arn = str(cfg["arn"]).strip().upper()
        if not arn.startswith("ARN-"):
            arn = "ARN-" + arn
        email, user, password = (str(cfg[k]).strip() for k in ("cams_email", "kfintech_username", "kfintech_password"))

        win = self.win
        im, cx, cy = await asyncio.to_thread(ops_sig.prepare, _scribble(), 0)
        png = ops_sig.png(im)
        win._photo = None
        win._cleaned = (png, cx, cy)
        try:                                            # beside setup's draft, as `_clean` does, so a restart keeps it
            png_file, meta_file, _photo = win._setup_files()
            png_file.parent.mkdir(parents=True, exist_ok=True)
            png_file.write_bytes(png)
            meta_file.write_text(json.dumps({"cx": cx, "cy": cy}), encoding="utf-8")
        except OSError:
            pass
        self.store.put_secret("cams_email", email)
        self.store.put_secret("kfintech_username", user)
        self.store.put_secret("kfintech_password", password)

        if forward.configured(self.store):
            mailbox = {"provider": "forward", "address": self.store.get(forward.EMAIL) or "", "connected": True}
        else:
            mailbox = {"provider": "folder", "address": "", "connected": True}
        own = str(cfg["invoices"]) == "own"
        tick = {"version": _consent_version(), "at": local.note_now(),
                "text": f"I authorise {NAME} to sign in and act for me on CAMS and KFintech."}
        return {"ok": True, "draft": {
            "arn": arn, "name": str(cfg["name"]).strip(), "gstin": str(cfg["gstin"]).strip().upper(),
            "camsUsed": True, "camsEmail": email, "camsArn": arn, "mailbox": mailbox,
            "kfintech": {"used": True, "username": shown(user), "loggedInAs": shown(user), "arn": arn},
            "invoices": {"source": "own" if own else "registrar", "last": str(cfg.get("last_number") or "") if own else "",
                         "at": -1,
                         "settings": {"address": ["Dev address, line 1", "Dev city 400001"], "phone": "9000000000"}
                         if own else {}},
            "consent": None, "ticks": {"cams": tick, "kfintech": tick},
            "signatureImage": ops_sig.data_url(png)}}

    async def _tally(self, arn: str, gstin: str, company: str) -> str:
        """Pick the Tally company by name; '' when done, else why not (the rest of the fill stands)."""
        got = await self.win.books_setup("tally", gstin, arn)
        if got.get("state") != "ready":
            return f"Tally is {got.get('state')}: company not picked."
        for c in got.get("companies") or []:
            if c["name"].strip().lower() == company.lower():
                (await self.win._books()).keep("tally", self.win.base(arn), {
                    "company": c["name"], "guid": c["guid"], "gstin": c["gstin"], "sure": True})
                return ""
        return f"Tally has no open company named {company}."

    # --- saved states -----------------------------------------------------------------------------------------

    def _names(self) -> list[str]:
        return sorted(p.name for p in self.states.glob("*") if (p / "client.db").is_file()) if self.states.exists() else []

    def _dir(self, name: str) -> Path | None:
        return self.states / name if NAME_OK.match(name or "") else None

    def _left_out(self, folder, names):
        return [n for n in names if n in LEFT_OUT or (Path(folder) == self.workspace and n.startswith("client.db"))]

    async def dev_save_state(self, name: str) -> dict:
        d = self._dir(name)
        if d is None:
            return {"ok": False, "said": "A name of letters, digits, spaces, - _ . (up to 40)."}
        await asyncio.to_thread(self._save, d)
        return {"ok": True}

    def _save(self, d: Path) -> None:
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        shutil.copytree(self.workspace, d / "workspace", ignore=self._left_out)
        out = sqlite3.connect(d / "client.db")
        try:
            self.store.db.backup(out)
        finally:
            out.close()

    async def dev_load_state(self, name: str) -> dict:
        d = self._dir(name)
        if d is None or not (d / "client.db").is_file():
            return {"ok": False, "said": f"No saved state called {name}."}
        if self.win._task is not None:
            return {"ok": False, "said": "A run is going."}
        await asyncio.to_thread(self._load, d)
        self.win._cleaned = self.win._photo = None
        await self.win.read_plan()
        return {"ok": True, "said": "Reopened in place (no restart): the vault and files are the saved ones."}

    def _load(self, d: Path) -> None:
        for p in self.workspace.iterdir():
            if p.name in LEFT_OUT or p.name.startswith("client.db"):
                continue
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
        shutil.copytree(d / "workspace", self.workspace, dirs_exist_ok=True)
        src = sqlite3.connect(d / "client.db")
        try:
            src.backup(self.store.db)               # into the open store: nothing else holds another copy
        finally:
            src.close()

    async def dev_delete_state(self, name: str) -> dict:
        d = self._dir(name)
        if d is not None and d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
        return {"ok": True}


# the window's method name -> (the Window attribute it is put on, how its arguments arrive)
METHODS = {"devState": ("dev_state", "pos"), "devSet": ("dev_set", "kw"), "devBackToSetup": ("dev_back_to_setup", "pos"),
           "devFill": ("dev_fill", "pos"), "devDraft": ("dev_draft", "pos"), "devSaveState": ("dev_save_state", "pos"),
           "devLoadState": ("dev_load_state", "pos"), "devDeleteState": ("dev_delete_state", "pos")}


def install(win, hands, store) -> dict:
    tools = DevTools(win, hands, store)
    for attr, _how in METHODS.values():
        setattr(win, attr, getattr(tools, attr))
    return METHODS
