"""What the portal steps are given: the app, as they see it.

The steps (`client.automation`) come from the software's server and change whenever a portal does. This is the fixed
side they stand on: the browser's tabs, the person, this ARN's folder, the signature and the mailbox. Nothing here
knows anything about a portal, so nothing here has to change when one does. Adding to this class needs an update of
the app; everything on the other side of it does not.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
import re
import time
import traceback
from datetime import date
from pathlib import Path

from playwright.async_api import Keyboard, Locator, Page, async_playwright

from client.hands import forward, inbox, local, mail, ops_pdf
from client.hands.mail import MailError

log = logging.getLogger(__name__)

CLICK_MS = 45_000                # how long a click or a fill waits for its element: the portals are slow
OPEN_MS = 60_000

# What is logged of a run: every action the steps take on a page, how long it took and how it ended, and what the
# page itself did. What is typed may be a password, so only its length is logged. The portals' trackers and their
# complaints about them are left out.
ACTIONS = {Locator: ("click", "fill", "press", "check", "select_option", "set_input_files", "wait_for"),
           Page: ("goto", "reload", "wait_for_url", "wait_for_function", "wait_for_load_state"),
           Keyboard: ("press", "type")}
TYPED = ("fill", "type")
NOISE = ("google-analytics", "analytics.google", "google.com/ccm", "doubleclick", "facebook.com/tr",
         "Content Security Policy", "Loading.json")
_logged = False


def _noise(text: str) -> bool:
    return any(n in text for n in NOISE)


def _bare(url: str) -> str:
    return url.split("?")[0]


def _on(thing) -> str:
    if isinstance(thing, Page):
        return _bare(thing.url)
    found = re.search(r"selector='(.*)'>$", repr(thing))
    return found.group(1) if found else type(thing).__name__.lower()


def _logging(cls, name: str) -> None:
    real = getattr(cls, name)

    @functools.wraps(real)
    async def call(self, *a, **k):
        given = f"{len(str(a[0]))} characters" if name in TYPED and a else ", ".join(str(x)[:120] for x in a)
        what = f"{name}({given}) on {_on(self)}"
        log.debug("> %s", what)
        t = time.monotonic()
        try:
            got = await real(self, *a, **k)
        except BaseException as e:
            log.debug("x %s after %.1fs: %s", what, time.monotonic() - t,
                      (str(e).splitlines() or [type(e).__name__])[0])
            raise
        log.debug("< %s %.1fs", what, time.monotonic() - t)
        return got

    setattr(cls, name, call)


def _log_actions() -> None:
    global _logged
    if _logged or not log.isEnabledFor(logging.DEBUG):
        return
    _logged = True
    for cls, names in ACTIONS.items():
        for name in names:
            _logging(cls, name)


def _watch(page: Page) -> None:
    """Log what this tab does by itself: where it goes, what it asks the portal for, and what it complains of."""
    if not log.isEnabledFor(logging.DEBUG):
        return

    def answered(r) -> None:
        if r.request.resource_type in ("document", "xhr", "fetch") and not _noise(r.url):
            log.debug("  %s %s %s", r.status, r.request.method, _bare(r.url))

    log.debug("  tab at %s", _bare(page.url))
    page.on("framenavigated", lambda f: f == page.main_frame and log.debug("  now at %s", _bare(f.url)))
    page.on("response", answered)
    page.on("requestfailed", lambda r: _noise(r.url) or log.debug("  failed %s %s: %s", r.method, _bare(r.url),
                                                                 r.failure))
    page.on("console", lambda m: m.type in ("error", "warning") and not _noise(m.text)
            and log.debug("  page %s: %s", m.type, m.text[:300]))
    page.on("pageerror", lambda e: log.debug("  page error: %s", str(e)[:300]))
    page.on("download", lambda d: log.debug("  download: %s", d.suggested_filename))
    page.on("close", lambda p: log.debug("  tab closed: %s", _bare(p.url)))


# How long KFintech's sign-in is trusted after the browser was last used. 20 minutes was tested safe (4 Oct 2026);
# KFintech does not say when it ends a session, so past that its tabs and cookies are dropped and it is signed in to
# afresh. CAMS has no clock: its tab stays for as long as the app is open, and CAMS says when a session has ended.
IDLE_S = 20 * 60
KFIN_SITE = "kfintech.com"


class Host:
    def __init__(self, window, arn: str, run: str, submit: bool = True):
        self.w = window
        self.hands = window.hands
        self.store = window.store
        self.run = run                                   # '' for setup's verifications: nothing is shown as steps
        self.profile: dict = dict(window.profiles().get(arn) or {"arn": arn})
        self.profile.setdefault("mailbox", {"provider": "gmail"})
        self.profile["invoices"] = window.invoices_of(self.profile)
        self.base: Path = window.base(arn)
        self.submit = submit
        self.record: Path = window.workspace / "runs" / run if run else window.workspace / "runs" / "_setup"
        self._pw = None
        self._browser = None
        self._afresh = False
        self._shots = 0
        self._line = ""

    # --- the browser's tabs -------------------------------------------------------------------------------------------

    async def _context(self):
        if self._browser is None:
            used = self.hands.browser_used_at
            if used and time.monotonic() - used > IDLE_S:
                log.info("the browser was last used %d minutes ago: KFintech is signed in to afresh",
                         (time.monotonic() - used) // 60)
                self._afresh = True
            await self.hands.browser.ensure()
            self.hands.save_ua_cache()
            log.debug("the browser: %s", self.hands.browser.info())
            _log_actions()
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.connect_over_cdp(f"http://127.0.0.1:{self.hands.browser.port}")
            context = self._browser.contexts[0]
            context.set_default_timeout(CLICK_MS)
            context.set_default_navigation_timeout(OPEN_MS)
            for p in context.pages:
                _watch(p)
            context.on("page", _watch)
            if self._afresh:
                self._afresh = False
                await self._forget(KFIN_SITE)
        return self._browser.contexts[0]

    async def page(self, site: str) -> Page:
        """The tab for one portal: the one already on that site (it may still be signed in), else a new one. It is
        left open afterwards, so the next run can use it."""
        context = await self._context()
        for p in context.pages:
            if site in p.url:
                return p
        return await context.new_page()

    async def fresh_page(self) -> Page:
        """A new tab, for a piece of work that leaves nothing behind (setup's verifications close it)."""
        return await (await self._context()).new_page()

    async def afresh(self, site: str) -> None:
        """Drop one portal's sign-in: for a sign-in that has been left alone too long to trust. The other portal's
        tab is not touched. The tab the steps held is gone; it asks for a new one."""
        await self._forget(site)

    async def _forget(self, site: str) -> None:
        """Close the tabs on a site and clear what it kept (cookies, local and session storage)."""
        context = self._browser.contexts[0]
        for p in list(context.pages):
            if site in p.url:
                with contextlib.suppress(Exception):
                    await p.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
                with contextlib.suppress(Exception):
                    await p.close()
        await context.clear_cookies(domain=re.compile(re.escape(site)))

    async def close(self) -> None:
        """Let go of the browser without closing it: its tabs stay as they are, for a run that starts soon."""
        if self._browser is not None:
            self.hands.browser_used_at = time.monotonic()
        if self._pw is not None:
            with contextlib.suppress(Exception):
                await self._pw.stop()
        self._pw = self._browser = None

    # --- this ARN -----------------------------------------------------------------------------------------------------

    def secret(self, name: str) -> str:
        """One of this ARN's sign-in details, from this PC's vault."""
        arn = self.profile["arn"]
        return self.store.get_secret(f"{name}:{arn}") or (self.store.get_secret(name) if arn == self.w.selected()
                                                           else "") or ""

    def get(self, key: str, default=None):
        return local.get(self.store, f"{key}:{self.profile['arn']}", default)

    def put(self, key: str, value) -> None:
        local.put(self.store, f"{key}:{self.profile['arn']}", value)

    def signed_in(self, registrar: str) -> None:
        """A portal let this ARN in and showed its ARN, today."""
        self.w.note_sign_in(self.profile["arn"], registrar)

    def set_last_number(self, text: str, at: int) -> None:
        """The last invoice number in the person's books is now this one."""
        self.profile["invoices"].update(last=text, at=at)
        self.w.set_last_number(self.profile["arn"], text, at)

    def activity(self, text: str, registrar: str | None = None, tone: str = "plain") -> None:
        log.debug("activity: %s", text)
        self.w.log_activity(text, tone, registrar, who="")

    # --- the person ---------------------------------------------------------------------------------------------------

    async def captcha(self, png: bytes, attempt: int, message: str) -> dict:
        log.debug("asking for the captcha, attempt %s %s", attempt, message)
        got = await self.w.captcha(png, attempt, message, self.run)
        log.debug("the captcha was answered: %s", sorted(got) if isinstance(got, dict) else got)
        return got

    async def files(self, month: str, skip: bool = False) -> dict:
        """CAMS's zip and Excel, chosen or dropped by the person: {zip, xls}, each a path on this PC. `skip`: the
        person may leave CAMS out of this run instead, which answers {skip: True}."""
        got = await self.w.pick_files(self.run, month, skip)
        log.debug("CAMS's files: %s", sorted(got))
        return got

    async def looks_right(self, key: str, amc: str) -> dict:
        return await self.w.signature_check(self.run, key, amc)

    async def your_check(self, rows: list[dict], notes: list[str], books: dict | None = None) -> dict:
        """`books`: own invoices with books connected: {company, after, first}, shown above the table."""
        return await self.w.your_check(self.run, rows, notes, books)

    # --- the person's books (Tally) -----------------------------------------------------------------------------------

    def books_waiting(self, on: bool, company: str = "", said: str = "") -> None:
        """The books are not answering: the window shows a red line with a refresh button (on), or takes it down."""
        self.w.books_waiting(self.run, on, company, said)

    async def books_nap(self, seconds: float = 3.0) -> None:
        """Wait for the person's refresh, or this long, before the books are asked again."""
        await self.w.books_nap(seconds)

    async def books_ask(self, asks: list[dict]) -> dict:
        """The books' questions (which kind of sales voucher, which ledger, whether it is the right company):
        {id: answer}."""
        return await self.w.books_ask(self.run, asks)

    # --- telling the window -------------------------------------------------------------------------------------------

    async def steps(self, rows: list[dict]) -> None:
        line = " | ".join(f"{r['name']} {r['state']}: {r['line'] or r['result']}" for r in rows
                          if r["state"] != "waiting")
        if line != self._line:
            self._line = line
            log.debug("steps: %s", line)
        if self.run and rows:
            self.w.steps(self.run, rows)

    async def waiting_email(self, since: str, ref: str, skip: bool = False) -> None:
        self.w.waiting_email(self.run, since, ref, skip)

    def skip_wanted(self) -> bool:
        """Skip CAMS was pressed while its email was awaited."""
        return bool(getattr(self.w, "_skip_cams", False))

    async def submitted(self, registrar: str, count: int) -> None:
        self.w.submitted(self.run, registrar, count)

    async def changed(self) -> None:
        await self.w.changed()

    def hold_stop(self, on: bool) -> None:
        """While on, Stop waits: a Submit has been pressed and its answer is being read."""
        self.w.hold_stop(on)

    # --- the signature ------------------------------------------------------------------------------------------------

    def signature(self) -> dict:
        """Is a signature set up, and the shape it is placed by: {present, aspect, ink_cx, ink_cy, scale, way}."""
        return self.hands.door.info()

    def sign(self, src: Path, out: Path, places: list[dict]) -> str:
        return self.hands.door.sign_file(src, out, places)

    def draw(self, out: Path, page_w: float, page_h: float, ops: list[dict]) -> str:
        return ops_pdf.render_to(self.hands.door, out, page_w, page_h, ops)

    # --- the mailbox --------------------------------------------------------------------------------------------------

    async def confirm_arn(self) -> tuple[bool, str]:
        """CAMS's files for this ARN have been read: bind the ARN to the account if setup left that to the first run."""
        if not self.profile.get("bindOnRun"):
            return True, ""
        got = await self.w.confirm_arn(self.profile["arn"])
        if got["ok"]:
            self.profile.pop("bindOnRun", None)
        return got["ok"], got.get("said", "")

    def _fetch(self, folder: Path) -> None:
        """CAMS's emails into the inbox folder, from wherever this person's come: forwarded to us, or Gmail."""
        if self.profile["mailbox"].get("provider") == "forward":
            try:
                forward.fetch(self.store, folder)
            except OSError as e:                       # no internet, or our server not answering: the next look
                raise MailError(f"Couldn't reach MFDInvoice's server: {e}") from e
        else:
            mail.fetch(self.store, folder)

    async def mailbox_ok(self) -> tuple[bool, str]:
        if self.profile["mailbox"].get("provider") == "forward":
            return (True, "") if forward.configured(self.store) else                 (False, "Forwarding to MFDInvoice isn't set up on this PC.")
        user, password = self.store.get("gmail_user"), self.store.get_secret("gmail_app_password")
        if not user or not password:
            return False, "No mailbox is connected on this PC."
        try:
            await asyncio.to_thread(mail.test_login, user, password)
        except MailError as e:
            return False, str(e)
        return True, ""

    async def mail_look(self, ref: str) -> list[Path] | None:
        """One look in the mailbox for CAMS's email: its zip and Excel, or None while it has not come. `ref` is CAMS's
        reference for the request; without one, the newest pair in the mailbox is taken."""
        folder = self.hands.cfg.paths.inbox

        def look():
            try:
                self._fetch(folder)
            except MailError as e:
                log.warning("the mailbox: %s", e)
                return None
            pairs = inbox.scan(folder)
            got = pairs.get(inbox.ref_of(ref)) if ref else max(pairs.values(), key=lambda p: p.xls.stat().st_mtime,
                                                               default=None)
            return [got.zip, got.xls] if got else None

        return await asyncio.to_thread(look)

    async def mail_pairs(self, fetch: bool = True) -> list[list[Path]]:
        """Every one of CAMS's emails in the mailbox (zip and Excel), newest first, whichever request it answered: the
        steps pick the one that is this ARN's month. `fetch`: look in the mailbox first, else only at what is saved."""
        folder = self.hands.cfg.paths.inbox

        def look():
            if fetch:
                try:
                    self._fetch(folder)
                except MailError as e:
                    log.warning("the mailbox: %s", e)
            pairs = sorted(inbox.scan(folder).values(), key=lambda p: p.xls.stat().st_mtime, reverse=True)
            return [[p.zip, p.xls] for p in pairs]

        return await asyncio.to_thread(look)

    # --- the run's record: kept on this PC, and sent to us when something of ours broke -------------------------------

    async def picture(self, page: Page, name: str) -> None:
        """What the page looks like at this point of the run. Never worth failing anything for."""
        self._shots += 1
        log.debug("picture %02d %s of %s", self._shots, name, _bare(page.url))
        with contextlib.suppress(Exception):
            self.record.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(self.record / f"{self._shots:02}-{name}.jpg"), type="jpeg", quality=60,
                                  full_page=True, timeout=10_000)

    async def failure(self, page: Page, name: str, e: BaseException) -> None:
        """The page as it was when a step stopped: a picture, its HTML, and what went wrong."""
        log.debug("kept %s at %s in %s", name, _bare(page.url), self.record)
        await self.picture(page, name)
        with contextlib.suppress(Exception):
            (self.record / f"{self._shots:02}-{name}.html").write_text(await page.content(), encoding="utf-8")
        with contextlib.suppress(Exception):
            with (self.record / "what-happened.txt").open("a", encoding="utf-8") as f:
                f.write(f"--- {name} · {date.today().isoformat()} · {page.url}\n")
                f.write("".join(traceback.format_exception(e))[-8000:] + "\n")
