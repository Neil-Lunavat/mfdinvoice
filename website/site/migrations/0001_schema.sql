-- The website's database: accounts, sign-in, plans, ARNs, payments, receipts, gifts, support, the blog.
-- Times are ISO strings in UTC ('2026-09-26T14:05:00.000Z'); plan days are India calendar days ('2027-09-26');
-- money is in paise. Emails are stored as util.ts cleanEmail makes them (lower case, aliases removed).

-- One account per email. Billing details live here and go with the account.
-- AUTOINCREMENT: an id is never reused, so a deleted account's id can't come back as someone else's.
-- uid: added in 0006 (the panel's links).
-- delete_after: "Delete my account" sets it a day ahead ("Keep my account" clears it); the daily job deletes after it.
CREATE TABLE accounts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  email        TEXT NOT NULL UNIQUE,
  created_at   TEXT NOT NULL,
  bill_name    TEXT,
  bill_gstin   TEXT,
  bill_address TEXT,
  phone        TEXT,
  delete_after TEXT
);

-- Sign-in codes: only the hash is kept. 10 minutes, 3 tries. Cleared daily.
CREATE TABLE codes (
  id         INTEGER PRIMARY KEY,
  email      TEXT NOT NULL,
  hash       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  tries_left INTEGER NOT NULL DEFAULT 3,
  used_at    TEXT,
  ip         TEXT
);
CREATE INDEX codes_email ON codes (email, created_at);

-- Rate limits: one row per hit on a key ('code:<ip>', 'try:<ip>', 'support:<account>'), counted over the last hour.
-- Cleared daily.
CREATE TABLE hits (
  key TEXT NOT NULL,
  at  TEXT NOT NULL
);
CREATE INDEX hits_key ON hits (key, at);

-- Sessions: a browser cookie (kind 'web') or the app's token (kind 'app'). Only the hash is kept.
CREATE TABLE sessions (
  id         INTEGER PRIMARY KEY,
  hash       TEXT NOT NULL UNIQUE,
  account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
  kind       TEXT NOT NULL CHECK (kind IN ('web', 'app')),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  last_seen  TEXT NOT NULL
);
CREATE INDEX sessions_account ON sessions (account_id);

-- The plan an account has now: how many ARN slots and the last day it runs. One row per account, updated in place by a
-- payment or a gift. source: 'paid' or 'grant' (a gift). What each payment and gift was is in orders and gifts.
CREATE TABLE plans (
  account_id INTEGER PRIMARY KEY REFERENCES accounts (id) ON DELETE CASCADE,
  slots      INTEGER NOT NULL CHECK (slots BETWEEN 1 AND 6),
  starts_on  TEXT NOT NULL,
  ends_on    TEXT NOT NULL,
  source     TEXT NOT NULL CHECK (source IN ('paid', 'grant')),
  updated_at TEXT NOT NULL
);

-- The ARNs filling an account's slots. The app's server binds an ARN on its first run (/api/brain/bind), with the
-- holder's name as the app read it. An ARN belongs to one account only. (bound_at is dropped in 0003.)
CREATE TABLE arns (
  arn        TEXT PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
  holder     TEXT NOT NULL,
  bound_at   TEXT NOT NULL
);
CREATE INDEX arns_account ON arns (account_id);

-- Every purchase. Amounts are worked out on the server. Kept when the account is deleted.
-- provider: who took the money ('upi' now; 'cashfree' and 'razorpay' are parked). kind 'new' = a plan of `arns`
-- slots; 'add' = `arns` more slots, each charged for `months` (the months left on the plan).
-- status: created → review (a UPI screenshot sent, waiting for the owner) → paid or rejected.
-- claim: a one-off value written by whichever request completes the order, so it applies once.
-- terms: the TERMS_VERSION (consts.ts) the order was made under.
CREATE TABLE orders (
  id           TEXT PRIMARY KEY,
  provider     TEXT NOT NULL CHECK (provider IN ('upi', 'cashfree', 'razorpay')),
  account_id   INTEGER REFERENCES accounts (id) ON DELETE SET NULL,
  email        TEXT NOT NULL,
  phone        TEXT,
  kind         TEXT NOT NULL CHECK (kind IN ('new', 'add')),
  arns         INTEGER NOT NULL,
  months       INTEGER CHECK (months BETWEEN 1 AND 12),
  subtotal     INTEGER NOT NULL,
  gst          INTEGER NOT NULL,
  total        INTEGER NOT NULL,
  bill_name    TEXT NOT NULL,
  bill_gstin   TEXT,
  bill_address TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'review', 'paid', 'rejected')),
  payment_id   TEXT,
  claim        TEXT,
  utr          TEXT,
  proof        TEXT,
  terms        TEXT,
  created_at   TEXT NOT NULL,
  paid_at      TEXT,
  reviewed_at  TEXT,
  review_note  TEXT
);
CREATE INDEX orders_account ON orders (account_id);
CREATE INDEX orders_status ON orders (status);

