# 3. Backup e restore

[Indice](README.md)

## Centro, tipi e cartelle

**Backup center**, tasto `b`, riunisce ultimo backup, dimensione, risultato, **Compression** e schede.

| Scheda | Scopo |
| --- | --- |
| Download latest backup | Copiare file più recente trovato |
| Generate manual backup and download to PC | Generare, verificare e trasferire il database |
| Export MARC21 records now | Esportare bibliografia e autorità |
| Restore database | Sostituire database corrente |
| Configure cloud backup | Configurare invio esterno |
| Test integrity of latest backup | Provare importazione temporanea |

**Restore database è una scheda**, non pulsante superiore né voce autonoma del menu principale. Risultato riguarda ultima esecuzione notturna; data/dimensione il file più recente, eventualmente diverso.

SQL contiene database Koha, non immagine completa Windows/Debian o tutti i file. MARC21 contiene bibliografia/autorità in `.tar.gz`; non sostituisce SQL per lettori/circolazione. Prima del restore di un database con tabelle viene creata copia di sicurezza validata; database vuoto può saltarla.

Cartelle: `/var/backups/koha_sql` per SQL automatici/sicurezza, `/var/backups/koha_marc` per MARC. Backup manuale ha destinazione propria, predefinita `backups` nella cartella personale rilevata. `.part` è provvisorio fino a verifica e promozione a file finale.

## Compressione

**Compression**: gzip `.sql.gz` compatibile, Zstandard `.sql.zst` rapido/più piccolo per grandi cataloghi, XZ/LZMA `.sql.xz` minimo ma lento. Selezione salvata subito, senza altro pulsante, applicata a nuovi backup notturni/manuali/sicurezza, non ricomprime esistenti. Se programma manca o installazione fallisce, leggere errore e formato reale: può ripiegare su gzip. Restore riconosce indipendentemente `.sql`, `.sql.gz`, `.sql.zst`, `.sql.xz`; estensione non prova validità.

## Creare, scaricare, verificare

1. **Generate manual backup and download to PC**, controllare cartella server scrivibile.
2. **Save backup**, attendere generazione/controllo; durante salvataggio/copia la schermata non chiude.
3. Controllare nome/dimensione/percorso. WSL: **Save to Windows Downloads**, **Choose folder in Windows**; accesso remoto: comando mostrato da eseguire sul proprio computer.
4. Verificare ricezione e **Finish and exit**.

Pulsanti Windows solo WSL; non copiare comandi altrui perché dipendono da file/server rilevati. Se altro backup/restore è attivo, attendere senza aggirare blocco comune con operazioni concorrenti esterne.

**Download latest backup** scarica file esistente, non ne genera. Desktop Linux/WSL tenta Downloads, SSH può mostrare comando locale. Se assente, generare manuale.

**Test integrity of latest backup**: verificare file/data, **Choose another file** per cambiare, confermare e attendere importazione temporanea. Esito positivo indica quantità tabelle/record/lettori senza sostituire produzione. Vale per quel file e ambiente: mantenere accesso alla stessa copia trasferita.

## MARC e cloud

**Export MARC21 records now** richiede conferma, prepara pacchetto di bibliografia/autorità, mostra percorso/contenuto e download/trasferimento. Koha resta operativo; cloud configurato riporta anche invio. Tenere SQL per recupero completo.

**Configure cloud backup** offre due percorsi Google Drive e altri servizi, inclusi OneDrive, MEGA, S3. Scegliere autorizzazione su server o altro computer, seguire solo URL/istruzioni mostrate. S3 distingue servizio, regione/endpoint, bucket. Attendere prova reale e controllare ricezione; configurazione fallita non è una copia affidabile.

Dati privati solo nell’installazione, non manuale, immagini pubbliche o supporto. Questo testo non cita i relativi file. Predefiniti: SQL ogni giorno 23:00, MARC domenica 03:00, ora server; cron personalizzato può differire.

## Restore distruttivo

**La conferma autorizza sostituzione del database attuale.** Pianificare manutenzione e copia esterna: raccomandazione operativa, non trasferimento automaticamente eseguito dal pannello.

1. **Restore database**, scegliere file accessibile al server, trasferendo secondo guida se necessario. WSL può copiarlo da Windows a Linux prima del restore.
2. Leggere accessibilità, contenuto, integrità, spazio; indagare file sospetto/incompleto nonostante estensione.
3. Ricontrollare file alla conferma. Fino ad allora si può rinunciare; dopo attendere senza chiudere, flusso non annullabile.

Prima importa SQL in database temporaneo, verifica quantità e tabelle essenziali. Errore ferma prima di sostituire. Con tabelle esistenti crea copia SQL validata `pre_restore_safety_backup_` con data/ora/compressione; se fallisce non deve cancellare database esistente. Vuoto può saltare copia.

Poi ferma client, ricrea/importa, aggiorna schema, sincronizza ricerca, ricostruisce indici, riavvia servizi. Tenta ripristino tema salvato se stato disponibile.

Fallimento test temporaneo/copia non implica sostituzione. Su ricreazione/importazione/schema può tentare recupero precedente secondo fase/copia, ma **anche rollback può fallire**. Un indice può fallire dopo database restaurato: non presumere ritorno del catalogo precedente.

Conservare messaggio e `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log`, per indicizzazione `/var/log/koha-easy-install/zebra-rebuild.log`. Tornare alla scheda del centro, non numeri vecchi, chiedere aiuto se stato incerto. Verificare dashboard, record e ricerche OPAC/staff. Fine SQL non prova recupero di file esterni.

## Fonti verificate

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
