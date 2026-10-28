# koha.nexus for Windows - bootstrapper.
#
#   How to install Koha on Windows: this line, in PowerShell opened as
#   Administrator from your own (administrator) Windows account:
#   irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
#
# Step 0: hardware virtualization must be on (WSL 2 needs it). If it is
# off, nothing is downloaded: the BIOS/UEFI steps for this PC's board and
# CPU are shown, with an offer to restart straight into the firmware setup.
#
# It copies the Windows tools, the panel and its dictionaries to
# C:\Koha\bin (downloaded from GitHub with the
# SHA-256 of the installer checked), then runs "KohaEasy.ps1 Install" in
# Windows PowerShell 5.1: checks, the Debian user, WSL 2, Debian, systemd,
# Koha, shortcuts, the library network. All of it runs in the PowerShell
# window the command was typed in. Uninstall-Koha.cmd, in C:\Koha,
# removes it all again.
# Running it again continues where it stopped. An install made before the
# folder was renamed stays in C:\KohaEasy and is updated there.
#
# Options (environment variables): KOHAEASY_SOURCE (a local copy of the
# repository), KOHAEASY_BRANCH (default main), KOHAEASY_ROOT (default C:\Koha).
# ASCII only: it must survive "irm | iex" in every Windows PowerShell.

try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

# UTF-8 before anything is printed, so accents never turn into "?". The
# encoding has no BOM: [Text.Encoding]::UTF8 in Windows PowerShell 5.1 would
# put one in front of every script this installer sends into Debian.
try { & "$env:SystemRoot\System32\chcp.com" 65001 | Out-Null } catch { }
try {
    $kohaUtf8 = New-Object System.Text.UTF8Encoding($false)
    [Console]::OutputEncoding = $kohaUtf8
    [Console]::InputEncoding = $kohaUtf8
    $OutputEncoding = $kohaUtf8
} catch { }

# ----------------------------------------------------------------------
# Step 0: hardware virtualization (Intel VT-x / AMD-V). WSL 2 cannot start
# without it, so the installer stops here, before anything is downloaded or
# installed, and shows where the switch is in this PC's BIOS/UEFI.
# ----------------------------------------------------------------------

# What this PC reports. VirtualizationFirmwareEnabled is $null when Windows
# cannot tell (some virtual machines, ARM). With Hyper-V or WSL 2 already
# running, Windows reports it as False: the hypervisor took the CPU feature,
# which proves it is on (HypervisorPresent).
function Get-KohaVirtualizationFacts {
    $f = @{ Firmware = $null; Hypervisor = $false; Cpu = ''; CpuName = ''; Board = ''; Model = '' }
    try {
        $cpu = Get-CimInstance Win32_Processor -ErrorAction Stop | Select-Object -First 1
        $f.Firmware = $cpu.VirtualizationFirmwareEnabled
        $f.CpuName = [string]$cpu.Name
        $f.Cpu = [string]$cpu.Manufacturer
    } catch { }
    try {
        $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
        $f.Hypervisor = [bool]$cs.HypervisorPresent
        $csMaker = [string]$cs.Manufacturer
        $csModel = [string]$cs.Model
    } catch { $csMaker = ''; $csModel = '' }
    try {
        $bb = Get-CimInstance Win32_BaseBoard -ErrorAction Stop | Select-Object -First 1
        $f.Board = ([string]$bb.Manufacturer).Trim()
        $f.Model = ([string]$bb.Product).Trim()
    } catch { }
    # Boards without a name ("To be filled by O.E.M.", "Default string"):
    # the PC's own maker and model say more.
    if (-not $f.Board -or $f.Board -match 'O\.?E\.?M|Default string|System manufacturer') { $f.Board = $csMaker.Trim() }
    if (-not $f.Model -or $f.Model -match 'O\.?E\.?M|Default string|System Product') { $f.Model = $csModel.Trim() }
    return $f
}

# Pure: whether the installer may continue. Unknown (null) is not a reason
# to stop: the later checks and WSL itself still say so if it is off.
function Test-KohaVirtualizationOn {
    param([hashtable]$Facts)
    return ([bool]$Facts.Hypervisor -or $Facts.Firmware -ne $false)
}

