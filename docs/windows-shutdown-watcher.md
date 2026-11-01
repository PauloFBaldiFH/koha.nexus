# Windows shutdown watcher (koha.nexus 1.5.69)

When Windows shuts down, restarts or signs out, WSL2 is stopped with it. If
MariaDB, Zebra or Elasticsearch are still writing at that moment, InnoDB pages
and index files can be left half-written. The shutdown watcher makes Windows
wait for Koha's clean stop first.

## The pieces

| File | Runs on | What it does |
| --- | --- | --- |
| `windows/koha-graceful-shutdown.sh` | Debian (WSL2), as root | Stops Apache and koha-common, then Plack, the background workers (both queues), the indexers and Zebra of every instance, then MariaDB, then RabbitMQ, Memcached and Elasticsearch (MariaDB first: the 20 s at the end of a session go to the database); runs `sync`; `koha-stop-guard stop` records the clean stop. Exit 0 only when everything stopped. |
| `windows/KohaEasy.Watcher.ps1` | Windows, at sign-in, hidden | `KohaEasy.ps1 Watcher`. Checks every 30 s whether the `koha` distro runs. |
| `windows/KohaEasy.Watcher.cs` | loaded by the watcher | The hidden window that answers `WM_QUERYENDSESSION` / `WM_ENDSESSION`. |

The Windows side writes the script into Debian as
`/usr/local/bin/koha-graceful-shutdown.sh` whenever Koha starts and the file is
missing or out of date (`Update-KohaStopScript`). Stop, Restart and "Shut down
the PC safely" run the same script.

## What happens at shutdown

1. **`WM_QUERYENDSESSION`**: while Koha runs, the watcher holds the shutdown
   block reason (`ShutdownBlockReasonCreate`): *"O Koha está salvando o banco
   de dados e finalizando os serviços com segurança..."*. It answers TRUE at
   once, so it never cancels a shutdown.
2. **`WM_ENDSESSION`** (wParam TRUE, the session really ends): the watcher
   runs, through a `wsl.exe` with no console (so Windows does not close it
   with the console programs):
   `wsl.exe -d koha -u root -- timeout -k 3 20 sh /usr/local/bin/koha-graceful-shutdown.sh`,
   then `wsl.exe --shutdown`, which closes `ext4.vhdx`.
3. **`ShutdownBlockReasonDestroy`**: done or not, the reason is released and
   Windows carries on. The script gets 20 s (`SessionStopS`); the block is
   released after 37 s at the latest.

The window is a hidden top-level window, not a message-only window
(`HWND_MESSAGE`): message-only windows get no broadcast messages, so they never
see the end of the session.

A power cut, or a forced shutdown, never reaches the watcher; the clean-stop
guard inside Debian checks and repairs Koha at the next start, as before.

## How the installer registers it

Nothing to do by hand: every run of the one-line installer
(`irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex`)
does it, right after the tray:

1. Writes `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value
   `KohaEasyShutdownWatcher`, with the same hidden launch as the tray
   (`C:\Koha\bin\koha.nexus.exe Watcher -Hidden`, or the fallback launch the
   installer settled on for that PC). No administrator rights are needed.
2. Starts the watcher now (a repair run first ends the watcher of the older
   version) and checks it is running (mutex `Local\KohaEasyShutdownWatcher`).

After that:

- At every sign-in Windows starts it from the Run entry, with no console and no
  icon.
- While Koha runs, the keep-alive task starts it again within a minute if it
  crashed or was ended (at most 5 times), as it does for the tray.
- The Koha icon (desktop, Start menu) puts back a deleted Run entry.
- While the watcher runs, the tray leaves the end of the session to it. With the
  watcher off or not running, the tray does the same stop (the behaviour before
  1.5.69).

### By hand (PowerShell, as the librarian, not as administrator)

```powershell
# Turn on: Run entry + start it now
& "C:\Koha\bin\KohaEasy.ps1" EnableShutdownWatcher
# Turn off: removes the Run entry, ends it; remembered (state.json shutdownWatcher = off)
& "C:\Koha\bin\KohaEasy.ps1" DisableShutdownWatcher
# Is it registered and running?
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name KohaEasyShutdownWatcher
```

The log lines start with `watcher:` in `C:\Koha\logs\koha-YYYYMMDD.log`, and
`diagnose.ps1` shows the Run entry and whether the watcher is running.
Uninstalling Koha removes the Run entry and ends the watcher.

## The distro

The watcher stops the distro the installer created, `koha` (`Distro` in
`KohaEasy.Core.psm1`), the same name every Koha tool on Windows uses.

## Tests

- `tests/graceful_shutdown.bats`: the script's order, exit codes, non-systemd
  fallback, and that it ends in under 5 s (stand-in commands, no Koha).
- `tests/windows_checks.ps1` (CI, Windows PowerShell 5.1 on a Windows runner):
  the watcher window gets `WM_QUERYENDSESSION` / `WM_ENDSESSION` through
  `SendMessage` and holds, then releases, the reason; the detached run; the
  session-end stop with a stand-in for `wsl.exe`; the Run entry on a test key.
- Not tested: a real Windows shutdown with Koha running.
