-- The public list of catalogs (/libraries, /api/public-libraries) shows a
-- library only after it opts in from the panel (or the admin turns it on).
ALTER TABLE libraries ADD COLUMN public_listing INTEGER NOT NULL DEFAULT 0;
