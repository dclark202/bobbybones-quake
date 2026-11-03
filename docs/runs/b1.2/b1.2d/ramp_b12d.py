"""b1.2d's fade (owner, 2026-11-02: "all go at the start, fade over 40 updates from where they are now. All five changes"; then "fade starts at u10 and takes 60 updates"; CARD.md): five live dials move together in a straight line from b1.2c's
values to b1.2d's over updates 10 to 70 (--start, --over), written after each new update (live.json, read between rollouts): the table by the point (ITEM_PT_MIX 0 -> 1), SPEED_PAY 0.25 -> 0.125, DMG_TAKEN_W 1 -> 0.8,
STACK_DIFF 0.7 -> 0, RAIL_FAR_PAY 0.12 -> 0.25. Each save during the fade is kept with its optimizer (keep/policy_fade<update>_b12d.pt), and the first save with the fade done as keep/policy_faded_b12d.pt.
A check of 40% or less against the start holds the fade where it is until a later check is above it; a check under 50% is flagged in watch.log. Nothing here stops the run.
    python docs/runs/b1.2/b1.2d/ramp_b12d.py <run> [--over N] [--poll S] [--settle S] [--dir D]"""
import argparse
import json
import os
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DIALS = {"ITEM_PT_MIX": (0.0, 1.0), "SPEED_PAY": (0.25, 0.125), "DMG_TAKEN_W": (1.0, 0.8), "STACK_DIFF": (0.7, 0.0), "RAIL_FAR_PAY": (0.12, 0.25)}
FIXED = {"ITEM_PT_LO": 0.004, "ITEM_PT_HI": 0.002, "ITEM_DECAY": 0.002}
HOLD_AT = 0.40


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--start", type=int, default=10)
    ap.add_argument("--over", type=int, default=60)
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

    def write(f):
        d = json.load(open(LIVE, encoding="utf-8"))
        for k_, (s_, e_) in DIALS.items():
            d[k_] = round(s_ + f * (e_ - s_), 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        return {k_: d[k_] for k_ in DIALS}

    cur = json.load(open(LIVE, encoding="utf-8"))
    for k_, (s_, _) in DIALS.items():
        assert abs(float(cur.get(k_, -1)) - s_) < 1e-9, "{} is {} in live.json, not {}".format(k_, cur.get(k_), s_)
    for k_, v_ in FIXED.items():
        assert abs(float(cur.get(k_, -1)) - v_) < 1e-9, "{} is {} in live.json, not {}".format(k_, cur.get(k_), v_)
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_b12d on for {}: {} dials from b1.2c's values to b1.2d's over {} updates from update {}: {}; held at a check of {:.0%} or less".format(a.run, len(DIALS), a.over, a.start, DIALS, HOLD_AT))
    f, done_n, seen, held, faded_kept = 0.0, 0, mtime(), False, False
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        c_ = jl(os.path.join(WD, "checks_prev.jsonl"))
        low = bool(c_) and c_[-1]["won"] / max(1, c_[-1]["won"] + c_[-1]["lost"]) <= HOLD_AT
        if low != held:
            held = low
            log(("HOLD at update {}: the last check {}-{} is {:.0%} or less; the fade stays at {:.3f}" if low else "the hold lifts at update {}: the last check {}-{} is above {:.0%}; the fade goes on from {:.3f}").format(
                n, c_[-1]["won"], c_[-1]["lost"], HOLD_AT, f))
        if n > done_n and f < 1.0:
            inc_ = max(0, n - max(done_n, a.start))          # (--start) the fade begins after this update
            if not held and inc_ > 0:
                f = min(1.0, f + inc_ / float(a.over))
                v_ = write(f)
                log("FADE {:.3f} after update {}: {}".format(f, n, v_))
            done_n = n
        elif n > done_n:
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            if f < 1.0 or not faded_kept:
                if f >= 1.0:
                    keep("policy_faded_b12d.pt")
                    faded_kept = True
                    log("the fade done: kept keep/policy_faded_b12d.pt at the save of update {}".format(n))
                else:
                    keep("policy_fade{}_b12d.pt".format(n))
                    log("save at update {} kept with its optimizer (fade {:.3f})".format(n, f))


if __name__ == "__main__":
    main()
