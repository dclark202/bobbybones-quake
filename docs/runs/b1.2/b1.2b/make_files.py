"""b1.2b's train.cmd (owner, 2026-11-01), from b1.1a's (no head): --run duel_gru_b1_2b; --minutes MIN; the health and armor pay per point. The costs' dials are live, in live.json (start.ps1), moved by ramp_b12b.py.
    python docs/runs/b1.2/b1.2b/make_files.py [minutes]"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(HERE, "..", "..", "b1.1", "b1.1a", "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1] if len(sys.argv) > 1 else "1150"
t = t.replace("duel_gru_b1_1a", "duel_gru_b1_2b")
sub("--minutes 885 --gamma", "--minutes {} --gamma".format(MIN))
sub("set GONE_BELIEF=1\n", "set GONE_BELIEF=1\nrem (b1.2b) every health and armor point gained pays, bubbles and shards too, zero-sum, in ITEM_FLAT's place on them\nset ITEM_RATE_HP=0.0025\nset ITEM_RATE_AR=0.002\n")
sub("rem the repo root: this file lives in docs\\runs\\b1.1\\b1.1a\\",
    "rem ==== b1.2b (owner, 2026-11-01; docs/runs/b1.2/b1.2b/CARD.md): from b1.1, no head: the health and armor table at once; the firing costs, contact freedom, the jerk cost, by live dials (ramp_b12b.py). b1.1a's command with: run duel_gru_b1_2b;\n"
    "rem  --minutes; ITEM_RATE_HP, ITEM_RATE_AR. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.2\\b1.2b\\")
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(HERE, "..", "..", "b1.1", "b1.1a", "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
