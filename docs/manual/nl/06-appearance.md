# 6. Vormgeving van OPAC en staff

[Inhoud](README.md)

**OPAC and Staff Appearance**, `o`, heeft aparte instellingen voor openbaar en staff/intranet.

## Gecontroleerd toepassen

**Sync current OPAC settings** leest huidige waarden zonder toe te passen. Eén groep tegelijk wijzigen. **Preview** toont CSS/JavaScript/inhoud, geen volledige browserweergave. **Apply** toont samenvatting/bevestiging en maakt eerst databasebackup. Controleer thuis-/zoek-/record-/inlogpagina’s in browser, ook klein scherm.

Blokken in `OpacUserCSS/OpacUserJS` en waar nodig `IntranetUserCSS/IntranetUserJS`. Eigen blokken blijven, maar visuele conflicten met andere aanpassingen blijven mogelijk.

## Leesbaarheid en beelden

Textuur, vervaging, dekking, hoeken, accent-/achtergrondkleuren, licht/donker en startthema; houd contrast bij beeld/transparantie. Staff heeft bovenbalk, snelzoeken, modulekaarten, tabeldichtheid, tekst en contrast. **Apply color theme to Staff Client** inschakelen. **Copy OPAC preset** vult alleen; **Apply** schrijft.

Serverbereikbaar bestand, aangeboden beelddienst of directe HTTPS-URL. PNG/JPEG/GIF/WebP/ICO toegestaan, SVG geweigerd. Bestand alleen op eigen pc moet eerst serverbereikbaar. Gebruik beelden met rechten en toegankelijke omschrijving bij login; hostingpagina is niet altijd direct beeldadres. Externe diensten controleren, geen privé-informatie publiceren.

## Carrousel en inhoud

Nieuwe aanwinsten of Koha-lijst met nummer uit `shelfnumber=`. Titel/aantal/stijl/snelheid/autoplay en **Refresh carousel**. Hangt van beschikbare records/covers/netwerk af; ontbrekende cover betekent geen verwijderd record.

OPAC-/staff-knoppen apart met tekst/adres/doel/volgorde; **Add a button**, verwijderen per rij vóór toepassing. Login ondersteunt beeld/omschrijving/HTML, filtert scripts/stijlen/events; geen interne vertrouwelijke instructies. Nieuws aan beide zijden met eigen titel/tekst/knoppen; panelitems vervangen eigen bibliotheeknieuws niet.

Voettekst als `Field: value` volgens getoonde velden; extra links tekst `|` adres, maximaal zes, alleen openbaar.

**Remove** bevestigt en maakt backup vóór verwijderen van themablokken om Koha-vormgeving met eigen aanpassingen terug te brengen. Geen volledige restore of terugname van ander beheer. Foute groep aanpassen/opnieuw toepassen; foutbericht voor diagnose bewaren.

## Gecontroleerde bronnen

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
