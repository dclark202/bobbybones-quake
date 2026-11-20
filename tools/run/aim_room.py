"""The aim room: a network plays one weapon against a scripted, fast-moving target at a set distance, frame by frame recorded in the
pros' columns, and his aim is read beside the pros' (owner, 2026-11-19: "run an experiment with the current model ... with rail in
hand in a simulator simple room against a random moving enemy (fast movement) to track his aim ... Then do the same with lg and
rockets"). Measurement only: nothing here trains, sets a target or a pass mark; the pros are a readout of human limits beside his.

    python tools/run/aim_room.py spots [--maps ...]                         the room's lines on the duel maps (once; spots.json)
    python tools/run/aim_room.py play --tag T --weapon rg --dist 300,500 --target strafe,dodger,fighter --aim base,max
                                      [--minutes 20] [--games 16] [--maps-per 3] [--jobs 18] [--policy P]
    python tools/run/aim_room.py collect --src pros|<folder> --out rows.npz  per-shot rows: pro_knobs' COLS + own speed, enemy speed, in air ...
    python tools/run/aim_room.py report --tag T [--pros data/sim_runs/space/aimroom/pros_rows.npz]
    python tools/run/aim_room.py proof --tag T                              every setting of every job against the checks' (CLAUDE.md rule 5)

THE ROOM. The ten duel maps only: the network reads each map's own tables (the order's map numbers, the map sense) and refuses a map
without them (sim/desc22.py need_om), so testlab's rooms cannot seat him. The room is a LINE of a duel map: his spot S and the target's
home T, a clear sight line between them at the set distance (+-4%), the same floor height (+-40 units), and a LANE through T across
that line (at least 160 units each way, up to 384) that is walkable (a player's box passes, a floor 24 units under every point, no
lava) and in his clear sight all along (`spots`, from the map's own way points). Every item of the map is held down (taken, its timer
running and taken again at its respawn) and dropped weapons are removed, so nothing but the fight is on offer; his loadout is
enforced every frame (the tested weapon, the machine gun, the gauntlet; anything else he picks up is taken away and counted).

A ROUND (20 to 30 s, or until either dies): both placed on a line drawn from the map's lines for the distance, 100 health and 100
armor each, he with the tested weapon in hand and his view on the target's bearing +-45 degrees (inside his field of view: the
notice delay runs as in a game; his sighting is reset, so the target is noticed anew), the target facing him. His ammunition is
refilled every frame (it never runs out); the recorded ammunition counts every shot down, so the pros' tools find each shot.
His memory is NOT reset between rounds (he plays whole games: his clock, score and memory never start over, as in the checks).

THE TARGET (the odd seat of each match):
    strafe   unarmed, never shoots; this tool's keys: runs across the line at full speed, reversing at a random time 0.3-1.2 s
             after the last reversal (the existing script's draw) or at the lane's end; holds the jump key in 20% of the stretches
             (the existing script's share); faces him; pulled back onto the lane if pushed off it (rockets).
    dodger   the same, reversing every 0.15-0.5 s (the existing script's dodger).
    fighter  the simulator's own scripted fighter (script 2), which shoots back: with the rail the "sniper" persona (holds 700 to
             1,200 units, fires the rail), with the lightning and rockets the "dodger" (300 to 600 units, rockets under 350,
             lightning under 800, the rail beyond); its own movement (it leaves the lane: its distance is its own, read per frame).
The existing script 1 (the strafing target) moves relative to a facing that wanders toward open space and walks forward and back:
on a duel map it leaves the line; so the target's keys are written here (the existing hook mechanism, duel_eval BRANCH_HOOK), with
the existing script's timing.

THE NETWORK is played exactly as the checks played it (tools/duel_eval.py; the settings of the check's json, CHECK_REF; its delays,
its target lock, contact and weapon-own from its save, as tools/run/watch.py's hold_args), except the deliberate differences that
`proof` lists: OVERTIME 0 (no extra periods), the room (this hook), the aim variants (AIM below).

RECORDED (per job, data/sim_runs/space/aimroom/<tag>/<weapon>_<dist>_<target>_<aim>/rec_<map>_<seed>.npz): `lite` (the pros'
columns, tools/run/pro_aim.py's docstring; his seats, alive), `first` (a new stretch: a round's start), `extra` (EXTRA below), `meta`.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = r"C:\Users\dacla\anaconda3\python.exe"
OUT = os.path.join(ROOT, "data", "sim_runs", "space", "aimroom")
SPOTS = os.path.join(OUT, "spots.json")
POLICY = os.path.join(ROOT, "data", "sim_runs", "duel_gru_2_2d", "keep", "control_22a90.pt")     # = duel_gru_2_2a/keep/policy_90.pt (same bytes)
CHECK_REF = os.path.join(ROOT, "data", "sim_runs", "duel_gru_2_2d", "watch", "chk_10_prev_bloodrun.json")   # how 2.2d's checks played it
MAPS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "hektik", "toxicity", "campgrounds", "cure")
DISTS = {"rg": (300, 500, 768, 1000, 1500), "lg": (200, 400, 600, 750), "rl": (200, 400, 600, 800)}
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DT = 0.025
RL, RG, LG, MG = 0, 1, 2, 3
WNUM = {"rl": RL, "rg": RG, "lg": LG}
EXTRA = ("round", "d0", "he_ground", "dealt", "tg_turn", "tg_ground", "fire_last", "round_frame", "tg_alive", "lane_x", "pattern")
PATTERNS = {"strafe": (0.3, 1.2), "dodger": (0.15, 0.5), "fighter": None}
LEFT_F = 40                                                          # a round ends when the target has been out of his view this many frames
FIGHTER_PERSONA = {"rg": 1, "lg": 4, "rl": 4}                       # sim/duel_env.py PERSONAS: 1 sniper, 4 dodger


# ------------------------------------------------------------------------------------------------------------- the aim variants
def aim_variants():
    """name -> (react_ms, acquire_ms, {SEAT_AIM name: value} for his seats, {other name: value} for the process). base = the checks'
    (none of these). max / better: tools/aim2_levels.py --aim3's columns; the halves: the brief's lists, from the checks' values."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import aim2_levels as AL
    ref = json.load(open(CHECK_REF))["set"]
    f_ = lambda k, x: "{:g}".format(float(ref[k]) * x)
    eye = {k: f_(k, 0.5) for k in ("PERCEPT_SIGMA", "AIM2_C_SLIP", "AIM2_CAP_SLIP", "AIM2_C_ECC", "AIM2_CAP_ECC", "FLINCH_PER_DMG", "FLINCH_MAX")}
    hand = {k: f_(k, 0.5) for k in ("MOTOR_NOISE", "MOTOR_BASE")}
    out = {"base": (125, 225, {}), "eye_half": (125, 225, eye), "hand_half": (125, 225, hand), "both_half": (125, 225, dict(eye, **hand)),
           "smooth_half": (125, 225, {"AIM2_SMOOTH_K": "0.5"})}
    for nm in ("max", "better"):
        rm, am, ev = AL.TABLE3[nm]
        ev = dict(AL.COMMON, **ev)
        out[nm] = (rm, am, {k: v for k, v in ev.items() if ref.get(k) != v})     # (only what differs from the checks')
    # (coordinator, 2026-11-19: the age of the picture) the tracking delay and the velocity read's delay alone, from base and from better.
    # The delays move in whole frames of 25 ms (tools/../sim/test_suite.py set_delays rounds react_ms / 25); VEL_DELAY_MS likewise
    # (duel_env: vel_frames = round(VEL_DELAY_MS / 25)). Both are the process's / his seats' for every weapon.
    for nm, rm, vd in (("delay100", 100, "175"), ("delay75", 75, "100"), ("delay50", 50, "75"), ("delay25", 25, "25")):
        out[nm] = (rm, 225, {"VEL_DELAY_MS": vd})
    b_rm, b_am, b_v = out["better"]
    for nm, rm, vd in (("better75", 75, "100"), ("better50", 50, "75")):
        out[nm] = (rm, b_am, dict(b_v, VEL_DELAY_MS=vd))
    return out


def split_aim(vals, seat_names):
    he = {k: v for k, v in vals.items() if k in seat_names}
    proc = {k: v for k, v in vals.items() if k not in seat_names}
    return he, proc


# ------------------------------------------------------------------------------------------------------------- the simulator
def make_env(mp, n=1, seed=1):
    os.environ.update(json.load(open(CHECK_REF))["set"])
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import duel_env_ffa as E
    nav = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    return E, E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=n, seed=seed, loadout="all", nav=nav)


