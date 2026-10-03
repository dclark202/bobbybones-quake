#!/bin/bash
# (Re)create the public BobbyBones server (container ql, UDP 27970) with everything it needs:
# map pool, CPU priority over the trainers, promoted bot files, owner (admin) Steam ID.
# The owner's Steam ID lives in data/owner.env (git-ignored, never in the repo): QLX_OWNER=<SteamID64>
#   bash tools/public.sh
set -e
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1
ROOT="$(pwd -W 2>/dev/null || pwd)"
QLX_OWNER=""
[ -f data/owner.env ] && . data/owner.env
BOTS=""
ls data/practice/botfiles/bots/*.c >/dev/null 2>&1 && BOTS="-v $ROOT/data/practice/botfiles:/ql/home/baseq3/botfiles"
docker rm -f ql >/dev/null 2>&1 || true
docker run -d --name ql --restart unless-stopped --cpu-shares 16384 \
    -e LAB_VARIANT=aimonly -e LAB_MAPS=bloodrun,aerowalk,campgrounds -e QLX_OWNER="$QLX_OWNER" \
    -p 27970:27970/udp -v "$ROOT/data/practice:/tmp/practice" $BOTS qlbot +set net_port 27970 >/dev/null
echo "public server up (owner $([ -n "$QLX_OWNER" ] && echo set || echo none), bot files $([ -n "$BOTS" ] && echo promoted || echo stock))"
