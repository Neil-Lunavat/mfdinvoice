-- note_shared: 1 when the owner ticked "Send the reason to them" on a rejection; Checkout then shows the reason too.
ALTER TABLE orders ADD COLUMN note_shared INTEGER NOT NULL DEFAULT 0;
