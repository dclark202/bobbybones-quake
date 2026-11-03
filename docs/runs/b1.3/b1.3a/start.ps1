# b1.3a's start (owner, 2026-11-01; rebuilt on b1.2d 2026-11-02; the copy design of 11-02 evening; docs/runs/b1.3/b1.3a/CARD.md): the strategy head in, shut in play all run,
# learning to copy his target choice, from b1.2d's end.
# Refuses unless: no trainer runs; b1.2d's end and its optimizer and the widened controls are there; b1.2d's dials ended at their end values; the settings check passes against b1.2d's command;
# trial_copy.log has ALL PASSED; the run folder is new; the start with the head, shut and with its whole path run, answers exactly as the save.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.3\b1.3a\start.ps1 [-Minutes 720]
param([int]$Minutes = 720, [switch]$NoTrial)       # (owner, 11-02 evening: "Plan for that B1.3 to run for about 12 hours"; -NoTrial: owner 11-02 20:25, "stop the trial you are running. Let's just start B1.3 and see how it goes")
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_b1_2d"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_b1_3a"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_b12d.pt"; $OPTF = Join-Path $K0 "opt_end_b12d.pt"         # (python tools/run/stop_run.py duel_gru_b1_2d b12d, on the owner's word)
$CB11 = Join-Path $K0 "control_b11.pt"                                                        # b1.1, widened to 980 inputs (b1.2c)
$CV60 = Join-Path $SR "duel_gru_b1_2c\keep\control_v060_end.pt"                              # v0.6.0's end, widened (b1.2c)
foreach ($p in $END, $OPTF, $CB11, $CV60) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); end = dict(ITEM_PT_MIX=1.0, SPEED_PAY=0.125, DMG_TAKEN_W=0.8, STACK_DIFF=0.0, RAIL_FAR_PAY=0.25, COST_FIRE_W=0.0, COST_JERK_W=0.0, CONTACT_FREE=1.0); bad = {k: d.get(k) for k, v in end.items() if abs(float(d.get(k, -9)) - v) > 1e-6}; assert not bad, ('b1.2d did not end its dials', bad); print('b1.2d ended its dials')" (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "b1.2d's dials are not at their ends (a start from a save of its fade needs its own dials): not started"; exit 1 }
$MIN = $Minutes
& $PY (Join-Path $HERE "make_files.py") $MIN | ForEach-Object { Log ("train.cmd for $MIN minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.2\b1.2d\train.cmd") "--allow=--run,--minutes,--head2,--head2-cap,--head2-ctrl-src,--head2-gate,--head2-open,--head2-start,--head2-pay,--head2-pg,--head2-copy,H2_START" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
$f = Join-Path $HERE "trial_copy.log"
if ($NoTrial) { Log "started without the trial's verdict (owner's word, 11-02 20:25: the trial stopped at update 102; the copy's gradient reached the head only, gate 0, KL 2.26 -> about 1.45)" }
elseif (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 3) -match "^[0-9:]+ ALL PASSED$")) { Log "trial_copy.log has not passed: not started"; exit 1 }
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
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(H2_GATE_CAP=0.0, H2_GATE_OPEN=0.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
Remove-Item Env:CUDA_VISIBLE_DEVICES, Env:OMP_NUM_THREADS
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_b13a.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_b13a.pt")
$CK = Join-Path $R1 "keep\control_b12d.pt"; $CR = Join-Path $R1 "keep\control_b11.pt"
Copy-Item $END $CK
Copy-Item $CB11 $CR
Copy-Item $END (Join-Path $R1 "snapshots\anchor_b12d.pt")
Copy-Item $CB11 (Join-Path $R1 "snapshots\anchor_b11.pt")
Copy-Item $CV60 (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END)

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from b1.2d's end")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (b1.2d's end)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.1 (reference)"
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
# checks every 20 updates, 20 games a map: 200 a check (owner, 2026-11-02)
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"
# the cores (owner, 2026-11-02): the trainer on the 8 performance cores (train.cmd); everything beside it on 8 efficiency cores (2-5, 10-13: 0x3C3C), sized to them; 14-17 left for the owner
$CHK = [IntPtr]0x3C3C
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | self-play logger " + $s.Id + " | the head shut all run (gate 0), copying | no guard (owner: never stop the run)")
