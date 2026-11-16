r"""2.1f's train.cmd (the outlook inside the head; docs/runs/2.1/2.1f/CARD.md, the owner's idea of 2026-11-16: "he's thinking in the
hypothetical future (8 s ahead) and pulling towards what will have the best outlook"): 2.1d's command, every setting as it ran, with:
  --run duel_gru_2_1f, --minutes and --max-updates as given
  --outlook 1                           the outlook inside the head taught silently (its own Adam) on every keep reading of his on a held trip,
  --out-kinds seg,ret,all8,win8,win5    five label kinds (seg plays by default: out_pick 0); its term live OUT_G (0 at the start; ramp_21f.py
                                        opens it only once the owner's mark file exists), trial trips live OUT_TRIAL (0)
Everything else 2.1d's: --held 1 --held-g 0 (live HELD_G: start_live.py takes 2.1d's last), --plan 1, --pull 1 --pull-g 0 --pull-h 0 (live
PULL_G: start_live.py takes 2.1d's last; the ramp never writes it), --head2-lam 0.998, --dmg-taken-w 0.9. No slow halves (2.1f branches from
2.1d's end, as 2.1e did).
    python docs/runs/2.1/2.1f/make_files.py <minutes> <max updates>"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.1d"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN, UPDATES = sys.argv[1], sys.argv[2]
assert int(MIN) > 0 and int(UPDATES) > 0, (MIN, UPDATES)
KINDS = "seg,ret,all8,win8,win5"
NEW_ARGS = "--outlook 1 --out-kinds {} ".format(KINDS)


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
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_1d", "duel_gru_2_1f") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\2.1\\2.1d\\",
    "rem ==== 2.1f (owner, 2026-11-16: the outlook inside the head; docs/runs/2.1/2.1f): from 2.1d's end with the outlook added inside the head "
    "(tools/out_init.py add: out_g 0, out_pick 0). 2.1d's command with: run duel_gru_2_1f; --minutes {}; --max-updates {}; {}(live OUT_G opened by "
    "ramp_21f.py only once the owner's watch/out_mark.json exists; OUT_PICK and OUT_TRIAL set by the owner). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.1\\2.1f\\".format(MIN, UPDATES, NEW_ARGS))
t = t.replace("docs\\runs\\2.1\\2.1d\\", "docs\\runs\\2.1\\2.1f\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES) in cl_[0]
for x_ in ("--pfsp", "--opt-cold-ok", "--wrule", "--keep-freeze", "--keep-g", "--keepq-g", "--stay", "--keep-teach", "--branch", "--map-sense",
           "--cmb-g", "--padd", "--fadd", "--head2-fpg", "--pass-odds", "--space-read", "--ins", "--appraise", "--freeze-choice", "--ordered-heads",
           "--head2-sole", "--obs-half", "--pull-floor", "--slow-half", "--slow-clocks"):
    assert x_ + " " not in cl_[0], x_
for x_ in ("--held", "--held-g", "--plan", "--head2-lam", "--dmg-taken-w", "--pull", "--pull-g", "--pull-h", "--outlook", "--out-kinds"):
    assert cl_[0].count(" " + x_ + " ") == 1, x_
assert "--run duel_gru_2_1f " in cl_[0] and "--resume " in cl_[0] and "--dmg-taken-w 0.9 " in cl_[0] and "--head2-lam 0.998 " in cl_[0]
assert "--head2 1 " in cl_[0] and "--head2-add 1 " in cl_[0] and "--head2-l2 0.01" in cl_[0] and "--env duel_env_ffa20e " in cl_[0]
assert "--head2-pay all " in cl_[0] and "--aux 0.2 " in cl_[0], "the outlook's labels: the head's whole pay; the simulators' truth kept"
assert NEW_ARGS in cl_[0]
for s_ in ("INTENT_HOLD=8", "WEAPON_OWN=1", "INTENT_SWITCH=0", "AIM3=1", "KNOCK_QL=1", "KNOCK_NOW=1", "DODGE_IN=1", "DODGE_G=0"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
for s_ in ("COMBAT", "SPACE_IN", "SPACE_TRUTH", "EDGE_PAY", "COVER_PAY", "SPACE_GATE", "INSTR", "AIM3_HAND", "KEEP_ZONE", "KEEP_SIG"):
    assert not re.search(r"^set {}=".format(s_), t, re.M), s_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
assert re.findall(r"^set WIN_JUDGE=(\S*)$", t, re.M), "the win labels need the judge (WIN_JUDGE)"
assert not any("duel_gru_2_1d" in x for x in t.split("\n") if not x.startswith("rem")), "a line still names 2.1d's run"
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
assert "call %~dp0aim2_env.cmd" in t
a2_ = open(os.path.join(SRC, "aim2_env.cmd"), "rb").read()                  # (the command calls it beside itself: 2.1d's, as it is)
open(os.path.join(HERE, "aim2_env.cmd"), "wb").write(a2_)
print("wrote train.cmd: --minutes {} --max-updates {} {}; aim2_env.cmd: 2.1d's".format(MIN, UPDATES, NEW_ARGS))
