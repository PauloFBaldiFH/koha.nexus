# 2. Komma igång och använda panelen

[Innehåll](README.md)

## Öppna och navigera

På förberedd Debian/Ubuntu:

```bash
sudo config.sh
```

På Windows används **Koha**-ikonen eller MSIX-programmet. Första starten kan fråga språk. Om Textual inte kan förberedas kan den klassiska panelen erbjudas. Handboken beskriver främst Textual, inte äldre menynummer.

Markera sidofält med piltangenter och öppna med **Enter** eller klick. Markering ensam startar inget. Öppna uppgiftskort och läs frågor. **Tab** flyttar fokus; lämna textfält före bokstavsgenvägar.

| Tangent | Åtgärd |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Debian-terminal |
| `Ctrl+B` | Visa/dölj sidofält |
| `q` | Lämna panelen |

Att lämna panelen i vila stänger inte av servern. Följ pågående uppgifts avbrottsinstruktioner. Installation/restore har steg som inte kan avbrytas; tvångsstängning är osäker.

## Status och adresser

Dashboard visar Koha-status och tillgängligt minne, senaste backup med datum/ålder/fil, ledig disk, åtkomstadresser samt MariaDB, Apache, RabbitMQ, Memcached och Koha med HTTP-kontroller. Backupindikatorn använder filålder och senaste nattresultat: en ny fil kan finnas trots nattfel. Läs båda; god indikator ersätter inte restore-test. HTTP-svar bevisar inte färdig webbinstallation eller alla biblioteksfunktioner.

**Refresh** läser igen. **Restart Koha** begär tjänstereparation/omstart, med hänsyn till användarna. **Export diagnostics** skapar supportinformation. Knappar kan vara inaktiva om installeraren saknar uppgiften.

Adresskort öppnar/kopierar URL. Utan webbläsarstart klistras adressen in på egen dator. Lokalt OPAC `http://localhost/`, staff `http://localhost:8080/`, portar 80/8080. På annan dator används nätverksadressen, inte dess `localhost`. Vid WSL NAT-varning om LAN, kontrollera Windows-nätförberedelse med ansvarig; anta inte åtkomst från alla datorer.

Slutför Koha-webbinstalleraren om den visas; skärmarna varierar med version. **Create super librarian** under **Koha settings & parameters** skapar konto; privata uppgifter bara där.

Före drift: uppdatera dashboard, kontrollera komponenter/adresser, öppna OPAC/staff från rätt dator, skapa/testa backup, kontrollera extern kopia och vem som kan återställa. Sista punkten är driftråd: användbar extern kopia kräver färdig och kontrollerad överföring.

## Kontrollerade källor

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
