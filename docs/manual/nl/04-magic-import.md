# 4. Magische import

[Inhoud](README.md)

## Voorbereiding en herkenning

Magic Import leest bibliografische gegevens, exemplaren, leners en autoriteiten. Formaat herkend garandeert geen correcte velden, vooral zonder koppen of bij lokale tags. Bewaar origineel/gecontroleerde backup, probeer representatieve steekproef met meerdere exemplaren, accenten, lege waarden en uitzonderingen; vergelijk aantallen met bron. Publiceer geen lenersexport.

**Magic Import Tool**, `i`, kaart en bestands-/mapkiezer. Linux van paneel moet toegang hebben; bestand alleen op browser-/terminalcomputer staat niet automatisch op server.

| Invoer | Controle |
| --- | --- |
| MARC21 ISO 2709, MARCXML, MARC-tekst | Titels/tekens/autoriteiten/exemplaren; MarcEdit `.mrk` herkend, geen conversie alleen vanwege extensie. |
| CSV/TSV, `.xlsx`, `.xls`, `.ods`, `.dbf` | Scheiding, aanwezige koppen, waarden en bestemmingen. |
| Tabellair JSON/XML | Structuur; willekeurig XML is niet noodzakelijk MARCXML. |
| Tabellair SQL ook zonder koppen | Herkenbare data/relaties worden gelezen, geen uitvoering als migratieprogramma; dubbelzinnigheid controleren. |
| ISIS | Herkende PostgreSQL-export met `acervo`; CDS/ISIS `.mst` vanuit WinISIS naar ISO 2709 exporteren. |
| Biblioteca Fácil | Herkende backup of datamap, gerelateerde tabellen bijeen; records/leners/leningen/reserveringen apart controleren. |
| Volledige Koha-backup | Naar restore, dus vervangen in plaats van records toevoegen. |

Vreemde PostgreSQL-dump, vooral binair `pg_dump`, is geen kant-en-klare MariaDB. Bij afwijzing MARC/tabellen uit bronsysteem exporteren. Elk archieflid controleren; PDF/beelden/documenten/programma’s zijn geen bruikbare bibliografische export voor deze lezer.

## Geïntegreerde handmatige mapping

**Bibliographic/Patrons/Authorities** controleren en foutieve modus corrigeren. Raster en bestemmingen bekijken; scheidingsbalk of **Ctrl+Up/Down** wijzigt hoogte. Behouden, omleiden, vaste tekst, negeren; relaties begrijpen vóór identificator verwijderen.

**Values of this Koha** geeft codes, standaardbibliotheek/type/categorie en bron/doelvervangingen. **Record preview** toont resultaat; **Check the whole file** bereidt/valideert volledig zonder Koha-import op dat moment. Profielnaam/**Save**, kiezen/**Use**, bij structuurwijziging opnieuw controleren. **Apply/Ctrl+S** accepteert mapping en vervolgt, geen definitieve schrijfbevestiging. **Skip: import as it is/Esc** slaat mapping over, annuleert niet gehele procedure.

Groeperen/tekstcorrectie vereisen voorbeeldcontrole; geen blinde aanpassingen van afkortingen, namen en codes.

## Exemplaren en personen

Native `952` blijven, gevraagde bibliotheek/type-hercodering mogelijk. Geldige afwijkende code niet enkel voor standaard vervangen. Barcode, thuis-/huidige bibliotheek, signatuur, type, locatie, verwerving controleren. Lokale `949/852/950/990` kunnen tussen Pergamum/Biblivre verschillend betekenen.

Wettelijk-depotnotitie met `DL`/datum maakt niet automatisch lokaal exemplaar. Uitsluitingen en onafhankelijke inventarisaanwijzingen controleren. Ontbrekende barcode standaard herzien; generatie vereist expliciete keuze en stabiele migratie-/bronidentiteit, zonder stil hernummeren van botsingen. SQL-relaties moeten herkend, niet uit kolompositie/rijvolgorde geraden zijn. Onduidelijke koppeling vóór import corrigeren.

**Patrons**: voor-/achternaam, pasnummer, contact, adres, datums, bibliotheek/bestaande categorie. E-mail/CPF/datumvorm zijn aanwijzingen; geboorte/inschrijving/verval kunnen gelijk ogen. Bestaande leners bijwerken wordt gevraagd via pasnummer, anders dan alleen nieuw toevoegen. Geen rechten/authenticatie op basis van gok over kolommen.

**Authorities**: ID, geautoriseerde naam, varianten, relaties, type; moduswissel verzint ontbrekende gegevens niet.

## Bevestigen en nacontrole

Aantallen, afwijzingen, vragen lezen. Bestaande titel houden met alleen nieuwe items, inkomend vervangen, of zonder vergelijking nieuw maken: passend kiezen en herhaling vermijden.

**Latere fout kan eerdere importfasen laten staan.** Bewaar samenvatting/logs en controleer afgeronde stappen vóór herhaling. Steekproeven/exemplaren/leners/links in Koha nalopen. **Library tools > Undo a MARC import** behandelt MARC-batches, niet alle leners/leningen/reserveringen. Volledige database via Backup center met voorzorgen.

**Nog te bevestigen:** specifiek propriëtair layout/versie zonder voorbeeld en resultaatcontrole.

## Gecontroleerde bronnen

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
