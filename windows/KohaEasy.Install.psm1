# Koha Easy Installer for Windows: the install flow (blueprint 2.3).
# Started by windows\install.ps1 (the irm | iex one-liner, which
# Install-Koha.cmd also runs) as "KohaEasy.ps1 Install". Every phase is
# idempotent and recorded in state.json, so running Install again (or the
# RunOnce entry after a restart) continues where it stopped:
#   checks    Windows version, 64-bit, memory, disk, virtualization; then the
#             Debian user name and password, asked before anything is installed
#   wsl       WSL 2 platform (one UAC prompt; a restart when Windows asks)
#   distro    Debian installed as "koha" from Microsoft's own WSL list
#   systemd   the Debian user, /etc/wsl.conf with systemd, .wslconfig
#             (mirrored on Win 11), and a full restart of Debian until
#             systemd runs
#   koha      the panel copied in and opened for "1 - Install Koha server"
#   windows   tasks, automatic start choice, shortcuts and icons, access
#             from the library network, tray, first start
# Windows PowerShell 5.1 compatible. UTF-8 with BOM.

Set-StrictMode -Version 2.0
Import-Module (Join-Path $PSScriptRoot 'KohaEasy.Lang.psm1')
Import-Module (Join-Path $PSScriptRoot 'KohaEasy.Core.psm1')

$script:ManifestUrl = 'https://raw.githubusercontent.com/microsoft/WSL/master/distributions/DistributionInfo.json'
$script:Phases = @('checks', 'wsl', 'distro', 'systemd', 'koha', 'windows', 'done')
$script:DistroDir = '/root/koha-easy-installer'
$script:LauncherPath = '/usr/local/bin/koha-panel'

function Write-KohaStep {
    param([string]$Text, [ValidateSet('step', 'ok', 'warn', 'error')][string]$Kind = 'step')
    $color = @{ step = 'Cyan'; ok = 'Green'; warn = 'Yellow'; error = 'Red' }[$Kind]
    Write-Host ('{0} {1}' -f (Get-KohaStepMark $Kind), $Text) -ForegroundColor $color
    Write-KohaLog ('install: [{0}] {1}' -f $Kind, $Text) 'install'
}

# Emoji in Windows Terminal; plain tags in the classic console, which has
# no emoji font. Built from code points so this file stays readable in any
# editor. The warning sign takes U+FE0F to be drawn as an emoji.
function Get-KohaStepMark {
    param([string]$Kind, [string]$Mode = (Get-KohaGlyphMode))
    if ($Mode -eq '1') { return @{ step = '[>]'; ok = '[OK]'; warn = '[!]'; error = '[X]' }[$Kind] }
    $cp = @{ step = @(0x23F3); ok = @(0x2705); warn = @(0x26A0, 0xFE0F); error = @(0x274C) }[$Kind]
    return -join @($cp | ForEach-Object { [char]::ConvertFromUtf32($_) })
}

function Test-KohaPhaseDone {
    param([string]$Phase, [string]$Current)
    $i = [array]::IndexOf($script:Phases, $Phase)
    $c = [array]::IndexOf($script:Phases, $Current)
    return ($c -gt $i)
}

# ----------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------
function Get-KohaHostFacts {
    $f = @{ Build = [Environment]::OSVersion.Version.Build; Is64 = [Environment]::Is64BitOperatingSystem
        MemGB = 0; FreeGB = 0; VirtFirmware = $null; Hypervisor = $false; Arm = $false }
    try { $f.MemGB = [Math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1) } catch { }
    try { $f.Hypervisor = [bool](Get-CimInstance Win32_ComputerSystem).HypervisorPresent } catch { }
    try { $f.VirtFirmware = [bool](Get-CimInstance Win32_Processor | Select-Object -First 1).VirtualizationFirmwareEnabled } catch { }
    try { $f.FreeGB = [Math]::Round((New-Object System.IO.DriveInfo((Get-KohaPath Root).Substring(0, 2))).AvailableFreeSpace / 1GB, 1) } catch { }
    $f.Arm = ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64')
    return $f
}

# Pure: one row per check (Level ok | warn | error).
function Get-KohaPreflight {
    param([hashtable]$Facts)
    $rows = New-Object System.Collections.ArrayList
    $add = { param($ok, $level, $text) [void]$rows.Add([pscustomobject]@{ Ok = $ok; Level = $(if ($ok) { 'ok' } else { $level }); Text = $text }) }
    & $add ($Facts.Build -ge 19041) 'error' ((T 'Windows 10 version 2004 (build 19041) or later, or Windows 11. This PC: build {0}.') -f $Facts.Build)
    & $add ([bool]$Facts.Is64) 'error' (T 'A 64-bit Windows.')
    if ($Facts.MemGB -lt 4) {
        & $add $false 'error' ((T 'At least 4 GB of memory (8 GB recommended). This PC: {0} GB.') -f $Facts.MemGB)
    } else {
        & $add ($Facts.MemGB -ge 8) 'warn' ((T 'At least 4 GB of memory (8 GB recommended). This PC: {0} GB.') -f $Facts.MemGB)
    }
    if ($Facts.FreeGB -lt 10) {
        & $add $false 'error' ((T 'At least 10 GB free on drive C: (20 GB recommended). Free now: {0} GB.') -f $Facts.FreeGB)
    } else {
        & $add ($Facts.FreeGB -ge 20) 'warn' ((T 'At least 10 GB free on drive C: (20 GB recommended). Free now: {0} GB.') -f $Facts.FreeGB)
    }
    # With Hyper-V already running, Windows hides the firmware flag: that is fine.
    $virt = ($Facts.Hypervisor -or $Facts.VirtFirmware -ne $false)
    & $add $virt 'error' (T 'Virtualization turned on in the BIOS/UEFI (Intel VT-x or AMD-V, sometimes called SVM).')
    return @($rows)
}

# ----------------------------------------------------------------------
# WSL 2 platform
# ----------------------------------------------------------------------
function Test-KohaWslReady {
    $r = Invoke-KohaWsl -Arguments @('--version')
    return ($r.ExitCode -eq 0)
}

# One UAC prompt: "wsl --install --no-distribution" enables the Windows
# features and installs WSL from the Store package; then "wsl --update".
function Install-KohaWslPlatform {
    Start-KohaElevated -FilePath 'wsl.exe' -Arguments '--install --no-distribution' | Out-Null
    Start-KohaElevated -FilePath 'wsl.exe' -Arguments '--update' | Out-Null
}

function Start-KohaElevated {
    param([string]$FilePath, [string]$Arguments)
    $p = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Verb RunAs -Wait -PassThru
    return $p.ExitCode
}

# Pure: the command line that continues the install, in Windows Terminal
# when it is installed (emoji and accents), else in the classic console.
# -Pause keeps the window open at the end so the last lines can be read.
function Get-KohaInstallCommand {
    param([string]$PowerShell, [string]$Script, [string]$Terminal)
    $cmd = '"{0}" -NoProfile -ExecutionPolicy Bypass -File "{1}" Install' -f $PowerShell, $Script
    if (-not $Terminal) { return $cmd }
    return ('"{0}" -w new --title Koha {1} -Pause' -f $Terminal, $cmd)
}

# After a restart, Install runs again by itself (HKCU RunOnce, no admin).
function Register-KohaResume {
    $ps = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    $cmd = Get-KohaInstallCommand -PowerShell $ps -Script (Get-KohaScriptPath) -Terminal (Get-KohaTerminalPath)
    New-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' -Name 'KohaEasyInstall' -Value $cmd -PropertyType String -Force | Out-Null
}

