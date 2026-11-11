# 1.8a: stops the TRAINER (and only the trainer, with its simulators) right after a kept save, for the planned restart at update 150
# (docs/runs/1.8/1.8a/CARD.md: the two switches that are not live) or for the run's end. Nothing is deleted. The watcher, the ramp and the
# self-play logger are left running unless -All (the run's end). Every process is matched by its own command line (Windows reuses process
# IDs): the trainer by "train_duel_rnn.py" and the run's name; its simulators by "multiprocessing.spawn" AND "parent_pid=<the trainer's id>".
#   stop_18a.ps1 -Update 150           refuses unless keep\policy_u150_18a.pt and its optimizer are there and the run's policy.pt IS that save
#   stop_18a.ps1 -Update 310 -All      the end: also the ramp and the logger (the watcher finishes its check); the end kept as policy_end_18a.pt
# ON THE OWNER'S WORD ONLY (the card's planned restart, or his word to end the run).
param([Parameter(Mandatory = $true)][int]$Update, [switch]$All)
$RUN = "duel_gru_1_8a"
$ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$D = Join-Path $ROOT "data\sim_runs\$RUN"
$K = Join-Path $D "keep"
$LOG = Join-Path $PSScriptRoot "stop.log"
function Log($s) { $l = (Get-Date -Format "MM-dd HH:mm:ss") + " " + $s; Write-Output $l; Add-Content -Path $LOG -Value $l -Encoding utf8 }
function Short($c) { $c.Substring(0, [Math]::Min(130, $c.Length)) }

$PU = Join-Path $K ("policy_u" + $Update + "_18a.pt"); $OU = Join-Path $K ("opt_u" + $Update + "_18a.pt")
if (-not (Test-Path $PU) -or -not (Test-Path $OU)) { Log ("keep\policy_u" + $Update + "_18a.pt or its optimizer is not there yet: nothing stopped"); exit 1 }
$last = @(Get-Content (Join-Path $D "metrics.jsonl") | Where-Object { $_.Trim() }).Count      # (the run's updates: the lines; the trainer's own number restarts at 1)
if ((Get-FileHash (Join-Path $D "policy.pt")).Hash -ne (Get-FileHash $PU).Hash) { Log ("the run's policy.pt is no longer the save of update " + $Update + " (the last finished update is " + $last + "): nothing stopped"); exit 1 }
Log ("update " + $Update + "'s save is kept (" + (Get-Item $PU).LastWriteTime.ToString("HH:mm:ss") + ") and is the run's policy.pt; the last finished update is " + $last)

$all = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine }
$tr = @($all | Where-Object { $_.CommandLine -like "*train_duel_rnn.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
if ($tr.Count -ne 1) { Log ("expected one trainer, found " + $tr.Count + ": nothing stopped"); exit 1 }
$tid = $tr[0].ProcessId
$kids = @($all | Where-Object { $_.ParentProcessId -eq $tid -and $_.CommandLine -like "*multiprocessing.spawn*" -and $_.CommandLine -like "*parent_pid=$tid,*" })
$more = @()
if ($All) {
    $more += @($all | Where-Object { $_.CommandLine -like "*ramp_18a.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
    $sp = @($all | Where-Object { ($_.CommandLine -like "*selfplay_loop.py*" -or $_.CommandLine -like "*selfplay_log.py*") -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
    $spIds = @($sp | ForEach-Object { $_.ProcessId })
    $more += $sp
    $more += @($all | Where-Object { $spIds -contains $_.ParentProcessId -and $_.CommandLine -like "*ws_eval.py*" -and $_.CommandLine -like "*$RUN*" })
}
Log ("the trainer " + $tid + " with " + $kids.Count + " simulators" + $(if ($All) { "; the ramp and the self-play logger: " + $more.Count + " processes" } else { "; the watcher, the ramp and the logger are left running" }))
foreach ($p in @($tr) + $kids + $more) {
    if ($p.CommandLine -notlike "*multiprocessing.spawn*") { Log ("stopping " + $p.ProcessId + " " + (Short $p.CommandLine)) }
    Stop-Process -Id $p.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 5
$left = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and (($_.CommandLine -like "*train_duel_rnn.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*") -or $_.CommandLine -like "*parent_pid=$tid,*") })
if ($left.Count -gt 0) { $left | ForEach-Object { Log ("STILL RUNNING " + $_.ProcessId + " " + (Short $_.CommandLine)) }; exit 1 }
Log "the trainer and its simulators are stopped"
if ($All) {
    $PE = Join-Path $K "policy_end_18a.pt"; $OE = Join-Path $K "opt_end_18a.pt"
    if ((Test-Path $PE) -or (Test-Path $OE)) { Log "keep\policy_end_18a.pt or its optimizer exists already: not written over" }
    else { Copy-Item $PU $PE; Copy-Item $OU $OE; Log ("the end kept: keep\policy_end_18a.pt (the save of update " + $Update + ") with opt_end_18a.pt") }
}
