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
Check 'tray: Open Debian terminal, no status window' ($tray -match "Invoke-KohaCommand 'Terminal'" -and $tray -notmatch "Invoke-KohaCommand 'Window'")

# install.ps1 Step 0 (Paulo, 2026-10-16): only its functions are loaded,
# so nothing is installed and shutdown.exe is never called here.
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $repo 'windows\install.ps1'), [ref]$null, [ref]$null)
foreach ($fn in $ast.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)) {
    if ($fn.Name -ne 'Install-KohaEasyBootstrap') { . ([scriptblock]::Create($fn.Extent.Text)) }
}
Check 'virt: firmware on' (Test-KohaVirtualizationOn @{ Firmware = $true; Hypervisor = $false })
Check 'virt: off stops' (-not (Test-KohaVirtualizationOn @{ Firmware = $false; Hypervisor = $false }))
Check 'virt: Hyper-V/WSL 2 running hides the flag, still on' (Test-KohaVirtualizationOn @{ Firmware = $false; Hypervisor = $true })
Check 'virt: unknown does not stop' (Test-KohaVirtualizationOn @{ Firmware = $null; Hypervisor = $false })
Check 'virt: AMD' ((Get-KohaCpuBrand @{ Cpu = 'AuthenticAMD'; CpuName = 'AMD Ryzen 5 5600X' }) -eq 'AMD')
Check 'virt: Intel' ((Get-KohaCpuBrand @{ Cpu = 'GenuineIntel'; CpuName = 'Intel(R) Core(TM) i5' }) -eq 'Intel')
Check 'virt: ARM unknown' ((Get-KohaCpuBrand @{ Cpu = 'Qualcomm'; CpuName = 'Snapdragon X' }) -eq '')
$fam = @{ 'ASUSTeK COMPUTER INC.' = 'ASUS'; 'Gigabyte Technology Co., Ltd.' = 'Gigabyte'; 'Micro-Star International Co., Ltd.' = 'MSI'
    'ASRock' = 'ASRock'; 'Dell Inc.' = 'Dell'; 'HP' = 'HP'; 'Hewlett-Packard' = 'HP'; 'LENOVO' = 'Lenovo'; 'Acer' = ''; '' = '' }
foreach ($k in $fam.Keys) { Check ('virt: board ' + $k) ((Get-KohaBoardFamily $k) -eq $fam[$k]) (Get-KohaBoardFamily $k) }
$steps = (Get-KohaBiosSteps -Family 'ASUS' -Brand 'AMD') -join ' | '
Check 'virt: ASUS AMD path' ($steps -match 'F7' -and $steps -match 'Advanced > CPU Configuration > SVM Mode') $steps
$steps = (Get-KohaBiosSteps -Family 'ASUS' -Brand 'Intel') -join ' | '
Check 'virt: ASUS Intel path' ($steps -match 'CPU Configuration > Intel Virtualization Technology') $steps
Check 'virt: Gigabyte path' (((Get-KohaBiosSteps -Family 'Gigabyte' -Brand 'AMD') -join ' ') -match 'Tweaker \(on older boards M\.I\.T\.\) > Advanced CPU Settings > SVM Mode')
Check 'virt: MSI path' (((Get-KohaBiosSteps -Family 'MSI' -Brand 'Intel') -join ' ') -match 'OC > CPU Features > Intel Virtualization Tech')
Check 'virt: ASRock path' (((Get-KohaBiosSteps -Family 'ASRock' -Brand 'Intel') -join ' ') -match 'CPU Configuration > Intel Virtualization Technology \(VMX\)')
foreach ($f in 'Dell', 'HP', 'Lenovo', '') { Check ('virt: steps for ' + $(if ($f) { $f } else { 'generic' })) (@(Get-KohaBiosSteps -Family $f -Brand 'Intel').Count -ge 3) }
Check 'virt: generic AMD names SVM' (((Get-KohaBiosSteps -Family '' -Brand 'AMD') -join ' ') -match 'SVM Mode.*AMD-V')
# The restart: /fw first, Advanced startup (/o) when the firmware cannot be opened.
$calls = New-Object System.Collections.ArrayList
$r = Invoke-KohaFirmwareReboot -Run { param($a) [void]$calls.Add($a -join ' '); 0 }
Check 'virt: reboot into firmware' ($r -eq 'fw' -and ($calls -join ';') -eq '/r /fw /t 2') ($calls -join ';')
$calls.Clear()
$r = Invoke-KohaFirmwareReboot -Run { param($a) [void]$calls.Add($a -join ' '); if ($a -contains '/fw') { 1 } else { 0 } }
Check 'virt: legacy BIOS falls back to Advanced startup' ($r -eq 'o' -and ($calls -join ';') -eq '/r /fw /t 2;/r /o /t 2') ($calls -join ';')
$r = Invoke-KohaFirmwareReboot -Run { param($a) 5 }
Check 'virt: neither works' ($r -eq '')
# Assert: on -> $true, no question. Off -> the steps, the question; N stops
# without a restart, Y restarts.
$off = @{ Firmware = $false; Hypervisor = $false; Cpu = 'AuthenticAMD'; CpuName = 'AMD Ryzen 7'; Board = 'ASUSTeK COMPUTER INC.'; Model = 'TUF GAMING B550M-PLUS' }
$asked = 0; $rebooted = 0
$ok = Assert-VirtualizationReady -Facts @{ Firmware = $true; Hypervisor = $false } -Ask { $script:asked++; 'Y' } -Reboot { $script:rebooted++; 'fw' } 6>$null
Check 'virt: on continues without asking' ($ok -eq $true -and $asked -eq 0 -and $rebooted -eq 0)
$ok = Assert-VirtualizationReady -Facts $off -Ask { $script:asked++; 'n' } -Reboot { $script:rebooted++; 'fw' } 6>$null
Check 'virt: N pauses, no restart' ($ok -eq $false -and $asked -eq 1 -and $rebooted -eq 0)
$answers = New-Object System.Collections.Queue
'maybe', 'y' | ForEach-Object { $answers.Enqueue($_) }
$ok = Assert-VirtualizationReady -Facts $off -Ask { $answers.Dequeue() } -Reboot { $script:rebooted++; 'o' } 6>$null
Check 'virt: asks again until Y or N; Y restarts' ($ok -eq $false -and $rebooted -eq 1 -and $answers.Count -eq 0)
$all = @(Assert-VirtualizationReady -Facts $off -Ask { 'N' } -Reboot { 'fw' } 6>&1)
$shown = ($all | Where-Object { $_ -is [System.Management.Automation.InformationRecord] } | ForEach-Object { [string]$_.MessageData }) -join "`n"
Check 'virt: warning names the board, the photo and the pause' ($shown -match 'TURNED OFF' -and $shown -match 'ASUSTeK COMPUTER INC\. TUF' -and $shown -match 'Take a photo of this screen' -and $shown -match 'installation is paused') $shown

