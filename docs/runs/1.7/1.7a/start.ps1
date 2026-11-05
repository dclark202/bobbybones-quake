# 1.7a's start (owner, 2026-11-05; docs/runs/1.7/1.7a/CARD.md), ON THE OWNER'S COMMAND ONLY, with the length he gives (-Minutes; no
# default: CLAUDE.md, "ask him to specify the length"): from 1.6a's end with its optimizer, given the keep choice at share 0
# (tools/keep_init.py add: its start the lock made soft, re-fitted for five readings a second; at share 0 the network plays as 1.6a's end);
# live KEEP_G 0 -> 1 over updates 10 to 90 (ramp_17a.py: reported, never held or stepped back, CLAUDE.md rule 6), then 1 to the end. The
# league as 1.6a: its even draw (no --pfsp), the habit seats (HABIT_P 0.3), its anchors with 1.6a's end added. No cost for firing at all
# (owner, 11-04 night): refused unless every firing cost is zero in the command and live.json. Refuses unless: the code here is 1.7a's (b17a
# merged); no trainer runs; 1.6a's end (keep/policy_end_16a.pt, else its save of update 80, kept as the end), its optimizer, controls and
# anchors are there; 1.6a's dials at their end values; the settings check passes against 1.6a's command (only the run name, the length,
# 1.6a's --max-updates and --keep-g differ) and against 1.6a's end (its live dials carried in live.json); the start answers as 1.6a's end
# (keep_init same: 0 actions differ at share 0; at share 1 the start's re-decisions); the run folder is new. After the start: the trainer's
# log must say the optimizer's state was loaded (a failed load stops the trainer: no --opt-cold-ok). No dry run (owner, 11-04).
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\1.7\1.7a\start.ps1 -Minutes <the owner's length>
param([int]$Minutes = 0)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_1_6a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_1_7a"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ($Minutes -le 0) { Log "no length given (-Minutes): the owner gives it (CLAUDE.md): not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\head2.py") -Pattern "^KEEP_F = 7" -Quiet)) { Log "the code here is not 1.7a's (merge b17a first): not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_16a.pt"; $OPTF = Join-Path $K0 "opt_end_16a.pt"
if (-not (Test-Path $END)) {                                         # (1.6a ends at its save of update 80, kept by its ramp: the end, kept so)
    $U80 = Join-Path $K0 "policy_u80_16a.pt"; $O80 = Join-Path $K0 "opt_u80_16a.pt"
    if ((Test-Path $U80) -and (Test-Path $O80) -and -not (Test-Path $OPTF)) {
        Copy-Item $U80 $END; Copy-Item $O80 $OPTF
        Log "1.6a's end kept as keep/policy_end_16a.pt and opt_end_16a.pt (copies of its save of update 80)"
    }
}
$CB12 = Join-Path $K0 "control_b12d.pt"; $CB11 = Join-Path $K0 "control_b11.pt"; $C13 = Join-Path $K0 "control_13b.pt"; $C15 = Join-Path $K0 "control_15a.pt"
foreach ($p in $END, $OPTF, $CB12, $CB11, $C13, $C15) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
foreach ($n in "anchor_15a.pt", "anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt") {
    if (-not (Test-Path (Join-Path $R0 "snapshots\$n"))) { Log "MISSING 1.6a's anchor ${n}: not started"; exit 1 }
}
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); end = dict(INTENT_TEACH_W=0.0, SPEED_PAY=0.0, H2_WPG=1.0, HABIT_P=0.3, COST_FIRE_W=0.0, H2_PG=1.0, CONTACT_FREE=1.0, INTENT_HOLD=8.0, H2_GATE_CAP=0.0, H2_MIX=0.0); bad = {k: d.get(k) for k, v in end.items() if abs(float(d.get(k, -9)) - v) > 1e-9}; bad.update({'KEEP_G': d['KEEP_G']} if 'KEEP_G' in d else {}); print('1.6a dials at their ends' if not bad else 'NOT at their ends: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "1.6a's dials are not at their ends: not started"; exit 1 }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd for $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
# (owner, 11-04 night: "there should be no cost for firing AT ALL") every firing cost at zero, in the command and in live.json
& $PY -c "import json, re, sys; t = open(sys.argv[1]).read(); d = json.load(open(sys.argv[2])); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); bad.update({'live ' + n: d[n] for n in ('COST_FIRE_W', 'SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if n in d and float(d[n]) != 0}); bad.update({} if 'COST_FIRE_W' in d else {'live COST_FIRE_W': 'missing (1 by default)'}); print('no firing cost: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\1.6\1.6a\train.cmd") "--allow=--run,--minutes,--max-updates,--keep-g" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.6a's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $END "--allow=--max-updates,--keep-g,CONTACT_FREE,LEVEL_PULL,RAIL_FAR_PAY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.6a's end): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"
& $PY (Join-Path $ROOT "tools\keep_init.py") add $END (Join-Path $R1 "policy.pt") --opt $OPTF (Join-Path $R1 "opt.pt") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Remove-Item Env:\CUDA_VISIBLE_DEVICES; Log "keep_init add failed: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\keep_init.py") same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
$sameOk = $LASTEXITCODE
Remove-Item Env:\CUDA_VISIBLE_DEVICES
if ($sameOk -ne 0) { Log "THE START DOES NOT ANSWER AS 1.6a's END (keep_init same): not started (the run folder has the start files only)"; exit 1 }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(KEEP_G=0.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
& $PY (Join-Path $ROOT "docs\runs\b1.4\1.4c\live_check.py") $END (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json does not carry the save's live dials: not started"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_17a.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_17a.pt")
$CK = Join-Path $R1 "keep\control_16a.pt"; $CR = Join-Path $R1 "keep\control_b12d.pt"
Copy-Item $END $CK
Copy-Item $CB12 $CR
Copy-Item $CB11 (Join-Path $R1 "keep\control_b11.pt")
Copy-Item $C13 (Join-Path $R1 "keep\control_13b.pt")
Copy-Item $C15 (Join-Path $R1 "keep\control_15a.pt")
Copy-Item $END (Join-Path $R1 "snapshots\anchor_16a.pt")
foreach ($n in "anchor_15a.pt", "anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt") { Copy-Item (Join-Path $R0 "snapshots\$n") (Join-Path $R1 "snapshots\$n") }
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END + " given the keep choice at share 0, with its optimizer; anchors 1.6a's end, 1.5a's end, 1.3b's end, b1.2d's end, b1.1, v0.6.0's end (1.6a's even draw)")

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from 1.6a's end, " + $Minutes + " minutes")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (1.6a's end)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.2d's end (reference)"
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$CHK = [IntPtr]0x3C3C                                              # (owner, 2026-11-02) everything beside the trainer on 8 efficiency cores; 14-17 left for the owner
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_17a.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (KEEP_G 0 -> 1 over updates 10 to 90, then 1; never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
$TL = Join-Path $SR ($RUN + ".log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {                                    # (change 4: the optimizer's state from 1.6a's, never a cold start unasked)
    Start-Sleep 10
    if ((Test-Path $TL) -and (Select-String -Path $TL -Pattern "optimizer: " -Quiet)) { $ok = $true; break }
}
if ($ok) { Select-String -Path $TL -Pattern "optimizer: |keep choice" | ForEach-Object { Log ("trainer: " + $_.Line) } }
else { Log "the trainer's log has no optimizer line after 10 minutes: LOOK AT IT" }
