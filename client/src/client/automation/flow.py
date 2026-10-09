"""The month's job, top to bottom: `run`, and its two shorter forms, `check` (what the registrars have) and `download`
(the month's invoices onto this PC, and nothing more).

    Check        sign in (the captcha first, so the person is needed once and early), the ARN each portal shows, what
                 each registrar already has, what each lists
    Get          the month's files: the ones on this PC when the registrar still lists exactly what they hold, else
                 fetched (CAMS by email, KFintech by download)
    Read         every figure, from the registrars' own files
    Sign         the registrar's invoices signed; the first run for an ARN shows one first, "Does this look right?"
    Your check   the person compares with their bank statement and unticks what does not match. The one yes.
    Your books   own invoices with books connected (Tally or Zoho Books): after Your check, each ticked invoice is
                 written into the books in date order and the invoice number the books hold is read back; only then
                 is each PDF drawn with exactly that number (Sign comes after it), and put with the invoice in the
                 books. The books are read before Your check too. Once a registrar has taken an invoice, the books
                 may call it sent.
    CAMS         the upload made for what stayed ticked, attached, CAMS's own reading of it compared, CAMS's own
                 validation, Submit, and its status read again
    KFintech     the same on KFintech's page

Rules that hold throughout:

- The ARN each portal shows must be the ARN this run is for, on every run. Anything else ends the run.
- What a registrar already has is never sent again: its status is read first, by this run.
- A portal that doesn't respond is tried once more, with a countdown on the step (`Job.patient`); never Submit, and
  KFintech is never signed in to again by itself. Past that the registrar is set aside and the run says why; the next
  run starts from the top and uses the files already on this PC.
- Submit is written down before it is pressed. If the registrar never answers, the next run's status reading settles
  it, and nothing is pressed twice.
- The person's own invoice numbers are given for good when they are in the books (books connected), else when
  Submit is pressed.
- A problem at one registrar does not stop the other.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from playwright.async_api import Error as PWError

from client.automation import books, cams, files, kfin, numbering, own, signature, widgets, words
from client.brand import NAME
from client.automation.month import Month, now
from client.automation import page as portal_page
from client.automation.page import Changed, Refused, Stop
from client.automation.words import CAMS, KFIN, NAMES, inr, plural

log = logging.getLogger(__name__)

MAIL_EVERY_S = 15                # CAMS's email takes from a minute to several (asked 17:07, sent 17:09 on 6 Oct)
MAIL_GIVE_UP_S = 10 * 60
# An own invoice dated before the newest invoice in an Auto Renumber type would make Tally renumber the ones after it.
# The person may date it the day it is sent instead: in Tally, on the drawn PDF and in KFintech's date box (`dated` on
# the item; CAMS's upload carries no date). Switch this off and the invoice can only be put aside.
DATE_IF_RENUMBERED = True
MIN_SHOWN_S = 0.5                # "Fetching your last invoice number" stays on screen at least this long
RETRY_IN_S = 7                   # a portal that didn't respond is tried once more after this many seconds, counted down
IDLE_S = 20 * 60                 # KFintech left alone longer than this is signed in to afresh (tested safe, 4 Oct 2026)


class Job:
    def __init__(self, host, period: str, registrars: list[str]):
        self.host, self.period = host, period
        self.arn = host.profile["arn"]
        self.own = host.profile["invoices"]["source"] == "own"
        # own invoices with books connected: the books give the invoice numbers, and are written to before Sign
        self.kind = books.connected(host.base) if self.own else ""
        self.books = (books.open(self.kind, host.base, period, host.profile, token=getattr(host, "books_token", None))
                      if self.kind else None)
        self.bname = books.name(self.kind)
        self.month = Month(host.base, period)
        self.label, self.kf_label = words.labels(period)
        self.regs = [r for r in (CAMS, KFIN) if r in registrars]          # the order things are sent in
        self.pages: dict = {}
        self.aside: dict[str, str] = {}          # registrar -> why it takes no part in this run
        self.unlisted: set[str] = set()          # ... the ones that do not list the month yet
        self.skipped: set[str] = set()           # ... the ones the person left out of this run
        self.wait_email = True                    # False: CAMS's email is asked for, not waited for (several months)
        self.behind = ""                          # CAMS lists more than its last email held: said in the file box
        self.locked: dict[str, str] = {}         # own invoices without books: the numbers already given for good
        self.numbers: dict[str, str] = {}        # own invoices with books: key -> the invoice number the books gave
        self.glanced: dict = {}                  # what the books said at the look before Your check
        self.first = ""                          # a new financial year's first invoice number, as the person typed it
        self.entered: list[dict] = []            # own invoices without books, submitted: for the person's books
        self.left: list[dict] = []               # own invoices the books would not take: {amc, why}
        self.listed: dict[str, list[str]] = {}   # registrar -> the invoices it lists for the month
        self.no_file: list[str] = []             # listed by KFintech, with no file in its download
        self.items: dict[str, dict] = {}         # every invoice read off the month's files, by key
        self.open: list[str] = []                # the ones this run may send, CAMS's first
        self.blocked: dict[str, str] = {}        # key -> why it cannot be sent by this run
        self.cannot_draw: dict[str, str] = {}    # ... of those, the ones that cannot be drawn as the person's own
        self.preview: tuple[str, dict] | None = None   # the first run's peeked invoice: its key and its row before
        self.renumber: dict[str, dict] = {}      # key -> why Tally would renumber others for it: dated today, or aside
        self.report: list[dict] = []             # CAMS's Excel, every row
        self.report_file: Path | None = None
        self.signed: dict[str, Path] = {}
        self.sent: dict[str, int] = {}
        self.ready: dict[str, int] = {}          # checked by the registrar and not submitted: Submit is switched off
        self.problems: dict[str, Stop] = {}
        self.late = ""                           # CAMS's files hold fewer invoices than it lists: said after they are read
        self.notes: list[str] = []             # what went wrong while the run carried on: shown at the end
        self.used: list[str] = []
        self.steps: list[dict] = []
        self.portals_at = time.monotonic()       # when this run last did anything on a portal's page

    # --- what the window shows ----------------------------------------------------------------------------------------

    async def plan(self, names: list[str]) -> None:
        self.steps = [{"index": i, "name": n, "state": "waiting", "line": "", "result": ""}
                      for i, n in enumerate(names)]
        await self.host.steps(self.steps)

    async def at(self, name: str, line: str) -> None:
        for s in self.steps:
            if s["name"] == name:
                s.update(state="running", line=line)
            elif s["state"] == "running":
                s["state"] = "done"
        await self.host.steps(self.steps)

    async def done(self, name: str, result: str) -> None:
        for s in self.steps:
            if s["name"] == name:
                s.update(state="done", result=result)
        await self.host.steps(self.steps)

    async def failed(self) -> None:
        for s in self.steps:
            if s["state"] == "running":
                s["state"] = "bad"
        await self.host.steps(self.steps)

    def note(self, text: str) -> None:
        """Something went wrong that the run carried on past: said now, and again at the end."""
        if text not in self.notes:
            self.notes.append(text)
            self.host.activity(text, tone="warn")

    async def say(self, line: str) -> None:
        """What a portal module (`page.tell`) says while it works something out: shown on the step that is running."""
        name = next((s["name"] for s in self.steps if s["state"] == "running"), "")
        if name:
            await self.at(name, line)

    async def patient(self, reg: str, do: Callable[[], Awaitable]):
        """Run one portal read or prepare step (`do()` makes a fresh coroutine). A portal that doesn't respond (the page
        isn't what was expected, or a wait ran out) gets a visible countdown, then one more go: CAMS after a reload
        (signed in again if the reload shows its sign-in form), KFintech as it is (its captcha means it is never
        signed in again by itself). Still nothing: this registrar is set aside with "didn't respond". The portal's own
        answers (Stop, Refused) pass untouched. Never used from Submit onwards."""
        fails = (Changed, PWError, AssertionError)
        try:
            return await do()
        except fails as e:
            log.info("%s didn't respond (%s): trying once more", reg, type(e).__name__, exc_info=True)
        name = next((s["name"] for s in self.steps if s["state"] == "running"), "")
        line = next((s["line"] for s in self.steps if s["name"] == name), "")
        who = NAMES[reg]
        for left in range(RETRY_IN_S, 0, -1):
            if name:
                await self.at(name, f"{who} didn't respond. Retrying in {left}s")
            await asyncio.sleep(1)
        if name:
            await self.at(name, f"Trying {who} again")
        try:
            if reg == CAMS:
                await cams.recover(self.pages[CAMS])
            got = await do()
        except fails as e:
            log.info("%s still didn't respond (%s)", reg, type(e).__name__, exc_info=True)
            raise Stop("portal_slow", f"{who} didn't respond", "Run again in a few minutes.",
                       said=await _portal_words(self.pages[reg], reg), registrar=reg) from e
        if name:
            await self.at(name, line)
        return got

    def active(self) -> list[str]:
        return [r for r in self.regs if r not in self.aside]

    # --- Check --------------------------------------------------------------------------------------------------------

    async def enter(self, step: str = "Check", only: list[str] | None = None) -> None:
        """Sign in to each portal (or use the tab already signed in), and hold each to the ARN law. A registrar that
        cannot be signed in to is set aside with its stop (`stopped`); the other goes on."""
        for reg in (KFIN, CAMS):                         # KFintech first: its captcha is the one thing asked of the person
            if reg not in (self.regs if only is None else only):
                continue
            try:
                await self._enter_one(reg, step)
            except (Stop, Refused, Changed, PWError, AssertionError) as e:
                await self.stopped(reg, e)

    async def _enter_one(self, reg: str, step: str) -> None:
        host = self.host
        await self.at(step, f"Signing in to {NAMES[reg]}")
        if reg == KFIN:
            user, password = host.secret("kfintech_username"), host.secret("kfintech_password")
            if not user or not password:
                raise Stop("setup", "Your KFintech login isn't saved on this PC",
                           "Add it in Settings › Connections, then run again.", registrar=KFIN)
            page = self.pages[KFIN] = await host.page("kfintech.com")
            try:
                shown = await kfin.enter(page, user, password, host.captcha, self.arn)
            except kfin.Cancelled:
                raise Stop("ended", "Stopped", "The captcha was closed, so KFintech was left out. Nothing was "
                                               "submitted to it.", registrar=KFIN) from None
        else:
            email = host.secret("cams_email")
            if not email:
                raise Stop("setup", "Your CAMS email isn't saved on this PC",
                           "Add it in Settings › Connections, then run again.", registrar=CAMS)
            page = self.pages[CAMS] = await host.page("camsonline.com")
            shown = await cams.enter(page, email, self.arn)
        if self.arn not in shown:
            # (the hyphen in an ARN is written so that it never breaks across two lines)
            raise Stop("arn_mismatch", f"{NAMES[reg]}'s ARN ({', '.join(sorted(shown))}) doesn't match your ARN "
                                       f"({self.arn})".replace("ARN-", "ARN‑"),
                       "Nothing was submitted. Check that the CAMS email and the KFintech login are both this "
                       "ARN's.", registrar=reg)
        host.signed_in(reg)
        if reg == KFIN:
            self.portals_at = time.monotonic()

    async def stopped(self, reg: str, e: Exception) -> None:
        """This registrar's step ended: it is set aside with its stop, its page kept for whoever fixes it, and the other
        registrar goes on. The run's end reports every registrar's stop."""
        self.problems[reg] = stop = await _why(self, e, reg)
        self.aside[reg] = f"{NAMES[reg]} stopped: {stop.title}"
        log.info("%s set aside: %s | %s", reg, stop.kind, stop.title)
        for s in self.steps:
            if s["name"] == NAMES[reg]:
                s.update(state="bad", result=stop.title)
        if reg in self.pages and stop.kind != "ended":
            await _keep(self, reg, e)
        await self.host.steps(self.steps)

    def raise_problems(self) -> None:
        if self.problems:
            raise next(iter(self.problems.values()))

    async def again(self) -> None:
        """KFintech was left alone too long to trust its sign-in (the person took their time at a screen): forget it
        and sign in again. CAMS has no clock: its tab stays, and `cams` signs in again if CAMS says it ended. Nothing
        has been prepared on KFintech yet."""
        log.info("the portals were left alone for %d minutes: signing in to KFintech afresh",
                 (time.monotonic() - self.portals_at) // 60)
        await self.host.afresh("kfintech.com")
        self.pages.pop(KFIN, None)
        await self.enter(step=NAMES[KFIN], only=[KFIN])

    async def status(self, listing_only: bool = False) -> None:
        """What each registrar already has, and what it lists for the month. `listing_only`: a download, which needs
        only what is listed (CAMS's status is a page of its own, and its slowest)."""
        m = self.month
        for reg in self.active():
            try:
                await self._status_one(reg, listing_only)
            except (Stop, Refused, Changed, PWError, AssertionError) as e:
                await self.stopped(reg, e)                   # this registrar is left out; the other goes on
        m.save()
        await self.host.changed()

    async def _status_one(self, reg: str, listing_only: bool) -> None:
        m, page = self.month, self.pages[reg]
        await self.at("Check", f"Reading what {NAMES[reg]} {'lists' if listing_only else 'already has'}")
        if reg == KFIN:
            # invoices KFintech listed for this month before: an empty table now is its site's trouble
            known = bool((m.facts.get("status") or {}).get(KFIN)) or bool((m.facts.get("fetched") or {}).get(KFIN))
            reading = await self.patient(reg, lambda: kfin.read_status(page, self.period, known))
            self.portals_at = time.monotonic()
            listed = None if reading is None else sorted(r["key"] for r in reading)
        else:
            reading = None
            if not listing_only:
                reading = await self.patient(reg, lambda: cams.read_status(page, self.period))
                await self.host.picture(page, "cams-status")
            listed = await self.patient(reg, lambda: cams.list_month(page, self.period))
        await self.host.picture(page, f"{reg.lower()}-listed")
        if reading is not None:
            strange = m.read_status(reg, [{"key": r["key"], "status": r["status"], "remarks": r["remarks"]}
                                          for r in reading])
            if strange:
                self.note(f"{NAMES[reg]} shows a status we haven't seen: {strange}. Shown as {NAMES[reg]} wrote it.")
        m.facts.setdefault("listedNow", {})[reg] = listed is not None
        if listed is None:
            self._unlisted(reg)
        else:
            self.listed[reg] = listed

    def _unlisted(self, reg: str) -> None:
        self.unlisted.add(reg)
        self.aside[reg] = f"{NAMES[reg]} doesn't list {self.kf_label if reg == KFIN else self.label} yet"

    def _open_at(self, reg: str) -> list[str]:
        return [k for k in self.listed.get(reg, []) if k not in self.month.with_registrar(reg)]

    def check_line(self) -> str:
        parts = []
        for reg in self.regs:
            if reg in self.aside:
                parts.append(self.aside[reg])
            else:
                n = len(self.month.with_registrar(reg))
                parts.append(f"{NAMES[reg]} {n} already submitted" if n else f"{NAMES[reg]} nothing submitted yet")
        return " · ".join(parts)

    def anything_to_do(self) -> None:
        """Ends the run when no registrar has anything open: none lists the month yet, or each has it all."""
        for reg in self.active():
            if not self._open_at(reg):
                self.aside[reg] = f"every invoice is already submitted to {NAMES[reg]}"
        if self.active():
            return
        self.raise_problems()                            # a registrar that stopped, and none left to carry on
        month = words.month_name(self.period)
        if all(r in self.unlisted for r in self.regs):
            raise Stop("not_listed", f"{month}'s invoices aren't listed yet",
                       "Fund houses usually list them in the first days of the month. Nothing was submitted.")
        out = self.unlisted | self.skipped
        who = " and ".join(NAMES[r] for r in self.regs if r not in out)
        raise Stop("nothing_to_do", f"Nothing to do for {month}",
                   f"Every invoice for {month} is already submitted to {who}{' portals' if ' and ' in who else ''}.",
                   *[f"{self.aside[r]}." for r in self.regs if r in out])

    # --- Get ----------------------------------------------------------------------------------------------------------

    async def get(self) -> None:
        m = self.month
        fetched = m.facts.setdefault("fetched", {})
        if KFIN in self.active():
            have, folder = fetched.get(KFIN), m.folder(KFIN, "fetched")
            if not (_kfin_files_good(have, self.listed[KFIN]) and _newest(folder, ".zip")):
                await self.at("Get", "Downloading KFintech's invoices")
                fetched.pop(KFIN, None)
                try:
                    got = await self.patient(KFIN, lambda: kfin.fetch(self.pages[KFIN], self.period,
                                                                      m.folder(KFIN, "fetched", empty=True)))
                    if got is None:
                        self._unlisted(KFIN)
                    else:
                        fetched[KFIN] = {"at": now(), "listed": self.listed[KFIN]}
                        self.host.activity(f"Downloaded KFintech's invoices for {self.kf_label}", KFIN)
                except (Stop, Refused, Changed, PWError, AssertionError) as e:
                    await self.stopped(KFIN, e)              # KFintech is left out; CAMS goes on
                self.portals_at = time.monotonic()
                m.save()
        if CAMS in self.active():
            have, folder = fetched.get(CAMS), m.folder(CAMS, "fetched")
            if not (have and have.get("listed") == self.listed[CAMS] and _pair(folder)):
                fetched.pop(CAMS, None)
                try:
                    if await self._cams_get():
                        fetched[CAMS] = {"at": now(), "listed": self.listed[CAMS]}
                        m.facts.pop("asked", None)
                except (Stop, Refused, Changed, PWError, AssertionError) as e:
                    await self.stopped(CAMS, e)              # CAMS is left out; KFintech goes on
                m.save()

    async def _cams_get(self) -> bool:
        """CAMS emails the month: ask for it (once), then take the zip and the Excel from the mailbox, or from the
        person when no mailbox is connected. False when the person skipped CAMS instead of adding its files: CAMS
        is left out of this run, and the next one does not ask CAMS for the email again."""
        host, m, page = self.host, self.month, self.pages[CAMS]
        # forwarded to us, or Gmail: the email is waited for; whatever fails falls back to by hand (Neil, 7 Oct)
        by_hand = host.profile["mailbox"]["provider"] not in ("gmail", "forward")
        if not by_hand:
            ok, said = await host.mailbox_ok()
            if not ok:
                host.activity(f"CAMS's email couldn't be read ({said}): its files are asked for instead", CAMS)
                by_hand = True
        asked = m.facts.get("asked") or {}
        # CAMS's last request is waited on while CAMS still lists what it listed then: its email holds every invoice.
        # Anything new listed since, and CAMS is asked again (Neil, 8 Oct: by what CAMS lists, not by the clock)
        waiting = bool(asked) and asked.get("listed") == self.listed[CAMS]
        # an email of CAMS's for this month already on this PC (from the mailbox, or added by hand on Downloads) does,
        # whichever request it answered: CAMS isn't asked again. The mailbox is looked in first when it is read by itself
        looking = not (by_hand or waiting)
        if looking:
            await self.at("Get", "Looking for CAMS's emails already in your mailbox")
        shown = time.monotonic()
        found = await self._month_mail(fetch=looking)
        if looking:
            await asyncio.sleep(max(0.0, MIN_SHOWN_S - (time.monotonic() - shown)))
        if found:
            return self._take_cams(found, "Found CAMS's email for {} in your mailbox")
        if not waiting:
            await self.at("Get", f"Asking CAMS to email {self.label}'s invoices")
            async def ask() -> str:                      # (after a reload the listing is read again first)
                if not await cams.ready_to_ask(page):
                    await cams.list_month(page, self.period)
                return await cams.request_mailback(page)
            ref = await self.patient(CAMS, ask)
            await host.picture(page, "cams-asked")
            asked = m.facts["asked"] = {"ref": ref or asked.get("ref", ""), "at": now(), "listed": self.listed[CAMS]}
            m.save()
            host.activity(f"Asked CAMS to email {self.label}'s invoices" + (f" (ref {ref})" if ref else ""), CAMS)

        dest = m.folder(CAMS, "fetched")
        if by_hand:
            pair = await self._by_hand()
            if pair is None:
                return False
        elif not self.wait_email:
            # several months at once: asked now, read in later by the app's wait over all of them (`pickup`)
            pair = await self._ours(await host.mail_look(asked["ref"])) or await self._month_mail(fetch=False)
            if not pair:
                self.skipped.add(CAMS)
                self.aside[CAMS] = "CAMS's email is asked for"
                return False
        else:
            await self.at("Get", "Waiting for CAMS's email")
            # Skip CAMS (KFintech goes on) or, CAMS alone, Don't wait (Neil, 8 Oct): the email is read in when it comes.
            # A software too old for Don't wait offers Skip CAMS only with KFintech; older still, neither.
            skip = getattr(host, "skip_wanted", None)
            alone = KFIN not in self.active()
            if skip and "alone" in inspect.signature(host.waiting_email).parameters:
                await host.waiting_email(asked["at"], asked["ref"], skip=True, alone=alone)
            elif skip and not alone:
                await host.waiting_email(asked["at"], asked["ref"], skip=True)
            else:
                skip = None
                await host.waiting_email(asked["at"], asked["ref"])
            deadline = time.monotonic() + MAIL_GIVE_UP_S
            while True:
                pair = await self._ours(await host.mail_look(asked["ref"])) or await self._month_mail(fetch=False)
                if pair:
                    break
                if skip and skip():
                    # CAMS's request stands (`asked` is kept): its email is read when it comes, and asked for no more
                    self.skipped.add(CAMS)
                    self.aside[CAMS] = "CAMS's email hadn't come; it's read when it does"
                    return False
                if time.monotonic() > deadline:
                    # not here in time: by hand from here (the files from CAMS's email, if it has come elsewhere).
                    # The request stands, so the email is still read when it comes; a request already waited out
                    # once (an email lost on the way) is forgotten, and the next run asks CAMS again
                    if waiting:
                        m.facts.pop("asked", None)
                        m.save()
                    host.activity(f"CAMS's email hadn't come {MAIL_GIVE_UP_S // 60} minutes after it was asked "
                                  "for: its files were asked for instead", CAMS)
                    pair = await self._by_hand()
                    if pair is None:
                        return False
                    break
                await asyncio.sleep(MAIL_EVERY_S)
        return self._take_cams(pair, "Got CAMS's invoices for {}")

    async def _by_hand(self) -> list[Path] | None:
        """CAMS's two files, chosen by the person; None when they skipped CAMS instead. Files that can't be this run's
        (another month or ARN, a zip not of its Excel) are refused there and then,
        with the reason, and the person chooses again or skips CAMS (Neil, 8 Oct)."""
        await self.at("Get", "Choose CAMS's invoice files")
        said = self.behind
        while True:
            got = await self._files(said)
            if got.get("skip"):
                self.skipped.add(CAMS)
                self.aside[CAMS] = "CAMS's files weren't added"
                return None
            pair = [Path(got["zip"]), Path(got["xls"])]
            said = await asyncio.to_thread(self._unusable, pair)
            if not said:
                return pair
            log.info("CAMS's files refused: %s", said)

    async def _files(self, said: str) -> dict:
        skip = KFIN in self.active()
        if "message" in inspect.signature(self.host.files).parameters:
            return await self.host.files(self.label, skip=skip, message=said)
        if said and said != self.behind:                # a software too old to say why: the run stops on it instead
            raise Stop("wrong_files", "These files can't be used", said, registrar=CAMS)
        return await self.host.files(self.label, skip=skip)

    def _unusable(self, pair: list[Path]) -> str:
        """Why this zip and Excel can't be this run's, in a sentence; empty when they can."""
        try:
            got = cams.added(pair[0], pair[1])
        except Stop as e:
            return f"{e.title}."
        if got["arn"] != re.sub(r"\D", "", str(self.host.profile.get("arn") or "")):
            return f"These files are for ARN-{got['arn']}, not this ARN."
        if got["period"] != self.period:
            return f"These files are {words.labels(got['period'])[0]}'s, not {self.label}'s."
        return ""                    # fewer invoices than CAMS lists is no reason to refuse: the run says what's missing

    def _take_cams(self, pair: list[Path], said: str) -> bool:
        dest = self.month.folder(CAMS, "fetched", empty=True)        # the latest pair only, never two
        for src in pair:
            shutil.copyfile(src, dest / Path(src).name)
        self.host.activity(said.format(self.label), CAMS)
        return True

    def _arn_rows(self, rows: list[dict]) -> bool:
        arn = re.sub(r"\D", "", str(self.host.profile.get("arn") or ""))
        return {re.sub(r"\D", "", str(r.get("BROKER CODE") or "")) for r in rows} == {arn}

    async def _ours(self, pair: list[Path] | None) -> list[Path] | None:
        """A pair from the mailbox only if its Excel is this ARN's and this month's; else it is ignored, so a
        mailback for another month never reaches this month's folder."""
        if not pair:
            return None
        try:
            rows = await asyncio.to_thread(cams.read_report, pair[1], self.period)
        except (Stop, Changed, OSError, ValueError):
            return None
        return pair if self._arn_rows(rows) else None

    async def _month_mail(self, fetch: bool) -> list[Path] | None:
        """The newest of CAMS's emails on this PC (the mailbox's, or added on Downloads) that is this ARN's month and
        holds every invoice CAMS lists now, whichever request it answered (Neil, 7 Oct). None when there is none, or the
        software is too old to say."""
        look = getattr(self.host, "mail_pairs", None)
        if look is None:
            return None
        for zip_file, xls in await look(fetch):
            try:
                rows = await asyncio.to_thread(cams.read_report, xls, self.period)
            except (Stop, Changed, OSError, ValueError):
                continue                                             # another month's, or not a report we know
            if not self._arn_rows(rows):
                continue
            missing = [k for k in self.listed[CAMS] if k not in {r[cams.CAMS_INVOICE] for r in rows}]
            if missing:                                              # older than what CAMS lists now: said once
                self.behind = self.behind or (
                    f"CAMS lists {plural(len(self.listed[CAMS]), 'invoice')} for {self.label} now and its last email "
                    f"held {len(rows)}: {', '.join(missing)} came since, so CAMS was asked to email them again.")
                continue
            return [zip_file, xls]
        return None

    # --- Read ---------------------------------------------------------------------------------------------------------

    async def read(self) -> None:
        m = self.month
        self.locked = self.issued().locked if self.own and not self.books else {}
        if CAMS in self.active():
            await self.at("Read", "Reading CAMS's invoices")
            try:
                await asyncio.to_thread(self._read_cams)
                if self.late:
                    self.note(self.late)
                # the files are this ARN's month, as emailed by CAMS: an ARN set up without KFintech is bound now
                confirm = getattr(self.host, "confirm_arn", None)
                if confirm:
                    ok, said = await confirm()
                    if not ok:
                        raise Stop("arn_unbound", "This ARN couldn't be added to your account", "Nothing was submitted. "
                                   "CAMS's files for this month are on this PC, so the next run starts from them.",
                                   said=said, registrar=CAMS)
            except Stop as e:
                if not e.registrar:
                    raise
                await self.stopped(CAMS, e)                  # CAMS is left out; KFintech goes on
        if KFIN in self.active():
            await self.at("Read", "Reading KFintech's invoices")
            await asyncio.to_thread(self._read_kfin)
            # KFintech lists it and its download holds no file for it (seen 7 Oct): said, and the rest go on
            self.no_file = [k for k in self.listed.get(KFIN, []) if k not in self.items]
            m.facts.get("fetched", {}).get(KFIN, {}).pop("lacks", None)
            if self.no_file:
                # the files are not the whole listing: the next run fetches them again, this one goes on without
                m.facts.setdefault("fetched", {}).setdefault(KFIN, {})["lacks"] = list(self.no_file)
                self.note(f"KFintech lists {plural(len(self.listed[KFIN]), 'invoice')} for {self.kf_label} "
                          f"and its download held {len(self.listed[KFIN]) - len(self.no_file)}. "
                          f"No file for {', '.join(self.no_file)}.")
        self.open = [k for reg in self.regs for k, i in self.items.items()
                     if i["registrar"] == reg and reg in self.active() and k not in m.with_registrar(reg)]
        if self.own:
            self.cannot_draw = {k: why for k in self.open if (why := own.drawable(self.items[k]))}
        # two invoices under one KFintech reference (`kfin.read_zip`): how KFintech takes them back is not known yet
        self.cannot_draw.update({k: "KFintech raised two invoices for this payment (GST on top and GST within). "
                                    f"{NAME} doesn't send these yet: send this one on KFintech yourself."
                                 for k in self.open if len(self.items[k].get("one", {}).get("parts") or []) > 1})
        self.blocked = dict(self.cannot_draw)
        m.save()
        await self.host.changed()

    def _read_cams(self) -> None:
        m = self.month
        zip_file, xls = _pair(m.folder(CAMS, "fetched"))
        try:
            self.report = cams.read_report(xls, self.period)
            behind = set(self.listed[CAMS]) - {r[cams.CAMS_INVOICE] for r in self.report}
            if behind:
                # the run goes on with what the files hold; the next run fetches them again
                # (this runs in a thread: the note is said by `read`, once it is back)
                self.late = (f"CAMS lists {plural(len(self.listed[CAMS]), 'invoice')} for {self.label} and its files "
                             f"hold {len(self.report)}: {', '.join(sorted(behind))} weren't in them, so they weren't "
                             "sent. The next run gets them.")
                m.facts.get("fetched", {}).pop(CAMS, None)
                m.save()
            pdfs = cams.match_pdfs(self.report, files.zip_extract(zip_file, m.folder(CAMS, "invoices")))
        except Stop:
            m.facts.get("fetched", {}).pop(CAMS, None)           # not the month's files: the next run gets them again
            m.save()
            raise
        self.report_file = xls
        for r in self.report:
            key = r[cams.CAMS_INVOICE]
            info = cams.read_pdf(pdfs[key])
            house = words.fund_house(r["AMC NAME"] or info["name"], r["AMC CODE"], CAMS) or key
            self.items[key] = {
                "key": key, "registrar": CAMS, "house": house, "code": r["AMC CODE"], "date": info["date"],
                "party": info["party"], "taxable": words.amount(r["TAXABLE VALUE"]),
                "cgst": words.amount(r["CGST AMOUNT"]), "sgst": words.amount(r["SGST AMOUNT"]),
                "igst": words.amount(r["IGST AMOUNT"]), "pdf": pdfs[key], "gap": info["gap"],
                "page_h": info["page_h"], "name": pdfs[key].name, "row": r}
            self._row(self.items[key], number=key)

    def _read_kfin(self) -> None:
        m = self.month
        for one in kfin.read_zip(_newest(m.folder(KFIN, "fetched"), ".zip"), m.folder(KFIN, "invoices")):
            key = one["ref"]
            info = kfin.read_pdf(one)
            house = words.fund_house(one["amc_name"], one["fund_code"], KFIN) or key
            self.items[key] = {
                "key": key, "registrar": KFIN, "house": house, "code": one["fund_code"],
                "date": words.iso_date(one["date"]), "party": one["party"], "taxable": one["taxable"],
                "cgst": one["cgst"], "sgst": one["sgst"], "igst": one["igst"], "pdf": one["pdf"], "gap": info["gap"],
                "page_h": info["page_h"], "name": kfin.upload_name(one["pdf"].name), "one": one}
            self._row(self.items[key], number=one["serial"])

    def _row(self, item: dict, number: str) -> None:
        """The invoice's row in the month's record. A number or a signed file it already has is kept."""
        m, key, reg = self.month, item["key"], item["registrar"]
        had = m.rows.get(key, {})
        said = m.said_about(reg, key)
        kept = had.get("file") if had.get("file") and m.path(had["file"]).is_file() else m.rel(item["pdf"])
        item["dated"] = (had.get("dated") or "") if self.own else ""      # sent dated another day than the registrar's
        if self.own:                                  # the number on the person's own invoice, once it has one
            number = had.get("number", "") if self.books else self.locked.get(key, "")
        party = item.get("party")                     # the fund house as the invoice names it: Tally finds it by GSTIN
        gstin = (party.gstin if party else "") or (item.get("one") or {}).get("amc_gstin", "")
        m.put(reg, key, gstin=gstin.upper(), party=party.name if party else "",
              amc=item["house"], code=item["code"], date=item["date"], taxable=item["taxable"],
              cgst=item["cgst"], sgst=item["sgst"], igst=item["igst"], number=number,
              said=said.get("status", ""), remarks=said.get("remarks", ""), file=kept)

    def read_line(self) -> str:
        xs = [self.items[k] for k in self.open]
        gst = sum(i["cgst"] + i["sgst"] + i["igst"] for i in xs)
        return f"{plural(len(xs), 'invoice')} to do · {inr(sum(i['taxable'] for i in xs))} taxable · {inr(gst)} GST"

    # --- Sign ---------------------------------------------------------------------------------------------------------

    def _sign_one(self, key: str) -> Path:
        """The registrar's own invoice, with the signature where its own words say it goes."""
        item, sig = self.items[key], self.host.signature()
        out = self.month.folder(item["registrar"], "signed") / item["name"]
        self.host.sign(item["pdf"], out, [signature.place(item["gap"], sig, item["page_h"])])
        self.signed[key] = out
        self.month.put(item["registrar"], key, file=self.month.rel(out), signedAt=now(), own=False)
        return out

    def _draw_one(self, key: str, number: str) -> Path:
        """The person's own invoice for this one, with this number, signed."""
        item = self.items[key]
        shown = {**item, "date": item.get("dated") or item["date"]}
        out = own.draw(self.host, shown, number, self.period, self.month.folder(item["registrar"], "signed"))
        self.signed[key] = out
        self.month.put(item["registrar"], key, file=self.month.rel(out), signedAt=now(), own=True, number=number)
        return out

    def issued(self) -> numbering.Issued:
        inv = self.host.profile["invoices"]
        return numbering.Issued(self.host.base / "books.json", inv.get("last") or "", int(inv.get("at", -1)))

    def _need_signature(self) -> None:
        if not self.host.signature().get("present"):
            raise Stop("setup", "Your signature isn't set up on this PC",
                       "Add it in Settings › Your invoices, then run again. Nothing was submitted.")

    async def _look(self, first: str, number: str, step: str) -> None:
        """The first run for this ARN: one real invoice, before the rest are signed. `number` is shown, not given."""
        host, m = self.host, self.month
        while True:
            await self.at(step, "Signing one invoice for you to look at")
            if self.own:
                reg, was = self.items[first]["registrar"], m.rows.get(first, {})
                if self.books and self.preview is None:
                    self.preview = (first, {k: was.get(k, "") for k in ("number", "file", "signedAt")})
                await asyncio.to_thread(self._draw_one, first, number)
                if self.books:                               # the books' own number (an earlier run's) stays on the row
                    m.put(reg, first, number=self.preview[1]["number"])
                else:
                    m.put(reg, first, number="")
            else:
                await asyncio.to_thread(self._sign_one, first)
            m.save()
            answer = await host.looks_right(first, self.items[first]["house"])
            if answer.get("looks_right"):
                host.put("signature_seen", now())
                return
            if not answer.get("fixed"):
                raise Stop("ended", "Stopped", "The signature wasn't confirmed, so nothing was signed or submitted.")

    async def sign(self) -> None:
        """Registrar invoices signed; own invoices without books: only the first-run look (they are drawn after Your
        check). Own invoices with books never come here: `preview_first`, then `sign_own`."""
        host, m = self.host, self.month
        self._need_signature()
        can = [k for k in self.open if k not in self.blocked]
        if self.own and can and not self.issued().ready:
            raise Stop("setup", "Your last invoice number is missing",
                       "Add it in Settings › Your invoices, then run again. Nothing was submitted.")
        if can and not host.get("signature_seen"):
            number = self.issued().hand_out([can[0]])[can[0]] if self.own else ""
            await self._look(can[0], number, "Sign")
        if not self.own:
            await self.at("Sign", "Signing the invoices")
            for key in can:
                await asyncio.to_thread(self._sign_one, key)
            m.save()
            await host.changed()

    # --- the books (own invoices, Tally or Zoho Books connected) --------------------------------------------------------------------

    def _books_line(self, on: bool, got: dict | None = None) -> None:
        self.host.books_waiting(on, books.company(self.host.base) if on else "", (got or {}).get("said", ""), self.kind)

    async def _books_call(self, call, *args) -> dict:
        """Run a call on the books (in a thread). While they are not answering the run waits, on a red line with a
        refresh button, and goes on when they answer. Stop works throughout. A refusal passes through."""
        waiting = False
        try:
            while True:
                try:
                    got = await asyncio.to_thread(call, *args)
                except books.Off as e:
                    got = {"state": "off", "said": e.said}
                if got.get("state", "ready") == "ready":
                    return got
                waiting = True
                self._books_line(True, got)
                await self.host.books_nap()
        finally:
            if waiting:
                self._books_line(False)

    def _blocked_by_books(self, got: dict) -> None:
        """What the books say cannot go in this run, on top of what cannot be drawn. An invoice that Tally would
        renumber others for is not blocked: Your check offers to date it today."""
        self.renumber = {}
        blocks = {}
        for r in got["rows"]:
            if not r.get("block"):
                continue
            if (r.get("why") or {}).get("kind") == "renumber" and DATE_IF_RENUMBERED:
                self.renumber[r["key"]] = r["why"]
            else:
                blocks[r["key"]] = r["block"]
        self.blocked = {**self.cannot_draw, **blocks}

    async def glance(self) -> None:
        """Read the books before Your check: what each open invoice would do there, what is blocked and why, the
        year's first number, the older-month line. The books' questions are asked here, once, and remembered."""
        keys = [k for k in self.open if k not in self.blocked]
        await self.at("Read", f"Reading your {self.bname}")
        for _round in range(4):
            got = await self._books_call(self.books.glance, keys)
            if not got["asks"]:
                break
            answers = await self.host.books_ask(got["asks"])
            await asyncio.to_thread(self.books.answer, answers)
        else:
            raise Stop("ours", f"{self.bname}'s questions weren't settled", "Nothing was submitted.")
        self.glanced = got
        self._blocked_by_books(got)

    async def finish_in_books(self) -> None:
        """Own invoices already with the registrar and in the books by our id: their signed PDF put with them and
        called sent, if an earlier run could not (both are safe to repeat; Tally's are nothing). A refusal is written
        in the activity and the run goes on."""
        m = self.month
        keys = [k for k, r in m.rows.items() if r.get("own") and r["registrar"] in self.regs
                and k in m.with_registrar(r["registrar"])]
        if not keys:
            return
        try:
            got = await self._books_call(self.books.glance, keys)
        except books.Refused as e:
            log.warning("books: the look at sent invoices was refused: %s", e)
            return
        for r in got.get("rows", []):
            if r.get("action") != "in_books":
                continue
            row = m.rows.get(r["key"], {})
            pdf = m.path(row["file"]) if row.get("file") else None
            if pdf and pdf.is_file():
                await self._books_note(r["key"], self.books.after_sign, r["key"], pdf)
            await self._books_note(r["key"], self.books.after_submit, r["key"])

    async def preview_first(self) -> None:
        """The first run for this ARN, own invoices with books: one invoice drawn with the number the books would give
        next (looked at, nothing written to the books), before Your check."""
        self._need_signature()
        can = [k for k in self.open if k not in self.blocked]
        if can and not self.host.get("signature_seen"):
            await self._look(can[0], self.glanced.get("peek") or "1", "Read")

    async def fetch_numbers(self, ticked: list[str]) -> list[str]:
        """Each ticked invoice into the books, in date order, and the invoice number it holds there read back. One the
        books refuse is not numbered or sent this run, with the books' words; the others go on."""
        host, m = self.host, self.month
        started = time.monotonic()
        await self.at("Your books", "Fetching your last invoice number")
        await self._books_call(self.books.glance, ticked)
        await asyncio.sleep(max(0.0, MIN_SHOWN_S - (time.monotonic() - started)))
        # every number the books will give is checked before the first write: KFintech refuses what Rule 46 or its own
        # length rule refuses, and an invoice written into the books keeps its number for good
        guess = await self._books_call(self.books.predict, ticked, self.first)
        for n in guess.get("numbers") or []:
            if numbering.rule_46(n):
                if self.kind == "zoho":
                    fix = ("In Zoho Books, set the invoice numbering to start from your next number (with its prefix), "
                           "or to manual.")
                else:
                    fix = (f"In Tally, set {guess.get('where') or 'the sales voucher type'}'s numbering to start from "
                           "your next number (with its prefix or suffix), or to Manual.")
                raise Stop("numbering", f"{self.bname} would number this invoice {n}",
                           f"KFintech needs invoice numbers of at least 3 characters. {fix} Nothing was written to {self.bname}.")
        order = sorted(ticked, key=lambda k: (self.items[k].get("dated") or self.items[k]["date"], self.items[k]["registrar"] != CAMS,
                                              self.items[k]["house"].lower()))
        said = []
        for key in order:
            item = self.items[key]
            await self.at("Your books", f"Putting {item['house']}'s invoice into {self.bname}")
            try:
                placed = await self._books_call(self.books.place, key, self.first)
            except books.Refused as e:
                self.blocked[key] = str(e)
                self.left.append({"amc": item["house"], "why": str(e)})
                said.append(f"{item['house']}: {e}")
                continue
            self.numbers[key] = placed["number"]
            m.put(item["registrar"], key, number=placed["number"], books=placed["number"], booksAt=now())
            m.save()
            host.activity(f"{item['house']}'s invoice is in {self.bname} as {placed['number']}"
                          + (" (it was typed there already)" if placed["adopted"] else
                             "" if placed["fresh"] else " (it was there already)"))
        await self._reread(said)
        try:
            self.issued().keep(self.numbers)
        except OSError:
            log.warning("books.json could not be written", exc_info=True)
        good = [k for k in ticked if k in self.numbers]
        if not good:
            raise Stop("books_refused", f"{self.bname} took none of the invoices", "Nothing was submitted.",
                       said="\n".join(said[:8]))
        await self.done("Your books", plural(len(good), "invoice") + f" in {self.bname}")
        return good

    async def _reread(self, said: list[str]) -> None:
        """Every invoice placed, read once more by our id: placing a later one can change an earlier one's number (the
        books renumber), so the number each holds now is the one used. Two holding one number are both set aside
        for this run: two PDFs are never drawn with one number."""
        m = self.month
        placed = list(self.numbers)
        if not placed:
            return
        got = await self._books_call(self.books.glance, placed)
        held = {r["key"]: r.get("number") for r in got.get("rows", [])
                if r.get("action") == "in_books" and r.get("number")}
        for key in placed:
            number = held.get(key)
            if number and number != self.numbers[key]:
                log.info("books: %s changed from %s to %s since it was placed", key, self.numbers[key], number)
                self.numbers[key] = number
                m.put(self.items[key]["registrar"], key, number=number, books=number)
        by_number: dict[str, list[str]] = {}
        for key in placed:
            by_number.setdefault(self.numbers[key], []).append(key)
        for number, keys in by_number.items():
            if len(keys) < 2:
                continue
            houses = " and ".join(self.items[k]["house"] for k in keys)
            why = f"{houses} both hold the number {number} in {self.bname}. Fix one there, then run again."
            for key in keys:
                self.numbers.pop(key, None)
                self.blocked[key] = why
                m.put(self.items[key]["registrar"], key, number="")
            self.left.append({"amc": houses, "why": why})
            said.append(why)
        m.save()

    async def _books_note(self, key: str, call, *args) -> None:
        """A step after the invoice is in the books (its PDF put with it, then called sent). The invoice is there
        either way, so a refusal is written in the activity, not a reason to stop; the next run does it again
        (`finish_in_books`)."""
        try:
            await self._books_call(call, *args)
        except books.Refused as e:
            log.warning("books: %s for %s: %s", call.__name__, key, e)
            house = self.items.get(key, {}).get("house") or self.month.rows.get(key, {}).get("amc") or key
            self.host.activity(f"{house}'s invoice is in {self.bname}, but not finished there: {e}",
                               tone="bad")

    def unpreview(self, ticked: list[str]) -> None:
        """The first run's preview was drawn with a number only peeked at. If that invoice is not going on in this run
        (not ticked), its row goes back to unsigned so the peeked PDF is not left as its file."""
        if not self.preview or self.preview[0] in ticked:
            return
        key, was = self.preview
        reg = self.items[key]["registrar"]
        shown = self.signed.pop(key, None)
        self.month.put(reg, key, file=was["file"], signedAt=was["signedAt"], number=was["number"])
        if shown and shown.is_file() and self.month.rel(shown) != was["file"]:
            try:
                shown.unlink()
            except OSError:
                log.warning("the preview of %s could not be removed", key, exc_info=True)
        self.month.save()

    async def sign_own(self, ticked: list[str]) -> None:
        """Every invoice that is in the books, drawn with exactly the invoice number the books hold, and signed."""
        self._need_signature()
        await self.at("Sign", "Making your invoices")
        for key in ticked:
            await asyncio.to_thread(self._draw_one, key, self.numbers[key])
        self.month.save()
        await self.host.changed()
        for key in ticked:                                  # the signed PDF goes with the invoice in the books
            await self._books_note(key, self.books.after_sign, key, self.signed[key])
        await self.done("Sign", f"{len(ticked)} made")

    # --- Your check ---------------------------------------------------------------------------------------------------

    async def your_check(self) -> list[str] | None:
        """The person's look at every open invoice. Returns the ones that stayed ticked, or None for "Not now"."""
        host, m = self.host, self.month
        left_out = set(m.facts.get("leftOut") or [])
        can = [k for k in self.open if k not in self.blocked]
        issued = self.issued() if self.own and not self.books else None
        proposed = issued.hand_out(can) if issued and can else {}
        rows = []
        by_key = {r["key"]: r for r in self.glanced.get("rows", [])} if self.books else {}
        for key in self.open:
            i = self.items[key]
            said = m.said_about(i["registrar"], key)
            rejected = words.meaning(i["registrar"], said.get("status")) == "rejected"
            row = {"key": key, "registrar": i["registrar"], "amc": i["house"], "number": proposed.get(key, ""),
                   "taxable": i["taxable"], "gst": round(i["cgst"] + i["sgst"] + i["igst"], 2), "igst": i["igst"] > 0,
                   "included": key not in left_out and key not in self.blocked and key not in self.renumber,
                   "blocked": self.blocked.get(key, ""),
                   "rejection": (said.get("remarks") or said.get("status") or "") if rejected else ""}
            if key in proposed:
                row.update(seq=can.index(key), kept=bool(issued.number_of(key)))
            if key in self.renumber:
                row["renumber"] = {"date": self.renumber[key]["date"], "type": self.renumber[key]["type"]}
            if key in by_key:
                got = by_key[key]
                if got["action"] == "in_books":
                    row["note"] = f"In {self.bname} as {got['number']}, not sent yet" if got["number"] else f"In {self.bname}, not sent yet"
                elif got["action"] == "by_hand":
                    row["note"] = (f"Typed in {self.bname} as {got['number']}. It will be changed to the registrar's "
                                   "figures, keeping that number.")
            rows.append(row)
        extra = None
        if self.books:
            g = self.glanced
            extra = {"kind": self.kind, "company": g.get("company") or books.company(host.base), "after": g.get("after", ""),
                     "first": g.get("first"), "creates": g.get("creates") or []}
        await self.at("Your check", "Your check")
        notes = [f"{self.aside[r]}." for r in self.regs if r in self.aside]
        answer = await (host.your_check(rows, notes, extra) if extra else host.your_check(rows, notes))
        if not answer.get("confirmed"):
            return None
        ticked = [k for k in self.open if k in set(answer.get("included") or []) and k not in self.blocked]
        today = datetime.now().date().isoformat()
        dated = set(answer.get("dated") or [])
        # one Tally would renumber for: ticked only when the person chose to date it today, else it is put aside
        ticked = [k for k in ticked if k not in self.renumber or k in dated]
        for key in ticked:
            if key in self.renumber:
                self.items[key]["dated"] = today
                m.put(self.items[key]["registrar"], key, dated=today)
        m.facts["leftOut"] = [k for k in self.open if k not in ticked and k not in self.blocked]
        if self.books:
            self.first = str(answer.get("first") or "").strip()
            if self.first and (why := numbering.rule_46(self.first)):
                raise Stop("setup", "That first invoice number can't be used", why, "Nothing was submitted.")
        m.save()
        host.activity(f"Checked {plural(len(self.open), 'invoice')}, {len(ticked)} ticked")
        return ticked

    # --- one registrar: prepare, its own check, Submit ----------------------------------------------------------------

    async def send(self, reg: str, ticked: list[str]) -> None:
        host, m, page = self.host, self.month, self.pages[reg]
        name = NAMES[reg]
        sending = [k for k in ticked if self.items[k]["registrar"] == reg]
        numbers: dict[str, str] | None = None
        issued = None
        if self.own and self.books:
            numbers = {k: self.numbers[k] for k in sending}      # in the books already, and drawn after Your books
        elif self.own:
            await self.at(name, "Making your invoices")
            issued = self.issued()
            numbers = issued.hand_out(sending)
            for key in sending:
                await asyncio.to_thread(self._draw_one, key, numbers[key])
                m.put(reg, key, number="")                 # the number is the invoice's only once Submit is pressed
            m.save()

        if reg == CAMS:
            await self.at(name, "Preparing CAMS's upload")
            folder = m.folder(CAMS, "upload", empty=True)
            out_zip, out_sheet = folder / f"CAMS_{self.period}.zip", folder / f"CAMS_{self.period}.xlsx"
            await asyncio.to_thread(cams.pack, sending, self.report, self.report_file, self.signed, numbers,
                                    out_zip, out_sheet)
            async def open_and_attach() -> list[dict]:
                await cams.open_upload(page, self.period, self.own)
                return await cams.attach(page, out_zip, out_sheet)
            review = await self.patient(CAMS, open_and_attach)
            await host.picture(page, "cams-review")
            await self.at(name, "Checking CAMS read the upload right")
            rows = [r for r in self.report if r[cams.CAMS_INVOICE] in set(sending)]
            unfilled = [r for r in self.report if r[cams.CAMS_INVOICE] not in set(sending)]
            diffs = cams.compare(rows, review, unfilled, numbers)
            if diffs:
                await cams.cancel_review(page)
                m.facts.get("fetched", {}).pop(CAMS, None)       # the files may be behind CAMS: got again next run
                m.save()
                raise Stop("mismatch", "CAMS read the upload differently", "Nothing was submitted. The next run gets "
                           "CAMS's invoices again.", said="\n".join(self._diff(d) for d in diffs[:6]), registrar=CAMS)
            await self.at(name, "CAMS is checking every invoice")
            verdict = await cams.press_continue(page, sending)
            await host.picture(page, "cams-validation")
            bad = verdict["refused"] + [{"key": k, "remarks": "not in CAMS's list"} for k in verdict["absent"]]
            if bad or verdict["invalid"]:
                await cams.back_to_files(page)
                raise Stop("portal_validation",
                           f"CAMS didn't accept {len(bad) or verdict['invalid']} of {plural(len(sending), 'invoice')}",
                           "Nothing was submitted. Run again and untick them at Your check; the rest can go.",
                           said="\n".join(f"{self.items[b['key']]['house']}: {b['remarks'] or 'no reason given'}"
                                          for b in bad[:8]), registrar=CAMS)
            button = await cams.find_submit(page)
        else:
            await self.at(name, "Filling in KFintech's page")
            ones = [{**self.items[k]["one"], "date": self.items[k]["dated"]} if self.items[k].get("dated")
                    else self.items[k]["one"] for k in sending]
            filled = await self.patient(KFIN, lambda: kfin.fill_grid(page, self.period, ones, self.signed, numbers))
            await self.at(name, "Checking KFintech's page")
            await kfin.verify_grid(page, filled)
            await host.picture(page, "kfintech-ready")
            button = await kfin.find_submit(page)

        for key in sending:
            m.put(reg, key, checkedAt=now())
        if not host.submit:
            self.ready[reg] = len(sending)
            await self.done(name, f"{len(sending)} ready, not submitted")
            return

        # Written down before it is pressed, so a press nobody answered is still known about. The person's own
        # numbers are these invoices' for good from here.
        await self.at(name, f"Submitting to {name}")
        m.facts.setdefault("pressed", {})[reg] = {"at": now(), "keys": sending}
        if numbers:
            if issued:                                   # without books: given for good now
                top = issued.lock(numbers, numbering.fy_of(self.items[sending[0]]["date"]))
                host.set_last_number(top, issued.at)
            self.used += [numbers[k] for k in sending]
            for key in sending:
                m.put(reg, key, number=numbers[key])
        m.save()
        host.activity(f"Pressed Submit for {plural(len(sending), 'invoice')}", reg)
        host.hold_stop(True)                             # Stop waits for the registrar's answer to this one press
        try:
            if reg == CAMS:
                answered, said = await cams.click_submit(page, button, sending)
            else:
                answered, said, _all = await kfin.click_submit(page, button)
        finally:
            host.hold_stop(False)
        await host.picture(page, f"{reg.lower()}-after-submit")
        if not answered:
            raise Stop("unknown_submit", f"{name} didn't answer the Submit",
                       "It may or may not have gone through. Nothing is sent twice: the next run reads "
                       f"{name}'s status first and sends only what {name} doesn't have.", said=said, registrar=reg)

        # The registrar's own status page says what it has now.
        await self.at(name, f"Reading what {name} has now")
        if reg == CAMS:
            reading = await cams.read_status(page, self.period)
        else:
            reading = await kfin.read_status(page, self.period) or []
        m.read_status(reg, [{"key": r["key"], "status": r["status"], "remarks": r["remarks"]}
                            for r in reading])
        # a word never seen on a pressed invoice: the registrar has it, so it counts as submitted (`is_final`)
        landed = [k for k in sending if k in m.with_registrar(reg)]
        for r in reading:
            if r["key"] in landed and words.meaning(reg, r["status"]) == "unknown":
                self.note(f"{name} shows '{(r['status'] or '').strip()}' for {self.items[r['key']]['house']}: "
                          "counted as submitted.")
        for key in landed:
            m.put(reg, key, sentAt=now())
            if self.own and not self.books and numbers:   # no books: for the person to enter in theirs
                self.entered.append({"registrar": reg, "amc": self.items[key]["house"], "key": key,
                                     "number": numbers[key]})
        m.save()
        await host.changed()
        if self.own and self.books:
            for key in landed:                               # the registrar has it: the books may call it sent
                await self._books_note(key, self.books.after_submit, key)
        if landed:
            self.sent[reg] = len(landed)
            await host.submitted(reg, len(landed))
            host.activity(f"Submitted {plural(len(landed), 'invoice')}", reg)
        if len(landed) < len(sending):
            raise Stop("unconfirmed", f"{name}'s status shows {len(landed)} of {len(sending)} submitted",
                       f"Nothing is sent twice: the next run reads {name}'s status first and sends only what "
                       f"{name} doesn't have.", said=said, registrar=reg)
        await self.done(name, f"{len(landed)} submitted")

    def _diff(self, d: dict) -> str:
        house = self.items.get(d["key"], {}).get("house") or d["key"]
        if not d["ours"] and not d["theirs"]:
            return f"{house}: {d['what']}"
        return f"{house}: {d['what']} is {d['ours']} in the upload and {d['theirs']} in CAMS's review"

    # --- the end ------------------------------------------------------------------------------------------------------

    def summary(self, ticked: list[str]) -> str:
        month = words.month_name(self.period)
        done = sum(self.sent.values())
        left = len(self.open) - done
        if not done:
            return f"Nothing was submitted for {month}."
        return f"{plural(done, 'invoice')} submitted for {month}." + (f" {left} left for later." if left else "")

    def used_line(self) -> str:
        if not self.used:
            return ""
        if self.books:
            return numbering.used_line(self.used, numbering.default_counter(self.used[0]), f"Invoice numbers from {self.bname}:")
        return numbering.used_line(self.used, self.issued().at)

    def so_far(self) -> str:
        parts = []
        for reg in self.regs:
            if reg in self.sent:
                parts.append(f"{NAMES[reg]}: {self.sent[reg]} submitted")
            elif reg in self.ready:
                parts.append(f"{NAMES[reg]}: {self.ready[reg]} ready, not submitted")
            elif reg in self.problems:
                parts.append(f"{NAMES[reg]}: stopped" + (f" ({self.problems[reg].title})" if len(self.problems) > 1 else ""))
            elif reg in self.aside:
                parts.append(self.aside[reg])
        return " · ".join(parts)


def _kfin_files_good(have: dict | None, listed: list[str]) -> bool:
    """Are the KFintech files on this PC still this month's, and all of it? They are when KFintech lists exactly what
    it listed when they were fetched, and no listed fund was found to lack a file when they were read (its download
    can trail its listing; seen 7 Oct). One that lacked a file sends the next run back to fetch them again."""
    return bool(have) and have.get("listed") == listed and not have.get("lacks")


def _newest(folder: Path, *suffixes: str) -> Path | None:
    got = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in suffixes] if folder.is_dir() else []
    return max(got, key=lambda p: p.stat().st_mtime) if got else None