$env:KOHAEASY_ROOT = Join-Path ([IO.Path]::GetTempPath()) ('koha-checks-' + [guid]::NewGuid().ToString('N'))
Import-Module (Join-Path $repo 'windows\KohaEasy.Lang.psm1') -Force
Import-Module (Join-Path $repo 'windows\KohaEasy.Core.psm1') -Force
Import-KeiLanguage -LangDir (Join-Path $repo 'lang') -Culture 'en-US'
$wsl = 'C:\Windows\System32\wsl.exe'

# RAM on Windows (a desktop or virtualized environment): 8 GB minimum, 12 GB
# recommended. Windows reports the usable RAM, so an 8 GB PC shows about 7.7 GB
# and must still pass. Row 2 of the preflight is the memory row.
$ramAst = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $repo 'windows\KohaEasy.Install.psm1'), [ref]$null, [ref]$null)
foreach ($fn in $ramAst.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $a.Name -eq 'Get-KohaPreflight' }, $false)) {
    . ([scriptblock]::Create($fn.Extent.Text))
}
function Get-RamLevel {
    param([double]$Gb)
    $rows = @(Get-KohaPreflight @{ Build = 22631; Is64 = $true; MemGB = $Gb; FreeGB = 50; Hypervisor = $true; VirtFirmware = $null })
    return $rows[2].Level
}
Check 'RAM: 3.8 GB is an error' ((Get-RamLevel 3.8) -eq 'error') (Get-RamLevel 3.8)
Check 'RAM: 7.4 GB is an error' ((Get-RamLevel 7.4) -eq 'error') (Get-RamLevel 7.4)
Check 'RAM: 7.7 GB (an 8 GB PC) meets the minimum, warns below 12 GB'((Get-RamLevel 7.7) -eq 'warn') (Get-RamLevel 7.7)
Check 'RAM: 8 GB is a warning below 12 GB' ((Get-RamLevel 8.0) -eq 'warn') (Get-RamLevel 8.0)
Check 'RAM: 11.4 GB is a warning' ((Get-RamLevel 11.4) -eq 'warn') (Get-RamLevel 11.4)
Check 'RAM: 11.8 GB (a 12 GB PC) is fine' ((Get-RamLevel 11.8) -eq 'ok') (Get-RamLevel 11.8)
Check 'RAM: 16 GB is fine' ((Get-RamLevel 16) -eq 'ok') (Get-RamLevel 16)

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

