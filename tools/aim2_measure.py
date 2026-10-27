"""AIM2's calibration measures, the same for the pros' demos and the simulator's games: every shot as a row (weapon, hit,
distance, how fast the target crosses his view, the retinal slip, the eccentricity, the time since the sighting, the damage
he took just before, the time since the target's last strafe reversal, a rocket's / plasma ball's miss along and across the
target's motion), every sighting as a flick row (the angle off at the sighting, the first shot of each weapon after it, its
time and whether it hit). Tables by weapon style (docs/v0.5.2/AIM_MODEL.md).

    python tools/aim2_measure.py pros --set trance|demos --maps bloodrun,aerowalk --limit 60 --procs 5 --out <npz>
    python tools/aim2_measure.py sim --policy <pt> --maps bloodrun,aerowalk --games 6 --minutes 4 --procs 5 \
           --run-cmd <run .cmd> --live <live.json> [--set NAME=VALUE ...] --out <npz>
    python tools/aim2_measure.py report <npz> [<npz> ...]           (one column per file)

How each measure is read (the same functions for both; the record is tools/pro_yardsticks.make_record's):
  shot        a weapon's ammunition going down between two frames (pro_yardsticks); a lightning frame is a shot.
  hit         pro_yardsticks.hit_combos(): a step of the player's own hit counter on the frame of a hitscan shot or the next
              (lightning, rail, machine gun, shotgun); otherwise given to the rocket / plasma ball due about then. In a demo
              the counter is the player state's PERS_HITS; in the simulator a frame on which his damage dealt rises.
  distance    eye to the enemy's place + 8 units, where the enemy's place is known.
  cross       the enemy's angular speed across the line from his eye (deg/s), from the two places' change (both moving).
  slip        |the enemy's bearing rate - his view's rate| (deg/s; yaw scaled by the cosine of the elevation), the frame
              before the shot to the shot's frame: what the eyes see move on the screen.
  ecc         the angle between his view and the enemy at the shot (deg).
  since       seconds since the enemy came into view (this sighting).
  took        damage (health + armor, 3 or more a frame) he took in the 0.5 s before the shot (any source, own splash too).
  rev         seconds since the enemy's last reversal of his sideways movement across the line of sight (both sides
              over 100 u/s within 0.4 s; 9 = none known).
  miss        rockets and plasma: the closest pass of the projectile (straight from his eye along his view at the weapon's
              speed, to the wall) to the enemy's later places (+8 units); split into along the enemy's horizontal motion at
              the shot (+ = the projectile ahead of him: led too much), across it (horizontal) and up (vertical).
  flick rows  a sighting = the enemy in view after 1 s out of it (pro_yardsticks' rule); the angle off at it; for rail,
              shotgun, lightning and rockets the first shot of that weapon within 1.5 s inside the same sighting: its time,
              whether it hit, whether the weapon was already in hand at the sighting.
"""
import argparse
import glob
import json
import multiprocessing as mp_
import os
import sys
import tempfile
import time

import numpy as np

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIM = os.path.join(ROOT, "sim")
sys.path.insert(0, HERE)
sys.path.insert(0, SIM)

SHOT_COLS = ("w", "cnt", "hit", "direct", "dist", "cross", "slip", "ecc", "since", "took", "rev", "m_along", "m_across", "m_up",
             "espeed", "src")
FLICK_COLS = ("w", "ang", "dt", "hit", "inhand", "dist", "src")
NAMES = ("rl", "rg", "lg", "mg", "sg", "gl", "pg", "hmg", "g")


def _wrap(x):
    return (x + 180.0) % 360.0 - 180.0


