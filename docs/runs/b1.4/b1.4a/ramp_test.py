"""ramp_b13.py on a fake run folder: all twelve steps in order, one save kept with its optimizer before each, the stages' names, a hold at a check of 40% that lifts at a later check, a flag under 50%.
    python docs/runs/b1.3/b1.3a/ramp_test.py <empty scratch folder> > docs/runs/b1.3/b1.3a/ramp_test.log"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
D = sys.argv[1]
assert not os.path.exists(os.path.join(D, "live.json")), "use an empty folder"
os.makedirs(os.path.join(D, "watch"), exist_ok=True)
json.dump(dict(CONTACT_FREE=0.0, DMG_TAKEN_W=1.0, INTENT_TEACH_W=1.0, WIN_ADD=0.33), open(os.path.join(D, "live.json"), "w"))


def save(u):
    for f in ("policy.pt", "opt.pt"):
        open(os.path.join(D, f), "w").write(str(u))
    with open(os.path.join(D, "metrics.jsonl"), "a") as fh:
        fh.write(json.dumps(dict(update=u)) + "\n")


def check(won, lost, u):
    with open(os.path.join(D, "watch", "checks_prev.jsonl"), "a") as fh:
        fh.write(json.dumps(dict(won=won, lost=lost, update=u)) + "\n")


save(0)
time.sleep(0.2)
p = subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_b13.py"), "fake", "--dir", D, "--min-s", "0", "--poll", "0.1", "--settle", "0"])
time.sleep(1)
seq, u = [], 0
for k in range(40):
    u += 10
    if u == 110:
        check(60, 100, u)                                    # 37.5%: holds
    if u == 150:
        check(70, 90, u)                                     # 43.8%: flagged, no hold
    time.sleep(0.5)
    save(u)
    time.sleep(0.6)
    d = json.load(open(os.path.join(D, "live.json")))
    seq.append((u, d["CONTACT_FREE"], d["DMG_TAKEN_W"], d["INTENT_TEACH_W"]))
p.kill()
ok = True


def need(name, c):
    global ok
    ok = ok and bool(c)
    print(("PASS " if c else "FAIL ") + name, flush=True)


for s in seq:
    print(s)
when = {}
prev = (0.0, 1.0, 1.0)
for s in seq:
    if s[1:] != prev:
        when[s[1:]] = s[0]
        prev = s[1:]
print("the steps at updates", list(when.values()))
need("twelve steps", len(when) == 12)
need("the end values", seq[-1][1:] == (1.0, 0.65, 0.0))
need("the first at update 10, the next three every 20", list(when.values())[:4] == [10, 30, 50, 70])
need("no step while the check stood at 37.5%", not any(110 <= v < 150 for v in when.values()))
need("steps again after the later check", any(v >= 150 for v in when.values()))
k = os.listdir(os.path.join(D, "keep"))
need("a save and an optimizer before each step", all("policy_step{}_b13a.pt".format(i) in k and "opt_step{}_b13a.pt".format(i) in k for i in range(12)))
need("the stages' saves", all(x in k for x in ("policy_contact_b13a.pt", "opt_contact_b13a.pt", "policy_fight_b13a.pt", "opt_fight_b13a.pt")))
w = open(os.path.join(D, "watch", "watch.log")).read()
need("a flag under 50%, a HOLD logged", "FLAG check update 150" in w and "HOLD at the save" in w)
print("ALL PASSED" if ok else "FAILED", flush=True)
sys.exit(0 if ok else 1)
