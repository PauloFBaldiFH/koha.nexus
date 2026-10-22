#Requires -Version 5.1
<#
.SYNOPSIS
    Installs the Koha.Nexus MSIX on a PC that does not trust its certificate yet.
.DESCRIPTION
    The MSIX is signed with Paulo's own certificate (CN=PauloFBaldiFH), which
    no Windows trusts out of the box: App Installer shows "Fornecedor:
    Desconhecido" and refuses with "Nao foi possivel verificar o certificado
    de fornecedor deste pacote de aplicativo".

    This script:
      1. downloads the MSIX from the GitHub release (or uses -MsixPath);
      2. reads the signer certificate inside the package and accepts it only
         when its thumbprint is one of $KnownThumbprints below;
      3. adds that certificate (public part only) to Local Machine > Trusted
         People, the store App Installer checks: one UAC prompt, once per PC;
      4. installs the package for the current user and opens Koha.Nexus.

    Windows still checks the package signature itself in step 4: the script
    only decides which certificate this PC trusts.

    One line, in a normal (not administrator) PowerShell window:
      irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex

    ASCII only, no BOM: it runs through irm | iex (see tests/windows_checks.ps1).
.PARAMETER MsixPath
    A .msix already on this PC; nothing is downloaded.
.PARAMETER ReleaseTag
    The GitHub release that holds KohaNexus.msix.
.PARAMETER NoLaunch
    Install only; do not open Koha.Nexus at the end.
#>
param(
    [string]$MsixPath = '',
    [string]$ReleaseTag = 'windows-v1.0.27.0',
    [switch]$NoLaunch
)

# SHA-1 thumbprints of the certificates that sign Koha.Nexus packages. A new
# certificate (renewal, new PC) is added here in the same commit as its
# KohaNexus-Publisher.cer; the old one stays while its packages are in use.
$KnownThumbprints = @(
    'F3B8345A573381F2E71B56A96F5EF3253B80A26C'   # CN=PauloFBaldiFH, 2026-10-20 to 2027-10-20
    'B6721986CB46257290395751E429897B6A48FBBB'   # CN=PauloFBaldiFH, 2026-10-22 to 2029-10-22 (from 1.0.27.0; the F3B8 key was lost)
)
$ExpectedSubject = 'CN=PauloFBaldiFH'
$PackageName = 'KohaNexus'
$ApplicationId = 'KohaNexus'

function Write-Step {
    param([string]$Text, [string]$Color = 'Cyan')
    Write-Host $Text -ForegroundColor $Color
}

# Pure: the signer certificate of an MSIX. AppxSignature.p7x is "PKCX"
# followed by a PKCS#7 SignedData; the signer is the first SignerInfo.
function Get-KohaMsixSigner {
    param([Parameter(Mandatory = $true)][string]$Path)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    Add-Type -AssemblyName System.Security
    $zip = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entry = $zip.GetEntry('AppxSignature.p7x')
        if ($null -eq $entry) { throw 'O pacote nao esta assinado (falta AppxSignature.p7x).' }
        $stream = $entry.Open()
        $buffer = New-Object System.IO.MemoryStream
        try { $stream.CopyTo($buffer) } finally { $stream.Dispose() }
        $bytes = $buffer.ToArray()
    } finally {
        $zip.Dispose()
    }
    if ($bytes.Length -lt 8 -or [Text.Encoding]::ASCII.GetString($bytes, 0, 4) -ne 'PKCX') {
        throw 'Assinatura do pacote em formato desconhecido.'
    }
    $der = New-Object byte[] ($bytes.Length - 4)
    [Array]::Copy($bytes, 4, $der, 0, $der.Length)
    $cms = New-Object System.Security.Cryptography.Pkcs.SignedCms
    $cms.Decode($der)
    if ($cms.SignerInfos.Count -lt 1 -or $null -eq $cms.SignerInfos[0].Certificate) {
        throw 'A assinatura do pacote nao traz o certificado do fornecedor.'
    }
    return $cms.SignerInfos[0].Certificate
}

# Pure: Identity Name and Version from the package manifest.
function Get-KohaMsixIdentity {
    param([Parameter(Mandatory = $true)][string]$Path)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entry = $zip.GetEntry('AppxManifest.xml')
        if ($null -eq $entry) { throw 'O pacote nao tem AppxManifest.xml.' }
        $reader = New-Object System.IO.StreamReader($entry.Open())
        try { [xml]$xml = $reader.ReadToEnd() } finally { $reader.Dispose() }
    } finally {
        $zip.Dispose()
    }
    $id = $xml.Package.Identity
    return [pscustomobject]@{ Name = [string]$id.Name; Version = [string]$id.Version; Publisher = [string]$id.Publisher }
}

function Test-KohaTrustedPublisher {
    param([string]$Thumbprint)
    return [bool](Get-ChildItem -Path 'Cert:\LocalMachine\TrustedPeople' -ErrorAction SilentlyContinue |
        Where-Object { $_.Thumbprint -eq $Thumbprint } | Select-Object -First 1)
}

