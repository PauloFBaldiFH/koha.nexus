# 4. Magický import

[Obsah](README.md)

## Vstup a příprava

Magic Import čte bibliografii, exempláře, čtenáře a autority. Poznaný formát nezaručuje pole, zvlášť bez hlaviček/lokální. Ponechte originál/ověřený backup, zkuste reprezentativní vzorek s více kusy, diakritikou, prázdnými hodnotami, výjimkami a srovnejte počty. Exporty čtenářů nezveřejňovat.

**Magic Import Tool**, `i`, karta a soubor/adresář dostupný Linux panelu; soubor jen na počítači prohlížeče/terminálu není automaticky na serveru.

| Vstup | Kontrola |
| --- | --- |
| MARC21 ISO 2709, MARCXML, text MARC | Tituly/znaky/autority/exempláře; `.mrk` MarcEdit rozpoznán bez konverze jen kvůli příponě. |
| CSV/TSV, `.xlsx/.xls/.ods/.dbf` | Oddělovače/hlavičky/hodnoty/cíle. |
| Tabulkové JSON/XML | Struktura; obecné XML není automaticky MARCXML. |
| Tabulkové SQL i bez hlaviček | Čte data/vztahy, nespouští migrační program; kontrolujte nejednoznačnost. |
| ISIS | Rozpoznaný PostgreSQL s `acervo`; hlavní CDS/ISIS `.mst` exportovat z WinISIS ISO 2709. |
| Biblioteca Fácil | Rozpoznaný backup/složka, související tabulky spolu, zvlášť záznamy/čtenáři/výpůjčky/rezervace. |
| Úplný backup Koha | Směřuje k restore, ne přidávání. |

Jiný PostgreSQL, zvláště binární `pg_dump`, není připravená MariaDB. Při odmítnutí exportujte MARC/tabulky ve zdroji. Každý člen archivu prověřit. PDF/obrázek/dokument/program není bibliografický export tohoto čtení.

## Integrované mapování

**Bibliographic/Patrons/Authorities** ověřit/opravit. Mřížka/cíle, výška děličem nebo **Ctrl+Up/Down**. Zachovat/přesměrovat/pevný text/ignorovat; před odstraněním ID pochopte vazby. **Values of this Koha**: kódy, výchozí knihovna/typ/kategorie, náhrady zdroj/cíl. **Record preview** výsledek, **Check the whole file** celá validace bez importu. Profil jméno/**Save**, volba/**Use**, revize při změně struktury. **Apply/Ctrl+S** přijme mapování, ne konečný zápis. **Skip: import as it is/Esc** přeskočí mapování, nezruší vše. Seskupování/korekce textu vyžadují náhled, ne slepé úpravy zkratek/jmen/kódů.

## Exempláře a lidé

`952` zachován, knihovna/typ lze na požádání přemapovat; platný jiný kód nenahrazovat pouze výchozím. Barcode, vlastnická/aktuální knihovna, signatura, typ, umístění, nabytí. Lokální `949/852/950/990` mohou mít v Pergamum/Biblivre rozdílné významy. Povinný výtisk `DL`/datum nevytváří automaticky místní kus; zkontrolujte vyřazení a nezávislé inventární důkazy. Bez barcode výchozí revize; tvorba potřebuje volbu a stabilní identitu migrace/zdroje, ne tiché přečíslování kolizí. SQL-vazba musí být rozpoznána, ne odhad pozice/pořadí; nejasnost opravit před importem.

**Patrons**: jméno/příjmení/průkaz/kontakt/adresa/data/knihovna/existující kategorie. E-mail/CPF/datum jen indicie, narození/zápis/expirace podobné. Aktualizace existujících se ptá a páruje průkaz, není jen přidání nových; práva/autentizaci neodhadovat. **Authorities**: ID, autorizovaná forma, varianty, vztahy, typ; změna režimu nedoplní neexistující fakta.

Čtěte počty/odmítnutí/otázky. Existující lze ponechat a nové kusy, nahradit, nebo nový bez porovnání. **Pozdější chyba může ponechat dřívější import.** Uchovejte výsledek/log, před opakováním ověřte fáze, vzorky/exempláře/osoby/vazby. **Library tools > Undo a MARC import** jen dávky MARC, ne univerzální čtenáři/výpůjčky/rezervace. Úplná databáze přes bezpečný postup Backup center.

**K potvrzení:** konkrétní proprietární rozvržení/verze bez vzorku a kontroly.

## Ověřené zdroje

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
