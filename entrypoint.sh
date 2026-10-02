#!/bin/bash
redis-server --daemonize yes >/dev/null
cp -n /ql/baseq3-extra/* /ql/baseq3/ 2>/dev/null
/tools/bootstrap.sh >/dev/null 2>&1 &
cd /ql
./run_server_x64_minqlx.sh \
    +set net_ip 0.0.0.0 \
    +set net_port 27960 \
    +set sv_hostname "ql-bot lab" \
    +set fs_homepath /ql/home \
    +set qlx_plugins "botctl, jumplab, practice, itemrun" \
    +set qlx_pluginsPath /ql/minqlx-plugins \
    +set qlx_owner "${QLX_OWNER:-}" \
    +set zmq_stats_enable 1 \
    +set zmq_stats_password "lab" \
    +set zmq_rcon_enable 1 \
    +set zmq_rcon_ip 127.0.0.1 \
    +set zmq_rcon_password "lab" \
    +set bot_enable 1 \
    +set bot_nochat 1 \
    +exec lab.cfg \
    "$@" 2>&1 | tee -a /tmp/practice/server.log
exit ${PIPESTATUS[0]}
