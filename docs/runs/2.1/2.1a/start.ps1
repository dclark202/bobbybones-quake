# 2.1a (owner, 2026-11-12; docs/runs/2.1/2.1a/CARD.md), ON THE OWNER'S COMMAND ONLY.
# From 1.8a's save of update 50 (keep\policy_u50_18a.pt + opt_u50_18a.pt, "b1.2d under AIM3", list 18) brought to the input list 21
# (tools\inputs21.py convert: the hands' 48 instruction columns at zero weights, the token "instr" shut) and given the head's choice of an
# instruction (tools\head21_init.py add: the head's input part at zero, the scorer inside the head with its last layers at zero, its share
# 0), both at zero effect. The dials, live, straight lines (ramp_21a.py; the owner's schedule of 2026-11-12, 220 updates): Part I 0 to 60
# (drills, frozen moments, the token's gate over 0 to 30; the speed pay out over 0 to 40; the head taught in shadow), Part II 60 to 160
# (the head's share 60 to 110, the pay on its choice 110 to 160), Part III 160 to 220 (the strategy inputs out of the hands 160 to 200).
# The row "none" is never offered (INS_NO_NONE=1); the head re-decides every 0.2 s. No restart. No firing cost.
#   start.ps1 -Minutes <n>            the start
#   start.ps1 -Minutes <n> -Resume    the run folder as it is (after a stop on the owner's word): the trainer from its save, the ramp with --resume
# Refuses: a trainer running; a missing file (the measured FIN_RATE table and the map sense's start among them); a difference from 1.8a's
# command beyond the card's; a firing cost above zero; a start that does not answer as update 50; a live.json the trainer would refuse (or
# one the ramp will write). Then: the trainer (the 8 performance cores, 0xC03C3), the watcher (checks every 20 updates, 200 games, against
# the start = 1.8a's update 50; every fourth against 1.8a's end = its update 190, the head in 1.3b's form; Cypher's measures; BOTH SEATS
# UNDER AIM3 AT ITS END VALUES), the ramp and the self-play logger (all on 8 efficiency cores, 0x3C3C). Nothing opens a window.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\2.1\2.1a\start.ps1 -Minutes <n> [-Resume]
param([int]$Minutes = 0, [switch]$Resume)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_1_8a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_2_1a"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ($Minutes -le 0) { Log "give the length: -Minutes <n> (owner, 2026-10-30: ask him to specify the length)"; exit 1 }
if ($Minutes -le 60) { Log "under an hour left: not started"; exit 1 }
if (-not (Test-Path (Join-Path $SR "duel_gru_1_8a")) ) { Log "no data here (a worktree?): the run starts from the repo's own tree: not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\train_duel_rnn.py") -Pattern '"--ins-bind"' -Quiet) -or -not (Select-String -Path (Join-Path $ROOT "sim\duel_env_ffa.py") -Pattern '"INTENT_SWITCH", "WEAPON_OWN",' -Quiet) -or -not (Test-Path (Join-Path $ROOT "tools\head21_init.py"))) { Log "the code here has no binding weapon, no live INTENT_SWITCH or no tools/head21_init.py (branch b21 not merged?): not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn.py*" -and $_.Name -like "python*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$S0 = Join-Path $K0 "policy_u50_18a.pt"; $OPTF = Join-Path $K0 "opt_u50_18a.pt"
$CEND = Join-Path $K0 "policy_end_18a.pt"
$JUDGE = Join-Path $SR "judge\judge_v060_wpn.npz"
$SAMPLE = Join-Path $SR "inputs18\sample_obs.npy"
$FIN = Join-Path $HERE "fin_rate_u50.json"                       # (tools\run\fin_rate.py measure on update 50's recorded games: his own damage a second)
$MS = Join-Path $SR "space\mapsense_start.pt"                    # (tools\run\mapsense_init.py rows, then fit)
if (-not (Test-Path $MS)) { $MS = Join-Path $SR "scratch_21a_start\mapsense_start.pt" }
foreach ($p in $S0, $OPTF, $CEND, $JUDGE, $SAMPLE, $FIN, $MS, (Join-Path $ROOT "tools\inputs21.py"), (Join-Path $ROOT "sim\duel_env_ffa21.py"), (Join-Path $ROOT "sim\input_list_21.json"), (Join-Path $R0 "live.json"), (Join-Path $R0 "live_settings.env")) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
$ANCH = "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt"
foreach ($n in $ANCH) { if (-not (Test-Path (Join-Path $R0 "snapshots\$n"))) { Log "MISSING 1.8a's anchor ${n}: not started"; exit 1 } }
if ($Resume) {
    foreach ($p in (Join-Path $R1 "policy.pt"), (Join-Path $R1 "opt.pt"), (Join-Path $R1 "live.json")) { if (-not (Test-Path $p)) { Log "the resume: MISSING ${p}: not started"; exit 1 } }
}
& $PY (Join-Path $HERE "make_files.py") $Minutes --fin $FIN | ForEach-Object { Log ("train.cmd, $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
# (owner, 11-04 night: "there should be no cost for firing AT ALL") every firing cost at zero in the command
& $PY -c "import re, sys; t = open(sys.argv[1]).read(); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); print('no firing cost in the command: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
# (the card: against 1.8a's command as it last ran only these differ; the list is make_files.py's ALLOW)
$ALLOW = "--allow=" + (& $PY -c "import sys; sys.path.insert(0, sys.argv[1]); import make_files; print(make_files.ALLOW)" $HERE)
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\1.8\1.8a\train.cmd") $ALLOW | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.8a's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
$CK = Join-Path $R1 "keep\control_18a_u50.pt"; $CR = Join-Path $R1 "keep\control_18a_end.pt"
if (-not $Resume) {
    if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }
    New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
    # the start: update 50 on list 21, the head's instruction part added; each step proved by its `same` (0 actions differ on real rows);
    # --opt-small-items 1 in the command carries the optimizer's moments over the widened layers, the trainer adds the group "ins"
    $env:CUDA_VISIBLE_DEVICES = "-1"; $env:INSTR = "1"; $env:INS_WAY = "1"
    $A = Join-Path $R1 "keep\u50_list21.pt"
    & $PY (Join-Path $ROOT "tools\inputs21.py") convert $S0 $A | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -eq 0) { & $PY (Join-Path $ROOT "tools\head21_init.py") add $A (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ } }
    if ($LASTEXITCODE -ne 0) { Remove-Item Env:\CUDA_VISIBLE_DEVICES; Remove-Item Env:\INSTR; Log "the start was not made (list 21 or the head's part): not started"; exit 1 }
    & $PY (Join-Path $ROOT "tools\inputs21.py") same $S0 $A --sample $SAMPLE | ForEach-Object { Log $_ }
    $sameOk = $LASTEXITCODE
    if ($sameOk -eq 0) { & $PY (Join-Path $ROOT "tools\head21_init.py") same $A (Join-Path $R1 "policy.pt") --sample $SAMPLE | ForEach-Object { Log $_ }; $sameOk = $LASTEXITCODE }
    foreach ($n in $ANCH) {                                        # (the league's anchors have no head: list 21 alone)
        if ($sameOk -eq 0) {
            & $PY (Join-Path $ROOT "tools\inputs21.py") convert (Join-Path $R0 "snapshots\$n") (Join-Path $R1 "snapshots\$n") | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) { $sameOk = 1 }
        }
    }
    if ($sameOk -eq 0) {                                           # (the start itself stays in the league: the control as an anchor, under no instruction)
        & $PY (Join-Path $ROOT "tools\head21_init.py") widen-league $A (Join-Path $R1 "snapshots\anchor_18a_u50.pt") | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) { $sameOk = 1 }
    }
    Remove-Item Env:\CUDA_VISIBLE_DEVICES; Remove-Item Env:\INSTR
    if ($sameOk -ne 0) { Log "THE START DOES NOT ANSWER AS UPDATE 50 (inputs21 same, head21_init same) or a league file was not converted: not started (the run folder has the start files only)"; exit 1 }
    & $PY (Join-Path $HERE "start_live.py") $S0 (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log ("live.json: " + $_) }
    if ($LASTEXITCODE -ne 0) { Log "live.json not made from update 50's record: not started"; exit 1 }
    Copy-Item $OPTF (Join-Path $R1 "opt.pt")
    Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_21a.pt")
    Copy-Item $OPTF (Join-Path $R1 "keep\opt_start_21a.pt")
    Copy-Item $MS (Join-Path $R1 "keep\mapsense_start.pt")
    Copy-Item $S0 $CK
    Copy-Item $CEND $CR
    Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
    Log ("from " + $S0 + " on the input list 21 (852 inputs: the hands 844, the brain 691), the head's choice of an instruction added at zero effect, with update 50's optimizer; anchors b1.2d's end, b1.1, v0.6.0's end and the start itself; the map sense's start " + $MS + "; the judge " + $JUDGE)
} else {
    if (Test-Path (Join-Path $R1 "live_status.json")) { Move-Item (Join-Path $R1 "live_status.json") (Join-Path $R1 ("live_status.before_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")) }
    Log "the resume: the run's policy.pt, opt.pt and live.json as they are"
}
& $PY (Join-Path $ROOT "tools\run\live_accept.py") (Join-Path $R1 "live.json") --env duel_env_ffa21 --ramp (Join-Path $HERE "ramp_21a.py") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE TRAINER WOULD REFUSE live.json (or a file the ramp will write): not started"; exit 1 }

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", " + $Minutes + " minutes" + $(if ($Resume) { " (resumed)" } else { "" }))
$ST = Join-Path $R1 "live_status.json"; $t0 = Get-Date
while (-not (Test-Path $ST) -and -not $t.HasExited -and ((Get-Date) - $t0).TotalMinutes -lt 20) { Start-Sleep 5 }
$st = if (Test-Path $ST) { Get-Content $ST -Raw | ConvertFrom-Json } else { $null }
if ($null -eq $st -or $st.status -ne "applied") {
    Log ("THE TRAINER DID NOT APPLY live.json (" + $(if ($null -eq $st) { if ($t.HasExited) { "the trainer exited" } else { "no answer in 20 minutes" } } else { $st.reason }) + "): the watcher, the ramp and the logger not started; see " + $RUN + ".log")
    exit 1
}
Log ("live.json applied by the trainer before its first rollout (" + $st.time + ")")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (1.8a's update 50)"
# the checks' aim (tools/run/panel.py PANEL_SETS: v0.6.0's switches as every run since, then AIM3 at its END values for both seats)
$env:PANEL_SETS = "AIM_LEVEL=3,PERCEPT_SPEED=0,AIM2=1,AIM2_SPLIT=1,AIM2_FOCUS=1,AIM2_FLINCH=1,PERCEPT_SIGMA=0.9,PERCEPT_TAU=0.15,SURPRISE_MS=0,MOTOR_NOISE=0.10,MOTOR_BASE=0.05,AIM2_W=1,AIM2_SPLIT_W=1,AIM2_FOCUS_GAIN=0,AIM2_FOCUS_SIG=1.0,AIM2_C_SLIP=0.023,AIM2_S0=5,AIM2_CAP_SLIP=2.1,AIM2_C_ECC=0.06,AIM2_E0=0,AIM2_CAP_ECC=2.8,FLINCH_PER_DMG=0.012,FLINCH_MAX=0.7,FLINCH_TAU=0.3,VEL_DELAY_MS=200,VEL_WEBER=0.2,RANGE_WEBER=0.19,AIM3=1,AIM3_W=1,AIM3_SIZE_A=0.39,AIM3_SIZE_B=0.355,AIM3_PURSUIT_TAU=0.125,AIM3_PURSUIT_GAIN=1.0,AIM3_FIX_TAU=0.05,AIM3_LEAD=1,AIM3_RELOAD=0,COMBAT=0"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "1.8a's end (update 190: the head in 1.3b's form)"
Remove-Item Env:\CTRL_TABLE -ErrorAction SilentlyContinue
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$env:CHECK_CYPHER = "1"                                            # Cypher's measures of every check against the start
$CHK = [IntPtr]0x3C3C                                              # (owner, 2026-11-02) everything beside the trainer on 8 efficiency cores; 14-17 left for the owner
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
function Running($pat) { @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like $pat -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" }) }
$w0 = Running "*tools\run\watch.py*"; $r0 = Running "*ramp_21a.py*"; $s0 = Running "*selfplay_loop.py*"
if ($w0.Count + $r0.Count + $s0.Count) { Log ("already running, left as they are: watcher " + ($w0 | ForEach-Object { $_.ProcessId }) + " | ramp " + ($r0 | ForEach-Object { $_.ProcessId }) + " | logger " + ($s0 | ForEach-Object { $_.ProcessId })) }
$wid = "-"; $rid = "-"; $sid = "-"
if ($w0.Count -eq 0) {
    $w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
    $w.ProcessorAffinity = $CHK; $wid = $w.Id
    Start-Sleep 5
}
if ($r0.Count -eq 0) {
    $r = Start-Process -FilePath $PY -ArgumentList $(if ($Resume) { (Join-Path $HERE "ramp_21a.py"), $RUN, "--resume" } else { (Join-Path $HERE "ramp_21a.py"), $RUN }) -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
    $r.ProcessorAffinity = $CHK; $rid = $r.Id
}
if ($s0.Count -eq 0) {
    $s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
    $s.ProcessorAffinity = $CHK; $sid = $s.Id
}
Log ("started now (- = it was running): watcher " + $wid + " | ramp " + $rid + " (its dials: ramp_21a.py; never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log) | self-play logger " + $sid + " | all on 0x3C3C; the checks under AIM3's end values, both seats | no guard (owner: never stop the run)")
$TL = Join-Path $SR ($RUN + ".log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {                                    # (the optimizer's state from update 50's or the run's own, never a cold start unasked)
    Start-Sleep 10
    if ((Test-Path $TL) -and (Select-String -Path $TL -Pattern "optimizer: " -Quiet)) { $ok = $true; break }
}
if ($ok) { Select-String -Path $TL -Pattern "optimizer: |binding weapon|instruction's token|strategy head|device " | ForEach-Object { Log ("trainer: " + $_.Line) } }
else { Log "no optimizer line in the trainer's log after 10 minutes: look at it" }
