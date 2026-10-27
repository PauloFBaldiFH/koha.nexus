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
$assetsSourceDir = Join-Path $scriptRoot 'Assets'

# Versão solicitada originalmente. Precisa ser maior que qualquer versão
# anterior que ainda esteja instalada se o pacote for atualizado sem remoção.
$targetVersion = '1.0.29.0'
# Revision interna do payload: força a atualização de instalações incompletas
# feitas por builds anteriores, sem precisar alterar a versão pública do MSIX.
$payloadRevision = '1.0.29.0-msix-v21'
$packageName = 'KohaNexus'
$packagePublisher = 'CN=PauloFBaldiFH'
$publisherDisplayName = 'PauloFBaldiFH'
$storeIdentityPath = Join-Path $scriptRoot 'store-identity.json'
$applicationId = 'KohaNexus'
$entryExeName = 'KohaMsixEntry.exe'
$buildSucceeded = $false

# Ícones e blocos do pacote: PNGs prontos em windows\msix\Assets, gerados por
# gerar_assets.py. Antes eram desenhados aqui com System.Drawing a partir do
# .ico, cujos quadros são PNG: no Windows PowerShell 5.1 isso saía como ruído
# colorido, e a Store recusou o pacote (10.1.1.11, ícone não nítido).
function Get-KohaMsixAssetSizes {
    $tiles = [ordered]@{
        'Square44x44Logo'   = @(44, 44)
        'StoreLogo'         = @(50, 50)
        'Square71x71Logo'   = @(71, 71)
        'Square150x150Logo' = @(150, 150)
        'Wide310x150Logo'   = @(310, 150)
        'Square310x310Logo' = @(310, 310)
    }
    $sizes = [ordered]@{}
    foreach ($tile in $tiles.Keys) {
        foreach ($scale in @(100, 125, 150, 200, 400)) {
            $width = [int][Math]::Floor($tiles[$tile][0] * $scale / 100 + 0.5)
            $height = [int][Math]::Floor($tiles[$tile][1] * $scale / 100 + 0.5)
            $sizes[('{0}.scale-{1}.png' -f $tile, $scale)] = @($width, $height)
        }
    }
    foreach ($target in @(16, 24, 32, 48, 256)) {
        $sizes[('Square44x44Logo.targetsize-{0}.png' -f $target)] = @($target, $target)
        $sizes[('Square44x44Logo.targetsize-{0}_altform-unplated.png' -f $target)] = @($target, $target)
    }
    return $sizes
}

# Lista o que falta ou tem o tamanho errado em Assets (largura e altura lidas
# do cabeçalho PNG, sem System.Drawing).
function Test-KohaMsixAssets {
    param([Parameter(Mandatory = $true)][string]$AssetsDir)
    $problems = @()
    $sizes = Get-KohaMsixAssetSizes
    foreach ($name in $sizes.Keys) {
        $path = Join-Path $AssetsDir $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $problems += "falta Assets\$name"
            continue
        }
        $bytes = [System.IO.File]::ReadAllBytes($path)
        if ($bytes.Length -lt 24 -or $bytes[0] -ne 0x89 -or $bytes[1] -ne 0x50 -or $bytes[12] -ne 0x49 -or $bytes[15] -ne 0x52) {
            $problems += "Assets\$name não é PNG"
            continue
        }
        $width = ([int]$bytes[16] -shl 24) -bor ([int]$bytes[17] -shl 16) -bor ([int]$bytes[18] -shl 8) -bor [int]$bytes[19]
        $height = ([int]$bytes[20] -shl 24) -bor ([int]$bytes[21] -shl 16) -bor ([int]$bytes[22] -shl 8) -bor [int]$bytes[23]
        if ($width -ne $sizes[$name][0] -or $height -ne $sizes[$name][1]) {
            $problems += ('Assets\{0} tem {1}x{2}, esperado {3}x{4}' -f $name, $width, $height, $sizes[$name][0], $sizes[$name][1])
        }
    }
    return $problems
}

