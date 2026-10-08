# MFDInvoice: how Neil and I work on it

How we work, what the software is, and the rules Neil has decided. Where things stand is `TODO.md`, not here. Neil
edits this; where it and he disagree, he wins.

## How we work

- **Neil decides everything.** I read the code and tell him what a thing does, why it is there, whether the job needs
  it, and my lean with the reason. He answers. Nothing is trashed, kept or changed in behaviour on my own say.
- **Decisions come as numbered items**, grouped by screen or step: what is there today, then "Lean:" and one reason.
  He answers by number. Short and plain; he wants an informed decision with little to hold in his head.
- **Master and workers.** The main session (Opus) holds the context and the decisions. It turns each decided piece
  into a deterministic brief (files, the exact change, the checks to run, what not to touch) and spawns a worker for
  it (`Agent`, model `sonnet`). The worker edits and checks, never commits; the master reviews its diff and checks,
  then hands it to Neil. Workers keep their output out of the master's context: tokens matter.
- **Priorities, in order:** it is reliable; it works or it says why; the UX feels good. After those: low cost, speed.
  Secrecy is not a priority. Simple and working beats clever. What serves neither function nor form goes.
- **Old reasons are not trusted.** Comments and docstrings may describe an architecture that is gone ("brain",
  "contract", "SOFTWARE.md"). Read what the code does, question every inherited rule, and clean the stale words in a
  file when touching it.
- **Neil is the tester, by hand, in the real software, with real credentials.** No test suites, and nothing faked for
  him unless he says "fake". I check my own work before handing it over (type-check, build, a script that drives it)
  and say exactly what was checked and what was not. No screenshots of screens for my own checks (Neil, 8 Oct).
- **One working piece at a time:** build it, he runs it, he reports with screenshots, I fix, then the next piece.
- **He is blunt and fast.** Match the pace: no hedging, no padding, no obvious questions. When I am unsure of
  something he knows (what a portal shows), I say so and he shows me.
- **Words in the window matter to him.** "Verify", not "Test". "Software", not "app". No deadlines or reminders: that
  is the person's job. Make them feel they own it. He rewrites copy; take his wording.
- **Commit only when asked; stage files by name.** `main` is on GitHub (`origin`, `Neil-Lunavat/mfdinvoice`,
  private). The local branch `old-history` holds the real ARN and KFintech username in files since deleted: it is
  never pushed. One repo holds the software, its server and the website, because a release writes into all three. A
  cloud session pushes a branch, never `main`; Neil pulls it and merges.
- **What I am not allowed to do** (deleting files outside the code, writes to the live databases, deploys, the app's
  data) I hand him as one `!` command.

## What must not be touched

