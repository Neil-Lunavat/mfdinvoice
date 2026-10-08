/* Everything about the business that can still change lives here, and nowhere else: the product's name, the company
   behind it, the price, the trial, where money and email go. Change a value here and every page, email and receipt
   follows. Nothing else in the code may hard-code these values. A value still in [brackets] isn't decided yet and is
   shown greyed. */

/* The product's name. It appears nowhere else in the code. */
export const NAME = 'MFDInvoice';
/* The wordmark (option B, owner 29 Sep 2026): the leading capitals strong, the rest quiet. MFD + Invoice. */
export const WORDMARK = (m => (m ? [m[1], m[2]] : [NAME, '']))(NAME.match(/^([A-Z]+)([A-Z][a-z].*)$/)) as [string, string];

/* The site's address, used for canonical URLs, Open Graph, the sitemap and robots.txt. */
export const SITE_URL = 'https://mfdinvoice.co.in';

/* false until launch: every page carries <meta name="robots" content="noindex">
   and robots.txt disallows everything. true: both go, and robots.txt points at the sitemap. */
export const INDEXING = true;

/* One yearly plan: ₹4,000 a year for the first ARN, ₹2,000 a year for each extra ARN, up to 6 ARNs on one account.
   Prices are before GST: 18% goes on top once SALES.gst is on. */
export const PRICE = { first: 4000, extra: 2000, maxArns: 6, gst: 0.18 };

/* The free trial (lib/server/trial.ts): `days` on one ARN, once per account, starting when the app adds the account's
   first ARN. An email goes out `remind` days before it ends, and another once it has. */
export const TRIAL = { days: 15, remind: 3 };

/* How we sell until the company is registered (owner, 28 Sep 2026). The card gateways (Cashfree, Razorpay) need a
   registered business, so they're parked: one ARN per email, paid by UPI to the owner and checked by hand, no GST
   (not registered), a receipt instead of a tax invoice. Set both true once the company and a gateway are ready. */
export const SALES = {
  moreArns: true,         /* false: one ARN per email; "More ARNs per email: coming soon" */
  gst: false,             /* false: no GST charged, and our document is a receipt, not a tax invoice */
};

/* UPI payments (PAYMENTS = "upi" in wrangler.jsonc): the QR on Checkout pays this ID, with the amount and the
   order's reference filled in. `notify` gets an email with the screenshot for each payment to check. */
export const UPI = {
  id: 'neillunavat3192@okicici',
  name: 'Neil Lunavat',
  refPrefix: 'MFD',
  notify: 'neillunavat3192@gmail.com',
};

/* The owner's own inbox: payments to check, and the support requests he can fix from his phone. */
export const OWNER_EMAIL = 'neillunavat3192@gmail.com';

/* The invoice numbers drawn on the home page's sample invoices (samples, not a registrar's real format).
   i is the invoice's position in the sample month (0, 1, 2 ...). */
export const invNo = (i: number) => `${74 + i}/26-27`;

export const EMAIL = {
  support: 'support@mfdinvoice.co.in',
  hello: 'hello@mfdinvoice.co.in',
  from: 'no-reply@mfdinvoice.co.in',      /* every email the site sends; replies go to support */
};

/* Our own tax invoices to buyers: PREFIX/26-27/0001, one unbroken series per financial year.
   GST allows at most 16 characters. */
export const INVOICE_PREFIX = 'MFD';
/* Receipts (no GST, while SALES.gst is false): their own series, RECEIPT_PREFIX/26-27/0001. */
export const RECEIPT_PREFIX = 'MFDI';

/* The company behind the product: on receipts and tax invoices, in the footer, and in the Terms, the Privacy policy
   and the Refund policy. Ayen Systems, a sole proprietorship of Neil Lunavat (owner, 1 Oct 2026), until it is
   registered as a private limited company: then legalName and entity change here, and nowhere else. A receipt keeps
   the details it was issued with.
   stateCode decides the tax on an invoice: CGST + SGST when the buyer's GSTIN starts with it, otherwise IGST. It is
   the first two digits of the GSTIN (27: Maharashtra). */
