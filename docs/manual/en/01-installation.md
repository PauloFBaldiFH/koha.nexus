# 1. Installation

[Manual index](README.md) · [Next: the panel](02-panel.md)

## 1.1 Choose the environment

On Windows, Koha runs inside Debian under WSL 2. The Windows tools prepare that environment, open the panel and integrate the application with the computer. On Debian or Ubuntu, the panel and services are installed directly on the server.

Do not use installation to open an existing catalogue: when the panel detects an installed instance, reinstallation has its own destructive confirmation. To use an existing installation, open the panel as described in chapter 2.

### Requirements checked in the code

| Environment | System and architecture | Memory | Free space |
| --- | --- | --- | --- |
| Windows | Windows 10 version 2004, build 19041 or later, or Windows 11; 64-bit system; virtualisation enabled | 8 GB; 12 GB recommended | 10 GB on the installation drive; 20 GB recommended |
| Debian/Ubuntu | Debian 11, 12 or 13; Ubuntu 22.04 or 24.04; the installer identifies amd64 and arm64 as its tested architectures | See the qualification below | Less than 5 GB blocks installation; 5 GB to under 10 GB produces a warning; 10 GB or more passes this check |

These are entry checks. The catalogue, attachments, indexes and backup copies also need space during operation.

**Linux RAM, to confirm:** the existing installation guide recommends 4 GB for a dedicated server, with 8 GB recommended, and 8 GB for a desktop or virtualised environment, with 12 GB recommended. However, the inspected Linux preflight does not enforce a numerical RAM minimum. Passing that step is not a capacity guarantee. Sizing must take the computer and the library's workload into account.

On Windows, the check allows for some memory reserved by hardware: its internal thresholds are 7.5 GB and 11.5 GB of detected memory. This explains why a computer sold with 8 GB can report slightly less without being rejected.

On Linux, the installer requires administrative privileges and checks access to the Koha repository. TCP ports 80 and 8080 serve the public catalogue and staff interface. If they are occupied, the panel offers to stop the services using them. **Accept only if you know those services can be interrupted.**

Sources: [`Get-KohaPreflight`](../../../windows/KohaEasy.Install.psm1); `install_precheck`, `platform_check`, `validate_network_and_system` and `install_free_ports` in the [installer](../../../installer); requirements in the [existing installation guide](../../../README.md).

## 1.2 Windows: PowerShell installation

1. Sign in to the Windows account that will use Koha and has administrator rights.
2. Open PowerShell as administrator in that same account.
3. Run:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

If elevation asks for another person's account, cancel and sign in with an appropriate administrator account. WSL components belong to the account used for installation.

4. Read the computer checks. If virtualisation is disabled, follow the instructions shown for the hardware and resolve the problem before resuming.
5. Answer the Debian account creation questions directly in the installer window. This account is separate from the Koha library account.
6. Wait while WSL 2 and Debian are prepared. If a restart is required, the installer registers a continuation for the next Windows sign-in.
7. When the panel opens, choose the language and **Install Koha server**. Follow section 1.5.
8. After installation finishes in the panel, exit it normally so the Windows flow can continue. Wait for integration to finish and read the final result.

The default tools folder is `C:\Koha`. An older installation in `C:\KohaEasy` may remain there. Do not move the folder manually to try to repair an interrupted installation.

If preparation stops, record the message. The flow records completed stages and can resume when you run the installer again. If it detects that Koha installation is incomplete, it may reopen the panel to finish it. This does not make destructive reinstallation safe to repeat without reading the confirmations.

Sources: [Windows bootstrap](../../../windows/install.ps1), `Install-Koha` and `Register-KohaResume` in [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1), and path configuration in [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).

## 1.3 Windows: MSIX package

The MSIX is another entry point for preparing the same WSL environment. Installing the package does not mean that the Koha server and database are already configured.

To install the project's package with the existing helper, open a **normal**, non-elevated PowerShell window and run:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

The helper downloads the package configured in its script, checks its origin, requests the necessary administrative authorisation and installs it for the current user. Do not ignore rejection messages. It then opens Koha.Nexus to continue preparation.

On first launch, wait for preparation and follow the guided installation inside the panel. After completing it, exit the panel normally and wait for Windows shortcuts, background tasks and networking to be finalised. If you close the panel before finishing the Koha server, open the application again to continue; closing the window alone should not mark installation complete.

**Microsoft Store, to confirm:** the repository includes a Store packaging mode. Availability and the public listing address need confirmation. This manual does not supply an assumed Store link.

**ARM64, to confirm:** the generated MSIX manifest is x64. Do not infer compatibility of that package with ARM64 from the Linux installer's arm64 support.

The package manifest permits an older Windows version than the complete WSL flow accepts. When planning a Koha installation, use the full requirement in section 1.1, rather than the manifest minimum alone.

Sources: [MSIX installation helper](../../../windows/msix/instalar_msix.ps1), `NeedsVisibleSetup` in the [MSIX entry point](../../../windows/msix/KohaMsixEntry.cs), [continuation after the panel](../../../windows/KohaMsixPanel.ps1), and the manifest generated by the [MSIX compiler](../../../windows/msix/compilar_msix.ps1). These files were inspected, not executed during this review.

## 1.4 Debian or Ubuntu

In a terminal on the server, download and open the installer as documented in the existing guide:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

To keep a repository copy and its translations alongside the installer, the documented alternative is:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Choose the language and open **Install Koha server**. Installation checks the system, required programs, network access, space and ports. Resolve critical failures before continuing. Read warnings rather than treating them as approval for any workload.

If using a distribution under WSL, it must be WSL 2 with systemd running. The code rejects WSL 1 in this flow. Windows users should use the guided preparation in section 1.2 or 1.3.

Sources: [commands in the existing guide](../../../README.md); `install_precheck`, `platform_check` and `require_systemd` in the [installer](../../../installer).

## 1.5 Install the server inside the panel

1. Open **Install Koha server** and wait for the initial check.
2. Read the report. Critical failures prevent progress. If ports are occupied, assess the impact before authorising their release.
3. Confirm the start only after checking the target computer.
4. Confirm the detected timezone or select a region and city.
5. **If an existing instance is detected, stop and check:** reinstallation deletes its database and configuration. It requires an additional confirmation and the exact word `REINSTALL`. Do not use it simply to open or update the panel.
6. Wait for the stages to finish. The screen estimates 10 to 30 minutes, but actual time depends on hardware and the network. Installation is marked as non-cancellable in the panel; do not close the window during the operation.
7. Read the final result. Completion with issues does not mean that every service is healthy. Open the offered report and record failed checks.
8. Consider restarting when offered. In the MSIX flow, also wait for the Windows continuation described above after leaving the panel.

Do not copy private data from the result screen into public documents or support requests. The next chapter explains addresses and initial checks without reproducing those details.

Source: `install_koha` and `_choose_timezone` in [routines/install.py](../../../panel/kei_panel/routines/install.py).
