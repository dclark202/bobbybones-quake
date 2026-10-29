# v0.6.1b's start (owner, 2026-10-29: "run v0.6.1b overnight to tomorrow morning"; docs/runs/v0.6.1b/CARD.md): the old hand-built
# belief faded out of the brain, from v0.6.1's end, with the game-end pay fix. Refuses unless: no trainer runs; v0.6.1 has ended
# (its log ends in "exit"); the judge file is there and passed its axiom check; the code has --brain-fade and the game-end fix
# ($FIX_MARK below); the settings check passes against v0.6.1's command (only --run, --minutes, --brain-fade allowed to differ);
# the brain's dial passes its identity check on v0.6.1's end (tools/run/brain_fade_check.py); the run folder is new.
# Then: keeps v0.6.1's end (keep/policy_end_v061.pt + opt), makes duel_gru_v0_6_1b (its start = v0.6.1's end with its optimizer;
# live.json = v0.6.1's as it ended with BRAIN_FADE 0; the league = v0.6.1's end and v0.6.0's end as anchors), starts the trainer,
# the watcher (checks every 10 updates against v0.6.1's end, every fourth against v0.6.0's end), the brain's ramp
# (tools/run/ramp_live.py: BRAIN_FADE 0 -> 1 by 0.1, right after each save, at least 25 min apart; the save before the first step
# kept as keep/policy_prefade_v061b.pt) and the self-play logger. No WIN_GAIN ramp (it stays as v0.6.1 ended). Nothing stops the run.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.1b\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { (Join-Path $env:USERPROFILE "anaconda3\python.exe") }
$R0 = Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_1"
$RUN = "duel_gru_v0_6_1b"
$R1 = Join-Path $ROOT "data\sim_runs\$RUN"
$JUDGE = Join-Path $ROOT "data\sim_runs\judge\judge_v060_wpn.npz"
$LOG = Join-Path $HERE "start.log"
# the game-end pay fix (docs/runs/v0.6.1/WINPAY_END.md): a string its code carries in sim\duel_env.py, set by whoever lands it.
# Empty: not started. If the fix is a switch, it must also be set in train.cmd and allowed below.
$FIX_MARK = "WIN_END"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$last = Get-Content (Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_1.log") -Tail 1
if ($last -notlike "exit*") { Log "v0.6.1's log does not end in exit ($last): not started"; exit 1 }
if (-not (Test-Path $JUDGE)) { Log "MISSING the judge ${JUDGE}: not started"; exit 1 }
& $PY -c "import sys, json, numpy as np; m = json.loads(str(np.load(sys.argv[1])['meta'])); print('judge:', m); sys.exit(0 if m.get('axioms_ok') else 1)" $JUDGE | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE JUDGE FAILED ITS AXIOM CHECK: not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\train_duel_rnn.py") -Pattern "--brain-fade" -SimpleMatch -Quiet)) { Log "the code has no --brain-fade: not started"; exit 1 }
if ($FIX_MARK -eq "") { Log "the game-end pay fix is not named (FIX_MARK in start.ps1): not started"; exit 1 }
foreach ($f in "duel_env.py", "duel_env_ffa.py") {
    if (-not (Select-String -Path (Join-Path $ROOT "sim\$f") -Pattern $FIX_MARK -SimpleMatch -Quiet)) { Log "sim\$f has no '$FIX_MARK' (the game-end fix; duel_env_ffa.py regenerated?): not started"; exit 1 }
}
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\v0.6.1\train.cmd") "--allow=--run,--minutes,--brain-fade,WIN_END" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

# v0.6.1's end, kept
$K0 = Join-Path $R0 "keep"
if (-not (Test-Path (Join-Path $K0 "policy_end_v061.pt"))) {
    Copy-Item (Join-Path $R0 "policy.pt") (Join-Path $K0 "policy_end_v061.pt")
    Copy-Item (Join-Path $R0 "opt.pt") (Join-Path $K0 "opt_end_v061.pt")
    Log "kept v0.6.1's end: keep\policy_end_v061.pt + opt_end_v061.pt"
}
# the brain's dial on v0.6.1's end: at 0 exactly as before, at 1 the columns count for nothing (CPU, one thread, low priority)
$env:OPENBLAS_NUM_THREADS = "1"; $env:OMP_NUM_THREADS = "1"; $env:CUDA_VISIBLE_DEVICES = "-1"
& $PY (Join-Path $ROOT "tools\run\brain_fade_check.py") $ROOT (Join-Path $K0 "policy_end_v061.pt") | ForEach-Object { Log $_ }
$bfc = $LASTEXITCODE
Remove-Item Env:OMP_NUM_THREADS, Env:CUDA_VISIBLE_DEVICES
if ($bfc -ne 0) { Log "THE BRAIN'S DIAL FAILED ITS CHECK on v0.6.1's end: not started"; exit 1 }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); assert d.get('WIN_W') == 1.0 and d.get('FADE_V') == 1.0, d; print('v0.6.1 ended at WIN_W 1, FADE_V 1, WIN_GAIN', d.get('WIN_GAIN'), ', LEVEL_PULL', d.get('LEVEL_PULL'))" (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "v0.6.1's live.json is not at win pay only: not started"; exit 1 }

# the new run's folder
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep") | Out-Null
Copy-Item (Join-Path $K0 "policy_end_v061.pt") (Join-Path $R1 "policy.pt")
Copy-Item (Join-Path $K0 "opt_end_v061.pt") (Join-Path $R1 "opt.pt")
Copy-Item (Join-Path $K0 "policy_end_v061.pt") (Join-Path $R1 "keep\policy_start_v061b.pt")
Copy-Item (Join-Path $R0 "snapshots\anchor_v060_end.pt") (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $K0 "policy_end_v061.pt") (Join-Path $R1 "snapshots\anchor_v061_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(BRAIN_FADE=0.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }

$env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id)
$WD = Join-Path $R1 "watch"
New-Item -ItemType Directory -Force $WD | Out-Null
$env:CTRL_PREV = Join-Path $K0 "policy_end_v061.pt"; $env:CTRL_PREV_LABEL = "v0.6.1's end"
$env:CTRL_REF = Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_0\keep\policy_end_v060.pt"; $env:CTRL_REF_LABEL = "v0.6.0's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $env:CTRL_PREV
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\ramp_live.py"), $RUN, "BRAIN_FADE", "0", "1", "0.1", "--keep-as", "policy_prefade_v061b.pt" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | brain's ramp " + $r.Id + " (BRAIN_FADE 0 -> 1 by 0.1 after each save, 25 min apart) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
