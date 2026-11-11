# Gives the free space inside Docker's disk file back to C: (owner, 2026-11-11). Docker's docker_data.vhdx only grows: what a prune frees
# inside it stays allocated on C: until the file is compacted. BY HAND, AS ADMINISTRATOR, with nothing running in Docker:
#   powershell -ExecutionPolicy Bypass -File tools\run\docker_compact.ps1
# It refuses if a container is running or a trainer is running. It stops Docker Desktop and WSL (any open WSL shell closes), compacts the
# file with diskpart (attached read-only: its contents are not changed), and says the size before and after. Docker Desktop is started
# again by hand. Nothing is deleted.
$ErrorActionPreference = "Stop"
$VHD = Join-Path $env:LOCALAPPDATA "Docker\wsl\disk\docker_data.vhdx"
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { "run this from an administrator PowerShell: nothing done"; exit 1 }
if (-not (Test-Path $VHD)) { "not found: $VHD"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { "a trainer is running: nothing done"; exit 1 }
$up = (& docker ps -q 2>$null | Measure-Object).Count
if ($up -gt 0) { "$up container(s) running: stop them first (docker stop): nothing done"; exit 1 }
$before = (Get-Item $VHD).Length
"before: {0:N1} GB" -f ($before / 1GB)
Get-Process "Docker Desktop", "com.docker.backend", "com.docker.build" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 5
& wsl --shutdown
Start-Sleep 8
$script = Join-Path $env:TEMP "bb_compact_vhd.txt"
@("select vdisk file=`"$VHD`"", "attach vdisk readonly", "compact vdisk", "detach vdisk") | Set-Content -Path $script -Encoding ascii
& diskpart /s $script
$after = (Get-Item $VHD).Length
"after: {0:N1} GB ({1:N1} GB back on C:). Start Docker Desktop again when you need it." -f ($after / 1GB), (($before - $after) / 1GB)
