# 1.9a: run to the full 120 updates (owner, 2026-11-12 19:40: "just let it go until it's done then the full 120 updates"). ON THE OWNER'S WORD.
# The trainer started at 19:35 for 744 minutes (until 08:00, about update 106). This script, hidden: waits for the trainer to stop at its
# minutes (it saves as it ends), resumes it at once from the run's own save (start.ps1 -Resume: the watcher, the ramp and the logger are left
# running), waits for the kept save of update 120 (keep/policy_u120_19a.pt), then ends the run (stop_19a.ps1 -Update 120 -All: the end kept as
# policy_end_19a.pt), gives the watcher's check up to 45 minutes and stops the watcher. Every process matched by its own command line. Its log:
# finish_19a.log. Nothing is deleted.
#   wscript.exe docs\runs\1.9\1.9a\finish_19a.vbs
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$RUN = "duel_gru_1_9a"
$R1 = Join-Path $ROOT ("data\sim_runs\" + $RUN)
$LOG = Join-Path $HERE "finish_19a.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }
function Tree($root) { $all = @(Get-CimInstance Win32_Process); $out = @(); $q = @($root); while ($q.Count) { $p = $q[0]; $q = @($q | Select-Object -Skip 1); $k = @($all | Where-Object { $_.ParentProcessId -eq $p.ProcessId }); $out += $k; $q += $k }; return $out }
function Trainers() { @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" }) }
Log "finish_19a: waiting for the trainer to stop at its minutes"
foreach ($p in (Trainers)) { try { (Get-Process -Id $p.ProcessId -ErrorAction Stop).WaitForExit() } catch {} }
$n = (Get-Content (Join-Path $R1 "metrics.jsonl") | Measure-Object -Line).Lines
Log ("the trainer has stopped at update " + $n)
if ($n -lt 120) {
    Start-Sleep 20
    & powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File (Join-Path $HERE "start.ps1") -Minutes 240 -Resume | ForEach-Object { Log ("resume: " + $_) }
    $PU = Join-Path $R1 "keep\policy_u120_19a.pt"
    while (-not (Test-Path $PU)) {
        if (@(Trainers).Count -eq 0) { Log "THE TRAINER IS NOT RUNNING and the save of 120 is not kept: stopped here (the owner decides)"; exit 1 }
        Start-Sleep 30
    }
    Start-Sleep 60
    Log "the save of update 120 is kept: ending the run"
    & powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File (Join-Path $HERE "stop_19a.ps1") -Update 120 -All | ForEach-Object { Log ("stop: " + $_) }
}
$w = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*tools\run\watch.py*" -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })
$t0 = Get-Date
while ($w.Count -and ((Get-Date) - $t0).TotalMinutes -lt 45 -and @(Tree $w[0] | Where-Object { $_.Name -like "python*" }).Count -gt 0) { Start-Sleep 30 }
foreach ($pat in "*tools\run\watch.py*", "*ramp_19a.py*", "*selfplay_loop.py*") {
    foreach ($p in @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like $pat -and $_.CommandLine -like "*$RUN*" -and $_.Name -like "python*" })) {
        $kids = Tree $p
        foreach ($k in $kids) { Stop-Process -Id $k.ProcessId -Force -ErrorAction SilentlyContinue }
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Log ("stopped: " + $pat.Trim("*") + " (" + $p.ProcessId + ", " + $kids.Count + " children)")
    }
}
Log "finish_19a: done"
