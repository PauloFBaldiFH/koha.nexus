# 6. Utseende för OPAC och staff

[Innehåll](README.md)

**OPAC and Staff Appearance**, `o`, har egna inställningar för publikt OPAC och staff/intranät.

**Sync current OPAC settings** läser aktuellt utan att tillämpa. Ändra en grupp i taget. **Preview** visar CSS/JavaScript/innehåll som ska skrivas, inte full webbrendering. **Apply** visar sammanfattning/bekräftelse och tar backup först. Granska startsida, sökning, post och inloggning i webbläsare, också liten skärm.

Block skrivs i `OpacUserCSS/OpacUserJS` och vid behov `IntranetUserCSS/IntranetUserJS`. Egna block bevaras, men visuella konflikter med annan anpassning kan finnas.

## Läsbarhet, bilder och innehåll

Textur, oskärpa, opacitet, hörn, accent-/bakgrundsfärg samt ljus/mörker och starttema: behåll kontrast med bilder/transparens. Staff har topplist, snabbsökning, modulkort, tabelldensitet, textstorlek/kontrast. **Apply color theme to Staff Client** aktiveras; **Copy OPAC preset** fyller bara, **Apply** sparar.

Serveråtkomlig fil, erbjuden bildtjänst eller direkt HTTPS-URL. PNG/JPEG/GIF/WebP/ICO accepteras, SVG avvisas. Fil bara på användardator måste först nås från servern. Använd tillåtna bilder och inloggningsbildens tillgänglighetsbeskrivning; värdsida är inte alltid direkt bildadress. Kontrollera externa tjänster utan privata uppgifter i publicerade bilder.

Karusell: nyheter eller Koha-lista med nummer från `shelfnumber=`; titel/antal/stil/hastighet/autoplay och **Refresh carousel**. Beroende på poster/omslag/nätverk, saknat omslag betyder inte borttagen post.

OPAC-/staff-knappar separat, text/adress/mål/ordning; **Add a button**, radering per rad före tillämpning. Inloggning tillåter bild/beskrivning/filtrerad HTML utan skript/stilar/händelser; inga interna hemliga instruktioner. Nyheter på respektive sida har egna titel/text/knappar utan att ersätta bibliotekets befintliga nyheter. Sidfot `Field: value`, extralänkar text `|` adress, högst sex, bara offentligt.

**Remove** bekräftar och tar backup före temablock tas bort och Koha-utseende återkommer med egna anpassningar. Ingen full restore eller återtagning av annan administration. Rätta fel grupp och tillämpa, spara fel för diagnos.

## Kontrollerade källor

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
