"""2.0a's train.cmd (owner, 2026-11-08: "If you think you have something to try tonight try it. I want the report after it's done at 7";
docs/runs/2.0/2.0a/CARD.md, docs/design/PLAN_2.md): 1.7a's command, every setting as 1.7a ran, with --run duel_gru_2_0a, the length (--minutes as
given: what is left of the 21:00 to 07:00 window), and:
  --keep-g 0.975              the keep choice at the share 1.7a's update 90 played (live KEEP_G the same), LEARNING (not frozen: the pay change is
                              what should reshape when he keeps a fight and when he leaves; its drift is flagged by the ramp)
Nothing else changes in the command: the one new thing is in live.json and the ramp (ramp_20a.py): DMG_REWARD 0.0055 -> 0.001 (the damage pay
down to a floor), DMG_TAKEN_W 0.8 -> 1.0 (the floor zero-sum), WIN_ADD 0.33 -> 0.6 (the judge's weight up), straight lines over updates 10 to
70. The order stays shut as at update 90 (--cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0; live CMB_G 0, PADD 0, ORD_GATE -30, FADD 0, H2_FPG 0); the
habit seats (--habit-p 0.3) and the head's weapon credit (--head2-wpg 1) as 1.7a; no table (--wrule absent). The judge is v0.6.0's fit
(WIN_JUDGE judge_v060_wpn.npz, as 1.7a). The start network is 1.7a's update 90 widened to today's 994 inputs (start.ps1) with its optimizer.
The trainer on the 8 performance cores (0xC03C3), as 1.7a.
    python docs/runs/2.0/2.0a/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "1.7", "1.7a"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
OLD = "--keep-g 0 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0.3 --pass-warm 0"
NEW = "--keep-g 0.975 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0.3 --pass-warm 0"


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
c = c.replace(OLD, NEW)
c = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), c)
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_1_7a", "duel_gru_2_0a") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\1.7\\1.7a\\",
    "rem ==== 2.0a (owner, 2026-11-08: \"If you think you have something to try tonight try it\"; docs/runs/2.0/2.0a/CARD.md): the damage pay "
    "down to a floor and the judge's weight up, live, faded over updates 10 to 70 by ramp_20a.py (DMG_REWARD 0.0055 -> 0.001, DMG_TAKEN_W "
    "0.8 -> 1.0, WIN_ADD 0.33 -> 0.6); the keep choice at update 90's share and learning; the order shut; everything else as 1.7a. From 1.7a's "
    "update 90 widened to 994 inputs with its optimizer. 1.7a's command with: run duel_gru_2_0a; --minutes (what is left of the 21:00 to 07:00 "
    "window); " + NEW + ". Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.0\\2.0a\\")
t = t.replace("docs\\runs\\1.7\\1.7a\\", "docs\\runs\\2.0\\2.0a\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --gamma ".format(MIN) in cl_[0]
assert "--pfsp" not in cl_[0] and "--opt-cold-ok" not in cl_[0] and "--max-updates" not in cl_[0] and "--wrule" not in cl_[0] and "--keep-freeze" not in cl_[0]
assert NEW + " " in cl_[0] and "--run duel_gru_2_0a " in cl_[0] and "--habit-p 0.3 " in cl_[0] and "--head2-wpg 1 " in cl_[0]
assert "--head2-l2 0.01" in cl_[0] and "--track 0.3 " in cl_[0] and "--dmg-reward 0.0055 " in cl_[0] and "--dmg-taken-w 1.0 " in cl_[0]
assert "--opt-small-items 1 " in cl_[0] and "--gamma 0.999 " in cl_[0]
for s_ in ("SHOT_COST=0", "BLIND_FIRE_W=0", "BLIND_RL_DMG=0", "WEAPON_OWN=1", "INTENT_SWITCH=0", "COMBAT=1", "BRAIN_READ=1", "ITEM_BELIEF=1",
           "WIN_JUDGE=%ROOT%\\data\\sim_runs\\judge\\judge_v060_wpn.npz", "WIN_SHADOW=1", "WIN_END=1", "PAY_SPLIT=1", "DMG_ENEMY_ONLY=1"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
assert "1.7a" not in "\n".join(x for x in t.split("\n") if not x.startswith("rem"))
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
