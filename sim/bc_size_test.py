"""Does a bigger network predict pro players better? Imitation only, on the converted pro demos: the same kind of
network as BobbyBones at several sizes, each trained for the same wall-clock time, scored on demos it has not seen.

    python sim/bc_size_test.py --dir T:/quake-demos/sets/bloodrun --minutes 9 --sizes 256x512,512x1024,512x2048

Sizes are <layer width>x<memory>. The current network is 256x512. Prints loss and accuracy on held-out demos.
"""
import argparse
import glob
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ACTION_DIMS = (3, 3, 3, 23, 15, 2, 10, 2)
NAMES = ("forward", "strafe", "vertical", "turn", "pitch", "fire", "weapon", "walk")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--minutes", type=float, default=9.0)
    ap.add_argument("--sizes", default="256x512,512x1024,512x2048")
    ap.add_argument("--train-files", type=int, default=160)
    ap.add_argument("--val-files", type=int, default=30)
    ap.add_argument("--len", type=int, default=64)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--norm", default=os.path.join(ROOT, "data", "sim_runs", "duel_gru_v4", "policy.pt"))
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    rng = np.random.default_rng(0)
    files = sorted(glob.glob(os.path.join(a.dir, "*.npz")))
    files = [files[k] for k in rng.permutation(len(files))]
    ck = torch.load(a.norm, weights_only=False, map_location="cpu")
    mean, sd = ck["obs_mean"].astype(np.float32), np.sqrt(ck["obs_var"] + 1e-8).astype(np.float32)

    def load(fs):
        out = []
        for f in fs:
            z = np.load(f)
            if len(z["act"]) > a.len + 1:
                out.append((z["obs"], z["act"]))
        return out
    val = load(files[:a.val_files])
    train = load(files[a.val_files:a.val_files + a.train_files])
    print("train {} demos ({:.1f} h), held out {} demos ({:.1f} h)".format(
        len(train), sum(len(x[1]) for x in train) / 144000, len(val), sum(len(x[1]) for x in val) / 144000), flush=True)

    def batch(pool, r, B):
        o = np.zeros((B, a.len, len(mean)), np.float32)
        ac = np.zeros((B, a.len, len(ACTION_DIMS)), np.int64)
        for b in range(B):
            ob, act = pool[int(r.integers(len(pool)))]
            s0 = int(r.integers(0, len(act) - a.len))
            o[b] = np.clip((ob[s0:s0 + a.len].astype(np.float32) - mean) / sd, -10, 10)
            ac[b] = act[s0:s0 + a.len]
        return torch.from_numpy(o).to(dev), torch.from_numpy(ac).to(dev)

    vr = np.random.default_rng(1)
    val_batches = [batch(val, vr, a.batch) for _ in range(24)]          # the same held-out sequences for every size

    def score(net):
        net.eval()
        tot, acc, n = 0.0, np.zeros(len(ACTION_DIMS)), 0
        keys = turn1 = 0.0
        with torch.no_grad():
            for o, ac in val_batches:
                lg = net(o)[:, 8:]
                A = ac[:, 8:]
                parts = lg.split(ACTION_DIMS, -1)
                tot += float(sum(nn.functional.cross_entropy(p.reshape(-1, p.shape[-1]), A[..., j].reshape(-1))
                                 for j, p in enumerate(parts)))
                pred = [p.argmax(-1) for p in parts]
                acc += np.array([float((pred[j] == A[..., j]).float().mean()) for j in range(len(parts))])
                keys += float(((pred[0] == A[..., 0]) & (pred[1] == A[..., 1])).float().mean())
                turn1 += float(((pred[3] - A[..., 3]).abs() <= 1).float().mean())
                n += 1
        net.train()
        return tot / n, acc / n, keys / n, turn1 / n

    for size in a.sizes.split(","):
        W, H = (int(x) for x in size.split("x"))

        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.enc = nn.Sequential(nn.Linear(len(mean), W), nn.Tanh(), nn.Linear(W, W), nn.Tanh())
                self.gru = nn.GRU(W, H, batch_first=True)
                self.pi = nn.Linear(H, sum(ACTION_DIMS))

            def forward(self, x):
                return self.pi(self.gru(self.enc(x))[0])
        torch.manual_seed(0)
        net = Net().to(dev)
        opt = torch.optim.Adam(net.parameters(), lr=3e-4)
        r = np.random.default_rng(2)
        t0, steps = time.time(), 0
        while time.time() - t0 < a.minutes * 60:
            o, ac = batch(train, r, a.batch)
            lg = net(o)[:, 8:]
            A = ac[:, 8:]
            loss = sum(nn.functional.cross_entropy(p.reshape(-1, p.shape[-1]), A[..., j].reshape(-1))
                       for j, p in enumerate(lg.split(ACTION_DIMS, -1)))
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            steps += 1
        l, acc, keys, turn1 = score(net)
        print("size {:9s} weights {:9,d} steps {:5d} | held-out loss {:.3f} | movement keys right {:.3f} | turn within one bin {:.3f} | "
              "per head {}".format(size, sum(p.numel() for p in net.parameters()), steps, l, keys, turn1,
                                   {n_: round(float(v), 3) for n_, v in zip(NAMES, acc)}), flush=True)


if __name__ == "__main__":
    main()
