# Everything that is left (5 Oct 2026)

One list for the software, the two servers and the website. `CLAUDE.md` says how we work and where the code is.
Website detail that predates this list is in `website/todo/` (`launch.md`, `design.md`, `after-*.md`).

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

### After Tuesday 6 Oct (Neil's word, 4 Oct night)
- [ ] **Launch again as 1.0.0, tidy:** clean the live databases (the website's and the software's server's), remove
      Neil's own test account and its ARN, empty the release notes back to one first release, then release 1.0.0.
- [ ] **Uninstall from the app.** The installer already makes an uninstaller (Windows Settings › Apps › MFDInvoice ›
      Uninstall); it removes the program and leaves the person's data. Wanted: a button in Settings that starts it,
      and words that say what stays on the PC.
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
- [ ] Delete a run's record 90 days after the run (rows and R2 files). The Privacy page already promises it.
- [ ] Pictures with every run: stop after October, keep them for a run that stopped on our side. Neil has not
      said yes yet.

### The admin panel's Software tab (`website/site/src/pages/control/software.astro`), waiting on Neil's yes/no
- [ ] 1. A run's result as a colour: ended well, stopped on the person's side, ours.
- [ ] 2. A person's message tied to the run it is about.
- [ ] 3. Seen / fixed on "Ours to fix" and "From a person".
- [ ] 4. A Reply button: an email from support@ with the run number in the subject.
- [ ] 5. How long the run took.
- [ ] 6. An account's runs on its own page.
- [ ] 7. Overview: runs today, "Ours to fix" open.
- [ ] The table and the View box were changed blind on 4 Oct (fit the screen, scroll sideways): look at them.

### From a report to a fix
- [ ] `ops/reports.py` lists and unpacks what the app sent. Wanted: one command that pulls every open "ours" and
      "from a person" report into a folder a session can read (log, pictures, page HTML), grouped by stop kind and
      page, so "fix what came in" is one sitting. Reading needs `~/.mfdinvoice/server-admin.key`, so the pull runs
      on the PC. The folder holds real invoices: it is never committed, so the fixing of a real report is done on
      the PC, or from a description of it with the real data taken out.

### The website, page by page (`website/site/`)
- [ ] Read every page as a visitor against the app as it is now: home, pricing, downloads, release notes, setup,
      security, privacy, terms, refunds, FAQ, support, account, checkout, sign-in, blog.
- [ ] Home page: the app drawn there against the real window (seven setup steps, the Tally tab, the month picker).
- [ ] Claims to check: "the app opens only the registrar's invoice mails", "it never sends, moves or deletes
      anything" (FAQ, Security); "Windows 11" (Downloads, FAQ); Zoho Books says "soon" everywhere.
- [ ] `/setup`: pictures of each step; the videos when they exist.
- [ ] More than one ARN: Pricing, Checkout, FAQ and Account read again now that the stepper shows.
- [ ] Logo and favicon; the look (`website/todo/design.md`).
- [ ] The facts sheet for the lawyer: everything the website and the software's server store, and for how long.
- [ ] A place for a signed-in person to send an idea (Neil is thinking about it).
- [ ] `website/todo/launch.md`, `after-meeting.md`, `after-proprietorship.md`, `after-pvt-ltd.md`: read, and fold
      what still stands into this list.

### The app's window (`client/window/`; seen on the made-up backend, shipped as an app update)
- [ ] The words on every screen, read once through (Neil rewrites; take his wording).
- [ ] Tally tab: a GSTIN that differs is only a warning there; make it a question that holds Import, as in setup.
- [ ] Settings › Connections › Tally: show the company's GSTIN beside this ARN's, and let it be changed.
- [ ] Settings: an ARN set up before 4 Oct with CAMS never verified now reads "Needs a change". Check the words.
- [ ] `arn_unbound` is a new stop: add it to `logic/stops.ts` and the dev panel's list if it needs its own words.
- [ ] The dev panel's "Fill setup" knows nothing of the Tally step.
- [ ] Stale words in comments and docstrings ("brain", "contract", "SOFTWARE.md"): clean them in a file when
      touching it.

## C. Not built, in this order
- [ ] **Zoho Books**, before launch. The way to do it: a lab first (Neil makes an organisation on zoho.in and an
      API client on api-console.zoho.in, as a real person would), try everything broadly, write the results, go
      deep on the paths we need, then build. Setup's Tally step is where its connection would sit.
- [ ] **IGST on own invoices**, after launch. Set aside at Your check today.
- [ ] **The USB signing token**: hidden, code kept (`DSC_OFFERED`), `client/packaging/dsc_check.py` tests one.
      Neil has no token now.
- Decided against: updates that download only what changed (87 MB each time; the steps update by themselves).
