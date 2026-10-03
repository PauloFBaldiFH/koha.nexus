# Koha Easy Installer for Windows - shortcut and tray check.
#
#   Checks, step by step, what the Koha icon and the Koha tray need, creates
#   the shortcuts and starts the tray again, and prints every error in full
#   (type, message, line and stack). Run it in Windows PowerShell as the
#   signed-in user (not as administrator):
#   irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
#
# Everything shown is also saved in C:\Koha\logs\diagnose-<date>.txt
# (no passwords are read). ASCII only: it must survive "irm | iex".

function Invoke-KohaEasyDiagnose {
    $ErrorActionPreference = 'Stop'
    # C:\Koha, or C:\KohaEasy for an install made before the folder was renamed.
    $root = 'C:\Koha'
    if ($env:KOHAEASY_ROOT) { $root = $env:KOHAEASY_ROOT }
    elseif (-not (Test-Path -LiteralPath (Join-Path $root 'bin')) -and (Test-Path -LiteralPath 'C:\KohaEasy\bin')) { $root = 'C:\KohaEasy' }
    $bin = Join-Path $root 'bin'
    $logs = Join-Path $root 'logs'
    New-Item -ItemType Directory -Path $logs -Force -ErrorAction SilentlyContinue | Out-Null
    $out = Join-Path $logs ('diagnose-{0}.txt' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    try { Start-Transcript -LiteralPath $out -Force | Out-Null } catch { }

    function Say { param([string]$Text, [string]$Color = 'Gray') Write-Host $Text -ForegroundColor $Color }
    function Head { param([string]$Text) Write-Host ''; Write-Host ('== ' + $Text) -ForegroundColor Cyan }
    function Show-Err {
        param($E)
        $x = $E.Exception
        Say ('  ERROR {0}: {1}' -f $x.GetType().FullName, $x.Message) 'Red'
        while ($x.InnerException) { $x = $x.InnerException; Say ('  inner {0}: {1}' -f $x.GetType().FullName, $x.Message) 'Red' }
        if ($E.Exception.HResult) { Say ('  HRESULT 0x{0:X8}' -f $E.Exception.HResult) 'Red' }
        if ($E.InvocationInfo) { Say ('  at ' + ($E.InvocationInfo.PositionMessage -replace "`r?`n", ' ')) 'DarkRed' }
        if ($E.ScriptStackTrace) { Say ('  stack: ' + ($E.ScriptStackTrace -replace "`r?`n", ' <- ')) 'DarkRed' }
    }

    Head 'Windows and PowerShell'
    $who = ''; $admin = ''
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        $who = $id.Name
        $admin = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { Show-Err $_ }
    Say ('  Windows {0} | PowerShell {1} ({2}) | user {3} | administrator: {4}' -f [Environment]::OSVersion.Version, $PSVersionTable.PSVersion, $PSVersionTable.PSEdition, $who, $admin)
    if ($admin -eq $true) { Say '  -> Run this as the signed-in user, not as administrator: an administrator window can write to another account''s desktop.' 'Yellow' }
    $mode = $ExecutionContext.SessionState.LanguageMode
    Say ('  PowerShell language mode: {0}' -f $mode)
    if ($mode -ne 'FullLanguage') { Say '  -> Windows restricts PowerShell here (AppLocker, WDAC or Smart App Control): shortcuts (COM) and the tray (Add-Type) cannot work in this mode.' 'Red' }
    if ($PSVersionTable.PSEdition -eq 'Core') { Say '  (This is PowerShell 7. Koha''s tools run in Windows PowerShell 5.1; the checks below still apply.)' 'Yellow' }
    try { Say ('  execution policy: ' + ((Get-ExecutionPolicy -List | ForEach-Object { '{0}={1}' -f $_.Scope, $_.ExecutionPolicy }) -join ', ')) } catch { Show-Err $_ }

    Head ('Files in ' + $bin)
    foreach ($f in 'KohaEasy.ps1', 'KohaEasy.Core.psm1', 'KohaEasy.Install.psm1', 'KohaEasy.Lang.psm1', 'KohaEasy.Tray.ps1', 'KohaEasy.Window.ps1', 'KohaEasy.Hidden.js', 'KohaEasy.exe', 'koha.ico', 'koha-logo.png') {
        $p = Join-Path $bin $f
        if (Test-Path -LiteralPath $p) { Say ('  ok      {0} ({1:yyyy-MM-dd HH:mm})' -f $f, (Get-Item -LiteralPath $p).LastWriteTime) } else { Say ('  missing {0}' -f $f) 'Yellow' }
    }

    Head 'Installer state (state.json)'
    $statePath = Join-Path $root 'state.json'
    $state = $null
    try {
        $state = Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop | ConvertFrom-Json
        foreach ($k in 'phase', 'launcher', 'hiddenLaunch', 'autostart', 'desired', 'trayClosed', 'appIdShortcut', 'linuxUser') {
            Say ('  {0} = {1}' -f $k, $state.$k)
        }
        if ($state.phase -ne 'done') {
            Say ('  -> The installation stopped at phase "{0}". The shortcuts, the tray and the tasks are made only in the last phase ("windows"), so none exist yet. Run the one-line installer again and send the red lines it prints.' -f $state.phase) 'Red'
        }
    } catch { Show-Err $_ }

    Head 'Latest logs'
    try {
        Get-ChildItem -LiteralPath $logs -Filter '*.log' -ErrorAction Stop | Sort-Object LastWriteTime -Descending | Select-Object -First 4 |
            ForEach-Object { Say ('  {0:yyyy-MM-dd HH:mm}  {1}' -f $_.LastWriteTime, $_.Name) }
        $install = Get-ChildItem -LiteralPath $logs -Filter 'install-*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($install) {
            Say ('  Important lines of {0}:' -f $install.Name)
            Select-String -LiteralPath $install.FullName -Pattern 'step failed|shortcut|Koha icon|tray|hidden launch|launcher|KohaEasy.exe|desktop|error|failed|phase' |
                Select-Object -Last 40 | ForEach-Object { Say ('    ' + $_.Line) }
        } else { Say '  no install-*.log: the installer never wrote its log here' 'Yellow' }
        $koha = Get-ChildItem -LiteralPath $logs -Filter 'koha-*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($koha) {
            Say ('  Last lines of {0}:' -f $koha.Name)
            Get-Content -LiteralPath $koha.FullName -Tail 15 | ForEach-Object { Say ('    ' + $_) }
        }
    } catch { Show-Err $_ }

    Head 'Desktop and Start menu folders'
    $shellDesk = ''
    try { $shellDesk = [string](New-Object -ComObject WScript.Shell).SpecialFolders.Item('Desktop') } catch { Show-Err $_ }
    $regDesk = ''
    try { $regDesk = [Environment]::ExpandEnvironmentVariables([string](Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders' -Name Desktop -ErrorAction Stop).Desktop) } catch { Show-Err $_ }
    $folders = [ordered]@{
        'Desktop (Windows)'     = [Environment]::GetFolderPath('Desktop')
        'Desktop (shell)'       = $shellDesk
        'Desktop (registry)'    = $regDesk
        'Public desktop'        = [Environment]::GetFolderPath('CommonDesktopDirectory')
        'Start menu programs'   = [Environment]::GetFolderPath('Programs')
    }
    foreach ($k in $folders.Keys) {
        $v = $folders[$k]
        $there = $false
        if ($v) { $there = Test-Path -LiteralPath $v }
        Say ('  {0,-22} {1}  (exists: {2})' -f $k, $v, $there)
    }
    foreach ($k in 'Desktop (Windows)', 'Start menu programs') {
        $d = $folders[$k]
        if (-not $d) { continue }
        if ($k -eq 'Start menu programs') { $d = Join-Path $d 'Koha' }
        if ($d) { Say ('  Koha.lnk in {0}: {1}' -f $d, (Test-Path -LiteralPath (Join-Path $d 'Koha.lnk'))) }
    }

    Head 'Writing a test shortcut on the desktop (WScript.Shell), then removing it'
    $desk = $folders['Desktop (Windows)']
    if ($desk) {
        $test = Join-Path $desk 'Koha test.lnk'
        try {
            $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($test)
            $lnk.TargetPath = Join-Path $env:SystemRoot 'explorer.exe'
            $lnk.Save()
            Say ('  written: {0}' -f (Test-Path -LiteralPath $test)) 'Green'
            Remove-Item -LiteralPath $test -Force -ErrorAction SilentlyContinue
        } catch { Show-Err $_ }
    }

    Head 'Loading Koha''s tools'
    $loaded = $false
    try {
        Import-Module (Join-Path $bin 'KohaEasy.Lang.psm1') -Force -ErrorAction Stop
        Import-Module (Join-Path $bin 'KohaEasy.Core.psm1') -Force -ErrorAction Stop
        Import-KeiLanguage -LangDir (Join-Path $bin 'lang')
        $loaded = $true
        Say ('  loaded, version {0}' -f $KohaEasyVersion) 'Green'
    } catch { Show-Err $_ }

    if ($loaded) {
        Head 'Creating the Koha shortcuts (the installer''s own step)'
        try {
            $d = Get-KohaDesktopPath
            Say ('  desktop chosen: {0}' -f $d)
            $made = @(New-KohaShortcuts -Desktop $d)
            Say ('  created: {0}' -f $made.Count) 'Green'
            foreach ($m in $made) { Say ('    ' + $m) }
            foreach ($e in @(Get-KohaShortcutErrors)) { Say ('  not created: ' + $e) 'Red' }
        } catch { Show-Err $_ }

        Head 'Sign-in entry and scheduled tasks'
        try {
            $run = (Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'KohaEasyTray' -ErrorAction SilentlyContinue).KohaEasyTray
            Say ('  Run entry KohaEasyTray: {0}' -f $(if ($run) { $run } else { '(missing)' }))
            if (-not $run) {
                Set-KohaTrayAtSignIn -Enabled $true
                $run = (Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'KohaEasyTray' -ErrorAction SilentlyContinue).KohaEasyTray
                if ($run) { Say '  Run entry written again' 'Green' } else { Say '  Run entry could not be written (see the error above)' 'Red' }
            }
        } catch { Show-Err $_ }
        try {
            $tasks = @(Get-ScheduledTask -TaskPath '\' -ErrorAction Stop | Where-Object { $_.TaskName -like 'Koha - *' }) + @(Get-ScheduledTask -TaskPath '\KohaEasy\' -ErrorAction SilentlyContinue)
            if ($tasks.Count -eq 0) { throw 'none' }
            foreach ($t in $tasks) { Say ('  task {0}: {1} | {2} {3}' -f $t.TaskName, $t.State, @($t.Actions)[0].Execute, @($t.Actions)[0].Arguments) }
        } catch { Say '  no KohaEasy tasks' 'Yellow' }

        Head 'Starting the tray the way Windows does, and checking it stays up'
        try {
            $l = Get-KohaHiddenLaunch -Arguments 'Tray'
            Say ('  hidden launch: {0} {1}' -f $l.Target, $l.Arguments)
            if (Test-KohaTrayRunning) {
                Say '  the tray is already running' 'Green'
            } else {
                Set-KohaState @{ trayClosed = $false } | Out-Null
                Start-Process -FilePath $l.Target -ArgumentList $l.Arguments | Out-Null
                Start-Sleep -Seconds 10
                if (Test-KohaTrayRunning) {
                    Say '  the tray started and is still running after 10 s' 'Green'
                } else {
                    Say '  the tray is not running 10 s after the hidden launch. Starting it once more in a window of its own, where its error stays on screen:' 'Red'
                    $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
                    $arg = '-NoExit -NoProfile -ExecutionPolicy Bypass -File "{0}" Tray -Hidden' -f (Join-Path $bin 'KohaEasy.ps1')
                    $p = Start-Process -FilePath $ps -ArgumentList $arg -PassThru
                    Start-Sleep -Seconds 10
                    Say ('  that window''s PowerShell is {0}; if an error shows there, copy it (right-click the title bar, Edit, Select All).' -f $(if ($p.HasExited) { 'already closed' } else { 'running, process ' + $p.Id })) 'Yellow'
                }
            }
        } catch { Show-Err $_ }
    }

    try { Stop-Transcript | Out-Null } catch { }
    Write-Host ''
    Write-Host ('Saved: ' + $out) -ForegroundColor Green
    Write-Host 'Send this file (it has no passwords).' -ForegroundColor Green
}

Invoke-KohaEasyDiagnose
