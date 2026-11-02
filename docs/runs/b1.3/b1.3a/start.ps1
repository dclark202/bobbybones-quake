# b1.3a's start (owner, 2026-11-01; docs/runs/b1.3/b1.3a/CARD.md): the strategy head opens, as the only learner of his target. NOT RUN YET.
# Refuses unless: no trainer runs; b1.2c's end and its optimizer are there; the settings check passes against b1.2c's command; trial.log ends ALL PASSED; the run folder is new; the start with the head, shut and with its whole path run, answers exactly as the save.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.3\b1.3a\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_b1_2c"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_b1_3a"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_b12c.pt"; $OPTF = Join-Path $K0 "opt_end_b12c.pt"; $REF = Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt"
foreach ($p in $END, $OPTF, $REF) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.2\b1.2c\train.cmd") "--allow=--run,--minutes,--head2,--head2-cap,--head2-ctrl-src,--head2-gate,--head2-open,--head2-start,--head2-pay,--head2-sole,H2_START" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
$f = Join-Path $HERE "trial.log"
if (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 1) -like "*ALL PASSED*")) { Log "trial.log has not passed: not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"; $env:OPENBLAS_NUM_THREADS = "1"; $env:OMP_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$H2I = Join-Path $ROOT "tools\head2_init.py"
$T1 = Join-Path $R1 "watch\start_head_gate1.pt"
& $PY $H2I add $END $T1 --gate 1 --ctrl-src belief | ForEach-Object { Log $_ }
$same = & $PY $H2I same $END $T1 | ForEach-Object { Log $_ }
if (-not ($same -match "actions that differ: 0$")) { Log "THE HEAD (its whole path run) CHANGES HIS ANSWERS: not started"; exit 1 }
& $PY $H2I add $END (Join-Path $R1 "policy.pt") --gate 0 --ctrl-src belief --opt $OPTF (Join-Path $R1 "opt.pt") | ForEach-Object { Log $_ }
$same = & $PY $H2I same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
if (-not ($same -match "actions that differ: 0$")) { Log "THE START NETWORK ANSWERS DIFFERENTLY: not started (its policy.pt left for a look; nothing deleted)"; exit 1 }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); assert d.get('WIN_ADD', 0) > 0 and d.get('ITEM_RATE_HP') == 0.0025 and d.get('COST_FIRE_W') == 0.0 and d.get('COST_JERK_W') == 0.0 and d.get('CONTACT_FREE') == 1.0 and d.get('COST_FIRE_W') == 0.0, d; d.update(H2_GATE_CAP=0.0, H2_GATE_OPEN=1.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made (b1.2c's dials not at their ends?): not started"; exit 1 }
Remove-Item Env:CUDA_VISIBLE_DEVICES, Env:OMP_NUM_THREADS
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_b13a.pt")
Copy-Item $END (Join-Path $R1 "snapshots\anchor_b12c.pt")
Copy-Item $REF (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from b1.2c's end")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $END; $env:CTRL_PREV_LABEL = "the start (b1.2c's end)"
$env:CTRL_REF = $REF; $env:CTRL_REF_LABEL = "v0.6.0's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $END; $env:CHECK_RULE = "0"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_b13a.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | ramp and tripwire " + $r.Id + " | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
