# Checks of the Windows tools that need no WSL and no Koha (CI on a Windows
# runner, Windows PowerShell 5.1): every script parses, and the pure
# functions behind the tray give what the tray expects. Not copied to
# C:\Koha (install.ps1 copies windows\ only).
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$failed = 0
function Check {
    param([string]$Name, [bool]$Ok, [string]$Got = '')
    if ($Ok) { Write-Host "ok   $Name" } else { Write-Host "FAIL $Name $Got" -ForegroundColor Red; $script:failed++ }
}

foreach ($f in Get-ChildItem (Join-Path $repo 'windows') -Filter '*.ps*1') {
    $tokens = $null; $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$tokens, [ref]$errors)
    Check ('parses: ' + $f.Name) (@($errors).Count -eq 0) ((@($errors) | ForEach-Object { $_.Message }) -join '; ')
}

# Encoding. The one-liner scripts (irm ... | iex) must have no BOM: Windows
# PowerShell 5.1 keeps it in front of the first "#", and iex then fails with
# ObjectNotFound (#:String). They stay ASCII so no BOM is ever needed. Every
# other script with accents or emoji keeps its BOM: without one, Windows
# PowerShell 5.1 reads the file as ANSI and mangles them.
foreach ($f in Get-ChildItem (Join-Path $repo 'windows') -Filter '*.ps*1') {
    $bytes = [IO.File]::ReadAllBytes($f.FullName)
    $bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $start = 0
    if ($bom) { $start = 3 }
    $ascii = $true
    for ($i = $start; $i -lt $bytes.Length; $i++) { if ($bytes[$i] -gt 0x7F) { $ascii = $false; break } }
    if (@('install.ps1', 'diagnose.ps1') -contains $f.Name) {
        Check ('no BOM (irm | iex): ' + $f.Name) (-not $bom)
        Check ('ASCII only (irm | iex): ' + $f.Name) $ascii
    } elseif (-not $ascii) {
        Check ('BOM for its accents (PS 5.1): ' + $f.Name) $bom
    }
}

# One interface: the Koha status window is gone (only install.ps1 names it,
# to delete it from older installs), and nothing opens it any more.
$names = @(Get-ChildItem (Join-Path $repo 'windows') -File | Where-Object { (Get-Content -Raw -LiteralPath $_.FullName) -match 'KohaEasy\.Window\.ps1' } | ForEach-Object { $_.Name })
Check 'no Koha status window' (-not (Test-Path (Join-Path $repo 'windows\KohaEasy.Window.ps1')) -and ($names -join ',') -eq 'install.ps1') ($names -join ',')
$tray = Get-Content -Raw -LiteralPath (Join-Path $repo 'windows\KohaEasy.Tray.ps1')
Check 'tray: Open the terminal, no status window' ($tray -match "Invoke-KohaCommand 'Terminal'" -and $tray -notmatch "Invoke-KohaCommand 'Window'")

$env:KOHAEASY_ROOT = Join-Path ([IO.Path]::GetTempPath()) ('koha-checks-' + [guid]::NewGuid().ToString('N'))
Import-Module (Join-Path $repo 'windows\KohaEasy.Lang.psm1') -Force
Import-Module (Join-Path $repo 'windows\KohaEasy.Core.psm1') -Force
Import-KeiLanguage -LangDir (Join-Path $repo 'lang') -Culture 'en-US'
$wsl = 'C:\Windows\System32\wsl.exe'

# The Koha icon opens the panel; no shortcut opens the old status window.
$cmds = @(Get-KohaShortcutList | Where-Object { $_.Kind -eq 'lnk' } | ForEach-Object { $_.Arguments })
Check 'shortcuts: no Window verb' (@($cmds | Where-Object { $_ -match '\sWindow(\s|$)' }).Count -eq 0) ($cmds -join ' | ')
Check 'shortcuts: the Koha icon is Launch' (@($cmds | Where-Object { $_ -match '\sLaunch(\s|$)' }).Count -eq 1) ($cmds -join ' | ')

