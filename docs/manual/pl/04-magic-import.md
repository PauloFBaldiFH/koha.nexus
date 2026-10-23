# 4. Magiczny import

[Spis treści](README.md)

## Przygotowanie i formaty

Magic Import czyta bibliografię, egzemplarze, czytelników, rekordy wzorcowe. Rozpoznanie formatu nie gwarantuje pól, zwłaszcza bez nagłówków/lokalnych. Zachowaj oryginał/sprawdzony backup, próbę z wieloma kopiami, znakami, pustymi wartościami, wyjątkami; porównaj liczby ze źródłem. Nie publikuj eksportów czytelników.

**Magic Import Tool**, `i`, karta i plik/katalog dostępny dla Linux panelu; plik wyłącznie na komputerze przeglądarki/zdalnego terminala nie jest automatycznie na serwerze.

| Wejście | Kontrola |
| --- | --- |
| MARC21 ISO 2709, MARCXML, tekst MARC | Tytuły/znaki/rekordy wzorcowe/egzemplarze; `.mrk` MarcEdit rozpoznawany bez konwersji tylko z powodu rozszerzenia. |
| CSV/TSV, `.xlsx/.xls/.ods/.dbf` | Separator/nagłówki/wartości/cele. |
| Tabelaryczny JSON/XML | Struktura; dowolny XML nie oznacza MARCXML. |
| SQL tabelaryczny również bez nagłówków | Odczyt danych/relacji, nie wykonywanie programu migracji; sprawdź wieloznaczność. |
| ISIS | Rozpoznany PostgreSQL z `acervo`; główny CDS/ISIS `.mst` wyeksportuj z WinISIS ISO 2709. |
| Biblioteca Fácil | Backup/katalog rozpoznany, powiązane tabele razem, dane/czytelnicy/pożyczki/rezerwacje osobno sprawdzić. |
| Pełny backup Koha | Przekierowanie do restore, nie dodawanie rekordów. |

Obcy PostgreSQL, szczególnie binarny `pg_dump`, nie jest gotową MariaDB. Odmowa: eksportuj MARC/tabele w źródle. Sprawdź każdy element archiwum. PDF/obrazy/dokumenty/programy nie są tu eksportem bibliograficznym.

## Mapowanie i dane

Sprawdź **Bibliographic/Patrons/Authorities**. Siatka/cel, wysokość separatorem lub **Ctrl+Up/Down**. Zachowaj/przekieruj/stały tekst/ignoruj; zrozum powiązania przed usunięciem ID. **Values of this Koha** pokazuje kody, domyślne bibliotekę/typ/kategorię i zamiany źródło/cel. **Record preview** wynik, **Check the whole file** pełna walidacja bez importu. Profil nazwa/**Save**, wybór/**Use**, sprawdź przy zmianie struktury. **Apply/Ctrl+S** zatwierdza mapowanie, nie końcowy zapis. **Skip: import as it is/Esc** pomija mapowanie, nie anuluje całości. Grupowanie/korekta tekstu wymagają podglądu; nie zmieniaj ślepo skrótów/nazw/kodów.

`952` zachowane, mapowanie biblioteki/typu na żądanie; ważnego kodu nie zamieniaj tylko dla domyślnego. Sprawdź barcode, bibliotekę macierzystą/aktualną, sygnaturę, typ, miejsce, nabycie. Lokalne `949/852/950/990` w Pergamum/Biblivre mogą mieć różną semantykę. Notatka depozytu `DL` z datą nie tworzy automatycznie egzemplarza; sprawdź wykluczenia/niezależne ślady inwentarza. Brak barcode domyślnie do przeglądu; generowanie wymaga wyboru i trwałej tożsamości migracji/źródła, bez cichego numerowania kolizji. SQL wymaga rozpoznanej relacji, nie pozycji kolumn/kolejności wierszy; popraw niejasność przed importem.

**Patrons**: imię/nazwisko/karta/kontakt/adres/daty/biblioteka/istniejąca kategoria. E-mail/CPF/data to wskazówki, narodziny/rejestracja/wygaśnięcie mogą wyglądać podobnie. Aktualizacja istniejących pytana z dopasowaniem karty, odrębna od nowych; nie zgaduj uprawnień/uwierzytelniania. **Authorities**: ID, forma wzorcowa, warianty, relacje, typ; zmiana trybu nie tworzy brakujących informacji.

Czytaj ilości/odrzucenia/pytania. Dla istniejących: zachować i nowe egzemplarze, zastąpić lub tworzyć bez porównania. **Późniejszy błąd może pozostawić wcześniejszy import.** Zachowaj podsumowanie/logi i sprawdź przed powtórką. Kontroluj próbki/egzemplarze/osoby/relacje w Koha. **Library tools > Undo a MARC import** dotyczy MARC, nie uniwersalnie pożyczek/czytelników. Pełna baza według zasad Backup center.

**Do potwierdzenia:** konkretne własnościowe układy/wersje eksportu bez próbki i przeglądu.

## Sprawdzone źródła

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
