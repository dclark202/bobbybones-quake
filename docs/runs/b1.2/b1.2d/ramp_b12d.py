"""b1.2d's schedule (owner, 2026-11-02; CARD.md): the table is in force from the start; this moves two live dials, a step right after a save, at least --min-s apart: SPEED_PAY 0.19, 0.125 at
updates 30 and 40; RAIL_FAR_PAY 0.18, 0.25 at updates 70 and 80. The save before each step is kept with its optimizer (keep/policy_step<n>_b12d.pt), the stages' ends under their names, the last
two saves after its last step. A check of 40% or less against the start holds the next step until a later check is above it; a check under 50% is flagged in watch.log. Nothing here stops the run.
    python docs/runs/b1.2/b1.2d/ramp_b12d.py <run> [--min-s S] [--poll S] [--settle S] [--dir D]"""
import argparse
import json
import os
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
STEPS = [("SPEED_PAY", 0.19), ("SPEED_PAY", 0.125), ("RAIL_FAR_PAY", 0.18), ("RAIL_FAR_PAY", 0.25)]
GAPS = (3, 1, 3, 1)                                          # saves before each step (a save every 10 updates)
NAMED = {0: "policy_table_b12d.pt", 2: "policy_speed_b12d.pt"}     # (the save before step n, counted from 0: a stage's end)
END = "policy_rail_b12d.pt"                                  # (two saves after the last step)
START = {"SPEED_PAY": 0.25, "RAIL_FAR_PAY": 0.12, "ITEM_PT_LO": 0.004, "ITEM_PT_HI": 0.002, "ITEM_DECAY": 0.002}
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
        names = {"checks_prev.jsonl": "the start (b1.2c's end)", "checks_ref.jsonl": "b1.1"}
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

    def keep(name):
        shutil.copy2(POL, os.path.join(KEEP, name))
        shutil.copy2(OPT, os.path.join(KEEP, name.replace("policy_", "opt_", 1)))

    cur = json.load(open(LIVE, encoding="utf-8"))
    for k_, v_ in START.items():
        assert abs(float(cur.get(k_, -1)) - v_) < 1e-9, "{} is {} in live.json, not {}".format(k_, cur.get(k_), v_)
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_b12d on for {}: {} steps, saves between them {}, at least {:g} min apart; held at a check of {:.0%} or less".format(a.run, len(STEPS), GAPS, a.min_s / 60, HOLD_AT))
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
        ke_ = "policy_step{}_b12d.pt".format(i)
        keep(ke_)
        if i in NAMED:
            keep(NAMED[i])
        d = json.load(open(LIVE, encoding="utf-8"))
        d[name] = val
        with open(LIVE + ".tmp", "w", encoding="utf-8") as f:
            f.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        log("RAMP {} {} (step {} of {}, right after the save of update {}, kept as keep/{}; last check {})".format(name, val, i + 1, len(STEPS), n, ke_, "{}-{}".format(c_[-1]["won"], c_[-1]["lost"]) if c_ else "none yet"))
        i, t_last = i + 1, time.time()
        due = GAPS[i] if i < len(STEPS) else 0
    log("ramp_b12d: every step taken; the checks are still flagged")
    while due_end > 0:                                       # the last stage's end: two saves after its last step
        time.sleep(a.poll)
        m_ = mtime()
        if m_ <= seen or time.time() - m_ < a.settle:
            continue
        seen = m_
        due_end -= 1
    keep(END)
    log("ramp_b12d done: the last stage's end kept as keep/" + END)
    while True:
        time.sleep(a.poll)


if __name__ == "__main__":
    main()
