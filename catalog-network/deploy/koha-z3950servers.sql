-- Koha's row for the koha.nexus Catalog Network (Administration >
-- Z39.50/SRU servers). Run it on the Koha server, INSTANCE being the Koha
-- instance's name:
--   sudo koha-mysql INSTANCE < koha-z3950servers.sql
-- The koha.nexus panel does the same with its "Rede koha.nexus" switch
-- (Z39.50 / SRU servers screen). Change catalog.koha.nexus if the tunnel's
-- hostname is another one: Koha talks HTTPS when the host starts with https://.
-- Safe to run again: a row already there (same address, else same name) is
-- updated in place and keeps its tick and rank; otherwise it is inserted.
SET @kei_t0 := (SELECT id FROM z3950servers WHERE recordtype = 'biblio'
                 AND host = 'https://catalog.koha.nexus' AND port = 443 ORDER BY id LIMIT 1);
SET @kei_t0 := IFNULL(@kei_t0, (SELECT id FROM z3950servers WHERE recordtype = 'biblio'
                 AND servername = 'Rede koha.nexus (Catalogação Compartilhada)' ORDER BY id LIMIT 1));
UPDATE z3950servers
   SET host = 'https://catalog.koha.nexus', port = 443, db = 'sru',
       servername = 'Rede koha.nexus (Catalogação Compartilhada)', syntax = 'MARC21', encoding = 'utf8',
       timeout = 15, servertype = 'sru',
       sru_fields = 'title=dc.title,isbn=dc.isbn,author=dc.creator,issn=dc.issn,subject=dc.subject,srchany=cql.serverChoice',
       sru_options = 'sru=get,sru_version=1.1'
 WHERE id = @kei_t0;
DELETE FROM z3950servers
 WHERE recordtype = 'biblio' AND id <> IFNULL(@kei_t0, 0)
   AND (servername = 'Rede koha.nexus (Catalogação Compartilhada)'
        OR (host = 'https://catalog.koha.nexus' AND port = 443));
INSERT INTO z3950servers (host, port, db, servername, checked, `rank`, syntax, encoding, timeout,
                          servertype, recordtype, sru_fields, sru_options, add_xslt)
SELECT 'https://catalog.koha.nexus', 443, 'sru', 'Rede koha.nexus (Catalogação Compartilhada)', 1, 1,
       'MARC21', 'utf8', 15, 'sru', 'biblio',
       'title=dc.title,isbn=dc.isbn,author=dc.creator,issn=dc.issn,subject=dc.subject,srchany=cql.serverChoice',
       'sru=get,sru_version=1.1', ''
  FROM DUAL WHERE @kei_t0 IS NULL;
