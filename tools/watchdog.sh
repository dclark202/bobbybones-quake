#!/bin/bash
# Kill the server if it is truly hung: its CPU time stops advancing (a live server always burns a little
# CPU running frames, even idle or between maps). The container then restarts and re-sets itself up.
sleep 120
last=""; stuck=0
while true; do
    sleep 30
    pid=$(pgrep -f qzeroded | head -1)
    [ -z "$pid" ] && continue
    t=$(awk '{print $14 + $15}' /proc/$pid/stat 2>/dev/null)
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
