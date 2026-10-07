# Lab: CAMS and KFintech, on October 2026's real invoices

Written 7 Oct 2026 for a lab session with Neil. The lab's code and notes go in `labs/` (not in git); the results go in
`labs/portals-results.md`; real data (the partner's name, ARN, GSTIN, PAN, invoices, emails) never goes in the repo.

## Why now

On 7 Oct KFintech lists 3 invoices for the October run (its trail month, September) and CAMS lists 3 (Invoice Status:
"File Not Uploaded"). For the first time there is something to submit, so the pages never seen can be seen. Some
answers also decide designs that are waiting (see "What each answer decides" at the end).

## The software, in short (what the lab is for)

MFDInvoice is a Windows desktop program for mutual fund distributors. Each month it does, for one ARN:
**Check** (sign in to CAMS and KFintech, read the ARN they show, read each registrar's status and listing) → **Get**
(KFintech: download the month's zip; CAMS: ask for the mailback, which CAMS emails as a zip of PDFs and an Excel) →
**Read** (the invoices, from those files) → **Sign** (the person's signature image, or a USB token) → **Your check**
(the person ticks what goes) → per registrar: **prepare** the upload, the registrar's **own check**, **Submit**,
**status again**. A headless Edge drives the portals (Playwright); the person sees steps, not the browser
(`uv run app --show-browser` shows it).

- The steps are `client/src/client/automation/`: `flow.py` (the run), `cams.py`, `kfin.py` (every page),
  `cams_selectors.toml`, `kfin_selectors.toml` (every selector, each marked where it was verified or UNVERIFIED).
- Two kinds of invoice: **the registrar's** (CAMS or KFintech made it, with its own number, e.g. CAMS's
  `KM/26-27/E/6`), signed and uploaded as is; and **own invoices** (`invoices.source = "own"`): the distributor's own
  invoice, drawn by the software, carrying the distributor's own number series (e.g. `73/26-27`). CAMS takes them
  through "Your Own Invoice Format" (Excel column `BROKER INVOICE NUMBER`); KFintech through On Screen Upload,
  source "MFD", with an Invoice No box and a date box per row.
- The law of the ARN: the ARN the person set up = the ARN CAMS shows = the ARN KFintech shows, at setup and on every
  run. A mismatch stops.
- In a checkout, a run stops just before Submit unless `client/config.toml` has `[dev] submit = true`.
- Known facts are in the selector files and the module docstrings. Read them before guessing.

## Rules for this lab

1. **Before each try, write the guess down** (what we expect to see), then the smallest try that answers it.
2. **Submit stays off** until the guess for that page holds. A rerun is safe: status is read fresh.
3. Keep a picture and the HTML of every new page (`labs/portals/<date>-<page>.png|html`).
4. Nothing is clicked that can't be undone without saying so first.

## The unknowns

Each: what we expect · why it matters · the best possible finding.

### A. Never seen by anyone
1. **CAMS's final Submit**, and what CAMS says after it. Expect: a Submit button only once every row is valid
   (`final_submit` is UNVERIFIED), then a success text, then Invoice Status changing. Matters: the run must know it
   went through. Best: a clear success text with a reference, and the status updating at once.
2. **KFintech's Invoice No and date boxes on own invoices** (On Screen Upload, source MFD). Expect: enabled only for
   Pending/Rejected rows (selector notes). Matters: own invoices are typed there. Best: plain inputs that take our
   number and `dd/MM/yyyy`, kept on a page reload.
3. **KFintech's result text after Upload Selected Invoices.** Expect "Signed invoices uploaded successfully" or
   "Upload completed with…" (read from the page's bundle, never seen). Best: per-row results.
4. **What CAMS shows for a row left out of an upload** (part of a month is sent by leaving rows' FILE NAME empty).
   Matters: Your check lets the person untick invoices. Best: the left-out rows stay "File Not Uploaded" and can go
   in a later upload.
5. **Where a rejection's words appear**, at each registrar (Remarks column? another page?). Matters: Overview shows
   "X rejected Y: '<their words>'". Best: a Remarks column on the status page we already read.
6. **Does KFintech's header show the ARN on every page?** Matters: the ARN law is checked from what the portal shows.

### B. Numbers (decides the own-invoice numbering design, still open)
7. For an own invoice **already submitted by hand, outside the software**: does either registrar show the number the
   distributor gave it? CAMS: the mailback Excel's `BROKER INVOICE NUMBER` for a submitted month, and the Invoice
   Status page. KFintech: the Excel-tab status table's `Invoice Ref No`, and View Submitted. Expect: unknown. Best:
   the distributor's own number, readable for every past submitted invoice.
8. Is `Invoice Ref No` (KFintech) the registrar's reference or the distributor's number?

### C. Who the person is (decides setup without typing the ARN)
9. **Where each portal shows the ARN, the distributor's name and the GSTIN**: after sign-in, on a profile page, in the
   downloaded files. Known: CAMS's report has `BROKER CODE` and `BROKER GST NUMBER`; KFintech shows the logged-in
   name and (it seems) the ARN in its header. Best: ARN, name and GSTIN all readable right after sign-in at both,
   before any month is touched.
10. Does a CAMS sign-in (email only) show the ARN at once, and is it always one ARN per email?

### D. CAMS's mailback (decides multi-month Download and the email design)
11. **Can CAMS take mailback requests back to back**, one per month, without waiting for each email? Known: the same
    request twice says "already queued" / "same input". Expect: different months are separate requests. Best: six
    months asked in a minute, six emails arriving.
12. **How long CAMS takes to send**, by time of day (6 Oct: asked 17:07, sent 17:09, in Gmail 17:10). Note several.
13. **What's in the email itself**: subject `WBR106. GST invoice, Request Id:<n>R106`; the body names the registered
    email and the Report Request No; the attachments are `GST_REPORT_<n>R106_<stamp>.zip|.xls`. Confirm it is the
    same every time, and whether the zip has a password.
14. **Forwarding (for "forward your mailbacks to us")**: a Gmail filter forwarding CAMS's mail keeps DKIM passing for
    camsonline.com (Show original said PASS on a direct mailback). Check one forwarded copy end to end.

### E. Downloads for past months
15. KFintech: can any past month be downloaded (back to April 2026), and is a submitted month's file the same as
    before? CAMS: the same for mailbacks of submitted months.
16. Credit notes (both portals have Credit Note Download/Upload): what are they, when do they appear, does a
    distributor have to sign and upload them too? Only to know; nothing is built.

## What each answer decides

- 7, 8 → own invoice numbers for months submitted outside the software, and what goes into Tally for them.
- 9, 10 → setup without typing the ARN (and the name and GSTIN).
- 11, 12 → Download for several months at once; how long a run waits for CAMS.
- 13, 14 → the three ways CAMS's email arrives (forwarded to us, Gmail app password, by hand).
- 1 to 6 → the run after Read, end to end, and the words on its screens.

## The most wonderful findings, for us

- Both portals show the distributor's own invoice number for every submitted invoice (7): numbering stops guessing.
- ARN, name and GSTIN on both portals right after sign-in (9): setup becomes "sign in to CAMS and KFintech".
- CAMS takes back-to-back requests and sends within a minute (11, 12): a year of downloads in one go.
- Rejection words on the status page we already read (5): nothing new to open.
