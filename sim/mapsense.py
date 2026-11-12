"""2.1 (docs/runs/2.1/DESIGN.md, question S8; the trainer's --map-sense): the map sense. "What is my place worth with the enemy where I
believe him": the damage he deals and takes in the next 5 s, for the weapon in his hand (rockets, the rail, the lightning gun, any
other). The owner, 2026-11-10: "it has to be a rule for the map he's playing on that he can adjust by self play".

Two parts, both learnt, nothing hand-set:
  the shared part    a small network over the map's SEEDS of a pair of places (his, the enemy's): how much of the ground the enemy can
                     reach in 1.5 s sees him, by the length of the line (3), the same the other way (3), each one's seconds to cover
                     from the other, how open each place is, the distance and height between them, how far he moved in the last
                     second, the two weapons. The same network on every map. Its start: the pros' fit (tools/run/seed_calib2.py's
                     models, distilled by tools/run/mapsense_init.py), or zero.
  the correction     a number a place of each map (the walking points of data/maps/space_<map>.npz) for each output, at zero to begin
                     with, pulled back toward zero after every step of its optimizer by MAP_SENSE_PULL (decoupled, as the head's
                     decay H2_L2): his games adjust the map and cannot erase it.

A LESSON ONLY: no pay, nothing reads its output yet (gate 0 of the design), its gradient reaches its own layers alone. It is not a part
of the policy: its own module, its own Adam, a top-level entry "map_sense" of the checkpoint (as the shadow win value's), so the
export, the checks, the league and the anchors do not see it.

Fairness: the FEATURES take the enemy's place and weapon from the brain's belief (what the head will read); the LABEL is the truth
(what the next 5 s really brought), known in hindsight. A sample with no believed place is not learnt from.

feats() is the one definition of the seeds (tools/run/seed_calib.py's, copied to the letter: its columns and order are FEATS).
"""
import math
import os

import numpy as np

VERSION = 1
SEED = 4061
FEATS = ("see_on_me_near", "see_on_me_mid", "see_on_me_far", "see_on_him_near", "see_on_him_mid", "see_on_him_far", "my_cover_s", "his_cover_s",
         "open_me", "open_him", "dist", "dz", "moved", "w_me", "w_him")
CLASSES = ("rockets", "rail", "lightning", "other")           # the weapon in his hand: duel_env's 0, 1, 2; every other weapon
OUTS = ("dealt", "taken")
NW = 9
NEAR = 1500.0                                                 # the enemy believed within this: a sample (seed_calib2's NEAR)
Y_SCALE = 100.0                                               # damage / 100
# what divides each numeric seed before the network (the two weapons go in as one-hots): shares stay; seconds to cover and the
# openness are capped at 3 s by the table; the distance within NEAR; the height; the units moved in a second
SCALE = np.array([1, 1, 1, 1, 1, 1, 3.0, 3.0, 3.0, 3.0, NEAR, 300.0, 320.0], np.float32)
N_IN = 13 + 2 * NW


def cls_of(w):
    w = np.asarray(w, np.int64)
    return np.where((w >= 0) & (w <= 2), w, 3)


def feats(S, i, j, pos, en, wme, wen, moved):
    """the seeds of the pairs (his point i, place pos; the enemy's point j, place en) -> [n, 15] (tools/run/seed_calib.py feats)"""
    X = np.zeros((len(i), len(FEATS)), np.float32)
    for q in range(3):
        X[:, q] = S.seeb[q][j, i] / 255.0
        X[:, 3 + q] = S.seeb[q][i, j] / 255.0
    X[:, 6], X[:, 7] = S.cov[j, i] / 80.0, S.cov[i, j] / 80.0
    X[:, 8], X[:, 9] = S.B[i], S.B[j]
    X[:, 10] = np.linalg.norm(pos - en, axis=1)
    X[:, 11] = pos[:, 2] - en[:, 2]
    X[:, 12] = moved
    X[:, 13], X[:, 14] = np.clip(wme, 0, 8), np.clip(wen, 0, 8)
    return X


