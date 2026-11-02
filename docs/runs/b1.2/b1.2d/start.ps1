# b1.2d's start (owner, 2026-11-02; docs/runs/b1.2/b1.2d/CARD.md): from b1.2c's end, five pay changes faded in together over 40 updates by the ramp: the table by the point, speed pay, damage taken, stack lead, long rail.
# Refuses unless: no trainer runs; the start save and its optimizer, and b1.2c's widened controls, are there; b1.2c's dials ended at their end values; the settings check passes against b1.2c's command;
# pay_check.log and ramp_test.log end ALL PASSED; the run folder is new.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.2\b1.2d\start.ps1 [-From <a b1.2c save, default keep\policy_nojerk_b12c.pt>]
param([string]$From = "")
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_b1_2c"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_b1_2d"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$SRC = if ($From) { $From } else { Join-Path $K0 "policy_nojerk_b12c.pt" }
$SRCO = Join-Path (Split-Path -Parent $SRC) ((Split-Path -Leaf $SRC) -replace "^policy_", "opt_")
if ((Split-Path -Leaf $SRC) -eq "policy.pt") { $SRCO = Join-Path (Split-Path -Parent $SRC) "opt.pt" }
$CB11 = Join-Path $K0 "control_b11.pt"; $CV60 = Join-Path $K0 "control_v060_end.pt"
foreach ($p in $SRC, $SRCO, $CB11, $CV60) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); bad = {k: d.get(k) for k, v in (('COST_FIRE_W', 0.0), ('COST_JERK_W', 0.0), ('CONTACT_FREE', 1.0)) if abs(float(d.get(k, -1)) - v) > 1e-9}; assert not bad, ('b1.2c did not end its dials', bad); print('b1.2c ended its dials')" (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "b1.2c's dials are not at their ends (a start from an earlier stage needs its own dials): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.2\b1.2c\train.cmd") "--allow=--run,--minutes,ITEM_PT_LO,ITEM_PT_HI,ITEM_DECAY,SM_PASS,DMG_ENEMY_ONLY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
foreach ($f in (Join-Path $HERE "pay_check.log"), (Join-Path $HERE "ramp_test.log")) { if (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 1) -like "*ALL PASSED*")) { Log "$f has not passed: not started"; exit 1 } }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
Copy-Item $SRC (Join-Path $R1 "policy.pt")
Copy-Item $SRCO (Join-Path $R1 "opt.pt")
Copy-Item $SRC (Join-Path $R1 "keep\policy_start_b12d.pt")
Copy-Item $SRCO (Join-Path $R1 "keep\opt_start_b12d.pt")
$CK = Join-Path $R1 "keep\control_b12c.pt"; $CR = Join-Path $R1 "keep\control_b11.pt"
Copy-Item $SRC $CK
Copy-Item $CB11 $CR
Copy-Item $CB11 (Join-Path $R1 "snapshots\anchor_b11.pt")
Copy-Item $CV60 (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item $SRC (Join-Path $R1 "snapshots\anchor_b12c.pt")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(ITEM_PT_LO=0.004, ITEM_PT_HI=0.002, ITEM_DECAY=0.002, ITEM_PT_MIX=0.0, SPEED_PAY=0.25, DMG_TAKEN_W=1.0, STACK_DIFF=0.7, RAIL_FAR_PAY=0.12); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $SRC)

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from b1.2c")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (b1.2c's end)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.1 (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
# the cores (owner, 2026-11-02): the trainer on the 8 performance cores (train.cmd); everything beside it on 8 efficiency cores (2-5, 10-13: 0x3C3C), sized to them; 14-17 left for the owner
$CHK = [IntPtr]0x3C3C
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_b12d.py"), $RUN, "--start", "10", "--over", "60" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
$fc = $null
if (-not (Test-Path (Join-Path $R0 "watch\final_check_started"))) {           # b1.2c's final check of its update 250 save, once, beside b1.2d on the check cores (owner, 2026-11-02)
    Set-Content -Path (Join-Path $R0 "watch\final_check_started") -Value (Get-Date -Format "MM-dd HH:mm:ss")
    $fc = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "final_check_b12c.py") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "final_check_b12c_stdout.log") -RedirectStandardError (Join-Path $WD "final_check_b12c_stderr.log")
    $fc.ProcessorAffinity = $CHK
    Log ("b1.2c's final check of update 250 started: " + $fc.Id + " (results in duel_gru_b1_2c\watch\watch.log)")
}
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (five dials faded together over updates 10 to 70; held only at a check of 40% or less) | self-play logger " + $s.Id)
