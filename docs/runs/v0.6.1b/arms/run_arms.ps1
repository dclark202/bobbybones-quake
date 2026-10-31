# The entropy arms (owner, 2026-10-30: "Run the experiment"; docs/runs/v0.6.1b/DRIFT.md), one after the other on the graphics
# card: arm B (--ent-coef 0.002) first, then arm A (0.005, as v0.6.1b). Each from v0.6.1b's end (update 180), 130 minutes, with a
# watcher: checks every 10 updates against v0.6.1's end (comparable to v0.6.1b's own checks), every fourth against v0.6.0's end,
# and the behaviour panel. Refuses while a trainer runs or on a failed settings check. Nothing stops an arm early.
# Usage (PowerShell, detached):  powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.1b\arms\run_arms.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = Join-Path $env:USERPROFILE "anaconda3\python.exe"
$SR = Join-Path $ROOT "data\sim_runs"
$LOG = Join-Path $HERE "arms.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

foreach ($arm in "arm_v061b_ent002", "arm_v061b_ent005") {
    if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: $arm not started"; exit 1 }
    $CMD = Join-Path $HERE "train_$arm.cmd"
    & $PY (Join-Path $ROOT "tools\run\check_settings.py") $CMD --ref (Join-Path $ROOT "docs\runs\v0.6.1b\train.cmd") "--allow=--run,--minutes,--ent-coef" | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: $arm not started"; exit 1 }
    $R = Join-Path $SR $arm
    $WD = Join-Path $R "watch"
    New-Item -ItemType Directory -Force $WD | Out-Null
    $env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
    $env:CTRL_PREV = Join-Path $SR "duel_gru_v0_6_1\keep\policy_end_v061.pt"; $env:CTRL_PREV_LABEL = "v0.6.1's end"
    $env:CTRL_REF = Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt"; $env:CTRL_REF_LABEL = "v0.6.0's end (reference)"
    $env:CHECK_EVERY = "10"; $env:PANEL_RUN = $arm; $env:PANEL_CTRL = $env:CTRL_PREV
    $w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $arm -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
    $w.ProcessorAffinity = [IntPtr]0xC03C3
    Log "$arm started (watcher $($w.Id))"
    $t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $CMD -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -Wait
    Log ("$arm trainer ended: " + (Get-Content (Join-Path $SR "$arm.log") -Tail 1))
}
Log "both arms done (the watchers finish their checks on their own)"
