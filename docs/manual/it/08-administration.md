# 8. Amministrazione, messaggi e VPN

[Indice](README.md)

Prima di amministrare verificare stato e backup recente. Configurazione non prova funzionamento nella rete: controllare dopo.

## Cron

**Schedules & cron tasks**, `s`: attivazione/frequenza/ora, giorno o espressione propria. **Reload**, attivare necessario, ora `HH:MM`, **Preview**, **Save** e conferma, poi rileggere. Gestisce `/etc/cron.d/koha_tasks`, conserva `koha_tasks.bak`. Disattivate restano commentate con orario; righe proprie preservate. **Defaults** riempie, richiede salvataggio.

SQL giornaliero 23:00, MARC domenica 03:00 predefiniti, verificare fuso/personalizzazioni. Server/Linux devono essere in esecuzione; cron non garantisce accensione Windows. Avvisi Koha hanno meccanismo separato.

## VPN

**Security & access hub > WireGuard VPN**, `v`, indirizzo pubblico/nome e porta UDP. **Set up the VPN** mostra modifiche prima della conferma; router deve inoltrare UDP al server. Nome dispositivo, **Add device**, **QR code & profile** al client; verificare connessione/staff/traffico. Non pubblicare profili/QR.

**Revoke** invalida profilo, ne serve nuovo per tornare; **Turn off** disconnette ma conserva. Split tunnel solo `10.66.0.0/24`, internet/DNS restano propri. Staff connesso `http://10.66.0.1:8080`. WSL senza rete mirrored è segnalato non direttamente raggiungibile, VPN disattivata.

## Comunicazione

**Messaging & interoperability**, `m`: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**. Attivare e-mail, controllare SMTP predefinito; pulsanti a SMTP, indirizzo biblioteca, avvisi/ricevute, regole ritardo. Non compila ogni destinatario/regola/modello: verificare preferenze e autenticazione privata del fornitore.

**Set up WhatsApp and Telegram** gestisce servizio, paese/prefisso, test, attivazione e telefoni. WhatsApp necessita gateway, Telegram bot/destinatari. Test autorizzato prima produzione, formati/modelli prima di correzione massiva. SMS porta a `SMSSendDriver` e preferenze lettori; driver/servizio compatibili necessari, nome solo non basta.

**Alerts**: promemoria scadenza, ritardi, ripetizione, riepilogo quotidiano/canali; salvare e **Dry run (sends nothing)** simulare. Attiva job: verificare cron, evitare doppioni con avvisi Koha. SIP2: porta/rete/biblioteca/permessi dispositivo, rimuovere esempi, creare account Koha dal pulsante; conto/server devono corrispondere. Non esporre tutte le reti per prova locale. Z39.50 rinvia al capitolo 5, ingresso/uscita distinti.

## Sicurezza e gestione

Hub con Cloudflare Tunnel, UFW, restrizione 8080 staff, HTTPS, Fail2ban. Leggere stato/riepilogo, distinguere tunnel/VPN/accesso diretto. Non cambiare firewall remoto senza sapere come continuare amministrazione. **Da confermare:** dominio/router/provider/politica istituzionale; nessuna ricetta universale deducibile dal codice.

**Koha settings & parameters** dimensiona memoria/processi, crea super bibliotecario e imposta fuso; limitare privilegi. **Koha languages** distingue scaricare/attivare, solo scaricare, attivare installato, elencare; verificare pannello/OPAC/staff.

**Update center** distingue pacchetti/schema da pannello GitHub. Backup e manutenzione; aggiornamento pannello può chiudere sessione per ricaricare. Schema fallito non è risolto necessariamente da riavvio.

**Library tools** include sincronizzazione/legami autorità, duplicati, SQL, categorie, qualità, privacy. Categoria: origine/destinazione diverse, filtro/biblioteca, simulazione prima di conferma con backup. Qualità legge, non ripara tutto. Anonimizzare elimina legami di vecchio storico con lettori secondo Koha, non bibliografia intera. Eliminare lettori richiede filtri, simulazione e quantità confermata: distruttivo, verificare conservazione. Nomi simili non provano stessa persona; strumenti nascosti non sono schede disponibili.

## Fonti verificate

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
