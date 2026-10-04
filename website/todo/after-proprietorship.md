# After the sole proprietorship is registered

Until then: one ARN per email, paid by UPI to your personal UPI ID, checked by hand, with a receipt and no GST. That
is enough for the October tests.

## Card payments (Cashfree)
- [ ] Open a Cashfree account in the proprietorship's name. Get its two keys.
- [ ] Put the keys on the live site as secrets: `CASHFREE_APP_ID`, `CASHFREE_SECRET_KEY`.
- [ ] Test with Cashfree's test keys first (`CASHFREE_MODE: "sandbox"` in `site/wrangler.jsonc`), then switch to
  `"production"`.
- [ ] Switch new payments to Cashfree: `PAYMENTS: "cashfree"` in `site/wrangler.jsonc`. The Cashfree code is built and
  waiting; the UPI route stops taking new payments but keeps the old ones.
- [ ] Then decide what happens to the UPI code and the Payments page in the panel: keep it as a backup, or remove it.
- [ ] Cashfree asks for a mobile number at checkout. Checkout already asks for it when Cashfree is on.
- [ ] Update the Privacy page's Payments section (it says UPI checked by hand).

## Until card payments start
- [ ] If you keep taking UPI after registering, move the UPI ID to the proprietorship's bank account: `UPI` in
  `site/src/consts.ts`.

## GST, if the proprietorship registers for it
- [ ] Turn on GST: `SALES.gst = true` in `site/src/consts.ts`. Prices then get 18% on top, Checkout asks for a GSTIN,
  and buyers get tax invoices instead of receipts.
- [ ] Fill in `gstin` and `sac` in `BUSINESS` (the CA gives the SAC code).
- [ ] The CA checks the tax invoice: open any receipt in the panel to see the layout.

## Code-signing
- [ ] Ask the certificate sellers whether a proprietorship (or you as a person) can get one. If yes, sign the installer
  now and the Windows "unknown publisher" warning goes. If not, it waits for the private limited company.
