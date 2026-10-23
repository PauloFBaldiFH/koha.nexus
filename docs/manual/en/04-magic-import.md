# 4. Magic Import

[Manual index](README.md) · [Previous: backup](03-backup-restore.md)

The Magic Import Tool reads bibliographic records, items, patrons and authorities. Recognising a format does not guarantee correct interpretation of every field. The librarian must review the result, especially for exports without headers and local fields.

## Before importing

Keep the original file and a checked Koha backup. Start with a representative sample, including records with multiple items, accented characters, empty fields and exceptional cases. Compare totals from the source system with the preview totals. Do not publish patron exports.

Open **Magic Import Tool** from the sidebar or with **i**, then open its tool card. Choose the file or folder in the picker. The path must be accessible to the Linux environment running the panel; a file that exists only on the browser or remote terminal computer is not automatically on the server.

## Formats and limits

| Input | Preparation and checks |
| --- | --- |
| MARC21 ISO 2709, MARCXML and textual MARC | Check titles, accents, authorities and items. The current reader recognises MarcEdit `.mrk` text; conversion is not required merely because it is `.mrk`. |
| CSV/TSV, Excel `.xlsx` and `.xls`, LibreOffice `.ods`, dBase `.dbf` | Check the delimiter, headers, field types and values actually detected. Recognition uses content and headers when available. |
| Tabular JSON and XML | Check the recognised structure and whether selected fields represent the intended data. An arbitrary XML file is not necessarily MARCXML. |
| Tabular SQL, including fragments without headers | The reader extracts recognisable data and relationships; it does not execute the SQL file as a migration program. Review ambiguous fields and links between tables. |
| ISIS | The specific reader accepts recognised PostgreSQL exports containing the `acervo` table. For a CDS/ISIS `.mst` master file, export the WinISIS database as ISO 2709; the master file is not directly read as a catalogue. |
| Biblioteca Fácil | Use a recognised backup or data folder, keeping related tables together. The specific reader can prepare recognised records, patrons, loans and holds. Check each stream separately. |
| Full Koha backup | The tool redirects to restore. That replaces the database rather than adding records. Read the backup chapter before confirming. |

A PostgreSQL dump from another system, particularly binary `pg_dump` format, is not a MariaDB database ready for Koha. If the tool says it cannot read it, export MARC or spreadsheets from the source system. For archives, read each member's detection result. PDFs, images, text documents and executables are not usable bibliographic exports for this reader.

## Review manual field mapping

The mapping screen appears during preparation. It is integrated with automatic import and lets you review the result before writing.

1. Check the mode at the top: **Bibliographic**, **Patrons** or **Authorities**. Use the selector to correct a misclassification. Labels may be translated in your installation.
2. Inspect the sample grid, arranged by records and fields. Select a field and check the proposed destination. Resize the grid using its divider or **Ctrl+Up** and **Ctrl+Down**.
3. Choose the field's function: keep it, redirect it to a destination, assign fixed text or leave it out. Do not discard an identifier until you understand the relationships depending on it.
4. Open **Values of this Koha** to check available codes and defaults for library, item type and patron category. Also check mappings from source values to destination values.
5. Use **Record preview** to inspect the resulting record. **Check the whole file** prepares and validates the entire file without importing data into Koha at that stage.
6. To reuse a mapping, name the profile and use **Save**. Select a saved profile and use **Use** to load it. Review it again if the export structure changes.
7. Use **Apply** or **Ctrl+S** to accept the mapping and continue preparation. This is not the final import confirmation. **Skip: import as it is**, including **Esc** on this screen, skips manual mapping; it does not cancel the whole procedure.

Additional options include grouping duplicates and text adjustments. Inspect the preview before accepting a batch transformation. Do not apply spelling or case corrections indiscriminately to acronyms, proper names or item codes.

## Bibliographic records and items

Native Koha items are stored in `952`. Normalisation preserves their data and can remap libraries and item types when requested. Do not replace a valid code just because it differs from the default: check the libraries and item types in the destination Koha.

Local fields such as `949`, `852`, `950` and `990` need interpretation. Pergamum and Biblivre exports can store codes and dates in different subfields; a tag number alone does not establish its meaning. Check barcode, home and holding library, call number, item type, location and acquisition date.

A legal deposit annotation, such as a number followed by `DL` and a date, should not automatically create a local item. The normaliser distinguishes these annotations from fields carrying independent evidence of a real item. Review excluded holdings and ambiguous cases.

The default policy for a missing barcode is review. Generating identifiers requires the corresponding choice and stable migration/source identity; it does not silently renumber collisions with existing barcodes. Check missing, duplicate and colliding codes before importing.

For related SQL tables, bibliographic metadata and items need a recognised relationship. Do not assume that column position or row order links the tables. If the association is unclear in the preview, stop the import and correct the mapping.

## Patrons and authorities

In **Patrons**, review each destination, including first name, surname, card number, contacts, address, dates, library and category. Recognised e-mails, CPFs or dates are evidence, not proof of correct column classification. Birth, enrolment and expiry dates can share a format while having different meanings. The default category must exist in Koha.

The flow asks whether existing patrons should be updated, matching by card number. Read this choice before confirming; updating existing patrons differs from only adding new ones. Do not assign administrative permissions or authentication information based on a guess about a column.

In **Authorities**, check the identifier, authorised heading, variants, relationships and authority type. The mode supports mapping authority MARC fields; switching a table's mode does not create information missing from the source.

## Confirm and check the result

After mapping, the tool prepares output files and presents a preview and counts. Answer outstanding questions about library, item type, category and patron updates. Read rejections and warnings before accepting database writes.

For existing records, the flow offers to keep the catalogue record and add only new items, replace the catalogue record with the incoming record, or skip comparison and create a new title for every record. Choose according to the migration, avoiding accidental repetition of a batch.

Execution can have separate record, authority, patron and circulation stages. **A later failure does not guarantee that earlier stages have been undone.** Keep the summary and logs, check counts and do not automatically repeat the complete batch.

Afterwards, search samples in Koha and check items in their libraries, patron accounts and authority links. Under **Library tools**, **Undo a MARC import** handles MARC batches; it is not a universal undo for patrons, loans and holds. For full database recovery, use Backup center with the precautions in the preceding chapter.

## Point to confirm

**To confirm:** compatibility with an export from a particular version of another system requires a sample and review of the result. Recognition of the formats above is not a guarantee for every proprietary layout.

## Checked sources

- [Panel menus](../../../panel/kei_panel/menus.py), the `import` section.
- [Manual field mapping](../../../panel/kei_panel/screens/fieldmap.py), screen composition, modes, preview and application.
- [Installer and readers](../../../installer), `lt_magic_import`, `_lt_magic_run` and the generated `detect`, `bridge`, `engine`, `readers`, `relational` and `holdings` modules.
