"""b1.2d's train.cmd (owner, 2026-11-02; CARD.md), from b1.2c's: --run duel_gru_b1_2d; --minutes as given; the table by the point (ITEM_PT_LO 0.004, ITEM_PT_HI 0.002, ITEM_DECAY 0.002: it takes ITEM_RATE's place); SM_PASS (a counter). The speed pay and the long rail move by ramp_b12d.py's steps, from live.json.
    python docs/runs/b1.2/b1.2d/make_files.py <minutes>"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(HERE, "..", "b1.2c", "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
t = t.replace("duel_gru_b1_2c", "duel_gru_b1_2d")
sub("--resume --minutes ", "--resume --minutes {} --gamma_".format(MIN))
t = t.replace(" --gamma_" + t.split(" --gamma_")[1].split(" --gamma ")[0] + " --gamma ", " --gamma ")
sub("set SM_ITEMS=1\n", "set SM_ITEMS=1\n"
    "rem (b1.2d) the table by the point: up to 100 0.004 a point, above it 0.002, the decay above 100 charged back at 0.002 (in ITEM_RATE's place); the small places near his way counted\n"
    "set ITEM_PT_LO=0.004\nset ITEM_PT_HI=0.002\nset ITEM_DECAY=0.002\nset SM_PASS=1\n")
sub("rem the repo root: this file lives in docs\\runs\\b1.2\\b1.2c\\",
    "rem ==== b1.2d (owner, 2026-11-02; docs/runs/b1.2/b1.2d/CARD.md): from b1.2c's end, the pay table by the point (the line at 100, the decay charged back), then the speed pay down, then the long rail up (ramp_b12d.py). b1.2c's command with: run duel_gru_b1_2d; --minutes; ITEM_PT_LO, ITEM_PT_HI, ITEM_DECAY, SM_PASS. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.2\\b1.2d\\")
assert "--minutes {} --gamma ".format(MIN) in t
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(HERE, "..", "b1.2c", "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
