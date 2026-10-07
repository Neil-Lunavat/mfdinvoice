# Everything that is left (7 Oct 2026)

One list for the software, the two servers and the website. `CLAUDE.md` says how we work and where the code is.
The website's own list is `website/todo/WEBSITE-TODO.md`; ideas parked for later are in `IDEAS.md`.

**Where each kind of change ships from.** Only Neil's PC holds the keys, so every one of these happens there:

| A change to | Ships by |
|---|---|
| `client/src/client/automation/` (the steps) | `uv run --project client python ops/automation.py publish`, then `cd server && bun run deploy`. No app update |
| anything else under `client/` (the app, the window) | raise `version` in `client/pyproject.toml`, `uv lock`, commit, `uv run python packaging/build.py` in `client/`, `ops/release.py "<one sentence>"`, deploy the website |
| `server/` | `cd server && bun run deploy` |
| `website/site/` | `cd website/site && bun run deploy` (`bun run check` first: 51 checks on a local database) |

A cloud session can read and change all the code, run `bun run check`, the window's `bunx svelte-check`, and look at
the window on the made-up backend (`bun run dev` in `client/window`, then screenshots with a headless browser). It
cannot deploy, publish, build the installer, run the real app, or reach CAMS, KFintech, Gmail or Tally. It pushes a
branch; Neil pulls, and the shipping is done on his PC.

## A. Only on Neil's PC

### To look at in 1.0.3 (built 4 Oct, none of it seen by Neil yet)
- [ ] Sign-in: "New here? Sign up" opens the website; an email with no account is refused, with the sign-up link.
      The live website does refuse (`/api/app/code` → `404 no_account`, asked from the checkout on 4 Oct).
- [ ] Setup, CAMS step: Continue stays off until CAMS shows the ARN; "I don't use CAMS" is the other way through.
- [ ] Setup, Tally step (6 of 7): Tally shut, no company open, one company, two companies, a GSTIN that differs
      (needs the tick), "Don't connect Tally now". The company chosen is the one the Tally tab opens on.
- [ ] Setup, the invoice preview: the blue corner button and a click on the image both open it full screen.
- [ ] Tally tab: the page scrolls as one; the sales-ledger card with "Same for all…"; the tick before Import; the
      "TallyPrime isn't answering" text centred; both window sizes.
- [ ] "Import into Tally" (end of a run, and a month in Invoices) left Neil on Invoices once. Not reproduced; the
      code opens the Tally tab. Try again and say which button.
- [ ] After a publish of the steps: a Check status shows a newer steps version in the Software panel with the
      app's version unchanged (steps without an app update).

### Never run against a signed-in portal (October's invoices are the first chance)
- [ ] Everything in a run after Read: Sign, Your check, prepare, the registrar's own check, Submit, status again.
- [ ] Never seen by anyone: CAMS's final Submit and what it says after; KFintech's number and date boxes on own
      invoices; what CAMS shows for a row left out of an upload; where a rejection's words appear; whether
      KFintech's header shows the ARN on every page.
- [ ] CAMS's email through the Gmail mailbox; Skip CAMS; "not listed yet"; "I don't use CAMS"; the ARN mismatch
      screen; the 20-minute sign-in rule (a second check inside 20 minutes asks no captcha; after it, `app.log` says
      "last used N minutes ago: closed").
- [ ] An ARN set up without KFintech: setup binds nothing; the first run binds it after CAMS's files are read
      (the trial starts then); a refused bind stops the run as `arn_unbound`. Needs a second ARN or account.
- [ ] More than one ARN on one account, with a second distributor through the partner.

### Tally, on MFD Test (never the partner's real books)
- [ ] Import a month, import again (nothing to import), Look again, Forget in Settings › Connections › Tally.
- [ ] The Excel export's two new columns; Tally's last number beside yours before a run on own invoices.
- [ ] Tally moved to another port (9001): the tab finds it (`tally.py` `_listening`). Checked by script only.
- [ ] Not tried: a restricted (data-entry) Tally user; Tally run as administrator.
- [ ] `TALLY-FOR-CA.md` (19 decisions) goes to the partner's CA. The answers may change `tally.py`.

### The plan for the ten distributors (to write, then run)
- [ ] First on Neil's own ARN: one guess written down per unknown page above, the smallest run that answers it,
      Submit off (`client/config.toml` `[dev] submit`) until the guess holds. A rerun is safe: status is read fresh.
- [ ] Then the ten: what each is given, what is read from `control.mfdinvoice.co.in/software` after each run, how
      a report becomes a fix (see B, "From a report to a fix"), and when the one update ships.

