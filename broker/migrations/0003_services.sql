-- What a library publishes through its address: Koha (the catalogue and the
-- staff interface, <slug> and <slug>-admin), Tainacan (the collection,
-- <slug>-acervo), or both. Every existing library and request is Koha only,
-- so nothing changes for them.
ALTER TABLE libraries ADD COLUMN services TEXT NOT NULL DEFAULT 'koha';
ALTER TABLE libraries ADD COLUMN collection_record_id TEXT;
ALTER TABLE enrollments ADD COLUMN services TEXT NOT NULL DEFAULT 'koha';
