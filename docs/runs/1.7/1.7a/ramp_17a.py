"""1.7a's dial (owner, 2026-11-04 night: "start the lock handover ... and let it go for 80 updates"; CARD.md), on the clock of updates done:
  KEEP_G          0 -> 1      over updates 10 to 90  (the hand-over: the share of his seconds the keep choice decides; the lock rule the rest)
then held at 1 to the run's end (the lock out of his play). Written to live.json (read between rollouts) after each new update. The clock
never holds or steps back (owner, 2026-11-04; CLAUDE.md rule 6): every check is logged with its win rate, one under 40% as a MAJOR PROBLEM,
and the owner decides. Kept with their optimizers: the first saves at or past updates 10 (share 0), 50 (0.5) and 90 (1)
(keep/policy_u<update>_17a.pt). Logged in watch.log each update: the keep choice's record (its share, readings a second in its seconds,
re-decisions in contact, heard, quiet and at arrivals, the parts of its logit: the head's state against its own numbers, i.e. whose decision
it is), trips and targets reached, speed, big weapons owned, his weapon in hand, the firing cost. Flagged: targets reached 30% under the run's
first five updates or trips a minute 50% over (b1.1a's flicker), speed 10% under, big weapons owned 0.05 under, the keep choice's step on
the head's term over 0.05, a part of his target or weapon scores over 40, any firing cost above zero (the owner's rule: none at all).
Nothing here stops the run.
    python docs/runs/1.7/1.7a/ramp_17a.py <run> [--poll S] [--settle S] [--dir D] [--resume]"""
import argparse
import json
import os
import shutil
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DIALS = (("KEEP_G", 10, 90, 0.0, 1.0),)
END = max(d[2] for d in DIALS)
MARKS = (10, 50, 90)
SIZE_FLAG = 40.0
MAJOR = 0.40


