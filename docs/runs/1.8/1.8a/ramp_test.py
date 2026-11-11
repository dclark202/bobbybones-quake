"""ramp_18a.py on fake files (2026-11-11): a fake run folder in the temp directory (the start's live.json values, a policy.pt and opt.pt,
metrics.jsonl and a check written by this script), the ramp run with a short poll. Checks: each dial follows the clock of metrics.jsonl's
LINES (AIM3 0 to 30, H2_PG 50 to 130, INTENT_TEACH_W and SPEED_PAY 160 to 190, KEEP_G 210 to 250, SFADE 270 to 310) and holds after; the other names are
untouched (DMG_REWARD 0.005); the marks are kept once with their optimizers; THE RESTART: the ramp stopped at 150 lines and started again with
--resume while the trainer's own update number starts at 1 again: the clock goes on from 150, nothing steps back, no mark is kept twice; a
check under 40% is logged as a MAJOR PROBLEM and the clock not held; a firing cost above zero and the lightning over half are flagged.
    python docs/runs/1.8/1.8a/ramp_test.py"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix="ramp18a_")
os.makedirs(os.path.join(D, "watch"))
START = dict(AIM3_W=0.0, AIM3_SIZE_A=1.0, AIM3_SIZE_B=0.0, AIM3_LEAD=0.0, AIM3_RELOAD=1.0, H2_PG=0.0, INTENT_TEACH_W=1.0, SPEED_PAY=0.125, KEEP_G=0.0, SFADE=0.0, DMG_REWARD=0.005, DMG_TAKEN_W=0.8,
             WIN_ADD=0.33, COST_FIRE_W=0.0, H2_WPG=0.0, HABIT_P=0.0)
json.dump(START, open(os.path.join(D, "live.json"), "w"))
for f in ("policy.pt", "opt.pt"):
    open(os.path.join(D, f), "w").write("x")
MET, CHK, LIVE = os.path.join(D, "metrics.jsonl"), os.path.join(D, "watch", "checks_prev.jsonl"), os.path.join(D, "live.json")
ok = True
lines = [0]


def check(name, c):
    global ok
    ok = ok and bool(c)
    print(("PASS " if c else "FAIL ") + name, flush=True)


def feed(upto, own=None, lg=0.4, shot=0.0):
    """metrics lines up to `upto` lines in all; `own` = the trainer's own number of the first line written (after a restart: 1)"""
    with open(MET, "a") as f:
        while lines[0] < upto:
            lines[0] += 1
            u = lines[0] if own is None else own + (lines[0] - feed.base)
            f.write(json.dumps(dict(update=u, frags_per_match_min=2.0, v15=dict(in_hand_games=dict(rl=0.3, lg=lg, rg=0.05)), shot_cost_per_player_min=shot,
                                    head2=dict(hands=22.0, raw=3.0, cos=-0.1, credit=0.5), pay_terms=dict(per_player_min=dict(dmg_dealt=1.5, dmg_taken=-1.3, frag=1.0, death=-1.0, win_part=0.0),
                                                                                                         size_share=dict(win_part=0.4), total_per_player_min=0.1))) + "\n")
    open(os.path.join(D, "policy.pt"), "w").write("x{}".format(upto))    # (a save: the marks are kept at a settled save)
    open(os.path.join(D, "opt.pt"), "w").write("o{}".format(upto))


feed.base = 0


def live():
    for _ in range(50):
        try:
            return json.load(open(LIVE))
        except (OSError, ValueError):
            time.sleep(0.05)
    raise RuntimeError("live.json not readable")


def wait_clock(n, t=20):
    t0 = time.time()
    while time.time() - t0 < t:
        if "clock {} after update {}".format(min(n, 310), n) in (open(os.path.join(D, "watch", "ramp.log")).read() if os.path.exists(os.path.join(D, "watch", "ramp.log")) else ""):
            time.sleep(1.2)                                  # (and the save's settle time, for the marks)
            return True
        time.sleep(0.2)
    return False


def ramp(resume=False):
    return subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_18a.py"), "fake", "--dir", D, "--poll", "0.3", "--settle", "0.3"] + (["--resume"] if resume else []),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def near(a, b):
    return abs(float(a) - b) < 1e-6


