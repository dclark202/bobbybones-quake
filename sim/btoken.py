"""v0.4.1: the brain's answer as one more token of the hands' attention (docs/v0.4.0/RUN_v0.4.1.md; sim/attn.py "btok").

The brain (sim/belief.py) ticks every K frames (0.2 s); at a tick its readouts (sim/track.py: the enemy's place with its
spreads, stack band, weapon in hand, weapons owned; sim/track_z.py: the zone odds, speed, direction) answer in his facing of
that frame. The answer is kept in map coordinates (his own place and yaw at the tick: his own knowledge) and turned into his
facing of every later frame until the next tick, so a turn between two ticks turns the answer with him. The readouts' frame
is turned by yaw only (forward, left, up), so the token is too; pitch is not used.

What the token says (the feature list is made from the readouts' layouts in the checkpoint: a part is in it when its lesson
weight there is above zero; the list is written into the checkpoint's "btoken" entry and never changes after):
  pos    the believed place from him now (forward, left, up; thousands of units), its distance across the floor, the two
         log spreads (across, up and down)
  vel    (only if its lesson is on) the believed velocity turned to him now, its log spread
  band   the odds of the enemy's stack band (4)
  hand   the odds of the weapon in his hand (9)
  own    the chance he owns each of six weapons (6)
  zone   the odds over the map's zones (24, by the zone's number; 0 past the map's count), and the three likeliest zones'
         centres from him now (forward, left, up; thousands of units) with their odds
  spd    the believed speed (thousands of units a second), its log spread
  dir    the believed way he moves, turned to him now: (cos, sin) x k / (1 + k), and log(1 + k) / 5 (k the concentration)
  always the time since he last noticed the enemy in view (his own input "enemy: noticed in view"), log(1 + s) / log(61),
         the answer's age (frames since its tick / K) and that there is an answer (0 after a reset until the next tick)
The point and the zones are both there always (the owner, 2026-10-23): the hands weigh them by the time since seen.

Plain numpy: the trainer (on the host, every seat in one call) and the checks (test_suite.Policy) make the same numbers.
The numbers the hands see are rounded to half precision before use, so the trainer's learning step reads exactly what was
played (it stores them so).
"""
import math
import os

import numpy as np

VERSION = 1
UNSEEN_CAP = 60.0
DT = 0.025
TRK_LS = dict(ls_xy=(math.log(0.04), math.log(4.0)), ls_z=(math.log(0.03), math.log(1.5)), ls_v=(math.log(0.03), math.log(1.0)))
TRK_SL = dict(pos=(0, 3), ls_xy=3, ls_z=4, vel=(5, 7), ls_v=7, band=(8, 12), hand=(12, 21), own=(21, 27))
Z_MAX = 24
Z_SL = dict(zone=(0, 24), spd=24, ls_s=25, dir=(26, 28))
Z_LS = (math.log(0.01), math.log(0.6))
TOPZ = 3
SEEN_INPUT = ("enemy", "noticed in view")


def _on(L, part):
    return L is not None and part in L.get("parts", ()) and float((L.get("weights") or {}).get(part, 0.0)) > 0.0


def layout(trk_L, trz_L, every, seen_col):
    """the checkpoint's "btoken" entry: the feature names, their count, the clock, the gate (shut)"""
    f = []
    if _on(trk_L, "pos"):
        f += ["pos_f", "pos_l", "pos_u", "pos_dist", "pos_ls_xy", "pos_ls_z"]
    if _on(trk_L, "vel"):
        f += ["vel_f", "vel_l", "vel_ls"]
    if _on(trk_L, "band"):
        f += ["band_{}".format(i) for i in range(4)]
    if _on(trk_L, "hand"):
        f += ["hand_{}".format(i) for i in range(9)]
    if _on(trk_L, "own"):
        f += ["own_{}".format(w) for w in ("rl", "rg", "lg", "pg", "gl", "sg")]
    if _on(trz_L, "zone"):
        f += ["zone_{}".format(i) for i in range(Z_MAX)]
        for k in range(TOPZ):
            f += ["ztop{}_{}".format(k, c) for c in ("f", "l", "u", "p")]
    if _on(trz_L, "spd"):
        f += ["spd", "spd_ls"]
    if _on(trz_L, "dir"):
        f += ["dir_c", "dir_s", "dir_k"]
    f += ["unseen", "age", "valid"]
    return dict(version=VERSION, every=int(every), seen_col=int(seen_col), feats=f, dim=len(f), gate=0.0)


