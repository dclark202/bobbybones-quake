r"""2.1d's train.cmd (the pull; owner 2026-11-15, the idea approved: "I'm going to go get mega ... otherwise I'm inclined to stick with the goal
I set for myself"): 2.1c's command, every setting as it runs, with:
  --run duel_gru_2_1d, --minutes and --max-updates as given
  --head2-lam <lam>      the head's credit (2.1c: 0.998; given here so a change is said)
  --pull 1 --pull-g 0    the pull built in, its strength shut (live PULL_G: ramp_21d.py opens it); the plan inside the head (tools/plan_init.py
  --pull-h <h>           add); which of the plan's horizons pulls (0: 2 s, 1: 5 s)
Everything else 2.1c's: --held 1 --held-g 0 (live HELD_G: start_live.py takes 2.1c's last), --plan 1 (now the head's own layers, taught on the
learner's copy), --dmg-taken-w 0.9.
    python docs/runs/2.1/2.1d/make_files.py <minutes> <max updates> <head2 lam> <pull horizon>"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.1c"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN, UPDATES, LAM, PH = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
assert int(MIN) > 0 and int(UPDATES) > 0 and 0.99 <= float(LAM) < 1.0 and int(PH) in (0, 1), (MIN, UPDATES, LAM, PH)
NEW_ARGS = "--pull 1 --pull-g 0 --pull-h {} ".format(int(PH))


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
assert len(re.findall(r"--minutes \d+ --max-updates \d+ --gamma ", c)) == 1, "2.1c's --minutes / --max-updates not found"
c = re.sub(r"--minutes \d+ --max-updates \d+ --gamma ", "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES), c)
assert c.count(" --head2-lam 0.998 ") == 1, "2.1c's --head2-lam 0.998 not found"
c = c.replace(" --head2-lam 0.998 ", " --head2-lam {} ".format(LAM))
assert c.count(" --held 1 --held-g 0 --plan 1 %LEARN% >> ") == 1, "2.1c's --held 1 --held-g 0 --plan 1 not found at the end"
c = c.replace(" --held 1 --held-g 0 --plan 1 %LEARN% >> ", " --held 1 --held-g 0 --plan 1 " + NEW_ARGS + "%LEARN% >> ")
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_1c", "duel_gru_2_1d") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\2.1\\2.1c\\",
    "rem ==== 2.1d (owner, 2026-11-15: the pull; docs/runs/2.1/2.1d): from a 2.1c save with the slow plan moved inside the head (tools/plan_init.py "
    "add). 2.1c's command with: run duel_gru_2_1d; --minutes {}; --max-updates {}; --head2-lam {}; {}(live PULL_G, opened by ramp_21d.py; "
    "his target scores as played + PULL_G x log(the plan's odds)). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.1\\2.1d\\".format(MIN, UPDATES, LAM, NEW_ARGS))
t = t.replace("docs\\runs\\2.1\\2.1c\\", "docs\\runs\\2.1\\2.1d\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES) in cl_[0]
for x_ in ("--pfsp", "--opt-cold-ok", "--wrule", "--keep-freeze", "--keep-g", "--keepq-g", "--stay", "--keep-teach", "--branch", "--map-sense",
           "--cmb-g", "--padd", "--fadd", "--head2-fpg", "--pass-odds", "--space-read", "--ins", "--appraise", "--freeze-choice", "--ordered-heads",
           "--head2-sole"):
    assert x_ + " " not in cl_[0], x_
for x_ in ("--held", "--held-g", "--plan", "--head2-lam", "--dmg-taken-w", "--pull", "--pull-g", "--pull-h"):
    assert cl_[0].count(" " + x_ + " ") == 1, x_
assert "--pull-floor" not in cl_[0], "--pull-floor: the default (0.01)"
assert "--run duel_gru_2_1d " in cl_[0] and "--resume " in cl_[0] and "--dmg-taken-w 0.9 " in cl_[0] and "--head2-lam {} ".format(LAM) in cl_[0]
assert "--head2 1 " in cl_[0] and "--head2-add 1 " in cl_[0] and "--head2-l2 0.01" in cl_[0] and "--env duel_env_ffa20e " in cl_[0]
for s_ in ("INTENT_HOLD=8", "WEAPON_OWN=1", "INTENT_SWITCH=0", "AIM3=1", "KNOCK_QL=1", "KNOCK_NOW=1", "DODGE_IN=1", "DODGE_G=0"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
for s_ in ("COMBAT", "SPACE_IN", "SPACE_TRUTH", "EDGE_PAY", "COVER_PAY", "SPACE_GATE", "INSTR", "AIM3_HAND", "KEEP_ZONE", "KEEP_SIG"):
    assert not re.search(r"^set {}=".format(s_), t, re.M), s_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
assert not any("duel_gru_2_1c" in x for x in t.split("\n") if not x.startswith("rem")), "a line still names 2.1c's run"
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
assert "call %~dp0aim2_env.cmd" in t
a2_ = open(os.path.join(SRC, "aim2_env.cmd"), "rb").read()                  # (the command calls it beside itself: 2.1c's, as it is)
open(os.path.join(HERE, "aim2_env.cmd"), "wb").write(a2_)
print("wrote train.cmd: --minutes {} --max-updates {} --head2-lam {} {}; aim2_env.cmd: 2.1c's".format(MIN, UPDATES, LAM, NEW_ARGS))
