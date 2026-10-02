# Koha Easy Installer for Windows: Shut down the PC safely (KohaEasy.ps1
# SafeShutdown, from the Start menu, the tray and the Koha window).
# The librarian's one click at the end of the day: Koha's services stop in
# order, everything is written to disk and WSL closes Debian's virtual
# disk, each step ticked off on screen, and only then is Windows asked to
# shut down (or restart). Nothing races Windows here, unlike the tray's
# end-of-session stop, which has to work inside the time Windows gives.
# When the stop does not finish in time, Windows shuts down anyway and the
# clean-stop guard inside Debian checks and repairs Koha at the next start.
# The stop runs in a background runspace, so the window keeps answering.
# Windows PowerShell 5.1. Loaded by KohaEasy.ps1 (modules imported).

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$title = T 'Shut down the PC safely'
$mutex = New-Object System.Threading.Mutex($false, 'Local\KohaEasyShutdown')
if (-not $mutex.WaitOne(0)) {
    Show-KohaOpenWindow $title | Out-Null
    return
}
Set-KohaProcessAppId | Out-Null

$here = $PSScriptRoot
$W = 460
function New-Rgb { param([int]$R, [int]$G, [int]$B) return [System.Drawing.Color]::FromArgb($R, $G, $B) }
$theme = @{
    Bg          = New-Rgb 24 24 27
    Text        = New-Rgb 244 244 245
    Muted       = New-Rgb 161 161 170
    Green       = New-Rgb 34 197 94
    Red         = New-Rgb 239 68 68
    Amber       = New-Rgb 245 158 11
    Grey        = New-Rgb 113 113 122
    Accent      = New-Rgb 37 99 235
    AccentHover = New-Rgb 59 130 246
    Button      = New-Rgb 48 48 55
    ButtonHover = New-Rgb 63 63 72
}
$fontUi = New-Object System.Drawing.Font('Segoe UI', 9.5)
$fontTitle = New-Object System.Drawing.Font('Segoe UI Semibold', 12)
$fontGlyph = New-Object System.Drawing.Font('Segoe UI Symbol', 10)

function New-Text {
    param([string]$Text, $Font = $fontUi, $Color = $theme.Text, [int]$Width = 0)
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $Text
    $l.Font = $Font
    $l.ForeColor = $Color
    $l.AutoSize = $true
    if ($Width -gt 0) { $l.MaximumSize = New-Object System.Drawing.Size($Width, 0) }
    $l.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 6)
    return $l
}

function New-Button {
    param([string]$Text, [bool]$Primary, [scriptblock]$OnClick)
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $Text
    $b.Font = $fontUi
    $b.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $b.FlatAppearance.BorderSize = 0
    $b.UseVisualStyleBackColor = $false
    $b.AutoSize = $true
    $b.AutoSizeMode = [System.Windows.Forms.AutoSizeMode]::GrowAndShrink
    $b.Padding = New-Object System.Windows.Forms.Padding(10, 5, 10, 5)
    $b.Margin = New-Object System.Windows.Forms.Padding(8, 0, 0, 0)
    $b.ForeColor = $theme.Text
    $b.BackColor = $theme.Button
    $b.FlatAppearance.MouseOverBackColor = $theme.ButtonHover
    if ($Primary) {
        $b.BackColor = $theme.Accent
        $b.FlatAppearance.MouseOverBackColor = $theme.AccentHover
        $b.ForeColor = [System.Drawing.Color]::White
    }
    $b.add_Click($OnClick)
    return $b
}

$form = New-Object System.Windows.Forms.Form
$form.Text = $title
$form.BackColor = $theme.Bg
$form.ForeColor = $theme.Text
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedSingle
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$form.AutoSize = $true
$form.AutoSizeMode = [System.Windows.Forms.AutoSizeMode]::GrowAndShrink
$form.TopMost = $true
$form.KeyPreview = $true
$ico = Get-KohaIcon -Path (Join-Path $here 'koha.ico') -Exe (Join-Path $here 'KohaEasy.exe')
if ($ico) { $form.Icon = $ico }