def describe(L):
    return "brain token (v0.4.1): {} numbers ({}), gate {:.4f}".format(L["dim"], ", ".join(sorted({n.split("_")[0] for n in L["feats"]})),
                                                                      float(L.get("gate", 0.0)))


def seen_col(inputs_csv):
    """the index of his input "enemy: noticed in view" in docs/INPUTS.csv"""
    import csv
    for r in csv.DictReader(open(inputs_csv, encoding="utf-8")):
        if (r["group"], r["input"]) == SEEN_INPUT:
            return int(r["index"])
    raise ValueError("no input {} in {}".format(SEEN_INPUT, inputs_csv))


def _squash(x, lo, hi):
    mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
    return mid + half * np.tanh((x - mid) / half)


def _softmax(l):
    l = l - l.max(-1, keepdims=True)
    e = np.exp(l)
    return e / e.sum(-1, keepdims=True)


_ZC = {}


def zone_table():
    """[maps, Z_MAX, 3] the zones' centres by sim/zonemap.py's map numbers, [maps] their counts (0: no zones)"""
    if "t" not in _ZC:
        import zonemap as zm
        c = np.zeros((len(zm.MAPS), Z_MAX, 3), np.float32)
        k = np.zeros(len(zm.MAPS), np.int64)
        for i, m in enumerate(zm.MAPS):
            z = zm.load(m)
            if z is not None:
                k[i] = z.k
                c[i, :z.k] = z.centres
        _ZC["t"] = (c, k)
    return _ZC["t"]


def pose_from_aux(aux, cols):
    """his own place and yaw (degrees) [n, 4] and the zones' map number [n] from info["aux"] rows (the trainer)"""
    C = {k: i for i, k in enumerate(cols)}
    p = np.stack([aux[:, C["x"]], aux[:, C["y"]], aux[:, C["z"]], aux[:, C["yaw"]]], 1).astype(np.float32)
    zm = aux[:, C["zone_map"]].round().astype(np.int64) if "zone_map" in C else np.full(len(aux), -1, np.int64)
    return p, zm


def pose_from_env(env, mapname=None):
    """the same numbers straight from a simulator (the checks): as aux() writes them (float32, yaw in -180 .. 180); the zones'
    map number from the simulator (TRACK_Z) or the map's name"""
    n = env.n
    p = np.zeros((n, 4), np.float32)
    p[:, :3] = env.state[:n, :3]
    p[:, 3] = (np.asarray(env.yaw[:n]) + 180.0) % 360.0 - 180.0
    zm_ = getattr(env, "zone_map", None)
    if zm_ is None:
        import zonemap as zm
        zm_ = zm.MAPS.index(mapname) if mapname in zm.MAPS else -1
    return p, np.full(n, int(zm_), np.int64)


def _turn(yaw_deg, f, l):
    """(forward, left) in a facing of yaw -> (x, y) of the map"""
    r = np.radians(yaw_deg.astype(np.float64))
    c, s = np.cos(r), np.sin(r)
    return c * f - s * l, s * f + c * l


def _unturn(yaw_deg, x, y):
    """(x, y) of the map -> (forward, left) in a facing of yaw (as the simulator's en_fwd, en_left)"""
    r = np.radians(yaw_deg.astype(np.float64))
    c, s = np.cos(r), np.sin(r)
    return c * x + s * y, -s * x + c * y


