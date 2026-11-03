"""b1.4a's fades (owner, 2026-11-02 evening: "B1.4 - fade OLD rules out"; CARD.md): live dials in a straight line each, on one clock of
updates that stops while a hold is on, written after each new update (live.json, read between rollouts):
  A  H2_MIX 0 -> 1 over clock 10 to 50: his target choice moves from the hands' (the rules' imprint, frozen) to the head's own
     H2_COPY 1 -> 0 over clock 10 to 70: the copy lesson (the head held near the hands' choice) fades behind it
  B  INTENT_HOLD 8 -> 0 over clock 50 to 80: the target lock out
  C  INTENT_SEEK_W 1 -> 0 over clock 80 to 110: the way pay out
(--scale stretches or shrinks every span; the card's numbers are at 1.) Each save during the fades is kept with its optimizer
(keep/policy_fade<update>_b14a.pt); the first save past each fade's end as keep/policy_<A|B|C>done_b14a.pt.
A check of 40% or less against the start holds the clock until a later check is above it; a check under 50% is flagged. The tripwire
(flagged, nothing stopped): the head's own target logits' centred length over --raw-lim, a non-finite number, a skipped piece.
Nothing here stops the run.
    python docs/runs/b1.4/b1.4a/ramp_b14a.py <run> [--start 10] [--scale 1] [--raw-lim 60] [--poll S] [--settle S] [--dir D]"""
import argparse
import json
import math
import os
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
# name: (from, to, clock start, clock end) at --scale 1, the clock counted from --start
DIALS = {"H2_MIX": (0.0, 1.0, 0, 40), "H2_COPY": (1.0, 0.0, 0, 60), "INTENT_HOLD": (8.0, 0.0, 40, 70), "INTENT_SEEK_W": (1.0, 0.0, 70, 100)}
DONE = (("A", 40, "his target choice the head's"), ("B", 70, "the target lock out"), ("C", 100, "the way pay out"))
HOLD_AT = 0.40


def value(spec, c, scale):
    s_, e_, c0, c1 = spec
    c0, c1 = c0 * scale, c1 * scale
    f = 0.0 if c <= c0 else 1.0 if c >= c1 else (c - c0) / (c1 - c0)
    return round(s_ + f * (e_ - s_), 6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--start", type=int, default=10)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--raw-lim", type=float, default=60.0)
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    ap.add_argument("--prev-label", default="the start (b1.3a's end)")
    ap.add_argument("--ref-label", default="b1.1")
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
                return [json.loads(x.replace("NaN", "null")) for x in f if x.strip()]
        except FileNotFoundError:
            return []

    def flags():
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": a.prev_label, "checks_ref.jsonl": a.ref_label}
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

    def write(c):
        d = json.load(open(LIVE, encoding="utf-8"))
        for k_, sp_ in DIALS.items():
            d[k_] = value(sp_, c, a.scale)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        return {k_: d[k_] for k_ in DIALS}

    def trip(m):
        h = m.get("head2") or {}
        c = h.get("copy") or {}
        bad = []
        for k_, v_ in (("raw", c.get("raw")), ("hands", h.get("hands")), ("kl", c.get("kl")), ("pg_loss", h.get("pg_loss")), ("v_loss", h.get("v_loss"))):
            if v_ is None or (isinstance(v_, float) and not math.isfinite(v_)):
                bad.append("{} not a number".format(k_))
        if isinstance(c.get("raw"), (int, float)) and c["raw"] > a.raw_lim:
            bad.append("the head's own target logits' length {} over {}".format(c["raw"], a.raw_lim))
        if h.get("skipped"):
            bad.append("{} pieces skipped".format(h["skipped"]))
        return bad

    cur = json.load(open(LIVE, encoding="utf-8"))
    for k_, sp_ in DIALS.items():
        assert abs(float(cur.get(k_, sp_[0])) - sp_[0]) < 1e-9, "{} is {} in live.json, not {}".format(k_, cur.get(k_), sp_[0])
    write(0.0)
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_b14a on for {}: the clock from update {}, every span x {}: {}; held at a check of {:.0%} or less; tripwire: raw over {}".format(
        a.run, a.start, a.scale, DIALS, HOLD_AT, a.raw_lim))
    c, done_n, seen, held, done_kept, tripped = 0.0, 0, mtime(), False, set(), 0
    end_ = max(sp_[3] for sp_ in DIALS.values()) * a.scale
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        for m in L[tripped:]:
            for b_ in trip(m):
                log("TRIPWIRE update {}: {}".format(m.get("update"), b_))
        tripped = len(L)
        ck_ = jl(os.path.join(WD, "checks_prev.jsonl"))
        low = bool(ck_) and ck_[-1]["won"] / max(1, ck_[-1]["won"] + ck_[-1]["lost"]) <= HOLD_AT
        if low != held:
            held = low
            log(("HOLD at update {}: the last check {}-{} is {:.0%} or less; the clock stays at {:.1f}" if low else "the hold lifts at update {}: the last check {}-{} is above {:.0%}; the clock goes on from {:.1f}").format(
                n, ck_[-1]["won"], ck_[-1]["lost"], HOLD_AT, c))
        if n > done_n:
            inc_ = max(0, n - max(done_n, a.start))
            if not held and inc_ > 0 and c < end_:
                c = min(end_, c + inc_)
                v_ = write(c)
                log("CLOCK {:.1f} after update {}: {}".format(c, n, v_))
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            for nm_, cend_, what_ in DONE:
                if c >= cend_ * a.scale and nm_ not in done_kept:
                    keep("policy_{}done_b14a.pt".format(nm_))
                    done_kept.add(nm_)
                    log("fade {} done ({}): kept keep/policy_{}done_b14a.pt at the save of update {}".format(nm_, what_, nm_, n))
            if c < end_:
                keep("policy_fade{}_b14a.pt".format(n))
                log("save at update {} kept with its optimizer (clock {:.1f})".format(n, c))


if __name__ == "__main__":
    main()
