# Everything that is left

One list for the software and its server, in the order of the passes we work in. `CLAUDE.md` says how we work, the
rules Neil has decided, and how each change ships. The website's own list is `website/todo/WEBSITE-TODO.md`; ideas
parked for later are in `IDEAS.md`. Delete a line when it is done, a section when it is empty.

## 1. Delete (8 Oct)

- [ ] Once the portal work below is in: `LAB-PORTALS.md`, `LAB-ZOHO.md`.

## 2. Built 8 Oct, all of it unseen by Neil (checked: compile, type-check, MFD Test in Tally and Zoho)

- The portal lab in the software: status words, CAMS (one browser, sign-in again on expiry, only ticked rows,
  validation, Submit's answer, the survey), KFintech (sign-in by the server's reply, greyed rows, tab clicks, missing
  files fetched next run). CAMS files checked for month and ARN before they enter a month. Rule 46 where typed.
- Invoice numbers, books first (Tally and Zoho); setup's new order with Name and GSTIN; Zoho Books; the Books tab.
- A code review of all of it (11 findings, all fixed).
- Before March: a run whose invoices span two financial years (March invoices sent in April) assumes one year.
- Zoho asks for full access; try the narrower scopes once Neil has clicked Accept for real.

## 3. Neil's pass in the real software

On a fresh start, from onboarding (the app data was wiped 8 Oct). Nothing below has been seen by him in the real
software.

- Setup's 9 screens: the name and GSTIN read from CAMS and KFintech; Books: Tally, Zoho Books (the browser's Accept
  page, the organisation, its GSTIN), or neither; Your invoices "continue from" the books.
- A run on own invoices with Tally: "Fetching your last invoice number", Tally shut (the red line, Refresh), Tally's
  questions inside the run, Your check without the number column, the books step, the end screen's invoice numbers,
  "In Tally as …, not sent yet" on the next run. The same with Zoho Books (attached, marked sent after Submit).

- Sign-in: "New here? Sign up" opens `/signin?from=app`; an email with no account is refused; "Free trial used".
- Setup: every step, both "I don't use" ways, the Tally step's cases (Tally shut, no company, one, two, a GSTIN that
  differs), the DSC at the signature step, the preview's full screen, CAMS's email three ways (forwarding needs
  Email Routing below).
- Overview: the month picker (April 2026 on), Check now, Run, Skip CAMS while its email is awaited ("Run CAMS"), a late
  CAMS email read in by itself, the survey toast.
- Downloads tab: several months in one go.
- Tally tab: import, import again, Refresh, Change, a GSTIN that differs, a hand-typed own invoice taking Tally's
  number, the voucher type asked when there is more than one, Tally on another port.
- Settings: This PC › Uninstall, Send an idea, Tally's GSTIN beside yours.
- The new logo in the window, the .exe and the installer.
- **A run after Read, against signed-in portals, on October's invoices**, Submit off until each guess holds: Sign,
  Your check, prepare, the registrar's own check, Submit, status again. Never seen by anyone: CAMS's Submit answer
  and its survey; KFintech's upload with own number and date; KFintech's session expiring mid-run; a rejection's
  words; the ARN set up without KFintech (bound by its first run).

Then the fixes his pass turns up, and a last pass over the words on every screen.

**Pass of 8 Oct: done** (setup, runs to just before Submit, Tally numbering into MFD Real, downloads of every month).
Still never run by Neil in the real software:
- A real Submit on CAMS and on KFintech (`[dev] submit = true`): reading their answers after Submit.
- KFintech's retry on an empty table (66413b7) and its own words when Upload stays disabled: wait for KFintech to
  misbehave live.
- The before-write number check against a live Tally; the last invoice number typed when the books are empty.
- Zoho Books' browser connect; Gmail and forwarding (several months' emails asked together, Check mail); a DSC token;
  a second ARN; an ARN with CAMS only; Send to support; sign out; Update now.
- Add CAMS's files → Add N months; files dropped from Explorer on the run's file box.
- Tally: MFD Real holds test vouchers 1–9 from this pass; Neil cancels them and sets the Sales type's numbering.

## In Neil's hands

- [ ] Ask the partner (the CA): for invoices CAMS or KFintech made, should the voucher number in Tally be the
      registrar's invoice number (the one the AMC holds and matches in GSTR-2B)? Today Tally's registrar import gives
      Tally's own next numbers and keeps the registrar's as a reference; Zoho stores the registrar's number.
- [ ] Ask the CA: KFintech sometimes raises two invoices for one payment under one reference (Bank of India, June
      2026, ref 116260601005784): "ExclusiveGST" (taxable 7,156.56 + GST 1,288.18, serial BMTI/2026-27/003) and
      "InclusiveGST" (taxable 20.21, GST within, no serial). KFintech's own status table shows only the first.
      Decided for now (8 Oct): the software shows and imports KFintech's figure (the first) and keeps the second's
      PDF and figures attached, unused; such an invoice still open to send is held back with the reason. What should
      the books hold, and should the second be sent or entered at all? (`automation/kfin.py` `read_zip`)

- [ ] Cloudflare Email Routing on `mailback.mfdinvoice.co.in` (check it changes no record of the apex, where
      Hostinger's MX is), then `cams@mailback.mfdinvoice.co.in` → Send to a Worker → `software`.
- [ ] Someone who knows Zoho Books from the inside checks what an import looks like there.
- [ ] Publish the steps after his pass (`uv run app` uses them from the folder until then).

## Launch: 1.0.0

- [ ] Clean both live databases and the file store; remove Neil's test account and its ARN.
- [ ] Release notes back to one first release; release 1.0.0.
- [ ] The website's launch items (`WEBSITE-TODO.md`).
- [ ] The ten distributors through the partner: what each is given, what is read from
      `control.mfdinvoice.co.in/software` after each run, how a report becomes a fix, when the one update ships.
      From a report to a fix: `uv run --project client python ops/reports.py pull` puts every open report, with its
      log and record, into `~/.mfdinvoice/reports/pull-<when>/` with an INDEX.md. It holds real invoices: never in
      the repo.

## Owed by people

- [ ] The lawyer reads Terms, Privacy and Refunds; then the "A draft" line goes (`components/Legal.astro`).
- [ ] The how-to videos. Setup's "How to · 1 min" buttons open `/setup` today.
- [ ] A code-signing certificate for the installer, or keep "Windows protected your PC" (More info, Run anyway).
- [ ] Neil's old app data in `Desktop\Automation-old-data\appdata-backup-2026-10-04\`: keep or delete.

## After launch

- IGST on own invoices (set aside at Your check today).
- Zoho: payments with TDS, credit notes, GSTR-1 (`IDEAS.md`).
- The month picker gets a year once there is a second financial year.
- Decided against: updates that download only what changed (87 MB each time; the steps update by themselves).
