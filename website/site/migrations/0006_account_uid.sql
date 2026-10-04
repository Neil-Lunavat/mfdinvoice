-- uid: the account's id in the admin panel's links (/accounts/<uid>) and in a copy of its data: 16 random hex
-- characters, so the running count of accounts isn't on show. The number id stays inside (the app's server uses it).
ALTER TABLE accounts ADD COLUMN uid TEXT;
UPDATE accounts SET uid = lower(hex(randomblob(8))) WHERE uid IS NULL;
CREATE UNIQUE INDEX accounts_uid ON accounts (uid);
