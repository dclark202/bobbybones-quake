# Registers the hidden scheduled task "BobbyBones nightly" (tools/run/nightly.py: the backup to T:, the offload of intermediates to T:,
# the weekly Docker tidy). pythonw.exe: no console window (CLAUDE.md, global rule); as the logged-on user, not elevated; daily at 04:30,
# run as soon as possible after a missed start. Registering it again replaces it.
#   powershell -ExecutionPolicy Bypass -File tools\run\register_nightly.ps1
$ErrorActionPreference = "Stop"
$ROOT = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\..")).Path
$PYW = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $PYW) { $PYW = Join-Path $env:USERPROFILE "anaconda3\pythonw.exe" }
if (-not (Test-Path $PYW)) { "no pythonw.exe found: not registered"; exit 1 }
$act = New-ScheduledTaskAction -Execute $PYW -Argument ('"' + (Join-Path $ROOT "tools\run\nightly.py") + '"') -WorkingDirectory $ROOT
$trg = New-ScheduledTaskTrigger -Daily -At "04:30"
$set = New-ScheduledTaskSettingsSet -StartWhenAvailable -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 8) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "BobbyBones nightly" -Action $act -Trigger $trg -Settings $set -Description "BobbyBones: backup to T:, intermediates moved to T: after a verified copy, weekly Docker tidy (tools/run/nightly.py). Hidden, no window." -Force | Out-Null
$t = Get-ScheduledTask -TaskName "BobbyBones nightly"
"registered: " + $t.TaskName + " | " + $t.Actions[0].Execute + " " + $t.Actions[0].Arguments + " | next " + ($t | Get-ScheduledTaskInfo).NextRunTime
