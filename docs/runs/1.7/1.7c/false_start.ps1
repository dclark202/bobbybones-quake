# 1.7c's false start (2026-11-08 01:45): the trainer's reference log-probability pass lacked the weapon key's mask, so PPO's ratio was
# inflated on every frame under the table; the KL estimate went negative from update 25 and the checks fell. Fixed in
# sim/train_duel_rnn.py (tests pass). ON THE OWNER'S WORD ONLY: this stops the false start's processes (the trainer, the ramp, the
# watcher, the self-play logger and their check processes: by their own command lines, nothing else), renames its run folder and log
# (nothing deleted: data\sim_runs\duel_gru_1_7c -> duel_gru_1_7c_false1, duel_gru_1_7c.log -> duel_gru_1_7c_false1.log), then runs
# start.ps1 again with the length given.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\1.7\1.7c\false_start.ps1 -Minutes <until noon>
param([int]$Minutes = 0)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$SR = Join-Path $ROOT "data\sim_runs"
$RUN = "duel_gru_1_7c"
if ($Minutes -le 0) { Write-Output "no length (-Minutes): nothing done"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\train_duel_rnn.py") -Pattern "the same mask as the learner's, or the ratio lies" -Quiet)) { Write-Output "the trainer here lacks the fix: nothing done"; exit 1 }
$ps = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*$RUN*" -and ($_.CommandLine -like "*train_duel_rnn.py*" -or $_.CommandLine -like "*ramp_17c.py*" -or $_.CommandLine -like "*selfplay_loop.py*" -or $_.CommandLine -like "*watch.py*" -or $_.CommandLine -like "*duel_eval.py*" -or $_.CommandLine -like "*dump_eval.py*" -or $_.CommandLine -like "*1.7c\train.cmd*") -and $_.CommandLine -notlike "*Get-CimInstance*" -and $_.CommandLine -notlike "*false_start.ps1*" }
$ps | ForEach-Object { Write-Output ("stopping " + $_.ProcessId + " " + $_.CommandLine.Substring(0, [Math]::Min(120, $_.CommandLine.Length))) }
$ps | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
Start-Sleep 8
$left = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*$RUN*" -and $_.CommandLine -notlike "*Get-CimInstance*" -and $_.CommandLine -notlike "*false_start.ps1*" -and $_.CommandLine -notlike "*powershell*" }
if (($left | Measure-Object).Count -gt 0) { $left | ForEach-Object { Write-Output ("STILL RUNNING " + $_.ProcessId + " " + $_.CommandLine.Substring(0, [Math]::Min(120, $_.CommandLine.Length))) }; Write-Output "not renamed, not restarted"; exit 1 }
$n = 1
while (Test-Path (Join-Path $SR ($RUN + "_false" + $n))) { $n += 1 }
Rename-Item (Join-Path $SR $RUN) ($RUN + "_false" + $n)
if (Test-Path (Join-Path $SR ($RUN + ".log"))) { Rename-Item (Join-Path $SR ($RUN + ".log")) ($RUN + "_false" + $n + ".log") }
Write-Output ("the false start's folder and log renamed to " + $RUN + "_false" + $n + " (nothing deleted)")
& powershell -ExecutionPolicy Bypass -File (Join-Path $HERE "start.ps1") -Minutes $Minutes
