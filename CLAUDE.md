# MFDInvoice: how Neil and I work on it

Written on 4 Oct 2026 by the session that took the cloud server out, so the next one starts where it stopped. Neil
edits this; where it and he disagree, he wins.

## How we work

- **Neil decides everything.** I read the code and tell him what a thing does, why it is there, whether the job needs
  it, and my lean with the reason. He answers. Nothing is trashed, kept or changed in behaviour on my own say.
- **Decisions come as numbered items**, grouped by screen or step: what is there today, then "Lean:" and one reason.
  He answers by number. Short and plain; he wants an informed decision with little to hold in his head.
- **Priorities, in order:** it is reliable; it works or it says why; the UX feels good. After those: low cost, speed.
  Secrecy is not a priority. Simple and working beats clever. What serves neither function nor form goes.
- **Old reasons are not trusted.** Comments and docstrings were written for an architecture that is gone; many still
  say "brain", "contract", "SOFTWARE.md". Read what the code does, question every inherited rule, and clean the stale
  words in a file when touching it.
- **Neil is the tester, by hand, in the real app, with real credentials.** No test suites (they were deleted on his
  word) and nothing faked for him unless he says "fake". I check my own work before handing it over (type-check,
  build, a script that drives it, looking at the image it drew) and say exactly what was checked and what was not.
- **One working piece at a time:** build it, he runs it, he reports with screenshots, I fix, then the next piece.
- **He is blunt and fast.** Match the pace: no hedging, no padding, no obvious questions. When I am unsure of
  something he knows (what a portal shows), I say so and he shows me.
- **Words in the window matter to him.** "Verify", not "Test". No deadlines or reminders: that is the person's job.
  Make them feel they own it. He rewrites copy; take his wording.
- **Commit only when asked; stage files by name.** The rewrite went in on 4 Oct (`808c6a8`), and he wants each
  finished piece committed from here on. `main` is pushed nowhere. Before it ever is: commits older than `808c6a8`
  hold the real ARN and KFintech username in files since deleted.
- **What I am not allowed to do** (writes to the live database, deploys, gcloud changes) I hand him as one `!` command.

## What must not be touched

