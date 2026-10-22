#Requires -Version 5.1
# -Store: gera o pacote para a Microsoft Store com a identidade de
# windows\msix\store-identity.json, sem assinar e sem instalar (a Store assina).
param([switch]$Store)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# ============================================================
# KOHA.NEXUS - BUILD, SIGN, INSTALL AND LAUNCH MSIX (V17)
# PowerShell 5.1 | MakeAppx | SignTool | certificado local
# ============================================================

$scriptRoot = $PSScriptRoot
$repoDir    = (Resolve-Path -LiteralPath (Join-Path $scriptRoot '..\..')).Path
$distDir    = Join-Path $repoDir 'dist'
$pkgDir     = Join-Path $distDir 'PackageRoot'
$msixPath   = Join-Path $distDir 'KohaNexus.msix'
$sdkDir     = Join-Path $env:TEMP 'MakeAppxSdk'
$makeAppx   = Join-Path $sdkDir 'MakeAppx.exe'
$signTool   = Join-Path $sdkDir 'SignTool.exe'
$windowsDir = Join-Path $repoDir 'windows'
$langDir    = Join-Path $repoDir 'lang'
$panelDir   = Join-Path $repoDir 'panel'
$installer  = Join-Path $repoDir 'installer'
$installerHash = Join-Path $repoDir 'installer.sha256'
# Assets customizados entregues junto com este script (devem ficar na mesma pasta).
$iconPath      = Join-Path $scriptRoot 'KohaNexusIcon.ico'
$logoImagePath = Join-Path $scriptRoot 'KohaNexusLogo.png'

# Versão solicitada originalmente. Precisa ser maior que qualquer versão
# anterior que ainda esteja instalada se o pacote for atualizado sem remoção.
$targetVersion = '1.0.26.0'
# Revision interna do payload: força a atualização de instalações incompletas
# feitas por builds anteriores, sem precisar alterar a versão pública do MSIX.
$payloadRevision = '1.0.26.0-msix-v18'
$packageName = 'KohaNexus'
$packagePublisher = 'CN=PauloFBaldiFH'
$publisherDisplayName = 'PauloFBaldiFH'
$storeIdentityPath = Join-Path $scriptRoot 'store-identity.json'
$applicationId = 'KohaNexus'
$entryExeName = 'KohaMsixEntry.exe'
$buildSucceeded = $false

function New-LogoPng {
    param(
        [Parameter(Mandatory = $true)][string]$SourceIcon,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][int]$Size
    )

    $icon = $null
    $sourceBitmap = $null
    $bitmap = $null
    $graphics = $null

    try {
        $icon = New-Object System.Drawing.Icon -ArgumentList $SourceIcon
        $sourceBitmap = $icon.ToBitmap()
        $bitmap = New-Object System.Drawing.Bitmap -ArgumentList @($Size, $Size)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.Clear([System.Drawing.Color]::Transparent)
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.DrawImage($sourceBitmap, 0, 0, $Size, $Size)
        $bitmap.Save($Destination, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        if ($graphics) { $graphics.Dispose() }
        if ($bitmap) { $bitmap.Dispose() }
        if ($sourceBitmap) { $sourceBitmap.Dispose() }
        if ($icon) { $icon.Dispose() }
    }
}

function New-LogoFromImagePng {
    param(
        [Parameter(Mandatory = $true)][string]$SourceImage,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][int]$Size
    )

    $sourceBitmap = $null
    $bitmap = $null
    $graphics = $null

    try {
        $sourceBitmap = [System.Drawing.Bitmap]::FromFile($SourceImage)
        # Bitmap padrão mantém canal alfa para preservar o fundo transparente do logo.
        $bitmap = New-Object System.Drawing.Bitmap -ArgumentList @($Size, $Size)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.Clear([System.Drawing.Color]::Transparent)
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
        $graphics.DrawImage($sourceBitmap, 0, 0, $Size, $Size)
        $bitmap.Save($Destination, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        if ($graphics) { $graphics.Dispose() }
        if ($bitmap) { $bitmap.Dispose() }
        if ($sourceBitmap) { $sourceBitmap.Dispose() }
    }
}

# A identidade que o Partner Center reservou para o app (Gerenciamento de
# produto > Identidade do produto). A Store recusa o pacote se Name, Publisher
# ou PublisherDisplayName forem diferentes desses valores.
function Get-KohaStoreIdentity {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Arquivo de identidade da Store não encontrado: $Path"
    }
    $data = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    $identity = [pscustomobject]@{
        Name                 = ([string]$data.Name).Trim()
        Publisher            = ([string]$data.Publisher).Trim()
        PublisherDisplayName = ([string]$data.PublisherDisplayName).Trim()
    }
    if (-not $identity.Name -or -not $identity.Publisher -or -not $identity.PublisherDisplayName) {
        throw "Preencha Name, Publisher e PublisherDisplayName em $Path com os valores de Partner Center > Identidade do produto."
    }
    if ($identity.Name -notmatch '^[A-Za-z0-9.\-]{3,50}$') {
        throw "Name inválido em ${Path}: '$($identity.Name)'."
    }
    if ($identity.Publisher -notmatch '^CN=\S') {
        throw "Publisher inválido em ${Path}: deve começar com 'CN=', como no Partner Center."
    }
    return $identity
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal -ArgumentList $identity
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

