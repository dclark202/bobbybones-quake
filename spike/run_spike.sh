#!/bin/bash
# run_spike.sh -- Phase-0 spike driver (runs on KNECHT).
#
# Boots the botctl-patched Quake3e dedicated server with a FRESH home
# (~/.q3a_spike), port 28133 (28132 = live dwc.4 training, never touched),
# waits for the botctl socket, runs the requested sidecar scenario, checks
# the engine stayed alive, and (for t5) confirms the match actually started
# via the second "InitGame:" log line (the match_carespawn in-place
# map_restart re-runs G_Init).
#
# TDM setup -- hard-won facts (2026-11-15, see cvar_ab/cvar_verify runs):
#  * g_gametype is CVAR_LATCH. Engine-cvar +set args are DEFERRED by
#    Com_StartupVariable and re-applied with force=qfalse (latch path);
#    the "map" command then applies latched values (SV_Map_f: Cvar_Get
#    "force latched values to get set"). So: engine cvars on the command
#    line, game cvars in spike.cfg exec'd AFTER startup, then "map".
#  * OSP's TDM is g_gametype 3 (GT_TEAM) -- NOT 2! 2 is GT_SINGLE_PLAYER
#    and SV_Map_f explicitly rewrites GT_SINGLE_PLAYER -> GT_FFA (0).
#    (The live server runs g_gametype 3, "TeamplayDM".)
#  * Real cvar names: "timelimit" (not g_timelimit), "fraglimit" (not
#    g_fraglimit); there is no scorelimit cvar in this OSP build.
#  * t5 marker: the in-place map_restart does NOT run sv_onRestart (that
#    only fires on the 12h/time-wrap SV_Restart, commit 81eaa5fd). It
#    DOES re-run G_Init -> a second "InitGame:" line in the log.
#    (Baseline: a single map load produces exactly ONE "InitGame:" line.)
#  * Engine SIGTERM handling works (linux_signals.c handler -> SV_Shutdown
#    + _exit(0), logged as "Signal caught (15)"). The T1-151413 "hang"
#    was a bash trap: "wait $!" on a backgrounded PIPELINE waits for the
#    WHOLE pipeline, so the feeder subshell's "sleep 99999" kept the wait
#    alive for minutes. => stdin goes through a FIFO now, both PIDs are
#    owned explicitly, cleanup = TERM with 10 s grace + KILL fallback.
#
# Usage:  run_spike.sh <scenario t1..t8> [seconds]
#
# Logs:   ~/tmp/spike/server_<scen>_<ts>.log
#         ~/tmp/spike/sidecar_<scen>_<ts>.log

set -u

SCEN=${1:-t1}
case "$SCEN" in
  t6) SECS=${2:-600} ;;
  t3) SECS=${2:-16}  ;;   # 2x8s substep runs
  *)  SECS=${2:-10}  ;;
esac

Q3=/home/hkuehnemund/q3e
ENGINE=/home/hkuehnemund/tmp/q3e_botctl/build/release-linux-x86_64/quake3e.ded.x64
SPIKE_HOME=/home/hkuehnemund/.q3a_spike
SIDECAR=/home/hkuehnemund/tmp/knecht-q3-bot/spike/sidecar.py
PORT=28133
# engine default socket (V2): fs_homepath + /botctl-<net_port>.sock, chmod 0600
SOCK=$SPIKE_HOME/botctl-$PORT.sock
LOGDIR=/home/hkuehnemund/tmp/spike
TS=$(date +%H%M%S)
mkdir -p "$LOGDIR"
LOG=$LOGDIR/server_${SCEN}_${TS}.log
SCLOG=$LOGDIR/sidecar_${SCEN}_${TS}.log
FIFO=$LOGDIR/stdin-$SCEN-$TS.fifo

SERVER_PID=""
FEEDER_PID=""

fail() { echo "RESULT $SCEN: FAIL $*" | tee -a "$SCLOG"; exit 1; }

[ -x "$ENGINE" ] || fail "engine not built: $ENGINE"

# only 28133 must be free (28132 = live dwc.4 training, expected & untouched)
if ss -ltnu 2>/dev/null | awk '{print $5}' | grep -qE ":$PORT\s*$"; then
  fail "port $PORT already in use"
fi

# fresh home every run: isolated from production ~/.q3a (no persisted cvars,
# no botmem learn files -- bot_memory 0 anyway)
rm -rf "$SPIKE_HOME"
mkdir -p "$SPIKE_HOME/osp"

