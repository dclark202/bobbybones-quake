"""ramp_21a.py on fake files (2026-11-12): a fake run folder in the temp directory (the start's live.json values, a policy.pt and opt.pt,
metrics.jsonl and a check written by this script), the ramp run with a short poll. One CPU process, no simulator, nothing of a run touched.
Checks: each dial follows the clock of metrics.jsonl's LINES on its stage and holds after; the three parts of the owner's schedule; the other names are untouched; the marks are kept once with their optimizers; the ramp stopped and started again with --resume goes
on from its clock and keeps no mark twice; a check under 40% is logged as a MAJOR PROBLEM and the clock not held; a firing cost is a MAJOR
line, the target-switch cost its own line and not a MAJOR one; the old head's credit above 0 is a MAJOR line.
    python docs/runs/2.1/2.1a/ramp_test.py"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ramp_21a", os.path.join(HERE, "ramp_21a.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
D = tempfile.mkdtemp(prefix="ramp21a_")
os.makedirs(os.path.join(D, "watch"))
START = {n_: pre for n_, lo, hi, v0, v1, pre in R.DIALS}
FIXED = dict(H2_PG=0.0, KEEP_G=0.0, DMG_REWARD=0.005, DMG_TAKEN_W=1.0, WIN_ADD=0.33, COST_FIRE_W=0.0, AIM3_W=1.0, INS_TEACH=1.0)
json.dump(dict(START, **FIXED), open(os.path.join(D, "live.json"), "w"))
for f in ("policy.pt", "opt.pt"):
    open(os.path.join(D, f), "w").write("x")
MET, CHK, LIVE, LOG = os.path.join(D, "metrics.jsonl"), os.path.join(D, "watch", "checks_prev.jsonl"), os.path.join(D, "live.json"), os.path.join(D, "watch", "ramp.log")
ok = True
lines = [0]


def check(name, c):
    global ok
    ok = ok and bool(c)
    print(("PASS " if c else "FAIL ") + name, flush=True)


def feed(upto, shot=0.0, switch=-0.3, credit=0.0, own=None):
    with open(MET, "a") as f:
        while lines[0] < upto:
            lines[0] += 1
            u = lines[0] if own is None else own + (lines[0] - feed.base)
            f.write(json.dumps(dict(update=u, frags_per_match_min=2.0, v15=dict(in_hand_games=dict(rl=0.3, lg=0.4, rg=0.05)), shot_cost_per_player_min=shot,
                                    head2=dict(hands=22.0, raw=0.0, cos=0.0, credit=credit), ins_bind=dict(bound=0.2, not_his_pick=0.5, weapon_changes_min=6.0),
                                    pay_terms=dict(per_player_min=dict(dmg_dealt=1.5, dmg_taken=-1.5, frag=1.0, death=-1.0, win_part=0.0, intent_switch=switch),
                                                   size_share=dict(win_part=0.4), total_per_player_min=0.1))) + "\n")
    open(os.path.join(D, "policy.pt"), "w").write("x{}".format(upto))
    open(os.path.join(D, "opt.pt"), "w").write("o{}".format(upto))


feed.base = 0


def live():
    for _ in range(50):
        try:
            return json.load(open(LIVE))
        except (OSError, ValueError):
            time.sleep(0.05)
    raise RuntimeError("live.json not readable")


def wait_clock(n, t=30):
    t0 = time.time()
    while time.time() - t0 < t:
        if "clock {} after update {}".format(min(n, R.END), n) in (open(LOG).read() if os.path.exists(LOG) else ""):
            time.sleep(1.2)
            return True
        time.sleep(0.2)
    return False


def ramp(resume=False):
    return subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_21a.py"), "fake", "--dir", D, "--poll", "0.3", "--settle", "0.3"] + (["--resume"] if resume else []),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def want(clock):
    return {n_: round(R.dial_at(clock, lo, hi, v0, v1, pre), 6) for n_, lo, hi, v0, v1, pre in R.DIALS}


def at(clock, **kw):
    feed(clock, **kw)
    got = wait_clock(clock)
    lv = live()
    w = want(clock)
    bad = {k: (lv.get(k), v) for k, v in w.items() if abs(float(lv.get(k, 1e9)) - v) > 1e-6}
    check("clock {}: every dial on its line{}".format(clock, "" if not bad else " " + repr(bad)), got and not bad)
    check("clock {}: the fixed names untouched".format(clock), all(lv.get(k) == v for k, v in FIXED.items()))
    return lv


p = ramp()
time.sleep(1.5)
lv = at(15)
check("15 (Part I): the drills and the frozen moments half open, the token's gate at -6, the speed pay at 0.078; the head's share 0",
      abs(lv["DRILL_INS_P"] - 0.125) < 1e-6 and abs(lv["DRILL_INS_RATE"] - 0.01) < 1e-6 and abs(lv["BRANCH_P"] - 0.075) < 1e-6 and abs(lv["INS_GATE"] + 6.0) < 1e-6
      and abs(lv["SPEED_PAY"] - 0.125 * (1 - 15 / 40.0)) < 1e-6 and lv["INS_G"] == 0)
lv = at(60)
check("60: Part I at its end values (the speed pay 0), the head's share still 0, the lock 8", lv["DRILL_INS_P"] == 0.25 and lv["INS_GATE"] == 0.0 and lv["SPEED_PAY"] == 0.0
      and lv["INS_G"] == 0.0 and lv["H2_INS_PG"] == 0.0 and lv["INTENT_HOLD"] == 8.0)
lv = at(85)
check("85 (Part II): the head's share at half; no pay on it", abs(lv["INS_G"] - 0.5) < 1e-6 and lv["H2_INS_PG"] == 0.0 and abs(lv["BRANCH_WPN_P"] - 0.15) < 1e-6)
with open(CHK, "a") as f:
    f.write(json.dumps(dict(update=80, won=70, lost=130)) + "\n")
lv = at(109)
p.terminate()
p.wait()
feed.base = lines[0]
p = ramp(resume=True)
time.sleep(1.5)
lv = at(135, own=1)
check("135 (after a stop and --resume, the trainer's own number at 1 again): the head's share 1, the pay on its choices at half, nothing of the hands' inputs faded",
      lv["INS_G"] == 1.0 and abs(lv["H2_INS_PG"] - 0.5) < 1e-6 and lv["SFADE"] == 0.0)
lv = at(180, shot=0.2, credit=0.3, own=46)
check("180 (Part III): the strategy inputs half out of the hands", lv["H2_INS_PG"] == 1.0 and abs(lv["SFADE"] - 0.5) < 1e-6)
lv = at(222, own=88)
check("222: every dial at its end value and held", lv == dict(want(R.END), **FIXED))
time.sleep(1.0)
p.terminate()
p.wait()
log = open(os.path.join(D, "watch", "watch.log")).read()
kept = sorted(f for f in os.listdir(os.path.join(D, "keep")) if f.startswith("policy_u"))
opts = sorted(f for f in os.listdir(os.path.join(D, "keep")) if f.startswith("opt_u"))
check("the marks kept once each with their optimizers ({}): {}".format(len(kept), kept), len(kept) == len(opts) and len(kept) == len(set(kept)) and 5 <= len(kept) <= len(R.MARKS))
check("a check under 40% is a MAJOR PROBLEM line and the clock went on", "MAJOR PROBLEM check update 80" in log and "clock 109 after update 109" in log)
check("the target-switch cost is its own line and not a MAJOR one", "the target-switch cost a player-minute" in log and "FIRING COST ABOVE ZERO: shot cost 0.0" not in log)
check("a firing cost above zero is a MAJOR line; the old head's credit above 0 is a MAJOR line",
      "A FIRING COST ABOVE ZERO: shot cost 0.2" in log and "the old head's target credit is 0.3" in log)
check("the marks of the three parts are kept (60, 110 or the first save past it, 160 or past it, 220 or past it)", any(f in kept for f in ("policy_u60_21a.pt",)) and len(kept) >= 6)
print("ALL PASSED" if ok else "FAILED", "(the fake folder: {})".format(D))
sys.exit(0 if ok else 1)
