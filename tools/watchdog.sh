#!/bin/bash
# Kill the server if it is truly hung: its main thread's CPU time stops advancing (a live server always burns a little
# CPU running frames, even idle or between maps: 21 ticks in 30 s with no bots and nobody on). The container then
# restarts and re-sets itself up. The main thread's time, not the whole process's: with the main thread blocked for good
# (2026-10-09: in a console print, on an rcon client that left during a map load) the game's helper threads still
# used 5 ticks in 20 s and the hang went unseen.
sleep 120
last=""; stuck=0
while true; do
    sleep 30
    pid=$(pgrep -f qzeroded | head -1)
    [ -z "$pid" ] && continue
    if [ -f /tmp/practice/restart.flag ]; then          # the tuning coach wants fresh bot files loaded
        rm -f /tmp/practice/restart.flag
        echo "$(date -u) restart requested (new candidate)" >> /tmp/practice/watchdog.log
        kill -9 "$pid"; last=""; stuck=0; continue
    fi
    t=$(awk '{print $14 + $15}' /proc/$pid/task/$pid/stat 2>/dev/null)
    if [ -n "$last" ] && [ "$t" = "$last" ]; then
        stuck=$((stuck + 1))
        echo "$(date -u) server CPU time not advancing ($stuck)" >> /tmp/practice/watchdog.log
        if [ "$stuck" -ge 3 ]; then
            echo "$(date -u) server hung - killing it so the container restarts" >> /tmp/practice/watchdog.log
            kill -9 "$pid"; stuck=0
        fi
    else
        stuck=0
    fi
    last=$t
done