def _pair(folder: Path) -> tuple[Path, Path] | None:
    """CAMS's zip and Excel in a folder, or None when either is missing."""
    zip_file, xls = _newest(folder, ".zip"), _newest(folder, ".xls", ".xlsx")
    return (zip_file, xls) if zip_file and xls else None


# =====================================================================================================================
# what the app calls
# =====================================================================================================================

async def run(host, period: str, registrars: list[str]) -> dict:
    """The month's run. Returns how it ended: {how: done | stopped | nothing | closed, stop, summary, used, so_far}."""
    job = Job(host, period, registrars)
    order = ["Your check", "Your books", "Sign"] if job.books else ["Sign", "Your check"]
    await job.plan(["Check", "Get", "Read", *order, *[NAMES[r] for r in job.regs]])
    return await _guarded(job, _run)


async def _run(job: Job) -> dict:
    host = job.host
    if job.books and not (hasattr(host, "books_waiting") and (job.kind != "zoho" or hasattr(host, "books_token"))):
        raise Stop("setup", f"This version of {NAME} can't put invoices into {job.bname}",
                   "Update it, then run again. Nothing was submitted.")
    await job.enter()
    await job.status()
    job.anything_to_do()
    await job.done("Check", job.check_line())

    await job.at("Get", "Getting the invoices")
    await job.get()
    job.anything_to_do()
    await job.done("Get", " · ".join(f"{NAMES[r]} {len(job.listed[r])}" for r in job.active()))

    await job.read()
    if not job.open:
        job.raise_problems()
        raise Stop("nothing_to_do", f"Nothing to do for {words.month_name(job.period)}",
                   "Every invoice the registrars have raised is already submitted.")
    if job.books:
        await job.finish_in_books()
        await job.glance()                               # Tally is read, and waited for, before the person ticks
        await job.preview_first()
    await job.done("Read", job.read_line())

    if job.books:
        ticked = await job.your_check()
        if ticked is None:
            job.unpreview([])
            job.month.ended("stopped", "You closed Your check", code="not_now")
            return {"how": "closed"}
        await job.done("Your check", f"{len(ticked)} ticked")
        job.unpreview(ticked)
        ticked = await job.fetch_numbers(ticked)
        await job.sign_own(ticked)
    else:
        await job.sign()
        await job.done("Sign", "Made after your check" if job.own else f"{len(job.signed)} signed")
        ticked = await job.your_check()
        if ticked is None:
            job.month.ended("stopped", "You closed Your check", code="not_now")
            return {"how": "closed"}
        await job.done("Your check", f"{len(ticked)} ticked")
    going = [r for r in job.regs if r not in job.aside and any(job.items[k]["registrar"] == r for k in ticked)]
    for reg in job.regs:
        mine = [k for k in ticked if job.items[k]["registrar"] == reg]
        if reg in job.problems:                          # stopped before Submit: reported at the end
            continue
        if reg == KFIN and reg in going and time.monotonic() - job.portals_at > IDLE_S:
            await job.again()                            # KFintech's tab was last used over 20 minutes ago
            if reg in job.problems:
                continue
        if reg in job.aside or not mine:
            await job.done(NAMES[reg], job.aside.get(reg) or "nothing ticked")
            continue
        try:
            await job.send(reg, ticked)
        except (Stop, Refused, Changed, PWError, AssertionError) as e:
            job.problems[reg] = await _why(job, e, reg)
            await _keep(job, reg, e)
            await job.failed()

    summary = job.summary(ticked)
    if job.problems:
        raise next(iter(job.problems.values()))
    if job.ready:
        raise Stop("not_submitting", "Stopped just before Submit",
                   "Everything up to here was real, and the registrars have checked the uploads. Submit is switched "
                   "off on this PC.")
    job.month.ended("done", summary)
    host.activity(summary + (f" {job.used_line()}." if job.used else ""))
    total = sum(sum(job.items[k][f] for f in ("taxable", "cgst", "sgst", "igst")) for k in ticked)
    return {"how": "done", "summary": summary, "used": job.used_line(), "counts": job.sent, "total": round(total, 2),
            "enter": job.entered, "left": job.left, "notes": job.notes}


