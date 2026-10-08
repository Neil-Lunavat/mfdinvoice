# Handoff: after Neil's pass of 8 Oct

The pass is done: setup, runs up to just before Submit, Tally numbering into MFD Real, downloads of every month. This
chat picks up what is left. Nothing new unless Neil asks.

## Read first, in this order

1. `CLAUDE.md`: how we work, and every rule Neil has decided. Many were added on 8 Oct (setup's two-try portal message,
   the network toast, Add CAMS's files, Check mail, the run's file box, Your check, several-month downloads, KFintech's
   flaky table, the last invoice number, Tally's missing ledgers). If code and `CLAUDE.md` disagree, `CLAUDE.md` wins
   unless Neil says otherwise; then change `CLAUDE.md` first.
2. `TODO.md`: section 3 ends with **"Pass of 8 Oct: done"** and the list of what Neil has still never run. "In Neil's
   hands" has the two questions for a CA.
3. Only when a report touches them: `portals-report.md`, `portals-results.md`, `tally-results.md`,
   `zoho-results.md`, in `Desktop\Automation-old-data\labs\`. Facts about the portals come from these, from Neil, or from the live page; never guesses.

Do not read old chat transcripts.

## Where things stand

- `main` is clean at `c1d631a`. The 8 Oct commits, oldest first: 77d62ff … 80f077f (setup fixes, network toast,
  KFintech's firewall, CAMS's swallowed clicks, the preview race), 387f3a1 (Tally makes missing ledgers), 6c83e13
  (layouts), 865e3e1 (Add CAMS's files), 26b82d9 (the run's file box, Your check), 99b97fa (CAMS signs in again on a
  kept tab), 0cab72f + 1c5f43b (a KFintech retry that hung live, taken back out), 5f76f19 (several-month email wait,
  `pickup` exposed, KFintech's two invoices under one reference), e668d09 (last invoice number, 3-character rule, Check
  mail), 66413b7 (KFintech's retry, page-based), c1d631a (KFintech's own figure for the two-invoice case, CA note).
- Nothing is published. The steps (`client/src/client/automation/`) run from the folder under `uv run app`; users get
  them only after `ops/automation.py publish` + `cd server && bun run deploy`. Window and `hands/` changes need a
  software release (`CLAUDE.md`, "Where each change ships from").
- Neil's PC: `client/config.toml` has no `[dev] submit = true`, so runs stop just before Submit. Mailbox is by hand
  ("folder"), so Check mail and the several-month email wait are not visible to him. Tally company "MFD Real" holds
  test vouchers 1–9 from the pass (Sales type, Automatic, bare from 1); Neil cancels them and sets the numbering.
- Neil runs it as `cd client && uv run app --show-browser` (a bare `uv run app` from the repo root fails: no `app`).
  Never leave the shell's cwd changed.

## Learnt on 8 Oct (keep these)

- **KFintech is flaky.** Its table can come up "No invoice details" for a month it lists, and stay so; its API
  (`dssapi/GetGeneric`) is used for many things on a page and some calls fail while others succeed, so **never wait on
  its network answers**: read what the page shows. Bad site data in the browser profile once got "Request Rejected"
  from its F5 firewall; a fresh sign-in now clears KFintech's site data (`kfin._forget`).
- **KFintech refuses invoice numbers under 3 characters** (its page script). Now part of `numbering.rule_46`.
- **KFintech can raise two invoices for one payment** under one reference (Bank of India, June 2026). Read as one, with
  KFintech's own figures; the second kept in `parts`. CA question in TODO.
- **CAMS** allows one session: Neil signing in by hand ends ours; the run signs in again once (`cams._signed`). Its
  Angular pages swallow clicks made while data loads: `page.quiet` before acting, then check what was clicked held.
- **CAMS's mailback Excel** gives the month (PAYMENT MONTH YEAR) and ARN (BROKER CODE); zip and Excel pair by the
  request number in their names (`hands/inbox.py`, `cams.added`).
- Tally's voucher type numbering tags as TallyPrime 7.1 sends them: PREFIXLIST.LIST, SUFFIXLIST.LIST, BEGINNINGNUMBER,
  PREFILLZERO, WIDTHOFNUMBER, PERIODBEGINNIGNUM (`tally._bare_start`).
- Anything a window method returns must be async (shell.py's bridge runs every method as a coroutine).

## Open, ask Neil before doing

- A real Submit on each portal (needs `[dev] submit = true`; real, his partner's ARN): reading the answers after
  Submit has never run live. The biggest gap.
- Everything else on TODO's "still never run" list; each needs Neil in the real software.
- The CA's two answers (registrar invoice voucher numbers in Tally; KFintech's two-invoice payments).
- Then: publish the steps, version bump, build, release 1.0.0 (TODO "Launch").

## How to work in this chat

- Neil reports with a screenshot and what he pressed. Read `%LOCALAPPDATA%\MFDInvoice\workspace\logs\app.log` and the
  run's `workspace\runs\<id>\log.txt` (+ `what-happened.txt`, saved pages `*.html`); reading is allowed, writing never.
  The app can stay open while you read.
- Small, obvious fixes: do them, check them, say what was checked. Behaviour changes: numbered items with "Lean:" and
  one reason; he answers by number. **Write each decision into `CLAUDE.md` the moment he makes it.** Take his wording.
- Multi-file pieces go to Sonnet workers with exact briefs; review their diffs and screenshots before committing. He
  wants each finished piece committed, staged by name.
- Before trusting a new wait or retry on a portal, say it is untested live; he tests it. When something new hangs on
  the live page, go back to the code that worked first (he asked for that), then design the fix.
- Checks before handing back: `cd client && uv run python -m compileall -q src`, import the touched modules,
  `cd client/window && bunx svelte-check --threshold warning`, `bun run build`. No screenshots (Neil, 8 Oct).
