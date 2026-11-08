"""1.7c's train.cmd (owner, 2026-11-07 evening: "ok let's do it then. start it when it's ready, 12 hrs is fine, or you can run it until noon
tomorrow"; docs/runs/1.7/1.7c/TRAIN_UNDER_TABLE.md, CARD.md): 1.7a's command, every setting as 1.7a ran, with --run duel_gru_1_7c, the
length (--minutes as given), and:
  --keep-g 0.975              the keep choice at the share 1.7a's update 90 played (its ramp's value there; live KEEP_G the same)
  --keep-freeze 1             ... and it learns nothing (it drifted into flicker in 1.7a after update 130 and in 1.7b)
  --wrule 0 --wrule-imit 0.1  the pros' weapon table chooses the weapon of every network seat (live WRULE_P 0 -> 1 over updates 0 to 20:
                              ramp_17c.py); the weapon key's policy gradient and entropy off on those frames; the key copies the table
                              (cross-entropy 0.1, the key's own layer, standing)
  --habit-p 0                 the habit seats off (the table replaces them)
  --head2-wpg 0               the head's weapon credit off (the key is not his while the table chooses)
The order stays shut as at update 90 (--cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0; live CMB_G 0, PADD 0, ORD_GATE -30, FADD 0, H2_FPG 0). The
pay as update 90 (live.json from the save's own live values: ITEM_FLAT MH:0.35,RA:0.30,YA:0.15, WIN_ADD 0.33, DMG_TAKEN_W 0.8, no firing
cost). The start network is 1.7a's update 90 as it is (keep/policy_end_17a.pt) with its optimizer: no conversion. The trainer on the 8
performance cores (0xC03C3), as 1.7a.
    python docs/runs/1.7/1.7c/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "1.7a")
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
OLD = "--keep-g 0 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0.3 --pass-warm 0"
NEW = "--keep-g 0.975 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0.3 --pass-warm 0 --wrule 0 --wrule-imit 0.1 --keep-freeze 1"


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


MIN = sys.argv[1]
assert int(MIN) > 0
lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
assert c.count(OLD) == 1 and len(re.findall(r"--minutes \d+ --gamma ", c)) == 1
assert c.count("--habit-p 0.3 ") == 1 and c.count("--head2-wpg 1 ") == 1
c = c.replace(OLD, NEW).replace("--habit-p 0.3 ", "--habit-p 0 ").replace("--head2-wpg 1 ", "--head2-wpg 0 ")
c = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), c)
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_1_7a", "duel_gru_1_7c") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\1.7\\1.7a\\",
    "rem ==== 1.7c (owner, 2026-11-07 evening: \"ok let's do it then. start it when it's ready\"; docs/runs/1.7/1.7c/TRAIN_UNDER_TABLE.md): the pros' "
    "weapon table chooses the weapon of every network seat (sim/weapon_dial.py choose(), as !weapons pros and the checks' --wpush-form replace); "
    "the weapon key's policy gradient and entropy off there, the key copying the table; the keep choice at update 90's share and frozen; the "
    "order shut; the habit seats off; the pay as update 90. From 1.7a's update 90 as it is with its optimizer. 1.7a's command with: run "
    "duel_gru_1_7c; --minutes (the owner's length); " + NEW + " (live WRULE_P 0 -> 1 over updates 0 to 20: ramp_17c.py); --habit-p 0; "
    "--head2-wpg 0. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\1.7\\1.7c\\")
t = t.replace("docs\\runs\\1.7\\1.7a\\", "docs\\runs\\1.7\\1.7c\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --gamma ".format(MIN) in cl_[0]
assert "--pfsp" not in cl_[0] and "--opt-cold-ok" not in cl_[0] and "--max-updates" not in cl_[0]
assert NEW + " " in cl_[0] and "--run duel_gru_1_7c " in cl_[0] and "--habit-p 0 " in cl_[0] and "--head2-wpg 0 " in cl_[0]
assert "--head2-l2 0.01" in cl_[0] and "--track 0.3 " in cl_[0] and "--dmg-reward 0.0055 " in cl_[0]
for s_ in ("SHOT_COST=0", "BLIND_FIRE_W=0", "BLIND_RL_DMG=0", "WEAPON_OWN=1", "INTENT_SWITCH=0", "COMBAT=1", "BRAIN_READ=1", "ITEM_BELIEF=1"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
assert "1.7a" not in "\n".join(x for x in t.split("\n") if not x.startswith("rem"))
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
