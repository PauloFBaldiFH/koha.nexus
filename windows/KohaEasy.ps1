<#
.SYNOPSIS
    koha.nexus for Windows: shortcuts, scheduled tasks and tray.
.DESCRIPTION
    KohaEasy.ps1 Start [-Trigger user|logon]   Koha - Start shortcut, tray, sign-in task
    KohaEasy.ps1 Stop [-Force]                 Koha - Stop shortcut, tray
    KohaEasy.ps1 Restart [-Force]              Koha - Restart shortcut, tray
    KohaEasy.ps1 SafeShutdown                  Koha - Shut down the PC safely (Start menu, tray): stops Koha step by step with progress, then shuts down or restarts Windows
    KohaEasy.ps1 Launch                        the Koha icon (desktop, Start menu): starts the tray and Koha when they are not running, puts back a deleted sign-in entry or task, then the control panel
    KohaEasy.ps1 Window                        the same as Panel (the shortcut of the old Koha status window)
    KohaEasy.ps1 Status                        the same summary in a message box
    KohaEasy.ps1 RestartServices               restart Koha's services inside Debian, without restarting WSL (tray)
    KohaEasy.ps1 Panel                         Open Dashboard (tray, double-click): starts Koha, opens the control panel
    KohaEasy.ps1 Panel -Action <name>          the same, straight on one routine (installer --run <name>)
    KohaEasy.ps1 Terminal                      the tray (Open Debian terminal): a Debian shell as the Debian user (advanced), while Debian runs
    KohaEasy.ps1 UserFolder                    the tray: the Debian user's home folder in Windows Explorer
    KohaEasy.ps1 RebuildIndex                  the tray: rebuilds the search index, with notifications
    KohaEasy.ps1 Open                          starts Koha if needed, opens the staff interface
    KohaEasy.ps1 Run                           action of the "Keep Koha running" task
    KohaEasy.ps1 Tray                          notification-area icon (starts at sign-in)
    KohaEasy.ps1 Watcher                       shutdown watcher (starts at sign-in, no window): Koha's clean stop when Windows shuts down, restarts or signs out
    KohaEasy.ps1 EnableShutdownWatcher         registers the watcher at sign-in (HKCU Run) and starts it; the installer does this on every run
    KohaEasy.ps1 DisableShutdownWatcher        removes the watcher's sign-in entry and ends it; the tray then does the stop
    KohaEasy.ps1 ExportReport                  diagnostico_koha.txt for support on the desktop
    KohaEasy.ps1 ExportDiagnostics             .zip for support on the desktop
    KohaEasy.ps1 CheckDisk                     free space around the virtual disk
    KohaEasy.ps1 CompactDisk                   give unused space back to Windows (admin)
    KohaEasy.ps1 SetAutostart -Mode logon|manual
    KohaEasy.ps1 RegisterTasks [-Mode logon|manual]   koha.nexus.exe, tasks, tray and shutdown watcher at sign-in, and shortcuts
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
    [ValidateSet('Launch', 'Window', 'Panel', 'Terminal', 'UserFolder', 'Open', 'Start', 'Stop', 'Restart', 'SafeShutdown', 'RestartServices', 'RebuildIndex', 'Status', 'Run', 'Tray', 'Watcher', 'EnableShutdownWatcher', 'DisableShutdownWatcher', 'ExportReport', 'ExportDiagnostics', 'CheckDisk', 'CompactDisk', 'SetAutostart', 'RegisterTasks', 'CreateShortcuts', 'SetupNetwork', 'UpdatePortProxy', 'Install', 'Uninstall', 'UninstallAdmin')]
    [string]$Command = 'Status',
    [ValidateSet('user', 'logon')][string]$Trigger = 'user',
    [ValidateSet('logon', 'manual')][string]$Mode,
    [switch]$Force,
    [switch]$Quiet,
    [switch]$Pause,
    # Painel de Gestão: rotina de execução direta
    [ValidatePattern('^[a-z][a-z0-9-]*$')][string]$Action,
    [switch]$Hidden
)

