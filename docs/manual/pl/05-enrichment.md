# 5. Wzbogacanie i Z39.50/SRU

[Spis treści](README.md)

## Wzbogacanie

Import przejmuje eksport, wzbogacanie uzupełnia lub szuka nowej książki. Zgodny tytuł wymaga kontroli bibliograficznej. **Library tools > Enrich from world catalogues**, `n`; dawny ekran bibliograficznych partii nie jest aktualną ścieżką.

`all` lub `biblionumbers`, np. `101, 102, 500-510`, **Search**. Obserwuj zadanie/serwery; duże w tle, może wznowić po restarcie przy dostępnej maszynie. **Pause/Resume** nie cofa zmian. Raport: tematy/klasyfikacja/notatki/opis fizyczny porównać. **Search more servers** odpytuje nowe źródła; **Choose donor** wybiera dawcę grup pól. **Apply** po przeglądzie/potwierdzeniu; szukanie/raport nie zapisuje.

Bezpośrednie Z39.50 ma limity/awarie: brak wyniku nie dowodzi braku książki. Nie ma ogólnego limitu 50 rekordów: próg ochrony przy zastosowaniu, kopie rekordów małe zadania, pełny zweryfikowany backup duże. **Revert** przywraca wersje zgodnie z zabezpieczeniami, zachowuje później edytowane, nie pełny restore ani cofanie wszystkich cudzych zmian.

## Nowe rekordy i wzorcowe

ISBN/tytuł, autor/rok pomagają, **Find**, wybierz po kontroli. **Import as new record** dodaje z potwierdzeniem, nie zastępuje tego samego ISBN. Usuwa lokalne `9XX` dawcy, zapisuje źródło, nie kopiuje cudzych egzemplarzy jako własnych. Sprawdź rekord i dodaj lokalne kopie; partia przez **Undo a MARC import**.

**Enrich & standardize authorities**, `h`: zakres, formy dokładne/zbliżone. Zbliżone mogą proponować korektę i rekordy wstępne: kontroluj szczególnie. Najpierw własne Koha, potem baza wzbogacania/serwery bezpośrednie; brazylijskie priorytetowo, tematy tylko z nich. Nie gwarantuje lokalnej polityki. **Apply** tworzy potrzebne wzorcowe/relacje z backup, zachowując zmiany od raportu. Revert zachowa nowe wzorcowe nadal powiązane.

## Serwery

**Z39.50 / SRU servers**, `z`: wejściowy udostępnia katalog i zmienia port zapory przy przełączeniu. Sieć wspólnotowa odrębna od źródeł bezpośrednich. **Reset/Reset all** pozwala ponowić, nie naprawia zdalnie. Spacja wybiera, **Scan** wyszukuje realny rekord, **Add to Koha** dodaje wybrane działające. SRU w ustawieniach nie oznacza SRU we wszystkich zapytaniach; szukanie na zewnątrz nie wymaga otwierania wejścia.

**Do potwierdzenia:** dostępność, zakres i warunki każdej zewnętrznej bazy z lokalnej sieci w chwili użycia.

## Sprawdzone źródła

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