export const BUSINESS = {
  legalName: 'Ayen Systems',
  entity: 'a sole proprietorship of Neil Lunavat',   /* "Ayen Systems, <entity>" */
  address: 'M-16 Kumar Park, Bibwewadi Kondhwa Road, Pune 411037',
  courts: 'Pune',                       /* the courts that hear a dispute (the Terms) */
  state: 'Maharashtra',
  stateCode: '27',
  phone: '+91 75179 11229',              /* on the Terms, Privacy and Refunds pages only */
  email: 'ayensystems@gmail.com',          /* the company's own address; buyers write to EMAIL.support */
  gstin: '[GSTIN]',                       /* once registered for GST (SALES.gst) */
  sac: '[SAC]',                           /* the service's SAC code, printed on each invoice line */
  grievanceOfficer: 'Neil Lunavat',     /* the Privacy page puts EMAIL.support and the phone beside the name */
};

/* The date the Terms, the Privacy policy or the Refund policy last changed. The three pages show it as "Last
   updated", and every payment records the version it was made under. Change it whenever any of them changes. */
export const TERMS_VERSION = '2026-10-08';

/* How long the record of a run (its steps, the portals' words, the pictures of the portals' pages) is kept on the
   software's server before it is deleted. The server's daily job deletes them (server/src/index.ts, KEEP_DAYS). */
export const KEEP = { runs: '90 days' };

/* Every release of the app, newest first. `ops/release.py` writes each one, after uploading its installer: the
   version, the day, the size, the installer's sha256 (the app checks its download against it), one sentence for the
   app's update screen, and what changed. Downloads and Release notes read this list. */
export type Release = { version: string; date: string; size: string; sha256: string; note: string;
  changes: { tag: 'New' | 'Better' | 'Fixed'; text: string }[] };
export const RELEASES: Release[] = [
  /* ops/release.py writes the newest release here */
  { version: '1.0.0', date: '8 October 2026', size: 'About 87 MB',
    sha256: '60e3b50b24bb1a896f6fd97b65dedbf28e30e6414d2219bf8aca7ac05d4b7301', note: 'The first release: your CAMS and KFintech commission invoices, made, signed, submitted, and imported into the bookkeeping software of your choice.',
    changes: [{ tag: 'New', text: 'The first release: your CAMS and KFintech commission invoices, made, signed, submitted, and imported into the bookkeeping software of your choice.' }, { tag: 'New', text: 'Your ARN, name and GSTIN are read from CAMS and KFintech. Nothing is typed that the portals already know.' }, { tag: 'New', text: 'Each month\'s invoices come from CAMS, by its email (forwarded from Gmail, read with a Gmail app password, or added by hand), and from KFintech.' }, { tag: 'New', text: 'Your own invoices, numbered as GST asks, or the registrars\' own.' }, { tag: 'New', text: 'Signed with a photo of your signature, or with your DSC token.' }, { tag: 'New', text: 'Your check before anything is sent: only what you tick goes.' }, { tag: 'New', text: 'Submitted to CAMS and KFintech, and what each has is read back.' }, { tag: 'New', text: 'Tally and Zoho Books: invoice numbers come from your books, and each invoice is entered in them.' }, { tag: 'New', text: 'Downloads of any months, with every figure.' }, { tag: 'New', text: 'When CAMS or KFintech change something on their portals, we fix it on our side as fast as we can, most often without an update, so the service stays reliable.' }] },
];

/* The app's current version, which is also the oldest that may run: an older app shows only Update now (the app reads
   this from /api/app/me). Before the first release there is none to update to. */
export const APP = RELEASES[0]
  ? { version: RELEASES[0].version, sha256: RELEASES[0].sha256, note: RELEASES[0].note }
  : { version: '1.0.0', sha256: '', note: '' };

/* The installer's key in R2: the latest one replaces the one before (bun run installer; /api/download serves it). */
export const INSTALLER = `installer/${NAME}-Setup.exe`;
