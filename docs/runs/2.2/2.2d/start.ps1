# 2.2d (docs/runs/2.2/2.2d/CARD.md; the build: BUILD.md). RUNS ONLY ON THE OWNER'S COMMAND (CLAUDE.md hard rule 2). Run it from the checkout that holds data\.
# 2.2c's start.ps1 with three pays at zero: from 2.2a's update 90 (-From: keep\policy_90.pt), the start made exactly as 2.2c's (tools/inputs21.py convert
# to list 22b, tools/fight22_init.py layout and norm on -Samples, tools/inputs22c.py convert to list 22c, tools/lever22_init.py layout, the ahead columns'
# statistics measured on the start's play: play22d.py sample, tools/inputs22c.py stats), answering as 2.2a's update 90 (play22d.py ident: 0 actions differ).
# The league (2.2c's league_22c.py): 2.2a's anchors, its last 8 snapshots up to update 90, the control as anchor_22a90.pt, all list 22c. The optimizer:
# 2.2a's update-100 optimizer carried (-ColdOpt: cold). The win scales from win_scale_22d.json (measured on the start's games with 2.2d's pay: BUILD.md).
# The command (make_files.py): 2.2c's with CONTEST_W 0, CEDE_W 0, CONTEST_LOG=1 (the contest pay exactly 0, its counters kept), RAIL_LINE_PAY 0,
# NEAR_PAY 0, RAIL_WOULD=1 and FREE_SEE=1 (two log lines), --kl-heads 1 (the weapon-speed alarm's figure every update). The ramp (ramp_22d.py): H2_WADD
# 1 -> 0 over clocks 0 to 7, the hands' token gate -30 to clock 8 then 0 at clock 17; the lever at 0 to update 10 by the trainer's own count
# (--lev-from 10), LEV_G 1 after; the rail's pickup pay 0.15 and the far-rail pay 0.5 from update 0; the two alarms and the freeze's proof every update;
# a MAJOR line if a dropped pay pays; saves kept at 10, 20, 40, 60, 80 and the end (policy_end_22d.pt). Never held or stepped back.
# The checks (tools/run/watch.py CHECK_AT, in a queue, none skipped): 200 games against the start (2.2a's update 90) at updates 10, 30, 50, 60, 70 and
# the end; at 60 also against 2.1d's end (the long-term control).
# Refuses: no data\ here; a trainer running; a missing file; the items' fit not accepted (make_files.py, the judge's guard); a firing cost above zero;
# a difference from 2.2c's command beyond the names of BUILD.md; a difference from the start file's settings beyond DESC_OX and the new play switches;
# the command's start values not the live file's (start_values.py); a start that does not answer as 2.2a's update 90; a live.json the trainer would
# refuse (or one the ramp could write, or a live name at its range's ends); a run folder that already has a policy.pt. Then: the backup; the trainer
# (0xC03C3), the watcher, the ramp and the self-play logger (0x3C3C). Every window hidden.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\2.2\2.2d\start.ps1 -Minutes <n> -Updates <n> [-From <2.2a's policy_90.pt>]
#   [-Samples <dir with 2.2b's samples s_<map>.npz>] [-Opt <an optimizer file to carry>] [-ColdOpt]
# -DryRun: every check and every file made, into data\sim_runs\scratch_22d_dryrun<-DryRunTag> (log: start_dryrun.log); the trainer and its helpers
# not started, no backup.
param([int]$Minutes = 0, [int]$Updates = 0, [string]$From = "", [string]$Samples = "", [string]$Opt = "", [switch]$ColdOpt, [switch]$DryRun, [string]$DryRunTag = "")
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$C22 = Join-Path $ROOT "docs\runs\2.2\2.2c"
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_2_2a"
$RUN = if ($DryRun) { "scratch_22d_dryrun" + $DryRunTag } else { "duel_gru_2_2d" }
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE $(if ($DryRun) { "start_dryrun.log" } else { "start.log" })
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }
if (-not $From) { $From = Join-Path $R0 "keep\policy_90.pt" }
if (-not $Samples) { $Samples = Join-Path $SR "scratch_22b_start" }
if ($ColdOpt) { $Opt = "" } elseif (-not $Opt) { $Opt = Join-Path $R0 "keep\opt_u100.pt" }