async def download(host, period: str, registrars: list[str], wait_email: bool = True) -> dict:
    """The month's invoices onto this PC, with their figures, and nothing more: nothing is signed or sent.
    `wait_email` False (several months, a mailbox read by itself): CAMS is asked for its email and the download goes on
    without waiting; the app waits for every month's email once they have all been asked for (Neil, 8 Oct)."""
    job = Job(host, period, registrars)
    job.wait_email = wait_email
    await job.plan(["Check", "Get", "Read"])

    async def steps(job: Job) -> dict:
        await job.enter()
        await job.status(listing_only=True)
        if not job.active():
            job.raise_problems()                         # every registrar stopped: the first stop ends it
            raise Stop("not_listed", f"{words.month_name(period)}'s invoices aren't listed yet",
                       "Fund houses usually list them in the first days of the month.")
        await job.done("Check", " · ".join(job.aside.get(r) or f"{NAMES[r]} lists {len(job.listed[r])}"
                                           for r in job.regs))
        await job.at("Get", "Getting the invoices")
        await job.get()
        await job.done("Get", " · ".join(job.aside.get(r) or f"{NAMES[r]} {len(job.listed[r])}" for r in job.regs))
        await job.read()
        short = f" KFintech's download had no file for {plural(len(job.no_file), 'invoice')} it lists." if job.no_file else ""
        await job.done("Read", f"{plural(len(job.items), 'invoice')} on this PC")
        summary = f"{plural(len(job.items), 'invoice')} for {words.month_name(period)} downloaded.{short}"
        job.host.activity(summary)
        return {"how": "done", "summary": summary, "used": "", "counts": {}, "total": 0, "downloaded": True,
                "notes": job.notes}

    return await _guarded(job, steps, keeps_last_run=True)


