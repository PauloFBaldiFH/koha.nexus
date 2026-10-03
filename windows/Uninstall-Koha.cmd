@echo off
setlocal
title Koha - Uninstall

rem Removes Koha from this PC: double-click it in the Koha folder (C:\Koha).
rem It asks before anything is removed. The Debian "koha" with the Koha
rem databases, the shortcuts, the status icon, the scheduled tasks and this
rem folder go; the Backups folder stays unless you choose to delete it too.
rem Settings > Apps > Koha > Uninstall does the same.
rem The whole command is one line, so this file can be deleted while it runs.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0bin\KohaEasy.ps1" Uninstall & exit /b
