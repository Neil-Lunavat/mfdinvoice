-- Send to support from the app goes to the software's own server now (server/), not to this database. Nothing
-- writes this table any more, and nothing reads it.
DROP TABLE reports;
