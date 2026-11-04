# 1.4b's start (owner, 2026-11-03; docs/runs/b1.4/1.4b/CARD.md): from 1.3b's end with its optimizer: the switch cost out and a weapon he holds
# choosable from the start (INTENT_SWITCH=0, WEAPON_OWN=1), matchmaking by difficulty opened over updates 0 to 10, the item rule's lesson out over
# 10 to 70, the speed pay out over 70 to 90 (ramp_14b.py, one clock held and stepped back by the checks).
# Refuses unless: no trainer runs; 1.3b's end, its optimizer and the controls are there; 1.3b's dials ended at their end values; the settings check
# passes against 1.3b's command (only the run name, the length, the matchmaking's arguments, WEAPON_OWN and INTENT_SWITCH differ);
# the run folder is new. No dry run (owner, 2026-11-04: small changes; the first 10 updates are the trial).
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.4\1.4b\start.ps1 [-Minutes 720] [-Zero 0.5]
param([int]$Minutes = 720, [double]$Zero = 0.5)    # (-Zero: the checks' zero point, the same network against itself; CARD.md)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_1_3b"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_1_4b"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_13b.pt"; $OPTF = Join-Path $K0 "opt_end_13b.pt"
$CB12 = Join-Path $SR "duel_gru_b1_2d\keep\policy_end_b12d.pt"                              # b1.2d's end (the servers' network)
$CB11 = Join-Path $K0 "control_b11.pt"                                                        # b1.1, widened to 980 inputs (b1.2c)
$CV60 = Join-Path $SR "duel_gru_b1_2c\keep\control_v060_end.pt"                              # v0.6.0's end, widened (b1.2c)
foreach ($p in $END, $OPTF, $CB12, $CB11, $CV60) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); end = dict(H2_PG=1.0, INTENT_TEACH_W=1.0, SPEED_PAY=0.125, CONTACT_FREE=1.0, INTENT_HOLD=8.0, H2_GATE_CAP=0.0, H2_MIX=0.0); bad = {k: d.get(k) for k, v in end.items() if abs(float(d.get(k, -9)) - v) > 1e-9}; print('1.3b dials at their ends' if not bad else 'NOT at their ends: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "1.3b's dials are not at their ends: not started"; exit 1 }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd for $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.3\1.3b\train.cmd") "--allow=--run,--minutes,--pfsp,--pfsp-fixed,WEAPON_OWN,INTENT_SWITCH" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.3b's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $END "--allow=WEAPON_OWN,INTENT_SWITCH" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.3b's end): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
Copy-Item $END (Join-Path $R1 "policy.pt")
Copy-Item $OPTF (Join-Path $R1 "opt.pt")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(PFSP=0.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_14b.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_14b.pt")
$CK = Join-Path $R1 "keep\control_13b.pt"; $CR = Join-Path $R1 "keep\control_b12d.pt"
Copy-Item $END $CK
Copy-Item $CB12 $CR
Copy-Item $CB11 (Join-Path $R1 "keep\control_b11.pt")
Copy-Item $END (Join-Path $R1 "snapshots\anchor_13b.pt")
Copy-Item $CB12 (Join-Path $R1 "snapshots\anchor_b12d.pt")
Copy-Item $CB11 (Join-Path $R1 "snapshots\anchor_b11.pt")
Copy-Item $CV60 (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END + " with its optimizer; anchors 1.3b's end (fixed share), b1.2d's end, b1.1, v0.6.0's end")

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from 1.3b's end, " + $Minutes + " minutes")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (1.3b's end)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.2d's end (reference)"
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$CHK = [IntPtr]0x3C3C                                              # (owner, 2026-11-02) everything beside the trainer on 8 efficiency cores; 14-17 left for the owner
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_14b.py"), $RUN, "--zero", $Zero -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (PFSP 0 -> 1 over 0 to 10, INTENT_TEACH_W 1 -> 0 over 10 to 70, SPEED_PAY 0.125 -> 0 over 70 to 90; the clock held and stepped back by the checks, zero point " + $Zero + ") | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