# spike.cfg = the game cvars, exec'd AFTER startup (see header: latch +
# SV_Map_f single-player rewrite). t5 uses g_warmup 10 so the match starts
# ~9 s after the last team join (SetTeam resets warmup to
# level.time + 1000*g_warmup - 1000).
WARMUP=30
[ "$SCEN" = "t5" ] && WARMUP=10
# t7 needs the botlib game side (rcon "addbot dwcbot1 5 red" after the kick):
# bot_enable 1 + the dwc botfiles pk3 (scripts/bots.txt + botfiles/bots/*_c.c)
# deployed into the HOME gamedir -- it outranks the install pk3s.
BOT_ENABLE=0
[ "$SCEN" = "t7" ] && BOT_ENABLE=1
cat > "$SPIKE_HOME/osp/spike.cfg" <<EOF
rconPassword testrcon123
g_gametype 3
g_doWarmup 1
g_warmup $WARMUP
timelimit 20
fraglimit 0
g_teamAutoJoin 0
g_teamForceBalance 0
match_carespawn 1
match_instagib 0
pmove_fixed 0
bot_enable $BOT_ENABLE
bot_ai 0
bot_autoload "[none]"
bot_memory 0
EOF
if [ "$SCEN" = "t7" ]; then
  ASSET=/home/hkuehnemund/tmp/spike_assets/zzz_dwc_bots.pk3
  [ -f "$ASSET" ] || fail "t7 needs the dwc botfiles pk3: $ASSET missing"
  cp "$ASSET" "$SPIKE_HOME/osp/" || fail "copy $ASSET"
fi

cd "$Q3" || fail "cd $Q3"

# stdin via FIFO: the feeder's open-for-write blocks until the engine opens
# the FIFO at startup, then it paces the console commands. (A pipe would
# work too, but then "wait $!" waits for the whole pipeline, incl. the
# feeder's "sleep 99999" -- see the header note.)
mkfifo "$FIFO" || fail "mkfifo $FIFO"
(
  sleep 3
  printf 'exec spike\n'
  sleep 2
  printf 'map q3dm7\n'
  sleep 99999
) > "$FIFO" &
FEEDER_PID=$!

nohup "$ENGINE" \
   +set fs_game osp \
   +set dedicated 1 \
   +set net_port "$PORT" \
   +set match_instagib 0 \
   +set com_hunkMegs 256 \
   +set fs_basepath "$Q3" \
   +set fs_homepath "$SPIKE_HOME" \
   +set sv_pure 0 \
   +set botctl_enable 1 \
   < "$FIFO" > "$LOG" 2>&1 &
SERVER_PID=$!
echo "SERVER_PID=$SERVER_PID FEEDER_PID=$FEEDER_PID LOG=$LOG SCLOG=$SCLOG"

cleanup() {
  # feeder first: its "sleep 99999" must not outlive the run
  if [ -n "$FEEDER_PID" ]; then
    kill "$FEEDER_PID" 2>/dev/null
  fi
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill -TERM "$SERVER_PID" 2>/dev/null
    # the engine's SIGTERM handler does a full SV_Shutdown (logged as
    # "Signal caught (15)"); give it up to 10 s, then KILL
    for i in $(seq 1 20); do
      kill -0 "$SERVER_PID" 2>/dev/null || break
      sleep 0.5
    done
    if kill -0 "$SERVER_PID" 2>/dev/null; then
      echo "engine ignored SIGTERM, sending KILL" | tee -a "$SCLOG"
      kill -KILL "$SERVER_PID" 2>/dev/null
    fi
  fi
  if [ -n "$SERVER_PID" ]; then
    wait "$SERVER_PID" 2>/dev/null
    echo "SERVER_EXIT=$?" | tee -a "$SCLOG"
  fi
  [ -n "$FEEDER_PID" ] && wait "$FEEDER_PID" 2>/dev/null
  rm -f "$FIFO" "$SOCK" 2>/dev/null
  return 0
}
trap cleanup EXIT

# wait for the botctl socket (engine startup, before the map)
for i in $(seq 1 60); do
  [ -S "$SOCK" ] && break
  sleep 0.5
done
[ -S "$SOCK" ] || fail "botctl socket never appeared (see $LOG)"
echo "socket up: $SOCK"

# wait for the map load AND confirm the server is really TDM:
# the InitGame line carries the cvar values at G_Init time
ok=0
for i in $(seq 1 90); do
  if grep -q 'InitGame: .*\\g_gametype\\3' "$LOG" 2>/dev/null; then
    ok=1
    break
  fi
  kill -0 "$SERVER_PID" 2>/dev/null || fail "engine died during startup (see $LOG)"
  sleep 0.5
