"""v0.6.1e's schedule (owner, 2026-10-31): first the pay, over the first 40 updates, twenty steps, one every 2 updates: FADE_V 0.125 -> 0.5 and WIN_GAIN
0.33 -> 0.87 (WIN_W stays 0.5), no fades. Then the pull and the brain's old belief together by tools/run/ramp_live.py: BRAIN_FADE 0 -> 1 and
LEVEL_PULL 0.95 -> 1 in the same write, eight steps, a step right after each save and at least 25 min apart.
    python docs/runs/v0.6.1e/ramp_fades.py <run> [--pay-steps N] [--pay-every N] [--poll S] [--dir D] [ramp_live arguments]"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RAMP = os.path.join(ROOT, "tools", "run", "ramp_live.py")
A = sys.argv[1:]
run = A.pop(0)


def opt(name, default):
    if name in A:
        i = A.index(name)
        v = A[i + 1]
        del A[i:i + 2]
        return v
    return default


STEPS = int(opt("--pay-steps", 20))
EVERY = int(opt("--pay-every", 2))
POLL = float(opt("--poll", 30))
D = os.path.join(ROOT, "data", "sim_runs", run)
if "--dir" in A:
    D = A[A.index("--dir") + 1]
LIVE, MET = os.path.join(D, "live.json"), os.path.join(D, "metrics.jsonl")
WD = os.path.join(D, "watch")
os.makedirs(WD, exist_ok=True)


def log(s):
    line = time.strftime("%m-%d %H:%M:%S ") + s
    for f in ("ramp.log", "watch.log"):
        with open(os.path.join(WD, f), "a") as fh:
            fh.write(line + "\n")


def updates():
    try:
        return sum(1 for x in open(MET) if x.strip())
    except FileNotFoundError:
        return 0


def put(**kw):
    d = json.load(open(LIVE, encoding="utf-8"))
    d.update(kw)
    open(LIVE + ".tmp", "w", encoding="utf-8").write(json.dumps(d))
    os.replace(LIVE + ".tmp", LIVE)


for i in range(1, STEPS + 1):
    while updates() < i * EVERY:
        time.sleep(POLL)
    v, g = round(0.125 + 0.375 * i / STEPS, 4), round(0.33 + 0.54 * i / STEPS, 3)
    put(FADE_V=v, WIN_GAIN=g)
    log("RAMP pay step {}: FADE_V {} WIN_GAIN {} (u{})".format(i, v, g, updates()))
log("the pay at half and half; the fades begin")
sys.exit(subprocess.run([sys.executable, RAMP, run, "BRAIN_FADE", "0", "1", "0.125", "--also", "LEVEL_PULL:0.95:1.0:0.00625",
                         "--keep-as", "policy_prefade_v061e.pt"] + A, cwd=ROOT).returncode)
