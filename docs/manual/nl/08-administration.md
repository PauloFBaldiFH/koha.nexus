# 8. Beheer, berichten en VPN

[Inhoud](README.md)

Controleer huidige toestand en recente backup vóór beheer. Instelling bewijst geen werking door eigen netwerk: achteraf controleren.

## Cron

**Schedules & cron tasks**, `s`: aan/uit, frequentie, tijd en dag/eigen expressie. **Reload**, benodigde taken aan, `HH:MM`, **Preview**, **Save** en bevestigen, herladen. Beheert `/etc/cron.d/koha_tasks`, bewaart `koha_tasks.bak`. Uitgeschakelde regels blijven commentaar met tijd, eigen regels blijven. **Defaults** vult, vraagt nog opslaan.

Standaard SQL dagelijks 23:00, MARC zondag 03:00; tijdzone/eigen planning controleren. Server/Linux moeten draaien; cron garandeert Windows-inschakeling niet. Koha-meldingen hebben eigen mechanisme.

## VPN

**Security & access hub > WireGuard VPN**, `v`: openbaar adres/naam en UDP-poort. **Set up the VPN** toont netwerkwijzigingen; router moet UDP doorsturen naar server. Elk apparaat naam, **Add device**, **QR code & profile** voor client; verbinding/staff/verkeer controleren. Profiel/QR niet publiceren.

**Revoke** blokkeert profiel, nieuw nodig om terug te keren. **Turn off** verbreekt maar bewaart profielen. Split tunnel alleen `10.66.0.0/24`, internet/DNS blijven eigen; staff `http://10.66.0.1:8080`. WSL zonder mirrored netwerk is niet direct bereikbaar, deze VPN blijft uit.

## Berichten

**Messaging & interoperability**, `m`: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**. E-mail aan en standaard-SMTP controleren. Knoppen naar SMTP, bibliotheekadres, meldingen/bewijzen, te-laatregels. Activatie vult niet alle regels/ontvangers/sjablonen; voorkeuren/authenticatie privé controleren.

**Set up WhatsApp and Telegram** regelt dienst, land/netnummer, tests, activatie, telefoons. WhatsApp vereist gateway, Telegram bot/ontvangers. Geautoriseerde test vóór productie; formaten/sjablonen vóór massale correctie. SMS naar `SMSSendDriver` en lenersvoorkeuren; compatibele dienst/driver nodig, naam alleen niet genoeg.

**Alerts** stelt herinnering vóór verval, te-laat/herhaling en dagoverzicht/kanalen. Opslaan en **Dry run (sends nothing)** simuleert. Schakelt taak in, cron controleren en doublures met Koha-meldingen vermijden. SIP2: poort/netwerk/bibliotheek/apparaatrechten, voorbeelden verwijderen, benodigde Koha-account via knop; account/server moeten overeenkomen. Niet alle netwerken openen voor lokale test. Z39.50 naar hoofdstuk 5, inkomend/uitgaand onderscheiden.

## Veiligheid en administratie

Hub bevat Cloudflare Tunnel, UFW, beperking staff 8080, HTTPS, Fail2ban. Staat/samenvatting lezen, verschillend bereik tunnel/VPN/direct onderscheiden. Remote-firewall niet zonder overblijvende beheerroute wijzigen. **Nog te bevestigen:** domein/router/provider/institutioneel beleid; code biedt geen universeel publicatierecept.

**Koha settings & parameters** past geheugen/workers, superbeheeraccount en tijdzone aan; uitgebreide rechten beperken. **Koha languages** onderscheidt downloaden/activeren, alleen downloaden, geïnstalleerd activeren en opsommen; paneel/OPAC/staff controleren.

**Update center** scheidt systeem/schema van GitHub-paneelupdate. Backup/onderhoud plannen; paneel kan sessie beëindigen voor nieuwe versie. Schemamigratiefout is niet bewezen gerepareerd door herstart.

**Library tools** bevat autoriteitslinks/synchronisatie, dubbele auteurs, SQL, categorieën, kwaliteit, privacy. Verschillende bron/doelcategorie, filter/bibliotheek, dry run vóór beschermde bevestiging. Kwaliteit leest, corrigeert niet alles. Anonimisering verwijdert oude lenerskoppelingen volgens Koha, niet alle bibliografie. Leners wissen vraagt filters, simulatie en aantalbevestiging: destructief, bewaarbeleid controleren. Gelijkende namen bewijzen geen zelfde persoon. Verborgen kaarten worden niet als beschikbaar beschreven.

## Gecontroleerde bronnen

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
