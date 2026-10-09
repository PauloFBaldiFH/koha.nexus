-- Koha's row for the koha.nexus Catalog Network (Administration >
-- Z39.50/SRU servers). Run it on the Koha server, INSTANCE being the Koha
-- instance's name:
--   sudo koha-mysql INSTANCE < koha-z3950servers.sql
-- The koha.nexus panel does the same with its "Rede koha.nexus" switch
-- (Z39.50 / SRU servers screen). Change catalog.koha.nexus if the tunnel's
-- hostname is another one: Koha talks HTTPS when the host starts with https://.
DELETE FROM z3950servers
 WHERE recordtype = 'biblio' AND servername = 'Rede koha.nexus (Catalogação Compartilhada)';
INSERT INTO z3950servers (host, port, db, servername, checked, `rank`, syntax, encoding, timeout,
                          servertype, recordtype, sru_fields, sru_options, add_xslt)
VALUES ('https://catalog.koha.nexus', 443, 'sru', 'Rede koha.nexus (Catalogação Compartilhada)', 1, 1,
        'MARC21', 'utf8', 15, 'sru', 'biblio',
        'title=dc.title,isbn=dc.isbn,author=dc.creator,issn=dc.issn,subject=dc.subject,srchany=cql.serverChoice',
        'sru=get,sru_version=1.1', '');