$root = New-Object System.Windows.Forms.TableLayoutPanel
$root.ColumnCount = 1
$root.AutoSize = $true
$root.Padding = New-Object System.Windows.Forms.Padding(20, 16, 20, 16)
[void]$root.Controls.Add((New-Text $title $fontTitle))
$intro = New-Text (T 'Koha stops step by step and saves everything to disk, then Windows shuts down. Anyone using the catalog will be disconnected.') $fontUi $theme.Muted $W
$intro.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 12)
[void]$root.Controls.Add($intro)

# One row per step: a mark (waiting, running, done) and the step in words.
$steps = @(Get-KohaStopSteps)
$grid = New-Object System.Windows.Forms.TableLayoutPanel
$grid.ColumnCount = 2
$grid.AutoSize = $true
$grid.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 10)
$marks = @()
for ($i = 0; $i -lt $steps.Count; $i++) {
    $m = New-Text ([string][char]0x25CB) $fontGlyph $theme.Grey
    $m.Margin = New-Object System.Windows.Forms.Padding(0, 2, 8, 4)
    $t = New-Text $steps[$i] $fontUi $theme.Muted ($W - 30)
    $t.Margin = New-Object System.Windows.Forms.Padding(0, 3, 0, 4)
    [void]$grid.Controls.Add($m, 0, $i)
    [void]$grid.Controls.Add($t, 1, $i)
    $marks += , @{ Mark = $m; Text = $t }
}
[void]$root.Controls.Add($grid)

$lblStatus = New-Text '' $fontUi $theme.Muted $W
$lblStatus.Margin = New-Object System.Windows.Forms.Padding(0, 0, 0, 12)
[void]$root.Controls.Add($lblStatus)

$buttons = New-Object System.Windows.Forms.FlowLayoutPanel
$buttons.AutoSize = $true
$buttons.FlowDirection = [System.Windows.Forms.FlowDirection]::RightToLeft
$buttons.Dock = [System.Windows.Forms.DockStyle]::Fill
$buttons.Margin = New-Object System.Windows.Forms.Padding(0)
$btnCancel = New-Button (T 'Cancel') $false { $form.Close() }
$btnRestart = New-Button (T 'Restart safely') $false { Start-PowerOff $true }
$btnShutdown = New-Button (T 'Shut down safely') $true { Start-PowerOff $false }
foreach ($b in $btnCancel, $btnRestart, $btnShutdown) { [void]$buttons.Controls.Add($b) }
[void]$root.Controls.Add($buttons)
$form.Controls.Add($root)
$form.AcceptButton = $btnShutdown
$form.CancelButton = $btnCancel

# ----------------------------------------------------------------------
# The stop, in the background
# ----------------------------------------------------------------------
$iss = [System.Management.Automation.Runspaces.InitialSessionState]::CreateDefault()
$iss.ImportPSModule(@((Join-Path $here 'KohaEasy.Lang.psm1'), (Join-Path $here 'KohaEasy.Core.psm1')))
$rs = [runspacefactory]::CreateRunspace($iss)
$rs.Open()
$progress = [hashtable]::Synchronized(@{ Step = 0 })
$script:job = $null
$script:restart = $false
$script:powerOffAt = $null
$script:spin = 0
$spinner = @([char]0x25D0, [char]0x25D3, [char]0x25D1, [char]0x25D2)

function Start-PowerOff {
    param([bool]$Restart)
    if ($null -ne $script:job) { return }
    $script:restart = $Restart
    foreach ($b in $btnShutdown, $btnRestart, $btnCancel) { $b.Enabled = $false }
    $lblStatus.ForeColor = $theme.Amber
    $lblStatus.Text = T 'Stopping Koha...'
    $ps = [powershell]::Create()
    $ps.Runspace = $rs
    [void]$ps.AddScript({
            param($Progress)
            Stop-KohaForPowerOff -OnStep ({ param($n) $Progress.Step = $n }.GetNewClosure())
        }).AddArgument($progress)
    $script:job = @{ PS = $ps; Handle = $ps.BeginInvoke() }
}

