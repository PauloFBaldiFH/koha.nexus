<#
.SYNOPSIS
    Koha Easy Installer for Windows: shortcuts, scheduled tasks and tray.
.DESCRIPTION
    KohaEasy.ps1 Start [-Trigger user|logon]   Koha - Start shortcut, tray, sign-in task
    KohaEasy.ps1 Stop [-Force]                 Koha - Stop shortcut, tray
    KohaEasy.ps1 Restart [-Force]              Koha - Restart shortcut, tray
    KohaEasy.ps1 SafeShutdown                  Koha - Shut down the PC safely (Start menu, tray, Koha window): stops Koha step by step with progress, then shuts down or restarts Windows
    KohaEasy.ps1 Launch                        the Koha icon (desktop, Start menu): starts the tray and Koha when they are not running, puts back a deleted sign-in entry or task, then the Koha window (or brings it to the front)
    KohaEasy.ps1 Window                        the Koha window: banner, quick access, components, actions (Koha - Status, tray)
    KohaEasy.ps1 Status                        the same summary in a message box
    KohaEasy.ps1 RestartServices               restart Koha's services inside Debian, without restarting WSL (tray)
    KohaEasy.ps1 Panel                         the Koha window and the tray: starts Koha, opens the control panel
    KohaEasy.ps1 Panel -Action <name>          the Koha window's Painel de Gestão: the same, straight on one routine (installer --run <name>)
    KohaEasy.ps1 Terminal                      the Koha window: a Debian shell as the Debian user (advanced), while Debian runs
    KohaEasy.ps1 RebuildIndex                  the tray: rebuilds the search index, with notifications
    KohaEasy.ps1 Open                          starts Koha if needed, opens the staff interface
    KohaEasy.ps1 Run                           action of the "Keep Koha running" task
    KohaEasy.ps1 Tray                          notification-area icon (starts at sign-in)
    KohaEasy.ps1 ExportReport                  diagnostico_koha.txt for support on the desktop
    KohaEasy.ps1 ExportDiagnostics             .zip for support on the desktop
    KohaEasy.ps1 CheckDisk                     free space around the virtual disk
    KohaEasy.ps1 CompactDisk                   give unused space back to Windows (admin)
    KohaEasy.ps1 SetAutostart -Mode logon|manual
    KohaEasy.ps1 RegisterTasks [-Mode logon|manual]   KohaEasy.exe, tasks, tray at sign-in and shortcuts
    KohaEasy.ps1 Install                       the whole installation (windows\install.ps1 starts it)
    KohaEasy.ps1 CreateShortcuts               Start menu "Koha" and desktop, with koha.ico
    KohaEasy.ps1 SetupNetwork                  firewall and port forwarding for the library network (admin)
    KohaEasy.ps1 UpdatePortProxy               action of the "Koha network" task (NAT networking)
    KohaEasy.ps1 Uninstall [-Force]            removes Koha from this PC (Uninstall-Koha.cmd, Settings > Apps); -Force asks nothing and keeps the backups
    KohaEasy.ps1 UninstallAdmin                the part of Uninstall that needs administrator rights (firewall, port forwarding, tasks)
    -Quiet: no dialog boxes (scheduled tasks).
    -Pause: Install waits for Enter before its window closes (Windows Terminal).
    -Hidden: started with no console (every shortcut, task and tray launch).
    Windows PowerShell 5.1.
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('Launch', 'Window', 'Panel', 'Terminal', 'Open', 'Start', 'Stop', 'Restart', 'SafeShutdown', 'RestartServices', 'RebuildIndex', 'Status', 'Run', 'Tray', 'ExportReport', 'ExportDiagnostics', 'CheckDisk', 'CompactDisk', 'SetAutostart', 'RegisterTasks', 'CreateShortcuts', 'SetupNetwork', 'UpdatePortProxy', 'Install', 'Uninstall', 'UninstallAdmin')]
    [string]$Command = 'Status',
    [ValidateSet('user', 'logon')][string]$Trigger = 'user',
    [ValidateSet('logon', 'manual')][string]$Mode,
    [switch]$Force,
    [switch]$Quiet,
    [switch]$Pause,
    # Panel: open the terminal straight on one routine of the panel
    # (installer --run <action>), as the Koha window's Painel de Gestão does.
    [ValidatePattern('^[a-z][a-z0-9-]*$')][string]$Action,
    # Set by every hidden launch (Get-KohaHiddenLaunch); see below.
    [switch]$Hidden
)

$ErrorActionPreference = 'Stop'

