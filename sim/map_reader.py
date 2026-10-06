"""The map reader (B-104): a small convolutional network that reads a map's top-down picture (tools/map_raster.py)
and says, for every 64-unit cell, 16 numbers about that place, learned by predicting facts computed from the map
(travel times to the big items, openness, height, distance to hazards and spawns) on many maps at once. The 16
numbers are the layer before the predictions; they are written out per map as the cell table the simulator and the
game-server plugin look up for a player's own cell and the enemy's (duel_env.N_INTENT, data/maps/cells_<map>.npy).

    python sim/map_reader.py train [--hold-out aerowalk,lostworld] [--epochs 400]       (Anaconda Python, GPU)
    python sim/map_reader.py export                                                    -> data/maps/cells_<map>.npy
    python sim/map_reader.py eval --hold-out ...                                       label error, seen vs unseen maps

One picture is one map: 48 input planes (24 channels x 2 height layers), ~60 x 70 cells. Training data are a few
dozen maps, so the network is small (about 60k weights), the facts are only scored on walkable cells, and every
map is seen flipped and turned (the facts do not depend on which way is north).
"""
import argparse
import glob
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS_DIR = os.path.join(ROOT, "data", "maps")
MODEL = os.path.join(ROOT, "data", "maps", "map_reader.pt")
EMB = 16


def load_rasters(names=None):
    out = {}
    for f in sorted(glob.glob(os.path.join(MAPS_DIR, "raster_*.npz"))):
        name = os.path.basename(f)[7:-4]
        if names is not None and name not in names:
            continue
        z = np.load(f)
        out[name] = dict(x=z["x"], y=z["y"], mask=z["mask"], lo=z["lo"], cell_n=z["cell_n"], zmid=float(z["zmid"]))
    return out


def make_model(n_in, n_lab):
    import torch.nn as nn
    return nn.Sequential(nn.Conv2d(n_in, 32, 3, padding=1), nn.ReLU(), nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(),
                         nn.Conv2d(32, 32, 3, padding=2, dilation=2), nn.ReLU(), nn.Conv2d(32, 2 * EMB, 3, padding=1), nn.Tanh(),
                         nn.Conv2d(2 * EMB, n_lab, 1))                      # 16 numbers per cell and height layer


def to_tensors(r, dev):
    import torch
    x = torch.from_numpy(r["x"].reshape(-1, *r["x"].shape[2:])).float().to(dev)          # (2*C, ny, nx)
    y = torch.from_numpy(r["y"].reshape(-1, *r["y"].shape[2:])).float().to(dev)          # (2*L, ny, nx) -> per layer below
    m = torch.from_numpy(r["mask"]).float().to(dev)                                      # (2, ny, nx)
    return x, y, m


def forward_layers(model, x):
    """the picture holds both height layers; the reader is run once with both as channels and predicts per layer"""
    return model(x[None])[0]                                                             # (n_lab, ny, nx) shared head


def loss_of(model, x, y, m, n_lab):
    import torch
    out = forward_layers(model, x)                                                       # (n_lab, ny, nx)
    L = n_lab // 2
    tot, cnt = torch.zeros((), device=x.device), 0.0
    for layer in range(2):
        pred = out[layer * L:(layer + 1) * L]
        tgt = y[layer * L:(layer + 1) * L]
        known = (tgt >= 0).float() * m[layer][None]
        tot = tot + (((pred - tgt) ** 2) * known).sum()
        cnt += float(known.sum())
    return tot / max(cnt, 1.0)


def augment(x, y, m, rng):
    import torch
    k = int(rng.integers(4))
    x, y, m = torch.rot90(x, k, (1, 2)), torch.rot90(y, k, (1, 2)), torch.rot90(m, k, (1, 2))
    if rng.random() < 0.5:
        x, y, m = torch.flip(x, (2,)), torch.flip(y, (2,)), torch.flip(m, (2,))
    return x, y, m


