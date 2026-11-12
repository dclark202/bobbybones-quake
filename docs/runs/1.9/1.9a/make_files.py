r"""1.9a's train.cmd (owner, 2026-11-12: the head in charge from 1.8a's end, 2.1's instruction in a smaller form; docs/runs/1.9/1.9a/CARD.md):
1.8a's CURRENT command (docs/runs/1.8/1.8a/train.cmd as it last ran, phase 2: its update 190 played it), every setting as it ran, with:
  --run duel_gru_1_9a, --minutes as given
  --env duel_env_ffa21     the input list 21 = list 18 + the hands' 48 instruction columns (852 inputs: the hands 844, the brain 691)
  set INSTR=1              the instruction in the simulator (no instruction given: the simulator as before)
  set INS_BIND=1           the weapon an instruction asks for is binding; --ins-bind 1
  set INS_NO_NONE=1        the row "none" is never offered to the head: a seat whose coin is on is always under a real order
  set INS_WAY=1            the receiver's side of spam (2.1a's rows, 67 wide)
  set HEAD_PAY_TRUTH=1     the head's stream: the judge's change in win chance (a label)
  set JUDGE_ITEMS=<file>   ... with the next mega's and red armor's race in it (tools/run/fit_items.py; the head's only: owner, 11-12)
  set FOLLOW_PAY=0         the hands' pay for carrying an instruction out: live, the ramp opens it
  set DRILL_INS_P=0        no drills (1.9a has none)
  set FIGHT_TRUTH=1        the fight odds' labels (a label only: how a fight that was on ended); --fight-odds 1 --fight-warm 0: the
                           readout learns from update 0 (1.7b's setting); the head reads it (its part "fight", tools/b19_init.py)
  set FIN_RATE=...         his own damage a second by weapon and distance, measured on the start (tools/run/fin_rate.py; --fin <its json>)
  --appraise 1 --branch 1 --branch-p 0 --branch-ins 1    the trainer's --ins needs both; no frozen moment is ever played (BRANCH_P 0 all
                           run), so the appraisals never warm and nothing is taught toward them
  --ins 1 --ins-g 0 --ins-teach 0 --ins-copy 1 --ins-pg 0 --ins-quiet 0 --ins-ms 0 --ins-pay-win 1 --ins-bind 1
                           the head's choice of an instruction: its share 0 at the start (live INS_G), the copy lesson on (live INS_COPY),
                           the game's pay on its choice 0 (live H2_INS_PG), its side paid by the win chance alone; no quiet, no map sense
Unchanged and worth saying: --head2-pg 1 with live H2_PG set to 0 at the start (the old head's target credit closed: the instruction's rows
do that job), --head2-pay all (the old head's own value; it gets no credit), --keep-g 0 (the lock does not act on a seat under the head's
instruction), --gate-open 0 (the instruction's token has its own live gate, INS_GATE). Everything that moves is live (ramp_19a.py).
    python docs/runs/1.9/1.9a/make_files.py <minutes> --fin <fin_rate.json> --items <items.json> [--base <1.8a's train.cmd>] [--out <train.cmd>]"""
import argparse
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DROOT = os.environ.get("QLBOT_ROOT") or ROOT
RUN = "duel_gru_1_9a"
NEW_SETS = ["INSTR=1", "INS_NO_NONE=1", "INS_WAY=1", "INS_BIND=1", "HEAD_PAY_TRUTH=1", "FOLLOW_PAY=0", "DRILL_INS_P=0", "FIGHT_TRUTH=1"]
ARGS = (("--env", "duel_env_ffa18", "duel_env_ffa21"),)
NEW_ARGS = ("--fight-odds 1 --fight-warm 0 --appraise 1 --branch 1 --branch-p 0 --branch-ins 1 "
            "--ins 1 --ins-g 0 --ins-teach 0 --ins-copy 1 --ins-pg 0 --ins-quiet 0 --ins-ms 0 --ins-pay-win 1 --ins-bind 1")
