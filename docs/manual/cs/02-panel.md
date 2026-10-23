# 2. První kroky a panel

[Obsah](README.md)

## Otevření a ovládání

V připraveném Debian/Ubuntu:

```bash
sudo config.sh
```

Ve Windows ikona **Koha** nebo MSIX. První start může požádat jazyk. Při selhání Textual může být klasický panel. Příručka popisuje hlavně Textual, nikoli stará čísla menu.

Šipkami vyberte sekci, **Enter** nebo klik otevře. Pouhé označení nic nespouští. Otevřete kartu úlohy, čtěte otázky. **Tab** přesouvá fokus, před písmenovými zkratkami opusťte textové pole.

| Klávesa | Akce |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Terminál Debian |
| `Ctrl+B` | Zobrazit/skrýt boční panel |
| `q` | Opustit panel |

Opuštění nečinného panelu nevypíná server. Respektujte možnosti přerušení úlohy. Instalace/restore mají nezrušitelné fáze; násilné zavření není bezpečné.

## Stav a adresy

Dashboard ukazuje Koha/dostupnou paměť, poslední backup s datem/stářím/souborem, disk, adresy a MariaDB, Apache, RabbitMQ, Memcached, Koha s HTTP. Backup kombinuje stáří a poslední noční výsledek; nový soubor může doprovázet noční chybu. Čtěte oba: dobrý ukazatel nenahrazuje restore-test. HTTP nedokazuje dokončeného webového průvodce ani všechny knihovní funkce.

**Refresh** znovu čte; **Restart Koha** opravuje/restartuje služby se zřetelem k uživatelům; **Export diagnostics** připraví podporu. Tlačítka nemusí fungovat, pokud přítomný instalátor úlohu nepodporuje.

Adresní karty otevřou/kopírují URL; bez možnosti otevření prohlížeče vložte adresu do vlastního. Na serveru OPAC `http://localhost/`, staff `http://localhost:8080/`, porty 80/8080. Jinde síťová adresa, ne tamní `localhost`. Při WSL NAT/nedostupném LAN ověřte přípravu s technikem, nepředpokládejte všeobecný přístup.

Pokud se zobrazí webový instalátor Koha, dokončete před provozem; obrazovky závisejí na verzi. **Create super librarian** v **Koha settings & parameters** vytvoří účet, soukromé hodnoty jen tam.

Před prací aktualizujte dashboard, ověřte komponenty/adresy, otevřete OPAC/staff ze správného místa, vytvořte/testujte backup a ověřte externí kopii a odpovědnou osobu. Poslední bod je provozní doporučení, vyžaduje dokončený/ověřený přenos.

## Ověřené zdroje

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
