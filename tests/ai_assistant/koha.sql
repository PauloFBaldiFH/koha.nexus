CREATE TABLE biblio (biblionumber INTEGER PRIMARY KEY, title TEXT, subtitle TEXT, author TEXT, seriestitle TEXT, copyrightdate INTEGER, abstract TEXT, notes TEXT, datecreated TEXT);
CREATE TABLE biblio_metadata (id INTEGER PRIMARY KEY, biblionumber INTEGER, format TEXT, schema TEXT, metadata TEXT);
CREATE TABLE biblioitems (biblioitemnumber INTEGER PRIMARY KEY, biblionumber INTEGER, isbn TEXT, publishercode TEXT);
CREATE TABLE items (itemnumber INTEGER PRIMARY KEY, biblionumber INTEGER, barcode TEXT, homebranch TEXT, itemcallnumber TEXT, onloan TEXT);
CREATE TABLE borrowers (borrowernumber INTEGER PRIMARY KEY, cardnumber TEXT, firstname TEXT, surname TEXT, categorycode TEXT, branchcode TEXT, email TEXT, phone TEXT, dateenrolled TEXT, dateexpiry TEXT, lastseen TEXT, password TEXT);
CREATE TABLE issues (issue_id INTEGER PRIMARY KEY, borrowernumber INTEGER, itemnumber INTEGER, issuedate TEXT, date_due TEXT);
CREATE TABLE accountlines (accountlines_id INTEGER PRIMARY KEY, borrowernumber INTEGER, amount REAL, amountoutstanding REAL, debit_type_code TEXT, description TEXT);
CREATE TABLE saved_sql (id INTEGER PRIMARY KEY, report_name TEXT, notes TEXT, savedsql TEXT);
CREATE TABLE reserves (reserve_id INTEGER PRIMARY KEY, borrowernumber INTEGER, biblionumber INTEGER, branchcode TEXT, priority INTEGER, found TEXT, reservedate TEXT);
CREATE TABLE old_issues (issue_id INTEGER PRIMARY KEY, borrowernumber INTEGER, itemnumber INTEGER, issuedate TEXT, date_due TEXT, returndate TEXT);
CREATE TABLE branches (branchcode TEXT PRIMARY KEY, branchname TEXT, branchaddress1 TEXT, branchcity TEXT, branchphone TEXT, branchemail TEXT, branchurl TEXT);
CREATE TABLE library_hours (library_id TEXT, day INTEGER, open_time TEXT, close_time TEXT);
CREATE TABLE repeatable_holidays (id INTEGER PRIMARY KEY, branchcode TEXT, weekday INTEGER, day INTEGER, month INTEGER, title TEXT);
CREATE TABLE special_holidays (id INTEGER PRIMARY KEY, branchcode TEXT, day INTEGER, month INTEGER, year INTEGER, isexception INTEGER, title TEXT);
CREATE TABLE systempreferences (variable TEXT PRIMARY KEY, value TEXT, explanation TEXT, type TEXT);
INSERT INTO biblio VALUES (1,'It','a novel','King, Stephen',NULL,1986,'Seven friends face Pennywise the dancing clown.',NULL,'2026-01-10'),
 (2,'A coisa',NULL,'King, Stephen',NULL,2014,'Edição brasileira de It: o palhaço Pennywise aterroriza Derry.',NULL,'2026-09-20'),
 (3,'Dom Casmurro',NULL,'Assis, Machado de',NULL,1899,NULL,NULL,'2025-05-01'),
 (4,'O pequeno príncipe',NULL,'Saint-Exupéry, Antoine de',NULL,1943,NULL,NULL,'2026-09-25'),
 (5,'Drop dead gorgeous','a mystery','Smith, Jane',NULL,2001,NULL,NULL,'2024-01-01'),
 (6,'Coraline',NULL,'Gaiman, Neil',NULL,2002,'Adaptado para o cinema em 2009.',NULL,'2026-10-01'),
 (7,'The thorn birds',NULL,'McCullough, Colleen',NULL,1977,NULL,NULL,'2023-03-03');
INSERT INTO biblioitems VALUES (1,1,'9781501142970','Scribner'),(2,2,'9788556510785','Suma'),(3,3,'9788594318602','Penguin'),(4,4,'9788595081512','HarperCollins'),(5,5,'',''),(6,6,'9788551001189','Intrínseca'),(7,7,'9780060129569','Harper & Row');
INSERT INTO biblio_metadata VALUES (3,3,'marcxml','MARC21','<record xmlns="http://www.loc.gov/MARC21/slim"><datafield tag="100" ind1="1" ind2=" "><subfield code="a">Assis, Machado de,</subfield><subfield code="d">1839-1908.</subfield></datafield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">Dom Casmurro</subfield></datafield><datafield tag="650" ind1=" " ind2="4"><subfield code="a">Literatura brasileira</subfield><subfield code="x">Romance.</subfield></datafield></record>'),
 (7,7,'marcxml','MARC21','<record xmlns="http://www.loc.gov/MARC21/slim"><datafield tag="100" ind1="1" ind2=" "><subfield code="a">McCullough, Colleen.</subfield></datafield><datafield tag="245" ind1="1" ind2="4"><subfield code="a">The thorn birds</subfield></datafield><datafield tag="650" ind1=" " ind2="0"><subfield code="a">Australian literature</subfield><subfield code="y">20th century.</subfield></datafield><datafield tag="651" ind1=" " ind2="0"><subfield code="a">Australia</subfield><subfield code="v">Fiction.</subfield></datafield></record>');
