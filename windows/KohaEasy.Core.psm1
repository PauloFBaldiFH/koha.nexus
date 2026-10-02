# Koha Easy Installer for Windows: shared logic for the shortcuts, the
# scheduled tasks and the tray (blueprint, part 2).
#   * state.json: what the librarian asked for (desired running/stopped,
#     automatic start) and what was already notified.
#   * Start / Stop / Restart and the automatic start at sign-in (2.5.1).
#   * Status, read from "config.sh --status-json" inside the distro.
#   * Windows notifications for service events and nightly backups.
#   * Diagnostics exported to one .zip for support.
#   * Watchdog for the free space around the distro's virtual disk (ext4.vhdx).
# Windows PowerShell 5.1 compatible (no ??, ternary or &&). UTF-8 with BOM.

Set-StrictMode -Version 2.0
Import-Module (Join-Path $PSScriptRoot 'KohaEasy.Lang.psm1')

$script:Cfg = @{
    Root        = 'C:\KohaEasy'
    Distro      = 'koha'
    OldDistros  = @('KohaEasy')
    TaskPath    = '\KohaEasy\'
    KeepTask    = 'Keep Koha running'
    SignInTask  = 'Start Koha at sign-in'
    NetTask     = 'Koha network'
    FirewallRule = 'Koha (web, local network)'
    WebPorts    = @(80, 8080)
    PanelPath   = '/usr/local/bin/koha-panel'
    StaffUrl    = 'http://localhost:8080/'
    OpacUrl     = 'http://localhost/'
    StartWaitS  = 180
    StopWaitS   = 60
    BootGraceS  = 45
    StopScript  = '/usr/local/sbin/koha-easy-stop'
    DiskWarnGB  = 10
    DiskCritGB  = 5
    StaleBackupH = 36
    ToastAppId  = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    AppId       = 'KohaEasy.Koha'
    WindowPath  = '/usr/local/bin/koha-window'
    LanSetup    = 2
}
if ($env:KOHAEASY_ROOT) { $script:Cfg.Root = $env:KOHAEASY_ROOT }

# Set by the tray: notifications fall back to its balloon tips when Windows
# toasts are unavailable.
$script:TrayIcon = $null

function Get-KohaConfig { return $script:Cfg }
function Set-KohaTrayIcon { param($Icon) $script:TrayIcon = $Icon }
function Set-KohaConfig {
    param([hashtable]$Values)
    foreach ($k in $Values.Keys) { $script:Cfg[$k] = $Values[$k] }
}

# ----------------------------------------------------------------------
# Paths, log and state.json
# ----------------------------------------------------------------------
function Get-KohaPath {
    param([ValidateSet('Root', 'Bin', 'Logs', 'Backups', 'State', 'Wsl', 'Lang')][string]$Name)
    $r = $script:Cfg.Root
    switch ($Name) {
        'Root'    { return $r }
        'Bin'     { return [System.IO.Path]::Combine($r, 'bin') }
        'Logs'    { return [System.IO.Path]::Combine($r, 'logs') }
        'Backups' { return [System.IO.Path]::Combine($r, 'Backups') }
        'State'   { return [System.IO.Path]::Combine($r, 'state.json') }
        'Wsl'     { return [System.IO.Path]::Combine($r, 'wsl') }
        'Lang'    { return [System.IO.Path]::Combine($r, 'bin', 'lang') }
    }
}

function Write-KohaLog {
    param([string]$Message, [string]$Name = 'koha')
    try {
        $dir = Get-KohaPath Logs
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $file = Join-Path $dir ('{0}-{1}.log' -f $Name, (Get-Date -Format 'yyyyMMdd'))
        $line = '{0} | {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
        Add-Content -LiteralPath $file -Value $line -Encoding UTF8
    } catch { }
}

$script:StateDefaults = [ordered]@{
    desired              = 'running'
    autostart            = 'logon'
    startedAt            = 0
    lastState            = ''
    firstSeen            = 0
    lastBackupLogEpoch   = 0
    lastStaleBackupWarn  = 0
    lastDiskLevel        = 'ok'
    lastDiskWarn         = 0
    lastRecoveryEpoch    = 0
    lastRecoveryNotice   = 0
    notifyBackupOk       = $true
    handshakePending     = $false
    hiddenLaunch         = 'conhost'
    stopScriptHash       = ''
    launcher             = ''
    launcherHash         = ''
    appIdShortcut        = $false
    lanSetup             = 0
    trayClosed           = $false
    trayPromoted         = $false
    trayTipShown         = $false
    poweredOffAt         = 0
    netLaunch            = ''
}

# state.json as an ordered hashtable, with defaults for missing keys. A
# damaged file is kept aside (state.json.bad) instead of breaking Start/Stop.
function Get-KohaState {
    $state = [ordered]@{}
    foreach ($k in $script:StateDefaults.Keys) { $state[$k] = $script:StateDefaults[$k] }
    $file = Get-KohaPath State
    if (Test-Path -LiteralPath $file) {
        try {
            $json = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach ($p in $json.PSObject.Properties) { $state[$p.Name] = $p.Value }
        } catch {
            Write-KohaLog "state.json unreadable, kept as state.json.bad: $($_.Exception.Message)"
            Copy-Item -LiteralPath $file -Destination ($file + '.bad') -Force -ErrorAction SilentlyContinue
        }
    }
    if (@('running', 'stopped') -notcontains $state.desired) { $state.desired = 'running' }
    if (@('logon', 'manual') -notcontains $state.autostart) { $state.autostart = 'logon' }
    return $state
}

# Merges $Changes into state.json. Written to a temporary file and moved, so
# a shortcut and the tray writing at the same time never leave half a file.
function Set-KohaState {
    param([Parameter(Mandatory = $true)][hashtable]$Changes)
    $state = Get-KohaState
    foreach ($k in $Changes.Keys) { $state[$k] = $Changes[$k] }
    $file = Get-KohaPath State
    $dir = Split-Path -Parent $file
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $tmp = $file + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tmp, ($state | ConvertTo-Json -Depth 5), $utf8)
    Move-Item -LiteralPath $tmp -Destination $file -Force
    return $state
}

function Get-UnixTime { return [int64][Math]::Floor(([DateTimeOffset]::UtcNow).ToUnixTimeSeconds()) }

# ----------------------------------------------------------------------
# WSL
# ----------------------------------------------------------------------
# UTF-8 for this console, both ways, and for text piped into wsl.exe. The
# encoding carries no BOM: [Text.Encoding]::UTF8 in Windows PowerShell 5.1
# would put one in front of every script sent to Debian through stdin.
function Set-KohaUtf8Console {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    try { & "$env:SystemRoot\System32\chcp.com" 65001 | Out-Null } catch { }
    try { [Console]::OutputEncoding = $utf8 } catch { }
    try { [Console]::InputEncoding = $utf8 } catch { }
    $global:OutputEncoding = $utf8
}

# Windows Terminal (wt.exe), when installed. It draws emoji; the classic
# console has no emoji font and shows them as boxes. KOHAEASY_NO_WT=1 keeps
# everything in the classic console.
function Get-KohaTerminalPath {
    if ($env:KOHAEASY_NO_WT -eq '1') { return $null }
    $c = Get-Command 'wt.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { return [string]$c.Source }
    return $null
}

