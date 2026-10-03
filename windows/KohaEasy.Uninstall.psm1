# Koha Easy Installer for Windows: removes Koha from this PC.
# Started by Uninstall-Koha.cmd (in the Koha folder) or by Settings > Apps
# (the "Koha" entry) as "KohaEasy.ps1 Uninstall". It asks before anything is
# removed, then takes away what the installer made, in this order:
#   * the tray, the Koha window and the keep-alive task's PowerShell
#   * the Debian "koha" (its virtual disk, with the Koha databases)
#   * the scheduled tasks, the sign-in entries, the Settings > Apps entry
#   * the shortcuts (desktop, Start menu) and the Windows Terminal profile
#   * the firewall rule and port forwarding (one UAC prompt, when present)
#   * the Koha folder, except Backups unless the librarian asks for it too
# WSL itself and .wslconfig stay: other Linux distributions may use them.
# Windows PowerShell 5.1 compatible. UTF-8 with BOM.

Set-StrictMode -Version 2.0
Import-Module (Join-Path $PSScriptRoot 'KohaEasy.Lang.psm1')
Import-Module (Join-Path $PSScriptRoot 'KohaEasy.Core.psm1')

function Write-KohaUninstallStep {
    param([string]$Text, [ValidateSet('step', 'ok', 'warn', 'error')][string]$Kind = 'step')
    $color = @{ step = 'Cyan'; ok = 'Green'; warn = 'Yellow'; error = 'Red' }[$Kind]
    $mark = @{ step = '[>]'; ok = '[OK]'; warn = '[!]'; error = '[X]' }[$Kind]
    Write-Host ('{0} {1}' -f $mark, $Text) -ForegroundColor $color
}

# Pure: whether the typed answer confirms the removal (the word KOHA, in any
# case, so it reads the same in every language).
function Test-KohaUninstallAnswer {
    param([string]$Answer)
    return ([string]$Answer).Trim().ToUpperInvariant() -eq 'KOHA'
}

# Pure: a yes/no answer whose default (Enter) is no.
function Test-KohaYesAnswer {
    param([string]$Answer)
    $a = ([string]$Answer).Trim().ToLowerInvariant()
    return ($a.StartsWith('y') -or $a.StartsWith('s') -or $a.StartsWith('o') -or $a.StartsWith('j'))
}