async def pickup(host, period: str) -> dict:
    """CAMS's email for a month whose run went on without it (Skip CAMS) or stopped waiting: when it has come, its
    files are taken and read, with no portal and no run. {got: N}, or {} when it hasn't come yet."""
    job = Job(host, period, [CAMS])
    m = job.month
    asked = m.facts.get("asked") or {}
    if not asked or (m.facts.get("fetched") or {}).get(CAMS):
        return {}
    job.listed[CAMS] = list(asked.get("listed") or [])
    pair = await job._month_mail(fetch=True)
    if not pair:
        return {}
    job._take_cams(pair, "CAMS's email for {} came; its invoices are on this PC")
    m.facts.setdefault("fetched", {})[CAMS] = {"at": now(), "listed": job.listed[CAMS]}
    m.facts.pop("asked", None)
    m.save()
    await job.read()
    return {"got": len(job.items)}


async def mailbacks(host) -> dict:
    """Every CAMS mailback in the mailbox that is this ARN's is read in, whoever asked for it (a run, or the person on
    CAMS's own site). A month with no CAMS files on this PC takes it; a month that has some takes it only when it holds
    more invoices than they do; the same or fewer, it is ignored. The mailbox is looked in once.
    {got: [{period, count}]}."""
    look = getattr(host, "mail_pairs", None)
    arn = re.sub(r"\D", "", str(host.profile.get("arn") or ""))
    out: dict = {"got": []}
    if look is None:
        return out
    for zip_file, xls in await look(True):
        try:
            mine = await asyncio.to_thread(cams.added, zip_file, xls)
        except Stop as e:
            log.info("mailback %s skipped: %s", Path(xls).name, e.title)
            continue
        except (Changed, OSError, ValueError) as e:
            log.info("mailback %s skipped: %r", Path(xls).name, e)
            continue
        if mine["arn"] != arn:
            continue
        period, invoices = mine["period"], mine["invoices"]
        try:
            job = Job(host, period, [CAMS])
            m = job.month
            have = _pair(m.folder(CAMS, "fetched"))
            if have:
                try:
                    held = len((await asyncio.to_thread(cams.added, *have))["invoices"])
                except (Stop, Changed, OSError, ValueError):
                    held = 0                                   # what is there can't be read: this one replaces it
                if len(invoices) <= held:
                    continue
            job.listed[CAMS] = sorted(invoices)
            job._take_cams([zip_file, xls], "CAMS's email for {} came; its invoices are on this PC")
            m.facts.setdefault("fetched", {})[CAMS] = {"at": now(), "listed": sorted(invoices)}
            m.facts.pop("asked", None)
            m.save()
            await job.read()
            out["got"].append({"period": period, "count": len(job.items)})
        except Exception as e:                                 # one month's mailback never stops the others
            log.info("mailback %s couldn't be read in: %r", Path(xls).name, e)
    return out


