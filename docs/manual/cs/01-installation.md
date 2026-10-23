# 1. Instalace

[Obsah](README.md)

## Prostředí a požadavky

Ve Windows běží Koha v Debian přes WSL 2. Nástroje Windows připraví prostředí, otevřou panel a integrují aplikaci. V Debian/Ubuntu se panel a služby instalují přímo. Existující katalog otevřete panelem, neopakujte kvůli tomu instalaci.

| Prostředí | Kontroly v kódu |
| --- | --- |
| Windows | Windows 10 verze 2004, sestavení 19041 nebo novější, případně Windows 11; 64 bitů a virtualizace; RAM 8 GB, doporučeno 12 GB; volných 10 GB na instalačním disku, doporučeno 20 GB. |
| Debian/Ubuntu | Debian 11/12/13 nebo Ubuntu 22.04/24.04; uvedené amd64/arm64; pod 5 GB blokace, 5 až méně než 10 GB varování, od 10 GB kontrola úspěšná. |

Katalog, přílohy, indexy a backup potřebují další místo. **RAM Linux, k potvrzení:** návod doporučuje 4 GB pro vyhrazený server, lépe 8 GB; desktop/virtualizace 8 GB, lépe 12 GB. Současná předběžná kontrola Linux nevynucuje číselné minimum RAM. Úspěch nezaručuje výkon pro každou zátěž. Windows toleruje paměť rezervovanou hardwarem: zjištěné hranice 7,5 a 11,5 GB.

Linux vyžaduje správce a přístup k balíčkovému úložišti Koha. TCP 80/8080 používají OPAC/staff. Při obsazení lze zastavit příslušné služby. **Souhlaste pouze, pokud je lze přerušit.**

## Windows a PowerShell

Přihlaste se správcovským účtem Windows, který bude Koha používat. Otevřete PowerShell jako správce ve stejném účtu:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Žádá-li zvýšení práv jiný účet, zrušte a přihlaste se vhodně: WSL patří instalačnímu účtu. Přečtěte kontroly, opravte vypnutou virtualizaci. V okně odpovězte na otázky k účtu Debian, odlišnému od knihovnického Koha.

Vyčkejte WSL 2/Debian. Požadovaný restart zaznamená pokračování při dalším přihlášení Windows. Vyberte jazyk/**Install Koha server**. Po dokončení v panelu běžně ukončete a vyčkejte integrace Windows.

Výchozí `C:\Koha`; starší instalace může ponechat `C:\KohaEasy`. Nepřesouvejte pro opravu přerušení. Zapište chybu: hotové fáze se ukládají, opakování může navázat či otevřít panel k dokončení. Destruktivní reinstalace tím není bezpečná.

## MSIX

Balíček připravuje stejné WSL; instalace balíčku nedokončuje server/databázi. **Běžný PowerShell bez předchozího zvýšení práv**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

Pomocník stáhne balíček nastavený v kódu, ověří původ, vyžádá správce a instaluje aktuálnímu uživateli. Odmítnutí neignorujte. Vyčkejte přípravy, dokončete průvodce serveru, běžně opusťte panel a počkejte na zástupce, úlohy a síť. Předčasné zavření není dokončení: otevřete znovu.

**K potvrzení:** veřejná dostupnost/adresa Microsoft Store; balicí kód nedokládá publikaci. Plný provoz MSIX na ARM64 rovněž nepotvrzen: manifest x64, podpora arm64 Linux nestačí. Manifest připouští starší Windows než celý WSL postup; plánujte podle plných požadavků výše.

## Debian/Ubuntu

V terminálu serveru:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

S lokálním repozitářem a překlady:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Jazyk/**Install Koha server**. Kritické chyby nejdříve opravte, varování není kapacitní záruka. WSL vyžaduje WSL 2 a spuštěný systemd, WSL 1 odmítá. Ve Windows preferujte předchozí vedenou přípravu.

## Instalace v panelu

Otevřete **Install Koha server**, vyčkejte kontroly a zprávy a zvažte dopad uvolnění portů. Ověřte cílový počítač a pásmo, případně region/město. **Existující instance: zastavte se a ověřte.** Reinstalace smaže databázi/konfiguraci, vyžaduje další potvrzení a přesné `REINSTALL`. Neslouží jen otevření/aktualizaci panelu.

Nezavírejte: nelze zrušit. Odhad 10 až 30 minut závisí na hardwaru/síti. Čtěte výsledek a zprávu: dokončení s problémy neznamená zdravé služby. Posuďte restart a u MSIX počkejte i na pokračování Windows. Soukromé údaje výsledku nepatří do veřejných dokumentů či podpory.

## Ověřené zdroje

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
