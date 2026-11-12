r"""2.1a's train.cmd (owner, 2026-11-12: the head opened once, in 2.1's form, from 1.8a's save of update 50; docs/runs/2.1/2.1a/CARD.md):
1.8a's CURRENT command (docs/runs/1.8/1.8a/train.cmd as it last ran, phase 2), every setting as it ran, with:
  --run duel_gru_2_1a, --minutes as given
  set INTENT_SWITCH=0.02, set WEAPON_OWN=0    as 1.8a's update 50 played them (its phase 1). Both are LIVE since this build: the ramp
                           leaves them there for the whole run (the owner.s schedule of 11-12 gives them no dial), so there is no restart
  --env duel_env_ffa21     the input list 21 = list 18 + the hands' 48 instruction columns (852 inputs: the hands 844, the brain 691)
  set INSTR=1              the instruction in the simulator (no instruction given: the simulator as before)
  set INS_BIND=1           the weapon an instruction asks for is binding (owner, 11-12); --ins-bind 1
  set INS_NO_NONE=1        the row "none" is never offered to the head (owner, 11-12): a seat whose coin is on is always under a real order
  set INS_WAY=1            the receiver's side of spam: three more numbers a row (a watched spam point on his way; owner, 11-12)
  --branch-long-spam 1     every branch on a spam row is read over the 30-second window (owner, 11-12)
  set KNOWN_TRUTH=1, SPAWN_TRUTH=1, HEAD_PAY_TRUTH=1   labels only (the brain's two questions; the judge's change in win chance)
  set DRILL_INS_P=0        the drills' share at the start (live: the ramp opens it over updates 0 to 30)
  set FIN_RATE=...         his own damage a second by weapon and distance, measured on the start (tools/run/fin_rate.py; --fin <its json>);
                           without --fin the simulator's placeholder table stands and start.ps1 refuses
  --map-sense 1 --map-sense-init <the run's keep\mapsense_start.pt, made at the start> --appraise 1 --known-odds 1 --spawn-odds 1
                           the lessons nothing plays from, on from update 0
  --branch 1 --branch-p 0 --branch-ins 1 --branch-long 1 --branch-long-p 0 --branch-wpn-p 0
                           the frozen-moment rounds: every share at 0 at the start (live BRANCH_P, BRANCH_LONG_P, BRANCH_WPN_P)
  --ins 1 --ins-g 0 --ins-teach 1 --ins-pg 0 --ins-quiet 1 --ins-ms 1 --ins-pay-win 1
                           the head's choice of an instruction: its share 0 at the start (live INS_G), its lesson on, the game's pay on
                           its choice 0 (live H2_INS_PG), the head's side paid by the win chance alone (owner, 11-11)
Unchanged and worth saying: --head2-pg 1 with live H2_PG at 0 for the whole run (the old head's target credit never opens: the
instruction's rows do that job), --head2-pay all (the old head's own value; the owner's call), --keep-g 0, --gate-open 0 (the instruction's
token has its own live gate, INS_GATE). Everything that moves is live (live.json, ramp_21a.py).
    python docs/runs/2.1/2.1a/make_files.py <minutes> [--fin <fin_rate.json>] [--base <1.8a's train.cmd>] [--out <train.cmd>]"""
import argparse
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DROOT = os.environ.get("QLBOT_ROOT") or ROOT                 # (a worktree without data: the repo that has it, and 1.8a's current command)
RUN = "duel_gru_2_1a"
SETS = dict(INTENT_SWITCH="0.02", WEAPON_OWN="0")
NEW_SETS = ["INSTR=1", "INS_NO_NONE=1", "INS_WAY=1", "INS_BIND=1", "KNOWN_TRUTH=1", "SPAWN_TRUTH=1", "HEAD_PAY_TRUTH=1", "DRILL_INS_P=0"]
ARGS = (("--env", "duel_env_ffa18", "duel_env_ffa21"),)
NEW_ARGS = ("--map-sense 1 --map-sense-init %ROOT%\\data\\sim_runs\\duel_gru_2_1a\\keep\\mapsense_start.pt --appraise 1 --known-odds 1 --spawn-odds 1 "
            "--branch 1 --branch-p 0 --branch-ins 1 --branch-long 1 --branch-long-spam 1 --branch-long-p 0 --branch-wpn-p 0 "
            "--ins 1 --ins-g 0 --ins-teach 1 --ins-pg 0 --ins-quiet 1 --ins-ms 1 --ins-pay-win 1 --ins-bind 1")
