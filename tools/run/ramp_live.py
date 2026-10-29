"""One live setting stepped on the clock, each step right after a save (owner, 2026-10-29: v0.6.1's pull toward level faded,
"one 0.01 step per 10 updates"; v0.6.1b's brain fade). A save is the trainer rewriting <run>/policy.pt (every 10 updates; the
watcher's keep/ copy is not needed, so it works in a smoke run without one): once the file has stood still for --settle s, the
first save is kept under --keep-as (the network before the first step), then NAME is set to FROM + STEP at once and one STEP more
right after each later save, at least --min-s apart, until TO. Logs <run>/watch/ramp.log and a RAMP line in watch.log. Nothing
else is touched.

    python tools/run/ramp_live.py <run> LEVEL_PULL 0.95 1.0 0.01 --keep-as policy_prelevel_v061.pt"""
import argparse
import json
import os
import shutil
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("name")
    ap.add_argument("frm", type=float)
    ap.add_argument("to", type=float)
    ap.add_argument("step", type=float)
    ap.add_argument("--every", type=int, default=1, help="saves between steps (a save every 10 updates)")
    ap.add_argument("--min-s", type=float, default=25 * 60)
    ap.add_argument("--keep-as", default="", help="keep the save before the first step as keep/<this>")
    ap.add_argument("--dir", default="", help="the run's folder (default data/sim_runs/<run>)")
    ap.add_argument("--sleep", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20, help="seconds policy.pt must stand still before it counts as saved")
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    LIVE, MET, POL, KEEP, WD = (os.path.join(D, x) for x in ("live.json", "metrics.jsonl", "policy.pt", "keep", "watch"))

    def log(s):
        line = time.strftime("%m-%d %H:%M:%S ") + s
        os.makedirs(WD, exist_ok=True)
        for f in ("ramp.log", "watch.log"):
            with open(os.path.join(WD, f), "a") as fh:
                fh.write(line + "\n")
        print(line, flush=True)

    def update():
        try:
            with open(MET) as f:
                L = [x for x in f if x.strip()]
        except FileNotFoundError:                            # (a fresh run: no update yet)
            return 0
        return int(json.loads(L[-1])["update"]) if L else 0

    def mtime():
        try:
            return os.path.getmtime(POL)
        except FileNotFoundError:
            return 0.0

    def put(v):
        d = json.load(open(LIVE, encoding="utf-8"))
        d[a.name] = v
        open(LIVE + ".tmp", "w", encoding="utf-8").write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)

    cur = json.load(open(LIVE, encoding="utf-8")).get(a.name)
    assert cur is None or abs(float(cur) - a.frm) < 1e-9, "{} is {} in live.json, not {}".format(a.name, cur, a.frm)
    sign = 1.0 if a.to >= a.frm else -1.0
    v = a.frm
    log("ramp_live on for {}: {} {} -> {} by {} right after a save (policy.pt rewritten), every {} save(s), at least {:g} min apart".format(
        a.run, a.name, a.frm, a.to, a.step, a.every, a.min_s / 60))
    seen = mtime()                                           # (the start file, or the last save before now: not a new save)
    saves, t_last = 0, 0.0
    while sign * (a.to - v) > 1e-9:
        time.sleep(a.sleep)
        m_ = mtime()
        if m_ <= seen or time.time() - m_ < a.settle:
            continue
        seen = m_
        saves += 1
        n = update()
        if (saves - 1) % a.every or time.time() - t_last < a.min_s:
            log("save at update {}: no step (every {} saves, at least {:g} min apart)".format(n, a.every, a.min_s / 60))
            continue
        if a.keep_as and t_last == 0.0:
            os.makedirs(KEEP, exist_ok=True)
            shutil.copy2(POL, os.path.join(KEEP, a.keep_as))
            log("kept the save of update {} as keep/{} (before the first step)".format(n, a.keep_as))
        v = round(v + sign * a.step, 6)
        v = a.to if sign * (v - a.to) > 0 else v
        put(v)
        log("RAMP {} {} (right after the save of update {}; it takes effect at the next rollout)".format(a.name, v, n))
        t_last = time.time()
    log("ramp_live done: {} at {}".format(a.name, v))


if __name__ == "__main__":
    main()
