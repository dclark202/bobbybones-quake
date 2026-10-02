#!/bin/bash
# Continuous learning + housekeeping, every 10 minutes.
#
# public server (default):
#   - weapons: re-learn the weapon table from all recorded play (weighted by damage dealt)
#   - routes:  rebuild this map's nav graph from bot + human movement (fastest observed move wins)
# training server (LAB_MODE=train):
#   - the aggregator trainer (TRAIN_AGGREGATOR=1) merges every trainer's experience into /tmp/train/shared
#   - every trainer pulls the shared routes + weapon table
# both: hot-swap into the running bot, rotate big logs
D=/tmp/practice
R="python3 /tools/rcon.py"
while true; do
    sleep 600
    MAP=$($R "mapname" --wait 1 | sed -n 's/.*"mapname" is:"\([^^"]*\).*/\1/p' | tr 'A-Z' 'a-z')
    if [ "$LAB_MODE" = "train" ]; then
        if [ "$TRAIN_AGGREGATOR" = "1" ]; then
            LAB_MAP=${MAP:-bloodrun} python3 /tools/train_aggregate.py > $D/aggregate_last.txt 2>&1
        fi
        S=/tmp/train/shared
        [ -f "$S/nav_$MAP.json" ] && cp "$S/nav_$MAP.json" "$D/nav_$MAP.json" && $R "qlx !ir nav" --wait 1 >/dev/null
        [ -f "$S/weapon_policy.json" ] && cp "$S/weapon_policy.json" "$D/weapon_policy.json" && $R "qlx !ir policy" --wait 1 >/dev/null
        echo "$(date -u) pulled shared knowledge" >> $D/learner.log
    else
        POLICY_OUT=$D/weapon_policy.json python3 /tools/learn_weapons.py $D/trace_live*.txt > $D/learner_last.txt 2>&1 \
            && $R "qlx !ir policy" --wait 1 >/dev/null
        if [ -n "$MAP" ] && [ -f "$D/trace_live_$MAP.txt" ]; then
            BASE=/ql/maps-data/$MAP/walk_trace.txt
            [ -f "$BASE" ] || BASE=""
            python3 /tools/navgraph.py $BASE $D/trace_live_$MAP.txt $D/nav_$MAP.json.new >> $D/learner_last.txt 2>&1 \
                && mv $D/nav_$MAP.json.new $D/nav_$MAP.json \
                && $R "qlx !ir nav" --wait 1 >/dev/null
        fi
        echo "$(date -u) map=$MAP $(grep -h 'situations learned\|nodes' $D/learner_last.txt | tr '\n' ' ')" >> $D/learner.log
    fi
    # housekeeping: rotate anything over 200 MB, keep 3 old copies
    for f in $D/itemrun_frames.jsonl $D/server.log $D/trace_live_*.txt $D/experience.jsonl; do
        [ -f "$f" ] || continue
        if [ "$(stat -c %s "$f")" -gt 209715200 ]; then
            for i in 2 1; do [ -f "$f.$i.gz" ] && mv "$f.$i.gz" "$f.$((i+1)).gz"; done
            gzip -c "$f" > "$f.1.gz" && : > "$f"
        fi
    done
done
