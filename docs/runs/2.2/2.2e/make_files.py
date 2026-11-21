r"""2.2e's train.cmd and aim2_env.cmd (docs/runs/2.2/2.2e/CARD.md; the build's brief of 2026-11-19): 2.2d's command as it ran
(docs/runs/2.2/2.2d/train.cmd), every setting as it ran, with:
  --run duel_gru_2_2e, --minutes and --max-updates as given (start.ps1: the minutes to 08:00 on 11-20, the updates a bound never reached);
                   --win-scale-items K_I --win-scale-fight K_F (measured again on the start's games under aim4: win_scale_22e.json)
  AIM4 (owner 11-19, "make that the aim4 default"): every value from tools/aim2_levels.py TABLE4["default"] (aim3's "better" row with
                   AIM3_SIZE_A 0, AIM3_SIZE_B 0.49): --react-ms 100 --acquire-ms 175; aim2_env.cmd written from the table (PERCEPT_SIGMA 0.64,
                   the slip 0.007 / 1.1, the off-centre error 0.01, the focus 0.7, no flinch, the hand 0.080 / 0.038, VEL_DELAY_MS 175,
                   VEL_WEBER 0.15, RANGE_WEBER 0.17); the command's own AIM3_* and VEL_* / RANGE_WEBER lines the table's (one value a name
                   wherever the file sets it); every seat of the simulator plays it (him and his league: the process's settings)
  OUT (owner 11-19) the rail's pickup pay: RAIL_PICK_PAY 0.15 -> 0 (RAIL_CHAIN=1 stays: its term reads exactly 0)
  CHANGED (owner 11-19) the far-rail pay: RAIL_FAR_PAY 0.5 -> 0.2 (its band unchanged: RAIL_FAR_LO 500, RAIL_FAR_HI 800)
  IN (owner 11-19) the rail drill: RDRILL=1 (sim/duel_env.py), RDRILL_P=0.10 (its share at the start; live, ramp_22e.py: 0.10 to update 40,
                   evenly to 0 at update 60)
  KEPT             everything else of 2.2d: the lever (--lever 1 --lev-g 1 --lev-from 10), the freeze (--h2-freeze 1 --h2-wsc-freeze 1
                   --h2-choice-warm 10), FIGHT_SPLIT=22c, JUDGE_PAY=1 with 2.2b's accepted refit, CONTEST_LOG=1, RAIL_WOULD=1, FREE_SEE=1,
                   --kl-heads 1, firing free
    python docs/runs/2.2/2.2e/make_files.py <minutes> <max updates> --win-scale-items K --win-scale-fight K"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.2d"))
sys.path.insert(0, os.path.join(REPO, "sim"))
sys.path.insert(0, os.path.join(REPO, "tools"))
import judge_guard as JG  # noqa: E402
import aim2_levels as AL  # noqa: E402

RM4, AM4, EV4 = AL.TABLE4["default"]
AIM4 = dict(AL.COMMON, **EV4)                                # (every aim setting of the level, the common ones included)
DRILL_P0 = "0.10"

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
for a_, b_ in (("--run duel_gru_2_2d ", "--run duel_gru_2_2e "), ("--react-ms 125 --acquire-ms 225 ", "--react-ms {} --acquire-ms {} ".format(RM4, AM4))):
    assert c.count(a_) == 1, a_
    c = c.replace(a_, b_)
for x_ in ("--env duel_env_ffa22c ", "--head2-wpg 0 ", "--h2-freeze 1 ", "--h2-wsc-freeze 1 ", "--h2-choice-warm 10 ", "--h2-wadd 1 ", "--fgt-gate -30 ",
           "--fgt-g 0 ", "--fgt-w 0 ", "--practice-p 0 ", "--head2-pay items_win ", "--fight22 1 ", "--lr-warm 60 ", "--lr-warm-start 26519 ",
           "--lever 1 --lev-g 1 --lev-from 10 ", "--kl-heads 1 "):
    assert c.count(x_) == 1, "2.2d's command lacks " + x_
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_2d", "duel_gru_2_2e") for x in lines)
setv("RAIL_PICK_PAY", "0")
setv("RAIL_FAR_PAY", "0.2")
for n_ in ("AIM3_SIZE_A", "AIM3_SIZE_B", "AIM3_PURSUIT_TAU", "AIM3_PURSUIT_GAIN", "AIM3_FIX_TAU", "AIM3_LEAD", "AIM3_RELOAD", "AIM3", "AIM3_W",
           "VEL_DELAY_MS", "VEL_WEBER", "RANGE_WEBER"):
    setv(n_, AIM4[n_])
for n_, v_ in (("CONTEST", "1"), ("CONTEST_LOG", "1"), ("CONTEST_W", "0"), ("CEDE_W", "0"), ("RAIL_CHAIN", "1"), ("RAIL_LINE_PAY", "0"), ("NEAR_PAY", "0"),
               ("NEAR_MISS", "1"), ("AHEAD_IN", "1"), ("FIGHT_SPLIT", "22c"), ("RAIL_FAR_LO", "500"), ("RAIL_FAR_HI", "800"), ("RAIL_WOULD", "1"),
               ("FREE_SEE", "1"), ("PAY_SPLIT", "1")):
    assert re.findall(r"^set {}=(.*)$".format(n_), t, re.M) == [v_], (n_, re.findall(r"^set {}=(.*)$".format(n_), t, re.M))
assert not re.search(r"^set (RDRILL|RDRILL_P|RDRILL_ALL|RDRILL_SPOTS)=", t, re.M)
NEW_SETS = "set RDRILL=1\nset RDRILL_P={}\n".format(DRILL_P0)
sub("set ROOT=%~dp0..\\..\\..\\..\ncd /d %ROOT%\n", "set ROOT=%~dp0..\\..\\..\\..\ncd /d %ROOT%\n" + NEW_SETS)
sub("rem the repo root: this file lives in docs\\runs\\2.2\\2.2d\\",
    "rem ==== 2.2e (owner, 2026-11-19: \"make that the aim4 default. build it and start it when it's ready\"; \"we'll plan to run it overnight til 8am\"; "
    "docs/runs/2.2/2.2e/CARD.md): from 2.2a's update 90 as 2.2d's start. 2.2d's command with: run duel_gru_2_2e; --minutes {}; --max-updates {}; "
    "--win-scale-items {:g} --win-scale-fight {:g}; aim4 (tools/aim2_levels.py TABLE4 default: --react-ms {} --acquire-ms {}, aim2_env.cmd and the AIM3_*, "
    "VEL_* and RANGE_WEBER lines from the table); RAIL_PICK_PAY 0 (the rail's pickup pay out); RAIL_FAR_PAY 0.2; RDRILL=1 RDRILL_P={} (the rail drill, "
    "live: ramp_22e.py). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.2\\2.2e\\".format(MIN, UPDATES, KI, KF, RM4, AM4, DRILL_P0))
t = "\n".join(x if (x.startswith("rem") or x.startswith("set JUDGE_ITEMS=")) else x.replace("docs\\runs\\2.2\\2.2d\\", "docs\\runs\\2.2\\2.2e\\")
              for x in t.split("\n"))
assert re.findall(r"^set JUDGE_ITEMS=(.*)$", t, re.M) == ["%ROOT%\\docs\\runs\\2.2\\2.2b\\items_22b.json"], "JUDGE_ITEMS: 2.2b's accepted refit"
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0]
for x_ in ("--outlook", "--out22", "--map-sense", "--obs-half", "--pfsp", "--wrule", "--keep-g", "--cmb-g", "--ins", "--old-judge-replay"):
    assert x_ + " " not in cl_[0], x_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG", "COST_FIRE_W"):          # (no firing cost)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
assert not re.search(r"^set (DESC_OX|COMBAT|INSTR|KEEP_ZONE|KEEP_SIG)=", t, re.M)
assert not any("duel_gru_2_2d" in x or "2.2\\2.2d" in x for x in t.split("\n") if not x.startswith("rem")), "a line still names 2.2d's run"
env_ = {m_.group(1): m_.group(2).strip() for m_ in re.finditer(r"(?im)^set ([A-Za-z0-9_]+)=(.*)$", t)}
ok_, why_ = JG.check(env_, None, REPO)
assert ok_, why_
assert "call %~dp0aim2_env.cmd" in t
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))

# aim2_env.cmd: 2.2d's names in 2.2d's order, each at aim4's value (every one of them is in the table; nothing else is set there)
src_ = open(os.path.join(SRC, "aim2_env.cmd"), encoding="ascii").read().replace("\r\n", "\n").split("\n")
out_ = ["rem ---- AIM4 default (2.2e, owner 2026-11-19: \"make that the aim4 default\"; docs/runs/2.2/2.2e/CARD.md): tools/aim2_levels.py TABLE4[\"default\"],",
        "rem      aim3's \"better\" row with the sight error in proportion to the enemy's size (AIM3_SIZE_A 0, AIM3_SIZE_B 0.49 in train.cmd). Written by",
        "rem      make_files.py; the delays are the trainer's --react-ms {} --acquire-ms {} (set in the command).".format(RM4, AM4)]
seen_ = set()
for ln_ in src_:
    m_ = re.match(r"^set ([A-Za-z0-9_]+)=(.*)$", ln_)
    if not m_:
        continue
    k_ = m_.group(1)
    if k_ == "PERCEPT_SPEED_MAX":                            # (unset, as 2.2d's)
        out_.append(ln_)
        continue
    assert k_ in AIM4, "aim2_env.cmd's {} is not in TABLE4".format(k_)
    out_.append("set {}={}".format(k_, AIM4[k_]))
    seen_.add(k_)
open(os.path.join(HERE, "aim2_env.cmd"), "w", encoding="ascii", newline="").write("\r\n".join(out_) + "\r\n")

# the proof: the command as read (train.cmd with aim2_env.cmd called, the last value of a name wins) has every aim4 value
sys.path.insert(0, os.path.join(REPO, "tools", "run"))
import check_settings as CS  # noqa: E402
E_, A_ = CS.read_cmd(os.path.join(HERE, "train.cmd"))
bad_ = {k_: (E_.get(k_), v_) for k_, v_ in AIM4.items() if not CS.same(E_.get(k_, "<unset>"), v_)}
assert not bad_, "the command as read is not aim4: {}".format(bad_)
assert CS.same(A_["--react-ms"], RM4) and CS.same(A_["--acquire-ms"], AM4), (A_["--react-ms"], A_["--acquire-ms"])
print("wrote train.cmd and aim2_env.cmd: --minutes {} --max-updates {}; win scales {:g} {:g}; aim4 ({} names and the delays {} / {} ms, all as read); "
      "RAIL_PICK_PAY 0, RAIL_FAR_PAY 0.2, RDRILL=1 RDRILL_P={}; the judge's guard: {}".format(MIN, UPDATES, KI, KF, len(AIM4), RM4, AM4, DRILL_P0, why_))