# Runs wsl.exe with UTF-8 output. Returns ExitCode and Output (one string).
# -OnLine gets each line as Linux writes it (the safe stop's progress).
function Invoke-KohaWsl {
    param([Parameter(Mandatory = $true)][string[]]$Arguments, [string]$InputText, [scriptblock]$OnLine)
    # Whatever Linux writes to stderr is part of the answer, never a
    # PowerShell error: under 'Stop', Windows PowerShell 5.1 turns the first
    # stderr line of a native command redirected with 2>&1 into an exception
    # ("id: 'paulo': no such user" stopped the installer that way).
    $ErrorActionPreference = 'Continue'
    $env:WSL_UTF8 = '1'
    $prev = [Console]::OutputEncoding
    try {
        [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        $relay = { process { $l = [string]$_; if ($OnLine) { try { & $OnLine $l } catch { } }; $l } }
        if ($PSBoundParameters.ContainsKey('InputText')) {
            $out = $InputText | & wsl.exe @Arguments 2>&1 | & $relay
        } else {
            $out = & wsl.exe @Arguments 2>&1 | & $relay
        }
        $code = $LASTEXITCODE
    } finally {
        [Console]::OutputEncoding = $prev
    }
    $text = (@($out) | ForEach-Object { [string]$_ }) -join "`n"
    return [pscustomobject]@{ ExitCode = $code; Output = $text.Replace([string][char]0, '') }
}

# Command inside the distro (Koha's by default), as root.
function Invoke-KohaLinux {
    param([Parameter(Mandatory = $true)][string[]]$Command, [string]$InputText, [string]$Distro = $script:Cfg.Distro, [scriptblock]$OnLine)
    $wslArgs = @('-d', $Distro, '-u', 'root', '--') + $Command
    $more = @{}
    if ($OnLine) { $more.OnLine = $OnLine }
    if ($PSBoundParameters.ContainsKey('InputText')) { return Invoke-KohaWsl -Arguments $wslArgs -InputText $InputText @more }
    return Invoke-KohaWsl -Arguments $wslArgs @more
}

# Runs a shell script as root inside the distro. The script crosses into
# Linux through stdin (tee) and runs from a file, so only plain words go on
# wsl.exe's command line: Windows PowerShell 5.1 does not escape the double
# quotes inside a native command's arguments, and "sh -c <script>" arrived
# in Linux cut into pieces. $InputText, when given, is the script's stdin.
# With -TimeoutSeconds, Linux's timeout ends the script (exit code 124).
# -OnLine as in Invoke-KohaWsl, for the script's own output.
function Invoke-KohaLinuxScript {
    param([Parameter(Mandatory = $true)][string]$Script, [string]$InputText, [string]$Distro = $script:Cfg.Distro, [int]$TimeoutSeconds = 0, [scriptblock]$OnLine)
    $file = '/run/kohaeasy-{0}.sh' -f ([guid]::NewGuid().ToString('N'))
    # "exit $?" ends the script before the CR LF that Windows adds after
    # piped text, which sh would otherwise run as a command.
    $body = ($Script -replace "`r", '') + "`nexit `$?`n"
    $w = Invoke-KohaLinux -Command @('tee', $file) -InputText $body -Distro $Distro
    if ($w.ExitCode -ne 0) { return $w }
    $run = @('sh', $file)
    if ($TimeoutSeconds -gt 0) { $run = @('timeout', '-k', '5', [string]$TimeoutSeconds) + $run }
    $more = @{}
    if ($OnLine) { $more.OnLine = $OnLine }
    try {
        if ($PSBoundParameters.ContainsKey('InputText')) { return (Invoke-KohaLinux -Command $run -InputText $InputText -Distro $Distro @more) }
        return (Invoke-KohaLinux -Command $run -Distro $Distro @more)
    } finally {
        Invoke-KohaLinux -Command @('rm', '-f', $file) -Distro $Distro | Out-Null
    }
}

# Names of the running distros. Never starts one (a status check must not
# turn on a Koha the librarian stopped).
function Get-KohaRunningDistros {
    $r = Invoke-KohaWsl -Arguments @('--list', '--running', '--quiet')
    if ($r.ExitCode -ne 0) { return @() }
    return @($r.Output -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Get-KohaInstalledDistros {
    $r = Invoke-KohaWsl -Arguments @('--list', '--quiet')
    if ($r.ExitCode -ne 0) { return @() }
    return @($r.Output -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Test-KohaDistroRunning { return (@(Get-KohaRunningDistros) -contains $script:Cfg.Distro) }
function Test-KohaDistroInstalled { return (@(Get-KohaInstalledDistros) -contains $script:Cfg.Distro) }

# ----------------------------------------------------------------------
# Handshake file (/etc/koha-easy-install/windows.conf)
# ----------------------------------------------------------------------
# Keeps only the characters the panel's parser accepts for each key.
function ConvertTo-KohaConfValue {
    param([string]$Value, [int]$Max = 64)
    $v = ([string]$Value) -replace '[^A-Za-z0-9._:/ -]', ''
    $v = $v -replace '\.\.+', '.'
    if ($v.Length -gt $Max) { $v = $v.Substring(0, $Max) }
    return $v.Trim()
}

# The network mode .wslconfig asks for: mirrored when it says so on a build
# that supports it (Windows 11 22H2, build 22621+), NAT otherwise.
function Get-KohaConfiguredNetMode {
    param([int]$Build = [Environment]::OSVersion.Version.Build)
    if (-not $env:USERPROFILE) { return 'nat' }
    $cfg = Join-Path $env:USERPROFILE '.wslconfig'
    if ($Build -ge 22621 -and (Test-Path -LiteralPath $cfg)) {
        if ((Get-Content -LiteralPath $cfg -Raw) -match '(?im)^\s*networkingMode\s*=\s*mirrored\s*$') { return 'mirrored' }
    }
    return 'nat'
}

# The network mode WSL really runs in. .wslconfig only asks for one: WSL
# falls back to NAT when mirrored networking cannot start, and a change
# waits for the next "wsl --shutdown". So while Debian runs, Debian is asked;
# when it is stopped, .wslconfig answers (a check never starts the distro).
function Get-KohaNetMode {
    param([int]$Build = [Environment]::OSVersion.Version.Build)
    if (Test-KohaDistroRunning) {
        $live = Get-KohaLiveNetMode
        if ($live) { return $live }
    }
    return (Get-KohaConfiguredNetMode -Build $Build)
}

# Asked inside the running Debian: WSL's own answer (wslinfo, WSL 2.0 and
# later), else whether Debian carries this PC's own network address, which
# only mirrored networking gives it. '' when neither answers.
function Get-KohaLiveNetMode {
    param([string]$LanIp = (Get-KohaLanIp))
    $info = ''
    $ips = ''
    $w = Invoke-KohaLinux -Command @('wslinfo', '--networking-mode')
    if ($w.ExitCode -eq 0) { $info = [string]$w.Output }
    $h = Invoke-KohaLinux -Command @('hostname', '-I')
    if ($h.ExitCode -eq 0) { $ips = [string]$h.Output }
    return (Resolve-KohaNetMode -WslInfo $info -DebianIps $ips -LanIp $LanIp)
}

# Pure: mirrored | nat | '' from what Debian reported.
function Resolve-KohaNetMode {
    param([string]$WslInfo, [string]$DebianIps, [string]$LanIp)
    $m = ([string]$WslInfo).Trim().ToLowerInvariant()
    if (@('mirrored', 'nat') -contains $m) { return $m }
    $ips = @(([string]$DebianIps).Trim() -split '\s+' | Where-Object { Test-KohaIPv4 $_ })
    if ($ips.Count -eq 0) { return '' }
    if ($LanIp -and ($ips -contains $LanIp)) { return 'mirrored' }
    return 'nat'
}

function Get-KohaLanIp {
    try {
        $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop | Sort-Object RouteMetric | Select-Object -First 1
        $ip = Get-NetIPAddress -InterfaceIndex $route.ifIndex -AddressFamily IPv4 -ErrorAction Stop | Select-Object -First 1
        return [string]$ip.IPAddress
    } catch { return '' }
}

function New-KohaHandshake {
    param([System.Collections.IDictionary]$State = (Get-KohaState))
    $os = [Environment]::OSVersion.Version
    $edition = ''
    try { $edition = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction Stop).EditionID } catch { }
    $memGb = 0
    try { $memGb = [int][Math]::Round((Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).TotalPhysicalMemory / 1GB) } catch { }
    $backup = Get-KohaPath Backups
    $wslBackup = ''
    if ($backup -match '^([A-Za-z]):[\\/](.*)$') { $wslBackup = '/mnt/' + $Matches[1].ToLowerInvariant() + '/' + ($Matches[2] -replace '[\\/]', '/') }
    $lines = @(
        '# Written by KohaEasy.ps1. Read by the panel (read_windows_conf), never executed.'
        'KEI_WIN_VERSION=' + (ConvertTo-KohaConfValue $script:KohaEasyVersion)
        'WIN_BUILD=' + $os.Build
        'WIN_EDITION=' + (ConvertTo-KohaConfValue $edition)
        'WIN_NET_MODE=' + (Get-KohaNetMode -Build $os.Build)
        'WIN_LAN_IP=' + (ConvertTo-KohaConfValue (Get-KohaLanIp))
        'WIN_HOSTNAME=' + (ConvertTo-KohaConfValue $env:COMPUTERNAME 63)
        'WIN_USER=' + (ConvertTo-KohaConfValue $env:USERNAME)
        'WIN_BACKUP_DIR=' + (ConvertTo-KohaConfValue $wslBackup 200)
        'WIN_MEM_GB=' + $memGb
        'WIN_UPDATED_AT=' + (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')
        'WIN_AUTOSTART=' + $State.autostart
    )
    # An empty value would be logged as invalid by the panel: leave the key out.
    return (@($lines | Where-Object { $_ -notmatch '^[A-Z_]+=$' }) -join "`n") + "`n"
}

# Writes the handshake through stdin: root-owned, 0644, replaced atomically,
# as read_windows_conf requires. Needs the distro running: when it is not,
# the write waits for the next Start (handshakePending).
function Update-KohaHandshake {
    if (-not (Test-KohaDistroRunning)) {
        Set-KohaState @{ handshakePending = $true } | Out-Null
        return $false
    }
    $script = 'umask 022; d=/etc/koha-easy-install; mkdir -p "$d" && t=$(mktemp "$d/.windows.conf.XXXXXX") && cat > "$t" && chown root:root "$t" && chmod 644 "$t" && mv -f "$t" "$d/windows.conf"'
    $r = Invoke-KohaLinuxScript -Script $script -InputText (New-KohaHandshake)
    if ($r.ExitCode -ne 0) {
        Write-KohaLog "handshake not written: $($r.Output)"
        return $false
    }
    Set-KohaState @{ handshakePending = $false } | Out-Null
    return $true
}

# ----------------------------------------------------------------------
# Status
# ----------------------------------------------------------------------
# Koha's own view of itself (config.sh --status-json), or $null.
function Get-KohaLinuxStatus {
    $r = Invoke-KohaLinux -Command @($script:Cfg.PanelPath, '--status-json')
    if ($r.ExitCode -ne 0) { return $null }
    $line = @($r.Output -split "`n" | Where-Object { $_.TrimStart().StartsWith('{') } | Select-Object -Last 1)
    if ($line.Count -eq 0) { return $null }
    try { return ($line[0] | ConvertFrom-Json) } catch { return $null }
}

# One-word state for the tray and the Status shortcut:
#   running | starting | not_responding | stopped_by_user | stopped | not_installed
# Pure. Until $GraceUntil (the first seconds after Windows starts, see
# Get-KohaBootGraceUntil), a Koha that should run and is not up yet is
# starting, not stopped or not responding: WSL, systemd and Koha's services
# take a while after a cold boot, and the sign-in task may not have run yet.
function Resolve-KohaState {
    param($Installed, $Running, $Linux, [System.Collections.IDictionary]$State, [int64]$Now = (Get-UnixTime), [int64]$GraceUntil = 0)
    if (-not $Installed) { return 'not_installed' }
    $grace = ($Now -lt $GraceUntil) -and ($State.desired -ne 'stopped') -and ($State.autostart -ne 'manual')
    if (-not $Running) {
        if ($State.desired -eq 'stopped') { return 'stopped_by_user' }
        if ($grace) { return 'starting' }
        return 'stopped'
    }
    $recent = $grace -or (($State.startedAt -gt 0) -and (($Now - [int64]$State.startedAt) -lt $script:Cfg.StartWaitS))
    if ($null -ne $Linux -and $Linux.state -eq 'ok') { return 'running' }
    if ($null -ne $Linux -and $Linux.state -eq 'not_installed') { return 'not_installed' }
    if ($recent) { return 'starting' }
    return 'not_responding'
}

# When the boot grace ends: $Cfg.BootGraceS after Windows started (the
# tray also passes its own start, since Fast Startup keeps Windows' uptime).
function Get-KohaBootGraceUntil {
    param([int64]$UptimeMs = [int64][Environment]::TickCount, [int64]$Now = (Get-UnixTime))
    # TickCount is an Int32 that wraps after 24.9 days.
    if ($UptimeMs -lt 0) { $UptimeMs += 4294967296 }
    return ($Now - [int64]($UptimeMs / 1000) + [int64]$script:Cfg.BootGraceS)
}

function Get-KohaStatus {
    param([int64]$GraceUntil = 0)
    $state = Get-KohaState
    $boot = Get-KohaBootGraceUntil
    if ($boot -gt $GraceUntil) { $GraceUntil = $boot }
    $installed = Test-KohaDistroInstalled
    $running = $false
    $linux = $null
    if ($installed) { $running = Test-KohaDistroRunning }
    if ($running) { $linux = Get-KohaLinuxStatus }
    return [pscustomobject]@{
        State     = (Resolve-KohaState -Installed $installed -Running $running -Linux $linux -State $state -GraceUntil $GraceUntil)
        Desired   = $state.desired
        Autostart = $state.autostart
        Linux     = $linux
        CheckedAt = (Get-UnixTime)
    }
}

function Get-KohaStateText {
    param([string]$State)
    switch ($State) {
        'running'         { return (T 'Koha is running') }
        'starting'        { return (T 'Koha is starting...') }
        'not_responding'  { return (T 'Koha is not responding') }
        'stopped_by_user' { return (T 'Koha is stopped (you stopped it)') }
        'stopped'         { return (T 'Koha is stopped') }
        default           { return (T 'Koha is not installed') }
    }
}

# ----------------------------------------------------------------------
# Notifications
# ----------------------------------------------------------------------
# Koha's own name and icon on its notifications once the Koha shortcut in
# the Start menu carries Koha's AppUserModelID (Windows ties notifications
# to it); Windows PowerShell's before that.
function Get-KohaToastAppId {
    if ([bool](Get-KohaState).appIdShortcut) { return $script:Cfg.AppId }
    return $script:Cfg.ToastAppId
}

# Windows toast (WinRT, Windows PowerShell 5.1). Falls back to the tray's
# balloon tip, and always goes to logs\notifications-*.log.
function Show-KohaNotification {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$Text,
        [ValidateSet('info', 'warning', 'error')][string]$Level = 'info'
    )
    Write-KohaLog ("[{0}] {1}: {2}" -f $Level, $Title, $Text) 'notifications'
    try {
        $null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
        $null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $scenario = ''
        if ($Level -eq 'error') { $scenario = ' scenario="reminder"' }
        $xml.LoadXml(('<toast{0}><visual><binding template="ToastGeneric"><text>{1}</text><text>{2}</text></binding></visual></toast>' -f
                $scenario, [Security.SecurityElement]::Escape($Title), [Security.SecurityElement]::Escape($Text)))
        $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier((Get-KohaToastAppId)).Show($toast)
        return 'toast'
    } catch {
        if ($null -ne $script:TrayIcon) {
            $icon = [System.Windows.Forms.ToolTipIcon]::Info
            if ($Level -eq 'warning') { $icon = [System.Windows.Forms.ToolTipIcon]::Warning }
            if ($Level -eq 'error') { $icon = [System.Windows.Forms.ToolTipIcon]::Error }
            $script:TrayIcon.ShowBalloonTip(10000, $Title, $Text, $icon)
            return 'balloon'
        }
        return 'log'
    }
}

function Format-KohaSize {
    param([double]$Bytes)
    if ($Bytes -ge 1GB) { return ('{0:N1} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N1} MB' -f ($Bytes / 1MB)) }
    return ('{0:N0} KB' -f ($Bytes / 1KB))
}

# What to tell the librarian after a status check, and the state.json
# changes that remember it. Pure function: the tray shows the result.
#   $Previous  last state word shown ('' on the first check)
#   $Status    Get-KohaStatus result
#   $Disk      Get-KohaDiskHealth result or $null
function Get-KohaNotifications {
    param([string]$Previous, $Status, $Disk, [System.Collections.IDictionary]$State, [int64]$Now = (Get-UnixTime))
    $out = New-Object System.Collections.ArrayList
    $changes = @{ lastState = $Status.State }
    $cur = $Status.State
    $wanted = ($State.desired -eq 'running')

    # Service events (only while the librarian wants Koha on).
    if ($wanted -and $Previous -and $Previous -ne $cur) {
        if ($cur -eq 'not_responding') {
            [void]$out.Add(@{ Level = 'error'; Title = (T 'Koha is not responding'); Text = (T 'The library system stopped answering. Use Restart Koha in the tray menu; if it happens again, export the diagnostics for support.') })
        } elseif ($cur -eq 'stopped' -and @('running', 'starting') -contains $Previous) {
            [void]$out.Add(@{ Level = 'error'; Title = (T 'Koha stopped unexpectedly'); Text = (T 'Koha was turned off without Stop Koha. It will be started again automatically.') })
        } elseif ($cur -eq 'running' -and @('not_responding', 'stopped') -contains $Previous) {
            [void]$out.Add(@{ Level = 'info'; Title = (T 'Koha is working again'); Text = (T 'The staff interface and the catalog are answering again.') })
        }
    }

    # Nightly backup: one notification per new line of backup_sql.log.
    if ($null -ne $Status.Linux -and $null -ne $Status.Linux.backup) {
        $b = $Status.Linux.backup
        if ([int64]$b.log_epoch -gt [int64]$State.lastBackupLogEpoch) {
            $changes.lastBackupLogEpoch = [int64]$b.log_epoch
            if ($State.lastBackupLogEpoch -gt 0 -or ($Now - [int64]$b.log_epoch) -lt 86400) {
                if ($b.last_result -eq 'ok' -and $State.notifyBackupOk) {
                    [void]$out.Add(@{ Level = 'info'; Title = (T 'Backup completed'); Text = ((T 'The nightly backup of the catalog was saved ({0}).') -f (Format-KohaSize ([double]$b.last_size))) })
                } elseif ($b.last_result -eq 'failed') {
                    [void]$out.Add(@{ Level = 'error'; Title = (T 'Backup FAILED'); Text = (T 'The nightly backup of the catalog failed. Open the tray menu and export the diagnostics for support.') })
                }
            }
        }
        # No good backup for too long (in manual mode Koha may be off at 23:00).
        # Counted from the first time Koha was seen, so a new install is not warned.
        $limit = $script:Cfg.StaleBackupH * 3600
        $first = [int64]$State.firstSeen
        if ($first -le 0) { $first = $Now; $changes.firstSeen = $Now }
        $age = $Now - [int64]$b.last_epoch
        if ($Status.Linux.koha_installed -and $age -gt $limit -and ($Now - $first) -gt $limit -and ($Now - [int64]$State.lastStaleBackupWarn) -gt 86400) {
            $changes.lastStaleBackupWarn = $Now
            $text = T 'There is no recent backup of the catalog. Use Control panel > Manual backup, or keep Koha on at 23:00.'
            if ($State.autostart -eq 'manual') {
                $text = T 'There is no recent backup of the catalog. Koha starts only when you click Koha - Start, and the nightly backup runs at 23:00 only while Koha is on.'
            }
            [void]$out.Add(@{ Level = 'warning'; Title = (T 'No recent backup'); Text = $text })
        }
    }

    # Repair after an unclean stop (a power cut, a forced shutdown): told
    # once when it starts and once when it ends, for repairs of the last week.
    if ($null -ne $Status.Linux -and $Status.Linux.PSObject.Properties['recovery'] -and $null -ne $Status.Linux.recovery) {
        $rec = $Status.Linux.recovery
        $epoch = [int64]$rec.epoch
        $recent = ($epoch -gt 0) -and (($Now - $epoch) -lt 604800)
        if ($recent -and $rec.state -eq 'running' -and $epoch -gt [int64]$State.lastRecoveryNotice) {
            $changes.lastRecoveryNotice = $epoch
            [void]$out.Add(@{ Level = 'warning'; Title = (T 'Koha was not shut down properly'); Text = (T 'The computer was turned off while Koha was running (for example, a power cut). Koha is checking its database and its search index; searches may be incomplete for a few minutes.') })
        }
        if ($recent -and $rec.state -eq 'done' -and $epoch -gt [int64]$State.lastRecoveryEpoch) {
            $changes.lastRecoveryEpoch = $epoch
            $changes.lastRecoveryNotice = $epoch
            $problems = New-Object System.Collections.ArrayList
            if ($rec.db -eq 'errors') { [void]$problems.Add((T 'the database check reported errors')) }
            if ($rec.db -eq 'unreachable') { [void]$problems.Add((T 'the database did not start')) }
            if ($rec.backup -eq 'failed') { [void]$problems.Add((T 'the new backup failed')) }
            if ($rec.index -eq 'failed') { [void]$problems.Add((T 'the search index could not be rebuilt')) }
            if ($problems.Count -eq 0) {
                [void]$out.Add(@{ Level = 'info'; Title = (T 'Koha repaired itself'); Text = (T 'The computer was turned off while Koha was running. Koha checked its database, made a new backup and updated its search index. Everything is working.') })
            } else {
                [void]$out.Add(@{ Level = 'error'; Title = (T 'Koha needs attention'); Text = ((T 'The computer was turned off while Koha was running, and the check afterwards found problems: {0}. Export the diagnostics from the tray menu and send them to support.') -f (@($problems) -join '; ')) })
            }
        }
    }

    # Disk space: on every level change, and a critical level again every 6 hours.
    if ($null -ne $Disk) {
        $changes.lastDiskLevel = $Disk.Level
        $again = ($Disk.Level -eq 'critical') -and (($Now - [int64]$State.lastDiskWarn) -gt 21600)
        if ($Disk.Level -ne 'ok' -and ($Disk.Level -ne $State.lastDiskLevel -or $again)) {
            $changes.lastDiskWarn = $Now
            $title = T 'Disk space is low'
            if ($Disk.Level -eq 'critical') { $title = T 'Disk space is critically low' }
            [void]$out.Add(@{ Level = $(if ($Disk.Level -eq 'critical') { 'error' } else { 'warning' }); Title = $title; Text = $Disk.Message })
        }
    }
    return [pscustomobject]@{ Notifications = @($out); Changes = $changes }
}

# ----------------------------------------------------------------------
# Virtual disk watchdog
# ----------------------------------------------------------------------
# WSL's registration of a distro (HKCU\...\Lxss\{guid}): PSPath, Name,
# BasePath (its folder) and, on recent WSL, ShortcutPath and
# TerminalProfilePath. $null when WSL does not know the name.
function Get-KohaLxssEntry {
    param([string]$Name = $script:Cfg.Distro)
    $lxss = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'
    if (-not (Test-Path $lxss)) { return $null }
    foreach ($k in Get-ChildItem $lxss -ErrorAction SilentlyContinue) {
        $p = Get-ItemProperty $k.PSPath -ErrorAction SilentlyContinue
        if ($null -eq $p -or -not $p.PSObject.Properties['DistributionName'] -or $p.DistributionName -ne $Name) { continue }
        $e = [ordered]@{ PSPath = $k.PSPath; Name = [string]$p.DistributionName; BasePath = ''; ShortcutPath = ''; TerminalProfilePath = '' }
        foreach ($v in 'BasePath', 'ShortcutPath', 'TerminalProfilePath') {
            if ($p.PSObject.Properties[$v]) { $e[$v] = ([string]$p.$v) -replace '^\\\\\?\\', '' }
        }
        return [pscustomobject]$e
    }
    return $null
}

# Folder of the distro (BasePath in HKCU\...\Lxss) and its ext4.vhdx.
function Get-KohaVhdxPath {
    $e = Get-KohaLxssEntry
    if ($null -eq $e -or -not $e.BasePath) { return $null }
    $file = Join-Path $e.BasePath 'ext4.vhdx'
    if (Test-Path -LiteralPath $file) { return $file }
    return $null
}

# Level from the numbers alone (pure, tested):
#   HostFree/HostTotal  the Windows drive that holds ext4.vhdx
#   VhdxSize            the file today (it grows, it does not shrink by itself)
#   LinuxUsed/LinuxTotal  "df /" inside the distro, 0 when unknown
function Measure-KohaDiskLevel {
    param([double]$HostFree, [double]$HostTotal, [double]$VhdxSize, [double]$LinuxUsed, [double]$LinuxTotal)
    $level = 'ok'
    $msgs = New-Object System.Collections.ArrayList
    $warn = $script:Cfg.DiskWarnGB * 1GB
    $crit = $script:Cfg.DiskCritGB * 1GB
    if ($HostTotal -gt 0) {
        if ($HostFree -lt $crit) {
            $level = 'critical'
        } elseif ($HostFree -lt $warn) {
            $level = 'warning'
        }
        if ($level -ne 'ok') {
            [void]$msgs.Add(((T 'Only {0} free on the Windows drive that holds Koha. When it is full, Koha and its backups stop working.') -f (Format-KohaSize $HostFree)))
        }
    }
    if ($LinuxTotal -gt 0) {
        $pct = $LinuxUsed / $LinuxTotal
        if ($pct -ge 0.95) { $level = 'critical' } elseif ($pct -ge 0.90 -and $level -eq 'ok') { $level = 'warning' }
        if ($pct -ge 0.90) { [void]$msgs.Add(((T 'The Koha disk is {0}% full.') -f [int]($pct * 100))) }
    }
    $reclaim = 0
    if ($VhdxSize -gt 0 -and $LinuxTotal -gt 0) {
        $reclaim = [Math]::Max([double]0, $VhdxSize - $LinuxUsed)
        if ($reclaim -gt 10GB -and $reclaim -gt ($VhdxSize * 0.3) -and $level -ne 'ok') {
            [void]$msgs.Add(((T 'About {0} can be given back to Windows: tray menu > Check disk space > Compact.') -f (Format-KohaSize $reclaim)))
        }
    }
    return [pscustomobject]@{ Level = $level; Message = ($msgs -join ' '); Reclaimable = $reclaim }
}

function Get-KohaDiskHealth {
    param($Linux)
    $vhdx = Get-KohaVhdxPath
    $size = 0
    $drive = (Get-KohaPath Root).Substring(0, 2)
    if ($vhdx) {
        $size = (Get-Item -LiteralPath $vhdx).Length
        $drive = $vhdx.Substring(0, 2)
    }
    $free = 0; $total = 0
    try {
        $di = New-Object System.IO.DriveInfo($drive)
        $free = $di.AvailableFreeSpace; $total = $di.TotalSize
    } catch { }
    $lUsed = 0; $lTotal = 0
    if ($null -ne $Linux -and $null -ne $Linux.disk) {
        $lTotal = [double]$Linux.disk.total
        $lUsed = $lTotal - [double]$Linux.disk.free
    }
    $m = Measure-KohaDiskLevel -HostFree $free -HostTotal $total -VhdxSize $size -LinuxUsed $lUsed -LinuxTotal $lTotal
    return [pscustomobject]@{
        Level = $m.Level; Message = $m.Message; Reclaimable = $m.Reclaimable
        Vhdx = $vhdx; VhdxSize = $size; Drive = $drive; HostFree = $free; HostTotal = $total
        LinuxUsed = $lUsed; LinuxTotal = $lTotal
    }
}

function Test-KohaAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Gives the unused space of ext4.vhdx back to Windows: fstrim inside Linux,
# Koha stopped cleanly and "wsl --shutdown" (the disk must be detached; this
# also stops any other WSL distro), diskpart "compact vdisk", then Koha is started again if it was
# meant to run. Needs administrator rights (diskpart). [verify] on real WSL.
function Invoke-KohaDiskCompact {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param()
    $vhdx = Get-KohaVhdxPath
    if (-not $vhdx) { throw (T 'The Koha virtual disk (ext4.vhdx) was not found.') }
    if (-not (Test-KohaAdmin)) { throw (T 'Compacting the disk needs administrator rights.') }
    $state = Get-KohaState
    $before = (Get-Item -LiteralPath $vhdx).Length
    if (-not $PSCmdlet.ShouldProcess($vhdx, 'compact')) { return }
    if (Test-KohaDistroRunning) { Invoke-KohaLinux -Command @('fstrim', '-av') | Out-Null }
    Stop-KohaKeepAlive
    Stop-KohaDebianGracefully -Shutdown | Out-Null
    $script = @(
        ('select vdisk file="{0}"' -f $vhdx)
        'attach vdisk readonly'
        'compact vdisk'
        'detach vdisk'
    ) -join "`r`n"
    $tmp = Join-Path $env:TEMP ('kohaeasy-compact-{0}.txt' -f [guid]::NewGuid().ToString('N'))
    Set-Content -LiteralPath $tmp -Value $script -Encoding ASCII
    try {
        $out = Invoke-KohaDiskpart -ScriptFile $tmp
        Write-KohaLog "compact: $out"
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
    if ($state.desired -eq 'running') { Start-KohaKeepAlive }
    $after = (Get-Item -LiteralPath $vhdx).Length
    return [pscustomobject]@{ Before = $before; After = $after; Freed = [Math]::Max([double]0, [double]($before - $after)) }
}

function Invoke-KohaDiskpart {
    param([string]$ScriptFile)
    return ((& diskpart.exe /s $ScriptFile 2>&1) -join "`n")
}

# ----------------------------------------------------------------------
# Start, Stop and automatic start (blueprint 2.5.1)
# ----------------------------------------------------------------------
# Pure: how a Koha command starts with no window at all, best first:
#   1. KohaEasy.exe, built on this PC (KohaEasy.Launcher.cs): a Windows
#      program, so Windows opens no console for it, and it starts PowerShell
#      with CREATE_NO_WINDOW;
#   2. wscript.exe KohaEasy.Hidden.js: Windows Script Host is a Windows
#      program too, and it starts PowerShell with its window hidden from the
#      start (window style 0), so Windows Terminal does not take it over.
#      Its shortcuts hold no PowerShell command line, which antivirus
#      programs treat as suspicious in a .lnk;
#   3. conhost.exe --headless: a console nobody sees (Windows 10 1903 and
#      later, which WSL 2 needs anyway);
#   4. powershell.exe -WindowStyle Hidden, the last resort: it flashes a
#      console, and where Windows Terminal is the default terminal (Windows
#      11) it leaves an empty Windows Terminal window open.
# The shortcuts, the tray at sign-in and the scheduled tasks all use it.
# -Hidden tells KohaEasy.ps1 it was started this way (see
# Test-KohaRelaunchHidden).
function Get-KohaHiddenLaunch {
    param(
        [string]$Arguments,
        [string]$Conhost = (Get-KohaConhostPath),
        [string]$Launcher = (Get-KohaLauncherPath),
        [string]$Wscript = (Get-KohaWscriptPath)
    )
    $Arguments = ($Arguments + ' -Hidden').Trim()
    if ($Launcher -and (Test-Path -LiteralPath $Launcher)) {
        return [pscustomobject]@{ Target = $Launcher; Arguments = $Arguments }
    }
    $ps = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    $a = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" {1}' -f (Get-KohaScriptPath), $Arguments
    if ($Wscript -and (Test-Path -LiteralPath $Wscript)) {
        $js = [System.IO.Path]::Combine((Get-KohaPath Bin), 'KohaEasy.Hidden.js')
        return [pscustomobject]@{ Target = $Wscript; Arguments = ('//B //Nologo "{0}" {1}' -f $js, $Arguments) }
    }
    if ($Conhost -and (Test-Path -LiteralPath $Conhost)) {
        return [pscustomobject]@{ Target = $Conhost; Arguments = ('--headless "{0}" {1}' -f $ps, $a) }
    }
    return [pscustomobject]@{ Target = $ps; Arguments = $a }
}

# conhost.exe, unless the installer found that it does not start Koha's
# tools on this PC (state.json hiddenLaunch = powershell).
function Get-KohaConhostPath {
    if ((Get-KohaState).hiddenLaunch -eq 'powershell') { return '' }
    return [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'conhost.exe')
}

# wscript.exe with KohaEasy.Hidden.js next to KohaEasy.ps1, unless the
# installer found that it does not start Koha's tools on this PC
# (hiddenLaunch = nowscript, or powershell).
function Get-KohaWscriptPath {
    if (@('nowscript', 'powershell') -contains (Get-KohaState).hiddenLaunch) { return '' }
    if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine((Get-KohaPath Bin), 'KohaEasy.Hidden.js')))) { return '' }
    return [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'wscript.exe')
}

# KohaEasy.ps1 commands that must never show a console: the windows, the
# tray and what the shortcuts and the tray menu run. The scheduled tasks'
# Run and UpdatePortProxy, and the commands the installer waits on, are
# left alone.
$script:HiddenCommands = @('Launch', 'Window', 'Tray', 'Panel', 'Terminal', 'Open', 'Start', 'Stop', 'Restart', 'SafeShutdown', 'RestartServices', 'RebuildIndex', 'ExportReport', 'ExportDiagnostics', 'CheckDisk')

# Pure: whether KohaEasy.ps1 should start itself again the hidden way and
# end, which closes the console it was given. That console comes from a
# launch without -Hidden: a shortcut, sign-in entry or task of an earlier
# version, or powershell.exe itself (Windows Terminal keeps an empty window
# for it). Only when the hidden launch is not powershell.exe itself, so it
# can never loop.
function Test-KohaRelaunchHidden {
    param([string]$Command, [bool]$Hidden, [string]$Target = (Get-KohaHiddenLaunch -Arguments '').Target)
    if ($Hidden -or $env:KOHAEASY_NO_RELAUNCH -eq '1') { return $false }
    if ($script:HiddenCommands -notcontains $Command) { return $false }
    return (($Target -split '[\\/]')[-1] -ne 'powershell.exe')
}

# Pure: the command line of that second start, from KohaEasy.ps1's own
# parameters.
function Get-KohaRelaunchArguments {
    param([string]$Command, [System.Collections.IDictionary]$Bound)
    $a = @($Command)
    foreach ($k in 'Trigger', 'Mode', 'Action') { if ($Bound.Contains($k) -and $Bound[$k]) { $a += ('-{0} {1}' -f $k, $Bound[$k]) } }
    foreach ($k in 'Force', 'Quiet', 'Pause') { if ($Bound.Contains($k) -and [bool]$Bound[$k]) { $a += ('-' + $k) } }
    return ($a -join ' ')
}

# KohaEasy.exe, once the installer built it and Windows let it run
# (state.json launcher = ok); '' otherwise.
function Get-KohaLauncherPath {
    if ((Get-KohaState).launcher -ne 'ok') { return '' }
    return [System.IO.Path]::Combine((Get-KohaPath Bin), 'KohaEasy.exe')
}

# ----------------------------------------------------------------------
# KohaEasy.exe (windows\KohaEasy.Launcher.cs)
# ----------------------------------------------------------------------
# Built here, on this PC, by the C# compiler of the .NET Framework that
# Windows 10 and 11 ship: nothing is downloaded, so SmartScreen does not ask,
# and the source next to it is what runs. Windows can still refuse it (Smart
# App Control, some antivirus): a program that does not pass its self-test
# is not used, and everything keeps starting through conhost --headless.

# Pure: the compiler options. A Windows (GUI) program with the Koha icon.
function Get-KohaLauncherCompilerOptions {
    param([string]$Icon)
    $o = '/target:winexe /platform:anycpu /optimize+'
    if ($Icon) { $o += (' /win32icon:"{0}"' -f $Icon) }
    return $o
}

# The C# compiler of the .NET Framework (CodeDom starts csc.exe).
function Invoke-KohaCsc {
    param([string]$Source, [string]$Output, [string]$Options)
    $provider = New-Object Microsoft.CSharp.CSharpCodeProvider
    $p = New-Object System.CodeDom.Compiler.CompilerParameters
    $p.GenerateExecutable = $true
    $p.GenerateInMemory = $false
    $p.OutputAssembly = $Output
    $p.CompilerOptions = $Options
    [void]$p.ReferencedAssemblies.Add('System.dll')
    $res = $provider.CompileAssemblyFromSource($p, [System.IO.File]::ReadAllText($Source))
    $errors = @($res.Errors | Where-Object { -not $_.IsWarning } | ForEach-Object { $_.ToString() })
    if ($errors.Count -gt 0) { throw ('KohaEasy.exe did not compile: ' + ($errors -join '; ')) }
}

# Whether Windows lets KohaEasy.exe run ("KohaEasy.exe --self-test" exits 0).
function Test-KohaLauncher {
    param([string]$Path)
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo($Path, '--self-test')
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        if (-not $p.WaitForExit(20000)) {
            try { $p.Kill() } catch { }
            Write-KohaLog 'KohaEasy.exe: the self-test did not end in 20 s'
            return $false
        }
        if ($p.ExitCode -ne 0) { Write-KohaLog ('KohaEasy.exe: self-test exit {0}' -f $p.ExitCode) }
        return ($p.ExitCode -eq 0)
    } catch {
        Write-KohaLog ('KohaEasy.exe does not run on this PC: ' + $_.Exception.Message)
        return $false
    }
}

# Puts a new file in place of $Path. A KohaEasy.exe that is running (the
# tray, a window) cannot be replaced or deleted, but it can be renamed: the
# old copy is set aside and removed on a later run.
function Set-KohaFileInPlace {
    param([string]$NewFile, [string]$Path)
    $dir = Split-Path -Parent $Path
    $name = Split-Path -Leaf $Path
    Get-ChildItem -LiteralPath $dir -Filter ($name + '.old-*') -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $Path) {
        try {
            Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
        } catch {
            Move-Item -LiteralPath $Path -Destination ('{0}.old-{1}' -f $Path, [DateTime]::Now.Ticks) -Force
        }
    }
    Move-Item -LiteralPath $NewFile -Destination $Path -Force
}