# Pure: AMD, Intel or '' (unknown, e.g. ARM), from the CPU's maker or name.
function Get-KohaCpuBrand {
    param([hashtable]$Facts)
    $t = ('{0} {1}' -f $Facts.Cpu, $Facts.CpuName)
    if ($t -match 'AMD') { return 'AMD' }
    if ($t -match 'Intel') { return 'Intel' }
    return ''
}

# Pure: the board maker's family (ASUS, Gigabyte, MSI, ASRock, Dell, HP,
# Lenovo) or '' for the generic steps.
function Get-KohaBoardFamily {
    param([string]$Maker)
    switch -Regex ($Maker) {
        'ASRock' { return 'ASRock' }
        'ASUS' { return 'ASUS' }
        'Gigabyte|AORUS' { return 'Gigabyte' }
        'Micro-Star|^MSI' { return 'MSI' }
        'Dell' { return 'Dell' }
        '^HP\b|Hewlett' { return 'HP' }
        'Lenovo' { return 'Lenovo' }
    }
    return ''
}

# Pure: where the switch is, for this board and CPU, one line per step.
function Get-KohaBiosSteps {
    param([string]$Family, [string]$Brand)
    $opt = switch ($Brand) {
        'AMD' { 'SVM Mode' }
        'Intel' { 'Intel Virtualization Technology' }
        default { 'SVM Mode (AMD) or Intel Virtualization Technology (Intel)' }
    }
    switch ($Family) {
        'ASUS' {
            return @('Restart the PC and press Del (or F2) repeatedly while the ASUS logo shows.',
                'Press F7 to switch to Advanced Mode.',
                ('Go to Advanced > CPU Configuration > {0} and set it to Enabled.' -f $opt),
                'Press F10 and confirm to save and restart.')
        }
        'Gigabyte' {
            return @('Restart the PC and press Del repeatedly while the GIGABYTE / AORUS logo shows.',
                'Press F2 if the Easy Mode screen opens, to reach the advanced screens.',
                ('Go to Tweaker (on older boards M.I.T.) > Advanced CPU Settings > {0} and set it to Enabled.' -f $opt),
                'Press F10 and confirm to save and restart.')
        }
        'MSI' {
            $msi = $opt
            if ($Brand -eq 'Intel') { $msi = 'Intel Virtualization Tech' }
            return @('Restart the PC and press Del repeatedly while the MSI logo shows.',
                'Press F7 to switch to Advanced mode.',
                ('Go to OC > CPU Features > {0} and set it to Enabled.' -f $msi),
                'Press F10 and confirm to save and restart.')
        }
        'ASRock' {
            $asr = $opt
            if ($Brand -eq 'Intel') { $asr = 'Intel Virtualization Technology (VMX)' }
            return @('Restart the PC and press F2 (or Del) repeatedly while the ASRock logo shows.',
                'Press F6 if the Easy Mode screen opens, to reach Advanced Mode.',
                ('Go to Advanced > CPU Configuration > {0} and set it to Enabled.' -f $asr),
                'Press F10 and confirm to save and restart.')
        }
        'Dell' {
            return @('Restart the PC and press F2 repeatedly while the Dell logo shows.',
                'Open Virtualization Support (on some models: Advanced Setup > Virtualization).',
                'Turn on Virtualization / Enable Intel Virtualization Technology (AMD-V on AMD models).',
                'Click Apply, then Exit to restart.')
        }
        'HP' {
            return @('Restart the PC and press Esc repeatedly, then F10 for BIOS Setup.',
                'Open Advanced > System Options (on older models: Security or System Configuration > Device Configurations).',
                'Turn on Virtualization Technology (VTx), or AMD-V / SVM on AMD models.',
                'Press F10 (or Save Changes and Exit) and confirm.')
        }
        'Lenovo' {
            return @('Restart the PC and press F1 (ThinkPad, ThinkCentre) or F2 / the Novo button (IdeaPad, Legion) while the Lenovo logo shows.',
                'ThinkPad / ThinkCentre: Security > Virtualization. IdeaPad / Legion: Configuration.',
                'Set Intel Virtualization Technology (Intel VT-x) or AMD V(TM) Technology / SVM to Enabled.',
                'Press F10 and confirm to save and restart.')
        }
    }
    return @('Restart the PC and press the setup key while its logo shows: usually Del or F2 (some PCs: F1, F10 or Esc).',
        'Look for a page named Advanced, CPU Configuration, Chipset or Virtualization.',
        ('Find {0} (other names: {1}) and set it to Enabled.' -f $opt, $(if ($Brand -eq 'AMD') { 'AMD-V, SVM' } elseif ($Brand -eq 'Intel') { 'VT-x, VMX, Intel VT' } else { 'AMD-V, SVM, VT-x, VMX' })),
        'Save and exit, usually with F10.')
}