try {
    Write-Host ''
    Write-Host '============================================================' -ForegroundColor Cyan
    Write-Host (' KOHA.NEXUS - GERAR, ASSINAR E INSTALAR MSIX ' + $targetVersion) -ForegroundColor Cyan
    Write-Host '============================================================' -ForegroundColor Cyan

    if ($Store) {
        $storeIdentity = Get-KohaStoreIdentity -Path $storeIdentityPath
        $packageName = $storeIdentity.Name
        $packagePublisher = $storeIdentity.Publisher
        $publisherDisplayName = $storeIdentity.PublisherDisplayName
        $msixPath = Join-Path $distDir 'KohaNexus-Store.msix'
        Write-Host ("Modo Store: {0} | {1} | {2}" -f $packageName, $packagePublisher, $publisherDisplayName) -ForegroundColor Cyan
    }

    # --------------------------------------------------------
    # 1. VALIDAR CAMINHOS E FERRAMENTAS ANTES DE ALTERAR ARQUIVOS
    # --------------------------------------------------------

    foreach ($requiredPath in @($repoDir, $windowsDir, $langDir, $panelDir)) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Container)) {
            throw "Diretório obrigatório não encontrado: $requiredPath"
        }
    }

    foreach ($requiredFile in @($installer, $installerHash, $iconPath, $logoImagePath)) {
        if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
            throw "Arquivo obrigatório não encontrado: $requiredFile"
        }
    }

    foreach ($toolPath in @($makeAppx, $signTool)) {
        if (-not (Test-Path -LiteralPath $toolPath -PathType Leaf)) {
            throw "Ferramenta do SDK não encontrada: $toolPath"
        }
    }

    $compilerCandidates = @(
        (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'),
        (Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe')
    )
    $csc = $compilerCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1

    if (-not $csc) {
        throw 'O compilador csc.exe do .NET Framework não foi encontrado neste Windows.'
    }

    $essentialWindowsFiles = @(
        'KohaEasy.ps1',
        'KohaEasy.Core.psm1',
        'KohaEasy.Lang.psm1',
        'KohaEasy.Launcher.cs',
        'install.ps1'
    )
    foreach ($name in $essentialWindowsFiles) {
        $path = Join-Path $windowsDir $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Arquivo essencial ausente no repositório: $path"
        }
    }

    # Localiza o certificado de assinatura pela identidade Publisher exata.
    # O certificado informado pelo diagnóstico estava em LocalMachine\My.
    $certificateCandidates = @()
    $certificateStores = @(
        [pscustomobject]@{ Path = 'Cert:\LocalMachine\My'; Scope = 'LocalMachine' },
        [pscustomobject]@{ Path = 'Cert:\CurrentUser\My'; Scope = 'CurrentUser' }
    )

    foreach ($store in $certificateStores) {
        $storeCertificates = Get-ChildItem -Path $store.Path -ErrorAction SilentlyContinue
        foreach ($certificate in $storeCertificates) {
            if (
                $certificate.Subject -eq $packagePublisher -and
                $certificate.HasPrivateKey -and
                $certificate.NotBefore -le (Get-Date) -and
                $certificate.NotAfter -gt (Get-Date)
            ) {
                $certificateCandidates += [pscustomobject]@{
                    Certificate = $certificate
                    Scope       = $store.Scope
                }
            }
        }
    }

    $certificateRecord = $certificateCandidates |
        Sort-Object { $_.Certificate.NotAfter } -Descending |
        Select-Object -First 1

    if ($Store) {
        # A Store descarta qualquer assinatura e assina o pacote ela mesma.
        Write-Host 'Modo Store: o pacote sai sem assinatura; a Microsoft Store assina.' -ForegroundColor Gray
    } elseif (-not $certificateRecord) {
        throw "Não encontrei certificado válido com chave privada e Subject '$packagePublisher' nos repositórios My do usuário ou do computador."
    } else {
        $signingCertificate = $certificateRecord.Certificate
        $certificateScope = $certificateRecord.Scope

        Write-Host "Certificado: $($signingCertificate.Subject)" -ForegroundColor Gray
        Write-Host "Thumbprint: $($signingCertificate.Thumbprint)" -ForegroundColor Gray
        Write-Host "Repositório: $certificateScope" -ForegroundColor Gray
    }

    # --------------------------------------------------------
    # 2. RECRIAR PACKAGEROOT E MANTER A ESTRUTURA DA DISTRIBUIÇÃO
    # --------------------------------------------------------

    Write-Host "`n[1/8] Recriando PackageRoot e montando a carga da aplicação..." -ForegroundColor Yellow

    if (-not (Test-Path -LiteralPath $distDir -PathType Container)) {
        New-Item -ItemType Directory -Path $distDir -Force | Out-Null
    }

    if (Test-Path -LiteralPath $pkgDir) {
        Remove-Item -LiteralPath $pkgDir -Recurse -Force
    }

    New-Item -ItemType Directory -Path $pkgDir -Force | Out-Null

    # O instalador Windows existente espera uma raiz de origem com as pastas
    # windows, lang e panel, mais installer e installer.sha256. Não achatar essa
    # estrutura: windows\install.ps1 usa KOHAEASY_SOURCE para instalar corretamente
    # os arquivos em C:\Koha\bin e o painel no local esperado.
    $payloadDir = Join-Path $pkgDir 'Payload'
    $payloadWindowsDir = Join-Path $payloadDir 'windows'
    $payloadLangDir = Join-Path $payloadDir 'lang'
    New-Item -ItemType Directory -Path $payloadWindowsDir -Force | Out-Null
    New-Item -ItemType Directory -Path $payloadLangDir -Force | Out-Null

    $excludedWindowsDirectories = @(
        'setup', '.git', '.github', 'node_modules', '__pycache__',
        '$Recycle.Bin', 'System Volume Information', 'Recovery', 'RECYCLER'
    )
    $excludedWindowsFiles = @('desktop.ini', 'Thumbs.db', 'ehthumbs.db', '.DS_Store')

    foreach ($item in (Get-ChildItem -LiteralPath $windowsDir -Force)) {
        if ($item.PSIsContainer) {
            if ($excludedWindowsDirectories -contains $item.Name) { continue }
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
        }
        else {
            if ($excludedWindowsFiles -contains $item.Name) { continue }
        }
        Copy-Item -LiteralPath $item.FullName -Destination $payloadWindowsDir -Recurse -Force
    }

    # Fixar a porta do staff em 8080 na COPIA do modulo Core (nao no repositorio).
    $coreModulePath = Join-Path $payloadWindowsDir 'KohaEasy.Core.psm1'
    if (-not (Test-Path -LiteralPath $coreModulePath -PathType Leaf)) {
        throw "Arquivo obrigatorio nao encontrado: $coreModulePath"
    }
    $coreText = [System.IO.File]::ReadAllText($coreModulePath)
    $staffUrlPattern = '(?m)^(\s*StaffUrl\s*=\s*)''[^'']*'''
    $webPortsPattern = '(?m)^(\s*WebPorts\s*=\s*)@\([^)]*\)'
    if ([regex]::Matches($coreText, $staffUrlPattern).Count -ne 1 -or
        [regex]::Matches($coreText, $webPortsPattern).Count -ne 1) {
        throw 'StaffUrl/WebPorts nao encontrados de forma unica. Revisar modulo de origem.'
    }
    $coreText = [regex]::Replace($coreText, $staffUrlPattern, '${1}''http://localhost:8080/''')
    $coreText = [regex]::Replace($coreText, $webPortsPattern, '${1}@(80, 8080)')
    [System.IO.File]::WriteAllText($coreModulePath, $coreText, (New-Object System.Text.UTF8Encoding($true)))
    Write-Host 'Staff Windows: localhost:8080; portas: 80 e 8080.' -ForegroundColor Gray

    # Windows pode manter o icon antigo de um .lnk (e o EXE local pode
    # permanecer da tentativa anterior). Guardar um ICO com nome exclusivo da
    # revisao no diretorio do Koha e atualizar apenas atalhos do Koha.
    $iconFixScriptPath = Join-Path $payloadWindowsDir 'KohaMsixRefreshIcons.ps1'
    $iconFixScriptContent = @'
$ErrorActionPreference = 'Stop'
$root = 'C:\Koha'
$bin = Join-Path $root 'bin'
$sourceIcon = Join-Path $bin 'KohaNexusDesktop.ico'
$versionedIcon = Join-Path $bin 'KohaNexus-icon-msix-v17.ico'
if (-not (Test-Path -LiteralPath $sourceIcon -PathType Leaf)) {
    throw ('Icone do Koha nao encontrado: ' + $sourceIcon)
}
Copy-Item -LiteralPath $sourceIcon -Destination $versionedIcon -Force -ErrorAction Stop
$dirs = @(
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('CommonDesktopDirectory'),
    (Join-Path ([Environment]::GetFolderPath('Programs')) 'Koha')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Container) } | Select-Object -Unique
$shell = New-Object -ComObject WScript.Shell
$updated = 0
foreach ($folder in $dirs) {
    $links = Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -File -ErrorAction SilentlyContinue
    foreach ($link in $links) {
        if ($folder -notlike '*\Koha' -and $link.BaseName -notmatch '(?i)^koha(\b|[ ._-])') { continue }
        try {
            $shortcut = $shell.CreateShortcut($link.FullName)
            # Preserve target and arguments; update only icons for Koha shortcuts.
            $shortcut.IconLocation = $versionedIcon + ',0'
            $shortcut.Save()
            $updated++
        } catch {
            Write-Warning ('Atalho nao atualizado: ' + $link.FullName + ' | ' + $_.Exception.Message)
        }
    }
}
# Invalidate file-icon cache/association view without deleting Explorer cache.
try {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class KohaIconRefresh {
    [DllImport("shell32.dll")]
    public static extern void SHChangeNotify(uint wEventId, uint uFlags, IntPtr item1, IntPtr item2);
}
"@ -ErrorAction Stop
    [KohaIconRefresh]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
} catch { }
Write-Host ('Atalhos Koha com icone atualizado: ' + $updated) -ForegroundColor Green
'@
    [System.IO.File]::WriteAllText($iconFixScriptPath, $iconFixScriptContent, (New-Object System.Text.UTF8Encoding($true)))

    # --------------------------------------------------------
    # 2. PATCHS PONTUAIS DO FLUXO MSIX (SEM ALTERAR install.ps1)
    # --------------------------------------------------------
    $installModulePath = Join-Path $payloadWindowsDir 'KohaEasy.Install.psm1'
    if (-not (Test-Path -LiteralPath $installModulePath -PathType Leaf)) {
        throw "Modulo de instalacao nao encontrado: $installModulePath"
    }

    $installModuleText = [System.IO.File]::ReadAllText($installModulePath)
    $installModuleText = $installModuleText -replace "`r`n?", "`n"

    # SECURITY: replace the temporary hard-coded password function with the
    # interactive SecureString prompt already present in the source module.
    # The password remains in memory only; New-KohaLinuxUser sends it on stdin
    # and the module never persists it to state.json or logs.
    $accountFunctionStart = $installModuleText.IndexOf('function Read-KohaLinuxAccount {', [System.StringComparison]::Ordinal)
    $accountDisabledStart = $installModuleText.IndexOf('function Read-KohaLinuxAccount_Disabled {', [System.StringComparison]::Ordinal)
    $newLinuxUserStart = $installModuleText.IndexOf('function New-KohaLinuxUser {', [System.StringComparison]::Ordinal)
    if ($accountFunctionStart -lt 0 -or $accountDisabledStart -le $accountFunctionStart -or $newLinuxUserStart -le $accountDisabledStart) {
        throw 'Nao foi possivel localizar com seguranca as funcoes de credenciais Debian. Nada sera empacotado.'
    }
    $interactiveAccountFunction = $installModuleText.Substring($accountDisabledStart, $newLinuxUserStart - $accountDisabledStart)
    $interactiveAccountFunction = $interactiveAccountFunction.Replace(
        'function Read-KohaLinuxAccount_Disabled {',
        'function Read-KohaLinuxAccount {'
    )
    if ($interactiveAccountFunction -notmatch 'Read-Host\s+-AsSecureString' -or $interactiveAccountFunction -notmatch 'passwords do not match|password.*match|senhas nao coincidem|nao correspondem') {
        # The prompt is validated structurally below as well; do not silently fall back to a fixed password.
        if ($interactiveAccountFunction -notmatch 'Read-Host\s+-AsSecureString') {
            throw 'A rotina interativa de credenciais nao usa entrada protegida. Nada sera empacotado.'
        }
    }
    $installModuleText = $installModuleText.Substring(0, $accountFunctionStart) +
        $interactiveAccountFunction +
        $installModuleText.Substring($newLinuxUserStart)
    if ($installModuleText -match 'kohanexuspassword123') {
        throw 'Foi encontrada uma senha fixa embutida no modulo Debian. Nada sera empacotado.'
    }

    # The second terminal owns the interactive Linux panel. After the user exits
    # that panel, the same terminal runs a separate post-panel continuation for
    # Windows shortcuts/tasks/network. The first preparation terminal does not
    # wait for it and never checks Koha's database or koha-conf.xml.
    $panelWrapperPath = Join-Path $payloadWindowsDir 'KohaMsixPanel.ps1'
    $panelWrapperContent = @'
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
'@
    [System.IO.File]::WriteAllText($panelWrapperPath, $panelWrapperContent, (New-Object System.Text.UTF8Encoding($true)))

    # Replace only Invoke-KohaPanel, not its adjacent legacy function. It now
    # launches the wrapper in Windows Terminal, or a regular PowerShell window
    # if Windows Terminal is unavailable.
    $panelPattern = '(?ms)^function Invoke-KohaPanel\s*\{.*?^\}\s*(?=function Invoke-KohaPanel_Old\s*\{)'
    $panelMatches = [regex]::Matches($installModuleText, $panelPattern)
    if ($panelMatches.Count -ne 1) {
        throw "Esperava encontrar uma funcao Invoke-KohaPanel independente; encontrado: $($panelMatches.Count). Nada sera empacotado."
    }
    $panelFunctionReplacement = @'
