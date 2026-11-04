"""1.4c's train.cmd (owner, 2026-11-04; docs/runs/b1.4/1.4c/CARD.md): 1.4b's command with --run duel_gru_1_4c; --minutes as given; the checks'
opponent at the even share now 1.4b's end (--pfsp-fixed anchor_14b.pt; live PFSP carried from 1.4b's live.json); the blind-fire cost out from
the start (BLIND_FIRE_W=0); the keep choice at share 0 at the start (--keep-g 0; live KEEP_G opened by ramp_14c.py). The start network is 1.4b's
end given the keep choice (tools/keep_init.py add). The trainer on the 8 performance cores (0xC03C3), as 1.4b.
    python docs/runs/b1.4/1.4c/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "1.4b")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
t = t.replace("duel_gru_1_4b", "duel_gru_1_4c")
assert len(re.findall(r"--minutes \d+ --gamma ", t)) == 1
t = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), t)
sub(" --pfsp 0 --pfsp-fixed anchor_13b.pt %LEARN% >> ", " --pfsp 0 --pfsp-fixed anchor_14b.pt --keep-g 0 %LEARN% >> ")
sub("set INTENT_SWITCH=0\n", "set INTENT_SWITCH=0\nrem (1.4c, owner 2026-11-04: \"make sure its out in 1.4c\") no blind-fire cost\nset BLIND_FIRE_W=0\n")
sub("rem the repo root: this file lives in docs\\runs\\b1.4\\1.4b\\",
    "rem ==== 1.4c (owner, 2026-11-04; docs/runs/b1.4/1.4c/CARD.md): the target lock out, by a learned choice to keep or re-decide. "
    "1.4b's command with: run duel_gru_1_4c; --minutes; --pfsp-fixed anchor_14b.pt; --keep-g 0 (live KEEP_G, ramp_14c.py); BLIND_FIRE_W=0. "
    "Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.4\\1.4c\\")
assert "/affinity C03C3 " in t and "--minutes {} --gamma ".format(MIN) in t
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
