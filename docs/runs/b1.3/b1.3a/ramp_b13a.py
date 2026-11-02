"""b1.3a's ramp and tripwire (owner, 2026-11-01; CARD.md). H2_GATE_CAP 0.2, 0.4, 0.6, 0.8, 1 right after each save from the first (update 10), at least --min-s apart; the save before each step kept with its optimizer; the head-open save at the save after the last.
A check of 40% or less against the start holds the next step; under 50% is flagged. The tripwire, every poll: the last update's head2.bias over BIAS_LIM, head2.hands over HANDS_MULT x its first reading, head2.skipped above 0, or a NaN: "TRIPWIRE" in watch.log, once for each kind until it clears. It stops nothing (rule 6): the chat is told, and the owner decides.
    python docs/runs/b1.3/b1.3a/ramp_b13a.py <run> [--min-s S] [--poll S] [--settle S] [--dir D] [--bias-lim X] [--hands-mult X]"""
import argparse
import json
import math
import os
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
VALS = (0.2, 0.4, 0.6, 0.8, 1.0)
HOLD_AT = 0.40


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--min-s", type=float, default=25 * 60)
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    ap.add_argument("--bias-lim", type=float, default=60.0, help="b1.2a passed 55 at update 40; set it from the trial")
    ap.add_argument("--hands-mult", type=float, default=1.5)
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
        names = {"checks_prev.jsonl": "the start", "checks_ref.jsonl": "v0.6.0's end"}
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

    cur = json.load(open(LIVE, encoding="utf-8"))
    assert abs(float(cur.get("H2_GATE_CAP", -1))) < 1e-9, "H2_GATE_CAP is {} in live.json, not 0".format(cur.get("H2_GATE_CAP"))
    threading.Thread(target=watch, daemon=True).start()
    log("ramp_b13a on for {}: gate {} right after a save, at least {:g} min apart; held at a check of {:.0%} or less; tripwire at bias {}, hands x {}".format(a.run, VALS, a.min_s / 60, HOLD_AT, a.bias_lim, a.hands_mult))
    seen, t_last, i = mtime(), 0.0, 0
    while i <= len(VALS):
        time.sleep(a.poll)
        m_ = mtime()
        if m_ <= seen or time.time() - m_ < a.settle:
            continue
        seen = m_
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        if i == len(VALS):
            shutil.copy2(POL, os.path.join(KEEP, "policy_head_open_b13a.pt"))
            shutil.copy2(OPT, os.path.join(KEEP, "opt_head_open_b13a.pt"))
            log("the head open: the save of update {} kept as keep/policy_head_open_b13a.pt, with its optimizer".format(n))
            i += 1
            break
        if time.time() - t_last < a.min_s:
            continue
        c_ = jl(os.path.join(WD, "checks_prev.jsonl"))
        if c_ and c_[-1]["won"] / max(1, c_[-1]["won"] + c_[-1]["lost"]) <= HOLD_AT:
            log("HOLD at the save of update {}: the last check {}-{}".format(n, c_[-1]["won"], c_[-1]["lost"]))
            continue
        ke_ = "policy_gate{}_b13a.pt".format(i)
        shutil.copy2(POL, os.path.join(KEEP, ke_))
        shutil.copy2(OPT, os.path.join(KEEP, ke_.replace("policy_", "opt_", 1)))
        d = json.load(open(LIVE, encoding="utf-8"))
        d["H2_GATE_CAP"] = VALS[i]
        with open(LIVE + ".tmp", "w", encoding="utf-8") as f:
            f.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        log("RAMP H2_GATE_CAP {} (right after the save of update {}, kept as keep/{})".format(VALS[i], n, ke_))
        i, t_last = i + 1, time.time()
    while True:
        time.sleep(a.poll)


if __name__ == "__main__":
    main()
