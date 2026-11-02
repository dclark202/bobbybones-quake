"""ramp_b12c.py on a fake run folder: all fourteen steps at their updates, a save and optimizer kept before each, the stages' names, a hold at a check of 40% that lifts at a later check, a flag under 50%.
    python docs/runs/b1.2/b1.2c/ramp_test.py <empty scratch folder> > docs/runs/b1.2/b1.2c/ramp_test.log"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
D = sys.argv[1]
assert not os.path.exists(os.path.join(D, "live.json")), "use an empty folder"
os.makedirs(os.path.join(D, "watch"), exist_ok=True)
json.dump(dict(COST_FIRE_W=1.0, COST_JERK_W=1.0, CONTACT_FREE=0.0, WIN_ADD=0.33), open(os.path.join(D, "live.json"), "w"))
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
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_b12c.py"), "fake", "--dir", D, "--min-s", "0", "--poll", "0.1", "--settle", "0"])
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
        seq.append((u, d["COST_FIRE_W"], d["CONTACT_FREE"], d["COST_JERK_W"]))
    p.kill()
    return seq


seq = run(410 if HOLD else 280, {150: (60, 100), 190: (70, 90)} if HOLD else {})
ok = True


def need(name, c):
    global ok
    ok = ok and bool(c)
    print(("PASS " if c else "FAIL ") + name, flush=True)


when = {}
prev = (1.0, 0.0, 1.0)
for s in seq:
    if s[1:] != prev:
        when[s[1:]] = s[0]
        prev = s[1:]
print("the steps at updates", list(when.values()))
need("fourteen steps", len(when) == 14)
need("the end values", seq[-1][1:] == (0.0, 1.0, 0.0))
if HOLD:
    need("no step while the check stood at 37.5%", not any(150 <= v < 190 for v in when.values()))
    need("steps again after the later check", any(v >= 190 for v in when.values()))
    w = open(os.path.join(D, "watch", "watch.log")).read()
    need("a flag under 50%, a HOLD logged", "FLAG check update 190" in w and "HOLD at the save" in w)
else:
    need("at updates 60 to 100, 120 to 180, 200 to 240", list(when.values()) == [60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 210, 220, 230, 240])
k = os.listdir(os.path.join(D, "keep"))
need("a save and an optimizer before each step", all("policy_step{}_b12c.pt".format(i) in k and "opt_step{}_b12c.pt".format(i) in k for i in range(14)))
need("the stages' saves", all(x in k for x in ("policy_table_b12c.pt", "opt_table_b12c.pt", "policy_nofire_b12c.pt", "opt_nofire_b12c.pt", "policy_contact_b12c.pt", "opt_contact_b12c.pt", "policy_nojerk_b12c.pt", "opt_nojerk_b12c.pt")))
if not HOLD:
    need("the last stage's end is the save of update 260", open(os.path.join(D, "keep", "policy_nojerk_b12c.pt")).read() == "260")
print("ALL PASSED" if ok else "FAILED", flush=True)
sys.exit(0 if ok else 1)
