r"""2.1a's train.cmd (owner, 2026-11-13: "freeze decisions; blend 2.0 and 2.1 into one ... call it 2.1a"; docs/runs/2.1/2.1a/CARD.md):
2.0d's command (= 1.7a's with AIM3's seven set lines, the corrected knockback, the dodge inputs, list 20d), every setting as it ran, with:
  --run duel_gru_2_1a, --minutes as given
  --env duel_env_ffa21d    the input list 21d = list 20d + the hands' 48 instruction columns (869 inputs: the hands 861, the brain 691)
  --freeze-choice 1        the head's decisions held as 1.7a's update 90 has them: his target, the weapon key, the keep choice (owner, 11-13)
  set INSTR=1              the instruction in the simulator (given on drill seats only: INS_G 0, no game seat is under one)
  set INS_BIND=1           the weapon an instruction names is binding (owner, 11-12): on drill seats only here; --ins-bind 1
  set INS_NO_NONE=1        the row "none" is never offered to the head (owner, 11-12)
  set INS_WAY=1            the receiver's side of spam: three more numbers a row (owner, 11-12)
  set KNOWN_TRUTH=1, SPAWN_TRUTH=1, HEAD_PAY_TRUTH=1   labels only (the brain's two questions; the judge's change in win chance)
  set DRILL_INS_P=0        the drills' share at the start (live: the ramp opens it over updates 30 to 60)
  set FIN_RATE=...         his own damage a second by weapon and distance, measured on 1.7a's update 90 under AIM3's end values and the
                           corrected knockback (tools/run/fin_rate.py; --fin <its json>); without --fin the placeholder stands, start.ps1 refuses
  --map-sense 1 --map-sense-init <the run's keep\mapsense_start.pt> --appraise 1 --known-odds 1 --spawn-odds 1   the lessons nothing plays from
  --branch 1 --branch-p 0 --branch-ins 1 --branch-long 1 --branch-long-spam 1 --branch-long-p 0 --branch-wpn-p 0   the frozen moments, at 0
  --ins 1 --ins-g 0 --ins-teach 1 --ins-pg 0 --ins-quiet 1 --ins-ms 1 --ins-pay-win 1 --ins-bind 1
                           the head's choice of an instruction: share 0 the whole run (live INS_G), taught in shadow, paid by the win chance alone
Kept from 2.0d's command: KNOCK_QL=1 KNOCK_NOW=1 (the corrected knockback), DODGE_IN=1 DODGE_G=0, AIM3 at its start values with
AIM3_FIX_TAU 0.05 (the ramp moves the rest), COMBAT=1 (the order's ten inputs; the order never asked), --keep-g 1, --pass-odds 0,
--habit-p 0, --head2-wpg 1 (held by --freeze-choice), --gate-open 0. Everything that moves is live (live.json, ramp_21a.py).
    python docs/runs/2.1/2.1a/make_files.py <minutes> [--fin <fin_rate.json>] [--out <train.cmd>]"""
import argparse
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
RUN = "duel_gru_2_1a"
BASE = os.path.join(ROOT, "docs", "runs", "2.0", "2.0d", "train.cmd")
NEW_SETS = ["INSTR=1", "INS_NO_NONE=1", "INS_WAY=1", "INS_BIND=1", "KNOWN_TRUTH=1", "SPAWN_TRUTH=1", "HEAD_PAY_TRUTH=1", "DRILL_INS_P=0"]
ARGS = (("--env", "duel_env_ffa20d", "duel_env_ffa21d"),)
NEW_ARGS = ("--freeze-choice 1 "
            "--map-sense 1 --map-sense-init %ROOT%\\data\\sim_runs\\duel_gru_2_1a\\keep\\mapsense_start.pt --appraise 1 --known-odds 1 --spawn-odds 1 "
            "--branch 1 --branch-p 0 --branch-ins 1 --branch-long 1 --branch-long-spam 1 --branch-long-p 0 --branch-wpn-p 0 "
            "--ins 1 --ins-g 0 --ins-teach 1 --ins-pg 0 --ins-quiet 1 --ins-ms 1 --ins-pay-win 1 --ins-bind 1")
# (tools/run/check_settings.py --allow: what may differ from 1.7a's command, and nothing else: 2.0d's list and 2.1a's)
ALLOW_20D = ("--run,--minutes,--keep-g,--gate-open,--pass-odds,--habit-p,--env,--brain-fade,AIM3,AIM3_W,AIM3_SIZE_A,AIM3_SIZE_B,AIM3_PURSUIT_TAU,"
             "AIM3_PURSUIT_GAIN,AIM3_FIX_TAU,AIM3_LEAD,AIM3_RELOAD,KNOCK_QL,KNOCK_NOW,DODGE_IN,DODGE_G")
ALLOW = ALLOW_20D + (",--freeze-choice,INSTR,INS_NO_NONE,INS_WAY,--branch-long-spam,INS_BIND,KNOWN_TRUTH,SPAWN_TRUTH,HEAD_PAY_TRUTH,DRILL_INS_P,FIN_RATE,"
                     "--map-sense,--map-sense-init,--appraise,--known-odds,--spawn-odds,--branch,--branch-p,--branch-ins,--branch-long,--branch-long-p,"
                     "--branch-wpn-p,--ins,--ins-g,--ins-teach,--ins-pg,--ins-quiet,--ins-ms,--ins-pay-win,--ins-bind")


