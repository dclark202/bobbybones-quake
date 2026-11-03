# b1.4a's start (owner, 2026-11-02 evening: "B1.4 - fade OLD rules out"; docs/runs/b1.4/b1.4a/CARD.md): from b1.3a's end, his target choice moved
# from the hands' to the head's, then the target lock and the way pay out (ramp_b14a.py).
# Refuses unless: no trainer runs; b1.3a's end and its optimizer and the controls are there; the start's head is shut (gate 0) with mix 0; the
# settings check passes against b1.3a's command; trial_b14a.log has ALL PASSED (or -NoTrial on the owner's word); the run folder is new.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.4\b1.4a\start.ps1 [-Minutes 720] [-From <policy save; default b1.3a's end>] [-NoTrial]
param([int]$Minutes = 720, [string]$From = "", [switch]$NoTrial)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_b1_3a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_b1_4a"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" -and $_.Name -eq "python.exe" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = if ($From) { $From } else { Join-Path $K0 "policy_end_b13a.pt" }
$OPTF = Join-Path (Split-Path -Parent $END) ((Split-Path -Leaf $END) -replace "^policy_", "opt_")
$CB12 = Join-Path $SR "duel_gru_b1_2d\keep\policy_end_b12d.pt"                              # b1.2d's end (980 inputs, no head)
$CB11 = Join-Path $SR "duel_gru_b1_2d\keep\control_b11.pt"                                  # b1.1, widened (b1.2c)
$CV60 = Join-Path $SR "duel_gru_b1_2c\keep\control_v060_end.pt"                             # v0.6.0's end, widened (b1.2c)
foreach ($p in $END, $OPTF, $CB12, $CB11, $CV60) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY -c "import sys, torch; c = torch.load(sys.argv[1], map_location='cpu', weights_only=False); sd = c['model']; assert c.get('head2') is not None, 'no head'; g = float(sd['head2.gate']); m = float(sd.get('head2.mix', 0.0)); assert g == 0.0 and m == 0.0, ('gate', g, 'mix', m); print('the start: head shut (gate 0), mix 0; target |w| {:.2f}'.format(float(sd['head2.target.weight'].abs().sum())))" $END | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "the start's head is not shut with mix 0: not started"; exit 1 }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd for $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.3\b1.3a\train.cmd") "--allow=--run,--minutes,--head2-pg,--head2-mix,--head2-sole" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
$f = Join-Path $HERE "trial_b14a.log"
if ($NoTrial) { Log "started without the trial's verdict (-NoTrial: the owner's word)" }
elseif (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 3) -match "^[0-9:]+ ALL PASSED$")) { Log "trial_b14a.log has not passed: not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
Copy-Item $END (Join-Path $R1 "policy.pt")
Copy-Item $OPTF (Join-Path $R1 "opt.pt")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(H2_GATE_CAP=0.0, H2_GATE_OPEN=0.0, H2_MIX=0.0, H2_COPY=1.0, INTENT_HOLD=8.0, INTENT_SEEK_W=1.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_b14a.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_b14a.pt")
$CK = Join-Path $R1 "keep\control_b13a.pt"; $CR = Join-Path $R1 "keep\control_b11.pt"
Copy-Item $END $CK
Copy-Item $CB11 $CR
Copy-Item $END (Join-Path $R1 "snapshots\anchor_b13a.pt")
Copy-Item $CB12 (Join-Path $R1 "snapshots\anchor_b12d.pt")
Copy-Item $CB11 (Join-Path $R1 "snapshots\anchor_b11.pt")
Copy-Item $CV60 (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END)

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from " + $END)
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (b1.3a's end)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.1 (reference)"
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
# checks every 20 updates, 20 games a map: 200 a check (owner, 2026-11-02)
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"
# the cores (owner, 2026-11-02): the trainer on the 8 performance cores (train.cmd); everything beside it on 8 efficiency cores (2-5, 10-13: 0x3C3C); 14-17 left for the owner
$CHK = [IntPtr]0x3C3C
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_b14a.py"), $RUN, "--start", "10" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp and tripwire " + $r.Id + " (A: the mix 0 -> 1 over updates 10 to 50, the copy 1 -> 0 to 70; B: the lock 8 -> 0 over 50 to 80; C: the way pay 1 -> 0 over 80 to 110) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
