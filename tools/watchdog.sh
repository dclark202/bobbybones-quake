#!/bin/bash
# Kill the server if it stops answering (hung); the container then restarts and re-sets itself up.
sleep 90
fails=0
while true; do
    sleep 30
    if timeout 15 python3 /tools/rcon.py "status" --wait 3 2>/dev/null | grep -q "map:"; then
        fails=0
    else
        fails=$((fails + 1))
        echo "$(date -u) no answer from server ($fails)" >> /tmp/practice/watchdog.log
        if [ "$fails" -ge 3 ]; then
            echo "$(date -u) server hung - killing it so the container restarts" >> /tmp/practice/watchdog.log
            pkill -9 -f qzeroded
            fails=0
        fi
    fi
done