# MakePri.exe vem no mesmo pacote NuGet Microsoft.Windows.SDK.BuildTools do
# MakeAppx (bin\<versão>\x64) ou no Windows SDK.
function Find-KohaMakePri {
    param([Parameter(Mandatory = $true)][string]$SdkDir)
    $candidates = @(Join-Path $SdkDir 'makepri.exe')
    if (Test-Path -LiteralPath $SdkDir -PathType Container) {
        $candidates += @(Get-ChildItem -LiteralPath $SdkDir -Filter 'makepri.exe' -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\(x86|arm64|arm)\\' } | ForEach-Object { $_.FullName })
    }
    $programFilesX86 = [Environment]::GetFolderPath('ProgramFilesX86')
    if ($programFilesX86) {
        $kitsBin = Join-Path $programFilesX86 'Windows Kits\10\bin'
        if (Test-Path -LiteralPath $kitsBin -PathType Container) {
            $candidates += @(Get-ChildItem -LiteralPath $kitsBin -Filter 'makepri.exe' -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match '\\x64\\' } | Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
        }
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $candidate }
    }
    return $null
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

# installer, installer.sha256, lang\ e panel\ rodam ou são lidos dentro do
# Debian e precisam chegar com LF. O Git para Windows com core.autocrlf
# grava CRLF: o installer deixa de bater com installer.sha256 e o
# windows\install.ps1 recusa a instalação ("The installer file is
# damaged"). Devolve a lista do que está errado; vazia quando está tudo
# certo. Usada pelo compilador sobre o repositório e sobre a carga, e por
# tests\windows_checks.ps1.
function Test-KohaMsixPayloadText {
    param([Parameter(Mandatory = $true)][string]$Root)
    $problems = New-Object System.Collections.Generic.List[string]
    $installerFile = Join-Path $Root 'installer'
    $hashFile = Join-Path $Root 'installer.sha256'
    if (-not (Test-Path -LiteralPath $installerFile -PathType Leaf) -or -not (Test-Path -LiteralPath $hashFile -PathType Leaf)) {
        $problems.Add('installer ou installer.sha256 ausente')
        return $problems.ToArray()
    }
    $expected = ((Get-Content -LiteralPath $hashFile -TotalCount 1) -split '\s+')[0].ToUpperInvariant()
    $actual = (Get-FileHash -LiteralPath $installerFile -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($expected -ne $actual) {
        $problems.Add(('installer: SHA-256 {0} não bate com installer.sha256 ({1})' -f $actual, $expected))
    }
    $files = @(Get-Item -LiteralPath $installerFile, $hashFile)
    foreach ($dirName in 'lang', 'panel') {
        $dirPath = Join-Path $Root $dirName
        if (Test-Path -LiteralPath $dirPath -PathType Container) {
            $files += @(Get-ChildItem -LiteralPath $dirPath -Recurse -File -Force | Where-Object { $_.FullName -notmatch '[\\/]__pycache__[\\/]' })
        }
    }
    $withCr = @(foreach ($file in $files) {
        if ([Array]::IndexOf([IO.File]::ReadAllBytes($file.FullName), [byte]13) -ge 0) {
            $file.FullName.Substring($Root.Length).TrimStart('\', '/')
        }
    })
    if ($withCr.Count -gt 0) {
        $more = ''
        if ($withCr.Count -gt 8) { $more = ' e mais {0}' -f ($withCr.Count - 8) }
        $problems.Add(('com CRLF em vez de LF: {0}{1}' -f (@($withCr | Select-Object -First 8) -join ', '), $more))
    }
    return $problems.ToArray()
}

# O que o bootstrap do MSIX usa dos fontes de windows\ (sem alterá-los):
# devolve a lista do que falta; vazia quando está tudo certo. Usada pelo
# compilador sobre a cópia da carga e por tests\windows_checks.ps1 sobre o
# repositório.
function Test-KohaMsixSources {
    param([Parameter(Mandatory = $true)][string]$WindowsDir)
    $problems = New-Object System.Collections.Generic.List[string]
    $texts = @{}
    foreach ($fileName in @('KohaEasy.Core.psm1', 'KohaEasy.Install.psm1', 'KohaEasy.ps1', 'install.ps1', 'KohaMsixPanel.ps1', 'KohaMsixRefreshIcons.ps1', 'KohaEasy.Launcher.cs')) {
        $filePath = Join-Path $WindowsDir $fileName
        if (Test-Path -LiteralPath $filePath -PathType Leaf) {
            $texts[$fileName] = [System.IO.File]::ReadAllText($filePath)
        } else {
            $texts[$fileName] = ''
            $problems.Add("arquivo ausente: windows\$fileName")
        }
    }
    $rules = @(
        @('KohaEasy.Core.psm1', "(?m)^\s*StaffUrl\s*=\s*'http://localhost:8080/'", 'StaffUrl = http://localhost:8080/'),
        @('KohaEasy.Core.psm1', '(?m)^\s*WebPorts\s*=\s*@\(80, 8080\)', 'WebPorts = @(80, 8080)'),
        @('KohaEasy.Install.psm1', 'KOHA_MSIX_FIRST_RUN', 'conta Debian pedida de novo quando o Debian ainda não existe (KOHA_MSIX_FIRST_RUN)'),
        @('KohaEasy.Install.psm1', 'KOHA_MSIX_FINALIZE', 'fase Windows depois do painel (KOHA_MSIX_FINALIZE)'),
        @('KohaEasy.Install.psm1', '(?m)^function Initialize-KohaPanelDependencies\b', 'dependências do painel no primeiro terminal (Initialize-KohaPanelDependencies)'),
        @('KohaEasy.Install.psm1', "'Launch -Hidden'", 'segundo terminal aberto por koha.nexus.exe Launch -Hidden'),
        @('KohaEasy.ps1', "KOHA_MSIX_PANEL_SETUP", 'Launch abre KohaMsixPanel.ps1 (KOHA_MSIX_PANEL_SETUP)'),
        @('KohaEasy.ps1', "'Panel'", 'comando Panel (o bootstrap abre o painel com ele)'),
        @('install.ps1', 'KOHAEASY_SOURCE', 'install.ps1 lê KOHAEASY_SOURCE'),
        @('install.ps1', 'KOHAEASY_NO_WT', 'install.ps1 respeita KOHAEASY_NO_WT'),
        @('install.ps1', '(?m)^\s*if \(\$PSCommandPath -and \$code -gt 0\) \{ exit \$code \}', 'install.ps1 devolve o código do Install (3 = reiniciar) quando roda com -File'),
        @('KohaMsixPanel.ps1', 'KOHA_MSIX_FINALIZE', 'KohaMsixPanel.ps1 roda a fase Windows depois do painel'),
        @('KohaMsixRefreshIcons.ps1', 'KohaNexusDesktop\.ico', 'KohaMsixRefreshIcons.ps1 usa KohaNexusDesktop.ico')
    )
    foreach ($rule in $rules) {
        if ($texts[$rule[0]] -notmatch $rule[1]) { $problems.Add(('windows\{0}: falta {1}' -f $rule[0], $rule[2])) }
    }
    # Segurança da conta Debian: uma única Read-KohaLinuxAccount, com senha
    # lida por Read-Host -AsSecureString; nenhuma senha fixa nem versão
    # desativada da função.
    $installText = $texts['KohaEasy.Install.psm1']
    if ($installText -match 'kohanexuspassword123') { $problems.Add('windows\KohaEasy.Install.psm1: senha fixa encontrada') }
    if ($installText -match 'function Read-KohaLinuxAccount_Disabled\b') { $problems.Add('windows\KohaEasy.Install.psm1: Read-KohaLinuxAccount_Disabled ainda existe') }
    $installAst = [System.Management.Automation.Language.Parser]::ParseInput($installText, [ref]$null, [ref]$null)
    $accountFunctions = @($installAst.FindAll({ param($a) $a -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $a.Name -eq 'Read-KohaLinuxAccount' }, $true))
    if ($accountFunctions.Count -ne 1) {
        $problems.Add(('windows\KohaEasy.Install.psm1: esperava uma função Read-KohaLinuxAccount; encontradas {0}' -f $accountFunctions.Count))
    } elseif ($accountFunctions[0].Extent.Text -notmatch 'Read-Host\s+-AsSecureString') {
        $problems.Add('windows\KohaEasy.Install.psm1: Read-KohaLinuxAccount não lê a senha com Read-Host -AsSecureString')
    }
    return $problems.ToArray()
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

    foreach ($requiredFile in @($installer, $installerHash, $iconPath)) {
        if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
            throw "Arquivo obrigatório não encontrado: $requiredFile"
        }
    }

    # O installer precisa bater com installer.sha256 e chegar ao Debian com
    # LF; um checkout com CRLF geraria um MSIX que para na instalação.
    $payloadTextProblems = @(Test-KohaMsixPayloadText -Root $repoDir)
    if ($payloadTextProblems.Count -gt 0) {
        throw ('A cópia local do repositório não serve para o MSIX. Nada será empacotado:' + [Environment]::NewLine +
            ($payloadTextProblems -join [Environment]::NewLine) + [Environment]::NewLine +
            'Com o .gitattributes atual (git pull), regrave esses arquivos com LF na raiz do repositório:' + [Environment]::NewLine +
            '  Remove-Item installer, installer.sha256; Remove-Item lang, panel -Recurse -Force' + [Environment]::NewLine +
            '  git checkout -- installer installer.sha256 lang panel')
    }

    # O modo Store não assina: só o MakeAppx é necessário.
    $requiredTools = @($makeAppx)
    if (-not $Store) { $requiredTools += $signTool }
    foreach ($toolPath in $requiredTools) {
        if (-not (Test-Path -LiteralPath $toolPath -PathType Leaf)) {
            throw "Ferramenta do SDK não encontrada: $toolPath"
        }
    }
    # Sem resources.pri o Windows usa só o arquivo sem qualificador e amplia
    # um ícone pequeno: os blocos saem borrados.
    $makePri = Find-KohaMakePri -SdkDir $sdkDir
    if (-not $makePri) {
        throw ("MakePri.exe não encontrado. Ele vem no mesmo pacote NuGet Microsoft.Windows.SDK.BuildTools do MakeAppx " +
            "(pasta bin\<versão>\x64): copie makepri.exe para $sdkDir.")
    }
    $assetProblems = @(Test-KohaMsixAssets -AssetsDir $assetsSourceDir)
    if ($assetProblems.Count -gt 0) {
        throw ('Ícones do pacote incompletos em windows\msix\Assets (git pull; ou python3 windows\msix\gerar_assets.py):' +
            [Environment]::NewLine + ($assetProblems -join [Environment]::NewLine))
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

    if ($Store) {
        # A Store descarta qualquer assinatura e assina o pacote ela mesma:
        # nenhum certificado local é procurado.
        Write-Host 'Modo Store: o pacote sai sem assinatura; a Microsoft Store assina.' -ForegroundColor Gray
    } else {
        # Localiza o certificado de assinatura pela identidade Publisher exata.
        # O certificado informado pelo diagnóstico estava em LocalMachine\My.
        # (Nenhuma variável aqui pode se chamar $store: o PowerShell não
        # diferencia maiúsculas e ela sobrescreveria o parâmetro -Store.)
        $certificateCandidates = @()
        $certificateStores = @(
            [pscustomobject]@{ Path = 'Cert:\LocalMachine\My'; Scope = 'LocalMachine' },
            [pscustomobject]@{ Path = 'Cert:\CurrentUser\My'; Scope = 'CurrentUser' }
        )

        foreach ($certificateStoreInfo in $certificateStores) {
            $storeCertificates = Get-ChildItem -Path $certificateStoreInfo.Path -ErrorAction SilentlyContinue
            foreach ($certificate in $storeCertificates) {
                if (
                    $certificate.Subject -eq $packagePublisher -and
                    $certificate.HasPrivateKey -and
                    $certificate.NotBefore -le (Get-Date) -and
                    $certificate.NotAfter -gt (Get-Date)
                ) {
                    $certificateCandidates += [pscustomobject]@{
                        Certificate = $certificate
                        Scope       = $certificateStoreInfo.Scope
                    }
                }
            }
        }

        $certificateRecord = $certificateCandidates |
            Sort-Object { $_.Certificate.NotAfter } -Descending |
            Select-Object -First 1

        if (-not $certificateRecord) {
            throw "Não encontrei certificado válido com chave privada e Subject '$packagePublisher' nos repositórios My do usuário ou do computador."
        }

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
        # msix: esta pasta de build (fontes, Assets, o .msix antigo) nao roda no app.
        'setup', 'msix', '.git', '.github', 'node_modules', '__pycache__',
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

    # As adaptações do MSIX (staff na porta 8080, conta Debian pedida com
    # Read-Host -AsSecureString, os dois terminais, KohaMsixPanel.ps1 e
    # KohaMsixRefreshIcons.ps1) estão nos próprios fontes de windows\ desde
    # o commit 543272d. O compilador não reescreve mais nenhum arquivo da
    # carga: só confere que a cópia tem o que o bootstrap do MSIX usa, e
    # para com a lista do que falta. tests\windows_checks.ps1 roda a mesma
    # conferência sobre os arquivos do repositório.
    $coreModulePath = Join-Path $payloadWindowsDir 'KohaEasy.Core.psm1'
    $installModulePath = Join-Path $payloadWindowsDir 'KohaEasy.Install.psm1'
    $mainWindowsPath = Join-Path $payloadWindowsDir 'KohaEasy.ps1'
    $panelWrapperPath = Join-Path $payloadWindowsDir 'KohaMsixPanel.ps1'
    $iconFixScriptPath = Join-Path $payloadWindowsDir 'KohaMsixRefreshIcons.ps1'
    $sourceProblems = @(Test-KohaMsixSources -WindowsDir $payloadWindowsDir)
    if ($sourceProblems.Count -gt 0) {
        throw ('Os fontes de windows\ não têm o que o MSIX usa. Nada será empacotado:' + [Environment]::NewLine + ($sourceProblems -join [Environment]::NewLine))
    }
    Write-Host 'Fontes de windows\ conferidos: staff na porta 8080, conta Debian protegida, dois terminais.' -ForegroundColor Gray

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
    $payloadTextProblems = @(Test-KohaMsixPayloadText -Root $payloadDir)
    if ($payloadTextProblems.Count -gt 0) {
        throw ('A carga do MSIX não confere com installer.sha256. Nada será empacotado:' + [Environment]::NewLine + ($payloadTextProblems -join [Environment]::NewLine))
    }

    # Entry point do MSIX chama este bootstrap, não "KohaEasy.ps1 Launch".
    # O comando Launch mostra corretamente "Koha is not installed" fora do
    # contexto de instalação; aqui primeiro executamos o bootstrap oficial.
    $bootstrapPath = Join-Path $pkgDir 'Bootstrap-MSIX.ps1'
    $bootstrapContent = @'
# -ResultFile: o KohaMsixEntry.exe mostra o resultado na janela dele; sem
# caixas de erro aqui (Store 10.1.2.10). 3 reiniciar, 10 parou, 11 sem virtualizacao.
param([string]$ResultFile = '')
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

function Write-BootstrapResult {
    param([string]$Message)
    if (-not $ResultFile) { return }
    try {
        New-Item -ItemType Directory -Path (Split-Path -Parent $ResultFile) -Force | Out-Null
        [System.IO.File]::WriteAllText($ResultFile, $Message, (New-Object System.Text.UTF8Encoding($false)))
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
            PayloadMissing = 'Falta um arquivo do aplicativo; reinstale o Koha.Nexus: '
            InstallStopped = 'A instalação parou (código {0}). As mensagens da janela de console e os registros em C:\Koha\logs dizem o motivo.'
            MainMissing = 'A preparação terminou, mas o KohaEasy.ps1 não foi copiado para '
            ElevationTitle = 'Permissão de administrador'
            ElevationBody = "Na primeira execução o Koha.Nexus precisa de permissão de administrador para ativar o WSL 2 e instalar o Debian com o Koha. A permissão foi recusada, ou esta conta do Windows não é de administrador.`r`n`r`nAbra o Koha.Nexus de novo e responda Sim no aviso do Windows (ou entre com uma conta de administrador). Nada foi alterado neste computador."
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
        PayloadMissing = 'A file of the app is missing; reinstall Koha.Nexus: '
        InstallStopped = 'Setup stopped (code {0}). The console window messages and the logs in C:\Koha\logs give the reason.'
        MainMissing = 'Preparation finished, but KohaEasy.ps1 was not copied to '
        ElevationTitle = 'Administrator permission'
        ElevationBody = "On its first run Koha.Nexus needs administrator permission to turn on WSL 2 and install Debian with Koha. The permission was declined, or this Windows account is not an administrator.`r`n`r`nOpen Koha.Nexus again and answer Yes in the Windows prompt (or sign in with an administrator account). Nothing was changed on this computer."
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
        throw ($ui.PayloadMissing + $installScript)
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
    if ($virtualizationState -is [bool] -and -not $virtualizationState -and $ResultFile) {
        Write-BootstrapLog 'Virtualization is off; reported to the launcher window.'
        Write-BootstrapResult $ui.VirtualizationTitle
        exit 11
    }
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
        if ($ResultFile) { $arguments += (' -ResultFile "{0}"' -f $ResultFile) }
        Write-BootstrapLog 'Elevation required; opening the elevated bootstrap window.'
        try {
            Start-Process -FilePath $powershell -ArgumentList $arguments -Verb RunAs -WindowStyle Normal -ErrorAction Stop | Out-Null
        }
        catch {
            # UAC recusado ou conta sem administrador: explicar, sem a caixa de erro.
            Write-BootstrapLog ('Elevation declined or unavailable: ' + $_.Exception.Message)
            $null = Show-BootstrapMessage -Text $ui.ElevationBody -Title $ui.ElevationTitle -Buttons 'OK' -Icon 'Information'
        }
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
            if ($ResultFile) { exit 3 }
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
            throw ($ui.InstallStopped -f $installProcess.ExitCode)
        }

        if (-not (Test-Path -LiteralPath $mainScript -PathType Leaf)) {
            throw ($ui.MainMissing + $kohaBin)
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
    exit 0
}
catch {
    $message = $_.Exception.Message
    Write-BootstrapLog ('ERRO: ' + $message)
    if ($ResultFile) {
        Write-BootstrapResult $message
        exit 10
    }
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show(
            "$($ui.GenericErrorPrefix)`r`n`r`n$message`r`n`r`nLog: $logDir\msix-bootstrap.log",
            'Koha.Nexus',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        )
    } catch { }
    # 10: erro ja mostrado (ou gravado em -ResultFile para a janela do launcher).
    exit 10
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

    Write-Host "`n[2/8] Copiando os ícones e blocos PNG..." -ForegroundColor Yellow
    $assetsDir = Join-Path $pkgDir 'Assets'
    New-Item -ItemType Directory -Path $assetsDir -Force | Out-Null
    foreach ($assetName in (Get-KohaMsixAssetSizes).Keys) {
        Copy-Item -LiteralPath (Join-Path $assetsSourceDir $assetName) -Destination (Join-Path $assetsDir $assetName) -Force
    }

    # --------------------------------------------------------
    # 4. COMPILAR O PONTO DE ENTRADA MSIX SEM JANELA DE CONSOLE
    # --------------------------------------------------------

    Write-Host "`n[3/8] Compilando o launcher MSIX..." -ForegroundColor Yellow

    # O launcher fica em windows\msix\KohaMsixEntry.cs (o CI compila o mesmo
    # arquivo). Ele abre a janela de instalação e o painel.
    $entrySource = [System.IO.File]::ReadAllText((Join-Path $scriptRoot 'KohaMsixEntry.cs'))
    if ($entrySource -notmatch '__PAYLOAD_VERSION__') {
        throw 'KohaMsixEntry.cs sem o marcador __PAYLOAD_VERSION__.'
    }
    $entrySource = $entrySource.Replace('__PAYLOAD_VERSION__', $payloadRevision)
    $entrySourcePath = Join-Path $distDir 'KohaMsixEntry.cs'
    $entryExePath = Join-Path $pkgDir $entryExeName
    [System.IO.File]::WriteAllText($entrySourcePath, $entrySource, (New-Object System.Text.UTF8Encoding($false)))

    & $csc /nologo /target:winexe /platform:anycpu /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Management.dll "/out:$entryExePath" "/win32icon:$iconPath" "/win32manifest:$(Join-Path $scriptRoot 'KohaMsixEntry.manifest')" $entrySourcePath
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
                          Square44x44Logo="Assets\Square44x44Logo.png">
        <uap:DefaultTile Wide310x150Logo="Assets\Wide310x150Logo.png"
                         Square71x71Logo="Assets\Square71x71Logo.png"
                         Square310x310Logo="Assets\Square310x310Logo.png"
                         ShortName="Koha.Nexus">
          <uap:ShowNameOnTiles>
            <uap:ShowOn Tile="square150x150Logo" />
            <uap:ShowOn Tile="wide310x150Logo" />
            <uap:ShowOn Tile="square310x310Logo" />
          </uap:ShowNameOnTiles>
        </uap:DefaultTile>
      </uap:VisualElements>
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

    # resources.pri: indica ao Windows os arquivos scale-* e targetsize-* de
    # cada ícone. Indexa só Assets e o manifesto (numa cópia), não a carga.
    $priDir = Join-Path $distDir '_KohaNexus_PRI'
    if (Test-Path -LiteralPath $priDir) {
        Remove-Item -LiteralPath $priDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $priDir -Force | Out-Null
    Copy-Item -LiteralPath $assetsDir -Destination $priDir -Recurse -Force
    Copy-Item -LiteralPath $manifestPath -Destination $priDir -Force
    $priConfig = Join-Path $distDir 'priconfig.xml'
    & $makePri createconfig /cf $priConfig /dq pt-BR /pv 10.0.0 /o
    if ($LASTEXITCODE -ne 0) {
        throw "MakePri createconfig falhou com código $LASTEXITCODE."
    }
    # Sem a seção packaging: um único resources.pri, sem pacotes de recursos.
    $priConfigDocument = New-Object System.Xml.XmlDocument
    $priConfigDocument.Load($priConfig)
    foreach ($packagingNode in @($priConfigDocument.SelectNodes('//packaging'))) {
        [void]$packagingNode.ParentNode.RemoveChild($packagingNode)
    }
    $priConfigDocument.Save($priConfig)
    $priPath = Join-Path $pkgDir 'resources.pri'
    & $makePri new /pr $priDir /cf $priConfig /mn (Join-Path $priDir 'AppxManifest.xml') /of $priPath /o
    if ($LASTEXITCODE -ne 0) {
        throw "MakePri new falhou com código $LASTEXITCODE; sem resources.pri os ícones saem borrados."
    }
    Remove-Item -LiteralPath $priDir -Recurse -Force

    # Confirma que a carga mínima está na raiz do pacote.
    foreach ($requiredInPackage in @(
        'AppxManifest.xml', 'Bootstrap-MSIX.ps1', $entryExeName, 'resources.pri',
        'Assets\Square44x44Logo.targetsize-256.png', 'Assets\Square150x150Logo.scale-400.png',
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
        # submissão no Partner Center. Confere o arquivo final: identidade,
        # versão e arquitetura do manifesto, e nenhuma assinatura (nem a do
        # certificado de desenvolvimento CN=PauloFBaldiFH).
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $storeZip = [System.IO.Compression.ZipFile]::OpenRead($msixPath)
        try {
            if ($null -ne $storeZip.GetEntry('AppxSignature.p7x')) {
                throw 'O pacote da Store saiu assinado, mas o modo Store não deve assinar com o certificado local.'
            }
            foreach ($entryName in @('AppxManifest.xml', 'AppxBlockMap.xml', '[Content_Types].xml')) {
                if ($null -eq $storeZip.GetEntry($entryName)) { throw "O pacote da Store não contém $entryName." }
            }
            $storeReader = New-Object System.IO.StreamReader($storeZip.GetEntry('AppxManifest.xml').Open())
            try { [xml]$storeManifest = $storeReader.ReadToEnd() } finally { $storeReader.Dispose() }
        } finally {
            $storeZip.Dispose()
        }
        $storeIdentityNode = $storeManifest.Package.Identity
        $checks = @(
            @('Name', [string]$storeIdentityNode.Name, $packageName),
            @('Publisher', [string]$storeIdentityNode.Publisher, $packagePublisher),
            @('Version', [string]$storeIdentityNode.Version, $targetVersion),
            @('ProcessorArchitecture', [string]$storeIdentityNode.ProcessorArchitecture, 'x64'),
            @('PublisherDisplayName', [string]$storeManifest.Package.Properties.PublisherDisplayName, $publisherDisplayName)
        )
        foreach ($check in $checks) {
            if ($check[1] -cne $check[2]) {
                throw ("Manifesto do pacote da Store: {0} = '{1}', esperado '{2}'." -f $check[0], $check[1], $check[2])
            }
            Write-Host ("  {0}: {1}" -f $check[0], $check[1]) -ForegroundColor Gray
        }
        Write-Host '  Assinatura: nenhuma (a Store assina na publicação)' -ForegroundColor Gray
        Write-Host ("  SHA-256: {0}" -f (Get-FileHash -LiteralPath $msixPath -Algorithm SHA256).Hash) -ForegroundColor Gray

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
