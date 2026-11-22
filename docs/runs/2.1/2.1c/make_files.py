r"""2.1c's train.cmd (owner, 2026-11-15: the 8-second lock out by the held draw; docs/runs/2.1/2.1c/CARD.md): 2.0e's command, every setting
as it ran, with:
  --run duel_gru_2_1c, --minutes and --max-updates as given
  --held 1 --held-g 0   the held draw built in, its share shut (the lock decides every trip, as 2.0e's end; live HELD_G: ramp_21c.py)
  --head2-lam <lam>     the head's credit over a trip (2.0e: 0.995, about 5 s; the card's decision 4)
  --dmg-taken-w 0.9     (owner 11-14: damage taken costs 0.9 of the pay of damage dealt; as 2.1b)
  --plan 1              (2.1c, owner 11-15) the slow plan in shadow (sim/slowplan.py): it learns his own target odds 2 s and 5 s ahead;
                        nothing reads it (readouts only)
Nothing of 2.1b: no keep choice, no stay value, no frozen moments, no map sense, KEEP_ZONE and KEEP_SIG unset.
    python docs/runs/2.1/2.1c/make_files.py <minutes> <max updates> <head2 lam>"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "2.0", "2.0e"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN, UPDATES, LAM = sys.argv[1], sys.argv[2], sys.argv[3]
assert int(MIN) > 0 and int(UPDATES) > 0 and 0.99 <= float(LAM) < 1.0, (MIN, UPDATES, LAM)
NEW_ARGS = "--held 1 --held-g 0 --plan 1 "


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
assert len(re.findall(r"--minutes \d+ --max-updates \d+ --gamma ", c)) == 1, "2.0e's --minutes / --max-updates not found"
c = re.sub(r"--minutes \d+ --max-updates \d+ --gamma ", "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES), c)
assert c.count(" --dmg-taken-w 1.0 ") == 1, "2.0e's --dmg-taken-w 1.0 not found"
c = c.replace(" --dmg-taken-w 1.0 ", " --dmg-taken-w 0.9 ")
assert c.count(" --head2-lam 0.995 ") == 1, "2.0e's --head2-lam 0.995 not found"
c = c.replace(" --head2-lam 0.995 ", " --head2-lam {} ".format(LAM))
assert c.count(" %LEARN% >> ") == 1
c = c.replace(" %LEARN% >> ", " " + NEW_ARGS + "%LEARN% >> ")
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_0e", "duel_gru_2_1c") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\2.0\\2.0e\\",
    "rem ==== 2.1c (owner, 2026-11-15: the lock out by the held draw; docs/runs/2.1/2.1c/CARD.md): from 2.0e's end. 2.0e's command with: run "
    "duel_gru_2_1c; --minutes {}; --max-updates {}; --dmg-taken-w 0.9 (owner 11-14); --head2-lam {} (the head's credit over a trip); {}(live "
    "HELD_G, opened by ramp_21c.py; --plan 1: the slow plan in shadow, nothing reads it). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.1\\2.1c\\".format(MIN, UPDATES, LAM, NEW_ARGS))
t = t.replace("docs\\runs\\2.0\\2.0e\\", "docs\\runs\\2.1\\2.1c\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES) in cl_[0]
for x_ in ("--pfsp", "--opt-cold-ok", "--wrule", "--keep-freeze", "--keep-g", "--keepq-g", "--stay", "--keep-teach", "--branch", "--map-sense",
           "--cmb-g", "--padd", "--fadd", "--head2-fpg", "--pass-odds", "--space-read", "--ins", "--appraise", "--freeze-choice", "--ordered-heads"):
    assert x_ + " " not in cl_[0], x_
for x_ in ("--held", "--held-g", "--plan", "--head2-lam", "--dmg-taken-w"):
    assert cl_[0].count(" " + x_ + " ") == 1, x_
assert "--gate-open 0 " in cl_[0] and "--run duel_gru_2_1c " in cl_[0] and "--habit-p 0 " in cl_[0] and "--resume " in cl_[0]
assert "--head2 1 " in cl_[0] and "--head2-add 1 " in cl_[0] and "--head2-wpg 1 " in cl_[0] and "--head2-l2 0.01" in cl_[0]
assert "--env duel_env_ffa20e " in cl_[0] and "--brain-fade 0 " in cl_[0] and "--dmg-reward 0.0055 " in cl_[0]
for s_ in ("INTENT_HOLD=8", "WEAPON_OWN=1", "INTENT_SWITCH=0", "AIM3=1", "KNOCK_QL=1", "KNOCK_NOW=1", "DODGE_IN=1", "DODGE_G=0"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
for s_ in ("COMBAT", "SPACE_IN", "SPACE_TRUTH", "EDGE_PAY", "COVER_PAY", "SPACE_GATE", "INSTR", "AIM3_HAND", "KEEP_ZONE", "KEEP_SIG"):
    assert not re.search(r"^set {}=".format(s_), t, re.M), s_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
print("wrote train.cmd: --minutes {} --max-updates {} --head2-lam {} {}".format(MIN, UPDATES, LAM, NEW_ARGS))
