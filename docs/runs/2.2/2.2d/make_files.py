r"""2.2d's train.cmd (docs/runs/2.2/2.2d/CARD.md; the build's brief of 2026-11-18): 2.2c's command as it ran (docs/runs/2.2/2.2c/train.cmd),
every setting as it ran, with:
  --run duel_gru_2_2d, --minutes and --max-updates as given; --win-scale-items K_I --win-scale-fight K_F (measured again on the start's games
                   with 2.2d's pay: win_scale_22d.json)
  OUT (owner 11-18) the contest pay: CONTEST_W 0.8 -> 0, CEDE_W 0.1 -> 0, and CONTEST_LOG=1 (sim/duel_env.py: every term of the contest pay exactly
                   0.0 at the pickup, the free pickup's charge, the steal and by the second; its counters kept, the steals and the frames by the
                   second counted on the event); CONTEST=1 stays (the counters)
                   the long sighting with the rail in hand: RAIL_LINE_PAY 0.10 -> 0 (the term rail_line exactly 0; RAIL_CHAIN=1 stays for
                   RAIL_PICK_PAY 0.15; RAIL_FAR_PAY 0.5 unchanged)
                   the near miss: NEAR_PAY 5 -> 0 (the term near_miss exactly 0; NEAR_MISS=1 stays: its counters)
  IN (logging)     RAIL_WOULD=1 (what a rail would have dealt against what he dealt, by distance), FREE_SEE=1 (his line to the item at the enemy's
                   free big pickups): sim/duel_env.py, read only
                   --kl-heads 10 -> 1 (the weapon-choice-speed alarm's figure, kl_heads, measured every update: with 10 it was measured on the
                   first 20 updates and every 10th only, so 2.2c's alarm lost it from update 21; read only, no effect on the learning)
  KEPT             everything else of 2.2c: the lever (--lever 1 --lev-g 1 --lev-from 10), FIGHT_SPLIT=22c, AHEAD_IN=1, --head2-wpg 0,
                   --h2-freeze 1, --h2-wsc-freeze 1, --h2-choice-warm 10, --h2-wadd 1, --fgt-gate -30, JUDGE_PAY=1 with 2.2b's accepted refit
                   (items_22b.json), firing free
    python docs/runs/2.2/2.2d/make_files.py <minutes> <max updates> --win-scale-items K --win-scale-fight K"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.2c"))
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
assert len(re.findall(r"--minutes \d+ --max-updates \d+ --gamma ", c)) == 1
c = re.sub(r"--minutes \d+ --max-updates \d+ --gamma ", "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES), c)
assert len(re.findall(r"--win-scale-items \S+ --win-scale-fight \S+ ", c)) == 1
c = re.sub(r"--win-scale-items \S+ --win-scale-fight \S+ ", "--win-scale-items {:g} --win-scale-fight {:g} ".format(KI, KF), c)
for a_, b_ in (("--run duel_gru_2_2c ", "--run duel_gru_2_2d "), ("--kl-heads 10 ", "--kl-heads 1 ")):
    assert c.count(a_) == 1, a_
    c = c.replace(a_, b_)
for x_ in ("--env duel_env_ffa22c ", "--head2-wpg 0 ", "--h2-freeze 1 ", "--h2-wsc-freeze 1 ", "--h2-choice-warm 10 ", "--h2-wadd 1 ", "--fgt-gate -30 ",
           "--fgt-g 0 ", "--fgt-w 0 ", "--practice-p 0 ", "--head2-pay items_win ", "--fight22 1 ", "--lr-warm 60 ", "--lr-warm-start 26519 ",
           "--lever 1 --lev-g 1 --lev-from 10 "):
    assert c.count(x_) == 1, "2.2c's command lacks " + x_
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_2c", "duel_gru_2_2d") for x in lines)
setv("CONTEST_W", "0")
setv("CEDE_W", "0")
setv("RAIL_LINE_PAY", "0")
setv("NEAR_PAY", "0")
for n_, v_ in (("CONTEST", "1"), ("RAIL_CHAIN", "1"), ("RAIL_PICK_PAY", "0.15"), ("RAIL_FAR_PAY", "0.5"), ("NEAR_MISS", "1"), ("AHEAD_IN", "1"),
               ("FIGHT_SPLIT", "22c")):
    assert re.findall(r"^set {}=(.*)$".format(n_), t, re.M) == [v_], (n_, re.findall(r"^set {}=(.*)$".format(n_), t, re.M))
NEW_SETS = "set CONTEST_LOG=1\nset RAIL_WOULD=1\nset FREE_SEE=1\n"
sub("set ROOT=%~dp0..\\..\\..\\..\ncd /d %ROOT%\n", "set ROOT=%~dp0..\\..\\..\\..\ncd /d %ROOT%\n" + NEW_SETS)
sub("rem the repo root: this file lives in docs\\runs\\2.2\\2.2c\\",
    "rem ==== 2.2d (owner, 2026-11-18: \"keep the pay split, rail pickup, far [rail], and aggression [lever]. drop the long sighting pay and near miss "
    "pay and contest pay\"; docs/runs/2.2/2.2d/CARD.md): from 2.2a's update 90 as 2.2c's start. 2.2c's command with: run duel_gru_2_2d; --minutes {}; "
    "--max-updates {}; --win-scale-items {:g} --win-scale-fight {:g}; CONTEST_W 0, CEDE_W 0, CONTEST_LOG=1 (the contest pay exactly 0, its counters "
    "kept); RAIL_LINE_PAY 0; NEAR_PAY 0; RAIL_WOULD=1 and FREE_SEE=1 (two log lines); --kl-heads 1 (the weapon-speed alarm's figure every update). "
    "Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.2\\2.2d\\".format(MIN, UPDATES, KI, KF))
t = "\n".join(x if (x.startswith("rem") or x.startswith("set JUDGE_ITEMS=")) else x.replace("docs\\runs\\2.2\\2.2c\\", "docs\\runs\\2.2\\2.2d\\")
              for x in t.split("\n"))
assert re.findall(r"^set JUDGE_ITEMS=(.*)$", t, re.M) == ["%ROOT%\\docs\\runs\\2.2\\2.2b\\items_22b.json"], "JUDGE_ITEMS: 2.2b's accepted refit"
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0]
for x_ in ("--outlook", "--out22", "--map-sense", "--obs-half", "--pfsp", "--wrule", "--keep-g", "--cmb-g", "--ins", "--old-judge-replay"):
    assert x_ + " " not in cl_[0], x_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG", "COST_FIRE_W"):          # (no firing cost)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
assert not re.search(r"^set (DESC_OX|COMBAT|INSTR|KEEP_ZONE|KEEP_SIG)=", t, re.M)
assert not any("duel_gru_2_2c" in x or "2.2\\2.2c" in x for x in t.split("\n") if not x.startswith("rem")), "a line still names 2.2c's run"
env_ = {m_.group(1): m_.group(2).strip() for m_ in re.finditer(r"(?im)^set ([A-Za-z0-9_]+)=(.*)$", t)}
ok_, why_ = JG.check(env_, None, REPO)
assert ok_, why_
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
assert "call %~dp0aim2_env.cmd" in t
open(os.path.join(HERE, "aim2_env.cmd"), "wb").write(open(os.path.join(SRC, "aim2_env.cmd"), "rb").read())   # (2.2c's, as it is)
print("wrote train.cmd: --minutes {} --max-updates {}; win scales {:g} {:g}; CONTEST_W 0 CEDE_W 0 CONTEST_LOG 1 RAIL_LINE_PAY 0 NEAR_PAY 0 RAIL_WOULD 1 "
      "FREE_SEE 1 --kl-heads 1; the judge's guard: {}".format(MIN, UPDATES, KI, KF, why_))