function Test-KohaAdministrator {
    $principal = New-Object Security.Principal.WindowsPrincipal ([Security.Principal.WindowsIdentity]::GetCurrent())
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Install-KohaNexusMsix {
    if ([Environment]::OSVersion.Version.Build -lt 17763) {
        throw 'O Koha.Nexus precisa do Windows 10 versao 1809 ou mais novo.'
    }

    # 1. The package.
    $msix = $MsixPath
    if (-not $msix) {
        $url = 'https://github.com/PauloFBaldiFH/koha.nexus/releases/download/{0}/KohaNexus.msix' -f $ReleaseTag
        $msix = Join-Path $env:TEMP ('KohaNexus-{0}.msix' -f $ReleaseTag)
        Write-Step ('Baixando {0} ...' -f $url)
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $old = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        try { Invoke-WebRequest -Uri $url -OutFile $msix -UseBasicParsing -ErrorAction Stop } finally { $ProgressPreference = $old }
    }
    if (-not (Test-Path -LiteralPath $msix -PathType Leaf)) { throw ('Arquivo nao encontrado: ' + $msix) }
    $msix = (Resolve-Path -LiteralPath $msix).Path

    # 2. Its signer must be a certificate this project publishes.
    $signer = Get-KohaMsixSigner -Path $msix
    $identity = Get-KohaMsixIdentity -Path $msix
    Write-Step ('Pacote {0} {1}, assinado por {2} ({3})' -f $identity.Name, $identity.Version, $signer.Subject, $signer.Thumbprint) 'Gray'
    if ($KnownThumbprints -notcontains $signer.Thumbprint.ToUpperInvariant() -or $signer.Subject -ne $ExpectedSubject -or $identity.Publisher -ne $ExpectedSubject) {
        throw ('O certificado deste pacote nao e um dos certificados do Koha.Nexus (impressao digital {0}). Nada foi instalado.' -f $signer.Thumbprint)
    }

    # 3. Trust it on this PC (public part only; Trusted People, not the root store).
    if (Test-KohaTrustedPublisher -Thumbprint $signer.Thumbprint) {
        Write-Step 'O certificado do Koha.Nexus ja e confiavel neste computador.' 'Green'
    } else {
        $cer = Join-Path $env:TEMP 'KohaNexus-Publisher.cer'
        [IO.File]::WriteAllBytes($cer, $signer.Export([Security.Cryptography.X509Certificates.X509ContentType]::Cert))
        Write-Step 'Adicionando o certificado do Koha.Nexus as Pessoas Confiaveis do computador (o Windows pede permissao uma vez)...'
        if (Test-KohaAdministrator) {
            Import-Certificate -FilePath $cer -CertStoreLocation 'Cert:\LocalMachine\TrustedPeople' -ErrorAction Stop | Out-Null
        } else {
            $certutil = Join-Path $env:SystemRoot 'System32\certutil.exe'
            try {
                $p = Start-Process -FilePath $certutil -ArgumentList ('-addstore TrustedPeople "{0}"' -f $cer) -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ErrorAction Stop
            } catch {
                throw 'A permissao de administrador foi recusada; o certificado nao foi adicionado.'
            }
            if ($p.ExitCode -ne 0) { throw ('certutil terminou com codigo {0}.' -f $p.ExitCode) }
        }
        if (-not (Test-KohaTrustedPublisher -Thumbprint $signer.Thumbprint)) {
            throw 'O certificado nao aparece em Cert:\LocalMachine\TrustedPeople depois da importacao.'
        }
        Write-Step 'Certificado adicionado.' 'Green'
    }

    # 4. Install for this user. The same version already installed is kept:
    # Windows refuses a different package under the same version number.
    $installed = Get-AppxPackage -Name $PackageName -ErrorAction SilentlyContinue |
        Sort-Object { [version]$_.Version } -Descending | Select-Object -First 1
    if ($installed -and [version]$installed.Version -ge [version]$identity.Version) {
        Write-Step ('Koha.Nexus {0} ja esta instalado.' -f $installed.Version) 'Green'
    } else {
        Write-Step ('Instalando Koha.Nexus {0} ...' -f $identity.Version)
        Add-AppxPackage -Path $msix -ErrorAction Stop
        $installed = Get-AppxPackage -Name $PackageName -ErrorAction Stop |
            Sort-Object { [version]$_.Version } -Descending | Select-Object -First 1
        if (-not $installed) { throw 'Add-AppxPackage terminou, mas o pacote nao aparece instalado.' }
        Write-Step ('Koha.Nexus {0} instalado.' -f $installed.Version) 'Green'
    }

    if (-not $NoLaunch) {
        $aumid = '{0}!{1}' -f $installed.PackageFamilyName, $ApplicationId
        Start-Process -FilePath (Join-Path $env:WINDIR 'explorer.exe') -ArgumentList ('shell:AppsFolder\' + $aumid)
        Write-Step 'Koha.Nexus aberto. A preparacao continua na janela que acabou de abrir.' 'Green'
    }
}

try {
    Install-KohaNexusMsix
    $global:LASTEXITCODE = 0
} catch {
    Write-Host ''
    Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
    $global:LASTEXITCODE = 1
    # Under irm | iex an exit would close the user's window.
    if ($PSCommandPath) { exit 1 }
}
