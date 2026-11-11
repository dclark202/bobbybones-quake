"""The input audit (owner, 2026-11-11): how much do his actions depend on each group of inputs? 1.8a's start (b1.2d's end's weights) and a
copy with one group's columns blanked, i.e. replaced by their training average: with normalized inputs that is the columns' weights set to
zero in every part that reads them (the hands' encoder, the attention tokens' first layers, and with --who all also the brain's input layer
and the strategy head's). Both play the same 400 frames x 8 seats of inputs drawn from the network's own input statistics, the same random
draws (tools/head2_init.py same): the share of his action choices that differ. Not games: a group can matter in rare moments this does not
weigh; and inputs drawn independently are not real situations. It ranks; it does not prove.
    python docs/runs/1.8/1.8a/audit_ablate.py <start.pt> <out.json> [--who hands|all]"""
import argparse
import collections
import csv
import json
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def main():
    import torch
    import head2_init as H
    ap = argparse.ArgumentParser()
    ap.add_argument("pol")
    ap.add_argument("out")
    ap.add_argument("--who", default="hands")
    ap.add_argument("--frames", type=int, default=400)
    ap.add_argument("--seats", type=int, default=8)
    a = ap.parse_args()
    R = list(csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8")))
    groups = collections.OrderedDict()
    for i, r in enumerate(R):
        groups.setdefault(r["group"], []).append(i)
    ck = torch.load(a.pol, map_location="cpu", weights_only=False)
    L = ck.get("head2") or {}
    hc = [int(c) for c in (L.get("obs_cols") or [])]
    tmp = os.path.join(tempfile.mkdtemp(prefix="audit18_"), "abl.pt")
    res = {}
    A = argparse.Namespace(a=a.pol, b=tmp, frames=a.frames, seats=a.seats)
    total = a.frames * a.seats * len(ck["action_dims"])
    for name, cols in groups.items():
        c2 = torch.load(a.pol, map_location="cpu", weights_only=False)
        sd = c2["model"]
        cs = set(cols)
        sd["enc.0.weight"][:, cols] = 0.0
        for i_, k_ in enumerate(c2["attn"]["kinds"]):
            js = sorted({j for row in k_["idx"] for j, c in enumerate(row) if c in cs and all(r2[j] in cs for r2 in k_["idx"])})
            if js:
                sd["attn.emb.{}.weight".format(i_)][:, js] = 0.0
        if a.who == "all":
            bc = [c for c in cols if c < sd["belief.inp.weight"].shape[1]]
            if bc:
                sd["belief.inp.weight"][:, bc] = 0.0
            if hc and "head2.inp.weight" in sd:
                import head2 as head2_
                o0 = head2_._offs(L)["obs"][0]
                hj = [o0 + j for j, c in enumerate(hc) if c in cs]
                if hj:
                    sd["head2.inp.weight"][:, hj] = 0.0
        torch.save(c2, tmp)
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            dh, dact = H.same(A)
        res[name] = dict(n=len(cols), differ=dact, share=dact / total, dh=dh)
        print("{:18s} {:4d} inputs: {:6d} of {} action choices differ ({:.2%})".format(name, len(cols), dact, total, dact / total), flush=True)
    json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
