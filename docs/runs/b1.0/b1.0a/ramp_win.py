"""b1.0a's ramp (owner, 2026-10-31): WIN_ADD shut to update 10; 0 -> 0.15 over updates 10 to 40; held through update 50; 0.15 -> 0.33 over updates 50 to 80;
then held. "Dont stop the ramp for anything >40%, but flag them here": a check under 50% against v0.6.0's end is written as FLAG; a check of 40% or less holds the
ramp until a later check is above it. WIN_ADD changed by hand in live.json: the ramp leaves it and ends (the owner's value stands).
    python docs/runs/b1.0a/ramp_win.py <run> [--shut 10] [--steps 15] [--every 2] [--pause 10] [--poll 30] [--dir D]"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LEG1, LEG2 = 0.15, 0.33


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--shut", type=int, default=10)
    ap.add_argument("--steps", type=int, default=15, help="steps a leg")
    ap.add_argument("--every", type=int, default=2, help="updates a step")
    ap.add_argument("--pause", type=int, default=10, help="updates held between the legs")
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--dir", default="")
    ap.add_argument("--once", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    LIVE, MET, WD = os.path.join(D, "live.json"), os.path.join(D, "metrics.jsonl"), os.path.join(D, "watch")
    CHK = os.path.join(WD, "checks_prev.jsonl")
    os.makedirs(WD, exist_ok=True)
    seen = [0]

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

    def last_check():
        """flags every new check under 50%; -> the last check's win rate, or None"""
        try:
            R = [json.loads(x) for x in open(CHK) if x.strip()]
        except FileNotFoundError:
            return None
        for d in R[seen[0]:]:
            wr_ = d["won"] / max(1, d["won"] + d["lost"])
            if wr_ < 0.5:
                log("FLAG check update {} against v0.6.0's end: {}-{} = {:.1%}".format(d["update"], d["won"], d["lost"], wr_))
        seen[0] = len(R)
        return R[-1]["won"] / max(1, R[-1]["won"] + R[-1]["lost"]) if R else None

    def cur():
        return float(json.load(open(LIVE, encoding="utf-8")).get("WIN_ADD", 0.0))

    def put(x):
        d = json.load(open(LIVE, encoding="utf-8"))
        d["WIN_ADD"] = x
        open(LIVE + ".tmp", "w", encoding="utf-8").write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)

    sched, u, x0 = [], a.shut, 0.0
    for leg, to in enumerate((LEG1, LEG2)):
        if leg:
            u += a.pause
        for i in range(1, a.steps + 1):
            sched.append((u + i * a.every, round(x0 + (to - x0) * i / a.steps, 4)))
        u, x0 = u + a.steps * a.every, to
    log("ramp_win on for {}: {} steps, the last at update {} to WIN_ADD {}".format(a.run, len(sched), sched[-1][0], sched[-1][1]))
    last = cur()
    assert last == 0.0, "WIN_ADD is {} at the ramp's start".format(last)
    held = False
    for ui, x in sched:
        while True:
            wr = last_check()
            if updates() >= ui:
                if wr is not None and wr <= 0.40:
                    if not held:
                        log("HOLD the ramp at WIN_ADD {}: the last check {:.1%} is 40% or less (raised with the owner)".format(last, wr))
                    held = True
                else:
                    if held:
                        log("the hold is over: the last check {:.1%}".format(wr))
                    held = False
                    break
            if cur() != last:
                log("WIN_ADD is {} by hand, the ramp had {}: the ramp ends, the value stands".format(cur(), last))
                return flag_loop(last_check, a.poll)
            time.sleep(a.poll)
        if cur() != last:
            log("WIN_ADD is {} by hand, the ramp had {}: the ramp ends, the value stands".format(cur(), last))
            return flag_loop(last_check, a.poll)
        put(x)
        last = x
        log("RAMP WIN_ADD {} (u{})".format(x, updates()))
    log("the ramp is done: WIN_ADD {}, held; the checks are still flagged".format(last))
    if not a.once:
        flag_loop(last_check, a.poll)


def flag_loop(last_check, poll):
    while True:
        last_check()
        time.sleep(poll)


if __name__ == "__main__":
    sys.exit(main())
