# Koha.Nexus Store installer: checks run after the files are copied, before
# the install itself. Called by koha-nexus.iss, nothing else.
#
# Exit codes (the installer passes them on, see koha-nexus.iss):
#   0      the payload matches installer.sha256 and github.com answers
#   1625   ERROR_INSTALL_PACKAGE_REJECTED: the installer file is damaged
#   12029  ERROR_INTERNET_CANNOT_CONNECT: github.com cannot be reached
#   1      unexpected error in this script (the installer maps it to 1603)
#
# ASCII only, so it needs no byte order mark.

param(
    [Parameter(Mandatory = $true)]
    [string]$AppDir
)

$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

$ERROR_INSTALL_PACKAGE_REJECTED = 1625
$ERROR_INTERNET_CANNOT_CONNECT = 12029

# 1. Payload: the same SHA-256 check install.ps1 makes on the downloaded copy.
try {
    $expected = ((Get-Content -LiteralPath (Join-Path $AppDir 'installer.sha256') -TotalCount 1) -split '\s+')[0].ToUpperInvariant()
    $actual = (Get-FileHash -LiteralPath (Join-Path $AppDir 'installer') -Algorithm SHA256).Hash.ToUpperInvariant()
} catch {
    exit $ERROR_INSTALL_PACKAGE_REJECTED
}
if ((-not $expected) -or ($expected -ne $actual)) {
    exit $ERROR_INSTALL_PACKAGE_REJECTED
}

# 2. Network: the Debian image and Koha come from the internet during Install.
try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri 'https://github.com' -Method Head -UseBasicParsing -TimeoutSec 30 | Out-Null
} catch {
    exit $ERROR_INTERNET_CANNOT_CONNECT
}

exit 0
