# 8. Administration, meddelanden och VPN

[Innehåll](README.md)

Kontrollera status och färsk backup före administration. Konfiguration bevisar inte funktion i nätet; kontrollera efteråt.

## Cron och VPN

**Schedules & cron tasks**, `s`: aktivering/frekvens/tid/dag eller eget uttryck. **Reload**, aktivera behövt, `HH:MM`, **Preview**, **Save**/bekräftelse, läs igen. Hanterar `/etc/cron.d/koha_tasks`, behåller `koha_tasks.bak`. Avstängda rader kommenteras med tid, egna rader bevaras. **Defaults** fyller men kräver sparande. SQL dagligen 23:00/MARC söndag 03:00 standard; tidszon/anpassning kontrolleras. Dator/Linux måste köra; cron garanterar inte Windows-start. Koha-notiser har egen mekanism.

**Security & access hub > WireGuard VPN**, `v`: offentlig adress/namn, UDP-port. **Set up the VPN** visar nätändringar; router måste vidarebefordra UDP till server. Namnge enhet/**Add device**, **QR code & profile**, kontrollera anslutning/staff/trafik. Publicera aldrig profil/QR. **Revoke** kräver ny profil för återkomst; **Turn off** kopplar från men behåller. Delad tunnel bara `10.66.0.0/24`, internet/DNS egna; staff `http://10.66.0.1:8080`. WSL utan mirrored-nät är inte direkt nåbart och VPN hålls av.

## Meddelanden

**Messaging & interoperability**, `m`: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**. Aktivera e-post/kontrollera standard-SMTP; knappar för SMTP, biblioteksadress, notiser/kvitton/förseningsregler. Alla regler/mottagare/mallar fylls inte automatiskt; granska och konfigurera leverantörens inloggning privat.

**Set up WhatsApp and Telegram**: tjänst/land/riktnummer/test/aktivering/telefonkontroll. WhatsApp behöver gateway, Telegram bot/mottagare. Testa behörig mottagare före produktion och kontrollera format/mallar före massändring. SMS via `SMSSendDriver`/låntagarinställningar behöver kompatibel tjänst/drivrutin, inte bara namn.

**Alerts**: förfallopåminnelser/försening/upprepning/dagssammanfattning med kanaler; spara, **Dry run (sends nothing)** simulerar. Slår på cron-uppgift; kontrollera och undvik dubbla Koha-notiser. SIP2 ställer port/nät/bibliotek/enhetsrättigheter, ta bort exempel och skapa motsvarande Koha-konto via knapp. Öppna inte alla nät för lokalt test. Z39.50 till kapitel 5, in-/utgående olika.

## Övrig administration

Hub har Cloudflare Tunnel/UFW/staff-8080/HTTPS/Fail2ban. Läs status/översikt, skilj VPN/tunnel/direktåtkomst. Ändra inte fjärrbrandvägg utan kvarvarande administrationsväg. **Att bekräfta:** domän/router/leverantör/institution, ingen universell publiceringsmetod från koden.

**Koha settings & parameters**: minne/workers, superbibliotekarie, tidszon; begränsa höga rättigheter. **Koha languages** skiljer hämta/aktivera, bara hämta, aktivera installerat/lista; kontrollera panel/OPAC/staff. **Update center** skiljer system/schema och GitHub-panel; backup/underhåll, paneluppdatering kan avsluta session. Schemafel bevisas inte åtgärdat av omstart.

**Library tools**: auktoritetslänkar/synk, författardubbletter, SQL, kategorier, kvalitet, integritet. Olika källa/målkategori, urval/bibliotek och simulering före skyddad bekräftelse. Kvalitet läser, lagar inte allt. Anonymisering tar bort gammal historiks personlänkar enligt Koha, inte all bibliografi. Radera låntagare kräver filter/simulering/antalbekräftelse: destruktivt, kontrollera bevarandepolicy. Liknande namn bevisar inte samma person. Dolda katalogkort anges inte som tillgängliga.

## Kontrollerade källor

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