class Token:
    """the token's state for n seats: the last tick's answer in map coordinates, its age, the time since the enemy was noticed"""

    def __init__(self, n, L):
        self.L, self.n = L, n
        self.f = list(L["feats"])
        self.ix = {k: i for i, k in enumerate(self.f)}
        self.K = int(L["every"])
        self.col = int(L["seen_col"])
        self.valid = np.zeros(n, bool)
        self.age = np.zeros(n, np.float32)
        self.unseen = np.full(n, UNSEEN_CAP, np.float32)
        self.P = np.zeros((n, 3), np.float64)          # the believed place (map)
        self.ls = np.zeros((n, 2), np.float32)
        self.V = np.zeros((n, 2), np.float64)          # the believed velocity (map; units a second)
        self.lsv = np.zeros(n, np.float32)
        self.band = np.zeros((n, 4), np.float32)
        self.hand = np.zeros((n, 9), np.float32)
        self.own = np.zeros((n, 6), np.float32)
        self.zone = np.zeros((n, Z_MAX), np.float32)
        self.zmap = np.full(n, -1, np.int64)
        self.spd = np.zeros((n, 2), np.float32)
        self.eta = np.zeros((n, 2), np.float64)        # the direction's natural parameters, turned to the map

    def state(self):
        return {k: getattr(self, k).copy() for k in ("valid", "age", "unseen", "P", "ls", "V", "lsv", "band", "hand", "own", "zone",
                                                    "zmap", "spd", "eta")}

    def load(self, st):
        for k, v in st.items():
            setattr(self, k, v.copy())

    def see(self, obs_raw):
        """once a frame, before features(): his own input "noticed in view" of this frame"""
        s = np.asarray(obs_raw)[:, self.col] > 0.5
        self.unseen = np.where(s, 0.0, np.minimum(self.unseen + DT, UNSEEN_CAP)).astype(np.float32)

    def answer(self, rows, o_trk, o_trz, pose, zmap):
        """a tick for these seats (rows: bool [n] or None = all): the readouts' outputs [m, 27] / [m, 28] (None: not in the
        network) and his own pose [m or n, 4] and zones' map [m or n] at the tick frame -> the answer kept in map coordinates"""
        r = np.arange(self.n) if rows is None else np.nonzero(rows)[0]
        if len(r) == 0:
            return
        pz = pose if len(pose) == len(r) else pose[r]
        zm = zmap if len(zmap) == len(r) else zmap[r]
        y = pz[:, 3]
        if o_trk is not None:
            o = np.asarray(o_trk, np.float64)
            a0, a1 = TRK_SL["pos"]
            x_, y_ = _turn(y, o[:, a0] * 1000.0, o[:, a0 + 1] * 1000.0)
            self.P[r] = np.stack([pz[:, 0] + x_, pz[:, 1] + y_, pz[:, 2] + o[:, a0 + 2] * 1000.0], 1)
            self.ls[r, 0] = _squash(o[:, TRK_SL["ls_xy"]], *TRK_LS["ls_xy"])
            self.ls[r, 1] = _squash(o[:, TRK_SL["ls_z"]], *TRK_LS["ls_z"])
            v0, _ = TRK_SL["vel"]
            self.V[r] = np.stack(_turn(y, o[:, v0] * 1000.0, o[:, v0 + 1] * 1000.0), 1)
            self.lsv[r] = _squash(o[:, TRK_SL["ls_v"]], *TRK_LS["ls_v"])
            b0, b1 = TRK_SL["band"]
            self.band[r] = _softmax(o[:, b0:b1])
            h0, h1 = TRK_SL["hand"]
            self.hand[r] = _softmax(o[:, h0:h1])
            w0, w1 = TRK_SL["own"]
            self.own[r] = 1.0 / (1.0 + np.exp(-o[:, w0:w1]))
        if o_trz is not None:
            o = np.asarray(o_trz, np.float64)
            _, kz = zone_table()
            k_ = np.where(zm >= 0, kz[np.clip(zm, 0, len(kz) - 1)], 0)
            lg = o[:, 0:Z_MAX].copy()
            lg[np.arange(Z_MAX)[None, :] >= np.maximum(k_, 1)[:, None]] = -1e4      # (as track_z.zone_logits)
            pzn = _softmax(lg)
            pzn[k_ <= 0] = 0.0
            self.zone[r] = pzn
            self.spd[r, 0] = o[:, Z_SL["spd"]]
            self.spd[r, 1] = _squash(o[:, Z_SL["ls_s"]], *Z_LS)
            d0, _ = Z_SL["dir"]
            self.eta[r] = np.stack(_turn(y, o[:, d0], o[:, d0 + 1]), 1)
        self.zmap[r] = zm
        self.valid[r] = True
        self.age[r] = 0.0

    def answer_rows(self, a=0, b=None):
        """(v0.4.2a, BRAIN_READ) the answer of seats a..b for the simulator's readers (duel_env.brain_in): see answer_of"""
        return answer_of(self, slice(a, b))

    def reset(self, d):
        """after a frame: d [n] (1 where his memory and the brain's are cleared): no answer until the next tick"""
        m = np.asarray(d) > 0.5
        self.valid[m] = False
        self.age[m] = 0.0

    def features(self, pose, zmap):
        """the token of this frame for every seat [n, F] float16: the answer turned to his pose now (call after see(), before
        this frame's tick); the answer's age counts on"""
        F = np.zeros((self.n, len(self.f)), np.float32)
        ix = self.ix
        y = pose[:, 3]
        v = self.valid
        if "pos_f" in ix:
            f_, l_ = _unturn(y, self.P[:, 0] - pose[:, 0], self.P[:, 1] - pose[:, 1])
            F[:, ix["pos_f"]] = f_ / 1000.0
            F[:, ix["pos_l"]] = l_ / 1000.0
            F[:, ix["pos_u"]] = (self.P[:, 2] - pose[:, 2]) / 1000.0
            F[:, ix["pos_dist"]] = np.hypot(f_, l_) / 1000.0
            F[:, ix["pos_ls_xy"]] = self.ls[:, 0]
            F[:, ix["pos_ls_z"]] = self.ls[:, 1]
        if "vel_f" in ix:
            f_, l_ = _unturn(y, self.V[:, 0], self.V[:, 1])
            F[:, ix["vel_f"]] = f_ / 1000.0
            F[:, ix["vel_l"]] = l_ / 1000.0
            F[:, ix["vel_ls"]] = self.lsv
        for nm, src in (("band_0", self.band), ("hand_0", self.hand), ("own_rl", self.own), ("zone_0", self.zone)):
            if nm in ix:
                F[:, ix[nm]:ix[nm] + src.shape[1]] = src
        if "ztop0_f" in ix:
            ct, _ = zone_table()
            zm = np.clip(np.where(self.zmap >= 0, self.zmap, 0), 0, len(ct) - 1)
            top = np.argsort(-self.zone, 1, kind="stable")[:, :TOPZ]
            for k in range(TOPZ):
                c = ct[zm, top[:, k]].astype(np.float64)                      # [n, 3]
                f_, l_ = _unturn(y, c[:, 0] - pose[:, 0], c[:, 1] - pose[:, 1])
                j = ix["ztop{}_f".format(k)]
                p_ = self.zone[np.arange(self.n), top[:, k]]
                ok = (p_ > 0) & (self.zmap >= 0)
                F[:, j] = np.where(ok, f_ / 1000.0, 0.0)
                F[:, j + 1] = np.where(ok, l_ / 1000.0, 0.0)
                F[:, j + 2] = np.where(ok, (c[:, 2] - pose[:, 2]) / 1000.0, 0.0)
                F[:, j + 3] = np.where(ok, p_, 0.0)
        if "spd" in ix:
            F[:, ix["spd"]] = self.spd[:, 0]
            F[:, ix["spd_ls"]] = self.spd[:, 1]
        if "dir_c" in ix:
            f_, l_ = _unturn(y, self.eta[:, 0], self.eta[:, 1])
            k_ = np.hypot(f_, l_)
            sc = 1.0 / (1.0 + k_)                                             # (cos, sin) k / (1 + k) = eta / (1 + k)
            F[:, ix["dir_c"]] = f_ * sc
            F[:, ix["dir_s"]] = l_ * sc
            F[:, ix["dir_k"]] = np.log1p(k_) / 5.0
        F[~v] = 0.0
        F[:, ix["unseen"]] = np.log1p(self.unseen) / math.log1p(UNSEEN_CAP)
        F[:, ix["age"]] = np.where(v, self.age / self.K, 0.0)
        F[:, ix["valid"]] = v
        self.age = np.where(v, self.age + 1.0, 0.0).astype(np.float32)
        return np.clip(F, -60000.0, 60000.0).astype(np.float16)