INSERT INTO items VALUES (10,1,'0001','CPL','813 K52i',NULL),(11,2,'0002','CPL','813 K52c','2026-09-12'),(12,2,'0003','CPL','813 K52c','2026-09-17'),(13,3,'0004','CPL','869.3 A848d','2026-09-23'),(14,4,'0005','CPL','843 S135p','2026-09-02'),(15,6,'0006','CPL','823 G142c','2026-09-29'),(16,3,'0007','CPL','869.3 A848d','2026-09-28'),(17,4,'0008','CPL','843 S135p','2026-12-05'),(18,5,'0009','CPL','813 S642d','2026-09-27'),(19,6,'0010','CPL','823 G142c','2026-09-26');
INSERT INTO borrowers VALUES (101,'C0101','Ana','Souza','ADULT','CPL','ana@example.org','','2024-03-01','2027-03-01','2026-10-01','$2a$08$x'),
 (102,'C0102','Bruno','Lima','ADULT','CPL','','','2023-05-10','2026-12-31','2026-09-27','$2a$08$y'),
 (103,'C0103','Carla','Mendes','STUDENT','CPL','','','2025-02-11','2027-02-11','2026-08-23','$2a$08$z'),
 (104,'C0104','Diego','Rocha','ADULT','CPL','','','2022-08-20','2026-11-20','2026-09-30','$2a$08$w');
INSERT INTO issues VALUES (1,101,11,'2026-08-23','2026-09-12 23:59:00'),(2,101,12,'2026-08-28','2026-09-17 23:59:00'),(3,101,13,'2026-09-02','2026-09-23 23:59:00'),(4,101,14,'2026-08-13','2026-09-02 23:59:00'),(5,102,17,'2026-09-21','2099-12-05 23:59:00'),(6,104,15,'2026-09-12','2026-09-29 23:59:00'),(7,104,16,'2026-09-11','2026-09-28 23:59:00'),(8,104,18,'2026-09-10','2026-09-27 23:59:00'),(9,104,19,'2026-09-09','2026-09-26 23:59:00');
INSERT INTO accountlines VALUES (1,101,100.0,100.0,'OVERDUE','It'),(2,101,44.0,44.0,'OVERDUE','Dom Casmurro'),(3,104,144.0,144.0,'LOST','Coraline'),(4,104,20.0,-20.0,NULL,'Payment'),(5,102,5.0,0.0,'OVERDUE','');
INSERT INTO saved_sql VALUES (1,'Overdues by branch','Circulation','SELECT branchcode, COUNT(*) FROM issues WHERE date_due < NOW() GROUP BY branchcode'),(2,'Patrons with fines over 50','Accounts','SELECT borrowernumber, SUM(amountoutstanding) FROM accountlines GROUP BY borrowernumber HAVING SUM(amountoutstanding) > 50');
INSERT INTO systempreferences VALUES ('OverdueNoticeCalendar','0','Use the calendar when calculating overdue notices','YesNo'),('finesMode','production','Calculate fines (production) or only test them','Choice'),('SearchEngine','Zebra','Search engine used by the catalogue','Choice');
INSERT INTO reserves VALUES (1,103,6,'CPL',1,'W','2026-09-30');
INSERT INTO old_issues VALUES (1,102,10,'2026-02-01','2026-02-21','2026-02-20'),(2,103,10,'2026-03-01','2026-03-21','2026-03-15'),(3,104,10,'2026-04-01','2026-04-21','2026-04-10'),(4,102,13,'2026-05-01','2026-05-21','2026-05-20');
INSERT INTO branches VALUES ('CPL','Centerville Public Library','Rua das Flores, 100','Centerville','(41) 3333-0000','biblioteca@example.org','https://library.example.org'),('FPL','Fairview Branch','Av. Brasil, 9','Fairview','','','');
INSERT INTO library_hours VALUES ('CPL',0,NULL,NULL),('CPL',1,'08:00','18:00'),('CPL',2,'08:00','18:00'),('CPL',3,'08:00','18:00'),('CPL',4,'08:00','18:00'),('CPL',5,'08:00','18:00'),('CPL',6,'09:00','12:00');
INSERT INTO repeatable_holidays VALUES (1,'CPL',0,NULL,NULL,'Sunday');
INSERT INTO special_holidays VALUES (1,'CPL',25,12,2099,0,'Christmas');
