"""2.1 M1 (docs/runs/2.1/README.md "Before any training"): keep against a new draw, read from a run's <run>/stay_forks.jsonl (the trainer's
--branch-keep: a line a moment, both branches' dv, sim/branch.py log_keep).

    python tools/run/m1_report.py <run folder or stay_forks.jsonl> [--from U] [--to U] [--json out.json]

For each kind of moment (quiet, in contact, arrived) and by the target's age (s): the moments, how often the new draw was the held target
(no choice made), and among the others: how often the new draw beat keeping (dv_new > dv_keep), the mean of keep less new and its spread,
the standard error, and the moments it takes for the mean's sign to stand at two standard errors (n = (2 sd / |mean|)^2): "how many moments
tell the sign". Read beside: a stay value is learnable where the sign stands within the forks an update; a mean near 0 with a wide spread
says one moment's fork is mostly noise (2.1a's appraisals learnt nothing from 9,104). For 1.7a's update 90 (the instrument's check) its quiet
re-decisions must show as losing: in quiet, the new draw loses on average."""
import argparse
import json
import math
import os

import numpy as np

KINDS = ("quiet", "contact", "arrived")
AGES = ((0, 2), (2, 5), (5, 8), (8, 12), (12, 99))


def stats(y):
    y = np.asarray(y, np.float64)
    n = len(y)
    if n == 0:
        return dict(n=0)
    m, sd = float(y.mean()), float(y.std(ddof=1)) if n > 1 else float("nan")
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    need = (2.0 * sd / abs(m)) ** 2 if (n > 1 and m != 0) else float("inf")
    return dict(n=n, new_wins=round(float((y < 0).mean()), 4), mean=round(m, 5), sd=round(sd, 5), se=round(se, 5),
                t=round(m / se, 2) if se and se == se and se > 0 else None, moments_for_sign=(int(math.ceil(need)) if math.isfinite(need) else None))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--from", dest="u0", type=int, default=-1)
    ap.add_argument("--to", dest="u1", type=int, default=10 ** 9)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    p = a.src if a.src.endswith(".jsonl") else os.path.join(a.src, "stay_forks.jsonl")
    R = [json.loads(x) for x in open(p, encoding="utf-8") if x.strip()]
    R = [r for r in R if a.u0 <= int(r["update"]) <= a.u1]
    out = dict(source=p, moments=len(R), updates=(min(r["update"] for r in R), max(r["update"] for r in R)) if R else None, kinds={})
    print("M1, keep against a new draw: {} moments from {} (updates {})".format(len(R), p, out["updates"]))
    print("  y = dv(keep) - dv(new draw), the head's value units; 'new wins' = the share of moments where the draw did better")
    for k in KINDS:
        rk = [r for r in R if r["kind"] == k]
        if not rk:
            continue
        diff = [r for r in rk if not r["same"]]
        y = [r["dv_keep"] - r["dv_new"] for r in diff]
        s_ = stats(y)
        same = round(1.0 - len(diff) / len(rk), 4)
        wins = sorted(set(r["win"] for r in rk))
        out["kinds"][k] = dict(all=len(rk), same_draw=same, windows=wins, differ=s_, by_age={})
        print("  {:8s} {:5d} moments, the draw was the held target {:.1%}; window {} frames | draw differs: {}".format(k, len(rk), same, wins, s_))
        for lo, hi in AGES:
            ya = [r["dv_keep"] - r["dv_new"] for r in diff if r.get("age") is not None and lo <= r["age"] < hi]
            if ya:
                sa = stats(ya)
                out["kinds"][k]["by_age"]["{}-{}".format(lo, hi)] = sa
                print("      age {:>2}-{:<2} s: {}".format(lo, hi if hi < 99 else "", sa))
    ups = sorted(set(r["update"] for r in R))
    if ups:
        per = len(R) / max(1, len(ups))
        print("  moments an update: {:.1f} (over {} updates)".format(per, len(ups)))
        out["per_update"] = round(per, 2)
    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
