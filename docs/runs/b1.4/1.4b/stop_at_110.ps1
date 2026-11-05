# 1.4b's stop at the save of update 110 (owner, 2026-11-04: "save it at update 110, then run the check. We'll start 1.4c afterward on my
# approval"). Waits for the ramp's copy of that save with its optimizer (keep/policy_u110_14b.pt, opt_u110_14b.pt), checks it is the save in
# place (policy.pt the same file), then stops the trainer (its cmd and every child), the ramp and the self-play logger, and keeps the end as
# keep/policy_end_14b.pt + opt_end_14b.pt. The watcher stays: it runs the check of update 110 against 1.3b's end by itself.
$R = "C:\Users\dacla\Documents\gh\BobbyBones\data\sim_runs\duel_gru_1_4b"
$K = Join-Path $R "keep"
$LOG = "C:\Users\dacla\Documents\gh\BobbyBones\docs\runs\b1.4\1.4b\stop.log"
function Log($s) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $s; Add-Content -Path $LOG -Value $l; Write-Output $l }
Log "waiting for the save of update 110"
while (-not ((Test-Path "$K\policy_u110_14b.pt") -and (Test-Path "$K\opt_u110_14b.pt"))) { Start-Sleep 20 }
Start-Sleep 60
$h1 = (Get-FileHash "$R\policy.pt").Hash; $h2 = (Get-FileHash "$K\policy_u110_14b.pt").Hash
$n = (Get-Content "$R\metrics.jsonl" | Measure-Object -Line).Lines
if ($h1 -ne $h2) { Log "policy.pt is not the kept save of update 110 (updates recorded: $n): NOT stopped"; exit 1 }
Log "the save of update 110 is in place (updates recorded: $n); stopping the trainer"
& taskkill /T /F /PID 36304 2>&1 | ForEach-Object { Log $_ }
Start-Sleep 5
foreach ($p in 26000, 33812) { & taskkill /T /F /PID $p 2>&1 | ForEach-Object { Log $_ } }
Copy-Item "$K\policy_u110_14b.pt" "$K\policy_end_14b.pt"
Copy-Item "$K\opt_u110_14b.pt" "$K\opt_end_14b.pt"
$left = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'train_duel_rnn' }
Log ("kept keep/policy_end_14b.pt and opt_end_14b.pt (update 110); trainers still running: " + @($left).Count)