### Built 7 Oct, for the next build (none of it seen by Neil yet)
Checked by me: the window's type-check, the Python imports, and pictures of the month picker, the Tally tab, Settings ›
This PC and the trial-used screen on the made-up backend. Nothing here has run in the real software.
- [ ] Month picker: April 2026 to this month, month names only. "App" is "software" in every word a person reads.
- [ ] Sign up opens `/signin?from=app`. "Free trial used" screen, and a refused bind says it (`trial_used`). **Neil
      rewrites the words once he sees them.**
- [ ] Settings › This PC › Uninstall: starts Windows' uninstaller and closes; the data stays.
- [ ] Tally tab: a GSTIN that differs is a question that holds Import ("This is the right company"), remembered for
      that company's GSTIN; setup's tick is remembered too. Settings › Tally shows the company's GSTIN beside yours,
      and Change (it forgets the company; the Tally tab asks again). "Look again" is "Refresh" there.
- [ ] `arn_unbound` has its own lines; the website's words show as the quote. Fill setup fills the Tally step.
- [ ] The USB token (DSC) is offered at setup's signature step (Neil, 7 Oct: the proof of concept signed).
- [ ] The new logo: the window's mark; the .exe and installer icon (`client/packaging/icon.ico`).
- [ ] `brand.json` points at `https://mfdinvoice.co.in` and `https://software.mfdinvoice.co.in`. **Deploy both servers
      on their new names before building**, and keep the workers.dev addresses answering for copies already out.
- [ ] Tally: the voucher type is Sales when it is the only sales type, asked once when there are more (no more
      guessing from the last voucher entered). MFD Test still remembers the lab's type: Settings › Tally › Change.
- [ ] CAMS's email: any email of CAMS's in the mailbox for this ARN and month will do, whichever request it answered
      (checked by the Excel's month, BROKER CODE and listing); a Download looks there before asking CAMS. Checked on
      two saved real mailbacks only.
- [ ] Settings › Send an idea (the last tab): the words and a picture they choose, to the software's server as an idea.
- [ ] Surveys: the panel's Survey tab has Website | Software; Software lists surveys as cards, writes one (questions
      one by one: one choice, several, short answer, "Other"), sends it live, closes it, shows the results with each
      email. The software shows the live one on Overview as a toast (X: never again for that survey), asks one
      question at a time, then the heart and "We read every answer ourselves. Every bit of feedback counts!" (Neil
      may reword). Website checks: 54 of 54, one for the survey end to end.

### Built 7 Oct, second round (type-checked; nothing run for real)
- [ ] Skip CAMS while its email is awaited; Overview's Run then says "Run CAMS" (Run both, Run KFintech only in its
      menu). A late CAMS email is read in by itself (a look every 90 s while the software is open; no portal, no run).
- [ ] Downloads tab: pick any months (April 2026 on) and download them in one go; Download left Overview's menu.
- [ ] Tally: an own invoice already in Tally (typed by hand) takes Tally's number as its own, for good.
- [ ] CAMS's email, three ways: forwarded to us (setup: a code to the CAMS email, then Gmail's forwarding code shown,
      then the filter), Gmail app password, by hand. Forwarding or Gmail failing, or 10 minutes without the email,
      falls back to by hand. **Neil, in Cloudflare:** Email Routing on the subdomain `mailback.mfdinvoice.co.in`
      (check it changes no record of the apex, where Hostinger's MX is), then the address
      `cams@mailback.mfdinvoice.co.in` → Send to a Worker → `software`.
- [x] Deployed 7 Oct: the software's server (software.mfdinvoice.co.in, forwarding, the 90-day delete, /admin/stats)
      and the website (mfdinvoice.co.in, control., write.; migrations 0012, 0013). workers.dev still answers.
- [ ] The steps (`automation/`) are not published: `uv run app` uses them from the folder. Publish after Neil's pass.

### To talk through before building (Neil, 7 Oct)
- [ ] **Setup without typing the ARN:** read the ARN (and the name and GSTIN, if the portals show them) from CAMS's
      and KFintech's sign-ins. CAMS's ARN and KFintech's must still be the same.
      Neil, 7 Oct night: setup goes CAMS → KFintech → a "name and GSTIN" step → the rest. KFintech verified: that
      step shows the name (Distributor Profile) and GSTIN (View Uploaded, filled once a month is picked) and asks "Is
      this correct?", editable. KFintech skipped: the person types both. (CAMS shows the name, never the GSTIN.)
- [ ] **Own invoice numbers for months already submitted, and Tally:** a past month downloaded today got fresh numbers
      (May in one format, September in another). The voucher type picked was the lab's ("labs RID").
- [ ] **CAMS's email that arrives after the run stopped** comes in without another run (a look every few minutes while
      the software is open). Agreed; its design waits on the three ways below. And a "Skip CAMS" while waiting for
      the email (today only the files screen has it; the wait itself only has Stop).