def spots(a):
    """the room's lines on each map (see the docstring): {map: {distance: [[Sx,Sy,Sz, Tx,Ty,Tz, ux,uy, lane-, lane+], ...]}}"""
    if os.path.exists(a.out) and not a.force:
        raise SystemExit(a.out + " is there (--force to make it again)")
    dists = [int(x) for x in a.dists.split(",")] if a.dists else sorted({d for v in DISTS.values() for d in v})
    lane_at = {int(k): float(v) for k, v in (x.split(":") for x in a.lane_at.split(",") if x)}
    res = {}
    rng = np.random.default_rng(5)
    for mp in a.maps.split(","):
        E, env = make_env(mp)
        W, sight = env.w, env.sight
        N = np.asarray(env.route.nodes, np.float32)
        fl = np.array([W.trace(p, p - np.array([0, 0, 64], np.float32))["fraction"] * 64 for p in N])
        N = N[np.abs(fl - 24.0) < 2.0]                       # way points standing on a floor
        cont = W.contents_n(N + np.array([0, 0, -23.0], np.float32))
        N = N[(np.asarray(cont) & (E.C_LAVA | E.C_SLIME | E.C_WATER)) == 0]
        H = np.hypot(N[:, None, 0] - N[None, :, 0], N[:, None, 1] - N[None, :, 1])
        DZ = np.abs(N[:, None, 2] - N[None, :, 2])
        res[mp] = {}
        for d in dists:
            ii, jj = np.nonzero((np.abs(H - d) < 0.04 * d) & (DZ < 40))
            if len(ii) > 8000:
                q = rng.choice(len(ii), 8000, replace=False)
                ii, jj = ii[q], jj[q]
            eye = N[ii] + np.array([0, 0, E.VIEW_H], np.float32)
            ok = (W.lines(eye, N[jj] + np.array([0, 0, 4.0], np.float32), mask=sight) >= 0.999) & \
                 (W.lines(eye, N[jj] + np.array([0, 0, 28.0], np.float32), mask=sight) >= 0.999)
            ii, jj = ii[ok], jj[ok]
            if len(ii) > 2500:
                q = rng.choice(len(ii), 2500, replace=False)
                ii, jj = ii[q], jj[q]
            cand = []
            for i, j in zip(ii, jj):
                S, T = N[i], N[j]
                v = (S - T)[:2] / max(1e-3, float(np.hypot(*(S - T)[:2])))
                u = np.array([-v[1], v[0]], np.float32)
                ext = []
                for sg in (-1.0, 1.0):
                    far = T + np.array([sg * u[0] * 384, sg * u[1] * 384, 0], np.float32)
                    tr = W.trace(T + np.array([0, 0, 2.0], np.float32), far + np.array([0, 0, 2.0], np.float32), E.MINS, E.MAXS)
                    if tr["startsolid"]:
                        ext.append(0.0)
                        continue
                    clear = tr["fraction"] * 384 - 16
                    xs = np.arange(32, 385, 32, dtype=np.float32)
                    P = T[None, :] + np.stack([sg * u[0] * xs, sg * u[1] * xs, np.zeros_like(xs)], 1)
                    down = W.lines(P, P - np.array([0, 0, 64], np.float32)) * 64
                    see = (W.lines(np.repeat(S[None] + np.array([0, 0, E.VIEW_H], np.float32), len(P), 0), P + np.array([0, 0, 4.0], np.float32),
                                   mask=sight) >= 0.999)
                    liq = (np.asarray(W.contents_n(P + np.array([0, 0, -23.0], np.float32))) & (E.C_LAVA | E.C_SLIME)) != 0
                    good = (xs <= clear) & (np.abs(down - 24.0) < 6.0) & see & ~liq
                    bad = np.nonzero(~good)[0]
                    ext.append(float(xs[bad[0] - 1]) if len(bad) and bad[0] > 0 else (0.0 if len(bad) else float(xs[-1])))
                if min(ext) >= lane_at.get(d, a.lane):
                    cand.append((min(ext), [float(x) for x in S] + [float(x) for x in T] + [float(u[0]), float(u[1]), ext[0], ext[1]]))
            cand.sort(key=lambda c: -c[0])
            keep = []
            for _, c in cand:
                if all(np.hypot(c[3] - k[3], c[4] - k[4]) > 96 or np.hypot(c[0] - k[0], c[1] - k[1]) > 96 for k in keep):
                    keep.append(c)
                if len(keep) >= 12:
                    break
            res[mp][str(d)] = keep
            print("{:15s} {:5d} units: {:5d} pairs in sight, {:4d} with a lane, kept {:2d} (lanes {})".format(
                mp, d, len(ii), len(cand), len(keep), [int(min(k[8], k[9])) for k in keep]), flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(res, open(a.out, "w"), indent=0)
    print("->", a.out)


# ------------------------------------------------------------------------------------------------------------- the hook
class Hook:
    """tools/duel_eval.py's BRANCH_HOOK: the room. Configured by the environment variable AROOM (json: weapon, dist, target, out)."""

    def __init__(self, E, env, mp, seed, ev, od):
        cfg = json.loads(os.environ["AROOM"])
        self.E, self.env, self.mp, self.cfg = E, env, mp, cfg
        self.rng = np.random.default_rng(int(seed) * 7919 + 13)
        self.he, self.tg = np.asarray(ev), np.asarray(od)
        self.M = len(self.he)
        self.W = WNUM[cfg["weapon"]]
        self.d0 = float(cfg["dist"])
        self.lines = np.array(json.load(open(cfg.get("spots") or SPOTS))[mp][str(cfg["dist"])], np.float64)
        assert len(self.lines), "no line on {} at {} units".format(mp, cfg["dist"])
        self.kind = cfg["target"]
        self.pat = PATTERNS[self.kind]
        self.fighter = self.pat is None
        env.script[self.tg] = 2 if self.fighter else 0
        if self.fighter:
            env.sc_persona[self.tg] = FIGHTER_PERSONA[cfg["weapon"]]
        self.zt, self.zp = int(np.abs(E.TURN).argmin()), int(np.abs(E.PITCH).argmin())
        M = self.M
        self.home = np.zeros((M, 3))
        self.u = np.zeros((M, 2))
        self.v = np.zeros((M, 2))                            # the line's own direction, from the target's home toward his spot
        self.oov = np.zeros(M, np.int64)                     # frames the target has been out of his view
        self.lane = np.zeros((M, 2))
        self.sdir = np.ones(M)
        self.tmr = np.zeros(M)
        self.jump = np.zeros(M, bool)
        self.rend = np.zeros(M, np.int64)
        self.rid = np.zeros(M, np.int64)
        self.rf = np.zeros(M, np.int64)
        self.first_next = np.ones(M, bool)
        self.turned = np.zeros(M)
        self.t = 0
        self.rows, self.first, self.extra = [], [], []
        self.cum = np.zeros(M)
        self.meta = dict(rounds=0, he_deaths=0, tg_deaths=0, stripped=0, timeouts=0, left=0, rev_random=0, rev_lane=0, pulled=0, frames=0)
        self.big = np.array([w for w in (RL, RG, LG) if w != self.W] + [4, 5, 6, 7])    # (sg, gl, pg, hmg)
        self.amax = np.asarray(E.AMMO_MAX, np.float32)
        for m in range(M):
            self._round(m)
        self.prev_ammo = env.ammo.copy()
        self.dl0 = np.asarray(env.dmg_life, np.float64)[self.he].copy()
        self._items()

    # --- a round
    def _round(self, m):
        E, env, rng = self.E, self.env, self.rng
        h, g = int(self.he[m]), int(self.tg[m])
        L = self.lines[int(rng.integers(len(self.lines)))]
        S, T = L[0:3], L[3:6]
        self.home[m], self.u[m], self.lane[m] = T, L[6:8], L[8:10]
        self.v[m] = (S - T)[:2] / max(1e-3, float(np.hypot(*(S - T)[:2])))
        by = float(np.degrees(np.arctan2(T[1] - S[1], T[0] - S[0])))
        yh = by + float(rng.uniform(-45.0, 45.0))
        yt = by + 180.0
        env.w.reset(h, (S[0], S[1], S[2] + 1.0), (0, 0, 0), yh)
        env._fresh(h, yh)
        env.w.reset(g, (T[0], T[1], T[2] + 1.0), (0, 0, 0), yt)
        env._fresh(g, yt)
        env.state = env.w.state()
        for i in (h, g):
            env.hp[i], env.armor[i] = 100.0, 100.0
            env.vis_run[i], env.acquired[i], env.visible[i] = 0, False, False
            env.cool[i], env.fire_cd[i] = 0.0, 0.0
        env.has[h, :] = False
        env.has[h, [self.W, MG, E.G]] = True
        env.ammo[h, self.W], env.ammo[h, MG] = self.amax[self.W], 100.0
        env.weapon[h] = self.W
        env.has[g, :] = False
        env.has[g, [MG, E.G]] = True
        if self.fighter:
            env.has[g, [RL, RG, LG]] = True
            env.ammo[g, [RL, RG, LG]] = self.amax[[RL, RG, LG]]
            env.weapon[g] = RG if self.W == RG else LG
        else:
            env.weapon[g] = MG
        self.sdir[m] = 1.0 if rng.random() < 0.5 else -1.0
        self.tmr[m] = rng.uniform(*self.pat) if self.pat else 0.0
        self.jump[m] = rng.random() < 0.2
        self.rend[m] = self.t + int(round(rng.uniform(20.0, 30.0) / DT))
        self.rid[m] += 1
        self.rf[m] = 0
        self.oov[m] = 0
        self.first_next[m] = True
        self.meta["rounds"] += 1

    def _items(self):
        env = self.env
        env.item_up[:] = False                               # every item held down: taken again at its respawn
        due = env.item_t <= DT
        if due.any():
            resp = np.array([float(it[2]) for it in env.item_def], np.float32)
            env.item_t[:] = np.where(due, resp[None, :], env.item_t)
        env.drop_w[:] = -1
        env.drop_t[:] = 0.0

    # --- duel_eval's calls
    def top(self, t, obs, h, h2):
        pass

    def act(self, t, obs, a):
        self.t = t
        self.fire = (a[self.he, 5] == 1)
        if self.fighter:
            return
        env, rng = self.env, self.rng
        s = env.state
        P, Q = s[self.tg, :3], s[self.he, :3]
        self.tmr -= DT
        self.turned[:] = 0.0
        for m in np.nonzero(self.tmr <= 0)[0]:              # the existing script's draw: a new stretch every 0.3-1.2 s (dodger 0.15-0.5)
            self.sdir[m] = -self.sdir[m]
            self.tmr[m] = rng.uniform(*self.pat)
            self.jump[m] = rng.random() < 0.2
            self.turned[m] = 1.0
            self.meta["rev_random"] += 1
        off = P[:, :2] - self.home[:, :2]
        x = (off * self.u).sum(1)
        for m in range(self.M):                              # the lane's end: back the other way
            if (x[m] > self.lane[m, 1] and self.sdir[m] > 0) or (x[m] < -self.lane[m, 0] and self.sdir[m] < 0):
                self.sdir[m] = -self.sdir[m]
                self.tmr[m] = rng.uniform(*self.pat)
                self.turned[m] = 2.0
                self.meta["rev_lane"] += 1
        self.lane_x = x
        yw = np.degrees(np.arctan2(Q[:, 1] - P[:, 1], Q[:, 0] - P[:, 0]))
        env.yaw[self.tg] = yw                                # facing him (the turn key at nothing; his view's inertia cleared)
        env.mv[self.tg] = 0.0
        yr = np.radians(yw)
        fwdv = np.stack([np.cos(yr), np.sin(yr)], 1)
        left = np.stack([-np.sin(yr), np.cos(yr)], 1)
        want = self.sdir[:, None] * self.u                   # along the lane, whatever his place: the keys of the nearest of the eight directions
        along = (off * self.v).sum(1)                        # (+: off the lane toward his spot)
        want = want - np.clip(along / 96.0, -1.0, 1.0)[:, None] * self.v * (np.abs(along) > 32.0)[:, None]   # (pulled back onto the lane)
        f_, l_ = (want * fwdv).sum(1), (want * left).sum(1)
        nrm = np.maximum(np.hypot(f_, l_), 1e-6)
        f_, l_ = f_ / nrm, l_ / nrm
        fwd = np.where(f_ > 0.38, 2, np.where(f_ < -0.38, 0, 1))
        side = np.where(l_ > 0.38, 0, np.where(l_ < -0.38, 2, 1))
        self.meta["pulled"] += int((np.abs(along) > 32.0).sum())
        a[self.tg, :] = 0
        a[self.tg, 0], a[self.tg, 1], a[self.tg, 2] = fwd, side, self.jump.astype(np.int64)
        a[self.tg, 3], a[self.tg, 4] = self.zt, self.zp

    def after(self, t, r, info):
        E, env = self.E, self.env
        s, i, o = env.state, self.he, self.tg
        dl = np.asarray(env.dmg_life, np.float64)[i]
        dealt = np.maximum(dl - self.dl0, 0.0)
        fired = np.maximum(self.prev_ammo[i, self.W] - env.ammo[i, self.W], 0.0)
        self.cum += fired
        alive = env.hp[i] > 0
        am = env.ammo[i].astype(np.float64).copy()
        am[:, self.W] = 100000.0 - self.cum                  # every shot counts down (the ammunition itself is refilled below)
        row = np.concatenate([env.hp[i, None], env.armor[i, None], env.weapon[i, None], self.fire[:, None], env.visible[i, None], s[i, :3], s[o, :3],
                              s[o, 3:6], env.yaw[i, None], env.pitch[i, None], (env.hp[o] > 0)[:, None], np.zeros((self.M, 1)), i[:, None], am,
                              env.cool[i, None] * 1000.0, env.duck[i, None], s[i, 3:6]], 1)
        self.hitc = getattr(self, "hitc", np.zeros(self.M)) + (dealt > 0.5)
        row[:, 17] = self.hitc
        ex = np.stack([self.rid, np.full(self.M, self.d0), s[i, 6], dealt, self.turned if not self.fighter else np.zeros(self.M), s[o, 6],
                       env.fire_last[i], self.rf, (env.hp[o] > 0), getattr(self, "lane_x", np.zeros(self.M)),
                       np.full(self.M, list(PATTERNS).index(self.kind))], 1)
        keep = alive
        if keep.any():
            self.rows.append(row[keep].astype(np.float32))
            self.extra.append(ex[keep].astype(np.float32))
            self.first.append(self.first_next[keep].copy())
            self.first_next[keep] = False
        self.meta["frames"] += int(keep.sum())
        self.rf += 1
        self.oov = np.where(env.visible[i], 0, self.oov + 1)
        died = np.zeros(env.n, bool)
        for e in info.get("events", ()):
            died[int(e["victim"])] = True
        new = np.zeros(self.M, bool)
        for m in range(self.M):
            if died[i[m]] or died[o[m]] or env.hp[i[m]] <= 0 or env.hp[o[m]] <= 0:
                self.meta["he_deaths"] += int(died[i[m]])
                self.meta["tg_deaths"] += int(died[o[m]])
                new[m] = True
            elif self.oov[m] >= LEFT_F and self.rf[m] >= 20:
                self.meta["left"] += 1                       # he has left the fight: the target out of his view for a second
                new[m] = True
            elif t + 1 >= self.rend[m]:
                self.meta["timeouts"] += 1
                new[m] = True
        for m in np.nonzero(new)[0]:
            self._round(int(m))
        extra_w = env.has[i][:, self.big].any(1)             # his loadout: only the tested weapon (and the machine gun, the gauntlet)
        if extra_w.any():
            self.meta["stripped"] += int(extra_w.sum())
            for m in np.nonzero(extra_w)[0]:
                env.has[i[m], self.big] = False
                if not env.has[i[m], env.weapon[i[m]]]:
                    env.weapon[i[m]] = self.W
        env.ammo[i, self.W] = self.amax[self.W]
        env.ammo[i, MG] = 100.0
        if self.fighter:
            env.ammo[o[:, None], np.array([RL, RG, LG])[None, :]] = self.amax[[RL, RG, LG]][None, :]
        self._items()
        self.prev_ammo = env.ammo.copy()
        self.dl0 = np.asarray(env.dmg_life, np.float64)[i].copy()

    def end(self):
        lite = np.concatenate(self.rows) if self.rows else np.zeros((0, 33), np.float32)
        first = np.concatenate(self.first) if self.first else np.zeros(0, bool)
        extra = np.concatenate(self.extra) if self.extra else np.zeros((0, len(EXTRA)), np.float32)
        o_ = np.argsort(lite[:, 18], kind="stable")          # each seat's frames together, in time order (as the pros' files and aim_rec_hook)
        lite, first, extra = lite[o_], first[o_], extra[o_]
        np.savez_compressed(self.cfg["out"], lite=lite, first=first, extra=extra,
                            extra_cols=np.array(EXTRA), meta=np.array(json.dumps(dict(self.meta, map=self.mp, **self.cfg))))


# ------------------------------------------------------------------------------------------------------------- play
def hold_args(pol):
    """his own target lock, contact and weapon-own from his save, as tools/run/watch.py hold_args (his side's flags)"""
    import torch
    ev_ = torch.load(pol, map_location="cpu", weights_only=False).get("env_vars") or {}
    out = []
    if ev_.get("INTENT_HOLD") not in (None, ""):
        out += ["--hold", str(ev_["INTENT_HOLD"])]
    out += ["--contact", str(ev_.get("CONTACT_FREE") or 0)]
    out += ["--wown", "1" if str(ev_.get("WEAPON_OWN") or "0") not in ("0", "", "0.0") else "0"]
    return out


def job_cmd(a, weapon, dist, target, aim, mp, seed, out, AV, seat_names, hold):
    ref = json.load(open(CHECK_REF))
    rm, am, vals = AV[aim]
    he_aim, proc = split_aim(vals, seat_names)
    sets = dict(ref["set"])
    for k in ("SEAT_HOLD_HE", "SEAT_HOLD_OPP", "SEAT_CONTACT_HE", "SEAT_CONTACT_OPP", "SEAT_WOWN_HE", "SEAT_WOWN_OPP"):
        sets.pop(k, None)                                    # (made again from his save by --hold, --contact, --wown)
    sets["OVERTIME"] = "0"
    sets.update(proc)
    cmd = [PY, "tools/duel_eval.py", "--run", "aimroom", "--policy", a.policy, "--opp", "runner", "--inputs", os.path.join(ROOT, "docs", "INPUTS.csv"),
           "--map", mp, "--games", str(a.games), "--minutes", str(a.minutes), "--procs", "1", "--seed", str(seed),
           "--json", out + ".eval.json", "--react-ms", str(rm), "--acquire-ms", str(am), "--round", "600", "--opp-round", "600"]
    cmd += [x for k, v in sets.items() for x in ("--set", "{}={}".format(k, v))]
    cmd += hold
    if he_aim:
        cmd += ["--aim-he", ",".join("{}={}".format(k, v) for k, v in he_aim.items())]
    cfg = dict(weapon=weapon, dist=int(dist), target=target, aim=aim, out=out)
    return cmd, cfg


def play(a):
    sp = json.load(open(SPOTS))
    AV = aim_variants()
    E_, env_ = make_env("bloodrun")
    seat_names = set(env_.SEAT_AIM)
    hold = hold_args(a.policy)
    tag_dir = os.path.join(OUT, a.tag)
    if os.path.exists(tag_dir) and not a.add:
        raise SystemExit(tag_dir + " is there: another --tag (nothing is overwritten)")
    os.makedirs(tag_dir, exist_ok=True)
    queue = []
    seed = a.seed
    for weapon in a.weapon.split(","):
        dists = DISTS[weapon] if a.dist == "all" else [int(x) for x in a.dist.split(",")]
        for dist in dists:
            maps = [mp for mp in MAPS if len(sp.get(mp, {}).get(str(dist), []))]
            maps.sort(key=lambda mp: -sum(min(k[8], k[9]) for k in sp[mp][str(dist)]))
            maps = [mp for mp in a.maps.split(",") if mp in maps] if a.maps else maps[:a.maps_per]
            for target in a.target.split(","):
                for aim in a.aim.split(","):
                    cond = "{}_{}_{}_{}".format(weapon, dist, target, aim)
                    cd = os.path.join(tag_dir, cond)
                    if os.path.exists(cd):
                        raise SystemExit(cd + " is there (nothing is overwritten)")
                    os.makedirs(cd)
                    for mp in maps:
                        for r in range(a.reps):
                            seed += 101
                            out = os.path.join(cd, "rec_{}_{}.npz".format(mp, seed))
                            queue.append(job_cmd(a, weapon, dist, target, aim, mp, seed, out, AV, seat_names, hold))
    print("{} jobs ({} at once), {} matches x {} min each".format(len(queue), a.jobs, a.games, a.minutes), flush=True)
    json.dump([dict(cmd=c, cfg=g) for c, g in queue], open(os.path.join(tag_dir, "jobs_{}.json".format(int(time.time()))), "w"), indent=0)
    run, t0 = [], time.time()
    while queue or run:
        while queue and len(run) < a.jobs:
            cmd, cfg = queue.pop(0)
            env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1", PYTHONFAULTHANDLER="1",
                       BRANCH_HOOK="aim_room", AROOM=json.dumps(cfg))
            p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=open(cfg["out"] + ".log", "w"), stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, creationflags=0x4000 | NOWIN)
            run.append((cfg, p))
        time.sleep(5)
        for cfg, p in list(run):
            if p.poll() is not None:
                run.remove((cfg, p))
                print("{:6.0f} s  {}  exit {}  {}".format(time.time() - t0, os.path.relpath(cfg["out"], tag_dir), p.returncode,
                                                         "written" if os.path.exists(cfg["out"]) else "NOT WRITTEN"), flush=True)