# (tools/run/check_settings.py --allow: what may differ from 1.8a's current command, and nothing else)
ALLOW = ("--run,--minutes,--env,FIGHT_TRUTH,--fight-odds,--fight-warm,INSTR,INS_NO_NONE,INS_WAY,INS_BIND,HEAD_PAY_TRUTH,JUDGE_ITEMS,FOLLOW_PAY,DRILL_INS_P,FIN_RATE,"
         "--appraise,--branch,--branch-p,--branch-ins,--ins,--ins-g,--ins-teach,--ins-copy,--ins-pg,--ins-quiet,--ins-ms,--ins-pay-win,--ins-bind")


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
    ap.add_argument("--items", default="", help="the items' judge (tools/run/fit_items.py's json); written as JUDGE_ITEMS with its full path")
    ap.add_argument("--base", default=os.path.join(DROOT, "docs", "runs", "1.8", "1.8a", "train.cmd"))
    ap.add_argument("--out", default=os.path.join(HERE, "train.cmd"))
    a = ap.parse_args()
    assert a.minutes > 0
    t = open(a.base, encoding="ascii").read().replace("\r\n", "\n")
    assert "phase 2" in t and len(re.findall(r"^set WEAPON_OWN=1$", t, re.M)) == 1 and len(re.findall(r"^set INTENT_SWITCH=0$", t, re.M)) == 1, \
        "the base is not 1.8a's command as it last ran (phase 2): " + a.base
    for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost: as 1.8a's command has them)
        assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
    assert re.findall(r"^set WIN_JUDGE=", t, re.M), "1.8a's command has no WIN_JUDGE: the head's stream needs the judge"
    new = list(NEW_SETS) + (["FIN_RATE=" + fin_string(a.fin)] if a.fin else []) \
        + (["JUDGE_ITEMS=" + os.path.abspath(a.items)] if a.items else [])
    if a.items:
        import sys
        sys.path.insert(0, os.path.join(ROOT, "sim"))
        import win_judge as wj_
        wj_.items_load(a.items)                                                  # (refuses a file that breaks the axioms)
    for x_ in new:
        assert not re.findall(r"^set {}=".format(x_.split("=")[0]), t, re.M), "1.8a's command has {} already".format(x_)
    assert t.count("set AIM3_RELOAD=1\n") == 1
    t = t.replace("set AIM3_RELOAD=1\n", "set AIM3_RELOAD=1\nrem (1.9a) the instruction, its binding weapon, the head's stream with the items, the follow pay (live), his own damage a second\n"
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
    assert c.count(" %LEARN% >> ") == 1 and "--ins " not in c and "--branch " not in c and "--appraise " not in c
    c = c.replace(" %LEARN% >> ", " " + NEW_ARGS + " %LEARN% >> ")
    lines[cl_[0]] = c
    t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_1_8a", RUN) for x in lines)      # (the history lines stay as written)
    old_ = "rem the repo root: this file lives in docs\\runs\\1.8\\1.8a\\"
    assert t.count(old_) == 1, "the base's root line"
    t = t.replace(old_, "rem ==== 1.9a (owner, 2026-11-12; docs/runs/1.9/1.9a/CARD.md): from 1.8a's end (its save of update 190) brought to the input list 21, "
                  "the head's choice of an instruction added at zero effect. 1.8a's command as it last ran with: run {}; --minutes; --env duel_env_ffa21; {}; {}. "
                  "The dials are live (ramp_19a.py). Made by make_files.py.\n"
                  "rem the repo root: this file lives in docs\\runs\\1.9\\1.9a\\".format(RUN, ", ".join(new), NEW_ARGS))
    t = t.replace("docs\\runs\\1.8\\1.8a\\", "docs\\runs\\1.9\\1.9a\\")
    cl_ = [x for x in t.split("\n") if "train_duel_rnn.py" in x and not x.startswith("rem")]
    assert len(cl_) == 1 and "/affinity C03C3 " in cl_[0] and "--minutes {} --gamma ".format(a.minutes) in cl_[0] and "--run {} ".format(RUN) in cl_[0]
    assert "--pfsp" not in cl_[0] and "--opt-cold-ok" not in cl_[0] and "--max-updates" not in cl_[0] and "--wrule" not in cl_[0]
    assert "--gate-open 0 " in cl_[0] and "--keep-g 0 " in cl_[0] and "--head2-wpg 0 " in cl_[0] and "--opt-small-items 1 " in cl_[0]
    assert "--head2-pg 1 " in cl_[0] and "--head2-pay all " in cl_[0] and "--env duel_env_ffa21 " in cl_[0] and "--ins-pay-win 1 --ins-bind 1 " in cl_[0]
    for k_ in ("OPENBLAS_NUM_THREADS=1", "PYTHONFAULTHANDLER=1"):
        assert re.findall(r"^set {}$".format(k_), t, re.M), k_
    live_ = [x for x in t.split("\n") if not x.startswith("rem")]
    assert not any("duel_gru_1_8a" in x for x in live_)
    tmp = a.out + ".tmp"
    open(tmp, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    os.replace(tmp, a.out)
    aim_ = os.path.join(os.path.dirname(a.out), "aim2_env.cmd")
    if not os.path.exists(aim_):
        shutil.copy2(os.path.join(os.path.dirname(a.base), "aim2_env.cmd"), aim_)
    print("train.cmd written: {} minutes; {}{}{}".format(a.minutes, ", ".join(x_[:60] for x_ in new),
                                                       "" if a.fin else "; NO FIN_RATE (the placeholder table: not for a start)",
                                                       "" if a.items else "; NO JUDGE_ITEMS (the head's judge without the items: not for a start)"))
    print("check_settings: --allow=" + ALLOW)


if __name__ == "__main__":
    main()
