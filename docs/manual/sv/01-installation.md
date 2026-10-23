# 1. Installation

[Innehåll](README.md)

## Miljö och krav

På Windows körs Koha i Debian via WSL 2. Windows-verktygen förbereder miljön, öppnar panelen och integrerar programmet. På Debian/Ubuntu installeras panel och tjänster direkt. Öppna en befintlig katalog via panelen, inte genom att installera igen.

| Miljö | Kontroller i koden |
| --- | --- |
| Windows | Windows 10 version 2004, build 19041 eller senare, eller Windows 11; 64 bitar och aktiverad virtualisering; 8 GB RAM, 12 GB rekommenderat; 10 GB ledigt på installationsenheten, 20 GB rekommenderat. |
| Debian/Ubuntu | Debian 11/12/13 eller Ubuntu 22.04/24.04; angivna arkitekturer amd64 och arm64; under 5 GB ledigt stoppar installationen, 5 till under 10 GB ger varning, minst 10 GB klarar kontrollen. |

Katalog, bilagor, index och backup kräver extra utrymme. **Linux-RAM, att bekräfta:** guiden rekommenderar 4 GB för dedikerad server, helst 8 GB; skrivbord/virtualisering 8 GB, helst 12 GB. Linux-förkontrollen kräver inte något numeriskt RAM-minimum. Godkänt betyder inte kapacitet för varje belastning. Windows tolererar hårdvarureserverat minne med uppmätta gränser 7,5 och 11,5 GB.

Linux kräver administratörsrättigheter och åtkomst till Koha-paketarkivet. TCP 80/8080 används för OPAC/staff. Om upptagna erbjuds stopp av berörda tjänster. **Godkänn bara om de får avbrytas.**

## Windows med PowerShell

Logga in med Windows-administratörskontot som ska använda Koha. Öppna PowerShell som administratör i samma konto:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Om behörighetshöjningen begär någon annans konto, avbryt och logga in rätt: WSL-komponenterna tillhör installationskontot. Läs kontrollerna och åtgärda avstängd virtualisering. Besvara Debian-kontofrågorna i fönstret; kontot är skilt från Koha-bibliotekskontot.

Vänta på WSL 2/Debian. Begärd omstart registrerar fortsättning vid nästa Windows-inloggning. Välj språk och **Install Koha server**. När panelinstallationen är klar, avsluta normalt och låt Windows-integrationen slutföras.

Standardmapp `C:\Koha`, äldre installation kan behålla `C:\KohaEasy`. Flytta inte mappen för att reparera avbrott. Spara felmeddelandet: slutförda steg registreras, körningen kan återupptas eller panelen öppnas för färdigställande. Det gör inte destruktiv ominstallation ofarlig.

## MSIX

Paketet förbereder samma WSL; installerat MSIX innebär inte färdig Koha-server/databas. Använd **vanlig PowerShell utan föregående administratörshöjning**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

Hjälpen hämtar paketet som koden anger, kontrollerar ursprung, begär administrativa rättigheter och installerar för aktuell användare. Ignorera inte avslag. Vänta på förberedelsen, slutför den guidade serverinstallationen, lämna panelen normalt och vänta på genvägar, bakgrundsuppgifter och nätverk. För tidig stängning slutför inte servern; öppna igen för att fortsätta.

**Att bekräfta:** offentlig Microsoft Store-tillgänglighet och adress. Paketeringsstöd bevisar inte publicering. Även MSIX på ARM64 behöver fullständig kontroll: manifestet är x64; Linux-arm64 räcker inte som bevis. Manifestet tillåter äldre Windows än hela WSL-flödet; planera efter fullständiga krav ovan.

## Debian/Ubuntu

I serverns terminal:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Med lokal repositorykopia och översättningar:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Välj språk och **Install Koha server**. Åtgärda kritiska fel först; varningar är ingen allmän kapacitetsgaranti. WSL kräver WSL 2 med systemd igång; WSL 1 avvisas. Windows-användare bör använda förberedelsen ovan.

## Serverinstallation i panelen

1. Öppna **Install Koha server**, invänta förkontroll, läs rapport och bedöm portfrigöringens påverkan.
2. Bekräfta rätt måldator och tidszon eller välj region/stad.
3. **Befintlig instans: stanna och kontrollera.** Ominstallation raderar databas och konfiguration, med extra bekräftelse och exakt `REINSTALL`. Inte för att bara öppna/uppdatera panelen.
4. Vänta utan att stänga; installationen kan inte avbrytas. Uppskattade 10 till 30 minuter beror på dator/nätverk.
5. Läs resultat/rapport; avslut med problem betyder inte friska tjänster. Bedöm erbjuden omstart och invänta även Windows-fortsättningen vid MSIX.

Kopiera inte privata uppgifter från resultatet till offentliga dokument eller supportärenden.

## Kontrollerade källor

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
