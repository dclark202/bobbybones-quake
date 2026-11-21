# 2.1d: restart ONLY the trainer of the existing run from its last save (data\sim_runs\duel_gru_2_1d\policy.pt and opt.pt; the command
# has --resume). RUNS ONLY ON THE OWNER'S COMMAND, or for a crashed run he approved (CLAUDE.md hard rule 2). Run it from the checkout that
# holds data\. Made for --obs-half's retirement (owner, 2026-11-15: the learner reads the inputs as played; the trainer refuses the flag):
# train.cmd is rebuilt by make_files.py (2.1c's command without --obs-half).
# Refuses: no data\ here; a trainer running; the run's policy.pt or opt.pt missing; make_files.py failing; a firing cost above zero; a
# difference from 2.1c's command beyond --run, --minutes, --max-updates, --head2-lam, --pull, --pull-g, --pull-h, --obs-half; a live.json
# the trainer would refuse (or one the ramp may write). Then: the trainer (0xC03C3, from train.cmd), hidden; waits up to 20 minutes for the
# trainer to rewrite live_status.json as "applied". It starts NOTHING else: the watcher, the ramp and the self-play logger are only looked
# for (by command line), and a missing one is logged loudly.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\2.1\2.1d\restart.ps1 -Minutes <n> -Updates <n> [-Lam 0.998] [-PullH 0]
# (-Minutes and -Updates: the remaining length; --max-updates counts the run's updates as the trainer resumes them)
param([int]$Minutes = 0, [int]$Updates = 0, [string]$Lam = "0.998", [int]$PullH = 0)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$RUN = "duel_gru_2_1d"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

Log "restart.ps1 (the trainer only, from the run's last save): -Minutes $Minutes -Updates $Updates -Lam $Lam -PullH $PullH"
if ($Minutes -le 0) { Log "-Minutes (the remaining length) is needed: not restarted"; exit 1 }
if ($Updates -le 0) { Log "-Updates (the run's --max-updates) is needed: not restarted"; exit 1 }
if ($PullH -lt 0 -or $PullH -gt 1) { Log "-PullH 0 (2 s) or 1 (5 s): not restarted"; exit 1 }
if (-not (Test-Path (Join-Path $ROOT "data"))) { Log "NO data FOLDER IN $ROOT (a worktree?): not restarted"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not restarted"; exit 1 }
foreach ($p in (Join-Path $R1 "policy.pt"), (Join-Path $R1 "opt.pt"), (Join-Path $R1 "live.json")) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not restarted"; exit 1 } }
& $PY (Join-Path $HERE "make_files.py") $Minutes $Updates $Lam $PullH | ForEach-Object { Log ("train.cmd, $Minutes minutes, $Updates updates, head2-lam ${Lam}, pull horizon ${PullH}: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not restarted"; exit 1 }
& $PY -c "import re, sys; t = open(sys.argv[1]).read(); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); print('no firing cost in the command: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not restarted"; exit 1 }
# 2.1c's command and these differences, exactly (as start.ps1; --obs-half: removed, retired by the owner 2026-11-15)
$ALLOW = "--run,--minutes,--max-updates,--head2-lam,--pull,--pull-g,--pull-h,--obs-half"
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\2.1\2.1c\train.cmd") "--allow=$ALLOW" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 2.1c's command): not restarted"; exit 1 }
$env:DODGE_IN = "1"
& $PY (Join-Path $ROOT "tools\run\live_accept.py") (Join-Path $R1 "live.json") --env duel_env_ffa20e --ramp (Join-Path $HERE "ramp_21d.py") | ForEach-Object { Log $_ }
$la = $LASTEXITCODE
Remove-Item Env:\DODGE_IN
if ($la -ne 0) { Log "THE TRAINER WOULD REFUSE live.json (or a file the ramp may write): not restarted"; exit 1 }

$ST = Join-Path $R1 "live_status.json"
$m0 = if (Test-Path $ST) { (Get-Item $ST).LastWriteTimeUtc } else { [DateTime]::MinValue }
$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer restarted: cmd " + $t.Id + ", --resume from " + (Join-Path $R1 "policy.pt") + " and opt.pt, " + $Minutes + " minutes, at most " + $Updates + " updates (--max-updates)")
$t0 = Get-Date
while (-not ((Test-Path $ST) -and (Get-Item $ST).LastWriteTimeUtc -gt $m0) -and -not $t.HasExited -and ((Get-Date) - $t0).TotalMinutes -lt 20) { Start-Sleep 5 }
$st = if ((Test-Path $ST) -and (Get-Item $ST).LastWriteTimeUtc -gt $m0) { Get-Content $ST -Raw | ConvertFrom-Json } else { $null }
if ($null -eq $st -or $st.status -ne "applied") {
    Log ("THE TRAINER DID NOT APPLY live.json (" + $(if ($null -eq $st) { if ($t.HasExited) { "the trainer exited" } else { "no new live_status.json in 20 minutes" } } else { $st.reason }) + "); see " + $RUN + ".log")
}
else { Log ("live.json applied by the restarted trainer (" + $st.time + ")") }

$PR = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine })
foreach ($j in @(@("the watcher", "*watch.py*$RUN*"), @("the ramp", "*ramp_21d.py*$RUN*"), @("the self-play logger", "*selfplay_loop.py*$RUN*"))) {
    $hit = @($PR | Where-Object { $_.CommandLine -like $j[1] })
    if ($hit.Count -gt 0) { Log ($j[0] + " running: " + (($hit | ForEach-Object { $_.ProcessId }) -join ", ")) }
    else { Log ("!!!! " + $j[0].ToUpper() + " IS NOT RUNNING (no process like " + $j[1] + "): this script starts none; start it as start.ps1 does !!!!") }
}
if ($null -eq $st -or $st.status -ne "applied") { exit 1 }
