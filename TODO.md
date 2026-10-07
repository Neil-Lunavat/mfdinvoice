# Everything that is left

One list for the software and its server, in the order of the passes we work in. `CLAUDE.md` says how we work, the
rules Neil has decided, and how each change ships. The website's own list is `website/todo/WEBSITE-TODO.md`; ideas
parked for later are in `IDEAS.md`. Delete a line when it is done, a section when it is empty.

## 1. Delete (8 Oct)

- [ ] Deploy both servers with `workers_dev: false`.
- [ ] Once the portal work below is in: `LAB-PORTALS.md`, `LAB-ZOHO.md`.

## 2. Small things (the portal lab into the software, and bugs found reading)

The portal lab's findings, bugs and Neil's answers: `labs/portals-report.md` (sections 2, 4 and 5); its working
scripts: `labs/portals/`.

- [ ] **Status words** (`words.py`, `month.said_about`): whole words, forgiving (case, spaces, a trailing full stop);
      unknown stops with the words; several rows for one invoice, the latest wins. "File Not Uploaded." is not final;
      KFintech's "Uploaded & Verification pending" is with the registrar. Both final states show "Approved".
- [ ] **CAMS:** sign-in checks the box's value after typing, and ignores the old expiry toast; one browser for good,
      sign in again on the expiry toast or form and redo the step once (no 20-minute rule); the upload's Excel holds
      only the ticked rows; validation waits until every row is decided and reads "VALIDATED"; Submit's answer is
      `.re-success` + each row's Message; the survey pop-up is cancelled.
- [ ] **KFintech:** sign-in reads loginAPI's 10000/10001 and the snackbar's text (not its colour), a wrong captcha asks
      again; greyed rows (`pointer-events: none`) are not clickable; tab clicks repeat until `aria-selected`; a listed
      fund with no file means the files are fetched again on the next run.
- [ ] The SEP-2026 CAMS folder held August's mailback: files land in the wrong month.
- [ ] `MonthView.check` still uses the old toast (Overview has the new one).
- [ ] Own invoice numbers obey GST Rule 46 where they are typed (16 characters; letters, digits, `-`, `/`).
- [ ] Website: Privacy and Security say invoice files never reach us, but forwarded CAMS mail passes through our
      server (encrypted, deleted once fetched); they don't mention survey answers or ideas. "The records of runs is";
      Terms' "before you say press upload".

## 3. Big things

- [ ] **Numbering: books first** (rules in `CLAUDE.md`, "Invoice numbers"). The Tally lab's numbering answers (`e40`)
      decide Automatic numbering with a back-dated month. Then: the import moves into the run before Sign for own
      invoices; the wait on TallyPrime with its refresh button; the guard without books; the end-of-run list
      without books; Your check's new-year line; the Tally tab stops importing own and submitted invoices.
- [ ] The month view's Check now greys out like Overview's.
- [ ] **Setup's new order** (rules in `CLAUDE.md`): the name and GSTIN step from CAMS and KFintech; Books before Your
      invoices. Then the website's `/setup` page follows it (with forwarding, the DSC and Zoho).
- [ ] **Zoho Books** (`labs/zoho-results.md`): connect from the browser's Accept page back to the PC (loopback, PKCE,
      the secret shipped); the organisation and its GSTIN checked like Tally's company; the customer by GSTIN (made if
      missing; two with one GSTIN stop and ask); our number or the registrar's (`ignore_auto_number_generation`);
      our id in `reference_number`; the signed PDF attached; marked sent with no email; one invoice per request,
      Zoho's own words on a refusal; the look before anything is written; an invoice typed by hand is adopted.
      Neil makes a Zoho login for MFDInvoice to own the API client; until then, his MFD Test client.

## 4. Neil's pass in the real software

On a fresh start, from onboarding. Nothing below has been seen by him in the real software.

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

## In Neil's hands

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
