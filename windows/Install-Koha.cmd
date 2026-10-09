@echo off
setlocal
cd /d "%~dp0"
title koha.nexus

rem koha.nexus for Windows: double-click to install Koha on this PC.
rem It runs exactly the PowerShell one-line command of the README (the latest
rem windows\install.ps1 from GitHub), so both ways install the same way.
rem Running it again continues where it stopped.
rem
rem It runs as the signed-in user, never "as administrator": Debian, the
rem shortcuts and the restart step belong to this user, and Windows asks for
rem permission (UAC) only for the steps that need it (WSL, the network).
rem Elevating the whole install refused it for users without an administrator
rem password and put Debian in the administrator's account instead.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex"
if errorlevel 1 (
    echo.
    echo The installer could not start. If Windows or the antivirus blocked it,
    echo open PowerShell from the Start menu and paste the command from the
    echo README: it installs the same way.
)
echo.
pause
