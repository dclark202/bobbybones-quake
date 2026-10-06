"""Carry a trained network over to a simulator whose inputs were reordered, retired or added, and whose action heads
grew: every input is matched by name between the old and the new docs/INPUTS.csv, so the weights of the inputs that
stayed are kept in their new places; retired inputs drop their weights; new inputs start at zero. New action heads
start uniform (zero weights). The learned map table (sim/train_duel_rnn.py, "cell") is added with small random
numbers, its encoder weights at zero, so the network plays exactly as before until training starts using it.

    python sim/reshape_policy.py --src data/sim_runs/duel_gru_v7/policy.pt --old docs/INPUTS_v7.csv \\
                                 --dst data/sim_runs/duel_gru_v8/policy.pt --env duel_env_ffa
"""
import argparse
import csv
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def names(path):
    return [(r["group"], r["input"]) for r in csv.DictReader(open(path, encoding="utf-8"))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--old", required=True, help="docs/INPUTS.csv as it was for the source network")
    ap.add_argument("--new", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--cell-dim", type=int, default=16)
    a = ap.parse_args()
    import importlib
    E = importlib.import_module(a.env)
    old, new = names(a.old), names(a.new)
    assert len(set(old)) == len(old) and len(set(new)) == len(new), "input names must be unique"
    assert len(new) == E.OBS_DIM, (len(new), E.OBS_DIM)
    ck = torch.load(a.src, weights_only=False, map_location="cpu")
    sd = ck["model"]
    W = sd["enc.0.weight"]
    assert W.shape[1] == len(old), "the source network has {} inputs, the old list {}".format(W.shape[1], len(old))
    where = {k: i for i, k in enumerate(old)}
    m = [where.get(k, -1) for k in new]
    body = len(new) - 2                                       # the last two inputs are cell numbers (E.CELL_COLS)
    assert tuple(E.CELL_COLS) == (len(new) - 2, len(new) - 1)
    Wn = torch.zeros(W.shape[0], body + 2 * a.cell_dim, dtype=W.dtype)
    for j, i in enumerate(m[:body]):
        if i >= 0:
            Wn[:, j] = W[:, i]
    sd["enc.0.weight"] = Wn
    sd["cell.weight"] = torch.randn(E.MAX_CELLS, a.cell_dim) * 0.1
    old_dims, new_dims = tuple(int(x) for x in ck["action_dims"]), tuple(E.ACTION_DIMS)
    assert new_dims[:len(old_dims)] == old_dims, (old_dims, new_dims)
    extra = sum(new_dims) - sum(old_dims)
    if extra:
        sd["pi.weight"] = torch.cat([sd["pi.weight"], torch.zeros(extra, sd["pi.weight"].shape[1], dtype=sd["pi.weight"].dtype)], 0)
        sd["pi.bias"] = torch.cat([sd["pi.bias"], torch.zeros(extra, dtype=sd["pi.bias"].dtype)])
    mean, var = np.zeros(len(new)), np.ones(len(new))
    for j, i in enumerate(m):
        if i >= 0:
            mean[j], var[j] = ck["obs_mean"][i], ck["obs_var"][i]
    ck["obs_mean"], ck["obs_var"] = mean, var
    ck["obs_dim"], ck["action_dims"], ck["cells"], ck["cell_dim"] = E.OBS_DIM, new_dims, E.MAX_CELLS, a.cell_dim
    ck["reshaped_from"] = os.path.relpath(a.src, ROOT)
    os.makedirs(os.path.dirname(os.path.abspath(a.dst)), exist_ok=True)
    torch.save(ck, a.dst)
    kept = sum(1 for i in m if i >= 0)
    print("{} -> {} inputs: {} kept, {} new (zero), {} retired; heads {} -> {}".format(
        len(old), len(new), kept, len(new) - kept, len(old) - kept, old_dims, new_dims))
    print("new:", ", ".join("{}: {}".format(*new[j]) for j, i in enumerate(m) if i < 0))


if __name__ == "__main__":
    main()
