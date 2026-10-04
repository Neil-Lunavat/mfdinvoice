# Tally import: what the app does, for a CA to check

MFDInvoice puts a month's commission invoices into the TallyPrime open on the distributor's PC, through Tally's own
XML server (port 9000). Each line below is something the app decides. Mark any that a CA would do differently.

## Which company, which ledgers
1. **Company.** The one open in TallyPrime. If several are open, the person picks one; it is remembered per ARN.
   A warning shows when the company's GSTIN in Tally differs from the one in the app.
2. **Fund house (party) ledger.** Found by the fund house's GSTIN on its ledger, never by name. If several ledgers
   carry the GSTIN, the one under Sundry Debtors that already has invoices; otherwise the person is asked once.
3. **Missing fund house.** A new ledger is made under **Sundry Debtors**, with its GSTIN, registration Regular, its
   state as place of supply, and **bill-by-bill** turned on.
4. **Sales ledger.** The one used on that fund house's last invoice in Tally. If it has none, the person picks one of
   the Sales Accounts ledgers (asked once, remembered). The app never makes a sales ledger.
5. **GST ledgers.** The CGST, SGST and IGST ledgers the company's invoices already use; else the only one with that
   tax and rate. If no IGST ledger exists and an invoice needs one, "Output IGST @ 18%" is made under Duties & Taxes.

## The invoice itself
6. **Voucher type.** The Sales type the company's latest invoice used.
7. **Date.** The date printed on the registrar's invoice.
8. **Figures.** Taxable value, CGST, SGST, IGST exactly as on the registrar's invoice, to the paisa. The party is
   debited with the total.
9. **Reference.** The registrar's invoice reference, in Tally's Reference field.
10. **Narration.** "CAMS <reference>, <month>" (on the distributor's own invoices: "Invoice <number> (CAMS
    <reference>), <month>").
11. **Tax off by paise.** When the registrar's GST differs from exactly 9% / 18% by paise, the invoice is marked
    accepted ("Accept As Is"), so GSTR-1 does not list it as uncertain.
12. **Bill.** On a bill-by-bill ledger, a New Ref bill named after the invoice's number in Tally, so the bank receipt
    can be set against it.

## Numbers
13. **Automatic numbering** (Tally's default): Tally gives the number and ignores any sent. The app works out the
    numbers Tally will give before anything goes in, imports in that order, and reads them back.
14. **Manual numbering:** the app asks "your last invoice number in Tally" and sends the next ones.
15. **Submitted only, or all.** "Submitted only" is the default. With "All", the submitted ones go first and the rest
    take the numbers after them, and keep those numbers when they are submitted later.
16. **The distributor's own invoices.** The number printed on the PDF uploaded to the registrar must be the number in
    Tally. Before a run, Tally's last number is shown beside the app's for the person to confirm. If someone types an
    invoice in Tally between Submit and the import, Tally's numbers will differ; the app shows each difference and the
    button reads "Import anyway". It cannot change Tally's numbers from outside.

## Safety
17. **Never twice.** Each invoice carries the app's own id; one already in the books is skipped and shown with its
    number.
18. **Typed by hand already.** An invoice to the same fund house, in the same month, within ₹1 of the total, not put
    in by the app, is held back and shown. On the person's tick it is changed to the registrar's exact figures,
    keeping its number and its bill.
19. **No undo.** Nothing is deleted in Tally (a deleted invoice leaves a gap in the numbering for good). The screen
    shows everything that will happen before the one Import button.

## Not covered yet
- Tally on another PC (a CA's office), a company with a password, ports other than 9000, Tally ERP 9 and TallyPrime
  older than 7.1.
- IGST on the distributor's own invoices (set aside for now).
