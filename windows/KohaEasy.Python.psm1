# koha.nexus for Windows: the Python runtime of the new tray and window.
# Puts the embeddable CPython from python.org in <root>\bin\python, with
# the packages of bin\client\runtime.lock.json in its Lib\site-packages.
# Every file is checked against the SHA-256 in that lock before it is used;
# one that differs is deleted and the step stops. Nothing is compiled or
# run from the internet: wheels are zip files, unpacked as they are.
#   bin\python\python312._pth   names bin\client (koha_nexus_win) and bin
#                               (nexus_core), so "pythonw.exe -m
#                               koha_nexus_win" works with no PATH or
#                               environment variable
#   <root>\downloads\python     the checked files, kept so running the
#                               installer again downloads nothing
# The runtime is built in bin\python.new and swapped in at the end, so a
# failed download never leaves half a runtime. Nothing starts it yet
# (Phase 1): the PowerShell tray and window stay what librarians use.
# Windows PowerShell 5.1 compatible. UTF-8 with BOM.

Set-StrictMode -Version 2.0

function Get-KohaSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Read-KohaPythonLock {
    param([Parameter(Mandatory = $true)][string]$Path)
    $lock = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([int]$lock.lock -ne 1) { throw ('runtime.lock.json: unknown lock format {0}' -f $lock.lock) }
    foreach ($e in @(@($lock.python) + @($lock.packages))) {
        if ([string]$e.sha256 -notmatch '^[0-9a-f]{64}$') { throw ('runtime.lock.json: bad SHA-256 for {0}' -f $e.url) }
        if ([string]$e.url -notmatch '^https://(www\.python\.org|files\.pythonhosted\.org)/') { throw ('runtime.lock.json: unexpected download address {0}' -f $e.url) }
    }
    return $lock
}

# Pure: the cache file name of a download (the last part of its address).
function Get-KohaDownloadName {
    param([Parameter(Mandatory = $true)][string]$Url)
    $name = ($Url -split '/')[-1]
    if ($name -notmatch '^[A-Za-z0-9._+-]+$') { throw ('unexpected file name in {0}' -f $Url) }
    return $name
}

# The file at $Url in $Dir, checked: a cached copy with the right hash is
# used as it is; anything else is downloaded again and checked.
function Get-KohaCheckedDownload {
    param([Parameter(Mandatory = $true)][string]$Url, [Parameter(Mandatory = $true)][string]$Sha256, [Parameter(Mandatory = $true)][string]$Dir)
    if (-not (Test-Path -LiteralPath $Dir)) { New-Item -ItemType Directory -Path $Dir -Force | Out-Null }
    $file = [System.IO.Path]::Combine($Dir, (Get-KohaDownloadName $Url))
    if ((Test-Path -LiteralPath $file) -and (Get-KohaSha256 $file) -eq $Sha256) { return $file }
    $part = $file + '.part'
    if (Test-Path -LiteralPath $part) { Remove-Item -LiteralPath $part -Force }
    $curl = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'curl.exe')
    $done = $false
    if ($env:SystemRoot -and (Test-Path -LiteralPath $curl)) {
        & $curl -fsSL --retry 3 -A 'KohaEasyInstaller' -o $part $Url 2>&1 | Out-Null
        $done = ($LASTEXITCODE -eq 0)
    }
    if (-not $done) {
        $prev = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        try { Invoke-WebRequest -Uri $Url -OutFile $part -UseBasicParsing -UserAgent 'KohaEasyInstaller' } finally { $ProgressPreference = $prev }
    }
    $got = Get-KohaSha256 $part
    if ($got -ne $Sha256) {
        Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
        throw ('{0}: SHA-256 {1} does not match the lock ({2})' -f (Get-KohaDownloadName $Url), $got, $Sha256)
    }
    Move-Item -LiteralPath $part -Destination $file -Force
    return $file
}

function Expand-KohaZip {
    param([Parameter(Mandatory = $true)][string]$Zip, [Parameter(Mandatory = $true)][string]$Dest)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (-not (Test-Path -LiteralPath $Dest)) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }
    [System.IO.Compression.ZipFile]::ExtractToDirectory($Zip, $Dest)
}

# A wheel into site-packages: unpacked apart, its *.data\purelib and
# platlib moved to the top (the rest of *.data, scripts and headers, is not
# needed), then merged in.
function Install-KohaWheel {
    param([Parameter(Mandatory = $true)][string]$Wheel, [Parameter(Mandatory = $true)][string]$SitePackages)
    $tmp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), 'koha-wheel-' + [guid]::NewGuid().ToString('N'))
    try {
        Expand-KohaZip -Zip $Wheel -Dest $tmp
        foreach ($data in @(Get-ChildItem -LiteralPath $tmp -Directory -Filter '*.data')) {
            foreach ($lib in 'purelib', 'platlib') {
                $src = [System.IO.Path]::Combine($data.FullName, $lib)
                if (Test-Path -LiteralPath $src) {
                    Get-ChildItem -LiteralPath $src -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $tmp -Recurse -Force }
                }
            }
            Remove-Item -LiteralPath $data.FullName -Recurse -Force
        }
        if (-not (Test-Path -LiteralPath $SitePackages)) { New-Item -ItemType Directory -Path $SitePackages -Force | Out-Null }
        Get-ChildItem -LiteralPath $tmp -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $SitePackages -Recurse -Force }
    } finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# A pure-Python package published only as source (.tar.gz): its package
