# 8. Administracja, wiadomości i VPN

[Spis treści](README.md)

Sprawdź stan/świeży backup przed administracją. Konfiguracja nie dowodzi działania w twojej sieci; sprawdź później.

## Cron i VPN

**Schedules & cron tasks**, `s`: aktywacja/częstość/czas/dzień lub wyrażenie własne. **Reload**, potrzebne zadania, `HH:MM`, **Preview**, **Save**/potwierdzenie, odczytaj. `/etc/cron.d/koha_tasks`, poprzedni `koha_tasks.bak`; wyłączone komentowane z czasem, własne zachowane. **Defaults** wypełnia, wymaga zapisu. SQL dziennie 23:00/MARC niedziela 03:00 domyślnie, sprawdź strefę/własne. Serwer/Linux muszą działać, cron nie gwarantuje włączenia Windows. Powiadomienia Koha mają inny mechanizm.

**Security & access hub > WireGuard VPN**, `v`: publiczny adres/nazwa i UDP. **Set up the VPN** pokazuje zmiany; router przekazuje port do serwera. Nazwa/**Add device**, **QR code & profile**, sprawdź łączność/staff/ruch. Nie publikuj profilu/QR. **Revoke** unieważnia, wymaga nowego; **Turn off** rozłącza, zachowuje profile. Split tunnel tylko `10.66.0.0/24`, własny internet/DNS, staff `http://10.66.0.1:8080`. WSL bez mirrored nie jest bezpośrednio dostępne, VPN wyłączona.

## Wiadomości

**Messaging & interoperability**, `m`: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**. Włącz e-mail/sprawdź domyślny SMTP; przyciski SMTP/adres biblioteki/wezwania-pokwitowania/reguły opóźnień. Nie wypełnia wszystkich odbiorców/reguł/szablonów: kontroluj preferencje i prywatną konfigurację dostawcy.

**Set up WhatsApp and Telegram** ustawia usługę/kraj/numer kierunkowy/test/aktywację/telefony. WhatsApp wymaga gateway, Telegram bot/odbiorców. Próba uprawnionemu przed produkcją, formaty/szablony przed masową korektą. SMS przez `SMSSendDriver`/preferencje czytelników potrzebuje zgodnej usługi/sterownika, nie tylko nazwy.

**Alerts**: przypomnienia terminu/opóźnienia/powtórzeń/podsumowania/kanałów, zapisz i **Dry run (sends nothing)**. Włącza zadanie, sprawdź cron i unikaj powielenia Koha. SIP2: port/sieć/biblioteka/uprawnienia, usuń przykłady i utwórz konto Koha przyciskiem; konto/serwer zgodne. Nie otwieraj całej sieci na lokalny test. Z39.50 do rozdziału 5, wejście różne od wyjścia.

## Dalsze zarządzanie

Hub Cloudflare Tunnel/UFW/staff-8080/HTTPS/Fail2ban: czytaj stan/podsumowanie, rozróżniaj VPN/tunel/bezpośrednie. Nie zmieniaj zapory zdalnej bez drogi dalszej administracji. **Do potwierdzenia:** domena/router/dostawca/instytucja; kod nie daje uniwersalnej publikacji.

**Koha settings & parameters** ustawia pamięć/workers, super bibliotekarza, strefę; ogranicz szerokie prawa. **Koha languages** rozróżnia pobierz/aktywuj, samo pobranie, aktywuj zainstalowane/listuj, sprawdź panel/OPAC/staff. **Update center** rozdziela system/schema i GitHub-panel; backup/konserwacja, aktualizacja może zamknąć sesję. Restart nie dowodzi naprawy migracji schema.

**Library tools**: relacje/synchronizacja wzorcowych, duplikaty autorów, SQL, kategorie, jakość, prywatność. Różne źródło/cel kategorii, filtr/biblioteka i symulacja przed chronioną zgodą. Jakość tylko czyta, nie naprawia wszystkiego. Anonimizacja usuwa stare powiązania historii/czytelników według Koha, nie całą bibliografię. Usuwanie czytelników wymaga filtrów/symulacji/liczby potwierdzającej: destrukcyjne, sprawdź retencję. Podobne nazwiska nie dowodzą tej samej osoby. Ukryte karty nie są przedstawiane jako dostępne.

## Sprawdzone źródła

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