# The shutdown watcher's window (KohaEasy.Watcher.cs), sent the messages
# Windows sends at the end of a session. Nothing is shut down: SendMessage
# calls the window directly, and the stop is a stand-in.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -ReferencedAssemblies System.Windows.Forms -Path (Join-Path $repo 'windows\KohaEasy.Watcher.cs')
$reason = 'Koha is saving the database and stopping its services safely...'
$w = New-Object KohaShutdownWatcher $reason
$ends = New-Object System.Collections.ArrayList
$w.add_SessionEnding({ [void]$ends.Add($w.QueryReason()) })
$QES = [KohaShutdownWatcher]::WM_QUERYENDSESSION; $ES = [KohaShutdownWatcher]::WM_ENDSESSION
Check 'watcher: a hidden window' ($w.Handle -ne [IntPtr]::Zero)
Check 'watcher: Koha stopped, the query is answered TRUE' (($w.Send($QES, $false)) -eq 1)
Check 'watcher: Koha stopped, no reason held' (-not $w.Blocking -and $w.QueryReason() -eq '') $w.QueryReason()
[void]$w.Send($ES, $true)
Check 'watcher: Koha stopped, no stop at the end of the session' ($ends.Count -eq 0) ($ends.Count)
$w.Armed = $true
Check 'watcher: Koha running, the reason is held' ($w.Blocking -and $w.QueryReason() -eq $reason) $w.QueryReason()
Check 'watcher: Koha running, the query is still answered TRUE' (($w.Send($QES, $false)) -eq 1)
[void]$w.Send($ES, $false)
Check 'watcher: a cancelled shutdown releases the reason, no stop' (-not $w.Blocking -and $ends.Count -eq 0)
[void]$w.Send($QES, $false)
Check 'watcher: the query sets the reason again' ($w.Blocking -and $w.QueryReason() -eq $reason)
[void]$w.Send($ES, $true)
Check 'watcher: the session ends: the stop runs while the reason is held' ($ends.Count -eq 1 -and $ends[0] -eq $reason) ($ends -join '|')
Check 'watcher: then the reason is released' (-not $w.Blocking -and $w.QueryReason() -eq '')
$w2 = New-Object KohaShutdownWatcher $reason
$w2.add_SessionEnding({ throw 'stop failed' })
$w2.Armed = $true
[void]$w2.Send($ES, $true)
Check 'watcher: a failed stop still releases the reason' (-not $w2.Blocking)
$w2.Dispose(); $w.Dispose()
$cmd = Join-Path $env:SystemRoot 'System32\cmd.exe'
Check 'watcher: detached run returns the exit code' ([KohaShutdownWatcher]::RunDetached(('"{0}" /c exit 3' -f $cmd), 10000) -eq 3)
Check 'watcher: detached run past its time is -1' ([KohaShutdownWatcher]::RunDetached(('"{0}" /c ping -n 4 127.0.0.1 >nul' -f $cmd), 300) -eq -1)
Check 'watcher: a program that cannot start is -2' ([KohaShutdownWatcher]::RunDetached('"C:\no\such.exe"', 1000) -eq -2)

