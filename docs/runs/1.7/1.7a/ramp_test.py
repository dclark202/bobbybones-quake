"""ramp_17a.py on fake files (2026-11-05): a fake run folder (live.json at 1.6a's end values with KEEP_G 0, a policy.pt and opt.pt,
metrics.jsonl and checks written by this script), the ramp run with a short poll. Checks: KEEP_G follows the clock (0 to update 10, then
+0.0125 an update to 1 at 90) and stays at 1 after; the marks 10, 50, 90 kept once with their optimizers; a check under 40% logged as a
MAJOR PROBLEM and the clock not held; the keep record logged each update; flicker (targets reached 30% under the start), the keep step over
0.05 and a firing cost above zero flagged; the other dials untouched.
    python docs/runs/1.7/1.7a/ramp_test.py"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
D = tempfile.mkdtemp(prefix="ramp17a_")
os.makedirs(os.path.join(D, "watch"))
json.dump(dict(KEEP_G=0.0, INTENT_TEACH_W=0.0, SPEED_PAY=0.0, H2_WPG=1.0, HABIT_P=0.3, COST_FIRE_W=0.0, H2_PG=1.0), open(os.path.join(D, "live.json"), "w"))
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


def upd(n, save=False, reached=0.5, kl=0.001, shot=0.0):
    with open(MET, "a") as f:
        f.write(json.dumps(dict(update=n, pace=dict(trip_speed=339, over_320=0.52), intent=dict(trips_per_player_min=18.0, reached=reached),
                                head2=dict(hands=22, raw=5), stack=dict(big_weapons=1.7), shot_cost_per_player_min=shot,
                                keep=dict(g=0.5, kl=kl, pull=dict(s=0.1, hands=0.0, own=3.2), arrived=dict(share=0.1, p=0.37),
                                          sim2=dict(seconds=900.0, readings_a_second=5.0, decided=4000, redecide=0.12)),
                                pay_terms=dict(per_player_min=dict(dmg_dealt=1.8, intent_switch=0.0)))) + "\n")
    if save:
        for f_ in ("policy.pt", "opt.pt"):
            open(os.path.join(D, f_), "w").write(str(n))


def chk(n, w, l):
    with open(CHK, "a") as f:
        f.write(json.dumps(dict(update=n, won=w, lost=l)) + "\n")


def wait():
    time.sleep(float(os.environ.get("RAMP_WAIT") or 1.6))   # (a busy machine: longer)


def log():
    return open(os.path.join(D, "watch", "watch.log")).read()


p = subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_17a.py"), "fake", "--dir", D, "--poll", "0.2", "--settle", "0.3"])
time.sleep(1.5)
for n in range(1, 6):
    upd(n)
    wait()
v = live()
check("update 5: KEEP_G 0 ({})".format(v["KEEP_G"]), v["KEEP_G"] == 0.0)
upd(10, save=True)
wait()
wait()
check("mark 10 kept", os.path.exists(os.path.join(D, "keep", "policy_u10_17a.pt")) and os.path.exists(os.path.join(D, "keep", "opt_u10_17a.pt")))
chk(10, 70, 130)                                             # 35%: a MAJOR PROBLEM, never held
wait()
upd(20, save=True, reached=0.30)
wait()
wait()
v = live()
check("not held by a check of 35%: clock 20 (KEEP_G {:.4f} = 10/80)".format(v["KEEP_G"]), abs(v["KEEP_G"] - 0.125) < 1e-6)
check("the check of 35% logged as a MAJOR PROBLEM", "MAJOR PROBLEM check update 10" in log())
check("targets reached 0.30 against 0.5 flagged", "FLAG update 20: targets reached 0.3" in log())
check("the keep record logged", "update 20: keep share 0.5 | its seconds 900.0 readings a second 5.0" in log())
check("no save kept between marks", not os.path.exists(os.path.join(D, "keep", "policy_u20_17a.pt")))
upd(30, kl=0.08, shot=0.01)
wait()
check("the keep step over 0.05 flagged", "FLAG update 30: the keep choice's step" in log())
check("a firing cost above zero flagged", "FLAG update 30: A FIRING COST ABOVE ZERO" in log())
upd(50, save=True)
wait()
wait()
v = live()
check("update 50: KEEP_G 0.5 ({})".format(v["KEEP_G"]), abs(v["KEEP_G"] - 0.5) < 1e-6)
check("mark 50 kept", os.path.exists(os.path.join(D, "keep", "policy_u50_17a.pt")))
upd(90, save=True)
wait()
wait()
v = live()
check("update 90: KEEP_G 1 ({})".format(v["KEEP_G"]), v["KEEP_G"] == 1.0)
check("mark 90 kept", os.path.exists(os.path.join(D, "keep", "policy_u90_17a.pt")) and os.path.exists(os.path.join(D, "keep", "opt_u90_17a.pt")))
upd(140, save=True)
wait()
wait()
v = live()
check("held at 1 past the end ({})".format(v["KEEP_G"]), v["KEEP_G"] == 1.0)
check("the other dials untouched ({})".format(v), v["INTENT_TEACH_W"] == 0.0 and v["SPEED_PAY"] == 0.0 and v["H2_WPG"] == 1.0 and v["HABIT_P"] == 0.3
      and v["COST_FIRE_W"] == 0.0 and v["H2_PG"] == 1.0)
p.kill()
print(log())
print("ALL PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
