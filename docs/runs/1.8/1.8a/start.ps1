# 1.8a (owner, 2026-11-11: "the fast track aim3 in at b1.2d ... Call this model 1.8"; docs/runs/1.8/1.8a/CARD.md), ON THE OWNER'S COMMAND ONLY.
# From b1.2d's end (keep/policy_end_b12d.pt + opt_end_b12d.pt) widened to today's 1,053 inputs with zero weights (tools/b18_init.py widen), the
# strategy head added as 1.3b's (tools/head2_init.py add --add 1 --chrono-lo 1 --gate 0 --ctrl-src belief) and the keep choice as 1.7a's
# (tools/keep_init.py add), both at zero effect; the tokens order, timers, space and targets shut for the whole run (--gate-open 0). The dials,
# live, straight lines (ramp_18a.py): AIM3 over updates 0 to 30, the head's credit 50 to 130, the item rule's lesson and the speed pay in games
# out 160 to 190, the keep choice 210 to 250 (the last stage, the strategy inputs out of the hands, is built with the input clean-up). The damage pay 0.005 from the start (owner, 11-11). No firing cost.
#   start.ps1 -Minutes <n>             phase 1: the start (INTENT_SWITCH 0.02, WEAPON_OWN 0, as b1.2d and 1.3b)
#   start.ps1 -Restart -Minutes <n>    phase 2: the planned restart at the save of update 150 (INTENT_SWITCH 0, WEAPON_OWN 1, as 1.4b on): the
#                                      trainer must be stopped right after that save (stop_18a.ps1), the run folder is used as it is
# Refuses: a trainer running; a missing file; a difference from 1.7a's command beyond the card's; a firing cost above zero; a start that does not
# answer as b1.2d's end; a live.json the trainer would refuse (or one the ramp will write). Then: the trainer (the 8 performance cores, 0xC03C3),
# the watcher (checks every 20 updates, 200 games, against b1.2d's end, the start; every fourth against 1.7a's update 90, the point re-reached;
# Cypher's measures; BOTH SEATS UNDER AIM3 AT ITS END VALUES), the ramp and the self-play logger (all on 8 efficiency cores, 0x3C3C).
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\1.8\1.8a\start.ps1 -Minutes <n> [-Restart]
param([int]$Minutes = 0, [switch]$Restart)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_b1_2d"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_1_8a"
$R2 = Join-Path $SR "duel_gru_1_3b"                             # (1.3b's league: its anchors b1.2d's end, b1.1, v0.6.0's end, 980 inputs)
$PHASE = if ($Restart) { "2" } else { "1" }
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ($Minutes -le 0) { Log "give the length: -Minutes <n> (owner, 2026-10-30: ask him to specify the length)"; exit 1 }
if ($Minutes -le 60) { Log "under an hour left: not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\train_duel_rnn.py") -Pattern '"DMG_REWARD"' -Quiet) -or -not (Select-String -Path (Join-Path $ROOT "sim\duel_env_ffa.py") -Pattern '"AIM3_SIZE_A", "AIM3_SIZE_B"' -Quiet) -or -not (Test-Path (Join-Path $ROOT "tools\b18_init.py"))) { Log "the code here has no live DMG_REWARD, no AIM3 (sim/duel_env_ffa.py) or no tools/b18_init.py: not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_b12d.pt"; $OPTF = Join-Path $K0 "opt_end_b12d.pt"
$C17 = Join-Path $SR "duel_gru_1_7a\keep\policy_end_17a.pt"
$JUDGE = Join-Path $SR "judge\judge_v060_wpn.npz"
foreach ($p in $END, $OPTF, $C17, $JUDGE, (Join-Path $R0 "live.json"), (Join-Path $R0 "live_settings.env")) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
$ANCH = "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt"
foreach ($n in $ANCH) { if (-not (Test-Path (Join-Path $R2 "snapshots\$n"))) { Log "MISSING 1.3b's anchor ${n}: not started"; exit 1 } }
if ($Restart) {
    foreach ($p in (Join-Path $R1 "policy.pt"), (Join-Path $R1 "opt.pt"), (Join-Path $R1 "keep\policy_u150_18a.pt"), (Join-Path $R1 "keep\opt_u150_18a.pt")) { if (-not (Test-Path $p)) { Log "the restart: MISSING ${p}: not started"; exit 1 } }
    $lastU = @(Get-Content (Join-Path $R1 "metrics.jsonl") | Where-Object { $_.Trim() }).Count      # (the run's updates: the lines; the trainer's own number restarts at 1)
    if ($lastU -lt 150 -or $lastU -gt 151) { Log ("the restart is for the save of update 150; the last finished update is " + $lastU + ": not started"); exit 1 }
    if ((Get-FileHash (Join-Path $R1 "policy.pt")).Hash -ne (Get-FileHash (Join-Path $R1 "keep\policy_u150_18a.pt")).Hash) { Log "the run's policy.pt is not the kept save of update 150: not started"; exit 1 }
}
& $PY (Join-Path $HERE "make_files.py") $Minutes $PHASE | ForEach-Object { Log ("train.cmd, $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
# (owner, 11-04 night: "there should be no cost for firing AT ALL") every firing cost at zero in the command
& $PY -c "import re, sys; t = open(sys.argv[1]).read(); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); print('no firing cost in the command: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
# (the card: against 1.7a's command only these differ; phase 1 also the two switches of the restart)
$ALLOW = "--allow=--run,--minutes,--gate-open,--head2-wpg,--pass-odds,--habit-p,COMBAT,AIM3,AIM3_W,AIM3_SIZE_A,AIM3_SIZE_B,AIM3_PURSUIT_TAU,AIM3_PURSUIT_GAIN,AIM3_FIX_TAU" + $(if ($Restart) { "" } else { ",INTENT_SWITCH,WEAPON_OWN" })
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\1.7\1.7a\train.cmd") $ALLOW | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.7a's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
$CK = Join-Path $R1 "keep\control_b12d.pt"; $CR = Join-Path $R1 "keep\control_17a.pt"
if (-not $Restart) {
    if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }
    New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
    # the start: b1.2d's end widened (zero weights, the new tokens shut), the head (1.3b's form), the keep choice (1.7a's form); it answers as
    # b1.2d's end with the new inputs random too (b18_init same); --opt-small-items 1 in the command carries the optimizer's moments over the
    # widened layers, the trainer adds the head's and the keep choice's groups
    $env:CUDA_VISIBLE_DEVICES = "-1"
    $W = Join-Path $R1 "keep\b12d_1053.pt"; $H = Join-Path $R1 "keep\b12d_1053_head.pt"
    & $PY (Join-Path $ROOT "tools\b18_init.py") widen $END $W | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -eq 0) { & $PY (Join-Path $ROOT "tools\head2_init.py") add $W $H --add 1 --chrono-lo 1 --gate 0 --ctrl-src belief | ForEach-Object { Log $_ } }
    if ($LASTEXITCODE -eq 0) { & $PY (Join-Path $ROOT "tools\keep_init.py") add $H (Join-Path $R1 "policy.pt") --opt $OPTF (Join-Path $R1 "opt.pt") | ForEach-Object { Log $_ } }
    if ($LASTEXITCODE -ne 0) { Remove-Item Env:\CUDA_VISIBLE_DEVICES; Log "the start was not made (widen, head or keep): not started"; exit 1 }
    & $PY (Join-Path $ROOT "tools\b18_init.py") same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
    $sameOk = $LASTEXITCODE
    foreach ($n in $ANCH) {
        if ($sameOk -eq 0) {
            & $PY (Join-Path $ROOT "tools\b18_init.py") widen (Join-Path $R2 "snapshots\$n") (Join-Path $R1 "snapshots\$n") | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) { $sameOk = 1 }
        }
    }
    Remove-Item Env:\CUDA_VISIBLE_DEVICES
    if ($sameOk -ne 0) { Log "THE START DOES NOT ANSWER AS b1.2d's END (b18_init same) or a league file was not widened: not started (the run folder has the start files only)"; exit 1 }
    & $PY (Join-Path $HERE "start_live.py") $END (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log ("live.json: " + $_) }
    if ($LASTEXITCODE -ne 0) { Log "live.json not made from b1.2d's: not started"; exit 1 }
    Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_18a.pt")
    Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_18a.pt")
    Copy-Item $END $CK
    Copy-Item $C17 $CR
    Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
    Log ("from " + $END + " widened to 1,053 inputs, the head and the keep choice added at zero effect, with its optimizer; anchors b1.2d's end, b1.1, v0.6.0's end; the judge " + $JUDGE)
} else {
    Remove-Item (Join-Path $R1 "live_status.json") -ErrorAction SilentlyContinue   # (the trainer writes it anew at its first read: waited for below)
    Log ("the planned restart from the save of update 150 (keep\policy_u150_18a.pt, the run's policy.pt and opt.pt as they are): INTENT_SWITCH 0, WEAPON_OWN 1")
}
& $PY (Join-Path $ROOT "tools\run\live_accept.py") (Join-Path $R1 "live.json") --env duel_env_ffa --ramp (Join-Path $HERE "ramp_18a.py") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE TRAINER WOULD REFUSE live.json (or a file the ramp will write): not started"; exit 1 }

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", phase " + $PHASE + ", " + $Minutes + " minutes")
$ST = Join-Path $R1 "live_status.json"; $t0 = Get-Date
while (-not (Test-Path $ST) -and -not $t.HasExited -and ((Get-Date) - $t0).TotalMinutes -lt 20) { Start-Sleep 5 }
$st = if (Test-Path $ST) { Get-Content $ST -Raw | ConvertFrom-Json } else { $null }
if ($null -eq $st -or $st.status -ne "applied") {
    Log ("THE TRAINER DID NOT APPLY live.json (" + $(if ($null -eq $st) { if ($t.HasExited) { "the trainer exited" } else { "no answer in 20 minutes" } } else { $st.reason }) + "): the watcher, the ramp and the logger not started; see " + $RUN + ".log")
    exit 1
}
Log ("live.json applied by the trainer before its first rollout (" + $st.time + ")")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (b1.2d's end)"
# the checks' aim (tools/run/panel.py PANEL_SETS: the whole list, v0.6.0's switches as every run since, then AIM3 at its END values for both seats)
$env:PANEL_SETS = "AIM_LEVEL=3,PERCEPT_SPEED=0,AIM2=1,AIM2_SPLIT=1,AIM2_FOCUS=1,AIM2_FLINCH=1,PERCEPT_SIGMA=0.9,PERCEPT_TAU=0.15,SURPRISE_MS=0,MOTOR_NOISE=0.10,MOTOR_BASE=0.05,AIM2_W=1,AIM2_SPLIT_W=1,AIM2_FOCUS_GAIN=0,AIM2_FOCUS_SIG=1.0,AIM2_C_SLIP=0.023,AIM2_S0=5,AIM2_CAP_SLIP=2.1,AIM2_C_ECC=0.06,AIM2_E0=0,AIM2_CAP_ECC=2.8,FLINCH_PER_DMG=0.012,FLINCH_MAX=0.7,FLINCH_TAU=0.3,VEL_DELAY_MS=200,VEL_WEBER=0.2,RANGE_WEBER=0.19,AIM3=1,AIM3_W=1,AIM3_SIZE_A=0.39,AIM3_SIZE_B=0.355,AIM3_PURSUIT_TAU=0.125,AIM3_PURSUIT_GAIN=1.0,AIM3_FIX_TAU=0.10,COMBAT=1"                  # (COMBAT=1: 1.7a's update 90 reads the order's inputs; 1.8a's weights on them are zero)
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "1.7a's update 90 (the point re-reached)"
Remove-Item Env:\CTRL_TABLE -ErrorAction SilentlyContinue
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$env:CHECK_CYPHER = "1"                                            # Cypher's measures of every check against the start
$CHK = [IntPtr]0x3C3C                                              # (owner, 2026-11-02) everything beside the trainer on 8 efficiency cores; 14-17 left for the owner
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
# (the restart: phase 1's watcher, ramp and logger keep running; each is started here only if it is not there, the ramp then with --resume)
function Running($pat) { @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like $pat -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" }) }
$w0 = Running "*tools\run\watch.py*"; $r0 = Running "*ramp_18a.py*"; $s0 = Running "*selfplay_loop.py*"
if ($w0.Count + $r0.Count + $s0.Count) { Log ("already running, left as they are: watcher " + ($w0 | ForEach-Object { $_.ProcessId }) + " | ramp " + ($r0 | ForEach-Object { $_.ProcessId }) + " | logger " + ($s0 | ForEach-Object { $_.ProcessId })) }
$wid = "-"; $rid = "-"; $sid = "-"
if ($w0.Count -eq 0) {
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK; $wid = $w.Id
Start-Sleep 5 }
if ($r0.Count -eq 0) {
$r = Start-Process -FilePath $PY -ArgumentList $(if ($Restart) { (Join-Path $HERE "ramp_18a.py"), $RUN, "--resume" } else { (Join-Path $HERE "ramp_18a.py"), $RUN }) -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK; $rid = $r.Id }
if ($s0.Count -eq 0) {
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK; $sid = $s.Id }
Log ("started now (- = it was running): watcher " + $wid + " | ramp " + $rid + " (its dials: ramp_18a.py, AIM3 over updates 0 to 30, H2_PG 50 to 130, INTENT_TEACH_W and SPEED_PAY 160 to 190, KEEP_G 210 to 250; never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log) | self-play logger " + $sid + " | all on 0x3C3C; the checks under AIM3's end values, both seats | no guard (owner: never stop the run)")
$TL = Join-Path $SR ($RUN + ".log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {                                    # (the optimizer's state from b1.2d's or the run's own, never a cold start unasked)
    Start-Sleep 10
    if ((Test-Path $TL) -and (Select-String -Path $TL -Pattern "optimizer: " -Quiet)) { $ok = $true; break }
}
if ($ok) { Select-String -Path $TL -Pattern "optimizer: |keep choice|strategy head|combat order|device " | ForEach-Object { Log ("trainer: " + $_.Line) } }
else { Log "no optimizer line in the trainer's log after 10 minutes: look at it" }
