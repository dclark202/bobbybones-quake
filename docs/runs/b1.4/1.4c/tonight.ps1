# 1.4c tonight (owner, 2026-11-04: "run 1.4b til this evening and 1.4c overnight"), on the owner's go only. In order, each step logged to
# tonight.log beside this file, stopping at the first that fails (nothing deleted, nothing overwritten):
#  1. waits for 1.4b's trainer to end by itself (its 12 hours, --minutes 720: the last save is policy.pt / opt.pt)
#  2. keeps 1.4b's end: keep\policy_end_14b.pt and keep\opt_end_14b.pt (refuses if they are there), then a backup (tools\run\backup.py)
#  3. waits for 1.4b's running check (duel_eval of duel_gru_1_4b) to finish, at most 80 min, then stops 1.4b's watcher, ramp and
#     self-play logger (the run is over: tools\run\stop_run.py's list, its trainer already gone)
#  4. merges branch b14c into main (the main checkout clean, no rebase), so the main checkout has 1.4c's code
#  5. the level check of the start at share 1 (level.py level, 200 games, the 8 efficiency cores) and the dry run (dryrun_14c.py, 10
#     updates on the graphics card and the 8 performance cores), side by side
#  6. if both passed: start.ps1 -Minutes <Minutes> (its own refusals stand)
# Usage (PowerShell, detached):  powershell -ExecutionPolicy Bypass -File <this file> [-Minutes 720]
param([int]$Minutes = 720)
$ErrorActionPreference = "Stop"
$MAIN = Join-Path $env:USERPROFILE "Documents\gh\BobbyBones"
$WT = Join-Path $env:USERPROFILE "Documents\gh\BobbyBones-14b"
$PY = Join-Path $env:USERPROFILE "anaconda3\python.exe"
$R0 = Join-Path $MAIN "data\sim_runs\duel_gru_1_4b"
$D14C = Join-Path $MAIN "docs\runs\b1.4\1.4c"
$LOG = Join-Path $WT "docs\runs\b1.4\1.4c\tonight.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }
function Procs($pat) { @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like $pat -and $_.CommandLine -notlike "*tonight.ps1*" }) }

Log "tonight: on; 1.4c for $Minutes minutes once 1.4b ends and the checks pass"
# 1.
while ((Procs "*train_duel_rnn*duel_gru_1_4b*").Count -gt 0) { Start-Sleep 60 }
Start-Sleep 30
Log "1.4b's trainer has ended: $((Get-Content (Join-Path $MAIN 'data\sim_runs\duel_gru_1_4b.log') -Tail 1))"
# 2.
$END = Join-Path $R0 "keep\policy_end_14b.pt"; $OPTE = Join-Path $R0 "keep\opt_end_14b.pt"
if ((Test-Path $END) -or (Test-Path $OPTE)) { Log "1.4b's end is already kept ($END): not overwritten; stopped"; exit 1 }
Copy-Item (Join-Path $R0 "policy.pt") $END
Copy-Item (Join-Path $R0 "opt.pt") $OPTE
Log ("kept 1.4b's end: " + $END + " (" + (Get-Item $END).Length + " bytes, " + (Get-Item $END).LastWriteTime + ") with its optimizer")
& $PY (Join-Path $MAIN "tools\run\backup.py") | ForEach-Object { Log $_ }
# 3.
$t0 = Get-Date
while ((Procs "*duel_eval*duel_gru_1_4b*").Count -gt 0 -and ((Get-Date) - $t0).TotalMinutes -lt 80) { Start-Sleep 60 }
if ((Procs "*duel_eval*duel_gru_1_4b*").Count -gt 0) { Log "1.4b's check still runs after 80 min: stopped here (look first)"; exit 1 }
foreach ($pat in "*watch.py*duel_gru_1_4b*", "*ramp_14b*duel_gru_1_4b*", "*selfplay_loop*duel_gru_1_4b*", "*selfplay_log*duel_gru_1_4b*", "*dump_eval*duel_gru_1_4b*", "*ws_eval*duel_gru_1_4b*") {
    foreach ($p in (Procs $pat)) { Stop-Process -Id $p.ProcessId -Force; Log ("stopped 1.4b's " + $pat.Trim("*").Split("*")[0] + " (" + $p.ProcessId + ")") }
}
Start-Sleep 10
if ((Procs "*duel_gru_1_4b*").Count -gt 0) { Log ("something of 1.4b still runs: " + ((Procs "*duel_gru_1_4b*" | ForEach-Object { $_.CommandLine.Substring(0, [Math]::Min(120, $_.CommandLine.Length)) }) -join " | ") + "; stopped here"); exit 1 }
# 4.
$ch = @(& git -C $MAIN diff --name-only main b14c)                  # (git refuses a merge that would overwrite a local change; this says which first)
$st = @(& git -C $MAIN status --porcelain --untracked-files=no | ForEach-Object { $_.Substring(3) })
$both = @($st | Where-Object { $ch -contains $_ })
if ($both.Count -gt 0) { Log ("uncommitted changes in the main checkout to files the merge brings: " + ($both -join ", ") + "; not merged, stopped"); exit 1 }
$msg = "Merge branch 'b14c': 1.4c's keep choice (the target lock out by a learned choice to keep or re-decide), BLIND_FIRE_W`n`nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
& git -C $MAIN merge --no-ff b14c -m $msg 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "the merge failed: stopped (git merge --abort puts it back)"; exit 1 }
Log ("merged: " + ((& git -C $MAIN log --oneline -1) -join ""))
# 5.
$env:OPENBLAS_NUM_THREADS = "1"; $env:OMP_NUM_THREADS = "1"; $env:PYTHONFAULTHANDLER = "1"
$lv = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "set CUDA_VISIBLE_DEVICES=-1&& set PANEL_RUN=duel_gru_1_4b&& start `"`" /b /wait /low /affinity 3C3C `"$PY`" `"$D14C\level.py`" level `"$END`" --out `"$D14C\level`" --run duel_gru_1_4b > `"$D14C\level.log`" 2>&1" -WorkingDirectory $MAIN -WindowStyle Hidden -PassThru
Log ("level check started (" + $lv.Id + "): the start at share 1 against 1.4b's end, 200 games, efficiency cores")
$dr = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$PY`" `"$D14C\dryrun_14c.py`" > `"$D14C\dryrun_14c.log`" 2>&1" -WorkingDirectory $MAIN -WindowStyle Hidden -PassThru
Log ("dry run started (" + $dr.Id + "): 10 updates at full size, share 0.5")
$lv.WaitForExit(); $dr.WaitForExit()
Get-Content (Join-Path $D14C "level.log") -Tail 3 | ForEach-Object { Log ("level: " + $_) }
Get-Content (Join-Path $D14C "dryrun_14c.log") | Select-String -Pattern "PASS|FAIL" | ForEach-Object { Log ("dry run: " + $_.Line) }
if (-not (Select-String -Path (Join-Path $D14C "level.log") -Pattern "LEVEL PASS" -Quiet)) { Log "the level check did not pass: 1.4c not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $D14C "dryrun_14c.log") -Pattern "ALL PASSED" -Quiet)) { Log "the dry run did not pass: 1.4c not started"; exit 1 }
# 6.
Log "both passed: start.ps1 -Minutes $Minutes"
& powershell -ExecutionPolicy Bypass -File (Join-Path $D14C "start.ps1") -Minutes $Minutes | ForEach-Object { Log ("start: " + $_) }
Log ("tonight: done (start.ps1 exit " + $LASTEXITCODE + ")")
