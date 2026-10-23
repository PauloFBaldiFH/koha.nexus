# 8. Pamamahala, mensahe at VPN

[Nilalaman](README.md)

Suriin ang kalagayan ng sistema at ang pinakabagong backup bago magbago ng mga setting. Ang pagtatapos ng pag-setup ay hindi patunay na gumagana na ang koneksiyon; subukan ito pagkatapos.

## Cron at VPN

**Schedules & cron tasks**, `s`: on/frequency/time/day/expression. **Reload**, kailangan lang, `HH:MM`, **Preview**, **Save**/kumpirma, basa muli. `/etc/cron.d/koha_tasks`, dati `koha_tasks.bak`; off bilang comment may oras, sariling row nananatili. **Defaults** pumupuno, save pa. SQL araw-araw 23:00/MARC Linggo 03:00, suriin zone/custom. Server/Linux umaandar, cron hindi garantisadong bubuhay Windows; Koha notices hiwalay.

**Security & access hub > WireGuard VPN**, `v`: public name/address/UDP. **Set up the VPN** nagpapakita pagbabago, router ipapasa UDP sa server. Pangalan/**Add device**, **QR code & profile**, test koneksiyon/staff/traffic. Huwag publish profile/QR. **Revoke** bagong profile para bumalik; **Turn off** disconnect pero iniingatan. Split tunnel `10.66.0.0/24` lang, sariling internet/DNS, staff `http://10.66.0.1:8080`. WSL walang mirrored hindi direktang reachable, VPN off.

## Mensahe

**Messaging & interoperability**, `m`: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**. Enable e-mail/check SMTP; buttons SMTP/library address/notices-slips/overdue. Hindi lahat rules/recipients/templates, suriin preferences/private provider setup.

**Set up WhatsApp and Telegram** service/country/area/test/activation/phones. WhatsApp gateway, Telegram bot/recipients. Authorized test bago production, format/template bago mass correction. SMS `SMSSendDriver`/preferences kailangan compatible service/driver, hindi pangalan lang.

**Alerts** due/overdue/repeat/daily summary/channels, save/**Dry run (sends nothing)**. Enable task: check cron, iwas dobleng Koha. SIP2 port/network/library/device rights, alisin halimbawa at gumawa Koha account via button; account/server tugma. Huwag lahat networks para local test. Z39.50 kabanata 5, incoming/outgoing iba.

## Pamamahala

Hub Cloudflare Tunnel/UFW/staff-8080/HTTPS/Fail2ban, estado/summary, iba VPN/tunnel/direct. Huwag baguhin remote firewall nang walang matitirang daan. **Kailangang kumpirmahin:** domain/router/provider/institution, walang pangkalahatang recipe sa code.

**Koha settings & parameters** memory/workers, super librarian, zone; limitahan broad rights. **Koha languages** download/activate, download lang, activate installed/list, check panel/OPAC/staff. **Update center** system/schema hiwalay GitHub-panel, backup/maintenance; maaaring matapos session. Restart hindi patunay ng ayos na schema migration.

**Library tools** authority links/sync, duplicate authors, SQL, categories, quality/privacy. Magkaibang source/target category, filter/library, dry run bago protected approval. Ang pagsusuri ng kalidad ay nagbabasa lamang ng datos; hindi nito awtomatikong inaayos ang lahat ng problema. Anonymization nag-aalis lumang history/patron links ayon Koha, hindi bibliograpiya lahat. Patron delete filter/simulation/count, mapanira, check retention. Ang magkaparehong pangalan ay hindi patunay na iisang tao ang dalawang tala. Huwag ipalagay na magagamit ang isang kasangkapan kung hindi ipinapakita ang card nito.

## Sinuring sanggunian

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