-- Our receipts and tax invoices to buyers. One per paid order. Never deleted.
-- doc 'receipt' (no GST charged; RECEIPT_PREFIX in consts.ts) or 'tax' (INVOICE_PREFIX); each has its own unbroken series
-- per financial year: MFDI/26-27/0001.
-- The buyer's and seller's details are copied on as they were when it was issued.
CREATE TABLE invoices (
  number        TEXT PRIMARY KEY,
  doc           TEXT NOT NULL CHECK (doc IN ('tax', 'receipt')),
  fy            TEXT NOT NULL,
  seq           INTEGER NOT NULL,
  order_id      TEXT NOT NULL UNIQUE REFERENCES orders (id),
  account_id    INTEGER REFERENCES accounts (id) ON DELETE SET NULL,
  issued_at     TEXT NOT NULL,
  email         TEXT NOT NULL,
  buyer_name    TEXT NOT NULL,
  buyer_gstin   TEXT,
  buyer_address TEXT NOT NULL,
  buyer_state   TEXT,
  seller        TEXT NOT NULL,
  lines         TEXT NOT NULL,
  subtotal      INTEGER NOT NULL,
  cgst          INTEGER NOT NULL,
  sgst          INTEGER NOT NULL,
  igst          INTEGER NOT NULL,
  total         INTEGER NOT NULL,
  UNIQUE (doc, fy, seq)
);
CREATE INDEX invoices_account ON invoices (account_id);
CREATE INDEX invoices_issued ON invoices (issued_at);

-- A free plan given to an email from the admin panel: `years` on `arns` ARNs. It starts the day that email signs in
-- (or at once, if it has an account without an active plan), exactly once (`claim`, as for orders). Never a sale.
CREATE TABLE gifts (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  email      TEXT NOT NULL,
  arns       INTEGER NOT NULL DEFAULT 1 CHECK (arns BETWEEN 1 AND 6),
  years      INTEGER NOT NULL DEFAULT 1,
  given_at   TEXT NOT NULL,
  given_by   TEXT NOT NULL,
  used_at    TEXT,
  account_id INTEGER REFERENCES accounts (id) ON DELETE SET NULL,
  claim      TEXT,
  revoked_at TEXT,
  revoked_by TEXT
);
CREATE INDEX gifts_email ON gifts (email);

-- The activity log: what changed, who did it (an admin's email, 'buyer', 'writer:<email>' or 'system'), on which
-- account, and a reference (an order, receipt, gift, ARN, request or post). Written in the same batch as the change.
CREATE TABLE events (
  id         INTEGER PRIMARY KEY,
  at         TEXT NOT NULL,
  actor      TEXT NOT NULL,
  action     TEXT NOT NULL,
  account_id INTEGER,
  ref        TEXT,
  note       TEXT
);
CREATE INDEX events_account ON events (account_id, at);

-- Support requests about the website, sent by a signed-in account; the conversation then happens by email.
-- id: a random 6-digit number. files: the screenshots' keys in R2 (support/…), a JSON array.
-- topic 'data' is a copy of the account's data: the hourly job emails it at due_at, then marks it solved.
CREATE TABLE requests (
  id         INTEGER PRIMARY KEY,
  account_id INTEGER REFERENCES accounts (id) ON DELETE CASCADE,
  email      TEXT NOT NULL,
  topic      TEXT NOT NULL,
  arn        TEXT,
  new_email  TEXT,
  message    TEXT,
  files      TEXT NOT NULL DEFAULT '[]',
  status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'solved')),
  created_at TEXT NOT NULL,
  due_at     TEXT,
  solved_at  TEXT,
  solved_by  TEXT
);
CREATE INDEX requests_account ON requests (account_id);
CREATE INDEX requests_status ON requests (status, created_at);

-- Survey answers: one row per answer, so a new question or a new survey needs no schema change.
-- survey: which set of questions ('after_payment'); question: its key; answer: an option's key, or text for "other".
CREATE TABLE answers (
  account_id INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
  survey     TEXT NOT NULL,
  question   TEXT NOT NULL,
  answer     TEXT NOT NULL,
  at         TEXT NOT NULL,
  PRIMARY KEY (account_id, survey, question)
);
CREATE INDEX answers_survey ON answers (survey, question, answer);

-- Deleted accounts, for the app's server to delete their runs too (/api/brain/deleted).
CREATE TABLE deletions (
  account_id INTEGER NOT NULL,
  deleted_at TEXT NOT NULL
);
CREATE INDEX deletions_at ON deletions (deleted_at);

-- The blog. A post is live once saved; the editor saves, edits and deletes. Its address is /blog/<cluster slug>/<slug>.
-- faq: [{ q, a }] as JSON. cover: an image key in R2 (blog/…).
CREATE TABLE posts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  slug        TEXT NOT NULL UNIQUE,
  cluster     TEXT NOT NULL,
  title       TEXT NOT NULL,
  description TEXT NOT NULL,
  body        TEXT NOT NULL,
  faq         TEXT NOT NULL DEFAULT '[]',
  author      TEXT,
  cover       TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