# Restarts into the BIOS/UEFI setup (shutdown /r /fw). Where that is not
# possible (legacy BIOS, no firmware support), into the Advanced startup
# menu instead (shutdown /r /o): Troubleshoot > Advanced options > UEFI
# Firmware Settings. $Run is the call to shutdown.exe (tests replace it).
# Returns 'fw', 'o' or '' when neither worked.
function Invoke-KohaFirmwareReboot {
    param([scriptblock]$Run = { param([string[]]$a) & (Join-Path $env:SystemRoot 'System32\shutdown.exe') @a 2>&1 | Out-Null; $LASTEXITCODE })
    if ((& $Run @('/r', '/fw', '/t', '2')) -eq 0) { return 'fw' }
    if ((& $Run @('/r', '/o', '/t', '2')) -eq 0) { return 'o' }
    return ''
}

# Step 0. $true: virtualization is on, the install goes on. $false: it is
# off; the steps for this PC were shown and the person either restarts into
# the BIOS now or later. Nothing was installed either way.
function Assert-VirtualizationReady {
    param([hashtable]$Facts = (Get-KohaVirtualizationFacts),
        [scriptblock]$Ask = { Read-Host 'Restart into the BIOS/UEFI now? [Y/N]' },
        [scriptblock]$Reboot = { Invoke-KohaFirmwareReboot })
    $okMark = '[OK]'
    if ($env:WT_SESSION) { $okMark = '[' + [char]0x2713 + ']' }
    if (Test-KohaVirtualizationOn $Facts) {
        Write-Host ('{0} Hardware virtualization is active. Proceeding...' -f $okMark) -ForegroundColor Green
        return $true
    }
    $brand = Get-KohaCpuBrand $Facts
    $family = Get-KohaBoardFamily $Facts.Board
    $line = '=' * 72
    Write-Host ''
    Write-Host $line -ForegroundColor Red
    Write-Host '  [!] HARDWARE VIRTUALIZATION IS TURNED OFF' -ForegroundColor Yellow
    Write-Host '  Koha runs in WSL 2, which needs it. The installation stopped here:' -ForegroundColor Yellow
    Write-Host '  nothing was downloaded or installed.' -ForegroundColor Yellow
    Write-Host $line -ForegroundColor Red
    Write-Host ''
    Write-Host 'This PC' -ForegroundColor Cyan
    $cpuText = $Facts.CpuName
    if (-not $cpuText) { $cpuText = 'unknown' }
    $boardText = ('{0} {1}' -f $Facts.Board, $Facts.Model).Trim()
    if (-not $boardText) { $boardText = 'unknown' }
    Write-Host ('  Processor:   {0}' -f $cpuText) -ForegroundColor White
    Write-Host ('  Motherboard: {0}' -f $boardText) -ForegroundColor White
    Write-Host ''
    $title = 'How to turn it on'
    if ($family) { $title = ('How to turn it on ({0} BIOS/UEFI)' -f $family) }
    Write-Host $title -ForegroundColor Cyan
    $n = 0
    foreach ($s in (Get-KohaBiosSteps -Family $family -Brand $brand)) {
        $n++
        Write-Host ('  {0}. ' -f $n) -ForegroundColor Yellow -NoNewline
        Write-Host $s -ForegroundColor White
    }
    Write-Host '  Menus differ between models and BIOS versions: look for the same words nearby.' -ForegroundColor Gray
    Write-Host ''
    Write-Host '  >> Take a photo of this screen with your phone before proceeding. <<' -ForegroundColor Magenta
    Write-Host ''
    Write-Host 'Y restarts this PC straight into the BIOS/UEFI in a few seconds: save your work first.' -ForegroundColor Cyan
    $answer = ''
    while ($answer -notmatch '^[YyNn]') {
        $answer = [string](& $Ask)
        if ($null -eq $answer -or $answer -eq '') { $answer = 'N' }
    }
    if ($answer -match '^[Yy]') {
        $how = & $Reboot
        if ($how -eq 'fw') {
            Write-Host '[>] Restarting into the BIOS/UEFI...' -ForegroundColor Green
        } elseif ($how -eq 'o') {
            Write-Host '[>] This PC cannot open its firmware setup directly. Restarting into Advanced startup:' -ForegroundColor Yellow
            Write-Host '    choose Troubleshoot > Advanced options > UEFI Firmware Settings > Restart.' -ForegroundColor Yellow
        } else {
            Write-Host '[!] Windows could not restart into the BIOS/UEFI. Restart the PC yourself and press the setup key shown in step 1.' -ForegroundColor Yellow
        }
    } else {
        Write-Host '[i] The installation is paused.' -ForegroundColor Yellow
        Write-Host '    Save your work, turn on virtualization in the BIOS/UEFI as shown above, then run the same' -ForegroundColor Yellow
        Write-Host '    command again: the installation starts from the beginning, nothing was changed.' -ForegroundColor Yellow
    }
    return $false
}

