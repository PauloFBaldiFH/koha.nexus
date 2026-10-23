# 5. Pagpapayaman at Z39.50/SRU

[Nilalaman](README.md)

## Pagpapayaman

Import naglilipat ng export; pagpapayaman nagdadagdag datos o naghahanap bagong libro. Titulo na tugma kailangan pa ng bibliographic review. **Library tools > On-demand enrichment**, `n`; hindi na kasalukuyang menu ang lumang batch screen.

`all` o `biblionumbers`, gaya `101, 102, 500-510`, **Search**. Subaybayan trabaho/server; malaki sa background, maaaring tumuloy matapos restart kung may computer. **Pause/Resume** hindi nag-undo pagbabago. Ulat: paksa/klasipikasyon/tala/pisikal na paglalarawan. **Search more servers** hindi pa ginamit, **Choose donor** donor ng field groups. **Apply** matapos review/kumpirma; search/report hindi sumusulat.

Direktang Z39.50 may limit/sira; walang resulta hindi patunay walang libro. Walang pangkalahatang 50-record limit: threshold ng proteksiyon, record copies maliit, buong verified backup malaki. **Revert** ibinabalik bersyon ayon proteksiyon, pinananatili ang kalaunang edit; hindi buong restore o lahat ng pagbabago ng iba.

## Bago at awtoridad

ISBN/titulo, may-akda/taon, **Find**, suriin/piliin. **Import as new record** dagdag na may kumpirma, hindi pinapalitan kaparehong ISBN. Tinatanggal lokal `9XX` ng donor at itinatala pinagmulan, hindi nagiging sariling sipi ang iba. Suriin record at likhain lokal na sipi normal; batch **Undo a MARC import**.

**Enrich & standardize authorities**, `h`: saklaw/eksakto/malapit. Malapit maaaring mungkahi sa baybay/pansamantalang authority, ingatan. Sariling Koha muna, pagkatapos enrichment base/direct servers; Brazil una, mga paksa roon lang, hindi lokal na patakaran na garantiya. **Apply** gumagawa authority/links may backup, pinananatili edit mula report. Revert iniiwan bagong authority na ginagamit pa.

**Z39.50 / SRU servers**, `z`: incoming para sa ibang aklatan at binabago firewall port. Community network iba sa direct sources. **Reset/Reset all** bagong subok, hindi pagkumpuni ng remote. Space pili, **Scan** tunay na record search, **Add to Koha** piling gumagana. SRU setup hindi bawat query SRU; outgoing search hindi kailangan buksan incoming.

**Kailangang kumpirmahin:** availability/saklaw/kondisyon ng bawat source mula lokal na network sa oras ng gamit.

## Sinuring sanggunian

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