- [ ] **Download separate from Run, for several months at once.** Run stays one month. Download takes a pick of
      months and fetches them all in one go. A Run of a month not yet downloaded still downloads it; one already
      downloaded is not fetched again (already so). Lab: does CAMS take mailback requests back to back?
- [ ] **CAMS's email, three ways, in this order:** (1) the person's Gmail forwards CAMS's mailbacks to one address of
      ours (Cloudflare Email Routing to a Worker, the mail kept encrypted for their PC only, deleted once fetched);
      (2) Gmail with an app password (today's); (3) by hand (today's). Each mailback names the CAMS email it was asked
      from and its request number, so one address can serve everyone. DKIM passes for camsonline.com (Neil, 7 Oct).
      support@ is Hostinger's mailbox (the apex MX), so this address must not take over the apex: a subdomain or the
      spare domain. CAMS itself takes minutes to send (asked 17:07, sent 17:09, in Gmail 17:10 on 6 Oct).
- [ ] **Zoho Books:** `LAB-ZOHO.md` is the brief. **The portals' last lab:** `LAB-PORTALS.md`.

### Pre-launch testing (before the 1.0.0 below)
- [ ] Everything under "To look at in 1.0.3" and "Built 7 Oct" above, in the real software.
- [ ] One last lab on October's real invoices (KFintech lists 3, CAMS 3 on 7 Oct): the screens never seen, with Submit
      off until each guess holds. Then the run after Read against signed-in portals.

### After Tuesday 6 Oct (Neil's word, 4 Oct night)
- [ ] **Launch again as 1.0.0, tidy:** clean the live databases (the website's and the software's server's), remove
      Neil's own test account and its ARN, empty the release notes back to one first release, then release 1.0.0.
- [ ] Left untested on purpose: the ARN set up without KFintech (bound by its first run). Fix it if support hears
      of it.
- [ ] The ten-distributor plan, written as numbered items with a lean, after Neil's own ARN has gone through October.

### Owed by people
- [ ] The partner: business address, the city whose courts hear a dispute, GSTIN, SAC code, the grievance
      officer's name and email (`BUSINESS` in `website/site/src/consts.ts`; each shows greyed until filled).
- [ ] The lawyer reads Terms, Privacy and Refunds; then the "A draft" line goes (`components/Legal.astro`).
- [ ] The how-to videos. Setup's "How to · 1 min" buttons open `/setup` today.
- [ ] A code-signing certificate for the installer, or keep "Windows protected your PC" (More info, Run anyway).
- [ ] Neil's old app data is in `Desktop\Automation-old-data\appdata-backup-2026-10-04\`. Keep or delete.
- [ ] Delete the empty "Tally import: decisions to check with a CA" doc under the other Claude account.
- [ ] The stopped Google Cloud project: delete it, or keep `ops/stop-cloud.sh`.

## B. Can be done in a cloud session (then shipped from the PC)

### The software's server (`server/`)
- [ ] Deploy it: the 90-day delete (built, a daily cron), `/admin/stats`, and its new name `software.mfdinvoice.co.in`.
- Pictures go with every run, for good (Neil, 7 Oct).

### From a report to a fix
- `uv run --project client python ops/reports.py pull` puts every open "ours" and "from a person" report, with its log
  and record, into `~/.mfdinvoice/reports/pull-<when>/`, grouped by its words, with an INDEX.md (tried on the live
  server, 7 Oct: 2 open). It holds real invoices: never in the repo.

### The app's window (`client/window/`; seen on the made-up backend, shipped as an app update)
- [ ] A place to send an idea, inside the software (ideas come while using it). Neil designs it with us.
- [ ] The month picker gets a year once there is a second financial year.
- [ ] The words on every screen, read once through (Neil rewrites; take his wording).
- [ ] Settings: an ARN set up before 4 Oct with CAMS never verified now reads "Needs a change". Neil reads the words.
- [ ] Stale words in comments and docstrings ("brain", "contract", "SOFTWARE.md"): clean them in a file when
      touching it.

## C. Not built, in this order
- [ ] **Zoho Books**, before launch. The way to do it: a lab first (Neil makes an organisation on zoho.in and an
      API client on api-console.zoho.in, as a real person would), try everything broadly, write the results, go
      deep on the paths we need, then build. Setup's Tally step is where its connection would sit.
- [ ] **IGST on own invoices**, after launch. Set aside at Your check today.
- Decided against: updates that download only what changed (87 MB each time; the steps update by themselves).