# The control panel: Windows Terminal with the Koha Nexus profile and title,
# else cmd.exe in UTF-8 with the same title.
$l = Get-KohaPanelLaunch -Wsl $wsl -Terminal 'C:\wt.exe' -Pause 'x' -Action 'backup-manual'
Check 'wt: file' ($l.File -eq 'C:\wt.exe') $l.File
Check 'wt: profile and title' ($l.Arguments.StartsWith('-w new -M -p "Koha Nexus" --title "Koha Nexus" "C:\Windows\System32\wsl.exe" -d koha -u root')) $l.Arguments
Check 'wt: emoji glyphs, one routine' ($l.Arguments -match 'KEI_PLAIN_GLYPHS=0 ' -and $l.Arguments.EndsWith('/usr/local/bin/koha-panel --run backup-manual')) $l.Arguments
$l = Get-KohaPanelLaunch -Wsl $wsl -Terminal '' -Cmd 'C:\Windows\System32\cmd.exe'
Check 'cmd: file' ($l.File -eq 'C:\Windows\System32\cmd.exe') $l.File
Check 'cmd: UTF-8, title, wsl' ($l.Arguments.StartsWith('/c chcp 65001 >nul & title Koha Nexus& "C:\Windows\System32\wsl.exe" -d koha -u root')) $l.Arguments
Check 'cmd: plain glyphs' ($l.Arguments -match 'KEI_PLAIN_GLYPHS=1 ') $l.Arguments
Check 'cmd: maximized' ($l.WindowStyle -eq 'Maximized') $l.WindowStyle

# The Windows Terminal fragment is valid JSON with the profile's settings.
$p = (Get-KohaTerminalProfileJson -Wsl $wsl -Icon 'C:\Koha\bin\koha.ico' | ConvertFrom-Json).profiles[0]
Check 'profile: name' ($p.name -eq 'Koha Nexus') $p.name
Check 'profile: command line' ($p.commandline -eq '"C:\Windows\System32\wsl.exe" -d koha -u root --cd /root -- env KEI_PLAIN_GLYPHS=0 /usr/local/bin/koha-window /usr/local/bin/koha-panel') $p.commandline
Check 'profile: title kept' ($p.tabTitle -eq 'Koha Nexus' -and $p.suppressApplicationTitle -eq $true)
Check 'profile: padding and font' ($p.padding -eq '12, 8' -and $p.font.face -eq 'Cascadia Mono')

# Toasts at the end of long panel jobs: each new event once; the first
# time only recent ones; unknown kinds skipped.
$now = [int64](Get-UnixTime)
$state = [ordered]@{ desired = 'running'; lastEventId = 0; lastBackupLogEpoch = 0; firstSeen = 1; lastStaleBackupWarn = 0
    autostart = 'logon'; lastRecoveryNotice = 0; lastRecoveryEpoch = 0; notifyBackupOk = $true; lastDiskLevel = 'ok'; lastDiskWarn = 0 }
$events = '[{{"id":{0},"level":"ok","kind":"restore"}},{{"id":{1},"level":"failed","kind":"backup_manual"}},{{"id":{2},"level":"ok","kind":"reindex"}},{{"id":{3},"level":"ok","kind":"later_kind"}}]' -f ($now * 1000 - 900000), ($now * 1000 - 5000), ($now * 1000 - 4000), ($now * 1000 - 3000)
$linux = ('{{"koha_installed":true,"backup":{{"last_epoch":{0},"log_epoch":0,"last_size":0,"last_result":"none"}},"events":{1}}}' -f $now, $events) | ConvertFrom-Json
$status = [pscustomobject]@{ State = 'running'; Linux = $linux }
$r = Get-KohaNotifications -Previous 'running' -Status $status -Disk $null -State $state -Now $now
$n = @($r.Notifications)
Check 'events: two told (old and unknown skipped)' ($n.Count -eq 2) ($n.Count)
Check 'events: failed backup is an error' ($n[0].Level -eq 'error' -and $n[0].Title -eq 'Backup FAILED') ($n[0].Title)
Check 'events: reindex is info' ($n[1].Level -eq 'info') ($n[1].Level)
Check 'events: newest id remembered' ($r.Changes.lastEventId -eq ($now * 1000 - 3000)) ($r.Changes.lastEventId)
$state.lastEventId = $r.Changes.lastEventId
$r = Get-KohaNotifications -Previous 'running' -Status $status -Disk $null -State $state -Now $now
Check 'events: told once' (@($r.Notifications).Count -eq 0)
$old = ('{{"koha_installed":true,"backup":{{"last_epoch":{0},"log_epoch":0,"last_size":0,"last_result":"none"}}}}' -f $now) | ConvertFrom-Json
$r = Get-KohaNotifications -Previous 'running' -Status ([pscustomobject]@{ State = 'running'; Linux = $old }) -Disk $null -State $state -Now $now
Check 'events: a panel without events still works' (@($r.Notifications).Count -eq 0)

# Portuguese texts for the tray's new items.
Import-KeiLanguage -LangDir (Join-Path $repo 'lang') -Culture 'pt-BR'
foreach ($k in 'Open Dashboard', 'Open User Folder', 'Restart Services', 'More options', 'Exit') {
    Check ('pt: ' + $k) ((T $k) -ne $k) (T $k)
}

if ($failed) { throw "$failed check(s) failed" }
Write-Host 'all checks passed'
