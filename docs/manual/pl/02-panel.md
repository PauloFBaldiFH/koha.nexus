# 2. Pierwsze kroki i panel

[Spis treści](README.md)

## Otwarcie i nawigacja

Na przygotowanym Debian/Ubuntu:

```bash
sudo config.sh
```

Windows: ikona **Koha** albo aplikacja MSIX. Pierwszy start może pytać o język. Błąd przygotowania Textual może uruchomić wariant klasyczny. Podręcznik dotyczy głównie Textual, nie dawnych numerów menu.

Strzałkami zaznacz sekcję boczną, **Enter** lub klik otwiera. Samo zaznaczenie niczego nie wykonuje. Otwórz kartę zadania i przeczytaj pytania. **Tab** zmienia fokus; opuść pola tekstowe przed skrótami literowymi.

| Klawisz | Działanie |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Terminal Debian |
| `Ctrl+B` | Pokaż/ukryj pasek boczny |
| `q` | Wyjście z panelu |

Wyjście z bezczynnego panelu nie wyłącza serwera. Podczas zadania respektuj dostępne anulowanie. Instalacja/restore mają etapy nieanulowalne; wymuszenie zamknięcia nie jest bezpieczne.

## Stan i adresy

Dashboard pokazuje Koha i dostępną pamięć, ostatni backup z datą/wiekiem/plikiem, wolny dysk, adresy oraz MariaDB, Apache, RabbitMQ, Memcached, Koha i kontrole HTTP. Wskaźnik backup uwzględnia wiek pliku i wynik nocny: nowy plik oraz nieudana noc mogą współistnieć. Czytaj oba; dobry wskaźnik nie zastępuje testu restore. HTTP nie dowodzi zakończonego instalatora WWW ani wszystkich funkcji bibliotecznych.

**Refresh** odczytuje ponownie. **Restart Koha** naprawia/restartuje usługi z uwzględnieniem użytkowników. **Export diagnostics** przygotowuje informacje pomocy. Przyciski mogą być nieaktywne, gdy obecny instalator nie obsługuje zadania.

Karty adresów otwierają/kopiują URL; bez lokalnego otwarcia przeglądarki wklej adres na swoim komputerze. Na serwerze OPAC `http://localhost/`, staff `http://localhost:8080/`, porty 80/8080. Z innego komputera użyj adresu sieci, nie jego `localhost`. Przy niedostępności LAN przez WSL NAT sprawdź przygotowanie Windows z administratorem; nie zakładaj powszechnego dostępu.

Ukończ instalator WWW Koha, jeśli się pojawi; ekrany zależą od wersji. **Create super librarian** w **Koha settings & parameters** tworzy konto, dane prywatne tylko tam.

Przed pracą odśwież stan, sprawdź komponenty/adresy, otwórz OPAC/staff z właściwego miejsca, wygeneruj/przetestuj backup i sprawdź kopię zewnętrzną oraz dostęp do odzyskania. Ostatni punkt jest zaleceniem operacyjnym: wymaga zakończenia i weryfikacji transferu.

## Sprawdzone źródła

- [installer](../../../installer).
- [app.py](../../../panel/kei_panel/app.py).
- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [main.py](../../../panel/kei_panel/screens/main.py).
- [install.py](../../../panel/kei_panel/routines/install.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [dashboard.py](../../../panel/kei_panel/views/dashboard.py).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [menus.py](../../../panel/kei_panel/menus.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
