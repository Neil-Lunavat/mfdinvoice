-- The free trial (src/lib/server/trial.ts).

-- A plan's source gains 'trial'. SQLite can't change a CHECK, so the table is rebuilt.
CREATE TABLE plans_next (
  account_id INTEGER PRIMARY KEY REFERENCES accounts (id) ON DELETE CASCADE,
  slots      INTEGER NOT NULL CHECK (slots BETWEEN 1 AND 6),
  starts_on  TEXT NOT NULL,
  ends_on    TEXT NOT NULL,
  source     TEXT NOT NULL CHECK (source IN ('paid', 'grant', 'trial')),
  updated_at TEXT NOT NULL
);
INSERT INTO plans_next SELECT account_id, slots, starts_on, ends_on, source, updated_at FROM plans;
DROP TABLE plans;
ALTER TABLE plans_next RENAME TO plans;

-- Every ARN that has had a free trial, and the email it was on. Never deleted, not even with the account: it is what
-- makes a trial once per ARN.
CREATE TABLE trials (
  arn        TEXT PRIMARY KEY,
  email      TEXT NOT NULL,
  started_at TEXT NOT NULL
);
