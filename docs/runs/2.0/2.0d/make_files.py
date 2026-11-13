"""2.0d's train.cmd (owner, 2026-11-13: "an overnight run to clean up the network by removing dead inputs, and make the structural fixes for
aim/dodging and simulator. That's it"; docs/runs/2.0/2.0d/CARD.md): 2.0c's command (= 1.7a's with AIM3's seven set lines and --gate-open
0), every setting as it ran, with:
  --run duel_gru_2_0d, --minutes as given
  --env duel_env_ffa20d     the input list 20d (item 1: list 18's cut, the order's ten kept, the dodge group; tools/inputs20d.py)
  --brain-fade 0            the brain's fade has nothing left to fade: the rule-made columns are out of the list (as 1.8a)
  --keep-g 1                the keep choice's share to 1 (item 3: the lock's last 2.5% out)
  --pass-odds 0             the brain's pass-odds lesson out (item 2: the combat order's; its order never asked at update 90)
  --habit-p 0               no weapon habits on the league's seats (item 6)
  set AIM3_FIX_TAU=0.05     AIM3's 11-11 tuning from the start (item 7); AIM3_W, AIM3_SIZE_A/B, AIM3_LEAD, AIM3_RELOAD move live (ramp_20d.py)
  set AIM3_LEAD=0, AIM3_RELOAD=1   at their start values (as before to the bit); the ramp moves them to 1 and 0 with AIM3_W
  set KNOCK_QL=1, KNOCK_NOW=1      the corrected knockback (item 4: a switch, not live)
  set DODGE_IN=1, DODGE_G=0        the dodge inputs (item 9): in, at their gate 0 (zeros); the ramp opens DODGE_G over updates 30 to 60
Kept as 1.7a's update 90: COMBAT=1 (the order's ten inputs carry his target's look point: the owner, 11-13, "keep them"), --cmb-g 0 --padd 0
--fadd 0 --head2-fpg 0 (never asked), --head2-wpg 1 (the head's weapon part, learning), --keep-g's choice learning, WIN_ADD 0.33.
Pay (live.json, start_live.py): DMG_REWARD 0.005 and DMG_TAKEN_W 1.0 (zero-sum, a step at the start: item 5), RAIL_FAR_PAY 0.1.
    python docs/runs/2.0/2.0d/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.0c"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN = sys.argv[1]
assert int(MIN) > 0
SETS = dict(AIM3_FIX_TAU="0.05")
NEW_SETS = ("AIM3_LEAD=0", "AIM3_RELOAD=1", "KNOCK_QL=1", "KNOCK_NOW=1", "DODGE_IN=1", "DODGE_G=0")
ARGS = (("--keep-g", "0.975", "1"), ("--pass-odds", "0.3", "0"), ("--habit-p", "0.3", "0"), ("--env", "duel_env_ffa", "duel_env_ffa20d"),
        ("--brain-fade", "1", "0"))


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


for n_, v_ in SETS.items():
    assert len(re.findall(r"^set {}=\S*$".format(n_), t, re.M)) == 1, n_
    t = re.sub(r"^set {}=\S*$".format(n_), "set {}={}".format(n_, v_), t, flags=re.M)
for x_ in NEW_SETS:
    assert not re.search(r"^set {}=".format(x_.split("=")[0]), t, re.M), x_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost: as 2.0c's command has them)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
sub("set AIM3_FIX_TAU=0.05\n", "set AIM3_FIX_TAU=0.05\n" + "".join("set {}\n".format(x_) for x_ in NEW_SETS))
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
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_0c", "duel_gru_2_0d") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\2.0\\2.0c\\",
    "rem ==== 2.0d (owner, 2026-11-13: \"an overnight run to clean up the network by removing dead inputs, and make the structural fixes for "
    "aim/dodging and simulator. That's it\"; docs/runs/2.0/2.0d/CARD.md): from 1.7a's update 90 brought to the input list 20d "
    "(tools/inputs20d.py). 2.0c's command with: run duel_gru_2_0d; --minutes; set {}; set {}; {}. The dials are live (ramp_20d.py). "
    "Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.0\\2.0d\\".format(
        ", ".join("{}={}".format(k_, v_) for k_, v_ in SETS.items()), ", ".join(NEW_SETS), ", ".join("{} {}".format(f_, v1_) for f_, _, v1_ in ARGS)))
t = t.replace("docs\\runs\\2.0\\2.0c\\", "docs\\runs\\2.0\\2.0d\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --gamma ".format(MIN) in cl_[0]
assert "--pfsp" not in cl_[0] and "--opt-cold-ok" not in cl_[0] and "--max-updates" not in cl_[0] and "--wrule" not in cl_[0] and "--keep-freeze" not in cl_[0]
assert "--space-read" not in cl_[0] and "--gate-open 0 " in cl_[0] and "--run duel_gru_2_0d " in cl_[0]
assert "--keep-g 1 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0 --pass-warm 0 " in cl_[0] and "--habit-p 0 " in cl_[0]
assert "--head2 1 " in cl_[0] and "--head2-add 1 " in cl_[0] and "--head2-wpg 1 " in cl_[0] and "--head2-l2 0.01" in cl_[0]
assert "--env duel_env_ffa20d " in cl_[0] and "--brain-fade 0 " in cl_[0] and "--opt-small-items 1 " in cl_[0] and "--dmg-reward 0.0055 " in cl_[0]
for s_ in ("COMBAT=1", "WEAPON_OWN=1", "INTENT_SWITCH=0", "AIM3=1", "AIM3_W=0", "AIM3_SIZE_A=1", "AIM3_SIZE_B=0", "AIM3_PURSUIT_TAU=0.125",
           "AIM3_PURSUIT_GAIN=1.0", "AIM3_FIX_TAU=0.05") + NEW_SETS:
    assert t.count("\nset {}\n".format(s_)) == 1, s_
for s_ in ("SPACE_IN", "SPACE_TRUTH", "EDGE_PAY", "COVER_PAY", "SPACE_GATE", "INSTR"):          # nothing of 2.0b or 2.1
    assert not re.search(r"^set {}=".format(s_), t, re.M), s_
live_ = "\n".join(x for x in t.split("\n") if not x.startswith("rem"))
assert "2_0c" not in live_ and "2.0c" not in live_
tmp = os.path.join(HERE, "train.cmd.tmp")
open(tmp, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
os.replace(tmp, os.path.join(HERE, "train.cmd"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("train.cmd written: {} minutes; set {}; {}".format(MIN, ", ".join(NEW_SETS), ", ".join("{} {}".format(f_, v1_) for f_, _, v1_ in ARGS)))