CHECK_AGAIN_S = 10 * 60         # a status read less than this long ago is shown again, not read again
SHOWN_AGAIN_S = 1.2              # ... each line of it staying this long


def _checked_just_now(m: Month) -> bool:
    try:
        return (datetime.now() - datetime.fromisoformat(m.facts.get("checkedAt") or "")).total_seconds() < CHECK_AGAIN_S
    except (ValueError, TypeError):
        return False


async def check(host, period: str, registrars: list[str]) -> dict:
    """What CAMS and KFintech say about the month right now. Returns {news}, or {stop} when it could not be read."""
    job = Job(host, period, registrars)
    await job.plan(["Check"])

    async def steps(job: Job) -> dict:
        if _checked_just_now(job.month):
            # read under ten minutes ago: it looks like a check and the portals are left alone (Neil, 7 Oct)
            for line in [f"Signing in to {NAMES[r]}" for r in job.regs] + [f"Reading what {NAMES[r]} has" for r in job.regs]:
                await job.at("Check", line)
                await asyncio.sleep(SHOWN_AGAIN_S)
            return {"how": "done", "news": job.month.facts.get("checkNews") or job.check_line(), "notes": job.notes}
        await job.enter()
        await job.status()
        if not job.active():
            job.raise_problems()                         # every registrar stopped: the first stop ends it
        for reg, p in job.problems.items():              # one stopped, the other was read: said, not hidden
            job.note(f"{NAMES[reg]} stopped: {p.title}")
        job.month.facts["checkNews"] = job.check_line()
        job.month.save()
        return {"how": "done", "news": job.month.facts["checkNews"], "notes": job.notes}

    got = await _guarded(job, steps, keeps_last_run=True)
    return {"news": got.get("news", ""), "stop": got.get("stop")}