- `%LOCALAPPDATA%\MFDInvoice\` is the software's data, in development as in production. It stays through every change,
  as it would through an update. Only Neil wipes it.
- `Desktop\Automation-old-data\labs\` (moved out of the repo 8 Oct), `.env`, `client/config.toml`, `website/site/.dev.vars`.
- Real data never goes in the repo: real invoices, CAMS's reports, and his partner's name, GSTIN, PAN and ARN. It
  lives in `Desktop\Automation-old-data\`.
- The signing key `~/.mfdinvoice/automation.key`: whoever holds it can put code on every user's PC. Never commit it,
  never print it. `~/.mfdinvoice/server-admin.key` reads the reports back.

## The architecture

- **Everything runs on the PC:** the window, a hidden browser the software owns (headless Edge), files, mailbox,
  vault, signing, the books (Tally, Zoho Books), and the run.
- **Two servers, kept apart** (Neil: SOFTWARE + its server, WEBSITE + accounts).
  - The website (`website/site`, Cloudflare Worker + D1, `mfdinvoice.co.in`, the panel at `control.`): sign-in, plan,
    free trial, binding an ARN to an account, surveys, the current software version. The software's routes are
    `/api/app/*` (`website/site/API.md`).
  - The software's server (`server/`, its own Worker + D1 + R2, `software.mfdinvoice.co.in`): the current portal
    steps as a signed zip; what the software sends to support, with each run's record (kept 90 days, a daily job
    deletes them); CAMS's mailbacks forwarded to us (Email Routing on `mailback.mfdinvoice.co.in`, kept encrypted for
    the person's PC only, deleted once fetched). Nobody signs in to it.
- **The portal steps are not baked into the software.** `client/src/client/automation/` is zipped, signed
  (`ops/automation.py publish`) and deployed with the server. Before any portal work the software asks which version
  is current, downloads it if new, checks the signature, and runs it locally (`hands/loader.py`). No answer from the
  server means no portal work. In a checkout (`uv run app`) the steps run straight from the folder. The boundary is
  `hands/host.py`: anything behind it needs a software update; the steps do not.
- **Updates are forced:** a software older than `APP.version` in `website/site/src/consts.ts` shows only Update now.
- **Accounts:** email + code. An account is made on the website only; the software signs in to one and never makes
  one (`/api/app/code` answers `no_account`). One free trial per account, 15 days; a second ARN is bought. Finishing
  setup binds the ARN (on a plan); Activate free trial binds it and starts the trial. An ARN set up without KFintech
  is bound by its first run once CAMS's files for it are read (`bindOnRun`, `confirm_arn`). The law: the ARN read at
  setup = the ARN CAMS shows = the ARN KFintech shows, at setup and on every run; a mismatch (two logins of two
  different ARNs) stops, and nothing is suggested. An ARN belongs to one account while that account's plan runs; once it has ended, another account that
  binds it takes it.
- **One PC per account** (Neil, 8 Oct; not built yet): signing in on a second PC asks there, as CAMS does, whether to
  sign the other PC out and sign in here, or keep the other PC and not sign in here.

## Where the code is

| | |
|---|---|
| `client/src/client/hands/shell.py` | `uv run app`: the launcher. In a checkout it builds the window again first when `client/window` changed since the last build. In a checkout a run stops just before Submit unless `client/config.toml` has `[dev]` `submit = true`. `--show-browser` shows the browser a run drives. The log is always full (every action on a page, every portal answer, every stop with its traceback) in `workspace\logs\app.log` (I may read it; typed text is logged by length only), and each run's own part in `workspace\runs\<id>\log.txt` |
| `client/src/client/hands/window.py` | the window's Python side: every method the window calls; `_drive` runs a run, a check or a download |
| `client/src/client/hands/host.py` | what the steps are given: tabs, the person, files, signature, mailbox, the run's record |
| `client/src/client/hands/loader.py`, `server.py`, `site.py`, `forward.py`, `zoho.py` | getting the steps; the software's server; the website's API; CAMS's forwarded mailbacks; Zoho's sign-in and tokens (keys in `~/.mfdinvoice/zoho.json`, bundled by `packaging/build.py`, never in git) |
| `client/src/client/automation/` | the steps: `flow.py` (the run, top to bottom), `cams.py`, `kfin.py` (every page), `words.py` (status words), `month.py` (the month on disk), `numbering.py`, `own.py`, `books.py` (the books seam), `tally.py`, `zoho.py`, `files.py`, `invoices/` |
| `client/window/src/` | the window (Svelte). `bridge/types.ts` is the boundary; `bridge/fake/` is a made-up backend for `bun run dev` (mine, for looking at screens) |
| `server/` | the software's server: `bun run deploy` |
| `ops/automation.py`, `ops/reports.py`, `ops/release.py` | sign and publish the steps; pull what was sent to support; release the software |
| `website/site/` | the website: `bun run check` runs its own checks on a fresh local database (nothing live); `-- --keep` leaves the panel up on :8800 with sample data |
| `TODO.md`, `website/todo/WEBSITE-TODO.md`, `AFTER-LAUNCH.md`, `IDEAS.md` | what is left before launch for the software and servers, and for the website; what is decided for after launch; ideas parked |
| `Desktop\Automation-old-data\labs\` (outside the repo) | what the portals, Tally and Zoho really do: `*-results.md` and `portals-report.md`, with the scripts that found it |

Each ARN's data: `%LOCALAPPDATA%\MFDInvoice\workspace\arns\<ARN>\<OCT-2026>\` (`month.json`, `invoices.json`,
`cams/`, `kfintech/`), `books.json` (own invoice numbers given for good). A run's record: `workspace\runs\<id>\`.

**Where each change ships from** (only Neil's PC holds the keys):

| A change to | Ships by |
|---|---|
| `client/src/client/automation/` (the steps) | `uv run --project client python ops/automation.py publish`, then `cd server && bun run deploy`. No software update |
| anything else under `client/` | raise `version` in `client/pyproject.toml`, `uv lock`, commit, `uv run python packaging/build.py` in `client/`, `ops/release.py "<one sentence>"`, deploy the website |
| `server/` | `cd server && bun run deploy` |
| `website/site/` | `bun run check`, then `cd website/site && bun run deploy` |

## Setup, as Neil decided it

CAMS → KFintech → Your ARN, name and GSTIN → Signature → Books → Your invoices → Mailbox → Check everything
(8 steps). **The ARN is never typed:** it is read from the portals, one ARN per login.

- CAMS and KFintech each carry their own consent tick ("I authorise MFDInvoice to sign in and act for me on CAMS",
  the same for KFintech).
- CAMS gives the ARN (its header "ARN-n / Name") and the name. KFintech gives the ARN, the name (Distributor Profile)
  and the GSTIN (View Uploaded); with both, KFintech's name wins. No CAMS page shows the GSTIN.
- "Your ARN, name and GSTIN" shows what was read: the ARN not editable, the name and GSTIN prefilled and editable
  ("Is this correct?"). CAMS only: the GSTIN is typed.
- Binding: with KFintech, the ARN is bound when setup finishes. CAMS only: bound by the first run (below).
- Books: Tally, Zoho Books, or neither; one per ARN, whichever they pick. Before Your invoices, so the last invoice
  number is read from the books.
- "I don't use CAMS" exists like "I don't use KFintech"; one of the two must be used.
- A portal's sign-in page that misbehaves at Verify: the first time "CAMS portal behaved unexpectedly, try again";
  twice in a row "Something on the CAMS portal seems to have changed. You can skip CAMS for now and continue with
  KFintech, or you can send to support and we'll fix it as soon as possible." (both links). No internet says so
  instead, and doesn't count. Same for KFintech.
- No network: a toast at the top right of every screen, "Network not connected. Retrying in 7s · reconnect", until it
  is back. Retries after 1, 5, 10, 30 s, then every 2 min; reconnect checks at once.
- The consent tick sits just above Verify, under the fields, on both portals' steps.

## The run, as Neil decided it

Check (sign in, ARN, status, listing) → Get → Read → Sign → **Your check** → per registrar: prepare, the registrar's
own check, Submit, status again. Your check comes before anything is prepared, so there is one round for every case.

- A run needs nothing asked first, except on own invoices without books: "Is this still your last invoice number?"
  With books connected nothing is asked: the books are read inside the run (see "Invoice numbers").
- Sessions: CAMS keeps one browser for good, and signs in again only on its expiry toast or sign-in form, then redoes
  that step once. KFintech: reused for 20 minutes of being left alone, then closed and signed in afresh. No sign-out;
  no counting of sign-ins. A CAMS lock says try again in 15 minutes.
- Status words are matched as whole words, forgivingly (case, extra spaces, a trailing full stop). An unknown word
  stops and shows the registrar's words. Several rows for one invoice: the most final state wins (Approved over Rejected, whatever the order). Both registrars' final state
  shows as "Approved" (KFintech's "Payment processed" too).
- CAMS and KFintech approve on their own; neither reads the PDF. The person's tick at Your check is the real check.
- Status is read fresh by every run. Submitted and approved invoices are not shown at Your check; rejected ones come
  back with the registrar's words.
- Files are reused when the registrar still lists exactly what they held when fetched; a listed invoice with no file
  means they are fetched again on the next run.
- CAMS's email, three ways, in this order: forwarded to us, Gmail with an app password, by hand. Any mailback for this
  ARN and month will do (checked by the Excel's month, BROKER CODE and listing). 10 minutes without it falls back to
  by hand; a late one is read in by itself while the software is open. Skip CAMS lets KFintech carry on.
- "Add CAMS's files" (Downloads beside Download, and each month's page): a modal where any number of CAMS's zips and
  Excels, of any months, are dropped or picked at once. They are paired by the request number in their names; each
  Excel gives the month and the ARN (BROKER CODE). Per month it says "October 2026: 5 invoices added"; another ARN's
  pair or a file without its partner is refused with the reason. Its "Add N months" reads them in (CAMS only); a
  run or download uses files on the PC when they hold every invoice CAMS lists now.
- Forwarded to us: the email proved in the software is the mailbox whose filter forwards to us; CAMS's mail may pass
  through others first (CAMS's registered email → another Gmail → us), and the server matches any mailbox on the way
  (Neil, 8 Oct). Chains through other providers are seen after launch.
- Waiting for CAMS's email with a mailbox read by itself (forwarded, Gmail): "Don't wait" in every run and download,
  one month as several (Neil, 8 Oct); the email is read in by itself when it comes.
- "Check mail" (left of Add CAMS's files, only with Gmail or forwarding): CAMS's emails looked for now, for every
  month waiting on one, instead of at the next turn of the background reader.
- CAMS's files given in a run are checked there and then (month, ARN, zip with its Excel, every invoice CAMS lists
  now); unusable ones are refused in the same box with the reason, to choose again or skip CAMS. When CAMS lists more
  than its last email held, the box says which invoices came since.
- Tally: a missing ledger is made by the software, never a stop: the fund house's (Sundry Debtors), IGST, CGST and
  SGST (Duties & Taxes), and "Commission Received" (Sales Accounts) when the company has no sales ledger. Where one
  already exists and the choice is not obvious, the person picks, as before.
- CAMS's upload holds only the ticked rows.
- KFintech's site is flaky: its table sometimes comes up "No invoice details" for a month it lists, and stays so.
  Read from the page only (never its network answers, which serve many things): an empty table for a month KFintech
  listed before, or with invoices to send, gets another month and back after 2, 5, 10 s; then "KFintech's website is
  having trouble. Run again in a few minutes." A month never listed before keeps "not listed yet".
- Both registrars stopped: the end screen says "CAMS and KFintech both stopped" and gives each its own block.
- A problem at one registrar does not stop the other. Nothing is retried by itself. Stop is at once, except while a
  Submit's answer is being read. A stop is how a run ended (`run_ended.stop`), never a question.
- Every run, check and download is sent to the software's server when it ends (kind `run`), with its own log and the
  pictures of the pages. Send to support attaches the latest run's record too. The person sees none of this.
- Your check: the table only, no invoice preview; its buttons are Cancel and Submit. With books connected it says the
  ticked invoices go into the books first (company named) and which ledgers will be new.
- Downloads of several months with a mailbox read by itself (forwarded, Gmail): every month's CAMS email is asked for
  first, nothing waits per month; then all are waited for together (10 minutes, "Don't wait"), each read in as it
  comes; any later one is read in by itself while the software is open.
- KFintech can raise two invoices under one reference (GST on top and GST within, Bank of India June 2026): read as one
  invoice with KFintech's own figures (the first's, as its table shows), the second kept attached; one still open is
  held back with the reason. What the books should hold is a question for a CA (TODO.md).
- Run is one month (the month picker at the top right of Overview). Downloads takes any months at once.
- Check now: a reading under 10 minutes old is shown again.
- IGST on own invoices: set aside at Your check, for now. Keep the door open.

## Invoice numbers, as Neil decided it (8 Oct)

**The problem.** An own invoice's number lives in four places: the PDF; the registrar (CAMS's Excel column BROKER
INVOICE NUMBER, which CAMS requires to equal the PDF's; KFintech's number box), which passes it to the AMC; the
person's books; and GSTR-1, filed from the books, which the AMC matches in its GSTR-2B. All four must be the same.
The law (GST Rule 46): unique in the financial year, consecutive, at most 16 characters of letters, digits, `-` and
`/`; an issued number is never changed or reused; an invoice that won't go ahead is cancelled, never deleted.

**Own invoices with books connected: books first.** The run goes Check → Get → Read → Your check → **into the books**
→ Sign → Submit. "Fetching your last invoice number" (shown at least half a second) reads the books; the ticked
invoices go in one at a time, in date order (Manual numbering: the books' highest at that moment + 1; Automatic: the
books choose); each number is read back; then each PDF is drawn with exactly that number. A number is the invoice's
for good once it is in the books, and is sent again unchanged after a failed or rejected submit. Unticked invoices get
no number. An open invoice someone already typed into the books (same fund house, month, within a rupee) takes that
voucher's number instead of a second voucher. The books must answer: if TallyPrime is not open, the run waits on a
red line saying so, with a refresh button; nothing reaches the portals without the books' numbers.

**The last invoice number is always shown** (setup's Your invoices, and Settings): fixed, read from the books, when
they hold invoices this financial year; typed ("What was your last invoice number?") when there are no books, or the
books hold none yet. A Tally sales type on Automatic numbering with no invoices numbers from 1 whatever is sent: setup
says so and how to set it in Tally (start from the next number, or Manual); nothing is renumbered, as none exist.
Every number also passes KFintech's rule (at least 3 characters), checked before anything is written to the books.
When KFintech's Upload stays disabled, its own words are shown.

**Own invoices without books:** the person types the last number before each run; it may skip ahead but never go below
the highest number the software has used (no repeats). A number is fixed at Submit. The run's end lists "enter these
in your books with these numbers".

**Registrar invoices:** the number is the registrar's. With books connected, the import numbers each voucher the
books' way (+1 from their last) and reads it back; nothing of ours is remembered.

**Past (submitted) invoices are never numbered, matched or imported:** they already carry their number, on the PDF the
registrar holds and in the person's books. Running September before July is allowed: July takes the numbers after
September's, and Your check says so. Tally set to renumber (a back-dated invoice would shift every later invoice
number): such an invoice is offered "Date it today" (it goes in last; nothing shifts) or "Put it aside"; we never
suggest changing Tally's setting (switching it renumbers existing invoices itself). A new financial year with Manual numbering: Your check proposes the year's
first number from the pattern (`1/27-28`), editable. Rule 46 is checked wherever a number is typed.
