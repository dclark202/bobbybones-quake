# 1.7b's start (owner, 2026-11-06 evening: "let's start 1.7b now"; "Just keep 1.7b as we agreed"; docs/runs/1.7/1.7b/CARD.md, BUILD.md),
# ON THE OWNER'S COMMAND ONLY. Its length is the owner's (11-06 evening: about 150 updates, "That's fine"): --max-updates 150 in the
# command, -Minutes a cap above it (default 1080). From 1.7a's result (its save of update 90, keep/policy_end_17a.pt) with its optimizer,
# given 1.7b's parts at zero effect (tools/b17b_init.py add: the yellow armors' timers at zero weight and their token shut, the head's new
# inputs and its part "fight" at zero, the brain's fight odds readout at zero, the order's reference for the KL); it plays as update 90
# (b17b_init same: 0 actions differ, at its own shares and at share 1). The league's files widened (b17b_init widen-league): 1.7a's anchors
# and 1.7a's update 90 as one more (the control rule). Dials (ramp_17b.py: reported, never held or stepped back, CLAUDE.md rule 6):
# DMG_TAKEN_W 0.8 -> 1.0 over updates 0 to 20; the order CMB_G 0 -> 1 over 30 to 40, its token ORD_GATE -12 -> 0 over 30 to 45; the
# order's share of the head's term H2_OPG 0 -> 1 over 60 to 120; ORD_KL sized at update 64 and held. The fight odds' lesson from update 0.
# No cost for firing at all: refused unless every firing cost is zero. Refuses unless: the code here is 1.7b's; no trainer runs; 1.7a's
# update 90, its optimizer, its save of update 10 (the order's reference is checked against it), the controls and the anchors are there;
# the settings check passes against 1.7a's command (only the named differences) and against the save; the start answers as update 90;
# the run folder is new; live.json and every file the ramp will write are accepted by the trainer's own reader. After the start: the
# trainer's log must say the optimizer's state was loaded (a failed load stops the trainer: no --opt-cold-ok). No dry run (owner, 11-04).
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File docs\runs\1.7\1.7b\start.ps1 [-Minutes 1080]
param([int]$Minutes = 1080)
$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = (Resolve-Path (Join-Path $HERE "..\..\..\..")).Path
$PY = if ($env:BB_PY) { $env:BB_PY } else { Join-Path $env:USERPROFILE "anaconda3\python.exe" }
$SR = Join-Path $ROOT "data\sim_runs"
$R0 = Join-Path $SR "duel_gru_1_7a"
$K0 = Join-Path $R0 "keep"
$RUN = "duel_gru_1_7b"
$R1 = Join-Path $SR $RUN
$LOG = Join-Path $HERE "start.log"
function Log($m) { $l = (Get-Date -Format "MM-dd HH:mm:ss ") + $m; Add-Content -Path $LOG -Value $l; $l }