function Install-KohaEasyBootstrap {
    $ErrorActionPreference = 'Stop'
    $repo = 'PauloFBaldiFH/koha.nexus'
    $branch = 'main'
    if ($env:KOHAEASY_BRANCH) { $branch = $env:KOHAEASY_BRANCH }
    $root = 'C:\Koha'
    $old = 'C:\KohaEasy'
    if ($env:KOHAEASY_ROOT) { $root = $env:KOHAEASY_ROOT }
    elseif (-not (Test-Path -LiteralPath (Join-Path $root 'state.json')) -and
        ((Test-Path -LiteralPath (Join-Path $old 'state.json')) -or (Test-Path -LiteralPath (Join-Path $old 'bin\KohaEasy.ps1')))) {
        $root = $old
    }
    $bin = Join-Path $root 'bin'
    $tmp = $null

    Write-Host ''
    Write-Host 'koha.nexus for Windows' -ForegroundColor Green
    if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'This installer runs on Windows 10 or 11.' }
    # Emoji only where they can be drawn: Windows Terminal. Code points keep
    # this file ASCII.
    $mark = '[>]'
    if ($env:WT_SESSION) { $mark = [char]::ConvertFromUtf32(0x1F680) }

    $src = $env:KOHAEASY_SOURCE
    if (-not $src) {
        Write-Host ('{0} Downloading koha.nexus ({1})...' -f $mark, $branch) -ForegroundColor Cyan
        $tmp = Join-Path $env:TEMP ('KohaEasy-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tmp -Force | Out-Null
        $zip = Join-Path $tmp 'source.zip'
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri ('https://github.com/{0}/archive/refs/heads/{1}.zip' -f $repo, $branch) -OutFile $zip -UseBasicParsing
        Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
        $src = (Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1).FullName
    } else {
        Get-ChildItem -LiteralPath $src -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
    }

    foreach ($need in 'installer', 'installer.sha256', 'windows\KohaEasy.ps1', 'windows\KohaEasy.Install.psm1') {
        if (-not (Test-Path -LiteralPath (Join-Path $src $need))) { throw ('Missing file in the installer package: ' + $need) }
    }
    $expected = ((Get-Content -LiteralPath (Join-Path $src 'installer.sha256') -TotalCount 1) -split '\s+')[0].ToUpperInvariant()
    $actual = (Get-FileHash -LiteralPath (Join-Path $src 'installer') -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($expected -ne $actual) { throw 'The installer file is damaged (SHA-256 does not match installer.sha256). Download it again.' }

    New-Item -ItemType Directory -Path (Join-Path $bin 'lang') -Force | Out-Null
    # The Python tray and window of 1.5.x test builds (bin\client, its
    # bin\python runtime and bin\nexus_core) were dropped: removed, with
    # their download cache, so nothing of them is left on this PC. One still
    # running from bin\python is ended first (Windows keeps a running
    # program's files). The Koha status window (KohaEasy.Window.ps1) went
    # too: the control panel replaced it.
    try {
        $pyDir = (Join-Path $bin 'python') + '\'
        Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" -ErrorAction Stop |
            Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($pyDir, [StringComparison]::OrdinalIgnoreCase) } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch { }
    $oldWindow = Join-Path $bin 'KohaEasy.Window.ps1'
    if (Test-Path -LiteralPath $oldWindow) { Remove-Item -LiteralPath $oldWindow -Force -ErrorAction SilentlyContinue }
    foreach ($old in 'client', 'nexus_core', 'python') {
        $oldBin = Join-Path $bin $old
        if (Test-Path -LiteralPath $oldBin) { Remove-Item -LiteralPath $oldBin -Recurse -Force -ErrorAction SilentlyContinue }
    }
    $oldCache = Join-Path $root 'downloads\python'
    if (Test-Path -LiteralPath $oldCache) { Remove-Item -LiteralPath $oldCache -Recurse -Force -ErrorAction SilentlyContinue }
    Copy-Item -Path (Join-Path $src 'windows\*') -Destination $bin -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $src 'installer'), (Join-Path $src 'installer.sha256') -Destination $bin -Force
    Copy-Item -Path (Join-Path $src 'lang\*.cache') -Destination (Join-Path $bin 'lang') -Force
    # The new panel (Python/Textual); KohaEasy.Install copies it into Debian.
    $panelBin = Join-Path $bin 'panel'
    if (Test-Path -LiteralPath $panelBin) { Remove-Item -LiteralPath $panelBin -Recurse -Force }
    if (Test-Path -LiteralPath (Join-Path $src 'panel')) {
        Copy-Item -LiteralPath (Join-Path $src 'panel') -Destination $bin -Recurse -Force
    }
    Copy-Item -LiteralPath (Join-Path $src 'windows\Uninstall-Koha.cmd') -Destination $root -Force
    if ($tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }

    # The tray and toasts need Windows PowerShell 5.1, even when this ran in
    # PowerShell 7. Start-Process -NoNewWindow gives the install the console
    # itself: its messages, questions and the Koha panel appear here. (Calling
    # it with & inside this function would capture its output as the return
    # value, so the librarian would see nothing and the panel could not draw.)
    $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $env:KOHAEASY_ROOT = $root
    $arg = '-NoProfile -ExecutionPolicy Bypass -File "{0}" Install' -f (Join-Path $bin 'KohaEasy.ps1')

    # The whole install stays in this window, from the first line to the
    # end: no Windows Terminal or other window is opened to continue it.
    # Outside Windows Terminal the classic console has no emoji font, so the
    # panel shows plain symbols there (KEI_PLAIN_GLYPHS). KOHAEASY_NO_WT is
    # no longer needed for this and is left unread.
    $p = Start-Process -FilePath $ps -ArgumentList $arg -NoNewWindow -Wait -PassThru
    return [int]$p.ExitCode
}

