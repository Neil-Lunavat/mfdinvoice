-- One PC per account: the software is signed in on one PC at a time. An app session carries the PC's name; when
-- another PC signs in (and the person agrees), the old session is ended, not deleted, so that PC learns who took over.
-- device: the PC's name (app sessions). ended_at / ended_by: when it was signed out, and by which PC (null if unnamed).
ALTER TABLE sessions ADD COLUMN device TEXT;
ALTER TABLE sessions ADD COLUMN ended_at TEXT;
ALTER TABLE sessions ADD COLUMN ended_by TEXT;
