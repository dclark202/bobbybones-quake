"""1.6a's train.cmd (owner, 2026-11-04 night / 11-05 morning; docs/runs/1.6/1.6a/CARD.md): 1.5a's command, every setting as 1.5a ran,
with --run duel_gru_1_6a, the length (--minutes as given, a cap; --max-updates 80: the run ends at update 80, its save) and SHOT_COST=0
(no cost for firing at all, at its source; owner, 11-04 night). The item teacher (live INTENT_TEACH_W) and the speed pay (live SPEED_PAY)
go out by ramp_16a.py over updates 0 to 40, held at 0 to update 80; no new code. The trainer on the 8 performance cores (0xC03C3), as 1.5a.
    python docs/runs/1.6/1.6a/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "1.5", "1.5a")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_1_5a", "duel_gru_1_6a") for x in t.split("\n"))   # (the history lines stay as written)
assert len(re.findall(r"--minutes \d+ --gamma ", t)) == 1
t = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --max-updates 80 --gamma ".format(MIN), t)
sub(" --head2-wpg 0 --habit-p ", " --head2-wpg 1 --habit-p ")                   # (1.5a ended at live H2_WPG 1: the command says so from the first update)
sub("set SHOT_COST=0.10\n", "rem (1.6a, owner 2026-11-04 night: \"there should be no cost for firing AT ALL\") the shot's price at its source: 0 (it was 0.10 x live COST_FIRE_W 0)\n"
    "set SHOT_COST=0\n")
sub("rem the repo root: this file lives in docs\\runs\\1.5\\1.5a\\",
    "rem ==== 1.6a (owner, 2026-11-05; docs/runs/1.6/1.6a/CARD.md): the item teacher and the speed pay out over updates 0 to 40 (live "
    "INTENT_TEACH_W 1 -> 0, SPEED_PAY 0.125 -> 0, ramp_16a.py), held to update 80, from 1.5a's end with its optimizer. 1.5a's command with: "
    "run duel_gru_1_6a; --minutes (a cap) --max-updates 80; --head2-wpg 1 (1.5a's end value); SHOT_COST=0. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\1.6\\1.6a\\")
t = t.replace("docs\\runs\\1.5\\1.5a\\", "docs\\runs\\1.6\\1.6a\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --max-updates 80 --gamma ".format(MIN) in cl_[0]
assert "--pfsp" not in cl_[0] and "--habit-p 0.3" in cl_[0] and "--head2-l2 0.01" in cl_[0]
for s_ in ("SHOT_COST=0", "BLIND_FIRE_W=0", "BLIND_RL_DMG=0", "WEAPON_OWN=1", "INTENT_SWITCH=0"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
assert "1.5a" not in "\n".join(x for x in t.split("\n") if not x.startswith("rem"))
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