def answer_of(tk, rows=slice(None)):
    """(v0.4.2a) the brain's answer as the simulator's readers take it (duel_env.brain_in), for these rows of a Token: the
    believed place in map coordinates [m, 3] float32, that there is an answer [m] bool, the stack band's odds [m, 4]
    float32 (under 75, 75-124, 125-200, over 200), the likeliest zone's number [m] int16 (-1: no zones)"""
    z = tk.zone[rows]
    zt = np.where(z.sum(1) > 0, z.argmax(1), -1).astype(np.int16)
    return dict(bel=tk.P[rows].astype(np.float32), ok=tk.valid[rows].copy(), band=tk.band[rows].astype(np.float32), ztop=zt)


def numpy_brain(sd, bel_L, trk_L, trz_L):
    """(the checks) the brain and its readouts in numpy from a state dict of numpy arrays -> a dict of the weights"""
    g = lambda k: np.asarray(sd[k], np.float32)
    B = dict(inp_w=g("belief.inp.weight"), inp_b=g("belief.inp.bias"), wih=g("belief.gru.weight_ih"), whh=g("belief.gru.weight_hh"),
             bih=g("belief.gru.bias_ih"), bhh=g("belief.gru.bias_hh"), H=int(bel_L["hid"]), K=int(bel_L["every"]))
    if trk_L is not None and "track.0.weight" in sd:
        B["trk"] = tuple(g("track.{}.{}".format(i, w)) for i in (0, 2) for w in ("weight", "bias"))
    if trz_L is not None and "trackz.0.weight" in sd:
        B["trz"] = tuple(g("trackz.{}.{}".format(i, w)) for i in (0, 2) for w in ("weight", "bias"))
    return B