$ErrorActionPreference = 'Stop'

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
    if (@('Launch', 'Window', 'Tray', 'Panel', 'Terminal', 'UserFolder', 'SafeShutdown') -contains $Command -and -not $Quiet) {
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
        if ($env:KOHA_MSIX_PANEL_SETUP -eq '1') {
            # The first terminal called koha.nexus.exe Launch -Hidden after
            # preparing the Debian environment. Open exactly one panel window.
            # The wrapper retains the post-panel Windows setup after Exit.
            $wrapper = Join-Path $PSScriptRoot 'KohaMsixPanel.ps1'
            if (-not (Test-Path -LiteralPath $wrapper -PathType Leaf)) {
                throw ('Koha MSIX panel wrapper not found: ' + $wrapper)
            }
            $powerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
            $quotedWrapper = '"' + $wrapper + '"'
            $psArguments = '-NoProfile -ExecutionPolicy Bypass -NoExit -File {0} -Distro "{1}" -LinuxDir "/root/koha-easy-installer" -WindowScript "{2}"' -f $quotedWrapper, $cfg.Distro, $cfg.WindowPath
            $wt = Get-Command 'wt.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($wt) {
                Start-Process -FilePath $wt.Source -ArgumentList ('-w new --title "Koha.Nexus" powershell.exe ' + $psArguments) -ErrorAction Stop | Out-Null
            } else {
                Start-Process -FilePath $powerShellExe -ArgumentList $psArguments -ErrorAction Stop | Out-Null
            }
            break
        }
        Invoke-KohaLaunch | Out-Null
        Open-KohaPanel
    }
    'Window' {
        if (-not (Test-KohaDistroInstalled)) { Show-Box (Get-KohaStateText 'not_installed') 'OK' 'Warning' | Out-Null; break }
        Open-KohaPanel
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
        if (-not (Test-KohaDistroRunning)) { Show-Box (T 'Debian is stopped. Start Koha first.') 'OK' 'Warning' | Out-Null; break }
        Open-KohaDebianTerminal
    }
    'UserFolder' {
        if (-not (Test-KohaDistroInstalled)) { Show-Box (Get-KohaStateText 'not_installed') 'OK' 'Warning' | Out-Null; break }
        if (-not (Open-KohaUserFolder)) { Show-Box (T 'The Debian user folder could not be found. Open the control panel and try again.') 'OK' 'Warning' | Out-Null }
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
    'Watcher' { & (Join-Path $PSScriptRoot 'KohaEasy.Watcher.ps1') }
    'EnableShutdownWatcher' {
        Set-KohaState @{ shutdownWatcher = 'on' } | Out-Null
        Install-KohaShutdownWatcher -Restart | Out-Null
        if (-not $Quiet) { (T 'The shutdown watcher is on: when Windows shuts down, restarts or signs out, Koha is stopped cleanly first.') }
        exit 0
    }
    'DisableShutdownWatcher' {
        Uninstall-KohaShutdownWatcher
        if (-not $Quiet) { (T 'The shutdown watcher is off. The Koha icon still stops Koha cleanly while it runs.') }
        exit 0
    }
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
        $linux =$null
        if (Test-KohaDistroRunning) { $linux = Get-KohaLinuxStatus }
        $d = Get-KohaDiskHealth -Linux $linux
        $text = (T 'Free on drive {0}: {1}. Koha virtual disk: {2}.') -f $d.Drive, (Format-KohaSize $d.HostFree), (Format-KohaSize $d.VhdxSize)
        if ($d.Message) {$text += "`n`n" + $d.Message }
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
        exit 0
    }
    'RegisterTasks' {
        Install-KohaLauncher | Out-Null
        if ($Mode) { Register-KohaTasks -Autostart $Mode } else { Register-KohaTasks }
        Set-KohaTrayAtSignIn -Enabled $true
        if (Test-KohaWatcherWanted) { Set-KohaWatcherAtSignIn -Enabled $true }
        New-KohaShortcuts | Out-Null
        Set-KohaDistroIcon | Out-Null
        exit 0
    }
    'CreateShortcuts' { 
        New-KohaShortcuts | Out-Null
        Set-KohaDistroIcon | Out-Null 
        exit 0
    }
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
        if (-not $Force -and -not $Quiet) {
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
        Set-KohaConsoleFont | Out-Null
        Set-KohaConsoleDefaults | Out-Null
        try {
            $code = [int](@(Install-Koha) | Select-Object -Last 1)
        } catch {
            Write-KohaStep $_.Exception.Message 'error'
            Write-Host (T 'Run the installer again to continue from this step. The log is in C:\KohaEasy\logs.') -ForegroundColor Red
            $code = 1
        }
        # 75: the install went on in a new window; this one closes at once.
        if ($Pause -and -not $Quiet -and $code -ne 75) {
            Write-Host ''
            try { Read-Host (T 'Press Enter to close this window.') | Out-Null } catch { }
        }
        exit $code
    }
}
