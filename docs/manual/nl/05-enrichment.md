# 5. Verrijking en Z39.50/SRU

[Inhoud](README.md)

## Bestaande records verrijken

Import haalt exportgegevens binnen; verrijking zoekt aanvulling of een nieuw boek. Titelovereenkomst vereist nog bibliografische beoordeling. **Library tools > On-demand enrichment**, `n`; oude bibliografische batchscherm is geen huidige menuroute.

`all` of `biblionumbers` zoals `101, 102, 500-510`, **Search**. Taak/servers volgen; groot werk draait op achtergrond en kan na herstart verder, met beschikbare machine. **Pause/Resume** stuurt zoeken, draait geen toegepaste wijzigingen terug. Rapport openen, onderwerpen/classificatie/notities/fysieke beschrijving vergelijken. **Search more servers** vraagt nog ongebruikte bronnen; **Choose donor** kiest bron voor beschikbare veldgroepen. **Apply** na beoordeling/bevestiging; zoeken/rapport schrijft nog niet.

Huidig direct Z39.50. Limieten/storingen kunnen vertragen; geen resultaat bewijst geen afwezigheid. Geen algemene grens van 50 records: drempel voor bescherming bij toepassen, recordkopieën voor kleine taken, volledige gecontroleerde backup voor grote. Beoordeling blijft nodig.

**Revert** herstelt eerdere versies volgens beveiligingen en bewaart later bewerkte records. Geen algehele restore of ongedaan maken van elke wijziging door anderen.

## Nieuw boek en autoriteiten

ISBN/titel plus auteur/jaar, **Find**, bronnen beoordelen/selecteren. **Import as new record** voegt na bevestiging toe zonder bestaand gelijk ISBN te vervangen. Verwijdert lokale `9XX` van donor en noteert herkomst, zodat vreemde exemplaren niet eigen worden. Controleer record, voeg lokale exemplaren normaal toe; MARC-batch via **Undo a MARC import** behandelen.

**Enrich & standardize authorities**, `h`: bereik, exacte/nabije vormen. Nabije kunnen spellingcorrectie/voorlopige autoriteiten voorstellen, zorgvuldig beoordelen. Eerst eigen Koha, dan verrijkingsbasis/directe servers; Braziliaanse bronnen eerst, onderwerpen uitsluitend daarvan. Geen garantie voor lokaal beleid.

**Apply** maakt benodigde autoriteiten/links met veiligheidsbackup, behoudt sinds rapport bewerkte records. Revert bewaart nieuw gemaakte autoriteiten zolang gekoppeld.

## Servers

**Z39.50 / SRU servers**, `z`: inkomende server laat andere bibliotheken zoeken en schakelt firewallpoort mee. Gemeenschapsnetwerk is anders dan directe verrijkingsservers. Gezondheid met **Reset/Reset all** staat nieuwe poging toe, repareert externe dienst niet. Spatie selecteert, **Scan** zoekt echt record, **Add to Koha** registreert gekozen werkende bronnen.

SRU in configuratie betekent niet SRU bij elke verrijkingsvraag. Buiten zoeken vereist inkomende server niet openzetten.

**Nog te bevestigen:** bereikbaarheid/dekking/toegangsvoorwaarden per bron vanaf lokale netwerk op gebruiksmoment.

## Gecontroleerde bronnen

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