# The stop at the end of the session: the script in Debian through a wsl.exe
# with no console, 20 s, then "wsl --shutdown". No WSL here: the runs are
# recorded and answered by a stand-in.
$cfgK = Get-KohaConfig
Check 'stop script: /usr/local/bin/koha-graceful-shutdown.sh, 20 s' ($cfgK.StopScript -eq '/usr/local/bin/koha-graceful-shutdown.sh' -and $cfgK.SessionStopS -eq 20)
$file = ([IO.File]::ReadAllText((Join-Path $repo 'windows\koha-graceful-shutdown.sh')) -replace "`r", '')
$stopText = & (Get-Module KohaEasy.Core) { $script:GracefulStopScript }
Check 'stop script: read from koha-graceful-shutdown.sh' ($stopText -eq $file -and $stopText -match 'stop_units mariadb')
$h1 = Get-KohaStopScriptHash
Set-KohaConfig @{ StopScript = '/usr/local/sbin/koha-easy-stop' }
Check 'stop script: written again when its place changes' ((Get-KohaStopScriptHash) -ne $h1)
Set-KohaConfig @{ StopScript = '/usr/local/bin/koha-graceful-shutdown.sh' }
Set-KohaState @{ stopScriptHash = $h1; poweredOffAt = 0 } | Out-Null
$runs = New-Object System.Collections.ArrayList
$how = Stop-KohaForSessionEnd -RunDetached { param($c, $t) [void]$runs.Add(('{0} @{1}' -f $c, $t)); 0 }
Check 'session end: clean' ($how -eq 'clean') $how
Check 'session end: the script, 20 s (+3 s kill)' ($runs[0] -eq ('"{0}" -d koha -u root -- timeout -k 3 20 sh /usr/local/bin/koha-graceful-shutdown.sh @25000' -f $wsl)) $runs[0]
Check 'session end: then all of WSL, 10 s' ($runs.Count -eq 2 -and $runs[1] -eq ('"{0}" --shutdown @10000' -f $wsl)) ($runs -join ' | ')
$runs.Clear()
$how = Stop-KohaForSessionEnd -RunDetached { param($c, $t) [void]$runs.Add($c); -1 }
Check 'session end: past its time is forced, WSL still shut down' ($how -eq 'forced' -and $runs.Count -eq 2) ("$how " + ($runs -join ' | '))
$runs.Clear()
Set-KohaState @{ poweredOffAt = (Get-UnixTime) } | Out-Null
$how = Stop-KohaForSessionEnd -RunDetached { param($c, $t) [void]$runs.Add($c); 0 }
Check 'session end: after "Shut down the PC safely" nothing runs' ($how -eq 'not_running' -and $runs.Count -eq 0) ("$how " + ($runs -join ' | '))
Set-KohaState @{ poweredOffAt = 0 } | Out-Null
Check 'watcher: releases the block within 37 s' ((Get-KohaSessionStopDeadline) -eq 37) (Get-KohaSessionStopDeadline)

# The watcher at sign-in: its own Run entry, the hidden launch, removed
# again. A test key, not the real Run key.
$key = 'HKCU:\Software\KohaChecks-' + [guid]::NewGuid().ToString('N')
New-Item -Path $key -Force | Out-Null
try {
    Set-KohaWatcherAtSignIn -Enabled $true -Key $key
    $v = (Get-ItemProperty -Path $key -Name 'KohaEasyShutdownWatcher').KohaEasyShutdownWatcher
    Check 'watcher: Run entry with the hidden launch' ($v -match '\sWatcher -Hidden$') $v
    Check 'watcher: Run entry found' (Test-KohaWatcherAtSignIn -Key $key)
    Set-KohaWatcherAtSignIn -Enabled $false -Key $key
    Check 'watcher: Run entry removed' (-not (Test-KohaWatcherAtSignIn -Key $key))
} finally { Remove-Item -Path $key -Recurse -Force -ErrorAction SilentlyContinue }
Check 'watcher: wanted unless turned off' (Test-KohaWatcherWanted)
Set-KohaState @{ shutdownWatcher = 'off' } | Out-Null
Check 'watcher: turned off' (-not (Test-KohaWatcherWanted) -and (Repair-KohaWatcher) -eq 'off')
Set-KohaState @{ shutdownWatcher = 'on' } | Out-Null
Check 'watcher: not running here' (-not (Test-KohaWatcherRunning))
Check 'watcher: never shows a console' (-not (Test-KohaRelaunchHidden -Command 'Watcher' -Hidden $true) -and (Test-KohaRelaunchHidden -Command 'Watcher' -Hidden $false -Target 'C:\Koha\bin\koha.nexus.exe'))
$trayText = Get-Content -Raw -LiteralPath (Join-Path $repo 'windows\KohaEasy.Tray.ps1')
Check 'tray: leaves the end of the session to the watcher' (([regex]::Matches($trayText, 'Test-KohaWatcherRunning')).Count -eq 2)

# Portuguese texts for the tray's new items.
Import-KeiLanguage -LangDir (Join-Path $repo 'lang') -Culture 'pt-BR'
foreach ($k in 'Open Dashboard', 'Open User Folder', 'Restart Services', 'More options', 'Exit', 'Koha is saving the database and stopping its services safely...') {
    Check ('pt: ' + $k) ((T $k) -ne $k) (T $k)
}
# (This file is ASCII with no BOM: the accents are written as [char].)
$ptReason = 'O Koha est' + [char]0xE1 + ' salvando o banco de dados e finalizando os servi' + [char]0xE7 + 'os com seguran' + [char]0xE7 + 'a...'
Check 'pt: the shutdown reason in Paulo''s words' ((T 'Koha is saving the database and stopping its services safely...') -eq $ptReason) (T 'Koha is saving the database and stopping its services safely...')

