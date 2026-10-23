# 5. Record enrichment and Z39.50/SRU servers

[Manual index](README.md) · [Previous: import](04-magic-import.md)

Import and enrichment have different purposes. Import brings records from an export. Enrichment seeks complementary data for existing records, or finds a book to add as a new record. A title match does not remove the need for bibliographic review.

## Enrich existing records

Open **Library tools**, then **On-demand enrichment**. The **n** key opens this screen. The old batch bibliographic enrichment screen is no longer the route presented in the current menu.

1. Enter `all` for all records or the required `biblionumbers`, such as `101, 102, 500-510`, and use **Search**.
2. Monitor the job and server table. A large job continues in the background and can resume after a restart. The machine must remain available for it to progress.
3. Use **Pause** and **Resume** when needed. Pausing a search does not revert changes already applied.
4. Select the job and open its report. Compare proposed fields with the current record, especially subjects, classification, notes and physical description.
5. Use **Search more servers** to query sources not yet used, or **Choose donor** to select the source for a group of fields from available results.
6. Use **Apply** only after review and read the confirmation. Searching and preparing a report do not write those proposals into the catalogue.

The current screen describes direct Z39.50 searches. Servers have their own limits and can become temporarily unavailable. A delay or search without results does not establish that the book is absent from other catalogues.

There is no general 50-record search limit. Small and large jobs differ in their protection at application time: the code uses record copies for small jobs and a verified full backup for larger ones. This does not make review optional.

**Revert** recovers previous record versions according to the flow's protection rules. Records edited in Koha after application are preserved. Do not treat it as a full database restore or as an undo of every edit by other users.

## Find a book and import it

On the same screen, use ISBN or title; author and year help identification. Use **Find**, inspect the sources and select the desired result. **Import as new record** adds a record after confirmation; it does not replace an existing record with the same ISBN.

This flow removes the donor catalogue's local `9XX` fields and records the source. That prevents another library's holdings from becoming your own. Check the added record in Koha and create local items according to library procedures. **Undo a MARC import** under Library tools can handle the corresponding MARC batch.

## Enrich and standardise authorities

Open **Enrich & standardize authorities** under Library tools, or press **h**. Set the scope and choose exact forms or close forms. The close-forms option can propose a spelling correction and create authorities marked preliminary; review it carefully.

The flow first searches this Koha's authorities, then the enrichment database and direct servers. The code prioritises Brazilian sources and restricts subject searches to Brazilian sources. Those rules do not guarantee that every proposed heading fits your cataloguing policy.

Read the report before **Apply**. Application creates needed authorities and links records, with a safety backup. Records edited after report preparation are preserved. When reverting, authorities created by the job that still have links are retained; do not expect indiscriminate deletion.

## Configure Z39.50 and SRU

Open **Z39.50 / SRU servers** from the sidebar or press **z**. Distinguish the screen's functions:

- This Koha's server lets other libraries search your catalogue. Turning it on or off also changes the corresponding firewall port opening through the panel's flow.
- The community network configures a shared catalogue source in Koha. This differs from the direct servers queried by on-demand enrichment.
- The health table shows failures of servers used for direct searches. **Reset** or **Reset all** permits another attempt; it does not repair the remote service.
- Outbound catalogues support copy cataloguing. **Show servers** tests every server with a real search (not merely a connection to a port) and lists the ones that return a record; a backup server appears only when its main server returns none. Tick the servers for the cataloguing search with **Select for search** or the space bar, untick with **Unselect for search** (at most 20 is recommended) and use **Save to Koha**. **Update** tests again.

SRU support in this configuration does not mean every enrichment search uses SRU. Do not expose the inbound server merely to query an external catalogue: these are different directions of communication.

## Point to confirm

**To confirm:** each external source's availability, coverage and access conditions at the time of use. Source code and a server list do not establish that all are accessible from the library's network.

## Checked sources

- [Menus](../../../panel/kei_panel/menus.py), Library tools and server actions.
- [On-demand enrichment](../../../panel/kei_panel/views/ondemand.py), screen composition, search, import and application protection.
- [Jobs and authorities](../../../panel/kei_panel/views/enrich.py), reports, application, revert and `AuthEnrichView`.
- [Servers](../../../panel/kei_panel/views/z3950.py), inbound service, health, selection, scanning and addition.
