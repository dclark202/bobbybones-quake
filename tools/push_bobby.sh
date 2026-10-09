#!/bin/bash
# Put a run's current network on the public server. The server's address is in data/owner.env (git-ignored):
#   PUBLIC_HOST=root@<address>
#   bash tools/push_bobby.sh <run> [simulator module=duel_env_ffa]          the network only: the running server picks
#                                                                             it up by itself between rooms
#   CODE=1 bash tools/push_bobby.sh <run> [module] [map=aerowalk]           also the newest code and maps (git pull, image
#                                                                             build, restart in free-for-all with FFA=<n> Bobbys, 2 by default
#                                                                             (owner, 2026-10-09: Aerowalk and two; it was arena1 and three);
#                                                                             build, restart): needed whenever the simulator,
#                                                                             the plugin or a map changed since the last push
set -e
cd "$(dirname "$0")/.."
RUN="${1:?run name}"; ENVMOD="${2:-duel_env_ffa}"; MAP="${3:-aerowalk}"
HOST="$(grep '^PUBLIC_HOST=' data/owner.env 2>/dev/null | cut -d= -f2)"
[ -n "$HOST" ] || { echo "add PUBLIC_HOST=root@<address> to data/owner.env"; exit 1; }
mkdir -p data/public
"${PYTHON:-python}" sim/export_duel.py --run "$RUN" --env "$ENVMOD" --out data/public/policy.npz $EXPORT_ARGS   # EXPORT_ARGS="--set INTENT_HOLD=8": the switches a run before v13 was trained with
if [ -n "$CODE" ]; then
    ssh -o BatchMode=yes "$HOST" 'cd bobbybones-quake && git checkout -q -- . && git pull -q && docker build -q -t qlbot . >/dev/null && echo "code and image up to date: $(git log --oneline | head -1)"'
fi
scp -o BatchMode=yes -q data/public/policy.npz "$HOST":bobbybones-quake/data/duellive/policy.npz
echo "network of $RUN copied to the public server"
if [ -n "$CODE" ]; then
    DEFAULT_QL="doppz's bot arena | duel & FFA | chicago"          # (kept out of the ${...:-...} below: an apostrophe inside it is a syntax error in bash)
    NAME_QL="${HOSTNAME_QL:-$DEFAULT_QL}"                         # the name in the server list (HOSTNAME_QL=... to change it)
    # the routes need the walking maps, and data/ is not in git: the maps the server offers, each as the PC has it now
    # (2026-10-09: only the start map's was copied, and Aerowalk's on the server was two days older than the one he trained on)
    # (2026-10-09 evening: the ten duel maps of the !map list; the map file itself the plugin takes from the game's own pak)
    for m_ in "$MAP" bloodrun aerowalk lostworld sinister furiousheights battleforged campgrounds hektik toxicity cure; do
        scp -o BatchMode=yes -q data/maps/nav_${m_}_sim.json data/maps/cells_${m_}.npy "$HOST":bobbybones-quake/data/maps/ 2>/dev/null || true
    done
    ssh -o BatchMode=yes "$HOST" "cd bobbybones-quake && PUBLIC=1 FFA=${FFA:-2} RESTART=1 HOSTNAME_QL=\"$NAME_QL\" bash tools/duel_server.sh - $MAP | tail -1"
fi
ssh -o BatchMode=yes "$HOST" 'sleep 20; tail -1 bobbybones-quake/data/duellive/duelbot.log'
