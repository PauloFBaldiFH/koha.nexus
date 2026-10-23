# 1. Installatie

[Inhoud](README.md)

## Omgeving en vereisten

Op Windows draait Koha in Debian via WSL 2. Windows-hulpmiddelen bereiden de omgeving voor, openen het paneel en integreren de toepassing. Op Debian/Ubuntu worden paneel en diensten rechtstreeks geïnstalleerd. Open een bestaande catalogus via het paneel, niet door installatie te herhalen.

| Omgeving | Controles in de code |
| --- | --- |
| Windows | Windows 10 versie 2004, build 19041 of later, of Windows 11; 64-bits en virtualisatie ingeschakeld; 8 GB RAM, 12 GB aanbevolen; 10 GB vrij op installatieschijf, 20 GB aanbevolen. |
| Debian/Ubuntu | Debian 11/12/13 of Ubuntu 22.04/24.04; door installer genoemde amd64/arm64; onder 5 GB vrij blokkeert, 5 tot minder dan 10 GB waarschuwt, vanaf 10 GB slaagt deze controle. |

Catalogus, bijlagen, indexen en backups vragen extra ruimte. **Linux-RAM nog te bevestigen:** de gids adviseert 4 GB voor een toegewezen server, liever 8 GB; desktop/virtualisatie 8 GB, liever 12 GB. De huidige Linux-voorcontrole dwingt geen numeriek RAM-minimum af. Slagen garandeert geen capaciteit voor elke belasting. Windows staat hardwaregereserveerd geheugen toe, met gedetecteerde grenzen 7,5 en 11,5 GB.

Linux vereist beheerdersrechten en toegang tot de Koha-pakketbron. TCP 80/8080 zijn voor OPAC/staff. Bij bezetting biedt het paneel aan de betreffende diensten te stoppen. **Alleen toestaan als onderbreking verantwoord is.**

## Windows met PowerShell

Meld aan met het Windows-beheerdersaccount dat Koha gaat gebruiken en open PowerShell daarin als administrator:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Vraagt verhoging om een ander account, annuleer en meld passend aan: WSL-componenten horen bij het installatieaccount. Lees controles en verhelp uitgeschakelde virtualisatie. Beantwoord Debian-accountvragen in het venster; dit account verschilt van de Koha-bibliotheekgebruiker.

Wacht op WSL 2 en Debian. Een gevraagde herstart registreert voortzetting bij volgende Windows-aanmelding. Kies taal en **Install Koha server** in het paneel. Na voltooiing normaal verlaten en Windows-integratie laten afronden.

Standaardmap `C:\Koha`; oudere installaties kunnen `C:\KohaEasy` behouden. Niet verplaatsen om een onderbreking te herstellen. Noteer fout: afgeronde fasen worden bewaard, herstart kan hervatten of paneel voor afronding openen. Dat maakt destructieve herinstallatie niet veilig.

## MSIX op Windows

MSIX bereidt dezelfde WSL-omgeving voor; pakket installeren betekent geen ingerichte server/database. Open **normale PowerShell, niet vooraf verhoogd**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

De helper downloadt het in de code ingestelde pakket, controleert herkomst, vraagt beheerstoestemming en installeert voor huidige gebruiker. Afwijzingen niet negeren. Wacht bij eerste start op voorbereiding en rond begeleide installatie af. Verlaat paneel normaal en wacht op snelkoppelingen, taken en netwerk. Voortijdig sluiten voltooit Koha niet: opnieuw openen om verder te gaan.

**Nog te bevestigen:** openbare beschikbaarheid/URL Microsoft Store; verpakkingscode bewijst geen publicatie. Ook volledige MSIX-werking op ARM64 is onbevestigd: manifest x64, Linux-arm64-ondersteuning is geen bewijs. Manifest staat ouder Windows toe dan volledige WSL-route; gebruik de volledige vereisten hierboven.

## Debian of Ubuntu

In de serverterminal:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Om repository en vertalingen te bewaren:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Kies taal en **Install Koha server**. Verhelp kritieke fouten eerst; waarschuwingen zijn geen onbeperkte capaciteitstoestemming. Onder WSL zijn WSL 2 en draaiend systemd vereist, WSL 1 wordt geweigerd. Windows-gebruikers kunnen beter de begeleide voorbereiding volgen.

## Server installeren in het paneel

1. **Install Koha server** openen, voorcontrole afwachten, rapport lezen en gevolgen van poortvrijgave beoordelen.
2. Doelcomputer controleren vóór bevestiging; tijdzone overnemen of regio/stad kiezen.
3. **Bestaande instantie: stop en controleer.** Herinstallatie wist database/configuratie, vraagt extra bevestiging en exact `REINSTALL`. Niet gebruiken om slechts paneel te openen/bijwerken.
4. Niet sluiten: niet annuleerbaar. Schatting 10 tot 30 minuten hangt van hardware/netwerk af.
5. Resultaat/rapport lezen; voltooid met problemen betekent geen gezonde diensten. Aangeboden herstart beoordelen, bij MSIX Windows-vervolg afwachten.

Geen privégegevens van het resultaat overnemen in openbare documenten of hulpvragen.

## Gecontroleerde bronnen

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