# Builds KohaEasy.exe when its source changed (or it is missing) and checks
# that Windows lets it run. Returns current | built | failed | refused |
# no-source; state.json launcher (ok | failed | refused) says whether the
# Koha tools use it.
function Install-KohaLauncher {
    param(
        [string]$Bin = (Get-KohaPath Bin),
        [scriptblock]$Compile = { param($Source, $Output, $Options) Invoke-KohaCsc -Source $Source -Output $Output -Options $Options },
        [scriptblock]$SelfTest = { param($Path) Test-KohaLauncher -Path $Path }
    )
    $src = [System.IO.Path]::Combine($Bin, 'KohaEasy.Launcher.cs')
    $exe = [System.IO.Path]::Combine($Bin, 'KohaEasy.exe')
    if (-not (Test-Path -LiteralPath $src)) {
        Set-KohaState @{ launcher = 'failed' } | Out-Null
        return 'no-source'
    }
    $hash = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
    $state = Get-KohaState
    if ($state.launcher -eq 'ok' -and $state.launcherHash -eq $hash -and (Test-Path -LiteralPath $exe)) { return 'current' }
    # The tray did not come up through this KohaEasy.exe (the installer's
    # check): not tried again until its source changes.
    if ($state.launcher -eq 'refused' -and $state.launcherHash -eq $hash) { return 'refused' }
    $tmp = [System.IO.Path]::Combine($Bin, ('KohaEasy.{0}.new.exe' -f [guid]::NewGuid().ToString('N')))
    try {
        $icon = [System.IO.Path]::Combine($Bin, 'koha.ico')
        if (-not (Test-Path -LiteralPath $icon)) { $icon = '' }
        & $Compile $src $tmp (Get-KohaLauncherCompilerOptions -Icon $icon)
        if (-not (Test-Path -LiteralPath $tmp)) { throw 'the compiler wrote no KohaEasy.exe' }
        if (-not (& $SelfTest $tmp)) { throw 'Windows did not let KohaEasy.exe run (Smart App Control or an antivirus)' }
        Set-KohaFileInPlace -NewFile $tmp -Path $exe
        Set-KohaState @{ launcher = 'ok'; launcherHash = $hash } | Out-Null
        Write-KohaLog 'KohaEasy.exe built and checked'
        return 'built'
    } catch {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        Set-KohaState @{ launcher = 'failed'; launcherHash = $hash } | Out-Null
        Write-KohaLog ('KohaEasy.exe not used: ' + $_.Exception.Message)
        return 'failed'
    }
}

# KohaEasy.Native (in KohaEasy.exe) for this PowerShell: the Koha identity
# on the taskbar and on the shortcuts. $false when KohaEasy.exe is not used.
function Import-KohaNative {
    if ('KohaEasy.Native' -as [type]) { return $true }
    $exe = Get-KohaLauncherPath
    if (-not $exe -or -not (Test-Path -LiteralPath $exe)) { return $false }
    try {
        [void][System.Reflection.Assembly]::LoadFrom($exe)
        return [bool]('KohaEasy.Native' -as [type])
    } catch {
        Write-KohaLog ('KohaEasy.exe could not be loaded: ' + $_.Exception.Message)
        return $false
    }
}

# The windows of this process group on the taskbar as Koha (with the Koha
# shortcut's name and icon when pinned), not as Windows PowerShell.
function Set-KohaProcessAppId {
    if (-not [bool](Get-KohaState).appIdShortcut) { return $false }
    if (-not (Import-KohaNative)) { return $false }
    try { return [bool][KohaEasy.Native]::SetProcessAppId($script:Cfg.AppId) } catch { return $false }
}

# An open Koha window, restored and brought to the front (the Koha icon
# clicked again): KohaEasy.Native when KohaEasy.exe is in use, else the
# Windows shell.
function Show-KohaOpenWindow {
    param([string]$Title)
    if (Import-KohaNative) {
        try { if ([KohaEasy.Native]::FocusWindow($Title)) { return $true } } catch { }
    }
    try { return [bool](New-Object -ComObject WScript.Shell).AppActivate($Title) } catch { return $false }
}

function Set-KohaShortcutAppId {
    param([string]$Path)
    if (-not (Import-KohaNative)) { return $false }
    try {
        [KohaEasy.Native]::SetShortcutAppId($Path, $script:Cfg.AppId)
        return $true
    } catch {
        Write-KohaLog ('shortcut identity not set on {0}: {1}' -f $Path, $_.Exception.Message)
        return $false
    }
}

function Start-KohaHidden {
    param([string]$Arguments)
    $l = Get-KohaHiddenLaunch -Arguments $Arguments
    Start-Process -FilePath $l.Target -ArgumentList $l.Arguments -WindowStyle Hidden | Out-Null
}

# A small Koha dialog with buttons of its own ([ordered]@{ key = label }),
# for questions a Yes/No box cannot ask. Returns the key, or the last key
# when the window is closed.
function Show-KohaChoice {
    param([string]$Text, [System.Collections.IDictionary]$Choices, [string]$Title = (Get-KohaAppTitle))
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $keys = @($Choices.Keys)
    $form = New-Object System.Windows.Forms.Form
    $form.Text = $Title
    $form.Font = New-Object System.Drawing.Font('Segoe UI', 9)
    $form.AutoScaleDimensions = New-Object System.Drawing.SizeF(96, 96)
    $form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Dpi
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.TopMost = $true
    $form.AutoSize = $true
    $form.AutoSizeMode = [System.Windows.Forms.AutoSizeMode]::GrowAndShrink
    $icon = Get-KohaIcon
    if ($icon) { $form.Icon = $icon }
    $layout = New-Object System.Windows.Forms.TableLayoutPanel
    $layout.AutoSize = $true
    $layout.Padding = New-Object System.Windows.Forms.Padding(12)
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Text
    $label.AutoSize = $true
    $label.MaximumSize = New-Object System.Drawing.Size(420, 0)
    $label.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 12)
    [void]$layout.Controls.Add($label, 0, 0)
    $row = New-Object System.Windows.Forms.FlowLayoutPanel
    $row.AutoSize = $true
    $row.FlowDirection = [System.Windows.Forms.FlowDirection]::LeftToRight
    $form.Tag = $keys[-1]
    foreach ($k in $keys) {
        $b = New-Object System.Windows.Forms.Button
        $b.Text = [string]$Choices[$k]
        $b.AutoSize = $true
        $b.Tag = $k
        $b.add_Click({ param($sender, $e) $form.Tag = $sender.Tag; $form.Close() }.GetNewClosure())
        [void]$row.Controls.Add($b)
    }
    $form.AcceptButton = $row.Controls[0]
    $form.CancelButton = $row.Controls[$row.Controls.Count - 1]
    [void]$layout.Controls.Add($row, 0, 1)
    $form.Controls.Add($layout)
    [void]$form.ShowDialog()
    $choice = [string]$form.Tag
    $form.Dispose()
    return $choice
}

# Two tasks of the user (no administrator rights, no stored password):
#   "Keep Koha running"      action Run: holds the distro open; triggers on
#                            unlock and on resume only repair a Koha meant to run.
#   "Start Koha at sign-in"  action Start -Trigger logon; enabled only in
#                            "logon" mode.
function Get-KohaScriptPath { return [System.IO.Path]::Combine((Get-KohaPath Bin), 'KohaEasy.ps1') }

# The tasks start like the shortcuts: with no window. A task that ran
# powershell.exe itself opened an empty Windows Terminal window at sign-in
# on Windows 11, and the keep-alive task kept it open all day.
function New-KohaAction {
    param([string]$Arguments)
    $l = Get-KohaHiddenLaunch -Arguments $Arguments
    return New-ScheduledTaskAction -Execute $l.Target -Argument $l.Arguments -WorkingDirectory (Get-KohaPath Bin)
}

function Register-KohaTasks {
    param([ValidateSet('logon', 'manual')][string]$Autostart = (Get-KohaState).autostart)
    $user = '{0}\{1}' -f $env:USERDOMAIN, $env:USERNAME
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $keepSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -Hidden
    $ns = 'Root/Microsoft/Windows/TaskScheduler'
    $unlock = New-CimInstance -CimClass (Get-CimClass -Namespace $ns -ClassName MSFT_TaskSessionStateChangeTrigger) -ClientOnly -Property @{ StateChange = 8; UserId = $user }
    $resume = New-CimInstance -CimClass (Get-CimClass -Namespace $ns -ClassName MSFT_TaskEventTrigger) -ClientOnly -Property @{
        Subscription = '<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name=''Microsoft-Windows-Power-Troubleshooter''] and EventID=1]]</Select></Query></QueryList>'
    }
    Register-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.KeepTask -Action (New-KohaAction 'Run') `
        -Trigger @($unlock, $resume) -Principal $principal -Settings $keepSettings -Force | Out-Null

    $signSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -Hidden
    $logon = New-ScheduledTaskTrigger -AtLogOn -User $user
    Register-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.SignInTask -Action (New-KohaAction 'Start -Trigger logon') `
        -Trigger $logon -Principal $principal -Settings $signSettings -Force | Out-Null
    Set-KohaAutostart -Mode $Autostart | Out-Null
}

