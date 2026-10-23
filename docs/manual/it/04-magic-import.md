# 4. Importazione magica

[Indice](README.md)

## Preparazione e formati

Magic Import legge bibliografia, esemplari, lettori e autorità. Riconoscere formato non garantisce interpretazione di ogni campo, soprattutto senza intestazioni e nei campi locali. Conservare originale/backup verificato, provare campione con più copie, accenti, vuoti ed eccezioni, confrontare quantità origine/anteprima. Non pubblicare esportazioni lettori.

**Magic Import Tool**, `i`, poi scheda e selettore file/cartella. Deve essere accessibile al Linux del pannello; un file solo sul computer del browser/terminale remoto non è automaticamente sul server.

| Input | Controllo |
| --- | --- |
| MARC21 ISO 2709, MARCXML, testo MARC | Titoli, accenti, autorità, esemplari. `.mrk` MarcEdit riconosciuto, senza obbligo di conversione per sola estensione. |
| CSV/TSV, `.xlsx`, `.xls`, `.ods`, `.dbf` | Separatore, intestazioni disponibili, valori e destinazioni. |
| JSON/XML tabellare | Struttura; XML generico non equivale a MARCXML. |
| SQL tabellare anche senza intestazioni | Estrae dati/relazioni riconosciuti, non esegue un programma di migrazione; verificare ambiguità. |
| ISIS | Export PostgreSQL riconosciuto con `acervo`; maestro CDS/ISIS `.mst` da esportare WinISIS ISO 2709. |
| Biblioteca Fácil | Backup riconosciuto/cartella con tabelle correlate insieme, rivedendo separatamente record, lettori, prestiti, prenotazioni. |
| Backup Koha completo | Passa a restore, sostituendo la base anziché aggiungere record. |

Dump PostgreSQL altrui, specialmente binario `pg_dump`, non è MariaDB pronta. Se rifiutato, esportare MARC/fogli dal sistema origine. Controllare ogni membro compresso. PDF, immagini, documenti ed eseguibili non sono esportazioni bibliografiche leggibili qui.

## Mappatura integrata

Verificare **Bibliographic/Patrons/Authorities** e correggere modo. Griglia record/campi e destinazioni; divisore o **Ctrl+Up/Down** regola altezza. Conservare, deviare, testo fisso o ignorare, comprendendo prima relazioni degli identificatori.

**Values of this Koha** mostra codici, biblioteca/tipo/categoria predefiniti e sostituzioni origine/destinazione. **Record preview** mostra risultato; **Check the whole file** prepara/valida tutto senza importare in questa fase. Nominare/**Save** profilo, selezionare/**Use**, rivedere se struttura cambia. **Apply/Ctrl+S** accetta mappatura e continua, non conferma finale di scrittura. **Skip: import as it is/Esc** salta mappatura manuale, non annulla l’intera procedura.

Raggruppamento e correzioni richiedono anteprima; evitare alterazioni indiscriminate di sigle, nomi e codici.

## Esemplari, lettori e autorità

`952` nativo viene preservato, con rimappatura richiesta di biblioteca/tipo. Non sostituire codice valido solo diverso dal predefinito. Rivedere barcode, biblioteca proprietaria/attuale, collocazione, tipo, ubicazione, acquisizione. `949/852/950/990` locali hanno sottocampi con significati potenzialmente diversi fra Pergamum/Biblivre.

Deposito legale con `DL` e data non crea automaticamente copia locale; rivedere esclusioni e prove indipendenti d’inventario. Barcode assente richiede revisione predefinita; generazione richiede scelta esplicita e identità stabile migrazione/origine, senza rinumerare collisioni silenziosamente. In SQL relazionale serve legame riconosciuto, non posizione colonne/ordine righe. Correggere legami incerti prima di importare.

**Patrons**: nome/cognome, tessera, contatti, indirizzo, date, biblioteca/categoria esistente. E-mail/CPF/data riconosciuti sono indizi; nascita/iscrizione/scadenza possono apparire uguali. L’aggiornamento di lettori esistenti è chiesto con corrispondenza tessera, non equivale a soli nuovi. Non assegnare privilegi/autenticazione per supposizione.

**Authorities**: identificatore, intestazione autorizzata, varianti, relazioni, tipo. Cambio modo non inventa dati mancanti.

## Conferma e controllo

Leggere quantità, scarti e domande. Per record esistenti scegliere conservazione più nuovi esemplari, sostituzione entrante o nuovi titoli senza confronto. Evitare ripetizioni involontarie.

**Un errore successivo può lasciare fasi precedenti importate.** Conservare riepilogo/log e controllare prima di ripetere. Verificare campioni, copie, lettori e collegamenti in Koha. **Library tools > Undo a MARC import** tratta lotti MARC, non annulla universalmente lettori/prestiti/prenotazioni. Per base completa seguire Backup center con precauzioni.

**Da confermare:** compatibilità di layout proprietario/versione specifica senza campione e verifica.

## Fonti verificate

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