# MSIX v17: all panel dependencies are prepared and verified in the FIRST
# (setup) terminal. Only then is the definitive terminal started at the
# language selection screen. Never install the Koha server in this stage.
function Initialize-KohaPanelDependencies {
    $dependencyScript = @(
        'set -eu'
        'missing=""'
        'for spec in whiptail:whiptail dialog:dialog curl:curl xmllint:libxml2-utils unzip:unzip gpg:gpg wget:wget fuser:psmisc ss:iproute2 flock:util-linux zstd:zstd; do'
        '  cmd="${spec%%:*}"'
        '  pkg="${spec#*:}"'
        '  if ! command -v "$cmd" >/dev/null 2>&1; then missing="$missing $pkg"; fi'
        'done'
        'if [ -n "$missing" ]; then'
        '  export DEBIAN_FRONTEND=noninteractive'
        '  apt-get update -qq'
        '  apt-get -o DPkg::Lock::Timeout=300 install -y -qq --no-install-recommends $missing'
        'fi'
        'for cmd in whiptail dialog curl xmllint unzip gpg wget fuser ss flock zstd; do'
        '  if ! command -v "$cmd" >/dev/null 2>&1; then echo "Missing dependency: $cmd"; exit 17; fi'
        'done'
        'echo KOHA_MSIX_PANEL_DEPS_READY'
    ) -join "`n"
    Write-KohaStep 'Preparando dependencias do painel no Debian (instalando as que faltam)...'
    $result = Invoke-KohaLinuxScript -Script $dependencyScript
    if ($result.ExitCode -ne 0 -or ([string]$result.Output) -notmatch 'KOHA_MSIX_PANEL_DEPS_READY') {
        Write-KohaLog ('Panel dependency preparation failed (exit {0}): {1}' -f $result.ExitCode, ([string]$result.Output).Trim()) 'install'
        throw ('Falha ao preparar as dependencias do painel no Debian. Saida: ' + ([string]$result.Output).Trim())
    }
    Write-KohaStep 'Dependencias do painel prontas. Abrindo a selecao de idioma no segundo terminal...' 'ok'
    return $true
}

function Invoke-KohaPanel {
    # Download and verify dependencies while this FIRST terminal is active.
    # The second terminal must start with the language selection, not with APT.
    if (-not (Initialize-KohaPanelDependencies)) {
        throw 'As dependencias do painel ainda nao estao prontas.'
    }
    $launcher = Join-Path (Get-KohaPath Bin) 'koha.nexus.exe'
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
        throw ('Koha launcher not found: ' + $launcher)
    }
    $previous = $env:KOHA_MSIX_PANEL_SETUP
    try {
        # Keep the proven v16 handoff. This opens a separate terminal with
        # the Linux panel and avoids starting a non-installed Koha service.
        $env:KOHA_MSIX_PANEL_SETUP = '1'
        $process = Start-Process -FilePath $launcher -ArgumentList 'Launch -Hidden' -WorkingDirectory (Get-KohaPath Bin) -PassThru -ErrorAction Stop
        if ($null -eq $process) { throw 'The definitive Koha launcher did not start.' }
    }
    finally {
        if ($null -eq $previous) {
            Remove-Item Env:KOHA_MSIX_PANEL_SETUP -ErrorAction SilentlyContinue
        } else {
            $env:KOHA_MSIX_PANEL_SETUP = $previous
        }
    }
    return 0
}
'@
    $panelMatch = $panelMatches[0]
    $installModuleText = $installModuleText.Substring(0, $panelMatch.Index) +
        $panelFunctionReplacement +
        $installModuleText.Substring($panelMatch.Index + $panelMatch.Length)

    # Patch only the Install-Koha function. Its initial invocation returns as
    # soon as the panel is launched. The panel wrapper later calls Install again
    # with KOHA_MSIX_FINALIZE=1 to execute only the Windows integration phase.
    $installFunctionStart = $installModuleText.IndexOf('function Install-Koha {', [System.StringComparison]::Ordinal)
    $installFunctionEnd = -1
    if ($installFunctionStart -ge 0) {
        $installFunctionEnd = $installModuleText.IndexOf('# Runs one step of the Windows side', $installFunctionStart, [System.StringComparison]::Ordinal)
    }
    if ($installFunctionStart -lt 0 -or $installFunctionEnd -lt 0) {
        throw 'Nao foi possivel delimitar com seguranca a funcao Install-Koha. O original sera preservado e o MSIX nao sera gerado.'
    }
    $installFunctionText = $installModuleText.Substring($installFunctionStart, $installFunctionEnd - $installFunctionStart)

    # O primeiro terminal pede usuario e senha quando a distro nao existe,
    # mesmo se um state.json de tentativa anterior registrar um usuario.
    $originalAccountCondition = "    if (`$null -eq `$account -and `$phase -ne 'done' -and -not [string]`$state['linuxUser'] -and -not `$NonInteractive) {"
    $newAccountCondition = "    if (`$null -eq `$account -and -not `$NonInteractive -and ((`$phase -ne 'done' -and -not [string]`$state['linuxUser']) -or `$env:KOHA_MSIX_FIRST_RUN -eq '1')) {"
    if ([regex]::Matches($installFunctionText, [regex]::Escape($originalAccountCondition)).Count -ne 1) {
        throw 'Nao foi encontrada a condicao esperada para pedir credenciais Debian.'
    }
    $installFunctionText = $installFunctionText.Replace($originalAccountCondition, $newAccountCondition)
    if ($installFunctionText -notmatch 'KOHA_MSIX_FIRST_RUN') {
        throw 'Alteracao do prompt de usuario/senha Debian falhou.'
    }

    $phaseLine = "    if (-not `$phase -or `$script:Phases -notcontains `$phase) { `$phase = 'checks' }"
    if ([regex]::Matches($installFunctionText, [regex]::Escape($phaseLine)).Count -ne 1) {
        throw 'Nao foi possivel localizar a inicializacao de fase de Install-Koha. Nada sera empacotado.'
    }
    $finalizerPreamble = @'
    if ($env:KOHA_MSIX_FINALIZE -eq '1') {
        # The Debian panel owns Koha/database setup. A silent gate only prevents
        # marking Windows setup complete when the user closes the panel early.
        if (-not (Test-KohaInstalledInDistro)) {
            Write-KohaLog 'MSIX post-panel continuation skipped: panel did not report complete Koha installation.' 'install'
            return 0
        }
        Set-KohaState @{ phase = 'windows' } | Out-Null
        $state = Get-KohaState
        $phase = 'windows'
        Write-KohaLog 'MSIX post-panel continuation: Koha ready; continuing with Windows integration.' 'install'
    }
