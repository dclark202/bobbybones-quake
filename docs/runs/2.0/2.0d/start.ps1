# 2.0d (owner, 2026-11-13: "an overnight run to clean up the network by removing dead inputs, and make the structural fixes for aim/dodging and
# simulator. That's it"; docs/runs/2.0/2.0d/CARD.md), ON THE OWNER'S COMMAND ONLY. -Minutes is the trainer's limit; the run's length is 90
# updates (stop_at_90.ps1 once keep\policy_u90_20d.pt is kept).
# From 1.7a's update 90 (keep/policy_u90_17a.pt + opt_u90_17a.pt) brought to the input list 20d by tools/inputs20d.py (the cut, the columns
# re-measured on 1.7a's own play, the dodge group at zero weights behind a shut token), answering as update 90 (inputs20d same); the league's
# anchors the same way. Dials (ramp_20d.py): AIM3 over updates 0 to 30, DODGE_G over 30 to 60; the pay's steps in live.json (start_live.py).
# Refuses: a trainer running; a missing file; a difference from 1.7a's command beyond the card's; a firing cost above zero; a start that does
# not answer as update 90; a live.json the trainer would refuse (or one the ramp will write). Then: the trainer (0xC03C3), the watcher (checks
# every 20 updates, 200 games, against 1.7a's update 90, the control; every fourth against 1.8a's end; BOTH SEATS UNDER AIM3 AT ITS END VALUES
# AND THE CORRECTED KNOCKBACK), the ramp and the self-play logger (0x3C3C).
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\2.0\2.0d\start.ps1 -Minutes <n>
param([int]$Minutes = 0)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_1_7a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_2_0d"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ($Minutes -le 60) { Log "-Minutes (over 60) is needed: not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$U90 = Join-Path $K0 "policy_u90_17a.pt"; $OPTF = Join-Path $K0 "opt_u90_17a.pt"
$C18 = Join-Path $SR "duel_gru_1_8a\keep\policy_end_18a.pt"
$JUDGE = Join-Path $SR "judge\judge_v060_wpn.npz"
$SAMPLE = Join-Path $SR "inputs20d\sample_obs.npy"
foreach ($p in $U90, $OPTF, $C18, $JUDGE, $SAMPLE) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
$ANCH = "anchor_16a.pt", "anchor_15a.pt", "anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt"
foreach ($n in $ANCH) { if (-not (Test-Path (Join-Path $R0 "snapshots\$n"))) { Log "MISSING 1.7a's anchor ${n}: not started"; exit 1 } }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd, $Minutes minutes: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
& $PY -c "import re, sys; t = open(sys.argv[1]).read(); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); print('no firing cost in the command: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
$ALLOW = "--run,--minutes,--keep-g,--gate-open,--pass-odds,--habit-p,--env,--brain-fade,AIM3,AIM3_W,AIM3_SIZE_A,AIM3_SIZE_B,AIM3_PURSUIT_TAU,AIM3_PURSUIT_GAIN,AIM3_FIX_TAU,AIM3_LEAD,AIM3_RELOAD,KNOCK_QL,KNOCK_NOW,DODGE_IN,DODGE_G"
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\1.7\1.7a\train.cmd") "--allow=$ALLOW" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.7a's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $U90 "--allow=$ALLOW,CONTACT_FREE,LEVEL_PULL,RAIL_FAR_PAY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.7a's update 90): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"
& $PY (Join-Path $ROOT "tools\inputs20d.py") convert $U90 (Join-Path $R1 "policy.pt") --sample $SAMPLE --opt $OPTF (Join-Path $R1 "opt.pt") --report (Join-Path $R1 "keep\inputs20d_start.json") | ForEach-Object { Log $_ }
$sameOk = $LASTEXITCODE
if ($sameOk -eq 0) {
    & $PY (Join-Path $ROOT "tools\inputs20d.py") same $U90 (Join-Path $R1 "policy.pt") --sample $SAMPLE | ForEach-Object { Log $_ }
    $sameOk = $LASTEXITCODE
}
foreach ($n in @("anchor_17a.pt") + $ANCH) {                      # (the control in the league: 1.7a's update 90 itself, converted the same way)
    if ($sameOk -eq 0) {
        $in = if ($n -eq "anchor_17a.pt") { $U90 } else { Join-Path $R0 "snapshots\$n" }
        & $PY (Join-Path $ROOT "tools\inputs20d.py") convert $in (Join-Path $R1 "snapshots\$n") --sample $SAMPLE --league | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -ne 0) { $sameOk = 1 }
    }
}
Remove-Item Env:\CUDA_VISIBLE_DEVICES
if ($sameOk -ne 0) { Log "THE START DOES NOT ANSWER AS 1.7a's UPDATE 90 (inputs20d same) or a league file was not converted: not started (the run folder has the start files only)"; exit 1 }
& $PY (Join-Path $HERE "start_live.py") $U90 (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log ("live.json: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "live.json not made from the save's record: not started"; exit 1 }
$env:DODGE_IN = "1"
& $PY (Join-Path $ROOT "tools\run\live_accept.py") (Join-Path $R1 "live.json") --env duel_env_ffa20d --ramp (Join-Path $HERE "ramp_20d.py") | ForEach-Object { Log $_ }
$la = $LASTEXITCODE
Remove-Item Env:\DODGE_IN
if ($la -ne 0) { Log "THE TRAINER WOULD REFUSE live.json (or a file the ramp will write): not started"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_20d.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_20d.pt")
$CK = Join-Path $R1 "keep\control_17a.pt"; $CR = Join-Path $R1 "keep\control_18a.pt"
Copy-Item $U90 $CK
Copy-Item $C18 $CR
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $U90 + " brought to list 20d (tools/inputs20d.py, the sample " + $SAMPLE + "), with its optimizer; anchors 1.7a's update 90, 1.6a's end, 1.5a's end, 1.3b's end, b1.2d's end, b1.1, v0.6.0's end (list 20d); the judge " + $JUDGE)

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from 1.7a's update 90, " + $Minutes + " minutes (the run: 90 updates, stop_at_90.ps1)")
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
# the checks' aim and physics (tools/run/panel.py PANEL_SETS): v0.6.0's switches as every run since, AIM3 at its END values (11-11 tuning) and the
# corrected knockback, for both seats
$env:PANEL_SETS = "AIM_LEVEL=3,PERCEPT_SPEED=0,AIM2=1,AIM2_SPLIT=1,AIM2_FOCUS=1,AIM2_FLINCH=1,PERCEPT_SIGMA=0.9,PERCEPT_TAU=0.15,SURPRISE_MS=0,MOTOR_NOISE=0.10,MOTOR_BASE=0.05,AIM2_W=1,AIM2_SPLIT_W=1,AIM2_FOCUS_GAIN=0,AIM2_FOCUS_SIG=1.0,AIM2_C_SLIP=0.023,AIM2_S0=5,AIM2_CAP_SLIP=2.1,AIM2_C_ECC=0.06,AIM2_E0=0,AIM2_CAP_ECC=2.8,FLINCH_PER_DMG=0.012,FLINCH_MAX=0.7,FLINCH_TAU=0.3,VEL_DELAY_MS=200,VEL_WEBER=0.2,RANGE_WEBER=0.19,AIM3=1,AIM3_W=1,AIM3_SIZE_A=0.39,AIM3_SIZE_B=0.355,AIM3_PURSUIT_TAU=0.125,AIM3_PURSUIT_GAIN=1.0,AIM3_FIX_TAU=0.05,AIM3_LEAD=1,AIM3_RELOAD=0,KNOCK_QL=1,KNOCK_NOW=1"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "1.8a's end (the long-term control)"
Remove-Item Env:\CTRL_TABLE -ErrorAction SilentlyContinue
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$env:CHECK_CYPHER = "1"
$CHK = [IntPtr]0x3C3C
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_20d.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (ramp_20d.py: AIM3 over updates 0 to 30, DODGE_G over 30 to 60; never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log) | self-play logger " + $s.Id + " | all on 0x3C3C; the checks under AIM3's end values and KNOCK_QL/KNOCK_NOW, both seats")
$TL = Join-Path $SR ($RUN + ".log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 10
    if ((Test-Path $TL) -and (Select-String -Path $TL -Pattern "optimizer: " -Quiet)) { $ok = $true; break }
}
if ($ok) { Select-String -Path $TL -Pattern "optimizer: |keep choice|combat order|dodge token|device " | ForEach-Object { Log ("trainer: " + $_.Line) } }
else { Log "no optimizer line in the trainer's log after 10 minutes: look at it" }
