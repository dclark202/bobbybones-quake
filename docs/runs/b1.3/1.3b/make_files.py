"""1.3b's train.cmd (owner, 2026-11-03: "start with the builds"; docs/runs/b1.3/1.3b/CARD.md): b1.2d's command with --run duel_gru_1_3b; --minutes as given;
the strategy head in with its own target scores added to the hands' (--head2-add 1: one set of target logits, the hands' rows plus the head's target(s),
the head's part at zero at the start), its gate shut (no plan into the hands), its memory speeds spread (--head2-chrono-lo 1), its own advantage at lambda
0.995 (--head2-lam); the target's credit moved from his own advantage to the head's by live H2_PG (0 at the start: as b1.2d; the ramp's 0 -> 1 over
updates 10 to 90; owner 11-03: 80 updates). An L2 on both parts of his target scores (--head2-l2 0.01: decoupled weight decay, AdamW's L2, on both target layers, live H2_L2; owner 11-03: one weight for both; no cap: "Just use L2").
No copy lesson. The trainer on the 8 performance cores (0xC03C3), as b1.2d.
    python docs/runs/b1.3/1.3b/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "b1.2", "b1.2d")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
t = t.replace("duel_gru_b1_2d", "duel_gru_1_3b")
assert len(re.findall(r"--minutes \d+ --gamma ", t)) == 1
t = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), t)
sub(" %LEARN% >> ", " --head2 1 --head2-ctrl-src belief --head2-open 0 --head2-cap 0 --head2-gate 0 --head2-start %H2_START% --head2-pay all --head2-pg 1"
                    " --head2-add 1 --head2-chrono-lo 1 --head2-lam 0.995 --head2-l2 0.01 %LEARN% >> ")
sub('if "%RF_START%"=="" set RF_START=18411.038983547685', 'if "%H2_START%"=="" set H2_START=-1\nif "%RF_START%"=="" set RF_START=18411.038983547685')
sub("rem the repo root: this file lives in docs\\runs\\b1.2\\b1.2d\\",
    "rem ==== 1.3b (owner, 2026-11-03; docs/runs/b1.3/1.3b/CARD.md): his target choice gets the strategy head's slow memory: the head's own scores added to the hands' "
    "(target at zero at the start), the credit moved to the head's advantage by live H2_PG. b1.2d's command with: run duel_gru_1_3b; --minutes; the head's arguments "
    "with --head2-add 1 --head2-chrono-lo 1 --head2-lam 0.995 --head2-l2 0.01 (live H2_L2, decoupled weight decay). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.3\\1.3b\\")
assert "/affinity C03C3 " in t and "--minutes {} --gamma ".format(MIN) in t
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
