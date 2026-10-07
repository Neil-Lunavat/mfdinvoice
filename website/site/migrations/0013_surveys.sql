-- Surveys made in the panel (Survey › Software) and answered in the software, on Overview. The checkout's own
-- questions stay as they are (lib/survey.ts, the `answers` table; Survey › Website).
-- questions: JSON, [{ key, q, type: 'one' | 'many' | 'text', options: [text], other: bool }] (lib/surveys.ts).
-- state: draft (being written), live (the software asks it), closed (asked no more; its answers stay).
CREATE TABLE surveys (
  id         INTEGER PRIMARY KEY,
  title      TEXT NOT NULL,
  questions  TEXT NOT NULL,
  state      TEXT NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'live', 'closed')),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  live_at    TEXT,
  closed_at  TEXT
);
-- One row per account per survey: its answers (JSON, { key: { picked: [text], text } }), or NULL when the person
-- closed the toast with its X (that survey is never asked again).
CREATE TABLE survey_replies (
  survey_id  INTEGER NOT NULL REFERENCES surveys (id),
  account_id INTEGER NOT NULL,
  answers    TEXT,
  at         TEXT NOT NULL,
  PRIMARY KEY (survey_id, account_id)
);
CREATE INDEX survey_replies_account ON survey_replies (account_id);
