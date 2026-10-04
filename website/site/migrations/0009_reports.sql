-- A problem (or an idea) sent from the app: Send to support. Not a conversation: nobody is answered from here. It is
-- how we learn that something broke, with what the app knew when it did.
CREATE TABLE reports (
  id         INTEGER PRIMARY KEY,
  account_id INTEGER REFERENCES accounts (id) ON DELETE CASCADE,
  kind       TEXT NOT NULL CHECK (kind IN ('problem', 'idea')),
  arn        TEXT,           -- the ARN on screen, if one was set up
  message    TEXT,           -- the person's own words
  place      TEXT,           -- where in the app it was sent from
  version    TEXT,           -- the app's version
  pc         TEXT,           -- the PC: its name, Windows version, memory, free disk
  log        TEXT,           -- the app's latest log lines (never a password, the signature or the mailbox)
  created_at TEXT NOT NULL
);
CREATE INDEX reports_account ON reports (account_id);
CREATE INDEX reports_created ON reports (created_at);
