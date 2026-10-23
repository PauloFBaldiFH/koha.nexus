# 3. Backup i restore

[Spis treści](README.md)

## Centrum i kopie

**Backup center**, `b`: ostatni backup, rozmiar, wynik, **Compression** i karty.

| Karta | Cel |
| --- | --- |
| Download latest backup | Kopiowanie najnowszego znalezionego pliku |
| Generate manual backup and download to PC | Utworzenie, kontrola, transfer bazy |
| Export MARC21 records now | Eksport bibliografii i rekordów wzorcowych |
| Restore database | Zastąpienie obecnej bazy |
| Configure cloud backup | Wysyłanie zewnętrzne |
| Test integrity of latest backup | Test importu tymczasowego |

**Restore database to karta**, nie górny przycisk ani osobna pozycja główna. Wynik dotyczy ostatniej nocy, data/rozmiar najnowszego pliku, niekoniecznie tej samej operacji.

SQL zawiera bazę Koha, nie cały obraz Windows/Debian. MARC21 z bibliografią i rekordami wzorcowymi w `.tar.gz` nie zastępuje SQL dla czytelników/wypożyczeń. Przed restore bazy z tabelami tworzona jest sprawdzona kopia bezpieczeństwa; pusta może ją pominąć.

Automatyczne SQL/kopie bezpieczeństwa: `/var/backups/koha_sql`, MARC `/var/backups/koha_marc`. Ręczny backup ma osobny cel, domyślnie `backups` w wykrytym katalogu domowym. `.part` jest tymczasowy do zakończenia kontroli i zmiany nazwy.

## Kompresja i transfer

**Compression**: gzip `.sql.gz` kompatybilny, Zstandard `.sql.zst` szybki/mniejszy dla dużych katalogów, XZ/LZMA `.sql.xz` najmniejszy/wolniejszy. Zapisuje wybór od razu, bez dodatkowego przycisku, dla nowych nocnych/ręcznych/bezpieczeństwa, bez rekompresji istniejących. Brak programu/błąd instalacji może spowodować gzip: czytaj rzeczywisty format. Restore rozpoznaje niezależnie `.sql/.sql.gz/.sql.zst/.sql.xz`; rozszerzenie nie potwierdza treści.

**Generate manual backup and download to PC**: sprawdź zapisywalny katalog serwera, **Save backup**, poczekaj na tworzenie/weryfikację. Ekran nie zamyka się podczas zapisu/kopii. Sprawdź nazwę/rozmiar/ścieżkę. WSL: **Save to Windows Downloads/Choose folder in Windows**. Zdalnie wykonaj pokazane polecenie na własnym komputerze. Sprawdź plik i **Finish and exit**.

Przyciski Windows tylko WSL. Nie kopiuj poleceń z obcych instalacji: zależą od pliku/serwera. Przy innym backup/restore poczekaj, nie omijaj wspólnej blokady konkurencyjnym zadaniem. **Download latest backup** pobiera istniejący plik, nie tworzy. Desktop-Linux/WSL próbuje Downloads, SSH może pokazać polecenie lokalne; bez pliku utwórz ręczny.

## Test, MARC, chmura

**Test integrity of latest backup**: sprawdź plik/datę, **Choose another file**, potwierdź i poczekaj na import tymczasowy. Sukces podaje tabele/rekordy/czytelników bez zastępowania produkcji. Dotyczy konkretnej kopii/środowiska; zachowaj dostęp do tej samej przesłanej kopii.

**Export MARC21 records now**: potwierdź, poczekaj na pakiet bibliografii i rekordów wzorcowych, sprawdź ścieżkę/zawartość i transfer. Koha działa nadal; chmura, jeśli skonfigurowana, zgłasza również wysyłkę. Zachowaj SQL do pełnej bazy.

**Configure cloud backup**: dwie ścieżki Google Drive oraz m.in. OneDrive/MEGA/S3. Autoryzacja na serwerze/innym komputerze, tylko wskazana URL/instrukcja. S3 rozróżnia usługę, region/endpoint, bucket. Zaczekaj na rzeczywisty test i odbiór; nie polegaj na błędnej konfiguracji. Prywatne dane tylko w instalacji, nie publiczne dokumenty/obrazy/pomoc; nie wskazujemy ich plików. Domyślnie SQL codziennie 23:00, MARC niedziela 03:00, czas serwera; cron może zmienić.

## Destrukcyjny restore

**Potwierdzenie pozwala zastąpić obecną bazę.** Zaplanuj konserwację i kopię zewnętrzną; panel nie wykonuje tego dodatkowego zalecenia automatycznie.

W **Restore database** wybierz dostępny plik, korzystając z transferu. WSL może skopiować z Windows do Linux przed restore. Czytaj dostęp/treść/integralność/miejsce; wyjaśnij podejrzany/niepełny plik mimo rozszerzenia. Sprawdź ponownie przy potwierdzaniu: do niego można zrezygnować, potem czekaj bez zamykania, brak anulowania.

Najpierw SQL do bazy tymczasowej, kontrola ważnych tabel/liczby; błąd zatrzymuje przed zamianą. Obecne tabele wymagają zweryfikowanej kopii SQL `pre_restore_safety_backup_` z datą/czasem/kompresją; błąd kopii nie powinien usuwać obecnej bazy. Pusta może pominąć.

Następnie zatrzymanie klientów, odtworzenie/import, schema, synchronizacja wyszukiwania, indeksy i restart. Zapisany motyw jest ponownie stosowany, jeśli dostępny, jako próba. Błąd testu/kopii nie oznacza zastąpienia. W błędach tworzenia/importu/schema możliwa próba powrotu według etapu/kopii, **ale rollback też może zawieść**. Błąd indeksu może nastąpić po restore bazy bez powrotu starego katalogu.

Zachowaj komunikat i `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log`, dla indeksu `/var/log/koha-easy-install/zebra-rebuild.log`. Wróć do karty centrum zamiast dawnych numerów, wezwij pomoc przy nieznanym stanie. Sprawdź dashboard/rekordy/wyszukiwanie OPAC/staff. Koniec SQL nie potwierdza zewnętrznych plików.

## Sprawdzone źródła

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
