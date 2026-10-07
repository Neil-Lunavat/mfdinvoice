# Lab: Zoho Books

Written 7 Oct 2026 for a lab session with Neil. The lab's code and notes go in `labs/` (not in git); the results go in
`labs/zoho-results.md`. Keys (client id, secret, tokens) go in `.env` or `~/.mfdinvoice/`, never in the repo and
never printed. Real invoices stay out of the repo.

## How to work

Broad first, then deep: try everything below quickly and write what happened, then go deep only on the paths the
software needs. Before each try, write the guess down. Use Zoho's India data centre (`zoho.in`, `zohoapis.in`).
Setup: Neil makes a free organisation on zoho.in and an API client on api-console.zoho.in (a Self Client is the
quickest start; a real user's way in is question 1).

## The software, in short

MFDInvoice is a Windows desktop program (Python, with a Svelte window) for mutual fund distributors. Each month it
gets the distributor's commission invoices from CAMS and KFintech (the two registrars), signs them, submits them, and
then puts the month into the distributor's books. Everything runs on the person's PC; our servers only sign people in
and receive support reports. Tally is done (`client/src/client/automation/tally.py`, `labs/tally-results.md`).
Zoho Books is the second: the website already promises it, and Settings shows "Zoho Books · Coming soon".

**One invoice, as the software holds it:** the fund house (the customer: name, GSTIN, address, state), the date, the
month, the taxable value (commission), CGST + SGST (same state) or IGST (another state) at 18%, the total, the
registrar (CAMS or KFintech), the registrar's reference, and an invoice number: either the registrar's own
(`KM/26-27/E/6`) or, for distributors who issue their own invoices, the distributor's own series (`73/26-27`). Also
the signed PDF.

**What Tally taught us, to hold Zoho to the same standard:**
- A customer is found by GSTIN, never by name.
- Never twice: every invoice carries our id (`MFDInvoice/<ARN>/<registrar>/<reference>`), so a second import skips it.
- Whose number: Tally's Automatic numbering ignores a number sent; Manual keeps it. We must know, before writing,
  which number each invoice will end up with, and read it back after.
- An invoice typed by hand already (same customer, same month, within a rupee) is held back, not doubled.
- The company's GSTIN is checked against the distributor's; a difference is a question, not a warning.
- One invoice per request, so a refusal is tied to its invoice in Zoho's own words.
- Nothing is written before the person has seen what will happen to each invoice ("the look"); an import can't be
  undone, so the look is the check.

## Our scope (what must work)

Each month's invoices into the person's Zoho Books organisation as **sales invoices**: the fund house as the
customer (made if missing, with its GSTIN), the commission as the line, GST right, our number or the registrar's, our
id on it, the signed PDF attached, no duplicates, the organisation's GSTIN checked against the distributor's.

## The unknowns

Each: what we expect · why it matters · the best possible finding.

1. **How a real user lets the software in.** A desktop program can't hold a secret. Does Zoho's OAuth allow a
   loopback redirect (`http://127.0.0.1:<port>`) or a device-code style flow, with PKCE, for a public client? How
   long do access and refresh tokens last, and can a refresh token be revoked by the user? Matters: the whole
   connection. Best: a browser opens, the person approves, the software on their PC gets a long-lived refresh token,
   with no server of ours in between.
2. **Organisations.** List them; read each one's GSTIN, state and financial year. Matters: the GSTIN check and the
   choice of organisation (like Tally's companies). Best: one call.
3. **Customers.** Search by GSTIN (`gst_no`); create one with GST treatment (business, registered), place of
   supply, billing address. Best: an exact search by GSTIN.
4. **Invoices.** Create one with **our number** (switch off auto numbering for that invoice) or let Zoho number it;
   date; one line with the commission and its SAC; tax (CGST + SGST vs IGST: tax groups vs single taxes); place of
   supply. Read it back. Matters: everything. Best: our number kept exactly, tax right with no setup.
5. **Never twice.** Where does our id go (reference number, a custom field)? Can invoices be searched by it? What
   does Zoho say to a duplicate invoice number? Best: a searchable reference field.
6. **Numbering.** Zoho's invoice series and prefixes: can we read the next number Zoho would give, and the last one
   used? Matters: own-invoice distributors (their series must match their books).
7. **The signed PDF.** Attach it to the invoice. Size limit?
8. **Status.** Draft vs sent: an imported invoice should not email the fund house. Can it be marked sent (or stay
   draft) without Zoho sending anything?
9. **Limits.** Calls per minute and per day, by plan. Does the free plan allow API access at all? Matters: a month is
   10 to 40 invoices; a first import may be a whole year.
10. **Errors.** What a refusal looks like (code, message), so the person sees Zoho's own words.

## Worth exploring (possible features later; note what's possible, build nothing)

- **Filing GSTR-1 from Zoho** (Zoho files GST returns with the GST portal): could the software end the month with
  "GSTR-1 ready" or even filed?
- **Commission received.** Fund houses pay commission after TDS (section 194H). Recording the payment, the TDS as
  receivable, and matching it to the invoice. (Tally needs the same.)
- **Bank feeds**: Zoho matching the commission credits in the bank to the invoices.
- **Credit notes** (the registrars have them too).
- **Reports** (sales by fund house, receivables, by month): the analytics we want to offer one day.
- **e-invoicing (IRN)**: only for large turnover; note whether the API supports it.
- **Several ARNs, one organisation** vs one organisation per ARN.

## The most wonderful findings, for us

- Loopback OAuth with PKCE and a long refresh token: Zoho connects like signing in to any website, nothing on our side.
- A searchable reference field and an exact customer search by GSTIN: "never twice" and "found by GSTIN" for free.
- Our number kept exactly on demand, with the next Zoho number readable: own-invoice numbering works as in Tally.
- GSTR-1 through the API: a feature no one else gives distributors.
