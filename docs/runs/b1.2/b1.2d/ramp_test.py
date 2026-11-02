"""ramp_b12d.py on a fake run folder: the five dials in a straight line over 40 updates, from b1.2c's values to b1.2d's; a save and optimizer kept at each save of the fade, and the first save with it done; with "hold": the fade frozen while a check stands at 40% or less, going on after a later check, a flag under 50%.
    python docs/runs/b1.2/b1.2d/ramp_test.py <empty scratch folder> [hold] > docs/runs/b1.2/b1.2d/ramp_test.log"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
D = sys.argv[1]
assert not os.path.exists(os.path.join(D, "live.json")), "use an empty folder"
os.makedirs(os.path.join(D, "watch"), exist_ok=True)
json.dump(dict(ITEM_PT_MIX=0.0, SPEED_PAY=0.25, DMG_TAKEN_W=1.0, STACK_DIFF=0.7, RAIL_FAR_PAY=0.12, ITEM_PT_LO=0.004, ITEM_PT_HI=0.002, ITEM_DECAY=0.002, WIN_ADD=0.33), open(os.path.join(D, "live.json"), "w"))
HOLD = len(sys.argv) > 2
K = ("ITEM_PT_MIX", "SPEED_PAY", "DMG_TAKEN_W", "STACK_DIFF", "RAIL_FAR_PAY")


def update(u, save):
    if save:
        for f in ("policy.pt", "opt.pt"):
            open(os.path.join(D, f), "w").write(str(u))
    with open(os.path.join(D, "metrics.jsonl"), "a") as fh:
        fh.write(json.dumps(dict(update=u)) + "\n")


def check(won, lost, u):
    with open(os.path.join(D, "watch", "checks_prev.jsonl"), "a") as fh:
        fh.write(json.dumps(dict(won=won, lost=lost, update=u)) + "\n")


update(0, True)
time.sleep(0.2)
p = subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_b12d.py"), "fake", "--dir", D, "--poll", "0.05", "--settle", "0"])
time.sleep(1)
seq = []
holds = {10: (60, 100), 20: (70, 90)} if HOLD else {}
for u in range(1, 61):
    if u in holds:
        check(*holds[u], u)
        time.sleep(0.4)
    update(u, u % 10 == 0)
    time.sleep(0.3)
    d = json.load(open(os.path.join(D, "live.json")))
    seq.append((u,) + tuple(d[k] for k in K))
p.kill()
ok = True


def need(name, c):
    global ok
    ok = ok and bool(c)
    print(("PASS " if c else "FAIL ") + name, flush=True)


end = (1.0, 0.125, 0.8, 0.0, 0.25)
print("at update 10:", seq[9][1:], "| 20:", seq[19][1:], "| 40:", seq[39][1:], "| 60:", seq[59][1:])
need("the end values", seq[-1][1:] == end)
k = os.listdir(os.path.join(D, "keep"))
need("the faded save kept with its optimizer", "policy_faded_b12d.pt" in k and "opt_faded_b12d.pt" in k)
if HOLD:
    frozen = [s for s in seq if 10 <= s[0] < 20]
    need("no movement while the check stood at 37.5%", len(set(s[1:] for s in frozen)) == 1)
    need("the fade goes on after the later check", seq[-1][1:] == end)
    w = open(os.path.join(D, "watch", "watch.log")).read()
    need("a flag under 50%, a HOLD logged", "FLAG check update 20" in w and "HOLD at update" in w)
else:
    need("a straight line: a quarter at update 10, half at 20, done at 40",
         abs(seq[9][1] - 0.25) < 1e-6 and abs(seq[19][1] - 0.5) < 1e-6 and seq[39][1:] == end and abs(seq[19][2] - 0.1875) < 1e-6 and abs(seq[19][3] - 0.9) < 1e-6 and abs(seq[19][4] - 0.35) < 1e-6 and abs(seq[19][5] - 0.185) < 1e-6)
    need("the fade's saves kept with their optimizers (10, 20, 30)", all("policy_fade{}_b12d.pt".format(u) in k and "opt_fade{}_b12d.pt".format(u) in k for u in (10, 20, 30)))
    need("the faded save is the save of update 40", open(os.path.join(D, "keep", "policy_faded_b12d.pt")).read() == "40")
print("ALL PASSED" if ok else "FAILED", flush=True)
sys.exit(0 if ok else 1)