# (tools/run/check_settings.py --allow: what may differ from 1.8a's current command, and nothing else)
ALLOW = ("--run,--minutes,--env,INTENT_SWITCH,WEAPON_OWN,INSTR,INS_NO_NONE,INS_WAY,--branch-long-spam,INS_BIND,KNOWN_TRUTH,SPAWN_TRUTH,HEAD_PAY_TRUTH,DRILL_INS_P,FIN_RATE,"
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
    n_ = len(s.replace(";", ",").split(","))                 # (the weapons joined by ';', a weapon's three distances by ',')
    assert n_ == 27 and all(float(x_) >= 0 for x_ in s.replace(";", ",").split(",")), "FIN_RATE: 27 numbers (9 weapons x 3 distances), got {}".format(n_)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("minutes", type=int)
    ap.add_argument("--fin", default="")
    ap.add_argument("--base", default=os.path.join(DROOT, "docs", "runs", "1.8", "1.8a", "train.cmd"))
    ap.add_argument("--out", default=os.path.join(HERE, "train.cmd"))
    a = ap.parse_args()
    assert a.minutes > 0
    t = open(a.base, encoding="ascii").read().replace("\r\n", "\n")
    assert "phase 2" in t and len(re.findall(r"^set WEAPON_OWN=1$", t, re.M)) == 1 and len(re.findall(r"^set INTENT_SWITCH=0$", t, re.M)) == 1, \
        "the base is not 1.8a's command as it last ran (phase 2): " + a.base
    for n_, v_ in SETS.items():
        assert len(re.findall(r"^set {}=\S*$".format(n_), t, re.M)) == 1, n_
        t = re.sub(r"^set {}=\S*$".format(n_), "set {}={}".format(n_, v_), t, flags=re.M)
    for n_ in ("SHOT_COST", "BLIND_FIRE_W", "BLIND_RL_DMG"):                    # (no firing cost: as 1.8a's command has them)
        assert re.findall(r"^set {}=(\S*)$".format(n_), t, re.M) == ["0"], n_
    new = list(NEW_SETS) + (["FIN_RATE=" + fin_string(a.fin)] if a.fin else [])
    for x_ in new:
        assert not re.findall(r"^set {}=".format(x_.split("=")[0]), t, re.M), "1.8a's command has {} already".format(x_)
    assert t.count("set AIM3_RELOAD=1\n") == 1
    t = t.replace("set AIM3_RELOAD=1\n", "set AIM3_RELOAD=1\nrem (2.1a) the instruction, its binding weapon, the labels, the drills' share at the start, his own damage a second\n"
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
    assert c.count(" %LEARN% >> ") == 1 and "--ins " not in c and "--branch " not in c and "--map-sense " not in c
    c = c.replace(" %LEARN% >> ", " " + NEW_ARGS + " %LEARN% >> ")
    lines[cl_[0]] = c
    t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_1_8a", RUN) for x in lines)      # (the history lines stay as written)
    old_ = "rem the repo root: this file lives in docs\\runs\\1.8\\1.8a\\"
    assert t.count(old_) == 1, "the base's root line"
    t = t.replace(old_, "rem ==== 2.1a (owner, 2026-11-12; docs/runs/2.1/2.1a/CARD.md): from 1.8a's save of update 50 brought to the input list 21, the head's "
                  "choice of an instruction added at zero effect. 1.8a's command as it last ran with: run {}; --minutes; set {}; set {}; --env duel_env_ffa21; {}. "
                  "The dials are live (ramp_21a.py). Made by make_files.py.\n"
                  "rem the repo root: this file lives in docs\\runs\\2.1\\2.1a\\".format(
                      RUN, ", ".join("{}={}".format(k_, v_) for k_, v_ in SETS.items()), ", ".join(new), NEW_ARGS))
    t = t.replace("docs\\runs\\1.8\\1.8a\\", "docs\\runs\\2.1\\2.1a\\")
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
    print("train.cmd written: {} minutes; set {}; {}{}".format(a.minutes, ", ".join("{}={}".format(k_, v_) for k_, v_ in SETS.items()), ", ".join(new),
                                                               "" if a.fin else "; NO FIN_RATE (the placeholder table: not for a start)"))
    print("check_settings: --allow=" + ALLOW)


if __name__ == "__main__":
    main()
