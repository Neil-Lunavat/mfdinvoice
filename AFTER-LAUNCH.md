# After launch

What waits until 1.0.0 is out, decided by Neil. Nothing here is claimed anywhere (site, software, emails) until it is
built. Ideas not yet decided stay in `IDEAS.md`; what is left before launch is `TODO.md` and
`website/todo/WEBSITE-TODO.md`. Delete a line when it is done.

## The software

- Aadhaar eSign as a way to sign invoices. Nothing of it exists in the code; it is claimed nowhere.
- A run whose invoices span two financial years (March invoices sent in April) assumes one year today. Needed before
  the first April run.
- IGST on own invoices (set aside at Your check today; keep the door open).
- Zoho past the import: payments with TDS, credit notes, GSTR-1 (`IDEAS.md`).
- The month picker gets a year once there is a second financial year.
- Decided against: updates that download only what changed (87 MB each time; the steps update by themselves).

## Reports to fixes

- A project skill that pulls the open reports (`ops/reports.py pull`), reads each with its log and says what happened,
  why (and why not the other cause), and the fix. First a few rounds by plain prompting; Neil judges, then the skill.

## The website and panel

- Blog posts (delegated); `write.` and its writers' Cloudflare Access with them. The blog stays empty, with its
  footer link, until then.
- Read the checkout answers and the analytics after October.
- The Software tab: an account's runs on its own page.
- When the software blanks encoded passwords too (URL-encoded, base64, and in the page HTML), the Security page can
  show those forms again.
- `control.` and `write.` face Neil, not the public: iterated as he wishes, never a launch gate.

## The repository

- Clean-up: delete, consolidate, refactor. Only then `LAB-PORTALS.md` and `LAB-ZOHO.md` go: nothing that holds what
  the portals do is deleted before.
