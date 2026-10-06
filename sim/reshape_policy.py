"""Carry a trained network over to a simulator whose inputs were reordered, retired or added, and whose action heads
grew: every input is matched by name between the old and the new docs/INPUTS.csv, so the weights of the inputs that
stayed are kept in their new places; retired inputs drop their weights; new inputs start at zero, unless a second,
older network (--also, with its own list --also-old) still has them by name: then its weights are used. New action
heads start uniform (zero weights). The learned map table (sim/train_duel_rnn.py, "cell") is carried over when the
source has one, else added with small random numbers and zero encoder weights, so the network plays exactly as before
until training starts using it.

    python sim/reshape_policy.py --src data/sim_runs/duel_gru_v7/policy.pt --old docs/INPUTS_v7.csv \\
                                 --dst data/sim_runs/duel_gru_v8/policy.pt --env duel_env_ffa
    python sim/reshape_policy.py --src .../v8/policy.pt --old docs/INPUTS_v8a.csv --also .../v7/policy.pt --also-old docs/INPUTS_v7.csv ...
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


def load(path, lst, cell_dim):
    """-> state dict, checkpoint, encoder body columns (inputs that are values), names of those columns"""
    ck = torch.load(path, weights_only=False, map_location="cpu")
    sd = ck["model"]
    W = sd["enc.0.weight"]
    has_cell = "cell.weight" in sd
    body = len(lst) - 2 if has_cell else len(lst)
    assert W.shape[1] == body + (2 * cell_dim if has_cell else 0), (path, W.shape[1], len(lst))
    return sd, ck, W[:, :body], lst[:body]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--old", required=True, help="docs/INPUTS.csv as it was for the source network")
    ap.add_argument("--also", default="", help="an older network whose weights fill inputs the source lacks")
    ap.add_argument("--also-old", default="", help="docs/INPUTS.csv as it was for --also")
    ap.add_argument("--new", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--cell-dim", type=int, default=16)
    a = ap.parse_args()
    import importlib
    E = importlib.import_module(a.env)
    new = names(a.new)
    old = names(a.old)
    assert len(set(old)) == len(old) and len(set(new)) == len(new), "input names must be unique"
    assert len(new) == E.OBS_DIM, (len(new), E.OBS_DIM)
    has_new_cell = getattr(E, "CELL_COLS", None) is not None
    if has_new_cell:
        assert tuple(E.CELL_COLS) == (len(new) - 2, len(new) - 1)
    sd, ck, W, old_body = load(a.src, old, a.cell_dim)
    body = len(new) - 2 if has_new_cell else len(new)
    srcs = [(W, old_body, ck["obs_mean"], ck["obs_var"], old, "source")]
    if a.also:
        lst2 = names(a.also_old)
        sd2, ck2, W2, body2 = load(a.also, lst2, a.cell_dim)
        srcs.append((W2, body2, ck2["obs_mean"], ck2["obs_var"], lst2, "older"))
    Wn = torch.zeros(W.shape[0], body + (2 * a.cell_dim if has_new_cell else 0), dtype=W.dtype)
    mean, var = np.zeros(len(new)), np.ones(len(new))
    got = {}
    for j, k in enumerate(new):
        for Ws, lst_body, m_, v_, lst_all, tag in srcs:
            if j < body and k in lst_body:
                Wn[:, j] = Ws[:, lst_body.index(k)]
            if k in lst_all:
                i = lst_all.index(k)
                mean[j], var[j] = m_[i], v_[i]
                got[j] = tag
                break
    if not has_new_cell:                                  # the learned table is gone (v9): its weights are dropped
        sd.pop("cell.weight", None)
    elif "cell.weight" in sd:
        Wn[:, body:] = sd["enc.0.weight"][:, len(old) - 2:]
    else:
        sd["cell.weight"] = torch.randn(E.MAX_CELLS, a.cell_dim) * 0.1
    sd["enc.0.weight"] = Wn
    old_dims, new_dims = tuple(int(x) for x in ck["action_dims"]), tuple(E.ACTION_DIMS)
    assert new_dims[:len(old_dims)] == old_dims, (old_dims, new_dims)
    extra = sum(new_dims) - sum(old_dims)
    if extra:
        sd["pi.weight"] = torch.cat([sd["pi.weight"], torch.zeros(extra, sd["pi.weight"].shape[1], dtype=sd["pi.weight"].dtype)], 0)
        sd["pi.bias"] = torch.cat([sd["pi.bias"], torch.zeros(extra, dtype=sd["pi.bias"].dtype)])
    ck["obs_mean"], ck["obs_var"] = mean, var
    ck["obs_dim"], ck["action_dims"] = E.OBS_DIM, new_dims
    ck["cells"], ck["cell_dim"] = (E.MAX_CELLS, a.cell_dim) if has_new_cell else (0, 0)
    ck["reshaped_from"] = os.path.relpath(a.src, ROOT)
    os.makedirs(os.path.dirname(os.path.abspath(a.dst)), exist_ok=True)
    torch.save(ck, a.dst)
    n_src = sum(1 for t in got.values() if t == "source")
    n_old = sum(1 for t in got.values() if t == "older")
    print("{} -> {} inputs: {} kept from the source, {} from the older network, {} new (zero), {} retired; heads {} -> {}".format(
        len(old), len(new), n_src, n_old, len(new) - len(got), len(old) - n_src, old_dims, new_dims))
    print("new:", ", ".join("{}: {}".format(*new[j]) for j in range(len(new)) if j not in got))


if __name__ == "__main__":
    main()
