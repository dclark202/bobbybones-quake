"""ramp_14b.py on fake files (2026-11-03): a fake run folder (live.json at the start values, a policy.pt and opt.pt, metrics.jsonl and checks
written by this script), the ramp run with a short poll. Checks: the dials follow the clock (PFSP over 0 to 10, INTENT_TEACH_W 10 to 70,
SPEED_PAY 70 to 90); a check under 50% stops the clock; one under 45% steps it back 10; the hold lifts; every save kept while the clock
moves, the step marks kept once; nothing past the end.
    python docs/runs/b1.4/1.4b/ramp_test.py"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix="ramp14b_")
os.makedirs(os.path.join(D, "watch"))
json.dump(dict(PFSP=0.0, INTENT_TEACH_W=1.0, SPEED_PAY=0.125, H2_PG=1.0), open(os.path.join(D, "live.json"), "w"))
for f in ("policy.pt", "opt.pt"):
    open(os.path.join(D, f), "w").write("x")
MET, CHK = os.path.join(D, "metrics.jsonl"), os.path.join(D, "watch", "checks_prev.jsonl")
ok = True


def check(name, c):
    global ok
    ok = ok and bool(c)
    print(("PASS " if c else "FAIL ") + name, flush=True)


def live():
    return json.load(open(os.path.join(D, "live.json")))


def upd(n, save=False):
    with open(MET, "a") as f:
        f.write(json.dumps(dict(update=n, pace=dict(trip_speed=339, over_320=0.52), intent=dict(trips_per_player_min=18.0), head2=dict(hands=22, raw=5))) + "\n")
    if save:
        for f_ in ("policy.pt", "opt.pt"):
            open(os.path.join(D, f_), "w").write(str(n))


def chk(n, w, l):
    with open(CHK, "a") as f:
        f.write(json.dumps(dict(update=n, won=w, lost=l)) + "\n")


def wait():
    time.sleep(1.6)


p = subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_14b.py"), "fake", "--dir", D, "--poll", "0.2", "--settle", "0.3"])
time.sleep(1.5)
for n in range(1, 6):
    upd(n)
    wait()
v = live()
check("update 5: PFSP 0.5, rule 1, speed 0.125 ({})".format(v), abs(v["PFSP"] - 0.5) < 1e-6 and v["INTENT_TEACH_W"] == 1.0 and v["SPEED_PAY"] == 0.125)
upd(10, save=True)
wait()
wait()
v = live()
check("update 10: PFSP 1, rule 1 ({})".format(v), v["PFSP"] == 1.0 and v["INTENT_TEACH_W"] == 1.0)
check("step 10 kept", os.path.exists(os.path.join(D, "keep", "policy_step10_14b.pt")) and os.path.exists(os.path.join(D, "keep", "opt_step10_14b.pt")))
chk(10, 98, 102)                                             # 49%: hold
wait()
upd(20, save=True)
wait()
wait()
v = live()
check("held at clock 10 by a check of 49% ({})".format(v), v["INTENT_TEACH_W"] == 1.0)
check("the save of update 20 kept while held", os.path.exists(os.path.join(D, "keep", "policy_u20_14b.pt")))
chk(20, 105, 95)                                             # lifts
wait()
upd(40)
wait()
v = live()
check("lifted: clock 30 after update 40 (rule {:.4f} = 1 - 20/60)".format(v["INTENT_TEACH_W"]), abs(v["INTENT_TEACH_W"] - (1 - 20 / 60.0)) < 1e-4)
chk(40, 80, 120)                                             # 40%: back 10
wait()
v = live()
check("back 10: clock 20 (rule {:.4f} = 1 - 10/60)".format(v["INTENT_TEACH_W"]), abs(v["INTENT_TEACH_W"] - (1 - 10 / 60.0)) < 1e-4)
chk(60, 110, 90)
wait()
upd(130, save=True)
wait()
wait()
v = live()
check("past the end: rule 0, speed 0, PFSP 1 ({})".format(v), v["INTENT_TEACH_W"] == 0.0 and v["SPEED_PAY"] == 0.0 and v["PFSP"] == 1.0)
check("steps 70 and 90 kept", all(os.path.exists(os.path.join(D, "keep", "policy_step{}_14b.pt".format(k))) for k in (70, 90)))
upd(140, save=True)
wait()
wait()
check("no save kept after the end", not os.path.exists(os.path.join(D, "keep", "policy_u140_14b.pt")))
check("H2_PG untouched ({})".format(live()["H2_PG"]), live()["H2_PG"] == 1.0)
p.kill()
print(open(os.path.join(D, "watch", "ramp.log")).read())
print("ALL PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
