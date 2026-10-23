# 2. Primi passi e pannello

[Indice](README.md)

## Apertura e navigazione

Su Debian/Ubuntu preparato dall’installatore:

```bash
sudo config.sh
```

Su Windows usare icona **Koha** o applicazione MSIX. Il primo avvio può chiedere la lingua; se Textual non viene preparato, può apparire il pannello classico. Questo manuale descrive soprattutto Textual, non la numerazione dei vecchi menu.

Nella barra laterale evidenziare con frecce, aprire con **Enter** o clic. Spostare l’evidenziazione non esegue azioni. Aprire la scheda e leggere le domande. **Tab** cambia focus; uscire dai campi di testo prima delle scorciatoie alfabetiche.

| Tasto | Azione |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Terminale Debian |
| `Ctrl+B` | Mostrare/nascondere barra laterale |
| `q` | Uscire dal pannello |

Uscire a riposo non spegne il server. Durante un’operazione seguire le sue possibilità di annullamento. Installazione e restore hanno fasi non annullabili; chiudere forzatamente non è sicuro.

## Leggere lo stato

Dashboard mostra stato Koha e memoria disponibile, ultimo backup (data/età/file), disco libero, indirizzi e componenti MariaDB, Apache, RabbitMQ, Memcached, Koha con controlli HTTP. Il backup considera età e ultimo esito notturno: possono coesistere file recente e esecuzione fallita. Leggere entrambi; un indicatore favorevole non sostituisce un test di restore. Risposta HTTP non prova installazione web completata né tutte le funzioni bibliotecarie.

**Refresh** rilegge. **Restart Koha** richiede riparazione/riavvio considerando gli utenti attivi. **Export diagnostics** prepara supporto. I pulsanti possono essere disabilitati se l’installatore presente non implementa la funzione.

## Indirizzi e avvio dell’attività

Le schede aprono/copiano URL; se non è possibile lanciare browser, incollare sul proprio computer. Localmente: OPAC `http://localhost/`, staff `http://localhost:8080/`, porte 80/8080. Da altro computer usare indirizzo di rete indicato, non il proprio `localhost`. Se WSL NAT segnala LAN inaccessibile, verificare la preparazione Windows con responsabile tecnico, senza presumere accessibilità universale.

Se appare l’installatore web Koha, completarlo prima della gestione dell’acervo; le schermate dipendono dalla versione. **Create super librarian** in **Koha settings & parameters** apre creazione account: dati privati solo nell’installazione.

Prima dell’uso aggiornare dashboard, controllare componenti/indirizzi, aprire OPAC/staff dal posto corretto, generare e testare backup e verificare copia esterna e responsabili del recupero. Quest’ultimo è consiglio operativo: una copia esterna utile richiede trasferimento concluso e verificato.

## Fonti verificate

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
