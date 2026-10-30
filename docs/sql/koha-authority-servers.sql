-- Koha's three authority servers (Administration > Z39.50/SRU servers) and
-- the Biblioteca Nacional's dead Z39.50 rows unticked. Run it on the Koha
-- server, INSTANCE being the Koha instance's name:
--   sudo koha-mysql INSTANCE < koha-authority-servers.sql
-- The panel does the same with the blue "Update" (Atualizar) button on the
-- Z39.50 / SRU screen, before it tests the list, and config.sh at install
-- (--task z3950-seed). Generated from the installer's z3950_auth_rows,
-- z3950_upsert_sql add and z3950_dead_sql; tests/z3950.bats checks it.
--
-- Safe to run again: a server already there (same host, port and database,
-- else the same name, among the authority rows) gets these settings and
-- keeps its tick and rank; otherwise it is inserted. Rows on 200.20.12.18
-- or 162.214.168.248 are unticked, never deleted. The last line shows how
-- many rows were added, updated and unticked.
SET NAMES utf8mb4;
SET @kei_claimed := '';
SET @kei_t0 := (SELECT id FROM z3950servers WHERE recordtype = 'authority' AND FIND_IN_SET(id, @kei_claimed) = 0 AND host = 'lx2.loc.gov' AND port = 210 AND IFNULL(db,'') = 'NAF' ORDER BY id LIMIT 1);
SET @kei_claimed := CONCAT_WS(',', NULLIF(@kei_claimed, ''), @kei_t0);
SET @kei_t1 := (SELECT id FROM z3950servers WHERE recordtype = 'authority' AND FIND_IN_SET(id, @kei_claimed) = 0 AND host = 'lx2.loc.gov' AND port = 210 AND IFNULL(db,'') = 'SAF' ORDER BY id LIMIT 1);
SET @kei_claimed := CONCAT_WS(',', NULLIF(@kei_claimed, ''), @kei_t1);
SET @kei_t2 := (SELECT id FROM z3950servers WHERE recordtype = 'authority' AND FIND_IN_SET(id, @kei_claimed) = 0 AND host = 'https://sru.koha.nexus' AND port = 443 AND IFNULL(db,'') = 'sru/bn-aut' ORDER BY id LIMIT 1);
SET @kei_claimed := CONCAT_WS(',', NULLIF(@kei_claimed, ''), @kei_t2);
SET @kei_t0 := IFNULL(@kei_t0, (SELECT id FROM z3950servers WHERE recordtype = 'authority' AND FIND_IN_SET(id, @kei_claimed) = 0 AND servername = 'BIBLIOTECA DOS NOMES DO CONGRESSO' ORDER BY id LIMIT 1));
SET @kei_claimed := CONCAT_WS(',', NULLIF(@kei_claimed, ''), @kei_t0);
SET @kei_t1 := IFNULL(@kei_t1, (SELECT id FROM z3950servers WHERE recordtype = 'authority' AND FIND_IN_SET(id, @kei_claimed) = 0 AND servername = 'BIBLIOTECA DOS ASSUNTOS DO CONGRESSO' ORDER BY id LIMIT 1));
SET @kei_claimed := CONCAT_WS(',', NULLIF(@kei_claimed, ''), @kei_t1);
SET @kei_t2 := IFNULL(@kei_t2, (SELECT id FROM z3950servers WHERE recordtype = 'authority' AND FIND_IN_SET(id, @kei_claimed) = 0 AND servername = 'BIBLIOTECA NACIONAL (AUTORIDADES)' ORDER BY id LIMIT 1));
SET @kei_claimed := CONCAT_WS(',', NULLIF(@kei_claimed, ''), @kei_t2);
SET @kei_added := 0, @kei_updated := 0;
UPDATE z3950servers SET host = 'lx2.loc.gov', port = 210, db = 'NAF', syntax = 'USMARC', encoding = 'utf8', timeout = 10, servertype = 'zed', sru_fields = '', sru_options = '', userid = IF('' = '', userid, ''), password = IF('' = '', password, '') WHERE id = @kei_t0;
SET @kei_updated := @kei_updated + GREATEST(ROW_COUNT(), 0);
INSERT INTO z3950servers (host, port, db, userid, password, servername, checked, `rank`, syntax, timeout, servertype, encoding, recordtype, sru_fields, sru_options, add_xslt) SELECT 'lx2.loc.gov', 210, 'NAF', '', '', 'BIBLIOTECA DOS NOMES DO CONGRESSO', 1, 1, 'USMARC', 10, 'zed', 'utf8', 'authority', '', '', '' FROM DUAL WHERE @kei_t0 IS NULL AND NOT EXISTS (SELECT 1 FROM z3950servers WHERE recordtype = 'authority' AND host = 'lx2.loc.gov' AND port = 210 AND IFNULL(db,'') = 'NAF');
SET @kei_added := @kei_added + GREATEST(ROW_COUNT(), 0);
UPDATE z3950servers SET host = 'lx2.loc.gov', port = 210, db = 'SAF', syntax = 'USMARC', encoding = 'utf8', timeout = 10, servertype = 'zed', sru_fields = '', sru_options = '', userid = IF('' = '', userid, ''), password = IF('' = '', password, '') WHERE id = @kei_t1;
SET @kei_updated := @kei_updated + GREATEST(ROW_COUNT(), 0);
INSERT INTO z3950servers (host, port, db, userid, password, servername, checked, `rank`, syntax, timeout, servertype, encoding, recordtype, sru_fields, sru_options, add_xslt) SELECT 'lx2.loc.gov', 210, 'SAF', '', '', 'BIBLIOTECA DOS ASSUNTOS DO CONGRESSO', 1, 2, 'USMARC', 10, 'zed', 'utf8', 'authority', '', '', '' FROM DUAL WHERE @kei_t1 IS NULL AND NOT EXISTS (SELECT 1 FROM z3950servers WHERE recordtype = 'authority' AND host = 'lx2.loc.gov' AND port = 210 AND IFNULL(db,'') = 'SAF');
SET @kei_added := @kei_added + GREATEST(ROW_COUNT(), 0);
UPDATE z3950servers SET host = 'https://sru.koha.nexus', port = 443, db = 'sru/bn-aut', syntax = 'MARC21', encoding = 'utf8', timeout = 30, servertype = 'sru', sru_fields = 'nameany=dc.creator,authorany=dc.creator,authorpersonal=bath.personalName,authorcorp=bath.corporateName,authormeetingcon=bath.conferenceName,srchany=cql.serverChoice', sru_options = 'sru=get,sru_version=1.1', userid = IF('' = '', userid, ''), password = IF('' = '', password, '') WHERE id = @kei_t2;
SET @kei_updated := @kei_updated + GREATEST(ROW_COUNT(), 0);
INSERT INTO z3950servers (host, port, db, userid, password, servername, checked, `rank`, syntax, timeout, servertype, encoding, recordtype, sru_fields, sru_options, add_xslt) SELECT 'https://sru.koha.nexus', 443, 'sru/bn-aut', '', '', 'BIBLIOTECA NACIONAL (AUTORIDADES)', 1, 3, 'MARC21', 30, 'sru', 'utf8', 'authority', 'nameany=dc.creator,authorany=dc.creator,authorpersonal=bath.personalName,authorcorp=bath.corporateName,authormeetingcon=bath.conferenceName,srchany=cql.serverChoice', 'sru=get,sru_version=1.1', '' FROM DUAL WHERE @kei_t2 IS NULL AND NOT EXISTS (SELECT 1 FROM z3950servers WHERE recordtype = 'authority' AND host = 'https://sru.koha.nexus' AND port = 443 AND IFNULL(db,'') = 'sru/bn-aut');
SET @kei_added := @kei_added + GREATEST(ROW_COUNT(), 0);
UPDATE z3950servers SET checked = 0 WHERE checked <> 0 AND host IN ('200.20.12.18', 'http://200.20.12.18', 'https://200.20.12.18', 'z3950://200.20.12.18', '162.214.168.248', 'http://162.214.168.248', 'https://162.214.168.248', 'z3950://162.214.168.248');
SET @kei_unchecked := GREATEST(ROW_COUNT(), 0);
SELECT @kei_added AS added, @kei_updated AS updated, @kei_unchecked AS unticked;