# ------------------------------------------------------------------------------------------------------------- proof (rule 5)
def proof(a):
    """every job's settings as it ran (its duel_eval json: set, delays) against the checks' (CHECK_REF): each difference listed and
    marked deliberate (the variant's, OVERTIME) or NOT"""
    ref = json.load(open(CHECK_REF))
    AV = aim_variants()
    R = dict(ref["set"])
    he_ref = {"SEAT_HOLD": R.pop("SEAT_HOLD_OPP"), "SEAT_CONTACT": R.pop("SEAT_CONTACT_OPP"), "SEAT_WOWN": R.pop("SEAT_WOWN_OPP")}  # (the control sat as the opponent)
    for k in ("SEAT_HOLD_HE", "SEAT_CONTACT_HE", "SEAT_WOWN_HE"):
        R.pop(k)
    bad, n, seen = 0, 0, {}
    for js in sorted(glob.glob(os.path.join(OUT, a.tag, "*", "*.eval.json"))):
        d = json.load(open(js))
        cond = os.path.basename(os.path.dirname(js))
        aim = cond.split("_", 3)[3]
        rm, am, vals = AV[aim]
        S = dict(d["set"])
        mine = {"SEAT_HOLD": S.pop("SEAT_HOLD_HE", None), "SEAT_CONTACT": S.pop("SEAT_CONTACT_HE", None), "SEAT_WOWN": S.pop("SEAT_WOWN_HE", None)}
        seat_aim = dict(kv.split("=", 1) for kv in S.pop("SEAT_AIM_HE", "").split(",") if "=" in kv)
        diffs = []
        for k in sorted(set(R) | set(S)):
            if R.get(k) != S.get(k):
                ok = (k == "OVERTIME" and S.get(k) == "0") or (k in vals and str(vals[k]) == S.get(k))
                diffs.append((k, R.get(k), S.get(k), "deliberate" if ok else "NOT DELIBERATE"))
                bad += not ok
        for k, v in seat_aim.items():
            ok = k in vals and str(vals[k]) == v
            diffs.append(("his seat " + k, R.get(k), v, "deliberate" if ok else "NOT DELIBERATE"))
            bad += not ok
        for k in vals:
            if k not in seat_aim and S.get(k) != str(vals[k]):
                diffs.append((k, "variant " + str(vals[k]), S.get(k), "VARIANT NOT APPLIED"))
                bad += 1
        for k in he_ref:
            if str(he_ref[k]) != str(mine[k]):
                diffs.append(("his " + k, he_ref[k], mine[k], "NOT DELIBERATE"))
                bad += 1
        dl = d["delays_ms"]["he"]
        if [float(x) for x in dl] != [float(rm), float(am)]:
            ok = aim != "base"
            diffs.append(("delays", ref["delays_ms"]["opponent"], dl, "deliberate" if ok else "NOT DELIBERATE"))
            bad += not ok
        if (d["policy"] != a.policy and os.path.normcase(d["policy"]) != os.path.normcase(a.policy)) or d["env"] != ref["env"]:
            diffs.append(("network / module", (a.policy, ref["env"]), (d["policy"], d["env"]), "NOT DELIBERATE"))
            bad += 1
        key = json.dumps(diffs)
        seen.setdefault(key, []).append(cond)
        n += 1
    for key, conds in seen.items():
        print("{} jobs ({}): differences from the checks' settings for the control (2.2d's chk json):".format(len(conds), ", ".join(sorted(set(conds)))[:300]))
        for k, r_, s_, v in json.loads(key):
            print("    {:28s} checks {!s:>10}  here {!s:>10}  {}".format(k, r_, s_, v))
    print("{} jobs read; {} differences not deliberate".format(n, bad))
    return bad


