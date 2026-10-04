-- A trial is once per account, no longer once per ARN: the same ARN may start one again under another email.
-- `trials` stops being the rule and becomes the record: one row per trial started, never deleted, not even with the
-- account. How often an ARN has been through a free trial, and under which emails:
--   SELECT arn, COUNT(*) AS trials, group_concat(email, ', ') AS emails FROM trials GROUP BY arn HAVING COUNT(*) > 1;
CREATE TABLE trials_next (
  id         INTEGER PRIMARY KEY,
  arn        TEXT NOT NULL,
  email      TEXT NOT NULL,
  started_at TEXT NOT NULL
);
INSERT INTO trials_next (arn, email, started_at) SELECT arn, email, started_at FROM trials;
DROP TABLE trials;
ALTER TABLE trials_next RENAME TO trials;
CREATE INDEX trials_arn ON trials (arn);