def rows_of(rec, world, src=0):
    """a record (pro_yardsticks.make_record) -> (shot rows, flick rows), numpy arrays of SHOT_COLS / FLICK_COLS"""
    import pro_yardsticks as Y
    Y.see(rec, world)
    t, alive, inview, en, eye = rec["t"], rec["alive"], rec["inview"], rec["enemy"], rec["eye"]
    n = len(t)
    first = rec["first"]
    seg_end = np.zeros(n, np.int64)
    ends = np.nonzero(np.concatenate([first[1:], [True]]))[0]
    for a, b in zip(np.nonzero(first)[0], ends):
        seg_end[a:b + 1] = b
    sh = rec["shots"]
    sh = sh[alive[sh[:, 0]]] if len(sh) else sh
    frag = np.zeros(n, bool)
    frag[1:] = (rec["score"][1:] > rec["score"][:-1]) & ~first[1:]
    T = Y.new_tally()
    hits, pr = Y.hit_combos(rec, T, sh, frag, world, seg_end)
    if not len(sh) or rec["hits"] is None:
        return np.zeros((0, len(SHOT_COLS))), np.zeros((0, len(FLICK_COLS)))
    up = np.array([0, 0, 8.0])
    fd = Y._fwd(rec["yaw"], rec["pitch"]).astype(np.float64)
    known = np.isfinite(en[:, 0]) & alive
    dt = np.zeros(n)
    dt[1:] = np.diff(t)
    ok1 = np.zeros(n, bool)
    ok1[1:] = ~first[1:] & known[1:] & known[:-1] & (dt[1:] > 0) & (dt[1:] < 0.06)
    tgt = np.where(known[:, None], en + up - eye, np.nan)
    by = np.degrees(np.arctan2(tgt[:, 1], tgt[:, 0]))
    bp = np.degrees(np.arctan2(tgt[:, 2], np.hypot(tgt[:, 0], tgt[:, 1])))
    vy, vp = rec["yaw"].astype(np.float64), -rec["pitch"].astype(np.float64)
    slip = np.full(n, np.nan)
    sy = _wrap(np.diff(by)) - _wrap(np.diff(vy))
    sp_ = np.diff(bp) - np.diff(vp)
    slip[1:] = np.where(ok1[1:], np.hypot(sy * np.cos(np.radians(bp[1:])), sp_) / np.maximum(dt[1:], 1e-3), np.nan)
    cosang = (tgt * fd).sum(1) / (np.linalg.norm(tgt, axis=1) + 1e-9)
    ecc = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    ev = np.full((n, 3), np.nan)                                 # the enemy's velocity from his places
    ev[1:] = np.where(ok1[1:, None], np.diff(en, axis=0) / np.maximum(dt[1:, None], 1e-3), np.nan)
    rel = ev - rec["vel"]
    d_ = tgt / (np.linalg.norm(tgt, axis=1, keepdims=True) + 1e-9)
    perp = rel - (rel * d_).sum(1, keepdims=True) * d_
    cross = np.degrees(np.linalg.norm(perp, axis=1) / (np.linalg.norm(tgt, axis=1) + 1e-9))
    espeed = np.hypot(ev[:, 0], ev[:, 1])
    # the enemy's sideways speed across the line of sight, and its reversals
    lat = ev[:, 0] * (-d_[:, 1]) + ev[:, 1] * d_[:, 0]
    sg = np.where(np.abs(lat) > 100.0, np.sign(lat), 0.0)
    rev_t = np.full(n, 9.0)
    last_s, last_i, last_rev = 0.0, -1, -1e9
    for i in range(n):
        if first[i]:
            last_s, last_i, last_rev = 0.0, -1, -1e9
        if sg[i] != 0 and not np.isnan(lat[i]):
            if last_s != 0 and sg[i] != last_s and t[i] - t[last_i] <= 0.4:
                last_rev = t[i]
            last_s, last_i = sg[i], i
        rev_t[i] = min(9.0, t[i] - last_rev)
    # damage taken in the last 0.5 s
    dh, da = np.zeros(n), np.zeros(n)
    dh[1:], da[1:] = np.diff(rec["health"]), np.diff(rec["armor"])
    okd = ~first & alive & np.concatenate([[False], alive[:-1]])
    took = np.maximum(0.0, -(dh + da)) * okd
    took[took < 3.0] = 0.0
    ct = np.cumsum(took)
    b5 = np.searchsorted(t, t - 0.5, side="left")
    took5 = ct - ct[np.maximum(b5 - 1, 0)]
    # since the sighting
    since_start = np.full(n, np.nan)
    st_ = -1
    for i in range(n):
        if first[i] or not inview[i]:
            st_ = -1
            continue
        if st_ < 0:
            st_ = i
        since_start[i] = t[i] - t[st_]
    # hits per shot
    hit_scan = {}
    for f, wq, k in hits:
        if k < 0:
            hit_scan.setdefault(wq, set()).add(f)
    pr_hit = {}
    pr_idx = np.nonzero(np.isin(sh[:, 1], (Y.RL, Y.GL, Y.PG)))[0]
    for f, wq, k in hits:
        if k >= 0:
            pr_hit[int(pr_idx[k])] = f
    rows = []
    for q, (i, wq, cnt) in enumerate(sh):
        i, wq, cnt = int(i), int(wq), int(cnt)
        if wq in (Y.GL, Y.GAUNT):
            continue
        if wq in (Y.RL, Y.PG):
            hf = pr_hit.get(q)
            hit = 1 if hf is not None else 0
        else:
            s_ = hit_scan.get(wq, set())
            hit = int(i in s_ or (i + 1) in s_)
        direct, ma, mc, mu = 0, np.nan, np.nan, np.nan
        if wq in (Y.RL, Y.PG) and known[i]:
            spd = Y.PROJ[wq]
            wall = 8192.0 * float(world.lines(eye[i:i + 1].astype(np.float32), (eye[i] + fd[i] * 8192.0)[None].astype(np.float32),
                                                mask=Y.SOLID)[0])
            tmax = wall / spd
            j1 = min(int(np.searchsorted(t, t[i] + tmax + 0.05, side="right")), seg_end[i] + 1)
            js = np.arange(i, j1)
            js = js[known[js]]
            if len(js):
                tau = t[js] - t[i]
                p = eye[i] + fd[i] * (spd * np.minimum(tau, tmax))[:, None]
                off = p - (en[js] + up)
                k_ = int(np.argmin(np.linalg.norm(off, axis=1)))
                o = off[k_]
                v0 = ev[i] if np.isfinite(ev[i, 0]) else np.zeros(3)
                hv = np.array([v0[0], v0[1], 0.0])
                if np.linalg.norm(hv) > 50.0:
                    u = hv / np.linalg.norm(hv)
                    ma = float(o @ u)
                    mc = float(np.hypot(*(o[:2] - ma * u[:2])))
                mu = float(o[2])
                direct = int(hit and np.linalg.norm(o) <= 60.0)
        rows.append((wq, cnt, hit, direct, rec["dist"][i] if np.isfinite(rec["dist"][i]) else np.nan,
                     cross[i], slip[i], ecc[i] if known[i] else np.nan, since_start[i], took5[i], rev_t[i], ma, mc, mu,
                     espeed[i], src))
    R = np.array(rows, np.float64).reshape(-1, len(SHOT_COLS))
    # flicks
    since = rec["since"]
    starts = np.nonzero(inview & ~first & (np.concatenate([[0.0], since[:-1]]) >= Y.SIGHT_OUT_S - 0.03))[0]
    F = []
    shot_by_w = {}
    for row, (i, wq, cnt) in zip(range(len(sh)), sh):
        shot_by_w.setdefault(int(wq), []).append((int(i), row))
    for s in starts:
        endv = s
        while endv + 1 <= seg_end[s] and inview[endv + 1] and t[endv + 1] - t[s] <= 1.5:
            endv += 1
        for wq in (Y.RG, Y.SG, Y.LG, Y.RL):
            lst = shot_by_w.get(wq, [])
            cand = [i for i, _ in lst if s <= i <= endv]
            if not cand:
                continue
            i = cand[0]
            s_ = hit_scan.get(wq, set())
            if wq == Y.RL:
                rr = [r for ii, r in lst if ii == i]
                hit = int(rr[0] in pr_hit) if rr else 0
            else:
                hit = int(i in s_ or (i + 1) in s_)
            F.append((wq, ecc[s], t[i] - t[s], hit, int(rec["weapon"][s] == wq), rec["dist"][s], src))
    return R, np.array(F, np.float64).reshape(-1, len(FLICK_COLS))


