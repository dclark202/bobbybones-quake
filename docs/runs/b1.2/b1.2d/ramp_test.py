"""ramp_b12d.py on a fake run folder: all four steps at their updates, a save and optimizer kept before each, the stages' names, the last stage's end two saves after its last step; with "hold": a hold at a check of 40% that lifts at a later check, a flag under 50%.
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
json.dump(dict(SPEED_PAY=0.25, RAIL_FAR_PAY=0.12, ITEM_PT_LO=0.004, ITEM_PT_HI=0.002, ITEM_DECAY=0.002, WIN_ADD=0.33), open(os.path.join(D, "live.json"), "w"))
HOLD = len(sys.argv) > 2


def save(u):
    for f in ("policy.pt", "opt.pt"):
        open(os.path.join(D, f), "w").write(str(u))
    with open(os.path.join(D, "metrics.jsonl"), "a") as fh:
        fh.write(json.dumps(dict(update=u)) + "\n")


def check(won, lost, u):
    with open(os.path.join(D, "watch", "checks_prev.jsonl"), "a") as fh:
        fh.write(json.dumps(dict(won=won, lost=lost, update=u)) + "\n")


def run(seq_to, holds):
    save(0)
    time.sleep(0.2)
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_b12d.py"), "fake", "--dir", D, "--min-s", "0", "--poll", "0.1", "--settle", "0"])
    time.sleep(1)
    seq, u = [], 0
    while u < seq_to:
        u += 10
        if u in holds:
            check(*holds[u], u)
        time.sleep(0.4)
        save(u)
        time.sleep(0.5)
        d = json.load(open(os.path.join(D, "live.json")))
        seq.append((u, d["SPEED_PAY"], d["RAIL_FAR_PAY"]))
    p.kill()
    return seq


seq = run(200 if HOLD else 120, {20: (60, 100), 60: (70, 90)} if HOLD else {})
ok = True


def need(name, c):
    global ok
    ok = ok and bool(c)
    print(("PASS " if c else "FAIL ") + name, flush=True)


when = {}
prev = (0.25, 0.12)
for s in seq:
    if s[1:] != prev:
        when[s[1:]] = s[0]
        prev = s[1:]
print("the steps at updates", list(when.values()))
need("four steps", len(when) == 4)
need("the end values", seq[-1][1:] == (0.125, 0.25))
if HOLD:
    need("no step while the check stood at 37.5%", not any(20 <= v < 60 for v in when.values()))
    need("steps again after the later check", any(v >= 60 for v in when.values()))
    w = open(os.path.join(D, "watch", "watch.log")).read()
    need("a flag under 50%, a HOLD logged", "FLAG check update 60" in w and "HOLD at the save" in w)
else:
    need("at updates 30, 40, 70, 80", list(when.values()) == [30, 40, 70, 80])
k = os.listdir(os.path.join(D, "keep"))
need("a save and an optimizer before each step", all("policy_step{}_b12d.pt".format(i) in k and "opt_step{}_b12d.pt".format(i) in k for i in range(4)))
need("the stages' saves", all(x in k for x in ("policy_table_b12d.pt", "opt_table_b12d.pt", "policy_speed_b12d.pt", "opt_speed_b12d.pt", "policy_rail_b12d.pt", "opt_rail_b12d.pt")))
if not HOLD:
    need("the table's end is the save of update 30, the speed's of 70, the rail's of 100",
         [open(os.path.join(D, "keep", f)).read() for f in ("policy_table_b12d.pt", "policy_speed_b12d.pt", "policy_rail_b12d.pt")] == ["30", "70", "100"])
print("ALL PASSED" if ok else "FAILED", flush=True)
sys.exit(0 if ok else 1)
