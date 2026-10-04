-- Recovery codes: a library that lost its server key (reinstall, new
-- machine) takes its address back with the code it was given at enrollment.
-- Only the sha256 of the code is stored.
ALTER TABLE libraries ADD COLUMN recovery_hash TEXT;
