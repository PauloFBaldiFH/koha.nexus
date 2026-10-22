param(
    [Parameter(Mandatory = $true)][string]$Distro,
    [Parameter(Mandatory = $true)][string]$LinuxDir,
    [Parameter(Mandatory = $true)][string]$WindowScript
)
$ErrorActionPreference = 'Stop'
$kohaRoot = 'C:\Koha'
$kohaBin = Join-Path $kohaRoot 'bin'
$mainScript = Join-Path $kohaBin 'KohaEasy.ps1'
$logPath = Join-Path $kohaRoot 'logs\msix-bootstrap.log'
$wslExe = Join-Path $env:SystemRoot 'System32\wsl.exe'
$powerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

# The preparation stage sets this only to keep its own console in place. The
# panel must use the normal Windows Terminal path, with UTF-8 output.
Remove-Item Env:KOHAEASY_NO_WT -ErrorAction SilentlyContinue
$env:KOHAEASY_ROOT = $kohaRoot
try {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $chcp = Join-Path $env:SystemRoot 'System32\chcp.com'
    if (Test-Path -LiteralPath $chcp -PathType Leaf) { & $chcp 65001 | Out-Null }
    [Console]::InputEncoding = $utf8
    [Console]::OutputEncoding = $utf8
    $global:OutputEncoding = $utf8
} catch { }

function Write-PanelLog {
    param([string]$Message)
    try {
        New-Item -ItemType Directory -Path (Split-Path -Parent $logPath) -Force | Out-Null
        Add-Content -LiteralPath $logPath -Encoding UTF8 -Value ('{0} | {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message)
    } catch { }
}

$finalizerExit = 0
try {
    if (-not (Test-Path -LiteralPath $wslExe -PathType Leaf)) { throw 'wsl.exe was not found.' }
    Write-PanelLog ('Panel terminal started; distro={0}; user={1}' -f $Distro, [Security.Principal.WindowsIdentity]::GetCurrent().Name)
    Write-Host ''
    Write-Host 'Koha.Nexus control panel' -ForegroundColor Green
    Write-Host 'Choose the language and use the panel to install the Koha server and database.' -ForegroundColor Gray
    Write-Host ''

    # What Invoke-KohaPanel tells the panel, through WSLENV: plain symbols
    # outside Windows Terminal, and whether this window runs as administrator
    # (Windows then refuses files dragged from Explorer, and the panel says to
    # paste the path instead).
    $env:KEI_PLAIN_GLYPHS = '1'
    if ($env:WT_SESSION) { $env:KEI_PLAIN_GLYPHS = '0' }
    $principal = New-Object Security.Principal.WindowsPrincipal ([Security.Principal.WindowsIdentity]::GetCurrent())
    $env:KEI_WIN_ELEVATED = '0'
    if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { $env:KEI_WIN_ELEVATED = '1' }
    $wslEnv = @(([string]$env:WSLENV) -split ':' | Where-Object { $_ })
    foreach ($name in 'KEI_PLAIN_GLYPHS', 'KEI_WIN_ELEVATED') {
        if (@($wslEnv | ForEach-Object { ($_ -split '/')[0] }) -notcontains $name) { $wslEnv += $name }
    }
    $env:WSLENV = $wslEnv -join ':'

    & $wslExe --distribution $Distro --user root --cd $LinuxDir -- $WindowScript bash ./installer
    $panelExit = $LASTEXITCODE
    Write-PanelLog ('Control panel exited with code {0}; beginning Windows post-setup.' -f $panelExit)

    # A separate PowerShell process runs the project's normal Windows setup
    # phase after the panel closes. Its quiet readiness gate avoids changing
    # installation state if the user exits the panel before finishing Koha.
    if (Test-Path -LiteralPath $mainScript -PathType Leaf) {
        $oldFinalize = $env:KOHA_MSIX_FINALIZE
        $oldRoot = $env:KOHAEASY_ROOT
        try {
            $env:KOHA_MSIX_FINALIZE = '1'
            $env:KOHAEASY_ROOT = $kohaRoot
            $arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" Install' -f $mainScript
            Write-Host ''
            Write-Host 'Finishing Windows shortcuts, background tasks and network setup...' -ForegroundColor Cyan
            $process = Start-Process -FilePath $powerShellExe -ArgumentList $arguments -NoNewWindow -PassThru -Wait -ErrorAction Stop
            $finalizerExit = [int]$process.ExitCode
            Write-PanelLog ('Windows post-setup exited with code {0}.' -f $finalizerExit)
            $iconFixer = Join-Path $kohaBin 'KohaMsixRefreshIcons.ps1'
            if (Test-Path -LiteralPath $iconFixer -PathType Leaf) {
                try { & $iconFixer } catch { Write-PanelLog ('Icon refresh warning: ' + $_.Exception.Message) }
            }

        }
        finally {
            if ($null -eq $oldFinalize) { Remove-Item Env:KOHA_MSIX_FINALIZE -ErrorAction SilentlyContinue } else { $env:KOHA_MSIX_FINALIZE = $oldFinalize }
            if ($null -eq $oldRoot) { Remove-Item Env:KOHAEASY_ROOT -ErrorAction SilentlyContinue } else { $env:KOHAEASY_ROOT = $oldRoot }
        }
    }
    else {
        Write-PanelLog 'KohaEasy.ps1 not found; skipped Windows post-setup.'
        Write-Host 'The Windows post-setup script was not found. Check C:\Koha\logs\msix-bootstrap.log.' -ForegroundColor Yellow
        $finalizerExit = 2
    }

    Write-Host ''
    Write-Host 'The panel has closed. If Koha server installation was not completed, open Koha.Nexus again to continue.' -ForegroundColor Gray
    if ($finalizerExit -ne 0) {
        Write-Host ('Windows post-setup ended with code {0}. See C:\Koha\logs\msix-bootstrap.log.' -f $finalizerExit) -ForegroundColor Yellow
    }
    Read-Host 'Press Enter to close this window' | Out-Null
    exit $finalizerExit
}
catch {
    $message = $_.Exception.Message
    Write-PanelLog ('ERROR in panel wrapper: ' + $message)
    Write-Host ''
    Write-Host ('Panel wrapper error: ' + $message) -ForegroundColor Red
    Write-Host 'See C:\Koha\logs\msix-bootstrap.log for details.' -ForegroundColor Yellow
    Read-Host 'Press Enter to close this window' | Out-Null
    exit 1
}