# ---------------------------------------------------------------------------------------------------------------- pros
_W = {}


def _exe(Y):
    """tools/demodump/demodump.exe is built in the main repo only (git-ignored): use it from there in a worktree"""
    if not os.path.exists(Y.EXE):
        main_ = os.path.join(os.path.dirname(os.path.realpath(os.path.join(ROOT, "data"))), "tools", "demodump", "demodump.exe")
        if os.path.exists(main_):
            Y.EXE = main_


def _init(mp, tmp):
    import pro_yardsticks as Y
    _exe(Y)
    Y.low_priority()
    from qsim import World
    w = World(os.path.join(ROOT, "data", "maps", mp + ".bsp"))
    w.add_solids()
    _W.update(world=w, tmp=os.path.join(tmp, str(os.getpid())))
    os.makedirs(_W["tmp"], exist_ok=True)


def _one(demo):
    import pro_yardsticks as Y
    try:
        rec, info = Y.parse(demo, _W["tmp"])
        if rec is None:
            return None
        return rows_of(rec, _W["world"])
    except Exception as e:                                      # noqa: BLE001
        print("skip", os.path.basename(demo), repr(e)[:120], file=sys.stderr)
        return None


def pros(a):
    import pro_yardsticks as Y
    out_s, out_f = [], []
    for mp in a.maps.split(","):
        if a.set == "trance":
            files = sorted(glob.glob(os.path.join("T:/quake-demos/trance/by_map", mp, "*.dm_*")))
            cat = {}
            catf = "T:/quake-demos/trance/catalog.csv"
            if os.path.exists(catf):
                import csv
                for r in csv.DictReader(open(catf, encoding="utf-8", errors="replace")):
                    cat[os.path.basename(r["file"].replace("\\", "/"))] = r
            files = [f for f in files if cat.get(os.path.basename(f), {}).get("snap_ms", "25.0") in ("25.0", "25", "")]
        else:
            files = sorted(f for f in glob.glob(os.path.join(Y.demo_root(), "demos", mp, "*.dm_*")) if not f.endswith(".part"))
        if a.limit:
            files = files[::max(1, len(files) // a.limit)][:a.limit]
        tmp = tempfile.mkdtemp(prefix="aim2p_")
        t0 = time.time()
        with mp_.Pool(a.procs, initializer=_init, initargs=(mp, tmp)) as pool:
            res = pool.map(_one, files, chunksize=2)
        ok = [r for r in res if r is not None]
        for r in ok:
            out_s.append(r[0])
            out_f.append(r[1])
        print("{} {}: {} demos ({} read), {:.0f} s".format(a.set, mp, len(files), len(ok), time.time() - t0), file=sys.stderr, flush=True)
    S = np.concatenate(out_s) if out_s else np.zeros((0, len(SHOT_COLS)))
    F = np.concatenate(out_f) if out_f else np.zeros((0, len(FLICK_COLS)))
    np.savez(a.out, shots=S, flicks=F, about=np.array(json.dumps(dict(kind="pros", set=a.set, maps=a.maps, limit=a.limit))))


# ---------------------------------------------------------------------------------------------------------------- sim
def cmd_env(path):
    env = {}
    for ln in open(path, encoding="utf-8", errors="replace"):
        s = ln.strip()
        if s.lower().startswith("set ") and "=" in s:
            k, v = s[4:].split("=", 1)
            env[k.strip()] = v.strip()
    return env


_REC = {}


def _recorder(E):
    """wraps E.DuelEnv.step once: every step's state kept in _REC["B"] (lists of per-frame arrays)"""
    if getattr(E.DuelEnv, "_aim2_rec", False):
        return
    step0 = E.DuelEnv.step

    def step(self, a):
        out = step0(self, a)
        B = _REC.setdefault("B", {k: [] for k in ("pos", "vel", "air", "yaw", "pitch", "hp", "ar", "w", "ammo", "duck", "dmg",
                                                   "died", "a2")})
        s = self.state
        B["pos"].append(s[:, :3].copy())
        B["vel"].append(s[:, 3:6].copy())
        B["air"].append(s[:, 6] < 0.5)
        B["yaw"].append(np.asarray(self.yaw, np.float32).copy())
        B["pitch"].append(np.asarray(self.pitch, np.float32).copy())
        B["hp"].append(np.asarray(self.hp, np.float32).copy())
        B["ar"].append(np.asarray(self.armor, np.float32).copy())
        B["w"].append(np.asarray(self.weapon).copy())
        B["ammo"].append(np.asarray(self.ammo, np.float32).copy())
        B["duck"].append(np.asarray(self.duck).copy())
        B["dmg"].append(np.asarray(self.dmg_life, np.float32).copy())
        d_ = np.zeros(self.n, bool)
        for e in out[3]["events"]:
            d_[int(e["victim"])] = True
        B["died"].append(d_)
        a2_ = getattr(self, "a2_last", None)
        B["a2"].append(np.stack(a2_, 1) if a2_ is not None else np.zeros((self.n, 3), np.float32))
        return out
    E.DuelEnv.step = step
    E.DuelEnv._aim2_rec = True


def play(job):
    """duel_eval.play's games (the network on every seat, the checks' setup) with every frame recorded -> shot and flick
    rows of every seat, and the AIM2 terms (slip, ecc, error) of the frames they were read on"""
    import pro_yardsticks as Y
    import duel_eval as DE
    import importlib
    Y.low_priority()
    envmod, envvars = job[0], job[1]
    os.environ.update(envvars)
    E = importlib.import_module(envmod)
    _recorder(E)
    _REC.clear()
    DE.play(job)
    B = {k: np.stack(v) for k, v in _REC["B"].items()}
    mp = job[2]
    from qsim import World
    w = World(os.path.join(ROOT, "data", "maps", mp + ".bsp"))
    w.add_solids()
    frames, n = B["hp"].shape
    tm = (np.arange(frames) + 1) * E.DT
    nw = len(E.WEAPONS)
    score = np.zeros((frames, n), np.int64)
    S, F = [], []
    for p in range(n):
        o = p ^ 1
        dead = B["died"][:, p]
        alive = (B["hp"][:, p] > 0) & ~dead
        both = alive & np.concatenate([[False], alive[:-1]])
        shots = []
        for wq in range(nw):
            if E.WEAPONS[wq] == "g":
                continue
            dec = np.zeros(frames)
            dec[1:] = B["ammo"][:-1, p, wq] - B["ammo"][1:, p, wq]
            shots += [(int(i), wq, int(round(dec[i]))) for i in np.nonzero(both & (dec > 0.5) & (dec <= 6))[0]]
        shots.sort()
        upd = np.zeros(frames, bool)
        upd[1:] = B["dmg"][1:, p] > B["dmg"][:-1, p]
        enemy = B["pos"][:, o].copy()
        enemy[B["died"][:, o]] = np.nan
        rec = Y.make_record(t=tm, pos=B["pos"][:, p], vel=B["vel"][:, p], yaw=B["yaw"][:, p], pitch=B["pitch"][:, p],
                            weapon=B["w"][:, p], shots=shots, health=np.where(dead, 0.0, B["hp"][:, p]), armor=B["ar"][:, p],
                            score=score[:, p], enemy=enemy, enemy_score=score[:, o], clock=tm, alive=alive,
                            eye_h=np.where(B["duck"][:, p], 12.0, 26.0), enemy_air=B["air"][:, o].astype(np.int64),
                            hits=np.cumsum(upd))
        r, f = rows_of(rec, w, src=1)
        S.append(r)
        F.append(f)
    a2 = B["a2"].reshape(-1, 3)
    a2 = a2[a2[:, 0] > 0]
    return mp, np.concatenate(S), np.concatenate(F), a2


def sim(a):
    import pro_yardsticks as Y
    Y.low_priority()
    envvars = cmd_env(a.run_cmd) if a.run_cmd else {}
    if a.live:
        envvars.update({k: str(v) for k, v in json.load(open(a.live)).items()})
    envvars.update(dict(x.split("=", 1) for x in a.set))
    envvars.update(OPENBLAS_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1", PYTHONFAULTHANDLER="1")
    os.environ.update(envvars)
    import test_suite as TS
    pol = TS.Policy(a.policy, seed=1)
    idx = np.arange(len(pol.mean))
    delays = (pol.react_ms, pol.acquire_ms, pol.react_ms, pol.acquire_ms)
    if "BRAIN_READ" not in envvars and getattr(pol, "rf_read", False) and pol.rfg > 0:
        envvars["BRAIN_READ"] = "1"
    jobs = [(a.env, envvars, mp, a.games, a.minutes, a.seed + 17 * q, pol, idx, "policy", pol, idx, (600.0, 600.0, False), False,
             delays) for q, mp in enumerate(a.maps.split(","))]
    t0 = time.time()
    S, F, A2 = [], [], []
    with mp_.Pool(min(a.procs, len(jobs)), maxtasksperchild=1) as pool:
        for mp, s, f, a2 in pool.imap_unordered(play, jobs):
            S.append(s)
            F.append(f)
            A2.append(a2)
            print("sim {}: {} shots, {:.0f} s".format(mp, len(s), time.time() - t0), file=sys.stderr, flush=True)
    np.savez(a.out, shots=np.concatenate(S), flicks=np.concatenate(F), a2=np.concatenate(A2) if A2 else np.zeros((0, 3)),
             about=np.array(json.dumps(dict(kind="sim", policy=a.policy, sets=a.set, maps=a.maps, games=a.games,
                                            minutes=a.minutes))))


# ---------------------------------------------------------------------------------------------------------------- report
STYLES = (("lightning (tracking)", "lg"), ("machine gun (tracking + spread)", "mg"), ("heavy machine gun", "hmg"),
          ("rail (flicking)", "rg"), ("shotgun (close flick)", "sg"), ("rockets (prediction)", "rl"),
          ("plasma (prediction + tracking)", "pg"))


def _rate(S, m):
    w = S[m, 1]
    return (float((S[m, 2] * w).sum() / w.sum()) * 100.0 if w.sum() > 0 else float("nan")), int(w.sum())


def _matched(S, C, mA, mB):
    """mA's hits against what mB's hit rate by distance band would give mA's shots (100 = no difference)"""
    d = S[:, C["dist"]]
    exp_, got_, nA = 0.0, 0.0, 0
    for lo, hi in ((0, 250), (250, 500), (500, 750), (750, 1100), (1100, 1e9)):
        b = (d >= lo) & (d < hi)
        wa, wb = S[mA & b, 1], S[mB & b, 1]
        if wa.sum() == 0 or wb.sum() < 20:
            continue
        rb = (S[mB & b, 2] * wb).sum() / wb.sum()
        exp_ += wa.sum() * rb
        got_ += (S[mA & b, 2] * wa).sum()
        nA += int(wa.sum())
    return (100.0 * got_ / exp_ if exp_ > 0 else float("nan")), nA


def tables(path):
    Z = np.load(path)
    S, F = Z["shots"], Z["flicks"]
    C = {c: i for i, c in enumerate(SHOT_COLS)}
    out = {}
    for label, nm in STYLES:
        wq = NAMES.index(nm)
        m0 = (S[:, 0] == wq) & np.isfinite(S[:, C["dist"]])
        o = out[nm] = {}
        o["all"] = _rate(S, m0)
        for lo, hi in ((0, 250), (250, 500), (500, 750), (750, 1100), (1100, 1e9)):
            o["dist {}-{}".format(lo, hi if hi < 1e9 else "")] = _rate(S, m0 & (S[:, C["dist"]] >= lo) & (S[:, C["dist"]] < hi))
        for lo, hi in ((0, 15), (15, 30), (30, 60), (60, 1e9)):
            o["cross {}-{}".format(lo, hi if hi < 1e9 else "")] = _rate(S, m0 & (S[:, C["cross"]] >= lo) & (S[:, C["cross"]] < hi))
        for lo, hi in ((0, 10), (10, 25), (25, 50), (50, 100), (100, 1e9)):
            o["slip {}-{}".format(lo, hi if hi < 1e9 else "")] = _rate(S, m0 & (S[:, C["slip"]] >= lo) & (S[:, C["slip"]] < hi))
        for lo, hi in ((0, 2), (2, 5), (5, 10), (10, 1e9)):
            o["ecc {}-{}".format(lo, hi if hi < 1e9 else "")] = _rate(S, m0 & (S[:, C["ecc"]] >= lo) & (S[:, C["ecc"]] < hi))
        for lo, hi in ((0, 0.1), (0.1, 0.2), (0.2, 0.35), (0.35, 0.6), (0.6, 9.5)):
            o["rev {}-{}".format(lo, hi)] = _rate(S, m0 & (S[:, C["rev"]] >= lo) & (S[:, C["rev"]] < hi))
        o["took 0 (none in 0.5 s)"] = _rate(S, m0 & (S[:, C["took"]] == 0))
        o["took 1-29"] = _rate(S, m0 & (S[:, C["took"]] > 0) & (S[:, C["took"]] < 30))
        o["took 30+"] = _rate(S, m0 & (S[:, C["took"]] >= 30))
        calm = m0 & (S[:, C["took"]] == 0)
        o["after damage (any in 0.5 s), distance-matched, % of calm"] = _matched(S, C, m0 & (S[:, C["took"]] > 0), calm)
        o["after 30+ damage, distance-matched, % of calm"] = _matched(S, C, m0 & (S[:, C["took"]] >= 30), calm)
        steady = m0 & (S[:, C["rev"]] >= 0.6)
        o["0.1-0.2 s after a reversal, distance-matched, % of steady"] = _matched(
            S, C, m0 & (S[:, C["rev"]] >= 0.1) & (S[:, C["rev"]] < 0.2), steady)
        o["0.2-0.35 s after a reversal, distance-matched, % of steady"] = _matched(
            S, C, m0 & (S[:, C["rev"]] >= 0.2) & (S[:, C["rev"]] < 0.35), steady)
        slow = m0 & (S[:, C["slip"]] < 25)
        o["slip 50+ deg/s, distance-matched, % of slip under 25"] = _matched(S, C, m0 & (S[:, C["slip"]] >= 50), slow)
        if nm in ("rl", "pg"):
            mm = m0 & np.isfinite(S[:, C["m_along"]]) & (S[:, C["espeed"]] > 200)
            o["miss along med (moving)"] = (float(np.median(S[mm, C["m_along"]])) if mm.any() else float("nan"), int(mm.sum()))
            o["miss |along| med"] = (float(np.median(np.abs(S[mm, C["m_along"]]))) if mm.any() else float("nan"), int(mm.sum()))
            o["miss across med"] = (float(np.median(S[mm, C["m_across"]])) if mm.any() else float("nan"), int(mm.sum()))
            o["direct %"] = (float(S[m0, C["direct"]].mean() * 100) if m0.any() else float("nan"), int(m0.sum()))
        if nm in ("rg", "sg", "lg", "rl"):
            fm = F[:, 0] == wq
            for lo, hi in ((0, 5), (5, 15), (15, 30), (30, 60), (60, 181)):
                q = fm & (F[:, 1] >= lo) & (F[:, 1] < hi)
                if q.any():
                    o["flick {}-{} deg: first-shot time med".format(lo, hi)] = (float(np.median(F[q, 2])), int(q.sum()))
                    o["flick {}-{} deg: first-shot hit %".format(lo, hi)] = (float(F[q, 3].mean() * 100), int(q.sum()))
    return out


def report(paths):
    T = [tables(p) for p in paths]
    for label, nm in STYLES:
        print("\n## {}".format(label))
        keys = list(T[0][nm].keys())
        print("| measure | " + " | ".join(os.path.basename(p) for p in paths) + " |")
        print("|---|" + "---|" * len(paths))
        for k in keys:
            cells = []
            for t in T:
                v, c = t[nm].get(k, (float("nan"), 0))
                cells.append("{:.1f} ({})".format(v, c) if c else "-")
            print("| {} | {} |".format(k, " | ".join(cells)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("pros", "sim", "report"))
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--set", default="demos")
    ap.add_argument("--maps", default="bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--procs", type=int, default=5)
    ap.add_argument("--out", default="aim2.npz")
    ap.add_argument("--policy", default="")
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--minutes", type=float, default=4.0)
    ap.add_argument("--seed", type=int, default=900)
    ap.add_argument("--run-cmd", default="")
    ap.add_argument("--live", default="")
    ap.add_argument("--sets", dest="set_", action="append", default=[], help="NAME=VALUE (sim)")
    a = ap.parse_args()
    if a.mode == "pros":
        pros(a)
    elif a.mode == "sim":
        a.set = a.set_
        sim(a)
    else:
        report(a.paths)


if __name__ == "__main__":
    main()
