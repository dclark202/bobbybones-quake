# 1.8a: the planned restart at the save of update 150, done unattended (owner, 2026-11-11: "you can set it up so the second part starts
# automatically when the first part ends? It seems like it will be in the middle of the night"). Started hidden by
# start.ps1 -AutoRestart <minutes of phase 2>; no window. It only does what the card says is done by hand:
#   waits for keep\policy_u150_18a.pt and its optimizer (the ramp keeps them right after the save of update 150),
#   then at once: stop_18a.ps1 -Update 150 (the trainer alone; it refuses unless the run's policy.pt IS that save),
#   then:         start.ps1 -Restart -Minutes <n> (phase 2: INTENT_SWITCH 0, WEAPON_OWN 1; every check of start.ps1 runs again).
# It acts once and ends. It never retries a refused stop or start and never touches another save: a refusal is logged as
# "AUTO RESTART FAILED" in auto_restart.log (and the trainer, if still running, goes on in phase 1 as it was). It ends without acting if
# the trainer is gone for ten minutes before the mark is there. Nothing is deleted.
#   -Dry -RunDir <folder>   a test: the same waiting and checks on that folder, the two scripts only named, not run
param([Parameter(Mandatory = $true)][int]$Minutes, [switch]$Dry, [string]$RunDir = "", [int]$PollSeconds = 20)
$RUN = "duel_gru_1_8a"
$HERE = $PSScriptRoot
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$D = if ($RunDir) { $RunDir } else { Join-Path $ROOT "data\sim_runs\$RUN" }
$LOG = if ($Dry) { Join-Path $D "auto_restart_test.log" } else { Join-Path $HERE "auto_restart.log" }
function Log($s) { $l = (Get-Date -Format "MM-dd HH:mm:ss") + " " + $s; Add-Content -Path $LOG -Value $l -Encoding utf8; $l }
function Trainer { @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" }).Count }
if ($Minutes -le 60) { Log "give phase 2's length: -Minutes <n> (over 60): not armed"; exit 1 }
$PU = Join-Path $D "keep\policy_u150_18a.pt"; $OU = Join-Path $D "keep\opt_u150_18a.pt"
if ((Test-Path $PU) -and -not $Dry) { Log "keep\policy_u150_18a.pt is there already: the restart is not this script's to do (by hand: stop_18a.ps1, start.ps1 -Restart): not armed"; exit 1 }
Log ("armed: waiting for the save of update 150 (keep\policy_u150_18a.pt); then the trainer is stopped and started again in phase 2 for " + $Minutes + " minutes" + $(if ($Dry) { " (DRY: nothing is run)" } else { "" }))
$gone = $null
while ($true) {
    if ((Test-Path $PU) -and (Test-Path $OU)) { break }
    if (-not $Dry) {
        if ((Trainer) -eq 0) { if ($null -eq $gone) { $gone = Get-Date } elseif (((Get-Date) - $gone).TotalMinutes -ge 10) { Log "no trainer for ten minutes and no save of update 150: ended, nothing done"; exit 1 } }
        else { $gone = $null }
    }
    Start-Sleep -Seconds $PollSeconds
}
Start-Sleep -Seconds 3                                             # (the ramp's copy of the optimizer finished)
Log "the save of update 150 is kept: stopping the trainer"
if ($Dry) { Log ("DRY: would run stop_18a.ps1 -Update 150, then start.ps1 -Restart -Minutes " + $Minutes); exit 0 }
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $HERE "stop_18a.ps1") -Update 150 | ForEach-Object { Log ("stop: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "AUTO RESTART FAILED: stop_18a.ps1 refused (see the lines above and stop.log); nothing else done; the trainer, if it runs, goes on in phase 1"; exit 1 }
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $HERE "start.ps1") -Restart -Minutes $Minutes | ForEach-Object { Log ("start: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "AUTO RESTART FAILED: the trainer is stopped at the save of update 150 and start.ps1 -Restart refused (see the lines above and start.log). By hand: start.ps1 -Restart -Minutes <n>"; exit 1 }
if ((Trainer) -ne 1) { Log "AUTO RESTART FAILED: start.ps1 -Restart ended without a trainer running (see start.log)"; exit 1 }
Log "phase 2 is running (INTENT_SWITCH 0, WEAPON_OWN 1) from the save of update 150"