# .wslconfig: Koha's keys are added, the user's own values are kept
# (autoMemoryReclaim=gradual on every build; mirrored networking and
# hostAddressLoopback from build 22621).
foreach ($fn in $ramAst.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $a.Name -eq 'Merge-KohaWslConfig' }, $false)) {
    . ([scriptblock]::Create($fn.Extent.Text))
}
$cfg = Merge-KohaWslConfig -Text '' -Build 19045
Check 'wslconfig: autoMemoryReclaim on Windows 10' ($cfg -match '(?m)^\[experimental\]\r?\nautoMemoryReclaim=gradual\r?$' -and $cfg -notmatch 'mirrored') $cfg
$cfg = Merge-KohaWslConfig -Text '' -Build 22631
Check 'wslconfig: Windows 11 keys' ($cfg -match 'networkingMode=mirrored' -and $cfg -match 'autoMemoryReclaim=gradual' -and $cfg -match 'hostAddressLoopback=true') $cfg
$mine = "[wsl2]`r`nmemory=6GB`r`n`r`n[experimental]`r`nautoMemoryReclaim=dropcache`r`n"
$cfg = Merge-KohaWslConfig -Text $mine -Build 19045
Check 'wslconfig: the user''s autoMemoryReclaim is kept' ($cfg -match 'autoMemoryReclaim=dropcache' -and $cfg -notmatch 'gradual' -and $cfg -match 'memory=6GB' -and $cfg -match 'vmIdleTimeout=-1') $cfg
Check 'wslconfig: a second merge changes nothing' ((Merge-KohaWslConfig -Text $cfg -Build 19045) -eq $cfg)

# Store installer (windows\setup): its PowerShell parses, and every exit
# code the script sets is a different value.
foreach ($f in Get-ChildItem (Join-Path $repo 'windows\setup') -Filter '*.ps1') {
    $tokens = $null; $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$tokens, [ref]$errors)
    Check ('parses: setup\' + $f.Name) (@($errors).Count -eq 0) ((@($errors) | ForEach-Object { $_.Message }) -join '; ')
}
$iss = Get-Content -LiteralPath (Join-Path $repo 'windows\setup\koha-nexus.iss') -Raw
$codes = @([regex]::Matches($iss, '(?m)^\s*Exit\w+\s*=\s*(\d+);') | ForEach-Object { $_.Groups[1].Value })
Check 'store: exit codes are distinct' ((@($codes | Select-Object -Unique)).Count -eq $codes.Count -and $codes.Count -eq 7) ($codes -join ',')

# No parameter or command glued to a variable ("-Autostart$Mode",
# "Join-Path$env:SystemRoot"): PowerShell reads them as one word, so the
# value never arrives or the command is not found.
foreach ($f in Get-ChildItem (Join-Path $repo 'windows') -Filter '*.ps*1') {
    $fileAst = [System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$null, [ref]$null)
    $glued = @($fileAst.FindAll({ param($a) $a -is [System.Management.Automation.Language.CommandAst] }, $true) | ForEach-Object {
        foreach ($el in $_.CommandElements) { if ($el.Extent.Text -match '^-?[A-Za-z][\w-]*\$') { '{0}: {1}' -f $el.Extent.StartLineNumber, $el.Extent.Text } }
    })
    Check ('nothing glued to a variable: ' + $f.Name) ($glued.Count -eq 0) ($glued -join '; ')
}

# MSIX (windows\msix): its scripts parse; instalar_msix.ps1 runs through
# irm | iex, so it stays ASCII with no BOM; it trusts exactly the
# certificate that signed the published package, and the .cer next to it
# is that same certificate.
foreach ($f in Get-ChildItem (Join-Path $repo 'windows\msix') -Filter '*.ps1') {
    $tokens = $null; $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$tokens, [ref]$errors)
    Check ('parses: msix\' + $f.Name) (@($errors).Count -eq 0) ((@($errors) | ForEach-Object { $_.Message }) -join '; ')
}
$msixInstaller = Join-Path $repo 'windows\msix\instalar_msix.ps1'
$bytes = [IO.File]::ReadAllBytes($msixInstaller)
Check 'no BOM, ASCII only (irm | iex): msix\instalar_msix.ps1' (@($bytes | Where-Object { $_ -gt 0x7F }).Count -eq 0)
$msixAst = [System.Management.Automation.Language.Parser]::ParseFile($msixInstaller, [ref]$null, [ref]$null)
foreach ($fn in $msixAst.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $a.Name -like 'Get-KohaMsix*' }, $false)) {
    . ([scriptblock]::Create($fn.Extent.Text))
}
$signer = Get-KohaMsixSigner -Path (Join-Path $repo 'windows\msix\KohaNexus.msix')
$identity = Get-KohaMsixIdentity -Path (Join-Path $repo 'windows\msix\KohaNexus.msix')
$cer = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 -ArgumentList (Join-Path $repo 'windows\msix\KohaNexus-Publisher.cer')
$pinned = Get-Content -Raw -LiteralPath $msixInstaller
Check 'msix: signer is the published .cer' ($signer.Thumbprint -eq $cer.Thumbprint) ('{0} / {1}' -f $signer.Thumbprint, $cer.Thumbprint)
Check 'msix: instalar_msix.ps1 knows the signer' ($pinned -match ("'" + $signer.Thumbprint + "'")) $signer.Thumbprint
Check 'msix: manifest Publisher is the signer subject' ($identity.Publisher -eq $signer.Subject) ('{0} / {1}' -f $identity.Publisher, $signer.Subject)

