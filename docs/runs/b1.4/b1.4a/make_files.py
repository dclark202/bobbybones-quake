"""b1.4a's train.cmd (owner, 2026-11-02 evening: "B1.4 - fade OLD rules out"; CARD.md): b1.3a's command (rule 3: the run it starts
from) with --run duel_gru_b1_4a; --minutes as given; the head learns from his whole pay (--head2-pg 1) as the only learner of his target
(--head2-sole 1: the hands' target outputs frozen), the mix from 0 (--head2-mix 0; live H2_MIX, ramp_b14a.py). The copy lesson stays
(--head2-copy 1, live H2_COPY fades it). The trainer on the 8 performance cores (0xC03C3), as b1.3a.
    python docs/runs/b1.4/b1.4a/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "b1.3", "b1.3a")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
t = t.replace("duel_gru_b1_3a", "duel_gru_b1_4a")
assert len(re.findall(r"--minutes \d+ --gamma ", t)) == 1
t = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), t)
sub(" --head2-pay all --head2-pg 0 --head2-copy 1 %LEARN% >> ", " --head2-pay all --head2-pg 1 --head2-copy 1 --head2-mix 0 --head2-sole 1 %LEARN% >> ")
sub("rem the repo root: this file lives in docs\\runs\\b1.3\\b1.3a\\",
    "rem ==== b1.4a (owner, 2026-11-02 evening; docs/runs/b1.4/b1.4a/CARD.md): the old rules fade out: his target choice moves from the hands' to the head's (live H2_MIX), the head learns from his whole pay as the only learner of it, the copy lesson fades (H2_COPY), the target lock (INTENT_HOLD) and the way pay (INTENT_SEEK_W) out: ramp_b14a.py. b1.3a's command with: run duel_gru_b1_4a; --minutes; --head2-pg 1, --head2-mix 0, --head2-sole 1. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.4\\b1.4a\\")
assert "/affinity C03C3 " in t and "--minutes {} --gamma ".format(MIN) in t
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
