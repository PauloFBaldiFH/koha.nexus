# 1. Pag-install

[Nilalaman](README.md)

## Kapaligiran at mga kailangan

Sa Windows, tumatakbo ang Koha sa Debian sa loob ng WSL 2. Inihahanda ng mga kasangkapang Windows ang kapaligiran, binubuksan ang panel at isinasama ang aplikasyon. Sa Debian/Ubuntu, direktang ini-install ang panel at serbisyo. Buksan sa panel ang umiiral na katalogo; huwag ulitin ang pag-install para lamang makapasok.

| Kapaligiran | Sinusuri ng code |
| --- | --- |
| Windows | Windows 10 bersyon 2004, build 19041 o mas bago, o Windows 11; 64 bit at aktibong virtualization; RAM 8 GB, inirerekomenda 12 GB; bakanteng 10 GB sa drive ng instalasyon, inirerekomenda 20 GB. |
| Debian/Ubuntu | Debian 11/12/13 o Ubuntu 22.04/24.04; nakatalang amd64/arm64; mas mababa sa 5 GB hinaharang, 5 hanggang kulang 10 GB babala, 10 GB pataas pasado sa pagsusuring ito. |

Kailangan pa ng espasyo ang katalogo, kalakip, index at backup. **RAM Linux, kailangang kumpirmahin:** mungkahing 4 GB sa dedikadong server, mas mabuti 8 GB; desktop/virtualization 8 GB, mas mabuti 12 GB. Walang ipinipilit na numerikong minimum RAM ang kasalukuyang Linux check. Hindi garantiya sa lahat ng bigat ng trabaho ang pagpasa. Isinasaalang-alang ng Windows ang memoryang nakareserba sa hardware: natukoy na hangganang 7,5 at 11,5 GB.

Kailangan ng Linux ang karapatang pang-administrador at koneksiyon sa repository ng Koha packages. TCP 80/8080 ang OPAC/staff. Kung ginagamit, iniaalok ihinto ang kaugnay na serbisyo. **Pumayag lamang kung maaari silang maantala.**

## Windows: PowerShell

Mag-sign in sa Windows administrator account na gagamit ng Koha. Buksan ang PowerShell bilang administrador sa parehong account:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Kung hinihingi ng pagtaas ng pahintulot ang account ng ibang tao, kanselahin at mag-sign in nang tama: nakatali ang WSL sa nag-install na account. Basahin ang checks at ayusin ang patay na virtualization. Sagutin sa bintana ang tungkol sa Debian account, na hiwalay sa Koha account ng aklatan.

Hintayin ang WSL 2/Debian. Ang hiniling na restart ay nagtatala ng pagpapatuloy sa susunod na Windows sign-in. Piliin ang wika/**Install Koha server**. Pagkatapos sa panel, lumabas nang normal at hintaying matapos ang Windows integration.

Karaniwang `C:\Koha`; maaaring manatili sa `C:\KohaEasy` ang lumang instalasyon. Huwag ilipat para ayusin ang pagkaputol. Itala ang error: iniingatan ang natapos na yugto, maaaring magpatuloy o magbukas muli ng panel. Hindi nito ginagawang ligtas ang mapanirang muling pag-install.

## MSIX

Parehong WSL ang inihahanda; hindi pa handang server/database ang naka-install na pakete. Gumamit ng **karaniwang PowerShell na hindi muna itinaas ang pahintulot**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

Kinukuha ng pantulong ang paketeng itinakda sa code, sinusuri ang pinagmulan, humihingi ng pahintulot at ini-install para sa kasalukuyang user. Huwag balewalain ang pagtanggi. Hintayin ang paghahanda, tapusin ang gabay ng server, lumabas normal at hintayin ang shortcuts, tasks at network Windows. Hindi natatapos ang Koha sa maagang pagsara: buksan muli.

**Kailangang kumpirmahin:** pampublikong pagkakaroon/URL Microsoft Store; hindi patunay ng paglalathala ang packaging code. Hindi rin kumpirmado ang buong MSIX ARM64: x64 ang manifest, hindi patunay ang Linux arm64. Mas lumang Windows ang pinapayagan ng manifest kaysa buong WSL flow; gamitin ang kumpletong kailangan sa itaas.

## Debian/Ubuntu

Sa terminal ng server:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Kasama ang lokal na repository at mga salin:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Wika/**Install Koha server**. Ayusin muna ang kritikal na error; hindi garantiya ng kapasidad ang babala. WSL 2 at umaandar na systemd ang kailangan; tinatanggihan WSL 1. Inirerekomenda sa Windows ang gabay sa itaas.

## Pag-install sa panel

**Install Koha server**, hintayin check/ulat, suriin ang epekto ng pagpapalaya sa ports. Tiyakin ang tamang computer at time zone o rehiyon/lungsod. **May umiiral na Koha: huminto at suriin.** Binubura ng muling pag-install ang database/configuration, may dagdag na kumpirmasyon at eksaktong `REINSTALL`. Hindi ito para lang buksan/i-update ang panel.

Huwag isara, hindi makakansela. Tantiyang 10–30 minuto ayon sa hardware/network. Basahin ang resulta/ulat: hindi nangangahulugang malusog ang serbisyo kapag may problemang natapos. Isaalang-alang ang restart at hintayin din ang pagpapatuloy Windows sa MSIX. Huwag ilathala ang pribadong datos ng resulta sa dokumento o support request.

## Sinuring sanggunian

- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [installer](../../../installer).
- [README.md](../../../README.md).
- [install.ps1](../../../windows/install.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [instalar_msix.ps1](../../../windows/msix/instalar_msix.ps1).
- [KohaMsixEntry.cs](../../../windows/msix/KohaMsixEntry.cs).
- [KohaMsixPanel.ps1](../../../windows/KohaMsixPanel.ps1).
- [compilar_msix.ps1](../../../windows/msix/compilar_msix.ps1).
- [install.py](../../../panel/kei_panel/routines/install.py).
