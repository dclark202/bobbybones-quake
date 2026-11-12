"""2.1: a network of the cleaned list 18 brought to list 21 (list 18 and the head's instruction to the hands: the columns of group
"b21 instruction", after the hands' columns and before the tail; sim/input_list.py extend, sim/duel_env_ffa21.py), with nothing of
them in effect, so that it answers as before. NOT RUN YET.

    python tools/inputs21.py convert <list18.pt> <out.pt>
        the hands' encoder: the group's columns (48) at zero weights after its 796; the attention part: one token "instr" after every older
        kind, its first layer at zero and its gate shut (left out altogether while shut: sim/attn.py DROP_SHUT; the trainer's
        --gate-open opens it); every kept column number at or past the hands' old end moved up by as many (the tail: the guessing
        lesson's marks, the yellows' timers in the head's own columns, the tokens that read them); the new columns' statistics by
        design (CLAUDE.md "Inputs": a flag 0.1 and 0.3, a number 0 and 0.32) until `stats` measures them. The brain reads its 691
        as before. The optimizer needs no file of its own: the trainer's --opt-small-items carries enc.0.weight and the tokens'
        marks over and starts the new token's first layer fresh (its end-appended columns and last kind are what that code expects).
    python tools/inputs21.py stats <list21.pt> <rows.npy> <out.pt>
        the new columns' mean and spread from real rows of list 21 with seats under an instruction (a drill's, a probe's); refused
        unless every weight on them is still zero (then he answers the same whatever the statistics)
    python tools/inputs21.py same <list18.pt> <list21.pt> --sample <obs.npy, the simulator's full rows>
        both through their own lists on real rows, the new columns filled with random numbers: 0 actions may differ
"""
import argparse
import csv
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
OLD, NEW, GROUP, TOKEN = 18, 21, "b21 instruction", "instr"
FLAG, NUM = (0.1, 0.09), (0.0, 0.1)                           # (mean, variance) by design: a 0-or-1 column, a number within about -1 .. 1
# (third pass, the finish time: columns within 0 .. 2, by design until `stats` measures them) a finish time (seconds / 5: a stack of 150
# at 40 a second is 0.75, a weapon he cannot use 2); seconds of fire (/ 10); "he has a belief" (nearly always)
DESIGN = {"seconds to finish him": (1.0, 0.5), "the cautious seconds": (1.1, 0.5), "seconds of fire he has": (0.5, 0.25),
          "finish: he has a belief of the enemy's stack": (0.9, 0.09)}


def design(name, scale):
    for k, v in DESIGN.items():
        if name.endswith(k):
            return v
    return FLAG if scale.strip() == "0 or 1" else NUM


def lists():
    import input_list as IL
    return IL.load(OLD), IL.load(NEW)


def new_cols(Ln):
    return [j for j, (g, _) in enumerate(Ln["names"]) if g == GROUP]