# ----------------------------------------------------------------------
# Debian distro
# ----------------------------------------------------------------------
# Pure: the Debian image of Microsoft's distribution list (the one that
# "wsl --install Debian" uses) for this processor: Url and Sha256.
function Get-KohaDebianImage {
    param([Parameter(Mandatory = $true)]$Manifest, [bool]$Arm = $false)
    if (-not $Manifest.PSObject.Properties['ModernDistributions']) { throw 'DistributionInfo.json has no ModernDistributions' }
    $debs = @($Manifest.ModernDistributions.Debian)
    $pick = @($debs | Where-Object { $_.PSObject.Properties['Default'] -and $_.Default }) + $debs | Select-Object -First 1
    if ($null -eq $pick) { throw 'Debian is not in the WSL distribution list' }
    $key = 'Amd64Url'
    if ($Arm) { $key = 'Arm64Url' }
    $img = $pick.$key
    $sha = ([string]$img.Sha256) -replace '^0x', ''
    return [pscustomobject]@{ Name = $pick.Name; Url = [string]$img.Url; Sha256 = $sha.ToUpperInvariant() }
}

function Get-KohaDistributionManifest { return (Invoke-RestMethod -Uri $script:ManifestUrl -UseBasicParsing) }

# curl.exe (built into Windows 10 1803 and later) first: download servers
# that screen browsers answer PowerShell's "Mozilla/5.0 ... WindowsPowerShell"
# user agent with a check page instead of the file.
function Save-KohaDownload {
    param([string]$Url, [string]$Path)
    $curl = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'curl.exe')
    if (Test-Path -LiteralPath $curl) {
        & $curl -fsSL --retry 3 -A 'KohaEasyInstaller' -o $Path $Url 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { return }
        Write-KohaLog ('curl.exe exit {0} for {1}' -f $LASTEXITCODE, $Url) 'install'
    }
    $prev = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'   # the progress bar makes 5.1 downloads many times slower
    try { Invoke-WebRequest -Uri $Url -OutFile $Path -UseBasicParsing -UserAgent 'KohaEasyInstaller' } finally { $ProgressPreference = $prev }
}

# Debian as "koha" in C:\KohaEasy\wsl. First choice: WSL itself installs
# Debian from Microsoft's list and checks its hash ("wsl --install --name
# --location", WSL 2.4.4 and later). When that is not available, the image is
# downloaded here, its SHA-256 checked against the same list, and imported.
function New-KohaDistro {
    param([bool]$Arm = $false)
    if (Test-KohaDistroInstalled) { return 'exists' }
    $name = (Get-KohaConfig).Distro
    $dir = Get-KohaPath Wsl
    $r = Invoke-KohaWsl -Arguments @('--install', 'Debian', '--name', $name, '--location', $dir, '--no-launch', '--web-download')
    if ($r.ExitCode -eq 0 -and (Test-KohaDistroInstalled)) { return 'installed' }
    Write-KohaLog ('wsl --install Debian did not work (exit {0}), downloading the image: {1}' -f $r.ExitCode, $r.Output) 'install'

    $img = Get-KohaDebianImage -Manifest (Get-KohaDistributionManifest) -Arm $Arm
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    # A disk left behind would block the import. The distro is not registered,
    # so nothing uses it, but it is set aside rather than deleted: it could
    # hold a library's data.
    $old = [System.IO.Path]::Combine($dir, 'ext4.vhdx')
    if (Test-Path -LiteralPath $old) {
        Move-Item -LiteralPath $old -Destination ('{0}.{1}.bak' -f $old, (Get-Date -Format 'yyyyMMdd-HHmmss')) -Force
    }
    $file = [System.IO.Path]::Combine($dir, 'debian-rootfs.tar.gz')
    Save-KohaDownload -Url $img.Url -Path $file
    try {
        $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToUpperInvariant()
        if ($img.Sha256 -and $hash -ne $img.Sha256) {
            $head = ''
            try { $head = (Get-Content -LiteralPath $file -TotalCount 1 -ErrorAction Stop | Out-String).Trim() } catch { }
            if ($head.Length -gt 120) { $head = $head.Substring(0, 120) }
            Write-KohaLog ('Debian image SHA-256 {0}, expected {1}, size {2}, from {3}, starts with: {4}' -f $hash, $img.Sha256, (Get-Item -LiteralPath $file).Length, $img.Url, $head) 'install'
            throw ((T 'The downloaded Debian image is damaged (SHA-256 does not match). Run the installer again.'))
        }
        $r = Invoke-KohaWsl -Arguments @('--import', $name, $dir, $file, '--version', '2')
        if ($r.ExitCode -ne 0) { throw ('wsl --import: ' + $r.Output) }
    } finally {
        Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue
    }
    return 'imported'
}

# The koha distro must still be registered when a later phase runs.
# When WSL no longer knows it, its disk is registered again in place
# (wsl --import-in-place), so Debian, its settings and any Koha data come
# back; without a disk, the install goes back to the Debian phase.
#   ok | reattached | missing
function Restore-KohaDistro {
    if (Test-KohaDistroInstalled) { return 'ok' }
    # A second, direct check: never act on a list that failed to parse.
    $probe = Invoke-KohaLinux -Command @('true')
    if ($probe.ExitCode -eq 0) { return 'ok' }
    $name = (Get-KohaConfig).Distro
    $list = Invoke-KohaWsl -Arguments @('--list', '--verbose')
    Write-KohaLog ('distro {0} is not registered: {1} | wsl --list --verbose: {2}' -f $name, $probe.Output, $list.Output) 'install'
    $vhd = [System.IO.Path]::Combine((Get-KohaPath Wsl), 'ext4.vhdx')
    if (Test-Path -LiteralPath $vhd) {
        $r = Invoke-KohaWsl -Arguments @('--import-in-place', $name, $vhd)
        if ($r.ExitCode -eq 0 -and (Test-KohaDistroInstalled)) {
            Write-KohaLog ('distro {0} registered again from {1}' -f $name, $vhd) 'install'
            return 'reattached'
        }
        Write-KohaLog ('wsl --import-in-place failed (exit {0}): {1}' -f $r.ExitCode, $r.Output) 'install'
    }
    return 'missing'
}

# ----------------------------------------------------------------------
# systemd and WSL settings
# ----------------------------------------------------------------------
# Pure: sets Key=Value in [Section] of an INI text such as /etc/wsl.conf,
# keeping every other section, key and comment as it was.
function Set-KohaIniValue {
    param([AllowEmptyString()][string]$Text, [string]$Section, [string]$Key, [string]$Value)
    $lines = New-Object System.Collections.ArrayList
    if ($Text) { foreach ($l in ($Text -split "`r?`n")) { [void]$lines.Add($l) } }
    while ($lines.Count -gt 0 -and $lines[$lines.Count - 1] -eq '') { $lines.RemoveAt($lines.Count - 1) }
    $start = -1; $end = $lines.Count
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^\s*\[(.+)\]\s*$') {
            if ($start -ge 0) { $end = $i; break }
            if ($Matches[1].Trim() -ieq $Section) { $start = $i }
        }
    }
    $entry = '{0}={1}' -f $Key, $Value
    if ($start -lt 0) {
        if ($lines.Count -gt 0) { [void]$lines.Add('') }
        [void]$lines.Add('[' + $Section + ']')
        [void]$lines.Add($entry)
    } else {
        $found = $false
        for ($i = $start + 1; $i -lt $end; $i++) {
            if ($lines[$i] -match '^\s*([A-Za-z0-9_.]+)\s*=' -and $Matches[1] -ieq $Key) { $lines[$i] = $entry; $found = $true; break }
        }
        if (-not $found) {
            $insert = $end
            while ($insert -gt $start + 1 -and $lines[$insert - 1].Trim() -eq '') { $insert-- }
            $lines.Insert($insert, $entry)
        }
    }
    return (($lines -join "`n") + "`n")
}

# /etc/wsl.conf: systemd, the Debian user chosen at the start as the default
# user of "wsl -d koha", no Windows folders in Linux's PATH. Anything else
# already there (the panel's [time] section, for one) is kept.
function Get-KohaWslConf {
    param([AllowEmptyString()][string]$Existing = '', [string]$User = 'root')
    $t = $Existing
    if (-not $t -or -not $t.Trim()) { $t = '# Written by Koha Easy Installer for Windows.' }
    $t = Set-KohaIniValue $t 'boot' 'systemd' 'true'
    $t = Set-KohaIniValue $t 'user' 'default' $User
    $t = Set-KohaIniValue $t 'interop' 'appendWindowsPath' 'false'
    return $t
}