if ($Minutes -le 0) { Log "no length (-Minutes): not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $ROOT "sim\duel_env.py") -Pattern "^FIGHT_TRUTH = " -Quiet) -or -not (Test-Path (Join-Path $ROOT "tools\b17b_init.py")) -or -not (Test-Path (Join-Path $ROOT "sim\fightodds.py"))) { Log "the code here is not 1.7b's (merge b17b first): not started"; exit 1 }
if ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*train_duel_rnn*" } | Measure-Object).Count -gt 0) { Log "A TRAINER IS RUNNING: not started"; exit 1 }
$END = Join-Path $K0 "policy_end_17a.pt"; $OPTF = Join-Path $K0 "opt_end_17a.pt"; $P10 = Join-Path $K0 "policy_10.pt"
$CB12 = Join-Path $K0 "control_b12d.pt"
foreach ($p in $END, $OPTF, $P10, $CB12) { if (-not (Test-Path $p)) { Log "MISSING ${p}: not started"; exit 1 } }
$ANCH = "anchor_16a.pt", "anchor_15a.pt", "anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt"
foreach ($n in $ANCH) { if (-not (Test-Path (Join-Path $R0 "snapshots\$n"))) { Log "MISSING 1.7a's anchor ${n}: not started"; exit 1 } }
& $PY (Join-Path $HERE "make_files.py") $Minutes | ForEach-Object { Log ("train.cmd, a cap of $Minutes minutes, 150 updates: " + $_) }
if ($LASTEXITCODE -ne 0) { Log "make_files failed: not started"; exit 1 }
# (owner, 11-04 night: "there should be no cost for firing AT ALL") every firing cost at zero, in the command and in live.json
& $PY -c "import json, re, sys; t = open(sys.argv[1]).read(); d = json.load(open(sys.argv[2])); s = lambda n: float((re.findall(r'^set ' + n + r'=(\S*)\s*$', t, re.M) or ['0'])[-1] or 0); bad = {n: s(n) for n in ('SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if s(n) != 0}; bad.update({'BLIND_RL_DMG (unset: 6 by default)': 6} if not re.search(r'^set BLIND_RL_DMG=', t, re.M) else {}); bad.update({'live ' + n: d[n] for n in ('COST_FIRE_W', 'SHOT_COST', 'RG_FAR_PRICE', 'BLIND_FIRE_W', 'BLIND_RL_DMG') if n in d and float(d[n]) != 0}); bad.update({} if 'COST_FIRE_W' in d else {'live COST_FIRE_W': 'missing (1 by default)'}); print('no firing cost: every one at zero' if not bad else 'A FIRING COST ABOVE ZERO: ' + str(bad)); sys.exit(1 if bad else 0)" (Join-Path $HERE "train.cmd") (Join-Path $R0 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "a firing cost above zero: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ref (Join-Path $ROOT "docs\runs\1.7\1.7a\train.cmd") "--allow=--run,--minutes,--max-updates,--keep-g,--fight-odds,--fight-warm,--head2-opg,--ord-kl,FIGHT_TRUTH,OUT_LIVE" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.7a's command): not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\check_settings.py") (Join-Path $HERE "train.cmd") --ck $END "--allow=--max-updates,--keep-g,--fight-odds,--fight-warm,--head2-opg,--ord-kl,FIGHT_TRUTH,OUT_LIVE,CONTACT_FREE,LEVEL_PULL,RAIL_FAR_PAY" | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "SETTINGS CHECK FAILED (against 1.7a's update 90): not started"; exit 1 }
if (Test-Path (Join-Path $R1 "policy.pt")) { Log "$R1 already has a policy.pt: not started (nothing overwritten)"; exit 1 }

& $PY (Join-Path $ROOT "tools\run\backup.py") | ForEach-Object { Log $_ }
New-Item -ItemType Directory -Force (Join-Path $R1 "snapshots"), (Join-Path $R1 "keep"), (Join-Path $R1 "watch") | Out-Null
$env:CUDA_VISIBLE_DEVICES = "-1"
& $PY (Join-Path $ROOT "tools\b17b_init.py") add $END (Join-Path $R1 "policy.pt") --ref $P10 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Remove-Item Env:\CUDA_VISIBLE_DEVICES; Log "b17b_init add failed: not started"; exit 1 }
Copy-Item $OPTF (Join-Path $R1 "opt.pt")
& $PY (Join-Path $ROOT "tools\b17b_init.py") same $END (Join-Path $R1 "policy.pt") | ForEach-Object { Log $_ }
$sameOk = $LASTEXITCODE
if ($sameOk -eq 0) {                                                 # (the league's files: 1.7b's inputs and the head's at zero; 1.7a's update 90 as an anchor)
    & $PY (Join-Path $ROOT "tools\b17b_init.py") widen-league $END (Join-Path $R1 "snapshots\anchor_17a.pt") | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) { $sameOk = 1 }
    foreach ($n in $ANCH) {
        if ($sameOk -eq 0) {
            & $PY (Join-Path $ROOT "tools\b17b_init.py") widen-league (Join-Path $R0 "snapshots\$n") (Join-Path $R1 "snapshots\$n") | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -ne 0) { $sameOk = 1 }
        }
    }
}
Remove-Item Env:\CUDA_VISIBLE_DEVICES
if ($sameOk -ne 0) { Log "THE START DOES NOT ANSWER AS 1.7a's UPDATE 90 (b17b_init same) or a league file was not converted: not started (the run folder has the start files only)"; exit 1 }
& $PY -c "import json, sys; d = json.load(open(sys.argv[1])); d.update(KEEP_G=1.0, CMB_G=0.0, PADD=0.0, ORD_GATE=-30.0, FADD=0.0, H2_FPG=0.0, DMG_TAKEN_W=0.8, H2_OPG=0.0, ORD_KL=0.0, FIGHT_W=1.0, VALUE_WARM=0); json.dump(d, open(sys.argv[2], 'w')); print('live.json:', d)" (Join-Path $R0 "live.json") (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json not made: not started"; exit 1 }
& $PY (Join-Path $ROOT "docs\runs\b1.4\1.4c\live_check.py") $END (Join-Path $R1 "live.json") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "live.json does not carry the save's live dials: not started"; exit 1 }
& $PY (Join-Path $ROOT "tools\run\live_accept.py") (Join-Path $R1 "live.json") --env duel_env_ffa --ramp (Join-Path $HERE "ramp_17b.py") | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) { Log "THE TRAINER WOULD REFUSE live.json (or a file the ramp will write): not started"; exit 1 }
Copy-Item (Join-Path $R1 "policy.pt") (Join-Path $R1 "keep\policy_start_17b.pt")
Copy-Item (Join-Path $R1 "opt.pt") (Join-Path $R1 "keep\opt_start_17b.pt")
$CK = Join-Path $R1 "keep\control_17a.pt"; $CR = Join-Path $R1 "keep\control_b12d.pt"
Copy-Item $END $CK
Copy-Item $CB12 $CR
Copy-Item (Join-Path $R0 "live_settings.env") (Join-Path $R1 "live_settings.env")
Log ("from " + $END + " given 1.7b's parts at zero effect, with its optimizer; anchors (widened) 1.7a's update 90, 1.6a's end, 1.5a's end, 1.3b's end, b1.2d's end, b1.1, v0.6.0's end (1.7a's even draw)")

