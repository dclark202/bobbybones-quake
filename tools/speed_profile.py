"""How speed is built and kept, not its mean (owner, 2026-10-10: "average speed is a bit of a misleading metric, because
speed is bursty ... when speed is built and how well it is maintained"; a player who stands or walks to be silent and
then moves fast has the mean of one who runs all the time).

    python tools/speed_profile.py --policy data/sim_runs/<run>/policy.pt --map bloodrun,aerowalk,lostworld --json him.json
    python tools/speed_profile.py --demos bloodrun,aerowalk,lostworld --json pros.json        the pros (light demo sets)
    python tools/speed_profile.py --show pros.json v14.json him.json                         a table side by side

A network plays ten-minute duels against the Nightmare stand-in in the simulator (--games a map); the pros come from
sim/demo_dataset.py --lite. Both are read the same way, from positions 40 times a second:
  time by speed   standing (under 40 units a second), slow (to 200), running (to 345), fast (to 420), very fast, for
                  all his time, travelling (no enemy in view) and fighting (an enemy in view)
  hops            a take-off is his height beginning to rise at a jump's speed; a chain is take-offs a second apart or
                  less. The speed at the 1st, 2nd, 3rd ... take-off of a chain: a strafe jumper gains with every hop
  fast spells     stretches at 400 or more: how many a minute, how long, how long it took to build them from under 330,
                  and what ended them (a sudden loss: a wall or a bad landing; an enemy came into view; he died; he slowed)
One JSON a source, with a minute of speed over time for a picture (tools/draw_speed.py, system Python).
"""
import argparse
import glob
import json
import multiprocessing as mp_
import os
import sys

import numpy as np

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE)
SIM = os.path.join(os.path.dirname(HERE), "sim")
DT = 0.025
BANDS = (40.0, 200.0, 345.0, 420.0)                         # (a runner without a jump reaches 320; with plain hops about 340)
BAND_NAMES = ("standing", "slow", "running", "fast", "very fast")
SETS = dict(AIM_LEVEL="3", ITEM_BELIEF="1", STYLE_P="0.75", INTENT_HOLD="8", KEY_RATE="8", AMMO_PACKS="0", GROUND_SENSE="1", DROPS="1",
            SHOT_MASK="1", LAVA="1", WALK_FIX="1", QL_MOVE="1", ITEM_DROP="1", SOLIDS="1", PRO_WAYS="1", NEAREST="1", PROJ_SEE="1", GL_QL="1")


