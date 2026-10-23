# 5. Berikning och Z39.50/SRU

[Innehåll](README.md)

## Berika befintliga poster

Import hämtar exporter, berikning kompletterar eller hittar nytt verk. Titelträff kräver bibliografisk granskning. **Library tools > On-demand enrichment**, `n`; gammal bibliografisk batchskärm är inte aktuell menyväg.

Ange `all` eller `biblionumbers` som `101, 102, 500-510`, **Search**. Följ jobb/servrar; stora jobb fortsätter i bakgrunden och kan återupptas efter omstart när datorn är tillgänglig. **Pause/Resume** styr sökningen, ångrar inte tillämpning. Läs rapport och jämför ämnen, klassifikation, noter, fysisk beskrivning. **Search more servers** frågar oanvända källor; **Choose donor** väljer givare för fältgrupper. **Apply** efter granskning/bekräftelse; sökning/rapport skriver ännu inte.

Nu direkt Z39.50; gränser/fel kan försena, ingen träff bevisar inte frånvaro. Ingen generell 50-postgräns: tröskeln gäller skydd vid tillämpning, postkopior små jobb, verifierad hel backup stora. **Revert** återför versioner enligt skydd, bevarar senare ändrade poster; ingen hel restore eller allmän ångring av andras ändringar.

## Nytt verk och auktoriteter

ISBN/titel med författare/år, **Find**, granska/välj. **Import as new record** lägger till efter bekräftelse utan att ersätta samma ISBN. Givarens lokala `9XX` tas bort och ursprung noteras, så deras exemplar inte blir egna. Kontrollera post, skapa lokala exemplar normalt; motsvarande MARC-parti via **Undo a MARC import**.

**Enrich & standardize authorities**, `h`: omfattning och exakta/närliggande former. Närliggande kan ge stavförslag/preliminära auktoriteter: granska noga. Egna Koha-auktoriteter först, därefter berikningsbas/direkta servrar; brasilianska prioriteras och ämnen endast därifrån. Inte garanti för lokal katalogpolicy. **Apply** skapar nödvändiga auktoriteter/länkar med backup och behåller sedan rapport ändrade poster. Revert behåller skapade auktoriteter som fortfarande används.

## Servrar

**Z39.50 / SRU servers**, `z`: inkommande server låter andra bibliotek söka och ändrar brandväggsport vid växling. Gemenskapsnät är annan källa än direkt berikning. Hälsa **Reset/Reset all** möjliggör nytt försök, reparerar inte fjärrtjänsten. Mellanslag väljer, **Scan** gör riktig postsökning, **Add to Koha** registrerar valda fungerande källor. SRU-konfiguration betyder inte SRU i varje berikningsfråga. Utgående sökning kräver inte öppet inkommande.

**Att bekräfta:** tillgänglighet, täckning och åtkomstvillkor per källa från lokala nätet vid användning.

## Kontrollerade källor

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
