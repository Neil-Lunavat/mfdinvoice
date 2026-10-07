-- The one reply sent from the panel's Support tab (Reply): when, and by whom. The rest of the conversation happens in
-- the support@ mailbox.
ALTER TABLE requests ADD COLUMN replied_at TEXT;
ALTER TABLE requests ADD COLUMN replied_by TEXT;
