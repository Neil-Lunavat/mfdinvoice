# Handoff: Neil's full pass (from the 8 Oct session)

This chat helps Neil do one full pass of the software by hand and fixes what he reports. Nothing else: no new
features, no redesigns, unless he asks.

## Read first, in this order

1. `CLAUDE.md`: how we work, and every rule Neil has decided (setup, the run, invoice numbers, the ARN law). It is the
   single source of decisions. If code and `CLAUDE.md` disagree, `CLAUDE.md` wins, unless Neil says otherwise; then
   change `CLAUDE.md` first.
2. `TODO.md`: section 3 is the pass checklist; "In Neil's hands" and "Launch" come after.
3. Only when a report touches them: `labs/portals-report.md` (what CAMS and KFintech really do), `labs/tally-results.md`
   (the e40/e41 numbering lab at the end), `labs/zoho-results.md`. Facts about the portals come from these or from
   Neil, never from guesses.

Do not read old chat transcripts.

## Where things stand

- Commits on `main` from 8 Oct, newest first: `c5b0e93` audit gaps, `b5f8fa5` setup reads the ARN, `7373649` the
  review's fixes, `92fa18d` Zoho + Books tab, `5f10103` Name and GSTIN step, `0cc3006` invoice numbers (books first),
  `ab0d664` portal lab in the software, `8a9bdd9` the 7 Oct work. The tree was clean at handoff.
- Live: the website (mfdinvoice.co.in) and the software's server (software.mfdinvoice.co.in), workers.dev off. The
  website's newest `/setup` page may still need Neil's deploy. The steps (`client/src/client/automation/`) are not
  published: `uv run app` runs them from the folder.
- Neil's app data was wiped on 8 Oct: the pass starts at sign-in, then setup.
- Checked by the workers and me: compile, the window's type-check, Tally on MFD Test (LAB40 voucher types), Zoho on
  the MFD Test organisation, setup screens on the made-up backend. **Never run in the real software:** every new
  screen, everything after Read in a run, and both portals' new code (sign-in, Submit's answer, sessions).

## What was built on 8 Oct (all unseen by Neil)

- **Setup**, 8 steps: CAMS → KFintech → Your ARN, name and GSTIN → Signature → Books → Your invoices → Mailbox →
  Check everything. ARN read from the logins, never typed; a consent tick on each registrar's step.
- **Invoice numbers, books first** (Tally and Zoho): the books give the number before the PDF is drawn; the red line
  and Refresh while Tally is shut; Tally's questions inside the run; "Date it today" / "Put it aside" for Tally set to
  renumber; without books, the last number can't go below the highest used.
- **Zoho Books**: connect through the browser's Accept page (India only), keys in `~/.mfdinvoice/zoho.json`; the
  Books tab serves Tally and Zoho.
- **Portal lab in the software**: status words (exact, unknown stops, most final row wins, both show "Approved");
  CAMS one browser with sign-in again on expiry, only ticked rows, validation, Submit's Success table, the survey;
  KFintech sign-in by the server's reply, greyed rows, tab clicks, missing files fetched next run.
- **Each registrar stops on its own**: one's stop sets it aside, the other carries on.

Watch in the pass (most likely to need fixes): the end screen when one registrar stopped and the other finished; a
second KFintech captcha just before its Submit after 20 idle minutes; CAMS's Success table matching invoices; Zoho's
real browser connect; the setup screens' words (Neil rewrites copy).

## How to work in this chat

- Neil reports with a screenshot and what he pressed. Read `workspace\logs\app.log` and the run's
  `workspace\runs\<id>\log.txt` under `%LOCALAPPDATA%\MFDInvoice\` (reading is allowed; never write there).
- Small, obvious fixes: do them, check them, say what was checked. Anything that changes behaviour: one numbered item
  with a lean, he answers. **Write each decision into `CLAUDE.md` the moment he makes it.**
- Master and workers (`CLAUDE.md`): brief Sonnet workers for multi-file fixes, review their diffs, commit finished
  pieces (he wants each one committed; stage by name). Before briefing, check the brief against `CLAUDE.md`; a worker
  told to "keep" a rule keeps it even when it's wrong.
- Workers that change a screen screenshot it on the made-up backend (`bun run dev` in `client/window`) and describe
  it. Say plainly what was and wasn't seen.
- Don't treat code as a fact about the outside world (a function returning a set is not proof a portal shows
  several ARNs). Unsure what a portal, Tally or Zoho shows: say so, ask Neil, or check the lab files.
- Deletions outside the code, deploys, live database writes, and the app's data: hand Neil one `!` command.

## Main files for the pass

| Area | Files |
|---|---|
| The run | `client/src/client/automation/flow.py` (top to bottom), `month.py`, `words.py` |
| Portals | `automation/cams.py`, `kfin.py`, `cams_selectors.toml`, `kfin_selectors.toml` |
| Books and numbers | `automation/books.py` (the seam), `tally.py`, `zoho.py`, `numbering.py`, `own.py`; app side `hands/zoho.py` |
| Window's Python side | `client/src/client/hands/window.py`, `host.py`, `shell.py` (`uv run app`, `--show-browser`) |
| Window | `client/window/src/`: `bridge/types.ts` (the boundary), `screens/setup/`, `screens/run/`, `screens/Books.svelte`, `screens/Settings.svelte`, `logic/details.ts` (setup steps) |
| Website | `website/site/src/pages/setup.astro`, `privacy.astro`, `security.astro` |

Checks before handing anything back: `cd client && uv run python -m compileall -q src`, import the touched modules,
`cd client/window && bunx svelte-check --threshold warning`; website: `cd website/site && bun run check`.

## Open, not for this pass unless Neil raises it

- The CA question (TODO "In Neil's hands"): a registrar invoice's voucher number in Tally (today Tally's own; Zoho
  stores the registrar's).
- Cloudflare Email Routing for CAMS forwarding; a Zoho login for MFDInvoice to own the API client.
- Before March: a run whose invoices span two financial years.
- After the pass: publish the steps, version bump, build, release 1.0.0 (TODO "Launch").
