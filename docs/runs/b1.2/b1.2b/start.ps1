# b1.2b's start (owner, 2026-11-01; docs/runs/b1.2/b1.2b/CARD.md): from b1.1, no head: the health and armor table at once; the firing costs, contact freedom, the jerk cost.
# Refuses unless: no trainer runs; b1.1 and its optimizer are there, with no head and the lock at 8 s; the settings check passes against b1.1a's command; ident.log, ramp_test.log and smoke.log end ALL PASSED; the run folder is new.
# Then the trainer, the watcher, the ramp, the self-play logger. Nothing stops the run.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.2\b1.2b\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_b1_1a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_b1_2b"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_b1.1.pt"; $OPTF = Join-Path $K0 "opt_b1.1.pt"; $REF = Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt"
foreach ($p in $END, $OPTF, $REF) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.1\b1.1a\train.cmd") "--allow=--run,--minutes,ITEM_RATE_HP,ITEM_RATE_AR" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
foreach ($n in "ident.log", "ramp_test.log", "smoke.log") { $f = Join-Path $HERE $n; if (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 1) -like "*ALL PASSED*")) { Log "$n has not passed: not started"; exit 1 } }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$env:CUDA_VISIBLE_DEVICES = "-1"; $env:OMP_NUM_THREADS = "1"
& $PY -c "import json, sys, torch; d = json.load(open(sys.argv[1])); ck = torch.load(sys.argv[2], map_location='cpu', weights_only=False); ev = ck.get('env_vars') or {}; g = ((ck.get('belief') or {}).get('fade') or {}).get('g', 0.0); assert ck.get('head2') is None, 'a head'; assert float(ev.get('INTENT_HOLD', -1)) == 8.0, ev.get('INTENT_HOLD'); assert float(g) == 1.0 and float(ev.get('LEVEL_PULL', 0)) == 1.0, (g, ev.get('LEVEL_PULL')); assert d.get('WIN_ADD', 0) > 0 and d.get('WIN_W') == 0.0 and d.get('FADE_V') == 0.0, d; d.update(INTENT_TEACH_W=1.0, VALUE_WARM=0, BRAIN_FADE=1.0, LEVEL_PULL=1.0, INTENT_HOLD=8.0, ITEM_RATE_HP=0.0025, ITEM_RATE_AR=0.002, COST_FIRE_W=1.0, COST_JERK_W=1.0, CONTACT_FREE=0.0); json.dump(d, open(sys.argv[3], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") $END (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
Remove-Item Env:CUDA_VISIBLE_DEVICES, Env:OMP_NUM_THREADS
Copy-Item $END (Join-Path $R1 "policy.pt")
Copy-Item $OPTF (Join-Path $R1 "opt.pt")
Copy-Item $END (Join-Path $R1 "keep\policy_start_b12b.pt")
Copy-Item $OPTF (Join-Path $R1 "keep\opt_start_b12b.pt")
Copy-Item $END (Join-Path $R1 "snapshots\anchor_b11.pt")
Copy-Item $REF (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from b1.1")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $END; $env:CTRL_PREV_LABEL = "the start (b1.1)"
$env:CTRL_REF = $REF; $env:CTRL_REF_LABEL = "v0.6.0's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $END; $env:CHECK_RULE = "0"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_b12b.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (the table from the start; fourteen steps; held only at a check of 40% or less) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
