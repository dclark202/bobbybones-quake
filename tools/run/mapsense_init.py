"""2.1: the map sense's start from the pros' fit (sim/mapsense.py; docs/runs/2.1/DESIGN.md "the map sense ... starts from the pros'
fit"). The seeds' fit (tools/run/seed_calib2.py: two gradient-boosted models, data/sim_runs/space/seed_v2.joblib: what the next 5 s
bring, taken and dealt, from the 15 seeds) is distilled into the map sense's shared network, so the trainer needs no scikit-learn.
A STARTING POINT, measured from the pros' outcomes at places (CLAUDE.md rule 12: what a place is worth); the corrections a place
start at zero and his own games move them. Two steps, because scikit-learn lives in the system Python and torch in the Anaconda one:

    python tools/run/mapsense_init.py rows [--maps a,b] [--n 400000] [--out data/sim_runs/space/mapsense_rows.npz]      (system Python)
        pairs of walking points of each map within 1,500 units, a weapon each, a second's movement: their seeds and the two models'
        answers (measurement only: reads the maps' tables and the fit)
    <anaconda python> tools/run/mapsense_init.py fit [--rows ...] [--out data/sim_runs/space/mapsense_start.pt] [--hid 64] [--epochs 30]
        the shared network fitted to those answers (CPU, a minute or two on one core); prints its R2 against the fit on rows held out

The file's "mlp" is what the trainer's --map-sense-init loads (the hidden width must be --map-sense-hid)."""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import mapsense as MS  # noqa: E402

SPACE = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data", "sim_runs", "space")
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure"
W_P = np.array([0.28, 0.2, 0.28, 0.08, 0.04, 0.04, 0.06, 0.01, 0.01])      # the weapons drawn for the rows (the three big ones most)


def rows(a):
    import joblib
    M = joblib.load(os.path.join(SPACE, "seed_v2.joblib"))
    assert tuple(M["feats"]) == MS.FEATS, "the fit's seeds are not sim/mapsense.py's"
    T, miss = MS.load_tables(os.environ.get("QLBOT_ROOT") or ROOT, a.maps.split(","))
    if miss:
        print("no table for {}: skipped".format(", ".join(miss)))
    assert T, "no map has a table (data/maps/space_<map>.npz: tools/run/space_score.py score)"
    rng = np.random.default_rng(21)
    per = max(1, a.n // len(T))
    X = []
    for mp, S in sorted(T.items()):
        i = rng.integers(0, S.n, 4 * per)
        j = rng.integers(0, S.n, 4 * per)
        ok = np.linalg.norm(S.P[i] - S.P[j], axis=1) < MS.NEAR
        i, j = i[ok][:per], j[ok][:per]
        moved = np.where(rng.random(len(i)) < 0.3, rng.uniform(0, 60, len(i)), rng.uniform(60, 400, len(i)))
        X.append(MS.feats(S, i, j, S.P[i], S.P[j], rng.choice(9, len(i), p=W_P), rng.choice(9, len(i), p=W_P), moved))
        print("{}: {} pairs".format(mp, len(i)), flush=True)
    X = np.concatenate(X)
    take, put = M["models"]["take"].predict(X), M["models"]["put"].predict(X)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    np.savez_compressed(a.out, X=X.astype(np.float32), take=take.astype(np.float32), put=put.astype(np.float32), maps=np.array(sorted(T)))
    print("wrote {}: {} rows; the fit's mean taken {:.1f}, dealt {:.1f}".format(a.out, len(X), take.mean(), put.mean()))


def fit(a):
    import torch
    torch.set_num_threads(1)
    d = np.load(a.rows)
    X, y = d["X"], np.stack([d["put"], d["take"]], 1) / MS.Y_SCALE          # (OUTS: dealt, taken)
    L = MS.layout({}, hid=a.hid)
    mod = MS.make_module(L)
    x, c, yt = torch.from_numpy(MS.encode(X)), torch.from_numpy(MS.cls_of(X[:, 13])), torch.from_numpy(y.astype(np.float32))
    n = len(x)
    g = torch.Generator().manual_seed(22)
    pm = torch.randperm(n, generator=g)
    te, tr = pm[:n // 10], pm[n // 10:]
    opt = torch.optim.Adam(mod.mlp.parameters(), lr=a.lr)

    def pred(ii):
        return mod(x[ii], None).gather(2, c[ii][:, None, None].expand(-1, 2, 1))[..., 0]
    for ep in range(a.epochs):
        p2 = tr[torch.randperm(len(tr), generator=g)]
        for b in range(0, len(p2), 4096):
            ii = p2[b:b + 4096]
            loss = torch.nn.functional.mse_loss(pred(ii), yt[ii])
            opt.zero_grad()
            loss.backward()
            opt.step()
        if ep % 5 == 4 or ep == a.epochs - 1:
            with torch.no_grad():
                e = ((pred(te) - yt[te]) ** 2).mean(0)
                v = yt[te].var(0)
            print("epoch {}: on rows held out, R2 against the fit: dealt {:.4f}, taken {:.4f}".format(ep + 1, 1 - float(e[0] / v[0]), 1 - float(e[1] / v[1])), flush=True)
    torch.save(dict(mlp=mod.mlp.state_dict(), about=dict(rows=os.path.basename(a.rows), n=int(n), hid=int(a.hid), epochs=int(a.epochs),
                                                         maps=[str(m) for m in d["maps"]], feats=list(MS.FEATS), classes=list(MS.CLASSES))), a.out)
    print("wrote " + a.out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("rows", "fit"))
    ap.add_argument("--maps", default=MAPS)
    ap.add_argument("--n", type=int, default=400000)
    ap.add_argument("--rows", default=os.path.join(SPACE, "mapsense_rows.npz"))
    ap.add_argument("--out", default="")
    ap.add_argument("--hid", type=int, default=64)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lr", type=float, default=2e-3)
    a = ap.parse_args()
    if not a.out:
        a.out = os.path.join(SPACE, "mapsense_rows.npz" if a.cmd == "rows" else "mapsense_start.pt")
    dict(rows=rows, fit=fit)[a.cmd](a)
