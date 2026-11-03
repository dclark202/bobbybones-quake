# v0.6.2a's start (owner, 2026-10-29; docs/runs/v0.6.2a/CARD.md): the strategy head faded in only (the item rule stays on: its fade is v0.6.3's), from v0.6.1c's end
# (owner, 2026-10-29 evening: "Yes, prepare it"), on win chance only. Refuses unless: no trainer runs; v0.6.1c has ended (its log
# ends in "exit"); the judge is there and passed its axiom check; the code has WIN_END; the settings check passes against
# v0.6.1c's command (only --run, --minutes and the head's arguments allowed to differ); v0.6.1c's end carries the brain's dial at
# 1 and passes its check; v0.6.1c's live.json ended at BRAIN_FADE 1, WIN_W 1, FADE_V 1; the run folder is new; the start network
# with the head (shut, and with its whole path run) answers exactly as v0.6.1c's end.
# Then: keeps v0.6.1c's end (keep/policy_end_v061c.pt + opt), backs up, makes duel_gru_v0_6_2a (its start = v0.6.1c's end given
# the strategy head shut, with its optimizer; live.json = v0.6.1c's end state with the head's gate cap 0 and the item rule at 1;
# the league = v0.6.1c's end and v0.6.0's end as anchors), starts the trainer, the watcher (checks every 10 updates against
# v0.6.1c's end, every fourth against v0.6.0's end), the ramp (tools/run/ramp_head.py: shut 10 updates, the gate 0.1 a step to 1,
# the head-open save kept, done there: RAMP_HEAD_ONLY; on the clock) and the self-play logger. Nothing stops the run.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.2a\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$R0 = Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_1c"
$RP = Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_0"
$RUN = "duel_gru_v0_6_2a"
$R1 = Join-Path $ROOT "data\sim_runs\$RUN"
$JUDGE = Join-Path $ROOT "data\sim_runs\judge\judge_v061_wpn.npz"
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$last = Get-Content (Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_1c.log") -Tail 1
if ($last -notlike "exit*") { Log "v0.6.1c's log does not end in exit ($last): not started"; exit 1 }
if (-not (Test-Path $JUDGE)) { Log "MISSING the judge ${JUDGE}: not started"; exit 1 }
& $PY -c "import sys, json, numpy as np; m = json.loads(str(np.load(sys.argv[1])['meta'])); print('judge:', m); sys.exit(0 if m.get('axioms_ok') else 1)" $JUDGE | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE JUDGE FAILED ITS AXIOM CHECK: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\v0.6.1c\train.cmd") "--allow=--run,--minutes,--adv-pay-ref,--adv-pay-warm,--head2,--head2-cap,--head2-ctrl-src,--head2-gate,--head2-open,--head2-start" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
$sm = Join-Path $HERE "smoke.log"
if (-not (Test-Path $sm) -or -not ((Get-Content $sm -Tail 1) -like "*ALL PASSED*")) { Log "the smoke run has not passed (smoke.log): not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\duel_env_ffa.py") -Pattern "WIN_END" -SimpleMatch -Quiet)) { Log "the code has no WIN_END: not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

# v0.6.1c's end, kept, and a backup before anything new is made
$K0 = Join-Path $R0 "keep"
if (-not (Test-Path (Join-Path $K0 "policy_end_v061c.pt"))) {
    Copy-Item (Join-Path $R0 "policy.pt") (Join-Path $K0 "policy_end_v061c.pt")
    Copy-Item (Join-Path $R0 "opt.pt") (Join-Path $K0 "opt_end_v061c.pt")
    Log "kept v0.6.1c's end: keep\policy_end_v061c.pt + opt_end_v061c.pt"
}
$END = Join-Path $K0 "policy_end_v061c.pt"
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); assert d.get('BRAIN_FADE') == 1.0 and d.get('WIN_W') == 1.0 and d.get('FADE_V') == 1.0, d; print('v0.6.1c ended at BRAIN_FADE 1, WIN_W 1, FADE_V 1, WIN_GAIN', d.get('WIN_GAIN'), ', LEVEL_PULL', d.get('LEVEL_PULL'))" (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "v0.6.1c's live.json is not at BRAIN_FADE 1 and win pay only: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }

# the brain's dial on v0.6.1c's end: g 1 in the save, and its check (CPU)
$env:CUDA_VISIBLE_DEVICES = "-1"; $env:OPENBLAS_NUM_THREADS = "1"; $env:OMP_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
& $PY -c "import sys, torch; ck = torch.load(sys.argv[1], map_location='cpu', weights_only=False); fd = (ck.get('belief') or {}).get('fade') or {}; print('the end save: belief.fade g', fd.get('g'), 'on', len(fd.get('cols', [])), 'columns'); sys.exit(0 if fd.get('g') == 1.0 and sorted(fd.get('cols', [])) == sorted(ck['rule_fade']['cols']) else 1)" $END | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "v0.6.1c's end does not carry the brain's dial at 1: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\brain_fade_check.py") $ROOT $END | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE BRAIN'S DIAL FAILED ITS CHECK on v0.6.1c's end: not started"; exit 1 }

# the start network: v0.6.1c's end given the strategy head, proven to answer as before (on the CPU)
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$H2I = Join-Path $ROOT "tools\head2_init.py"
$T1 = Join-Path $R1 "watch\start_head_gate1.pt"
& $PY $H2I add $END $T1 --gate 1 --ctrl-src belief | ForEach-Object { Log $_ }
$same = & $PY $H2I same $END $T1 | ForEach-Object { Log $_ }
if (-not ($same -match "actions that differ: 0$")) { Log "THE HEAD (its whole path run) CHANGES HIS ANSWERS: not started"; exit 1 }
& $PY $H2I add $END (Join-Path $R1 "policy.pt") --gate 0 --ctrl-src belief --opt (Join-Path $K0 "opt_end_v061c.pt") (Join-Path $R1 "opt.pt") | ForEach-Object { Log $_ }
$same = & $PY $H2I same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
if (-not ($same -match "actions that differ: 0$")) { Log "THE START NETWORK ANSWERS DIFFERENTLY: not started (its policy.pt left for a look; nothing deleted)"; exit 1 }
Remove-Item Env:CUDA_VISIBLE_DEVICES, Env:OMP_NUM_THREADS
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_v062a.pt")
Copy-Item $END (Join-Path $R1 "snapshots\anchor_v061c_end.pt")
Copy-Item (Join-Path $RP "keep\policy_end_v060.pt") (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(ADV_PAY_REF=10.0, H2_GATE_CAP=0.0, H2_GATE_OPEN=1.0, INTENT_TEACH_W=1.0, VALUE_WARM=0, BRAIN_FADE=1.0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id)
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $END; $env:CTRL_PREV_LABEL = "v0.6.1c's end"
$env:CTRL_REF = Join-Path $RP "keep\policy_end_v060.pt"; $env:CTRL_REF_LABEL = "v0.6.0's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $env:CTRL_PREV
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$env:RAMP_HEAD_ONLY = "1"
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\ramp_head.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | ramp_head " + $r.Id + " (shut 10 updates, then the gate, the head-open save, done; the item rule stays on; on the clock) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
