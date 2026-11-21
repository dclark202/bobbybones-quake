r"""2.2a's train.cmd (docs/runs/2.2/DESIGN.md "2.2a in detail"; the owner's brief of 2026-11-16 evening): 2.1d's command (never an older copy),
every setting as it ran, with:
  --run duel_gru_2_2a, --minutes and --max-updates as given
  --outlook 1 --out-kinds seg,ret,all8,win8,win5,segw,winit8
                                        the outlook inside the head (2.1f's, kept exactly) with the facts and the two kinds of the judge that sees
                                        the items, taught silently; its term live OUT_G (0 at the start; ramp_22a.py opens it from the owner's
                                        watch/out_mark.json, or by its automatic mark at update 60: auto_mark.json), OUT_PICK (seg), OUT_TRIAL
                                        (ramp: 0 -> 0.03 over updates 0 to 10)
  --out22 1                             the tracker, the desc outlooks (live OUT_SRC: which outlook's term plays), the facts, the head's second value
  --map-sense 1 --map-sense-init <start>  the map sense's lesson switched on (its start: the init file's "map_sense", made from the start file)
  set DESC_OX=1                         order_feat()'s targets' numbers without COMBAT (sim/duel_env.py: a read only, off and on the same game)
  set FIGHT_TRUTH=1                     the fight odds' labels (the tracker's "a fight now")
  set JUDGE_ITEMS=<items_22a.json>      the judge that sees the items (sim/win_judge.py): the head's win_raw only; --head2-pay all is unchanged, so
                                        the head's pay and the hands' are the same with and without it (proved); only with --items (an ACCEPTED fit)
Everything else 2.1d's: --held 1 --held-g 0 (live HELD_G: start_live.py takes 2.1d's last), --plan 1, --pull 1 --pull-g 0 --pull-h 0 (live
PULL_G: 2.1d's last; the ramp never writes it), --head2-lam 0.998, --dmg-taken-w 0.9, --head2-pay all, --control 1 --control-src belief,both.
    python docs/runs/2.2/2.2a/make_files.py <minutes> <max updates> [--items docs/runs/2.2/2.2a/items_22a.json]"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "2.1", "2.1d"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN, UPDATES = sys.argv[1], sys.argv[2]
ITEMS = sys.argv[sys.argv.index("--items") + 1] if "--items" in sys.argv else ""
assert int(MIN) > 0 and int(UPDATES) > 0, (MIN, UPDATES)
KINDS = "seg,ret,all8,win8,win5,segw,winit8"
NEW_ARGS = ("--outlook 1 --out-kinds {} --out22 1 --map-sense 1 --map-sense-init %ROOT%\\data\\sim_runs\\space\\mapsense_start.pt ".format(KINDS))
if ITEMS:
    IP_ = json.load(open(ITEMS if os.path.isabs(ITEMS) else os.path.join(REPO, ITEMS), encoding="utf-8"))
    assert IP_.get("accepted") is True, "--items: the fit was not accepted: the run starts without the judge that sees the items"


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
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_1d", "duel_gru_2_2a") for x in lines)   # (the history lines stay as written)
sets_ = "set DESC_OX=1\nset FIGHT_TRUTH=1\n" + ("set JUDGE_ITEMS=%ROOT%\\{}\n".format(ITEMS.replace("/", "\\")) if ITEMS else "")
sub("rem the repo root: this file lives in docs\\runs\\2.1\\2.1d\\",
    "rem ==== 2.2a (owner, 2026-11-16: the outlook, the tracker, the desc outlooks; docs/runs/2.2/DESIGN.md): from 2.1d's end with 2.2a's parts added "
    "inside the head at zero (tools/out22_init.py add). 2.1d's command with: run duel_gru_2_2a; --minutes {}; --max-updates {}; {}(live OUT_G opened by "
    "ramp_22a.py from the owner's watch/out_mark.json or its automatic mark at update 60; OUT_SRC; OUT_TRIAL 0 -> 0.03 over updates 0 to 10); "
    "DESC_OX=1, FIGHT_TRUTH=1{}. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.2\\2.2a\\".format(MIN, UPDATES, NEW_ARGS, ", JUDGE_ITEMS" if ITEMS else ""))
sub("set ROOT=%~dp0..\\..\\..\\..\ncd /d %ROOT%\n", "set ROOT=%~dp0..\\..\\..\\..\ncd /d %ROOT%\n" + sets_)
t = t.replace("docs\\runs\\2.1\\2.1d\\", "docs\\runs\\2.2\\2.2a\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES) in cl_[0]
for x_ in ("--pfsp", "--opt-cold-ok", "--wrule", "--keep-freeze", "--keep-g", "--keepq-g", "--stay", "--keep-teach", "--branch",
           "--cmb-g", "--padd", "--fadd", "--head2-fpg", "--pass-odds", "--space-read", "--ins", "--appraise", "--freeze-choice", "--ordered-heads",
           "--head2-sole", "--obs-half", "--pull-floor", "--slow-half", "--slow-clocks", "--fight-odds"):
    assert x_ + " " not in cl_[0], x_
for x_ in ("--held", "--held-g", "--plan", "--head2-lam", "--dmg-taken-w", "--pull", "--pull-g", "--pull-h", "--outlook", "--out-kinds", "--out22",
           "--map-sense", "--map-sense-init", "--control", "--head2-pay"):
    assert cl_[0].count(" " + x_ + " ") == 1, x_
assert "--run duel_gru_2_2a " in cl_[0] and "--resume " in cl_[0] and "--dmg-taken-w 0.9 " in cl_[0] and "--head2-lam 0.998 " in cl_[0]
assert "--head2 1 " in cl_[0] and "--head2-add 1 " in cl_[0] and "--head2-l2 0.01" in cl_[0] and "--env duel_env_ffa20e " in cl_[0]
assert "--head2-pay all " in cl_[0] and "--aux 0.2 " in cl_[0] and "--control-src belief,both " in cl_[0], "the head's whole pay; the truth; both readouts"
assert NEW_ARGS in cl_[0]
for s_ in ("INTENT_HOLD=8", "WEAPON_OWN=1", "INTENT_SWITCH=0", "AIM3=1", "KNOCK_QL=1", "KNOCK_NOW=1", "DODGE_IN=1", "DODGE_G=0", "DESC_OX=1",
           "FIGHT_TRUTH=1", "CONTROL_TRUTH=1", "TRACK_TRUTH=1", "EN_STACK=1"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
for s_ in ("COMBAT", "SPACE_IN", "SPACE_TRUTH", "EDGE_PAY", "COVER_PAY", "SPACE_GATE", "INSTR", "AIM3_HAND", "KEEP_ZONE", "KEEP_SIG"):
    assert not re.search(r"^set {}=".format(s_), t, re.M), s_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
assert re.findall(r"^set WIN_JUDGE=(\S*)$", t, re.M), "the win labels need the judge (WIN_JUDGE)"
assert len(re.findall(r"^set JUDGE_ITEMS=", t, re.M)) == (1 if ITEMS else 0)
assert not any("duel_gru_2_1d" in x for x in t.split("\n") if not x.startswith("rem")), "a line still names 2.1d's run"
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
assert "call %~dp0aim2_env.cmd" in t
a2_ = open(os.path.join(SRC, "aim2_env.cmd"), "rb").read()                  # (the command calls it beside itself: 2.1d's, as it is)
open(os.path.join(HERE, "aim2_env.cmd"), "wb").write(a2_)
print("wrote train.cmd: --minutes {} --max-updates {} {}; {}; aim2_env.cmd: 2.1d's".format(MIN, UPDATES, NEW_ARGS,
      "JUDGE_ITEMS=" + ITEMS if ITEMS else "no JUDGE_ITEMS"))
