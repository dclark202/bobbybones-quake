"""ramp_16a.py on fake files (2026-11-05): a fake run folder (live.json at 1.5a's end values, a policy.pt and opt.pt, metrics.jsonl and
checks written by this script), the ramp run with a short poll and no blanked check (--blank-at 0: the real one plays 200 games). Checks:
the two dials follow the clock (1 -> 0 and 0.125 -> 0 over updates 0 to 40) and stay at 0 to 80; the marks 10, 40, 80 kept once with their
optimizers; a check under 40% logged as a MAJOR PROBLEM and the clock not held; big weapons owned 0.05 under the first five updates
flagged; a firing cost above zero flagged; the other dials untouched.
    python docs/runs/1.6/1.6a/ramp_test.py"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix="ramp16a_")
os.makedirs(os.path.join(D, "watch"))
json.dump(dict(INTENT_TEACH_W=1.0, SPEED_PAY=0.125, H2_WPG=1.0, HABIT_P=0.3, COST_FIRE_W=0.0, H2_PG=1.0), open(os.path.join(D, "live.json"), "w"))
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


def upd(n, save=False, bw=1.70, shot=0.0):
    with open(MET, "a") as f:
        f.write(json.dumps(dict(update=n, pace=dict(trip_speed=339, over_320=0.52), intent=dict(trips_per_player_min=18.0, reached=0.5),
                                head2=dict(hands=22, raw=5), stack=dict(big_weapons=bw), shot_cost_per_player_min=shot,
                                pay_terms=dict(per_player_min=dict(dmg_dealt=1.8, intent_switch=0.0, speed=0.3)))) + "\n")
    if save:
        for f_ in ("policy.pt", "opt.pt"):
            open(os.path.join(D, f_), "w").write(str(n))


def chk(n, w, l):
    with open(CHK, "a") as f:
        f.write(json.dumps(dict(update=n, won=w, lost=l)) + "\n")


def wait():
    time.sleep(1.6)


def log():
    return open(os.path.join(D, "watch", "watch.log")).read()


p = subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_16a.py"), "fake", "--dir", D, "--poll", "0.2", "--settle", "0.3", "--blank-at", "0"])
time.sleep(1.5)
for n in range(1, 6):
    upd(n)
    wait()
v = live()
check("update 5: teacher 0.875, speed 0.109375 ({})".format(v), abs(v["INTENT_TEACH_W"] - 0.875) < 1e-6 and abs(v["SPEED_PAY"] - 0.109375) < 1e-6)
upd(10, save=True)
wait()
wait()
check("mark 10 kept", os.path.exists(os.path.join(D, "keep", "policy_u10_16a.pt")) and os.path.exists(os.path.join(D, "keep", "opt_u10_16a.pt")))
chk(10, 70, 130)                                             # 35%: a MAJOR PROBLEM, never held
wait()
upd(20, save=True, bw=1.60)
wait()
wait()
v = live()
check("not held by a check of 35%: clock 20 (teacher {:.4f})".format(v["INTENT_TEACH_W"]), abs(v["INTENT_TEACH_W"] - 0.5) < 1e-6)
check("the check of 35% logged as a MAJOR PROBLEM", "MAJOR PROBLEM check update 10" in log())
check("big weapons owned 1.60 against 1.70 flagged", "FLAG update 20: big weapons owned 1.6" in log())
check("no save kept between marks", not os.path.exists(os.path.join(D, "keep", "policy_u20_16a.pt")))
upd(30, shot=0.01)
wait()
check("a firing cost above zero flagged", "FLAG update 30: A FIRING COST ABOVE ZERO" in log())
upd(40, save=True)
wait()
wait()
v = live()
check("update 40: both at 0 ({})".format(v), v["INTENT_TEACH_W"] == 0.0 and v["SPEED_PAY"] == 0.0)
check("mark 40 kept", os.path.exists(os.path.join(D, "keep", "policy_u40_16a.pt")))
upd(60, save=True)
wait()
wait()
v = live()
check("held at 0 at update 60 ({})".format(v), v["INTENT_TEACH_W"] == 0.0 and v["SPEED_PAY"] == 0.0)
upd(80, save=True)
wait()
wait()
check("mark 80 kept", os.path.exists(os.path.join(D, "keep", "policy_u80_16a.pt")) and os.path.exists(os.path.join(D, "keep", "opt_u80_16a.pt")))
v = live()
check("the other dials untouched ({})".format(v), v["H2_WPG"] == 1.0 and v["HABIT_P"] == 0.3 and v["COST_FIRE_W"] == 0.0 and v["H2_PG"] == 1.0)
p.kill()
print(log())
print("ALL PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