# ------------------------------------------------------------------------------------------------------------- collect
# a row a shot (the rail: each shot with the enemy in view on the frame before; the lightning: EVERY cell so) = tools/run/pro_knobs.py's
# COLS (the error measured exactly as the pros', at the player-game's own delay tau) and then:
#   own, en      his own / the enemy's speed over the ground (units a second) on the view's frame
#   air          moving up or down faster than 30 units a second (a jump, a fall: the demos have no ground flag; the same for both)
#   onbody       frames the crosshair has been within the enemy's body (half width 15, half height 28 units) up to the view's frame
#   loaded       the rail ready (no reload left) on that frame
#   held         frames since the stretch began (his: the round's start; the pros: the life's)
#   sight        frames the enemy has been in view
#   d0, pat, dealt, ground, fire   his only (nan for the pros): the round's start distance, the target (0 strafe, 1 dodger, 2 fighter),
#                damage dealt on the frame, on the ground (the simulator's flag), the trigger after the finger limits
ROWCOLS = ("uid", "w", "d", "off", "ey", "ep", "cross", "vsp", "trav", "run", "rev", "hit", "tau", "ahead",
           "own", "en", "air", "onbody", "loaded", "held", "sight", "d0", "pat", "dealt", "ground", "fire")
# a row a rocket (any, in view or not): distance, enemy in view on the frame before, hit (pro_aim's window), the most damage on a frame in
# that window (his: 85 or more = a direct hit; a splash is 84 at most), the view below the enemy's middle (units) and ahead of him as a
# share of the full lead (pro_aim's), own and enemy speed, in air, the full lead (degrees), the view's travel in 250 ms, held, sight
RKCOLS = ("uid", "d", "vis", "hit", "dealt", "below", "lead", "own", "en", "air", "full", "trav", "held", "sight")
# a row a unit (a player-game; his: a seat of a job): frame counts for the rates
UCOLS = ("uid", "frames", "rg", "lg", "rl", "vis", "vis_rg", "vis_lg", "vis_rl", "loaded_vis", "loaded_on", "loaded_on_still",
         "shots_rg", "shots_lg", "shots_rl", "dealt", "ground", "air", "own0", "own1", "own2", "own3", "en_vis", "stretches", "tau",
         "tg_turns", "tg_frames")
