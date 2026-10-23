# 2. Getting started and using the panel

[Manual index](README.md) · [Installation](01-installation.md) · [Backup and restore](03-backup-restore.md)

## 2.1 Open the panel

On Debian or Ubuntu already prepared by the installer, run:

```bash
sudo config.sh
```

On Windows, use the **Koha** icon created by the installer or open Koha.Nexus installed through MSIX. For the MSIX procedure, see section 1.3.

The first launch may ask you to choose a language before showing the main screen. If preparation of the Textual interface fails, the installer may offer the classic panel. This manual mainly describes the Textual panel; its screens do not reproduce the option numbers of the classic menu.

Sources: `install_panel_copy` and interface startup in the [installer](../../../installer), `on_mount` in [app.py](../../../panel/kei_panel/app.py), and the [Windows startup flow](../../../windows/KohaEasy.Install.psm1).

## 2.2 Find an action

The sidebar lists sections. Use the arrow keys to highlight a section and **Enter** to open it, or click it. Moving the highlight alone does not execute an action. In the content area, open the appropriate task card and read its questions before confirming.

**Tab** moves focus between controls. The shortcuts below belong to the main screen; finish editing or leave a text field before trying letter shortcuts.

| Key | Checked action |
| --- | --- |
| `d` | Open Control Dashboard |
| `b` | Open Backup center |
| `c` | Open the Debian terminal |
| `Ctrl+B` | Show or hide the sidebar |
| `q` | Exit the panel |

Exiting an idle panel is not the server shutdown procedure. For an operation in progress, follow that screen's cancellation instructions. Installation and restore have explicitly non-cancellable stages; forcibly closing the window is not a safe way to interrupt them.

Sources: `MainScreen.BINDINGS`, `on_option_list_option_selected` and `action_show` in [screens/main.py](../../../panel/kei_panel/screens/main.py); `BINDINGS` in [app.py](../../../panel/kei_panel/app.py); calls with `cancellable=False` in the [installation](../../../panel/kei_panel/routines/install.py) and [restore](../../../panel/kei_panel/routines/backup.py) routines.

## 2.3 Read Control Dashboard

The initial screen shows:

- **Koha:** overall state and available memory.
- **Last backup:** date, age and newest file found.
- **Free disk:** available space relative to total space.
- Access addresses for the catalogue and staff interface on this computer, the local network and, when configured, the internet.
- Components including MariaDB, Apache, RabbitMQ, Memcached and Koha, along with HTTP response checks.

The backup indicator considers both file age and the reported outcome of the last nightly run. A favourable card does not replace the restore test described in chapter 3. A recent file can coexist with a failed nightly run: read both indicators.

The HTTP result reports a response according to the panel's check. By itself, it does not establish that Koha's web installer has been completed or that every library function has been tested.

Use **Refresh** to read the status again. **Restart Koha** requests the service repair/restart routine; consider current catalogue users before doing so. **Export diagnostics** prepares diagnostic information. These buttons may be unavailable when the installed installer does not support the corresponding task.

Source: `DashboardView`, `backup_card`, `OVERALL`, `COMPONENTS` and `access_links` in [views/dashboard.py](../../../panel/kei_panel/views/dashboard.py).

## 2.4 Open the catalogue and staff interface

Use the address cards for your installation. Each lets you open or copy its URL. If the environment cannot open a browser, the panel may copy the address so you can paste it into your computer's browser.

By default, the catalogue uses port 80 and the staff interface uses 8080. On the server computer, the local addresses are:

- Public catalogue: `http://localhost/`.
- Staff interface: `http://localhost:8080/`.

These addresses are local: on another computer, use the network address shown by the panel. If it reports that the local network is unreachable because WSL uses NAT, do not assume the local address will work from every computer. Check the Windows network preparation result and consult the person responsible for the environment.

If the staff interface displays Koha's web installer, complete it before starting catalogue operations. This manual does not assume that every version of Koha has identical web installer steps.

Sources: `access_links` and `http_url` in [views/dashboard.py](../../../panel/kei_panel/views/dashboard.py), `open_url` in [app.py](../../../panel/kei_panel/app.py), defaults in [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1), and next-step instructions emitted by the [installer](../../../installer).

## 2.5 Prepare library operations

After completing the web installer, **Create super librarian** is available under **Koha settings & parameters**. It opens a separate account creation flow; enter private details only in your installation. This manual does not reproduce access values.

Before starting work with the collection:

1. Refresh Control Dashboard and check components and addresses.
2. Open the staff interface and catalogue using addresses appropriate to your computer.
3. Generate and test a backup as described in chapter 3.
4. Confirm where the copy outside the server was saved and who can recover it.

Step 4 is an operational recommendation: the panel can create and copy files, but a usable copy outside the computer depends on completing the transfer and checking its result.

Sources: the `settings` section of [menus.py](../../../panel/kei_panel/menus.py), `superlibrarian` in [routines/settings.py](../../../panel/kei_panel/routines/settings.py), and the [backup and transfer routines](../../../panel/kei_panel/routines/backup.py).
