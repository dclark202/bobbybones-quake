"""1.4b's dials (owner, 2026-11-03; CARD.md), on one clock of updates that stops while the checks say so:
  PFSP            0 -> 1      over clock 0 to 10   (matchmaking by difficulty)
  INTENT_TEACH_W  1 -> 0      over clock 10 to 70  (the item rule's lesson out: "the meat of the run")
  SPEED_PAY       0.125 -> 0  over clock 70 to 90  (the speed pay out)
Each dial is a straight line of the clock, written to live.json (read between rollouts) after each new update. The clock moves one a new
update; it stops while the last check against the start (checks_prev) reads under 50%, and steps back --back updates if one reads under 45%
or two in a row under 50% (the owner's rule, 2026-10-24); the bars are moved by the checks' zero point (--zero). A stop delays every later
dial. Every save while the clock is under its end is kept with its optimizer (keep/policy_u<update>_14b.pt), and the first save with the
clock at 10, 70 and 90 as keep/policy_step<10|70|90>_14b.pt. Flagged in watch.log: a check under 50%; a part of his target scores over 40;
his speed on trips or its share over 320 more than 10% under the run's first five updates; his trips a minute more than 50% over them.
Nothing here stops the run.
    python docs/runs/b1.4/1.4b/ramp_14b.py <run> [--back 10] [--zero 0.5] [--poll S] [--settle S] [--dir D]"""
import argparse
import json
import os
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DIALS = (("PFSP", 0, 10, 0.0, 1.0), ("INTENT_TEACH_W", 10, 70, 1.0, 0.0), ("SPEED_PAY", 70, 90, 0.125, 0.0))
END = max(d[2] for d in DIALS)
MARKS = (10, 70, 90)
SIZE_FLAG = 40.0


def dial_at(clock, lo, hi, v0, v1):
    f = min(1.0, max(0.0, (clock - lo) / float(hi - lo)))
    return v0 + (v1 - v0) * f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--back", type=int, default=10)
    ap.add_argument("--zero", type=float, default=0.5, help="the checks' zero point (the same network against itself)")
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    WD, LIVE, POL, OPT, KEEP, MET = (os.path.join(D, "watch"), os.path.join(D, "live.json"), os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt"),
                                     os.path.join(D, "keep"), os.path.join(D, "metrics.jsonl"))
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
        names = {"checks_prev.jsonl": "the start (1.3b's end)", "checks_ref.jsonl": "b1.2d's end"}
        seen_m, base = [0], []
        while True:
            for f_, n_ in seen.items():
                R = jl(os.path.join(WD, f_))
                for d in R[n_:]:
                    if wr(d) < HOLD:
                        log("FLAG check update {} against {}: {}-{} = {:.1%} (the bar {:.1%})".format(d["update"], names[f_], d["won"], d["lost"], wr(d), HOLD))
                seen[f_] = len(R)
            for m_ in jl(MET)[seen_m[0]:]:
                seen_m[0] += 1
                u_ = m_.get("update")
                h_ = m_.get("head2") or {}
                big_ = {k_: h_.get(k_) for k_ in ("hands", "raw") if (h_.get(k_) or 0) > SIZE_FLAG}
                if big_:
                    log("FLAG update {}: a part of his target scores over {}: {}".format(u_, SIZE_FLAG, big_))
                pc_, it_ = m_.get("pace") or {}, m_.get("intent") or {}
                now_ = (pc_.get("trip_speed"), pc_.get("over_320"), it_.get("trips_per_player_min"))
                if None in now_:
                    continue
                if len(base) < 5:                            # (owner: "speed is the thing to watch") the run's first five updates
                    base.append(now_)
                    continue
                b_ = [sum(x[i] for x in base) / len(base) for i in range(3)]
                if now_[0] < 0.9 * b_[0] or now_[1] < 0.9 * b_[1]:
                    log("FLAG update {}: speed on trips {} (start {:.0f}), share over 320 {} (start {:.3f})".format(u_, now_[0], b_[0], now_[1], b_[1]))
                if now_[2] > 1.5 * b_[2]:
                    log("FLAG update {}: trips a player-minute {} (start {:.1f}): flicker?".format(u_, now_[2], b_[2]))
            time.sleep(a.poll)

    def mtime():
        try:
            return os.path.getmtime(POL)
        except FileNotFoundError:
            return 0.0

    def keep(name):
        shutil.copy2(POL, os.path.join(KEEP, name))
        shutil.copy2(OPT, os.path.join(KEEP, name.replace("policy_", "opt_", 1)))

    def write(clock):
        d = json.load(open(LIVE, encoding="utf-8"))
        for n_, lo, hi, v0, v1 in DIALS:
            d[n_] = round(dial_at(clock, lo, hi, v0, v1), 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        return {n_: d[n_] for n_, *_ in DIALS}

    cur = json.load(open(LIVE, encoding="utf-8"))
    for n_, lo, hi, v0, v1 in DIALS:
        assert abs(float(cur.get(n_, -1)) - v0) < 1e-9, "{} is {} in live.json, not {}".format(n_, cur.get(n_), v0)
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_14b on for {}: {}; the clock stops under {:.1%}, back {} updates under {:.1%} or two checks under {:.1%} (zero point {:.1%})".format(
        a.run, ", ".join("{} {} -> {} over {} to {}".format(n_, v0, v1, lo, hi) for n_, lo, hi, v0, v1 in DIALS), HOLD, a.back, BACK, HOLD, a.zero))
    clock, done_n, seen, held, n_checks, marked = 0.0, 0, mtime(), False, 0, set()
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        C = jl(os.path.join(WD, "checks_prev.jsonl"))
        if len(C) > n_checks:                                # a new check: hold, lift or step back
            n_checks = len(C)
            last = wr(C[-1])
            two = len(C) >= 2 and wr(C[-2]) < HOLD and last < HOLD
            if clock < END and (last < BACK or two):
                c_ = max(0.0, clock - a.back)
                v_ = write(c_)
                log("BACK at update {}: the check of update {} {}-{} = {:.1%}{}; the clock {:.0f} -> {:.0f}: {}".format(
                    n, C[-1]["update"], C[-1]["won"], C[-1]["lost"], last, " (two under the bar)" if two else "", clock, c_, v_))
                clock = c_
            low = last < HOLD
            if low != held:
                held = low
                log(("HOLD at update {}: the last check {:.1%} is under {:.1%}; the clock stays at {:.0f}" if low else
                     "the hold lifts at update {}: the last check {:.1%} is not under {:.1%}; the clock goes on from {:.0f}").format(n, last, HOLD, clock))
        if n > done_n:
            if clock < END and not held:
                clock = min(float(END), clock + (n - done_n))
                v_ = write(clock)
                log("clock {:.0f} after update {}: {}".format(clock, n, v_))
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            for k_ in MARKS:
                if clock >= k_ and k_ not in marked:
                    marked.add(k_)
                    keep("policy_step{}_14b.pt".format(k_))
                    log("the clock at {}: kept keep/policy_step{}_14b.pt at the save of update {}".format(k_, k_, n))
            if clock < END or END not in marked:
                keep("policy_u{}_14b.pt".format(n))
                log("save at update {} kept with its optimizer (clock {:.0f})".format(n, clock))


if __name__ == "__main__":
    main()
