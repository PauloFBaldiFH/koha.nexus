# 4. Magic Import

[Nilalaman](README.md)

## Paghahanda at format

Binabasa ng Magic Import ang bibliograpiya, sipi, mambabasa at awtoridad. Nakilalang format hindi garantiya sa fields, lalo walang header/lokal. Itago orihinal/nasubukang backup, kinatawang sample na maraming sipi, accent, blanko/exception; ihambing bilang sa pinagmulan. Huwag ilathala exports ng mambabasa.

**Magic Import Tool**, `i`, card at file/folder na maaabot ng Linux panel. File lamang sa browser/terminal computer ay hindi awtomatikong nasa server.

| Input | Suriin |
| --- | --- |
| MARC21 ISO 2709, MARCXML, MARC-text | Titulo/titik/awtoridad/sipi; `.mrk` MarcEdit kinikilala nang hindi kinokonvert dahil lang extension. |
| CSV/TSV, `.xlsx/.xls/.ods/.dbf` | Separator/header/halaga/destinasyon. |
| Tabular JSON/XML | Estruktura; hindi lahat ng XML ay MARCXML. |
| Tabular SQL kahit walang header | Binabasa data/relasyon, hindi pinapatakbong migration program; suriin malabo. |
| ISIS | Nakilalang PostgreSQL may `acervo`; CDS/ISIS `.mst` mula WinISIS bilang ISO 2709. |
| Biblioteca Fácil | Nakilalang backup/folder, magkakaugnay na tables sama-sama; records/tao/pahiram/reservation hiwalay. |
| Buong Koha-backup | Sa restore, hindi dagdag records. |

Ibang PostgreSQL, lalo binary `pg_dump`, ay hindi handang MariaDB. Kung tinanggihan, MARC/table export sa pinagmulang sistema. Bawat laman ng archive suriin; PDF/larawan/dokumento/program hindi bibliographic export dito.

## Mapping at datos

**Bibliographic/Patrons/Authorities** suriin. Grid/destinasyon, divider o **Ctrl+Up/Down** sa taas. Itira/ilipat/fixed text/ignore, unawain relasyon bago alisin ID. **Values of this Koha** codes, default aklatan/uri/kategorya, pagpapalit source/target. **Record preview** resulta, **Check the whole file** buong paghahanda/check nang walang import noon. Pangalan/**Save** profile, pili/**Use**, suriin kung nagbago estruktura. **Apply/Ctrl+S** tumatanggap mapping, hindi panghuling pagsulat. **Skip: import as it is/Esc** lumalaktaw mapping, hindi kansela lahat. Group/text-correction kailangan preview, huwag bulag baguhin daglat/pangalan/code.

Nananatili `952`, maaari hinging mapping aklatan/uri; huwag palitan valid na code para lang default. Barcode, tahanan/kasalukuyang aklatan, call number, uri, lokasyon, acquisition. Lokal `949/852/950/990` maaaring iba ang kahulugan sa Pergamum/Biblivre. Legal-deposit note `DL`/petsa hindi awtomatikong lokal na sipi; suriin exclusion/hiwalay na ebidensiya ng imbentaryo. Nawawalang barcode default review; generation kailangan pagpili/matatag na migration-source identity, hindi tahimik na renumber ng banggaan. SQL-relasyon dapat nakilala, hindi hula sa kolum/hanay, ayusin muna.

**Patrons**: pangalan/card/contact/address/petsa/aklatan/umiiral na kategorya. E-mail/CPF/date pahiwatig lang; kapanganakan/rehistro/expiry magkapareho ang anyo. Update ng umiiral tinatanong gamit card, iba sa bagong dagdag lang; huwag hulaan permissions/authentication. **Authorities**: ID, awtorisadong anyo, baryante, relasyon, uri; mode-change hindi lumilikha ng kulang na impormasyon.

Basahin bilang/rejections/tanong. Umiiral itira plus bagong sipi, palitan, o bago nang walang compare. **Maaaring manatiling imported ang naunang yugto kapag may huling error.** Itago ulat/log, suriin natapos/sample/sipi/tao/relasyon bago ulitin. **Library tools > Undo a MARC import** para MARC, hindi lahat ng tao/pahiram/reservation. Buong database ayon Backup center.

**Kailangang kumpirmahin:** partikular na saradong layout/bersyon nang walang sample at pagsusuri.

## Sinuring sanggunian

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
