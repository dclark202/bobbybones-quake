#!/bin/bash
# First-start nudge; the lab plugin keeps everything (map, warmup, bot, item run, recording) in shape after that.
sleep 12
python3 /tools/rcon.py "qlx !record on" --wait 2
echo "bootstrap done $(date -u)" >> /tmp/practice/bootstrap.log