C = {k: i for i, k in enumerate(ROWCOLS)}
RK = {k: i for i, k in enumerate(RKCOLS)}
UC = {k: i for i, k in enumerate(UCOLS)}
OWN_BINS = (0, 50, 200, 330, 1e9)


def unit_rows(u, uid, tau0, X, PK):
    """one unit -> (shot rows, rocket rows, the unit's counts, the first shot of each stretch)"""
    r, tau, lag, j, k = PK.one(u, uid, tau0, lg_every=1, frames=True)
    L, n, w, vis, same = u["L"], u["n"], u["w"], u["vis"], u["same"]
    own = np.hypot(L[:, 30], L[:, 31])
    en = np.hypot(L[:, 11], L[:, 12])
    air = (np.abs(L[:, 32]) > 30).astype(float)
    off, ey, ep, brg, bpt, d = PK.shifted(u, tau)
    half, hh = np.degrees(np.arctan2(15.0, d)), np.degrees(np.arctan2(28.0, d))
    onb = (np.abs(ey) <= half) & (np.abs(ep) <= hh) & vis
    run_on, held = np.zeros(n), np.zeros(n)
    run_on[0] = float(onb[0])
    for q in range(1, n):
        run_on[q] = (run_on[q - 1] + 1 if same[q] else 1.0) if onb[q] else 0.0
        held[q] = held[q - 1] + 1 if same[q] else 0.0
    loaded = (L[:, 28] <= 0) & (w == RG)
    if X is None:                                          # (the pros: d0, pat, dealt, ground, fire unknown)
        X = np.full((n, 5), np.nan)
        tg = np.zeros(n)
    else:
        tg = X[:, 5]
        X = X[:, :5]
    x = np.concatenate([np.stack([own, en, air, run_on, loaded, held, u["run"].astype(float)], 1), X], 1)
    rows = np.concatenate([r, x[j]], 1) if len(r) else np.zeros((0, len(ROWCOLS)))
    shot = u["shot"]
    soon = shot.copy()
    soon[:-1] |= shot[1:]
    cnt = [uid, n, (w == RG).sum(), (w == LG).sum(), (w == RL).sum(), vis.sum(), (vis & (w == RG)).sum(), (vis & (w == LG)).sum(),
           (vis & (w == RL)).sum(), (loaded & vis).sum(), (loaded & onb).sum(), (loaded & onb & ~soon).sum(),
           (shot & (w == RG)).sum(), (shot & (w == LG)).sum(), (shot & (w == RL)).sum(), np.nansum(X[:, 2]), np.nansum(X[:, 3]), air.sum()]
    cnt += [((own >= lo) & (own < hi)).sum() for lo, hi in zip(OWN_BINS[:-1], OWN_BINS[1:])]
    cnt += [np.median(en[vis]) if vis.any() else np.nan, u["seg"][-1] + 1, tau, (tg > 0).sum(), n]
    rk = _rockets(u, uid, x)
    # the first shot of each stretch (his: a round): the time from the stretch's first frame with the enemy in view (and from its start)
    # to the shot's aim frame, whether it hit (the rail, the lightning's first cell), the enemy in view on the aim frame, the distance
    fs = []
    starts = np.nonzero(np.r_[True, ~same[1:]])[0]
    ends = np.r_[starts[1:], n]
    hitk = {int(kk): bool(r_[C["hit"]]) for kk, r_ in zip(k, r)}
    for s0, s1 in zip(starts, ends):
        v0 = np.nonzero(vis[s0:s1])[0]
        sh = np.nonzero(shot[s0:s1] & np.isin(w[s0:s1], (RL, RG, LG)))[0]
        if not len(v0) or not len(sh):
            continue
        k0 = s0 + sh[0]
        fs.append([uid, w[k0], (k0 - 1 - (s0 + v0[0])) * 25.0, (k0 - 1 - s0) * 25.0, float(hitk.get(int(k0), np.nan)) if w[k0] != RL else np.nan,
                   float(vis[k0 - 1]), d[k0 - 1]])
    return rows, rk, np.array(cnt, np.float64), np.array(fs, np.float64).reshape(-1, 7)


def _rockets(u, uid, x):
    k = np.nonzero(u["shot"] & (u["w"] == RL))[0]
    if not len(k):
        return np.zeros((0, len(RKCOLS)))
    L = u["L"]
    fl = np.clip(np.rint(u["d"][k] / 1000.0 / DT).astype(int), 1, 100)
    h = np.zeros(len(k), bool)
    dmax = np.full(len(k), np.nan)
    for a_, kk in enumerate(k):                            # (pro_aim.measure's window: the flight time less 150 ms to plus 400 ms)
        lo, hi = kk + max(1, fl[a_] - 6), min(u["n"] - 1, kk + fl[a_] + 16)
        if lo <= hi:
            sg = u["seg"][lo:hi + 1] == u["seg"][kk]
            h[a_] = (u["dh"][lo:hi + 1] * sg).sum() > 0
            dl_ = x[lo:hi + 1, 9][sg]
            if np.isfinite(dl_).any():
                dmax[a_] = np.nanmax(dl_)
    j = np.maximum(k - 1, 0)
    below = -np.tan(np.radians(u["ep"][j])) * u["hd"][j]
    ev, to = L[j, 11:14], u["to"][j]
    side = np.stack([-to[:, 1], to[:, 0]], 1) / u["hd"][j][:, None]
    vp = (ev[:, :2] * side).sum(1)
    full = np.degrees(np.arctan2(np.abs(vp) * (u["d"][j] / 1000.0), u["hd"][j]))
    lead = np.where(full > 3.0, -u["ey"][j] * np.sign(vp) / np.maximum(full, 1e-6), np.nan)
    return np.stack([np.full(len(k), uid), u["d"][k], u["vis"][j], h, dmax, below, lead, x[j, 0], x[j, 1], x[j, 2], full,
                     np.nan_to_num(u["trav"][j], nan=-1), x[j, 5], x[j, 6]], 1)


def _units(src, maps):
    """(name, unit, X): the pros' player-games (X None), or his recordings under a folder (a unit = a seat of a job; X: d0, pat, dealt,
    ground, fire, the target's scripted turns)"""
    sys.path.insert(0, HERE)
    import pro_aim as PA
    if src == "pros":
        for nm, u in PA.load_units("pros", maps):
            yield nm, u, None
        return
    for f in sorted(glob.glob(os.path.join(src, "**", "rec_*.npz"), recursive=True)):
        if maps and not any("rec_{}_".format(mp) in os.path.basename(f) for mp in maps):
            continue
        z = np.load(f)
        L, first, Xa = z["lite"].astype(np.float64), z["first"], z["extra"].astype(np.float64)
        cols = list(z["extra_cols"])
        for c in np.unique(L[:, 18]):
            m = L[:, 18] == c
            if m.sum() < 400:
                continue
            fi = first[m].copy()
            fi[0] = True
            fi[1:] |= np.diff(np.nonzero(m)[0]) > 1
            Xm = Xa[m]
            X = np.stack([Xm[:, cols.index(k_)] for k_ in ("d0", "pattern", "dealt", "he_ground", "fire_last", "tg_turn")], 1)
            yield os.path.basename(f), PA.unit(L[m], fi), X


def collect_rows(src, maps, tau0):
    sys.path.insert(0, HERE)
    import pro_knobs as PK
    R, RKs, U, F = [], [], [], []
    for uid, (nm, u, X) in enumerate(_units(src, maps)):
        r, rk, cnt, fs = unit_rows(u, uid, tau0, X, PK)
        R.append(r)
        RKs.append(rk)
        U.append(cnt)
        F.append(fs)
        if uid and uid % 500 == 0:
            print(uid, flush=True)
    cat = lambda xs, w_: np.concatenate(xs) if xs else np.zeros((0, w_))
    return cat(R, len(ROWCOLS)), cat(RKs, len(RKCOLS)), np.array(U).reshape(-1, len(UCOLS)), cat(F, 7)


def collect(a):
    if os.path.exists(a.out):
        raise SystemExit(a.out + " is there (nothing is overwritten)")
    R, RKs, U, F = collect_rows(a.src, a.maps.split(","), a.tau0)
    np.savez_compressed(a.out, rows=R.astype(np.float32), rockets=RKs.astype(np.float32), units=U, first=F, cols=np.array(ROWCOLS),
                        rkcols=np.array(RKCOLS), ucols=np.array(UCOLS))
    print("{}: {} units, {} rows, {} rockets -> {}".format(a.src, len(U), len(R), len(RKs), a.out))


# ------------------------------------------------------------------------------------------------------------- report
WMAX = {RG: (40.0, 80.0 / 1.5), LG: (1200.0, 120.0), RL: (75.0, 100.0 / 0.8)}   # the fastest shots a minute (lightning: cells), damage a second
TRAV_BINS = ((0, 3), (3, 8), (8, 15), (15, 30), (30, 181))
REV_BINS = ((0, 3), (3, 6), (6, 12), (12, 401))           # frames of 25 ms since the enemy's crossing changed side: 0-75, 75-150, 150-300, 300+ ms
EN_BINS = ((0, 50), (50, 200), (200, 330), (330, 1e9))


