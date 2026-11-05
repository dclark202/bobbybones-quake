# 1.6a's start (owner, 2026-11-05; docs/runs/1.6/1.6a/CARD.md), ON THE OWNER'S COMMAND ONLY: from 1.5a's end with its optimizer, nothing
# new in the network; the item teacher (live INTENT_TEACH_W 1 -> 0) and the speed pay (live SPEED_PAY 0.125 -> 0) out over updates 0 to 40
# (ramp_16a.py: reported, never held or stepped back, CLAUDE.md rule 6), held at 0 to update 80 (--max-updates 80; --minutes a cap). The
# league as 1.5a: its even draw (no --pfsp), the habit seats (HABIT_P 0.3), its anchors with 1.5a's end added. No cost for firing at all
# (owner, 11-04 night): refused unless every firing cost is zero in the command and live.json. Refuses unless: no trainer runs; 1.5a's end
# (keep/policy_end_15a.pt), its optimizer and its anchors are there; 1.5a's dials at their end values; the settings check passes against
# 1.5a's command (only the run name, the length, --head2-wpg at its end value 1 and SHOT_COST 0 differ) and against 1.5a's end; the run
# folder is new. No dry run (owner, 11-04: the first 10 updates and the check at update 10).
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\1.6\1.6a\start.ps1 [-Minutes 600]
param([int]$Minutes = 600)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_1_5a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_1_6a"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_15a.pt"; $OPTF = Join-Path $K0 "opt_end_15a.pt"
$CB12 = Join-Path $K0 "control_b12d.pt"; $CB11 = Join-Path $K0 "control_b11.pt"; $C13 = Join-Path $K0 "control_13b.pt"
foreach ($p in $END, $OPTF, $CB12, $CB11, $C13) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
foreach ($n in "anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt") {
    if (-not (Test-Path (Join-Path $R0 "snapshots\$n"))) { Log "MISSING 1.5a's anchor ${n}: not started"; exit 1 }
}
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); end = dict(INTENT_TEACH_W=1.0, SPEED_PAY=0.125, H2_WPG=1.0, HABIT_P=0.3, COST_FIRE_W=0.0, H2_PG=1.0, CONTACT_FREE=1.0, INTENT_HOLD=8.0, H2_GATE_CAP=0.0, H2_MIX=0.0); bad = {k: d.get(k) for k, v in end.items() if abs(float(d.get(k, -9)) - v) > 1e-9}; print('1.5a dials at their ends' if not bad else 'NOT at their ends: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "1.5a's dials are not at their ends: not started"; exit 1 }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd for $Minutes minutes (a cap; 80 updates): " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
# (owner, 11-04 night: "there should be no cost for firing AT ALL") every firing cost at zero, in the command and in live.json
& $PY -c "import json, re, sys; t = open(sys.argv[1]).read(); d = json.load(open(sys.argv[2])); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); bad.update({'live ' + n: d[n] for n in ('COST_FIRE_W', 'SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if n in d and float(d[n]) != 0}); bad.update({} if 'COST_FIRE_W' in d else {'live COST_FIRE_W': 'missing (1 by default)'}); print('no firing cost: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\1.5\1.5a\train.cmd") "--allow=--run,--minutes,--max-updates,--head2-wpg,SHOT_COST" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.5a's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $END "--allow=--max-updates,--head2-wpg,SHOT_COST,CONTACT_FREE,LEVEL_PULL,RAIL_FAR_PAY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.5a's end): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
Copy-Item $END (Join-Path $R1 "policy.pt")
Copy-Item $OPTF (Join-Path $R1 "opt.pt")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
& $PY (Join-Path $ROOT "docs\runs\b1.4\1.4c\live_check.py") $END (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json does not carry the save's live dials: not started"; exit 1 }
Copy-Item $END (Join-Path $R1 "keep\policy_start_16a.pt")
Copy-Item $OPTF (Join-Path $R1 "keep\opt_start_16a.pt")
$CK = Join-Path $R1 "keep\control_15a.pt"; $CR = Join-Path $R1 "keep\control_b12d.pt"
Copy-Item $END $CK
Copy-Item $CB12 $CR
Copy-Item $CB11 (Join-Path $R1 "keep\control_b11.pt")
Copy-Item $C13 (Join-Path $R1 "keep\control_13b.pt")
Copy-Item $END (Join-Path $R1 "snapshots\anchor_15a.pt")
foreach ($n in "anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt") { Copy-Item (Join-Path $R0 "snapshots\$n") (Join-Path $R1 "snapshots\$n") }
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END + " with its optimizer; anchors 1.5a's end, 1.3b's end, b1.2d's end, b1.1, v0.6.0's end (1.5a's even draw)")

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from 1.5a's end, 80 updates (cap " + $Minutes + " minutes)")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (1.5a's end)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.2d's end (reference)"
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$CHK = [IntPtr]0x3C3C                                              # (owner, 2026-11-02) everything beside the trainer on 8 efficiency cores; 14-17 left for the owner
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_16a.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (INTENT_TEACH_W 1 -> 0 and SPEED_PAY 0.125 -> 0 over updates 0 to 40, held to 80, never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log; the head's weapon scores switched off for a check at update 80) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