# Step 0 first: nothing is downloaded or installed on a PC without
# virtualization. Run as a script file (-File), it ends with exit code 1;
# through "irm | iex" exit would close the person's PowerShell window with
# the steps still to read, so it only stops.
$kohaVirtOk = $true
try { $kohaVirtOk = Assert-VirtualizationReady } catch { Write-Host ('[!] The virtualization check failed: {0}. Continuing.' -f $_.Exception.Message) -ForegroundColor Yellow }
if (-not $kohaVirtOk) {
    if ($PSCommandPath) { exit 1 }
    $global:LASTEXITCODE = 1
} else {
    try {
        $code = Install-KohaEasyBootstrap
        if ($code -eq 3) { Write-Host 'Restart Windows now. The installation continues after you sign in again.' -ForegroundColor Yellow }
        elseif ($code -ne 0) { Write-Host ('The installation stopped (code {0}). Run the same command again to continue. Log: {1}\logs' -f $code, $env:KOHAEASY_ROOT) -ForegroundColor Red }
        # Run as a file (the MSIX bootstrap does), the exit code says what
        # happened: 3 = restart Windows, other codes = stopped. Under
        # "irm | iex" exit would close the window, so it only stops.
        if ($PSCommandPath -and $code -gt 0) { exit $code }
    } catch {
        Write-Host ('[X] ' + $_.Exception.Message) -ForegroundColor Red
        if ($PSCommandPath) { exit 1 }
    }
}
