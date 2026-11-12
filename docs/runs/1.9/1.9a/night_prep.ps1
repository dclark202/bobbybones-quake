# 1.9a, the night's measurements before the start (owner, 2026-11-12: runs only overnight ~21:00 to 08:00; nothing heavy by day).
# ON THE OWNER'S COMMAND ONLY. Nothing of a real run is touched: the measurements read 1.8a's end and write to scratch folders and to this folder.
#   1. the settings check of the measurements' games against 1.8a's command and its end (tools\run\cypher_measure.py check): any difference
#      but the legs network's path spelled two ways = stop
#   2. at once, all cores (no run is training): (a) his own damage a second by weapon and distance, FIN_RATE: 1.8a's end against itself,
#      6 games a map x 2 jobs, 8 jobs at a time (tools\run\cypher_measure.py sim, then tools\run\fin_rate.py measure -> fin_rate_u190.json);
#      (b) the items' race: 1.8a's end against itself, 10 games a map x 2 jobs, 4 maps at a time, every second with the items' race
#      (tools\run\selfplay_log.py with WS_ITEMS=1), then tools\run\fit_items.py -> items_19a.json (accepted or not, the file says)
#   3. with -Start, and only if both are made and the items' judge is ACCEPTED: start.ps1 -Minutes <until -Until, default 08:00 (owner, 11-12: "run it until 8am")>
#      (the run's own first ten updates are its trial). Without -Start: the measurements only.
#   -Resume (the next nights): no measurements; start.ps1 -Resume -Minutes <until -Until>.
#   4. the morning (with -Start or -Resume): when the trainer has stopped at its minutes, the watcher's check that is still playing is given up
#      to 45 minutes to finish, then the watcher, the ramp and the self-play logger are stopped (each matched by its own command line and the
#      run's name; their children by parent): the day is quiet (owner, 11-12). The next night's -Resume starts them again.
# Every process hidden. Its log: night_prep.log.
#   wscript.exe docs\runs\1.9\1.9a\night_prep.vbs [start|resume]       (no window at all)
param([switch]$Start, [switch]$Resume, [string]$Until = "08:00")
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$S0 = Join-Path $SR "duel_gru_1_8a\keep\policy_end_18a.pt"
$CMD18 = Join-Path $ROOT "docs\runs\1.8\1.8a\train.cmd"
$LOG = Join-Path $HERE "night_prep.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }
Log ("night_prep: " + $(if ($Start) { "measure, then start 1.9a if accepted (until " + $Until + ")" } else { "measure only" }))
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn.py*" -and $_.Name -like "python*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: nothing done"; exit 1 }
$RUN = "duel_gru_1_9a"
function Minutes() {
    $end = [datetime]::ParseExact((Get-Date -Format "yyyy-MM-dd") + " " + $Until, "yyyy-MM-dd HH:mm", $null)
    if ($end -lt (Get-Date)) { $end = $end.AddDays(1) }
    return [int][math]::Floor(($end - (Get-Date)).TotalMinutes)
}
function Tree($root) { $all = @(Get-CimInstance Win32_Process); $out = @(); $q = @($root); while ($q.Count) { $p = $q[0]; $q = @($q | Select-Object -Skip 1); $k = @($all | Where-Object { $_.ParentProcessId -eq $p.ProcessId }); $out += $k; $q += $k }; return $out }
function Morning() {
    $tr = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
    Log ("the morning: waiting for the trainer to stop at its minutes (" + ($tr | ForEach-Object { $_.ProcessId }) + ")")
    foreach ($p in $tr) { try { (Get-Process -Id $p.ProcessId -ErrorAction Stop).WaitForExit() } catch {} }
    Log "the trainer has stopped"
    $w = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*tools\run\watch.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
    $t0 = Get-Date
    while ($w.Count -and ((Get-Date) - $t0).TotalMinutes -lt 45 -and @(Tree $w[0] | Where-Object { $_.Name -like "python*" }).Count -gt 0) { Start-Sleep 30 }
    $left = if ($w.Count) { @(Tree $w[0] | Where-Object { $_.Name -like "python*" }).Count } else { 0 }
    Log ("the watcher's games " + $(if ($left) { "still playing after 45 minutes (" + $left + " processes): stopped with it" } else { "done" }))
    foreach ($pat in "*tools\run\watch.py*", "*ramp_19a.py*", "*selfplay_loop.py*") {
        foreach ($p in @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like $pat -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })) {
            $kids = Tree $p
            foreach ($k in $kids) { Stop-Process -Id $k.ProcessId -Force -ErrorAction SilentlyContinue }
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            Log ("stopped for the day: " + $pat.Trim("*") + " (" + $p.ProcessId + ", " + $kids.Count + " children)")
        }
    }
}
if ($Resume) {
    $min = Minutes
    Log ("resuming 1.9a for " + $min + " minutes (until " + $Until + ")")
    & powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File (Join-Path $HERE "start.ps1") -Minutes $min -Resume | ForEach-Object { Log ("start: " + $_) }
    Morning
    exit 0
}
$FIND = Join-Path $SR ("scratch_19a_fin_" + (Get-Date -Format "MMdd"))
$TAG = "items19_u190_" + (Get-Date -Format "MMdd")
$ITD = Join-Path $SR ("duel_gru_1_8a\selfplay\" + $TAG)
if (Test-Path $FIND) { Log "$FIND is there already: nothing done (nothing written over)"; exit 1 }
if (Test-Path $ITD) { Log "$ITD is there already: nothing done (nothing written over)"; exit 1 }
New-Item -ItemType Directory -Force $FIND | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"; $env:OPENBLAS_NUM_THREADS = "1"; $env:OMP_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
# 1. the settings check
$chk = & $PY (Join-Path $ROOT "tools\run\cypher_measure.py") check --run duel_gru_1_8a --policy $S0 --cmd $CMD18 2>&1
$chk | ForEach-Object { Add-Content -Path (Join-Path $FIND "settings_check.log") -Value $_ }
$diff = @($chk | Where-Object { $_ -like "DIFF *" -and $_ -notlike "DIFF LEGS_NET *" })
if ($diff.Count -gt 0) { Log ("SETTINGS CHECK: differences beyond the legs network's path: " + ($diff -join " | ") + ": stopped"); exit 1 }
Log ("settings check: " + ($chk | Select-Object -Last 1))
# 2. both measurements at once
$a = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\cypher_measure.py"), "sim", "--run", "duel_gru_1_8a", "--policy", $S0, "--out", (Join-Path $FIND "rec"), "--games", "6", "--procs", "2", "--par", "8" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $FIND "sim.log") -RedirectStandardError (Join-Path $FIND "sim_err.log")
$env:WS_ITEMS = "1"; $env:PANEL_RUN = "duel_gru_1_8a"
$b = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_log.py"), "--policy", $S0, "--tag", $TAG, "--games", "10", "--procs", "2", "--par", "4", "--minutes", "10", "--run", "duel_gru_1_8a" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $FIND "items_play.log") -RedirectStandardError (Join-Path $FIND "items_play_err.log")
Remove-Item Env:\WS_ITEMS; Remove-Item Env:\PANEL_RUN
Log ("started: FIN_RATE games (pid " + $a.Id + ") and the items' race games (pid " + $b.Id + ")")
$a.WaitForExit(); $b.WaitForExit()
Log ("games done: FIN_RATE exit " + $a.ExitCode + ", the items' race exit " + $b.ExitCode)
$FIN = Join-Path $HERE "fin_rate_u190.json"; $ITEMS = Join-Path $HERE "items_19a.json"
& $PY (Join-Path $ROOT "tools\run\fin_rate.py") measure (Join-Path $FIND "rec") --out $FIN 2>&1 | ForEach-Object { Log ("fin_rate: " + $_) }
$okF = ($LASTEXITCODE -eq 0) -and (Test-Path $FIN)
& $PY (Join-Path $ROOT "tools\run\fit_items.py") $ITD --judge (Join-Path $SR "judge\judge_v060_wpn.npz") --out $ITEMS 2>&1 | ForEach-Object { Log ("fit_items: " + $_) }
$okI = ($LASTEXITCODE -eq 0) -and (Test-Path $ITEMS)
Log ("FIN_RATE " + $(if ($okF) { "made" } else { "NOT MADE" }) + "; the items' judge " + $(if ($okI) { "ACCEPTED" } else { "NOT ACCEPTED" }))
if (-not $Start) { Log "measure only: not started"; exit 0 }
if (-not ($okF -and $okI)) { Log "not started: a measurement is missing or not accepted (the owner decides)"; exit 1 }
$min = Minutes
Log ("starting 1.9a for " + $min + " minutes (until " + $Until + ")")
& powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File (Join-Path $HERE "start.ps1") -Minutes $min | ForEach-Object { Log ("start: " + $_) }
Morning