'@
    $installFunctionText = $installFunctionText.Replace($phaseLine, $phaseLine + "`n" + $finalizerPreamble.TrimEnd("`r", "`n"))

    $kohaProbeCondition = "    if (Test-KohaPhaseDone 'koha' `$phase) {"
    if ([regex]::Matches($installFunctionText, [regex]::Escape($kohaProbeCondition)).Count -ne 1) {
        throw 'Nao foi possivel localizar a verificacao de fase koha para o caminho de finalizacao. Nada sera empacotado.'
    }
    $installFunctionText = $installFunctionText.Replace(
        $kohaProbeCondition,
        "    if ((Test-KohaPhaseDone 'koha' `$phase) -and `$env:KOHA_MSIX_FINALIZE -ne '1') {"
    )

    # After launching the second terminal, return immediately. The wrapper
    # itself will run Install-Koha again only after the panel closes.
    $panelCallPattern = '(?m)^[ \t]*Invoke-KohaPanel\s+\|\s+Out-Null[ \t]*$'
    $panelCallMatches = [regex]::Matches($installFunctionText, $panelCallPattern)
    if ($panelCallMatches.Count -ne 1) {
        throw "Esperava uma unica chamada a Invoke-KohaPanel dentro de Install-Koha; encontrado: $($panelCallMatches.Count). Nada sera empacotado."
    }
    $panelCall = $panelCallMatches[0]
    $panelCallLineEnd = $installFunctionText.IndexOf("`n", $panelCall.Index + $panelCall.Length)
    if ($panelCallLineEnd -lt 0) { throw 'A chamada a Invoke-KohaPanel nao termina numa linha completa.' }
    $installedMarker = "Write-KohaStep (T 'Koha is installed.') 'ok'"
    $installedMarkerMatches = [regex]::Matches($installFunctionText, [regex]::Escape($installedMarker))
    if ($installedMarkerMatches.Count -ne 1) {
        throw "Esperava um marcador estavel apos a chamada do painel; encontrados: $($installedMarkerMatches.Count). Nada sera empacotado."
    }
    $installedMarkerIndex = $installFunctionText.IndexOf($installedMarker, $panelCallLineEnd + 1, [System.StringComparison]::Ordinal)
    if ($installedMarkerIndex -lt 0) { throw 'O marcador apos o painel esta antes da chamada ao painel.' }
    $installedLineStart = $installFunctionText.LastIndexOf("`n", $installedMarkerIndex) + 1
    $postPanelLogicStart = $panelCallLineEnd + 1
    $replacement = @'
            # MSIX: panel runs independently. The first terminal only prepares Windows/WSL/Debian.
            # The panel wrapper runs the deferred Windows integration phase after the user exits.
            return 0
        }