function Set-Marks {
    param([int]$Current, [bool]$AllDone)
    for ($i = 0; $i -lt $marks.Count; $i++) {
        $n = $i + 1
        $r = $marks[$i]
        if ($AllDone -or $n -lt $Current) {
            $r.Mark.Text = [string][char]0x2713
            $r.Mark.ForeColor = $theme.Green
            $r.Text.ForeColor = $theme.Text
        } elseif ($n -eq $Current) {
            $r.Mark.Text = [string]$spinner[$script:spin]
            $r.Mark.ForeColor = $theme.Amber
            $r.Text.ForeColor = $theme.Text
        } else {
            $r.Mark.Text = [string][char]0x25CB
            $r.Mark.ForeColor = $theme.Grey
            $r.Text.ForeColor = $theme.Muted
        }
    }
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 200
$timer.add_Tick({
        # Windows was asked to shut down: this window goes a few seconds
        # later (if a program with unsaved work stops Windows, Koha starts
        # again on its own within a minute).
        if ($null -ne $script:powerOffAt) {
            if ((Get-Date) -ge $script:powerOffAt.AddSeconds(4)) { $timer.Stop(); $form.Close() }
            return
        }
        if ($null -eq $script:job) { return }
        if (-not $script:job.Handle.IsCompleted) {
            $script:spin = ($script:spin + 1) % 4
            $step = [int]$progress.Step
            if ($step -lt 1) { $step = 1 }
            Set-Marks $step $false
            $lblStatus.Text = (T 'Step {0} of {1}') -f $step, $marks.Count
            return
        }
        $how = $null
        $err = $null
        try {
            $res = @($script:job.PS.EndInvoke($script:job.Handle))
            if ($res.Count -gt 0) { $how = [string]$res[-1] }
            if (-not $how -and $script:job.PS.Streams.Error.Count -gt 0) { $err = $script:job.PS.Streams.Error[0].Exception.Message }
        } catch {
            $err = $_.Exception.Message
        } finally {
            $script:job.PS.Dispose()
            $script:job = $null
        }
        if ($err) {
            # Nothing is shut down after an error the stop could not report:
            # the librarian decides again.
            Write-KohaLog ('safe shutdown failed: ' + $err)
            $lblStatus.ForeColor = $theme.Red
            $lblStatus.Text = (T 'Koha could not be stopped: {0}') -f $err
            foreach ($b in $btnShutdown, $btnRestart, $btnCancel) { $b.Enabled = $true }
            return
        }
        Set-Marks 0 $true
        $go = T 'Windows is shutting down...'
        if ($script:restart) { $go = T 'Windows is restarting...' }
        switch ($how) {
            'forced' {
                $lblStatus.ForeColor = $theme.Amber
                $lblStatus.Text = (T 'Koha did not stop in time. Windows shuts down anyway; Koha checks and repairs itself at the next start.') + "`n" + $go
            }
            'not_running' {
                $lblStatus.ForeColor = $theme.Green
                $lblStatus.Text = (T 'Koha was not running.') + "`n" + $go
            }
            default {
                $lblStatus.ForeColor = $theme.Green
                $lblStatus.Text = (T 'Koha stopped cleanly.') + "`n" + $go
            }
        }
        $form.Refresh()
        try {
            Invoke-KohaPowerOff -Restart:$script:restart
        } catch {
            Write-KohaLog ('shutdown.exe failed: ' + $_.Exception.Message)
            $lblStatus.ForeColor = $theme.Red
            $lblStatus.Text = (T 'Windows could not be shut down: {0}') -f $_.Exception.Message
            $btnCancel.Text = T 'Close'
            $btnCancel.Enabled = $true
            return
        }
        $script:powerOffAt = Get-Date
    })

# A stop in progress is never cut short by closing the window.
$form.add_FormClosing({
        param($s, $e)
        if ($null -ne $script:job) { $e.Cancel = $true }
    })
$form.add_Shown({ $form.Activate(); $timer.Start() })

try {
    [System.Windows.Forms.Application]::Run($form)
} finally {
    $timer.Stop()
    $rs.Close()
    $mutex.ReleaseMutex()
}
