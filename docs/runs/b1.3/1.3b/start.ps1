# 1.3b's start (owner, 2026-11-03; docs/runs/b1.3/1.3b/CARD.md): from b1.2d's end, his target choice gets the strategy head's slow memory:
# the head's own scores added to the hands' (at zero at the start), one learner, the credit moved to the head's advantage over updates 10 to 90 (ramp_13b.py; owner 11-03: 80 updates).
# Refuses unless: no trainer runs; b1.2d's end, its optimizer and the controls are there; b1.2d's dials ended at their end values; the settings check
# passes against b1.2d's command (only the head's arguments and the run name differ); dryrun_13b.log has ALL PASSED (or -NoTrial on the owner's word);
# the run folder is new; the start answers exactly as b1.2d's end (0 actions differ) and a copy with the head's layer set at random does not (the path is live).
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.3\1.3b\start.ps1 [-Minutes 720] [-Zero 0.5] [-NoTrial]
param([int]$Minutes = 720, [double]$Zero = 0.5, [switch]$NoTrial)    # (-Zero: the checks' zero point, the same network against itself; CARD.md)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_b1_2d"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_1_3b"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_b12d.pt"; $OPTF = Join-Path $K0 "opt_end_b12d.pt"
$CB11 = Join-Path $K0 "control_b11.pt"                                                        # b1.1, widened to 980 inputs (b1.2c)
$CV60 = Join-Path $SR "duel_gru_b1_2c\keep\control_v060_end.pt"                              # v0.6.0's end, widened (b1.2c)
foreach ($p in $END, $OPTF, $CB11, $CV60) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); end = dict(ITEM_PT_MIX=1.0, SPEED_PAY=0.125, DMG_TAKEN_W=0.8, STACK_DIFF=0.0, RAIL_FAR_PAY=0.25, COST_FIRE_W=0.0, COST_JERK_W=0.0, CONTACT_FREE=1.0); bad = {k: d.get(k) for k, v in end.items() if abs(float(d.get(k, -9)) - v) > 1e-9}; print('b1.2d dials at their ends' if not bad else 'NOT at their ends: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "b1.2d's dials are not at their ends: not started"; exit 1 }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd for $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.2\b1.2d\train.cmd") "--allow=--run,--minutes,--head2,--head2-cap,--head2-ctrl-src,--head2-gate,--head2-open,--head2-start,--head2-pay,--head2-pg,--head2-add,--head2-chrono-lo,--head2-lam,--head2-l2" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
$f = Join-Path $HERE "dryrun_13b.log"
if ($NoTrial) { Log "started without the dry run's verdict (the owner's word)" }
elseif (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 3) -match "ALL PASSED$")) { Log "dryrun_13b.log has not passed: not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"; $env:OPENBLAS_NUM_THREADS = "1"; $env:OMP_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$H2I = Join-Path $ROOT "tools\head2_init.py"
& $PY $H2I add $END (Join-Path $R1 "policy.pt") --gate 0 --ctrl-src belief --add 1 --chrono-lo 1 --opt $OPTF (Join-Path $R1 "opt.pt") | ForEach-Object { Log $_ }
$same = & $PY $H2I same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
if (-not ($same -match "actions that differ: 0$")) { Log "THE START NETWORK ANSWERS DIFFERENTLY: not started (its policy.pt left for a look; nothing deleted)"; exit 1 }
$PK = Join-Path $R1 "watch\start_head_random.pt"
& $PY -c "import torch, sys; ck = torch.load(sys.argv[1], weights_only=False, map_location='cpu'); sd = ck['model']; torch.manual_seed(1); sd['head2.target.weight'] = torch.randn_like(sd['head2.target.weight']) * 0.3; sd['head2.target.bias'] = torch.randn_like(sd['head2.target.bias']) * 0.3; torch.save(ck, sys.argv[2]); print('the head layer set at random (a test copy)')" (Join-Path $R1 "policy.pt") $PK | ForEach-Object { Log $_ }
$live = & $PY $H2I same $END $PK | ForEach-Object { Log $_ }
if ($live -match "actions that differ: 0$") { Log "THE HEAD'S PATH IS NOT LIVE (a random head layer changes nothing): not started"; exit 1 }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(H2_GATE_CAP=0.0, H2_GATE_OPEN=0.0, H2_PG=0.0, H2_MIX=0.0, H2_COPY=0.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
Remove-Item Env:CUDA_VISIBLE_DEVICES, Env:OMP_NUM_THREADS
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_13b.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_13b.pt")
$CK = Join-Path $R1 "keep\control_b12d.pt"; $CR = Join-Path $R1 "keep\control_b11.pt"
Copy-Item $END $CK
Copy-Item $CB11 $CR
Copy-Item $END (Join-Path $R1 "snapshots\anchor_b12d.pt")
Copy-Item $CB11 (Join-Path $R1 "snapshots\anchor_b11.pt")
Copy-Item $CV60 (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END + " (the head added: add 1, target at zero, memory spread 1 to 300 ticks)")

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from b1.2d's end, " + $Minutes + " minutes")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (b1.2d's end)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.1 (reference)"
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$CHK = [IntPtr]0x3C3C                                              # (owner, 2026-11-02) everything beside the trainer on 8 efficiency cores; 14-17 left for the owner
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_13b.py"), $RUN, "--start", "10", "--over", "80", "--zero", $Zero -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (H2_PG 0 -> 1 over updates 10 to 90, hold and step back by the checks, zero point " + $Zero + ") | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
