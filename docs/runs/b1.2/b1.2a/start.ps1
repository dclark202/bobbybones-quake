# b1.2a's start (owner, 2026-10-31; docs/runs/b1.2/b1.2a/CARD.md): the strategy head faded in, learning from combat plus win pay, the item rule on.
# Refuses unless: no trainer runs; the start save and its optimizer are there; the settings check passes against b1.1a's command; smoke.log ends ALL PASSED; the run folder is new; the start with the head (shut, and with its
# whole path run) answers exactly as the save without it. The live dials (brain, pull, lock, win pay) come from the save and b1.1a's live.json. Then the trainer, the watcher, the ramp, the self-play logger. Nothing stops the run.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\b1.2\b1.2a\start.ps1 [-Save policy_nopull_b11a.pt] [-Opt opt_end_b11a.pt]     (default: b1.1a's end; files in duel_gru_b1_1a\keep)
param([string]$Save = "policy_end_b11a.pt", [string]$Opt = "opt_end_b11a.pt")
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_b1_1a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_b1_2a"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started (b1.1a stopped and its end kept first?)"; exit 1 }
$END = Join-Path $K0 $Save; $OPTF = Join-Path $K0 $Opt
foreach ($p in $END, $OPTF, (Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt")) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\b1.1\b1.1a\train.cmd") "--allow=--run,--minutes,--head2,--head2-cap,--head2-ctrl-src,--head2-gate,--head2-open,--head2-start,--head2-pay,H2_START" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED: not started"; exit 1 }
$f = Join-Path $HERE "smoke.log"
if (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 1) -like "*ALL PASSED*")) { Log "smoke.log has not passed: not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"; $env:OPENBLAS_NUM_THREADS = "1"; $env:OMP_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$H2I = Join-Path $ROOT "tools\head2_init.py"
$T1 = Join-Path $R1 "watch\start_head_gate1.pt"
& $PY $H2I add $END $T1 --gate 1 --ctrl-src belief | ForEach-Object { Log $_ }
$same = & $PY $H2I same $END $T1 | ForEach-Object { Log $_ }
if (-not ($same -match "actions that differ: 0$")) { Log "THE HEAD (its whole path run) CHANGES HIS ANSWERS: not started"; exit 1 }
& $PY $H2I add $END (Join-Path $R1 "policy.pt") --gate 0 --ctrl-src belief --opt $OPTF (Join-Path $R1 "opt.pt") | ForEach-Object { Log $_ }
$same = & $PY $H2I same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
if (-not ($same -match "actions that differ: 0$")) { Log "THE START NETWORK ANSWERS DIFFERENTLY: not started (its policy.pt left for a look; nothing deleted)"; exit 1 }
Remove-Item Env:CUDA_VISIBLE_DEVICES, Env:OMP_NUM_THREADS
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_b12a.pt")
Copy-Item $END (Join-Path $R1 "snapshots\anchor_b11a.pt")
Copy-Item (Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt") (Join-Path $R1 "snapshots\anchor_v060_end.pt")
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
& $PY -c "import json, sys, torch; d = json.load(open(sys.argv[1])); ck = torch.load(sys.argv[2], map_location='cpu', weights_only=False); ev = ck.get('env_vars') or {}; g = ((ck.get('belief') or {}).get('fade') or {}).get('g', 0.0); assert d.get('WIN_ADD', 0) > 0 and d.get('WIN_W') == 0.0 and d.get('FADE_V') == 0.0, d; d.update(H2_GATE_CAP=0.0, H2_GATE_OPEN=1.0, INTENT_TEACH_W=1.0, VALUE_WARM=0, BRAIN_FADE=float(g), LEVEL_PULL=float(ev.get('LEVEL_PULL', 0.95)), INTENT_HOLD=float(ev.get('INTENT_HOLD', 8))); json.dump(d, open(sys.argv[3], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") $END (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from " + $Save + " with " + $Opt)
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $END; $env:CTRL_PREV_LABEL = "the start (" + $Save + ")"
$env:CTRL_REF = Join-Path $SR "duel_gru_v0_6_0\keep\policy_end_v060.pt"; $env:CTRL_REF_LABEL = "v0.6.0's end (reference)"
$env:CHECK_EVERY = "10"; $env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $END; $env:CHECK_RULE = "0"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = [IntPtr]0xC03C3
Start-Sleep 5
$env:RAMP_HEAD_ONLY = "1"; $env:RAMP_OPEN_NAME = "policy_head_open_b12a.pt"; $env:RAMP_HOLD_AT = "0.40"
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\ramp_head.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = [IntPtr]0xC03C3
Log ("watcher " + $w.Id + " | ramp_head " + $r.Id + " (shut 10 updates, then the gate +0.1 a step, the head-open save; held only at a check of 40% or less) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