def convert(a):
    import torch
    import attn as A
    Lo, Ln = lists()
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    I = ck.get("inputs") or {}
    assert int(I.get("list", -1)) == OLD and [tuple(x) for x in ck["input_names"]] == [tuple(x) for x in Lo["names"]], "not a network of list {}".format(OLD)
    sd = ck["model"]
    nh, n0 = int(Lo["n_hands"]), int(Lo["n"])
    cols = new_cols(Ln)
    K = len(cols)
    assert cols == list(range(nh, nh + K)) and Ln["n"] == n0 + K and Ln["n_hands"] == nh + K and Ln["n_brain"] == Lo["n_brain"]
    assert [tuple(x) for x in Ln["names"][:nh]] == [tuple(x) for x in Lo["names"][:nh]] and [tuple(x) for x in Ln["names"][nh + K:]] == [tuple(x) for x in Lo["names"][nh:]]
    sh = lambda c: int(c) + K if int(c) >= nh else int(c)    # noqa: E731  (a kept column's number in the new list)
    # ---- the hands' encoder and the statistics
    W = sd["enc.0.weight"]
    assert tuple(W.shape)[1] == nh, (tuple(W.shape), nh)
    sd["enc.0.weight"] = torch.cat([W, torch.zeros(W.shape[0], K, dtype=W.dtype)], 1)
    rows = {(r["group"], r["input"]): r for r in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))}
    des = np.array([design(Ln["names"][j][1], rows[tuple(Ln["names"][j])]["scale"]) for j in cols], np.float64)
    for key, col in (("obs_mean", 0), ("obs_var", 1)):
        v = np.asarray(ck[key], np.float64)
        assert len(v) == n0
        ck[key] = np.concatenate([v[:nh], des[:, col], v[nh:]]).astype(np.asarray(ck[key]).dtype)
    ck["obs_dim"] = n0 + K
    # ---- the attention part: the old kinds' columns moved, the new token last, at zero, shut
    lay = dict(ck["attn"])
    assert int(lay["obs_dim"]) == n0 and lay.get("gated") and all(k["name"] != TOKEN for k in lay["kinds"])
    kinds = [dict(k, idx=[[(c if int(c) < 0 else sh(c)) for c in row] for row in k["idx"]]) for k in lay["kinds"]]
    kinds.append(dict(name=TOKEN, idx=[cols]))
    D = int(lay["D"])
    mark, gate = sd["attn.mark"], sd["attn.gate"]
    assert tuple(mark.shape) == (int(lay["tokens"]), D) and len(gate) == int(lay["tokens"])
    g = torch.Generator().manual_seed(2100)
    sd["attn.emb.{}.weight".format(len(kinds) - 1)] = torch.zeros((D, K), dtype=mark.dtype)
    sd["attn.mark"] = torch.cat([mark[:-1], (torch.randn((1, D), generator=g) * 0.1).to(mark.dtype), mark[-1:]], 0)   # (the summary token's stays the last)
    sd["attn.gate"] = torch.cat([gate[:-1], torch.full((1,), A.GATE_SHUT, dtype=gate.dtype), gate[-1:]], 0)
    nt = int(lay["tokens"]) + 1
    ck["attn"] = dict(lay, obs_dim=n0 + K, kinds=kinds, tokens=nt, read=[nt - 1] + [int(x) for x in lay["read"][1:]])
    assert int(lay["read"][0]) == int(lay["tokens"]) - 1, "the summary token is not the last row"
    # ---- every other kept column number
    moved = []
    if ck.get("rule_fade") is not None:
        rf = dict(ck["rule_fade"])
        rf["cols"] = [sh(c) for c in rf["cols"]]
        if rf.get("more") and rf["more"].get("cols"):
            rf["more"] = dict(rf["more"], cols=[sh(c) for c in rf["more"]["cols"]])
        ck["rule_fade"] = rf
        moved.append("the rule fade's {}".format(len(rf["cols"])))
    if ck.get("head2") is not None:
        h2 = dict(ck["head2"])
        for key in ("obs_cols", "wobs_cols"):
            if h2.get(key) is not None:
                h2[key] = [sh(c) for c in h2[key]]
                moved.append("the head's {} ({} at or past {})".format(key, sum(int(c) >= nh + K for c in h2[key]), nh))
        ck["head2"] = h2
    if ck.get("btoken") is not None and "seen_col" in ck["btoken"]:
        ck["btoken"] = dict(ck["btoken"], seen_col=sh(ck["btoken"]["seen_col"]))
    for key in ("belief", "track", "track_z", "ahead", "control", "fightodds", "spaceread", "passodds"):   # (a column list this converter does not know)
        d = ck.get(key)
        if isinstance(d, dict):
            for k2, v2 in d.items():
                nums_ = isinstance(v2, (int, np.integer)) or (isinstance(v2, (list, tuple, np.ndarray)) and len(v2) > 0
                                                               and all(isinstance(x_, (int, np.integer)) for x_ in np.asarray(v2, object).ravel()))
                if (k2.endswith("cols") or k2.endswith("_col")) and nums_:      # (a list of the truth labels' NAMES, as track["cols"], is no column list)
                    raise SystemExit("{}['{}'] holds column numbers this converter does not move: add it".format(key, k2))
    ck["inputs"] = dict(list=NEW, n=n0 + K, n_brain=int(Ln["n_brain"]), n_hands=nh + K, full=int(Ln["full"]), design_stats=[nh, nh + K])
    ck["input_names"] = [list(x) for x in Ln["names"]]
    ck["env_module"] = "duel_env_ffa{}".format(NEW)
    torch.save(ck, a.out)
    print("wrote {}: list {} ({} inputs; the brain the first {}, the hands the first {}, the tail {}); {} new columns at zero weights with "
          "design statistics; the token '{}' last, its first layer zero, shut; moved: {}".format(
              a.out, NEW, n0 + K, Ln["n_brain"], nh + K, n0 - nh, K, TOKEN, "; ".join(moved) or "nothing"))


