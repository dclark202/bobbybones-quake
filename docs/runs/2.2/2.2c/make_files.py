r"""2.2c's train.cmd (docs/runs/2.2/2.2c/CARD.md; the build's brief of 2026-11-18): 2.2b's command as it ran (docs/runs/2.2/2.2b/train.cmd, the
restart's), every setting as it ran, with:
  --run duel_gru_2_2c, --minutes and --max-updates as given; --env duel_env_ffa22c (list 22c: 22b and the hands' yellow timers and the brain's
                   places ahead, AHEAD_IN=1)
  IN (change 2)    --lever 1 --lev-g 1 --lev-from 10 (sim/fightnet.py VERSION_LEVER: the fight network's one number x LEV_G on the item picker's
                   score of "the enemy"; 0 on the rollouts of the run's first 10 updates by its own count, as --h2-choice-warm; then LEV_G, 1)
                   --win-scale-items K_I --win-scale-fight K_F (measured on the start's games with 2.2c's pay: win_scale.py)
  IN (change 1)    CONTEST=1 CONTEST_W=0.8 CEDE_W=0.1 (the contest pay, its share and the free pickup's charge, live)
  IN (change 1b)   RAIL_CHAIN=1 RAIL_PICK_PAY=0.15 RAIL_LINE_PAY=0.10 (the rail's pickup and long-line pays, live); RAIL_FAR_PAY 0.1 -> 0.5
  KEPT             FIGHT_SPLIT=22c (sim/fight22.py: the pay split by network, 2.2c's groups); NEAR_PAY=5 (the near-miss pay at 2.2b's size from
                   update 0); everything else of 2.2b's restart as it ran: --head2-wpg 0, --h2-freeze 1, --h2-wsc-freeze 1, --h2-choice-warm 10,
                   --h2-wadd 1 (the ramp writes H2_WADD 1 -> 0 over clocks 0 to 7), --fgt-gate -30 (the ramp opens it over updates 10 to 20),
                   --head2-pay items_win, JUDGE_PAY=1 with 2.2b's accepted refit (items_22b.json: the same start's games), COST_FIRE_W=0,
                   BLIND_FIRE_W=0, --fgt-g 0 --fgt-w 0 --practice-p 0 (no options, no nudge, no practice: --lever refuses anything else)
    python docs/runs/2.2/2.2c/make_files.py <minutes> <max updates> --win-scale-items K --win-scale-fight K"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.2b"))
sys.path.insert(0, os.path.join(REPO, "sim"))
import judge_guard as JG  # noqa: E402

t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN, UPDATES = sys.argv[1], sys.argv[2]
arg_ = lambda n_, d_=None: sys.argv[sys.argv.index(n_) + 1] if n_ in sys.argv else d_   # noqa: E731
KI, KF = float(arg_("--win-scale-items", "1")), float(arg_("--win-scale-fight", "1"))
ITEMS = "docs/runs/2.2/2.2b/items_22b.json"
assert int(MIN) > 0 and int(UPDATES) > 0, (MIN, UPDATES)
IP_ = json.load(open(os.path.join(REPO, ITEMS), encoding="utf-8"))
assert IP_.get("accepted") is True, "the items' fit was not accepted: no start (the item-blind judge is never the pay)"
assert KI >= 1.0 and KF >= 1.0, "the win scales are at least 1 (rule 14: the win part at least the flat part's size)"


def setv(name, val):
    """a `set NAME=...` line of the command to this value (it must be there once)"""
    global t
    k_ = len(re.findall(r"^set {}=.*$".format(name), t, re.M))
    assert k_ == 1, (name, k_)
    t = re.sub(r"^set {}=.*$".format(name), "set {}={}".format(name, val), t, flags=re.M)


def sub(a, b, n=1):
    global t
    assert t.count(a) == n, (a, t.count(a))
    t = t.replace(a, b)


lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
c = re.sub(r"--minutes \d+ --max-updates \d+ --gamma ", "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES), c)
c = re.sub(r"--win-scale-items \S+ --win-scale-fight \S+ ", "--win-scale-items {:g} --win-scale-fight {:g} ".format(KI, KF), c)
for a_, b_ in (("--env duel_env_ffa22b ", "--env duel_env_ffa22c "), ("--run duel_gru_2_2b ", "--run duel_gru_2_2c ")):
    assert c.count(a_) == 1, a_
    c = c.replace(a_, b_)
for x_ in ("--head2-wpg 0 ", "--h2-freeze 1 ", "--h2-wsc-freeze 1 ", "--h2-choice-warm 10 ", "--h2-wadd 1 ", "--fgt-gate -30 ", "--fgt-g 0 ", "--fgt-w 0 ",
           "--practice-p 0 ", "--head2-pay items_win ", "--fight22 1 ", "--lr-warm 60 ", "--lr-warm-start 26519 "):
    assert c.count(x_) == 1, "2.2b's command lacks " + x_
NEW_ARGS = "--lever 1 --lev-g 1 --lev-from 10 "
assert c.count(" %LEARN% >> ") == 1
c = c.replace(" %LEARN% >> ", " " + NEW_ARGS + "%LEARN% >> ")
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_2b", "duel_gru_2_2c") for x in lines)
setv("RAIL_FAR_PAY", "0.5")
NEW_SETS = ("set CONTEST=1\nset CONTEST_W=0.8\nset CEDE_W=0.1\nset RAIL_CHAIN=1\nset RAIL_PICK_PAY=0.15\nset RAIL_LINE_PAY=0.10\nset AHEAD_IN=1\n"
            "set FIGHT_SPLIT=22c\nset NEAR_PAY=5\n")
sub("set ROOT=%~dp0..\\..\\..\\..\ncd /d %ROOT%\n", "set ROOT=%~dp0..\\..\\..\\..\ncd /d %ROOT%\n" + NEW_SETS)
sub("rem the repo root: this file lives in docs\\runs\\2.2\\2.2b\\",
    "rem ==== 2.2c (owner, 2026-11-18: \"Yes to all. Build it and then start it when it's ready.\"; docs/runs/2.2/2.2c/CARD.md): the contest pay and the "
    "aggression lever, from 2.2a's update 90 (list 22c; the lever: tools/inputs22c.py convert, tools/lever22_init.py layout, inputs22c.py stats). "
    "2.2b's command with: run duel_gru_2_2c; --minutes {}; --max-updates {}; --env duel_env_ffa22c; {}--win-scale-items {:g} --win-scale-fight {:g}; "
    "{}RAIL_FAR_PAY 0.1 -> 0.5. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.2\\2.2c\\".format(MIN, UPDATES, NEW_ARGS, KI, KF, NEW_SETS.replace("\n", " ").replace("set ", "")))
t = "\n".join(x if (x.startswith("rem") or x.startswith("set JUDGE_ITEMS=")) else x.replace("docs\\runs\\2.2\\2.2b\\", "docs\\runs\\2.2\\2.2c\\")
              for x in t.split("\n"))
assert re.findall(r"^set JUDGE_ITEMS=(.*)$", t, re.M) == ["%ROOT%\\docs\\runs\\2.2\\2.2b\\items_22b.json"], "JUDGE_ITEMS: 2.2b's accepted refit"
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0]
for x_ in ("--outlook", "--out22", "--map-sense", "--obs-half", "--pfsp", "--wrule", "--keep-g", "--cmb-g", "--ins", "--old-judge-replay"):
    assert x_ + " " not in cl_[0], x_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG", "COST_FIRE_W"):          # (no firing cost: D8)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
assert not re.search(r"^set (DESC_OX|COMBAT|INSTR|KEEP_ZONE|KEEP_SIG)=", t, re.M)
assert not any("duel_gru_2_2b" in x for x in t.split("\n") if not x.startswith("rem")), "a line still names 2.2b's run"
env_ = {m_.group(1): m_.group(2).strip() for m_ in re.finditer(r"(?im)^set ([A-Za-z0-9_]+)=(.*)$", t)}
ok_, why_ = JG.check(env_, None, REPO)
assert ok_, why_
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
assert "call %~dp0aim2_env.cmd" in t
open(os.path.join(HERE, "aim2_env.cmd"), "wb").write(open(os.path.join(SRC, "aim2_env.cmd"), "rb").read())   # (2.2b's, as it is)
print("wrote train.cmd: --minutes {} --max-updates {}; {}; win scales {:g} {:g}; {}; the judge's guard: {}".format(MIN, UPDATES, NEW_ARGS, KI, KF,
                                                                                                                  NEW_SETS.replace("\n", " "), why_))
