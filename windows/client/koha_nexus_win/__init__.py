"""koha_nexus_win: the koha.nexus Control Center for Windows.

One process with the tray icon and one resizable window: the control
panel's sections in a sidebar (read from panel/kei_panel/menus.py), the
status dashboard, and tasks of the installer (--task) running inside the
window. Phase A of the Control Center study, on the Phase 1 foundation:
installed next to the PowerShell tools in C:\\Koha\\bin\\client and run
by the embeddable Python in C:\\Koha\\bin\\python (KohaEasy.Python.psm1
puts both in place). Nothing starts it yet: the
PowerShell tray and window (KohaEasy.Tray.ps1, KohaEasy.Window.ps1) stay
what librarians use until the switch of Phase E. To try it by hand:

    C:\\Koha\\bin\\python\\pythonw.exe -m koha_nexus_win app      (close the Koha icon first)
    C:\\Koha\\bin\\python\\pythonw.exe -m koha_nexus_win tray     (the same, only the icon at first)
    C:\\Koha\\bin\\python\\python.exe  -m koha_nexus_win check    (one status check, printed)

Layout:
  config.py   the Koha folder, state.json, URLs and names ($Cfg of KohaEasy.Core.psm1)
  store.py    state.json, read and merged the way Get/Set-KohaState do
  wsl.py      the Runner: wsl.exe into the "koha" distro, never starting it
  notify.py   the Notifier: Windows toast, else the tray balloon, always the log
  actions.py  tray and window buttons, run as the existing KohaEasy.ps1 verbs
  menu.py     the tray menu as data (which items, enabled when)
  viewmodel.py  what the window shows, as plain JSON for ui/app.js
  tray.py     pystray icon + background checks (nexus_core.monitor)
  window.py   the Api the page calls (dashboard, sections, tasks)
  engine.py   runs `koha-panel --task NAME` in Debian, reads its @@ events
              (nexus_core.taskproto) and batches them for the page
  app.py      the window (pywebview on ui/) and the tray in one process
  winapi.py   the few Win32 calls (named mutex and event, UI language, uptime)

Only tray.py, app.py, notify.py and winapi.py touch Windows-only modules,
and only inside functions, so everything else is tested on Linux.
"""

__version__ = "0.1.0"
