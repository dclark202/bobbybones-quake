#!/bin/bash
# Continuous learning: every 10 minutes, re-learn BobbyBones' weapon table from all recorded play
# and hot-swap it into the running bot.
while true; do
    sleep 600
    POLICY_OUT=/tmp/practice/weapon_policy.json python3 /tools/learn_weapons.py /tmp/practice/trace_live*.txt \
        > /tmp/practice/learner_last.txt 2>&1 \
        && python3 /tools/rcon.py "qlx !ir policy" --wait 1 >/dev/null \
        && echo "$(date -u) relearned: $(tail -1 /tmp/practice/learner_last.txt)" >> /tmp/practice/learner.log
done
