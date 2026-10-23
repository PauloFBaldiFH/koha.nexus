# 7. IA locale

[Indice](README.md)

**AI**, `a`, unisce fornitore, Ollama e catalogazione foto MARC Replace/assistente staff. Configurare fornitore non installa strumenti automaticamente.

## Configurazione locale

Leggere avviso CPU/RAM: elaborazione può rallentare Koha. **Ollama on this server > Check Ollama**, poi **Install Ollama** se manca. Scegliere dalla lista e **Download** con rete/spazio necessari. Non si fissano nomi di modelli, poiché elenco/disponibilità cambiano.

**Local Ollama**, URL da verificare (default `http://127.0.0.1:11434`), **Use for chat/Use for cataloguing**. Foto richiedono visione, non solo testo. **Test connection/Save**, oppure **F5/Ctrl+S**: riempire non salva. Chat vuoto usa scelta visiva. **Load models** interroga fornitore e segnala lista integrata in caso di mancato accesso.

Installato occupa disco, caricato RAM. **Free memory** scarica senza cancellare download, ricaricabili alla richiesta. Riquadro Ollama resta con altro fornitore: verificare URL/fornitore salvati prima di presumere elaborazione locale.

## MARC Replace e foto

Installare/aggiornare pagina e aprire; verifica compilazione Koha e propone collegamenti staff. Un record per volta: file `.mrc/.xml` o testo, `biblionumber`, **Preview**, confronto e conferma. Vuoto crea nuovo: evitare duplicati. Esemplari esistenti preservati, entranti esclusi. Versione precedente MARCXML scaricabile e reinviabile allo stesso identificatore; non sostituisce backup completo.

In **AI cataloguing**, foto leggibili copertina/frontespizio/verso disponibili, JPEG/PNG/WebP, almeno una. Framework o record bersaglio, **Read the photos**, attesa e confronto bozza: titolo, responsabilità, pubblicazione, ISBN, classificazione, dati assenti. Correggere MARC prima di confermare. Classificazione proposta va verificata nelle tavole; cifra ISBN corretta non prova edizione. Bozza non salva campi di esemplare.

## Assistente e riservatezza

**Install, update or remove the assistant** sostituisce blocco notizie iniziale staff, lasciando OPAC. Ricerca Koha e interrogazioni di lettura definite, non SQL libero generato; può proporre azioni/link.

**Una proposta non è un cambiamento eseguito.** Verificare record, prima/dopo, effetto; **Approve & Execute** con permessi propri necessario. Una modifica intervenuta può richiedere nuova proposta. Consultare cambiamenti confermati; cancellare conversazione/rimuovere assistente non li annulla. Rimozione elimina conversazioni e conserva registro delle azioni approvate.

Monitorare hardware/Koha, evitare nuove foto se lento e liberare memoria se opportuno. Nessuna latenza garantita. Fornitore remoto riceve richiesta: valutare politica dati/immagini, non testare con lettori reali. Etichette di costo non garantiscono gratuità.

**Da confermare:** RAM/disco/tempi per ogni scelta e hardware; minimo Koha non garantisce prestazioni IA.

## Fonti verificate

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