async def _guarded(job: Job, steps, keeps_last_run: bool = False) -> dict:
    """Run these steps, and turn however they end into what the app shows. A stop pressed by the person (the task is
    cancelled) passes straight through."""
    portal_page.tell_hook = job.say                      # the portal modules' words on the running step (`page.tell`)
    try:
        return await steps(job)
    except asyncio.CancelledError:
        if not keeps_last_run:
            job.month.ended("stopped", "You stopped it", code="ended")
        raise
    except (Stop, Refused, Changed, PWError, AssertionError, OSError, ValueError, KeyError, numbering.NumberError) as e:
        log.info("ended on %s", type(e).__name__, exc_info=not isinstance(e, Stop))
        stop = await _why(job, e, _whose(job, e))
        log.info("the stop: %s | %s | %s | said: %s", stop.kind, stop.title, " ".join(stop.lines), stop.said)
        await job.failed()
        if stop.kind not in ("nothing_to_do", "not_listed", "not_submitting", "ended"):
            for reg in job.pages:
                if reg not in job.problems:              # a registrar that stopped while sending already has its page kept
                    await _keep(job, reg, e)
        how = "nothing" if stop.kind == "nothing_to_do" else "stopped"
        if not keeps_last_run:
            job.month.ended(how, stop.title, stop.said, stop.kind)
        out = {"kind": stop.kind, "title": stop.title, "lines": stop.lines, "said": stop.said,
               "registrar": stop.registrar, "so_far": job.so_far(),
               # the other registrar's stop too: each gets its own block at the end (Neil, 8 Oct)
               "others": [{"kind": p.kind, "title": p.title, "lines": p.lines, "said": p.said, "registrar": reg}
                          for reg, p in job.problems.items() if reg != stop.registrar]}
        return {"how": how, "stop": out, "used": job.used_line(), "counts": job.sent, "enter": job.entered,
                "left": job.left, "notes": job.notes}
    finally:
        portal_page.tell_hook = None


