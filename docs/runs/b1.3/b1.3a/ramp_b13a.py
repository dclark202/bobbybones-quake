"""b1.3a's ramp and tripwire (owner, 2026-11-01; the line, 2026-11-02: "ramp over 80 updates starting at u10"; CARD.md). H2_GATE_CAP from 0 to 1 in a straight line over updates 10 to 90 (--start, --over),
written after each new update (live.json, read between rollouts), as b1.2d's fade. Each save during the ramp is kept with its optimizer (keep/policy_gate<update>_b13a.pt), and the first save with the
gate at 1 as keep/policy_head_open_b13a.pt. A check of 40% or less against the start holds the gate where it is until a later check is above it; under 50% is flagged.
The tripwire, every poll: the last update's head2.bias over BIAS_LIM, head2.hands over HANDS_MULT x its first reading, head2.skipped above 0, or a NaN: "TRIPWIRE" in watch.log, once for each kind
until it clears. It stops nothing (rule 6): the chat is told, and the owner decides.
    python docs/runs/b1.3/b1.3a/ramp_b13a.py <run> [--start N] [--over N] [--poll S] [--settle S] [--dir D] [--bias-lim X] [--hands-mult X] [--ref-label L]"""
import argparse
import json
import math
import os
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
HOLD_AT = 0.40


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--start", type=int, default=10)
    ap.add_argument("--over", type=int, default=80)
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    ap.add_argument("--bias-lim", type=float, default=60.0, help="b1.2a passed 55 at update 40; set it from the trial")
    ap.add_argument("--hands-mult", type=float, default=1.5)
    ap.add_argument("--ref-label", default="b1.1", help="the reference check's opponent, for the flags")
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

    def watch():
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": "the start", "checks_ref.jsonl": a.ref_label}
        h0, on = None, set()
        while True:
            for f_, n_ in seen.items():
                R = jl(os.path.join(WD, f_))
                for d in R[n_:]:
                    wr_ = d["won"] / max(1, d["won"] + d["lost"])
                    if wr_ < 0.5:
                        log("FLAG check update {} against {}: {}-{} = {:.1%}".format(d["update"], names[f_], d["won"], d["lost"], wr_))
                seen[f_] = len(R)
            M = jl(MET)
            h = (M[-1].get("head2") or {}) if M else {}
            if h:
                b_, hd_, sk_ = h.get("bias"), h.get("hands"), h.get("skipped", 0)
                if h0 is None and isinstance(hd_, (int, float)) and hd_ > 0:
                    h0 = hd_
                now = {}
                if b_ is None or hd_ is None or (isinstance(b_, float) and math.isnan(b_)):
                    now["nan"] = "a NaN in the head's numbers"
                else:
                    if b_ > a.bias_lim:
                        now["bias"] = "the bias's length {} over {}".format(b_, a.bias_lim)
                    if h0 and hd_ > a.hands_mult * h0:
                        now["hands"] = "the hands' target length {} over {} x its first, {}".format(hd_, a.hands_mult, h0)
                if sk_:
                    now["skipped"] = "{} pieces skipped: a loss not finite".format(sk_)
                for k_, s_ in now.items():
                    if k_ not in on:
                        log("TRIPWIRE update {}: {}".format(M[-1].get("update"), s_))
                on = set(now)
            time.sleep(a.poll)

    def mtime():
        try:
            return os.path.getmtime(POL)
        except FileNotFoundError:
            return 0.0

    def keep(name):
        shutil.copy2(POL, os.path.join(KEEP, name))
        shutil.copy2(OPT, os.path.join(KEEP, name.replace("policy_", "opt_", 1)))

    def write(g):
        d = json.load(open(LIVE, encoding="utf-8"))
        d["H2_GATE_CAP"] = round(g, 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)

    cur = json.load(open(LIVE, encoding="utf-8"))
    assert abs(float(cur.get("H2_GATE_CAP", -1))) < 1e-9, "H2_GATE_CAP is {} in live.json, not 0".format(cur.get("H2_GATE_CAP"))
    threading.Thread(target=watch, daemon=True).start()
    log("ramp_b13a on for {}: H2_GATE_CAP 0 to 1 over {} updates from update {}; held at a check of {:.0%} or less; tripwire at bias {}, hands x {}".format(
        a.run, a.over, a.start, HOLD_AT, a.bias_lim, a.hands_mult))
    g, k_n, done_n, seen, held, open_kept = 0.0, 0, 0, mtime(), False, False    # (k_n: updates of the ramp done; g from it, no sum of fractions)
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        c_ = jl(os.path.join(WD, "checks_prev.jsonl"))
        low = bool(c_) and c_[-1]["won"] / max(1, c_[-1]["won"] + c_[-1]["lost"]) <= HOLD_AT
        if low != held:
            held = low
            log(("HOLD at update {}: the last check {}-{} is {:.0%} or less; the gate stays at {:.3f}" if low else "the hold lifts at update {}: the last check {}-{} is above {:.0%}; the gate goes on from {:.3f}").format(
                n, c_[-1]["won"], c_[-1]["lost"], HOLD_AT, g))
        if n > done_n and g < 1.0:
            inc_ = max(0, n - max(done_n, a.start))          # (--start) the ramp begins after this update
            if not held and inc_ > 0:
                k_n = min(a.over, k_n + inc_)
                g = k_n / float(a.over)
                write(g)
                log("GATE {:.4f} after update {}".format(g, n))
            done_n = n
        elif n > done_n:
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            if g < 1.0:
                keep("policy_gate{}_b13a.pt".format(n))
                log("save at update {} kept with its optimizer (gate {:.3f})".format(n, g))
            elif not open_kept:
                keep("policy_head_open_b13a.pt")
                open_kept = True
                log("the head open: kept keep/policy_head_open_b13a.pt at the save of update {}, with its optimizer".format(n))


if __name__ == "__main__":
    main()