# Whether the keep-alive task is running now with another action than this
# version's (an older version started PowerShell with a window of its own,
# which stays open until that run ends).
function Test-KohaKeepAliveOutdated {
    try {
        $t = Get-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.KeepTask -ErrorAction Stop
    } catch { return $false }
    if ($null -eq $t -or [string]$t.State -ne 'Running') { return $false }
    $want = Get-KohaHiddenLaunch -Arguments 'Run'
    $a = @($t.Actions)[0]
    return -not ([string]$a.Execute -eq $want.Target -and [string]$a.Arguments -eq $want.Arguments)
}

function Test-KohaTaskPresent {
    param([string]$Name)
    try { return ($null -ne (Get-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $Name -ErrorAction Stop)) } catch { return $false }
}

# Koha starts through its keep-alive task, and the sign-in task starts it
# at sign-in: a task that was deleted by hand (Task Scheduler) is made again,
# with this version's hidden launch, before Koha is started.
function Repair-KohaTasks {
    if ((Test-KohaTaskPresent $script:Cfg.KeepTask) -and (Test-KohaTaskPresent $script:Cfg.SignInTask)) { return 'present' }
    $mode = [string](Get-KohaState).autostart
    if (@('logon', 'manual') -notcontains $mode) { $mode = 'logon' }
    Write-KohaLog ('Koha tasks missing; registering them again (autostart {0})' -f $mode)
    Register-KohaTasks -Autostart $mode
    return 'registered'
}

function Set-KohaSignInTask {
    param([bool]$Enabled)
    if (-not (Test-KohaTaskPresent $script:Cfg.SignInTask)) {
        $mode = 'manual'
        if ($Enabled) { $mode = 'logon' }
        Register-KohaTasks -Autostart $mode
        return
    }
    if ($Enabled) {
        Enable-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.SignInTask | Out-Null
    } else {
        Disable-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.SignInTask | Out-Null
    }
}
function Start-KohaKeepAlive { Start-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.KeepTask }
function Stop-KohaKeepAlive {
    Stop-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.KeepTask -ErrorAction SilentlyContinue
    # Started through KohaEasy.exe, the task's PowerShell is a child process,
    # which Task Scheduler leaves running when it ends the task.
    try {
        Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction Stop |
            Where-Object { $_.ProcessId -ne $PID -and ([string]$_.CommandLine) -match 'KohaEasy\.ps1"?\s+Run(\s|$)' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch { }
}

# "Start Koha automatically when I sign in to Windows": Yes (logon) / No (manual).
# Changes only the sign-in task and the saved choice; never stops a running Koha.
function Set-KohaAutostart {
    param([Parameter(Mandatory = $true)][ValidateSet('logon', 'manual')][string]$Mode)
    Set-KohaSignInTask -Enabled ($Mode -eq 'logon')
    Set-KohaState @{ autostart = $Mode } | Out-Null
    Update-KohaHandshake | Out-Null
    Write-KohaLog "autostart set to $Mode"
    return $Mode
}

# Waits until the staff interface answers (any HTTP status below 500).
function Wait-KohaHttp {
    param([int]$Seconds = $script:Cfg.StartWaitS, [scriptblock]$OnTick)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $script:Cfg.StaffUrl -UseBasicParsing -TimeoutSec 5 -MaximumRedirection 0 -ErrorAction Stop
            if ([int]$r.StatusCode -lt 500) { return $true }
        } catch {
            $resp = $null
            if ($_.Exception.PSObject.Properties['Response']) { $resp = $_.Exception.Response }
            if ($null -ne $resp -and [int]$resp.StatusCode -lt 500) { return $true }
        }
        if ($OnTick) { & $OnTick }
        Start-Sleep -Seconds 3
    }
    return $false
}

# KohaEasy.ps1 Start [-Trigger user|logon]
#   user   the Koha - Start shortcut or the tray: always starts
#   logon  the sign-in task: starts only in "logon" mode
function Start-Koha {
    param([ValidateSet('user', 'logon')][string]$Trigger = 'user', [switch]$Wait)
    $state = Get-KohaState
    if ($Trigger -eq 'logon' -and $state.autostart -ne 'logon') {
        Write-KohaLog 'sign-in: automatic start is off, nothing started'
        return 'skipped'
    }
    Set-KohaState @{ desired = 'running'; startedAt = (Get-UnixTime); poweredOffAt = 0 } | Out-Null
    try { Repair-KohaTasks | Out-Null } catch { Write-KohaLog ('Koha tasks not registered again: ' + $_.Exception.Message) }
    Start-KohaKeepAlive
    Write-KohaLog "start requested ($Trigger)"
    if (-not $Wait) { return 'started' }
    if (Wait-KohaHttp) { return 'ready' }
    return 'timeout'
}

# Windows is shutting down, restarting or signing out (the tray's session
# window): Koha is stopped cleanly in the time Windows gives, without
# changing what the librarian wants, so it starts again at the next sign-in
# in automatic mode. A power cut or a forced shutdown never gets here; the
# clean-stop guard inside Debian repairs Koha at the next start instead.
# At the end of a session Windows closes every console program with it
# (CTRL_SHUTDOWN_EVENT), and every wsl.exe the other stops start is one:
# the stop could be cut off halfway, and the next start then reported an
# unclean stop. So the tray runs the stop script already written into
# Debian (Update-KohaStopScript) through a wsl.exe with no console at all
# (DETACHED_PROCESS, $RunDetached), then ends the distro the same way.
# The tray calls it only while Koha runs, so it never asks WSL first. After
# "Shut down the PC safely" Koha is already stopped, and the tray may not
# have noticed yet: running the stop then would start Debian again.
# It ends with "wsl --shutdown", not "--terminate": Windows is ending the
# session anyway, and the whole WSL virtual machine stops with Debian's
# virtual disk (ext4.vhdx) closed, instead of being stopped by Windows.
function Stop-KohaForSessionEnd {
    param([scriptblock]$RunDetached = { param($CommandLine, $TimeoutMs) [KohaSessionWindow]::RunDetached($CommandLine, $TimeoutMs) })
    $wsl = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'wsl.exe')
    $state = Get-KohaState
    $off = [int64]$state.poweredOffAt
    if ($off -gt 0 -and ((Get-UnixTime) - $off) -lt 600) {
        Write-KohaLog 'Windows is ending the session: Koha was already stopped safely for it'
        return 'not_running'
    }
    if ($state.stopScriptHash -eq (Get-KohaStopScriptHash)) {
        Write-KohaLog 'Windows is ending the session: stopping Koha cleanly'
        $cmd = '"{0}" -d {1} -u root -- timeout -k 5 {2} sh {3}' -f $wsl, $script:Cfg.Distro, $script:Cfg.StopWaitS, $script:Cfg.StopScript
        $clock = [System.Diagnostics.Stopwatch]::StartNew()
        $code = [int](& $RunDetached $cmd (([int]$script:Cfg.StopWaitS + 10) * 1000))
        # A wsl.exe that failed at once (it could not run without a console)
        # stopped nothing: the usual stop below still can.
        $quick = ($code -gt 0 -and $clock.Elapsed.TotalSeconds -lt 2)
        if ($code -ne -2 -and -not $quick) {
            $how = 'clean'
            if ($code -ne 0) { $how = 'forced' }
            & $RunDetached ('"{0}" --shutdown' -f $wsl) 30000 | Out-Null
            Write-KohaLog ('session end: {0} stopped: {1} (exit {2})' -f $script:Cfg.Distro, $how, $code)
            return $how
        }
        Write-KohaLog ('session end: wsl.exe without a console did not run the stop (exit {0}); trying the usual stop' -f $code)
    } else {
        Write-KohaLog 'Windows is ending the session: the stop script is not in Debian yet; trying the usual stop'
    }
    if (-not (Test-KohaDistroRunning)) { return 'not_running' }
    return (Stop-KohaDebianGracefully -Shutdown)
}

# KohaEasy.ps1 Stop: desired=stopped first, so the keep-alive task's
# restart-on-failure does not bring Koha back a minute later. -OnStep as in
# Stop-KohaDebianGracefully.
function Stop-Koha {
    param([scriptblock]$OnStep)
    $more = @{}
    if ($OnStep) { $more.OnStep = $OnStep }
    $how = Stop-KohaDebianGracefully -SetStopped @more
    Write-KohaLog "stopped by the user ($how)"
    return 'stopped'
}

# The five steps of a safe stop, as the librarian reads them. Steps 1 to 4
# run inside Debian (the stop script says "@step N" as it reaches each),
# step 5 is WSL closing Debian.
function Get-KohaStopSteps {
    return @(
        (T 'Stopping the web interface and the search engine (Zebra)')
        (T 'Stopping the message queue and the cache')
        (T 'Closing the database (MariaDB) safely')
        (T 'Writing everything to disk')
        (T 'Closing Debian and its virtual disk')
    )
}

# "Shut down the PC safely" (KohaEasy.ps1 SafeShutdown): Koha's services
# stop in order, everything is written to disk and all of WSL stops, before
# Windows is asked to shut down or restart. What the librarian wants stays
# as it is, so Koha starts again at the next sign-in in automatic mode; and
# poweredOffAt tells the tray's own end-of-session stop that there is
# nothing left to stop. Should someone cancel the Windows shutdown, the
# keep-alive task starts Koha again within a minute (it clears the mark).
# Returns clean, forced or not_running, as Stop-KohaDebianGracefully.
function Stop-KohaForPowerOff {
    param([scriptblock]$OnStep)
    Update-KohaStopScript | Out-Null
    $more = @{}
    if ($OnStep) { $more.OnStep = $OnStep }
    $how = Stop-KohaDebianGracefully -Shutdown @more
    Set-KohaState @{ poweredOffAt = (Get-UnixTime) } | Out-Null
    Write-KohaLog "stopped to shut down the PC ($how)"
    return $how
}

# Pure: shutdown.exe's arguments. No delay: Koha is already stopped, and
# Windows still asks the open programs to close (unsaved work stops it).
function Get-KohaPowerOffArguments {
    param([switch]$Restart)
    if ($Restart) { return @('/r', '/t', '0') }
    return @('/s', '/t', '0')
}

function Invoke-KohaPowerOff {
    param([switch]$Restart)
    $exe = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'shutdown.exe')
    $a = Get-KohaPowerOffArguments -Restart:$Restart
    Write-KohaLog ('asking Windows to {0}' -f $(if ($Restart) { 'restart' } else { 'shut down' }))
    Start-Process -FilePath $exe -ArgumentList $a -WindowStyle Hidden
}

# What Debian runs before WSL stops it: Koha's services in the order a
# clean shutdown uses (the web first, then the queue and the cache, then
# MariaDB), Plack, Zebra and the workers of each instance even when the
# panel started them outside koha-common, then "koha-stop-guard stop",
# which records the clean stop the next boot looks for. Exit 0 only when
# everything stopped and the guard recorded it.
$script:GracefulStopScript = @'
if [ "$(ps -p 1 -o comm= 2>/dev/null)" != "systemd" ]; then sync; exit 0; fi
rc=0
# "@step N": how far the stop got, for the progress the Windows side shows.
stop_units() {
  units=""
  for s in "$@"; do systemctl cat "$s.service" >/dev/null 2>&1 && units="$units $s.service"; done
  [ -n "$units" ] || return 0
  systemctl stop $units || { echo "did not stop:$units"; rc=1; }
}
echo "@step 1"
stop_units apache2 koha-common
for i in $(koha-list 2>/dev/null); do
  for t in koha-plack koha-worker koha-indexer koha-es-indexer koha-zebra; do
    command -v "$t" >/dev/null 2>&1 && "$t" --stop "$i" >/dev/null 2>&1
  done
done
echo "@step 2"
stop_units rabbitmq-server memcached elasticsearch
echo "@step 3"
stop_units mariadb
echo "@step 4"
sync
if [ -x /usr/local/sbin/koha-stop-guard ]; then
  /usr/local/sbin/koha-stop-guard stop || { echo "not marked clean (see /var/log/koha-easy-install/stop-guard.log)"; rc=1; }
else
  echo "no clean-stop guard in this Debian yet"
fi
exit $rc
'@

# The stop script as a file in Debian ($Cfg.StopScript), for the end of a
# Windows session. Written while Debian runs, again whenever the script
# changes; state.json stopScriptHash records the version written.
function Get-KohaStopScriptHash {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes(($script:GracefulStopScript -replace "`r", '')))
        return (($bytes | ForEach-Object { $_.ToString('x2') }) -join '')
    } finally { $sha.Dispose() }
}

function Update-KohaStopScript {
    $hash = Get-KohaStopScriptHash
    if ((Get-KohaState).stopScriptHash -eq $hash) { return 'current' }
    if (-not (Test-KohaDistroRunning)) { return 'not_running' }
    $r = Invoke-KohaLinuxScript -Script ($script:WindowScriptInstall.Replace('__PATH__', $script:Cfg.StopScript)) -InputText $script:GracefulStopScript
    if ($r.ExitCode -ne 0) { Write-KohaLog ('stop script not written: ' + $r.Output); return 'failed' }
    Set-KohaState @{ stopScriptHash = $hash } | Out-Null
    Write-KohaLog ('stop script written to ' + $script:Cfg.StopScript)
    return 'written'
}

# The one way the Windows tools stop Debian (Stop, Restart, disk compaction,
# diagnostics, the installer's restarts): Koha's services are stopped
# inside Debian first, so MariaDB and Zebra are never cut off mid-write, and
# WSL stops the distro only afterwards. When that takes longer than
# $TimeoutSeconds, Debian is stopped anyway: the clean-stop mark is then
# missing, and the next start checks and repairs Koha.
#   -SetStopped  the librarian stopped Koha: desired=stopped and the
#                keep-alive task ended first, so it does not start Koha again
#   -Shutdown    "wsl --shutdown" (all of WSL) instead of "--terminate"
#   -OnStep      called with 1 to 5 as the stop reaches each step of
#                Get-KohaStopSteps (the progress windows show them)
# Returns clean, forced (a service did not stop, or the timeout) or
# not_running (nothing to stop: a stopped distro is never started for this).
function Stop-KohaDebianGracefully {
    param([string]$Distro = $script:Cfg.Distro, [switch]$SetStopped, [switch]$Shutdown, [int]$TimeoutSeconds = $script:Cfg.StopWaitS, [scriptblock]$OnStep)
    if ($SetStopped) {
        Set-KohaState @{ desired = 'stopped'; startedAt = 0 } | Out-Null
        Stop-KohaKeepAlive
    }
    $how = 'not_running'
    if (@(Get-KohaRunningDistros) -contains $Distro) {
        $more = @{}
        if ($OnStep) { $more.OnLine = { param($l) if ($l -match '^@step (\d+)') { & $OnStep ([int]$Matches[1]) } }.GetNewClosure() }
        $r = Invoke-KohaLinuxScript -Script $script:GracefulStopScript -Distro $Distro -TimeoutSeconds $TimeoutSeconds @more
        if ($r.ExitCode -eq 0) {
            $how = 'clean'
        } else {
            $how = 'forced'
            $why = ((([string]$r.Output) -split "`n" | Where-Object { $_ -notmatch '^@step ' }) -join "`n").Trim()
            if ($r.ExitCode -eq 124) { $why = ('Koha did not stop within {0} s. {1}' -f $TimeoutSeconds, $why).Trim() }
            Write-KohaLog ('graceful stop of {0} incomplete (exit {1}): {2}' -f $Distro, $r.ExitCode, $why)
        }
    }
    if ($OnStep) { try { & $OnStep 5 } catch { } }
    if ($Shutdown) {
        Invoke-KohaWsl -Arguments @('--shutdown') | Out-Null
    } else {
        Invoke-KohaWsl -Arguments @('--terminate', $Distro) | Out-Null
    }
    Write-KohaLog ('{0} stopped: {1}' -f $Distro, $how)
    return $how
}

# Pure: the process that holds Debian open ("sleep infinity" in the distro).
# CREATE_NO_WINDOW: a wsl.exe started with Start-Process -WindowStyle Hidden
# could still get a window of its own from Windows Terminal.
function Get-KohaHolderStartInfo {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'wsl.exe')
    $psi.Arguments = '-d {0} -u root --exec /bin/sleep infinity' -f $script:Cfg.Distro
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    return $psi
}

# The keep-alive task's action. Exits at once when Koha is meant to be off
# (Stop pressed, or an unlock/resume trigger while it was off). Otherwise it
# refreshes the handshake, starts the holder that keeps the distro alive and
# waits on it; a holder that dies ends the task with an error, and the task
# setting restarts it one minute later.
function Invoke-KohaRun {
    param([scriptblock]$Holder, [int]$WatchMs = 60000)
    $state = Get-KohaState
    if ($state.desired -ne 'running') {
        Write-KohaLog 'keep-alive: Koha is meant to be stopped, exiting'
        return 0
    }
    if (-not $Holder) { $Holder = { [System.Diagnostics.Process]::Start((Get-KohaHolderStartInfo)) } }
    if ([int64]$state.poweredOffAt -gt 0) { Set-KohaState @{ poweredOffAt = 0 } | Out-Null }
    $proc = & $Holder
    Start-Sleep -Seconds 2
    Update-KohaHandshake | Out-Null
    Start-KohaNetworkTask | Out-Null
    Update-KohaStopScript | Out-Null
    # Stop pressed meanwhile: not a failure.
    if (-not (Wait-KohaHttp) -and (Get-KohaState).desired -eq 'running') {
        Write-KohaLog 'keep-alive: the staff interface did not answer in time' 'health'
        Show-KohaNotification -Title (T 'Koha did not start') -Text (T 'Koha did not start. Open Koha - Status, or export the diagnostics from the tray menu.') -Level error | Out-Null
    }
    # While Koha runs, the Koha icon comes back within a minute if it
    # crashed or was ended (at most 5 times, so a broken tray cannot loop).
    $trayRestarts = 0
    while (-not $proc.WaitForExit($WatchMs)) {
        if ($trayRestarts -lt 5 -and (Get-KohaState).desired -eq 'running' -and (Repair-KohaTray) -eq 'restarted') { $trayRestarts++ }
    }
    if ((Get-KohaState).desired -ne 'running') { return 0 }
    Write-KohaLog "keep-alive: the WSL holder ended (exit $($proc.ExitCode)); the task will restart it"
    return 1
}