def _med(x):
    x = np.asarray(x, np.float64)
    x = x[np.isfinite(x)]
    return float(np.median(x)) if len(x) else float("nan")


def err_line(R, m):
    """the aim error of the rows in m: n, |left-right| degrees and half bodies, |up-down| degrees and half bodies, hit share"""
    r = R[m]
    if not len(r):
        return dict(n=0)
    half = np.degrees(np.arctan2(15.0, r[:, C["d"]]))
    return dict(n=int(len(r)), ey=_med(np.abs(r[:, C["ey"]])), ey_hb=_med(np.abs(r[:, C["ey"]]) / half), ep=_med(np.abs(r[:, C["ep"]])),
                ep_hb=_med(np.abs(r[:, C["ep"]]) / half), hit=float(np.mean(r[:, C["hit"]] > 0)), d=_med(r[:, C["d"]]))


def splits(R, m):
    """the error and hits by the brief's conditions"""
    out = {}
    tr = R[:, C["trav"]]
    for lo, hi in TRAV_BINS:
        out["travel {}-{} deg".format(lo, hi)] = err_line(R, m & (tr >= lo) & (tr < hi))
    own = R[:, C["own"]]
    for lo, hi in zip(OWN_BINS[:-1], OWN_BINS[1:]):
        out["own speed {}-{}".format(lo, "up" if hi > 1e8 else hi)] = err_line(R, m & (own >= lo) & (own < hi))
    out["own on the ground (flag)"] = err_line(R, m & (R[:, C["ground"]] > 0.5))
    out["own in the air (flag)"] = err_line(R, m & (R[:, C["ground"]] < 0.5))
    out["own on the ground (|vz| <= 30)"] = err_line(R, m & (R[:, C["air"]] < 0.5))
    out["own in the air (|vz| > 30)"] = err_line(R, m & (R[:, C["air"]] > 0.5))
    en = R[:, C["en"]]
    for lo, hi in EN_BINS:
        out["target speed {}-{}".format(lo, "up" if hi > 1e8 else hi)] = err_line(R, m & (en >= lo) & (en < hi))
    rv = R[:, C["rev"]]
    for lo, hi in REV_BINS:
        out["since turn-round {}-{} ms".format(lo * 25, "up" if hi > 400 else hi * 25)] = err_line(R, m & (rv >= lo) & (rv < hi) & (R[:, C["cross"]] >= 20))
    return out


def cond_metrics(R, RKs, U, F, W, meta):
    """one condition (his recordings): the brief's numbers"""
    fr = U[:, UC["frames"]].sum()
    mins = fr * DT / 60.0
    wk = {RG: "rg", LG: "lg", RL: "rl"}[W]
    shots = U[:, UC["shots_" + wk]].sum()
    o = dict(minutes=mins, in_hand=U[:, UC[wk]].sum() / fr, in_view=U[:, UC["vis"]].sum() / fr, in_hand_in_view=U[:, UC["vis_" + wk]].sum() / max(1.0, U[:, UC["vis"]].sum()),
             shots=int(shots), shots_min=shots / mins, shots_max=WMAX[W][0], dps=U[:, UC["dealt"]].sum() / (mins * 60.0), dps_max=WMAX[W][1],
             ground=U[:, UC["ground"]].sum() / fr, air=U[:, UC["air"]].sum() / fr, own=[U[:, UC["own%d" % q]].sum() / fr for q in range(4)],
             en_vis=_med(U[:, UC["en_vis"]]), tg_turns_min=U[:, UC["tg_turns"]].sum() / max(1e-9, mins), meta=meta)
    m = R[:, C["w"]] == W
    o["err"] = err_line(R, m)
    o["trav"] = _med(R[m, C["trav"]])
    o["own_at_shot"] = _med(R[m, C["own"]])
    o["splits"] = splits(R, m)
    f = F[F[:, 1] == W]
    o["first"] = dict(n=int(len(f)), from_view_ms=_med(f[:, 2]), from_start_ms=_med(f[:, 3]),
                      hit=float(np.nanmean(f[:, 4])) if len(f) and W != RL and np.isfinite(f[:, 4]).any() else float("nan"))
    if W == RG:
        ob = R[m, C["onbody"]]
        hh = R[m, C["hit"]] > 0
        o["rail"] = dict(onbody_ms=_med(ob * 25.0), off_body=float(np.mean(ob == 0)), swing=float(np.mean((ob >= 1) & (ob <= 2))),
                         waited=float(np.mean(ob >= 4)), loaded_on_still=U[:, UC["loaded_on_still"]].sum() / max(1.0, U[:, UC["loaded_on"]].sum()),
                         loaded_on_share=U[:, UC["loaded_on"]].sum() / max(1.0, U[:, UC["loaded_vis"]].sum()),
                         hit_off=float(np.mean(hh[ob == 0])) if (ob == 0).any() else float("nan"),
                         hit_swing=float(np.mean(hh[(ob >= 1) & (ob <= 2)])) if ((ob >= 1) & (ob <= 2)).any() else float("nan"),
                         hit_waited=float(np.mean(hh[ob >= 4])) if (ob >= 4).any() else float("nan"))
    if W == RL:
        v = RKs[:, RK["vis"]] > 0
        h = RKs[:, RK["hit"]] > 0
        dl = RKs[:, RK["dealt"]]
        nv = max(1, int(v.sum()))
        o["rockets"] = dict(n=int(len(RKs)), in_view=int(v.sum()), hit=float((v & h).sum() / nv), direct=float((v & h & (dl >= 85)).sum() / nv),
                            splash=float((v & h & (dl < 85)).sum() / nv), lead=_med(RKs[v, RK["lead"]]), below=_med(RKs[v, RK["below"]]),
                            d=_med(RKs[v, RK["d"]]), trav=_med(RKs[v, RK["trav"]]), own=_med(RKs[v, RK["own"]]))
    return o


def pros_metrics(P):
    """the pros beside (from `collect --src pros`): the rail's and the lightning's error by distance and the splits; the rail's wait on the
    body; the rockets' hit, lead and aim point by distance"""
    R, RKs, U = P["rows"].astype(np.float64), P["rockets"].astype(np.float64), P["units"]
    out = {}
    for W, nm in ((RG, "rail"), (LG, "lightning")):
        m = R[:, C["w"]] == W
        o = dict(all=err_line(R, m), trav=_med(R[m, C["trav"]]), own_at_shot=_med(R[m, C["own"]]), splits=splits(R, m))
        for lo, hi in ((0, 250), (250, 400), (400, 650), (650, 900), (900, 1250), (1250, 1800)):
            o["dist {}-{}".format(lo, hi)] = err_line(R, m & (R[:, C["d"]] >= lo) & (R[:, C["d"]] < hi))
        if W == RG:
            ob = R[m, C["onbody"]]
            hh = R[m, C["hit"]] > 0
            o["rail"] = dict(onbody_ms=_med(ob * 25.0), off_body=float(np.mean(ob == 0)), swing=float(np.mean((ob >= 1) & (ob <= 2))),
                             waited=float(np.mean(ob >= 4)), loaded_on_still=U[:, UC["loaded_on_still"]].sum() / max(1.0, U[:, UC["loaded_on"]].sum()),
                             loaded_on_share=U[:, UC["loaded_on"]].sum() / max(1.0, U[:, UC["loaded_vis"]].sum()),
                             hit_off=float(np.mean(hh[ob == 0])), hit_swing=float(np.mean(hh[(ob >= 1) & (ob <= 2)])), hit_waited=float(np.mean(hh[ob >= 4])))
        out[nm] = o
    v = RKs[:, RK["vis"]] > 0
    out["rockets"] = {"all": dict(n=int(v.sum()), hit=float(np.mean(RKs[v, RK["hit"]] > 0)), lead=_med(RKs[v, RK["lead"]]), below=_med(RKs[v, RK["below"]]))}
    for lo, hi in ((0, 300), (300, 500), (500, 700), (700, 1000)):
        mm = v & (RKs[:, RK["d"]] >= lo) & (RKs[:, RK["d"]] < hi)
        out["rockets"]["dist {}-{}".format(lo, hi)] = dict(n=int(mm.sum()), hit=float(np.mean(RKs[mm, RK["hit"]] > 0)) if mm.any() else float("nan"),
                                                          lead=_med(RKs[mm, RK["lead"]]), below=_med(RKs[mm, RK["below"]]))
    return out


DIST_BANDS = {RG: ((250, 400), (400, 650), (650, 900), (900, 1250), (1250, 1800)), LG: ((0, 250), (250, 400), (400, 650), (650, 900)),
              RL: ((0, 300), (300, 500), (500, 700), (700, 1000))}


def _bands(R, m, W):
    return {"{}-{}".format(lo, hi): err_line(R, m & (R[:, C["d"]] >= lo) & (R[:, C["d"]] < hi)) for lo, hi in DIST_BANDS[W]}


