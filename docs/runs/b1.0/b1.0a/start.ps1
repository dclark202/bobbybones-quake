# b1.0a's start (owner, 2026-10-31; docs/runs/b1.0a/CARD.md): v0.6.0's end, win chance pay added on top of the table (live WIN_ADD, ramp_win.py). Refuses unless:
# no trainer runs; the code and the judge are there; the settings check passes against v0.6.0's command; ident.log and smoke.log end ALL PASSED; the run folder is
# new. Then the trainer, the watcher (checks against v0.6.0's end only, every 10 updates), the ramp, the self-play logger. Nothing stops the run.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.0\b1.0a\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$K0 = Join-Path $SR "duel_gru_v0_6_0\keep"
$START = Join-Path $K0 "policy_end_v060.pt"
$RUN = "duel_gru_b1_0a"
$R1 = Join-Path $SR $RUN
$JUDGE = Join-Path $SR "judge\judge_v060_wpn.npz"
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\duel_env_ffa.py") -Pattern "WIN_ADD" -SimpleMatch -Quiet)) { Log "the code has no WIN_ADD: not started"; exit 1 }
foreach ($p in $START, (Join-Path $K0 "opt_end_v060.pt"), $JUDGE, (Join-Path $SR "duel_gru_v0_4_2\keep\policy_end_v042.pt")) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY -c "import sys, json, numpy as np; m = json.loads(str(np.load(sys.argv[1])['meta'])); print('judge axioms_ok', m.get('axioms_ok'), 'logloss', m.get('logloss')); sys.exit(0 if m.get('axioms_ok') else 1)" $JUDGE | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE JUDGE FAILED ITS AXIOM CHECK: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\v0.6.0\train.cmd") "--allow=--run,--minutes,WIN_JUDGE,WIN_END,WV_START,CTL_START" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
foreach ($n in "ident.log", "smoke.log") {
    $f = Join-Path $HERE $n
    if (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 1) -like "*ALL PASSED*")) { Log "$n has not passed: not started"; exit 1 }
}
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
Copy-Item $START (Join-Path $R1 "policy.pt")
Copy-Item (Join-Path $K0 "opt_end_v060.pt") (Join-Path $R1 "opt.pt")
Copy-Item $START (Join-Path $R1 "keep\policy_start_b10a.pt")
Copy-Item $START (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $SR "duel_gru_v0_4_2\keep\policy_end_v042.pt") (Join-Path $R1 "snapshots\anchor_v042_end.pt")
Copy-Item (Join-Path $SR "duel_gru_v0_6_0\live_settings.env") (Join-Path $R1 "live_settings.env")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(WIN_ADD=0.0, WIN_W=0.0, FADE_V=0.0, WIN_GAIN=1.0, WIN_SHAPE_K=0.0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $SR "duel_gru_v0_6_0\live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }

$env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id)
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $START; $env:CTRL_PREV_LABEL = "v0.6.0's end"
$env:CTRL_REF = $START; $env:CTRL_REF_LABEL = "v0.6.0's end"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $START; $env:CHECK_RULE = "0"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_win.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (WIN_ADD 0 -> 0.15 -> 0.33; held only at a check of 40% or less) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