$t = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", (Join-Path $HERE "train.cmd") -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Log ("trainer started: cmd " + $t.Id + ", from 1.7a's update 90, 150 updates (a cap of " + $Minutes + " minutes)")
$ST = Join-Path $R1 "live_status.json"; $t0 = Get-Date
while (-not (Test-Path $ST) -and -not $t.HasExited -and ((Get-Date) - $t0).TotalMinutes -lt 20) { Start-Sleep 5 }
$st = if (Test-Path $ST) { Get-Content $ST -Raw | ConvertFrom-Json } else { $null }
if ($null -eq $st -or $st.status -ne "applied") {
    Log ("THE TRAINER DID NOT APPLY live.json (" + $(if ($null -eq $st) { if ($t.HasExited) { "the trainer exited" } else { "no answer in 20 minutes" } } else { $st.reason }) + "): the watcher, the ramp and the logger not started; see " + $RUN + ".log")
    exit 1
}
Log ("live.json applied by the trainer before its first rollout (" + $st.time + ")")
$WD = Join-Path $R1 "watch"
$env:CTRL_PREV = $CK; $env:CTRL_PREV_LABEL = "the start (1.7a's update 90)"
$env:CTRL_REF = $CR; $env:CTRL_REF_LABEL = "b1.2d's end (reference)"
$env:PANEL_RUN = $RUN; $env:PANEL_CTRL = $CK; $env:CHECK_RULE = "0"
$env:CHECK_EVERY = "20"; $env:CHECK_GAMES = "20"                  # 200 games a check (owner, 2026-11-02)
$env:CHECK_CYPHER = "1"                                            # (1.7b, the card) Cypher's measures of every check against the start
$CHK = [IntPtr]0x3C3C                                              # (owner, 2026-11-02) everything beside the trainer on 8 efficiency cores; 14-17 left for the owner
$env:CHECK_BATCH = "4"; $env:PANEL_PAR = "2"; $env:PANEL_PAR_BUSY = "1"
$w = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\watch.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "watch_stdout.log") -RedirectStandardError (Join-Path $WD "watch_stderr.log")
$w.ProcessorAffinity = $CHK
Start-Sleep 5
$r = Start-Process -FilePath $PY -ArgumentList (Join-Path $HERE "ramp_17b.py"), $RUN -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "ramp_stdout.log") -RedirectStandardError (Join-Path $WD "ramp_stderr.log")
$r.ProcessorAffinity = $CHK
$s = Start-Process -FilePath $PY -ArgumentList (Join-Path $ROOT "tools\run\selfplay_loop.py"), $RUN, "--every", "40", "--games", "5", "--par", "1" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WD "selfplay_stdout.log") -RedirectStandardError (Join-Path $WD "selfplay_stderr.log")
$s.ProcessorAffinity = $CHK
Log ("watcher " + $w.Id + " | ramp " + $r.Id + " (its dials: ramp_17b.py; never held or stepped back; a check under 40% a MAJOR PROBLEM in watch.log) | self-play logger " + $s.Id + " | no guard (owner: never stop the run)")
$TL = Join-Path $SR ($RUN + ".log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {                                    # (the optimizer's state from 1.7a's, never a cold start unasked)
    Start-Sleep 10
    if ((Test-Path $TL) -and (Select-String -Path $TL -Pattern "optimizer: " -Quiet)) { $ok = $true; break }
}
if ($ok) { Select-String -Path $TL -Pattern "optimizer: |keep choice|combat order|fight odds|order KL|order's token|pass" | ForEach-Object { Log ("trainer: " + $_.Line) } }
else { Log "the trainer's log has no optimizer line after 10 minutes: LOOK AT IT" }
