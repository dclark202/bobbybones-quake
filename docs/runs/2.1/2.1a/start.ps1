# 2.1a, the blend (owner, 2026-11-13: "freeze decisions; blend 2.0 and 2.1 into one ... call it 2.1a"; docs/runs/2.1/2.1a/CARD.md), ON THE
# OWNER'S COMMAND ONLY. From 1.7a's update 90 (keep\policy_u90_17a.pt + opt_u90_17a.pt) in three proved steps, each answering as update 90:
#   tools\inputs20d.py convert   the input list 20d (2.0d's cut, the order's ten kept, the dodge group at zero behind a shut token)
#   tools\inputs21.py --old 20d --new 21d convert   the list 21d (the hands' 48 instruction columns at zero, the token "instr" shut)
#   tools\head21_init.py add     the head's choice of an instruction (its input part at zero, the scorer inside the head at zero, share 0)
# The head's decisions (his target, the weapon key, the keep choice) are frozen the whole run (--freeze-choice 1). The dials, live, straight
# lines (ramp_21a.py): AIM3 over updates 0 to 30; the dodge inputs, the frozen moments, the drills and the instruction's token over 30 to 60;
# the weapon-only moments over 60 to 90; held after. The head's instruction plays on no game seat (INS_G 0): taught in shadow.
#   start.ps1 -Minutes <n>            the start
#   start.ps1 -Minutes <n> -Resume    the run folder as it is (after a stop on the owner's word)
# Refuses: a trainer running; a missing file (the measured FIN_RATE table and the map sense's start among them); a difference from 1.7a's
# command beyond the card's; a firing cost above zero; a start that does not answer as update 90; a live.json the trainer would refuse (or one
# the ramp will write). Then: the trainer (0xC03C3), the watcher (checks every 20 updates, 200 games, against 1.7a's update 90; every fourth
# against 1.8a's end; BOTH SEATS UNDER AIM3 AT ITS END VALUES AND THE CORRECTED KNOCKBACK), the ramp and the self-play logger (0x3C3C).
# Nothing opens a window.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\2.1\2.1a\start.ps1 -Minutes <n> [-Resume]
param([int]$Minutes = 0, [switch]$Resume)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_1_7a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_2_1a"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ($Minutes -le 60) { Log "give the length: -Minutes <n> over 60 (owner, 2026-10-30: ask him to specify the length)"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\train_duel_rnn.py") -Pattern '"--freeze-choice"' -Quiet) -or -not (Select-String -Path (Join-Path $ROOT "sim\duel_env_ffa.py") -Pattern '"DODGE_G"' -Quiet)) { Log "the code here has no --freeze-choice or no DODGE_G: not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn.py*" -and $_.Name -like "python*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$U90 = Join-Path $K0 "policy_u90_17a.pt"; $OPTF = Join-Path $K0 "opt_u90_17a.pt"
$C18 = Join-Path $SR "duel_gru_1_8a\keep\policy_end_18a.pt"
$JUDGE = Join-Path $SR "judge\judge_v060_wpn.npz"
$SAMPLE = Join-Path $SR "inputs20d\sample_obs.npy"              # (47,992 full rows of 1.7a's update 90 under 2.0d's settings)
$FIN = Join-Path $HERE "fin_rate_17a_u90.json"                  # (tools\run\fin_rate.py measure: his own damage a second, AIM3's end values, the corrected knockback)
$MS = Join-Path $SR "space\mapsense_start.pt"                    # (tools\run\mapsense_init.py rows, then fit)
foreach ($p in $U90, $OPTF, $C18, $JUDGE, $SAMPLE, $FIN, $MS, (Join-Path $ROOT "sim\duel_env_ffa21d.py"), (Join-Path $ROOT "sim\input_list_21d.json"), (Join-Path $R0 "live.json"), (Join-Path $R0 "live_settings.env")) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
$ANCH = "anchor_16a.pt", "anchor_15a.pt", "anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt"
foreach ($n in $ANCH) { if (-not (Test-Path (Join-Path $R0 "snapshots\$n"))) { Log "MISSING 1.7a's anchor ${n}: not started"; exit 1 } }
if ($Resume) {
    foreach ($p in (Join-Path $R1 "policy.pt"), (Join-Path $R1 "opt.pt"), (Join-Path $R1 "live.json")) { if (-not (Test-Path $p)) { Log "the resume: MISSING ${p}: not started"; exit 1 } }
}
& $PY (Join-Path $HERE "make_files.py") $Minutes --fin $FIN | ForEach-Object { Log ("train.cmd, $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
& $PY -c "import re, sys; t = open(sys.argv[1]).read(); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); print('no firing cost in the command: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
$ALLOW = "--allow=" + (& $PY -c "import sys; sys.path.insert(0, sys.argv[1]); import make_files; print(make_files.ALLOW)" $HERE)
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\1.7\1.7a\train.cmd") $ALLOW | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.7a's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $U90 "$ALLOW,CONTACT_FREE,LEVEL_PULL,RAIL_FAR_PAY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.7a's update 90): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
$CK = Join-Path $R1 "keep\control_17a.pt"; $CR = Join-Path $R1 "keep\control_18a.pt"
if (-not $Resume) {
    if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }
    New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
    $env:CUDA_VISIBLE_DEVICES = "-1"; $env:INSTR = "1"; $env:INS_WAY = "1"
    $A20 = Join-Path $R1 "keep\u90_list20d.pt"; $A21 = Join-Path $R1 "keep\u90_list21d.pt"; $O20 = Join-Path $R1 "keep\opt_u90_list20d.pt"
    & $PY (Join-Path $ROOT "tools\inputs20d.py") convert $U90 $A20 --sample $SAMPLE --opt $OPTF $O20 --report (Join-Path $R1 "keep\inputs20d_start.json") | ForEach-Object { Log $_ }
    $ok = $LASTEXITCODE
    if ($ok -eq 0) { & $PY (Join-Path $ROOT "tools\inputs21.py") --old 20d --new 21d convert $A20 $A21 | ForEach-Object { Log $_ }; $ok = $LASTEXITCODE }
    if ($ok -eq 0) { & $PY (Join-Path $ROOT "tools\head21_init.py") add $A21 (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }; $ok = $LASTEXITCODE }
    if ($ok -eq 0) { & $PY (Join-Path $ROOT "tools\inputs20d.py") same $U90 $A20 --sample $SAMPLE | ForEach-Object { Log $_ }; $ok = $LASTEXITCODE }
    if ($ok -eq 0) { & $PY (Join-Path $ROOT "tools\inputs21.py") --old 20d --new 21d same $A20 $A21 --sample $SAMPLE | ForEach-Object { Log $_ }; $ok = $LASTEXITCODE }
    if ($ok -eq 0) { & $PY (Join-Path $ROOT "tools\head21_init.py") same $A21 (Join-Path $R1 "policy.pt") --sample $SAMPLE | ForEach-Object { Log $_ }; $ok = $LASTEXITCODE }
    foreach ($n in @("anchor_17a.pt") + $ANCH) {                  # (the control in the league: 1.7a's update 90 itself; every anchor the same way)
        if ($ok -eq 0) {
            $in = if ($n -eq "anchor_17a.pt") { $U90 } else { Join-Path $R0 "snapshots\$n" }
            $b20 = Join-Path $R1 ("keep\" + $n.Replace(".pt", "_20d.pt")); $b21 = Join-Path $R1 ("keep\" + $n.Replace(".pt", "_21d.pt"))
            & $PY (Join-Path $ROOT "tools\inputs20d.py") convert $in $b20 --sample $SAMPLE --league | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) { $ok = 1; continue }
            & $PY (Join-Path $ROOT "tools\inputs21.py") --old 20d --new 21d convert $b20 $b21 | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) { $ok = 1; continue }
            & $PY -c "import sys, torch; ck = torch.load(sys.argv[1], weights_only=False, map_location='cpu'); sys.exit(0 if ck.get('head2') else 3)" $b21
            if ($LASTEXITCODE -eq 0) {                                # (a league file with a head: widened to the learner's head, its share 0)
                & $PY (Join-Path $ROOT "tools\head21_init.py") widen-league $b21 (Join-Path $R1 "snapshots\$n") | ForEach-Object { Log $_ }
                if ($LASTEXITCODE -ne 0) { $ok = 1 }
            } else { Copy-Item $b21 (Join-Path $R1 "snapshots\$n"); Log ("$n has no head: list 21d alone") }
        }
    }
    Remove-Item Env:\CUDA_VISIBLE_DEVICES; Remove-Item Env:\INSTR; Remove-Item Env:\INS_WAY
    if ($ok -ne 0) { Log "THE START DOES NOT ANSWER AS 1.7a's UPDATE 90 (a same failed) or a league file was not converted: not started (the run folder has the start files only)"; exit 1 }
    & $PY (Join-Path $HERE "start_live.py") $U90 (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log ("live.json: " + $_) }
    if ($LASTEXITCODE -ne 0) { Log "live.json not made from update 90's record: not started"; exit 1 }
    Copy-Item $O20 (Join-Path $R1 "opt.pt")
    Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_21a.pt")
    Copy-Item $O20 (Join-Path $R1 "keep\opt_start_21a.pt")
    Copy-Item $MS (Join-Path $R1 "keep\mapsense_start.pt")
    Copy-Item $U90 $CK
    Copy-Item $C18 $CR
    Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
    Log ("from " + $U90 + " on the input list 21d (869 inputs: the hands 861, the brain 691), the head's choice of an instruction added at zero effect, with update 90's optimizer (converted; the new columns, tokens and the group 'ins' by --opt-small-items); anchors 1.7a's update 90, 1.6a's end, 1.5a's end, 1.3b's end, b1.2d's end, b1.1, v0.6.0's end; the map sense's start " + $MS + "; the judge " + $JUDGE)
} else {
    if (Test-Path (Join-Path $R1 "live_status.json")) { Move-Item (Join-Path $R1 "live_status.json") (Join-Path $R1 ("live_status.before_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")) }
    Log "the resume: the run's policy.pt, opt.pt and live.json as they are"
}
$env:DODGE_IN = "1"; $env:INSTR = "1"
& $PY (Join-Path $ROOT "tools\run\live_accept.py") (Join-Path $R1 "live.json") --env duel_env_ffa21d --ramp (Join-Path $HERE "ramp_21a.py") | ForEach-Object { Log $_ }
$la = $LASTEXITCODE
Remove-Item Env:\DODGE_IN; Remove-Item Env:\INSTR
if ($la -ne 0) { Log "THE TRAINER WOULD REFUSE live.json (or a file the ramp will write): not started"; exit 1 }

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
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the control (1.7a's update 90)"
# the checks' aim and physics (tools/run/panel.py PANEL_SETS): v0.6.0's switches, AIM3 at its END values and the corrected knockback, both seats
$env:PANEL_SETS = "AIM_LEVEL=3,PERCEPT_SPEED=0,AIM2=1,AIM2_SPLIT=1,AIM2_FOCUS=1,AIM2_FLINCH=1,PERCEPT_SIGMA=0.9,PERCEPT_TAU=0.15,SURPRISE_MS=0,MOTOR_NOISE=0.10,MOTOR_BASE=0.05,AIM2_W=1,AIM2_SPLIT_W=1,AIM2_FOCUS_GAIN=0,AIM2_FOCUS_SIG=1.0,AIM2_C_SLIP=0.023,AIM2_S0=5,AIM2_CAP_SLIP=2.1,AIM2_C_ECC=0.06,AIM2_E0=0,AIM2_CAP_ECC=2.8,FLINCH_PER_DMG=0.012,FLINCH_MAX=0.7,FLINCH_TAU=0.3,VEL_DELAY_MS=200,VEL_WEBER=0.2,RANGE_WEBER=0.19,AIM3=1,AIM3_W=1,AIM3_SIZE_A=0.39,AIM3_SIZE_B=0.355,AIM3_PURSUIT_TAU=0.125,AIM3_PURSUIT_GAIN=1.0,AIM3_FIX_TAU=0.05,AIM3_LEAD=1,AIM3_RELOAD=0,KNOCK_QL=1,KNOCK_NOW=1"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "1.8a's end (the long-term control)"
Remove-Item Env:\CTRL_TABLE -ErrorAction SilentlyContinue
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$env:CHECK_CYPHER = "1"
$CHK = [IntPtr]0x3C3C
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
function Running($pat) { @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like $pat -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" }) }
$w0 = Running "*tools\run\watch.py*"; $r0 = Running "*ramp_21a.py*"; $s0 = Running "*selfplay_loop.py*"
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
Log ("started now (- = it was running): watcher " + $wid + " | ramp " + $rid + " (ramp_21a.py: AIM3 0-30, the dodge inputs and the instruction's silent parts 30-60, weapon-only moments 60-90; never held; a check under 40% a MAJOR PROBLEM) | self-play logger " + $sid + " | all on 0x3C3C; the checks under AIM3's end values and the corrected knockback, both seats")
$TL = Join-Path $SR ($RUN + ".log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 10
    if ((Test-Path $TL) -and (Select-String -Path $TL -Pattern "optimizer: " -Quiet)) { $ok = $true; break }
}
if ($ok) { Select-String -Path $TL -Pattern "optimizer: |freeze-choice|dodge token|instruction's token|binding weapon|device " | ForEach-Object { Log ("trainer: " + $_.Line) } }
else { Log "no optimizer line in the trainer's log after 10 minutes: look at it" }
