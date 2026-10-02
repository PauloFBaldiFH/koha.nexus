@echo off
setlocal
cd /d "%~dp0"
title Koha Easy Installer

:: Already running as administrator? Otherwise ask Windows for it (UAC).
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :run
) else (
    echo Solicitando privilegios de Administrador...
    powershell -Command "Start-Process '%~f0' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit
)

:run
rem Koha Easy Installer for Windows: double-click to install Koha on this PC.
rem It runs exactly the PowerShell one-line command of the README (the latest
rem windows\install.ps1 from GitHub), so both ways install the same way.
rem Running it again continues where it stopped.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; irm https://raw.githubusercontent.com/PauloFBaldiFH/Koha-Easy-Installer/main/windows/install.ps1 | iex"
echo.
pause