def analyse(segs):
    """segs: [(pos (T, 3), inview (T,) bool)] of single lives, 40 frames a second -> the numbers"""
    band = {k: np.zeros(5) for k in ("all", "travel", "fight")}
    hop_sp = [[] for _ in range(8)]
    hop_tr = [[] for _ in range(8)]                            # ... of the chains that begin with no enemy in view
    chains, gains, hops, frames = [], [], 0, 0
    spells, builds, ends, f400, dist, dist400 = [], [], dict(sudden=0, fight=0, died=0, slowed=0), 0, 0.0, 0.0
    trace = None
    for pos, vis in segs:
        T = len(pos)
        if T < 40:
            continue
        d = np.diff(pos, axis=0) / DT
        s = np.hypot(d[:, 0], d[:, 1])
        vz = d[:, 2]
        if (s > 1500).any():                                   # (a teleporter inside a life: the step is no speed)
            s = np.where(s > 1500, np.nan, s)
            s = np.where(np.isnan(s), np.nanmedian(s), s)
        k = np.ones(11) / 11.0                                 # (a quarter of a second: a demo's positions jitter from frame to frame)
        sm = np.convolve(np.pad(s, 5, mode="edge"), k, mode="valid")
        v = vis[1:].astype(bool)
        b = np.digitize(sm, BANDS)
        for name, m in (("all", np.ones(len(b), bool)), ("travel", ~v), ("fight", v)):
            band[name] += np.bincount(b[m], minlength=5)
        frames += len(s)
        dist += float(sm.sum() * DT)
        dist400 += float(sm[sm >= 400].sum() * DT)
        # take-offs: his height begins to rise at a jump's speed (as tools/pro_gaps.py) and is still rising a frame later
        # (a step of the stairs is not)
        t = np.arange(1, len(vz) - 2)
        to = t[(vz[t] > 180) & (vz[t] < 400) & (vz[t - 1] < 100) & (vz[t + 1] > 120)]
        hops += len(to)
        i = 0
        while i < len(to):
            j = i
            while j + 1 < len(to) and to[j + 1] - to[j] <= 40:
                j += 1
            ch = to[i:j + 1]
            chains.append(len(ch))
            sp = [float(sm[max(0, c - 1):c + 2].mean()) for c in ch]
            for n_, x in enumerate(sp[:8]):
                hop_sp[n_].append(x)
                if not v[max(0, ch[0] - 20):ch[0] + 20].any():
                    hop_tr[n_].append(x)
            gains += [sp[n_ + 1] - sp[n_] for n_ in range(len(sp) - 1)]
            i = j + 1
        # spells at 400 or more (a dip of under 0.2 s does not end one)
        hi = sm >= 400
        f400 += int(hi.sum())
        idx = np.nonzero(hi)[0]
        if len(idx):
            cut = np.nonzero(np.diff(idx) > 8)[0]
            a0 = np.concatenate([[idx[0]], idx[cut + 1]])
            a1 = np.concatenate([idx[cut], [idx[-1]]])
            for x0, x1 in zip(a0, a1):
                if x1 - x0 + 1 < 12:                           # (under 0.3 s is no spell)
                    continue
                spells.append((x1 - x0 + 1) * DT)
                lo = np.nonzero(sm[:x0] < 330)[0]
                if len(lo):
                    builds.append(min(6.0, (x0 - lo[-1]) * DT))
                if x1 >= len(sm) - 4:
                    ends["died"] += 1
                elif (sm[x1] - sm[min(len(sm) - 1, x1 + 6)]) > 120:
                    ends["sudden"] += 1
                elif v[max(0, x1 - 10):x1 + 10].any():
                    ends["fight"] += 1
                else:
                    ends["slowed"] += 1
        if trace is None and T >= 2400 and len(to) >= 10:      # a minute for the picture: the first life long enough
            trace = dict(speed=[int(x) for x in sm[:2400]], hops=[int(x) for x in to if x < 2400], inview=[int(x) for x in np.nonzero(v[:2400])[0][::4]])
    mins = frames * DT / 60.0
    sh = lambda a: [round(float(x), 3) for x in a / max(1.0, a.sum())]
    return dict(player_minutes=round(mins, 1), time_by_speed={k: sh(v_) for k, v_ in band.items()},
                travelling_share=round(float(band["travel"].sum() / max(1.0, band["all"].sum())), 3),
                hops_per_min=round(hops / max(1e-9, mins), 1),
                chains=dict(per_min=round(sum(1 for c in chains if c >= 2) / max(1e-9, mins), 2),
                            three_or_more_per_min=round(sum(1 for c in chains if c >= 3) / max(1e-9, mins), 2),
                            hops_in_chains_of_3=round(sum(c for c in chains if c >= 3) / max(1, hops), 3),
                            longest=int(max(chains)) if chains else 0),
                speed_at_hop=[dict(hop=n_ + 1, speed=int(np.mean(x)), n=len(x)) for n_, x in enumerate(hop_tr) if len(x) >= 20],
                speed_at_hop_all=[dict(hop=n_ + 1, speed=int(np.mean(x)), n=len(x)) for n_, x in enumerate(hop_sp) if len(x) >= 20],
                gain_per_hop=dict(median=round(float(np.median(gains)), 1) if gains else None,
                                  gained=round(float(np.mean(np.array(gains) > 5)), 3) if gains else None),
                at_400=dict(time_share=round(f400 / max(1, frames), 3), distance_share=round(dist400 / max(1e-9, dist), 3),
                            spells_per_min=round(len(spells) / max(1e-9, mins), 2),
                            spell_seconds=dict(median=round(float(np.median(spells)), 2) if spells else None,
                                               p90=round(float(np.percentile(spells, 90)), 2) if spells else None),
                            build_seconds_from_330=round(float(np.median(builds)), 2) if builds else None,
                            ended_by={k: round(v_ / max(1, sum(ends.values())), 3) for k, v_ in ends.items()}),
                trace=trace)


