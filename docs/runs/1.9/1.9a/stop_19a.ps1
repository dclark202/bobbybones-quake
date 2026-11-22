# 1.9a: stops the TRAINER (and only the trainer, with its simulators) right after a kept save, on the owner's word (the run has no planned
# restart: the switch cost and "a held weapon is choosable" are live). Nothing is deleted. The watcher, the ramp and the self-play logger are
# left running unless -All (the run's end). Every process is matched by its own command line (Windows reuses process IDs): the trainer by
# "train_duel_rnn.py" and the run's name; its simulators by "multiprocessing.spawn" AND "parent_pid=<the trainer's id>". No variable shares a
# name with a parameter (1.8a's $all beside -All: one name in PowerShell, the stop found "0 trainers").
#   stop_19a.ps1 -Update 200 -All      the end: also the ramp and the logger (the watcher finishes its check); the end kept as policy_end_19a.pt
#   stop_19a.ps1 -Update <n>           the trainer alone, right after the kept save of update n (refuses unless the run's policy.pt IS that save)
# ON THE OWNER'S WORD ONLY.
param([Parameter(Mandatory = $true)][int]$Update, [switch]$All)
$RUN = "duel_gru_1_9a"
$ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$DR = if ($env:QLBOT_ROOT) { $env:QLBOT_ROOT } else { $ROOT }      # (the repo that has data\)
$D = Join-Path $DR "data\sim_runs\$RUN"
$K = Join-Path $D "keep"
$LOG = Join-Path $PSScriptRoot "stop.log"
function Log($s) { $l = (Get-Date -Format "MM-dd HH:mm:ss") + " " + $s; Write-Output $l; Add-Content -Path $LOG -Value $l -Encoding utf8 }
function Short($c) { $c.Substring(0, [Math]::Min(130, $c.Length)) }

$PU = Join-Path $K ("policy_u" + $Update + "_19a.pt"); $OU = Join-Path $K ("opt_u" + $Update + "_19a.pt")
if (-not (Test-Path $PU) -or -not (Test-Path $OU)) { Log ("keep\policy_u" + $Update + "_19a.pt or its optimizer is not there yet: nothing stopped"); exit 1 }
$last = @(Get-Content (Join-Path $D "metrics.jsonl") | Where-Object { $_.Trim() }).Count      # (the run's updates: the lines; the trainer's own number restarts at 1)
if ((Get-FileHash (Join-Path $D "policy.pt")).Hash -ne (Get-FileHash $PU).Hash) { Log ("the run's policy.pt is no longer the save of update " + $Update + " (the last finished update is " + $last + "): nothing stopped"); exit 1 }
Log ("update " + $Update + "'s save is kept (" + (Get-Item $PU).LastWriteTime.ToString("HH:mm:ss") + ") and is the run's policy.pt; the last finished update is " + $last)

$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine }
$tr = @($procs | Where-Object { $_.CommandLine -like "*train_duel_rnn.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
if ($tr.Count -ne 1) { Log ("expected one trainer, found " + $tr.Count + ": nothing stopped"); exit 1 }
$tid = $tr[0].ProcessId
$kids = @($procs | Where-Object { $_.ParentProcessId -eq $tid -and $_.CommandLine -like "*multiprocessing.spawn*" -and $_.CommandLine -like "*parent_pid=$tid,*" })
$more = @()
if ($All) {
    $more += @($procs | Where-Object { $_.CommandLine -like "*ramp_19a.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
    $sp = @($procs | Where-Object { ($_.CommandLine -like "*selfplay_loop.py*" -or $_.CommandLine -like "*selfplay_log.py*") -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
    $spIds = @($sp | ForEach-Object { $_.ProcessId })
    $more += $sp
    $more += @($procs | Where-Object { $spIds -contains $_.ParentProcessId -and $_.CommandLine -like "*ws_eval.py*" -and $_.CommandLine -like "*$RUN*" })
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
    $PE = Join-Path $K "policy_end_19a.pt"; $OE = Join-Path $K "opt_end_19a.pt"
    if ((Test-Path $PE) -or (Test-Path $OE)) { Log "keep\policy_end_19a.pt or its optimizer exists already: not written over" }
    else { Copy-Item $PU $PE; Copy-Item $OU $OE; Log ("the end kept: keep\policy_end_19a.pt (the save of update " + $Update + ") with opt_end_19a.pt") }
}