# No foreach variable named like a parameter of its own script or
# function: PowerShell ignores case, so "foreach ($store in ...)" in
# compilar_msix.ps1 wrote over [switch]$Store and -Store stopped with
# "cannot convert PSCustomObject to SwitchParameter".
$scripts = @(Get-ChildItem (Join-Path $repo 'windows') -Filter '*.ps*1') +
    @(Get-ChildItem (Join-Path $repo 'windows\msix') -Filter '*.ps1') +
    @(Get-ChildItem (Join-Path $repo 'windows\setup') -Filter '*.ps1')
foreach ($f in $scripts) {
    $fileAst = [System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$null, [ref]$null)
    $clashes = @()
    foreach ($loop in $fileAst.FindAll({ param($a) $a -is [System.Management.Automation.Language.ForEachStatementAst] }, $true)) {
        $owner = $loop.Parent
        while ($owner -and -not ($owner -is [System.Management.Automation.Language.ScriptBlockAst])) { $owner = $owner.Parent }
        $params = @()
        if ($owner.ParamBlock) { $params += $owner.ParamBlock.Parameters }
        if ($owner.Parent -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $owner.Parent.Parameters) { $params += $owner.Parent.Parameters }
        $name = $loop.Variable.VariablePath.UserPath
        foreach ($p in $params) {
            if ($p.Name.VariablePath.UserPath -ieq $name) { $clashes += ('{0}: ${1} / param ${2}' -f $loop.Extent.StartLineNumber, $name, $p.Name.VariablePath.UserPath) }
        }
    }
    Check ('no foreach variable named like a parameter: ' + $f.Name) ($clashes.Count -eq 0) ($clashes -join '; ')
}