def dial_at(clock, lo, hi, v0, v1):
    f = min(1.0, max(0.0, (clock - lo) / float(hi - lo)))
    return v0 + (v1 - v0) * f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    WD, LIVE, POL, OPT, KEEP, MET = (os.path.join(D, "watch"), os.path.join(D, "live.json"), os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt"),
                                     os.path.join(D, "keep"), os.path.join(D, "metrics.jsonl"))
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

    def wr(d):
        return d["won"] / max(1, d["won"] + d["lost"])

    def flags():
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": "the start (1.6a's end)", "checks_ref.jsonl": "b1.2d's end"}
        if a.resume:
            seen = {f_: len(jl(os.path.join(WD, f_))) for f_ in seen}
        seen_m, base, bw0 = [len(jl(MET)) if a.resume else 0], [], []
        while True:
            for f_, n_ in seen.items():
                R = jl(os.path.join(WD, f_))
                for d in R[n_:]:
                    log(("MAJOR PROBLEM " if wr(d) < MAJOR else "") + "check update {} against {}: {}-{} = {:.1%}{}".format(
                        d["update"], names[f_], d["won"], d["lost"], wr(d), " (under 40%)" if wr(d) < MAJOR else ""))
                seen[f_] = len(R)
            for m_ in jl(MET)[seen_m[0]:]:
                seen_m[0] += 1
                u_ = m_.get("update")
                k_ = m_.get("keep") or {}
                s2_ = k_.get("sim2") or {}
                pl_ = k_.get("pull") or {}
                ar_ = k_.get("arrived") or {}
                log("update {}: keep share {} | its seconds {} readings a second {} decided {} re-decide {} (contact {}, heard {}, quiet {}, "
                    "arrived {}) | pull: head state {} hands {} own numbers {} | kl {} | arrivals {} p {}".format(
                        u_, k_.get("g"), s2_.get("seconds"), s2_.get("readings_a_second"), s2_.get("decided"), s2_.get("redecide"),
                        s2_.get("redecide_contact"), s2_.get("redecide_heard"), s2_.get("redecide_quiet"), s2_.get("redecide_arrived"),
                        pl_.get("s"), pl_.get("hands"), pl_.get("own"), k_.get("kl"), ar_.get("share"), ar_.get("p")))
                if (k_.get("kl") or 0) > 0.05:
                    log("FLAG update {}: the keep choice's step on the head's term {} (over 0.05)".format(u_, k_.get("kl")))
                ih_ = (m_.get("v15") or {}).get("in_hand_games") or {}
                wp_ = m_.get("weapon") or {}
                bw_ = (m_.get("stack") or {}).get("big_weapons")
                sc_ = m_.get("shot_cost_per_player_min")
                fc_ = {k2_: v_ for k2_, v_ in ((m_.get("pay_terms") or {}).get("per_player_min") or {}).items()
                       if any(w_ in k2_ for w_ in ("shot", "fire", "switch", "blind")) and v_}
                log("update {}: big weapons owned {} | in hand in games rockets {} lightning {} rail {} | firing cost {} {}".format(
                    u_, bw_, ih_.get("rl"), ih_.get("lg"), ih_.get("rg"), sc_, fc_ or ""))
                if bw_ is not None:
                    if len(bw0) < 5:
                        bw0.append(bw_)
                    elif bw_ < sum(bw0) / len(bw0) - 0.05:
                        log("FLAG update {}: big weapons owned {} (start {:.3f}): 1.4b's drift?".format(u_, bw_, sum(bw0) / len(bw0)))
                if (sc_ or 0) > 0 or any(v_ < 0 for v_ in fc_.values()):
                    log("FLAG update {}: A FIRING COST ABOVE ZERO: shot cost {} {}".format(u_, sc_, fc_))
                big_ = {k2_: wp_.get(k2_) for k2_ in ("hands", "head") if (wp_.get(k2_) or 0) > SIZE_FLAG}
                if big_:
                    log("FLAG update {}: a part of his weapon-key scores over {}: {}".format(u_, SIZE_FLAG, big_))
                h2_ = m_.get("head2") or {}
                big2_ = {k2_: h2_.get(k2_) for k2_ in ("hands", "raw") if (h2_.get(k2_) or 0) > SIZE_FLAG}
                if big2_:
                    log("FLAG update {}: a part of his target scores over {}: {}".format(u_, SIZE_FLAG, big2_))
                pc_, it_ = m_.get("pace") or {}, m_.get("intent") or {}
                now_ = (pc_.get("trip_speed"), pc_.get("over_320"), it_.get("trips_per_player_min"), it_.get("reached"))
                if None in now_:
                    continue
                log("update {}: trips a player-minute {} reached {} | speed on trips {} over 320 {}".format(u_, now_[2], now_[3], now_[0], now_[1]))
                if len(base) < 5:                            # (owner: "speed is the thing to watch") the run's first five updates
                    base.append(now_)
                    continue
                b_ = [sum(x[i] for x in base) / len(base) for i in range(4)]
                if now_[3] < 0.7 * b_[3]:
                    log("FLAG update {}: targets reached {} (start {:.3f}): flicker?".format(u_, now_[3], b_[3]))
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
    for n_, lo, hi, v0, v1 in ([] if a.resume else DIALS):
        assert abs(float(cur.get(n_, -1)) - v0) < 1e-9, "{} is {} in live.json, not {}".format(n_, cur.get(n_), v0)
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_17a on for {}: {}; FREE: the clock never holds or steps back, a check under 40% is a MAJOR PROBLEM{}".format(
        a.run, ", ".join("{} {} -> {} over updates {} to {}".format(n_, v0, v1, lo, hi) for n_, lo, hi, v0, v1 in DIALS), " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = int(L0[-1]["update"]) if (a.resume and L0) else 0
    seen, marked = mtime(), set()
    if a.resume:
        marked = {k_ for k_ in MARKS if any(f_.startswith("policy_u") and f_.endswith("_17a.pt") and int(f_[8:-7]) >= k_
                                            for f_ in os.listdir(KEEP) if f_[8:-7].isdigit())}
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        if n > done_n:
            if done_n < END or n <= END:
                v_ = write(float(n))
                log("clock {} after update {}: {}".format(min(n, END), n, v_))
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            for k_ in MARKS:
                if n >= k_ and k_ not in marked:
                    marked.add(k_)
                    keep("policy_u{}_17a.pt".format(n))
                    log("kept keep/policy_u{}_17a.pt with its optimizer (the mark {})".format(n, k_))


if __name__ == "__main__":
    main()
