# 2.2a (docs/runs/2.2/DESIGN.md "2.2a in detail"). RUNS ONLY ON THE OWNER'S COMMAND (CLAUDE.md hard rule 2). Run it from the checkout that holds data\.
# From 2.1d's end (-From, with its optimizer -FromOpt) given 2.2a's parts inside the head at zero (tools/out22_init.py add: the outlook with its facts
# and seven kinds, the tracker, the desc outlooks with their inputs' norm measured on -Samples, the second value; out_g 0, out_pick 0, out_src 0;
# the checkpoint's "map_sense" from the start file), answering as the save (tools/run/play22.py same on recorded frames: 0 frames differ). The
# league's anchors (2.1d's snapshots\anchor_*.pt) and the control (2.1d's end, as anchor_21d.pt) as they are: the trainer gives a league file
# without the parts their layers with the last ones at zero (they never play). The ramp (ramp_22a.py): OUT_TRIAL 0 -> 0.03 over updates 0 to 10;
# OUT_G from the owner's watch\out_mark.json (it always wins) or THE AUTOMATIC MARK decided once at update 60 from watch\auto_mark.json (this
# folder's auto_mark.json, checked here); saves kept at 10, 60, 100, 140 and the end. PULL_G and HELD_G (2.1d's end) never written.
# Refuses: no data\ here; a trainer running; a missing file; a difference from 2.1d's command beyond --run, --minutes, --max-updates, --outlook,
# --out-kinds, --out22, --map-sense, --map-sense-init, DESC_OX, FIGHT_TRUTH, JUDGE_ITEMS; a firing cost above zero; a start that does not answer as
# the source; a live.json the trainer would refuse (or one the ramp could write, for the marks 0.5, 2, 20 and either source); an auto_mark.json the
# ramp would refuse; a run folder that already has a policy.pt. Then: the trainer (0xC03C3), the watcher (checks every 20 updates, 200 games,
# against 2.1d's end; every fourth against 2.0e's end), the ramp and the self-play logger (0x3C3C). Every window hidden.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\2.2\2.2a\start.ps1 -Minutes <n> -Updates <n> [-From <2.1d save>] [-FromOpt <its opt>]
#   [-Samples <dir with play22 samples s_<map>.npz and s_bloodrun_frames.npz>] [-NoItems]
param([int]$Minutes = 0, [int]$Updates = 0, [string]$From = "", [string]$FromOpt = "", [string]$Samples = "", [switch]$NoItems)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_2_1d"
$RUN = "duel_gru_2_2a"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }
if (-not $From) { $From = Join-Path $R0 "keep\policy_end_21d.pt" }
if (-not $FromOpt) { $FromOpt = Join-Path $R0 "keep\opt_end_21d.pt" }
if (-not $Samples) { $Samples = Join-Path $SR "scratch_22a_sample3" }