def np_mlp(P, s):
    w0, b0, w1, b1 = P
    return np.maximum(s @ w0.T + b0, 0.0) @ w1.T + b1


def np_gru(B, x, h):
    H = B["H"]
    gi = x @ B["wih"].T + B["bih"]
    gh = h @ B["whh"].T + B["bhh"]
    r = 1.0 / (1.0 + np.exp(-(gi[:, :H] + gh[:, :H])))
    z = 1.0 / (1.0 + np.exp(-(gi[:, H:2 * H] + gh[:, H:2 * H])))
    n = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
    return ((1 - z) * n + z * h).astype(np.float32)


class NpBrain:
    """(the checks) the brain stepped in numpy as the trainer's belief.State: frame() every frame on the normalised inputs
    (rounded to half precision where the trainer stores them so), a tick every K frames of its own clock"""
    FLOOR = -2.0

    def __init__(self, B, n, half=True):
        self.B, self.n, self.half = B, n, half
        H = B["H"]
        self.s = np.zeros((n, H), np.float32)
        self.sum = np.zeros((n, H), np.float32)
        self.mx = np.full((n, H), self.FLOOR, np.float32)
        self.cnt = np.zeros(n, np.float32)
        self.gv = np.zeros(n, np.int64)              # each seat's frames (its tick every K of them)

    def frame(self, x):
        """-> [n] bool: the seats that ticked on this frame"""
        if self.half:
            x = np.asarray(x, np.float32).astype(np.float16).astype(np.float32)
        u = np.tanh(x @ self.B["inp_w"].T + self.B["inp_b"])
        self.sum = self.sum + u
        self.mx = np.maximum(self.mx, u)
        self.cnt = self.cnt + 1.0
        self.gv = self.gv + 1
        tk = self.gv % self.B["K"] == 0
        if tk.any():
            s2 = np_gru(self.B, np.concatenate([self.sum[tk] / self.cnt[tk, None], self.mx[tk]], 1).astype(np.float32), self.s[tk])
            self.s = self.s.copy()
            self.s[tk] = s2
            self.sum[tk] = 0.0
            self.mx[tk] = self.FLOOR
            self.cnt[tk] = 0.0
        return tk

    def reset(self, d):
        m = np.asarray(d) > 0.5
        self.s[m] = 0.0
        self.sum[m] = 0.0
        self.cnt[m] = 0.0
        self.mx[m] = self.FLOOR

    def readouts(self, rows=None):
        s = self.s if rows is None else self.s[rows]
        o1 = np_mlp(self.B["trk"], s) if "trk" in self.B else None
        o2 = np_mlp(self.B["trz"], s) if "trz" in self.B else None
        return o1, o2


