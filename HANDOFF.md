# Handoff: 1.0.0 is out (8 Oct)

1.0.0 is released and live; the steps 2026.10.08.1056 are published. Both live databases were emptied after it, and
Neil's PC was wiped (no software data, the old 1.0.3 uninstalled). Next: the fresh-slate day on the partner's PC.
Nothing new unless Neil asks.

## Read first, in this order

1. `CLAUDE.md`: how we work, and every rule Neil has decided. If code and `CLAUDE.md` disagree, `CLAUDE.md` wins
   unless Neil says otherwise; then change `CLAUDE.md` first.
2. `TODO.md`: what is left before and around launch, with the plan for the real Submit. `website/todo/WEBSITE-TODO.md`
   for the website; `AFTER-LAUNCH.md` for what waits.
3. Only when a report touches them: `portals-report.md`, `portals-results.md`, `tally-results.md`,
   `zoho-results.md`, in `Desktop\Automation-old-data\labs\`. Facts about the portals come from these, from Neil, or
   from the live page; never guesses.

Do not read old chat transcripts.

## Where things stand

- `main` holds everything; the release commit is dc8fbcf (1.0.0, built from 35b6578).
- Decided and built on 8 Oct, in `CLAUDE.md`: one PC per account; forwarding through a chain of mailboxes (Gmail
  only); Gmail's forwarding confirmation is a link now (Confirm in Gmail); Don't wait for CAMS's email in every run;
  CAMS's last request is reused while CAMS lists the same invoices; an unconfirmed Submit is sent again.
- Proven live 8 Oct: forwarding end to end (CAMS → pritamutha@ → neillunavat3192@ → us → September read in).
- Never run live: a real Submit (the partner's PC, own invoices, his DSC; the plan is in `TODO.md`), the installed
  build fetching the steps, one PC per account on two PCs, Update now (first test: 1.0.1), Zoho Books, the Gmail app
  password route, a second ARN, a CAMS-only ARN, sign out.
- The first time a portal answers a repeated Submit with "already have it", its words come through support and go
  into the steps.

## How to work in this chat

- Neil reports with a screenshot and what he pressed. Read `%LOCALAPPDATA%\MFDInvoice\workspace\logs\app.log` and the
  run's `workspace\runs\<id>\log.txt`; on another PC, the run's record in control › Software
  (`uv run --project client python ops/reports.py pull`). Reading is allowed, writing never.
- Small, obvious fixes: do them, check them, say what was checked. Behaviour changes: numbered items with "Lean:" and
  one reason; he answers by number. Write each decision into `CLAUDE.md` the moment he makes it. Take his wording.
- Multi-file pieces go to Sonnet workers with exact briefs; review their diffs before committing. Commit each
  finished piece, staged by name.
- Fixes to the portal work ship as steps (`ops/automation.py publish`, then `cd server && bun run deploy`): no update.
  Anything under `client/` outside the steps is a release (`CLAUDE.md`, "Where each change ships from").
- Checks before handing back: `cd client && uv run python -m compileall -q src`, import the touched modules,
  `cd client/window && bunx svelte-check --threshold warning`, `bun run build`; the website's `bun run check`. No
  screenshots (Neil, 8 Oct).
- The `!` shell starts outside the repo: give full paths, and bash syntax (not PowerShell).
- Live databases: read with `bunx wrangler d1 execute <db> --remote` from `server/` (software-db) or `website/site/`
  (site-db); writes go to Neil as one command. `bunx wrangler tail software --format json` shows the server live.
