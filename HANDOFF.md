# Handoff: 1.0.1 is out (9 Oct)

1.0.1 is released and live (installer cac0c38, SHA-256 f036463f…); the steps 2026.10.09.1400 are published; the
software's server and the website are deployed with it. The partner's real submits on 8–9 Oct worked and two were
approved. Development is back on Neil's PC, in dev mode.

## Read first, in this order

1. `CLAUDE.md`: how we work, and every rule Neil has decided. If code and `CLAUDE.md` disagree, `CLAUDE.md` wins
   unless Neil says otherwise; then change `CLAUDE.md` first. Start with "Reliability is reaching the destination".
2. `TODO.md`: what is left. `website/todo/WEBSITE-TODO.md` for the website; `AFTER-LAUNCH.md` for what waits.
3. Only when a report touches them: the labs reports in `Desktop\Automation-old-data\labs\`, and CAMS's own guide
   `GST_Invoice_Upload_Process_Flow.pdf` at the repo's root (Neil's download, not committed). Facts about the portals
   come from these, from Neil, or from the live page; never guesses.

Do not read old chat transcripts.

## What 9 Oct changed (all in `CLAUDE.md`)

- The philosophy: nothing that can go on stops. Unknown status words are shown and carried on with; one registrar
  never stops the other; missing invoices leave the rest going; problems are listed at the end ("Along the way");
  portals that don't respond are retried once, with a countdown on screen. No stop says "ours to fix".
- Overview's Run is never replaced. Rejections: Send again (to Run) and the registrar's words.
- Every CAMS mailback is read in, whoever asked, within the last 3 days.
- Forwarding: no code of ours; Gmail's confirmation (or the first forwarded CAMS mail) proves the Gmail; setup shows
  it as a carousel of Neil's screenshots (`client/window/public/forward/`).
- Setup saved as it goes; real previews only (DSC mark unsigned); uninstall can delete all data (DELETE ALL).
- Second addresses on workers.dev (`site.` / `software.develop-tbc.workers.dev`) for ISP blocks. Run needs the website
  and the server (either address); no steps run without the server.
- Dev mode: `uv run app` starts at `hands/devstart.py`: no website (test@mfdinvoice.co.in / 000000), data in
  `%LOCALAPPDATA%\MFDInvoice-dev\`, the dev panel (Submit, show browser, back to setup, Fill everything, saved
  states). `client/config.toml` `[dev]` holds the test account. None of it is in the exe: `app.spec` leaves the three
  dev modules out, `shell.py` names none of them, `packaging/build.py` fails a build that packs any.

## How to work in this chat

- Neil reports with a screenshot and what he pressed. Dev mode's log: `%LOCALAPPDATA%\MFDInvoice-dev\workspace\logs\
  app.log`; an installed PC's run: control › Software, or `uv run --project client python ops/reports.py pull`.
- Small, obvious fixes: do them, check them, say what was checked. Behaviour changes: numbered items with "Lean:" and
  one reason; he answers by number. Write each decision into `CLAUDE.md` the moment he makes it. Take his wording.
- Multi-file pieces go to Sonnet workers with exact briefs; review their diffs before committing. Commit each
  finished piece, staged by name, when Neil says so.
- Ships: the steps (`ops/automation.py publish`, then `cd server && bun run deploy`), no update. Anything else under
  `client/` is a release: version bump, `uv lock`, commit, `uv run python packaging/build.py` in `client/` (it builds
  from git HEAD), `bash ops/release-<v>.sh` (notes in Neil's words, nothing that says how the software works under
  the hood), then `bun run check && bun run deploy` in `website/site`.
- Checks before handing back: `cd client && uv run python -m compileall -q src`, import the touched modules,
  `cd client/window && bunx svelte-check --threshold warning`, `bun run build`; the website's `bun run check`. No
  screenshots of screens for my own checks.
- Reading the live databases is Neil's: hand him the `bunx wrangler d1 execute … --remote` command. Deploys, uploads
  and anything outside the code go to him as one `!` command (bash syntax, full paths).

## Notes outside the repo

`Desktop\Automation-notes\`: `domain-warmup.md` (sign-in codes landing in Spam) and `isp-unblock.md` (Jio's MySafeNet
and Airtel), each for a separate Claude chat Neil runs.
