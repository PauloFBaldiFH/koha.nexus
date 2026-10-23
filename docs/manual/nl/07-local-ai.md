# 7. Lokale AI

[Inhoud](README.md)

**AI**, `a`, bundelt aanbieder, Ollama, foto-catalogisering MARC Replace en staff-assistent. Aanbieder instellen installeert hulpmiddelen niet automatisch.

## Lokaal instellen

Lees CPU/RAM-waarschuwing: lokaal verwerken kan Koha vertragen. **Ollama on this server > Check Ollama**, zo nodig **Install Ollama**. Lijstkeuze/**Download** vereist netwerk/schijf. Geen vaste modelnamen wegens veranderende beschikbaarheid.

**Local Ollama**, URL controleren (standaard `http://127.0.0.1:11434`), **Use for chat/Use for cataloguing**. Foto’s vereisen beeldcapaciteit, tekst alleen volstaat niet. **Test connection/Save** of **F5/Ctrl+S**; invullen slaat niet op. Leeg chatveld gebruikt beeldkeuze. **Load models** vraagt aanbieder en meldt ingebouwde lijst als fallback.

Geïnstalleerd gebruikt schijf, geladen RAM. **Free memory** ontlaadt zonder downloads te verwijderen; later opnieuw laadbaar. Ollama-vak blijft met andere aanbieder zichtbaar: opgeslagen aanbieder/URL controleren vóór lokale verwerking aannemen.

## MARC Replace en foto’s

Pagina installeren/bijwerken/openen; installer controleert compilatie en staff-links. Eén record tegelijk: `.mrc/.xml` of tekst, `biblionumber`, **Preview**, vergelijken/bevestigen. Leeg maakt nieuw: doublures vermijden. Bestaande exemplaren blijven, inkomende itemvelden vervallen. Vorige MARCXML-versie downloadbaar en aan zelfde ID opnieuw in te sturen; geen vervanging van volledige backup.

In **AI cataloguing** leesbare foto’s omslag/titelpagina/keerzijde, waar aanwezig; JPEG/PNG/WebP, minimaal één. Framework of te vervangen record kiezen, **Read the photos**, wachten en concept tegen beelden controleren: titel/verantwoordelijkheid/publicatie/ISBN/classificatie/ontbrekend. MARC corrigeren vóór schrijven. Voorstelclassificatie in bibliotheektabellen controleren; juiste ISBN-controlecijfer bewijst geen juiste editie. Concept bewaart geen exemplaarvelden.

## Assistent en privacy

**Install, update or remove the assistant** vervangt staff-startnieuws door chat, niet OPAC. Koha-zoeken en vastgelegde leesvragen, geen vrij gegenereerde SQL; links/actievoorstellen mogelijk.

**Voorstel is nog geen uitvoering.** Record/voor-na/gevolg beoordelen; **Approve & Execute** en eigen rechten vereist. Tussentijdse wijziging kan afwijzing/nieuw voorstel vragen. Bevestigde acties raadpleegbaar; gesprek wissen/assistent verwijderen draait ze niet terug. Verwijderen wist gesprekken en bewaart goedgekeurde wijzigingshistorie.

Hardware/Koha volgen, bij traagheid geen nieuwe foto’s starten en zo nodig geheugen vrijmaken. Geen gegarandeerde antwoordtijd. Externe aanbieder ontvangt aanvraag: privacy-/beeldbeleid controleren, geen echte leners om te testen. Kostlabels garanderen geen gratis gebruik.

**Nog te bevestigen:** RAM/schijf/latentie per keuze en hardware; Koha-minimum garandeert geen AI-prestatie.

## Gecontroleerde bronnen

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
