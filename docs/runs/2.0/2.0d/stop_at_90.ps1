# 2.0d's length (owner, 2026-11-13: 90 updates; docs/runs/2.0/2.0d/CARD.md): stops the TRAINER and the
# self-play logger once the ramp has kept update 90's save (keep\policy_u90_20d.pt with its optimizer). Nothing is deleted. The watcher is
# left to finish the check of update 90; the ramp is left until that check is logged (it writes the check's lines), then -Ramp stops it.
# Every process is matched by its own command line (Windows reuses process IDs): the trainer by "train_duel_rnn.py" and the run's name; its
# simulators by "multiprocessing.spawn" AND "parent_pid=<the trainer's id>" in their own command line.
# Usage: powershell -ExecutionPolicy Bypass -File docs\runs\2.0\2.0d\stop_at_90.ps1 [-Ramp]
param([switch]$Ramp)
$RUN = "duel_gru_2_0d"
$ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$D = Join-Path $ROOT "data\sim_runs\$RUN"
$K = Join-Path $D "keep"
$LOG = Join-Path $PSScriptRoot "stop.log"
function Log($s) { $l = (Get-Date -Format "MM-dd HH:mm:ss") + " " + $s; Write-Output $l; Add-Content -Path $LOG -Value $l -Encoding utf8 }
function Short($c) { $c.Substring(0, [Math]::Min(130, $c.Length)) }

$all = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine }
if ($Ramp) {
    $r = $all | Where-Object { $_.CommandLine -like "*ramp_20d.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" }
    $r | ForEach-Object { Log ("stopping the ramp " + $_.ProcessId + " " + (Short $_.CommandLine)); Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
    if (($r | Measure-Object).Count -eq 0) { Log "no ramp running" }
    exit 0
}
$PU = Join-Path $K "policy_u90_20d.pt"; $OU = Join-Path $K "opt_u90_20d.pt"
if (-not (Test-Path $PU) -or -not (Test-Path $OU)) { Log "keep\policy_u90_20d.pt or its optimizer is not there yet: nothing stopped"; exit 1 }
$last = (Get-Content (Join-Path $D "metrics.jsonl") -Tail 1 | ConvertFrom-Json).update
Log ("update 90's save is kept (" + (Get-Item $PU).LastWriteTime.ToString("HH:mm:ss") + "); the last finished update is " + $last)

$tr = @($all | Where-Object { $_.CommandLine -like "*train_duel_rnn.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
if ($tr.Count -ne 1) { Log ("expected one trainer, found " + $tr.Count + ": nothing stopped"); exit 1 }
$tid = $tr[0].ProcessId
$kids = @($all | Where-Object { $_.ParentProcessId -eq $tid -and $_.CommandLine -like "*multiprocessing.spawn*" -and $_.CommandLine -like "*parent_pid=$tid,*" })
$sp = @($all | Where-Object { $_.CommandLine -like "*selfplay_loop.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
$sl = @($all | Where-Object { $_.CommandLine -like "*selfplay_log.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
$slIds = @($sl | ForEach-Object { $_.ProcessId })
$sw = @($all | Where-Object { $slIds -contains $_.ParentProcessId -and $_.CommandLine -like "*ws_eval.py*" -and $_.CommandLine -like "*$RUN*" })
Log ("the trainer " + $tid + " with " + $kids.Count + " simulators; the self-play logger: " + ($sp.Count + $sl.Count + $sw.Count) + " processes")
foreach ($p in @($tr) + $kids + $sp + $sl + $sw) {
    Log ("stopping " + $p.ProcessId + " " + (Short $p.CommandLine))
    Stop-Process -Id $p.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 5
$left = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and (($_.CommandLine -like "*train_duel_rnn.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*") -or $_.CommandLine -like "*parent_pid=$tid,*" -or ($_.CommandLine -like "*selfplay_lo*.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*")) })
if ($left.Count -gt 0) { $left | ForEach-Object { Log ("STILL RUNNING " + $_.ProcessId + " " + (Short $_.CommandLine)) }; exit 1 }
Log "the trainer, its simulators and the self-play logger are stopped"
$PE = Join-Path $K "policy_end_20d.pt"; $OE = Join-Path $K "opt_end_20d.pt"
if ((Test-Path $PE) -or (Test-Path $OE)) { Log "keep\policy_end_20d.pt or its optimizer exists already: not written over" }
else {
    Copy-Item $PU $PE; Copy-Item $OU $OE
    Log ("the end kept: keep\policy_end_20d.pt (" + (Get-FileHash $PE -Algorithm SHA256).Hash.Substring(0, 16) + ", the same as policy_u90_20d.pt " + (Get-FileHash $PU -Algorithm SHA256).Hash.Substring(0, 16) + ") with opt_end_20d.pt")
}
$w = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*watch.py*" -and $_.CommandLine -like "*$RUN*" })
Log ("the watcher is left running (" + $w.Count + " process): it finishes the check of update 90")