if ($Minutes -le 60) { Log "-Minutes (over 60) is needed: not started"; exit 1 }
if ($Updates -le 0) { Log "-Updates (the run's --max-updates, the owner's length) is needed: not started"; exit 1 }
if (-not (Test-Path (Join-Path $ROOT "data"))) { Log "NO data FOLDER IN $ROOT (a worktree?): run it from the main checkout after the merge: not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$C20E = Join-Path $R0 "keep\control_20e.pt"
$JUDGE = Join-Path $SR "judge\judge_v060_wpn.npz"
$MSS = Join-Path $SR "space\mapsense_start.pt"
$ITEMS = Join-Path $HERE "items_22a.json"
$AUTO = Join-Path $HERE "auto_mark.json"
$LIVE0 = Join-Path $R0 "live.json"; $LSE = Join-Path $R0 "live_settings.env"
$MAPS = "bloodrun", "aerowalk", "campgrounds", "toxicity", "hektik", "sinister"
$SAMP = @($MAPS | ForEach-Object { Join-Path $Samples ("s_" + $_ + ".npz") })
$FRAMES = Join-Path $Samples "s_bloodrun_frames.npz"
foreach ($p in @($From, $FromOpt, $C20E, $JUDGE, $MSS, $AUTO, $LIVE0, $LSE, $FRAMES) + $SAMP) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
$ANCH = @(Get-ChildItem -Path (Join-Path $R0 "snapshots") -Filter "anchor_*.pt" | ForEach-Object { $_.Name })
if ($ANCH.Count -eq 0) { Log "MISSING 2.1d's anchors (snapshots\anchor_*.pt): not started"; exit 1 }
$IT = @()
if (-not $NoItems) {                                                  # (the judge that sees the items: only an ACCEPTED fit; -NoItems: the run without it)
    if (-not (Test-Path $ITEMS)) { Log "MISSING $ITEMS (the items' judge; -NoItems to start without it): not started"; exit 1 }
    $IT = @("--items", "docs/runs/2.2/2.2a/items_22a.json")
}
& $PY (Join-Path $HERE "make_files.py") $Minutes $Updates @IT | ForEach-Object { Log ("train.cmd, $Minutes minutes, $Updates updates: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed (an items' fit not accepted? -NoItems): not started"; exit 1 }
& $PY -c "import re, sys; t = open(sys.argv[1]).read(); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); print('no firing cost in the command: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
$ALLOW = "--run,--minutes,--max-updates,--outlook,--out-kinds,--out22,--map-sense,--map-sense-init,DESC_OX,FIGHT_TRUTH,JUDGE_ITEMS"
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\2.1\2.1d\train.cmd") "--allow=$ALLOW" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 2.1d's command): not started"; exit 1 }
$CKALLOW = "$ALLOW,AIM3_W,AIM3_SIZE_A,AIM3_SIZE_B,AIM3_LEAD,AIM3_RELOAD,DODGE_G,RAIL_FAR_PAY,CONTACT_FREE,LEVEL_PULL"
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $From "--allow=$CKALLOW" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against the source save): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }
$ac = & $PY -c "import importlib.util, json, sys; sp = importlib.util.spec_from_file_location('r', sys.argv[1]); R = importlib.util.module_from_spec(sp); sp.loader.exec_module(R); c, w = R.auto_check(json.load(open(sys.argv[2]))); print('auto_mark.json: ' + ('accepted: ' + json.dumps(c) if c else 'REFUSED: ' + str(w))); sys.exit(0 if c else 1)" (Join-Path $HERE "ramp_22a.py") $AUTO
Log $ac
if ($LASTEXITCODE -ne 0) { Log "auto_mark.json refused by the ramp: not started"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"; $env:OMP_NUM_THREADS = "1"; $env:OPENBLAS_NUM_THREADS = "1"; $env:QLBOT_ROOT = $ROOT
& $PY (Join-Path $ROOT "tools\out22_init.py") add $From (Join-Path $R1 "policy.pt") --samples ($SAMP -join ",") | ForEach-Object { Log $_ }
$sameOk = $LASTEXITCODE
if ($sameOk -eq 0) {
    $same = @(& $PY (Join-Path $ROOT "tools\run\play22.py") same --src $From --init (Join-Path $R1 "policy.pt") --frames $FRAMES | ForEach-Object { "$_" })
    $same | ForEach-Object { Log ("play22 same: " + $_) }
    if (-not ($same | Where-Object { $_ -match "^ALL PASSED" })) { $sameOk = 1 }
}
Remove-Item Env:\CUDA_VISIBLE_DEVICES; Remove-Item Env:\OMP_NUM_THREADS
if ($sameOk -ne 0) { Log "THE START DOES NOT ANSWER AS THE SOURCE SAVE (play22 same): not started (the run folder has the start file only)"; exit 1 }
foreach ($n in $ANCH) { Copy-Item (Join-Path $R0 "snapshots\$n") (Join-Path $R1 "snapshots\$n") }   # (as they are: the trainer gives them the parts at zero)
Copy-Item $From (Join-Path $R1 "snapshots\anchor_21d.pt")             # (the control in the league: the source save itself)
Copy-Item $FromOpt (Join-Path $R1 "opt.pt")                           # (the optimizer as it is: none of the new parts is in its groups)
& $PY (Join-Path $HERE "start_live.py") $LIVE0 (Join-Path $R1 "live.json") | ForEach-Object { Log ("live.json: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "live.json not made from 2.1d's last live.json (not at the values 2.1d ran with?): not started"; exit 1 }
Copy-Item $AUTO (Join-Path $R1 "watch\auto_mark.json")
$env:DODGE_IN = "1"; $env:DESC_OX = "1"; $env:FIGHT_TRUTH = "1"
$la = 0
foreach ($mk in "0.5,60,100", "2,60,100", "20,60,100") {             # (every file the ramp could write: OUT_TRIAL's line, a mark of 0.5, 2, 20, either source)
    foreach ($src in "0", "1") {
        $env:RAMP22A_MARK = $mk; $env:RAMP22A_SRC = $src
        & $PY (Join-Path $ROOT "tools\run\live_accept.py") (Join-Path $R1 "live.json") --env duel_env_ffa20e --ramp (Join-Path $HERE "ramp_22a.py") | ForEach-Object { Log ("mark " + $mk + " source " + $src + ": " + $_) }
        if ($LASTEXITCODE -ne 0) { $la = 1 }
    }
}
Remove-Item Env:\RAMP22A_MARK; Remove-Item Env:\RAMP22A_SRC; Remove-Item Env:\DODGE_IN; Remove-Item Env:\DESC_OX; Remove-Item Env:\FIGHT_TRUTH
if ($la -ne 0) { Log "THE TRAINER WOULD REFUSE live.json (or a file the ramp may write): not started"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_22a.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_22a.pt")
$CK = Join-Path $R1 "keep\control_21d.pt"; $CR = Join-Path $R1 "keep\control_20e.pt"
Copy-Item $From $CK
Copy-Item $C20E $CR
Copy-Item $LSE (Join-Path $R1 "live_settings.env")
Log ("from " + $From + " with 2.2a's parts inside the head (out22_init add), with its optimizer; anchors " + ($ANCH -join ", ") + " and anchor_21d.pt (the source) as they are; the judge " + $JUDGE + "; the items' judge " + $(if ($NoItems) { "OFF (-NoItems)" } else { $ITEMS }))

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
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
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the control (2.1d's end)"
$env:PANEL_SETS = "AIM_LEVEL=3,PERCEPT_SPEED=0,AIM2=1,AIM2_SPLIT=1,AIM2_FOCUS=1,AIM2_FLINCH=1,PERCEPT_SIGMA=0.9,PERCEPT_TAU=0.15,SURPRISE_MS=0,MOTOR_NOISE=0.10,MOTOR_BASE=0.05,AIM2_W=1,AIM2_SPLIT_W=1,AIM2_FOCUS_GAIN=0,AIM2_FOCUS_SIG=1.0,AIM2_C_SLIP=0.023,AIM2_S0=5,AIM2_CAP_SLIP=2.1,AIM2_C_ECC=0.06,AIM2_E0=0,AIM2_CAP_ECC=2.8,FLINCH_PER_DMG=0.012,FLINCH_MAX=0.7,FLINCH_TAU=0.3,VEL_DELAY_MS=200,VEL_WEBER=0.2,RANGE_WEBER=0.19,AIM3=1,AIM3_W=1,AIM3_SIZE_A=0.39,AIM3_SIZE_B=0.355,AIM3_PURSUIT_TAU=0.125,AIM3_PURSUIT_GAIN=1.0,AIM3_FIX_TAU=0.05,AIM3_LEAD=1,AIM3_RELOAD=0,KNOCK_QL=1,KNOCK_NOW=1,KEEP_ZONE=1,KEEP_SIG=1"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "2.0e's end (the long-term control)"
Remove-Item Env:\CTRL_TABLE -ErrorAction SilentlyContinue
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$env:CHECK_CYPHER = "1"
$CHK = [IntPtr]0x3C3C
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_22a.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (ramp_22a.py: OUT_TRIAL 0 -> 0.03 over updates 0 to 10; OUT_G from the owner's watch\out_mark.json or the automatic mark at update 60; saves kept at 10, 60, 100, 140 and the end; never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log) | self-play logger " + $s.Id + " | all on 0x3C3C")
$TL = Join-Path $SR ($RUN + ".log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 10
    if ((Test-Path $TL) -and (Select-String -Path $TL -Pattern "optimizer: " -Quiet)) { $ok = $true; break }
}
if ($ok) { Select-String -Path $TL -Pattern "optimizer: |held draw|slow plan|outlook|2.2a|map sense|strategy head|dodge token|device " | ForEach-Object { Log ("trainer: " + $_.Line) } }
else { Log "no optimizer line in the trainer's log after 10 minutes: look at it" }
