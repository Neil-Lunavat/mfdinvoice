# Everything that is left before launch

The software and its server. `CLAUDE.md` says how we work, the rules Neil has decided, and how each change ships. The
website's list is `website/todo/WEBSITE-TODO.md`; what is decided for after launch is `AFTER-LAUNCH.md`; ideas parked
are in `IDEAS.md`. Delete a line when it is done, a section when it is empty.

## Now (9 Oct)

- [x] 1.0.1 released 9 Oct (cac0c38), steps 2026.10.09.1400, server and website deployed: the "reach the destination"
      changes, forwarding without a code, the carousel, dev mode, the second addresses (`HANDOFF.md`).
- [ ] Neil tests 9 Oct's work in dev mode: setup resuming after a restart; the forwarding carousel end to end (name
      the Gmail, Confirm, filter, the first CAMS mail); "Along the way" at a run's end; a mailback asked for on
      CAMS's own site read in. Portal retries and the DSC preview wait for a flaky portal and a token.
- [ ] Update now, first live test: an installed 1.0.0 updating to 1.0.1.
- [ ] Fix & Send again, one rejection reason at a time: each new reason that comes through support gets a fix only
      when the registrar's words alone say what to change (`CLAUDE.md`).

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
- [ ] A code-signing certificate, after the proprietorship is registered (`WEBSITE-TODO.md`): an unsigned .exe from a
      young domain is a likely reason Jio's MySafeNet and Airtel block us.
- [ ] Getting unblocked on Jio and Airtel, and the sign-in codes out of Spam (Google Postmaster Tools, warm-up
      mails): `Desktop\Automation-notes\isp-unblock.md`, `domain-warmup.md`.
- [ ] Brave on Neil's PC: clear "Cached images and files" for all time (a redirect cached from before Cloudflare loops
      mfdinvoice.co.in).
- Kept for now: `Desktop\Automation-old-data\appdata-backup-2026-10-04\`; `LAB-PORTALS.md`, `LAB-ZOHO.md`.
