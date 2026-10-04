-- sent_at: when the UPI screenshot arrived. unblocked_at: when the owner let a rejected buyer pay again; until then a
-- rejected payment stops that account paying by UPI (Checkout sends them to support).
ALTER TABLE orders ADD COLUMN sent_at TEXT;
ALTER TABLE orders ADD COLUMN unblocked_at TEXT;

-- email: so someone who signs in again is told their old account was deleted. deleted_by: 'buyer' (their own
-- "Delete my account", after the day's wait) or the admin's email (deleted at once from the panel).
ALTER TABLE deletions ADD COLUMN email TEXT;
ALTER TABLE deletions ADD COLUMN deleted_by TEXT;
CREATE INDEX deletions_email ON deletions (email);
