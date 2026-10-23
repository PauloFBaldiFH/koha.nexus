# 1. Installazione

[Indice](README.md)

## Ambiente e requisiti

Su Windows, Koha funziona in Debian tramite WSL 2. Gli strumenti Windows preparano l’ambiente, aprono il pannello e integrano l’applicazione. Su Debian/Ubuntu servizi e pannello vengono installati direttamente. Per aprire un catalogo esistente usare il pannello, non ripetere l’installazione.

| Ambiente | Controlli presenti nel codice |
| --- | --- |
| Windows | Windows 10 versione 2004, build 19041 o successiva, oppure Windows 11; 64 bit e virtualizzazione attiva; 8 GB RAM, 12 GB consigliati; 10 GB liberi sull’unità di installazione, 20 GB consigliati. |
| Debian/Ubuntu | Debian 11/12/13 oppure Ubuntu 22.04/24.04; architetture amd64 e arm64 indicate dall’installatore; meno di 5 GB blocca, da 5 a meno di 10 GB avvisa, almeno 10 GB supera il controllo. |

Catalogo, allegati, indici e backup richiedono ulteriore spazio. **RAM Linux, da confermare:** la guida consiglia 4 GB su server dedicato, preferibilmente 8 GB; desktop/virtualizzazione 8 GB, preferibilmente 12 GB. Il preflight Linux non impone una soglia numerica attuale: superarlo non garantisce capacità per ogni carico. Windows ammette memoria riservata all’hardware con soglie rilevate di 7,5 e 11,5 GB.

Linux richiede privilegi amministrativi e accesso al repository Koha. TCP 80/8080 servono OPAC/staff. Se occupate, il pannello propone di fermare i servizi interessati: **accettare soltanto se possono essere interrotti.**

## Windows con PowerShell

Accedere all’account amministratore Windows che userà Koha e aprire PowerShell come amministratore nello stesso account:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Se l’elevazione richiede l’account di un’altra persona, annullare e accedere correttamente: WSL appartiene all’account di installazione. Leggere i controlli e risolvere la virtualizzazione disattivata. Rispondere nella finestra alle domande dell’account Debian, distinto dall’account bibliotecario Koha.

Attendere WSL 2 e Debian. Il riavvio richiesto registra la ripresa al prossimo accesso Windows. Nel pannello scegliere lingua e **Install Koha server**. Dopo il completamento uscire normalmente dal pannello e attendere la conclusione dell’integrazione Windows.

Cartella predefinita `C:\Koha`; le installazioni precedenti possono mantenere `C:\KohaEasy`. Non spostarla per riparare un’interruzione. Annotare il messaggio: le fasi completate sono registrate e il flusso può riprendere o riaprire il pannello per finire il server. Ciò non rende innocua la reinstallazione distruttiva.

## Windows con MSIX

MSIX prepara lo stesso WSL: installare il pacchetto non configura automaticamente server e database. Usare PowerShell **normale, senza elevazione preventiva**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

L’ausiliario scarica il pacchetto previsto nel codice, ne verifica l’origine, chiede autorizzazione amministrativa e installa per l’utente corrente. Non ignorare rifiuti. Al primo avvio attendere preparazione e completare la procedura nel pannello; uscire normalmente e aspettare collegamenti, attività e rete Windows. Una chiusura anticipata non completa il server: riaprire per continuare.

**Da confermare:** disponibilità e indirizzo pubblico Microsoft Store; il supporto di packaging non dimostra pubblicazione. Anche il funzionamento completo MSIX su ARM64 è da confermare: manifesto x64, supporto arm64 Linux non sufficiente. Il manifesto ammette Windows precedente al flusso WSL completo: pianificare con i requisiti completi sopra.

## Debian o Ubuntu

Nel terminale del server:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Per conservare repository e traduzioni:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Scegliere lingua e **Install Koha server**. Correggere errori critici prima di proseguire, leggere avvisi senza interpretarli come garanzia di capacità. Una distribuzione WSL deve usare WSL 2 con systemd attivo; WSL 1 viene rifiutato. Per Windows preferire preparazione guidata precedente.

## Installare dal pannello

1. Aprire **Install Koha server**, attendere preflight e leggere rapporto. Valutare l’impatto di liberare porte.
2. Verificare il computer di destinazione prima di confermare; accettare fuso rilevato o scegliere regione/città.
3. **Istanza esistente: fermarsi e controllare.** Reinstallare elimina database/configurazione e richiede ulteriore conferma con parola esatta `REINSTALL`. Non usarlo solo per aprire o aggiornare il pannello.
4. Attendere senza chiudere: non annullabile. Stima 10–30 minuti dipendente da hardware/rete.
5. Leggere risultato e rapporto; completamento con problemi non significa servizi sani. Valutare riavvio offerto e, in MSIX, aspettare continuazione Windows.

Non copiare dati privati del risultato in documenti pubblici o richieste di assistenza.

## Fonti verificate

- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [installer](../../../installer).
- [README.md](../../../README.md).
- [install.ps1](../../../windows/install.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [instalar_msix.ps1](../../../windows/msix/instalar_msix.ps1).
- [KohaMsixEntry.cs](../../../windows/msix/KohaMsixEntry.cs).
- [KohaMsixPanel.ps1](../../../windows/KohaMsixPanel.ps1).
- [compilar_msix.ps1](../../../windows/msix/compilar_msix.ps1).
- [install.py](../../../panel/kei_panel/routines/install.py).
