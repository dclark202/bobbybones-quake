"""1.8a's train.cmd (owner, 2026-11-11: "the fast track aim3 in at b1.2d ... Call this model 1.8"; docs/runs/1.8/1.8a/CARD.md): 2.0c's
command (= 1.7a's with AIM3's seven set lines and --gate-open 0), every setting as it ran, with:
  --run duel_gru_1_8a, --minutes as given
  set COMBAT=0             the combat order's simulator side off: 1.8a's network has no order (the hands' ten order inputs read zeros)
  --keep-g 0               the keep choice's share at the start (live KEEP_G: the ramp opens it over updates 210 to 250)
  --head2-wpg 0            no head part on the weapon key (1.5a's, scrapped)
  --pass-odds 0            no pass readout (it belonged to 1.7a's order)
  --habit-p 0              no weapon habits on the league's seats (1.5a's, scrapped)
  phase 1 (updates 0 to 150):   set INTENT_SWITCH=0.02, set WEAPON_OWN=0   (b1.2d's and 1.3b's: the switch cost, a held weapon no target)
  phase 2 (from the restart):   set INTENT_SWITCH=0,    set WEAPON_OWN=1   (1.4b's, as 1.7a's command)
Everything that moves is live (live.json, ramp_18a.py): AIM3_W, AIM3_SIZE_A, AIM3_SIZE_B, H2_PG, INTENT_TEACH_W, SPEED_PAY, KEEP_G; fixed
from the start in live.json: DMG_REWARD 0.005 and DMG_TAKEN_W 1.0 (owner, 11-11: zero-sum from the start), WIN_ADD 0.33, the item table, COST_FIRE_W 0.
    python docs/runs/1.8/1.8a/make_files.py <minutes> <phase: 1|2>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "2.0", "2.0c"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN, PHASE = sys.argv[1], int(sys.argv[2])
assert int(MIN) > 0 and PHASE in (1, 2)
SETS = dict(COMBAT="0", INTENT_SWITCH="0.02" if PHASE == 1 else "0", WEAPON_OWN="0" if PHASE == 1 else "1")
ARGS = (("--keep-g", "0.975", "0"), ("--head2-wpg", "1", "0"), ("--pass-odds", "0.3", "0"), ("--habit-p", "0.3", "0"))


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


for n_, v_ in SETS.items():
    assert len(re.findall(r"^set {}=\S*$".format(n_), t, re.M)) == 1, n_
    t = re.sub(r"^set {}=\S*$".format(n_), "set {}={}".format(n_, v_), t, flags=re.M)
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost: as 2.0c's command has them)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
for f_, v0_, v1_ in ARGS:
    assert c.count(" {} {} ".format(f_, v0_)) == 1, f_
    c = c.replace(" {} {} ".format(f_, v0_), " {} {} ".format(f_, v1_))
assert len(re.findall(r"--minutes \d+ --gamma ", c)) == 1
c = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), c)
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_0c", "duel_gru_1_8a") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\2.0\\2.0c\\",
    "rem ==== 1.8a (owner, 2026-11-11: \"the fast track aim3 in at b1.2d ... Call this model 1.8\"; docs/runs/1.8/1.8a/CARD.md), phase {}: from "
    "b1.2d's end widened to 1,053 inputs, the strategy head (1.3b's form) and the keep choice (1.7a's form) added at zero effect. 2.0c's command "
    "with: run duel_gru_1_8a; --minutes; set {}; {}. The dials are live (ramp_18a.py). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\1.8\\1.8a\\".format(
        PHASE, ", ".join("{}={}".format(k_, v_) for k_, v_ in SETS.items()), ", ".join("{} {}".format(f_, v1_) for f_, _, v1_ in ARGS)))
t = t.replace("docs\\runs\\2.0\\2.0c\\", "docs\\runs\\1.8\\1.8a\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --gamma ".format(MIN) in cl_[0]
assert "--pfsp" not in cl_[0] and "--opt-cold-ok" not in cl_[0] and "--max-updates" not in cl_[0] and "--wrule" not in cl_[0] and "--keep-freeze" not in cl_[0]
assert "--space-read" not in cl_[0] and "--gate-open 0 " in cl_[0] and "--run duel_gru_1_8a " in cl_[0]
assert "--keep-g 0 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0 --pass-warm 0 " in cl_[0] and "--habit-p 0 " in cl_[0]
assert "--head2 1 " in cl_[0] and "--head2-add 1 " in cl_[0] and "--head2-chrono-lo 1 " in cl_[0] and "--head2-lam 0.995 " in cl_[0] and "--head2-l2 0.01 " in cl_[0]
assert "--head2-wpg 0 " in cl_[0] and "--dmg-reward 0.0055 " in cl_[0]
live_ = [x for x in t.split("\n") if not x.startswith("rem")]
assert not any("duel_gru_2_0c" in x for x in live_)
tmp = os.path.join(HERE, "train.cmd.tmp")
open(tmp, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
os.replace(tmp, os.path.join(HERE, "train.cmd"))
if not os.path.exists(os.path.join(HERE, "aim2_env.cmd")):
    shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("train.cmd written: phase {}, {} minutes; set {}".format(PHASE, MIN, ", ".join("{}={}".format(k_, v_) for k_, v_ in SETS.items())))