# Pure: adds the keys Koha needs to the user's .wslconfig without changing
# anything the user already set. vmIdleTimeout=-1 keeps WSL running while
# Koha waits for readers. On Windows 11 22H2+ (build 22621): networking
# mirrored, so other PCs of the library reach Koha by this PC's address,
# and [experimental] hostAddressLoopback, so this PC reaches Koha by that
# address too (the library network test goes that way).
function Merge-KohaWslConfig {
    param([AllowEmptyString()][string]$Text, [int]$Build)
    $want = [ordered]@{ wsl2 = [ordered]@{ vmIdleTimeout = '-1' } }
    if ($Build -ge 22621) {
        $want.wsl2['networkingMode'] = 'mirrored'
        $want['experimental'] = [ordered]@{ hostAddressLoopback = 'true' }
    }
    $lines = New-Object System.Collections.ArrayList
    if ($Text) { foreach ($l in ($Text -split "`r?`n")) { [void]$lines.Add($l) } }
    while ($lines.Count -gt 0 -and $lines[$lines.Count - 1] -eq '') { $lines.RemoveAt($lines.Count - 1) }
    foreach ($section in $want.Keys) {
        $start = -1; $end = $lines.Count
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match '^\s*\[(.+)\]\s*$') {
                if ($start -ge 0) { $end = $i; break }
                if ($Matches[1].Trim() -ieq $section) { $start = $i }
            }
        }
        if ($start -lt 0) {
            if ($lines.Count -gt 0) { [void]$lines.Add('') }
            [void]$lines.Add('[' + $section + ']')
            $start = $lines.Count - 1; $end = $lines.Count
        }
        $present = @{}
        for ($i = $start + 1; $i -lt $end; $i++) {
            if ($lines[$i] -match '^\s*([A-Za-z0-9_.]+)\s*=') { $present[$Matches[1].ToLowerInvariant()] = $true }
        }
        $insert = $end
        while ($insert -gt $start + 1 -and $lines[$insert - 1].Trim() -eq '') { $insert-- }
        foreach ($k in $want[$section].Keys) {
            if (-not $present.ContainsKey($k.ToLowerInvariant())) {
                $lines.Insert($insert, ('{0}={1}' -f $k, $want[$section][$k]))
                $insert++
            }
        }
    }
    return (($lines -join "`r`n") + "`r`n")
}

function Update-KohaWslConfig {
    param([int]$Build = [Environment]::OSVersion.Version.Build)
    if (-not $env:USERPROFILE) { return $false }
    $file = [System.IO.Path]::Combine([string]$env:USERPROFILE, '.wslconfig')
    $old = ''
    if (Test-Path -LiteralPath $file) { $old = [System.IO.File]::ReadAllText($file) }
    $new = Merge-KohaWslConfig -Text $old -Build $Build
    if ($new -eq $old) { return $false }
    if ($old) { Copy-Item -LiteralPath $file -Destination ($file + '.kohaeasy.bak') -Force }
    [System.IO.File]::WriteAllText($file, $new, (New-Object System.Text.UTF8Encoding($false)))
    return $true
}

# systemd must be PID 1 and done booting (running, or degraded: a unit
# failed but the system is up). Prints "pid1=<name> state=<state>"; exit 3
# when systemd is not PID 1, 4 when it is but still booting after 2 minutes.
$script:SystemdProbe = @'
p=$(cat /proc/1/comm 2>/dev/null)
if [ "$p" != systemd ]; then echo "pid1=$p"; exit 3; fi
s=$(timeout 120 systemctl is-system-running --wait 2>/dev/null)
echo "pid1=systemd state=$s"
case "$s" in running|degraded) exit 0 ;; esac
exit 4
'@

function Test-KohaSystemd {
    $r = Invoke-KohaLinuxScript -Script $script:SystemdProbe
    Write-KohaLog ('systemd check (exit {0}): {1}' -f $r.ExitCode, ([string]$r.Output).Trim()) 'install'
    if ($r.ExitCode -eq 4 -and $r.Output -match 'pid1=systemd') {
        Write-KohaLog 'systemd is PID 1 but still booting after 2 minutes; carrying on' 'install'
        return $true
    }
    return ($r.ExitCode -eq 0)
}

function Wait-KohaDistroStopped {
    param([int]$Seconds = 30)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-KohaDistroRunning)) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

# The restart that makes /etc/wsl.conf (and .wslconfig) take effect. WSL
# reads wsl.conf only when the distro boots, and a command sent right after
# "wsl --terminate" can still land in the old instance. So: stop Koha's
# services and terminate (or shut all of WSL down when .wslconfig changed)
# through Stop-KohaDebianGracefully, wait until WSL lists the
# distro as stopped, give WSL its 8 seconds, boot it again and wait until
# systemd has finished starting. Nothing else runs in Debian before that.
function Restart-KohaDistro {
    param([switch]$Shutdown, [int]$SettleSeconds = 8)
    Stop-KohaDebianGracefully -Shutdown:$Shutdown | Out-Null
    if (-not (Wait-KohaDistroStopped)) {
        Write-KohaLog 'the distro was still running 30 s after --terminate; shutting WSL down' 'install'
        Invoke-KohaWsl -Arguments @('--shutdown') | Out-Null
        Wait-KohaDistroStopped | Out-Null
    }
    Start-Sleep -Seconds $SettleSeconds
    return (Test-KohaSystemd)
}

# /etc/wsl.conf with systemd and the default user, keeping everything else.
# WSL reads it when Debian starts.
function Write-KohaWslConf {
    param([string]$User = 'root')
    $cur = Invoke-KohaLinux -Command @('cat', '/etc/wsl.conf')
    $existing = ''
    if ($cur.ExitCode -eq 0) { $existing = [string]$cur.Output }
    $r = Invoke-KohaLinuxScript -Script "tr -d '\r' > /etc/wsl.conf" -InputText (Get-KohaWslConf -Existing $existing -User $User)
    if ($r.ExitCode -ne 0) { throw ('wsl.conf: ' + $r.Output) }
}

function Set-KohaDistroConfig {
    param([string]$User = 'root')
    Write-KohaWslConf -User $User
    $changed = Update-KohaWslConfig
    if ($changed) {
        # .wslconfig is read when the WSL virtual machine starts.
        Write-KohaStep (T 'Restarting WSL to apply the settings (other Linux windows will close).') 'warn'
    }
    Write-KohaStep (T 'Restarting Debian so that systemd takes over (up to 2 minutes)...')
    if (Restart-KohaDistro -Shutdown:$changed) { return $true }
    # Once more, with the whole of WSL restarted.
    Write-KohaLog 'systemd not running after the first restart; restarting WSL' 'install'
    return (Restart-KohaDistro -Shutdown)
}

# ----------------------------------------------------------------------
# The Debian user (asked first, before anything is installed)
# ----------------------------------------------------------------------
# Names Debian or Koha's packages already use.
$script:ReservedUsers = @('root', 'daemon', 'bin', 'sys', 'sync', 'games', 'man', 'lp', 'mail', 'news', 'uucp', 'proxy',
    'www-data', 'backup', 'list', 'irc', 'gnats', 'nobody', 'systemd-network', 'systemd-resolve', 'systemd-timesync',
    'messagebus', 'sshd', 'mysql', 'memcache', 'rabbitmq', 'postfix', 'koha', 'library-koha', 'sudo', 'admin', 'staff', 'users')

# Pure: a valid Debian user name from the Windows one (Joao.Silva -> joaosilva).
function ConvertTo-KohaLinuxUserName {
    param([string]$Name)
    $n = ([string]$Name).ToLowerInvariant().Normalize([Text.NormalizationForm]::FormD)
    $n = $n -replace '\p{Mn}', ''
    $n = $n -replace '[^a-z0-9_-]', ''
    $n = $n -replace '^[^a-z_]+', ''
    if ($n.Length -gt 32) { $n = $n.Substring(0, 32) }
    if (-not $n -or $script:ReservedUsers -contains $n) { $n = 'librarian' }
    return $n
}

