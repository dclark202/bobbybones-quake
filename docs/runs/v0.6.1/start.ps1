# v0.6.1's start (owner, 2026-10-28: "Build judge. Freeze now, train later"; docs/runs/v0.6.1/CARD.md): pay by win chance only,
# the chance from the frozen judge, from v0.6.0's end. Refuses unless: no trainer runs; v0.6.0 has ended (its log ends in "exit");
# the judge file is there and passed its axiom check; the settings check passes against v0.6.0's command (only --run, --minutes,
# WIN_JUDGE allowed to differ); the code has WIN_JUDGE (the branch v061j merged); the run folder is new.
# Then: keeps v0.6.0's end (keep/policy_end_v060.pt + opt), makes duel_gru_v0_6_1 (its start = v0.6.0's end with its optimizer;
# live.json = v0.6.0's with the blend at step 0; the league = v0.4.2b's end and v0.6.0's end as anchors), starts the trainer, the
# watcher (checks every 10 updates against v0.6.0's end, every fourth against v0.4.2b's end) and the ramp (RAMP_ALWAYS: WIN_GAIN
# sized from updates 21..30, step 1 with the critic's warm-up, then a step every 10 updates and 25 min; no shaping), and the
# self-play logger (the judge's later training data). Nothing stops the run.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.1\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { (Join-Path $env:USERPROFILE "anaconda3\python.exe") }
$R0 = Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_0"
$RUN = "duel_gru_v0_6_1"
$R1 = Join-Path $ROOT "data\sim_runs\$RUN"
$JUDGE = Join-Path $ROOT "data\sim_runs\judge\judge_v060_wpn.npz"
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$last = Get-Content (Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_0.log") -Tail 1
if ($last -notlike "exit*") { Log "v0.6.0's log does not end in exit ($last): not started"; exit 1 }
if (-not (Test-Path $JUDGE)) { Log "MISSING the judge $JUDGE (tools/run/fit_b.py ... --out): not started"; exit 1 }
& $PY -c "import sys, json, numpy as np; m = json.loads(str(np.load(sys.argv[1])['meta'])); print('judge:', m); sys.exit(0 if m.get('axioms_ok') else 1)" $JUDGE | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE JUDGE FAILED ITS AXIOM CHECK: not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\duel_env_ffa.py") -Pattern "WIN_JUDGE" -Quiet)) { Log "the code has no WIN_JUDGE (merge v061j first): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\v0.6.0\train.cmd") "--allow=--run,--minutes,WIN_JUDGE" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

# v0.6.0's end, kept
$K0 = Join-Path $R0 "keep"
if (-not (Test-Path (Join-Path $K0 "policy_end_v060.pt"))) {
    Copy-Item (Join-Path $R0 "policy.pt") (Join-Path $K0 "policy_end_v060.pt")
    Copy-Item (Join-Path $R0 "opt.pt") (Join-Path $K0 "opt_end_v060.pt")
    Log "kept v0.6.0's end: keep\policy_end_v060.pt + opt_end_v060.pt"
}
# the new run's folder
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep") | Out-Null
Copy-Item (Join-Path $K0 "policy_end_v060.pt") (Join-Path $R1 "policy.pt")
Copy-Item (Join-Path $K0 "opt_end_v060.pt") (Join-Path $R1 "opt.pt")
Copy-Item (Join-Path $K0 "policy_end_v060.pt") (Join-Path $R1 "keep\policy_start_v061.pt")
Copy-Item (Join-Path $R0 "snapshots\anchor_v042b_end.pt") (Join-Path $R1 "snapshots\anchor_v042b_end.pt")
Copy-Item (Join-Path $K0 "policy_end_v060.pt") (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(WIN_W=0.0, FADE_V=0.0, WIN_SHAPE_K=0.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }

$env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id)
$WD = Join-Path $R1 "watch"
New-Item -ItemType Directory -Force $WD | Out-Null
$env:CTRL_PREV = Join-Path $K0 "policy_end_v060.pt"; $env:CTRL_PREV_LABEL = "v0.6.0's end"
$env:CTRL_REF = Join-Path $ROOT "data\sim_runs\duel_gru_v0_4_2\keep\policy_end_v042.pt"; $env:CTRL_REF_LABEL = "v0.4.2b's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $env:CTRL_PREV
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$env:RAMP_ALWAYS = "1"; $env:RAMP_K = "0"; $env:RAMP_WARM = "10"; Remove-Item Env:RAMP_GAIN -ErrorAction SilentlyContinue
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\ramp.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (RAMP_ALWAYS, WIN_GAIN from the run's updates 21..30, no shaping) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