def _rk_bands(RKs, W=RL):
    v = RKs[:, RK["vis"]] > 0
    out = {}
    for lo, hi in DIST_BANDS[RL]:
        mm = v & (RKs[:, RK["d"]] >= lo) & (RKs[:, RK["d"]] < hi)
        h, dl = RKs[mm, RK["hit"]] > 0, RKs[mm, RK["dealt"]]
        out["{}-{}".format(lo, hi)] = dict(n=int(mm.sum()), hit=float(h.mean()) if mm.any() else float("nan"),
                                           direct=float((h & (dl >= 85)).mean()) if mm.any() else float("nan"),
                                           lead=_med(RKs[mm, RK["lead"]]), below=_med(RKs[mm, RK["below"]]))
    return out


def report(a):
    tag_dir = os.path.join(OUT, a.tag)
    res, pool = {}, {}
    for cd in sorted(glob.glob(os.path.join(tag_dir, "*_*_*_*"))):
        if not os.path.isdir(cd):
            continue
        cond = os.path.basename(cd)
        if a.only and not any(x in cond for x in a.only.split(",")):
            continue
        wn, dist, target, aim = cond.split("_", 3)
        W = WNUM[wn]
        R, RKs, U, F = collect_rows(cd, None, a.tau0)
        if not len(U):
            continue
        meta = {}
        for f in glob.glob(os.path.join(cd, "rec_*.npz")):
            mt = json.loads(str(np.load(f)["meta"]))
            for k, v in mt.items():
                if isinstance(v, (int, float)) and k != "dist":
                    meta[k] = meta.get(k, 0) + v
            meta.setdefault("maps", []).append(mt["map"])
        o = res[cond] = cond_metrics(R, RKs, U, F, W, meta)
        o["bands"] = _bands(R, R[:, C["w"]] == W, W)
        if W == RG:                                        # (the simulator's own shot frame: the enemy's place on the aim frame itself)
            R0 = collect_rows(cd, None, 0)[0]
            o["err_tau0"] = err_line(R0, R0[:, C["w"]] == RG)
            h0, half0 = R0[:, C["hit"]] > 0, np.degrees(np.arctan2(15.0, R0[:, C["d"]]))
            ib = lambda R_: (np.abs(R_[:, C["ey"]]) <= np.degrees(np.arctan2(15.0, R_[:, C["d"]]))) & (np.abs(R_[:, C["ep"]]) <= np.degrees(np.arctan2(28.0, R_[:, C["d"]])))
            h1 = R[:, C["hit"]] > 0
            o["tau_check"] = {"0": [float(ib(R0)[h0].mean()) if h0.any() else None, float(ib(R0)[~h0].mean()) if (~h0).any() else None],
                              "1": [float(ib(R)[h1].mean()) if h1.any() else None, float(ib(R)[~h1].mean()) if (~h1).any() else None]}
        if W == RL:
            o["rk_bands"] = _rk_bands(RKs)
        key = (wn, target, aim)
        pool.setdefault(key, [[], []])
        pool[key][0].append(R[R[:, C["w"]] == W])
        pool[key][1].append(RKs)
        e = o["err"]
        print("{:28s} {:6.0f} min | in hand {:4.0%} in view {:4.0%} | shots {:6d} ({:6.1f}/min of {:g}) | hit {:5.1%} | dmg/s {:5.1f} of {:5.1f} | "
              "error lr {:5.2f} deg {:5.2f} hb, ud {:5.2f} deg | dist {:5.0f} | n {}".format(
                  cond, o["minutes"], o["in_hand"], o["in_view"], o["shots"], o["shots_min"], o["shots_max"],
                  e.get("hit", np.nan), o["dps"], o["dps_max"], e.get("ey", np.nan), e.get("ey_hb", np.nan), e.get("ep", np.nan),
                  e.get("d", np.nan), e.get("n", 0)), flush=True)
    pooled = {}
    for (wn, target, aim), (Rs, RKl) in pool.items():
        W = WNUM[wn]
        R = np.concatenate(Rs)
        m = np.ones(len(R), bool)
        pooled["{}_{}_{}".format(wn, target, aim)] = dict(all=err_line(R, m), bands=_bands(R, m, W), splits=splits(R, m),
                                                          rk_bands=_rk_bands(np.concatenate(RKl)) if W == RL else None)
    out = dict(conds=res, pooled=pooled)
    if a.pros and os.path.exists(a.pros):
        P = np.load(a.pros)
        out["pros"] = pros_metrics(P)
        PR = P["rows"].astype(np.float64)
        out["pros"]["bands"] = {wn: _bands(PR, PR[:, C["w"]] == W, W) for wn, W in (("rg", RG), ("lg", LG))}
        out["pros"]["bands"]["rl"] = _rk_bands(P["rockets"].astype(np.float64))
    js = os.path.join(tag_dir, "report.json" if not a.only else "report_{}.json".format(int(time.time())))
    if os.path.exists(js):
        js = os.path.join(tag_dir, "report_{}.json".format(int(time.time())))
    json.dump(out, open(js, "w"), indent=1, default=float)
    md = js[:-5] + "_tables.md"
    open(md, "w", encoding="utf-8").write(tables(out))
    print("->", js, md)


def _f(x, fmt="{:.2f}"):
    try:
        return "-" if x is None or not np.isfinite(float(x)) else fmt.format(float(x))
    except (TypeError, ValueError):
        return "-"


def _pc(x):
    return _f(x, "{:.0%}")