async def _why(job: Job, e: Exception, reg: str) -> Stop:
    """The stop for whatever ended a step. A portal that has signed the run out makes every later step fail in some
    way of its own, so that is looked for first: it is the portal's doing, not a page that changed."""
    if not isinstance(e, (Stop, Refused)) and reg in job.pages:
        portal = cams if reg == CAMS else kfin
        try:
            if await portal.dropped(job.pages[reg]):
                return Stop("session_ended", f"{NAMES[reg]} signed this run out",
                            f"{NAMES[reg]} ends a session that sits idle. Run again: it signs in afresh, reads what "
                            f"{NAMES[reg]} has, and carries on with the files already on this PC.", registrar=reg)
        except PWError:
            pass
    stop = _as_stop(e, reg)
    if not isinstance(e, (Stop, Refused)) and reg in job.pages and not stop.said:
        stop.said = await _portal_words(job.pages[reg], reg)
    return stop


async def _portal_words(page, reg: str) -> str:
    """What the portal's toast or snackbar says right now, for the stop's `said`. Never raises."""
    try:
        if reg == CAMS:
            told = await asyncio.wait_for(widgets.toasts(page, cams.C["toast"]), 1)
        else:
            told = await asyncio.wait_for(widgets.toasts(page, kfin.C["snackbar"]), 1)
        return " ".join(told)[:300]
    except Exception:
        return ""