'@
    $installFunctionText = $installFunctionText.Substring(0, $postPanelLogicStart) +
        $replacement.TrimEnd("`r", "`n") + "`n" +
        $installFunctionText.Substring($installedLineStart)

    $patchedModuleText = $installModuleText.Substring(0, $installFunctionStart) +
        $installFunctionText +
        $installModuleText.Substring($installFunctionEnd)
    [System.IO.File]::WriteAllText($installModulePath, $patchedModuleText, (New-Object System.Text.UTF8Encoding($true)))

    # Patch local and narrow: when the launcher was invoked by the FIRST-RUN
    # handoff, open the SECOND terminal at the panel's language selection.
    # For normal desktop/tray launches, keep the original Launch behavior.
    $mainWindowsPath = Join-Path $payloadWindowsDir 'KohaEasy.ps1'
    $mainWindowsText = [System.IO.File]::ReadAllText($mainWindowsPath)
    $launchAnchor = @'
    'Launch' {
        if (-not (Test-KohaDistroInstalled)) { Show-Box (Get-KohaStateText 'not_installed') 'OK' 'Warning' | Out-Null; break }
        Invoke-KohaLaunch | Out-Null
        Open-KohaPanel
'@
    # Normaliza CRLF/LF no arquivo COPIADO para a busca nao falhar por quebras de linha.
    $mainWindowsText = $mainWindowsText.Replace("`r`n", "`n")
    if ($mainWindowsText.IndexOf($launchAnchor, [System.StringComparison]::Ordinal) -lt 0) {
        throw 'Nao encontrei o comando Launch original para aplicar o desvio de primeira instalacao com seguranca.'
    }
    $firstLaunchBranch = @'
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
'@
    $mainWindowsText = $mainWindowsText.Replace($launchAnchor, $firstLaunchBranch)
    [System.IO.File]::WriteAllText($mainWindowsPath, $mainWindowsText, (New-Object System.Text.UTF8Encoding($true)))
    if ($mainWindowsText -notmatch 'KOHA_MSIX_PANEL_SETUP' -or $installModuleText -notmatch 'Launch -Hidden') { throw 'A transicao entre os dois terminais nao foi aplicada corretamente.' }
    if ($patchedModuleText -notmatch 'function Initialize-KohaPanelDependencies' -or $patchedModuleText -notmatch 'KOHA_MSIX_PANEL_DEPS_READY' -or $patchedModuleText -notmatch 'if \(-not \(Initialize-KohaPanelDependencies\)\)') { throw 'Falha ao inserir a barreira de dependencias antes do segundo terminal.' }

    # Manter windows\install.ps1 original. O bootstrap define KOHAEASY_NO_WT=1
    # somente durante a preparacao inicial, impedindo uma janela extra para Install.
    # Invoke-KohaPanel continua abrindo separadamente o terminal do painel.
    $windowsInstallerPath = Join-Path $payloadWindowsDir 'install.ps1'
    if (-not (Test-Path -LiteralPath $windowsInstallerPath -PathType Leaf)) {
        throw "Instalador Windows nao encontrado: $windowsInstallerPath"
    }

    # Validar sintaxe do modulo e do instalador depois das alteracoes pontuais.
    # Preflight: conferir que o MSIX tera o prompt protegido e a porta correta.
    $verifyModule = [System.IO.File]::ReadAllText($installModulePath)
    if ($verifyModule -notmatch 'KOHA_MSIX_FIRST_RUN' -or
        $verifyModule -notmatch 'Read-Host\s+-AsSecureString') {
        throw 'O pacote nao contem o prompt protegido de usuario e senha Debian.'
    }
    $verifyCore = [System.IO.File]::ReadAllText($coreModulePath)
    if ($verifyCore -notmatch "StaffUrl\s*=\s*'http://localhost:8080/'" -or
        $verifyCore -notmatch 'WebPorts\s*=\s*@\(80, 8080\)') {
        throw 'A configuracao Windows do staff nao usa exclusivamente a porta 8080.'
    }

    foreach ($scriptToParse in @($installModulePath, $windowsInstallerPath, $mainWindowsPath, $panelWrapperPath, $iconFixScriptPath)) {
        $patchTokens = $null
        $patchErrors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile(
            $scriptToParse,
            [ref]$patchTokens,
            [ref]$patchErrors
        )
        if ($patchErrors -and $patchErrors.Count -gt 0) {
            $details = ($patchErrors | ForEach-Object {
                'Linha {0}, coluna {1}: {2}' -f $_.Extent.StartLineNumber, $_.Extent.StartColumnNumber, $_.Message
            }) -join [Environment]::NewLine
            throw "Erro de sintaxe no arquivo corrigido ${scriptToParse}:`r`n$details"
        }
    }

    # Usa o ícone enviado também nos atalhos criados pelo instalador Windows.
    # A bandeja e o executavel legado devem continuar usando o koha.ico ORIGINAL.
    # O icone personalizado fica em arquivo separado, apenas para os atalhos e o MSIX.
    $originalTrayIcon = Join-Path $windowsDir 'koha.ico'
    $packagedTrayIcon = Join-Path $payloadWindowsDir 'koha.ico'
    if (-not (Test-Path -LiteralPath $originalTrayIcon -PathType Leaf)) { throw 'Icone original da bandeja nao encontrado.' }
    if ((Get-FileHash -LiteralPath $originalTrayIcon -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $packagedTrayIcon -Algorithm SHA256).Hash) {
        throw 'O icone da bandeja mudou durante a preparacao do MSIX.'
    }
    Copy-Item -LiteralPath $iconPath -Destination (Join-Path $payloadWindowsDir 'KohaNexusDesktop.ico') -Force

    foreach ($langItem in (Get-ChildItem -LiteralPath $langDir -Force)) {
        if ($langItem.Name -in @('.git', '__pycache__', '$Recycle.Bin', 'System Volume Information')) { continue }
        if (($langItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
        Copy-Item -LiteralPath $langItem.FullName -Destination $payloadLangDir -Recurse -Force
    }

    Copy-Item -LiteralPath $installer -Destination $payloadDir -Force
    Copy-Item -LiteralPath $installerHash -Destination $payloadDir -Force
    Copy-Item -LiteralPath $panelDir -Destination $payloadDir -Recurse -Force

    # Entry point do MSIX chama este bootstrap, não "KohaEasy.ps1 Launch".
    # O comando Launch mostra corretamente "Koha is not installed" fora do
    # contexto de instalação; aqui primeiro executamos o bootstrap oficial.
    $bootstrapPath = Join-Path $pkgDir 'Bootstrap-MSIX.ps1'
    $bootstrapContent = @'
$ErrorActionPreference = 'Stop'
$payloadVersion = '__PAYLOAD_VERSION__'
$msixDir = $PSScriptRoot
$sourceDir = Join-Path $msixDir 'Payload'
$installScript = Join-Path $sourceDir 'windows\install.ps1'
$kohaRoot = 'C:\Koha'
$kohaBin = Join-Path $kohaRoot 'bin'
$mainScript = Join-Path $kohaBin 'KohaEasy.ps1'
$markerPath = Join-Path $kohaBin '.koha-msix-payload-version'
$logDir = Join-Path $kohaRoot 'logs'

# UTF-8 no console de fallback (PowerShell clássico). Se o Windows Terminal
# estiver disponível, os fluxos do Koha usam o perfil Unicode do próprio projeto.
try {
    $utf8Console = New-Object System.Text.UTF8Encoding($false)
    $chcpExe = Join-Path $env:SystemRoot 'System32\chcp.com'
    if (Test-Path -LiteralPath $chcpExe -PathType Leaf) { & $chcpExe 65001 | Out-Null }
    [Console]::InputEncoding = $utf8Console
    [Console]::OutputEncoding = $utf8Console
    $global:OutputEncoding = $utf8Console
} catch { }
# Nunca force o fallback em cmd.exe: permita que Get-KohaTerminalPath use wt.exe.
Remove-Item Env:KOHAEASY_NO_WT -ErrorAction SilentlyContinue

function Test-BootstrapAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal -ArgumentList $identity
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-BootstrapDistroNames {
    $wslExe = Join-Path $env:SystemRoot 'System32\wsl.exe'
    if (-not (Test-Path -LiteralPath $wslExe -PathType Leaf)) { return @() }

    $lines = @(& $wslExe --list --quiet 2>$null)
    $wslExitCode = $LASTEXITCODE
    if ($wslExitCode -ne 0) { return @() }

    $names = foreach ($line in $lines) {
        $clean = ([string]$line -replace '\x00', '').Trim()
        $clean = ($clean -replace '^\*\s*', '').Trim()
        if ($clean) { $clean }
    }
    return @($names)
}

function Write-BootstrapLog {
    param([string]$Message)
    try {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        Add-Content -LiteralPath (Join-Path $logDir 'msix-bootstrap.log') -Encoding UTF8 -Value ('{0} | {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message)
    } catch { }
}

function Get-BootstrapMessages {
    # Suporta somente Portugues e Ingles nesta tela inicial.
    # pt-PT tambem usa os textos em portugues brasileiro. Outros idiomas usam Ingles.
    $cultureName = [System.Globalization.CultureInfo]::CurrentUICulture.Name
    try {
        $uiOverride = Get-WinUILanguageOverride -ErrorAction Stop
        if ($uiOverride -and $uiOverride.Name) {
            $cultureName = [string]$uiOverride.Name
        }
    } catch { }

    $language = (($cultureName -split '[-_]')[0]).ToLowerInvariant()
    if ($language -eq 'pt') {
        return @{
            Language = 'pt'
            VirtualizationTitle = 'Virtualização necessária'
            VirtualizationBody = "O Koha.Nexus precisa da virtualização de hardware para instalar e executar o Koha no WSL 2, mas o Windows indica que ela pode estar desativada na BIOS/UEFI.`r`n`r`nComo habilitar:`r`n1. Entre nas configurações da BIOS/UEFI.`r`n2. Procure por Intel Virtualization Technology ou VT-x (Intel), ou SVM Mode ou AMD-V (AMD). O nome varia conforme o fabricante.`r`n3. Ative a opção e salve as alterações (geralmente F10). Não altere outras opções."
            VirtualizationPrompt = 'Deseja reiniciar agora e abrir a BIOS/UEFI? Salve seus arquivos antes de continuar.'
            BiosQuestionTitle = 'Abrir BIOS/UEFI'
            BiosFailure = "Não foi possível abrir a BIOS/UEFI automaticamente. O computador pode não oferecer suporte a essa reinicialização, ou a solicitação de administrador pode ter sido cancelada.`r`n`r`nTente manualmente: Configurações > Sistema > Recuperação > Inicialização avançada > Reiniciar agora > Solução de problemas > Opções avançadas > Configurações de Firmware UEFI. Alguns computadores não oferecem essa opção.`r`n`r`nAtive a virtualizacao e execute o Koha.Nexus novamente."
            GenericErrorPrefix = 'Não foi possível iniciar o Koha.Nexus.'
        }
    }

    return @{
        Language = 'en'
        VirtualizationTitle = 'Virtualization is required'
        VirtualizationBody = "Koha.Nexus needs hardware virtualization to install and run Koha in WSL 2, but Windows indicates it may be disabled in BIOS/UEFI.`r`n`r`nHow to enable it:`r`n1. Open your computer's BIOS/UEFI settings.`r`n2. Look for Intel Virtualization Technology or VT-x (Intel), or SVM Mode or AMD-V (AMD). The name varies by manufacturer.`r`n3. Enable the option and save changes (usually F10). Do not change other settings."
        VirtualizationPrompt = 'Would you like to restart now and open BIOS/UEFI? Save your work before continuing.'
        BiosQuestionTitle = 'Open BIOS/UEFI'
        BiosFailure = "Windows could not open BIOS/UEFI automatically, or the administrator request was cancelled.`r`n`r`nTry manually: Settings > System > Recovery > Advanced startup > Restart now > Troubleshoot > Advanced options > UEFI Firmware Settings. Some computers do not offer this option.`r`n`r`nEnable virtualization, then launch Koha.Nexus again."
        GenericErrorPrefix = 'Koha.Nexus could not be started.'
    }
}
function Show-BootstrapMessage {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Title,
        [ValidateSet('OK', 'YesNo')][string]$Buttons = 'OK',
        [ValidateSet('Information', 'Warning', 'Question', 'Error')][string]$Icon = 'Information'
    )
    Add-Type -AssemblyName System.Windows.Forms
    $buttonEnum = [System.Enum]::Parse([System.Windows.Forms.MessageBoxButtons], $Buttons)
    $iconEnum = [System.Enum]::Parse([System.Windows.Forms.MessageBoxIcon], $Icon)
    return [System.Windows.Forms.MessageBox]::Show($Text, $Title, $buttonEnum, $iconEnum)
}

function Get-BootstrapVirtualizationState {
    # $true: Windows reports an active hypervisor or firmware virtualization.
    # $false: all readable processor entries explicitly report firmware off.
    # $null: state could not be determined; do not block based on uncertain data.
    try {
        $computer = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
        $hypervisorProperty = $computer.PSObject.Properties['HypervisorPresent']
        if ($hypervisorProperty -and $hypervisorProperty.Value -eq $true) { return $true }

        $processors = @(Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop)
        if ($processors.Count -eq 0) { return $null }

        $values = @()
        foreach ($processor in $processors) {
            $property = $processor.PSObject.Properties['VirtualizationFirmwareEnabled']
            if ($property -and $null -ne $property.Value) {
                $values += [bool]$property.Value
            }
        }

        if ($values.Count -eq 0) { return $null }
        if ($values -contains $true) { return $true }
        if (@($values | Where-Object { $_ -eq $false }).Count -eq $values.Count) { return $false }
        return $null
    } catch {
        Write-BootstrapLog ('Não foi possível consultar o estado da virtualização: ' + $_.Exception.Message)
        return $null
    }
}

$ui = Get-BootstrapMessages
Write-BootstrapLog ('START | packageDir={0}; sourceDir={1}; version={2}; user={3}; admin={4}' -f $msixDir, $sourceDir, $payloadVersion, [Security.Principal.WindowsIdentity]::GetCurrent().Name, (Test-BootstrapAdministrator))

try {
    if (-not (Test-Path -LiteralPath $installScript -PathType Leaf)) {
        throw "Instalador do payload não encontrado: $installScript"
    }

    $distroNames = @(Get-BootstrapDistroNames)
    $distroInstalled = $distroNames -contains 'koha'
    Write-BootstrapLog ('WSL distributions: {0}; kohaInstalled={1}' -f ($distroNames -join ', '), $distroInstalled)

    $installedPayloadVersion = ''
    if (Test-Path -LiteralPath $markerPath -PathType Leaf) {
        $installedPayloadVersion = [string](Get-Content -LiteralPath $markerPath -Raw -ErrorAction SilentlyContinue)
        $installedPayloadVersion = $installedPayloadVersion.Trim()
    }
    $payloadNeedsUpdate = (-not (Test-Path -LiteralPath $mainScript -PathType Leaf)) -or ($installedPayloadVersion -ne $payloadVersion)

    # Verifique a virtualização antes de instalar ou abrir o painel.
    # Quando a leitura é inconclusiva, não bloqueie por um possível falso positivo.
    $virtualizationState = Get-BootstrapVirtualizationState
    if ($virtualizationState -is [bool] -and -not $virtualizationState) {
        $null = Show-BootstrapMessage `
            -Text $ui.VirtualizationBody `
            -Title $ui.VirtualizationTitle `
            -Buttons 'OK' `
            -Icon 'Warning' 

        $answer = Show-BootstrapMessage `
            -Text $ui.VirtualizationPrompt `
            -Title $ui.BiosQuestionTitle `
            -Buttons 'YesNo' `
            -Icon 'Question' 

        if ($answer -eq [System.Windows.Forms.DialogResult]::Yes) {
            try {
                $shutdownExe = Join-Path $env:SystemRoot 'System32\shutdown.exe'
                if (-not (Test-Path -LiteralPath $shutdownExe -PathType Leaf)) {
                    throw 'shutdown.exe não foi encontrado.'
                }

                if (Test-BootstrapAdministrator) {
                    $firmwareProcess = Start-Process -FilePath $shutdownExe -ArgumentList '/r /fw /t 0' -PassThru -Wait -ErrorAction Stop
                }
                else {
                    $firmwareProcess = Start-Process -FilePath $shutdownExe -ArgumentList '/r /fw /t 0' -Verb RunAs -PassThru -Wait -ErrorAction Stop
                }

                if ($firmwareProcess.ExitCode -ne 0) {
                    throw "shutdown.exe retornou código $($firmwareProcess.ExitCode)."
                }
                Write-BootstrapLog 'Usuário solicitou reinicialização para BIOS/UEFI.'
            }
            catch {
                Write-BootstrapLog ('Falha ao abrir BIOS/UEFI: ' + $_.Exception.Message)
                $null = Show-BootstrapMessage `
                    -Text $ui.BiosFailure `
                    -Title $ui.BiosQuestionTitle `
                    -Buttons 'OK' `
                    -Icon 'Error' 
            }
        }

        # Não continuar com a instalação até a pessoa habilitar a virtualização.
        exit 0
    }

    # A primeira implantação e a atualização da carga precisam de elevação.
    # A abertura normal, quando a carga já está atualizada, não pede UAC.
    if (($payloadNeedsUpdate -or -not $distroInstalled) -and -not (Test-BootstrapAdministrator)) {
        $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $PSCommandPath
        Write-BootstrapLog 'Elevation required; opening the elevated bootstrap window.'
        Start-Process -FilePath $powershell -ArgumentList $arguments -Verb RunAs -WindowStyle Normal | Out-Null
        exit 0
    }

    if ($payloadNeedsUpdate -or -not $distroInstalled) {
        # Usa o bootstrap oficial do repositório para copiar windows, lang,
        # panel e o instalador para C:\Koha\bin, validar SHA-256 e executar Install.
        $env:KOHAEASY_SOURCE = $sourceDir
        $env:KOHAEASY_ROOT = $kohaRoot
        # Sinal de instalacao nova para solicitar credenciais no PRIMEIRO terminal.
        if (-not $distroInstalled) {
            $env:KOHA_MSIX_FIRST_RUN = '1'
            Write-BootstrapLog 'Debian is absent: interactive Linux account prompt enabled.'
            Write-Host 'Neste terminal sera solicitado o usuario e a senha do Debian.' -ForegroundColor Cyan
        } else {
            Remove-Item Env:KOHA_MSIX_FIRST_RUN -ErrorAction SilentlyContinue
        }
        # MANTER a preparacao inicial nesta janela: impede windows\install.ps1
        # de abrir um terminal extra para executar o fluxo completo Install.
        # A chamada Invoke-KohaPanel dentro de Install-Koha continua abrindo o
        # segundo terminal independente, que contem o painel e instala o Koha.
        $env:KOHAEASY_NO_WT = '1'

        $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $installScript
        Write-BootstrapLog ('Starting install.ps1 in visible bootstrap console; script={0}; source={1}' -f $installScript, $sourceDir)
        Write-Host ''
        Write-Host 'Koha.Nexus: preparando a instalação do Koha no WSL 2...' -ForegroundColor Cyan
        Write-Host ('Registros de diagnóstico: {0}' -f (Join-Path $logDir 'msix-bootstrap.log')) -ForegroundColor Gray
        $installProcess = Start-Process -FilePath $powershell -ArgumentList $arguments -WorkingDirectory $sourceDir -NoNewWindow -PassThru -Wait
        Write-BootstrapLog ('install.ps1 returned exit code {0}' -f $installProcess.ExitCode)
        if ($installProcess.ExitCode -eq 3) {
            Write-BootstrapLog 'O instalador pediu reinicializacao do Windows; o marcador do payload nao sera atualizado.'
            if ($ui.Language -eq 'pt') {
                $restartText = 'O Windows precisa ser reiniciado para concluir a configuracao do WSL. Salve seus arquivos e reinicie o computador. O instalador continuara quando voce entrar novamente.'
                $restartTitle = 'Reinicializacao necessaria'
            } else {
                $restartText = 'Windows must restart to finish configuring WSL. Save your work and restart the computer. Setup will continue when you sign in again.'
                $restartTitle = 'Restart required'
            }
            $null = Show-BootstrapMessage -Text $restartText -Title $restartTitle -Buttons 'OK' -Icon 'Information'
            exit 0
        }
        if ($installProcess.ExitCode -ne 0) {
            throw "windows\install.ps1 terminou com codigo $($installProcess.ExitCode). Consulte $logDir\msix-bootstrap.log e C:\Koha\logs."
        }

        if (-not (Test-Path -LiteralPath $mainScript -PathType Leaf)) {
            throw "O bootstrap terminou, mas KohaEasy.ps1 não foi copiado para $kohaBin."
        }

        # Nao consultar koha-conf.xml, credenciais ou estado do banco aqui.
        # O instalador espera o painel terminar; o proprio painel informa se a
        # instalacao do servidor ou do banco precisa ser continuada.
        Write-BootstrapLog 'windows\install.ps1 completed; skipping the duplicate Koha/database post-check.'
        $iconFixer = Join-Path $kohaBin 'KohaMsixRefreshIcons.ps1'
        if (Test-Path -LiteralPath $iconFixer -PathType Leaf) {
            try {
                & $iconFixer
                Write-BootstrapLog 'Updated Koha desktop and Start menu shortcut icons.'
            } catch {
                Write-BootstrapLog ('Icon refresh warning: ' + $_.Exception.Message)
                Write-Warning ('Nao foi possivel atualizar alguns icones: ' + $_.Exception.Message)
            }
        }


        [System.IO.File]::WriteAllText(
            $markerPath,
            $payloadVersion,
            (New-Object System.Text.UTF8Encoding($false))
        )
        Write-BootstrapLog "Payload $payloadVersion instalado em $kohaBin"
        Write-BootstrapLog 'First-run setup terminal completed. The control panel owns Koha and database validation.'
        if ($ui.Language -eq 'pt') {
            Write-Host ''
            Write-Host 'A preparação do Windows terminou. A instalação do servidor e do banco de dados é conduzida pelo painel.' -ForegroundColor Green
            Write-Host 'Esta janela será fechada automaticamente.' -ForegroundColor Gray
        } else {
            Write-Host ''
            Write-Host 'Windows preparation is complete. The control panel manages Koha server and database installation.' -ForegroundColor Green
            Write-Host 'This window will close automatically.' -ForegroundColor Gray
        }
        # The installation ran in this PowerShell session and has completed.
        # Close this bootstrap terminal now; do not reopen a second panel.
        exit 0
    }

    # Remover a flag que forçava Get-KohaTerminalPath a cair no cmd.exe.
    Remove-Item Env:KOHAEASY_NO_WT -ErrorAction SilentlyContinue
    $env:KOHAEASY_ROOT = $kohaRoot
    Write-BootstrapLog "Abrindo o painel; distribuição 'koha' detectada. MainScript=$mainScript"
    & $mainScript Panel
    Write-BootstrapLog ('O comando Panel terminou; LASTEXITCODE={0}' -f $LASTEXITCODE)
}
catch {
    $message = $_.Exception.Message
    Write-BootstrapLog ('ERRO: ' + $message)
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show(
            "$($ui.GenericErrorPrefix)`r`n`r`n$message`r`n`r`nLog: $logDir\msix-bootstrap.log",
            'Koha.Nexus',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        )
    } catch { }
    exit 1
}
'@
    $bootstrapContent = $bootstrapContent.Replace('__PAYLOAD_VERSION__', $payloadRevision)
    # Saneamento extra para PowerShell 5.1: elimina todas as aspas tipograficas
    # (incluindo aspas simples curvas e aspas baixas alemas) do bootstrap gerado.
    # A tela inicial usa somente Portugues e Ingles para reduzir pontos de falha.
    $safeApostrophe = [string][char]39
    $bootstrapContent = [regex]::Replace($bootstrapContent, '[\u2018-\u201F\u00AB\u00BB]', $safeApostrophe)
    [System.IO.File]::WriteAllText($bootstrapPath, $bootstrapContent, (New-Object System.Text.UTF8Encoding($true)))

    # Validar a sintaxe do script gerado ANTES de empacotar. Isso impede que um
    # erro de parser seja entregue dentro do MSIX e feche o aplicativo ao abrir.
    $parseTokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $bootstrapPath,
        [ref]$parseTokens,
        [ref]$parseErrors
    )
    if ($parseErrors -and $parseErrors.Count -gt 0) {
        $parseDetails = ($parseErrors | ForEach-Object {
            'Linha {0}, coluna {1}: {2}' -f $_.Extent.StartLineNumber, $_.Extent.StartColumnNumber, $_.Message
        }) -join [Environment]::NewLine
        throw "O Bootstrap-MSIX.ps1 gerado tem erros de sintaxe e nao sera empacotado:`r`n$parseDetails"
    }

    $generatedBootstrapText = [System.IO.File]::ReadAllText($bootstrapPath)
    if ([regex]::IsMatch($generatedBootstrapText, '[\u2018-\u201F\u00AB\u00BB]')) {
        throw 'O Bootstrap-MSIX.ps1 contem aspas tipograficas nao permitidas.'
    }

    # --------------------------------------------------------
    # 3. CRIAR LOGOS PNG EXIGIDOS PELO MANIFESTO
    # --------------------------------------------------------

    Write-Host "`n[2/8] Gerando os logotipos PNG..." -ForegroundColor Yellow
    Add-Type -AssemblyName System.Drawing
    $assetsDir = Join-Path $pkgDir 'Assets'
    New-Item -ItemType Directory -Path $assetsDir -Force | Out-Null
    # Ícone do aplicativo: ICO personalizado. Logo de marca: PNG personalizado.
    New-LogoFromImagePng -SourceImage $logoImagePath -Destination (Join-Path $assetsDir 'StoreLogo.png') -Size 50
    New-LogoPng -SourceIcon $iconPath -Destination (Join-Path $assetsDir 'Square44x44Logo.png') -Size 44
    New-LogoPng -SourceIcon $iconPath -Destination (Join-Path $assetsDir 'Square44x44Logo.targetsize-256.png') -Size 256
    New-LogoPng -SourceIcon $iconPath -Destination (Join-Path $assetsDir 'Square44x44Logo.scale-200.png') -Size 88
    New-LogoPng -SourceIcon $iconPath -Destination (Join-Path $assetsDir 'Square150x150Logo.png') -Size 150
    New-LogoPng -SourceIcon $iconPath -Destination (Join-Path $assetsDir 'Square150x150Logo.scale-200.png') -Size 300

    # --------------------------------------------------------
    # 4. COMPILAR O PONTO DE ENTRADA MSIX SEM JANELA DE CONSOLE
    # --------------------------------------------------------

    Write-Host "`n[3/8] Compilando o launcher MSIX..." -ForegroundColor Yellow

    $entrySource = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

internal static class KohaMsixEntry
{
    private const string PayloadVersion = "__PAYLOAD_VERSION__";

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBox(IntPtr hWnd, string text, string caption, uint type);

    private static void ShowError(string text)
    {
        try { MessageBox(IntPtr.Zero, text, "Koha.Nexus", 0x10); } catch { }
    }

    private static bool HasKohaDistro()
    {
        string wsl = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "wsl.exe");
        if (!File.Exists(wsl)) return false;

        try
        {
            ProcessStartInfo check = new ProcessStartInfo();
            check.FileName = wsl;
            check.Arguments = "--list --quiet";
            check.UseShellExecute = false;
            check.CreateNoWindow = true;
            check.RedirectStandardOutput = true;

            using (Process process = Process.Start(check))
            {
                if (process == null) return false;
                if (!process.WaitForExit(10000))
                {
                    try { process.Kill(); } catch { }
                    try { process.WaitForExit(); } catch { }
                    return false;
                }
                string output = process.StandardOutput.ReadToEnd();
                if (process.ExitCode != 0) return false;

                output = output.Replace("\0", "");
                string[] lines = output.Split(new char[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
                foreach (string line in lines)
                {
                    string name = line.Trim().TrimStart('*').Trim();
                    if (String.Equals(name, "koha", StringComparison.OrdinalIgnoreCase)) return true;
                }
            }
        }
        catch { }
        return false;
    }

    private static bool NeedsVisibleSetup()
    {
        string bin = @"C:\Koha\bin";
        string mainScript = Path.Combine(bin, "KohaEasy.ps1");
        string marker = Path.Combine(bin, ".koha-msix-payload-version");

        try
        {
            if (!File.Exists(mainScript) || !File.Exists(marker)) return true;
            string installedVersion = File.ReadAllText(marker).Trim();
            if (!String.Equals(installedVersion, PayloadVersion, StringComparison.Ordinal)) return true;
            return !HasKohaDistro();
        }
        catch { return true; }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string packageDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string bootstrap = Path.Combine(packageDir, "Bootstrap-MSIX.ps1");
        if (!File.Exists(bootstrap))
        {
            ShowError("O arquivo de inicialização não foi encontrado dentro do pacote MSIX:\r\n" + bootstrap);
            return 2;
        }

        string systemDir = Environment.GetFolderPath(Environment.SpecialFolder.System);
        string powershell = Path.Combine(systemDir, @"WindowsPowerShell\v1.0\powershell.exe");
        if (!File.Exists(powershell))
        {
            ShowError("O Windows PowerShell 5.1 não foi encontrado:\r\n" + powershell);
            return 3;
        }

        // Primeira instalação, payload desatualizado ou distribuição WSL ausente:
        // mostrar o terminal para que o progresso e eventuais erros não fiquem ocultos.
        // Quando já está tudo instalado, manter a inicialização silenciosa do painel.
        bool visibleSetup = NeedsVisibleSetup();

        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = powershell;
        psi.Arguments = "-NoProfile -ExecutionPolicy Bypass " +
            (visibleSetup ? "" : "-WindowStyle Hidden ") +
            "-File \"" + bootstrap + "\"";
        psi.WorkingDirectory = packageDir;
        psi.UseShellExecute = false;
        psi.CreateNoWindow = !visibleSetup;
        psi.WindowStyle = visibleSetup ? ProcessWindowStyle.Normal : ProcessWindowStyle.Hidden;

        try
        {
            using (Process child = Process.Start(psi))
            {
                if (child == null)
                {
                    ShowError("O Windows não conseguiu iniciar o processo de inicialização do Koha.Nexus.");
                    return 4;
                }
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch (Exception ex)
        {
            ShowError("Não foi possível iniciar o Koha.Nexus.\r\n\r\n" + ex.Message +
                "\r\n\r\nTente executar novamente. Se o problema continuar, consulte C:\\Koha\\logs\\msix-bootstrap.log.");
            return 1;
        }
    }
}
'@

    $entrySource = $entrySource.Replace('__PAYLOAD_VERSION__', $payloadRevision)
    $entrySourcePath = Join-Path $distDir 'KohaMsixEntry.cs'
    $entryExePath = Join-Path $pkgDir $entryExeName
    [System.IO.File]::WriteAllText($entrySourcePath, $entrySource, (New-Object System.Text.UTF8Encoding($false)))

    & $csc /nologo /target:winexe /platform:anycpu "/out:$entryExePath" "/win32icon:$iconPath" $entrySourcePath
    if ($LASTEXITCODE -ne 0) {
        throw "csc.exe falhou ao compilar o launcher (código $LASTEXITCODE)."
    }
    if (-not (Test-Path -LiteralPath $entryExePath -PathType Leaf)) {
        throw 'O compilador terminou sem gerar KohaMsixEntry.exe.'
    }

    # --------------------------------------------------------
    # 5. GERAR UM APPXMANIFEST.XML COMPLETO E VÁLIDO
    # --------------------------------------------------------

    Write-Host "`n[4/8] Gerando o AppxManifest.xml..." -ForegroundColor Yellow

    $manifestContent = @"
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap rescap">
  <Identity Name="$packageName" Publisher="$([Security.SecurityElement]::Escape($packagePublisher))" Version="$targetVersion" ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>Koha.Nexus</DisplayName>
    <PublisherDisplayName>$([Security.SecurityElement]::Escape($publisherDisplayName))</PublisherDisplayName>
    <Logo>Assets\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Resources>
    <Resource Language="pt-BR" />
  </Resources>
  <Applications>
    <Application Id="$applicationId" Executable="$entryExeName" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="Koha.Nexus"
                          Description="Koha.Nexus para Windows"
                          BackgroundColor="transparent"
                          Square150x150Logo="Assets\Square150x150Logo.png"
                          Square44x44Logo="Assets\Square44x44Logo.png" />
    </Application>
  </Applications>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
"@

    $manifestPath = Join-Path $pkgDir 'AppxManifest.xml'
    [System.IO.File]::WriteAllText($manifestPath, $manifestContent.TrimStart(), (New-Object System.Text.UTF8Encoding($false)))

    # XML sintaticamente bem-formado antes de invocar o MakeAppx.
    $manifestDocument = New-Object System.Xml.XmlDocument
    $manifestDocument.Load($manifestPath)
    $identityNode = $manifestDocument.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Identity']")
    $appNode = $manifestDocument.SelectSingleNode("/*[local-name()='Package']/*[local-name()='Applications']/*[local-name()='Application']")
    if (-not $identityNode -or -not $appNode) {
        throw 'O manifesto gerado não contém Identity ou Application na estrutura esperada.'
    }
    if ($identityNode.GetAttribute('Publisher') -ne $packagePublisher) {
        throw 'O Publisher do manifesto não corresponde ao Subject do certificado.'
    }
    if ($identityNode.GetAttribute('Version') -ne $targetVersion) {
        throw 'A versão gravada no manifesto está incorreta.'
    }

    # Confirma que a carga mínima está na raiz do pacote.
    foreach ($requiredInPackage in @(
        'AppxManifest.xml', 'Bootstrap-MSIX.ps1', $entryExeName,
        'Payload\windows\install.ps1', 'Payload\windows\KohaEasy.ps1',
        'Payload\windows\KohaEasy.Core.psm1', 'Payload\windows\KohaEasy.Lang.psm1', 'Payload\windows\KohaMsixPanel.ps1', 'Payload\windows\KohaMsixRefreshIcons.ps1', 'Payload\windows\KohaNexusDesktop.ico',
        'Payload\installer', 'Payload\installer.sha256', 'Payload\lang\pt.cache',
        'Payload\panel'
    )) {
        $path = Join-Path $pkgDir $requiredInPackage
        if (-not (Test-Path -LiteralPath $path)) {
            throw "Arquivo obrigatório não foi empacotado: $path"
        }
    }

    # --------------------------------------------------------
    # 6. EMPACOTAR E VALIDAR O MSIX
    # --------------------------------------------------------

    Write-Host "`n[5/8] Empacotando e validando o MSIX..." -ForegroundColor Yellow

    if (Test-Path -LiteralPath $msixPath) {
        Remove-Item -LiteralPath $msixPath -Force
    }

    & $makeAppx pack /d $pkgDir /p $msixPath /o
    if ($LASTEXITCODE -ne 0) {
        throw "MakeAppx pack falhou com código $LASTEXITCODE. O MSIX não será assinado nem instalado."
    }
    if (-not (Test-Path -LiteralPath $msixPath -PathType Leaf)) {
        throw 'O MakeAppx não criou o arquivo MSIX de saída.'
    }

    # O MakeAppx não tem um subcomando "validate". O próprio "pack" faz
    # validação semântica; esta segunda verificação confirma que o pacote pode
    # ser aberto/descompactado como MSIX.
    $validationDir = Join-Path $distDir '_KohaNexus_MSIX_Validation'
    if (Test-Path -LiteralPath $validationDir) {
        Remove-Item -LiteralPath $validationDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $validationDir -Force | Out-Null
    & $makeAppx unpack /p $msixPath /d $validationDir
    if ($LASTEXITCODE -ne 0) {
        throw "MakeAppx unpack (verificação de integridade) falhou com código $LASTEXITCODE. O pacote não será instalado."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $validationDir 'AppxManifest.xml') -PathType Leaf)) {
        throw 'O pacote gerado não contém um AppxManifest.xml legível após a verificação.'
    }
    Remove-Item -LiteralPath $validationDir -Recurse -Force

    if ($Store) {
        # Sem assinatura e sem instalação: o arquivo vai direto para uma nova
        # submissão no Partner Center.
        $buildSucceeded = $true
        Write-Host ''
        Write-Host '============================================================' -ForegroundColor Green
        Write-Host ' MSIX PARA A MICROSOFT STORE GERADO (SEM ASSINATURA)' -ForegroundColor Green
        Write-Host '============================================================' -ForegroundColor Green
        Write-Host "Versão: $targetVersion"
        Write-Host "Arquivo: $msixPath"
        Write-Host 'Envie este arquivo numa nova submissão no Partner Center. Para testar no PC, rode o script sem -Store.' -ForegroundColor Gray
        return
    }

    # --------------------------------------------------------
    # 7. ASSINAR E CONFIAR NO CERTIFICADO LOCAL
    # --------------------------------------------------------

    Write-Host "`n[6/8] Assinando o MSIX..." -ForegroundColor Yellow

    $signArguments = @('sign', '/fd', 'SHA256', '/s', 'My', '/sha1', $signingCertificate.Thumbprint, '/v')
    if ($certificateScope -eq 'LocalMachine') {
        $signArguments += '/sm'
    }
    # Carimbo de tempo: sem ele a assinatura deixa de valer quando o
    # certificado vence (20/10/2027) e o Windows recusa instalar o pacote.
    $timestampArguments = @('/tr', 'http://timestamp.digicert.com', '/td', 'SHA256')

    & $signTool @($signArguments + $timestampArguments + @($msixPath))
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Assinatura com carimbo de tempo falhou (sem internet?); assinando sem carimbo.' -ForegroundColor Yellow
        & $signTool @($signArguments + @($msixPath))
    }
    if ($LASTEXITCODE -ne 0) {
        throw "SignTool sign falhou com código $LASTEXITCODE. O MSIX não será instalado."
    }

    # Parte pública do certificado ao lado do MSIX, para publicar na release
    # junto com o pacote (windows\msix\instalar_msix.ps1 confia nela).
    $publicCertPath = Join-Path $distDir 'KohaNexus-Publisher.cer'
    [System.IO.File]::WriteAllBytes($publicCertPath, $signingCertificate.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert))
    Write-Host "Certificado público: $publicCertPath" -ForegroundColor Gray

    # Confia no certificado público em Pessoas Confiáveis do COMPUTADOR: é
    # esse repositório que o Windows consulta para instalar um MSIX (o do
    # usuário atual não basta). A chave privada não é exportada.
    $trustedPeoplePath = 'Cert:\LocalMachine\TrustedPeople'
    $trustedCertificate = Get-ChildItem -Path $trustedPeoplePath -ErrorAction SilentlyContinue |
        Where-Object { $_.Thumbprint -eq $signingCertificate.Thumbprint } |
        Select-Object -First 1

    if (-not $trustedCertificate) {
        if (-not (Test-Administrator)) {
            throw 'Execute este script como administrador: confiar no certificado exige Cert:\LocalMachine\TrustedPeople.'
        }
        Import-Certificate -FilePath $publicCertPath -CertStoreLocation $trustedPeoplePath -ErrorAction Stop | Out-Null
    }

    & $signTool verify /pa /v $msixPath
    if ($LASTEXITCODE -ne 0) {
        throw "SignTool verify falhou com código $LASTEXITCODE. O pacote não será instalado."
    }

    # --------------------------------------------------------
    # 8. SUBSTITUIR A VERSÃO ATUAL, INSTALAR E ABRIR O APLICATIVO
    # --------------------------------------------------------

    Write-Host "`n[7/8] Removendo a versão anterior do usuário atual e instalando..." -ForegroundColor Yellow

    $oldPackages = @(Get-AppxPackage -Name $packageName -ErrorAction SilentlyContinue)
    foreach ($oldPackage in $oldPackages) {
        Remove-AppxPackage -Package $oldPackage.PackageFullName -Confirm:$false -ErrorAction Stop
    }

    Add-AppxPackage -Path $msixPath -ErrorAction Stop

    $installedPackage = Get-AppxPackage -Name $packageName -ErrorAction Stop |
        Sort-Object { [version]$_.Version } -Descending |
        Select-Object -First 1

    if (-not $installedPackage) {
        throw 'Add-AppxPackage não retornou o pacote instalado.'
    }
    if ([string]$installedPackage.Version -ne $targetVersion) {
        throw "Versão instalada inesperada: $($installedPackage.Version); esperado: $targetVersion."
    }

    Write-Host "`n[8/8] Abrindo o Koha.Nexus para executar o bootstrap e preparar C:\Koha\bin..." -ForegroundColor Yellow
    $aumid = '{0}!{1}' -f $installedPackage.PackageFamilyName, $applicationId
    Start-Process -FilePath (Join-Path $env:WINDIR 'explorer.exe') -ArgumentList ("shell:AppsFolder\$aumid") -ErrorAction Stop

    $buildSucceeded = $true
    Write-Host ''
    Write-Host '============================================================' -ForegroundColor Green
    Write-Host ' MSIX EMPACOTADO, VALIDADO, ASSINADO E INSTALADO' -ForegroundColor Green
    Write-Host '============================================================' -ForegroundColor Green
    Write-Host "Versão: $targetVersion"
    Write-Host "Arquivo: $msixPath"
    Write-Host 'Icone original mantido na bandeja; icone personalizado usado no desktop, launcher MSIX e tiles do aplicativo.' -ForegroundColor Gray
    Write-Host 'Obs.: o icone do arquivo .msix no Explorador depende da associacao de arquivos do Windows, nao do manifesto.' -ForegroundColor Yellow
    Write-Host 'O bootstrap usa UTF-8 e não força cmd.exe: permite que o Koha use o perfil Windows Terminal quando disponível.' -ForegroundColor Gray
}
catch {
    Write-Host ''
    Write-Host '============================================================' -ForegroundColor Red
    Write-Host ' FALHA NO PROCESSO MSIX' -ForegroundColor Red
    Write-Host '============================================================' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ''
    Write-Host 'O processo foi interrompido. Nenhuma mensagem de sucesso será mostrada.' -ForegroundColor Yellow
}
finally {
    Write-Host ''
    Read-Host 'Pressione Enter para fechar esta janela' | Out-Null
}