done
[ "$ok" = 1 ] || { tail -n 30 "$LOG" | tee -a "$SCLOG"; fail "map never loaded / not TDM (g_gametype 3)"; }
echo "map loaded, TDM confirmed"
sleep 1

# t5 adds its own red+blue pair; the single-bot scenarios need an explicit
# team (g_teamAutoJoin 0 here, so a teamless TDM player would just spectate)
TEAM_ARG=""
[ "$SCEN" != "t5" ] && TEAM_ARG="--team red"

python3 "$SIDECAR" --port "$PORT" --sockpath "$SOCK" --scenario "$SCEN" \
   --seconds "$SECS" --botname SpikeBot $TEAM_ARG >> "$SCLOG" 2>&1
RC=$?
tail -n 5 "$SCLOG"

# t5: the match must have started. match_carespawn 1 -> warmup expiry does
# an in-place map_restart -> G_Init runs again -> SECOND "InitGame:" line
# (sv_onRestart does NOT fire on map/map_restart, only on the 12h restart;
# baseline: the first map load produces exactly one InitGame line)
if [ "$SCEN" = "t5" ]; then
  echo -n "waiting for match start (second InitGame)..."
  for i in $(seq 1 60); do
    [ "$(grep -c '^InitGame:' "$LOG" 2>/dev/null)" -ge 2 ] && break
    sleep 1
  done
  if [ "$(grep -c '^InitGame:' "$LOG" 2>/dev/null)" -ge 2 ]; then
    echo "RESULT t5-log: PASS match restart observed in server log" | tee -a "$SCLOG"
  else
    echo "RESULT t5-log: FAIL no match restart in server log (warmup never ended?)" | tee -a "$SCLOG"
    RC=1
  fi
fi

# lifecycle scenarios: the engine-side drop hooks must show up in the log
# (Botctl_ClientDropped queues "management cleared"; the sidecar-loss drop
#  path uses the reason "bot control connection lost")
if [ "$SCEN" = "t7" ]; then
  if grep -q 'management cleared' "$LOG" 2>/dev/null; then
    echo "RESULT t7-log: PASS engine cleared management on its drop path" | tee -a "$SCLOG"
  else
    echo "RESULT t7-log: FAIL no 'management cleared' line in server log" | tee -a "$SCLOG"
    RC=1
  fi
fi
if [ "$SCEN" = "t5b" ]; then
  # TDM rotation (killBots=qfalse): managed clients are reconnected, NOT
  # dropped. NOTE: the rcon redirect swallows the map-change console output
  # (it is returned to the rcon client), so 'map ospdm6' never appears in
  # the log -- the rotation itself is proven by the sidecar's restart_id
  # check; the log only has to show NO wrongful management clearing.
  if ! grep -q 'management cleared' "$LOG" 2>/dev/null; then
    echo "RESULT t5b-log: PASS rotation kept management intact" | tee -a "$SCLOG"
  else
    echo "RESULT t5b-log: FAIL management wrongly cleared during rotation" | tee -a "$SCLOG"
    RC=1
  fi
fi
if [ "$SCEN" = "t8" ]; then
  if grep -q 'bot control connection lost' "$LOG" 2>/dev/null; then
    echo "RESULT t8-log: PASS engine dropped the orphaned managed clients" | tee -a "$SCLOG"
  else
    echo "RESULT t8-log: FAIL no 'bot control connection lost' line in server log" | tee -a "$SCLOG"
    RC=1
  fi
fi
if [ "$SCEN" = "t5c" ]; then
  # 'Server Shutdown (killserver)' itself is NOT log-verifiable: it is printed
  # inside the rcon redirect (returned to the rcon client -- the sidecar
  # asserts it from the RCON answer). The queued 'management cleared' line IS
  # drained by Botctl_Frame after the restart and lands in the log.
  if grep -q 'management cleared' "$LOG" 2>/dev/null; then
    echo "RESULT t5c-log: PASS shutdown cleared management" | tee -a "$SCLOG"
  else
    echo "RESULT t5c-log: FAIL missing management-cleared line" | tee -a "$SCLOG"
    RC=1
  fi
fi

# the engine must have survived the whole scenario
if kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "engine alive at scenario end" | tee -a "$SCLOG"
else
  echo "RESULT $SCEN: FAIL engine died during scenario (see $LOG)" | tee -a "$SCLOG"
  tail -n 30 "$LOG" | tee -a "$SCLOG"
  RC=1
fi

exit "$RC"
