# Everything that is left before launch

The software and its server. `CLAUDE.md` says how we work, the rules Neil has decided, and how each change ships. The
website's list is `website/todo/WEBSITE-TODO.md`; what is decided for after launch is `AFTER-LAUNCH.md`; ideas parked
are in `IDEAS.md`. Delete a line when it is done, a section when it is empty.

## Now (8 Oct)

- [ ] Clean the software's server: every report and its record (R2 `records/`), the forwarding boxes and mails. The
      website's database: what is left once Neil's account goes at 2:00 am (orders, receipts, events, answers,
      survey replies, deletions, trials). Neil runs the commands.
- [x] The keys backed up: `Desktop\MFDInvoice-keys\` (automation.key, server-admin.key, zoho.json, a README). Neil
      moves it somewhere safe.
- [ ] One PC per account (`CLAUDE.md`, Accounts): design with Neil, then build. Website and software.
- [ ] Forwarding: Cloudflare Email Routing on `mailback.mfdinvoice.co.in` (the apex's MX at Hostinger untouched), then
      `cams@mailback.mfdinvoice.co.in` → Send to a Worker → `software`. Proven without waiting on a CAMS mailback.
- [ ] Neil writes the first release notes.
- [ ] Publish the steps (`ops/automation.py publish`, `cd server && bun run deploy`): without them the built software
      does no portal work.
- [ ] Version 1.0.0, `uv lock`, build, `ops/release.py`, deploy the website.

## The partner's PC, a fresh slate

Neil signs up on the website, activates the free trial, downloads and installs on the partner's PC, and screenshots
every screen (Windows' "protected your PC", antivirus, the installer). Then:
- The installed build fetches the signed steps from the server, checks them and runs them.
- Setup from zero, with his DSC token at the signature step.
- **A real Submit on CAMS and on KFintech**, by the plan agreed with Neil (few invoices first; read what each portal
  accepts). Reading their answers after Submit, CAMS's survey, status again.
- Sign out.
- What it turns up: the steps (publish, no update) or 1.0.1, which is also the first real test of Update now.
- After it: `/setup`'s pictures from his screenshots.

## Never run live, verified after release

- Zoho Books' browser connect (someone who knows Zoho Books checks an import); then the narrower scopes.
- Gmail with an app password, in the refactored software; Check mail; several months' emails asked for together.
- A second ARN (bought on the website, then setup); an ARN set up with CAMS only, bound by its first run.
- Settings: This PC › Uninstall, Send an idea.
- KFintech's retry on an empty table (66413b7) and its words when Upload stays disabled: they come through support.
- Tally: the number check before writing, against a live Tally; the last number typed when the books are empty.
  MFD Real holds test vouchers 1–9: Neil cancels them and sets the Sales type's numbering.

Seen working by Neil: Add CAMS's files (the old Download CAMS files, renamed), Send to support.

## In Neil's hands

- [ ] The CA, in the meeting: (1) for invoices CAMS or KFintech made, should Tally's voucher number be the
      registrar's invoice number (the one the AMC matches in GSTR-2B)? Today Tally's registrar import gives Tally's own
      next numbers and keeps the registrar's as a reference; Zoho stores the registrar's number. (2) KFintech
      sometimes raises two invoices for one payment under one reference (Bank of India, June 2026, ref
      116260601005784): "ExclusiveGST" (taxable 7,156.56 + GST 1,288.18, serial BMTI/2026-27/003) and "InclusiveGST"
      (taxable 20.21, GST within, no serial). The software shows and imports the first and keeps the second attached;
      one still open is held back. What should the books hold, and should the second be sent or entered at all?
      (`automation/kfin.py` `read_zip`)
- [ ] The ten distributors through the partner, after today's run: what each is given, how a report becomes a fix,
      when updates ship. `uv run --project client python ops/reports.py pull` puts every open report, with its log and
      record, into `~/.mfdinvoice/reports/pull-<when>/` with an INDEX.md. It holds real invoices: never in the repo.
- [ ] The how-to videos. Setup's "How to · 1 min" buttons open `/setup` today.
- [ ] A code-signing certificate, after the proprietorship is registered (`WEBSITE-TODO.md`).
- Kept for now: `Desktop\Automation-old-data\appdata-backup-2026-10-04\`; `LAB-PORTALS.md`, `LAB-ZOHO.md`.
