#!/bin/bash
# Bring the lab back to "duel vs Sarge in permanent warmup" after every (re)start.
sleep 12
R="python3 /tools/rcon.py"
printf "campgrounds|duel\n" > /ql/baseq3/mappool_lab.txt
$R "sv_mapPoolFile mappool_lab.txt" "g_doWarmup 1" "sv_warmupReadyPercentage 2" "map campgrounds duel" --wait 10
$R "timelimit 0" "fraglimit 0" "qlx !autospec off" "addbot bones 5 free 0 BobbyBones" --wait 8
$R "qlx !record on" "qlx !ir start auto -1" --wait 2
echo "bootstrap done $(date -u)" >> /tmp/practice/bootstrap.log