p = ramp()
time.sleep(1.5)
for n, want in ((15, dict(AIM3_W=0.5, AIM3_SIZE_A=0.695, AIM3_SIZE_B=0.1775, AIM3_LEAD=0.5, AIM3_RELOAD=0.5, H2_PG=0.0, INTENT_TEACH_W=1.0, SPEED_PAY=0.125, KEEP_G=0.0)),
                (50, dict(AIM3_W=1.0, AIM3_SIZE_A=0.39, AIM3_SIZE_B=0.355, AIM3_LEAD=1.0, AIM3_RELOAD=0.0, H2_PG=0.0)),
                (90, dict(AIM3_W=1.0, H2_PG=0.5, INTENT_TEACH_W=1.0, KEEP_G=0.0)),
                (150, dict(H2_PG=1.0, INTENT_TEACH_W=1.0, SPEED_PAY=0.125, KEEP_G=0.0))):
    feed(n)
    got = wait_clock(n)
    d = live()
    check("{} lines: {}".format(n, {k: d.get(k) for k in want}), got and all(near(d[k], v) for k, v in want.items()) and near(d["DMG_REWARD"], 0.005) and near(d["WIN_ADD"], 0.33))
with open(CHK, "a") as f:
    f.write(json.dumps(dict(update=150, won=70, lost=130, mean=0.42)) + "\n")
time.sleep(1.5)
p.kill()
p.wait()
kept0 = sorted(os.listdir(os.path.join(D, "keep")))
check("the marks kept so far, each with its optimizer: {}".format(kept0), all(("policy_u{}_18a.pt".format(n) in kept0 and "opt_u{}_18a.pt".format(n) in kept0) for n in (50, 90, 150)))
# ---- the restart: the trainer's own update number starts at 1 again; the ramp with --resume
p = ramp(resume=True)
time.sleep(1.5)
feed.base = 150
for n, want in ((175, dict(H2_PG=1.0, INTENT_TEACH_W=0.5, SPEED_PAY=0.0625, KEEP_G=0.0)),
                (210, dict(INTENT_TEACH_W=0.0, SPEED_PAY=0.0, KEEP_G=0.0)),
                (230, dict(KEEP_G=0.4875, INTENT_TEACH_W=0.0, H2_PG=1.0, AIM3_W=1.0)),
                (270, dict(KEEP_G=0.975, SFADE=0.0)),
                (290, dict(KEEP_G=0.975, SFADE=0.5, INTENT_TEACH_W=0.0)),
                (320, dict(KEEP_G=0.975, SFADE=1.0, INTENT_TEACH_W=0.0, SPEED_PAY=0.0, H2_PG=1.0, AIM3_W=1.0, AIM3_SIZE_A=0.39, AIM3_SIZE_B=0.355))):
    feed(n, own=1, lg=0.6 if n == 230 else 0.4, shot=0.2 if n == 320 else 0.0)
    got = wait_clock(n) if n <= 310 else (time.sleep(3) or True)
    d = live()
    check("after the restart, {} lines (the trainer's own number {}): {}".format(n, n - 150, {k: d.get(k) for k in want}),
          got and all(near(d[k], v) for k, v in want.items()) and near(d["DMG_REWARD"], 0.005))
time.sleep(1.5)
p.kill()
p.wait()
kept = sorted(os.listdir(os.path.join(D, "keep")))
log = open(os.path.join(D, "watch", "watch.log")).read()
check("the marks after the restart by the run's update, none kept twice: {}".format([k for k in kept if k.startswith("policy_")]),
      all("policy_u{}_18a.pt".format(n) in kept for n in (50, 90, 150, 210, 230)) and len([k for k in kept if k.startswith("policy_")]) == len({k for k in kept if k.startswith("policy_")})
      and not any(k.startswith("policy_u") and int(k[8:-7]) < 150 and k not in kept0 for k in kept))
check("the check under 40% logged as a MAJOR PROBLEM, and the clock went on", "MAJOR PROBLEM check update 150" in log and "clock 175 after update 175" in log)
check("the lightning over half flagged (230) and a firing cost above zero a MAJOR PROBLEM (320)", "the lightning is in his hand 0.6" in log and "A FIRING COST ABOVE ZERO" in log)
check("the head's parts logged each update", "his target scores: the hands' part 22.0 the head's part 3.0" in log)
check("the resumed ramp says so and never wrote a clock under 150", "(resumed)" in log and not any("clock {} after".format(c) in log.split("(resumed)")[1] for c in range(1, 150)))
print("ALL PASSED" if ok else "FAILED", "|", D)
sys.exit(0 if ok else 1)
