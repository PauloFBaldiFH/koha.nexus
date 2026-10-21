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