"""Does he stand where people stand? The logged frames of people playing the bots on a map are pooled into a map of
where they are (cells of 32 units, top view), and set against Bobby's map from tools/stack_probe.py (docs/PLAN.md,
"the experiment", layer 3: positioning on arena1 as it is learned on the duel maps).

    python tools/position_overlap.py --map arena1 --bobby videos/duel_gru_v12_4720/probe_heat_arena1.npz [more .npz ...]
    python tools/position_overlap.py --map arena1 --people-only          (how much there is)

People: every session of that map in data/*/sessions and in the archive of the public server (T:/quake-sessions/public
or SESSION_ARCHIVE), the frames of the human players while alive; warmup included (people move the same way), no names.
Printed: minutes of people, and per Bobby map the overlap (0 = nowhere the same, 1 = the same distribution: the sum over
cells of the smaller of the two shares), the share of his time in the cells that hold 90% of people's time, and of theirs in his.
"""
import argparse
import csv
import glob
import io
import json
import os
import sys
import tarfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELL = 32


def people_xy(meta, rows):
    """x, y of the human players of one session (alive frames)"""
    r = csv.DictReader(rows)
    xs, ys = [], []
    ffa = "seat" in (r.fieldnames or [])
    px, hp = ("b_x", "b_health") if ffa else ("o_x", "o_health")
    py = px[:-1] + "y"
    for row in r:
        try:
            if ffa and row["bot"] != "0":
                continue
            if float(row[hp] or 0) <= 0:
                continue
            xs.append(float(row[px]))
            ys.append(float(row[py]))
        except (ValueError, KeyError, TypeError):
            continue
    return np.array(xs, np.float32), np.array(ys, np.float32)


def sessions(mp):
    """(name, meta, an open text file of frames.csv) for every logged session of the map"""
    seen = set()
    for d in sorted(glob.glob(os.path.join(ROOT, "data", "*", "sessions", "*"))):
        mj, fc = os.path.join(d, "meta.json"), os.path.join(d, "frames.csv")
        name = os.path.basename(d)
        if name in seen or name.endswith("_spar") or not (os.path.exists(mj) and os.path.exists(fc)):
            continue
        try:
            meta = json.load(open(mj, encoding="utf-8"))
        except ValueError:
            continue
        if str(meta.get("map", "")).lower() == mp:
            seen.add(name)
            yield name, meta, open(fc, encoding="utf-8", errors="replace", newline="")
    arch = os.environ.get("SESSION_ARCHIVE", "T:/quake-sessions/public")
    for f in sorted(glob.glob(os.path.join(arch, "*.tar.gz"))):
        name = os.path.basename(f)[:-7]
        if name in seen or name.endswith("_spar"):
            continue
        try:
            with tarfile.open(f) as tf:
                mem = {os.path.basename(m.name): m for m in tf.getmembers()}
                if "meta.json" not in mem or "frames.csv" not in mem:
                    continue
                meta = json.load(tf.extractfile(mem["meta.json"]))
                if str(meta.get("map", "")).lower() != mp:
                    continue
                txt = io.StringIO(tf.extractfile(mem["frames.csv"]).read().decode("utf-8", "replace"), newline="")
        except (tarfile.TarError, OSError, ValueError):
            continue
        seen.add(name)
        yield name, meta, txt


def core(p, share=0.9):
    """the smallest set of cells that holds this share of the time"""
    order = np.argsort(p.ravel())[::-1]
    k = int(np.searchsorted(np.cumsum(p.ravel()[order]), share)) + 1
    m = np.zeros(p.size, bool)
    m[order[:k]] = True
    return m.reshape(p.shape)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="arena1")
    ap.add_argument("--bobby", nargs="*", default=[], help="probe_heat_<map>.npz files of tools/stack_probe.py")
    ap.add_argument("--people-only", action="store_true")
    ap.add_argument("--save", default="", help="write the people's map here (.npz)")
    a = ap.parse_args()
    X, Y, n_sess = [], [], 0
    for name, meta, f in sessions(a.map):
        x, y = people_xy(meta, f)
        f.close()
        if len(x) >= 400:
            X.append(x)
            Y.append(y)
            n_sess += 1
    if not X:
        sys.exit("no frames of people on {}".format(a.map))
    X, Y = np.concatenate(X), np.concatenate(Y)
    print("people on {}: {} sessions, {:.0f} minutes alive".format(a.map, n_sess, len(X) / 2400.0))
    if a.people_only and not a.save:
        return
    ref = np.load(a.bobby[0]) if a.bobby else None
    lo = ref["lo"] if ref is not None else np.array([X.min(), Y.min()])
    shape = ref["heat"].shape if ref is not None else (int((Y.max() - lo[1]) / CELL) + 2, int((X.max() - lo[0]) / CELL) + 2)
    cx = np.clip(((X - lo[0]) / CELL).astype(int), 0, shape[1] - 1)
    cy = np.clip(((Y - lo[1]) / CELL).astype(int), 0, shape[0] - 1)
    P = np.zeros(shape)
    np.add.at(P, (cy, cx), 1.0)
    if a.save:
        np.savez(a.save, heat=P, lo=lo, cell=CELL)
    p = P / P.sum()
    for b in a.bobby:
        d = np.load(b)
        q = d["heat"] / max(1.0, d["heat"].sum())
        if q.shape != p.shape:
            print("{}: another grid, skipped".format(b))
            continue
        print("{}: overlap {:.3f} | his time in the cells that hold 90% of people's {:.0%} | people's time in the cells that hold 90% of his {:.0%}".format(
            os.path.relpath(b, ROOT) if os.path.isabs(b) else b, float(np.minimum(p, q).sum()), float(q[core(p)].sum()), float(p[core(q)].sum())))


if __name__ == "__main__":
    main()