# Anything that ends this script with an error goes into the Koha log with
# its stack ("<Command> failed: ..."), and a window, the tray or the Koha
# icon shows it in a message: started hidden, they have no console to show
# it in, and the installer reads it back when the tray does not come up.
trap {
    $failure = '{0} failed: {1} | stack: {2}' -f $Command, $_.Exception.Message, ([string]$_.ScriptStackTrace -replace "`r?`n", ' <- ')
    $logDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'logs'
    if ($env:KOHAEASY_ROOT) { $logDir = Join-Path $env:KOHAEASY_ROOT 'logs' }
    try { Write-KohaLog $failure } catch {
        try {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
            Add-Content -LiteralPath (Join-Path $logDir ('koha-{0}.log' -f (Get-Date -Format 'yyyyMMdd'))) -Value ('{0} | {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $failure)
        } catch { }
    }
    if (@('Launch', 'Window', 'Tray', 'Panel', 'Terminal', 'SafeShutdown') -contains $Command -and -not $Quiet) {
        try {
            Add-Type -AssemblyName System.Windows.Forms
            [void][System.Windows.Forms.MessageBox]::Show(('Koha: {0}{1}{1}{2}' -f $_.Exception.Message, [Environment]::NewLine, $logDir), 'Koha', 'OK', 'Error')
        } catch { }
    }
    break
}
Import-Module (Join-Path $PSScriptRoot 'KohaEasy.Lang.psm1') -Force
Import-Module (Join-Path $PSScriptRoot 'KohaEasy.Core.psm1') -Force
$langDir = Join-Path $PSScriptRoot 'lang'
if (-not (Test-Path -LiteralPath $langDir)) { $langDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'lang' }
Import-KeiLanguage -LangDir $langDir
Set-KohaUtf8Console
$cfg = Get-KohaConfig
if ($Trigger -eq 'logon') { $Quiet = $true }

# Started with a console someone can see (a shortcut, sign-in entry or task
# of an earlier version, or powershell.exe itself, which Windows Terminal
# keeps as an empty window): start again the hidden way and end here, so
# that console closes at once.
if (Test-KohaRelaunchHidden -Command $Command -Hidden $Hidden.IsPresent) {
    Write-KohaLog ('{0}: started with a console, starting again with none' -f $Command)
    Start-KohaHidden (Get-KohaRelaunchArguments -Command $Command -Bound $PSBoundParameters)
    return
}

function Show-Box {
    param([string]$Text, [string]$Buttons = 'OK', [string]$Icon = 'Information')
    if ($Quiet) { return 'None' }
    Add-Type -AssemblyName System.Windows.Forms
    return [string][System.Windows.Forms.MessageBox]::Show($Text, (Get-KohaAppTitle), $Buttons, $Icon)
}

function Confirm-Stop {
    param([string]$Question)
    if ($Force -or $Quiet) { return $true }
    return ((Show-Box ($Question + "`n`n" + (T 'Anyone using the catalog will be disconnected, and nightly backups will not run until Koha is started again.')) 'YesNo' 'Warning') -eq 'Yes')
}

function Invoke-Start {
    $r = Start-Koha -Trigger $Trigger -Wait:(-not $Quiet)
    if ($Quiet) { return }
    if ($r -eq 'ready') {
        if ((Show-Box (T 'Koha is running. Open the staff interface now?') 'YesNo') -eq 'Yes') { Start-Process $cfg.StaffUrl }
    } elseif ($r -eq 'timeout') {
        Show-Box (T 'Koha did not start. Open Koha - Status, or export the diagnostics from the tray menu.') 'OK' 'Error' | Out-Null
    }
}

switch ($Command) {
    'Launch' {
        if (-not (Test-KohaDistroInstalled)) { Show-Box (Get-KohaStateText 'not_installed') 'OK' 'Warning' | Out-Null; break }
        Invoke-KohaLaunch | Out-Null
        & (Join-Path $PSScriptRoot 'KohaEasy.Window.ps1')
    }
    'Window' {
        if (-not (Test-KohaDistroInstalled)) { Show-Box (Get-KohaStateText 'not_installed') 'OK' 'Warning' | Out-Null; break }
        & (Join-Path $PSScriptRoot 'KohaEasy.Window.ps1')
    }
    'RestartServices' {
        if (-not $Quiet) { Show-KohaNotification -Title 'Koha' -Text (T 'Restarting Koha services...') | Out-Null }
        $r = Restart-KohaServices -NoWait:$Quiet
        if (-not $Quiet) {
            switch ($r) {
                'ready'       { Show-KohaNotification -Title 'Koha' -Text (T 'Koha services restarted.') | Out-Null }
                'not_running' { Show-Box (T 'Debian is stopped. Start Koha first.') 'OK' 'Warning' | Out-Null }
                default       { Show-Box (T 'Koha services restarted, but the staff interface does not answer yet. Export the diagnostics and send them to whoever supports your library.') 'OK' 'Warning' | Out-Null }
            }
        }
        if (@('ready', 'restarted') -notcontains $r) { exit 1 }
    }
    'ExportReport' {
        $file = Export-KohaDiagnosticsText
        if (-not $Quiet) {
            Start-Process explorer.exe -ArgumentList ('/select,"{0}"' -f $file)
            Show-Box (((T 'Diagnostics saved on the desktop: {0}') -f $file) + "`n`n" + (T 'Send this file to whoever supports your library. Passwords are not included.')) | Out-Null
        } else {
            $file
        }
    }
    'Panel' {
        if (-not (Test-KohaDistroInstalled)) { Show-Box (Get-KohaStateText 'not_installed') 'OK' 'Warning' | Out-Null; break }
        Open-KohaPanel -Action $Action
    }
    'Terminal' {
        # Never starts Debian: WSL would end it abruptly after the shell.
        if (-not (Test-KohaDistroRunning)) { Show-Box (T 'Debian is stopped. Start Koha first.') 'OK' 'Warning' | Out-Null; break }
        Open-KohaDebianTerminal
    }
    'RebuildIndex' {
        if (-not $Quiet) { Show-KohaNotification -Title 'Koha' -Text (T 'Rebuilding the search index... On large catalogs this takes several minutes.') | Out-Null }
        $r = Invoke-KohaSearchReindex
        if (-not $Quiet) {
            switch ($r) {
                'rebuilt'     { Show-KohaNotification -Title 'Koha' -Text (T 'The search index was rebuilt.') | Out-Null }
                'not_running' { Show-Box (T 'Debian is stopped. Start Koha first.') 'OK' 'Warning' | Out-Null }
                default       { Show-KohaNotification -Title 'Koha' -Text (T 'Rebuilding the search index failed. Export the diagnostics and send them to whoever supports your library.') -Level error | Out-Null }
            }
        }
        if ($r -ne 'rebuilt') { exit 1 }
    }
    'Start' {
        if (-not $Quiet) { Show-KohaNotification -Title 'Koha' -Text (T 'Starting Koha... (up to 3 minutes)') | Out-Null }
        Invoke-Start
    }
    'Open' {
        $s = Get-KohaStatus
        if ($s.State -eq 'not_installed') { Show-Box (Get-KohaStateText $s.State) 'OK' 'Warning' | Out-Null; break }
        if ($s.State -ne 'running') {
            Show-KohaNotification -Title 'Koha' -Text (T 'Starting Koha... (up to 3 minutes)') | Out-Null
            if ((Start-Koha -Trigger user -Wait) -ne 'ready') {
                Show-Box (T 'Koha did not start. Open Koha - Status, or export the diagnostics from the tray menu.') 'OK' 'Error' | Out-Null
                break
            }
        }
        Start-Process $cfg.StaffUrl
    }
    'Stop' {
        if (Confirm-Stop (T 'Stop Koha?')) {
            Stop-Koha | Out-Null
            Show-Box (T 'Koha is stopped. Use Koha - Start to turn it on again.') | Out-Null
        }
    }
    'SafeShutdown' { & (Join-Path $PSScriptRoot 'KohaEasy.Shutdown.ps1') }
    'Restart' {
        if (Confirm-Stop (T 'Restart Koha?')) {
            Stop-Koha | Out-Null
            Invoke-Start
        }
    }
    'Status' {
        $s = Get-KohaStatus
        $lines = @(Get-KohaStateText $s.State)
        if ($s.Autostart -eq 'manual') { $lines += T 'Koha starts only when you click Koha - Start.' }
        if ($null -ne $s.Linux) {
            if ([int64]$s.Linux.backup.last_epoch -gt 0) {
                $when = [DateTimeOffset]::FromUnixTimeSeconds([int64]$s.Linux.backup.last_epoch).LocalDateTime
                $lines += (T 'Latest backup: {0} ({1})') -f $when.ToString('g'), (Format-KohaSize ([double]$s.Linux.backup.last_size))
            } else {
                $lines += T 'Latest backup: none yet'
            }
        }
        $disk = Get-KohaDiskHealth -Linux $s.Linux
        if ($disk.Message) { $lines += $disk.Message }
        if ($s.State -eq 'not_responding') {
            if ((Show-Box (($lines -join "`n`n") + "`n`n" + (T 'Restart Koha now?')) 'YesNo' 'Warning') -eq 'Yes') {
                Stop-Koha | Out-Null
                Invoke-Start
            }
        } else {
            Show-Box ($lines -join "`n`n") | Out-Null
        }
    }
    'Run' { exit (Invoke-KohaRun) }
    'Tray' { & (Join-Path $PSScriptRoot 'KohaEasy.Tray.ps1') }
    'ExportDiagnostics' {
        if (-not $Quiet) { Show-KohaNotification -Title 'Koha' -Text (T 'Collecting diagnostics... This can take a minute.') | Out-Null }
        $zip = Export-KohaDiagnostics
        if (-not $Quiet) {
            Show-Box ((T 'Diagnostics saved on the desktop:') + "`n$zip`n`n" + (T 'Send this file to whoever supports your library. Passwords are not included.')) | Out-Null
            Start-Process explorer.exe -ArgumentList ('/select,"{0}"' -f $zip)
        } else {
            $zip
        }
    }
    'CheckDisk' {
        $linux = $null
        if (Test-KohaDistroRunning) { $linux = Get-KohaLinuxStatus }
        $d = Get-KohaDiskHealth -Linux $linux
        $text = (T 'Free on drive {0}: {1}. Koha virtual disk: {2}.') -f $d.Drive, (Format-KohaSize $d.HostFree), (Format-KohaSize $d.VhdxSize)
        if ($d.Message) { $text += "`n`n" + $d.Message }
        if ($Quiet) { $d; break }
        if ($d.Reclaimable -gt 10GB) {
            $q = $text + "`n`n" + ((T 'About {0} can be given back to Windows. Compact the disk now? Koha stops for a few minutes and Windows asks for administrator rights.') -f (Format-KohaSize $d.Reclaimable))
            if ((Show-Box $q 'YesNo') -eq 'Yes') {
                $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
                Start-Process $ps -Verb RunAs -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "{0}" CompactDisk -Force' -f $PSCommandPath)
            }
        } else {
            Show-Box $text | Out-Null
        }
    }
    'CompactDisk' {
        if (-not $Force) {
            if ((Show-Box (T 'Compact the Koha disk? Koha and any other Linux (WSL) window stop for a few minutes.') 'YesNo' 'Warning') -ne 'Yes') { break }
        }
        $r = Invoke-KohaDiskCompact
        Show-Box ((T 'Done. {0} given back to Windows.') -f (Format-KohaSize $r.Freed)) | Out-Null
    }
    'SetAutostart' {
        if (-not $Mode) { throw 'SetAutostart needs -Mode logon or -Mode manual' }
        Set-KohaAutostart -Mode $Mode | Out-Null
        if ($Mode -eq 'manual' -and (Test-KohaDistroRunning) -and -not $Quiet) {
            if ((Show-Box (T 'Koha will no longer start when you sign in to Windows. It is still running now: stop it now?') 'YesNo') -eq 'Yes') {
                Stop-Koha | Out-Null
            }
        }
    }
    'RegisterTasks' {
        Install-KohaLauncher | Out-Null
        if ($Mode) { Register-KohaTasks -Autostart $Mode } else { Register-KohaTasks }
        Set-KohaTrayAtSignIn -Enabled $true
        New-KohaShortcuts | Out-Null
        Set-KohaDistroIcon | Out-Null
    }
    'CreateShortcuts' { New-KohaShortcuts; Set-KohaDistroIcon | Out-Null }
    'SetupNetwork' {
        try {
            Set-KohaLanAccess | Out-Null
            exit 0
        } catch {
            Write-KohaLog ('network setup failed: ' + $_.Exception.Message) 'network'
            exit 1
        }
    }
    'UpdatePortProxy' {
        if ((Update-KohaPortProxy) -eq 'failed') { exit 1 }
        exit 0
    }
    'Uninstall' {
        Import-Module (Join-Path $PSScriptRoot 'KohaEasy.Uninstall.psm1') -Force
        $code = [int](@(Uninstall-Koha -Yes:$Force) | Select-Object -Last 1)
        if (-not $Force) {
            Write-Host ''
            try { Read-Host (T 'Press Enter to close this window.') | Out-Null } catch { }
        }
        exit $code
    }
    'UninstallAdmin' {
        Import-Module (Join-Path $PSScriptRoot 'KohaEasy.Uninstall.psm1') -Force
        Remove-KohaAdminParts
        exit 0
    }
    'Install' {
        Import-Module (Join-Path $PSScriptRoot 'KohaEasy.Install.psm1') -Force
        try {
            # Only the last value is the result: anything else a step prints
            # must never turn the exit code into a list.
            $code = [int](@(Install-Koha) | Select-Object -Last 1)
        } catch {
            Write-KohaStep $_.Exception.Message 'error'
            Write-Host (T 'Run the installer again to continue from this step. The log is in C:\KohaEasy\logs.') -ForegroundColor Red
            $code = 1
        }
        if ($Pause) {
            Write-Host ''
            try { Read-Host (T 'Press Enter to close this window.') | Out-Null } catch { }
        }
        exit $code
    }
}