def stats(a):
    import torch
    _, Ln = lists()
    ck = torch.load(a.inp, weights_only=False, map_location="cpu")
    assert int((ck.get("inputs") or {}).get("list", -1)) == NEW, "not a network of list {}".format(NEW)
    cols = new_cols(Ln)
    sd = ck["model"]
    ki = [i for i, k in enumerate(ck["attn"]["kinds"]) if k["name"] == TOKEN][0]
    assert not sd["enc.0.weight"][:, cols].any() and not sd["attn.emb.{}.weight".format(ki)].any(), "a weight on the new columns is no longer zero: the statistics stay"
    X = np.load(a.rows, mmap_mode="r")
    assert X.shape[1] == Ln["n"], (X.shape, Ln["n"])
    x = np.asarray(X[:, cols], np.float64)
    on = x[:, 1:len_verbs()].sum(1) > 0                      # rows of a seat under an instruction (a verb other than "none")
    assert on.sum() >= 2000, "{} rows under an instruction: too few".format(int(on.sum()))
    m, v = x[on].mean(0), x[on].var(0)
    v = np.where(v > 1e-6, v, np.asarray(ck["obs_var"], np.float64)[cols])        # (a column constant in the sample keeps its design spread)
    mean, var = np.asarray(ck["obs_mean"], np.float64).copy(), np.asarray(ck["obs_var"], np.float64).copy()
    mean[cols], var[cols] = m, v
    ck["obs_mean"], ck["obs_var"] = mean.astype(np.asarray(ck["obs_mean"]).dtype), var.astype(np.asarray(ck["obs_var"]).dtype)
    ck["inputs"] = dict(ck["inputs"], design_stats=None, measured=dict(rows=int(on.sum()), file=os.path.basename(a.rows)))
    torch.save(ck, a.out)
    print("wrote {}: the {} new columns' statistics from {} rows under an instruction (constant in the sample, kept by design: {})".format(
        a.out, len(cols), int(on.sum()), int((x[on].var(0) <= 1e-6).sum())))


def len_verbs():
    return 9                                                  # (duel_env INS_VERBS: "none" and the eight)


def same(a):
    import test_suite as T
    Lo, Ln = lists()
    src = np.asarray(Lo["src"], np.int64)
    cols = new_cols(Ln)
    nh = int(Lo["n_hands"])
    pa, pb = T.Policy(a.a, seed=7), T.Policy(a.b, seed=7)
    assert len(pa.mean) == Lo["n"] and len(pb.mean) == Ln["n"], (len(pa.mean), len(pb.mean))
    for p in (pa, pb):
        if getattr(p, "h2", None) is not None and (float(p.h2W["gate"]) > 0 or float(p.h2W.get("add", 0.0)) > 0):
            p.h2_live = True
    X = np.load(a.sample, mmap_mode="r")
    assert X.shape[1] >= Lo["full"], X.shape
    rng = np.random.default_rng(3)
    B, F = a.seats, a.rows // a.seats
    pick = rng.permutation(len(X))[:B * F].reshape(F, B)
    ha, hb = pa.zeros(B), pb.zeros(B)
    pose, zmap = np.zeros((B, 4), np.float32), np.zeros(B, np.int64)
    dact, n, dh = 0, 0, 0.0
    for t in range(F):
        raw = np.asarray(X[np.sort(pick[t])], np.float32)[:, src]
        new = np.concatenate([raw[:, :nh], rng.uniform(-1, 1, (B, len(cols))).astype(np.float32), raw[:, nh:]], 1)
        pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
        pose[:, 3] = rng.uniform(-180, 180, B)
        kw = {}
        if pa.needs_xl:
            kw["xl"] = rng.normal(0, 1, (B, pa.legsP[0].shape[1])).astype(np.float32)
        oa, ha = pa.act(raw, ha, pose=pose, zmap=zmap, **kw)
        ob, hb = pb.act(new, hb, pose=pose, zmap=zmap, **kw)
        dact += int((oa != ob).sum())
        n += oa.size
        dh = max(dh, float(np.abs(np.asarray(ha) - np.asarray(hb)).max()) if np.shape(ha) == np.shape(hb) else float("nan"))
        if t % 97 == 96:
            r = rng.random(B) < 0.3
            pa.clear(ha, r)
            pb.clear(hb, r)
    print("same: {} real rows x {} seats, the new columns random: largest |memory a - memory b| = {:.3g}; actions that differ: {} of {}".format(F, B, dh, dact, n))
    print("ALL PASSED" if dact == 0 else "FAILED")
    return 0 if dact == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("convert")
    p.add_argument("inp")
    p.add_argument("out")
    p = sp.add_parser("stats")
    p.add_argument("inp")
    p.add_argument("rows")
    p.add_argument("out")
    p = sp.add_parser("same")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--sample", required=True)
    p.add_argument("--rows", type=int, default=3200)
    p.add_argument("--seats", type=int, default=8)
    a = ap.parse_args()
    sys.exit(int({"convert": convert, "stats": stats, "same": same}[a.cmd](a) or 0))


if __name__ == "__main__":
    main()