def gate_step(g, mins, last_mins, start, delay, open_min, cap):
    """the gate's schedule, one step between two rollouts: shut until start + delay; then rising by (minutes passed) / open_min
    (open_min 0: held where it is), never above cap (cap 0: shut at once)"""
    if mins >= start + delay and open_min > 0 and last_mins is not None:
        g = g + max(0.0, mins - max(last_mins, start + delay)) / open_min
    return float(min(max(g, 0.0), cap, 1.0))


# ---- (the checks) the brain's and the token's state packed into a seat's memory array: each seat carries its own, so a
# network that plays both sides of a check (one Policy object) keeps two separate states, and clearing a seat clears its own.
# Layout: [s H | sum H | max - FLOOR H | count 1 | frames 1 | the token's TOKW]; zeros are the start state (no answer, the
# time unseen at its cap, the max at its floor)
TOK_F = (("valid", 1), ("age", 1), ("unseen_left", 1), ("P", 3), ("ls", 2), ("V", 2), ("lsv", 1), ("band", 4), ("hand", 9),
         ("own", 6), ("zone", Z_MAX), ("zmap1", 1), ("spd", 2), ("eta", 2))
TOKW = sum(w for _, w in TOK_F)


def packed_width(H):
    return 3 * int(H) + 2 + TOKW


def unpack(B, L, arr):
    """a packed state [n, packed_width] -> (NpBrain, Token) over those rows"""
    H = B["H"]
    n = len(arr)
    br = NpBrain(B, n)
    br.s = arr[:, :H].astype(np.float32).copy()
    br.sum = arr[:, H:2 * H].astype(np.float32).copy()
    br.mx = (arr[:, 2 * H:3 * H] + NpBrain.FLOOR).astype(np.float32)
    br.cnt = arr[:, 3 * H].astype(np.float32).copy()
    br.gv = arr[:, 3 * H + 1].astype(np.int64)
    tk = Token(n, L)
    o = 3 * H + 2
    for k, w in TOK_F:
        v = arr[:, o:o + w]
        if k == "valid":
            tk.valid = v[:, 0] > 0.5
        elif k == "unseen_left":
            tk.unseen = (UNSEEN_CAP - v[:, 0]).astype(np.float32)
        elif k == "zmap1":
            tk.zmap = np.round(v[:, 0]).astype(np.int64) - 1
        elif k == "age":
            tk.age = v[:, 0].astype(np.float32).copy()
        elif k == "lsv":
            tk.lsv = v[:, 0].astype(np.float32).copy()
        else:
            setattr(tk, k, v.astype(getattr(tk, k).dtype).copy())
        o += w
    return br, tk


def pack(br, tk):
    H = br.B["H"]
    cols = [br.s, br.sum, br.mx - NpBrain.FLOOR, br.cnt[:, None], br.gv[:, None].astype(np.float32)]
    for k, w in TOK_F:
        if k == "valid":
            v = tk.valid[:, None]
        elif k == "unseen_left":
            v = (UNSEEN_CAP - tk.unseen)[:, None]
        elif k == "zmap1":
            v = (tk.zmap + 1)[:, None]
        elif k in ("age", "lsv"):
            v = getattr(tk, k)[:, None]
        else:
            v = getattr(tk, k)
        cols.append(np.asarray(v, np.float64).reshape(len(v), w))
    out = np.concatenate([np.asarray(c, np.float64) for c in cols], 1)
    assert out.shape[1] == 3 * H + 2 + TOKW
    return out


def packed_clear(arr, rows, H):
    """a seat's brain and answer cleared (the trainer's reset), in place: the state, the frames gathered, no answer; the time
    since he noticed the enemy and the tick clock kept"""
    r = slice(None) if rows is None else rows
    arr[r, :3 * H + 1] = 0.0
    o = 3 * H + 2
    arr[r, o] = 0.0                                   # valid
    arr[r, o + 1] = 0.0                               # age
