"""The safe places of a map for the generated mid-game starts (GEN_START_SHARE in sim/duel_env.py; owner, 2026-10-25: "a
generative way of putting people in random positions, stacks, ammo, weapons ... use the walking maps or some other safe way to
sample positions, make sure he's not stuck in a wall"; "biased towards [the pros'] heatmaps, but tunable to what we want to
encourage").

Every point of the walking map (data/maps/nav_<map>_sim.json) is tried in the simulator itself:
  - reachable from a spawn point over the walking map's links (walk, jump, drop, pads, teleporters);
  - the player's box is free there (no start in solid), and neither the box's middle nor its feet are in lava, slime or water;
  - stood there with no input for one second he stays: at most 24 units sideways, at most 40 down, on the ground at the end
    (no ledge, slope, pad or trigger takes him), the playable map's inside (a cluster), no hazard under him at the end.
Each kept place gets the pros' heatmap weight: the pros' places in sim/pro_moments/<map>.npz (both players, every moment)
counted at their nearest kept place (within 96 units), smoothed over the places within 128 units.

Writes sim/gen_places/<map>.npz: pos (N,3) float32 (the player's origin), heat (N,) float32 (the pros' count, smoothed,
summing to 1), node (N,) the walking map's index; and <map>.json with the counts.
Run from the repo root with the Anaconda Python:  python tools/gen_places.py [--map m ...]"""
import argparse, json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import qsim  # noqa: E402

MAPS = ["bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure"]
CONTENTS_LAVA, CONTENTS_SLIME, CONTENTS_WATER = 8, 16, 32
BAD = CONTENTS_LAVA | CONTENTS_SLIME | CONTENTS_WATER


def reachable(g, starts, links=()):
    """the points of the walking map reachable from the spawns: its own links and `links` (the jump pads and teleporters, which
    the raw walking map does not carry: 2026-10-25, every point only a pad reaches was left out, Campgrounds' rail among them)"""
    n = len(g["nodes"])
    adj = [[] for _ in range(n)]
    for e in g["edges"]:
        adj[int(e[0])].append(int(e[1]))
    for a_, b_ in links:
        adj[int(a_)].append(int(b_))
    nodes = np.array(g["nodes"], np.float32)
    seen = np.zeros(n, bool)
    stack = []
    for s in starts:
        j = int(np.linalg.norm(nodes - np.asarray(s, np.float32), axis=1).argmin())
        if not seen[j]:
            seen[j] = True
            stack.append(j)
    while stack:
        a = stack.pop()
        for b in adj[a]:
            if not seen[b]:
                seen[b] = True
                stack.append(b)
    return seen


def one(mp, out_dir):
    bsp = os.path.join(ROOT, "data", "maps", mp + ".bsp")
    g = json.load(open(os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))))
    nodes = np.array(g["nodes"], np.float32)
    n = len(nodes)
    w = qsim.World(bsp, n=n)
    spawns = [e["origin"] for e in w.spawns()]
    links, mv0, an0 = [], np.zeros((n, 3), np.int8), np.zeros((n, 2), np.float32)
    for kind, c, d in w.trigger_spots():                     # (a pad: where the simulator throws him; a teleporter: its destination)
        if kind == 0:
            w.reset(0, tuple(np.asarray(c, np.float32) + np.array([0, 0, 30.0], np.float32)), (0, 0, 0), 0.0)
            for _ in range(160):
                w.step(mv0, an0, 25)
            land = np.asarray(w.state()[0, :3], np.float32)
        else:
            land = np.asarray(d, np.float32)
        b_ = int(np.linalg.norm(nodes - land, axis=1).argmin())
        src = np.nonzero((np.hypot(nodes[:, 0] - c[0], nodes[:, 1] - c[1]) < 130.0) & (np.abs(nodes[:, 2] - c[2]) < 96.0))[0]
        links += [(int(a_), b_) for a_ in src]
    reach = reachable(g, spawns, links)
    lo, hi = qsim.World.PLAYER_MINS, qsim.World.PLAYER_MAXS
    ok = reach.copy()
    why = dict(unreachable=int((~reach).sum()), solid=0, hazard=0, moved=0, fell=0, air=0, outside=0)
    for j in range(n):
        if not ok[j]:
            continue
        p = nodes[j]
        if w.trace(p, p, lo, hi)["startsolid"]:
            ok[j] = False; why["solid"] += 1; continue
        if (w.contents(p) | w.contents(p + np.array([0, 0, -22], np.float32))) & BAD:
            ok[j] = False; why["hazard"] += 1; continue
    for j in range(n):                                       # (all of them stood at once: one world, a player each)
        w.reset(j, nodes[j], (0, 0, 0), 0.0)
    moves = np.zeros((n, 3), np.int8)
    angles = np.zeros((n, 2), np.float32)
    for _ in range(40):
        w.step(moves, angles, 25)
    st = w.state()
    pos, vel = np.asarray(st[:, 0:3], np.float32), np.asarray(st[:, 3:6], np.float32)
    for j in np.nonzero(ok)[0]:
        d = pos[j] - nodes[j]
        if np.hypot(d[0], d[1]) > 24.0:
            ok[j] = False; why["moved"] += 1; continue
        if d[2] < -40.0 or d[2] > 8.0:
            ok[j] = False; why["fell"] += 1; continue
        if st[j, 6] < 0.5 or np.hypot(vel[j, 0], vel[j, 1]) > 5.0:
            ok[j] = False; why["air"] += 1; continue
        if w.cluster(pos[j]) < 0:
            ok[j] = False; why["outside"] += 1; continue
        if (w.contents(pos[j]) | w.contents(pos[j] + np.array([0, 0, -22], np.float32))) & BAD:
            ok[j] = False; why["hazard"] += 1; continue
    keep = np.nonzero(ok)[0]
    P = pos[keep].astype(np.float32)                         # (where he came to rest: the floor under the point)
    heat = np.zeros(len(keep), np.float64)
    pf = os.path.join(ROOT, "sim", "pro_moments", mp + ".npz")
    pro_n = 0
    if os.path.exists(pf) and len(keep):
        with np.load(pf) as z:
            pp = z["pos"].reshape(-1, 3).astype(np.float32)
        pro_n = len(pp)
        for a in range(0, len(pp), 2000):
            d = np.linalg.norm(pp[a:a + 2000, None, :] - P[None, :, :], axis=2)
            j = d.argmin(1)
            near = d[np.arange(len(j)), j] <= 96.0
            np.add.at(heat, j[near], 1.0)
        dd = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=2)
        k = np.exp(-0.5 * (dd / 64.0) ** 2) * (dd <= 128.0)
        heat = k @ heat
    heat = heat / heat.sum() if heat.sum() > 0 else np.full(len(keep), 1.0 / max(1, len(keep)))
    os.makedirs(out_dir, exist_ok=True)
    np.savez_compressed(os.path.join(out_dir, mp + ".npz"), version=np.int32(1), pos=P, heat=heat.astype(np.float32),
                        node=keep.astype(np.int32))
    info = dict(map=mp, nodes=n, kept=int(len(keep)), dropped=why, pro_places=pro_n,
                heat_top10_share=float(np.sort(heat)[::-1][:max(1, len(heat) // 10)].sum()))
    json.dump(info, open(os.path.join(out_dir, mp + ".json"), "w"), indent=1)
    print(json.dumps(info), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", action="append", default=[])
    ap.add_argument("--out", default=os.path.join(ROOT, "sim", "gen_places"))
    a = ap.parse_args()
    for mp in (a.map or MAPS):
        one(mp, a.out)


if __name__ == "__main__":
    main()