def embed(model, x):
    """the 16 numbers per cell: the layer before the predictions"""
    import torch
    with torch.no_grad():
        h = x[None]
        for layer in list(model)[:-1]:
            h = layer(h)
        return h[0]                                                                      # (2 * EMB, ny, nx): 16 per layer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train", "export", "eval"])
    ap.add_argument("--hold-out", default="", help="maps kept out of training (comma separated)")
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--lr", type=float, default=2e-3)
    a = ap.parse_args()
    import torch
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    rasters = load_rasters()
    assert rasters, "no rasters: run tools/map_raster.py --all first"
    hold = [h for h in a.hold_out.split(",") if h]
    any_r = next(iter(rasters.values()))
    n_in = any_r["x"].shape[0] * any_r["x"].shape[1]
    n_lab = any_r["y"].shape[0] * any_r["y"].shape[1]
    if a.cmd == "train":
        model = make_model(n_in, n_lab).to(dev)
        opt = torch.optim.Adam(model.parameters(), lr=a.lr)
        rng = np.random.default_rng(1)
        train = [to_tensors(r, dev) for n, r in rasters.items() if n not in hold]
        test = [to_tensors(r, dev) for n, r in rasters.items() if n in hold]
        print("training on {} maps, holding out {}: {} weights".format(len(train), hold or "none", sum(p.numel() for p in model.parameters())))
        for ep in range(a.epochs):
            model.train()
            tot = 0.0
            for i in rng.permutation(len(train)):
                x, y, m = augment(*train[i], rng)
                loss = loss_of(model, x, y, m, n_lab)
                opt.zero_grad()
                loss.backward()
                opt.step()
                tot += float(loss)
            if ep % 50 == 0 or ep == a.epochs - 1:
                model.eval()
                with torch.no_grad():
                    te = np.mean([float(loss_of(model, *t, n_lab)) for t in test]) if test else float("nan")
                print("epoch {:4d}  train {:.4f}  held-out {:.4f}".format(ep, tot / len(train), te), flush=True)
        torch.save(dict(model=model.state_dict(), n_in=n_in, n_lab=n_lab, hold_out=hold), MODEL)
        print("->", MODEL)
    else:
        ck = torch.load(MODEL, weights_only=False, map_location=dev)
        model = make_model(ck["n_in"], ck["n_lab"]).to(dev)
        model.load_state_dict(ck["model"])
        model.eval()
        if a.cmd == "eval":
            L = ck["n_lab"] // 2
            names = sorted(rasters)
            print("{:20s} {:>8s}  per fact (rms): {}".format("map", "rms", " ".join(str(l) for l in np.load(glob.glob(os.path.join(MAPS_DIR, "raster_*.npz"))[0])["labels"])))
            for n in names:
                x, y, m = to_tensors(rasters[n], dev)
                with torch.no_grad():
                    out = forward_layers(model, x)
                errs = []
                for lab in range(L):
                    e, c = 0.0, 0.0
                    for layer in range(2):
                        p, t = out[layer * L + lab], y[layer * L + lab]
                        known = (t >= 0).float() * m[layer]
                        e += float((((p - t) ** 2) * known).sum())
                        c += float(known.sum())
                    errs.append((e / max(c, 1.0)) ** 0.5)
                print("{:20s} {:8.3f}  {}  {}".format(n, float(np.mean(errs)), " ".join("{:.2f}".format(v) for v in errs), "(held out)" if n in hold else ""))
            return
        # export: the per-map cell tables on the simulator's cell numbering (layer * nx * ny + cy * nx + cx + 1)
        for n, r in rasters.items():
            x, _, _ = to_tensors(r, dev)
            e = embed(model, x).cpu().numpy()                                             # (EMB, ny, nx) — same for both layers' channels
            nx, ny = int(r["cell_n"][0]), int(r["cell_n"][1])
            table = np.zeros((16384, EMB), np.float32)                                   # duel_env.MAX_CELLS
            for layer in range(2):
                for cy in range(ny):
                    for cx in range(nx):
                        idx = 1 + layer * nx * ny + cy * nx + cx
                        if idx < 16384:
                            table[idx] = e[layer * EMB:(layer + 1) * EMB, cy, cx]
            np.save(os.path.join(MAPS_DIR, "cells_{}.npy".format(n)), table)
        print("wrote cell tables for {} maps".format(len(rasters)))


if __name__ == "__main__":
    main()
