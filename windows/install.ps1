# koha.nexus for Windows - bootstrapper.
#
#   How to install Koha on Windows: this line, in PowerShell opened as
#   Administrator from your own (administrator) Windows account:
#   irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
#
# It copies the Windows tools, the panel and its dictionaries to
# C:\Koha\bin (downloaded from GitHub with the
# SHA-256 of the installer checked), then runs "KohaEasy.ps1 Install" in
# Windows PowerShell 5.1: checks, the Debian user, WSL 2, Debian, systemd,
# Koha, shortcuts, the library network. Uninstall-Koha.cmd, in C:\Koha,
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

    # The classic console has no emoji font. When Windows Terminal is
    # installed, the install continues in a Windows Terminal window, which
    # shows the emoji and accents; this window can then be closed. Without
    # Windows Terminal it stays here, with plain symbols.
    $wt = $null
    if (-not $env:WT_SESSION -and $env:KOHAEASY_NO_WT -ne '1') {
        $wt = Get-Command 'wt.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    # A Windows Terminal that is already open would not see KOHAEASY_ROOT;
    # KohaEasy.ps1 finds the folder from its own place (<root>\bin).
    if ($wt) {
        try {
            Start-Process -FilePath $wt.Source -ArgumentList ('-w new --title Koha "{0}" {1} -Pause' -f $ps, $arg) | Out-Null
            Write-Host '[>] The installation continues in the new Windows Terminal window.' -ForegroundColor Cyan
            return -1
        } catch {
            Write-Host '[!] Windows Terminal did not open; the installation continues here.' -ForegroundColor Yellow
        }
    }
    $p = Start-Process -FilePath $ps -ArgumentList $arg -NoNewWindow -Wait -PassThru
    return [int]$p.ExitCode
}

try {
    $code = Install-KohaEasyBootstrap
    if ($code -eq -1) { }
    elseif ($code -eq 3) { Write-Host 'Restart Windows now. The installation continues after you sign in again.' -ForegroundColor Yellow }
    elseif ($code -ne 0) { Write-Host ('The installation stopped (code {0}). Run the same command again to continue. Log: {1}\logs' -f $code, $env:KOHAEASY_ROOT) -ForegroundColor Red }
} catch {
    Write-Host ('[X] ' + $_.Exception.Message) -ForegroundColor Red
}