# Every process of the Windows side but this one and the one that started
# it: the tray, the Koha window, the keep-alive task, KohaEasy.exe.
function Stop-KohaWindowsSide {
    Stop-KohaKeepAlive
    $keep = @($PID)
    try { $keep += [int](Get-CimInstance Win32_Process -Filter ('ProcessId = {0}' -f $PID) -ErrorAction Stop).ParentProcessId } catch { }
    try {
        Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object { $keep -notcontains [int]$_.ProcessId -and ($_.Name -eq 'KohaEasy.exe' -or ([string]$_.CommandLine) -match 'KohaEasy\.(ps1|Tray\.ps1|Window\.ps1|Hidden\.js)') } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch { }
}

# What needs administrator rights: the firewall rules, the port forwarding,
# the "Koha network" task (made with the highest rights) and any task an
# earlier install made as administrator. "KohaEasy.ps1 UninstallAdmin" runs
# it, elevated.
function Test-KohaUninstallNeedsAdmin {
    $cfg = Get-KohaConfig
    if (@(Get-ScheduledTask -TaskPath $cfg.TaskPath -ErrorAction SilentlyContinue).Count -gt 0) { return $true }
    if (@(Get-NetFirewallRule -DisplayName $cfg.FirewallRule -ErrorAction SilentlyContinue).Count -gt 0) { return $true }
    try {
        if (@(Get-KohaPortProxyRules | Where-Object { $_.ListenAddress -eq '0.0.0.0' -and ($cfg.WebPorts -contains $_.ListenPort) }).Count -gt 0) { return $true }
    } catch { }
    return $false
}

function Remove-KohaAdminParts {
    $cfg = Get-KohaConfig
    Get-NetFirewallRule -DisplayName $cfg.FirewallRule -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    if (Get-Command Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue) {
        try { Get-NetFirewallHyperVRule -Name 'KohaWeb' -ErrorAction SilentlyContinue | Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue } catch { }
    }
    try { Remove-KohaPortProxy | Out-Null } catch { }
    Remove-KohaTasks
}

function Remove-KohaTasks {
    $cfg = Get-KohaConfig
    foreach ($t in @(Get-ScheduledTask -TaskPath $cfg.TaskPath -ErrorAction SilentlyContinue)) {
        try { Unregister-ScheduledTask -TaskPath $cfg.TaskPath -TaskName $t.TaskName -Confirm:$false -ErrorAction Stop } catch { }
    }
    # The empty task folder too.
    try {
        $svc = New-Object -ComObject 'Schedule.Service'
        $svc.Connect()
        $svc.GetFolder('\').DeleteFolder($cfg.TaskPath.Trim('\'), 0)
    } catch { }
}

function Remove-KohaShortcutFiles {
    $menu = [System.IO.Path]::Combine([Environment]::GetFolderPath('Programs'), 'Koha')
    if (Test-Path -LiteralPath $menu) { Remove-Item -LiteralPath $menu -Recurse -Force -ErrorAction SilentlyContinue }
    $names = @('Koha.lnk', ((ConvertTo-KohaFileName 'Koha - Staff interface') + '.url'), ((ConvertTo-KohaFileName 'Koha - Public catalog') + '.url'),
        ((ConvertTo-KohaFileName (T 'Koha - Staff interface')) + '.url'), ((ConvertTo-KohaFileName (T 'Koha - Public catalog')) + '.url'))
    foreach ($d in @((Get-KohaDesktopPath), [Environment]::GetFolderPath('CommonDesktopDirectory'))) {
        if (-not $d) { continue }
        foreach ($n in $names) {
            $f = [System.IO.Path]::Combine($d, $n)
            if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue }
        }
    }
    $frag = [System.IO.Path]::Combine([string]$env:LOCALAPPDATA, 'Microsoft', 'Windows Terminal', 'Fragments', 'KohaEasy')
    if (Test-Path -LiteralPath $frag) { Remove-Item -LiteralPath $frag -Recurse -Force -ErrorAction SilentlyContinue }
}

function Remove-KohaRegistryEntries {
    param([bool]$AppsEntry = $true)
    Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'KohaEasyTray' -ErrorAction SilentlyContinue
    Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' -Name 'KohaEasyInstall' -ErrorAction SilentlyContinue
    if ($AppsEntry) { Remove-Item -Path (Get-KohaUninstallKey) -Recurse -Force -ErrorAction SilentlyContinue }
}

# The Koha folder: everything but Backups when it is kept. The folder itself
# goes a few seconds later, once this window (whose current folder it may
# be) has closed.
function Remove-KohaFolder {
    param([bool]$KeepBackups = $true)
    $root = Get-KohaPath Root
    if (-not (Test-Path -LiteralPath $root)) { return $true }
    # Only a folder the installer made: never a drive or any other folder a
    # wrong KOHAEASY_ROOT could name.
    $full = [System.IO.Path]::GetFullPath($root).TrimEnd('\')
    $isKoha = (Test-Path -LiteralPath ([System.IO.Path]::Combine($full, 'bin', 'KohaEasy.ps1'))) -or (Test-Path -LiteralPath ([System.IO.Path]::Combine($full, 'state.json')))
    if (-not $isKoha -or $full -match '^[A-Za-z]:$' -or ($env:SystemRoot -and $full -eq [System.IO.Path]::GetFullPath([string]$env:SystemRoot).TrimEnd('\'))) {
        Write-KohaLog ('uninstall: {0} left as it is (not a Koha folder)' -f $root) 'install'
        return $false
    }
    Set-Location -LiteralPath $env:TEMP
    [Environment]::CurrentDirectory = $env:TEMP
    $left = @()
    foreach ($item in @(Get-ChildItem -LiteralPath $root -Force -ErrorAction SilentlyContinue)) {
        if ($KeepBackups -and $item.Name -eq 'Backups') { continue }
        try { Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction Stop } catch { $left += $item.FullName }
    }
    $cmd = Join-Path $env:SystemRoot 'System32\cmd.exe'
    try {
        Start-Process -FilePath $cmd -ArgumentList ('/d /c ping -n 4 127.0.0.1 >nul & rd "{0}"' -f $root) -WindowStyle Hidden -WorkingDirectory $env:TEMP | Out-Null
    } catch { }
    return ($left.Count -eq 0)
}

function Uninstall-Koha {
    param([switch]$Yes, [switch]$DeleteBackups)
    $cfg = Get-KohaConfig
    $root = Get-KohaPath Root
    $backups = Get-KohaPath Backups
    $deleteAll = $DeleteBackups.IsPresent
    Write-Host ''
    Write-Host (Get-KohaAppTitle) -ForegroundColor Green
    Write-Host ''
    Write-Host (T 'This removes Koha from this PC: the Debian "koha" with the Koha databases and everything in it, the shortcuts, the status icon, the scheduled tasks and the Koha folder.') -ForegroundColor Yellow
    $hasBackups = (Test-Path -LiteralPath $backups) -and @(Get-ChildItem -LiteralPath $backups -Force -ErrorAction SilentlyContinue).Count -gt 0
    if ($hasBackups) { Write-Host ((T 'The backups in {0} are kept unless you choose to delete them too.') -f $backups) -ForegroundColor Yellow }
    Write-Host ''
    if (-not $Yes) {
        if (-not (Test-KohaUninstallAnswer (Read-Host (T 'Type KOHA to remove Koha, or press Enter to cancel')))) {
            Write-KohaUninstallStep (T 'Nothing was removed.') 'ok'
            return 2
        }
        if ($hasBackups) { $deleteAll = Test-KohaYesAnswer (Read-Host (T 'Delete the backups too? [y/N]')) }
    }
    Write-KohaLog 'uninstall: started' 'install'

    Write-KohaUninstallStep (T 'Closing the Koha window and the status icon...')
    Stop-KohaWindowsSide

    $problems = 0
    $installed = @(Get-KohaInstalledDistros)
    foreach ($d in @(@($cfg.Distro) + @($cfg.OldDistros))) {
        if ($installed -notcontains $d) { continue }
        Write-KohaUninstallStep ((T 'Removing Debian "{0}" and the Koha databases...') -f $d)
        Invoke-KohaWsl -Arguments @('--terminate', $d) | Out-Null
        $r = Invoke-KohaWsl -Arguments @('--unregister', $d)
        if ($r.ExitCode -ne 0) {
            $problems++
            Write-KohaUninstallStep ((T 'Debian "{0}" was not removed: {1}') -f $d, $r.Output.Trim()) 'error'
        }
    }

    Write-KohaUninstallStep (T 'Removing the shortcuts, the scheduled tasks and the sign-in entries...')
    Remove-KohaTasks
    Remove-KohaShortcutFiles
    Remove-KohaRegistryEntries -AppsEntry $false

    if (Test-KohaUninstallNeedsAdmin) {
        Write-KohaUninstallStep (T 'Removing the library network access. Windows asks for permission...')
        $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        try {
            $p = Start-Process -FilePath $ps -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "{0}" UninstallAdmin' -f (Join-Path $PSScriptRoot 'KohaEasy.ps1')) -Verb RunAs -WindowStyle Hidden -Wait -PassThru
            if ($p.ExitCode -ne 0) { throw ('code {0}' -f $p.ExitCode) }
        } catch {
            $problems++
            Write-KohaUninstallStep (T 'The firewall rule and the Koha scheduled tasks were not removed: Windows did not give administrator rights.') 'warn'
        }
    }

    # Something left behind: the Koha folder, with Uninstall-Koha.cmd, and
    # the Settings > Apps entry stay, so the removal can be run again.
    if ($problems -gt 0) {
        Write-Host ''
        Write-KohaUninstallStep ((T 'Koha was not completely removed. Run Uninstall-Koha.cmd in {0} again to finish.') -f $root) 'warn'
        return 1
    }
    Remove-KohaRegistryEntries -AppsEntry $true
    Write-KohaUninstallStep ((T 'Deleting {0}...') -f $root)
    $clean = Remove-KohaFolder -KeepBackups (-not $deleteAll)
    Write-Host ''
    if ($clean) { Write-KohaUninstallStep (T 'Koha was removed from this PC.') 'ok' }
    else { Write-KohaUninstallStep ((T 'Koha was removed. Some files in {0} were in use: restart Windows and delete the folder.') -f $root) 'warn' }
    if ($hasBackups -and -not $deleteAll) { Write-KohaUninstallStep ((T 'Your backups are still in {0}.') -f $backups) 'ok' }
    return 0
}

Export-ModuleMember -Function Uninstall-Koha, Remove-KohaAdminParts, Test-KohaUninstallAnswer, Test-KohaYesAnswer
