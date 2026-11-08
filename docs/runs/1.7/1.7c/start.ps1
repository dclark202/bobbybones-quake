# 1.7c's start (owner, 2026-11-07 evening: "ok let's do it then. start it when it's ready, 12 hrs is fine, or you can run it until noon
# tomorrow"; docs/runs/1.7/1.7c/TRAIN_UNDER_TABLE.md, CARD.md), ON THE OWNER'S COMMAND ONLY. Its length is the owner's: -Minutes (until noon
# 11-08 from the start). From 1.7a's result (its save of update 90, keep/policy_end_17a.pt) AS IT IS with its optimizer: no conversion, no
# widening; the league's files 1.7a's anchors as they are and 1.7a's update 90 as one more (the control rule). The one new thing: the pros'
# weapon table chooses the weapon of every network seat (--wrule; live WRULE_P 0 -> 1 over updates 0 to 20, ramp_17c.py: reported, never
# held or stepped back, CLAUDE.md rule 6), the weapon key's policy gradient and entropy off there, the key copying the table (--wrule-imit
# 0.1); the keep choice at the save's share and frozen (--keep-freeze 1); the order shut; the habit seats off; the head's weapon credit off.
# The pay as update 90 (live.json from the save's own record: start_live.py). No cost for firing at all: refused unless every firing cost is
# zero. Refuses unless: the code here is 1.7c's (the trainer knows --wrule, the dial has choose()); no trainer runs; the save, its optimizer,
# the controls and the anchors are there; the settings check passes against 1.7a's command (only the named differences) and against the save;
# the run folder is new; live.json and every file the ramp will write are accepted by the trainer's own reader. After the start: the trainer
# must apply live.json before its first rollout and its log must say the optimizer's state was loaded (a failed load stops the trainer: no
# --opt-cold-ok). The checks (tools/run/watch.py): his saves UNDER the table against 1.7a's update 90 plain (the yardstick, 200 games) and
# against update 90 under the table too (100 games: what the training added), b1.2d's end plain every fourth; Cypher's measures; the rail
# owned by map. No dry run of the real command (owner, 11-04); the tests of tests.py (ident, live, smoke) passed before this file runs.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\1.7\1.7c\start.ps1 -Minutes <until noon>
param([int]$Minutes = 0)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_1_7a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_1_7c"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ($Minutes -le 0) { Log "no length (-Minutes): not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\train_duel_rnn.py") -Pattern "--wrule-imit" -Quiet) -or -not (Select-String -Path (Join-Path $ROOT "sim\weapon_dial.py") -Pattern "^def choose" -Quiet) -or -not (Select-String -Path (Join-Path $ROOT "sim\weapon_dial.py") -Pattern "^PRO_IN = " -Quiet)) { Log "the code here is not 1.7c's (merge b17c first): not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_17a.pt"; $OPTF = Join-Path $K0 "opt_end_17a.pt"
$CB12 = Join-Path $K0 "control_b12d.pt"
foreach ($p in $END, $OPTF, $CB12) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
$ANCH = "anchor_16a.pt", "anchor_15a.pt", "anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt"
foreach ($n in $ANCH) { if (-not (Test-Path (Join-Path $R0 "snapshots\$n"))) { Log "MISSING 1.7a's anchor ${n}: not started"; exit 1 } }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd, $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
& $PY (Join-Path $ROOT "sim\weapon_dial.py") | ForEach-Object { Log ("weapon_dial: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "weapon_dial.py's self-check failed (the pros' table against its files, the input columns): not started"; exit 1 }
# (owner, 11-04 night: "there should be no cost for firing AT ALL") every firing cost at zero in the command
& $PY -c "import re, sys; t = open(sys.argv[1]).read(); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); print('no firing cost in the command: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\1.7\1.7a\train.cmd") "--allow=--run,--minutes,--keep-g,--wrule,--wrule-imit,--keep-freeze,--habit-p,--head2-wpg" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.7a's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $END "--allow=--keep-g,--wrule,--wrule-imit,--keep-freeze,--habit-p,--head2-wpg,CONTACT_FREE,LEVEL_PULL,RAIL_FAR_PAY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.7a's update 90): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
# (today's simulator has 994 inputs: 1.7b's four yellow-armor timers; 1.7a's files have 990) the start and the league's files widened with
# zero weights on the new columns (tools/b17b_init.py widen-league); the start answers as update 90 (b17b_init same: 0 actions differ);
# --opt-small-items 1 in the command carries the optimizer's moments over the widened encoder
$env:CUDA_VISIBLE_DEVICES = "-1"
& $PY (Join-Path $ROOT "tools\b17b_init.py") widen-league $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Remove-Item Env:\CUDA_VISIBLE_DEVICES; Log "widen-league of the start failed: not started"; exit 1 }
Copy-Item $OPTF (Join-Path $R1 "opt.pt")
& $PY (Join-Path $ROOT "tools\b17b_init.py") same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
$sameOk = $LASTEXITCODE
if ($sameOk -eq 0) {
    & $PY (Join-Path $ROOT "tools\b17b_init.py") widen-league $END (Join-Path $R1 "snapshots\anchor_17a.pt") | ForEach-Object { Log $_ }   # (the control rule)
    if ($LASTEXITCODE -ne 0) { $sameOk = 1 }
    foreach ($n in $ANCH) {
        if ($sameOk -eq 0) {
            & $PY (Join-Path $ROOT "tools\b17b_init.py") widen-league (Join-Path $R0 "snapshots\$n") (Join-Path $R1 "snapshots\$n") | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) { $sameOk = 1 }
        }
    }
}
Remove-Item Env:\CUDA_VISIBLE_DEVICES
if ($sameOk -ne 0) { Log "THE START DOES NOT ANSWER AS 1.7a's UPDATE 90 (b17b_init same) or a league file was not widened: not started (the run folder has the start files only)"; exit 1 }
& $PY (Join-Path $HERE "start_live.py") $END (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log ("live.json: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "live.json not made from the save's record: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\live_accept.py") (Join-Path $R1 "live.json") --env duel_env_ffa --ramp (Join-Path $HERE "ramp_17c.py") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE TRAINER WOULD REFUSE live.json (or a file the ramp will write): not started"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_17c.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_17c.pt")
$CK = Join-Path $R1 "keep\control_17a.pt"; $CR = Join-Path $R1 "keep\control_b12d.pt"
Copy-Item $END $CK
Copy-Item $CB12 $CR
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END + " as it is, with its optimizer; anchors 1.7a's update 90, 1.6a's end, 1.5a's end, 1.3b's end, b1.2d's end, b1.1, v0.6.0's end")

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from 1.7a's update 90, " + $Minutes + " minutes")
$ST = Join-Path $R1 "live_status.json"; $t0 = Get-Date
while (-not (Test-Path $ST) -and -not $t.HasExited -and ((Get-Date) - $t0).TotalMinutes -lt 20) { Start-Sleep 5 }
$st = if (Test-Path $ST) { Get-Content $ST -Raw | ConvertFrom-Json } else { $null }
if ($null -eq $st -or $st.status -ne "applied") {
    Log ("THE TRAINER DID NOT APPLY live.json (" + $(if ($null -eq $st) { if ($t.HasExited) { "the trainer exited" } else { "no answer in 20 minutes" } } else { $st.reason }) + "): the watcher, the ramp and the logger not started; see " + $RUN + ".log")
    exit 1
}
Log ("live.json applied by the trainer before its first rollout (" + $st.time + ")")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (1.7a's update 90) plain"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.2d's end (reference)"
$env:CTRL_TABLE = $CK; $env:CTRL_TABLE_LABEL = "the start (1.7a's update 90) under the table"   # (1.7c) the second control: the same hands, the same table
$env:CHECK_TABLE_GAMES = "10"                                      # 100 games against it after each 200-game check
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$env:CHECK_CYPHER = "1"                                            # Cypher's measures of every check against the start
$CHK = [IntPtr]0x3C3C                                              # (owner, 2026-11-02) everything beside the trainer on 8 efficiency cores; 14-17 left for the owner
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_17c.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (its dial: ramp_17c.py, WRULE_P 0 -> 1 over updates 0 to 20; never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
$TL = Join-Path $SR ($RUN + ".log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {                                    # (the optimizer's state from 1.7a's, never a cold start unasked)
    Start-Sleep 10
    if ((Test-Path $TL) -and (Select-String -Path $TL -Pattern "optimizer: " -Quiet)) { $ok = $true; break }
}
if ($ok) { Select-String -Path $TL -Pattern "optimizer: |keep choice|pros' weapon table|combat order" | ForEach-Object { Log ("trainer: " + $_.Line) } }
else { Log "the trainer's log has no optimizer line after 10 minutes: LOOK AT IT" }
