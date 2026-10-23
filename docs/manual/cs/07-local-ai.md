# 7. Místní AI

[Obsah](README.md)

**AI**, `a`: poskytovatel, Ollama, fotografie MARC Replace a staff-asistent. Konfigurace neinstaluje nástroje automaticky.

## Místně

Čtěte varování CPU/RAM, Koha může zpomalit. **Ollama on this server > Check Ollama**, chybí-li **Install Ollama**. Volba/**Download** potřebuje síť/disk; jména modelů nefixujeme, nabídka se mění. **Local Ollama**, URL (výchozí `http://127.0.0.1:11434`), **Use for chat/Use for cataloguing**. Fotografie vyžaduje vidění, jen text nestačí. **Test connection/Save**, **F5/Ctrl+S**; vyplnění neukládá. Prázdný chat používá obrazovou volbu. **Load models** dotazuje poskytovatele, náhradní vestavěný seznam označí.

Instalované zabírá disk, načtené RAM. **Free memory** uvolní bez smazání, příště může načíst. Ollama viditelná i při jiném poskytovateli: ověřte uložené URL/poskytovatele, samotná instalace není místní zpracování.

## Nástroje

MARC Replace nainstalujte/aktualizujte, kontrola kompilace/zástupců staff. Jeden záznam: `.mrc/.xml` nebo text, `biblionumber`, **Preview**, porovnat/potvrdit. Prázdný vytvoří nový, pozor duplicity. Stávající exempláře zachovány, příchozí pole kusů vypuštěna. Minulý MARCXML lze stáhnout/znovu poslat stejnému ID, ne náhrada plného backup.

**AI cataloguing**: čitelné obálka/titulní strana/rub, JPEG/PNG/WebP, aspoň jedna. Framework/cílový záznam, **Read the photos**, čekat a srovnat název/odpovědnost/vydání/ISBN/třídu/chybějící. Před zápisem opravit MARC a klasifikaci ověřit v tabulkách; správná číslice ISBN nedokládá vydání. Návrh neukládá exemplářová pole.

**Install, update or remove the assistant** nahrazuje zprávy startu staff, ne OPAC. Koha-hledání/předdefinované čtení, ne volné SQL. **Návrh není vykonaná změna:** záznam/před-po/dopad, **Approve & Execute** s vlastními právy. Mezitímní změna může odmítnout/žádat nové. Potvrzené akce lze prohlížet; smazání konverzace/asistenta je nevrátí. Odstranění maže rozhovory, zachová historii schválení.

Sledujte stroj/Koha, při zpomalení nepřidávejte fotografie, případně uvolněte paměť. Žádný garantovaný čas. Vzdálený poskytovatel dostává požadavek: politika dat/obrázků, netestovat skutečnými čtenáři. Cenová značka nezaručuje bezplatnost.

**K potvrzení:** RAM/disk/latence pro volbu/hardware, minimum Koha není garance AI.

## Ověřené zdroje

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
