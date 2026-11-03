"""1.3b's credit dial (owner, 2026-11-03; CARD.md): live H2_PG, the share c of his target choice's gradient that comes from the strategy head's
own advantage (the rest, 1 - c, from his own), moves 0 -> 1 in a straight line over updates 10 to 90 (--start, --over; owner 11-03: 80 updates), written after each new
update (live.json, read between rollouts). The owner's rule for a new thing (2026-10-24): it holds while the last check against the start reads
under 50%, and steps back --back updates if one reads under 45% or two in a row under 50%; each bar is moved by the checks' zero point (--zero:
the same network against itself; 0.5 until measured). A check under 50% is flagged in watch.log. Each save during the dial is kept with its
optimizer (keep/policy_credit<update>_13b.pt), the first save at c = 1 as keep/policy_credited_13b.pt. Nothing here stops the run.
    python docs/runs/b1.3/1.3b/ramp_13b.py <run> [--start 10] [--over 80] [--back 10] [--zero 0.5] [--poll S] [--settle S] [--dir D]"""
import argparse
import json
import os
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DIAL = "H2_PG"
SIZE_FLAG = 40.0                                             # (the parts' centred lengths, head2.hands and head2.raw: about 24 and 0 at the start)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--start", type=int, default=10)
    ap.add_argument("--over", type=int, default=80)
    ap.add_argument("--back", type=int, default=10)
    ap.add_argument("--zero", type=float, default=0.5, help="the checks' zero point (the same network against itself)")
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    WD, LIVE, POL, OPT, KEEP, MET = os.path.join(D, "watch"), os.path.join(D, "live.json"), os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt"), os.path.join(D, "keep"), os.path.join(D, "metrics.jsonl")
    os.makedirs(WD, exist_ok=True)
    os.makedirs(KEEP, exist_ok=True)
    HOLD, BACK = 0.50 + (a.zero - 0.5), 0.45 + (a.zero - 0.5)

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

    def wr(d):
        return d["won"] / max(1, d["won"] + d["lost"])

    def flags():
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": "the start (b1.2d's end)", "checks_ref.jsonl": "b1.1"}
        seen_m = [len(jl(MET))]
        while True:
            for f_, n_ in seen.items():
                R = jl(os.path.join(WD, f_))
                for d in R[n_:]:
                    if wr(d) < HOLD:
                        log("FLAG check update {} against {}: {}-{} = {:.1%} (the bar {:.1%})".format(d["update"], names[f_], d["won"], d["lost"], wr(d), HOLD))
                seen[f_] = len(R)
            for m_ in jl(MET)[seen_m[0]:]:                    # (owner, 11-03: L2 only, no cap) a part of his target scores over SIZE_FLAG is flagged
                h_ = m_.get("head2") or {}
                big_ = {k_: h_.get(k_) for k_ in ("hands", "raw") if (h_.get(k_) or 0) > SIZE_FLAG}
                if big_:
                    log("FLAG update {}: a part of his target scores over {}: {} (raise live H2_L2?)".format(m_.get("update"), SIZE_FLAG, big_))
                seen_m[0] += 1
            time.sleep(a.poll)

    def mtime():
        try:
            return os.path.getmtime(POL)
        except FileNotFoundError:
            return 0.0

    def keep(name):
        shutil.copy2(POL, os.path.join(KEEP, name))
        shutil.copy2(OPT, os.path.join(KEEP, name.replace("policy_", "opt_", 1)))

    def write(c):
        d = json.load(open(LIVE, encoding="utf-8"))
        d[DIAL] = round(c, 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)

    cur = json.load(open(LIVE, encoding="utf-8"))
    assert abs(float(cur.get(DIAL, -1))) < 1e-9, "{} is {} in live.json, not 0".format(DIAL, cur.get(DIAL))
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_13b on for {}: {} 0 -> 1 over {} updates from update {}; hold under {:.1%}, back {} updates under {:.1%} or two checks under {:.1%} (zero point {:.1%})".format(
        a.run, DIAL, a.over, a.start, HOLD, a.back, BACK, HOLD, a.zero))
    c, done_n, seen, held, done_kept, n_checks = 0.0, 0, mtime(), False, False, 0
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        C = jl(os.path.join(WD, "checks_prev.jsonl"))
        if len(C) > n_checks:                                # a new check: hold, lift or step back
            n_checks = len(C)
            last = wr(C[-1])
            two = len(C) >= 2 and wr(C[-2]) < HOLD and last < HOLD
            if c < 1.0 and (last < BACK or two):
                c_ = max(0.0, c - a.back / float(a.over))
                log("BACK at update {}: the check of update {} {}-{} = {:.1%}{}; {} {:.3f} -> {:.3f}".format(
                    n, C[-1]["update"], C[-1]["won"], C[-1]["lost"], last, " (two under the bar)" if two else "", DIAL, c, c_))
                c = c_
                write(c)
            low = last < HOLD
            if low != held:
                held = low
                log(("HOLD at update {}: the last check {:.1%} is under {:.1%}; {} stays at {:.3f}" if low else
                     "the hold lifts at update {}: the last check {:.1%} is not under {:.1%}; {} goes on from {:.3f}").format(n, last, HOLD, DIAL, c))
        if n > done_n and c < 1.0:
            inc_ = max(0, n - max(done_n, a.start))          # (--start) the dial moves after this update
            if not held and inc_ > 0:
                c = min(1.0, c + inc_ / float(a.over))
                write(c)
                log("{} {:.3f} after update {}".format(DIAL, c, n))
            done_n = n
        elif n > done_n:
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            if c < 1.0 or not done_kept:
                if c >= 1.0:
                    keep("policy_credited_13b.pt")
                    done_kept = True
                    log("the dial at 1: kept keep/policy_credited_13b.pt at the save of update {}".format(n))
                elif n >= a.start:
                    keep("policy_credit{}_13b.pt".format(n))
                    log("save at update {} kept with its optimizer ({} {:.3f})".format(n, DIAL, c))


if __name__ == "__main__":
    main()
