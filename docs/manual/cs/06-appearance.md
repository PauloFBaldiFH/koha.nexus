# 6. Vzhled OPAC a staff

[Obsah](README.md)

**OPAC and Staff Appearance**, `o`, odděluje veřejný OPAC a staff/intranet.

**Sync current OPAC settings** načte bez použití. Měňte skupiny postupně. **Preview** ukáže CSS/JavaScript/obsah, ne plné vykreslení. **Apply** shrnutí/potvrzení a předchozí backup. V prohlížeči ověřte úvod/hledání/záznam/přihlášení a malý displej.

Bloky `OpacUserCSS/OpacUserJS`, případně `IntranetUserCSS/IntranetUserJS`; vlastní zůstávají, možné konflikty vzhledu s jinými úpravami.

## Nastavení a obsah

Textura/rozostření/krytí/rohy/barvy/pozadí, světlý/tmavý a výchozí motiv; udržte kontrast s obrázky/průhledností. Staff má horní lištu/rychlé hledání/moduly/hustotu tabulek/text/kontrast. **Apply color theme to Staff Client** zapnout; **Copy OPAC preset** pouze vyplní, **Apply** zapisuje.

Soubor přístupný serveru, nabízená služba či přímá HTTPS-URL. PNG/JPEG/GIF/WebP/ICO přijaty, SVG odmítá. Soubor jen na klientovi zpřístupněte serveru. Oprávněné obrázky a přístupný popis login; hostingová stránka není vždy adresa obrázku. Externí služby nastavit bez zveřejňování soukromí.

Karusel novinky/seznam Koha s `shelfnumber=`; název/počet/styl/rychlost/autoplay/**Refresh carousel**. Závisí na datech/obálkách/síti, chybějící obálka neznamená smazání. OPAC/staff tlačítka zvlášť: text/adresa/cíl/pořadí, **Add a button**, smazání řádku před použitím.

Login obrázek/popis/HTML bez skriptů/stylů/událostí, ne interní tajné pokyny. Zprávy každé strany vlastní název/text/tlačítka, nevytlačí knihovní zprávy. Patička `Field: value`, další odkazy text `|` adresa, nejvýš šest, veřejné údaje.

**Remove** potvrzuje a zálohuje před odstraněním bloků motivu, vrací Koha vzhled se zachováním vlastního. Není celý restore ani jiná správa zpět. Opravte chybnou skupinu, použijte; chybu uchovejte pro diagnostiku.

## Ověřené zdroje

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
