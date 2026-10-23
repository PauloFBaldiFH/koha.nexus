# 9. Diagnostica e log

[Indice](README.md)

Annotare azione, ora, errore completo e cosa funziona. Pagina accessibile, servizio attivo e ricerca riuscita sono verifiche diverse. Non reinstallare o fare restore come risposta iniziale universale.

## Diagnosi e percorsi

Aggiornare **Control Dashboard**. **Diagnostics & maintenance center > Detailed server & Koha status**, poi **Full system health check**, leggere rapporto. **View latest validation report** lo riapre; **Export diagnostics** nel dashboard mostra percorso del pacchetto. Nonostante oscuramento di dati d’accesso, controllare lettori, file, indirizzi sensibili prima di condividere; non copiare tutta installazione. Il fallback classico se Textual fallisce non annulla operazioni precedenti: conservare errore/log.

| Percorso | Contenuto |
| --- | --- |
| `/var/log/koha-easy-install/` | Directory principale Linux |
| `apt.log` | Pacchetti e relative fasi |
| `validacao-*.log` | Rapporti datati |
| `new-panel.log` | Errori Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/export |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | Indici/ricerca |
| `/var/log/koha-easy-install/tools/` | Strumenti |
| `C:\Koha\logs`, in precedenza `C:\KohaEasy\logs` | Windows secondo installazione |

`*` indica file datati, forse assenti prima del primo avvio. Preferire percorso esatto del messaggio. **Library tools > View tool logs** seleziona data/routine; accesso ristretto per possibili dati personali.

Rapporto con contesto/data/versione/OK/avvisi/errori/info. Leggere messaggi, non solo totale. **No critical failures** può avere avvisi; backup vecchio non equivale a guasto database. Dopo correzione rivalidare e confrontare.

**Real-time Apache log auditing** sceglie staff/OPAC e percorsi alternativi vecchi. Textual **Pause/p** ferma aggiornamento visuale, non Apache; **Continue** riprende, **Back/Esc** esce. Classico `Ctrl+C` per quel monitoraggio, non ogni lavoro. Leggere ora e contesto di `error/fatal/denied/fail`; colore non determina causa.

## Sintomi

- OPAC/staff non apre: Apache/MariaDB/Plack/cache e indirizzo locale/rete/VPN/tunnel. `localhost` è computer del browser. **Restart / repair Koha services (Memcached, Plack)** può interrompere; controllare esito e rivalidare.
- Record non trovato: motore/coda/indice-database. **Search engine & indexing > Repair / rebuild indexing**, leggere conferme e aspettare; cambio a Elasticsearch non è primo passo obbligatorio.
- Backup manca: orario/esito/disco, macchina/Linux al cron, `.part` incompleto; `backup_sql.log`, integrità o manuale. Non cancellare ultima copia valida senza altra sicura, evitare concorrenza.
- Importazione fallisce/quantità inattese: log Magic Import/MARC, ingresso/preparazione/scrittura, modo/codici/barcode/scarti/duplicati. Anteprima breve non certifica tutto; validazione completa e fasi finite prima di ripetere.
- Restore fallisce: identificare fase; indice può fallire dopo base restaurata e rollback può fallire anch’esso. Controllare base/ricerca/validazione.
- IA/arricchimento lento: Ollama/scelta/memoria o lavoro/server/limiti; non duplicare grandi attività per ritardo. Servizio esterno e RAM locale richiedono indagini diverse.

## Icona Windows

PowerShell dell’utente connesso, **senza amministratore**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Può ricreare collegamenti e riavviare tray, non è sola lettura. Scrive `diagnose-<date>.txt` in `logs` rilevato: conservare percorso/errore. Diverso dall’installazione amministrativa.

**Deep database optimization & log cleanup** manutiene e riavvia ma può cancellare tracce utili; conservare diagnosi prima e pianificare, non nascondere errori. Per assistenza: versione, Windows/WSL o distribuzione, azione/ora/errore completo, OPAC/staff/ricerca e operazione precedente, estratti controllati per privacy.

**Da confermare:** causa senza messaggio completo e log; non attribuire automaticamente a rete/installazione.

## Fonti verificate

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