# ----------------------------------------------------------------------
# Other PCs of the library network (ports 80 and 8080)
# ----------------------------------------------------------------------
# Apache inside Debian listens on every address. What Windows adds, once,
# with administrator rights (KohaEasy.ps1 SetupNetwork), for both network
# modes, so a WSL that falls back from mirrored to NAT (or comes back)
# needs nothing new:
#   * a Windows Firewall rule for TCP 80 and 8080 from the local network;
#   * the same ports in the Hyper-V firewall, which guards WSL in mirrored
#     mode (Windows 11);
#   * a task "Koha network" with the user's highest rights, started at each
#     start of Koha: under NAT it points netsh portproxy at Debian's
#     address, which changes at every start of WSL; under mirrored it
#     removes that forwarding, which would take the ports away from Debian.
# .wslconfig also gets hostAddressLoopback (Merge-KohaWslConfig): in
# mirrored mode this PC reaches Koha by its own network address only with
# it, and the library network test (Test-KohaLanAccess) goes that way.
$script:WslVmCreatorId = '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}'

# Debian's IPv4 address in WSL's NAT network, or '' (never starts the distro).
function Get-KohaWslIp {
    if (-not (Test-KohaDistroRunning)) { return '' }
    $r = Invoke-KohaLinux -Command @('hostname', '-I')
    if ($r.ExitCode -ne 0) { return '' }
    foreach ($ip in ($r.Output -split '\s+')) {
        if (Test-KohaIPv4 $ip) { return $ip }
    }
    return ''
}

function Test-KohaIPv4 {
    param([string]$Address)
    if ($Address -notmatch '^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$') { return $false }
    foreach ($i in 1..4) { if ([int]$Matches[$i] -gt 255) { return $false } }
    return $true
}

# Pure: the netsh commands that point ports 80 and 8080 of every Windows
# address at Debian (delete first, so a changed address never stacks up).
function Get-KohaPortProxyCommands {
    param([Parameter(Mandatory = $true)][string]$WslIp, [int[]]$Ports = $script:Cfg.WebPorts)
    $cmds = New-Object System.Collections.ArrayList
    foreach ($port in $Ports) {
        [void]$cmds.Add(@('interface', 'portproxy', 'delete', 'v4tov4', ('listenport={0}' -f $port), 'listenaddress=0.0.0.0'))
        [void]$cmds.Add(@('interface', 'portproxy', 'add', 'v4tov4', ('listenport={0}' -f $port), 'listenaddress=0.0.0.0', ('connectport={0}' -f $port), ('connectaddress={0}' -f $WslIp)))
    }
    return @($cmds)
}

# Pure: the rows of "netsh interface portproxy show v4tov4" (listen address
# and port, connect address and port). The headers, translated by Windows,
# are skipped.
function ConvertFrom-KohaPortProxyTable {
    param([AllowEmptyString()][string]$Text)
    $rows = New-Object System.Collections.ArrayList
    foreach ($l in (([string]$Text) -split "`r?`n")) {
        if ($l -match '^\s*(\S+)\s+(\d+)\s+(\S+)\s+(\d+)\s*$') {
            [void]$rows.Add([pscustomobject]@{ ListenAddress = $Matches[1]; ListenPort = [int]$Matches[2]; ConnectAddress = $Matches[3]; ConnectPort = [int]$Matches[4] })
        }
    }
    return @($rows)
}

# The forwarding Windows has now (reading it needs no administrator rights).
function Get-KohaPortProxyRules {
    $out = & netsh.exe interface portproxy show v4tov4 2>&1
    return @(ConvertFrom-KohaPortProxyTable -Text ((@($out) | ForEach-Object { [string]$_ }) -join "`n"))
}

# Mirrored mode: Koha's forwarding from a time WSL ran in NAT mode is
# removed, so ports 80 and 8080 of this PC go to Debian again.
function Remove-KohaPortProxy {
    $ours = @(Get-KohaPortProxyRules | Where-Object { $_.ListenAddress -eq '0.0.0.0' -and ($script:Cfg.WebPorts -contains $_.ListenPort) })
    foreach ($r in $ours) {
        & netsh.exe interface portproxy delete v4tov4 ('listenport={0}' -f $r.ListenPort) 'listenaddress=0.0.0.0' 2>&1 | Out-Null
    }
    if ($ours.Count -gt 0) { Write-KohaLog ('network: mirrored mode, port forwarding of {0} removed' -f (@($ours | ForEach-Object { $_.ListenPort }) -join ', ')) 'network' }
    return $ours.Count
}

# KohaEasy.ps1 UpdatePortProxy: the action of the "Koha network" task.
function Update-KohaPortProxy {
    param([string]$WslIp, [string]$Mode = (Get-KohaNetMode))
    if ($Mode -eq 'mirrored') {
        Remove-KohaPortProxy | Out-Null
        return 'mirrored'
    }
    if (-not $WslIp) { $WslIp = Get-KohaWslIp }
    if (-not (Test-KohaIPv4 $WslIp)) {
        Write-KohaLog 'network: Debian has no address yet, port forwarding not changed' 'network'
        return 'no-address'
    }
    foreach ($c in Get-KohaPortProxyCommands -WslIp $WslIp) {
        $out = & netsh.exe @c 2>&1
        if ($LASTEXITCODE -ne 0 -and $c[2] -eq 'add') {
            Write-KohaLog ('network: netsh {0} failed: {1}' -f ($c -join ' '), (@($out) -join ' ')) 'network'
            return 'failed'
        }
    }
    Write-KohaLog ('network: ports {0} forwarded to {1}' -f ($script:Cfg.WebPorts -join ', '), $WslIp) 'network'
    return 'forwarded'
}

# KohaEasy.ps1 SetupNetwork (administrator): the firewall rules, the
# "Koha network" task and the forwarding the current mode needs. Safe to
# run again.
function Set-KohaLanAccess {
    param([string]$Mode = (Get-KohaNetMode))
    $name = $script:Cfg.FirewallRule
    Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName $name -Group 'Koha' -Direction Inbound -Action Allow -Protocol TCP `
        -LocalPort $script:Cfg.WebPorts -RemoteAddress LocalSubnet -Profile Any | Out-Null
    $hv = Get-Command New-NetFirewallHyperVRule -ErrorAction SilentlyContinue
    if ($hv) {
        try {
            Get-NetFirewallHyperVRule -Name 'KohaWeb' -ErrorAction SilentlyContinue | Remove-NetFirewallHyperVRule -ErrorAction SilentlyContinue
            $rule = @{ Name = 'KohaWeb'; DisplayName = $name; Direction = 'Inbound'; VMCreatorId = $script:WslVmCreatorId
                Protocol = 'TCP'; LocalPorts = $script:Cfg.WebPorts; Action = 'Allow' }
            if ($hv.Parameters.ContainsKey('Profiles')) { $rule['Profiles'] = 'Any' }
            New-NetFirewallHyperVRule @rule | Out-Null
        } catch {
            Write-KohaLog ('network: Hyper-V firewall rule not added: ' + $_.Exception.Message) 'network'
        }
    }
    $user = '{0}\{1}' -f $env:USERDOMAIN, $env:USERNAME
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -Hidden
    Register-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.NetTask -Action (New-KohaAction 'UpdatePortProxy') `
        -Principal $principal -Settings $settings -Force | Out-Null
    # The task keeps this start (KohaEasy.exe, conhost...) until the next
    # SetupNetwork: Get-KohaLanSetupNeed compares it with the current one.
    Set-KohaState @{ netLaunch = (Get-KohaHiddenLaunch -Arguments 'UpdatePortProxy').Target } | Out-Null
    $now = Update-KohaPortProxy -Mode $Mode
    Write-KohaLog ('network: local network access set up ({0}, forwarding: {1})' -f $Mode, $now) 'network'
    return $Mode
}

# After each start: the task sets the forwarding for the mode WSL really
# runs in, with the rights it was given once. Nothing when it is missing.
function Start-KohaNetworkTask {
    try {
        $t = Get-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.NetTask -ErrorAction SilentlyContinue
        if ($null -eq $t) { return $false }
        Start-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.NetTask -ErrorAction Stop
        return $true
    } catch {
        Write-KohaLog ('network: task not started: ' + $_.Exception.Message) 'network'
        return $false
    }
}

function Test-KohaNetTaskRegistered {
    try {
        return ($null -ne (Get-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.NetTask -ErrorAction Stop))
    } catch { return $false }
}

# Why the library network needs SetupNetwork (administrator) again, read
# without administrator rights: open (never set up, or refused), update (set
# up by an older version, or its task starts Koha's tools in a way this PC
# no longer uses), repair (a firewall rule or the task is gone); '' when all
# is in place.
function Get-KohaLanSetupNeed {
    $st = Get-KohaState
    if (-not [bool]$st.lanAccess) { return 'open' }
    if ([int]$st.lanSetup -lt $script:Cfg.LanSetup) { return 'update' }
    if ([string]$st.netLaunch -ne (Get-KohaHiddenLaunch -Arguments 'UpdatePortProxy').Target) { return 'update' }
    $fw = Get-KohaFirewallFacts
    if (-not [bool]$fw.Rule -or $fw.HyperVRule -eq $false) { return 'repair' }
    if (-not (Test-KohaNetTaskRegistered)) { return 'repair' }
    return ''
}

# Addresses the other PCs use: by this PC's name, which stays the same when
# the router hands out a new address, and by its local IPv4 address.
function Get-KohaLanUrls {
    param([string]$Ip = (Get-KohaLanIp), [string]$ComputerName = $env:COMPUTERNAME)
    if (-not $Ip) { return $null }
    $o = [pscustomobject]@{ Opac = ('http://{0}/' -f $Ip); Staff = ('http://{0}:8080/' -f $Ip); OpacByName = ''; StaffByName = '' }
    $n = ([string]$ComputerName).ToLowerInvariant()
    if ($n -match '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$') {
        $o.OpacByName = 'http://{0}/' -f $n
        $o.StaffByName = 'http://{0}:8080/' -f $n
    }
    return $o
}

# One request, with no proxy (a library's web proxy cannot reach this PC's
# own address): whether anything answered below 500.
function Test-KohaHttpUrl {
    param([string]$Url, [int]$TimeoutMs = 5000)
    try {
        $req = [System.Net.WebRequest]::Create($Url)
        $req.Proxy = $null
        $req.Timeout = $TimeoutMs
        $req.AllowAutoRedirect = $false
        $resp = $req.GetResponse()
        $code = [int]$resp.StatusCode
        $resp.Close()
        return [pscustomobject]@{ Ok = ($code -lt 500); Code = $code; Error = '' }
    } catch {
        $ex = $_.Exception
        while ($null -ne $ex.InnerException -and -not ($ex -is [System.Net.WebException])) { $ex = $ex.InnerException }
        if ($ex -is [System.Net.WebException] -and $null -ne $ex.Response) {
            $code = [int]$ex.Response.StatusCode
            try { $ex.Response.Close() } catch { }
            return [pscustomobject]@{ Ok = ($code -lt 500); Code = $code; Error = '' }
        }
        return [pscustomobject]@{ Ok = $false; Code = 0; Error = [string]$ex.Message }
    }
}

# What could stop the other PCs at this PC's door: Koha's Windows Firewall
# rule, its Hyper-V firewall rule ($null where Windows has no Hyper-V
# firewall) and any other firewall product (Windows Security Center), whose
# own rules our Windows Firewall rule does not change.
function Get-KohaFirewallFacts {
    $f = [ordered]@{ Rule = $false; HyperVRule = $null; Others = @() }
    try {
        $r = @(Get-NetFirewallRule -DisplayName $script:Cfg.FirewallRule -ErrorAction Stop)
        $f.Rule = (@($r | Where-Object { [string]$_.Enabled -eq 'True' }).Count -gt 0)
    } catch { }
    if (Get-Command Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue) {
        try { $f.HyperVRule = (@(Get-NetFirewallHyperVRule -Name 'KohaWeb' -ErrorAction Stop).Count -gt 0) } catch { $f.HyperVRule = $false }
    }
    try {
        # productState bits 12-15: 1 when the product's firewall is on.
        $f.Others = @(Get-CimInstance -Namespace 'root/SecurityCenter2' -ClassName FirewallProduct -ErrorAction Stop |
                Where-Object { (([int64]$_.productState -shr 12) -band 0xF) -eq 1 } |
                ForEach-Object { [string]$_.displayName } | Where-Object { $_ })
    } catch { }
    return [pscustomobject]$f
}

# Whether .wslconfig turns on hostAddressLoopback (it takes effect when WSL
# starts again).
function Test-KohaLoopbackConfigured {
    if (-not $env:USERPROFILE) { return $false }
    $cfg = Join-Path $env:USERPROFILE '.wslconfig'
    if (-not (Test-Path -LiteralPath $cfg)) { return $false }
    return ((Get-Content -LiteralPath $cfg -Raw) -match '(?im)^\s*hostAddressLoopback\s*=\s*true\s*$')
}

# Pure: what the library network test tells the librarian. Ok when Koha
# answered on this PC's network address (staff interface and catalog);
# Lines are { Kind = ok | warn | info; Text }: the result, what to fix,
# then the addresses for the other computers.
function Resolve-KohaLanCheck {
    param($Urls, $Staff, $Opac, [string]$Mode, $Firewall, [bool]$Loopback = $true, [bool]$Running = $true)
    $lines = New-Object System.Collections.ArrayList
    $add = { param($kind, $text) [void]$lines.Add([pscustomobject]@{ Kind = $kind; Text = $text }) }
    if (-not $Running) {
        & $add 'warn' (T 'Debian is stopped. Start Koha first.')
        return [pscustomobject]@{ Ok = $false; Lines = @($lines) }
    }
    if ($null -eq $Urls) {
        & $add 'warn' (T 'This PC has no local network address: check its network cable or Wi-Fi.')
        return [pscustomobject]@{ Ok = $false; Lines = @($lines) }
    }
    $ip = ([uri]$Urls.Staff).Host
    $ok = ($null -ne $Staff -and [bool]$Staff.Ok -and $null -ne $Opac -and [bool]$Opac.Ok)
    if ($ok) {
        & $add 'ok' ((T 'Library network test passed: Koha answers on this PC''s network address ({0}).') -f $ip)
    } else {
        & $add 'warn' ((T 'Library network test failed: Koha does not answer on this PC''s network address ({0}).') -f $ip)
        if ($Mode -eq 'mirrored' -and -not $Loopback) {
            & $add 'warn' (T 'In mirrored mode this PC reaches its own address only with hostAddressLoopback. Run the installer again, or test from another computer.')
        }
        if ($Mode -eq 'nat') {
            & $add 'warn' (T 'WSL runs in NAT mode here, so the port forwarding may be missing. Run the installer again and allow the Windows permission prompt.')
        }
    }
    if ($null -ne $Firewall) {
        if (-not [bool]$Firewall.Rule) {
            & $add 'warn' ((T 'The Windows Firewall rule "{0}" is missing or turned off. Run the installer again and allow the Windows permission prompt.') -f $script:Cfg.FirewallRule)
        }
        if ($Mode -eq 'mirrored' -and $Firewall.HyperVRule -eq $false) {
            & $add 'warn' (T 'The Hyper-V firewall rule for WSL is missing. Run the installer again and allow the Windows permission prompt.')
        }
        foreach ($o in @($Firewall.Others)) {
            & $add 'warn' ((T 'Another firewall is active ({0}). Allow TCP ports 80 and 8080 from the local network in it too.') -f $o)
        }
    }
    if ($Urls.StaffByName) {
        & $add 'info' ((T 'Other computers of the library network: staff interface {0}  public catalog {1}') -f $Urls.StaffByName, $Urls.OpacByName)
    }
    & $add 'info' ((T 'By this PC''s address (it can change when the router restarts): staff interface {0}  public catalog {1}') -f $Urls.Staff, $Urls.Opac)
    return [pscustomobject]@{ Ok = $ok; Lines = @($lines) }
}

# The library network test: Koha asked through this PC's own network
# address (the way the other PCs come, minus the cable), and Windows checked
# for what would stop them. Never starts a stopped Debian.
function Test-KohaLanAccess {
    $running = Test-KohaDistroRunning
    $urls = Get-KohaLanUrls
    $mode = Get-KohaNetMode
    $staff = $null
    $opac = $null
    if ($running -and $null -ne $urls) {
        $staff = Test-KohaHttpUrl $urls.Staff
        $opac = Test-KohaHttpUrl $urls.Opac
    }
    $check = Resolve-KohaLanCheck -Urls $urls -Staff $staff -Opac $opac -Mode $mode -Firewall (Get-KohaFirewallFacts) -Loopback (Test-KohaLoopbackConfigured) -Running $running
    $detail = ''
    if ($null -ne $staff) { $detail = (' staff {0} {1}, catalog {2} {3}' -f $staff.Code, $staff.Error, $opac.Code, $opac.Error) }
    Write-KohaLog ('network test ({0}): ok={1}{2}' -f $mode, $check.Ok, $detail) 'network'
    return $check
}

# The library network part of the diagnostics.
function Get-KohaLanReport {
    $out = New-Object System.Collections.Generic.List[string]
    $out.Add(('Network mode: {0} (.wslconfig asks for {1}, hostAddressLoopback: {2})   this PC: {3} ({4})' -f (Get-KohaNetMode), (Get-KohaConfiguredNetMode), (Test-KohaLoopbackConfigured), (Get-KohaLanIp), $env:COMPUTERNAME))
    $fw = Get-KohaFirewallFacts
    $out.Add(('Windows Firewall rule: {0}   Hyper-V firewall rule: {1}   other firewalls: {2}' -f $fw.Rule, $fw.HyperVRule, (@($fw.Others) -join ', ')))
    $rules = @(Get-KohaPortProxyRules)
    if ($rules.Count -eq 0) { $out.Add('Port forwarding: none') }
    foreach ($r in $rules) { $out.Add(('Port forwarding: {0}:{1} -> {2}:{3}' -f $r.ListenAddress, $r.ListenPort, $r.ConnectAddress, $r.ConnectPort)) }
    foreach ($l in @((Test-KohaLanAccess).Lines)) { $out.Add(('[{0}] {1}' -f $l.Kind, $l.Text)) }
    return @($out)
}

