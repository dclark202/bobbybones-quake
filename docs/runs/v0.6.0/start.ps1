# v0.6.0's start (retrain of 2026-10-28, owner: "restart the v0.6.0 training exactly as it was last night"; then "running until 9pm":
# --minutes 535 from ~12:05; B data from saves 40 to 120 every 20, 6 games a map = 300 games, fitted after the run).
# Refuses unless: the settings check passes against last night's command (only --minutes and the brain pack allowed to differ),
# the run folder and the brain's pro pack are there, and no trainer runs. Then: the trainer (train.cmd), the watcher (checks
# against v0.4.2b's end every 20 updates), the self-play logger for B. No guard: the run is never stopped automatically.
# Usage (PowerShell, from anywhere):  powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.0\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { "C:\Users\dacla\anaconda3\python.exe" }
$RUN = "duel_gru_v0_6_0"
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $HERE "reference_20261027.cmd") "--allow=--minutes,--brain-human,--brain-human-mix" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
foreach ($p in "data\sim_runs\$RUN\policy.pt", "data\sim_runs\$RUN\opt.pt", "data\sim_runs\brainppl\pack_demo\obs.npy", "data\sim_runs\move_v17_look\policy.npz", "data\maps\nav_bloodrun_sim.json") {
    if (-not (Test-Path (Join-Path $ROOT $p))) { Log "MISSING ${p}: not started"; exit 1 }
}
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }

$env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id)
$WD = Join-Path $ROOT "data\sim_runs\$RUN\watch"
New-Item -ItemType Directory -Force $WD | Out-Null
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "20", "--from", "40", "--games", "6" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
