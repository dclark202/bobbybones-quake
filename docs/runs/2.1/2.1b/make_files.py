r"""2.1b's train.cmd (owner, 2026-11-14: the 8-second lock replaced by a learned keep choice, step by step, in ONE run; docs/runs/2.1/2.1b/CARD.md,
docs/runs/2.1/PLAN_FROM_20E.md): 2.0e's command, every setting as it ran, with:
  --run duel_gru_2_1b, --minutes and --max-updates as given
  set KEEP_ZONE=1  the keep choice split by zone: its zone layer in contact and at arrivals, its quiet layer in quiet (else the lock rule)
  set KEEP_SIG=1   the target's change signals (keep_feat's tail: the quiet layer's and the stay value's inputs)
  in: --keep-g 0 --keepq-g 0 (both shares shut: the lock decides everywhere, as 2.0e's end; live KEEP_G, KEEPQ_G: ramp_21b.py on steps.json)
      --stay 1 (the stay value, sim/stay.py, taught from the keep forks; live STAY_W)
      --keep-teach 1 (the keep choice's silent lesson toward the stay value's sign; live KEEP_TEACH)
      --branch 1 --branch-p 0 --branch-keep 1 --branch-zone-p 0.5 --branch-long 1 --branch-long-p 0 --branch-long-secs 30 --branch-win 320
      --branch-hold 40 --branch-log 1 --branch-keep-long quiet (the frozen moments: keep against a new draw, the quiet ones read over 30 s;
      live BRANCH_P, BRANCH_ZONE_P)
      --map-sense 1 --map-sense-init %ROOT%\data\sim_runs\duel_gru_2_1b\keep\mapsense_start.pt (the map sense learns silently, nothing reads
      it: owner "it learns silently in 2.1 either way"; its start copied there by start.ps1 from data\sim_runs\space\mapsense_start.pt)
Kept from 2.0e: AIM3's set lines (its start values: live.json carries 2.0e's end values), KNOCK_QL=1, KNOCK_NOW=1, DODGE_IN=1, DODGE_G=0, the lock
(INTENT_HOLD=8, CONTACT_FREE live), no firing cost, --habit-p 0, --brain-fade 0, --gate-open 0, --env duel_env_ffa20e, the cores (0xC03C3).
    python docs/runs/2.1/2.1b/make_files.py <minutes> <max updates>"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "2.0", "2.0e"))
t = open(os.path.join(SRC, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
MIN, UPDATES = sys.argv[1], sys.argv[2]
assert int(MIN) > 0 and int(UPDATES) > 0, (MIN, UPDATES)
NEW_ARGS = ("--keep-g 0 --keepq-g 0 --stay 1 --keep-teach 1 --branch 1 --branch-p 0 --branch-keep 1 --branch-zone-p 0.5 --branch-long 1 "
            "--branch-long-p 0 --branch-long-secs 30 --branch-win 320 --branch-hold 40 --branch-log 1 --branch-keep-long quiet "
            "--map-sense 1 --map-sense-init %ROOT%\\data\\sim_runs\\duel_gru_2_1b\\keep\\mapsense_start.pt ")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


sub("\nset DODGE_G=0\n", "\nset DODGE_G=0\n"
    "rem (2.1b) the keep choice by zone (contact and arrivals: its zone layer; quiet: its quiet layer or the lock rule) and the target's change signals\n"
    "set KEEP_ZONE=1\nset KEEP_SIG=1\n")
lines = t.split("\n")
cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1
c = lines[cl_[0]]
assert len(re.findall(r"--minutes \d+ --max-updates \d+ --gamma ", c)) == 1, "2.0e's --minutes / --max-updates not found"
c = re.sub(r"--minutes \d+ --max-updates \d+ --gamma ", "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES), c)
assert c.count(" %LEARN% >> ") == 1
c = c.replace(" %LEARN% >> ", " " + NEW_ARGS + "%LEARN% >> ")
lines[cl_[0]] = c
t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_0e", "duel_gru_2_1b") for x in lines)   # (the history lines stay as written)
sub("rem the repo root: this file lives in docs\\runs\\2.0\\2.0e\\",
    "rem ==== 2.1b (owner, 2026-11-14: the lock replaced by a learned keep choice, step by step, in one run; docs/runs/2.1/2.1b/CARD.md): from 2.0e's "
    "end with the keep choice and its quiet layer added at zero, shares 0 (tools/keep_init.py add --start zero --quiet 1). 2.0e's command with: run "
    "duel_gru_2_1b; --minutes {}; --max-updates {}; set KEEP_ZONE=1, KEEP_SIG=1; {}(live KEEP_G, KEEPQ_G, KEEP_TEACH, STAY_W, BRANCH_P, "
    "BRANCH_ZONE_P; the shares opened by ramp_21b.py only on the owner's steps.json). Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\2.1\\2.1b\\".format(MIN, UPDATES, NEW_ARGS))
t = t.replace("docs\\runs\\2.0\\2.0e\\", "docs\\runs\\2.1\\2.1b\\")
cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --max-updates {} --gamma ".format(MIN, UPDATES) in cl_[0]
for x_ in ("--pfsp", "--opt-cold-ok", "--wrule", "--keep-freeze", "--cmb-g", "--padd", "--fadd", "--head2-fpg", "--pass-odds", "--space-read",
           "--ins", "--appraise", "--freeze-choice"):
    assert x_ + " " not in cl_[0], x_
for x_ in NEW_ARGS.split(" --"):                                          # every new argument once
    x_ = x_.strip().split(" ")[0]
    x_ = x_ if x_.startswith("--") else "--" + x_
    assert cl_[0].count(" " + x_ + " ") == 1, x_
assert "--gate-open 0 " in cl_[0] and "--run duel_gru_2_1b " in cl_[0] and "--habit-p 0 " in cl_[0] and "--resume " in cl_[0]
assert "--head2 1 " in cl_[0] and "--head2-add 1 " in cl_[0] and "--head2-wpg 1 " in cl_[0] and "--head2-l2 0.01" in cl_[0]
assert "--env duel_env_ffa20e " in cl_[0] and "--brain-fade 0 " in cl_[0] and "--opt-small-items 1 " in cl_[0] and "--dmg-reward 0.0055 " in cl_[0]
for s_ in ("INTENT_HOLD=8", "WEAPON_OWN=1", "INTENT_SWITCH=0", "AIM3=1", "AIM3_W=0", "AIM3_SIZE_A=1", "AIM3_SIZE_B=0", "AIM3_PURSUIT_TAU=0.125",
           "AIM3_PURSUIT_GAIN=1.0", "AIM3_FIX_TAU=0.05", "AIM3_LEAD=0", "AIM3_RELOAD=1", "KNOCK_QL=1", "KNOCK_NOW=1", "DODGE_IN=1", "DODGE_G=0",
           "KEEP_ZONE=1", "KEEP_SIG=1"):
    assert t.count("\nset {}\n".format(s_)) == 1, s_
for s_ in ("COMBAT", "SPACE_IN", "SPACE_TRUTH", "EDGE_PAY", "COVER_PAY", "SPACE_GATE", "INSTR", "AIM3_HAND"):   # nothing of 1.7, 2.0b, 2.1a, no hand lag
    assert not re.search(r"^set {}=".format(s_), t, re.M), s_
for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost)
    assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
live_ = "\n".join(x for x in t.split("\n") if not x.startswith("rem"))
assert "2_0e" not in live_ and "2.0e" not in live_
tmp = os.path.join(HERE, "train.cmd.tmp")
open(tmp, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
os.replace(tmp, os.path.join(HERE, "train.cmd"))
shutil.copy2(os.path.join(SRC, "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("train.cmd written: {} minutes, {} updates; list 20e; KEEP_ZONE=1 KEEP_SIG=1; the keep choice and its quiet layer at share 0, the stay value "
      "and the keep lesson on, the keep forks on (BRANCH_P live), the map sense learning silently".format(MIN, UPDATES))
