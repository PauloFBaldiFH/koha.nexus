# 1. Installation

[Inhalt](README.md)

## Umgebung und Voraussetzungen

Unter Windows läuft Koha in Debian unter WSL 2. Die Windows-Werkzeuge bereiten diese Umgebung vor, öffnen die Bedienoberfläche und integrieren die Anwendung. Unter Debian/Ubuntu werden Dienste und Bedienoberfläche direkt installiert. Öffnen Sie einen vorhandenen Katalog über das Panel statt die Installation zu wiederholen.

| Umgebung | Prüfungen im Code |
| --- | --- |
| Windows | Windows 10 Version 2004, Build 19041 oder neuer, oder Windows 11; 64 Bit, Virtualisierung eingeschaltet; 8 GB RAM, 12 GB empfohlen; 10 GB frei auf dem Installationslaufwerk, 20 GB empfohlen. |
| Debian/Ubuntu | Debian 11/12/13 oder Ubuntu 22.04/24.04; vom Installer benannte Architekturen amd64 und arm64; unter 5 GB frei blockiert, 5 bis unter 10 GB warnt, ab 10 GB besteht diese Prüfung. |

Katalog, Anhänge, Indizes und Backups benötigen zusätzlich Platz. **Linux-RAM noch zu bestätigen:** Die Anleitung empfiehlt 4 GB für dedizierte Server, besser 8 GB; für Arbeitsplatz/Virtualisierung 8 GB, besser 12 GB. Die Linux-Vorprüfung erzwingt derzeit keinen numerischen RAM-Mindestwert. Bestehen garantiert keine ausreichende Leistung für jede Last. Windows berücksichtigt reservierten Arbeitsspeicher mit erkannten Schwellen 7,5 und 11,5 GB.

Linux verlangt administrative Rechte und Zugriff auf das Koha-Paketarchiv. TCP 80/8080 dienen OPAC/staff. Sind sie belegt, bietet das Panel an, die betreffenden Dienste anzuhalten. **Nur zustimmen, wenn deren Unterbrechung zulässig ist.**

## Windows mit PowerShell

Melden Sie sich mit dem Windows-Administratorkonto an, das Koha nutzen wird. Öffnen Sie PowerShell dort als Administrator:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Verlangt die Rechteerhöhung ein fremdes Konto, brechen Sie ab und melden sich passend an: WSL-Komponenten gehören zum Installationskonto. Lesen Sie die Prüfungen und beheben deaktivierte Virtualisierung. Beantworten Sie im Fenster die Fragen zum Debian-Konto; es ist vom Koha-Bibliothekskonto getrennt.

Warten Sie auf WSL 2 und Debian. Bei angefordertem Neustart wird die Fortsetzung für die nächste Windows-Anmeldung eingerichtet. Wählen Sie im Panel Sprache und **Install Koha server**. Nach Abschluss verlassen Sie es regulär und warten auf die Windows-Integration.

Standardordner ist `C:\Koha`; ältere Installationen können `C:\KohaEasy` behalten. Nicht zur Fehlerbehebung verschieben. Notieren Sie Fehler: abgeschlossene Schritte werden gespeichert, der Ablauf kann fortgesetzt oder das Panel zum Fertigstellen geöffnet werden. Eine destruktive Neuinstallation wird dadurch nicht gefahrlos.

## MSIX unter Windows

MSIX bereitet dieselbe WSL-Umgebung vor; Paketinstallation bedeutet noch keine fertige Koha-Datenbank. Öffnen Sie **normale PowerShell ohne vorherige Rechteerhöhung**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

Der Helfer lädt das im Code festgelegte Paket, prüft dessen Herkunft, fragt Verwaltungsrechte an und installiert für den aktuellen Benutzer. Ablehnungen nicht ignorieren. Warten Sie beim ersten Start auf die Vorbereitung und schließen die geführte Serverinstallation ab. Verlassen Sie das Panel regulär; Verknüpfungen, Hintergrundaufgaben und Windows-Netzwerk müssen fertig werden. Vorzeitig geschlossen heißt nicht fertig: erneut öffnen und fortsetzen.

**Noch zu bestätigen:** öffentliche Microsoft Store-Verfügbarkeit und Adresse. Verpackungscode beweist keine Veröffentlichung. Auch MSIX auf ARM64 ist nicht durchgehend bestätigt: Das Manifest ist x64; Linux-arm64-Support beweist keine Paketkompatibilität. Das Manifest erlaubt älteres Windows als der vollständige WSL-Ablauf; verwenden Sie die vollständigen Anforderungen oben.

## Debian oder Ubuntu

Im Terminal des Servers:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Mit lokaler Repository-Kopie und Übersetzungen:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Sprache und **Install Koha server** wählen. Kritische Fehler zuerst beheben, Warnungen lesen; sie sind keine allgemeine Kapazitätszusage. WSL benötigt Version 2 mit laufendem systemd, WSL 1 wird abgewiesen. Windows-Benutzer sollten die geführte Vorbereitung verwenden.

## Server im Panel installieren

1. **Install Koha server** öffnen, Vorprüfung abwarten, Bericht lesen und Auswirkungen einer Portfreigabe prüfen.
2. Erst nach Prüfung des Zielrechners bestätigen; erkannte Zeitzone übernehmen oder Region/Stadt wählen.
3. **Vorhandene Instanz: anhalten und prüfen.** Neuinstallation löscht Datenbank und Konfiguration, verlangt zusätzliche Bestätigung und exakt `REINSTALL`. Nicht nur zum Öffnen oder Aktualisieren verwenden.
4. Ohne Schließen warten: nicht abbrechbar. Geschätzte 10 bis 30 Minuten hängen von Rechner und Netzwerk ab.
5. Ergebnis und angebotenen Bericht lesen; Abschluss mit Problemen bedeutet nicht gesunde Dienste. Angebotenen Neustart prüfen; bei MSIX auch Windows-Fortsetzung abwarten.

Private Angaben der Ergebnisausgabe gehören nicht in öffentliche Dokumente oder Supportanfragen.

## Geprüfte Quellen

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
