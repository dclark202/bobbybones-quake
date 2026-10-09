#!/bin/bash
redis-server --daemonize yes >/dev/null
cp -n /ql/baseq3-extra/* /ql/baseq3/ 2>/dev/null
cp -f /ql/baseq3-extra/workshop.txt /ql/baseq3/workshop.txt 2>/dev/null   # ours replaces the game's empty one
/tools/watchdog.sh >/dev/null 2>&1 &
# No powerups on any server (owner, 2026-10-09; plugins/powerups.py): the game's own switch is off for the first map too
# (the plugins put a map's duel items in place in every mode, Campgrounds' mega among them).
cd /ql
./run_server_x64_minqlx.sh \
    +set net_ip 0.0.0.0 \
    +set net_port 27960 \
    +set fs_homepath /ql/home \
    +set qlx_plugins "${QLX_PLUGINS:-botctl, duelbot}" \
    +set qlx_pluginsPath /ql/minqlx-plugins \
    +set qlx_owner "${QLX_OWNER:-}" \
    +set zmq_stats_enable 1 \
    +set zmq_stats_password "lab" \
    +set zmq_rcon_enable 1 \
    +set zmq_rcon_ip 127.0.0.1 \
    +set zmq_rcon_password "lab" \
    +set bot_enable 1 \
    +set bot_nochat 1 \
    +set g_spawnItemPowerup 0 \
    +exec lab.cfg \
    "$@" \
    +map "${LAB_MAP:-bloodrun}" "${FACTORY:-duel}" 2>&1 | tee -a /tmp/practice/server.log
exit ${PIPESTATUS[0]}
