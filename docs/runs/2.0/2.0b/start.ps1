# 2.0b (owner, 2026-11-09: "continue the build and start it when it's ready. it can run until 8am tomorrow"; then "sure 16:00 is fine";
# docs/runs/2.0/2.0b/CARD.md), ON THE OWNER'S COMMAND ONLY. Without -Minutes the length is what is left until 16:00, less five minutes. From 2.0a's end
# (keep/policy_end_20a.pt + opt_end_20a.pt) given 2.0b's parts with nothing of them in effect (tools/b20b_init.py add). Three parts, opened one after
# the other by ramp_20b.py: the brain's readout "space" from update 0; the inputs against his belief (SPACE_GATE 0 -> 1 over updates 30 to 60); the
# pay by the place (EDGE_PAY 0 -> 0.0005 over updates 60 to 100). The command is 2.0a's with the run, the length, --space-read 1 and the five set
# lines of make_files.py. Refuses: a trainer running; a missing file (a map without its table); a difference from 2.0a's command beyond those; a
# firing cost above zero; a start that does not answer as 2.0a's end; a live.json the trainer would refuse (or one the ramp will write). Then: the
# trainer (the 8 performance cores, 0xC03C3), the watcher (checks every 20 updates, 200 games, against 1.7a's update 90, the control; every fourth
# against 1.6a's end; Cypher's measures), the ramp and the self-play logger (all on 8 efficiency cores, 0x3C3C).
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\2.0\2.0b\start.ps1 [-Minutes <n>]
param([int]$Minutes = 0)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_2_0a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_2_0b"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ($Minutes -le 0) {
    $now = Get-Date
    $end = if ($now.Hour -lt 16) { $now.Date.AddHours(16) } else { $now.Date.AddDays(1).AddHours(16) }
    $Minutes = [int][Math]::Floor(($end - $now).TotalMinutes) - 5
    Log ("the run ends 16:00 (owner, 11-09: 'sure 16:00 is fine'): " + $Minutes + " minutes from now")
}
if ($Minutes -le 60) { Log "under an hour left: not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\train_duel_rnn.py") -Pattern '"SPACE_W"' -Quiet) -or -not (Select-String -Path (Join-Path $ROOT "sim\duel_env.py") -Pattern '"EDGE_PAY", "COVER_PAY", "SPACE_GATE"' -Quiet)) { Log "the code here has no 2.0b (the readout's SPACE_W, the simulator's EDGE_PAY): not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_20a.pt"; $OPTF = Join-Path $K0 "opt_end_20a.pt"
$C17 = Join-Path $SR "duel_gru_1_7a\keep\policy_end_17a.pt"
$C16 = Join-Path $SR "duel_gru_1_6a\keep\policy_end_16a.pt"
$JUDGE = Join-Path $SR "judge\judge_v060_wpn.npz"
$MAPS = "bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure"
foreach ($m in $MAPS) { $p = Join-Path $ROOT ("data\maps\space_" + $m + ".npz"); if (-not (Test-Path $p)) { Log "MISSING the table of ${m} (${p}; tools/run/space_score.py score): not started"; exit 1 } }
foreach ($p in $END, $OPTF, $C16, $C17, $JUDGE, (Join-Path $ROOT "sim\space_weapon.json"), (Join-Path $R0 "live_applied.json")) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
$ANCH = "anchor_17a.pt", "anchor_16a.pt", "anchor_15a.pt", "anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt"
foreach ($n in $ANCH) { if (-not (Test-Path (Join-Path $R0 "snapshots\$n"))) { Log "MISSING 2.0a's anchor ${n}: not started"; exit 1 } }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd, $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
# (owner, 11-04 night: "there should be no cost for firing AT ALL") every firing cost at zero in the command
& $PY -c "import re, sys; t = open(sys.argv[1]).read(); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); print('no firing cost in the command: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\2.0\2.0a\train.cmd") "--allow=--run,--minutes,--space-read,--gate-start,SPACE_TRUTH,SPACE_IN,SPACE_GATE,EDGE_PAY,COVER_PAY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 2.0a's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $END "--allow=--space-read,--gate-start,SPACE_IN,SPACE_GATE,CONTACT_FREE,LEVEL_PULL,RAIL_FAR_PAY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 2.0a's end): not started"; exit 1 }
& $PY (Join-Path $HERE "tests_env.py") --frames 1200 | ForEach-Object { Log ("simulator: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "THE SIMULATOR'S TESTS FAILED (tests_env.py): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
# (2.0b's simulator has 59 inputs more: "b20b space", "b20b targets") the start gets them at zero weight, the head's columns at zero and the
# readout "space" (tools/b20b_init.py add); the league's files and the controls the inputs (widen-league); the start answers as 2.0a's end
# (b20b_init same: 0 actions differ); --opt-small-items 1 in the command carries the optimizer's moments over the widened encoder
$env:CUDA_VISIBLE_DEVICES = "-1"
& $PY (Join-Path $ROOT "tools\b20b_init.py") add $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Remove-Item Env:\CUDA_VISIBLE_DEVICES; Log "b20b_init add of the start failed: not started"; exit 1 }
Copy-Item $OPTF (Join-Path $R1 "opt.pt")
& $PY (Join-Path $ROOT "tools\b20b_init.py") same $END (Join-Path $R1 "policy.pt") --seats 8 | ForEach-Object { Log $_ }
$sameOk = $LASTEXITCODE
if ($sameOk -eq 0) {
    & $PY (Join-Path $ROOT "tools\b20b_init.py") widen-league $END (Join-Path $R1 "snapshots\anchor_20a.pt") | ForEach-Object { Log $_ }   # (2.0a's end in the league)
    if ($LASTEXITCODE -ne 0) { $sameOk = 1 }
    foreach ($n in $ANCH) {
        if ($sameOk -eq 0) {
            & $PY (Join-Path $ROOT "tools\b20b_init.py") widen-league (Join-Path $R0 "snapshots\$n") (Join-Path $R1 "snapshots\$n") | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) { $sameOk = 1 }
        }
    }
}
Remove-Item Env:\CUDA_VISIBLE_DEVICES
if ($sameOk -ne 0) { Log "THE START DOES NOT ANSWER AS 2.0a's END (b20b_init same) or a league file was not widened: not started (the run folder has the start files only)"; exit 1 }
& $PY (Join-Path $HERE "start_live.py") (Join-Path $R0 "live.json") (Join-Path $R0 "live_applied.json") (Join-Path $R1 "live.json") | ForEach-Object { Log ("live.json: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "live.json not made from 2.0a's last: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\live_accept.py") (Join-Path $R1 "live.json") --env duel_env_ffa --ramp (Join-Path $HERE "ramp_20b.py") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE TRAINER WOULD REFUSE live.json (or a file the ramp will write): not started"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_20b.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_20b.pt")
$CK = Join-Path $R1 "keep\control_17a.pt"; $CR = Join-Path $R1 "keep\control_16a.pt"
Copy-Item $C17 $CK
Copy-Item $C16 $CR
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END + " (b20b_init add), with its optimizer; anchors 2.0a's end, 1.7a's update 90, 1.6a's end, 1.5a's end, 1.3b's end, b1.2d's end, b1.1, v0.6.0's end; the judge " + $JUDGE)

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from 2.0a's end, " + $Minutes + " minutes")
$ST = Join-Path $R1 "live_status.json"; $t0 = Get-Date
while (-not (Test-Path $ST) -and -not $t.HasExited -and ((Get-Date) - $t0).TotalMinutes -lt 20) { Start-Sleep 5 }
$st = if (Test-Path $ST) { Get-Content $ST -Raw | ConvertFrom-Json } else { $null }
if ($null -eq $st -or $st.status -ne "applied") {
    Log ("THE TRAINER DID NOT APPLY live.json (" + $(if ($null -eq $st) { if ($t.HasExited) { "the trainer exited" } else { "no answer in 20 minutes" } } else { $st.reason }) + "): the watcher, the ramp and the logger not started; see " + $RUN + ".log")
    exit 1
}
Log ("live.json applied by the trainer before its first rollout (" + $st.time + ")")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the control (1.7a's update 90)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "1.6a's end (the long-term control)"
Remove-Item Env:\CTRL_TABLE -ErrorAction SilentlyContinue
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$env:CHECK_CYPHER = "1"                                            # Cypher's measures of every check against the control
$CHK = [IntPtr]0x3C3C                                              # (owner, 2026-11-02) everything beside the trainer on 8 efficiency cores; 14-17 left for the owner
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_20b.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (its dials: ramp_20b.py, SPACE_GATE 0 -> 1 over updates 30 to 60, EDGE_PAY 0 -> 0.0005 over 60 to 100; never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log) | self-play logger " + $s.Id + " | all on 0x3C3C")
$TL = Join-Path $SR ($RUN + ".log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {                                    # (the optimizer's state from 2.0a's, never a cold start unasked)
    Start-Sleep 10
    if ((Test-Path $TL) -and (Select-String -Path $TL -Pattern "optimizer: " -Quiet)) { $ok = $true; break }
}
if ($ok) { Select-String -Path $TL -Pattern "optimizer: |keep choice|combat order|device |space \(2.0b\)|space: the ring" | ForEach-Object { Log ("trainer: " + $_.Line) } }
else { Log "no optimizer line in the trainer's log after 10 minutes: look at it" }
