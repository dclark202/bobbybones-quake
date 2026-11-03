# v0.6.1e's start (owner, 2026-10-31; docs/runs/v0.6.1e/CARD.md): v0.6.1's save of update 90, the pay to half the table and half win chance over
# 40 updates (WIN_W 0.5, FADE_V 0.125 -> 0.5, WIN_GAIN 0.33 -> 0.87), the rescale at 10, then the pull and the brain's old belief
# faded out together. Refuses unless: no trainer runs; the code and the judge are there; the settings check passes against v0.6.1e's
# command (only --run, --minutes differ); smoke.log ends ALL PASSED; the run folder is new. Nothing stops the run.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.1e\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$K1 = Join-Path $SR "duel_gru_v0_6_1\keep"
$START = Join-Path $K1 "policy_90.pt"
$RUN = "duel_gru_v0_6_1e"
$R1 = Join-Path $SR $RUN
$JUDGE = Join-Path $SR "judge\judge_v061_wpn.npz"
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
foreach ($p in "--adv-pay-ref", "--brain-fade") {
    if (-not (Select-String -Path (Join-Path $ROOT "sim\train_duel_rnn.py") -Pattern $p -SimpleMatch -Quiet)) { Log "the trainer has no ${p}: not started"; exit 1 }
}
if (-not (Select-String -Path (Join-Path $ROOT "sim\duel_env_ffa.py") -Pattern "WIN_END" -SimpleMatch -Quiet)) { Log "the code has no WIN_END: not started"; exit 1 }
if (-not (Test-Path $START)) { Log "MISSING the start $START : not started"; exit 1 }
if (-not (Test-Path $JUDGE)) { Log "MISSING the judge ${JUDGE}: not started"; exit 1 }
& $PY -c "import sys, json, numpy as np; m = json.loads(str(np.load(sys.argv[1])['meta'])); print('judge axioms_ok', m.get('axioms_ok'), 'logloss', m.get('logloss')); sys.exit(0 if m.get('axioms_ok') else 1)" $JUDGE | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE JUDGE FAILED ITS AXIOM CHECK: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\v0.6.1d\train.cmd") "--allow=--run,--minutes" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
$sm = Join-Path $HERE "smoke.log"
if (-not (Test-Path $sm) -or -not ((Get-Content $sm -Tail 1) -like "*ALL PASSED*")) { Log "the smoke run has not passed (smoke.log): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
Copy-Item $START (Join-Path $R1 "policy.pt")
Copy-Item (Join-Path $K1 "opt_end_v061.pt") (Join-Path $R1 "opt.pt")
Copy-Item $START (Join-Path $R1 "keep\policy_start_v061e.pt")
Copy-Item $START (Join-Path $R1 "snapshots\anchor_v061_u90.pt")
Copy-Item (Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt") (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $SR "duel_gru_v0_6_1\live_settings.env") (Join-Path $R1 "live_settings.env")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); assert d.get('WIN_W') == 1.0 and d.get('FADE_V') == 1.0, d; d.update(WIN_W=0.5, FADE_V=0.125, WIN_GAIN=0.33, ADV_PAY_REF=10.0, LEVEL_PULL=0.95, BRAIN_FADE=0.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $SR "duel_gru_v0_6_1\live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }

$env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id)
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $START; $env:CTRL_PREV_LABEL = "v0.6.1's save of update 90 (the start)"
$env:CTRL_REF = Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt"; $env:CTRL_REF_LABEL = "v0.6.0's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $env:CTRL_PREV
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_fades.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | fades " + $r.Id + " (the pull 0.95 -> 1 and the brain 0 -> 1 together, eight steps, after saves, 25 min apart) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
