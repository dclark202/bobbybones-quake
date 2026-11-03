# v0.6.1c's start (owner, 2026-10-30; docs/runs/v0.6.1c/CARD.md): back to v0.6.1's save of update 250 (keep/policy_prelevel_v061.pt:
# the win pay faded in, the pull toward level still on), the advantages rescaled to v0.6.0's pay size, the pull and the old belief in
# the brain faded out together over the first ~5-6 h, 12 h in all. Refuses unless: no trainer runs; the code has --adv-pay-ref and
# --brain-fade and WIN_END; the judge is there and passed its axiom check; the settings check passes against v0.6.1b's command (only
# --run and the four --adv-pay-* allowed to differ); the smoke run passed (smoke.log ends ALL PASSED); the run folder is new.
# Then: backs up, makes duel_gru_v0_6_1c (its start = the save of update 250; the optimizer = v0.6.1's end's, the nearest kept: the
# save of update 250 kept none; live.json = v0.6.1's end with LEVEL_PULL 0.95 and BRAIN_FADE 0; the league = the start and v0.6.0's
# end as anchors), starts the trainer, the watcher (checks every 10 updates against the start, every fourth against v0.6.0's end,
# each save at its own pull and dial), the paired ramp (tools/run/ramp_live.py: BRAIN_FADE 0 -> 1 by 0.125 and LEVEL_PULL 0.95 -> 1
# by 0.00625 in the same write, right after each save, at least 25 min apart: eight steps, at ~update 80) and the self-play logger.
# Nothing stops the run.   Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.1c\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$K1 = Join-Path $SR "duel_gru_v0_6_1\keep"
$START = Join-Path $K1 "policy_prelevel_v061.pt"
$RUN = "duel_gru_v0_6_1c"
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
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\v0.6.1b\train.cmd") "--allow=--run,--adv-pay-ref,--adv-pay-tau,--adv-pay-max,--adv-pay-warm" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
$sm = Join-Path $HERE "smoke.log"
if (-not (Test-Path $sm) -or -not ((Get-Content $sm -Tail 1) -like "*ALL PASSED*")) { Log "the smoke run has not passed (smoke.log): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
Copy-Item $START (Join-Path $R1 "policy.pt")
Copy-Item (Join-Path $K1 "opt_end_v061.pt") (Join-Path $R1 "opt.pt")
Copy-Item $START (Join-Path $R1 "keep\policy_start_v061c.pt")
Copy-Item $START (Join-Path $R1 "snapshots\anchor_v061_u250.pt")
Copy-Item (Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt") (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $SR "duel_gru_v0_6_1\live_settings.env") (Join-Path $R1 "live_settings.env")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); assert d.get('WIN_W') == 1.0 and d.get('FADE_V') == 1.0, d; d.update(LEVEL_PULL=0.95, BRAIN_FADE=0.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $SR "duel_gru_v0_6_1\live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }

$env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id)
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $START; $env:CTRL_PREV_LABEL = "v0.6.1's save of update 250 (the start)"
$env:CTRL_REF = Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt"; $env:CTRL_REF_LABEL = "v0.6.0's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $env:CTRL_PREV
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\ramp_live.py"), $RUN, "BRAIN_FADE", "0", "1", "0.125", "--also", "LEVEL_PULL:0.95:1.0:0.00625", "--keep-as", "policy_prefade_v061c.pt" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | paired ramp " + $r.Id + " (BRAIN_FADE 0 -> 1 by 0.125 with LEVEL_PULL 0.95 -> 1 by 0.00625, after each save, 25 min apart) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
