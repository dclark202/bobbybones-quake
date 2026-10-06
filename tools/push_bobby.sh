#!/bin/bash
# Put a run's current network on the public server. The server's address is in data/owner.env (git-ignored):
#   PUBLIC_HOST=root@<address>
#   bash tools/push_bobby.sh <run> [simulator module=duel_env_ffa]          the network only: the running server picks
#                                                                             it up by itself between rooms
#   CODE=1 bash tools/push_bobby.sh <run> [module] [map=arena1]             also the newest code and maps (git pull, image
#                                                                             build, restart): needed whenever the simulator,
#                                                                             the plugin or a map changed since the last push
set -e
cd "$(dirname "$0")/.."
RUN="${1:?run name}"; ENVMOD="${2:-duel_env_ffa}"; MAP="${3:-arena1}"
HOST="$(grep '^PUBLIC_HOST=' data/owner.env 2>/dev/null | cut -d= -f2)"
[ -n "$HOST" ] || { echo "add PUBLIC_HOST=root@<address> to data/owner.env"; exit 1; }
mkdir -p data/public
"${PYTHON:-python}" sim/export_duel.py --run "$RUN" --env "$ENVMOD" --out data/public/policy.npz
if [ -n "$CODE" ]; then
    ssh -o BatchMode=yes "$HOST" 'cd bobbybones-quake && git pull -q && docker build -q -t qlbot . >/dev/null && echo "code and image up to date: $(git log --oneline | head -1)"'
fi
scp -o BatchMode=yes -q data/public/policy.npz "$HOST":bobbybones-quake/data/duellive/policy.npz
echo "network of $RUN copied to the public server"
if [ -n "$CODE" ]; then
    NAME_QL="$(ssh -o BatchMode=yes "$HOST" "docker inspect qlduel --format '{{index .Config.Cmd 5}}' 2>/dev/null")"
    ssh -o BatchMode=yes "$HOST" "cd bobbybones-quake && RESTART=1 HOSTNAME_QL=\"${NAME_QL:-BobbyBones - the learning quake bot}\" bash tools/duel_server.sh - $MAP | tail -1"
fi
ssh -o BatchMode=yes "$HOST" 'sleep 20; tail -1 bobbybones-quake/data/duellive/duelbot.log'
