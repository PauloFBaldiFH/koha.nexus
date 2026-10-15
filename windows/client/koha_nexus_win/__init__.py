"""koha_nexus_win: the Python tray and status window of koha.nexus for Windows.

Phase 1 foundation: installed next to the PowerShell tools in
C:\\Koha\\bin\\client and run by the embeddable Python in C:\\Koha\\bin\\python
(KohaEasy.Python.psm1 puts both in place). Nothing starts it yet: the
PowerShell tray and window (KohaEasy.Tray.ps1, KohaEasy.Window.ps1) stay
what librarians use until the switch of Phase 2. To try it by hand:

    C:\\Koha\\bin\\python\\pythonw.exe -m koha_nexus_win window
    C:\\Koha\\bin\\python\\pythonw.exe -m koha_nexus_win tray     (close the Koha icon first)
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
  window.py   pywebview window on ui/index.html
  winapi.py   the few Win32 calls (named mutex, UI language, uptime)

Only tray.py, window.py, notify.py and winapi.py touch Windows-only modules,
and only inside functions, so everything else is tested on Linux.
"""

__version__ = "0.1.0"