def encode(X):
    """the seeds as the network reads them [n, N_IN]: the 13 numbers scaled (clipped at 3), the two weapons one-hot"""
    X = np.asarray(X, np.float32)
    out = np.zeros((len(X), N_IN), np.float32)
    out[:, :13] = np.clip(X[:, :13] / SCALE, -3.0, 3.0)
    r = np.arange(len(X))
    out[r, 13 + np.clip(X[:, 13].astype(np.int64), 0, NW - 1)] = 1.0
    out[r, 13 + NW + np.clip(X[:, 14].astype(np.int64), 0, NW - 1)] = 1.0
    return out


class Table:
    """a map's table for the seeds (data/maps/space_<map>.npz, tools/run/space_score.py): the walking points, the sight shares by
    the line's length, the seconds to cover, the openness; at(): the nearest walking point of a place (the table's own 32-unit grid,
    as sim/space.py; without one: the nearest by distance, height counted double)"""

    def __init__(self, path):
        d = np.load(path)
        self.P = d["nodes"].astype(np.float32)
        self.B = d["B"].astype(np.float32)
        self.cov = d["cov8"]
        self.seeb = d["seeb8"]
        self.n = len(self.P)
        if "grid" in d.files:
            self.grid, self.lo, self.cell = d["grid"].astype(np.int64), d["lo"].astype(np.float64), float(d["cell"])
            self.dims = np.array(self.grid.shape, np.int64)
        else:
            self.grid = None

    def at(self, pos):
        pos = np.asarray(pos, np.float64).reshape(-1, 3)
        if self.grid is not None:
            c = np.clip(((pos - self.lo) / self.cell).astype(np.int64), 0, self.dims - 1)
            return self.grid[c[:, 0], c[:, 1], c[:, 2]]
        wz = np.array([1.0, 1.0, 2.0])
        out = np.zeros(len(pos), np.int64)
        for b in range(0, len(pos), 2048):
            out[b:b + 2048] = np.linalg.norm((pos[b:b + 2048, None] - self.P[None]) * wz, axis=2).argmin(1)
        return out


def table_path(root, mp):
    return os.path.join(root, "data", "maps", "space_{}.npz".format(mp))


def load_tables(root, maps):
    """-> ({map: Table}, [maps without a table, or whose table lacks the seeds' arrays]): a missing map is skipped, never an error"""
    T, miss = {}, []
    for mp in sorted(set(maps)):
        p = table_path(root, mp)
        try:
            T[mp] = Table(p)
        except Exception:                                    # noqa: BLE001  (no file; an older table without cov8 / seeb8)
            miss.append(mp)
    return T, miss


def layout(tables, hid=64, every=5, tick=8, horizon_frames=200):
    """tables: {map: Table} (or {map: number of points}); the corrections' rows are the maps' points one after another, by name"""
    names = sorted(tables)
    n = [int(tables[m].n if hasattr(tables[m], "n") else tables[m]) for m in names]
    off = np.concatenate([[0], np.cumsum(n)]).astype(int)
    return dict(version=VERSION, feats=list(FEATS), classes=list(CLASSES), outs=list(OUTS), inp=N_IN, hid=int(hid),
                d=len(OUTS) * len(CLASSES), maps={m: dict(off=int(off[k]), n=int(n[k])) for k, m in enumerate(names)}, rows=int(off[-1]),
                every=int(every), tick=int(tick), horizon=int(horizon_frames), near=NEAR, y_scale=Y_SCALE)


def make_module(L):
    """the shared network (its last layer at zero: a forecast of 0 until taught or given the pros' fit) and the corrections (at zero),
    from a random stream of its own"""
    import torch
    import torch.nn as nn

    class MapSense(nn.Module):
        def __init__(self):
            super().__init__()
            self.mlp = nn.Sequential(nn.Linear(int(L["inp"]), int(L["hid"])), nn.ReLU(), nn.Linear(int(L["hid"]), int(L["hid"])), nn.ReLU(),
                                     nn.Linear(int(L["hid"]), int(L["d"])))
            self.corr = nn.Embedding(max(1, int(L["rows"])), int(L["d"]))

        def forward(self, x, row=None):
            """x [B, inp] (encode()), row [B] the correction's row of his place (None or -1: none) -> [B, outs, classes] (damage / 100)"""
            y = self.mlp(x)
            if row is not None:
                ok = (row >= 0).to(y.dtype)[:, None]
                y = y + self.corr(row.clamp(min=0)) * ok
            return y.view(len(x), len(OUTS), len(CLASSES))

    assert int(L.get("version", 0)) == VERSION, "mapsense: layout version {} expected".format(VERSION)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(SEED)
        m = MapSense()
    with torch.no_grad():
        m.mlp[4].weight.zero_()
        m.mlp[4].bias.zero_()
        m.corr.weight.zero_()
    return m


