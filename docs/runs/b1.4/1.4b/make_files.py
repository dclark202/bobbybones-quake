"""1.4b's train.cmd (owner, 2026-11-03; docs/runs/b1.4/1.4b/CARD.md): 1.3b's command with --run duel_gru_1_4b; --minutes as given; matchmaking by
difficulty (--pfsp 0: the dial shut at the start, live PFSP opened by ramp_14b.py; the checks' opponent, 1.3b's end as anchor_13b.pt, at the even
share: --pfsp-fixed); the switch cost out from the start (INTENT_SWITCH=0); a weapon he holds may be chosen (WEAPON_OWN=1, beside WEAPON_FREE=1).
The item rule's lesson and the speed pay go out by live dials (ramp_14b.py). The trainer on the 8 performance cores (0xC03C3), as 1.3b.
    python docs/runs/b1.4/1.4b/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "b1.3", "1.3b")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
t = t.replace("duel_gru_1_3b", "duel_gru_1_4b")
assert len(re.findall(r"--minutes \d+ --gamma ", t)) == 1
t = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), t)
sub(" %LEARN% >> ", " --pfsp 0 --pfsp-fixed anchor_13b.pt %LEARN% >> ")
sub("set WEAPON_FREE=1\n", "set WEAPON_FREE=1\nrem (1.4b, owner 2026-11-03) a weapon he holds may be chosen; taking the one he chose still ends the choice\nset WEAPON_OWN=1\n"
    "rem (1.4b, owner 2026-11-03: the switch cost \"can just go\") no cost for a change of target\nset INTENT_SWITCH=0\n")
sub("rem the repo root: this file lives in docs\\runs\\b1.3\\1.3b\\",
    "rem ==== 1.4b (owner, 2026-11-03; docs/runs/b1.4/1.4b/CARD.md): the hand-written pieces on his target choice out, with matchmaking by difficulty. "
    "1.3b's command with: run duel_gru_1_4b; --minutes; --pfsp 0 --pfsp-fixed anchor_13b.pt (live PFSP); WEAPON_OWN=1; INTENT_SWITCH=0. "
    "The item rule's lesson and the speed pay by live dials (ramp_14b.py). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.4\\1.4b\\")
assert "/affinity C03C3 " in t and "--minutes {} --gamma ".format(MIN) in t
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
