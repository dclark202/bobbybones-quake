"""2.0e's train.cmd (owner, 2026-11-14: "start from 1.6a; include aim3 config, and other changes (damage pay, zero sum, dodge inputs) from
2.0d"; "The dead inputs must come out too"; "80 updates, rail at 0.1 ..., weapons habits ... should be dropped entirely";
docs/runs/2.0/2.0e/CARD.md): 2.0d's command, every setting as it ran, less what only 1.7a's network has, with:
  --run duel_gru_2_0e, --minutes as given, --max-updates 80
  --env duel_env_ffa20e     the input list 20e (list 18's cut and the dodge group; no order inputs: 1.6a has no combat order)
  out: --keep-g --cmb-g --padd --fadd --head2-fpg --pass-odds --pass-warm (the keep choice, the order, the fire push, the pass odds: 1.6a
       has none; the 8-second lock plays, as in 1.6a), set COMBAT=1
Kept from 2.0d: AIM3's set lines, KNOCK_QL=1, KNOCK_NOW=1, DODGE_IN=1, DODGE_G=0, --habit-p 0, --brain-fade 0, --gate-open 0.
The pay and the dials are live (start_live.py, ramp_20e.py).
    python docs/runs/2.0/2.0e/make_files.py <minutes>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.0d"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN = sys.argv[1]
assert int(MIN) > 0
UPDATES = 80
OUT_ARGS = " --keep-g 1 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0 --pass-warm 0 "


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


sub("\nset COMBAT=1\n", "\n")
lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
assert c.count(OUT_ARGS) == 1
c = c.replace(OUT_ARGS, " ")
assert c.count(" --env duel_env_ffa20d ") == 1
c = c.replace(" --env duel_env_ffa20d ", " --env duel_env_ffa20e ")
assert len(re.findall(r"--minutes \d+ --gamma ", c)) == 1 and "--max-updates" not in c
c = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES), c)
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_0d", "duel_gru_2_0e") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\2.0\\2.0d\\",
    "rem ==== 2.0e (owner, 2026-11-14: 2.0d's clean-up from 1.6a's end; docs/runs/2.0/2.0e/CARD.md): from 1.6a's end brought to the input "
    "list 20e (tools/inputs20d.py --list 20e). 2.0d's command with: run duel_gru_2_0e; --minutes; --max-updates {}; --env duel_env_ffa20e; "
    "out: COMBAT, --keep-g --cmb-g --padd --fadd --head2-fpg --pass-odds --pass-warm (1.6a has the lock, no keep choice, no order). "
    "The dials are live (ramp_20e.py). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.0\\2.0e\\".format(UPDATES))
t = t.replace("docs\\runs\\2.0\\2.0d\\", "docs\\runs\\2.0\\2.0e\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES) in cl_[0]
for x_ in ("--pfsp", "--opt-cold-ok", "--wrule", "--keep-freeze", "--keep-g", "--cmb-g", "--padd", "--fadd", "--head2-fpg", "--pass-odds",
           "--space-read", "--ins", "--branch"):
    assert x_ + " " not in cl_[0], x_
assert "--gate-open 0 " in cl_[0] and "--run duel_gru_2_0e " in cl_[0] and "--habit-p 0 " in cl_[0]
assert "--head2 1 " in cl_[0] and "--head2-add 1 " in cl_[0] and "--head2-wpg 1 " in cl_[0] and "--head2-l2 0.01" in cl_[0]
assert "--env duel_env_ffa20e " in cl_[0] and "--brain-fade 0 " in cl_[0] and "--opt-small-items 1 " in cl_[0] and "--dmg-reward 0.0055 " in cl_[0]
for s_ in ("INTENT_HOLD=8", "WEAPON_OWN=1", "INTENT_SWITCH=0", "AIM3=1", "AIM3_W=0", "AIM3_SIZE_A=1", "AIM3_SIZE_B=0", "AIM3_PURSUIT_TAU=0.125",
           "AIM3_PURSUIT_GAIN=1.0", "AIM3_FIX_TAU=0.05", "AIM3_LEAD=0", "AIM3_RELOAD=1", "KNOCK_QL=1", "KNOCK_NOW=1", "DODGE_IN=1", "DODGE_G=0"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
for s_ in ("COMBAT", "SPACE_IN", "SPACE_TRUTH", "EDGE_PAY", "COVER_PAY", "SPACE_GATE", "INSTR", "AIM3_HAND"):   # nothing of 1.7, 2.0b, 2.1, no hand lag
    assert not re.search(r"^set {}=".format(s_), t, re.M), s_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
live_ = "\n".join(x for x in t.split("\n") if not x.startswith("rem"))
assert "2_0d" not in live_ and "2.0d" not in live_
tmp = os.path.join(HERE, "train.cmd.tmp")
open(tmp, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
os.replace(tmp, os.path.join(HERE, "train.cmd"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("train.cmd written: {} minutes, {} updates; list 20e; the lock as 1.6a's; no keep choice, order, fire push or pass odds".format(MIN, UPDATES))
