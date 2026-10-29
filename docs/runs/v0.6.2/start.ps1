# v0.6.2's start (owner, 2026-10-29; docs/runs/v0.6.2/CARD.md): the strategy head replaces the item rule, from v0.6.1's end, on
# win chance only. Refuses unless: no trainer runs; v0.6.1 has ended (its log ends in "exit"); the refitted judge is there and
# passed its axiom check; the settings check passes against v0.6.1's command (only --run, WIN_JUDGE and the head's arguments
# allowed to differ); the run folder is new; the start network with the head (shut) answers exactly as v0.6.1's end.
# Then: keeps v0.6.1's end (keep/policy_end_v061.pt + opt), backs up, makes duel_gru_v0_6_2 (its start = v0.6.1's end given the
# strategy head shut, with its optimizer; live.json = v0.6.1's end state with the head's gate cap 0 and the item rule at 1; the
# league = v0.6.1's end and v0.6.0's end as anchors), starts the trainer, the watcher (checks every 10 updates against v0.6.1's
# end, every fourth against v0.6.0's end), the ramp (tools/run/ramp_head.py: shut 10 updates, the gate 0.1 a step to 1, the
# head-open save kept, then the item rule 0.1 a step to 0; on the clock) and the self-play logger. Nothing stops the run.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\v0.6.2\start.ps1
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$R0 = Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_1"
$RP = Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_0"
$RUN = "duel_gru_v0_6_2"
$R1 = Join-Path $ROOT "data\sim_runs\$RUN"
$JUDGE = Join-Path $ROOT "data\sim_runs\judge\judge_v061_wpn.npz"
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$last = Get-Content (Join-Path $ROOT "data\sim_runs\duel_gru_v0_6_1.log") -Tail 1
if ($last -notlike "exit*") { Log "v0.6.1's log does not end in exit ($last): not started"; exit 1 }
if (-not (Test-Path $JUDGE)) { Log "MISSING the judge $JUDGE (tools/run/fit_b.py, then tools/run/judge_weapons.py): not started"; exit 1 }
& $PY -c "import sys, json, numpy as np; m = json.loads(str(np.load(sys.argv[1])['meta'])); print('judge:', m); sys.exit(0 if m.get('axioms_ok') else 1)" $JUDGE | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE JUDGE FAILED ITS AXIOM CHECK: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\v0.6.1\train.cmd") "--allow=--run,WIN_JUDGE,WIN_END,--head2,--head2-cap,--head2-ctrl-src,--head2-gate,--head2-open,--head2-start" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\duel_env_ffa.py") -Pattern "WIN_END" -Quiet)) { Log "the code has no WIN_END (merge v062pay first): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

# v0.6.1's end, kept, and a backup before anything new is made
$K0 = Join-Path $R0 "keep"
if (-not (Test-Path (Join-Path $K0 "policy_end_v061.pt"))) {
    Copy-Item (Join-Path $R0 "policy.pt") (Join-Path $K0 "policy_end_v061.pt")
    Copy-Item (Join-Path $R0 "opt.pt") (Join-Path $K0 "opt_end_v061.pt")
    Log "kept v0.6.1's end: keep\policy_end_v061.pt + opt_end_v061.pt"
}
& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }

# the start network: v0.6.1's end given the strategy head, proven to answer as before (on the CPU)
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"; $env:OPENBLAS_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$H2I = Join-Path $ROOT "tools\head2_init.py"
$T1 = Join-Path $R1 "watch\start_head_gate1.pt"
& $PY $H2I add (Join-Path $K0 "policy_end_v061.pt") $T1 --gate 1 --ctrl-src belief | ForEach-Object { Log $_ }
$same = & $PY $H2I same (Join-Path $K0 "policy_end_v061.pt") $T1 | ForEach-Object { Log $_ }
if (-not ($same -match "actions that differ: 0$")) { Log "THE HEAD (its whole path run) CHANGES HIS ANSWERS: not started"; exit 1 }
& $PY $H2I add (Join-Path $K0 "policy_end_v061.pt") (Join-Path $R1 "policy.pt") --gate 0 --ctrl-src belief --opt (Join-Path $K0 "opt_end_v061.pt") (Join-Path $R1 "opt.pt") | ForEach-Object { Log $_ }
$same = & $PY $H2I same (Join-Path $K0 "policy_end_v061.pt") (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
if (-not ($same -match "actions that differ: 0$")) { Log "THE START NETWORK ANSWERS DIFFERENTLY: not started (its policy.pt left for a look; nothing deleted)"; exit 1 }
Remove-Item Env:CUDA_VISIBLE_DEVICES
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_v062.pt")
Copy-Item (Join-Path $K0 "policy_end_v061.pt") (Join-Path $R1 "snapshots\anchor_v061_end.pt")
Copy-Item (Join-Path $RP "keep\policy_end_v060.pt") (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(H2_GATE_CAP=0.0, H2_GATE_OPEN=1.0, INTENT_TEACH_W=1.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id)
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = Join-Path $K0 "policy_end_v061.pt"; $env:CTRL_PREV_LABEL = "v0.6.1's end"
$env:CTRL_REF = Join-Path $RP "keep\policy_end_v060.pt"; $env:CTRL_REF_LABEL = "v0.6.0's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $env:CTRL_PREV
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\ramp_head.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | ramp_head " + $r.Id + " (shut 10 updates, then the gate, the head-open save, the item rule; on the clock) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
