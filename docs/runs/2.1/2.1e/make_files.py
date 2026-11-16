r"""2.1e's train.cmd (the head's slow halves; docs/runs/2.1/2.1e/CARD.md, the owner's decision of 2026-11-15 evening: "we should plan to do
this anyway"): 2.1d's command, every setting as it runs, with:
  --run duel_gru_2_1e, --minutes and --max-updates as given
  --slow-half 1                  the three slow halves inside the head stepped, taught (the fast plan's lesson, their own Adam) and the picked
  --slow-clocks 5,10,20          one played (live SLOW_PICK, SLOW_MIX, SLOW_BACK: ramp_21e.py opens the mix, then the read-back); their clocks
                                 in head ticks (1, 2, 4 s)
Everything else 2.1d's: --held 1 --held-g 0 (live HELD_G: start_live.py takes 2.1d's last), --plan 1, --pull 1 --pull-g 0 --pull-h 0 (live
PULL_G: start_live.py takes 2.1d's last; the ramp never writes it), --head2-lam 0.998, --dmg-taken-w 0.9.
    python docs/runs/2.1/2.1e/make_files.py <minutes> <max updates> [<slow clocks, default 5,10,20>]"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.1d"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN, UPDATES = sys.argv[1], sys.argv[2]
CLOCKS = sys.argv[3] if len(sys.argv) > 3 else "5,10,20"
assert int(MIN) > 0 and int(UPDATES) > 0, (MIN, UPDATES)
assert re.fullmatch(r"\d+,\d+,\d+", CLOCKS) and all(int(c_) >= 1 for c_ in CLOCKS.split(",")), "three clocks of at least one head tick: " + CLOCKS
NEW_ARGS = "--slow-half 1 --slow-clocks {} ".format(CLOCKS)


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
assert len(re.findall(r"--minutes \d+ --max-updates \d+ --gamma ", c)) == 1, "2.1d's --minutes / --max-updates not found"
c = re.sub(r"--minutes \d+ --max-updates \d+ --gamma ", "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES), c)
assert c.count(" --held 1 --held-g 0 --plan 1 --pull 1 --pull-g 0 --pull-h 0 %LEARN% >> ") == 1, "2.1d's --held ... --pull-h 0 not found at the end"
c = c.replace(" --pull 1 --pull-g 0 --pull-h 0 %LEARN% >> ", " --pull 1 --pull-g 0 --pull-h 0 " + NEW_ARGS + "%LEARN% >> ")
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_1d", "duel_gru_2_1e") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\2.1\\2.1d\\",
    "rem ==== 2.1e (owner, 2026-11-15 evening: the head's slow halves; docs/runs/2.1/2.1e): from 2.1d's end with the three slow halves added "
    "inside the head (tools/slow_init.py add: mix 0, back 0, pick 1). 2.1d's command with: run duel_gru_2_1e; --minutes {}; --max-updates {}; "
    "{}(live SLOW_MIX, SLOW_BACK opened by ramp_21e.py; SLOW_PICK set by the owner). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.1\\2.1e\\".format(MIN, UPDATES, NEW_ARGS))
t = t.replace("docs\\runs\\2.1\\2.1d\\", "docs\\runs\\2.1\\2.1e\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES) in cl_[0]
for x_ in ("--pfsp", "--opt-cold-ok", "--wrule", "--keep-freeze", "--keep-g", "--keepq-g", "--stay", "--keep-teach", "--branch", "--map-sense",
           "--cmb-g", "--padd", "--fadd", "--head2-fpg", "--pass-odds", "--space-read", "--ins", "--appraise", "--freeze-choice", "--ordered-heads",
           "--head2-sole", "--obs-half", "--pull-floor"):
    assert x_ + " " not in cl_[0], x_
for x_ in ("--held", "--held-g", "--plan", "--head2-lam", "--dmg-taken-w", "--pull", "--pull-g", "--pull-h", "--slow-half", "--slow-clocks"):
    assert cl_[0].count(" " + x_ + " ") == 1, x_
assert "--run duel_gru_2_1e " in cl_[0] and "--resume " in cl_[0] and "--dmg-taken-w 0.9 " in cl_[0] and "--head2-lam 0.998 " in cl_[0]
assert "--head2 1 " in cl_[0] and "--head2-add 1 " in cl_[0] and "--head2-l2 0.01" in cl_[0] and "--env duel_env_ffa20e " in cl_[0]
assert "--opt-small-items 1 " in cl_[0], "--opt-small-items 1: the read-back's columns widen head2.inp (its moments carried by the file's map)"
assert "--slow-half 1 --slow-clocks {} ".format(CLOCKS) in cl_[0]
for s_ in ("INTENT_HOLD=8", "WEAPON_OWN=1", "INTENT_SWITCH=0", "AIM3=1", "KNOCK_QL=1", "KNOCK_NOW=1", "DODGE_IN=1", "DODGE_G=0"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
for s_ in ("COMBAT", "SPACE_IN", "SPACE_TRUTH", "EDGE_PAY", "COVER_PAY", "SPACE_GATE", "INSTR", "AIM3_HAND", "KEEP_ZONE", "KEEP_SIG"):
    assert not re.search(r"^set {}=".format(s_), t, re.M), s_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
assert not any("duel_gru_2_1d" in x for x in t.split("\n") if not x.startswith("rem")), "a line still names 2.1d's run"
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
assert "call %~dp0aim2_env.cmd" in t
a2_ = open(os.path.join(SRC, "aim2_env.cmd"), "rb").read()                  # (the command calls it beside itself: 2.1d's, as it is)
open(os.path.join(HERE, "aim2_env.cmd"), "wb").write(a2_)
print("wrote train.cmd: --minutes {} --max-updates {} {}; aim2_env.cmd: 2.1d's".format(MIN, UPDATES, NEW_ARGS))
