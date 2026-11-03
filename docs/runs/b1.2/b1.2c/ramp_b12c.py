"""b1.2c's schedule (owner, 2026-11-01; CARD.md): the table is in force from the start; this moves three live dials, a step right after a save, at least --min-s apart: COST_FIRE_W 0.8, 0.6, 0.4, 0.2, 0 at updates 60 to 100;
CONTACT_FREE 0.25, 0.5, 0.75, 1 at updates 120 to 180; COST_JERK_W 0.8, 0.6, 0.4, 0.2, 0 at updates 200 to 240. The save before each step is kept with its optimizer (keep/policy_step<n>_b12c.pt), and the stages' ends under their names. A check of 40% or less against the start holds the next step
until a later check is above it; a check under 50% is flagged in watch.log. Nothing here stops the run.
    python docs/runs/b1.2/b1.2c/ramp_b12c.py <run> [--min-s S] [--poll S] [--settle S] [--dir D]"""
import argparse
import json
import os
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
VALS = (0.8, 0.6, 0.4, 0.2, 0.0)
STEPS = [("COST_FIRE_W", v) for v in VALS] + [("CONTACT_FREE", v) for v in (0.25, 0.5, 0.75, 1.0)] + [("COST_JERK_W", v) for v in VALS]
GAPS = (6, 1, 1, 1, 1, 2, 2, 2, 2, 2, 1, 1, 1, 1)            # saves before each step (a save every 10 updates)
NAMED = {0: "policy_table_b12c.pt", 5: "policy_nofire_b12c.pt", 9: "policy_contact_b12c.pt"}     # (the save before step n, counted from 0: a stage's end)
START = {"COST_FIRE_W": 1.0, "COST_JERK_W": 1.0, "CONTACT_FREE": 0.0}
HOLD_AT = 0.40


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--min-s", type=float, default=25 * 60)
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    WD, LIVE, POL, OPT, KEEP, MET = os.path.join(D, "watch"), os.path.join(D, "live.json"), os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt"), os.path.join(D, "keep"), os.path.join(D, "metrics.jsonl")
    os.makedirs(WD, exist_ok=True)
    os.makedirs(KEEP, exist_ok=True)

    def log(s):
        line = time.strftime("%m-%d %H:%M:%S ") + s
        for f in ("ramp.log", "watch.log"):
            with open(os.path.join(WD, f), "a") as fh:
                fh.write(line + "\n")

    def jl(p):
        try:
            with open(p) as f:
                return [json.loads(x) for x in f if x.strip()]
        except FileNotFoundError:
            return []

    def flags():
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": "the start", "checks_ref.jsonl": "v0.6.0's end"}
        while True:
            for f_, n_ in seen.items():
                R = jl(os.path.join(WD, f_))
                for d in R[n_:]:
                    wr_ = d["won"] / max(1, d["won"] + d["lost"])
                    if wr_ < 0.5:
                        log("FLAG check update {} against {}: {}-{} = {:.1%}".format(d["update"], names[f_], d["won"], d["lost"], wr_))
                seen[f_] = len(R)
            time.sleep(a.poll)

    def mtime():
        try:
            return os.path.getmtime(POL)
        except FileNotFoundError:
            return 0.0

    cur = json.load(open(LIVE, encoding="utf-8"))
    for k_, v_ in START.items():
        assert abs(float(cur.get(k_, -1)) - v_) < 1e-9, "{} is {} in live.json, not {}".format(k_, cur.get(k_), v_)
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_b12c on for {}: {} steps, saves between them {}, at least {:g} min apart; held at a check of {:.0%} or less".format(a.run, len(STEPS), GAPS, a.min_s / 60, HOLD_AT))
    seen, due, t_last, i, due_end = mtime(), GAPS[0], 0.0, 0, 2
    while i < len(STEPS):
        time.sleep(a.poll)
        m_ = mtime()
        if m_ <= seen or time.time() - m_ < a.settle:
            continue
        seen = m_
        due -= 1
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        if due > 0 or time.time() - t_last < a.min_s:
            log("save at update {}: no step".format(n))
            continue
        c_ = jl(os.path.join(WD, "checks_prev.jsonl"))
        if c_ and c_[-1]["won"] / max(1, c_[-1]["won"] + c_[-1]["lost"]) <= HOLD_AT:
            log("HOLD at the save of update {}: the last check {}-{} is {:.0%} or less".format(n, c_[-1]["won"], c_[-1]["lost"], HOLD_AT))
            continue
        name, val = STEPS[i]
        ke_ = "policy_step{}_b12c.pt".format(i)
        shutil.copy2(POL, os.path.join(KEEP, ke_))
        shutil.copy2(OPT, os.path.join(KEEP, ke_.replace("policy_", "opt_", 1)))
        if i in NAMED:
            shutil.copy2(POL, os.path.join(KEEP, NAMED[i]))
            shutil.copy2(OPT, os.path.join(KEEP, NAMED[i].replace("policy_", "opt_", 1)))
        d = json.load(open(LIVE, encoding="utf-8"))
        d[name] = val
        with open(LIVE + ".tmp", "w", encoding="utf-8") as f:
            f.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        log("RAMP {} {} (step {} of {}, right after the save of update {}, kept as keep/{}; last check {})".format(name, val, i + 1, len(STEPS), n, ke_, "{}-{}".format(c_[-1]["won"], c_[-1]["lost"]) if c_ else "none yet"))
        i, t_last = i + 1, time.time()
        due = GAPS[i] if i < len(STEPS) else 0
    log("ramp_b12c: every step taken; the checks are still flagged")
    while due_end > 0:                                       # the last stage's end, as the others': two saves after its last step
        time.sleep(a.poll)
        m_ = mtime()
        if m_ <= seen or time.time() - m_ < a.settle:
            continue
        seen = m_
        due_end -= 1
    shutil.copy2(POL, os.path.join(KEEP, "policy_nojerk_b12c.pt"))
    shutil.copy2(OPT, os.path.join(KEEP, "opt_nojerk_b12c.pt"))
    log("ramp_b12c done: the last stage's end kept as keep/policy_nojerk_b12c.pt")
    while True:
        time.sleep(a.poll)


if __name__ == "__main__":
    main()