# '' when the name can be used, otherwise why not (translated).
function Test-KohaLinuxUserName {
    param([string]$Name)
    if ([string]$Name -cnotmatch '^[a-z_][a-z0-9_-]{0,31}$') { return (T 'Use lowercase letters, digits, - and _, starting with a letter, up to 32 characters.') }
    if ($script:ReservedUsers -contains $Name) { return (T 'Debian or Koha already uses that name. Choose another.') }
    return ''
}

function Test-KohaLinuxPassword {
    param([string]$Password)
    if ([string]$Password -match '[\x00-\x1f\x7f]') { return (T 'The password cannot contain control characters.') }
    if (([string]$Password).Length -lt 8) { return (T 'The password needs at least 8 characters.') }
    return ''
}

function ConvertFrom-KohaSecureString {
    param([System.Security.SecureString]$Secure)
    if ($null -eq $Secure) { return '' }
    $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

# Asked in this window before WSL, Debian or any package is installed. The
# password stays in memory only: it is never written to state.json or to a
# log, and after a Windows restart it is asked again.
function Read-KohaLinuxAccount {
    param([string]$Default = (ConvertTo-KohaLinuxUserName $env:USERNAME))
    Write-Host ''
    Write-KohaStep (T 'First, choose a user name and password for Debian, the Linux system that runs Koha on this PC. You will use them to open Debian and to run commands with sudo. They are not the login of the Koha staff interface.')
    while ($true) {
        $u = Read-Host ((T 'Debian user name [{0}]') -f $Default)
        if ([string]::IsNullOrWhiteSpace($u)) { $u = $Default }
        $u = $u.Trim()
        $why = Test-KohaLinuxUserName $u
        if (-not $why) { break }
        Write-KohaStep $why 'warn'
    }
    while ($true) {
        $p1 = ConvertFrom-KohaSecureString (Read-Host -AsSecureString (T 'Password (at least 8 characters)'))
        $why = Test-KohaLinuxPassword $p1
        if ($why) { Write-KohaStep $why 'warn'; continue }
        $p2 = ConvertFrom-KohaSecureString (Read-Host -AsSecureString (T 'Type the password again'))
        if ($p1 -cne $p2) { Write-KohaStep (T 'The passwords do not match. Try again.') 'warn'; continue }
        break
    }
    return [pscustomobject]@{ User = $u; Password = $p1 }
}

# Creates the user (or sets the password of one already there) with sudo
# rights. Only the name is on the script; the password crosses on stdin, in
# base64 so that no Windows code page can change a character of it.
function New-KohaLinuxUser {
    param([Parameter(Mandatory = $true)][string]$User, [Parameter(Mandatory = $true)][string]$Password)
    $why = Test-KohaLinuxUserName $User
    if ($why) { throw $why }
    $sh = @(
        'set -e'
        ("u='{0}'" -f $User)
        '# Read first: nothing after this may eat stdin.'
        'IFS= read -r b || true'
        'p=$(printf %s "$b" | tr -d "\r" | base64 -d)'
        '[ ${#p} -ge 8 ]'
        'if ! command -v sudo >/dev/null 2>&1; then'
        '  DEBIAN_FRONTEND=noninteractive apt-get update -qq </dev/null >/dev/null 2>&1 || true'
        '  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq sudo </dev/null >/dev/null 2>&1 || echo "sudo not installed yet"'
        'fi'
        'id "$u" >/dev/null 2>&1 || useradd -m -s /bin/bash "$u"'
        'usermod -aG sudo "$u"'
        'printf "%s:%s\n" "$u" "$p" | chpasswd'
    ) -join "`n"
    $b64 = [Convert]::ToBase64String((New-Object System.Text.UTF8Encoding($false)).GetBytes($Password))
    $r = Invoke-KohaLinuxScript -Script $sh -InputText $b64
    if ($r.ExitCode -ne 0) { throw ((T 'The Debian user could not be created: {0}') -f $r.Output) }
    # A Debian installed by "wsl --install" still has its first-start
    # questions pending (RunOOBE): the user now exists, so they are done.
    $e = Get-KohaLxssEntry
    if ($null -ne $e) {
        $p = Get-ItemProperty -LiteralPath $e.PSPath -ErrorAction SilentlyContinue
        if ($null -ne $p -and $p.PSObject.Properties['RunOOBE']) { Set-ItemProperty -LiteralPath $e.PSPath -Name RunOOBE -Value 0 -ErrorAction SilentlyContinue }
    }
    Write-KohaLog ('Debian user {0} ready' -f $User) 'install'
}

# Whether Debian has this user. WSL opens Debian as the user wsl.conf names;
# when that user is missing, every start prints "getpwnam(...) failed" and
# falls back to another account.
function Test-KohaLinuxUserExists {
    param([string]$User)
    if (-not $User -or $User -eq 'root') { return $true }
    if (Test-KohaLinuxUserName $User) { return $false }
    return ((Invoke-KohaLinuxScript -Script ("id -u '{0}' >/dev/null 2>&1" -f $User)).ExitCode -eq 0)
}

# ----------------------------------------------------------------------
# The old name of the distro
# ----------------------------------------------------------------------
# Installs before this version named the distro "KohaEasy". WSL keeps the
# name only in its registration (HKCU\...\Lxss\{guid}\DistributionName):
# changing it there, with WSL stopped, keeps Debian, its disk and Koha as
# they were. When WSL still answers with the old name afterwards (it read
# its list before the change), a Windows restart finishes the rename.
#   none | renamed | restart | kept (both names exist: nothing is touched)
function Rename-KohaLegacyDistro {
    $new = (Get-KohaConfig).Distro
    $installed = @(Get-KohaInstalledDistros)
    foreach ($old in @((Get-KohaConfig).OldDistros)) {
        if ($installed -notcontains $old) { continue }
        if ($installed -contains $new) {
            Write-KohaLog ('both {0} and {1} exist; {0} left as it is' -f $old, $new) 'install'
            return 'kept'
        }
        $e = Get-KohaLxssEntry -Name $old
        if ($null -eq $e) { return 'none' }
        try { Stop-KohaKeepAlive } catch { }
        Stop-KohaDebianGracefully -Distro $old -Shutdown | Out-Null
        Set-ItemProperty -LiteralPath $e.PSPath -Name DistributionName -Value $new
        if (@(Get-KohaInstalledDistros) -notcontains $new) {
            Write-KohaLog ('distro {0} renamed to {1} in the registry; WSL still lists the old name until Windows restarts' -f $old, $new) 'install'
            return 'restart'
        }
        Write-KohaLog ('distro {0} renamed to {1}' -f $old, $new) 'install'
        return 'renamed'
    }
    return 'none'
}

# ----------------------------------------------------------------------
# Koha (the panel inside Debian)
# ----------------------------------------------------------------------
function ConvertTo-KohaWslPath {
    param([string]$Path)
    if ($Path -match '^([A-Za-z]):[\\/](.*)$') { return '/mnt/' + $Matches[1].ToLowerInvariant() + '/' + ($Matches[2] -replace '[\\/]', '/') }
    return $Path
}

# Copies the installer, its dictionaries and the new panel into Debian and checks the
# SHA-256 again on the Linux side.
function Copy-KohaPanelIntoDistro {
    $src = ConvertTo-KohaWslPath (Get-KohaPath Bin)
    $sh = @(
        'set -e'
        ('d=''{0}''; s=''{1}''' -f $script:DistroDir, $src)
        'mkdir -p "$d/lang"'
        'cp "$s/installer" "$s/installer.sha256" "$d/"'
        'cp "$s"/lang/*.cache "$d/lang/" 2>/dev/null || true'
        '# The new panel (Python/Textual), opened by the installer when it can.'
        'rm -rf "$d/panel"'
        'if [ -d "$s/panel" ]; then cp -r "$s/panel" "$d/panel"; fi'
        'cd "$d"'
        'sha256sum -c installer.sha256'
        '# The panel launcher the Windows tools call: the newest of the copy from'
        '# Windows and the one "Update this panel" installs as config.sh.'
        ('l=''{0}''' -f $script:LauncherPath)
        'cat > "$l.tmp" <<EOF'
        '#!/bin/sh'
        '# Written by Koha Easy Installer for Windows.'
        'p=''$d/installer''; c=/usr/local/bin/config.sh'
        'if [ -x "\$c" ] && [ "\$c" -nt "\$p" ]; then exec "\$c" "\$@"; fi'
        'cd ''$d'' && exec bash ./installer "\$@"'
        'EOF'
        'chmod 755 "$l.tmp" && mv -f "$l.tmp" "$l"'
    ) -join "`n"
    $r = Invoke-KohaLinuxScript -Script $sh
    if ($r.ExitCode -ne 0) { throw ('copy: ' + $r.Output) }
    if (-not (Install-KohaWindowScript)) { throw ('copy: ' + (Get-KohaConfig).WindowPath + ' not written') }
}

# The data-safety settings inside Debian (installer, install_data_safety:
# the clean-stop guard...): the panel installs them with Koha; an existing
# Koha gets them, or their newer version, here, without opening the panel.
function Install-KohaDataSafety {
    $r = Invoke-KohaLinux -Command @($script:LauncherPath, '--install-data-safety')
    Write-KohaLog ('data-safety settings (exit {0}) {1}' -f $r.ExitCode, ([string]$r.Output).Trim()) 'install'
    return ($r.ExitCode -eq 0)
}

# Koha counts as installed only when option 1 went all the way: the
# instance exists, the koha-common package is fully configured ("ii": an
# install stopped inside its setup leaves it half-configured) and the panel
# wrote the credentials file, its last step.
$script:InstalledProbe = @'
test -f /etc/koha/sites/library/koha-conf.xml || exit 1
test -f /root/koha_credentials.txt || exit 2
dpkg-query -W -f='${db:Status-Abbrev}' koha-common 2>/dev/null | grep -q '^ii' || exit 3
exit 0
'@

$script:InstalledCheck = 0
function Test-KohaInstalledInDistro {
    $r = Invoke-KohaLinuxScript -Script $script:InstalledProbe
    $script:InstalledCheck = [int]$r.ExitCode
    if ($r.ExitCode -ne 0) { Write-KohaLog ('Koha not fully installed (check {0})' -f $r.ExitCode) 'install' }
    return ($r.ExitCode -eq 0)
}

# Which of the three checks above failed, said in words.
function Show-KohaInstalledCheck {
    switch ($script:InstalledCheck) {
        1 { $what = T 'The Koha instance "library" was not created (/etc/koha/sites/library/koha-conf.xml is missing).' }
        2 { $what = T 'Option 1 did not reach its last step: /root/koha_credentials.txt is missing.' }
        3 { $what = T 'The koha-common package is not fully configured (its setup stopped half-way).' }
        default { $what = (T 'Debian could not be checked (exit code {0}).') -f $script:InstalledCheck }
    }
    Write-KohaStep $what 'warn'
}

# The ways into Koha on Windows: KohaEasy.exe, the tasks, the Koha icon
# (desktop and Start menu), the tray at sign-in and the tray itself. Made as
# soon as Debian is ready, before Koha is installed.
function Install-KohaEntryPoints {
    $mode = [string](Get-KohaState).autostart
    if (@('logon', 'manual') -notcontains $mode) { $mode = 'logon' }
    Invoke-KohaSafeStep { Install-KohaLauncherStep }
    Invoke-KohaSafeStep { Register-KohaTasks -Autostart $mode }
    Invoke-KohaSafeStep { Install-KohaShortcuts }
    Invoke-KohaSafeStep { Register-KohaUninstallEntry }
    Invoke-KohaSafeStep { Start-KohaTrayChecked }
}

# Koha did not answer: what Debian reports, the diagnostics .zip on the
# desktop, and the control panel offered to repair it.
function Show-KohaStartProblem {
    param([switch]$NonInteractive)
    Write-KohaStep (T 'Koha did not start. Open Koha - Status, or export the diagnostics from the tray menu.') 'warn'
    Write-Host ''
    Write-Host (T 'What Debian reports (copy these lines when you ask for help):') -ForegroundColor Yellow
    foreach ($l in Get-KohaQuickCheck) {
        Write-Host ('    ' + $l)
        Write-KohaLog ('quick check: ' + $l) 'install'
    }
    Write-Host ''
    try {
        $zip = Export-KohaDiagnostics
        Write-KohaStep ((T 'Diagnostics saved on the desktop: {0}') -f $zip) 'ok'
    } catch {
        Write-KohaStep ((T 'The diagnostics could not be saved: {0}') -f $_.Exception.Message) 'warn'
    }
    if ($NonInteractive) { return }
    if (Read-KohaYesNo (T 'Open the control panel now? Option 7 (Diagnostics & maintenance), then 6 (Restart / repair Koha services), usually brings Koha back.')) {
        Invoke-KohaPanel | Out-Null
        Write-KohaStep (T 'Starting Koha (up to 3 minutes)...')
        if ((Start-Koha -Trigger user -Wait) -eq 'ready') {
            Write-KohaStep ((T 'Done! Staff interface: {0}  Public catalog: {1}') -f (Get-KohaConfig).StaffUrl, (Get-KohaConfig).OpacUrl) 'ok'
        } else {
            Write-KohaStep (T 'Koha did not start. Open Koha - Status, or export the diagnostics from the tray menu.') 'warn'
        }
    }
}

# The panel runs in this window: the librarian picks the language and
# "1 - Install Koha server", then leaves the panel with Exit. Start-Process
# -NoNewWindow hands it the console itself; "& wsl.exe" here would send its
# screens into Install-Koha's return value, and the panel could not draw.
# koha-window runs it, so a process the panel left holding the terminal
# cannot keep wsl.exe (and this installer) waiting after Exit.
# The console is switched to UTF-8, and the panel is told whether this is
# Windows Terminal (emoji) or the classic console (plain symbols), through
# WSLENV, the list of variables WSL passes into Linux.
function Invoke-KohaPanel {
    $a = '-d {0} -u root --cd {1} -- {2} bash ./installer' -f (Get-KohaConfig).Distro, $script:DistroDir, (Get-KohaConfig).WindowPath
    $saved = @{ WSLENV = $env:WSLENV; KEI_PLAIN_GLYPHS = $env:KEI_PLAIN_GLYPHS }
    $enc = $null
    try { $enc = [Console]::OutputEncoding; [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
    try {
        $env:KEI_PLAIN_GLYPHS = Get-KohaGlyphMode
        $env:WSLENV = Add-KohaWslEnv -Current $env:WSLENV -Name 'KEI_PLAIN_GLYPHS'
        $p = Start-Process -FilePath 'wsl.exe' -ArgumentList $a -NoNewWindow -Wait -PassThru
        return [int]$p.ExitCode
    } finally {
        $env:WSLENV = $saved.WSLENV
        $env:KEI_PLAIN_GLYPHS = $saved.KEI_PLAIN_GLYPHS
        if ($null -ne $enc) { try { [Console]::OutputEncoding = $enc } catch { } }
    }
}

# 1 = plain symbols (the classic console has no emoji font), 0 = emoji.
function Get-KohaGlyphMode {
    if ($env:WT_SESSION) { return '0' }
    return '1'
}

# Pure: WSLENV with Name added once (entries are separated by colons).
function Add-KohaWslEnv {
    param([AllowEmptyString()][string]$Current, [string]$Name)
    $items = @(([string]$Current) -split ':' | Where-Object { $_ })
    if (@($items | ForEach-Object { ($_ -split '/')[0] }) -contains $Name) { return $Current }
    return (@($items) + $Name) -join ':'
}

# Other PCs of the library reach Koha by this PC's address: one UAC prompt
# for the firewall rules (and, under NAT, the port forwarding task).
function Enable-KohaLanAccess {
    $ps = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    try {
        $code = Start-KohaElevated -FilePath $ps -Arguments ('-NoProfile -ExecutionPolicy Bypass -File "{0}" SetupNetwork' -f (Get-KohaScriptPath))
        return ([int]$code -eq 0)
    } catch {
        Write-KohaLog ('network setup not run: ' + $_.Exception.Message) 'install'
        return $false
    }
}

# ----------------------------------------------------------------------
# The whole flow
# ----------------------------------------------------------------------
# Yes unless the answer starts with n (no, não, non, nein, nee, nej, nie, net...).
function Read-KohaYesNo {
    param([string]$Question)
    $a = Read-Host ('{0} [Y/n]' -f $Question)
    if ([string]::IsNullOrWhiteSpace($a)) { return $true }
    return -not ($a.Trim().ToLowerInvariant().StartsWith('n') -or $a.Trim().ToLowerInvariant().StartsWith([string][char]0x43D))
}

# Returns 0 when done, 3 when Windows must restart first, 1 on a failure.
function Install-Koha {
    param([hashtable]$Facts, [switch]$NonInteractive, $Account)
    $state = Get-KohaState
    $phase = [string]$state['phase']
    if (-not $phase -or $script:Phases -notcontains $phase) { $phase = 'checks' }
    Write-Host ''
    Write-Host (T 'Koha Easy Installer for Windows') -ForegroundColor Green
    Write-Host ''

    if (-not (Test-KohaPhaseDone 'checks' $phase)) {
        Write-KohaStep (T 'Checking this computer...')
        if (-not $Facts) { $Facts = Get-KohaHostFacts }
        $rows = Get-KohaPreflight -Facts $Facts
        foreach ($r in $rows) { Write-KohaStep $r.Text $(if ($r.Level -eq 'ok') { 'ok' } else { $r.Level }) }
        if (@($rows | Where-Object { $_.Level -eq 'error' }).Count -gt 0) {
            Write-KohaStep (T 'This computer cannot run Koha yet. Fix the items marked X and run the installer again.') 'error'
            return 1
        }
        Set-KohaState @{ phase = 'wsl' } | Out-Null; $phase = 'wsl'
    }

    # The Debian user comes first, before WSL, Debian or any package is
    # installed. An install made before this question existed is asked too.
    $account = $Account
    if ($null -eq $account -and $phase -ne 'done' -and -not [string]$state['linuxUser'] -and -not $NonInteractive) {
        $account = Read-KohaLinuxAccount
    }

    # Installs made before this version called the distro KohaEasy.
    $renamed = 'none'
    if (Test-KohaPhaseDone 'wsl' $phase) { $renamed = Rename-KohaLegacyDistro }
    if ($renamed -eq 'restart') {
        Register-KohaResume
        Write-KohaStep (T 'Windows must restart to finish renaming the Debian of Koha. After the restart, the installer continues by itself when you sign in.') 'warn'
        return 3
    }

    if (-not (Test-KohaPhaseDone 'wsl' $phase)) {
        if (-not (Test-KohaWslReady)) {
            Write-KohaStep (T 'Installing WSL 2 (Windows asks for permission once)...')
            Install-KohaWslPlatform
            if (-not (Test-KohaWslReady)) {
                Register-KohaResume
                Write-KohaStep (T 'Windows must restart to finish installing WSL. After the restart, the installer continues by itself when you sign in.') 'warn'
                return 3
            }
        }
        Write-KohaStep (T 'WSL 2 is ready.') 'ok'
        Set-KohaState @{ phase = 'distro' } | Out-Null; $phase = 'distro'
    }

    # Debian must still be there for the phases after it (it can go missing
    # between two runs); when it cannot be brought back, install it again.
    if ((Test-KohaPhaseDone 'distro' $phase) -and (Restore-KohaDistro) -eq 'missing') {
        Set-KohaState @{ phase = 'distro' } | Out-Null; $phase = 'distro'
    }

    # After the Koha step, the panel inside Debian is refreshed on every run
    # (a new version, the koha-panel launcher), and an install of Koha that
    # stopped half-way sends the flow back to the Koha step.
    $wasDone = ($phase -eq 'done')
    if (Test-KohaPhaseDone 'koha' $phase) {
        Copy-KohaPanelIntoDistro
        if (-not (Test-KohaInstalledInDistro)) {
            Write-KohaStep (T 'Koha was not installed all the way. The control panel opens again to finish it.') 'warn'
            Show-KohaInstalledCheck
            Set-KohaState @{ phase = 'koha' } | Out-Null; $phase = 'koha'
        } else {
            Invoke-KohaSafeStep { Install-KohaDataSafety | Out-Null }
        }
    }

    if (-not (Test-KohaPhaseDone 'distro' $phase)) {
        if (Test-KohaDistroInstalled) {
            # Never installed over: this Debian may already hold Koha.
            Write-KohaLog 'distro phase: Debian is already registered, nothing downloaded' 'install'
            Write-KohaStep (T 'Debian is already installed; keeping it and its data.') 'ok'
        } else {
            Write-KohaStep (T 'Downloading and installing Debian (a few minutes)...')
            if (-not $Facts) { $Facts = Get-KohaHostFacts }
            New-KohaDistro -Arm ([bool]$Facts.Arm) | Out-Null
            Write-KohaStep (T 'Debian is installed.') 'ok'
        }
        Set-KohaState @{ phase = 'systemd' } | Out-Null; $phase = 'systemd'
    }

    # The Debian user that wsl.conf names must exist. A Debian installed again
    # (it went missing between two runs) no longer has it, and its password
    # was never saved, so it is asked again.
    $savedUser = [string](Get-KohaState)['linuxUser']
    if ($null -eq $account -and $savedUser -and (Test-KohaPhaseDone 'distro' $phase) -and -not (Test-KohaLinuxUserExists $savedUser)) {
        Write-KohaLog ('Debian user {0} is missing' -f $savedUser) 'install'
        if (-not $NonInteractive) {
            Write-KohaStep ((T 'The Debian user {0} is missing (Debian was installed again), so WSL cannot open Debian with it. Choose its password again.') -f $savedUser) 'warn'
            $account = Read-KohaLinuxAccount -Default $savedUser
        }
    }

    # Debian already runs systemd: create the user, point wsl.conf at it and
    # restart Debian, so WSL opens it with that user from now on.
    if ($null -ne $account -and (Test-KohaPhaseDone 'systemd' $phase)) {
        New-KohaLinuxUser -User $account.User -Password $account.Password
        Set-KohaState @{ linuxUser = $account.User } | Out-Null
        Write-KohaStep ((T 'Debian user {0} created.') -f $account.User) 'ok'
        Write-KohaWslConf -User $account.User
        $account = $null
        Write-KohaStep (T 'Restarting Debian so that WSL opens it with this user...')
        Restart-KohaDistro | Out-Null
    }

    if (-not (Test-KohaPhaseDone 'systemd' $phase)) {
        $user = [string](Get-KohaState)['linuxUser']
        if ($null -ne $account) {
            New-KohaLinuxUser -User $account.User -Password $account.Password
            $user = $account.User
            $account = $null
            Set-KohaState @{ linuxUser = $user } | Out-Null
            Write-KohaStep ((T 'Debian user {0} created.') -f $user) 'ok'
        }
        if (-not $user) { $user = 'root' }
        Write-KohaStep (T 'Configuring Debian for Koha (systemd)...')
        if (-not (Set-KohaDistroConfig -User $user)) {
            Write-KohaStep (T 'systemd did not start in WSL. Update WSL with "wsl --update" and run the installer again.') 'error'
            return 1
        }
        Write-KohaStep (T 'Debian is ready for Koha.') 'ok'
        if (-not (Test-KohaPhaseDone 'systemd' $phase)) { Set-KohaState @{ phase = 'koha' } | Out-Null; $phase = 'koha' }
    }

    $entryDone = $false
    if (-not (Test-KohaPhaseDone 'koha' $phase)) {
        Copy-KohaPanelIntoDistro
        if (-not (Test-KohaInstalledInDistro)) {
            if ($NonInteractive) { return 1 }
            # The Koha icon, the tray and the tasks do not wait for Koha: an
            # install that stops here (Koha half-installed, the panel left
            # early) still leaves the librarian a way in, and the Koha window
            # says what is missing.
            Install-KohaEntryPoints
            $entryDone = $true
            Write-Host ''
            Write-KohaStep (T 'The Koha control panel opens now. Choose your language, then 1 - Install Koha server. When it finishes, leave the panel with Exit.')
            Read-Host (T 'Press Enter to continue') | Out-Null
            Invoke-KohaPanel | Out-Null
            Write-KohaStep (T 'Back in the Windows installer. Checking the installation...')
            if (-not (Test-KohaInstalledInDistro)) {
                Write-KohaStep (T 'Koha was not installed. Run the installer again to continue from here.') 'error'
                Show-KohaInstalledCheck
                return 1
            }
        }
        Write-KohaStep (T 'Koha is installed.') 'ok'
        Set-KohaState @{ phase = 'windows' } | Out-Null; $phase = 'windows'
    }

    if (-not (Test-KohaPhaseDone 'windows' $phase)) {
        $auto = $true
        if (-not $NonInteractive) { $auto = Read-KohaYesNo (T 'Start Koha automatically when you sign in to Windows?') }
        $mode = 'manual'
        if ($auto) { $mode = 'logon' }
        Set-KohaState @{ autostart = $mode; desired = 'running' } | Out-Null
        # One step that fails must not skip the others. KohaEasy.exe first:
        # the tasks and shortcuts start through it. Made already in this run
        # when Koha was installed in the panel just now (above).
        if (-not $entryDone) { Invoke-KohaSafeStep { Install-KohaLauncherStep } }
        Invoke-KohaSafeStep { Register-KohaTasks -Autostart $mode }
        if (-not $entryDone) {
            Invoke-KohaSafeStep { Install-KohaShortcuts }
            Invoke-KohaSafeStep { Register-KohaUninstallEntry }
            # The tray settles how Koha's tools start on this PC (KohaEasy.exe,
            # conhost, PowerShell) before the Koha network task and the
            # keep-alive task are started with it.
            Invoke-KohaSafeStep { Start-KohaTrayChecked }
        }
        Write-KohaStep (T 'Opening Koha to the other computers of the library network (Windows asks for permission once)...')
        $lan = $true
        if (-not $NonInteractive) { $lan = Enable-KohaLanAccess }
        if (-not $lan) { Write-KohaStep (T 'Koha opens only on this computer for now. Run the installer again to open it to the library network.') 'warn' }
        Write-KohaStep (T 'Starting Koha (up to 3 minutes)...')
        $r = Start-Koha -Trigger user -Wait
        $done = @{ phase = 'done'; lanAccess = $lan }
        if ($lan) { $done['lanSetup'] = (Get-KohaConfig).LanSetup }
        Set-KohaState $done | Out-Null
        Write-Host ''
        if ($r -eq 'ready') {
            Write-KohaStep ((T 'Done! Staff interface: {0}  Public catalog: {1}') -f (Get-KohaConfig).StaffUrl, (Get-KohaConfig).OpacUrl) 'ok'
            if ($lan) { Show-KohaLanCheck }
            Write-KohaStep (T 'The first-access user and password are in the control panel, option 2. Keep this computer on during opening hours.') 'ok'
            if (-not $NonInteractive) { Start-Process (Get-KohaConfig).StaffUrl }
        } else {
            Show-KohaStartProblem -NonInteractive:$NonInteractive
        }
    }
    # Running the installer again on a finished install also repairs: Koha is
    # started, and when it does not answer, the same help as above.
    $ready = $false
    if ($wasDone -and $phase -eq 'done' -and -not $NonInteractive) {
        # KohaEasy.exe, the tasks, the shortcuts, the tray at sign-in and the
        # tray itself of this version (older tasks started PowerShell with a
        # window of its own).
        Invoke-KohaSafeStep { Install-KohaLauncherStep }
        $outdated = Test-KohaKeepAliveOutdated
        Invoke-KohaSafeStep { Register-KohaTasks -Autostart ([string](Get-KohaState).autostart) }
        Invoke-KohaSafeStep { Install-KohaShortcuts }
        Invoke-KohaSafeStep { Register-KohaUninstallEntry }
        # .wslconfig settings of this version (hostAddressLoopback) take
        # effect when WSL starts again, and a keep-alive task still running
        # with an older version's action keeps its window: Koha is stopped
        # cleanly first, and started again below.
        if (Update-KohaWslConfig) {
            Write-KohaStep (T 'Restarting WSL to apply the new network settings (other Linux windows will close)...') 'warn'
            Stop-KohaDebianGracefully -SetStopped -Shutdown | Out-Null
        } elseif ($outdated) {
            Write-KohaStep (T 'Restarting Koha so it runs in the background with no window...')
            Stop-KohaDebianGracefully -SetStopped | Out-Null
        }
        Invoke-KohaSafeStep { Start-KohaTrayChecked }
        Write-KohaStep (T 'Starting Koha (up to 3 minutes)...')
        if ((Start-Koha -Trigger user -Wait) -eq 'ready') {
            $ready = $true
            Write-KohaStep ((T 'Done! Staff interface: {0}  Public catalog: {1}') -f (Get-KohaConfig).StaffUrl, (Get-KohaConfig).OpacUrl) 'ok'
        } else {
            Show-KohaStartProblem
        }
    }
    # The library network: a finished install whose step was refused, or
    # that predates it, is offered it again on every run; one set up by an
    # older version, whose task no longer matches how Koha's tools start
    # here, or whose firewall rules or task went missing, is set up again.
    if ($phase -eq 'done' -and -not $NonInteractive) {
        $lan = [bool](Get-KohaState)['lanAccess']
        $need = Get-KohaLanSetupNeed
        if ($need) {
            if ($need -eq 'open') {
                Write-KohaStep (T 'Opening Koha to the other computers of the library network (Windows asks for permission once)...')
            } else {
                Write-KohaStep (T 'Updating the library network settings (Windows asks for permission once)...')
            }
            if (Enable-KohaLanAccess) {
                Set-KohaState @{ lanAccess = $true; lanSetup = (Get-KohaConfig).LanSetup } | Out-Null
                $lan = $true
            } elseif (-not $lan) {
                Write-KohaStep (T 'Koha opens only on this computer for now. Run the installer again to open it to the library network.') 'warn'
            } else {
                Write-KohaStep (T 'The library network settings were not updated. Run the installer again and allow the Windows permission prompt.') 'warn'
            }
        }
        if ($lan -and $ready) { Show-KohaLanCheck }
    }
    if ($renamed -eq 'renamed' -and (Test-KohaPhaseDone 'windows' $phase)) {
        # The shortcuts of a finished install still name KohaEasy.
        New-KohaShortcuts | Out-Null
        Set-KohaDistroIcon | Out-Null
        if ((Get-KohaState).desired -eq 'running') { Start-Koha -Trigger user | Out-Null }
        Write-KohaStep ((T 'The Debian of Koha is now called {0} in WSL.') -f (Get-KohaConfig).Distro) 'ok'
    }
    return 0
}

function Start-KohaTray { Start-KohaHidden 'Tray' }

# KohaEasy.exe for this PC, with what it means for the librarian.
function Install-KohaLauncherStep {
    # Every run of the installer tries each hidden launch again, best first:
    # the tray check below falls back again where one still fails, so a PC
    # does not stay on a launch that shows a console after one bad start.
    $st = Get-KohaState
    if ($st.launcher -eq 'refused' -or $st.hiddenLaunch -ne 'conhost') {
        Write-KohaLog ('hidden launch reset for a new check (launcher {0}, hiddenLaunch {1})' -f $st.launcher, $st.hiddenLaunch) 'install'
        $reset = @{ hiddenLaunch = 'conhost' }
        if ($st.launcher -eq 'refused') { $reset.launcher = ''; $reset.launcherHash = '' }
        Set-KohaState $reset | Out-Null
    }
    $r = Install-KohaLauncher
    if ($r -eq 'built') { Write-KohaStep (T 'KohaEasy.exe is ready: Koha starts in the background with no windows.') 'ok' }
    if ($r -eq 'failed') { Write-KohaStep (T 'KohaEasy.exe could not be used on this PC; Koha starts through a hidden console instead.') 'warn' }
}

# The library network test, printed: what works, what to fix, and the
# addresses for the other computers.
function Show-KohaLanCheck {
    $check = Test-KohaLanAccess
    foreach ($l in @($check.Lines)) {
        $kind = 'ok'
        if ($l.Kind -eq 'warn') { $kind = 'warn' }
        Write-KohaStep $l.Text $kind
    }
}

# Runs one step of the Windows side; a failure is shown and logged, and the
# steps after it still run.
function Invoke-KohaSafeStep {
    param([scriptblock]$Step)
    try {
        & $Step
    } catch {
        Write-KohaLog ('step failed: {0} | {1}' -f $Step.ToString().Trim(), $_.Exception.Message) 'install'
        Write-KohaStep ((T 'This step did not work: {0}') -f $_.Exception.Message) 'warn'
    }
}

# The Koha icon on the desktop and in the Start menu (folder Koha), the
# other shortcuts, the tray at sign-in and the Koha icon on Debian's own
# entries. The desktop is the one Windows reports, so a desktop moved by
# OneDrive gets it too. Each part runs on its own: a sign-in entry Windows
# refuses no longer takes the shortcuts with it. What is said is checked on
# disk, with Windows' own reason when a shortcut is missing.
function Install-KohaShortcuts {
    param([string]$StartMenu = [System.IO.Path]::Combine([Environment]::GetFolderPath('Programs'), 'Koha'))
    Test-KohaLanguageMode | Out-Null
    $desktop = Get-KohaDesktopPath
    New-KohaShortcuts -StartMenu $StartMenu -Desktop $desktop | Out-Null
    $errors = @(Get-KohaShortcutErrors)
    try { Set-KohaTrayAtSignIn -Enabled $true } catch { Write-KohaLog ('tray at sign-in not set: ' + $_.Exception.Message) 'install' }
    try { Set-KohaDistroIcon | Out-Null } catch { Write-KohaLog ('Debian entries keep their icon: ' + $_.Exception.Message) 'install' }
    $place = Get-KohaIconPlace
    $reason = ($errors | Select-Object -First 1)
    if (-not $desktop) { $reason = 'Windows reported no desktop folder for this account' }
    if (-not $reason) { $reason = '?' }
    Write-KohaLog ('Koha icon: {0} (desktop {1}, Start menu {2})' -f $place, $desktop, $StartMenu) 'install'
    foreach ($e in $errors) { Write-KohaLog ('shortcut not created: ' + $e) 'install' }
    switch ($place) {
        'desktop' { Write-KohaStep ((T 'Shortcuts created in the Start menu (folder Koha) and on the desktop ({0}).') -f $desktop) 'ok' }
        'public' { Write-KohaStep ((T 'Your own desktop refused the Koha icon, so it is on the desktop of all users. Reason: {0}') -f $reason) 'warn' }
        'startmenu' { Write-KohaStep ((T 'The Koha icon could not be put on the desktop ({0}). Open Koha from the Start menu (folder Koha). Reason: {1}') -f $desktop, $reason) 'warn' }
        default { Write-KohaStep ((T 'The Koha shortcuts could not be created. Reason: {0}. The log is in C:\KohaEasy\logs.') -f $reason) 'error' }
    }
}

# PowerShell restricted by Windows (AppLocker, WDAC, Smart App Control:
# ConstrainedLanguage) cannot write shortcuts or show the tray. Said once,
# plainly, instead of failing later without a word. $true when it is fine.
function Test-KohaLanguageMode {
    param([string]$Mode = [string]$ExecutionContext.SessionState.LanguageMode)
    if ($Mode -eq 'FullLanguage') { return $true }
    Write-KohaLog ('PowerShell language mode is {0}' -f $Mode) 'install'
    Write-KohaStep ((T 'Windows restricts PowerShell on this PC ({0} mode), so the Koha icon and the Koha tray cannot work. Ask whoever manages this PC to allow the scripts in C:\KohaEasy.') -f $Mode) 'error'
    return $false
}

# Starts the tray and checks it is there. When KohaEasy.exe does not bring
# it up, the Koha tools go back to conhost --headless; when that does not
# either, to a plain hidden PowerShell for good. The tray at sign-in, the
# shortcuts and the tasks follow.
function Start-KohaTrayChecked {
    param([int]$WaitSeconds = 8)
    Restart-KohaTray
    Start-Sleep -Seconds $WaitSeconds
    if ((Get-KohaState).launcher -eq 'ok' -and -not (Test-KohaTrayRunning)) {
        Write-KohaLog 'the tray did not start through KohaEasy.exe; using the next hidden launch' 'install'
        Set-KohaState @{ launcher = 'refused' } | Out-Null
        Set-KohaTrayAtSignIn -Enabled $true
        New-KohaShortcuts | Out-Null
        try { Register-KohaTasks } catch { Write-KohaLog ('tasks not registered again: ' + $_.Exception.Message) 'install' }
        Start-KohaTray
        Start-Sleep -Seconds $WaitSeconds
    }
    if (@('nowscript', 'powershell') -notcontains (Get-KohaState).hiddenLaunch -and (Get-KohaWscriptPath) -and -not (Test-KohaTrayRunning)) {
        Write-KohaLog 'the tray did not start through wscript KohaEasy.Hidden.js; using conhost --headless' 'install'
        Set-KohaState @{ hiddenLaunch = 'nowscript' } | Out-Null
        Set-KohaTrayAtSignIn -Enabled $true
        New-KohaShortcuts | Out-Null
        try { Register-KohaTasks } catch { Write-KohaLog ('tasks not registered again: ' + $_.Exception.Message) 'install' }
        Start-KohaTray
        Start-Sleep -Seconds $WaitSeconds
    }
    if ((Get-KohaState).hiddenLaunch -ne 'powershell' -and -not (Test-KohaTrayRunning)) {
        Write-KohaLog 'the tray did not start through conhost --headless; using powershell -WindowStyle Hidden' 'install'
        Set-KohaState @{ hiddenLaunch = 'powershell' } | Out-Null
        Set-KohaTrayAtSignIn -Enabled $true
        New-KohaShortcuts | Out-Null
        try { Register-KohaTasks } catch { Write-KohaLog ('tasks not registered again: ' + $_.Exception.Message) 'install' }
        Start-KohaTray
        Start-Sleep -Seconds $WaitSeconds
    }
    $l = Get-KohaHiddenLaunch -Arguments 'Tray'
    Write-KohaLog ('hidden launch in use: {0} {1} (launcher {2}, hiddenLaunch {3})' -f $l.Target, $l.Arguments, (Get-KohaState).launcher, (Get-KohaState).hiddenLaunch) 'install'
    # Checked once more after a pause: a tray that starts and then ends at
    # once (a missing part, a PowerShell Windows restricts) is not up.
    Start-Sleep -Seconds 2
    if (Test-KohaTrayRunning) {
        Write-KohaStep (T 'The Koha icon is in the notification area, next to the clock.') 'ok'
    } else {
        $why = Get-KohaLastFailure 'Tray'
        Write-KohaLog ('the tray is not running after every hidden launch; last tray error: {0}' -f $why) 'install'
        Write-KohaStep (T 'The Koha icon did not start. Open Koha - Status icon in the Start menu (folder Koha).') 'warn'
        if ($why) { Write-KohaStep ((T 'The tray stopped with this error: {0}') -f $why) 'warn' }
    }
}

# The tray of an older version keeps its old menu until it is restarted.
function Restart-KohaTray {
    try {
        Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction Stop |
            Where-Object { ([string]$_.CommandLine) -match 'KohaEasy\.ps1"?\s+Tray' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch { }
    Start-KohaTray
}

Export-ModuleMember -Function *
