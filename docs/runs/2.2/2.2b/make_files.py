r"""2.2b's train.cmd (docs/runs/2.2/2.2b/CARD.md; the brief of 2026-11-17): 2.2a's command as it ran (docs/runs/2.2/2.2a/train.cmd, never an older
copy), every setting as it ran, with:
  --run duel_gru_2_2b, --minutes and --max-updates as given; --env duel_env_ffa22b (list 22b: 20e and the hands' "b22b fight")
  OUT (change 1)   --outlook, --out-kinds, --out22, --map-sense, --map-sense-init (the rater of options and the map sense only it read); DESC_OX
  IN               --fight22 1 (sim/fightnet.py: the fight network, the one list, practice, its lesson; the tracker and its pass odds learn without
                   the outlook) --fight-lr 1e-4 --fgt-g 0 --fgt-w 0 --practice-p 0 --h2-wadd 1 --fgt-gate -30 (the ramp's dials start shut)
                   --head2-pay items_win (change 8) --win-scale-items K_I --win-scale-fight K_F (change 9: measured, win_scale.py)
                   --h2-choice-warm 10 --lr-warm 60 --lr-warm-start 26519 (the optimizer starts cold: none was kept at update 90; the learning
                   rate climbs from a tenth to full over 60 minutes (about 9 updates) from 2.2b's own start, minute 26,519 of the lineage)
                   FIGHT=1 OUT_LIVE=1.5 (the fight options; back off by living through it, 1.7b's 1.5 s) NEAR_MISS=1 (NEAR_PAY live, 0 at the start)
                   JUDGE_PAY=1 JUDGE_ITEMS=<items_22b.json> (the paid win part: the judge with the items, everywhere; the owner's correction)
                   FIGHT_START_P=0.20 PRO_START_P=0.15 (change 7; whole games stay GAME_P 0.65)
  START = LIVE     every value the live file sets is the command's start value too where the trainer takes one (a refused live file would
                   otherwise bring back what 2.2a's command still had written): --held-g 1 --pull-g 2 --intent-teach 0 --dmg-reward 0.005,
                   STACK_DIFF=0 SPEED_PAY=0 RAIL_FAR_PAY=0.1 ITEM_FLAT=MH:0.35,RA:0.30,YA:0.15 DODGE_G=1.0 WIN_ADD=0.33 LEVEL_PULL=1.0,
                   AIM3_W=1 AIM3_SIZE_A=0.39 AIM3_SIZE_B=0.355 AIM3_LEAD=1 AIM3_RELOAD=0 (start_values.py checks every name)
    python docs/runs/2.2/2.2b/make_files.py <minutes> <max updates> --items docs/runs/2.2/2.2b/items_22b.json --win-scale-items K --win-scale-fight K"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
SRC = os.path.normpath(os.path.join(HERE, "..", "2.2a"))
sys.path.insert(0, os.path.join(REPO, "sim"))
import judge_guard as JG  # noqa: E402

t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN, UPDATES = sys.argv[1], sys.argv[2]
arg_ = lambda n_, d_=None: sys.argv[sys.argv.index(n_) + 1] if n_ in sys.argv else d_   # noqa: E731
ITEMS = arg_("--items")
KI, KF = float(arg_("--win-scale-items", "1")), float(arg_("--win-scale-fight", "1"))
WARM0 = int(arg_("--warm-start", "26519"))   # (the optimizer's warm-up from 2.2b's own start: 2.2a's update 90 is at minute 26,519.4 of the lineage;
                                             # --fade-start 7214 as it ran, so --lr-warm alone would count from minute 7,214 and do nothing)
assert int(MIN) > 0 and int(UPDATES) > 0, (MIN, UPDATES)
assert ITEMS, "--items: the judge with the items (an accepted fit) is the paid win chance in 2.2b"
IP_ = json.load(open(ITEMS if os.path.isabs(ITEMS) else os.path.join(REPO, ITEMS), encoding="utf-8"))
assert IP_.get("accepted") is True, "--items: the fit was not accepted: no start (the item-blind judge is never the pay)"
assert KI >= 1.0 and KF >= 1.0, "the win scales are at least 1 (change 9: the win part at least the flat part's size)"


def sub(a, b, n=1):
    global t
    assert t.count(a) == n, (a, t.count(a))
    t = t.replace(a, b)


def setv(name, val):
    """a `set NAME=...` line of the command to this value (it must be there once)"""
    global t
    k_ = len(re.findall(r"^set {}=.*$".format(name), t, re.M))
    assert k_ == 1, (name, k_)
    t = re.sub(r"^set {}=.*$".format(name), "set {}={}".format(name, val), t, flags=re.M)


lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
OUT_ARGS = " --outlook 1 --out-kinds seg,ret,all8,win8,win5,segw,winit8 --out22 1 --map-sense 1 --map-sense-init %ROOT%\\data\\sim_runs\\space\\mapsense_start.pt "
assert c.count(OUT_ARGS) == 1, "2.2a's rater of options' arguments not found"
c = c.replace(OUT_ARGS, " ")
c = re.sub(r"--minutes \d+ --max-updates \d+ --gamma ", "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES), c)
for a_, b_ in (("--env duel_env_ffa20e ", "--env duel_env_ffa22b "), ("--run duel_gru_2_2a ", "--run duel_gru_2_2b "),
               ("--held-g 0 ", "--held-g 1 "), ("--pull-g 0 ", "--pull-g 2 "), ("--intent-teach 9.13 ", "--intent-teach 0 "),
               ("--dmg-reward 0.0055 ", "--dmg-reward 0.005 "), ("--head2-pay all ", "--head2-pay items_win ")):
    assert c.count(a_) == 1, a_
    c = c.replace(a_, b_)
NEW_ARGS = ("--fight22 1 --fight22-lr 1e-4 --fgt-g 0 --fgt-w 0 --practice-p 0 --h2-wadd 1 --fgt-gate -30 --win-scale-items {:g} --win-scale-fight {:g} "
            "--h2-choice-warm 10 --lr-warm 60 --lr-warm-start {} ".format(KI, KF, WARM0))
assert c.count(" %LEARN% >> ") == 1
c = c.replace(" %LEARN% >> ", " " + NEW_ARGS + "%LEARN% >> ")
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_2a", "duel_gru_2_2b") for x in lines)   # (the history lines stay as written)
sub("set DESC_OX=1\n", "")
for n_, v_ in (("STACK_DIFF", "0"), ("SPEED_PAY", "0"), ("RAIL_FAR_PAY", "0.1"), ("ITEM_FLAT", "MH:0.35,RA:0.30,YA:0.15"), ("DODGE_G", "1.0"),
               ("AIM3_W", "1"), ("AIM3_SIZE_A", "0.39"), ("AIM3_SIZE_B", "0.355"), ("AIM3_LEAD", "1"), ("AIM3_RELOAD", "0"), ("PRO_START_P", "0.15")):
    setv(n_, v_)
t = re.sub(r"^set JUDGE_ITEMS=.*$", "set JUDGE_ITEMS=%ROOT%\\\\{}".format(ITEMS.replace("/", "\\\\")), t, count=1, flags=re.M)
NEW_SETS = ("set FIGHT=1\nset OUT_LIVE=1.5\nset NEAR_MISS=1\nset JUDGE_PAY=1\nset FIGHT_START_P=0.20\nset WIN_ADD=0.33\nset LEVEL_PULL=1.0\n"
            "set CONTACT_FREE=1.0\nset COST_FIRE_W=0\nset COST_JERK_W=0\n")   # (the last three unset in 2.2a's command: 0, 1, 1 had its live file been refused)
sub("set ROOT=%~dp0..\\..\\..\\..\ncd /d %ROOT%\n", "set ROOT=%~dp0..\\..\\..\\..\ncd /d %ROOT%\n" + NEW_SETS)
sub("rem the repo root: this file lives in docs\\runs\\2.2\\2.2a\\",
    "rem ==== 2.2b (owner, 2026-11-17: a fight network beside the item picker; docs/runs/2.2/2.2b/CARD.md): from 2.2a's update 90 (list 22b, the rater "
    "out, the fight network added: tools/inputs21.py convert, tools/fight22_init.py layout, norm). 2.2a's command with: run duel_gru_2_2b; --minutes {}; "
    "--max-updates {}; --env duel_env_ffa22b; the rater of options and the map sense out; {}--head2-pay items_win; the command's start values the live "
    "file's (--held-g 1 --pull-g 2 --intent-teach 0 --dmg-reward 0.005 and the sets); {}JUDGE_ITEMS={}; PRO_START_P 0.35 -> 0.15. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.2\\2.2b\\".format(MIN, UPDATES, NEW_ARGS, NEW_SETS.replace("\n", " ").replace("set ", ""), ITEMS))
t = "\n".join(x if (x.startswith("rem") or x.startswith("set JUDGE_ITEMS=")) else x.replace("docs\\runs\\2.2\\2.2a\\", "docs\\runs\\2.2\\2.2b\\")
              for x in t.split("\n"))
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0]
for x_ in ("--outlook", "--out22", "--map-sense", "--obs-half", "--pfsp", "--wrule", "--keep-g", "--cmb-g", "--ins", "--old-judge-replay"):
    assert x_ + " " not in cl_[0], x_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
assert not re.search(r"^set (DESC_OX|COMBAT|INSTR|KEEP_ZONE|KEEP_SIG)=", t, re.M)
assert not any("duel_gru_2_2a" in x for x in t.split("\n") if not x.startswith("rem")), "a line still names 2.2a's run"
env_ = {m_.group(1): m_.group(2).strip() for m_ in re.finditer(r"(?im)^set ([A-Za-z0-9_]+)=(.*)$", t)}
ok_, why_ = JG.check(env_, None, REPO)                                     # (the judge's guard: the paid win part reads the items)
assert ok_, why_
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
assert "call %~dp0aim2_env.cmd" in t
open(os.path.join(HERE, "aim2_env.cmd"), "wb").write(open(os.path.join(SRC, "aim2_env.cmd"), "rb").read())   # (2.2a's, as it is)
print("wrote train.cmd: --minutes {} --max-updates {}; {}; {}; the judge's guard: {}".format(MIN, UPDATES, NEW_ARGS, NEW_SETS.replace("\n", " "), why_))
