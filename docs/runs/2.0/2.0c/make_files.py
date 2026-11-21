"""2.0c's train.cmd (owner, 2026-11-10 night: "Just start it when you have it, it can run until 9am tomorrow. Both changes at the same time
ramp from u0 to u40"; docs/runs/2.0/2.0c/CARD.md): 2.0a's command (= 1.7a's with --keep-g 0.975), every setting as it ran, with --run
duel_gru_2_0c, the length (--minutes as given), and:
  --gate-open 0               the attention gates are left as the start file has them: the three tokens 1.7a's update 90 never had (1.7b's
                              timers, 2.0b's space and targets: inputs today's simulator carries, zero weights) stay shut the whole run. 2.0a's
                              command (--gate-open 120 from a minute long past) would open all three at once
  set AIM3=1                  the aim model's switch (docs/design/AIM3.md); with the start values below it is AIM2 to the bit
  set AIM3_W=0                the blend from AIM2's slip and eccentricity (against his crosshair) to AIM3's (against his eye): live, ramp 0 -> 1
  set AIM3_SIZE_A=1           the base sight error by how big the enemy looks: PERCEPT_SIGMA x (A + B x his half width in degrees); live,
  set AIM3_SIZE_B=0           ramp 1, 0 (the fixed angle) -> 0.39, 0.355 (the pros' line, the same 0.9 degrees at 500 units)
  set AIM3_PURSUIT_TAU=0.125  the eye's lag (seconds), its gain, the fixation time: fixed (the default column of AIM3.md section 4)
  set AIM3_PURSUIT_GAIN=1.0
  set AIM3_FIX_TAU=0.10
Nothing else changes in the command. The pay change is in live.json and the ramp (ramp_20c.py): DMG_REWARD 0.0055 -> 0.002, DMG_TAKEN_W
0.8 -> 1.0 (zero-sum), with the aim's three dials, straight lines over updates 0 to 40. WIN_ADD stays 0.33. The start network is 1.7a's
update 90 widened to today's 1,053 inputs (start.ps1) with its optimizer.
    python docs/runs/2.0/2.0c/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.0a"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
SETS = ("AIM3=1", "AIM3_W=0", "AIM3_SIZE_A=1", "AIM3_SIZE_B=0", "AIM3_PURSUIT_TAU=0.125", "AIM3_PURSUIT_GAIN=1.0", "AIM3_FIX_TAU=0.10")


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
assert len(re.findall(r"--minutes \d+ --gamma ", c)) == 1 and c.count("--gate-open 120 ") == 1 and "--gate-from -12 " in c
c = c.replace("--gate-open 120 ", "--gate-open 0 ")
c = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(MIN), c)
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_0a", "duel_gru_2_0c") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\2.0\\2.0a\\",
    "rem ==== 2.0c (owner, 2026-11-10 night: \"Just start it when you have it, it can run until 9am tomorrow. Both changes at the same time "
    "ramp from u0 to u40\"; docs/runs/2.0/2.0c/CARD.md): the aim model AIM3 (docs/design/AIM3.md) and the damage pay 0.002 zero-sum, live, "
    "straight lines over updates 0 to 40 by ramp_20c.py (AIM3_W 0 -> 1, AIM3_SIZE_A 1 -> 0.39, AIM3_SIZE_B 0 -> 0.355, DMG_REWARD 0.0055 -> "
    "0.002, DMG_TAKEN_W 0.8 -> 1.0); WIN_ADD stays 0.33; everything else as 1.7a's update 90 played. From 1.7a's update 90 widened to 1,053 "
    "inputs with its optimizer. 2.0a's command with: run duel_gru_2_0c; --minutes; --gate-open 0; set " + ", ".join(SETS) + ". Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.0\\2.0c\\")
sub("\ncall %~dp0aim2_env.cmd\n", "\ncall %~dp0aim2_env.cmd\n" + "".join("set {}\n".format(s_) for s_ in SETS))
t = t.replace("docs\\runs\\2.0\\2.0a\\", "docs\\runs\\2.0\\2.0c\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --gamma ".format(MIN) in cl_[0]
assert "--pfsp" not in cl_[0] and "--opt-cold-ok" not in cl_[0] and "--max-updates" not in cl_[0] and "--wrule" not in cl_[0] and "--keep-freeze" not in cl_[0]
assert "--space-read" not in cl_[0] and "--gate-open 0 " in cl_[0]
assert "--keep-g 0.975 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0.3 --pass-warm 0 " in cl_[0]
assert "--run duel_gru_2_0c " in cl_[0] and "--habit-p 0.3 " in cl_[0] and "--head2-wpg 1 " in cl_[0]
assert "--head2-l2 0.01" in cl_[0] and "--track 0.3 " in cl_[0] and "--dmg-reward 0.0055 " in cl_[0] and "--dmg-taken-w 1.0 " in cl_[0]
assert "--opt-small-items 1 " in cl_[0] and "--gamma 0.999 " in cl_[0] and "--react-ms 125 " in cl_[0] and "--acquire-ms 225 " in cl_[0]
for s_ in ("SHOT_COST=0", "BLIND_FIRE_W=0", "BLIND_RL_DMG=0", "WEAPON_OWN=1", "INTENT_SWITCH=0", "COMBAT=1", "BRAIN_READ=1", "ITEM_BELIEF=1",
           "WIN_JUDGE=%ROOT%\\data\\sim_runs\\judge\\judge_v060_wpn.npz", "WIN_SHADOW=1", "WIN_END=1", "PAY_SPLIT=1", "DMG_ENEMY_ONLY=1") + SETS:
    assert t.count("\nset {}\n".format(s_)) == 1, s_
for s_ in ("SPACE_IN", "SPACE_TRUTH", "EDGE_PAY", "COVER_PAY", "SPACE_GATE"):          # nothing of 2.0b
    assert not re.search(r"^set {}=".format(s_), t, re.M), s_
live_ = "\n".join(x for x in t.split("\n") if not x.startswith("rem"))
assert "2_0a" not in live_ and "2.0a" not in live_
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