if ($Minutes -le 60) { Log "-Minutes (over 60) is needed: not started"; exit 1 }
if ($Updates -le 0) { Log "-Updates (the run's --max-updates, the owner's length: at most 80) is needed: not started"; exit 1 }
if ($Updates -gt 80) { Log "-Updates over 80 (the owner's length: at most 80 updates): not started"; exit 1 }
if (-not (Test-Path (Join-Path $ROOT "data"))) { Log "NO data FOLDER IN $ROOT (a worktree?): run it from the main checkout: not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$C21D = Join-Path $SR "duel_gru_2_1d\keep\policy_end_21d.pt"
$JUDGE = Join-Path $SR "judge\judge_v060_wpn.npz"
$ITEMS = Join-Path $ROOT "docs\runs\2.2\2.2b\items_22b.json"
$WS = Join-Path $HERE "win_scale_22d.json"
$LIVE0 = Join-Path $R0 "live.json"; $LSE = Join-Path $R0 "live_settings.env"
$MAPS = "bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure"
$SAMP = @($MAPS | ForEach-Object { Join-Path $Samples ("s_" + $_ + ".npz") })
foreach ($p in @($From, $C21D, $JUDGE, $ITEMS, $WS, $LIVE0, $LSE, (Join-Path $C22 "league_22c.py"), (Join-Path $C22 "start_values.py")) + $SAMP + @($Opt | Where-Object { $_ })) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

# the command: 2.2c's as it ran, with 2.2d's changes and the measured win scales; the judge's guard inside make_files.py
$ki = & $PY -c "import json, sys; d = json.load(open(sys.argv[1])); assert d['k_items'] >= 1 and d['k_fight'] >= 1; print('{:.4g} {:.4g}'.format(d['k_items'], d['k_fight']))" $WS
if ($LASTEXITCODE -ne 0) { Log "win_scale_22d.json unreadable or a scale under 1: not started"; exit 1 }
$KI, $KF = $ki.Trim().Split(" ")
& $PY (Join-Path $HERE "make_files.py") $Minutes $Updates --win-scale-items $KI --win-scale-fight $KF | ForEach-Object { Log ("train.cmd, $Minutes minutes, $Updates updates: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed (the items' fit not accepted? the judge's guard?): not started"; exit 1 }
$CMD = Join-Path $HERE "train.cmd"
& $PY -c "import re, sys; t = open(sys.argv[1]).read(); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG', 'COST_FIRE_W') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); print('no firing cost in the command: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" $CMD | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
& $PY -c "import re, sys; t = open(sys.argv[1]).read(); g = lambda n: (re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or [None])[-1]; want = dict(CONTEST='1', CONTEST_LOG='1', CONTEST_W='0', CEDE_W='0', RAIL_LINE_PAY='0', NEAR_PAY='0', NEAR_MISS='1', RAIL_CHAIN='1', RAIL_PICK_PAY='0.15', RAIL_FAR_PAY='0.5', RAIL_WOULD='1', FREE_SEE='1'); bad = {n: g(n) for n, v in want.items() if g(n) != v}; bad.update({} if ' --kl-heads 1 ' in t else {'--kl-heads': 'not 1'}); print('the dropped pays at 0 and the counters on in the command: ' + str(want) if not bad else 'THE COMMAND IS NOT 2.2d s: ' + str(bad)); sys.exit(1 if bad else 0)" $CMD | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "the command's dropped pays or counters are not as the card: not started"; exit 1 }
$ALLOW = "--run,--minutes,--max-updates,--kl-heads,--win-scale-items,--win-scale-fight,CONTEST_W,CEDE_W,CONTEST_LOG,RAIL_LINE_PAY,NEAR_PAY,RAIL_WOULD,FREE_SEE"
& $PY (Join-Path $ROOT "tools\run\check_settings.py") $CMD --ref (Join-Path $C22 "train.cmd") "--allow=$ALLOW" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 2.2c's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") $CMD --ck $From "--allow=DESC_OX,AHEAD_IN,RAIL_FAR_PAY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 2.2a's update 90): not started"; exit 1 }

