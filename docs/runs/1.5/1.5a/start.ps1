# 1.5a's start (owner, 2026-11-04 evening; docs/runs/1.5/1.5a/CARD.md), ON THE OWNER'S COMMAND ONLY ("I will give the final approval"):
# from 1.3b's end with its optimizer, given the head's weapon scores at zero (tools/weapon_init.py add, wadd 1); everything else as 1.3b
# ended (the item teacher, the speed pay, the 8 s lock, 1.3b's league and even draw), but the switch cost, the weapon override and the
# blind-fire cost out at update 0 (owner, 11-04 evening). The weapon key's credit H2_WPG 0 -> 1 over updates 10 to 90 (ramp_15a.py: reported, never held or stepped back, CLAUDE.md rule
# 6); the league seats' habits on 30% of their lives (--habit-p 0.3). Refuses unless: the code here is 1.5a's (b15a merged); no trainer
# runs; 1.3b's end, its optimizer and its anchors are there; 1.3b's dials at their end values; the settings check passes against 1.3b's
# command (only the run name, the length and the new flags differ) and against 1.3b's end (its live dials carried in live.json); the start
# answers as 1.3b's end (weapon_init same: 0 actions differ, memory and head state the same to the bit; random scores reach the weapon key
# alone; at add 0 the same again); the run folder is new. No dry run (owner, 11-04: the first 10 updates and the check at update 10).
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\1.5\1.5a\start.ps1 [-Minutes 720]
param([int]$Minutes = 720)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_1_3b"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_1_5a"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if (-not (Select-String -Path (Join-Path $ROOT "sim\head2.py") -Pattern "def has_weapon" -Quiet)) { Log "the code here is not 1.5a's (merge b15a first): not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_13b.pt"; $OPTF = Join-Path $K0 "opt_end_13b.pt"
$CB12 = Join-Path $K0 "control_b12d.pt"; $CB11 = Join-Path $K0 "control_b11.pt"
foreach ($p in $END, $OPTF, $CB12, $CB11) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
foreach ($n in "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt") {
    if (-not (Test-Path (Join-Path $R0 "snapshots\$n"))) { Log "MISSING 1.3b's anchor ${n}: not started"; exit 1 }
}
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); end = dict(INTENT_TEACH_W=1.0, SPEED_PAY=0.125, H2_PG=1.0, CONTACT_FREE=1.0, INTENT_HOLD=8.0, H2_GATE_CAP=0.0, H2_MIX=0.0); bad = {k: d.get(k) for k, v in end.items() if abs(float(d.get(k, -9)) - v) > 1e-9}; print('1.3b dials at their ends' if not bad else 'NOT at their ends: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "1.3b's dials are not at their ends: not started"; exit 1 }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd for $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.3\1.3b\train.cmd") "--allow=--run,--minutes,--head2-wpg,--habit-p,--habit-push,--habit-kinds,INTENT_SWITCH,WEAPON_OWN,BLIND_FIRE_W" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.3b's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $END "--allow=CONTACT_FREE,LEVEL_PULL,RAIL_FAR_PAY,--head2-wpg,--habit-p,--habit-push,--habit-kinds,INTENT_SWITCH,WEAPON_OWN,BLIND_FIRE_W" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.3b's end): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"
& $PY (Join-Path $ROOT "tools\weapon_init.py") add $END (Join-Path $R1 "policy.pt") --opt $OPTF (Join-Path $R1 "opt.pt") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "weapon_init add failed: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\weapon_init.py") same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
$sameOk = $LASTEXITCODE
Remove-Item Env:\CUDA_VISIBLE_DEVICES
if ($sameOk -ne 0) { Log "THE START DOES NOT ANSWER AS 1.3b's END (weapon_init same): not started (the run folder has the start files only)"; exit 1 }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(H2_WPG=0.0, HABIT_P=0.3, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
& $PY (Join-Path $ROOT "docs\runs\b1.4\1.4c\live_check.py") $END (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json does not carry the save's live dials: not started"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_15a.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_15a.pt")
$CK = Join-Path $R1 "keep\control_13b.pt"; $CR = Join-Path $R1 "keep\control_b12d.pt"
Copy-Item $END $CK
Copy-Item $CB12 $CR
Copy-Item $CB11 (Join-Path $R1 "keep\control_b11.pt")
Copy-Item $END (Join-Path $R1 "snapshots\anchor_13b.pt")
foreach ($n in "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt") { Copy-Item (Join-Path $R0 "snapshots\$n") (Join-Path $R1 "snapshots\$n") }
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END + " with its optimizer, given the head's weapon scores at zero; anchors 1.3b's end, b1.2d's end, b1.1, v0.6.0's end (1.3b's even draw)")

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
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_15a.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (H2_WPG 0 -> 1 over updates 10 to 90, never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log; the head's weapon scores switched off for a check at update 50) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