def load_start(mod, path):
    """the shared part's start from the pros' fit (tools/run/mapsense_init.py's file); the corrections stay at zero"""
    import torch
    st = torch.load(path, map_location="cpu", weights_only=False)
    mod.mlp.load_state_dict(st["mlp"])
    return st.get("about")


def sample_frames(L, T, back=40):
    """the frames of a rollout of T a sample is taken at: a tick of the brain's every `every` ticks, with a second behind it (for
    "moved") and the whole horizon ahead inside the rollout"""
    K, E, D = int(L["tick"]), int(L["every"]), int(L["horizon"])
    return [t for t in range(K - 1, T, K) if (t // K) % E == E - 1 and t >= back and t + D <= T]


def window_sum(x, stop, t, D):
    """sum over the frames f = t .. t + D - 1 of x[f] [.., N] while no stop came before f (stop[f] [.., N]: a round's end or his death
    in step f; that step's own x still counts) -> [N]"""
    x = np.asarray(x[t:t + D], np.float64)
    s = np.asarray(stop[t:t + D], np.float64) > 0.5
    live = np.ones_like(s)
    live[1:] = ~(np.cumsum(s[:-1], 0) > 0)
    return (x * live).sum(0)


def batch(L, tables, seat_map, aux, done, bel, ix, group=2, back=40):
    """this rollout's samples. aux [T + 1, N, C] the simulator's truth (row t: before step t; the damage of step t is in row t + 1),
    done [T, N], bel [T // tick, N, 5] the brain's belief at each tick (the enemy's place x, y, z in map coordinates; valid; the
    weapon believed in his hand), seat_map [N] the map's name of each seat, ix: column -> index of aux
    -> dict(x [B, inp], row [B], cls [B], y [B, 2], n_skip) on the host, or None"""
    assert group == 2, "mapsense: duels"
    def g(x):                                                # (a piece of the truth as float32 numpy: only what is read, the buffer is large)
        return x.float().cpu().numpy() if hasattr(x, "cpu") else np.asarray(x, np.float32)
    done = g(done)
    bel = np.asarray(bel, np.float32)
    T, N = done.shape
    K, D = int(L["tick"]), int(L["horizon"])
    foe = np.arange(N) ^ 1
    cx = ix["x"]
    stop = np.maximum(done, g(aux[1:T + 1, :, ix["died"]]))  # his stay ends with the round or his life
    a_dealt, a_taken = g(aux[1:T + 1, :, ix["dmg_dealt"]]), g(aux[1:T + 1, :, ix["dmg_taken"]])
    X, R, Cc, Y = [], [], [], []
    seat_map = np.asarray(seat_map)
    for t in sample_frames(L, T, back):
        b = bel[t // K]
        pos, pos0 = g(aux[t, :, cx:cx + 3]), g(aux[t - back, :, cx:cx + 3])
        quiet = ~(stop[t - back:t].max(0) > 0.5)             # the second behind him is one life's
        al = g(aux[t, :, ix["en_alive"]]) > 0.5
        alive = al & al[foe]
        ok = quiet & alive & (b[:, 3] > 0.5) & (np.linalg.norm(pos - b[:, :3], axis=1) < float(L["near"]))
        dealt = window_sum(a_dealt, stop, t, D)
        taken = window_sum(a_taken, stop, t, D)
        wme = g(aux[t, :, ix["en_weapon"]])[foe].astype(np.int64)  # (the enemy's row holds the weapon in MY hand)
        for mp, S in tables.items():
            m = np.nonzero(ok & (seat_map == mp))[0]
            if not len(m):
                continue
            i, j = S.at(pos[m]), S.at(b[m, :3])
            f = feats(S, i, j, pos[m], b[m, :3], wme[m], b[m, 4].astype(np.int64), np.linalg.norm(pos[m] - pos0[m], axis=1))
            X.append(encode(f))
            R.append(int(L["maps"][mp]["off"]) + i.astype(np.int64))
            Cc.append(cls_of(wme[m]))
            Y.append(np.stack([dealt[m], taken[m]], 1).astype(np.float32) / float(L["y_scale"]))
    if not X:
        return None
    return dict(x=np.concatenate(X), row=np.concatenate(R), cls=np.concatenate(Cc), y=np.concatenate(Y))


def learn(mod, opt, L, B, lr, pull, dev, gen, mb=8192, epochs=1):
    """score the forecast (before learning), then one pass of its lesson; after every step of its optimizer the corrections are
    pulled toward zero: weight x (1 - rate x pull) (decoupled; pull 0: none) -> the counters for record()"""
    import torch
    out = {}
    if B is None or not len(B["x"]):
        return out
    x, row = torch.from_numpy(B["x"]), torch.from_numpy(B["row"])
    cls, y = torch.from_numpy(B["cls"]), torch.from_numpy(B["y"])
    n = len(x)
    P = torch.empty(n, len(OUTS))
    P0 = torch.empty(n, len(OUTS))                           # the shared part alone (the seeds without the corrections)
    with torch.no_grad():
        for b in range(0, n, mb):
            xb, rb, cb = x[b:b + mb].to(dev), row[b:b + mb].to(dev), cls[b:b + mb].to(dev)
            P[b:b + mb] = mod(xb, rb).gather(2, cb[:, None, None].expand(-1, len(OUTS), 1))[..., 0].float().cpu()
            P0[b:b + mb] = mod(xb, None).gather(2, cb[:, None, None].expand(-1, len(OUTS), 1))[..., 0].float().cpu()
    y64 = y.double()
    out.update(n=n, sy=y64.sum(0), syy=(y64 ** 2).sum(0), sq=((P.double() - y64) ** 2).sum(0), sq0=((P0.double() - y64) ** 2).sum(0),
               ex=(((P[:, 0] - P[:, 1]).double() - (y64[:, 0] - y64[:, 1])) ** 2).sum(), exy=(y64[:, 0] - y64[:, 1]).sum(),
               exyy=((y64[:, 0] - y64[:, 1]) ** 2).sum(), by=torch.bincount(cls, minlength=len(CLASSES)).double())
    if lr > 0:
        for g_ in opt.param_groups:
            g_["lr"] = float(lr)
        for _ in range(int(epochs)):
            pm = torch.randperm(n, generator=gen)
            for b in range(0, n, mb):
                i_ = pm[b:b + mb]
                xb, rb, cb, yb = x[i_].to(dev), row[i_].to(dev), cls[i_].to(dev), y[i_].to(dev)
                p = mod(xb, rb).gather(2, cb[:, None, None].expand(-1, len(OUTS), 1))[..., 0]
                l_ = torch.nn.functional.smooth_l1_loss(p, yb)
                opt.zero_grad(set_to_none=True)
                l_.backward()
                torch.nn.utils.clip_grad_norm_(mod.parameters(), 1.0)
                opt.step()
                if pull > 0:
                    with torch.no_grad():
                        mod.corr.weight.mul_(max(0.0, 1.0 - float(lr) * float(pull)))
    with torch.no_grad():
        out["corr_abs"] = float(mod.corr.weight.abs().mean())
        out["corr_max"] = float(mod.corr.weight.abs().max())
    return out


def _r2(sq, sy, syy, n):
    var = float(syy) - float(sy) ** 2 / max(1.0, float(n))
    return None if var <= 0 or n < 2 else round(1.0 - float(sq) / var, 4)


def record(acc, w, pull, L, skipped=()):
    """the update's counters -> metrics.jsonl's "map_sense": the samples, by weapon class; R2 of dealt, taken and the exchange (dealt
    less taken) before the step, with the corrections and for the shared part alone; the corrections' size (damage / 100)"""
    rec = dict(w=round(float(w), 4), pull=round(float(pull), 6), frames=int(acc.get("n", 0)) if acc else 0)
    if skipped:
        rec["maps_without_table"] = list(skipped)
    if not acc or not acc.get("n"):
        return rec
    n = acc["n"]
    rec.update(by_class={c: int(acc["by"][k]) for k, c in enumerate(CLASSES)},
               mean={o: round(float(acc["sy"][k]) / n * float(L["y_scale"]), 2) for k, o in enumerate(OUTS)},
               r2={o: _r2(acc["sq"][k], acc["sy"][k], acc["syy"][k], n) for k, o in enumerate(OUTS)},
               r2_seeds={o: _r2(acc["sq0"][k], acc["sy"][k], acc["syy"][k], n) for k, o in enumerate(OUTS)},
               r2_exchange=_r2(acc["ex"], acc["exy"], acc["exyy"], n),
               corr_abs=round(acc["corr_abs"], 5), corr_max=round(acc["corr_max"], 4))
    return rec


def read(mod, L, tables, mp, pos, en, wme, wen, moved, dev="cpu"):
    """(for the head's inputs and the appraisals, later; and the tools) the forecast at places of one map -> [n, outs, classes] numpy
    (damage, not / 100); zeros for a map without a table"""
    import torch
    S = tables.get(mp)
    n = len(pos)
    if S is None:
        return np.zeros((n, len(OUTS), len(CLASSES)), np.float32)
    i, j = S.at(pos), S.at(en)
    x = torch.from_numpy(encode(feats(S, i, j, np.asarray(pos, np.float32), np.asarray(en, np.float32), wme, wen, moved))).to(dev)
    row = torch.from_numpy(int(L["maps"][mp]["off"]) + i.astype(np.int64)).to(dev) if mp in L["maps"] else None
    with torch.no_grad():
        return (mod(x, row).float().cpu().numpy() * float(L["y_scale"])).astype(np.float32)


def np_params(sd):
    """the module's weights as numpy (the checks, the servers)"""
    return {k: (v.detach().cpu().numpy() if hasattr(v, "detach") else np.asarray(v)).astype(np.float32) for k, v in sd.items()}


def np_forward(P, x, row=None):
    """the module's forward in numpy: x [B, inp] (encode()), row [B] (None or -1: no correction) -> [B, outs x classes] (damage / 100)"""
    y = np.maximum(x @ P["mlp.0.weight"].T + P["mlp.0.bias"], 0.0)
    y = np.maximum(y @ P["mlp.2.weight"].T + P["mlp.2.bias"], 0.0)
    y = y @ P["mlp.4.weight"].T + P["mlp.4.bias"]
    if row is not None:
        r = np.asarray(row, np.int64)
        y = y + P["corr.weight"][np.maximum(r, 0)] * (r >= 0)[:, None]
    return y.astype(np.float32)


def rows_at(fwd, L, tables, seat_map, P, pk, en, en_ok, wme, wen):
    """(2.1, piece: the map sense at each candidate's place) for every seat's candidate rows: P [n, C, 3] the rows' places and pk
    [n, C] which have one (and are offered), en [n, 3] the place the brain believes the enemy at and en_ok [n] that it believes
    one, wme [n] the weapon in his hand, wen [n] the weapon the brain believes in the enemy's; seat_map [n] each seat's map by
    name. "Standing there": the seed "moved in the last second" is 0. fwd(x [K, inp], row [K] or None) -> [K, 8] is the module
    (torch or numpy: the caller's). -> [n, C, 8] the module's own numbers (damage / 100; zeros for a row without a place, a seat
    without a believed place, a map without a table)"""
    pk = np.asarray(pk, bool) & np.asarray(en_ok, bool)[:, None]
    n, C = pk.shape
    out = np.zeros((n, C, len(OUTS) * len(CLASSES)), np.float32)
    if not pk.any():
        return out
    sm = np.asarray(seat_map)
    for mp, S in tables.items():
        r, c = np.nonzero(pk & (sm == mp)[:, None])
        if not len(r):
            continue
        pos, e = np.asarray(P, np.float32)[r, c], np.asarray(en, np.float32)[r]
        i, j = S.at(pos), S.at(e)
        x = encode(feats(S, i, j, pos, e, np.asarray(wme)[r], np.asarray(wen)[r], np.zeros(len(r), np.float32)))
        row = (int(L["maps"][mp]["off"]) + i.astype(np.int64)) if mp in L["maps"] else None
        out[r, c] = np.asarray(fwd(x, row), np.float32).reshape(len(r), -1)
    return out


def torch_fwd(mod, dev):
    """rows_at's fwd for the torch module"""
    import torch

    def f(x, row):
        with torch.no_grad():
            return mod(torch.from_numpy(x).to(dev), None if row is None else torch.from_numpy(row).to(dev)).float().reshape(len(x), -1).cpu().numpy()
    return f


def _nan(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x
