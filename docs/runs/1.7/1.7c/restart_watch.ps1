# 1.7c: restart the watcher alone (2026-11-07 22:3x: the table control's games were tagged "prev" because the control is the same file as
# the previous best; watch.py now tags them by a flag). The trainer, the ramp and the self-play logger are not touched. The same
# environment as start.ps1 gave the watcher. Usage: powershell -ExecutionPolicy Bypass -File docs\runs\1.7\1.7c\restart_watch.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$RUN = "duel_gru_1_7c"
$R1 = Join-Path $ROOT "data\sim_runs\$RUN"
$WD = Join-Path $R1 "watch"
$CK = Join-Path $R1 "keep\control_17a.pt"; $CR = Join-Path $R1 "keep\control_b12d.pt"
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*watch.py $RUN*" } | Measure-Object).Count -gt 0) { Write-Output "a watcher for $RUN still runs: not started"; exit 1 }
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (1.7a's update 90) plain"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.2d's end (reference)"
$env:CTRL_TABLE = $CK; $env:CTRL_TABLE_LABEL = "the start (1.7a's update 90) under the table"
$env:CHECK_TABLE_GAMES = "10"
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"
$env:CHECK_CYPHER = "1"
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout_2.log") -RedirectStandardError (Join-Path $WD "watch_stderr_2.log")
$w.ProcessorAffinity = [IntPtr]0x3C3C
Write-Output ("watcher restarted: " + $w.Id)
