# 2. Unang hakbang at panel

[Nilalaman](README.md)

## Pagbukas at paggalaw

Sa inihandang Debian/Ubuntu:

```bash
sudo config.sh
```

Windows: icon **Koha** o MSIX. Maaaring hingin ang wika sa unang bukas. Kapag nabigo ang Textual, maaaring ialok ang klasikong panel. Pangunahing Textual ang gabay, hindi lumang menu numbers.

Piliin ang seksiyon gamit ang arrows, **Enter** o click para buksan. Hindi nagpapatakbo ang pag-highlight lang. Buksan ang task card at basahin tanong. **Tab** naglilipat ng focus; lumabas sa text field bago letter shortcuts.

| Key | Gawain |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Debian terminal |
| `Ctrl+B` | Ipakita/itago sidebar |
| `q` | Lumabas sa panel |

Hindi pinapatay ang server sa paglabas sa nakapahingang panel. Sundin ang pagkansela ng kasalukuyang gawain. May hindi makakanselang yugto ang install/restore; hindi ligtas ang sapilitang pagsara.

## Kalagayan at address

Ipinapakita ang Koha/memorya, huling backup na may petsa/edad/file, disk, address, MariaDB, Apache, RabbitMQ, Memcached, Koha at HTTP. Pinagsasama ang edad at huling resulta sa gabi: maaaring bagong file ngunit bigong gabi. Basahin pareho; hindi kapalit ng restore-test ang mabuting indicator. Hindi patunay ng tapos na web installer o lahat ng gawain sa aklatan ang HTTP.

**Refresh** muling bumabasa; **Restart Koha** pagkukumpuni/restart na may pag-iingat sa gumagamit; **Export diagnostics** impormasyon para suporta. Maaaring hindi aktibo kung kulang ang suporta ng naka-install na installer.

Address cards bukas/kopya URL; kung walang browser, idikit sa sarili mong computer. Sa server OPAC `http://localhost/`, staff `http://localhost:8080/`, ports 80/8080. Sa ibang computer gamitin network address, hindi ang sarili nitong `localhost`. Sa WSL NAT/LAN warning, ipasuri ang Windows preparation sa tagapangasiwa; huwag ipagpalagay pangkalahatang akses.

Tapusin ang Koha web installer kung lumabas, nag-iiba ayon sa bersyon. **Koha settings & parameters > Create super librarian** account, pribadong halaga roon lamang.

Bago gamitin: dashboard/serbisyo/address, buksan OPAC/staff mula sa tama, gumawa/subukan backup, tiyakin ang panlabas na kopya at makakabawi nito. Huling hakbang ay payong pang-operasyon; kailangang tapos at nasuri ang transfer.

## Sinuring sanggunian

- [installer](../../../installer).
- [app.py](../../../panel/kei_panel/app.py).
- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [main.py](../../../panel/kei_panel/screens/main.py).
- [install.py](../../../panel/kei_panel/routines/install.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [dashboard.py](../../../panel/kei_panel/views/dashboard.py).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [menus.py](../../../panel/kei_panel/menus.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
