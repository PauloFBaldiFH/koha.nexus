# 1. Instalacja

[Spis treści](README.md)

## Środowisko i wymagania

W Windows Koha działa w Debian przez WSL 2. Narzędzia Windows przygotowują środowisko, otwierają panel i integrują aplikację. W Debian/Ubuntu panel i usługi instalowane są bezpośrednio. Istniejący katalog otwiera się przez panel, nie przez ponowną instalację.

| Środowisko | Kontrole w kodzie |
| --- | --- |
| Windows | Windows 10 wersja 2004, kompilacja 19041 lub nowsza, albo Windows 11; 64 bity, włączona wirtualizacja; RAM 8 GB, zalecane 12 GB; wolne 10 GB na dysku instalacji, zalecane 20 GB. |
| Debian/Ubuntu | Debian 11/12/13 albo Ubuntu 22.04/24.04; wskazane amd64/arm64; poniżej 5 GB blokada, od 5 do poniżej 10 GB ostrzeżenie, od 10 GB kontrola zaliczona. |

Katalog, załączniki, indeksy i backup potrzebują dodatkowej przestrzeni. **RAM Linux, do potwierdzenia:** instrukcja zaleca 4 GB dla serwera dedykowanego, najlepiej 8 GB; pulpit/wirtualizacja 8 GB, najlepiej 12 GB. Obecna kontrola Linux nie wymusza liczbowego minimum RAM. Jej zaliczenie nie gwarantuje obsługi każdego obciążenia. Windows uwzględnia pamięć zarezerwowaną sprzętowo: progi wykryte 7,5 i 11,5 GB.

Linux wymaga uprawnień administratora i dostępu do repozytorium pakietów Koha. TCP 80/8080 służą OPAC/staff. Zajęte porty wywołują propozycję zatrzymania usług. **Zgoda tylko, jeśli można je przerwać.**

## Windows: PowerShell

Zaloguj się na konto administratora Windows, które będzie używać Koha, i otwórz PowerShell jako administrator na tym samym koncie:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Jeśli podniesienie uprawnień żąda cudzego konta, anuluj i zaloguj się odpowiednio: WSL należy do konta instalującego. Przeczytaj kontrole, włącz wirtualizację, jeśli wymagana. Odpowiedz w oknie na pytania o konto Debian, odrębne od bibliotecznego konta Koha.

Poczekaj na WSL 2/Debian. Żądany restart zapisuje kontynuację przy następnym logowaniu Windows. Wybierz język i **Install Koha server**. Po zakończeniu instalacji w panelu wyjdź normalnie i poczekaj na integrację Windows.

Domyślnie `C:\Koha`; starsza instalacja może zachować `C:\KohaEasy`. Nie przenoś folderu, aby naprawić przerwanie. Zapisz błąd: ukończone etapy są rejestrowane, ponowienie może wznowić lub otworzyć panel do dokończenia. Nie czyni to destrukcyjnej reinstalacji bezpieczną.

## Windows: MSIX

Pakiet przygotowuje to samo WSL; instalacja pakietu nie oznacza gotowego serwera/bazy. Uruchom **zwykły PowerShell bez wcześniejszego podniesienia uprawnień**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

Pomocnik pobiera pakiet wskazany w kodzie, weryfikuje pochodzenie, prosi o zgodę administratora i instaluje dla bieżącego użytkownika. Nie ignoruj odmów. Zaczekaj na przygotowanie, ukończ instalację serwera, wyjdź z panelu normalnie i poczekaj na skróty, zadania i sieć Windows. Przedwczesne zamknięcie nie kończy instalacji: otwórz ponownie.

**Do potwierdzenia:** publiczna dostępność/adres Microsoft Store; kod pakowania nie dowodzi publikacji. Pełne działanie MSIX na ARM64 również niepotwierdzone: manifest x64, obsługa arm64 Linux nie wystarcza. Manifest dopuszcza starszy Windows niż cały proces WSL; kieruj się pełnymi wymaganiami powyżej.

## Debian/Ubuntu

W terminalu serwera:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Z lokalnym repozytorium i tłumaczeniami:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Wybierz język/**Install Koha server**. Najpierw usuń błędy krytyczne; ostrzeżenie nie gwarantuje wydajności. WSL wymaga WSL 2 i działającego systemd; WSL 1 odrzucany. W Windows zalecany wcześniejszy proces prowadzony.

## Instalacja z panelu

Otwórz **Install Koha server**, poczekaj na kontrolę i przeczytaj raport; oceń skutki zwolnienia portów. Sprawdź komputer docelowy, zaakceptuj strefę lub wybierz region/miasto.

**Istniejąca instancja: zatrzymaj się i sprawdź.** Reinstalacja usuwa bazę/konfigurację, wymaga dodatkowego potwierdzenia i dokładnie `REINSTALL`. Nie służy tylko otwarciu/aktualizacji panelu. Poczekaj bez zamykania: proces nieanulowalny, szacowane 10 do 30 minut zależy od sprzętu/sieci. Przeczytaj wynik/raport, bo zakończenie z problemami nie oznacza sprawnych usług. Rozważ proponowany restart, a dla MSIX poczekaj również na dalsze kroki Windows.

Prywatnych danych z wyniku nie umieszczaj w publicznych dokumentach ani zgłoszeniach.

## Sprawdzone źródła

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
