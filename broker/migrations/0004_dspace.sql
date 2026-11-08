-- No address is published by this migration. DSPACE_ENABLED must also be true.
CREATE TABLE broker_features (name TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO broker_features (name,value) VALUES ('dspace','1');
