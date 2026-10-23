# 4. Magisk import

[Innehåll](README.md)

## Förbereda och känna igen

Magic Import läser bibliografi, exemplar, låntagare och auktoriteter. Formatigenkänning garanterar inte rätt fält, särskilt utan rubriker/lokala taggar. Behåll original/verifierad backup, prova representativt urval med flera exemplar, accenter, tomma värden och undantag, jämför källans antal. Publicera inte låntagarexporter.

**Magic Import Tool**, `i`, kort och fil-/mappval: Linux som kör panelen måste nå filen; en fil bara på webbläsar-/terminaldatorn ligger inte automatiskt på servern.

| Inmatning | Kontroll |
| --- | --- |
| MARC21 ISO 2709, MARCXML, MARC-text | Titlar/tecken/auktoriteter/exemplar; MarcEdit `.mrk` känns igen utan konvertering bara för ändelsens skull. |
| CSV/TSV, `.xlsx/.xls/.ods/.dbf` | Avgränsare, rubriker, värden och mål. |
| Tabell-JSON/XML | Struktur; valfri XML är inte nödvändigtvis MARCXML. |
| Tabell-SQL även utan rubriker | Läser igenkända data/relationer, kör inte som migrationsprogram; granska tvetydigheter. |
| ISIS | Igenkänd PostgreSQL-export med `acervo`; CDS/ISIS `.mst` exporteras från WinISIS som ISO 2709. |
| Biblioteca Fácil | Igenkänd backup/datamapp med relaterade tabeller tillsammans; poster/låntagare/lån/reservationer var för sig. |
| Hel Koha-backup | Till restore, ersätter i stället för att lägga till poster. |

Annan PostgreSQL-dump, särskilt binär `pg_dump`, är ingen färdig MariaDB. Vid avslag exportera MARC/tabeller i källsystemet. Kontrollera varje arkivmedlem. PDF/bilder/dokument/program är inte läsbara bibliografiska exporter här.

## Integrerad mappning

Kontrollera **Bibliographic/Patrons/Authorities**, korrigera läge. Granska rutnät/mål, höjd med delare eller **Ctrl+Up/Down**. Behåll, omdirigera, fast text eller ignorera; förstå identifierarens relationer före borttagning.

**Values of this Koha** visar koder, standardbibliotek/typ/kategori och källa/mål-ersättning. **Record preview** visar resultat; **Check the whole file** förbereder/validerar allt utan Koha-import då. Namnge/**Save**, välj/**Use** profil, kontrollera vid strukturändring. **Apply/Ctrl+S** godtar mappning och fortsätter, inte slutlig skrivbekräftelse. **Skip: import as it is/Esc** hoppar över mappning, avbryter inte hela flödet. Gruppering/textkorrigering kräver förhandsgranskning, inte blinda ändringar av förkortningar/namn/koder.

## Exemplar och personer

Nativa `952` bevaras, begärd bibliotek-/typmappning möjlig. Ersätt inte giltig kod bara för standardens skull. Kontrollera barcode, ägar-/aktuellt bibliotek, hyllsignum, typ, plats och förvärv. Lokala `949/852/950/990` kan betyda olika i Pergamum/Biblivre.

Pliktleveransnotering `DL` med datum skapar inte automatiskt lokalt exemplar; granska undantag och självständiga inventariebevis. Saknad barcode granskas normalt; generering kräver uttryckligt val och stabil migrations-/källidentitet, utan tyst omnumrering av kollisioner. SQL-relationer måste identifieras, inte antas från kolumnposition/radordning; rätta oklar koppling före import.

**Patrons**: namn, kort, kontakt, adress, datum, bibliotek/befintlig kategori. E-post/CPF/datum är ledtrådar; födelse/registrering/utgång kan se lika ut. Uppdatering av befintliga frågas med kortmatchning, inte samma som bara nya. Tilldela inte behörigheter/autentisering genom gissning. **Authorities**: identifierare, auktoriserad form, varianter, relationer, typ; lägesbyte skapar inga saknade fakta.

Läs antal/avvisningar/frågor. Befintlig titel kan behållas med nya exemplar, ersättas eller skapas utan jämförelse. **Senare fel kan lämna tidigare steg importerade.** Behåll sammanfattning/loggar, kontrollera före upprepning. Granska prover, exemplar, låntagare/länkar. **Library tools > Undo a MARC import** gäller MARC-partier, inte alla lån/personer/reservationer. Hel databas via Backup center med försiktighet.

**Att bekräfta:** särskilda proprietära exportlayouter/versioner utan prov och resultatgranskning.

## Kontrollerade källor

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
