# b1.2c's start (owner, 2026-11-01; docs/runs/b1.2/b1.2c/CARD.md): from b1.1, widened: every small health and armor item as an input and the health and armor table, at once; the firing costs, contact freedom, the jerk cost by the ramp.
# Refuses unless: no trainer runs; b1.1 and its optimizer are there, no head, lock 8 s; the settings check passes against b1.2b's command; items_check.log and ramp_test.log, and b1.2b's ident.log and smoke.log, end ALL PASSED; the run folder is new; the widened network answers as b1.1.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.2\b1.2c\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_b1_1a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_b1_2c"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
$II = Join-Path $ROOT "tools\items_init.py"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_b1.1.pt"; $OPTF = Join-Path $K0 "opt_b1.1.pt"; $REF = Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt"
foreach ($p in $END, $OPTF, $REF) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.2\b1.2b\train.cmd") "--allow=--run,--minutes,--gate-open,--gate-start,--opt-small-items,SM_ITEMS" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
foreach ($f in (Join-Path $HERE "items_check.log"), (Join-Path $HERE "ramp_test.log"), (Join-Path $ROOT "docs\runs\b1.2\b1.2b\ident.log"), (Join-Path $ROOT "docs\runs\b1.2\b1.2b\smoke.log")) { if (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 1) -like "*ALL PASSED*")) { Log "$f has not passed: not started"; exit 1 } }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"; $env:CUDA_VISIBLE_DEVICES = "-1"; $env:OMP_NUM_THREADS = "1"
& $PY $II widen $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
$same = & $PY $II same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
if (-not ($same -match "actions that differ: 0$")) { Log "THE WIDENED NETWORK ANSWERS DIFFERENTLY: not started (its policy.pt left for a look)"; exit 1 }
Copy-Item $OPTF (Join-Path $R1 "opt.pt")                 # (the trainer carries it over: --opt-small-items)
& $PY $II widen $END (Join-Path $R1 "snapshots\anchor_b11.pt") | ForEach-Object { Log $_ }
& $PY $II widen $REF (Join-Path $R1 "snapshots\anchor_v060_end.pt") | ForEach-Object { Log $_ }
# the checks' controls: the widened networks (docs/INPUTS.csv lists 980 inputs: tools/duel_eval.py refuses a network of 868), each proved to answer as the original
$CK = Join-Path $R1 "keep\control_b11.pt"; $CR = Join-Path $R1 "keep\control_v060_end.pt"
Copy-Item (Join-Path $R1 "snapshots\anchor_b11.pt") $CK
Copy-Item (Join-Path $R1 "snapshots\anchor_v060_end.pt") $CR
foreach ($pair in @(@($END, $CK), @($REF, $CR))) { $same = & $PY $II same $pair[0] $pair[1] | ForEach-Object { Log $_ }; if (-not ($same -match "actions that differ: 0$")) { Log ("THE WIDENED CONTROL ANSWERS DIFFERENTLY: " + $pair[1] + ": not started"); exit 1 } }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); assert d.get('WIN_ADD', 0) > 0 and d.get('WIN_W') == 0.0 and d.get('FADE_V') == 0.0, d; d.update(INTENT_TEACH_W=1.0, VALUE_WARM=0, BRAIN_FADE=1.0, LEVEL_PULL=1.0, INTENT_HOLD=8.0, ITEM_RATE_HP=0.0025, ITEM_RATE_AR=0.002, COST_FIRE_W=1.0, COST_JERK_W=1.0, CONTACT_FREE=0.0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
Remove-Item Env:CUDA_VISIBLE_DEVICES, Env:OMP_NUM_THREADS
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_b12c.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_b12c.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from b1.1 widened")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (b1.1)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "v0.6.0's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_b12c.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (the table and the new inputs from the start; fourteen steps; held only at a check of 40% or less) | self-play logger " + $s.Id + " | no guard")
