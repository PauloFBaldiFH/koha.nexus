# koha.nexus for Windows: the shutdown watcher (KohaEasy.ps1 Watcher).
# Started at sign-in by its own entry (HKCU Run, KohaEasyShutdownWatcher),
# with no console and no icon, apart from the tray: closing the Koha icon
# does not close it, and the keep-alive task starts it again within a minute
# while Koha runs if it crashed or was ended.
# When Windows shuts down, restarts or signs out while Koha runs, WSL would
# otherwise be stopped with MariaDB and Zebra still writing. The watcher:
#   1. on WM_QUERYENDSESSION holds the shutdown block reason ("Koha is
#      saving the database...") and answers TRUE: it never cancels a
#      shutdown;
#   2. on WM_ENDSESSION runs /usr/local/bin/koha-graceful-shutdown.sh inside
#      Debian through a wsl.exe with no console (Stop-KohaForSessionEnd),
#      at most $Cfg.SessionStopS seconds, then "wsl --shutdown";
#   3. releases the block reason, done or not, and Windows carries on.
# A power cut or a forced shutdown never gets here; the clean-stop guard
# inside Debian repairs Koha at the next start instead.
# Whether Koha runs is checked every 30 s in a background runspace (asking
# WSL at the end of the session could start Debian again, or be cut off).
# While the watcher runs, the tray leaves the end of the session to it.
# Windows PowerShell 5.1. Loaded by KohaEasy.ps1 (modules already imported).

Add-Type -AssemblyName System.Windows.Forms

$mutex = New-Object System.Threading.Mutex($false, (Get-KohaWatcherMutexName))
if (-not $mutex.WaitOne(0)) { return }

$cfg = Get-KohaConfig
$here = $PSScriptRoot
$CHECK_EVERY_MS = 30000

if (-not ('KohaShutdownWatcher' -as [type])) {
    Add-Type -ReferencedAssemblies System.Windows.Forms -Path (Join-Path $here 'KohaEasy.Watcher.cs')
}
$watcher = New-Object KohaShutdownWatcher (T 'Koha is saving the database and stopping its services safely...')
if (-not [KohaShutdownWatcher]::ShutDownFirst()) { Write-KohaLog 'watcher: the shutdown order could not be set' }
Write-KohaLog ('watcher: started for {0} (stop limit {1} s)' -f $cfg.Distro, $cfg.SessionStopS)

$iss = [System.Management.Automation.Runspaces.InitialSessionState]::CreateDefault()
$iss.ImportPSModule(@((Join-Path $here 'KohaEasy.Lang.psm1'), (Join-Path $here 'KohaEasy.Core.psm1')))
$pool = [runspacefactory]::CreateRunspace($iss)
$pool.Open()
$script:job = $null

# Koha runs when its distro does: the same test as the tray's icon.
function Start-Check {
    $ps = [powershell]::Create()
    $ps.Runspace = $pool
    [void]$ps.AddScript({ @(Get-KohaRunningDistros) -contains (Get-KohaConfig).Distro })
    return @{ PS = $ps; Handle = $ps.BeginInvoke() }
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 1000
$script:nextCheck = Get-Date
$timer.add_Tick({
        if ($null -ne $script:job) {
            if (-not $script:job.Handle.IsCompleted) { return }
            try {
                $res = @($script:job.PS.EndInvoke($script:job.Handle))
                $on = ($res.Count -gt 0 -and [bool]$res[-1])
                if ($on -ne $watcher.Armed) { Write-KohaLog ('watcher: Koha {0}' -f $(if ($on) { 'is running; a shutdown waits for its clean stop' } else { 'is not running' })) }
                $watcher.Armed = $on
            } catch {
                Write-KohaLog ('watcher check failed: ' + $_.Exception.Message)
            } finally {
                $script:job.PS.Dispose()
                $script:job = $null
            }
        }
        if ((Get-Date) -ge $script:nextCheck) {
            $script:nextCheck = (Get-Date).AddMilliseconds($CHECK_EVERY_MS)
            $script:job = Start-Check
        }
    })
$timer.Start()

$watcher.add_SessionQuery({ Write-KohaLog ('watcher: Windows asks to end the session (Koha running: {0})' -f $watcher.Armed) })

# The session ends: the stop runs in its own runspace while this thread
# keeps answering Windows; the reason is released when this returns.
$watcher.add_SessionEnding({
        $timer.Stop()
        $rs = [runspacefactory]::CreateRunspace($iss)
        $rs.Open()
        $ps = [powershell]::Create()
        $ps.Runspace = $rs
        [void]$ps.AddScript({
                Stop-KohaForSessionEnd -RunDetached { param($CommandLine, $TimeoutMs) [KohaShutdownWatcher]::RunDetached($CommandLine, $TimeoutMs) }
            })
        $h = $ps.BeginInvoke()
        $deadline = (Get-Date).AddSeconds((Get-KohaSessionStopDeadline))
        while (-not $h.IsCompleted -and (Get-Date) -lt $deadline) {
            [System.Windows.Forms.Application]::DoEvents()
            Start-Sleep -Milliseconds 100
        }
        if ($h.IsCompleted) {
            $how = @($ps.EndInvoke($h))
            Write-KohaLog ('watcher: clean stop before the end of the session: {0}' -f ($how -join ' '))
        } else {
            Write-KohaLog 'watcher: the clean stop did not finish in time; Windows carries on'
        }
    })

try {
    [System.Windows.Forms.Application]::Run()
} finally {
    $timer.Stop()
    $watcher.Dispose()
    $pool.Close()
    $mutex.ReleaseMutex()
}