- `%LOCALAPPDATA%\MFDInvoice\` is the app's data, in development as in production. Neil onboarded there for real
  (his own invoices, CAMS's files chosen by hand). It stays through every change, as it would through an update.
- `labs/`, `.env`, `client/config.toml`, `website/site/.dev.vars`.
- Real data never goes in the repo: real invoices, and his partner's name, GSTIN, PAN and ARN. It lives in
  `Desktop\Automation-old-data\` (samples, the two registrar invoices and the script that makes the previews from them).

## The architecture now

- **Everything runs on the PC:** the window, a hidden browser the app owns (headless Edge), files, mailbox, vault,
  signing, and the run.
- **Two servers, kept apart** (Neil: SOFTWARE + its server, WEBSITE + accounts).
  - The website (`website/site`, Cloudflare Worker + D1): sign-in, plan, free trial, binding an ARN to an account,
    the current app version. The app's routes are `/api/app/*` (`website/site/API.md`).
  - The software's server (`server/`, its own Cloudflare Worker + D1 + R2): the current portal steps as a signed zip,
    and what the app sends to support, with each run's record. Nobody signs in to it.
- **The portal steps are not baked into the app.** `client/src/client/automation/` is zipped, signed with our key
  (`ops/automation.py publish`) and deployed with the server. Before any portal work the app asks which version is
  current, downloads it if it is new, checks the signature, and runs it locally (`hands/loader.py`). No answer from the
  server means no portal work. In a checkout (`uv run app`) the steps are run straight from the folder.
  The boundary between app and steps is `hands/host.py`: anything behind it needs an app update; the steps do not.
- **The signing key** is `~/.mfdinvoice/automation.key`, outside the repo. Whoever holds it can put code on every
  user's PC. Never commit it, never print it. `~/.mfdinvoice/server-admin.key` reads the reports back.
- **Updates are forced:** an app older than `APP.version` in `website/site/src/consts.ts` shows only Update now.
- **Accounts:** email + code. An account is made on the website only: the app signs in to one and never makes one
  (`/api/app/code` answers `no_account`). One free trial per account, 15 days; a second ARN is bought. Finishing
  setup binds the ARN (on a plan); Activate free trial binds it and starts the trial. An ARN set up without KFintech
  is bound later: CAMS's sign-in proves too little, so the first run binds it once CAMS's files for it are read
  (`bindOnRun`, `confirm_arn`), and its trial starts then. The law: the ARN typed = the ARN CAMS shows = the ARN
  KFintech shows, at setup and on every run; a mismatch stops, and nothing is suggested. An ARN belongs to one
  account while that account's plan runs; once it has ended, another account that binds it takes it.
- **The Google Cloud server is stopped** (`ops/stop-cloud.sh start` would bring it back). Nothing uses it.

## Where the code is

| | |
|---|---|
| `client/src/client/hands/shell.py` | `uv run app`: the launcher. In a checkout a run stops just before Submit unless `client/config.toml` has `[dev]` `submit = true`. `uv run app --show-browser` shows the browser a run drives; otherwise it is hidden. The log is always full: every action on a page, every answer from a portal, every stop with its traceback, in `workspace\logs\app.log` (I may read it; typed text is logged by length only), and each run's own part in `workspace\runs\<id>\log.txt` |
| `client/src/client/hands/window.py` | the window's Python side: every method the window calls; `_drive` runs a run, a check or a download |
| `client/src/client/hands/host.py` | what the steps are given: tabs, the person, files, signature, mailbox, the run's record |
| `client/src/client/hands/loader.py`, `server.py` | getting the steps (download, signature check), and the software's server |
| `client/src/client/hands/site.py` | the website's API |
| `client/src/client/automation/` | the steps: `flow.py` (the run, top to bottom), `cams.py`, `kfin.py` (every page), `month.py` (the month's record on disk), `numbering.py`, `own.py`, `files.py`, `words.py`, `invoices/` |
| `client/window/src/` | the window (Svelte). `bridge/types.ts` is the boundary; `bridge/fake/` is a made-up backend for `bun run dev` (mine, for looking at screens) |
| `server/` | the software's server. `bun run first` once, then `bun run deploy` |
| `ops/automation.py`, `ops/reports.py` | sign and publish the steps; read what was sent to support |
| `website/site/`, `website/todo/`, `TODO.md` | the website, its older lists, and the one list of everything left. `bun run check` in `website/site` runs its own checks on a fresh local database (51 of them; nothing live) |
| `labs/15_tally/`, `labs/tally-results.md` | the Tally lab (not in git): what Tally's XML server on port 9000 can and cannot do, found on a paid TallyPrime 7.1. `e21_import.py` is the working import; `e27_own.py`, `e28_reserve.py` are the own-number findings |

The run was ported from the old server's code, which is in git history, not on disk: `git show HEAD:demo/cams.py`,
`demo/kfin.py`, `demo/run.py` (the one-script version) and `git show HEAD:server/src/server/flow/cams.py`.

Each ARN's data: `%LOCALAPPDATA%\MFDInvoice\workspace\arns\<ARN>\<OCT-2026>\` (`month.json`, `invoices.json`,
`cams/`, `kfintech/`), `books.json` (own invoice numbers given for good). A run's record: `workspace\runs\<id>\`.

## The run, as Neil decided it (4 Oct 2026)

Check (sign in, ARN, status, listing) → Get → Read → Sign → **Your check** → per registrar: prepare, the registrar's
own check, Submit, status again. Your check comes before anything is prepared, so there is one round for every case.

- A run needs nothing asked first, except on own invoices: "Is this still your last invoice number?"
- Session reuse while the app is open, for 20 minutes of being left alone (tested safe); after that the browser is
  closed and the portals are signed in to afresh. No sign-out; no counting of sign-ins. A CAMS lock says try again in 15 minutes.
- Status is read fresh by every run. Submitted and approved invoices are not shown at Your check; rejected ones come
  back with the registrar's words.
- Files are reused when the registrar still lists exactly what they held when fetched; else fetched again. No clock.
  (Neil wants this explained again; he may add a clock.)
- CAMS's email: the app asks, waits 10 minutes, then stops; the next run looks first and never asks twice. With no
  mailbox, the app still asks CAMS, then the person drops or opens the zip and the Excel. Nothing is checked by name.
- Own invoice numbers: only ticked invoices get one, no gaps; a number is the invoice's for good when Submit is
  pressed, and when the month is imported into Tally (which numbers the unsubmitted ones after the rest).
- IGST on own invoices: set aside at Your check, for now. He means to do IGST after launch: keep the door open.
- A problem at one registrar does not stop the other. Nothing is retried by itself. Stop is at once, except while a
  Submit's answer is being read. A stop is how a run ended (`run_ended.stop`), never a question.
- Every run, check and download is sent to the software's server when it ends (kind `run`), with its own log. An
  "ours" stop also brings the run's record (pictures of the invoice pages, the page's HTML). Send to support
  attaches the latest run's record too. The person sees none of this.
- Download invoices reads what each registrar lists, not what is already submitted (CAMS's status page is its
  slowest). The listing stays: it is how a later run knows the files on this PC are still the month's.
- The files screen has Skip CAMS when KFintech is in the same run: CAMS is left out, KFintech carries on, and the
  next run does not ask CAMS for the email again.
- Month picker at the top right of Overview: Run, Check now and Download work on the month shown.
- Check now: a reading under 10 minutes old is shown again.
- "I don't use CAMS" exists like "I don't use KFintech"; one of the two must be used.

## Where it stands (5 Oct 2026)

`TODO.md` at the repo root is the full list of what is left, and says what ships from where.

- **Live:** the app 1.0.3, the website, the software's server and the steps, all released and deployed on 4 Oct.
- **Works, tested by Neil for real:** sign-in, setup with both portal verifications, the trial, Send to support,
  Settings, the own-invoice preview, the installer on a clean PC, an update (1.0.0 to 1.0.1), an update that fails
  and brings the old version back (1.0.2 was made to die at start), the Software tab taking what the app sends.
- **Run by him on the live portals (4 Oct):** both sign-ins inside a run, Check status (October: neither registrar
  lists it yet), Download invoices for September with CAMS's files added by hand (17 invoices read), the month
  picker. A Run of August for KFintech ended "already submitted".
- **Built on 4 Oct, in 1.0.3, not yet seen by him:** the app never making an account; CAMS's setup step needing a
  passed verify; the ARN bound by the first run when KFintech is not used; setup's optional Tally step (7 steps
  now); the Tally tab as one scrolling page with a tick before Import; the preview's full-screen button. What I
  checked: the window's type-check, the Tally tab and the Tally step on the made-up backend, the Tally look against
  his TallyPrime (read-only), the website's own checks (51 of 51). The bind in a run has not run for real.
- **Built and checked by me, not yet run by him:** everything in a run after Read (Sign, Your check, prepare, the
  registrar's own check), CAMS's email through the mailbox, Skip CAMS, "not listed yet", CAMS not used, the
  20-minute sign-in rule, the Tally import (tested by me on MFD Test only). **Nothing after Read has run against a
  signed-in portal.**
- **Never seen live by anyone:** CAMS's final Submit and what it says after; KFintech's number and date boxes on own
  invoices; what CAMS shows for a row left out of an upload; where a rejection's words appear; whether KFintech's
  header shows the ARN on every page. The code stops and keeps the page when a page is not what it expects.
- **Tally lab, 4 Oct** (`labs/tally-results.md`): a password on the company is no new case (logged in, it works;
  shut, it is a company that isn't open); a missing IGST ledger is made right; Tally moved off port 9000 is found
  by asking Windows which port `tally.exe` listens on.
- **Not built:** Zoho Books (before launch; a lab first), the deleting of run records after 90 days (the Privacy
  page says 90 days), IGST on own invoices (after launch).
- **Parked on his word:** the USB signing token (hidden, code kept; he has no token now).
- **His plan for October:** finish the software, give it to about ten distributors through his partner, collect
  every problem, fix, ship one update. Four kinds of work: sure now; needs the two of us to clear up; needs a lab;
  cannot be known without real invoices. Do the first three, make the fourth easy to learn from.
- **Cloud sessions** work on a copy of this repo with no keys: they change code and push a branch; building,
  publishing, releasing and deploying happen on his PC.
