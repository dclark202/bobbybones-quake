"""1.7a's train.cmd (owner, 2026-11-04 night / 11-05; docs/runs/1.7/1.7a/CARD.md): 1.6a's command, every setting as 1.6a ran, with
--run duel_gru_1_7a, the length (--minutes as given: the owner's; 1.6a's --max-updates 80 out) and --keep-g 0 (the keep choice at share 0
at the start; live KEEP_G opened by ramp_17a.py over updates 10 to 90). The start network is 1.6a's end given the keep choice
(tools/keep_init.py add, at share 0: it plays as 1.6a's end). No cost for firing at all (SHOT_COST=0, as 1.6a). The trainer on the 8
performance cores (0xC03C3), as 1.6a.
    python docs/runs/1.7/1.7a/make_files.py <minutes> [<1.6a's folder>]"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "1.6", "1.6a")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
assert int(MIN) > 0
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_1_6a", "duel_gru_1_7a") for x in t.split("\n"))   # (the history lines stay as written)
assert len(re.findall(r"--minutes \d+ --max-updates 80 --gamma ", t)) == 1
t = re.sub(r"--minutes \d+ --max-updates 80 --gamma ", "--minutes {} --gamma ".format(MIN), t)
sub(" --head2-wpg 1 --habit-p ", " --head2-wpg 1 --keep-g 0 --habit-p ")
sub("rem the repo root: this file lives in docs\\runs\\1.6\\1.6a\\",
    "rem ==== 1.7a (owner, 2026-11-05; docs/runs/1.7/1.7a/CARD.md): the lock overhauled: the keep choice at the head's tick (five a second), "
    "an arrival keepable, from 1.6a's end with its optimizer, given the keep choice at share 0 (tools/keep_init.py add). 1.6a's command with: "
    "run duel_gru_1_7a; --minutes (the owner's length; 1.6a's --max-updates 80 out); --keep-g 0 (live KEEP_G 0 -> 1 over updates 10 to 90, "
    "ramp_17a.py). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\1.7\\1.7a\\")
t = t.replace("docs\\runs\\1.6\\1.6a\\", "docs\\runs\\1.7\\1.7a\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --gamma ".format(MIN) in cl_[0]
assert "--pfsp" not in cl_[0] and "--max-updates" not in cl_[0] and "--opt-cold-ok" not in cl_[0]
assert "--keep-g 0 " in cl_[0] and "--habit-p 0.3" in cl_[0] and "--head2-l2 0.01" in cl_[0] and "--head2-wpg 1 " in cl_[0]
for s_ in ("SHOT_COST=0", "BLIND_FIRE_W=0", "BLIND_RL_DMG=0", "WEAPON_OWN=1", "INTENT_SWITCH=0"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
assert "1.6a" not in "\n".join(x for x in t.split("\n") if not x.startswith("rem"))
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