# ----------------------------------------------------------------------
# Control panel window and a quick check
# ----------------------------------------------------------------------
# koha-window, inside Debian: what every Windows window of Koha runs (the
# control panel from the Windows tools and from the installer, and the
# "Debian terminal (advanced)" button), so the window ends cleanly when the
# panel or the shell ends. Anything they left holding the terminal is
# stopped: wsl.exe waits for every process that still has the terminal
# open, so one background process kept the window open and black after
# Exit. The exit code is 0, so Windows Terminal closes the window; when
# KEI_WINDOW_PAUSE (base64 text) is set and the panel failed, that text is
# shown until Enter is pressed. With --shell, the user's login shell runs
# instead of the panel.
$script:WindowScript = @'
#!/bin/sh
# Written by Koha Easy Installer for Windows (KohaEasy.Core.psm1).
# koha-window [--shell | command...]: see Install-KohaWindowScript.
shell=0
if [ "${1:-}" = "--shell" ]; then shell=1; shift; fi
# Ctrl+C reaches the panel (or the shell), not this script, which still
# has to clean up after it.
trap ':' INT
if [ "$shell" = 1 ]; then
  login=$(getent passwd "$(id -un)" 2>/dev/null | cut -d: -f7)
  [ -x "$login" ] || login=/bin/bash
  "$login" -l
  rc=$?
else
  [ $# -gt 0 ] || set -- /usr/local/bin/koha-panel
  "$@"
  rc=$?
fi
tty=$(readlink "/proc/$$/fd/0" 2>/dev/null)
case "$tty" in
  /dev/pts/*|/dev/tty*)
    # This script and the WSL processes above it keep the terminal.
    keep=" $$ "
    p=$$
    while [ -n "$p" ] && [ "$p" -gt 1 ]; do
      p=$(awk '/^PPid:/ {print $2}' "/proc/$p/status" 2>/dev/null)
      [ -n "$p" ] && keep="$keep$p "
    done
    left=""
    for p in $(find /proc/[0-9]*/fd -maxdepth 1 -lname "$tty" 2>/dev/null </dev/null | sed -n 's|^/proc/\([0-9]*\)/fd/.*|\1|p' | sort -u); do
      case "$keep" in *" $p "*) continue ;; esac
      # The find, sed and sort above have ended already.
      [ -d "/proc/$p" ] || continue
      left="$left $p"
    done
    if [ -n "$left" ]; then
      kill -HUP $left 2>/dev/null
      sleep 1
      for p in $left; do [ -d "/proc/$p" ] && kill -KILL "$p" 2>/dev/null; done
    fi
    ;;
esac
# 130: left with Ctrl+C, not a failure.
if [ "$rc" -ne 0 ] && [ "$rc" -ne 130 ] && [ -n "${KEI_WINDOW_PAUSE:-}" ] && [ -t 0 ]; then
  printf '\n[%s] ' "$rc"
  printf '%s' "$KEI_WINDOW_PAUSE" | base64 -d 2>/dev/null
  printf ' '
  read -r _ || true
fi
exit 0
'@

# Writes koha-window into Debian (as root, through stdin). The installer
# does it on every run; the Windows tools do it when it is missing.
$script:WindowScriptInstall = @'
umask 022
f='__PATH__'
mkdir -p "$(dirname "$f")" || exit 1
t=$(mktemp "$f.XXXXXX") || exit 1
if tr -d '\r' > "$t" && chmod 755 "$t" && mv -f "$t" "$f"; then exit 0; fi
rm -f "$t"
exit 1
'@

function Install-KohaWindowScript {
    $r = Invoke-KohaLinuxScript -Script ($script:WindowScriptInstall.Replace('__PATH__', $script:Cfg.WindowPath)) -InputText $script:WindowScript
    if ($r.ExitCode -ne 0) { Write-KohaLog ('koha-window not written: ' + $r.Output); return $false }
    return $true
}

function Confirm-KohaWindowScript {
    if ((Invoke-KohaLinux -Command @('test', '-x', $script:Cfg.WindowPath)).ExitCode -eq 0) { return $true }
    return (Install-KohaWindowScript)
}

# Opens the Koha control panel in its own window, as root, and starts Koha
# as well (the panel alone would keep Debian up only while it is open). The
# window gets UTF-8 and the symbol mode, and closes when the panel ends.
function Open-KohaPanel {
    param([switch]$NoStart, [string]$Action = '')
    if (-not $NoStart) { Start-Koha -Trigger user | Out-Null }
    Confirm-KohaWindowScript | Out-Null
    $wsl = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'wsl.exe')
    $launch = Get-KohaPanelLaunch -Wsl $wsl -Terminal (Get-KohaTerminalPath) -Pause (T 'The control panel ended with an error. Press Enter to close this window.') -Action $Action
    Start-Process -FilePath $launch.File -ArgumentList $launch.Arguments | Out-Null
    if ($Action) { Write-KohaLog ('control panel opened on ' + $Action) } else { Write-KohaLog 'control panel opened' }
}

# Pure: how the control panel window opens. In Windows Terminal the panel
# shows emoji; in the classic console, plain symbols. The choice travels as
# "env KEI_PLAIN_GLYPHS=..." on the command line, because a Windows Terminal
# that is already open does not see this process's environment; the text
# shown after a failure travels in base64 (no spaces or ";" for wt.exe).
function Get-KohaPanelLaunch {
    param([string]$Wsl, [string]$Terminal, [string]$Pause = '', [string]$Action = '')
    $plain = '1'
    if ($Terminal) { $plain = '0' }
    $vars = 'KEI_PLAIN_GLYPHS=' + $plain
    if ($Pause) { $vars += ' KEI_WINDOW_PAUSE=' + [Convert]::ToBase64String((New-Object System.Text.UTF8Encoding($false)).GetBytes($Pause)) }
    $cmd = '-d {0} -u root --cd /root -- env {1} {2} {3}' -f $script:Cfg.Distro, $vars, $script:Cfg.WindowPath, $script:Cfg.PanelPath
    # One routine only (the Koha window's Painel de Gestão): the panel runs it
    # and ends, with no main menu. Only plain action names get through.
    if ($Action -cmatch '^[a-z][a-z0-9-]*$') { $cmd += ' --run ' + $Action }
    if ($Terminal) { return [pscustomobject]@{ File = $Terminal; Arguments = ('-w new --title Koha "{0}" {1}' -f $Wsl, $cmd) } }
    return [pscustomobject]@{ File = $Wsl; Arguments = $cmd }
}

# The Koha window's "Debian terminal (advanced)": a shell in Debian as the
# Debian user chosen at install (sudo for root), in its own window. Exit
# closes the window.
function Open-KohaDebianTerminal {
    Confirm-KohaWindowScript | Out-Null
    $wsl = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'wsl.exe')
    $launch = Get-KohaDebianTerminalLaunch -Wsl $wsl -Terminal (Get-KohaTerminalPath)
    Start-Process -FilePath $launch.File -ArgumentList $launch.Arguments | Out-Null
    Write-KohaLog 'Debian terminal opened'
}

# Pure: how the Debian terminal opens.
function Get-KohaDebianTerminalLaunch {
    param([string]$Wsl, [string]$Terminal)
    $cmd = '-d {0} --cd ~ -- {1} --shell' -f $script:Cfg.Distro, $script:Cfg.WindowPath
    if ($Terminal) { return [pscustomobject]@{ File = $Terminal; Arguments = ('-w new --title "Koha - Debian" "{0}" {1}' -f $Wsl, $cmd) } }
    return [pscustomobject]@{ File = $Wsl; Arguments = $cmd }
}

# What is running, in a few lines a librarian can paste into a message:
# Debian's services, the koha-common package, whether Apache answers inside
# Debian, and the keep-alive task. Starts nothing that was not running.
$script:QuickCheckScript = @'
printf 'systemd: %s\n' "$(systemctl is-system-running 2>/dev/null)"
for s in mariadb apache2 memcached rabbitmq-server koha-common; do
  printf '%s: %s\n' "$s" "$(systemctl is-active "$s" 2>/dev/null)"
done
printf 'koha-common package: %s\n' "$(dpkg-query -W -f='${db:Status-Abbrev}${Version}' koha-common 2>/dev/null || echo missing)"
printf 'koha instance: %s\n' "$(ls /etc/koha/sites 2>/dev/null | tr '\n' ' ')"
printf 'installation finished: %s\n' "$([ -f /root/koha_credentials.txt ] && echo yes || echo no)"
printf 'staff page inside Debian: %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8080/ 2>/dev/null)"
printf 'listening: %s\n' "$(ss -lnt 2>/dev/null | awk 'NR>1 {print $4}' | grep -E ':(80|8080|3306|11211|16613)$' | tr '\n' ' ')"
'@

function Get-KohaQuickCheck {
    $lines = New-Object System.Collections.ArrayList
    $running = Test-KohaDistroRunning
    [void]$lines.Add(('Debian ({0}) running: {1}' -f $script:Cfg.Distro, $running))
    try {
        $info = Get-ScheduledTaskInfo -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.KeepTask -ErrorAction Stop
        $task = Get-ScheduledTask -TaskPath $script:Cfg.TaskPath -TaskName $script:Cfg.KeepTask -ErrorAction Stop
        [void]$lines.Add(('Keep Koha running task: {0}, last result 0x{1:X}, last run {2}' -f $task.State, [int64]$info.LastTaskResult, $info.LastRunTime))
    } catch {
        [void]$lines.Add('Keep Koha running task: not found')
    }
    if ($running) {
        $r = Invoke-KohaLinuxScript -Script $script:QuickCheckScript
        foreach ($l in ([string]$r.Output -split "`n")) { if ($l.Trim()) { [void]$lines.Add($l.TrimEnd()) } }
    }
    return @($lines)
}

# ----------------------------------------------------------------------
# Services (the Koha window)
# ----------------------------------------------------------------------
# What the Koha window lists, in the order Koha needs them.
$script:KohaServices = @(
    @{ Unit = 'mariadb'; Name = 'MariaDB' }
    @{ Unit = 'apache2'; Name = 'Apache' }
    @{ Unit = 'rabbitmq-server'; Name = 'RabbitMQ' }
    @{ Unit = 'memcached'; Name = 'Memcached' }
    @{ Unit = 'koha-common'; Name = 'Koha (koha-common)' }
)

# Pure: systemctl is-active as one of running | starting | failed | stopped | unknown.
function ConvertTo-KohaServiceState {
    param([AllowEmptyString()][string]$Active)
    switch ($Active) {
        'active'       { return 'running' }
        'activating'   { return 'starting' }
        'reloading'    { return 'starting' }
        'failed'       { return 'failed' }
        'inactive'     { return 'stopped' }
        'deactivating' { return 'stopped' }
        default        { return 'unknown' }
    }
}

# Pure: the quick check's lines as the rows of the Koha window. With Debian
# stopped, nothing inside it runs, so every row reads stopped.
function ConvertFrom-KohaQuickCheck {
    param([AllowEmptyCollection()][string[]]$Lines)
    $map = @{}
    $debian = $false
    foreach ($l in @($Lines)) {
        if ($l -match '^Debian \([^)]*\) running:\s*(\S+)') { $debian = ($Matches[1] -eq 'True'); continue }
        if ($l -match '^([^:]+):\s*(.*)$') { $map[$Matches[1].Trim()] = $Matches[2].Trim() }
    }
    $rows = New-Object System.Collections.ArrayList
    [void]$rows.Add([pscustomobject]@{ Unit = 'wsl'; Name = 'Debian (WSL)'; State = $(if ($debian) { 'running' } else { 'stopped' }); Detail = '' })
    foreach ($s in $script:KohaServices) {
        $state = 'stopped'
        if ($debian) { $state = ConvertTo-KohaServiceState ([string]$map[$s.Unit]) }
        [void]$rows.Add([pscustomobject]@{ Unit = $s.Unit; Name = $s.Name; State = $state; Detail = '' })
    }
    $code = [string]$map['staff page inside Debian']
    $web = 'stopped'
    if ($debian) {
        $web = 'failed'
        if ($code -match '^[1-4]\d\d$') { $web = 'running' }
    }
    [void]$rows.Add([pscustomobject]@{ Unit = 'http'; Name = 'staff'; State = $web; Detail = $code })
    return [pscustomobject]@{ DebianRunning = $debian; Services = @($rows); Finished = ([string]$map['installation finished'] -eq 'yes') }
}

function Get-KohaServiceStateText {
    param([string]$State, [string]$Unit, [string]$Detail)
    if ($Unit -eq 'http') {
        if ($State -eq 'running') { return ((T 'Answers (HTTP {0})') -f $Detail) }
        if ($State -eq 'failed') { return (T 'Does not answer') }
    }
    switch ($State) {
        'running'  { return (T 'Running') }
        'starting' { return (T 'Starting') }
        'failed'   { return (T 'Failed') }
        'stopped'  { return (T 'Stopped') }
        default    { return (T 'Unknown') }
    }
}

# Pure: the Koha window's banner from the rows of Get-KohaServiceHealth and
# the state of Get-KohaStatus. Level is ok (every row running), starting,
# fault (the rows in Broken are down while Koha should run), stopped (the
# librarian stopped Koha: nothing is highlighted) or unknown.
function Get-KohaHealthSummary {
    param($Health, [string]$State)
    $rows = @()
    if ($null -ne $Health) { $rows = @($Health.Services) }
    $broken = @($rows | Where-Object { $_.State -ne 'running' -and $_.State -ne 'starting' })
    $level = 'unknown'
    $text = T 'Checking...'
    if ($State -eq 'not_installed') {
        $level = 'stopped'; $broken = @(); $text = Get-KohaStateText $State
    } elseif ($State -eq 'stopped_by_user') {
        $level = 'stopped'; $broken = @(); $text = Get-KohaStateText $State
    } elseif ($rows.Count -eq 0) {
        $broken = @()
    } elseif ($broken.Count -eq 0 -and @($rows | Where-Object { $_.State -eq 'starting' }).Count -eq 0) {
        $level = 'ok'; $text = T 'All services are running'
    } elseif ($State -eq 'starting' -or $broken.Count -eq 0) {
        # Koha is still coming up: the rows that are not up yet are not faults.
        $level = 'starting'; $broken = @(); $text = Get-KohaStateText 'starting'
    } else {
        $level = 'fault'
        if (-not [bool]$Health.DebianRunning) {
            # Everything inside Debian is down with it: name only Debian.
            $broken = @($rows | Where-Object { $_.Unit -eq 'wsl' })
        }
        if ($broken.Count -eq 1) {
            if ($broken[0].Unit -eq 'http') { $text = T 'Attention: the staff interface does not answer' }
            else { $text = (T 'Attention: {0} is offline') -f $broken[0].Name }
        } else {
            $text = (T 'Attention: {0} components are offline ({1})') -f $broken.Count, ((@($broken | ForEach-Object { Get-KohaServiceName $_ })) -join ', ')
        }
    }
    return [pscustomobject]@{ Level = $level; Text = $text; Broken = @($broken | ForEach-Object { $_.Unit }) }
}

# The row's name as the Koha window shows it.
function Get-KohaServiceName {
    param($Row)
    if ($Row.Unit -eq 'http') { return (T 'HTTP response') }
    return [string]$Row.Name
}

# Read-only, like the tray: a stopped Debian is reported, never started.
function Get-KohaServiceHealth {
    $lines = @(Get-KohaQuickCheck)
    $h = ConvertFrom-KohaQuickCheck -Lines $lines
    $h | Add-Member -NotePropertyName Lines -NotePropertyValue $lines
    return $h
}

# The Koha window's "Rebuild search index": the panel rebuilds the index of
# the active engine (Zebra or Elasticsearch) from scratch. Never starts a
# stopped Debian. Returns rebuilt, failed or not_running.
function Invoke-KohaSearchReindex {
    if (-not (Test-KohaDistroRunning)) { return 'not_running' }
    Write-KohaLog 'rebuilding the search index'
    $r = Invoke-KohaLinux -Command @($script:Cfg.PanelPath, '--rebuild-search-index')
    Write-KohaLog ('search index rebuild (exit {0}) {1}' -f $r.ExitCode, ([string]$r.Output).Trim())
    if ($r.ExitCode -eq 0) { return 'rebuilt' }
    return 'failed'
}

# Restarts Koha's services inside Debian, without restarting WSL: faster
# than Koha - Restart, and what most "Koha stopped answering" cases need.
$script:RestartServicesScript = @'
systemctl reset-failed >/dev/null 2>&1
rc=0
for s in mariadb memcached rabbitmq-server koha-common apache2; do
  systemctl cat "$s.service" >/dev/null 2>&1 || continue
  if systemctl restart "$s.service"; then echo "[OK] $s"; else echo "[FAILED] $s"; rc=1; fi
done
exit $rc
'@

function Restart-KohaServices {
    param([switch]$NoWait)
    if (-not (Test-KohaDistroRunning)) { return 'not_running' }
    Write-KohaLog 'restarting Koha services'
    $r = Invoke-KohaLinuxScript -Script $script:RestartServicesScript
    foreach ($l in ([string]$r.Output -split "`n")) { if ($l.Trim()) { Write-KohaLog ('restart services: ' + $l.TrimEnd()) } }
    if ($NoWait) {
        if ($r.ExitCode -eq 0) { return 'restarted' }
        return 'failed'
    }
    if (Wait-KohaHttp -Seconds 120) { return 'ready' }
    return 'timeout'
}

# ----------------------------------------------------------------------
# Diagnostics
# ----------------------------------------------------------------------
# Same rules as kei_redact in the installer.
function Protect-KohaText {
    param([AllowEmptyString()][string]$Text)
    $r = '[REDACTED]'
    $t = $Text
    $t = [regex]::Replace($t, '(?i)(<(pass|password|user_pass|encryption_key|api_key)>)[^<]*(</[a-z_]+>)', ('$1' + $r + '$3'))
    $t = [regex]::Replace($t, '(?i)([a-z_-]*(pass(word)?|passwd|pwd|secret|token|api[_-]?key)[a-z_-]*["'']?\s*[:=]\s*["'']?)[^"''\s,;&}]+', ('$1' + $r))
    $t = [regex]::Replace($t, '(?i)((proxy-)?authorization:\s*[a-z]+)\s+\S+', ('$1 ' + $r))
    $t = [regex]::Replace($t, '(?i)(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}', ('$1 ' + $r))
    $t = [regex]::Replace($t, '://[^/@\s:]+:[^/@\s]+@', ('://' + $r + '@'))
    $t = [regex]::Replace($t, 'ya29\.[A-Za-z0-9._-]+', $r)
    $t = [regex]::Replace($t, '1//[A-Za-z0-9._-]{20,}', $r)
    return $t
}

function Save-KohaText {
    param([string]$Path, [string]$Text)
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, (Protect-KohaText $Text), $utf8)
}

function Invoke-KohaCapture {
    param([scriptblock]$Block)
    try { return ((& $Block 2>&1 | Out-String -Width 200)) } catch { return ('ERROR: ' + $_.Exception.Message) }
}

