# koha.nexus for Windows: translations.
# Reads the panel's own dictionaries (lang\<code>.cache, one
# "base64(English)|base64(translation)" entry per line), so the Windows texts
# are translated once, in the same files, and checked by the same test (P13).
# Windows PowerShell 5.1 compatible. Saved as UTF-8 with BOM.

Set-StrictMode -Version 2.0

$script:KeiDictionary = @{}
$script:KeiLanguage = 'en'

# Windows culture name (pt-BR, es-ES, fil-PH...) to dictionary code, with the
# same rules as normalize_panel_language in the installer.
function ConvertTo-KeiLanguageCode {
    param([string]$Culture)
    $c = ([string]$Culture).ToLowerInvariant()
    $two = ($c -split '[-_]')[0]
    switch ($two) {
        ''    { return 'en' }
        'fil' { return 'tl' }
        'nb'  { return 'no' }
        'nn'  { return 'no' }
        default { return $two }
    }
}

# Loads lang\<code>.cache from $LangDir. English (or a missing dictionary)
# leaves every text as written.
function Import-KeiLanguage {
    param(
        [Parameter(Mandatory = $true)][string]$LangDir,
        [string]$Culture = (Get-UICulture).Name
    )
    $script:KeiDictionary = @{}
    $script:KeiLanguage = ConvertTo-KeiLanguageCode $Culture
    if ($script:KeiLanguage -eq 'en') { return }
    $file = Join-Path $LangDir ($script:KeiLanguage + '.cache')
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { return }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    foreach ($line in [System.IO.File]::ReadAllLines($file, $utf8)) {
        if ($line.StartsWith('#')) { continue }
        $parts = $line.Split('|')
        if ($parts.Count -ne 2) { continue }
        try {
            $key = $utf8.GetString([Convert]::FromBase64String($parts[0]))
            $val = $utf8.GetString([Convert]::FromBase64String($parts[1]))
        } catch { continue }
        if ($val.Trim().Length -gt 0) { $script:KeiDictionary[$key] = $val }
    }
}

# The Koha folder of this PC (C:\Koha, or C:\KohaEasy for an install made
# before the rename). Texts name it as C:\KohaEasy, so the dictionaries keep
# their entries; T shows the real folder.
$script:KeiRoot = ''
function Set-KeiRoot { param([string]$Path) $script:KeiRoot = [string]$Path }

# Translated text. Placeholders are {0}, {1}...: a translation that lost or
# added one is ignored, so "-f" never throws on a bad dictionary entry.
function T {
    param([Parameter(Mandatory = $true, Position = 0)][string]$Text)
    $out = $Text
    if ($script:KeiDictionary.ContainsKey($Text)) {
        $tr = $script:KeiDictionary[$Text]
        $want = @([regex]::Matches($Text, '\{\d+\}') | ForEach-Object { $_.Value } | Sort-Object -Unique)
        $have = @([regex]::Matches($tr, '\{\d+\}') | ForEach-Object { $_.Value } | Sort-Object -Unique)
        if (($want -join ',') -eq ($have -join ',')) { $out = $tr }
    }
    if ($script:KeiRoot -and $script:KeiRoot -ne 'C:\KohaEasy') { $out = $out.Replace('C:\KohaEasy', $script:KeiRoot) }
    return $out
}

function Get-KeiLanguage { return $script:KeiLanguage }

Export-ModuleMember -Function ConvertTo-KeiLanguageCode, Import-KeiLanguage, T, Get-KeiLanguage, Set-KeiRoot