# the start's live.json (2.2a's last, the rater's dials out, 2.2d's at their start); the command's start values must be the live file's
if (-not $DryRun) { & $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ } }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
& $PY (Join-Path $HERE "start_live.py") $LIVE0 (Join-Path $R1 "live.json") | ForEach-Object { Log ("live.json: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "live.json not made from 2.2a's last live.json (not at the values 2.2a ran with?): not started"; exit 1 }
& $PY (Join-Path $C22 "start_values.py") $CMD (Join-Path $R1 "live.json") | Where-Object { $_ -notmatch "^ok" } | ForEach-Object { Log ("start values: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "THE COMMAND'S START VALUES ARE NOT THE LIVE FILE'S (start_values.py): not started"; exit 1 }
$env:QLBOT_ROOT = $ROOT
& $PY (Join-Path $HERE "accept_22d.py") (Join-Path $R1 "live.json") $CMD | ForEach-Object { Log ("live accept: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "THE TRAINER WOULD REFUSE live.json (or a file the ramp may write, or a live name at an end of its range): not started"; exit 1 }

# the start file: as 2.2c's (list 22b, the fight layout and norm, list 22c, the lever, the ahead columns measured); it must answer as 2.2a's update 90
$env:CUDA_VISIBLE_DEVICES = "-1"; $env:OMP_NUM_THREADS = "1"; $env:OPENBLAS_NUM_THREADS = "1"
$K = Join-Path $R1 "keep"
$C22B = Join-Path $K "start_conv_22b.pt"; $L22B = Join-Path $K "start_layout_22b.pt"; $N22B = Join-Path $K "start_norm_22b.pt"
$C22C = Join-Path $K "start_conv_22c.pt"; $LEV = Join-Path $K "start_lever_22c.pt"; $AHS = Join-Path $K "start_ahead_sample.npz"
& $PY (Join-Path $ROOT "tools\inputs21.py") --old 20e --new 22b --group "b22b fight" --token fight22 convert $From $C22B | ForEach-Object { Log ("convert 22b: " + $_) }
$sameOk = $LASTEXITCODE
if ($sameOk -eq 0) { & $PY (Join-Path $ROOT "tools\fight22_init.py") layout $C22B $L22B | ForEach-Object { Log ("layout: " + $_) }; $sameOk = $LASTEXITCODE }
if ($sameOk -eq 0) { & $PY (Join-Path $ROOT "tools\fight22_init.py") norm $L22B $N22B --samples ($SAMP -join ",") | ForEach-Object { Log ("norm: " + $_) }; $sameOk = $LASTEXITCODE }
if ($sameOk -eq 0) { & $PY (Join-Path $ROOT "tools\inputs22c.py") convert $N22B $C22C | ForEach-Object { Log ("convert 22c: " + $_) }; $sameOk = $LASTEXITCODE }
if ($sameOk -eq 0) { & $PY (Join-Path $ROOT "tools\lever22_init.py") layout $C22C $LEV | ForEach-Object { Log ("lever: " + $_) }; $sameOk = $LASTEXITCODE }
if ($sameOk -eq 0) { & $PY (Join-Path $HERE "play22d.py") sample $LEV $AHS --frames 1500 --matches 16 | ForEach-Object { Log ("ahead sample: " + $_) }; $sameOk = $LASTEXITCODE }
if ($sameOk -eq 0) { & $PY (Join-Path $ROOT "tools\inputs22c.py") stats $LEV $AHS (Join-Path $R1 "policy.pt") | ForEach-Object { Log ("ahead stats: " + $_) }; $sameOk = $LASTEXITCODE }
if ($sameOk -eq 0) {
    $same = @(& $PY (Join-Path $HERE "play22d.py") ident $From (Join-Path $R1 "policy.pt") | ForEach-Object { "$_" })
    $same | ForEach-Object { Log ("ident: " + $_) }
    if (-not ($same | Where-Object { $_ -match "^ALL PASSED" })) { $sameOk = 1 }
}
if ($sameOk -eq 0) { & $PY (Join-Path $C22 "league_22c.py") $R0 $From (Join-Path $R1 "snapshots") (Join-Path $K "league_22b") | ForEach-Object { Log ("league: " + $_) }; $sameOk = $LASTEXITCODE }
Remove-Item Env:\CUDA_VISIBLE_DEVICES; Remove-Item Env:\OMP_NUM_THREADS
if ($sameOk -ne 0) { Log "THE START WAS NOT MADE, DOES NOT ANSWER AS 2.2a's UPDATE 90, OR THE LEAGUE WAS NOT CONVERTED: not started (see above)"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $K "policy_start_22d.pt")
if ($Opt) { Copy-Item $Opt (Join-Path $R1 "opt.pt"); Copy-Item $Opt (Join-Path $K "opt_start_22d.pt") }
$CK = Join-Path $K "control_22a90.pt"; $CR = Join-Path $K "control_21d.pt"
Copy-Item $From $CK
Copy-Item $C21D $CR
Copy-Item $LSE (Join-Path $R1 "live_settings.env")
Log ("from " + $From + " (list 22c, the rater out, the lever in, measured; the optimizer " + $(if ($Opt) { "carried from " + $Opt } else { "cold" }) + ", --lr-warm 60); the league in snapshots\; the judge " + $JUDGE + " with the items " + $ITEMS + "; the win scales " + $KI + " (items) and " + $KF + " (fight)")
if ($DryRun) { Log "DRY RUN: every check passed and every file is made in $R1; the backup, the trainer, the watcher, the ramp and the logger NOT started"; exit 0 }

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $CMD -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from " + $From + ", " + $Minutes + " minutes, at most " + $Updates + " updates (--max-updates)")
$ST = Join-Path $R1 "live_status.json"; $t0 = Get-Date
while (-not (Test-Path $ST) -and -not $t.HasExited -and ((Get-Date) - $t0).TotalMinutes -lt 20) { Start-Sleep 5 }
$st = if (Test-Path $ST) { Get-Content $ST -Raw | ConvertFrom-Json } else { $null }
if ($null -eq $st -or $st.status -ne "applied") {
    Log ("THE TRAINER DID NOT APPLY live.json (" + $(if ($null -eq $st) { if ($t.HasExited) { "the trainer exited" } else { "no answer in 20 minutes" } } else { $st.reason }) + "): the watcher, the ramp and the logger not started; see " + $RUN + ".log")
    exit 1
}
Log ("live.json applied by the trainer before its first rollout (" + $st.time + ")")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the control (2.2a's update 90)"
$env:PANEL_SETS = "AIM_LEVEL=3,PERCEPT_SPEED=0,AIM2=1,AIM2_SPLIT=1,AIM2_FOCUS=1,AIM2_FLINCH=1,PERCEPT_SIGMA=0.9,PERCEPT_TAU=0.15,SURPRISE_MS=0,MOTOR_NOISE=0.10,MOTOR_BASE=0.05,AIM2_W=1,AIM2_SPLIT_W=1,AIM2_FOCUS_GAIN=0,AIM2_FOCUS_SIG=1.0,AIM2_C_SLIP=0.023,AIM2_S0=5,AIM2_CAP_SLIP=2.1,AIM2_C_ECC=0.06,AIM2_E0=0,AIM2_CAP_ECC=2.8,FLINCH_PER_DMG=0.012,FLINCH_MAX=0.7,FLINCH_TAU=0.3,VEL_DELAY_MS=200,VEL_WEBER=0.2,RANGE_WEBER=0.19,AIM3=1,AIM3_W=1,AIM3_SIZE_A=0.39,AIM3_SIZE_B=0.355,AIM3_PURSUIT_TAU=0.125,AIM3_PURSUIT_GAIN=1.0,AIM3_FIX_TAU=0.05,AIM3_LEAD=1,AIM3_RELOAD=0,KNOCK_QL=1,KNOCK_NOW=1,KEEP_ZONE=1,KEEP_SIG=1,FIGHT=1,OUT_LIVE=1.5,AHEAD_IN=1"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "2.1d's end (the long-term control)"
Remove-Item Env:\CTRL_TABLE -ErrorAction SilentlyContinue
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_GAMES = "20"                                               # 200 games a check (owner, 2026-11-02)
$env:CHECK_AT = "10,30,50,60,70"; $env:CHECK_REF_AT = "60"; $env:CHECK_END = "1"   # (the card: in a queue, none skipped; 60 also against 2.1d's end; the end)
$env:CHECK_CYPHER = "1"
$CHK = [IntPtr]0x3C3C
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_22d.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " (checks at 10, 30, 50, 60 (also against 2.1d's end), 70 and the end, queued) | ramp " + $r.Id + " (ramp_22d.py: H2_WADD 1 -> 0 over clocks 0 to 7, the token gate over 8 to 17, the lever on from update 11 by the trainer's count; saves kept at 10, 20, 40, 60, 80 and the end; never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log) | self-play logger " + $s.Id + " | all on 0x3C3C")
$TL = Join-Path $SR ($RUN + ".log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 10
    if ((Test-Path $TL) -and (Select-String -Path $TL -Pattern "optimizer: " -Quiet)) { $ok = $true; break }
}
if ($ok) { Select-String -Path $TL -Pattern "optimizer: |held draw|2.2c|2.2d|league|strategy head|dodge token|device " | ForEach-Object { Log ("trainer: " + $_.Line) } }
else { Log "no optimizer line in the trainer's log after 10 minutes: look at it" }
