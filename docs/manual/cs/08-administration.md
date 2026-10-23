# 8. Správa, zprávy a VPN

[Obsah](README.md)

Před správou zkontrolujte stav/čerstvý backup. Nastavení nedokazuje provoz v síti, ověřte následně.

## Cron a VPN

**Schedules & cron tasks**, `s`: zapnutí/frekvence/čas/den nebo vlastní výraz. **Reload**, potřebné úlohy, `HH:MM`, **Preview**, **Save**/potvrzení, znovu načíst. `/etc/cron.d/koha_tasks`, starý `koha_tasks.bak`; vypnuté komentář s časem, vlastní řádky zůstávají. **Defaults** vyplní, vyžaduje uložení. SQL denně 23:00/MARC neděle 03:00, kontrola pásma/vlastní konfigurace. Server/Linux musí běžet; cron negarantuje zapnutí Windows, Koha oznámení mají vlastní mechanismus.

**Security & access hub > WireGuard VPN**, `v`: veřejná adresa/jméno/UDP. **Set up the VPN** ukáže změny, router přesměruje UDP serveru. Jméno/**Add device**, **QR code & profile**, test spojení/staff/provoz. Profil/QR nezveřejňovat. **Revoke** zneplatní a žádá nový; **Turn off** odpojí ale ponechá. Split tunnel jen `10.66.0.0/24`, vlastní internet/DNS, staff `http://10.66.0.1:8080`. WSL bez mirrored není přímo dosažitelný, VPN vypnutá.

## Zprávy

**Messaging & interoperability**, `m`: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**. Zapnout e-mail/ověřit výchozí SMTP; odkazy SMTP/adresa knihovny/oznámení-potvrzení/pravidla zpoždění. Nevyplní všechny příjemce/pravidla/šablony: ověřte preference a soukromé přihlášení poskytovatele.

**Set up WhatsApp and Telegram** nastaví službu/zemi/předvolbu/test/zapnutí/telefony. WhatsApp potřebuje gateway, Telegram bot/příjemce. Test oprávněnému před produkcí, formáty/šablony před hromadnou opravou. SMS `SMSSendDriver`/preference potřebuje kompatibilní službu/ovladač, ne jen jméno.

**Alerts**: blížící se termín/zpoždění/opakování/denní souhrn/kanály, uložit/**Dry run (sends nothing)**. Zapne úlohu, ověřte cron, zabraňte duplicitám Koha. SIP2: port/síť/knihovna/práva zařízení, odstranit příklady a vytvořit účet Koha tlačítkem; server/účet musí odpovídat. Neotvírat celou síť pro lokální test. Z39.50 viz kapitola 5, vstup/výstup odlišný.

## Další správa

Hub Cloudflare Tunnel/UFW/staff-8080/HTTPS/Fail2ban: číst stav/souhrn, rozlišit VPN/tunel/přímé. Vzdálený firewall neměnit bez další přístupové cesty. **K potvrzení:** doména/router/provider/instituce; žádný univerzální publikační návod z kódu.

**Koha settings & parameters** paměť/workers, superknihovník, pásmo; omezte široká práva. **Koha languages** stáhnout/aktivovat, jen stáhnout, aktivovat instalovaný/listovat, ověřte panel/OPAC/staff. **Update center** oddělí systém/schéma a GitHub-panel; backup/údržba, může ukončit relaci. Restart nedokazuje opravu migrace.

**Library tools**: autoritní vazby/synchronizace, duplicitní autoři, SQL, kategorie, kvalita, soukromí. Různá zdrojová/cílová kategorie, filtr/knihovna, simulace před chráněným potvrzením. Kvalita pouze čte, ne opraví vše. Anonymizace ruší staré vazby historie/čtenářů podle Koha, ne bibliografii. Mazání čtenářů vyžaduje filtry/simulaci/počet: destruktivní, ověřte uchování. Podobná jména nejsou důkaz stejné osoby. Skryté karty nejsou dostupné nástroje.

## Ověřené zdroje

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