def play(job):
    """one map in this process: positions and enemy-in-view of his lives. mode "game": the network against the stand-in;
    "item": the network alone in item runs; labels (a movement teacher's run): a player alone in item runs who presses
    exactly its labels with his hands (tools/label_check.py's pupil)"""
    mp, policy, games, minutes, seed, sets, mode, labels = job
    os.environ.update(sets)
    if mode == "item" or labels:
        os.environ.update(RUNNER_P="0", COLLECT_FIGHT_P="0", ITEM_RUN_P="1.0", JUMP_RUN_P="0", JUMPS="1", JUMP_ALL="1", RULE_WALK="1", STACK_KEYS="0",
                          STYLE_P="0", PRO_ITEMS="1", RUN_TEACHER="1" if labels else "0", TEACH_KEYS_ONLY="0")
    sys.path.insert(0, SIM)
    import duel_env_ffa as E
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    teacher = os.path.join(ROOT, "data", "sim_runs", labels, "policy.npz") if labels else None
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=games, seed=seed, loadout="all", nav=nav_, close_p=1.0, teacher=teacher)
    pol = None
    if not labels:
        import test_suite as T
        pol = T.Policy(policy, seed=seed)
        pol.rng = np.random.default_rng(seed)
        # (B-226) his seats at the delays he was trained with (or --react-ms / --acquire-ms); the stand-in keeps his tracking
        # delay and the simulator's own acquire delay
        T.set_delays(E, env, [(np.arange(0, env.n, 2) if mode == "game" else np.arange(env.n),
                               float(sets.get("REACT_MS") or pol.react_ms), float(sets.get("ACQUIRE_MS") or pol.acquire_ms))])
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.kind_p, env.bot_p = (1.0, 0.0, 0.0, 0.0), 0.0
    n = env.n
    if mode == "game" and not labels:
        env.arena_stack, env.arena_sets = False, [(E.MG,)]
        env.stack_p = env.near_item_p = env.close_p = env.item_run_p = env.jump_run_p = 0.0
        env.runner_p = 1.0
        env.round_t[:] = 1e9
        obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
        env.round_len = env.arena_len = 1e9
        env.round_t[:] = 0.0
        me, od = np.arange(0, n, 2), np.arange(1, n, 2)
        env.script[od], env.sc_persona[od], env.script[me] = 3, E.NIGHTMARE, 0
    else:
        env.item_reward, env.intent_seek, env.item_loss, env.dmg_reward = 0.75, 1.0, 0.5, 0.005
        env.runner_p = 0.0
        env.round_t[:] = 1e9
        obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
        me = np.arange(n)
    base = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
    base[:, 0], base[:, 1], base[:, 3], base[:, 4] = 1, 1, len(E.TURN) // 2, len(E.PITCH) // 2
    h = pol.zeros(len(me)) if pol is not None else None
    frames = int(minutes * 60 / DT)
    P = np.zeros((frames, len(me), 3), np.float32)
    V = np.zeros((frames, len(me)), bool)
    A = np.zeros((frames, len(me)), bool)
    for t in range(frames):
        if labels:
            a = base.copy()
            lab = env.teach[:, :4]
            on = (env.run_k > 0) & (env.hp > 0)
            for c in range(4):
                a[:, c] = np.where(on & (lab[:, c] >= 0), lab[:, c], a[:, c])
        else:
            a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
            al, h = pol.act(obs[me], h)
            a[me, :al.shape[1]] = al
        obs, r, done, info = env.step(a)
        if pol is not None and mode != "game":
            h[np.asarray(done)[me] > 0] = 0.0
        P[t], V[t], A[t] = env.state[me, :3], np.asarray(env.visible)[me] & (mode == "game"), env.hp[me] > 0
    segs = []
    for i in range(len(me)):
        jump = np.concatenate([[False], np.linalg.norm(np.diff(P[:, i], axis=0), axis=1) > 400.0])     # a respawn (or a teleporter)
        cut = np.nonzero(jump | ~A[:, i])[0]
        edges = np.concatenate([[0], cut, [frames]])
        for x0, x1 in zip(edges[:-1], edges[1:]):
            if x1 - x0 > 40:
                segs.append((P[x0 + 1:x1, i].copy(), V[x0 + 1:x1, i].copy()))
    return mp, segs


def demo_segs(mp, limit):
    root = open(os.path.join(ROOT, "data", "demo_root.txt")).read().strip()
    segs = []
    for f in sorted(glob.glob(os.path.join(root, "sets_lite", mp, "*.npz")))[:limit]:
        d = np.load(f, allow_pickle=True)
        L, first = d["lite"], d["first"]
        pos, vis, alive = L[:, 5:8], L[:, 4] > 0.5, L[:, 0] > 0
        step = np.concatenate([[False], np.linalg.norm(np.diff(pos, axis=0), axis=1) > 400.0])
        cut = np.nonzero(first | step | ~alive)[0]
        edges = np.concatenate([[0], cut, [len(L)]])
        for x0, x1 in zip(edges[:-1], edges[1:]):
            if x1 - x0 > 40:
                segs.append((pos[x0 + 1:x1], vis[x0 + 1:x1]))
    return segs