def tables(out):
    """the report's tables in markdown (the results page takes them from here)"""
    res, pooled, pros = out["conds"], out["pooled"], out.get("pros")
    L = []
    order = lambda c: (c.split("_")[0], int(c.split("_")[1]), ("strafe", "dodger", "fighter").index(c.split("_")[2]),
                       list(aim_variants()).index(c.split("_", 3)[3]))
    conds = sorted(res, key=order)
    for wn, nm in (("rg", "Rail"), ("lg", "Lightning"), ("rl", "Rockets")):
        cs = [c for c in conds if c.startswith(wn + "_")]
        if not cs:
            continue
        L += ["", "### {}: every condition".format(nm), "",
              "| start dist | target | aim | minutes | in hand | in view | shots{} | a minute (of max) | hit | dmg/s (of max) | error L-R deg | L-R half bodies | "
              "error U-D deg | view travel 250 ms | own speed at shot | own <50 / 50-200 / 200-330 / >330 | true dist | target speed | target turns/min |".format(
                  " (cells)" if wn == "lg" else ""),
              "|" + "---|" * 19]
        for c in cs:
            o = res[c]
            e = o["err"]
            _, d, t, aim = c.split("_", 3)
            L.append("| {} | {} | {} | {:.0f} | {} | {} | {} | {:.1f} ({:g}) | {} | {:.1f} ({:.0f}) | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                d, t, aim, o["minutes"], _pc(o["in_hand"]), _pc(o["in_view"]), o["shots"] if wn != "rl" else o["rockets"]["n"], o["shots_min"], o["shots_max"],
                _pc(e.get("hit")) if wn != "rl" else _pc(o["rockets"]["hit"]), o["dps"], o["dps_max"], _f(e.get("ey")), _f(e.get("ey_hb")), _f(e.get("ep")),
                _f(o["trav"], "{:.1f}"), _f(o["own_at_shot"] if wn != "rl" else o["rockets"]["own"], "{:.0f}"),
                " / ".join(_pc(x) for x in o["own"]), _f(e.get("d") if wn != "rl" else o["rockets"]["d"], "{:.0f}"), _f(o["en_vis"], "{:.0f}"),
                _f(o["tg_turns_min"] / max(1e-9, 1.0), "{:.0f}") if t != "fighter" else "-"))
        if wn in ("rg", "lg"):
            W = WNUM[wn]
            bands = [b for b in (pros["bands"][wn] if pros else {}) ] or ["{}-{}".format(lo, hi) for lo, hi in DIST_BANDS[W]]
            keys = [k for k in ("{}_strafe_base", "{}_dodger_base", "{}_fighter_base", "{}_strafe_max", "{}_strafe_both_half") if k.format(wn) in pooled]
            L += ["", "### {}: the error by the TRUE distance at the shot, his conditions pooled over the start distances, beside the pros".format(nm), "",
                  "| distance | pros: n | L-R deg | half bodies | hit | " + " | ".join("{}: n | half bodies | hit".format(k.format(wn)[len(wn) + 1:]) for k in keys) + " |",
                  "|" + "---|" * (5 + 3 * len(keys))]
            for b in bands:
                p = pros["bands"][wn][b] if pros else {}
                row = "| {} | {} | {} | {} | {} | ".format(b, p.get("n", "-"), _f(p.get("ey")), _f(p.get("ey_hb")), _pc(p.get("hit")))
                row += " | ".join("{} | {} | {}".format(pooled[k.format(wn)]["bands"][b].get("n", 0), _f(pooled[k.format(wn)]["bands"][b].get("ey_hb")),
                                                       _pc(pooled[k.format(wn)]["bands"][b].get("hit"))) for k in keys)
                L.append(row + " |")
            pk = "rail" if wn == "rg" else "lightning"
            sp_keys = [k.format(wn) for k in ("{}_strafe_base", "{}_fighter_base") if k.format(wn) in pooled]
            L += ["", "### {}: the error by his own speed, in the air, the target's speed, the time since the target turned, the view's travel (all distances)".format(nm), "",
                  "| split | pros: n | half bodies | L-R deg | hit | " + " | ".join("{}: n | half bodies | L-R deg | hit".format(k[len(wn) + 1:]) for k in sp_keys) + " |",
                  "|" + "---|" * (5 + 4 * len(sp_keys))]
            for s_ in pooled[sp_keys[0]]["splits"] if sp_keys else []:
                p = pros[pk]["splits"].get(s_, {}) if pros else {}
                row = "| {} | {} | {} | {} | {} | ".format(s_, p.get("n", "-") if "flag" not in s_ else "-", _f(p.get("ey_hb")) if "flag" not in s_ else "-",
                                                         _f(p.get("ey")) if "flag" not in s_ else "-", _pc(p.get("hit")) if "flag" not in s_ else "-")
                row += " | ".join("{} | {} | {} | {}".format(pooled[k]["splits"][s_].get("n", 0), _f(pooled[k]["splits"][s_].get("ey_hb")),
                                                            _f(pooled[k]["splits"][s_].get("ey")), _pc(pooled[k]["splits"][s_].get("hit"))) for k in sp_keys)
                L.append(row + " |")
        variants = sorted({c.split("_", 3)[3] for c in cs if c.split("_")[2] == "strafe"}, key=lambda v: list(aim_variants()).index(v))
        if len(variants) > 1:
            dists = sorted({int(c.split("_")[1]) for c in cs})
            L += ["", "### {}: the aim variants against base (target strafe 0.3-1.2 s; hit / L-R half bodies / damage a second)".format(nm), "",
                  "| start dist | " + " | ".join(variants) + " |", "|" + "---|" * (1 + len(variants))]
            for d in dists:
                cells = []
                for v in variants:
                    o = res.get("{}_{}_strafe_{}".format(wn, d, v))
                    if o is None:
                        cells.append("-")
                    elif wn == "rl":
                        cells.append("{} / lead {} / {:.1f}".format(_pc(o["rockets"]["hit"]), _f(o["rockets"]["lead"]), o["dps"]))
                    else:
                        cells.append("{} / {} / {:.1f}".format(_pc(o["err"].get("hit")), _f(o["err"].get("ey_hb")), o["dps"]))
                L.append("| {} | ".format(d) + " | ".join(cells) + " |")
        if wn == "rg":
            L += ["", "### Rail: does he wait for the line or fire in the swing", "",
                  "| condition | crosshair on the body at the aim frame: no / 1-2 frames (the swing) / 4+ frames (waited) | hit: off / swing / waited | "
                  "loaded and on the body: share of loaded frames in view | ... frames he does not fire | first shot: from in view, ms | its hit | L-R deg at the simulator's own frame (tau 0) | hits / misses within the body, tau 0 ; tau 1 |",
                  "|---|---|---|---|---|---|---|---|---|"]
            if pros:
                r_ = pros["rail"]["rail"]
                L.append("| pros | {} / {} / {} | {} / {} / {} | {} | {} | - | - | - | - |".format(_pc(r_["off_body"]), _pc(r_["swing"]), _pc(r_["waited"]), _pc(r_["hit_off"]),
                                                                                        _pc(r_["hit_swing"]), _pc(r_["hit_waited"]), _pc(r_["loaded_on_share"]), _pc(r_["loaded_on_still"])))
            for c in cs:
                if not c.endswith("_base"):
                    continue
                r_, f_, tc = res[c]["rail"], res[c]["first"], res[c].get("tau_check", {})
                L.append("| {} | {} / {} / {} | {} / {} / {} | {} | {} | {} | {} | {} | {} |".format(
                    c[3:-5], _pc(r_["off_body"]), _pc(r_["swing"]), _pc(r_["waited"]), _pc(r_["hit_off"]), _pc(r_["hit_swing"]), _pc(r_["hit_waited"]),
                    _pc(r_["loaded_on_share"]), _pc(r_["loaded_on_still"]), _f(f_["from_view_ms"], "{:.0f}"), _pc(f_["hit"]), _f(res[c]["err_tau0"].get("ey")),
                    "{} / {} ; {} / {}".format(*[_pc(x) for x in tc.get("0", [None, None]) + tc.get("1", [None, None])])))
        if wn == "rl":
            L += ["", "### Rockets: hits, direct and splash, where the view points (of the rockets fired with the target in view)", "",
                  "| condition | rockets | in view | hit | direct | splash | lead (share of the full lead, + ahead) | view below his middle, units | true dist |",
                  "|---|---|---|---|---|---|---|---|---|"]
            if pros:
                for b, p in pros["bands"]["rl"].items():
                    L.append("| pros {} units | {} | - | {} | - | - | {} | {} | - |".format(b, p["n"], _pc(p["hit"]), _f(p["lead"]), _f(p["below"], "{:.0f}")))
            for c in cs:
                r_ = res[c]["rockets"]
                L.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(c[3:], r_["n"], r_["in_view"], _pc(r_["hit"]), _pc(r_["direct"]), _pc(r_["splash"]),
                                                                          _f(r_["lead"]), _f(r_["below"], "{:.0f}"), _f(r_["d"], "{:.0f}")))
            L += ["", "### Rockets by the true distance (pooled over the start distances)", "",
                  "| distance | pros: n | hit | lead | below | " + " | ".join("{}: n | hit | direct | lead".format(k[3:]) for k in pooled if k.startswith("rl_")) + " |",
                  "|" + "---|" * (5 + 4 * len([k for k in pooled if k.startswith("rl_")]))]
            for b in ["{}-{}".format(lo, hi) for lo, hi in DIST_BANDS[RL]]:
                p = pros["bands"]["rl"][b] if pros else {}
                row = "| {} | {} | {} | {} | {} | ".format(b, p.get("n", "-"), _pc(p.get("hit")), _f(p.get("lead")), _f(p.get("below"), "{:.0f}"))
                row += " | ".join("{} | {} | {} | {}".format(pooled[k]["rk_bands"][b]["n"], _pc(pooled[k]["rk_bands"][b]["hit"]), _pc(pooled[k]["rk_bands"][b]["direct"]),
                                                            _f(pooled[k]["rk_bands"][b]["lead"])) for k in pooled if k.startswith("rl_"))
                L.append(row + " |")
    L += ["", "### Rounds", "", "| condition | rounds | ended: he left (target out of his view 1 s) | target killed | he killed | 20-30 s up | loadout stripped | target turns: random / lane end |",
          "|---|---|---|---|---|---|---|---|"]
    for c in conds:
        mt = res[c]["meta"]
        L.append("| {} | {} | {} | {} | {} | {} | {} | {} / {} |".format(c, mt.get("rounds"), mt.get("left"), mt.get("tg_deaths"), mt.get("he_deaths"),
                                                                     mt.get("timeouts"), mt.get("stripped"), mt.get("rev_random"), mt.get("rev_lane")))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("spots")
    s.add_argument("--maps", default=",".join(MAPS))
    s.add_argument("--out", default=SPOTS)
    s.add_argument("--force", action="store_true")
    s.add_argument("--lane", type=float, default=160.0, help="the least lane each way, units")
    s.add_argument("--dists", default="")
    s.add_argument("--lane-at", default="1500:96", help="distance:lane, a smaller least lane where the maps have no wider one")
    s = sub.add_parser("play")
    s.add_argument("--tag", required=True)
    s.add_argument("--add", action="store_true", help="add conditions to an existing tag (a condition already there is refused)")
    s.add_argument("--weapon", default="rg")
    s.add_argument("--dist", default="all")
    s.add_argument("--target", default="strafe")
    s.add_argument("--aim", default="base")
    s.add_argument("--policy", default=POLICY)
    s.add_argument("--games", type=int, default=16, help="matches in a job (each: him and a target)")
    s.add_argument("--minutes", type=float, default=20.0)
    s.add_argument("--maps", default="", help="these maps (those of them with lines at the distance), in place of --maps-per")
    s.add_argument("--maps-per", type=int, default=3, help="maps a condition is played on (those with the longest lanes at its distance)")
    s.add_argument("--reps", type=int, default=1, help="jobs a map and condition")
    s.add_argument("--jobs", type=int, default=18)
    s.add_argument("--seed", type=int, default=1000)
    s = sub.add_parser("collect")
    s.add_argument("--src", default="pros")
    s.add_argument("--maps", default="bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,hektik,toxicity,cure")
    s.add_argument("--out", required=True)
    s.add_argument("--tau0", type=int, default=2)
    s = sub.add_parser("report")
    s.add_argument("--tag", required=True)
    s.add_argument("--pros", default=os.path.join(OUT, "pros_rows.npz"))
    s.add_argument("--only", default="", help="only the conditions whose name holds one of these (comma-separated)")
    s.add_argument("--tau0", type=int, default=1, help="his delay in frames where no lightning hits find it (pro_knobs: his games 1)")
    s = sub.add_parser("proof")
    s.add_argument("--tag", required=True)
    s.add_argument("--policy", default=POLICY)
    a = ap.parse_args()
    {"spots": spots, "play": play, "collect": collect, "report": report, "proof": proof}[a.cmd](a)


if __name__ == "__main__":
    main()
