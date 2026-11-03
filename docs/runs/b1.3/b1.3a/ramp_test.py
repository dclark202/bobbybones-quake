"""ramp_b13a.py on a fake run folder (2026-11-02): H2_GATE_CAP in a straight line from 0 at update 10 to 1 at update 90, each save of the ramp kept with its optimizer, the head-open save at update 90;
with "hold": a check of 40% or less holds the gate until a later check is above it, a flag under 50%; the tripwire on each kind: the bias over the limit, the hands' length over 1.5 x its first, a piece skipped, a NaN.
    python docs/runs/b1.3/b1.3a/ramp_test.py <empty scratch folder> [hold] > docs/runs/b1.3/b1.3a/ramp_test.log"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
D = sys.argv[1]
assert not os.path.exists(os.path.join(D, "live.json")), "use an empty folder"
os.makedirs(os.path.join(D, "watch"), exist_ok=True)
json.dump(dict(H2_GATE_CAP=0.0, H2_GATE_OPEN=1.0, WIN_ADD=0.33), open(os.path.join(D, "live.json"), "w"))
HOLD = len(sys.argv) > 2
BAD = {} if HOLD else {102: dict(bias=80.0), 104: dict(hands=40.0), 106: dict(skipped=2), 108: dict(bias=None)}   # the tripwire's four kinds, after the ramp


def update(u, save):                                         # (as the trainer: the update's line, then its save)
    h = dict(bias=5.0 + 0.1 * u, hands=20.0, skipped=0)
    h.update(BAD.get(u, {}))
    with open(os.path.join(D, "metrics.jsonl"), "a") as fh:
        fh.write(json.dumps(dict(update=u, head2=h)).replace("null", "NaN") + "\n")
    if save:
        for f in ("policy.pt", "opt.pt"):
            open(os.path.join(D, f), "w").write(str(u))


def check(won, lost, u):
    with open(os.path.join(D, "watch", "checks_prev.jsonl"), "a") as fh:
        fh.write(json.dumps(dict(won=won, lost=lost, update=u)) + "\n")


update(0, True)
time.sleep(0.2)
p = subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_b13a.py"), "fake", "--dir", D, "--poll", "0.05", "--settle", "0", "--bias-lim", "60"])
time.sleep(1)
seq = []
holds = {30: (60, 100), 50: (110, 90)} if HOLD else {}
for u in range(1, 111):
    if u in holds:
        check(*holds[u], u)
        time.sleep(0.4)
    update(u, u % 10 == 0)
    time.sleep(0.3)
    seq.append((u, json.load(open(os.path.join(D, "live.json")))["H2_GATE_CAP"]))
p.kill()
ok = True


def need(name, c):
    global ok
    ok = ok and bool(c)
    print(("PASS " if c else "FAIL ") + name, flush=True)


g = dict(seq)
print("gate at updates 10, 11, 30, 50, 70, 90, 110:", [g[u] for u in (10, 11, 30, 50, 70, 90, 110)])
k = os.listdir(os.path.join(D, "keep"))
w = open(os.path.join(D, "watch", "watch.log")).read()
need("the gate open at the end", g[110] == 1.0)
need("the head-open save kept with its optimizer", "policy_head_open_b13a.pt" in k and "opt_head_open_b13a.pt" in k)
if HOLD:
    need("no movement while the check stood at 37.5% (updates 30 to 49)", len(set(g[u] for u in range(30, 50))) == 1)
    need("a flag under 50% and a HOLD logged", "FLAG check update 30" in w and "HOLD at update" in w)
else:
    need("shut to update 10; a straight line: 0.25 at 30, half at 50, open at 90",
         g[10] == 0.0 and abs(g[11] - 0.0125) < 1e-6 and abs(g[30] - 0.25) < 1e-6 and abs(g[50] - 0.5) < 1e-6 and abs(g[89] - 0.9875) < 1e-6 and g[90] == 1.0)
    need("the ramp's saves kept with their optimizers (10 to 80)", all("policy_gate{}_b13a.pt".format(u) in k and "opt_gate{}_b13a.pt".format(u) in k for u in range(10, 90, 10)))
    need("the head-open save is the save of update 90", open(os.path.join(D, "keep", "policy_head_open_b13a.pt")).read() == "90")
    need("no tripwire before the bad numbers", all("TRIPWIRE update {}:".format(u) not in w for u in range(1, 102)))
    need("the tripwire: bias, hands, skipped, NaN", all(s in w for s in ("the bias's length 80.0 over 60", "the hands' target length 40.0", "2 pieces skipped", "a NaN in the head's numbers")))
print("ALL PASSED" if ok else "FAILED", flush=True)
sys.exit(0 if ok else 1)
