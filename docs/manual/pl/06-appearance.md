# 6. Wygląd OPAC i staff

[Spis treści](README.md)

**OPAC and Staff Appearance**, `o`, ma oddzielne ustawienia OPAC i staff/intranetu.

**Sync current OPAC settings** czyta bez zastosowania. Zmieniaj grupę po grupie. **Preview** pokazuje CSS/JavaScript/treść, nie pełny widok przeglądarki. **Apply** podsumowanie/potwierdzenie i wcześniejszy backup. Sprawdź stronę główną, wyszukiwanie, rekord, logowanie, także mały ekran.

Bloki trafiają do `OpacUserCSS/OpacUserJS` i odpowiednio `IntranetUserCSS/IntranetUserJS`. Własne zachowane, konflikty wyglądu z innymi zmianami nadal możliwe.

## Wygląd i treść

Tekstura/rozmycie/krycie/rogi/kolory/tło, jasny/ciemny i początkowy motyw: zachowaj kontrast z obrazem/przezroczystością. Staff ma pasek/szybkie szukanie/moduły/gęstość tabel/tekst/kontrast. **Apply color theme to Staff Client** aktywuje; **Copy OPAC preset** tylko wypełnia, **Apply** zapisuje.

Plik dostępny serwerowi, oferowany hosting albo bezpośrednia HTTPS-URL. PNG/JPEG/GIF/WebP/ICO akceptowane, SVG odrzucane. Plik tylko na własnym komputerze wymaga udostępnienia serwerowi. Prawa do obrazów i opis dostępności logowania; strona hostingu nie zawsze jest adresem obrazu. Sprawdź usługi zewnętrzne, nie publikuj prywatnego.

Karuzela nowości/lista Koha z numerem `shelfnumber=`; tytuł/liczba/styl/szybkość/autoplay, **Refresh carousel**. Brak okładki nie oznacza usunięcia rekordu; zależy od dostępnych danych/okładek/sieci. Przyciski OPAC/staff oddzielne: tekst/adres/cel/kolejność, **Add a button**, usunięcie wiersza przed zastosowaniem.

Logowanie: obraz/opis/HTML filtrowany ze skryptów/stylów/zdarzeń; bez poufnych instrukcji. Wiadomości mają własne tytuł/tekst/przyciski, nie zastępują istniejących biblioteki. Stopka `Field: value`, linki tekst `|` adres, maksymalnie sześć, publiczne dane.

**Remove** potwierdza i robi backup przed zdjęciem motywu, wraca wygląd Koha z własnymi ustawieniami. Nie pełny restore ani cofnięcie innej administracji. Popraw błędną grupę, zastosuj, zachowaj błąd do diagnozy.

## Sprawdzone źródła

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
