"""The input health report (owner, 2026-11-11; CLAUDE.md "Inputs"; docs/design/INPUTS_CLEANUP.md rule F2): is every input a network is
given alive, at its right size, and read?

    python tools/run/input_health.py <policy.pt> <a sample of raw inputs: obs.npy> [--json out.json] [--quiet]

The sample: rows of raw inputs in the network's own list (the trainer's --obs-dump), or in the simulator's full list (a network of a
cleaned list then reads its own columns by name). Printed by group, and FLAG lines:
    constant    a column that never changes in the sample (a part that is off, or a rare event: listed, flagged only where the group is live)
    size        the spread after the network's normalizer outside 0.5 to 2 (1 = as intended)
    clip        more than 1% of the rows at the +-10 clip
    share       the group's part of what varies at each reader's first layer (the hands' encoder; the brain's input layer; the head's
                own columns): a group that is given and carries under 0.05% of a reader's signal is flagged
Exit 1 with a FLAG (the watcher logs it; nothing stops a run)."""
import argparse
import collections
import csv
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "sim"))


def main():
    import torch
    ap = argparse.ArgumentParser()
    ap.add_argument("pol")
    ap.add_argument("sample")
    ap.add_argument("--json", default="")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    ck = torch.load(a.pol, map_location="cpu", weights_only=False)
    sd = ck["model"]
    full = [(r["group"], r["input"]) for r in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    names = [tuple(x) for x in ck["input_names"]] if ck.get("input_names") else full[:int(ck["obs_dim"])]
    X = np.load(a.sample, mmap_mode="r")
    if X.shape[1] != len(names):
        assert X.shape[1] == len(full), "the sample has {} columns: neither the network's {} nor the simulator's {}".format(X.shape[1], len(names), len(full))
        ix = {n: i for i, n in enumerate(full)}
        X = np.asarray(X)[:, [ix[n] for n in names]]
    X = np.asarray(X, np.float64)
    n = len(names)
    I = ck.get("inputs") or {}
    nh, nb = int(I.get("n_hands", sd["enc.0.weight"].shape[1])), int(sd["belief.inp.weight"].shape[1]) if "belief.inp.weight" in sd else 0
    m, s = np.asarray(ck["obs_mean"], np.float64), np.sqrt(np.asarray(ck["obs_var"], np.float64) + 1e-8)
    Z = np.clip((X - m) / s, -10, 10)
    zs, clip, const = Z.std(0), (np.abs((X - m) / s) >= 10).mean(0), (X.max(0) - X.min(0)) == 0
    fade = set(int(c) for c in ((ck.get("rule_fade") or {}).get("cols") or ())) if float((ck.get("rule_fade") or {}).get("g", 0.0)) >= 1.0 else set()
    Zh = Z.copy()
    Zh[:, sorted(fade)] = 0.0

    def share(W, Zm, cols):
        Zc = Zm - Zm.mean(0)
        tot = (Zc[:, cols] @ W.T).var(0).sum()
        out = collections.OrderedDict()
        for j, c in enumerate(cols):
            out.setdefault(names[c][0], []).append(j)
        return {g: float(((Zc[:, [cols[j] for j in js]] @ W[:, js].T).var(0).sum()) / max(tot, 1e-30)) for g, js in out.items()}

    We = sd["enc.0.weight"].double().numpy()
    sh_h = share(We, Zh, list(range(nh)))
    sh_b = share(sd["belief.inp.weight"].double().numpy(), Z, list(range(nb))) if nb else {}
    sh_s = {}
    L = ck.get("head2")
    if L is not None and "head2.inp.weight" in sd:
        import head2 as head2_
        o0, o1 = head2_._offs(L)["obs"]
        sh_s = share(sd["head2.inp.weight"].double().numpy()[:, o0:o1], Z, [int(c) for c in L["obs_cols"]])
    groups = collections.OrderedDict()
    for j, (g, _) in enumerate(names):
        groups.setdefault(g, []).append(j)
    flags, rows = [], []
    for g, js in groups.items():
        js = np.array(js)
        lv = js[~const[js]]
        read_h = bool((js < nh).any()) and not all(int(j) in fade for j in js)
        r = dict(group=g, n=len(js), const=int(const[js].sum()), size=float(np.median(zs[lv])) if len(lv) else None,
                 small=int((zs[lv] < 0.5).sum()), large=int((zs[lv] > 2.0).sum()), clip=int((clip[js] > 0.01).sum()),
                 hands=sh_h.get(g), brain=sh_b.get(g), head=sh_s.get(g), read_by_hands=read_h)
        rows.append(r)
        if len(lv) and r["small"] + r["large"] > 0.25 * len(lv):
            flags.append("size: {} of the {} live columns of '{}' arrive outside 0.5 to 2 (median {:.2f})".format(r["small"] + r["large"], len(lv), g, r["size"]))
        if r["clip"]:
            flags.append("clip: {} column(s) of '{}' at the clip in over 1% of rows".format(r["clip"], g))
        for who, v in (("hands", r["hands"] if read_h else None), ("brain", r["brain"]), ("head", r["head"])):
            if v is not None and len(lv) and v < 0.0005:
                flags.append("share: '{}' ({} live columns) carries {:.3%} of the {}' first layer's signal".format(g, len(lv), v, who))
    if not a.quiet:
        print("{} inputs ({}); the hands read the first {}, the brain the first {}; the head {} of its own; {} rows".format(
            n, "list {}".format(I["list"]) if I else "the simulator's full list", nh, nb, len(L["obs_cols"]) if L else 0, len(X)))
        print("{:18s} {:>4s} {:>5s} {:>5s} {:>5s} {:>5s} {:>4s} {:>7s} {:>7s} {:>7s}".format("group", "n", "const", "size", "<0.5", ">2", "clip", "hands%", "brain%", "head%"))
        f = lambda v: "      -" if v is None else "{:7.2f}".format(100 * v)   # noqa: E731
        for r in rows:
            print("{:18s} {:4d} {:5d} {:>5s} {:5d} {:5d} {:4d} {} {} {}".format(r["group"], r["n"], r["const"], "-" if r["size"] is None else "{:.2f}".format(r["size"]),
                                                                              r["small"], r["large"], r["clip"], f(r["hands"] if r["read_by_hands"] else None), f(r["brain"]), f(r["head"])))
    lvn = ~const
    print("input health: {} inputs, {} constant in the sample; the live ones' size median {:.2f}, {:.1%} under 0.5, {:.1%} over 2; {} FLAG(s)".format(
        n, int(const.sum()), float(np.median(zs[lvn])), float((zs[lvn] < 0.5).mean()), float((zs[lvn] > 2.0).mean()), len(flags)))
    for x in flags:
        print("FLAG input health: " + x)
    if a.json:
        json.dump(dict(rows=rows, flags=flags, n=n, const=int(const.sum())), open(a.json, "w"), indent=0)
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main())
