-- The nightly clean-up finds expired sessions, the nightly deletions find accounts past delete_after, and the Sales page
-- finds a month's orders: an index each, so they don't read the whole table.
CREATE INDEX sessions_expires ON sessions (expires_at);
CREATE INDEX accounts_delete_after ON accounts (delete_after) WHERE delete_after IS NOT NULL;
CREATE INDEX orders_created ON orders (created_at);