def fin_string(path):
    """the FIN_RATE line's value from tools/run/fin_rate.py's json (its own string, or the table's 27 numbers)"""
    d = json.load(open(path, encoding="utf-8"))
    s = d.get("FIN_RATE") or d.get("env") or ""
    if not s:
        t = d.get("table") or d.get("rate")
        s = ",".join("{:g}".format(float(x)) for row in t for x in row)
    s = s.split("=", 1)[1] if s.startswith("FIN_RATE=") else s
    n_ = len(s.replace(";", ",").split(","))
    assert n_ == 27 and all(float(x_) >= 0 for x_ in s.replace(";", ",").split(",")), "FIN_RATE: 27 numbers (9 weapons x 3 distances), got {}".format(n_)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("minutes", type=int)
    ap.add_argument("--fin", default="")
    ap.add_argument("--out", default=os.path.join(HERE, "train.cmd"))
    a = ap.parse_args()
    assert a.minutes > 0
    t = open(BASE, encoding="ascii").read().replace("\r\n", "\n")
    for s_ in ("KNOCK_QL=1", "KNOCK_NOW=1", "DODGE_IN=1", "DODGE_G=0", "COMBAT=1", "AIM3=1", "AIM3_FIX_TAU=0.05", "AIM3_LEAD=0", "AIM3_RELOAD=1"):
        assert t.count("\nset {}\n".format(s_)) == 1, "2.0d's command lacks " + s_
    for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost: as 2.0d's command has them)
        assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
    new = list(NEW_SETS) + (["FIN_RATE=" + fin_string(a.fin)] if a.fin else [])
    for x_ in new:
        assert not re.findall(r"^set {}=".format(x_.split("=")[0]), t, re.M), "2.0d's command has {} already".format(x_)
    t = t.replace("set DODGE_G=0\n", "set DODGE_G=0\nrem (2.1a) the instruction, its binding weapon, the labels, the drills' share at the start, his own damage a second\n"
                  + "".join("set {}\n".format(x_) for x_ in new))
    lines = t.split("\n")
    cl_ = [i for i, x in enumerate(lines) if "train_duel_rnn.py" in x and not x.startswith("rem")]
    assert len(cl_) == 1
    c = lines[cl_[0]]
    for f_, v0_, v1_ in ARGS:
        assert c.count(" {} {} ".format(f_, v0_)) == 1, f_
        c = c.replace(" {} {} ".format(f_, v0_), " {} {} ".format(f_, v1_))
    assert len(re.findall(r"--minutes \d+ --gamma ", c)) == 1
    c = re.sub(r"--minutes \d+ --gamma ", "--minutes {} --gamma ".format(a.minutes), c)
    assert c.count(" %LEARN% >> ") == 1 and "--ins " not in c and "--branch " not in c and "--map-sense " not in c and "--freeze-choice" not in c
    c = c.replace(" %LEARN% >> ", " " + NEW_ARGS + " %LEARN% >> ")
    lines[cl_[0]] = c
    t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_0d", RUN) for x in lines)      # (the history lines stay as written)
    old_ = "rem the repo root: this file lives in docs\\runs\\2.0\\2.0d\\"
    assert t.count(old_) == 1, "the base's root line"
    t = t.replace(old_, "rem ==== 2.1a, the blend (owner, 2026-11-13: \"freeze decisions; blend 2.0 and 2.1 into one\"; docs/runs/2.1/2.1a/CARD.md): from "
                  "1.7a's update 90 brought to the input list 21d (20d's cut and dodge group, the instruction's columns), the head's choice of an "
                  "instruction added at zero effect, the head's decisions frozen. 2.0d's command with: run {}; --minutes; set {}; --env duel_env_ffa21d; {}. "
                  "The dials are live (ramp_21a.py). Made by make_files.py.\n"
                  "rem the repo root: this file lives in docs\\runs\\2.1\\2.1a\\".format(RUN, ", ".join(new), NEW_ARGS))
    t = t.replace("docs\\runs\\2.0\\2.0d\\", "docs\\runs\\2.1\\2.1a\\")
    cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
    assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --gamma ".format(a.minutes) in cl_[0] and "--run {} ".format(RUN) in cl_[0]
    assert "--pfsp" not in cl_[0] and "--opt-cold-ok" not in cl_[0] and "--max-updates" not in cl_[0] and "--wrule" not in cl_[0]
    assert "--gate-open 0 " in cl_[0] and "--keep-g 1 " in cl_[0] and "--head2-wpg 1 " in cl_[0] and "--opt-small-items 1 " in cl_[0]
    assert "--pass-odds 0 " in cl_[0] and "--habit-p 0 " in cl_[0] and "--env duel_env_ffa21d " in cl_[0] and "--freeze-choice 1 " in cl_[0]
    assert "--ins-pay-win 1 --ins-bind 1 " in cl_[0] and "--brain-fade 0 " in cl_[0]
    for k_ in ("OPENBLAS_NUM_THREADS=1", "PYTHONFAULTHANDLER=1"):
        assert re.findall(r"^set {}$".format(k_), t, re.M), k_
    live_ = [x for x in t.split("\n") if not x.startswith("rem")]
    assert not any("duel_gru_2_0d" in x for x in live_)
    tmp = a.out + ".tmp"
    open(tmp, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    os.replace(tmp, a.out)
    shutil.copy2(os.path.join(os.path.dirname(BASE), "aim2_env.cmd"), os.path.join(os.path.dirname(a.out), "aim2_env.cmd"))
    print("train.cmd written: {} minutes; set {}; --env duel_env_ffa21d; {}{}".format(a.minutes, ", ".join(new), NEW_ARGS,
                                                                                       "" if a.fin else "; NO FIN_RATE (the placeholder table: not for a start)"))
    print("check_settings: --allow=" + ALLOW)


if __name__ == "__main__":
    main()