# The last warnings of Koha's services and the tails of its error logs.
$script:ServiceLogScript = @'
for s in mariadb apache2 rabbitmq-server memcached koha-common; do
  echo "--- $s: latest warnings and errors"
  journalctl -u "$s" -p warning -n 25 --no-pager -o short-iso 2>/dev/null
done
for f in /var/log/koha/*/plack-error.log /var/log/koha/*/intranet-error.log /var/log/apache2/error.log; do
  [ -f "$f" ] || continue
  echo "--- $f: last 40 lines"
  tail -n 40 "$f"
done
'@

# Windows' "Turn off Windows write-cache buffer flushing on the device"
# (Device Manager > Disk drives > the disk > Policies) tells Windows the disk
# has its own battery, so the flushes MariaDB relies on stop reaching it and
# a power cut can lose or damage data. Stored as CacheIsPowerProtected=1
# under the disk's Device Parameters\Disk. [verify] on real Windows.
function Get-KohaDiskOfDrive {
    param([string]$Letter)
    $part = Get-Partition -DriveLetter $Letter -ErrorAction Stop | Select-Object -First 1
    $disk = Get-CimInstance Win32_DiskDrive -Filter ('Index={0}' -f [int]$part.DiskNumber) -ErrorAction Stop | Select-Object -First 1
    return [pscustomobject]@{ Number = [int]$part.DiskNumber; Model = [string]$disk.Model; PnpId = [string]$disk.PNPDeviceID }
}

function Get-KohaDiskFlushOff {
    param([string]$PnpId)
    $key = 'HKLM:\SYSTEM\CurrentControlSet\Enum\{0}\Device Parameters\Disk' -f $PnpId
    $p = Get-ItemProperty -LiteralPath $key -Name CacheIsPowerProtected -ErrorAction SilentlyContinue
    if ($null -eq $p) { return $false }
    return ([int]$p.CacheIsPowerProtected -eq 1)
}

# One line for the diagnostics: whether Windows still flushes the write
# cache of the disk that holds Koha's virtual disk (ext4.vhdx).
function Get-KohaWriteCacheCheck {
    param([string]$Vhdx = (Get-KohaVhdxPath))
    if ([string]$Vhdx -notmatch '^([A-Za-z]):') { return [pscustomobject]@{ Level = 'unknown'; Text = 'Write-cache flushing: the Koha virtual disk (ext4.vhdx) was not found on a drive letter.' } }
    $letter = $Matches[1].ToUpperInvariant()
    try {
        $d = Get-KohaDiskOfDrive -Letter $letter
        $name = 'drive {0}: (disk {1}, {2})' -f $letter, $d.Number, $d.Model
        if (Get-KohaDiskFlushOff -PnpId $d.PnpId) {
            return [pscustomobject]@{ Level = 'warning'; Text = ('WARNING: Windows write-cache buffer flushing is turned OFF for {0}. A power cut can lose or damage Koha''s database. Turn it back on: Device Manager > Disk drives > {1} > Policies > clear "Turn off Windows write-cache buffer flushing on the device".' -f $name, $d.Model) }
        }
        return [pscustomobject]@{ Level = 'ok'; Text = ('Write-cache flushing: on for {0} (safe).' -f $name) }
    } catch {
        return [pscustomobject]@{ Level = 'unknown'; Text = ('Write-cache flushing: could not be read for drive {0}: ({1}).' -f $letter, $_.Exception.Message) }
    }
}

# One text file on the desktop that anyone can open and paste into a
# message: Windows and WSL versions, the services, the saved choices,
# Debian's latest service errors and the Windows logs of the last days.
# Starts nothing (a stopped Debian is reported as stopped). Passwords,
# tokens and keys are removed, as in the .zip.
function Export-KohaDiagnosticsText {
    param([string]$Destination = [Environment]::GetFolderPath('Desktop'), [string]$FileName = 'diagnostico_koha.txt')
    $out = New-Object System.Collections.Generic.List[string]
    $out.Add(('Koha on Windows - diagnostics - {0}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')))
    $out.Add(('Computer: {0}   Koha Easy Installer for Windows {1}' -f $env:COMPUTERNAME, $script:KohaEasyVersion))
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        $out.Add(('Windows: {0} {1} (build {2})' -f $os.Caption, $os.Version, $os.BuildNumber))
    } catch { }
    $out.Add('')
    $out.Add('== WSL')
    $out.Add((Invoke-KohaWsl -Arguments @('--version')).Output)
    $out.Add((Invoke-KohaWsl -Arguments @('--list', '--verbose')).Output)
    $out.Add('')
    $out.Add('== Koha')
    $state = Get-KohaState
    $out.Add(('Wanted: {0}   automatic start: {1}   library network: {2}' -f $state.desired, $state.autostart, [bool]$state['lanAccess']))
    foreach ($l in @(Get-KohaQuickCheck)) { $out.Add($l) }
    $out.Add((Get-KohaWriteCacheCheck).Text)
    $out.Add('')
    $out.Add('== Library network')
    try { foreach ($l in @(Get-KohaLanReport)) { $out.Add([string]$l) } } catch { $out.Add('ERROR: ' + $_.Exception.Message) }
    if (Test-KohaDistroRunning) {
        $out.Add('')
        $out.Add('== Debian: service logs')
        $out.Add((Invoke-KohaLinuxScript -Script $script:ServiceLogScript).Output)
    }
    $logs = Get-KohaPath Logs
    if (Test-Path -LiteralPath $logs) {
        Get-ChildItem -LiteralPath $logs -Filter '*.log' | Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-3) } |
            Sort-Object LastWriteTime | ForEach-Object {
                $out.Add('')
                $out.Add(('== Windows log {0}: last 60 lines' -f $_.Name))
                foreach ($l in @(Get-Content -LiteralPath $_.FullName -Tail 60)) { $out.Add([string]$l) }
            }
    }
    if (-not (Test-Path -LiteralPath $Destination)) { New-Item -ItemType Directory -Path $Destination -Force | Out-Null }
    $file = Join-Path $Destination $FileName
    Save-KohaText $file (($out -join "`r`n") + "`r`n")
    Write-KohaLog "diagnostics report saved: $file"
    return $file
}

# Collects the Windows side, asks Linux for its own bundle
# (config.sh --export-diagnostics) and zips both into $Destination.
# A stopped Koha is started for the export and stopped again afterwards.
function Export-KohaDiagnostics {
    param([string]$Destination = [Environment]::GetFolderPath('Desktop'))
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $work = Join-Path $env:TEMP ('KohaEasy-diagnostics-' + $stamp)
    $win = Join-Path $work 'windows'
    New-Item -ItemType Directory -Path $win -Force | Out-Null
    $state = Get-KohaState

    Save-KohaText (Join-Path $win 'wsl.txt') ((Invoke-KohaWsl -Arguments @('--version')).Output + "`n`n" +
        (Invoke-KohaWsl -Arguments @('--status')).Output + "`n`n" + (Invoke-KohaWsl -Arguments @('--list', '--verbose')).Output)
    Save-KohaText (Join-Path $win 'computer.txt') (Invoke-KohaCapture {
            Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture, TotalVisibleMemorySize, FreePhysicalMemory, LastBootUpTime | Format-List
            Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, HypervisorPresent, NumberOfLogicalProcessors | Format-List
            Get-CimInstance Win32_Processor | Select-Object Name, VirtualizationFirmwareEnabled | Format-List
            Get-PSDrive -PSProvider FileSystem | Format-Table Name, Used, Free -AutoSize
        })
    if ($env:USERPROFILE) {
        $wslconfig = Join-Path $env:USERPROFILE '.wslconfig'
        if (Test-Path -LiteralPath $wslconfig) { Save-KohaText (Join-Path $win 'wslconfig.txt') (Get-Content -LiteralPath $wslconfig -Raw) }
    }
    Save-KohaText (Join-Path $win 'state.json') ($state | ConvertTo-Json -Depth 5)
    Save-KohaText (Join-Path $win 'tasks.txt') (Invoke-KohaCapture {
            Get-ScheduledTask -TaskPath $script:Cfg.TaskPath | ForEach-Object {
                $_ | Select-Object TaskName, State | Format-List
                $_ | Get-ScheduledTaskInfo | Select-Object LastRunTime, LastTaskResult, NextRunTime, NumberOfMissedRuns | Format-List
            }
        })
    $wasRunning = Test-KohaDistroRunning
    $linux = $null
    if ($wasRunning) { $linux = Get-KohaLinuxStatus }
    Save-KohaText (Join-Path $win 'disk.txt') ((Invoke-KohaCapture { Get-KohaDiskHealth -Linux $linux | Format-List }) + "`n" + (Get-KohaWriteCacheCheck).Text + "`n")
    Save-KohaText (Join-Path $win 'events.txt') (Invoke-KohaCapture {
            Get-WinEvent -FilterHashtable @{ LogName = 'Application', 'System'; Level = 1, 2, 3; StartTime = (Get-Date).AddDays(-3) } -MaxEvents 2000 -ErrorAction SilentlyContinue |
                Where-Object { $_.ProviderName -match 'wsl|Lxss|Hyper-V|vmcompute|Kernel-Power|Power-Troubleshooter|disk|Ntfs' } |
                Select-Object -First 300 | Format-List TimeCreated, ProviderName, Id, LevelDisplayName, Message
        })
    $logs = Get-KohaPath Logs
    if (Test-Path -LiteralPath $logs) {
        $dst = Join-Path $win 'logs'
        New-Item -ItemType Directory -Path $dst -Force | Out-Null
        Get-ChildItem -LiteralPath $logs -Filter '*.log' | Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-7) } | ForEach-Object {
            Save-KohaText (Join-Path $dst $_.Name) ((Get-Content -LiteralPath $_.FullName -Tail 2000) -join "`n")
        }
    }

    Save-KohaText (Join-Path $win 'quick-check.txt') ((Get-KohaQuickCheck) -join "`n")

    # Linux side, written straight into the work folder.
    $note = ''
    if (Test-KohaDistroInstalled) {
        $lp = (Invoke-KohaLinux -Command @('wslpath', '-a', '-u', $work)).Output.Trim()
        $r = Invoke-KohaLinux -Command @($script:Cfg.PanelPath, '--export-diagnostics', $lp)
        if ($r.ExitCode -eq 0) {
            $dir = ($r.Output -split "`n" | Where-Object { $_ -like '/*' } | Select-Object -Last 1)
            if ($dir) {
                $name = Split-Path -Leaf $dir
                if (Test-Path -LiteralPath (Join-Path $work $name)) { Rename-Item -LiteralPath (Join-Path $work $name) -NewName 'linux' }
            }
        } else {
            $note = 'Linux diagnostics failed: ' + $r.Output
        }
        if (-not $wasRunning -and $state.desired -ne 'running') { Stop-KohaDebianGracefully | Out-Null }
    } else {
        $note = ('The {0} distro is not installed.' -f $script:Cfg.Distro)
    }
    if ($note) { Save-KohaText (Join-Path $work 'NOTE.txt') $note }

    if (-not (Test-Path -LiteralPath $Destination)) { New-Item -ItemType Directory -Path $Destination -Force | Out-Null }
    $zip = Join-Path $Destination ('Koha-diagnostics-{0}-{1}.zip' -f $env:COMPUTERNAME, $stamp)
    Compress-Archive -Path (Join-Path $work '*') -DestinationPath $zip -Force
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    Write-KohaLog "diagnostics exported: $zip"
    return $zip
}

# ----------------------------------------------------------------------
# Shortcuts (Start menu folder "Koha" and desktop), all with koha.ico
# ----------------------------------------------------------------------
function Get-KohaIconPath { return [System.IO.Path]::Combine((Get-KohaPath Bin), 'koha.ico') }

# The application's title on the Koha window, its header, the dialogs and
# the Koha shortcut's tooltip (in Portuguese, "koha.nexus : Assistente
# inteligente e gratuito para facilitar a gestão de bibliotecas").
function Get-KohaAppTitle { return (T 'koha.nexus : A smart, free and easy-to-use assistant for library management') }

# The icon of the program shortcuts: KohaEasy.exe's own icon (koha.ico,
# built into the program the shortcuts start) while KohaEasy.exe is in use,
# else koha.ico. Explorer and the taskbar read an icon inside the program
# they start as reliably as the program itself; a loose .ico next to it
# came back as a blank page on the desktop and the taskbar after a
# restart, while the program still ran.
function Get-KohaShortcutIcon {
    param([string]$Launcher = (Get-KohaLauncherPath))
    if ($Launcher -and (Test-Path -LiteralPath $Launcher)) { return $Launcher }
    return (Get-KohaIconPath)
}

# koha.ico as an icon for a window or the tray ($Size 0: the file's own
# sizes). Read into memory, and tried again while a program still holds
# the file (an antivirus scan at sign-in); then KohaEasy.exe's own icon,
# the same koha.ico built in; then $null, and the window keeps Windows'
# default icon. Every failure is logged with Windows' reason.
function Get-KohaIcon {
    param(
        [int]$Size = 0,
        [string]$Path = (Get-KohaIconPath),
        [string]$Exe = ([System.IO.Path]::Combine((Get-KohaPath Bin), 'KohaEasy.exe')),
        [int]$Tries = 3,
        [int]$WaitMs = 700
    )
    try { Add-Type -AssemblyName System.Drawing -ErrorAction Stop } catch { }
    $why = 'the file is missing'
    if (Test-Path -LiteralPath $Path) {
        for ($i = 1; $i -le $Tries; $i++) {
            try {
                $ms = New-Object System.IO.MemoryStream(, [System.IO.File]::ReadAllBytes($Path))
                if ($Size -gt 0) { return (New-Object System.Drawing.Icon($ms, $Size, $Size)) }
                return (New-Object System.Drawing.Icon($ms))
            } catch {
                $why = $_.Exception.Message
                if ($i -lt $Tries) { Start-Sleep -Milliseconds $WaitMs }
            }
        }
    }
    $msg = 'koha.ico could not be loaded from {0}: {1}' -f $Path, $why
    if ($Exe -and (Test-Path -LiteralPath $Exe)) {
        try {
            $ico = [System.Drawing.Icon]::ExtractAssociatedIcon($Exe)
            if ($ico) {
                Write-KohaLog ($msg + '; using the icon inside KohaEasy.exe')
                if ($Size -gt 0) { return (New-Object System.Drawing.Icon($ico, $Size, $Size)) }
                return $ico
            }
        } catch { $msg += '; KohaEasy.exe: ' + $_.Exception.Message }
    }
    Write-KohaLog $msg
    return $null
}

# What to create (pure, tested). Kind "url" is an Internet shortcut (.url),
# "lnk" a program shortcut. Commands run KohaEasy.ps1 in Windows PowerShell 5.1.
function Get-KohaShortcutList {
    $ps = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    $lnk = { param($name, $a) $l = Get-KohaHiddenLaunch -Arguments $a; @{ Name = $name; Kind = 'lnk'; Target = $l.Target; Arguments = $l.Arguments } }
    $list = @(
        # The one desktop icon: starts what is not running (the tray, Koha)
        # and opens the Koha window, or brings the open one to the front
        # (Invoke-KohaLaunch). The window works even when Koha itself does
        # not answer. Also in the Start menu, where it carries Koha's
        # identity (AppId): the taskbar pins the Koha window as Koha, and
        # notifications show Koha's name.
        (& $lnk 'Koha' 'Launch') + @{ Desktop = $true; StartMenu = $true; AppId = $true }
        @{ Name = (T 'Koha - Staff interface'); Kind = 'url'; Target = $script:Cfg.StaffUrl }
        @{ Name = (T 'Koha - Public catalog'); Kind = 'url'; Target = $script:Cfg.OpacUrl }
        (& $lnk (T 'Koha - Control panel') 'Panel')
        @{ Name = (T 'Koha - Backups folder'); Kind = 'lnk'; Target = [System.IO.Path]::Combine([string]$env:SystemRoot, 'explorer.exe'); Arguments = ('"{0}"' -f (Get-KohaPath Backups)) }
        (& $lnk (T 'Koha - Start') 'Start')
        (& $lnk (T 'Koha - Stop') 'Stop')
        (& $lnk (T 'Koha - Restart') 'Restart')
        (& $lnk (T 'Koha - Shut down the PC safely') 'SafeShutdown')
        (& $lnk (T 'Koha - Status') 'Window')
        (& $lnk (T 'Koha - Export diagnostics') 'ExportReport')
        (& $lnk (T 'Koha - Status icon') 'Tray')
    )
    $lnkIcon = Get-KohaShortcutIcon
    foreach ($s in $list) {
        if ($s.Kind -eq 'lnk') { $s.Icon = $lnkIcon } else { $s.Icon = Get-KohaIconPath }
    }
    $list[0].Description = Get-KohaAppTitle
    return $list
}

# Characters Windows refuses in file names.
function ConvertTo-KohaFileName { param([string]$Name) return ($Name -replace '[\\/:*?"<>|]', '-').Trim() }

function Save-KohaUrlShortcut {
    param([string]$Path, [string]$Url, [string]$Icon)
    $text = "[InternetShortcut]`r`nURL=$Url`r`nIconFile=$Icon`r`nIconIndex=0`r`n"
    [System.IO.File]::WriteAllText($Path, $text, [System.Text.Encoding]::ASCII)
}

# Two independent ways: WScript.Shell, then the shell's own IShellLink in
# KohaEasy.exe (KohaEasy.Native). Throws with both reasons when neither
# could write it.
function Save-KohaLnkShortcut {
    param([string]$Path, [string]$Target, [string]$Arguments, [string]$Icon, [string]$Description = '')
    try {
        $shell = New-Object -ComObject WScript.Shell -ErrorAction Stop
        $lnk = $shell.CreateShortcut($Path)
        $lnk.TargetPath = $Target
        $lnk.Arguments = $Arguments
        $lnk.WorkingDirectory = Get-KohaPath Root
        $lnk.IconLocation = $Icon + ',0'
        if ($Description) { $lnk.Description = $Description }
        $lnk.Save()
        return
    } catch {
        $first = 'WScript.Shell: ' + $_.Exception.Message
    }
    if (-not (Import-KohaNative)) { throw $first }
    try {
        [KohaEasy.Native]::CreateShortcut($Path, $Target, $Arguments, (Get-KohaPath Root), $Icon)
        Write-KohaLog ('shortcut written through IShellLink after ' + $first)
    } catch {
        throw ('{0}; IShellLink: {1}' -f $first, $_.Exception.Message)
    }
}

