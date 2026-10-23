# 2. Eerste stappen en paneel

[Inhoud](README.md)

## Openen en navigeren

Op door de installer voorbereid Debian/Ubuntu:

```bash
sudo config.sh
```

Op Windows het **Koha**-pictogram of MSIX-toepassing openen. Eerste start kan taal vragen. Als Textual-voorbereiding faalt, kan klassiek paneel verschijnen. Deze handleiding beschrijft vooral Textual, niet oude menunummers.

Markeer zijbalk met pijlen en open met **Enter** of klik. Markeren alleen voert niets uit. Open taakkaart en lees vragen. **Tab** verplaatst focus; verlaat tekstvelden vóór lettersneltoetsen.

| Toets | Actie |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Debian-terminal |
| `Ctrl+B` | Zijbalk tonen/verbergen |
| `q` | Paneel verlaten |

Een inactief paneel verlaten schakelt server niet uit. Volg tijdens taken hun annuleerinstructies. Installatie/restore bevatten niet-annuleerbare fasen; geforceerd sluiten is niet veilig.

## Status lezen

Dashboard toont Koha-toestand en beschikbaar geheugen, laatste backup met datum/leeftijd/bestand, vrije schijf, toegangsadressen en MariaDB, Apache, RabbitMQ, Memcached, Koha met HTTP-controles. Backupindicator gebruikt bestandsleeftijd en laatste nachtresultaat: recent bestand en mislukte nacht kunnen samengaan. Lees beide; gunstige kaart vervangt geen restore-test. HTTP-antwoord bewijst niet afgeronde webinstaller of alle bibliotheekfuncties.

**Refresh** leest opnieuw. **Restart Koha** vraagt dienstreparatie/herstart; houd rekening met gebruikers. **Export diagnostics** maakt ondersteuningsinformatie. Knoppen kunnen uitgeschakeld zijn wanneer aanwezige installer de taak niet ondersteunt.

## Adressen en eerste gebruik

Adreskaarten openen/kopiëren URL. Zonder browsermogelijkheid plak gekopieerd adres in eigen browser. Op server standaard OPAC `http://localhost/`, staff `http://localhost:8080/`, poorten 80/8080. Elders het getoonde netwerkadres gebruiken, niet eigen `localhost`. Meldt WSL NAT onbereikbaar LAN, controleer Windows-netwerkvoorbereiding met beheerder; geen algemene bereikbaarheid aannemen.

Verschijnt Koha-webinstaller, eerst afronden; schermen kunnen per versie verschillen. Daarna **Create super librarian** onder **Koha settings & parameters** voor eigen account, privéwaarden alleen daar.

Voor ingebruikname dashboard verversen, componenten/adressen controleren, OPAC/staff vanaf juiste computer openen, backup maken/testen en externe kopie/toegang voor herstel controleren. Laatste punt is bedrijfsadvies: bruikbare externe kopie vraagt afgeronde en gecontroleerde overdracht.

## Gecontroleerde bronnen

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
