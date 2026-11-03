"""b1.4a's fade (owner, 2026-11-03: "MIX fades to 0.5, HEAD learns the whole time. For B1.4a, fade the HEAD in over 80 updates, 10--90";
"Do not stop the fade, just let it go over the 80 updates"; CARD.md): one live dial in a straight line, written after each new update
(live.json, read between rollouts):
  H2_MIX 0 -> 0.5 over updates 10 to 90: his target choice from the hands' (the rules' imprint, frozen) to half the head's own
(--scale stretches or shrinks the span; the card's numbers are at 1.) No hold: the fade runs whatever the checks read. Each save during the
fade is kept with its optimizer (keep/policy_fade<update>_b14a.pt); the first save at its end as keep/policy_Adone_b14a.pt.
A check under 50% against the start is flagged. The tripwire (flagged, nothing stopped): the head's own target logits' centred length over
--raw-lim, a non-finite number, a skipped piece. Nothing here stops the run.
    python docs/runs/b1.4/b1.4a/ramp_b14a.py <run> [--start 10] [--scale 1] [--mix-to 0.5] [--raw-lim 60] [--poll S] [--settle S] [--dir D]"""
import argparse
import json
import math
import os
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
SPAN = 80                                                     # updates, at --scale 1, counted from --start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--start", type=int, default=10)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--mix-to", type=float, default=0.5)
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
    end_ = SPAN * a.scale

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
        d["H2_MIX"] = round(a.mix_to * min(1.0, max(0.0, c / end_)), 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        return d["H2_MIX"]

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
    assert abs(float(cur.get("H2_MIX", 0.0))) < 1e-9, "H2_MIX is {} in live.json, not 0".format(cur.get("H2_MIX"))
    write(0.0)
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_b14a on for {}: H2_MIX 0 -> {} over updates {} to {} (no hold); tripwire: raw over {}".format(
        a.run, a.mix_to, a.start, a.start + end_, a.raw_lim))
    c, done_n, seen, done_kept, tripped = 0.0, 0, mtime(), False, 0
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        for m in L[tripped:]:
            for b_ in trip(m):
                log("TRIPWIRE update {}: {}".format(m.get("update"), b_))
        tripped = len(L)
        if n > done_n:
            inc_ = max(0, n - max(done_n, a.start))
            if inc_ > 0 and c < end_:
                c = min(end_, c + inc_)
                log("CLOCK {:.1f} after update {}: H2_MIX {}".format(c, n, write(c)))
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            if c >= end_ and not done_kept:
                keep("policy_Adone_b14a.pt")
                done_kept = True
                log("the fade done (H2_MIX {}): kept keep/policy_Adone_b14a.pt at the save of update {}".format(a.mix_to, n))
            if c < end_:
                keep("policy_fade{}_b14a.pt".format(n))
                log("save at update {} kept with its optimizer (clock {:.1f})".format(n, c))


if __name__ == "__main__":
    main()
