# 7. Lokal AI

[Innehåll](README.md)

**AI**, `a`, samlar leverantör, Ollama, fotokatalogisering MARC Replace och staff-assistent. Inställning installerar inte verktygen automatiskt.

## Lokalt

Läs CPU/RAM-varning: Koha kan bli långsamt. **Ollama on this server > Check Ollama**, vid behov **Install Ollama**. Välj i listan/**Download** med nätverk/disk. Inga fasta modellnamn eftersom utbud ändras. **Local Ollama**, kontrollera URL (standard `http://127.0.0.1:11434`), **Use for chat/Use for cataloguing**. Foton kräver bildförmåga, text räcker inte. **Test connection/Save**, **F5/Ctrl+S**; fylla fält sparar inte. Tom chatt använder bildvalet. **Load models** frågar leverantören och markerar inbyggd reservlista vid fel.

Installerat tar disk, laddat RAM. **Free memory** avlastar utan att radera; kan laddas igen på begäran. Ollama-rutan syns även med annan leverantör: kontrollera sparad URL/leverantör innan lokal behandling antas.

## MARC Replace och assistent

Installera/uppdatera sidan; installeraren testar kompilering och frågar staff-genvägar. En post åt gången: `.mrc/.xml` eller text, `biblionumber`, **Preview**, jämför/bekräfta. Tomt skapar ny: undvik dubbletter. Befintliga exemplar bevaras, inkommande exemplarfält utesluts. Föregående MARCXML-version kan hämtas/skickas till samma ID för återgång, inte ersättning för hel backup.

**AI cataloguing**: läsbara omslags-/titelsides-/baksidesfoton, JPEG/PNG/WebP, minst ett. Välj framework eller ersättningspost, **Read the photos**, invänta utkast och jämför titel/ansvar/utgivning/ISBN/klassifikation/saknat. Rätta MARC före bekräftelse; klassförslag granskas i bibliotekets tabeller, ISBN-kontrollsiffra bevisar inte rätt utgåva. Utkast sparar inga exemplarfält.

**Install, update or remove the assistant** ersätter staff-startens nyhetsblock, inte OPAC. Koha-sökning/fasta läsfrågor, inte fri AI-SQL. **Förslag är inte utförd ändring:** granska post, före/efter, effekt; **Approve & Execute** med egna rättigheter krävs. Mellanändring kan avvisa/förnya förslag. Bekräftade ändringar kan granskas; radera samtal/assistent ångrar dem inte. Borttagning raderar samtal men behåller ändringshistorik.

Bevaka dator/Koha, undvik nya foton vid seghet, frigör minne lämpligt; ingen garanterad svarstid. Fjärrleverantör får begärans data: granska integritet/bildpolicy, testa inte med riktiga låntagaruppgifter. Kostetikett garanterar inte gratis.

**Att bekräfta:** RAM/disk/svarstid per val och hårdvara; Koha-minimum garanterar inte AI-prestanda.

## Kontrollerade källor

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
