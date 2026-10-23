# 7. Lokal na AI

[Nilalaman](README.md)

**AI**, `a`: provider, Ollama, MARC Replace photos at staff assistant. Hindi awtomatikong nag-i-install ng tools ang configuration.

Basahin CPU/RAM warning, maaaring bumagal Koha. **Ollama on this server > Check Ollama**, kung wala **Install Ollama**. Pili/**Download** kailangan network/disk; hindi nakapirmi ang model names, nagbabago listahan. **Local Ollama**, URL (default `http://127.0.0.1:11434`), **Use for chat/Use for cataloguing**. Photos kailangan vision, hindi text lang. **Test connection/Save**, **F5/Ctrl+S**; pagpuno hindi save. Blangkong chat gumagamit vision choice. **Load models** nagtatanong provider, minamarkahan built-in fallback.

Installed disk, loaded RAM. **Free memory** unload walang delete, maaaring reload. Nakikita Ollama kahit ibang provider: suriin saved URL/provider, hindi lokal na pagproseso dahil naka-install lang.

## Mga kasangkapan

Install/update MARC Replace, compiler/shortcut check. Isang record: `.mrc/.xml` o text, `biblionumber`, **Preview**, compare/kumpirma. Blangko bago, iwas duplicate. Existing items nananatili, incoming item fields tinatanggal. Previous MARCXML download/ibalik sa parehong ID, hindi kapalit ng buong backup.

**AI cataloguing**: malinaw cover/title page/likod, JPEG/PNG/WebP, kahit isa. Framework/target, **Read the photos**, hintay at compare titulo/responsibilidad/publication/ISBN/classification/kulang. Itama MARC bago save, classification sa tables, ISBN digit hindi patunay ng edisyon. Draft hindi nagsasave item fields.

**Install, update or remove the assistant** kapalit ng staff home news, hindi OPAC. Koha search/itinakdang read queries, hindi malayang SQL. **Mungkahi hindi pa naisagawa:** record/bago-pagkatapos/epekto, **Approve & Execute** gamit sariling rights. Intervening edit puwedeng tanggihan/humingi bago. Nasuring confirmed actions, tanggal usapan/assistant hindi undo. Pag-alis binubura usapan, iniiwan approved history.

Bantayan hardware/Koha, huwag bagong photos kapag mabagal, free memory kung akma. Walang guaranteed time. Remote provider tumatanggap request: data/image policy, huwag totoong patrons pang-test. Cost label hindi libreng garantiya.

**Kailangang kumpirmahin:** RAM/disk/latency ayon choice/hardware; minimum Koha hindi AI guarantee.

## Sinuring sanggunian

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
