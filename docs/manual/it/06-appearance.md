# 6. Aspetto di OPAC e staff

[Indice](README.md)

**OPAC and Staff Appearance**, `o`, configura separatamente catalogo pubblico e staff/intranet.

## Applicare con controllo

**Sync current OPAC settings** legge preferenze attuali senza applicare. Modificare un gruppo per volta. **Preview** mostra CSS/JavaScript/contenuto da scrivere, non rendering completo. **Apply** con riepilogo/conferma crea prima backup. In browser verificare pagine iniziali, ricerca, record, login e schermo piccolo.

Blocchi in `OpacUserCSS/OpacUserJS`, staff `IntranetUserCSS/IntranetUserJS` quando necessario. Mantiene blocchi propri, senza garanzia contro conflitti visivi con altre personalizzazioni.

## Leggibilità e immagini

Texture, sfocatura, opacità, angoli, colori/fondi, chiaro/scuro e tema iniziale: mantenere contrasto con immagini/trasparenze. Staff aggiunge barra, ricerca rapida, moduli, densità tabelle, testo e contrasto. Attivare **Apply color theme to Staff Client**; **Copy OPAC preset** riempie soltanto, **Apply** scrive.

File accessibile al server, servizio offerto o URL HTTPS diretta. Accetta PNG/JPEG/GIF/WebP/ICO, rifiuta SVG. File solo sul computer del bibliotecario va reso accessibile. Usare immagini autorizzate, descrizione accessibile nel login; pagina hosting non è sempre indirizzo diretto. Controllare servizi esterni senza pubblicare informazioni private.

## Carosello, pulsanti e testi

Novità oppure lista Koha con numero da `shelfnumber=`. Titolo, quantità, stile, velocità, autoplay e **Refresh carousel**. Dipende da record/copertine disponibili e rete esterna: copertina assente non equivale a record cancellato.

Pulsanti OPAC/staff separati: testo/indirizzo/destinazione/ordine, **Add a button** e rimozione riga prima di applicare. Login supporta immagine/descrizione/HTML filtrato da script, stili, eventi; niente istruzioni riservate. Notizie dei due lati hanno titolo/testo/pulsanti propri, senza sostituire notizie della biblioteca.

Crediti come `Field: value` con campi indicati; link extra testo `|` indirizzo, massimo sei; solo informazioni pubbliche.

**Remove** conferma e salva prima di eliminare blocchi del tema e tornare all’aspetto Koha mantenendo personalizzazioni. Non è restore completo né annulla altra amministrazione. Correggere il gruppo errato e applicare; conservare errori per diagnosi.

## Fonti verificate

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
