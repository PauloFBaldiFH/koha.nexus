# 9. Diagnostyka i logi

[Spis treści](README.md)

Zapisz działanie/czas/pełny błąd i działające funkcje. Strona, aktywna usługa i udane wyszukiwanie to różne testy. Reinstalacja/restore nie jest pierwszą odpowiedzią na wszystko.

## Diagnostyka i logi

Odśwież **Control Dashboard**. **Diagnostics & maintenance center > Detailed server & Koha status**, potem **Full system health check** i raport. **View latest validation report** wraca do niego, **Export diagnostics** pokazuje katalog pomocy. Mimo maskowania sprawdź osoby/nazwy/adresy przed publikacją, nie kopiuj całej instalacji. Tryb klasyczny po awarii Textual nie cofa wcześniejszych operacji; zachowaj błąd/log.

| Lokalizacja | Zawartość |
| --- | --- |
| `/var/log/koha-easy-install/` | Główna Linux |
| `apt.log` | Pakiety/etapy |
| `validacao-*.log` | Raporty datowane |
| `new-panel.log` | Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/eksport |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | Indeks/szukanie |
| `/var/log/koha-easy-install/tools/` | Narzędzia |
| `C:\Koha\logs`, dawniej `C:\KohaEasy\logs` | Windows według instalacji |

`*` oznacza pliki z datą, mogą nie istnieć przed pierwszym użyciem. Preferuj dokładny wskazany plik. **Library tools > View tool logs** wybiera datę/rutynę, ograniczony dostęp przez dane osobowe. Raport: kontekst/data/wersja/OK/ostrzeżenia/błędy/informacje. Czytaj każdą pozycję, **No critical failures** może zawierać ostrzeżenia. Stary backup nie jest błędem bazy; po korekcie waliduj/porównaj.

**Real-time Apache log auditing** wybiera staff/OPAC z dawnymi alternatywnymi ścieżkami. Textual **Pause/p** pauzuje widok, nie Apache; **Continue** wznawia, **Back/Esc** zamyka. Klasyczny `Ctrl+C` dla obserwacji logu, nie każdego zadania. Szukaj czasu/kontekstu `error/fatal/denied/fail`; kolor nie ustala przyczyny.

## Objawy

- OPAC/staff niedostępny: Apache/MariaDB/Plack/cache i adres lokalny/sieć/VPN/tunel. `localhost` to komputer przeglądarki. **Restart / repair Koha services (Memcached, Plack)** przerywa dostęp; czytaj wynik i sprawdzaj ponownie.
- Rekord niewyszukiwany: silnik/kolejka/indeks-baza. **Search engine & indexing > Repair / rebuild indexing**, czytaj/poczekaj; zmiana na Elasticsearch nie jest obowiązkowym początkiem.
- Brak backup: czas/wynik/dysk i system przy cron, `.part` niegotowy. `backup_sql.log`, test/manualny; nie usuwaj ostatniej ważnej bez innej bezpiecznej, unikaj nakładania.
- Import/błędne liczby: logi Magic Import/MARC, wejście/przygotowanie/zapis, tryb/kody/barcode/odrzucenia/duplikaty. Mały podgląd nie waliduje całości; pełny test i zakończone etapy przed powtórką.
- Restore: ustal etap; indeks może zawieść po bazie, rollback również. Sprawdź baza/szukanie/walidacja.
- AI/wzbogacanie wolne: Ollama/wybór/RAM lub zadanie/serwery/limity; nie powielaj dużych zadań przez zwłokę. Awaria zewnętrzna i RAM lokalny to inne diagnozy.

## Ikona Windows

PowerShell zalogowanego użytkownika, **bez administratora**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Może odtworzyć skróty i restartować tray, nie tylko odczyt. Zapisuje `diagnose-<date>.txt` w wykrytym `logs`; zachowaj ścieżkę/błąd. Inne niż instalacja administracyjna.

**Deep database optimization & log cleanup** konserwuje/restartuje, może wymazać użyteczny ślad. Zabezpiecz diagnostykę przed planowaną konserwacją, nie ukrywaj błędu. Do pomocy: wersja, Windows/WSL/dystrybucja, działanie/czas/pełny błąd, OPAC/staff/szukanie, poprzednia operacja, fragmenty sprawdzone pod kątem prywatności.

**Do potwierdzenia:** przyczyna bez pełnego komunikatu/logu; nie przypisuj automatycznie sieci/instalacji.

## Sprawdzone źródła

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
