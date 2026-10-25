# 5. Obohacování a Z39.50/SRU

[Obsah](README.md)

## Obohacování

Import přebírá export, obohacení doplňuje nebo hledá novou knihu. Shoda názvu potřebuje bibliografickou revizi. **Library tools > Enrich from world catalogues**, `n`; stará dávková obrazovka není současná cesta.

`all` nebo `biblionumbers`, například `101, 102, 500-510`, **Search**. Sledujte práci/servery; velké úlohy na pozadí pokračují po restartu, s dostupným strojem. **Pause/Resume** nevrací změny. Zpráva: porovnat předměty/klasifikaci/poznámky/fyzický popis. **Search more servers** další zdroje, **Choose donor** zdroj skupin polí. **Apply** až po kontrole/potvrzení, hledání/zpráva nepíše.

Přímé Z39.50 má limity/poruchy, žádný výsledek nedokazuje neexistenci knihy. Není obecný limit 50 záznamů: hranice pro ochranu použití, kopie záznamů u malých, plný ověřený backup u velkých. **Revert** vrací verze podle ochran a zachová později upravené, není globální restore ani zrušení všech cizích editací.

## Nové tituly a autority

ISBN/název s autorem/rokem, **Find**, přezkoumat/vybrat. **Import as new record** přidává po potvrzení, nenahrazuje stejné ISBN. Odstraní lokální `9XX` dárce a zaznamená původ, aby cizí exempláře nebyly vaše. Zkontrolujte titul a založte místní kusy normálně; dávka přes **Undo a MARC import**.

**Enrich & standardize authorities**, `h`: rozsah a přesné/blízké tvary. Blízké mohou navrhnout opravu/předběžné autority, zvlášť kontrolovat. Nejprve vlastní Koha, pak databáze obohacení/přímé servery; brazilské přednostní a předměty jen z nich, ne záruka místní politiky. **Apply** vytvoří autority/vazby s backup, zachová změny od zprávy; Revert ponechá vytvořené autority stále navázané.

## Servery

**Z39.50 / SRU servers**, `z`: vstupní umožní cizí vyhledávání, přepíná port firewallu. Komunitní síť odlišná od přímých zdrojů. **Reset/Reset all** nové pokusy, ne oprava vzdálené služby. Mezera vybere, **Scan** hledá skutečný záznam, **Add to Koha** registruje zvolené funkční. SRU nastavení neznamená SRU pro každý dotaz; venkovní hledání nevyžaduje otevřený vstup.

**K potvrzení:** dostupnost/pokrytí/podmínky zdrojů z místní sítě v danou chvíli.

## Ověřené zdroje

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
