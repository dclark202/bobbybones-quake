#!/bin/bash
# Continuous learning + housekeeping, every 10 minutes:
#  - weapons: re-learn the weapon table from all recorded play (weighted by damage dealt)
#  - routes:  rebuild this map's nav graph from bot + human movement (fastest observed move wins)
#  - hot-swap both into the running bot, rotate big logs
D=/tmp/practice
while true; do
    sleep 600
    MAP=$(python3 /tools/rcon.py "mapname" --wait 1 | sed -n 's/.*"mapname" is:"\([^^"]*\).*/\1/p' | tr 'A-Z' 'a-z')
    POLICY_OUT=$D/weapon_policy.json python3 /tools/learn_weapons.py $D/trace_live*.txt > $D/learner_last.txt 2>&1 \
        && python3 /tools/rcon.py "qlx !ir policy" --wait 1 >/dev/null
    if [ -n "$MAP" ] && [ -f "$D/trace_live_$MAP.txt" ]; then
        BASE=/ql/maps-data/$MAP/walk_trace.txt
        [ -f "$BASE" ] || BASE=""
        python3 /tools/navgraph.py $BASE $D/trace_live_$MAP.txt $D/nav_$MAP.json.new >> $D/learner_last.txt 2>&1 \
            && mv $D/nav_$MAP.json.new $D/nav_$MAP.json \
            && python3 /tools/rcon.py "qlx !ir nav" --wait 1 >/dev/null
    fi
    echo "$(date -u) map=$MAP $(grep -h 'situations learned\|nodes' $D/learner_last.txt | tr '\n' ' ')" >> $D/learner.log
    # housekeeping: rotate anything over 200 MB, keep 3 old copies
    for f in $D/itemrun_frames.jsonl $D/server.log $D/trace_live_*.txt; do
        [ -f "$f" ] || continue
        if [ "$(stat -c %s "$f")" -gt 209715200 ]; then
            for i in 2 1; do [ -f "$f.$i.gz" ] && mv "$f.$i.gz" "$f.$((i+1)).gz"; done
            gzip -c "$f" > "$f.1.gz" && : > "$f"
        fi
    done
done
