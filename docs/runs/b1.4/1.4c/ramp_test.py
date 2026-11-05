"""ramp_14c.py on fake files (2026-11-04): a fake run folder (live.json at the start values, a policy.pt and opt.pt, metrics.jsonl and checks
written by this script), the ramp run with a short poll. Checks: KEEP_G follows the clock (0 to 10 at 0, 10 to 90 up to 1); a check under 50%
stops the clock; one under 45% steps it back 10; the hold lifts; every save kept while the clock moves, the step marks (10, 50, 90) kept once;
nothing past the end; the other dials untouched; the flicker and keep flags written.
    python docs/runs/b1.4/1.4c/ramp_test.py"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix="ramp14c_")
os.makedirs(os.path.join(D, "watch"))
json.dump(dict(KEEP_G=0.0, PFSP=1.0, INTENT_TEACH_W=0.0, SPEED_PAY=0.0, H2_PG=1.0), open(os.path.join(D, "live.json"), "w"))
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


def upd(n, save=False, trips=20.0, reached=0.25, kl=0.001):
    with open(MET, "a") as f:
        f.write(json.dumps(dict(update=n, pace=dict(trip_speed=339, over_320=0.52), intent=dict(trips_per_player_min=trips, reached=reached),
                                head2=dict(hands=17, raw=9), keep=dict(kl=kl))) + "\n")
    if save:
        for f_ in ("policy.pt", "opt.pt"):
            open(os.path.join(D, f_), "w").write(str(n))


def chk(n, w, l):
    with open(CHK, "a") as f:
        f.write(json.dumps(dict(update=n, won=w, lost=l)) + "\n")


def wait():
    time.sleep(1.6)


p = subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_14c.py"), "fake", "--dir", D, "--poll", "0.2", "--settle", "0.3"])
time.sleep(1.5)
for n in range(1, 6):
    upd(n)
    wait()
v = live()
check("update 5: KEEP_G 0 ({})".format(v), v["KEEP_G"] == 0.0)
upd(10, save=True)
wait()
wait()
check("step 10 kept", os.path.exists(os.path.join(D, "keep", "policy_step10_14c.pt")) and os.path.exists(os.path.join(D, "keep", "opt_step10_14c.pt")))
upd(20, save=True)
wait()
wait()
v = live()
check("update 20: KEEP_G 0.125 ({})".format(v["KEEP_G"]), abs(v["KEEP_G"] - 0.125) < 1e-6)
chk(20, 98, 102)                                             # 49%: hold
wait()
upd(30, save=True)
wait()
wait()
v = live()
check("held at clock 20 by a check of 49% ({})".format(v["KEEP_G"]), abs(v["KEEP_G"] - 0.125) < 1e-6)
check("the save of update 30 kept while held", os.path.exists(os.path.join(D, "keep", "policy_u30_14c.pt")))
chk(30, 105, 95)                                             # lifts
wait()
upd(50)
wait()
v = live()
check("lifted: clock 40 after update 50 ({:.4f} = 30/80)".format(v["KEEP_G"]), abs(v["KEEP_G"] - 30 / 80.0) < 1e-4)
chk(50, 80, 120)                                             # 40%: back 10
wait()
v = live()
check("back 10: clock 30 ({:.4f} = 20/80)".format(v["KEEP_G"]), abs(v["KEEP_G"] - 20 / 80.0) < 1e-4)
chk(60, 110, 90)
wait()
upd(61, trips=40.0, reached=0.1, kl=0.2)                     # flicker and a large keep step: flagged
wait()
upd(130, save=True)
wait()
wait()
v = live()
check("past the end: KEEP_G 1 ({})".format(v), v["KEEP_G"] == 1.0)
check("steps 50 and 90 kept", all(os.path.exists(os.path.join(D, "keep", "policy_step{}_14c.pt".format(k))) for k in (50, 90)))
upd(140, save=True)
wait()
wait()
check("no save kept after the end", not os.path.exists(os.path.join(D, "keep", "policy_u140_14c.pt")))
check("the other dials untouched ({})".format(live()), live()["PFSP"] == 1.0 and live()["INTENT_TEACH_W"] == 0.0 and live()["SPEED_PAY"] == 0.0 and live()["H2_PG"] == 1.0)
w_ = open(os.path.join(D, "watch", "watch.log")).read()
check("the flags written (trips, targets reached, the keep step)", "flicker?" in w_ and "targets reached" in w_ and "the keep choice's step" in w_)
p.kill()
print(open(os.path.join(D, "watch", "ramp.log")).read())
print("ALL PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
