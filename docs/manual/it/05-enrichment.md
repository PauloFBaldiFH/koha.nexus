# 5. Arricchimento e Z39.50/SRU

[Indice](README.md)

## Record esistenti

Importare acquisisce export; arricchire cerca integrazioni o un libro nuovo. Titolo corrispondente non sostituisce revisione bibliografica. **Library tools > Enrich from world catalogues**, `n`; vecchia schermata bibliografica a lotti non è più il percorso corrente.

Inserire `all` o `biblionumbers` come `101, 102, 500-510`, **Search**. Seguire lavoro/server; grandi attività restano in background e possono riprendere dopo riavvio, con macchina disponibile. **Pause/Resume** controlla ricerca, non annulla modifiche. Leggere rapporto confrontando soggetti, classificazione, note, descrizione fisica. **Search more servers** interroga fonti non ancora usate; **Choose donor** sceglie fonte di gruppi di campi disponibili. **Apply** solo dopo revisione e conferma: ricerca/rapporto non scrivono proposte.

Attualmente Z39.50 diretto. Limiti e indisponibilità possono ritardare; nessun risultato non prova assenza del libro. Nessun tetto generale di 50 record: soglia usata per protezione dell’applicazione, copie per piccoli lavori, backup completo verificato per grandi. Revisione sempre necessaria.

**Revert** recupera versioni precedenti secondo protezioni, preservando modifiche successive. Non è restore globale né annulla ogni modifica altrui.

## Nuovo libro e autorità

ISBN/titolo, con autore/anno se utile, **Find**, esaminare fonti e scegliere. **Import as new record** aggiunge con conferma senza sostituire record con stesso ISBN. Rimuove `9XX` locali del donatore e registra fonte, evitando copie altrui come proprie. Verificare e creare esemplari locali regolarmente. Lotto MARC trattabile con **Undo a MARC import**.

**Enrich & standardize authorities**, `h`: ambito, forme esatte/vicine. Vicine possono suggerire grafia e autorità preliminari; controllare attentamente. Prima autorità Koha proprie, poi base d’arricchimento/server diretti; fonti brasiliane prioritarie, soggetti limitati a esse. Non garantisce conformità alla politica locale.

**Apply** crea autorità/legami con backup, preservando record modificati dopo rapporto. Revert mantiene nuove autorità ancora collegate anziché eliminarle indiscriminatamente.

## Z39.50/SRU

**Z39.50 / SRU servers**, `z`: ingresso permette ricerche esterne e interruttore agisce sulla porta firewall. Rete comunitaria è distinta dai server diretti d’arricchimento. Salute con **Reset/Reset all** consente nuovo tentativo, non ripara remoto. Selezionare con spazio, **Scan** ricerca un vero record, **Add to Koha** aggiunge fonti selezionate funzionanti.

Supporto SRU in configurazione non significa SRU per tutte le ricerche. Consultare fuori non richiede esporre ingresso.

**Da confermare:** disponibilità, copertura e condizioni di ogni fonte dalla rete locale al momento dell’uso.

## Fonti verificate

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