# MSIX for the Store (compilar_msix.ps1 -Store): store-identity.json is
# either still empty or holds a valid Partner Center identity, and the
# payload revision moves with the package version (a rebuild under the same
# revision leaves old scripts in C:\Koha\bin).
$builder = Join-Path $repo 'windows\msix\compilar_msix.ps1'
$builderAst = [System.Management.Automation.Language.Parser]::ParseFile($builder, [ref]$null, [ref]$null)
foreach ($fn in $builderAst.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $a.Name -eq 'Get-KohaStoreIdentity' }, $false)) {
    . ([scriptblock]::Create($fn.Extent.Text))
}
$storeJson = Join-Path $repo 'windows\msix\store-identity.json'
$storeData = Get-Content -LiteralPath $storeJson -Raw | ConvertFrom-Json
if (-not ($storeData.Name -or $storeData.Publisher -or $storeData.PublisherDisplayName)) {
    Check 'store: identity not filled in yet' $true
} else {
    $storeError = ''
    try { [void](Get-KohaStoreIdentity -Path $storeJson) } catch { $storeError = $_.Exception.Message }
    Check 'store: store-identity.json is a valid identity' ($storeError -eq '') $storeError
}
# The MSIX build copies windows\ as it is (the MSIX changes live in the
# sources since 543272d) and only checks it with Test-KohaMsixSources: run
# the same check on the real files here, so a change to them that breaks
# the MSIX shows up in CI and not on the build PC. A copy with the old
# hard-coded password or the disabled account function must fail it.
foreach ($fn in $builderAst.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $a.Name -eq 'Test-KohaMsixSources' }, $false)) {
    . ([scriptblock]::Create($fn.Extent.Text))
}
$msixProblems = @(Test-KohaMsixSources -WindowsDir (Join-Path $repo 'windows'))
Check 'msix: windows\ has what the MSIX bootstrap uses' ($msixProblems.Count -eq 0) ($msixProblems -join '; ')
$badCopy = Join-Path ([IO.Path]::GetTempPath()) ('koha-msix-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $badCopy | Out-Null
try {
    Copy-Item -Path (Join-Path $repo 'windows\*') -Destination $badCopy -Recurse
    $badModule = Join-Path $badCopy 'KohaEasy.Install.psm1'
    $text = [IO.File]::ReadAllText($badModule)
    $text = $text.Replace('function Read-KohaLinuxAccount {', "function Read-KohaLinuxAccount { return @{ User = 'koha'; Password = 'kohanexuspassword123' } }`nfunction Read-KohaLinuxAccount_Disabled {")
    [IO.File]::WriteAllText($badModule, $text)
    $badProblems = @(Test-KohaMsixSources -WindowsDir $badCopy)
    Check 'msix: a fixed password or disabled account prompt stops the build' (($badProblems -join ';') -match 'senha fixa' -and ($badProblems -join ';') -match '_Disabled') ($badProblems -join '; ')
} finally {
    Remove-Item -LiteralPath $badCopy -Recurse -Force
}
# The installer, its hash, lang\ and panel\ go into Debian and must keep
# LF: Git for Windows (core.autocrlf, also on this CI runner) wrote the
# installer with CRLF, it no longer matched installer.sha256 and the MSIX
# stopped at "The installer file is damaged". .gitattributes keeps them LF;
# the build refuses a checkout without it. Runs on this runner's checkout,
# and on a copy whose installer has CRLF, which must fail.
foreach ($fn in $builderAst.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $a.Name -eq 'Test-KohaMsixPayloadText' }, $false)) {
    . ([scriptblock]::Create($fn.Extent.Text))
}
$textProblems = @(Test-KohaMsixPayloadText -Root $repo)
Check 'msix: installer matches installer.sha256, payload text is LF' ($textProblems.Count -eq 0) ($textProblems -join '; ')
$crlfCopy = Join-Path ([IO.Path]::GetTempPath()) ('koha-msix-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $crlfCopy | Out-Null
try {
    Copy-Item -LiteralPath (Join-Path $repo 'installer.sha256') -Destination $crlfCopy
    $lf = [IO.File]::ReadAllText((Join-Path $repo 'installer'))
    [IO.File]::WriteAllText((Join-Path $crlfCopy 'installer'), $lf.Replace("`n", "`r`n"))
    $crlfProblems = @(Test-KohaMsixPayloadText -Root $crlfCopy) -join ';'
    Check 'msix: an installer with CRLF stops the build' ($crlfProblems -match 'installer.sha256' -and $crlfProblems -match 'CRLF') $crlfProblems
} finally {
    Remove-Item -LiteralPath $crlfCopy -Recurse -Force
}
$builderText = Get-Content -LiteralPath $builder -Raw
$rewrites = [regex]::Matches($builderText, 'WriteAllText\(\$(coreModulePath|installModulePath|mainWindowsPath|panelWrapperPath|iconFixScriptPath|windowsInstallerPath)\b')
Check 'msix: the build rewrites no file of windows\' ($rewrites.Count -eq 0) (($rewrites | ForEach-Object { $_.Value }) -join '; ')
$version = [regex]::Match($builderText, "(?m)^\`$targetVersion = '([^']+)'").Groups[1].Value
$revision = [regex]::Match($builderText, "(?m)^\`$payloadRevision = '([^']+)'").Groups[1].Value
Check 'msix: payload revision follows the version' ($version -and $revision.StartsWith($version + '-')) ('{0} / {1}' -f $version, $revision)
# Store 10.1.1.11 (tile icon not clear): the build drew the tiles from the
# .ico with System.Drawing and Windows PowerShell 5.1 turned its PNG frames
# into colour noise. The tiles are now ready PNGs in windows\msix\Assets
# (gerar_assets.py), every scale the manifest needs, indexed by resources.pri.
foreach ($fn in $builderAst.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $a.Name -in @('Get-KohaMsixAssetSizes', 'Test-KohaMsixAssets') }, $false)) {
    . ([scriptblock]::Create($fn.Extent.Text))
}
$assetProblems = @(Test-KohaMsixAssets -AssetsDir (Join-Path $repo 'windows\msix\Assets'))
Check 'msix: Assets has every tile and icon at its size' ($assetProblems.Count -eq 0) ($assetProblems -join '; ')
$assetCopy = Join-Path ([IO.Path]::GetTempPath()) ('koha-msix-' + [guid]::NewGuid())
Copy-Item -LiteralPath (Join-Path $repo 'windows\msix\Assets') -Destination $assetCopy -Recurse
try {
    Remove-Item -LiteralPath (Join-Path $assetCopy 'StoreLogo.scale-100.png')
    Copy-Item -LiteralPath (Join-Path $assetCopy 'Square150x150Logo.scale-100.png') -Destination (Join-Path $assetCopy 'Square150x150Logo.scale-200.png') -Force
    $badAssets = @(Test-KohaMsixAssets -AssetsDir $assetCopy) -join ';'
    Check 'msix: a missing or wrong-size tile stops the build' ($badAssets -match 'StoreLogo.scale-100' -and $badAssets -match '150x150, esperado 300x300') $badAssets
} finally {
    Remove-Item -LiteralPath $assetCopy -Recurse -Force
}
Check 'msix: the build no longer draws tiles with System.Drawing' ($builderText -notmatch 'System\.Drawing\.(Icon|Bitmap)') ''
Check 'msix: the build makes resources.pri' ($builderText -match '\$makePri new ' -and $builderText -match "'resources.pri'") ''
Check 'msix: the manifest has the wide, small and large tiles' ($builderText -match 'Wide310x150Logo="Assets\\Wide310x150Logo.png"' -and $builderText -match 'Square71x71Logo="Assets\\Square71x71Logo.png"' -and $builderText -match 'Square310x310Logo="Assets\\Square310x310Logo.png"') ''
# Store 10.1.2.10 (crashes at launch, 1.0.27.0 and 1.0.28.0): the tester only
# saw the error box "Koha.Nexus could not be started". The launcher now opens
# its own setup window (requirements + Install button) and shows every stop
# inside it; the bootstrap, given -ResultFile, writes the reason there and
# shows no box.
$entryPath = Join-Path $repo 'windows\msix\KohaMsixEntry.cs'
$entryText = Get-Content -LiteralPath $entryPath -Raw
Check 'msix: the build compiles windows\msix\KohaMsixEntry.cs' ($builderText -match "Join-Path \`$scriptRoot 'KohaMsixEntry.cs'" -and $builderText -notmatch "entrySource = @'") ''
Check 'msix: the launcher has the payload marker and a setup window' ($entryText -match '"__PAYLOAD_VERSION__"' -and $entryText -match 'class SetupForm : Form' -and $entryText -match '-ResultFile') ''
Check 'msix: the launcher never shows "could not be started"' ($entryText -notmatch 'could not be started') ''
$csc = @((Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'), (Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe')) |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if ($csc) {
    $cscDir = Join-Path ([IO.Path]::GetTempPath()) ('koha-msix-' + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $cscDir | Out-Null
    try {
        $cscSource = Join-Path $cscDir 'KohaMsixEntry.cs'
        [IO.File]::WriteAllText($cscSource, $entryText.Replace('__PAYLOAD_VERSION__', 'test'), (New-Object System.Text.UTF8Encoding($false)))
        $cscOut = & $csc /nologo /target:winexe /platform:anycpu /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Management.dll ('/out:' + (Join-Path $cscDir 'KohaMsixEntry.exe')) $cscSource 2>&1
        Check 'msix: KohaMsixEntry.cs compiles with the .NET Framework csc' ($LASTEXITCODE -eq 0) (($cscOut | Out-String).Trim())
    } finally {
        Remove-Item -LiteralPath $cscDir -Recurse -Force
    }
}
$bootMatch = [regex]::Match($builderText, "(?s)\`$bootstrapContent = @'\r?\n(.*?)\r?\n'@")
$bootErrors = $null
[void][System.Management.Automation.Language.Parser]::ParseInput($bootMatch.Groups[1].Value, [ref]$null, [ref]$bootErrors)
Check 'msix: the bootstrap parses' ($bootMatch.Success -and @($bootErrors).Count -eq 0) ((@($bootErrors) | ForEach-Object { $_.Message }) -join '; ')
$bootText = $bootMatch.Groups[1].Value
Check 'msix: the bootstrap takes -ResultFile and writes stops there' ($bootText -match "(?m)^param\(\[string\]\`$ResultFile = ''\)" -and $bootText -match 'Write-BootstrapResult \$message' -and $bootText -match 'if \(\$ResultFile\) \{ exit 3 \}' -and $bootText -match 'exit 11') ''
Check 'msix: a declined UAC prompt shows ElevationBody, not the error box' ($builderText -match '-Verb RunAs -WindowStyle Normal -ErrorAction Stop' -and $builderText -match '\$ui\.ElevationBody') ''
Check 'msix: bootstrap errors exit 10' ($builderText -match '(?m)^    exit 10\r?$') ''
# Store 10.1.1.11 (1.0.28.0): the tiles showed the Koha community logo. The
# package icon is now drawn by gerar_assets.py; the old logo file is gone.
Check 'msix: the Koha logo is not a package source' (-not (Test-Path -LiteralPath (Join-Path $repo 'windows\msix\KohaNexusLogo.png')) -and (Test-Path -LiteralPath (Join-Path $repo 'windows\msix\KohaNexusMark.png'))) ''

if ($failed) { throw "$failed check(s) failed" }
Write-Host 'all checks passed'