# The signed-in user's own desktop, the one Explorer shows: Windows' answer
# (it follows OneDrive's desktop backup), else the Windows shell's (the
# WScript.Shell that writes the shortcuts), else the folder Explorer's
# registry value names, else OneDrive's and the profile's Desktop folders.
# Only a folder that exists, and never the Public desktop or another
# account's. '' when there is none.
function Get-KohaDesktopPath {
    param(
        [string]$Known = [Environment]::GetFolderPath('Desktop'),
        [string]$Shell = (Get-KohaShellDesktop),
        [string]$Registry = (Get-KohaRegistryDesktop),
        [string]$UserProfile = $env:USERPROFILE
    )
    $candidates = @($Known, $Shell, $Registry)
    if ($UserProfile) {
        $candidates += @(Get-ChildItem -LiteralPath $UserProfile -Directory -Filter 'OneDrive*' -ErrorAction SilentlyContinue |
                ForEach-Object { [System.IO.Path]::Combine($_.FullName, 'Desktop') })
        $candidates += [System.IO.Path]::Combine($UserProfile, 'Desktop')
    }
    foreach ($c in $candidates) {
        if (-not $c) { continue }
        if ($c -match '\\Users\\(Public|Default)\\') { continue }
        if ($UserProfile -and -not $c.StartsWith($UserProfile, [System.StringComparison]::OrdinalIgnoreCase) -and $c -match '^[A-Za-z]:\\Users\\') { continue }
        if (Test-Path -LiteralPath $c -PathType Container) { return $c }
    }
    return ''
}

function Get-KohaShellDesktop {
    try { return [string](New-Object -ComObject WScript.Shell).SpecialFolders.Item('Desktop') } catch { return '' }
}

function Get-KohaRegistryDesktop {
    try {
        $v = (Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders' -Name Desktop -ErrorAction Stop).Desktop
        return [Environment]::ExpandEnvironmentVariables([string]$v)
    } catch { return '' }
}

$script:ShortcutErrors = New-Object System.Collections.ArrayList
function Add-KohaShortcutError {
    param([string]$Path, [string]$Message)
    [void]$script:ShortcutErrors.Add(('{0}: {1}' -f $Path, $Message))
    Write-KohaLog ('shortcut not created: {0}: {1}' -f $Path, $Message)
}
# What went wrong in the last New-KohaShortcuts, one line per file.
function Get-KohaShortcutErrors { return @($script:ShortcutErrors) }
# Where the last New-KohaShortcuts left the Koha icon: desktop, public (the
# desktop of all users), startmenu, or '' (nowhere).
$script:KohaIconPlace = ''
function Get-KohaIconPlace { return $script:KohaIconPlace }

# Creates (or refreshes) every shortcut with the Koha icon. The icon is copied
# next to KohaEasy.ps1 first, so shortcuts keep it if the ZIP folder is deleted.
function New-KohaShortcuts {
    param(
        [string]$StartMenu = [System.IO.Path]::Combine([Environment]::GetFolderPath('Programs'), 'Koha'),
        [string]$Desktop = (Get-KohaDesktopPath),
        [string]$IconSource = [System.IO.Path]::Combine($PSScriptRoot, 'koha.ico'),
        [string]$PublicDesktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
    )
    # Every problem is kept (Get-KohaShortcutErrors) and none stops the
    # other shortcuts: the Koha icon comes first, and one shortcut Windows
    # refuses must not leave the librarian with none.
    $script:ShortcutErrors = New-Object System.Collections.ArrayList
    $icon = Get-KohaIconPath
    try {
        if ((Test-Path -LiteralPath $IconSource) -and ($IconSource -ne $icon)) {
            New-Item -ItemType Directory -Path (Split-Path -Parent $icon) -Force -ErrorAction Stop | Out-Null
            Copy-Item -LiteralPath $IconSource -Destination $icon -Force -ErrorAction Stop
        }
    } catch { Add-KohaShortcutError $icon $_.Exception.Message }
    try { New-Item -ItemType Directory -Path $StartMenu -Force -ErrorAction Stop | Out-Null } catch { Add-KohaShortcutError $StartMenu $_.Exception.Message }
    if ($Desktop) {
        # Older versions also put the two web shortcuts on the desktop; the
        # one Koha icon (the Koha window) replaces them.
        foreach ($n in @('Koha - Staff interface', 'Koha - Public catalog', (T 'Koha - Staff interface'), (T 'Koha - Public catalog'))) {
            $old = [System.IO.Path]::Combine($Desktop, (ConvertTo-KohaFileName $n) + '.url')
            if (Test-Path -LiteralPath $old) { Remove-Item -LiteralPath $old -Force -ErrorAction SilentlyContinue }
        }
    }
    $made = New-Object System.Collections.ArrayList
    $identity = $false
    foreach ($s in Get-KohaShortcutList) {
        $dirs = @()
        if (-not $s.ContainsKey('StartMenu') -or $s.StartMenu) { $dirs += $StartMenu }
        if ($s.ContainsKey('Desktop') -and $s.Desktop -and $Desktop) { $dirs += $Desktop }
        foreach ($d in $dirs) {
            $file = [System.IO.Path]::Combine($d, (ConvertTo-KohaFileName $s.Name) + '.' + $s.Kind)
            try {
                if ($s.Kind -eq 'url') {
                    Save-KohaUrlShortcut -Path $file -Url $s.Target -Icon $s.Icon
                } else {
                    $tip = ''
                    if ($s.ContainsKey('Description')) { $tip = $s.Description }
                    Save-KohaLnkShortcut -Path $file -Target $s.Target -Arguments $s.Arguments -Icon $s.Icon -Description $tip
                }
            } catch {
                Add-KohaShortcutError $file $_.Exception.Message
                continue
            }
            # Koha's identity is extra: without it the shortcut still works.
            if ($s.Kind -eq 'lnk' -and $s.ContainsKey('AppId') -and $s.AppId -and (Set-KohaShortcutAppId -Path $file) -and $d -eq $StartMenu) { $identity = $true }
            # Counted only once Windows shows it there.
            if (Test-Path -LiteralPath $file) { [void]$made.Add($file) }
            else { Add-KohaShortcutError $file 'the file was not there right after it was written' }
        }
    }
    # The Koha icon where the librarian looks for it, whatever refused the
    # first try: the Start menu one copied onto the desktop as a plain file,
    # then the desktop of all users (it needs administrator rights on most
    # PCs, so it is only a last try).
    $menuLnk = [System.IO.Path]::Combine($StartMenu, 'Koha.lnk')
    $deskLnk = ''
    if ($Desktop) { $deskLnk = [System.IO.Path]::Combine($Desktop, 'Koha.lnk') }
    $script:KohaIconPlace = ''
    if ($deskLnk -and -not (Test-Path -LiteralPath $deskLnk) -and (Test-Path -LiteralPath $menuLnk)) {
        try {
            [System.IO.File]::Copy($menuLnk, $deskLnk, $true)
            if (Test-Path -LiteralPath $deskLnk) { [void]$made.Add($deskLnk); Write-KohaLog ('Koha icon copied from the Start menu to ' + $deskLnk) }
        } catch { Add-KohaShortcutError $deskLnk ('copy from the Start menu: ' + $_.Exception.Message) }
    }
    if ($deskLnk -and (Test-Path -LiteralPath $deskLnk)) {
        $script:KohaIconPlace = 'desktop'
        # A second Koha icon from an earlier last try would show twice.
        if ($PublicDesktop) {
            $pub = [System.IO.Path]::Combine($PublicDesktop, 'Koha.lnk')
            if (Test-Path -LiteralPath $pub) { Remove-Item -LiteralPath $pub -Force -ErrorAction SilentlyContinue }
        }
    } elseif ($PublicDesktop -and (Test-Path -LiteralPath $PublicDesktop)) {
        $pub = [System.IO.Path]::Combine($PublicDesktop, 'Koha.lnk')
        try {
            if (Test-Path -LiteralPath $menuLnk) { [System.IO.File]::Copy($menuLnk, $pub, $true) }
            else { $k = @(Get-KohaShortcutList)[0]; Save-KohaLnkShortcut -Path $pub -Target $k.Target -Arguments $k.Arguments -Icon $k.Icon }
            if (Test-Path -LiteralPath $pub) { [void]$made.Add($pub); $script:KohaIconPlace = 'public' }
        } catch { Add-KohaShortcutError $pub $_.Exception.Message }
    }
    if (-not $script:KohaIconPlace -and (Test-Path -LiteralPath $menuLnk)) { $script:KohaIconPlace = 'startmenu' }
    # Only with the Start menu shortcut does Windows know Koha's name and
    # icon for its notifications and the taskbar.
    Set-KohaState @{ appIdShortcut = $identity } | Out-Null
    # Explorer and the taskbar draw the rewritten shortcuts again now, not
    # from icons cached before.
    if ($made.Count -gt 0 -and (Import-KohaNative)) {
        try { [KohaEasy.Native]::RefreshShellIcons() } catch { Write-KohaLog ('icon refresh: ' + $_.Exception.Message) }
    }
    Write-KohaLog ('shortcuts created: {0}, Koha icon: {1}, Koha identity on the taskbar: {2}' -f $made.Count, $script:KohaIconPlace, $identity)
    return @($made)
}

# The distro's own entries, made by WSL itself, show Debian's logo: its
# Start menu shortcut and the Windows Terminal profile it wrote. Both get
# koha.ico (and so does shortcut.ico, the file WSL points them at). When WSL
# wrote no terminal profile (older WSL), a Windows Terminal fragment adds a
# "Koha (Debian)" profile with the icon.
function Set-KohaDistroIcon {
    param(
        [string]$Icon = (Get-KohaIconPath),
        [string]$FragmentDir = [System.IO.Path]::Combine([string]$env:LOCALAPPDATA, 'Microsoft', 'Windows Terminal', 'Fragments', 'KohaEasy')
    )
    $done = New-Object System.Collections.ArrayList
    $e = Get-KohaLxssEntry
    if (-not (Test-Path -LiteralPath $Icon) -or $null -eq $e) { return @() }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    if ($e.BasePath -and (Test-Path -LiteralPath $e.BasePath)) {
        try { Copy-Item -LiteralPath $Icon -Destination (Join-Path $e.BasePath 'shortcut.ico') -Force; [void]$done.Add('shortcut.ico') } catch { }
    }
    if ($e.ShortcutPath -and (Test-Path -LiteralPath $e.ShortcutPath)) {
        try {
            $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($e.ShortcutPath)
            $lnk.IconLocation = $Icon + ',0'
            $lnk.Save()
            [void]$done.Add('start-menu')
        } catch { Write-KohaLog ('icon: Start menu shortcut not changed: ' + $_.Exception.Message) }
    }
    $hasProfile = $false
    if ($e.TerminalProfilePath -and (Test-Path -LiteralPath $e.TerminalProfilePath)) {
        try {
            $json = [System.IO.File]::ReadAllText($e.TerminalProfilePath) | ConvertFrom-Json
            foreach ($p in @($json.profiles)) {
                if ($p.PSObject.Properties['icon']) { $p.icon = $Icon } else { $p | Add-Member -NotePropertyName icon -NotePropertyValue $Icon }
            }
            [System.IO.File]::WriteAllText($e.TerminalProfilePath, ($json | ConvertTo-Json -Depth 10), $utf8)
            $hasProfile = $true
            [void]$done.Add('terminal')
        } catch { Write-KohaLog ('icon: terminal profile not changed: ' + $_.Exception.Message) }
    }
    if (-not $hasProfile -and $FragmentDir) {
        try {
            New-Item -ItemType Directory -Path $FragmentDir -Force | Out-Null
            $frag = [ordered]@{ profiles = @([ordered]@{
                        name = 'Koha (Debian)'; commandline = ('wsl.exe -d {0}' -f $script:Cfg.Distro)
                        icon = $Icon; startingDirectory = '~' }) }
            [System.IO.File]::WriteAllText((Join-Path $FragmentDir 'koha.json'), ($frag | ConvertTo-Json -Depth 5), $utf8)
            [void]$done.Add('terminal-fragment')
        } catch { Write-KohaLog ('icon: terminal fragment not written: ' + $_.Exception.Message) }
    }
    Write-KohaLog ('icon: koha.ico set on {0}' -f ($done -join ', '))
    return @($done)
}

# ----------------------------------------------------------------------
# Tray at sign-in (HKCU Run: no administrator rights)
# ----------------------------------------------------------------------
# The last "<Command> failed:" line KohaEasy.ps1 wrote today (its trap), so
# a tray that ended at once can say why. '' when there is none.
function Get-KohaLastFailure {
    param([string]$Command)
    try {
        $file = Join-Path (Get-KohaPath Logs) ('koha-{0}.log' -f (Get-Date -Format 'yyyyMMdd'))
        if (-not (Test-Path -LiteralPath $file)) { return '' }
        $hit = Select-String -LiteralPath $file -Pattern ('\| {0} failed: ' -f [regex]::Escape($Command)) | Select-Object -Last 1
        if ($hit) { return (($hit.Line -split ' failed: ', 2)[1] -split ' \| stack: ')[0] }
    } catch { }
    return ''
}

function Test-KohaTrayAtSignIn {
    try {
        $v = (Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'KohaEasyTray' -ErrorAction Stop).KohaEasyTray
        return [bool]$v
    } catch { return $false }
}

# The Koha icon (desktop and Start menu), before the Koha window opens:
# whatever is missing is started or put back, nothing is started twice.
#   - the Koha icon next to the clock at sign-in (the Run entry), and the
#     Koha tasks, when someone deleted them;
#   - the tray, when it is not running;
#   - Koha, when Debian is not running (the window shows it starting).
# Returns what it did: signin, tasks, tray, start.
function Invoke-KohaLaunch {
    $did = New-Object System.Collections.ArrayList
    try {
        if (-not (Test-KohaTrayAtSignIn)) { Set-KohaTrayAtSignIn -Enabled $true; [void]$did.Add('signin') }
    } catch { Write-KohaLog ('Koha icon: sign-in entry not written: ' + $_.Exception.Message) }
    try {
        if ((Repair-KohaTasks) -eq 'registered') { [void]$did.Add('tasks') }
    } catch { Write-KohaLog ('Koha icon: tasks not registered again: ' + $_.Exception.Message) }
    if (-not (Test-KohaTrayRunning)) {
        Set-KohaState @{ trayClosed = $false } | Out-Null
        Start-KohaHidden 'Tray'
        [void]$did.Add('tray')
    }
    if (-not (Test-KohaDistroRunning)) {
        Start-Koha -Trigger user | Out-Null
        [void]$did.Add('start')
    }
    Write-KohaLog ('Koha icon: {0}' -f ((@($did) + @('window')) -join ', '))
    return @($did)
}

function Set-KohaTrayAtSignIn {
    param([bool]$Enabled = $true)
    $key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    if ($Enabled) {
        $l = Get-KohaHiddenLaunch -Arguments 'Tray'
        $cmd = '"{0}" {1}' -f $l.Target, $l.Arguments
        New-ItemProperty -Path $key -Name 'KohaEasyTray' -Value $cmd -PropertyType String -Force -ErrorAction Stop | Out-Null
    } else {
        Remove-ItemProperty -Path $key -Name 'KohaEasyTray' -ErrorAction SilentlyContinue
    }
}

# The tray is the PowerShell running "KohaEasy.ps1 Tray" (whatever started it:
# KohaEasy.exe, conhost or PowerShell itself).
function Test-KohaTrayRunning {
    # The tray holds this mutex while it runs (KohaEasy.Tray.ps1).
    $m = $null
    try {
        if ([System.Threading.Mutex]::TryOpenExisting('Local\KohaEasyTray', [ref]$m)) { $m.Dispose(); return $true }
    } catch { }
    try {
        return (@(Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction Stop |
                Where-Object { ([string]$_.CommandLine) -match 'KohaEasy\.ps1"?\s+Tray' }).Count -gt 0)
    } catch { return $false }
}

# The keep-alive task's watch: the Koha icon starts at every sign-in, so a
# missing one crashed or was ended. The librarian's own "Close this icon"
# is respected until the next sign-in.
function Repair-KohaTray {
    if ([bool](Get-KohaState).trayClosed) { return 'closed' }
    if (Test-KohaTrayRunning) { return 'running' }
    Write-KohaLog 'keep-alive: the Koha icon was not running; starting it again'
    Start-KohaHidden 'Tray'
    return 'restarted'
}

# Windows 11 puts a new notification-area icon in the hidden overflow (^).
# When the Koha icon first appears, Windows records it under
# HKCU\Control Panel\NotifyIconSettings (one key per icon, with its program
# and its first tooltip, "Koha"); IsPromoted=1 shows it next to the clock.
# Done once: if the librarian hides it again, that choice stays. Windows 10
# has no such key. [verify] undocumented, on Windows 11 23H2 and 24H2.
function Set-KohaTrayPromoted {
    param([string]$Root = 'HKCU:\Control Panel\NotifyIconSettings')
    if ([bool](Get-KohaState).trayPromoted) { return 'done' }
    if (-not (Test-Path -LiteralPath $Root)) { return 'unsupported' }
    $found = $false
    foreach ($k in @(Get-ChildItem -LiteralPath $Root -ErrorAction SilentlyContinue)) {
        $p = Get-ItemProperty -LiteralPath $k.PSPath -ErrorAction SilentlyContinue
        if ($null -eq $p) { continue }
        $exe = ''
        $tip = ''
        if ($p.PSObject.Properties['ExecutablePath']) { $exe = [string]$p.ExecutablePath }
        if ($p.PSObject.Properties['InitialTooltip']) { $tip = [string]$p.InitialTooltip }
        if ($tip -ne 'Koha' -or $exe -notmatch '(?i)\\(powershell|KohaEasy)\.exe$') { continue }
        New-ItemProperty -LiteralPath $k.PSPath -Name IsPromoted -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue | Out-Null
        $found = $true
    }
    if (-not $found) { return 'not-found' }
    Set-KohaState @{ trayPromoted = $true } | Out-Null
    Write-KohaLog 'tray: the Koha icon is shown next to the clock'
    return 'promoted'
}

$script:KohaEasyVersion = '0.1.0'

Export-ModuleMember -Function * -Variable KohaEasyVersion
