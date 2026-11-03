# v0.6.1's fade of the pull toward level (owner, 2026-10-29: "starting at noon we fade pull to level out, one 0.01 step per 10
# updates"; "fold it in at the first good spot around noon"). It refuses (exit 2: try again in a few minutes) unless the watcher
# is idle: the last save copied into keep/ and no check or panel game running (between saves is fine: the restarted watcher takes
# the next save as usual, and ramp_live waits for it).
# Then: restarts the watcher alone (the same settings as start.ps1; its checks and panels now play each save at its own pull,
# tools/run/panel.py settings(ps, pol)) and starts tools/run/ramp_live.py: the next save kept as keep/policy_prelevel_v061.pt,
# then LEVEL_PULL 0.95 -> 1.0 by 0.01 right after each save. The trainer is not touched.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.1\fade_level.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$RUN = "duel_gru_v0_6_1"
$R1 = Join-Path $ROOT "data\sim_runs\$RUN"
$R0 = Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_0"
$WD = Join-Path $R1 "watch"
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

$P = Get-CimInstance Win32_Process
$tr = $P | Where-Object { $_.CommandLine -like "*train_duel_rnn*$RUN*" -and $_.Name -eq "python.exe" }
if (-not $tr) { Log "fade_level: no v0.6.1 trainer: not started"; exit 1 }
if ($P | Where-Object { $_.CommandLine -like "*ramp_live*$RUN*" }) { Log "fade_level: ramp_live already runs: nothing done"; exit 1 }
$busy = $P | Where-Object { ($_.CommandLine -like "*duel_eval.py*$RUN*" -or $_.CommandLine -like "*dump_eval.py*$RUN*") -and $_.CommandLine -notlike "*selfplay*" }
$n = (Get-Content (Join-Path $R1 "metrics.jsonl") | Measure-Object -Line).Lines
$saved = Test-Path (Join-Path $R1 ("keep\policy_{0}.pt" -f ([math]::Floor($n / 10) * 10)))
if ($busy -or -not $saved) { Log ("fade_level: not idle (update {0}, checks running {1}, last save kept {2}): try at the next save" -f $n, [bool]$busy, $saved); exit 2 }
if ((Get-Content (Join-Path $R1 "live.json") -Raw) -match '"LEVEL_PULL"') { Log "fade_level: live.json already sets LEVEL_PULL: nothing done"; exit 1 }

$w = $P | Where-Object { $_.CommandLine -like "*watch.py*$RUN*" -and $_.Name -eq "python.exe" }
foreach ($x in $w) { Stop-Process -Id $x.ProcessId -Confirm:$false; Log ("fade_level: watcher {0} stopped (idle at update {1})" -f $x.ProcessId, $n) }
$env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$env:CTRL_PREV = Join-Path $R0 "keep\policy_end_v060.pt"; $env:CTRL_PREV_LABEL = "v0.6.0's end"
$env:CTRL_REF = Join-Path $ROOT "data\sim_runs\duel_gru_v0_4_2\keep\policy_end_v042.pt"; $env:CTRL_REF_LABEL = "v0.4.2b's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $env:CTRL_PREV
$stamp = Get-Date -Format "HHmm"
$w2 = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout_$stamp.log") -RedirectStandardError (Join-Path $WD "watch_stderr_$stamp.log")
$w2.ProcessorAffinity = [IntPtr]0xC03C3
Log ("fade_level: watcher restarted: {0} (checks and panels at each save's own pull)" -f $w2.Id)
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\ramp_live.py"), $RUN, "LEVEL_PULL", "0.95", "1.0", "0.01", "--keep-as", "policy_prelevel_v061.pt" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_live_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_live_stderr.log")
Log ("fade_level: ramp_live {0}: the next save kept as keep\policy_prelevel_v061.pt, then LEVEL_PULL 0.96 .. 1.0, one 0.01 right after each save" -f $r.Id)
