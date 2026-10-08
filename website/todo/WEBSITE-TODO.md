# The website: everything left

The one list for the website. Delete a line when it is done, a section when it is empty. Ideas parked for later are
in `IDEAS.md` at the repo root; the software's list is `TODO.md`.

## What is decided (remember these)

- **Price:** ₹4,000 a year for the first ARN, ₹2,000 a year for each extra ARN, up to 6 ARNs on an account. More than
  six: write to us (Contact). **Prices are before GST.** No GST is charged until the proprietorship is registered for
  it; the pages say nothing about GST until then.
- **An ARN added partway through the year** ends on the plan's last day and costs ₹2,000 × months left ÷ 12, part
  months counting whole (7 months left: ₹1,167).
- **One free trial per email**, 15 days, on one ARN. Deleting the account and signing up again with the same email
  gives no second trial. The same ARN under different emails is allowed.
- **An ARN is free** when it is on no running plan (trial, gift or paid). A free ARN can be bound by any account; a
  bound one cannot. When another account takes it, the old account gets an email.
- **"Software", never "app"**, in every word a person reads.
- **Business:** Ayen Systems, a sole proprietorship of Neil Lunavat, M-16 Kumar Park, Bibwewadi Kondhwa Road, Pune
  411037, Maharashtra. Courts: Pune. Grievance officer: Neil Lunavat, support@mfdinvoice.co.in, +91 75179 11229.
  GSTIN and SAC: after the proprietorship's GST registration.
- **Windows 11 only** in every claim. The exclamation mark on the home page stays.
- **The admin panel** is used on a laptop and takes the whole width; Payments must work on a phone. It shows more
  rather than less until about 50 users; then it is redesigned (`IDEAS.md`).
- **Analytics:** Cloudflare Web Analytics, no cookies.

## Before launch (8 Oct)

- [ ] The logo: white on blue on Downloads (it drew dark there); a larger tile in the header. The emails' mark is still
      the ✓ (the picture can load from mfdinvoice.co.in now). A simpler 16px favicon if the tab icon looks smudged.
- [ ] The link preview (`og.png`): Neil checks it in WhatsApp and LinkedIn's Post Inspector once live.
- [ ] The legal pages: Neil has read them; the "A draft" line goes. Acting on CAMS and KFintech sits inside their terms.
- [ ] Google Search Console with the sitemap; one Lighthouse pass on a phone (Home, Pricing,
      Downloads).
- [ ] Cloudflare Web Analytics on (Neil, in the dashboard), and its line in Privacy.
- [ ] The panel: the Deletions card says when the soonest one goes, and an account page's "Delete now"; the Software
      tab's run view, wide, text left and pictures right. Anything else the panel should show, added as it comes up.
- [ ] Neil's read of every page, desktop and phone: Home, Setup, Security, Pricing, FAQ, Downloads, Release notes,
      Contact, Support, Blog, Terms, Privacy, Refunds, 404, Sign in, Account, Checkout, a receipt.
- [ ] Every email (`bun run emails`), including: an ARN taken by another account.
- [ ] Checkout, his pass. Kept for now: no word on why there is no GST; the UPI pays his own ID; four questions.
- [ ] Release notes back to one first release, 1.0.0, in Neil's words (`ops/release.py` writes `RELEASES`; never edit
      the version or sha256 by hand: installed software reads them).
- [ ] `/setup`: one picture per step, from Neil's screenshots on the partner's PC; then his videos.
- [ ] Zoho Books and DSC signing stay claimed (Home, Pricing, FAQ): both are built.
- [ ] A default blog cover: Neil makes it.
- [ ] Follow-ups from support@, not the Gmail address: Gmail › Settings › Accounts › Send mail as › add
      support@mfdinvoice.co.in (smtp.gmail.com, 587, the Gmail address and an app password); one reaches another inbox.

Done by Neil: mail arrives (support@, hello@; no-reply@ passes DKIM and DMARC), Support › Reply, the live site end to
end on his own account. Live 8 Oct: www to the apex, indexing on, the logo fixes, the panel's deletions and run
view. After launch: `AFTER-LAUNCH.md`.

## After the sole proprietorship is registered

Until then: UPI to Neil's own ID, checked by hand, a receipt, no GST.

**Card payments (Cashfree; built and parked)**
- [ ] A Cashfree account in the proprietorship's name; its keys as secrets `CASHFREE_APP_ID`, `CASHFREE_SECRET_KEY`.
- [ ] Test with the sandbox keys (`CASHFREE_MODE: "sandbox"`), then `"production"`.
- [ ] `PAYMENTS: "cashfree"` in `wrangler.jsonc`. UPI stops taking new payments and keeps the old ones. Checkout then
      asks for a mobile number (built).
- [ ] Decide: keep the UPI code and the panel's Payments page as a backup, or remove them.
- [ ] Words that say UPI and screenshots: Privacy ("Payments", "What this website keeps"), Terms ("Plans and
      payment"), Refunds ("How to ask"). Change them to Cashfree.
- [ ] Until Cashfree: if UPI goes on after registering, `UPI` in `consts.ts` moves to the business's bank account.

**GST (if the proprietorship registers for it)**
- [ ] `SALES.gst = true` in `consts.ts`: 18% on top, Checkout asks for a GSTIN, buyers get tax invoices, and the
      Terms and FAQ lines about "not registered for GST" switch by themselves.
- [ ] `gstin` and `sac` in `BUSINESS` (the CA gives the SAC).
- [ ] Pricing: a "+ 18% GST" line that shows only when `SALES.gst` is on. Same check on Checkout and the receipt.
- [ ] The CA checks the tax invoice's layout (open any receipt in the panel). `TERMS_VERSION` moves.

**Code signing**
- [ ] Ask the certificate sellers whether a proprietorship (or Neil as a person) can get one. If yes: sign the
      installer, and the Setup page's "Windows protected your PC · More info · Run anyway" goes.

## After the private limited company is registered

- [ ] `legalName` ("Ayen Systems Private Limited") and `entity` in `BUSINESS`. Every page, the footer and new receipts
      follow; old receipts keep the old name.
- [ ] The company's GSTIN, address and bank in `BUSINESS`; the payment provider's account moves to the company.
- [ ] `TERMS_VERSION` moves; the legal pages are read once more. Code signing, if it waited.
