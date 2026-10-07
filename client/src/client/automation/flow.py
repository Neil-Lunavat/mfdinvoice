"""The month's job, top to bottom: `run`, and its two shorter forms, `check` (what the registrars have) and `download`
(the month's invoices onto this PC, and nothing more).

    Check        sign in (the captcha first, so the person is needed once and early), the ARN each portal shows, what
                 each registrar already has, what each lists
    Get          the month's files: the ones on this PC when the registrar still lists exactly what they hold, else
                 fetched (CAMS by email, KFintech by download)
    Read         every figure, from the registrars' own files
    Sign         the registrar's invoices signed; the first run for an ARN shows one first, "Does this look right?"
    Your check   the person compares with their bank statement and unticks what does not match. The one yes.
    CAMS         the upload made for what stayed ticked, attached, CAMS's own reading of it compared, CAMS's own
                 validation, Submit, and its status read again
    KFintech     the same on KFintech's page

Rules that hold throughout:

- The ARN each portal shows must be the ARN this run is for, on every run. Anything else ends the run.
- What a registrar already has is never sent again: its status is read first, by this run.
- Nothing is retried by itself. A run that stops says why and ends; the next run starts from the top and uses the files
  already on this PC.
- Submit is written down before it is pressed. If the registrar never answers, the next run's status reading settles
  it, and nothing is pressed twice.
- The person's own invoice numbers are given for good when Submit is pressed, and only then.
- A problem at one registrar does not stop the other.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from playwright.async_api import Error as PWError

from client.automation import cams, files, kfin, numbering, own, signature, words
from client.brand import NAME
from client.automation.month import Month, now
from client.automation.page import Changed, Refused, Stop
from client.automation.words import CAMS, KFIN, NAMES, inr, plural

log = logging.getLogger(__name__)

MAIL_EVERY_S = 15                # CAMS's email takes from a minute to several (asked 17:07, sent 17:09 on 6 Oct)
MAIL_GIVE_UP_S = 10 * 60
ASKED_KEPT_S = 2 * 24 * 60 * 60  # an email asked for longer ago than this is not waited for; CAMS is asked again
IDLE_S = 20 * 60                 # a portal left alone longer than this is signed in to afresh (tested safe, 4 Oct 2026)


class Job:
    def __init__(self, host, period: str, registrars: list[str]):
        self.host, self.period = host, period
        self.arn = host.profile["arn"]
        self.own = host.profile["invoices"]["source"] == "own"
        self.month = Month(host.base, period)
        self.label, self.kf_label = words.labels(period)
        self.regs = [r for r in (CAMS, KFIN) if r in registrars]          # the order things are sent in
        self.pages: dict = {}
        self.aside: dict[str, str] = {}          # registrar -> why it takes no part in this run
        self.unlisted: set[str] = set()          # ... the ones that do not list the month yet
        self.skipped: set[str] = set()           # ... the ones the person left out of this run
        self.locked: dict[str, str] = {}         # own invoices: the numbers already given for good
        self.listed: dict[str, list[str]] = {}   # registrar -> the invoices it lists for the month
        self.no_file: list[str] = []             # listed by KFintech, with no file in its download
        self.items: dict[str, dict] = {}         # every invoice read off the month's files, by key
        self.open: list[str] = []                # the ones this run may send, CAMS's first
        self.blocked: dict[str, str] = {}        # key -> why it cannot be sent by this run
        self.report: list[dict] = []             # CAMS's Excel, every row
        self.report_file: Path | None = None
        self.signed: dict[str, Path] = {}
        self.sent: dict[str, int] = {}
        self.ready: dict[str, int] = {}          # checked by the registrar and not submitted: Submit is switched off
        self.problems: dict[str, Stop] = {}
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

    def active(self) -> list[str]:
        return [r for r in self.regs if r not in self.aside]

    # --- Check --------------------------------------------------------------------------------------------------------

    async def enter(self, step: str = "Check", only: list[str] | None = None) -> None:
        """Sign in to each portal (or use the tab already signed in), and hold each to the ARN law."""
        host = self.host
        for reg in (KFIN, CAMS):                         # KFintech first: its captcha is the one thing asked of the person
            if reg not in (self.regs if only is None else only):
                continue
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
                    raise Stop("ended", "Stopped", "The captcha was closed, so the run stopped. Nothing was "
                                                   "submitted.") from None
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
        self.portals_at = time.monotonic()

    async def again(self, going: list[str]) -> None:
        """The portals were left alone too long to trust their sign-ins (the person took their time at a screen):
        close the browser and sign in to the ones still needed. Nothing has been prepared on a portal yet."""
        log.info("the portals were left alone for %d minutes: signing in afresh",
                 (time.monotonic() - self.portals_at) // 60)
        await self.host.afresh()
        self.pages.clear()
        await self.enter(step=NAMES[going[0]], only=going)

    async def status(self, listing_only: bool = False) -> None:
        """What each registrar already has, and what it lists for the month. `listing_only`: a download, which needs
        only what is listed (CAMS's status is a page of its own, and its slowest)."""
        m = self.month
        for reg in self.regs:
            page = self.pages[reg]
            await self.at("Check", f"Reading what {NAMES[reg]} {'lists' if listing_only else 'already has'}")
            if reg == KFIN:
                reading = await kfin.read_status(page, self.period)
                listed = None if reading is None else sorted(r["key"] for r in reading)
            else:
                reading = None
                if not listing_only:
                    reading = await cams.read_status(page, self.period)
                    await self.host.picture(page, "cams-status")
                listed = await cams.list_month(page, self.period)
            await self.host.picture(page, f"{reg.lower()}-listed")
            if reading is not None:
                m.read_status(reg, [{"key": r["key"], "status": r["status"], "remarks": r["remarks"]}
                                    for r in reading])
            m.facts.setdefault("listedNow", {})[reg] = listed is not None
            if listed is None:
                self._unlisted(reg)
            else:
                self.listed[reg] = listed
        m.save()
        await self.host.changed()

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
            if not (have and have.get("listed") == self.listed[KFIN] and _newest(folder, ".zip")):
                await self.at("Get", "Downloading KFintech's invoices")
                fetched.pop(KFIN, None)
                got = await kfin.fetch(self.pages[KFIN], self.period, m.folder(KFIN, "fetched", empty=True))
                if got is None:
                    self._unlisted(KFIN)
                else:
                    fetched[KFIN] = {"at": now(), "listed": self.listed[KFIN]}
                    self.host.activity(f"Downloaded KFintech's invoices for {self.kf_label}", KFIN)
                m.save()
        if CAMS in self.active():
            have, folder = fetched.get(CAMS), m.folder(CAMS, "fetched")
            if not (have and have.get("listed") == self.listed[CAMS] and _pair(folder)):
                fetched.pop(CAMS, None)
                if await self._cams_get():
                    fetched[CAMS] = {"at": now(), "listed": self.listed[CAMS]}
                    m.facts.pop("asked", None)
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
        waiting = (asked.get("listed") == self.listed[CAMS]
                   and time.time() - datetime.fromisoformat(asked["at"]).timestamp() < ASKED_KEPT_S)
        # an email of CAMS's for this month already in the mailbox does, whichever request it answered: CAMS isn't
        # asked again
        found = None if by_hand or waiting else await self._month_mail(fetch=True)
        if found:
            return self._take_cams(found, "Found CAMS's email for {} in your mailbox")
        if not waiting:
            await self.at("Get", f"Asking CAMS to email {self.label}'s invoices")
            if not await cams.ready_to_ask(page):
                await cams.list_month(page, self.period)
            ref = await cams.request_mailback(page)
            await host.picture(page, "cams-asked")
            asked = m.facts["asked"] = {"ref": ref or asked.get("ref", ""), "at": now(), "listed": self.listed[CAMS]}
            m.save()
            host.activity(f"Asked CAMS to email {self.label}'s invoices" + (f" (ref {ref})" if ref else ""), CAMS)

        dest = m.folder(CAMS, "fetched")
        if by_hand:
            pair = await self._by_hand()
            if pair is None:
                return False
        else:
            await self.at("Get", "Waiting for CAMS's email")
            # Skip CAMS is offered while KFintech is in the same run (a software too old for it isn't asked)
            skip = getattr(host, "skip_wanted", None) if KFIN in self.active() else None
            await (host.waiting_email(asked["at"], asked["ref"], skip=True) if skip
                   else host.waiting_email(asked["at"], asked["ref"]))
            deadline = time.monotonic() + MAIL_GIVE_UP_S
            while True:
                pair = await host.mail_look(asked["ref"]) or await self._month_mail(fetch=False)
                if pair:
                    break
                if skip and skip():
                    # CAMS's request stands (`asked` is kept): its email is read when it comes, and asked for no more
                    self.skipped.add(CAMS)
                    self.aside[CAMS] = "CAMS's email hadn't come; it's read when it does"
                    return False
                if time.monotonic() > deadline:
                    # not here in time: by hand from here (the files from CAMS's email, if it has come elsewhere).
                    # The request stands, so the email is still read when it comes.
                    host.activity(f"CAMS's email hadn't come {MAIL_GIVE_UP_S // 60} minutes after it was asked "
                                  "for: its files were asked for instead", CAMS)
                    pair = await self._by_hand()
                    if pair is None:
                        return False
                    break
                await asyncio.sleep(MAIL_EVERY_S)
        return self._take_cams(pair, "Got CAMS's invoices for {}")

    async def _by_hand(self) -> list[Path] | None:
        """CAMS's two files, chosen by the person; None when they skipped CAMS instead."""
        await self.at("Get", "Choose CAMS's invoice files")
        got = await self.host.files(self.label, skip=KFIN in self.active())
        if got.get("skip"):
            self.skipped.add(CAMS)
            self.aside[CAMS] = "CAMS's files weren't added"
            return None
        return [Path(got["zip"]), Path(got["xls"])]

    def _take_cams(self, pair: list[Path], said: str) -> bool:
        dest = self.month.folder(CAMS, "fetched", empty=True)        # the latest pair only, never two
        for src in pair:
            shutil.copyfile(src, dest / Path(src).name)
        self.host.activity(said.format(self.label), CAMS)
        return True

    async def _month_mail(self, fetch: bool) -> list[Path] | None:
        """The newest of CAMS's emails in the mailbox that is this ARN's month and holds every invoice CAMS lists now,
        whichever request it answered (Neil, 7 Oct). None when there is none, or the software is too old to say."""
        look = getattr(self.host, "mail_pairs", None)
        if look is None:
            return None
        arn = re.sub(r"\D", "", str(self.host.profile.get("arn") or ""))
        for zip_file, xls in await look(fetch):
            try:
                rows = await asyncio.to_thread(cams.read_report, xls, self.period)
            except (Stop, Changed, OSError, ValueError):
                continue                                             # another month's, or not a report we know
            if {re.sub(r"\D", "", str(r.get("BROKER CODE") or "")) for r in rows} != {arn}:
                continue
            if set(self.listed[CAMS]) - {r[cams.CAMS_INVOICE] for r in rows}:
                continue                                             # older than what CAMS lists now
            return [zip_file, xls]
        return None

    # --- Read ---------------------------------------------------------------------------------------------------------

    async def read(self) -> None:
        m = self.month
        self.locked = self.books().locked if self.own else {}
        if CAMS in self.active():
            await self.at("Read", "Reading CAMS's invoices")
            await asyncio.to_thread(self._read_cams)
            # the files are this ARN's month, as emailed by CAMS: an ARN set up without KFintech is bound now
            confirm = getattr(self.host, "confirm_arn", None)
            if confirm:
                ok, said = await confirm()
                if not ok:
                    raise Stop("arn_unbound", "This ARN couldn't be added to your account", "Nothing was submitted. "
                               "CAMS's files for this month are on this PC, so the next run starts from them.",
                               said=said, registrar=CAMS)
        if KFIN in self.active():
            await self.at("Read", "Reading KFintech's invoices")
            await asyncio.to_thread(self._read_kfin)
            # KFintech lists it and its download holds no file for it (seen 7 Oct): said, and the rest go on
            self.no_file = [k for k in self.listed.get(KFIN, []) if k not in self.items]
            if self.no_file:
                self.host.activity(f"KFintech lists {plural(len(self.listed[KFIN]), 'invoice')} for {self.kf_label} "
                                   f"and its download held {len(self.listed[KFIN]) - len(self.no_file)}. "
                                   f"No file for {', '.join(self.no_file)}.", tone="warn")
        self.open = [k for reg in self.regs for k, i in self.items.items()
                     if i["registrar"] == reg and reg in self.active() and k not in m.with_registrar(reg)]
        if self.own:
            self.blocked = {k: why for k in self.open if (why := own.drawable(self.items[k]))}
        m.save()
        await self.host.changed()

    def _read_cams(self) -> None:
        m = self.month
        zip_file, xls = _pair(m.folder(CAMS, "fetched"))
        try:
            self.report = cams.read_report(xls, self.period)
            behind = set(self.listed[CAMS]) - {r[cams.CAMS_INVOICE] for r in self.report}
            if behind:
                raise Stop("wrong_files", "These files are older than what CAMS lists now",
                           f"CAMS lists {plural(len(self.listed[CAMS]), 'invoice')} for {self.label} and these files "
                           f"hold {len(self.report)}. Use the zip and the Excel from CAMS's latest email.",
                           registrar=CAMS)
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
        if self.own:                                  # the number on the person's own invoice, once it has one
            number = self.locked.get(key, "")
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
        out = own.draw(self.host, item, number, self.period, self.month.folder(item["registrar"], "signed"))
        self.signed[key] = out
        self.month.put(item["registrar"], key, file=self.month.rel(out), signedAt=now(), own=True, number=number)
        return out

    def books(self) -> numbering.Books:
        inv = self.host.profile["invoices"]
        return numbering.Books(self.host.base / "books.json", inv.get("last") or "", int(inv.get("at", -1)))

    async def sign(self) -> None:
        host, m = self.host, self.month
        if not host.signature().get("present"):
            raise Stop("setup", "Your signature isn't set up on this PC",
                       "Add it in Settings › Your invoices, then run again. Nothing was submitted.")
        can = [k for k in self.open if k not in self.blocked]
        if self.own and can and not self.books().ready:
            raise Stop("setup", "Your last invoice number is missing",
                       "Add it in Settings › Your invoices, then run again. Nothing was submitted.")
        if can and not host.get("signature_seen"):
            # the first run for this ARN: one real invoice, before the rest are signed
            first = can[0]
            while True:
                await self.at("Sign", "Signing one invoice for you to look at")
                if self.own:
                    number = self.books().hand_out([first])[first]
                    await asyncio.to_thread(self._draw_one, first, number)
                    m.put(self.items[first]["registrar"], first, number="")      # shown, not given
                else:
                    await asyncio.to_thread(self._sign_one, first)
                m.save()
                answer = await host.looks_right(first, self.items[first]["house"])
                if answer.get("looks_right"):
                    host.put("signature_seen", now())
                    break
                if not answer.get("fixed"):
                    raise Stop("ended", "Stopped", "The signature wasn't confirmed, so nothing was signed or "
                                                   "submitted.")
        if not self.own:
            await self.at("Sign", "Signing the invoices")
            for key in can:
                await asyncio.to_thread(self._sign_one, key)
            m.save()
            await host.changed()

    # --- Your check ---------------------------------------------------------------------------------------------------

    async def your_check(self) -> list[str] | None:
        """The person's look at every open invoice. Returns the ones that stayed ticked, or None for "Not now"."""
        host, m = self.host, self.month
        left_out = set(m.facts.get("leftOut") or [])
        can = [k for k in self.open if k not in self.blocked]
        proposed = self.books().hand_out(can) if self.own and can else {}
        books = self.books() if self.own else None
        rows = []
        for key in self.open:
            i = self.items[key]
            said = m.said_about(i["registrar"], key)
            rejected = "REJECT" in str(said.get("status", "")).upper()
            row = {"key": key, "registrar": i["registrar"], "amc": i["house"], "number": proposed.get(key, ""),
                   "taxable": i["taxable"], "gst": round(i["cgst"] + i["sgst"] + i["igst"], 2), "igst": i["igst"] > 0,
                   "included": key not in left_out and key not in self.blocked,
                   "blocked": self.blocked.get(key, ""),
                   "rejection": (said.get("remarks") or said.get("status") or "") if rejected else ""}
            if key in proposed:
                row.update(seq=can.index(key), kept=bool(books.number_of(key)))
            rows.append(row)
        await self.at("Your check", "Your check")
        answer = await host.your_check(rows, [f"{self.aside[r]}." for r in self.regs if r in self.aside])
        if not answer.get("confirmed"):
            return None
        ticked = [k for k in self.open if k in set(answer.get("included") or []) and k not in self.blocked]
        m.facts["leftOut"] = [k for k in self.open if k not in ticked and k not in self.blocked]
        m.save()
        host.activity(f"Checked {plural(len(self.open), 'invoice')}, {len(ticked)} ticked")
        return ticked

    # --- one registrar: prepare, its own check, Submit ----------------------------------------------------------------

    async def send(self, reg: str, ticked: list[str]) -> None:
        host, m, page = self.host, self.month, self.pages[reg]
        name = NAMES[reg]
        sending = [k for k in ticked if self.items[k]["registrar"] == reg]
        numbers: dict[str, str] | None = None
        if self.own:
            await self.at(name, "Making your invoices")
            books = self.books()
            numbers = books.hand_out(sending)
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
            await cams.open_upload(page, self.period, self.own)
            review = await cams.attach(page, out_zip, out_sheet)
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
            ones = [self.items[k]["one"] for k in sending]
            filled = await kfin.fill_grid(page, self.period, ones, self.signed, numbers)
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
            top = books.lock(numbers)
            host.set_last_number(top, books.at)
            self.used += [numbers[k] for k in sending]
            for key in sending:
                m.put(reg, key, number=numbers[key])
        m.save()
        host.activity(f"Pressed Submit for {plural(len(sending), 'invoice')}", reg)
        host.hold_stop(True)                             # Stop waits for the registrar's answer to this one press
        try:
            if reg == CAMS:
                answered, said = await cams.click_submit(page, button)
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
        m.read_status(reg, [{"key": r["key"], "status": r["status"], "remarks": r["remarks"]} for r in reading])
        landed = [k for k in sending if k in m.with_registrar(reg)]
        for key in landed:
            m.put(reg, key, sentAt=now())
        m.save()
        await host.changed()
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
        return numbering.used_line(self.used, self.books().at) if self.used else ""

    def so_far(self) -> str:
        parts = []
        for reg in self.regs:
            if reg in self.sent:
                parts.append(f"{NAMES[reg]}: {self.sent[reg]} submitted")
            elif reg in self.ready:
                parts.append(f"{NAMES[reg]}: {self.ready[reg]} ready, not submitted")
            elif reg in self.problems:
                parts.append(f"{NAMES[reg]}: stopped")
            elif reg in self.aside:
                parts.append(self.aside[reg])
        return " · ".join(parts)


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
    await job.plan(["Check", "Get", "Read", "Sign", "Your check", *[NAMES[r] for r in job.regs]])
    return await _guarded(job, _run)


async def _run(job: Job) -> dict:
    host = job.host
    await job.enter()
    await job.status()
    job.portals_at = time.monotonic()
    job.anything_to_do()
    await job.done("Check", job.check_line())

    await job.at("Get", "Getting the invoices")
    await job.get()
    job.anything_to_do()
    await job.done("Get", " · ".join(f"{NAMES[r]} {len(job.listed[r])}" for r in job.active()))

    await job.read()
    if not job.open:
        raise Stop("nothing_to_do", f"Nothing to do for {words.month_name(job.period)}",
                   "Every invoice the registrars have raised is already submitted.")
    await job.done("Read", job.read_line())

    await job.sign()
    await job.done("Sign", "Made after your check" if job.own else f"{len(job.signed)} signed")

    ticked = await job.your_check()
    if ticked is None:
        job.month.ended("stopped", "You closed Your check", code="not_now")
        return {"how": "closed"}
    await job.done("Your check", f"{len(ticked)} ticked")
    going = [r for r in job.regs if r not in job.aside and any(job.items[k]["registrar"] == r for k in ticked)]
    if going and time.monotonic() - job.portals_at > IDLE_S:
        await job.again(going)
    for reg in job.regs:
        mine = [k for k in ticked if job.items[k]["registrar"] == reg]
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
    return {"how": "done", "summary": summary, "used": job.used_line(), "counts": job.sent, "total": round(total, 2)}


async def download(host, period: str, registrars: list[str]) -> dict:
    """The month's invoices onto this PC, with their figures, and nothing more: nothing is signed or sent."""
    job = Job(host, period, registrars)
    await job.plan(["Check", "Get", "Read"])

    async def steps(job: Job) -> dict:
        await job.enter()
        await job.status(listing_only=True)
        if not job.active():
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
        return {"how": "done", "summary": summary, "used": "", "counts": {}, "total": 0, "downloaded": True}

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


CHECK_AGAIN_S = 10 * 60          # a status read less than this long ago is shown again, not read again
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
            return {"how": "done", "news": job.month.facts.get("checkNews") or job.check_line()}
        await job.enter()
        await job.status()
        job.month.facts["checkNews"] = job.check_line()
        job.month.save()
        return {"how": "done", "news": job.month.facts["checkNews"]}

    got = await _guarded(job, steps, keeps_last_run=True)
    return {"news": got.get("news", ""), "stop": got.get("stop")}


async def _guarded(job: Job, steps, keeps_last_run: bool = False) -> dict:
    """Run these steps, and turn however they end into what the app shows. A stop pressed by the person (the task is
    cancelled) passes straight through."""
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
               "registrar": stop.registrar, "so_far": job.so_far()}
        return {"how": how, "stop": out, "used": job.used_line(), "counts": job.sent}


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
    return _as_stop(e, reg)


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
    """Anything that ended a step, as the stop the person reads. The portal's no is quoted; everything else is ours."""
    if isinstance(e, Stop):
        e.registrar = e.registrar or registrar
        return e
    name = NAMES.get(registrar, "the registrar")
    if isinstance(e, Refused):
        return Stop("refused", f"{name} said no", "Nothing was submitted by this step.", said=e.said,
                    registrar=registrar)
    return Stop("ours", f"Something on {name}'s side isn't what {NAME} expects",
                "This one is ours to fix, and it has been sent to us. Nothing is sent twice: run again once the "
                "software says it is fixed.", registrar=registrar)