def show(files):
    R = [json.load(open(f)) for f in files]
    names = [r["tag"] for r in R]
    w = max(22, max(len(n_) for n_ in names) + 2)
    row = lambda label, vals: print("{:46s}".format(label) + "".join("{:>{w}s}".format(str(v), w=w) for v in vals))
    row("", names)
    row("player-minutes", [r["player_minutes"] for r in R])
    row("travelling (no enemy in view), share of time", ["{:.0%}".format(r["travelling_share"]) for r in R])
    for part in ("travel", "fight"):
        for i, b in enumerate(BAND_NAMES):
            row("{}: {}".format("travelling" if part == "travel" else "fighting", b), ["{:.0%}".format(r["time_by_speed"][part][i]) for r in R])
    row("take-offs a minute", [r["hops_per_min"] for r in R])
    row("chains of three hops or more a minute", [r["chains"]["three_or_more_per_min"] for r in R])
    row("share of his hops in such chains", ["{:.0%}".format(r["chains"]["hops_in_chains_of_3"]) for r in R])
    for n_ in range(1, 7):
        row("speed at hop {} of a chain (no enemy in view)".format(n_), [next((str(x["speed"]) for x in r["speed_at_hop"] if x["hop"] == n_), "-") for r in R])
    row("hops that gained speed", ["{:.0%}".format(r["gain_per_hop"]["gained"]) if r["gain_per_hop"]["gained"] is not None else "-" for r in R])
    row("gain a hop (median)", [r["gain_per_hop"]["median"] for r in R])
    row("time at 400 or more", ["{:.1%}".format(r["at_400"]["time_share"]) for r in R])
    row("distance covered at 400 or more", ["{:.0%}".format(r["at_400"]["distance_share"]) for r in R])
    row("spells at 400 or more a minute", [r["at_400"]["spells_per_min"] for r in R])
    row("a spell's seconds (median, nine in ten under)", ["{}, {}".format(r["at_400"]["spell_seconds"]["median"], r["at_400"]["spell_seconds"]["p90"]) for r in R])
    row("seconds to build one from under 330", [r["at_400"]["build_seconds_from_330"] for r in R])
    for k, label in (("sudden", "ended by a sudden loss (wall, landing)"), ("fight", "ended with an enemy in view"), ("slowed", "ended by slowing down"), ("died", "ended by his death")):
        row(label, ["{:.0%}".format(r["at_400"]["ended_by"][k]) for r in R])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="")
    ap.add_argument("--demos", default="", help="maps (commas): the pros, from the light demo sets")
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld")
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--procs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=30, help="demos a map")
    ap.add_argument("--tag", default="")
    ap.add_argument("--mode", default="game", choices=("game", "item"), help="game: against the stand-in; item: alone in item runs")
    ap.add_argument("--labels", default="", help="a movement teacher's run: its pupil alone in item runs (no --policy)")
    ap.add_argument("--json", default="")
    ap.add_argument("--show", nargs="*", default=None)
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--react-ms", type=float, default=None, help="his tracking delay (default: the checkpoint's react_ms)")
    ap.add_argument("--acquire-ms", type=float, default=None, help="his delay before an enemy who has just come into view is noticed "
                                                                    "(default: the checkpoint's acquire_ms; B-226)")
    a = ap.parse_args()
    if a.show is not None:
        show(a.show)
        return
    if a.demos:
        maps = a.demos.split(",")
        segs = sum((demo_segs(m, a.limit) for m in maps), [])
        out = dict(tag=a.tag or "the pros", source="demos", maps=maps, **analyse(segs))
    else:
        if os.name == "nt":
            import ctypes
            k32_ = ctypes.windll.kernel32                         # (with ctypes' default types the handle is cut to 32 bits and the call fails silently)
            k32_.GetCurrentProcess.restype = ctypes.c_void_p
            k32_.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
            k32_.SetPriorityClass(k32_.GetCurrentProcess(), 0x4000)
        maps = a.map.split(",")
        sets = dict(SETS, **dict(x.split("=", 1) for x in a.set))
        for k_, v_ in (("REACT_MS", a.react_ms), ("ACQUIRE_MS", a.acquire_ms)):
            if v_ is not None:
                sets[k_] = str(v_)
        jobs = [(m, a.policy, a.games, a.minutes, 100 + i, sets, a.mode, a.labels) for i, m in enumerate(maps)]
        sys.path.insert(0, SIM)
        import pin                                           # (PIN_CORES: a pool worker on a processor of its own)
        with mp_.Pool(min(a.procs, len(jobs)), initializer=pin.pin_pool_worker) as pool:
            res = pool.map(play, jobs)
        segs = sum((s for _, s in res), [])
        out = dict(tag=a.tag or (a.labels + "'s pupil" if a.labels else os.path.basename(os.path.dirname(os.path.abspath(a.policy)))),
                   source=a.labels or a.policy, mode="item" if a.labels else a.mode, maps=maps, **analyse(segs))
    if a.json:
        json.dump(out, open(a.json, "w"))
    show_ = {k: v for k, v in out.items() if k != "trace"}
    print(json.dumps(show_)[:1500])


if __name__ == "__main__":
    main()