# folder ($Copy, e.g. proxy_tools-0.1.0/proxy_tools) copied into
# site-packages. tar.exe ships with Windows 10 1803 and later (WSL 2 needs
# 2004 or later).
function Install-KohaSdistPackage {
    param([Parameter(Mandatory = $true)][string]$Archive, [Parameter(Mandatory = $true)][string]$Copy, [Parameter(Mandatory = $true)][string]$SitePackages)
    if ($Copy -notmatch '^[A-Za-z0-9._-]+/[A-Za-z0-9_]+$') { throw ('unexpected package folder {0}' -f $Copy) }
    $tmp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), 'koha-sdist-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    try {
        $tar = 'tar'
        if ($env:SystemRoot) {
            $t = [System.IO.Path]::Combine([string]$env:SystemRoot, 'System32', 'tar.exe')
            if (Test-Path -LiteralPath $t) { $tar = $t }
        }
        & $tar -xzf $Archive -C $tmp 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw ('tar could not unpack {0}' -f $Archive) }
        $src = [System.IO.Path]::Combine($tmp, ($Copy -replace '/', [System.IO.Path]::DirectorySeparatorChar))
        if (-not (Test-Path -LiteralPath $src)) { throw ('{0} is not in {1}' -f $Copy, $Archive) }
        if (-not (Test-Path -LiteralPath $SitePackages)) { New-Item -ItemType Directory -Path $SitePackages -Force | Out-Null }
        Copy-Item -LiteralPath $src -Destination $SitePackages -Recurse -Force
    } finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Pure: the lines of python3XX._pth. Paths are relative to the python
# folder: Lib\site-packages, bin\client (koha_nexus_win) and bin
# (nexus_core). "import site" lets the packages' .pth files work.
function Get-KohaPthLines {
    param([Parameter(Mandatory = $true)][string]$ZipName)
    return @($ZipName, '.', 'Lib\site-packages', '..\client', '..', 'import site')
}

function Set-KohaPythonPth {
    param([Parameter(Mandatory = $true)][string]$PythonDir)
    $pth = @(Get-ChildItem -LiteralPath $PythonDir -Filter 'python3*._pth' -File)
    if ($pth.Count -ne 1) { throw ('expected one python3*._pth in {0}, found {1}' -f $PythonDir, $pth.Count) }
    $zip = @(Get-ChildItem -LiteralPath $PythonDir -Filter 'python3*.zip' -File | Select-Object -First 1)
    if ($zip.Count -eq 0) { throw ('no python3*.zip in {0}' -f $PythonDir) }
    $text = (Get-KohaPthLines -ZipName $zip[0].Name) -join "`r`n"
    [System.IO.File]::WriteAllText($pth[0].FullName, $text + "`r`n", (New-Object System.Text.ASCIIEncoding))
}

# Builds the runtime in <Bin>\python.new from the lock, then swaps it in for
# <Bin>\python. Returns the python folder.
function Install-KohaPythonRuntime {
    param(
        [Parameter(Mandatory = $true)][string]$Bin,
        [Parameter(Mandatory = $true)][string]$Cache,
        [string]$LockPath = ([System.IO.Path]::Combine($Bin, 'client', 'runtime.lock.json'))
    )
    $lock = Read-KohaPythonLock -Path $LockPath
    $final = [System.IO.Path]::Combine($Bin, 'python')
    $new = $final + '.new'
    $old = $final + '.old'
    foreach ($d in $new, $old) { if (Test-Path -LiteralPath $d) { Remove-Item -LiteralPath $d -Recurse -Force } }
    $zip = Get-KohaCheckedDownload -Url $lock.python.url -Sha256 $lock.python.sha256 -Dir $Cache
    Expand-KohaZip -Zip $zip -Dest $new
    $site = [System.IO.Path]::Combine($new, 'Lib', 'site-packages')
    New-Item -ItemType Directory -Path $site -Force | Out-Null
    foreach ($p in @($lock.packages)) {
        $file = Get-KohaCheckedDownload -Url $p.url -Sha256 $p.sha256 -Dir $Cache
        if ($p.kind -eq 'wheel') { Install-KohaWheel -Wheel $file -SitePackages $site }
        elseif ($p.kind -eq 'sdist') { Install-KohaSdistPackage -Archive $file -Copy ([string]$p.copy) -SitePackages $site }
        else { throw ('runtime.lock.json: unknown kind {0} for {1}' -f $p.kind, $p.name) }
    }
    Set-KohaPythonPth -PythonDir $new
    if (Test-Path -LiteralPath $final) { Rename-Item -LiteralPath $final -NewName (Split-Path -Leaf $old) }
    Rename-Item -LiteralPath $new -NewName (Split-Path -Leaf $final)
    if (Test-Path -LiteralPath $old) { Remove-Item -LiteralPath $old -Recurse -Force -ErrorAction SilentlyContinue }
    return $final
}

# Imports everything the tray and the window need with the new runtime
# (no window opens: nothing is started). Returns ok, or what failed.
function Test-KohaPythonRuntime {
    param([Parameter(Mandatory = $true)][string]$PythonDir)
    $py = [System.IO.Path]::Combine($PythonDir, 'python.exe')
    if (-not (Test-Path -LiteralPath $py)) { return 'python.exe is missing' }
    $code = 'import nexus_core.monitor, koha_nexus_win.tray, koha_nexus_win.window, pystray, PIL, webview, windows_toasts; print("ok")'
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $out = & $py -c $code 2>&1 } finally { $ErrorActionPreference = $prev }
    $text = (@($out) | ForEach-Object { [string]$_ }) -join ' '
    if ($LASTEXITCODE -eq 0 -and $text.Trim() -eq 'ok') { return 'ok' }
    return $text.Trim()
}

Export-ModuleMember -Function Get-KohaSha256, Read-KohaPythonLock, Get-KohaDownloadName, Get-KohaCheckedDownload, Expand-KohaZip, Install-KohaWheel, Install-KohaSdistPackage, Get-KohaPthLines, Set-KohaPythonPth, Install-KohaPythonRuntime, Test-KohaPythonRuntime
