# 1.4c's start (owner, 2026-11-04; docs/runs/b1.4/1.4c/CARD.md): from 1.4b's end with its optimizer, given the keep choice (tools/keep_init.py
# add: the lock made soft, share 0): the blind-fire cost out from the start (BLIND_FIRE_W=0), the keep choice takes the lock rule's readings
# over updates 10 to 90 (live KEEP_G 0 -> 1, ramp_14c.py --free: the checks reported, never held or stepped back, CLAUDE.md rule 6).
# Refuses unless: no trainer runs; 1.4b's end, its optimizer and the controls are there; 1.4b's dials ended at their end values; the settings
# check passes against 1.4b's command (only the run name, the length, the checks' fixed anchor, --keep-g and BLIND_FIRE_W differ) and against
# 1.4b's end (its live dials carried in live.json); the start answers as 1.4b's end (keep_init same: 0 actions differ); the level check of the
# start at share 1 against a 1.4b save passed (level/summary.json; -NoTrial skips it on the owner's word); the run folder is new. No dry run
# (owner, 2026-11-04: a small change; its first 10 updates and the check at update 10 are the trial).
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.4\1.4c\start.ps1 [-Minutes 720] [-Zero 0.5] [-NoTrial]
param([int]$Minutes = 720, [double]$Zero = 0.5, [switch]$NoTrial)    # (-Zero: the checks' zero point, the same network against itself)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_1_4b"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_1_4c"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_14b.pt"; $OPTF = Join-Path $K0 "opt_end_14b.pt"
$C13 = Join-Path $R0 "snapshots\anchor_13b.pt"                                                # 1.3b's end
$CB12 = Join-Path $SR "duel_gru_b1_2d\keep\policy_end_b12d.pt"                              # b1.2d's end (the servers' network)
$CB11 = Join-Path $K0 "control_b11.pt"                                                        # b1.1, widened to 980 inputs (b1.2c)
$CV60 = Join-Path $R0 "snapshots\anchor_v060_end.pt"                                          # v0.6.0's end, widened (b1.2c)
foreach ($p in $END, $OPTF, $C13, $CB12, $CB11, $CV60) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); end = dict(PFSP=1.0, INTENT_TEACH_W=0.0, SPEED_PAY=0.0, H2_PG=1.0, CONTACT_FREE=1.0, INTENT_HOLD=8.0, H2_GATE_CAP=0.0, H2_MIX=0.0); bad = {k: d.get(k) for k, v in end.items() if abs(float(d.get(k, -9)) - v) > 1e-9}; print('1.4b dials at their ends' if not bad else 'NOT at their ends: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "1.4b's dials are not at their ends: not started"; exit 1 }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd for $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.4\1.4b\train.cmd") "--allow=--run,--minutes,--pfsp-fixed,--keep-g,BLIND_FIRE_W" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.4b's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $END "--allow=CONTACT_FREE,LEVEL_PULL,RAIL_FAR_PAY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.4b's end): not started"; exit 1 }
if (-not $NoTrial) {                                 # (no dry run: a small change, its first 10 updates are the trial; owner, 11-04)
    $LV = Join-Path $HERE "level\summary.json"
    if (-not (Test-Path $LV)) { Log "the level check has not run (level\summary.json): not started (-NoTrial on the owner's word)"; exit 1 }
    & $PY -c "import hashlib, json, sys; d = json.load(open(sys.argv[1])); sha = hashlib.sha256(open(sys.argv[2], 'rb').read()).hexdigest(); ok = d['win_rate'] >= 0.45 and 'duel_gru_1_4b' in d['ref']; print('level check of the start at share 1 (from {}{}): {}-{} = {:.1%}'.format(d['ref'], ', 1.4b\'s end itself' if d.get('from_sha') == sha else ', a save of 1.4b before its end', d['won'], d['lost'], d['win_rate']) + ('' if ok else ' NOT PASSED')); sys.exit(0 if ok else 1)" $LV $END | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) { Log "the level check did not pass: not started"; exit 1 }
}
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"
& $PY (Join-Path $ROOT "tools\keep_init.py") add $END (Join-Path $R1 "policy.pt") --opt $OPTF (Join-Path $R1 "opt.pt") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "keep_init add failed: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\keep_init.py") same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
$sameOk = $LASTEXITCODE
Remove-Item Env:\CUDA_VISIBLE_DEVICES
if ($sameOk -ne 0) { Log "THE START DOES NOT ANSWER AS 1.4b's END (keep_init same): not started (the run folder has the start files only)"; exit 1 }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(KEEP_G=0.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
& $PY (Join-Path $HERE "live_check.py") $END (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json does not carry the save's live dials: not started"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_14c.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_14c.pt")
$CK = Join-Path $R1 "keep\control_14b.pt"; $CR = Join-Path $R1 "keep\control_b12d.pt"
Copy-Item $END $CK
Copy-Item $CB12 $CR
Copy-Item $CB11 (Join-Path $R1 "keep\control_b11.pt")
Copy-Item $END (Join-Path $R1 "snapshots\anchor_14b.pt")
Copy-Item $C13 (Join-Path $R1 "snapshots\anchor_13b.pt")
Copy-Item $CB12 (Join-Path $R1 "snapshots\anchor_b12d.pt")
Copy-Item $CB11 (Join-Path $R1 "snapshots\anchor_b11.pt")
Copy-Item $CV60 (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END + " with its optimizer, given the keep choice at share 0; anchors 1.4b's end (fixed share), 1.3b's end, b1.2d's end, b1.1, v0.6.0's end")

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from 1.4b's end, " + $Minutes + " minutes")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (1.4b's end)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.2d's end (reference)"
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$CHK = [IntPtr]0x3C3C                                              # (owner, 2026-11-02) everything beside the trainer on 8 efficiency cores; 14-17 left for the owner
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_14c.py"), $RUN, "--zero", $Zero, "--free" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (KEEP_G 0 -> 1 over 10 to 90, --free: never held or stepped back, CLAUDE.md rule 6; a check under 40% a MAJOR PROBLEM in watch.log) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
