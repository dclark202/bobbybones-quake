#!/bin/bash
# Put a run's current network on the public server. The server's address is in data/owner.env (git-ignored):
#   PUBLIC_HOST=root@<address>
#   bash tools/push_bobby.sh <run> [simulator module=duel_env_ffa]          the network only: the running server picks
#                                                                             it up by itself between rooms
#   CODE=1 bash tools/push_bobby.sh <run> [module] [map=campgrounds]        also the newest code and maps (git pull, image
#                                                                             build, restart in 1v1 by default (owner, 2026-10-15: duel on every
#                                                                             map, Campgrounds; it was free-for-all with two Bobbys on Blood Run),
#                                                                             FFA=<n> for free-for-all with n Bobbys;
#                                                                             build, restart): needed whenever the simulator,
#                                                                             the plugin or a map changed since the last push
#   QLSTATS=1 CODE=1 bash tools/push_bobby.sh ...                           the restart also switches the leaderboard's QLStats
#                                                                             lookup on (plugins/ladder.py; off without it: every
#                                                                             CODE=1 push must name it again, as FFA and HOSTNAME_QL)
# v0.1 as it is on the server (the network unchanged, new code):
#   QLSTATS=1 CODE=1 EXPORT_ARGS="--policy policy_end_v15c.pt --legs move_v15n --set LEGS_OFF=2" \
#       bash tools/push_bobby.sh duel_gru_v15c duel_env_ffa_v15 bloodrun
set -e
cd "$(dirname "$0")/.."
RUN="${1:?run name}"; ENVMOD="${2:-duel_env_ffa}"; MAP="${3:-campgrounds}"
HOST="$(grep '^PUBLIC_HOST=' data/owner.env 2>/dev/null | cut -d= -f2)"
[ -n "$HOST" ] || { echo "add PUBLIC_HOST=root@<address> to data/owner.env"; exit 1; }
mkdir -p data/public
rm -f data/public/legs.npz                                    # (a network with legs brings its own: sim/export_duel.py --legs <run>)
"${PYTHON:-python}" sim/export_duel.py --run "$RUN" --env "$ENVMOD" --out data/public/policy.npz $EXPORT_ARGS   # EXPORT_ARGS="--set INTENT_HOLD=8": the switches a run before v13 was trained with
if [ -n "$CODE" ]; then
    ssh -o BatchMode=yes "$HOST" 'cd bobbybones-quake && git checkout -q -- . && git pull -q && docker build -q -t qlbot . >/dev/null && echo "code and image up to date: $(git log --oneline | head -1)"'
fi
if [ -f data/public/legs.npz ]; then                          # his legs' network first: the plugin loads it when it sees the new policy file
    scp -o BatchMode=yes -q data/public/legs.npz "$HOST":bobbybones-quake/data/duellive/legs.npz
fi
scp -o BatchMode=yes -q data/public/policy.npz "$HOST":bobbybones-quake/data/duellive/policy.npz
echo "network of $RUN copied to the public server"
if [ -n "$CODE" ]; then
    DEFAULT_QL="doppz's bot arena | duel & FFA | chicago"          # (kept out of the ${...:-...} below: an apostrophe inside it is a syntax error in bash)
    NAME_QL="${HOSTNAME_QL:-$DEFAULT_QL}"                         # the name in the server list (HOSTNAME_QL=... to change it)
    # the routes need the walking maps, and data/ is not in git: the maps the server offers, each as the PC has it now
    # (2026-10-09: only the start map's was copied, and Aerowalk's on the server was two days older than the one he trained on)
    # (2026-10-09 evening: the ten duel maps of the !map list; the map file itself the plugin takes from the game's own pak)
    # (v0.2: and each map's table of ways, data/maps/nav_<map>_sim.json.ways_*.npz, which the last 143 inputs read. The
    # server looks for it beside the walking map; where it is missing or was made under other switches, tools/duel_server.sh
    # makes it before the server starts, tools/prep_ways.py, so that no player waits through it.)
    for m_ in "$MAP" bloodrun aerowalk lostworld sinister furiousheights battleforged campgrounds hektik toxicity cure; do
        scp -o BatchMode=yes -q data/maps/nav_${m_}_sim.json data/maps/cells_${m_}.npy data/maps/nav_${m_}_sim.json.ways_*.npz "$HOST":bobbybones-quake/data/maps/ 2>/dev/null || true
    done
    ssh -o BatchMode=yes "$HOST" "cd bobbybones-quake && PUBLIC=1 FFA=${FFA:-} RESTART=1 QLSTATS=${QLSTATS:-} HOSTNAME_QL=\"$NAME_QL\" bash tools/duel_server.sh - $MAP | tail -1"   # (FFA empty: 1v1)
fi
ssh -o BatchMode=yes "$HOST" 'sleep 20; tail -1 bobbybones-quake/data/duellive/duelbot.log'