async def _keep(job: Job, reg: str, e: Exception) -> None:
    """Keep the page as it was when the run stopped, for whoever fixes it. Never a sign-in form."""
    page = job.pages[reg]
    try:
        if await (cams if reg == CAMS else kfin).dropped(page):
            return
    except PWError:
        return
    await job.host.failure(page, f"{reg.lower()}-stopped", e)


def _whose(job: Job, e: Exception) -> str:
    if isinstance(e, Refused) and e.who:
        return CAMS if e.who == "CAMS" else KFIN
    running = next((s["line"] for s in job.steps if s["state"] == "running"), "")
    return CAMS if "CAMS" in running else KFIN if "KFintech" in running else ""


def _as_stop(e: Exception, registrar: str = "") -> Stop:
    """Anything that ended a step, as the stop the person reads. The portal's no is quoted; anything else is the
    portal not doing what the steps expect."""
    if isinstance(e, Stop):
        e.registrar = e.registrar or registrar
        return e
    name = NAMES.get(registrar, "the registrar")
    if isinstance(e, Refused):
        return Stop("refused", f"{name} said no", "Nothing was submitted by this step.", said=e.said,
                    registrar=registrar)
    return Stop("ours", f"{name}'s website didn't do what we expected",
                "Run again in a few minutes. If it keeps happening, Send to support.", registrar=registrar)
