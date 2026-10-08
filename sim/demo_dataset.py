"""Turn pro demos into training data for BobbyBones: per 25 ms frame, what he would have seen (the simulator's own
inputs, built from the demo's game state) and what the player did (keys and mouse, inferred from the recording).

    python sim/demo_dataset.py --map bloodrun                 # every demo in data/demos/<map>, all CPU cores
    python sim/demo_dataset.py --map bloodrun --limit 20      # a quick sample
    python sim/demo_dataset.py --check data/demo_sets/bloodrun   # how well the inferred keys reproduce the motion

Input:  <demo root>/demos/<map>/*.dm_91|dm_90|dm_73 (tools/fetch_demos.py), parsed on the fly with tools/demodump.
Output: <demo root>/sets/<map>/<demo>.npz (demo root: data/, or the folder named in data/demo_root.txt) with
    obs    (N, 311) float16   the network inputs of duel_env, for the followed player
    act    (N, 8)   int8      forward, strafe, vertical, turn bin, pitch bin, fire, weapon, walk (duel_env's actions)
    first  (N,)     bool      True where a new stretch starts (spawn, a cut to another player, a gap in time)
    state  (N, 9)   float32   position, velocity, yaw, pitch, on ground (for checks and for the atlas)
No player names are written.

What a demo does not contain and how it is filled in
  keys      Demos hold no key presses. Forward / strafe come from the game's own "movement direction" field (eight
            directions), and "no keys" from whether the speed changed beyond friction; jump from leaving the ground
            with upward speed; crouch from the eye height; fire from the firing flag; weapon switches from the
            weapon in hand. The check option reports how well these reproduce the recorded motion.
  mouse     The view change per frame, turned back into the commanded turn through the simulator's view inertia,
            then put into the nearest turn / pitch bin.
  enemy     Present only while the server sent him (roughly: while he could be seen). His health is not in the demo.
  sounds, hit feedback, round clock and score: left at "nothing heard / start of round" in this version.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

def demo_root():
    """where demos and the training data made from them live: the folder named in data/demo_root.txt (one line,
    for a big separate drive), else data/"""
    f = os.path.join(ROOT, "data", "demo_root.txt")
    if os.path.exists(f):
        p = open(f).read().strip()
        if p:
            return p
    return os.path.join(ROOT, "data")


# Quake Live weapon numbers -> simulator weapon names
QLW = {1: "g", 2: "mg", 3: "sg", 4: "gl", 5: "rl", 6: "lg", 7: "rg", 8: "pg", 14: "hmg"}
# movementDir -> (forward, strafe) in {-1, 0, 1}; strafe +1 = right
MDIR = {0: (1, 0), 1: (1, -1), 2: (0, -1), 3: (-1, -1), 4: (-1, 0), 5: (-1, 1), 6: (0, 1), 7: (1, 1)}
STAT_HEALTH, STAT_WEAPONS, STAT_ARMOR = 0, 3, 4
DT = 0.025


def stat_layout(d):
    """which stats slots hold the weapon bits and the armor: they differ between demo formats, so find them.
    Weapon bits: a slot that always has the gauntlet and machine gun bits (2 | 4) while alive. Armor: the other
    slot that moves in the 0..200 range."""
    st = d["stats"]
    alive = st[:, 0] > 0
    if alive.sum() < 100:
        return STAT_WEAPONS, STAT_ARMOR
    wslot, aslot = STAT_WEAPONS, STAT_ARMOR
    best = -1
    for k in range(1, 16):
        v = st[alive, k].astype(np.int64)
        share = ((v & 6) == 6).mean() if (v >= 0).all() and v.max() < 65536 else 0.0
        if share > 0.98 and len(np.unique(v)) > best and v.max() >= 6:
            wslot, best = k, len(np.unique(v))
    cands = [(len(np.unique(st[alive, k])), k) for k in range(1, 16)
             if k != wslot and st[alive, k].min() >= 0 and st[alive, k].max() <= 200 and len(np.unique(st[alive, k])) > 8]
    if cands:
        aslot = max(cands)[1]
    return wslot, aslot


def infer_actions(E, d, i0, i1, wslot):
    """actions for frames i0..i1-1 of one stretch (the action at frame t leads from t to t+1)"""
    P = __import__("demo_reader").PS
    ps = d["ps"]
    n = i1 - i0
    act = np.zeros((n, 8), np.int8)
    act[:, 0] = act[:, 1] = 1
    ang = d["angles"][i0:i1]
    vel = d["velocity"][i0:i1]
    ground = d["groundEntityNum"][i0:i1] != 1023
    yaw, pit = ang[:, 1], ang[:, 0]
    # ---- mouse: view change per frame -> commanded turn (undoing the simulator's view inertia) -> nearest bin
    dyaw = np.zeros(n, np.float32)
    dpit = np.zeros(n, np.float32)
    dyaw[:-1] = (np.diff(yaw) + 180.0) % 360.0 - 180.0
    dpit[:-1] = np.diff(pit)
    prev = np.zeros((n, 2), np.float32)
    prev[1:, 0], prev[1:, 1] = dyaw[:-1], dpit[:-1]
    mv = np.stack([np.clip(dyaw, -E.TURN_CAP, E.TURN_CAP), dpit], 1)
    cmd = (mv - E.MOUSE_SMOOTH * prev) / (1.0 - E.MOUSE_SMOOTH)
    fine = (mv - E.MOUSE_SMOOTH_FINE * prev) / (1.0 - E.MOUSE_SMOOTH_FINE)
    cmd = np.where(np.abs(fine) <= 1.0, fine, cmd)
    act[:, 3] = np.abs(cmd[:, :1] - E.TURN[None]).argmin(1)
    act[:, 4] = np.abs(cmd[:, 1:] - E.PITCH[None]).argmin(1)
    # ---- keys
    md = ps[i0:i1, P["movementDir"]].astype(np.int64)
    sp = np.hypot(vel[:, 0], vel[:, 1])
    dv = np.zeros(n, np.float32)
    dv[:-1] = np.linalg.norm(vel[1:, :2] - vel[:-1, :2], axis=1)
    # no keys: in the air the horizontal velocity does not change; on the ground it only decays by friction
    fr = np.zeros(n, np.float32)
    fr[:-1] = np.maximum(0.0, sp[:-1] - sp[1:])                # speed lost this frame
    # (in the air the keys are taken from the movement direction as it is: a held key that adds no speed at this
    # view angle still tells where the player was steering)
    still = ground & ((dv < np.maximum(1.0, 1.15 * 6.0 * DT * np.maximum(sp, 100.0))) & (fr > 0.0) | (sp < 5.0))
    for k in range(n):
        f, s = MDIR.get(int(md[k]) & 7, (0, 0))
        if still[k]:
            f, s = 0, 0
        act[k, 0], act[k, 1] = f + 1, s + 1
    # jump: leaves the ground with upward speed on the next frame
    up = np.zeros(n, bool)
    up[:-1] = ground[:-1] & ~ground[1:] & (vel[1:, 2] > 150)
    # a jump right on landing (bunny hop): in the air before and after, upward speed restored
    up[:-2] |= ~ground[:-2] & (vel[:-2, 2] < -50) & (vel[1:-1, 2] > 150)
    duck = ps[i0:i1, P["viewheight"]] < 20
    act[:, 2] = np.where(up, 1, np.where(duck, 2, 0))
    # fire: the firing flag (0x100) or the weapon in its firing state
    act[:, 5] = ((ps[i0:i1, P["eFlags"]].astype(np.int64) & 0x100) != 0) | (d["weaponstate"][i0:i1] == 3)
    # weapon: the frame the weapon in hand starts to change gets "switch to the next one"
    names = E.WEAPONS
    w = np.array([names.index(QLW.get(int(x), "mg")) for x in d["weapon"][i0:i1]], np.int64)
    held = w.copy()                                            # as the simulator shows it: switched at once
    k = 0
    while k < n:
        if d["weaponstate"][i0 + k] == 2:                      # dropping: find what comes up
            j = k
            while j < n and w[j] == w[k]:
                j += 1
            if j < n:
                act[k, 6] = 1 + w[j]
                held[k:j] = w[j]
            k = max(j, k + 1)
        else:
            k += 1
    # walk: on the ground, keys down, steady and slow
    act[:, 7] = ground & ~still & (sp > 100) & (sp < 180) & (dv < 4)
    return act, held, mv


def build_demo(E, env, binf, out, lite=False):
    import demo_reader as D
    d = D.load(binf)
    N = len(d["time"])
    if N < 800:
        return 0, 0
    t = d["time"]
    pos, vel, ang = d["origin"], d["velocity"], d["angles"]
    wslot, aslot = stat_layout(d)
    normal = int(np.bincount(d["pm_type"].clip(0, 15)).argmax())
    ok = (d["pm_type"] == normal) & (d["stats"][:, STAT_HEALTH] > 0)
    dtm = np.diff(t, prepend=t[0] - 25)
    brk = np.ones(N, bool)
    brk[1:] = (d["clientNum"][1:] != d["clientNum"][:-1]) | ~ok[1:] | ~ok[:-1] | (dtm[1:] != 25)
    names = E.WEAPONS
    obs_out, act_out, first_out, state_out = [], [], [], []
    lite_out = []
    item_near = {}
    i = 0
    while i < N:
        if not ok[i]:
            i += 1
            continue
        j = i + 1
        while j < N and not brk[j]:
            j += 1
        if j - i >= 80:                                         # stretches of two seconds or more
            act, held, mv = infer_actions(E, d, i, j, wslot)
            env.opp_hist = []
            env.vis_run[:] = 0
            env.acquired[:] = False
            env.seen_t[:] = 9.0
            env.known[:] = pos[i]
            env.snd_t[:] = 99.0
            env.fb[:] = 0.0
            env.frags_r[:] = 0
            env.dmg_life[:] = 0.0
            opp_last = np.array([pos[i][0], pos[i][1], pos[i][2], 0, 0, 0, 1.0, 0.0], np.float32)
            me = int(d["clientNum"][i])
            for k in range(i, j - 1):                           # the last frame has no "next" to infer an action from
                s = d["stats"][k]
                env.state[0] = [*pos[k], *vel[k], float(d["groundEntityNum"][k] != 1023), ang[k][1]]
                env.yaw[0], env.pitch[0] = ang[k][1], np.clip(ang[k][0], -89, 89)
                env.hp[0], env.armor[0] = s[STAT_HEALTH], s[aslot]
                bits = int(s[wslot])
                for q, nm in QLW.items():
                    env.has[0, names.index(nm)] = bool(bits & (1 << q))
                    env.ammo[0, names.index(nm)] = 0 if nm == "g" else max(0.0, float(d["ammo"][k][q]))
                env.weapon[0] = held[k - i]
                env.cool[0] = env.fire_cd[0] = max(0.0, float(d["ps"][k, D.PS["weaponTime"]]) / 1000.0)
                env.duck[0] = d["ps"][k, D.PS["viewheight"]] < 20
                env.mv[0] = mv[k - i - 1] if k > i else 0.0
                env.round_t[0] = ((k - i) * DT) % 120.0
                present = False
                for row in d["players"][k]:
                    if int(row[1]) != me:
                        opp_last = np.array([row[2], row[3], row[4], row[5], row[6], row[7], 1.0, row[9]], np.float32)
                        env.yaw[1], env.pitch[1] = row[9], row[8]
                        env.weapon[1] = names.index(QLW.get(int(row[11]), "mg"))
                        present = True
                        break
                env.state[1] = opp_last
                env.hp[1] = 100.0
                for it in d["items"][k]:
                    key = (round(float(it[2])), round(float(it[3])), round(float(it[4])))
                    idx = item_near.get(key)
                    if idx is None:
                        dd = np.linalg.norm(env.item_pos - np.array(key, np.float32), axis=1) if env.nI else np.array([1e9])
                        idx = item_near[key] = int(dd.argmin()) if dd.min() < 48 else -1
                    if idx >= 0:
                        env.item_up[0, idx] = (int(it[5]) & 0x80) == 0
                # sight: field of view, line of sight, and only while the server sent him
                eye = env._eye(env.state)
                to = env.state[1, :3] - eye[0]
                dist = float(np.linalg.norm(to)) + 1e-6
                yr, pr = np.radians(env.yaw[0]), np.radians(env.pitch[0])
                fd = np.array([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], np.float32)
                vis = present and float((to * fd).sum()) / dist > E.FOV_COS and dist < 4000 and \
                    bool(env._los(eye[:1], env.state[1:2, :3] + np.array([0, 0, 8.0], np.float32))[0])
                env.visible[:] = (vis, False)
                env.vis_run[0] = env.vis_run[0] + 1 if vis else 0
                acq = vis and env.vis_run[0] >= max(1, env.acquire_frames - env.react_frames)
                env.acquired[0] = acq
                if acq:
                    env.known[0] = env.state[1, :3]
                env.seen_t[0] = 0.0 if acq else env.seen_t[0] + DT
                if lite:                                    # the few facts tools/pro_tables.py counts, without the inputs
                    lite_out.append([env.hp[0], env.armor[0], env.weapon[0], act[k - i][5], float(acq), *pos[k], *env.state[1, :3],
                                     env.weapon[1], *env.has[0].astype(np.float32), *(env.ammo[0] > 0).astype(np.float32),
                                     ang[k][1], float(present)])
                    obs_out.append(0)
                else:
                    obs_out.append(env.observe()[0].astype(np.float16))
                act_out.append(act[k - i])
                first_out.append(k == i)
                state_out.append([*pos[k], *vel[k], ang[k][1], ang[k][0], float(d["groundEntityNum"][k] != 1023)])
        i = j
    if len(obs_out) < 400:
        return 0, N
    if lite:
        np.savez_compressed(out, lite=np.array(lite_out, np.float32), first=np.array(first_out, bool))
        return len(obs_out), N
    np.savez_compressed(out, obs=np.array(obs_out), act=np.array(act_out, np.int8), first=np.array(first_out, bool),
                        state=np.array(state_out, np.float32))
    return len(obs_out), N


def worker(args):
    mp, files, out_dir, seed, lite = args
    import duel_env as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=1, seed=seed,
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)))
    env.kind[:] = E.NORMAL
    env.script[:] = 0
    exe = os.path.join(ROOT, "tools", "demodump", "demodump.exe")
    tmp = tempfile.mkdtemp(prefix="demoset_")
    done = []
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        out = os.path.join(out_dir, stem + ".npz")
        if os.path.exists(out) or os.path.exists(out + ".skip"):
            continue
        b, js = os.path.join(tmp, "d.bin"), os.path.join(tmp, "d.json")
        try:
            subprocess.run([exe, f, b, js], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
            n, total = build_demo(E, env, b, out, lite)
        except Exception as e:                               # a broken demo must not stop the batch
            n, total = 0, 0
            print("failed {}: {!r}".format(stem[:50], e), flush=True)
        if n == 0:
            open(out + ".skip", "w").close()
        done.append((n, total))
        for p in (b, js):
            if os.path.exists(p):
                os.remove(p)
    return done


def check(folder, n_files=6):
    """Play the inferred keys through the simulator for one frame from each recorded state and compare the speed it
    predicts with the recorded next frame, against "no keys" as the baseline."""
    import duel_env as E
    from qsim import World
    mp = os.path.basename(os.path.normpath(folder))
    w = World(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n=2)
    rng = np.random.default_rng(0)
    files = sorted(glob.glob(os.path.join(folder, "*.npz")))
    files = [files[k] for k in rng.choice(len(files), min(n_files, len(files)), replace=False)]
    err = {"keys": [], "none": []}
    counts = np.zeros((3, 3))
    jumps = fire = frames = 0
    for f in files:
        z = np.load(f)
        st, act, first = z["state"], z["act"], z["first"]
        frames += len(act)
        jumps += int((act[:, 2] == 1).sum())
        fire += int(act[:, 5].sum())
        for a0, a1 in act[:, :2]:
            counts[a0, a1] += 1
        idx = rng.choice(len(act) - 1, min(1500, len(act) - 1), replace=False)
        for k in idx:
            if first[k + 1]:
                continue
            for name in ("keys", "none"):
                a = act[k] if name == "keys" else np.array([1, 1, 0, 0, 0, 0, 0, 0])
                key = E.WALK if a[7] else 127
                mv = np.zeros((2, 3), np.int8)
                mv[0] = ((int(a[0]) - 1) * key, (int(a[1]) - 1) * key, 127 if a[2] == 1 else -127 if a[2] == 2 else 0)
                w.reset(0, st[k, :3], st[k, 3:6], float(st[k, 6]))
                w.reset(1, st[k, :3] + np.array([0, 0, 500.0], np.float32), (0, 0, 0), 0.0)
                y1 = float(st[k + 1, 6])
                for fr, ms in zip((8 / 25, 16 / 25, 1.0), (8, 8, 9)):
                    yy = st[k, 6] + ((y1 - st[k, 6] + 180) % 360 - 180) * fr
                    w.step(mv, np.array([[st[k, 7], yy], [0, 0]], np.float32), ms)
                s = w.state()[0]
                err[name].append(float(np.linalg.norm(s[3:5] - st[k + 1, 3:5])))
    print("{} files, {} frames".format(len(files), frames))
    print("next-frame horizontal velocity error, units/s: inferred keys median {:.1f} mean {:.1f} | no keys median {:.1f} mean {:.1f}".format(
        np.median(err["keys"]), np.mean(err["keys"]), np.median(err["none"]), np.mean(err["none"])))
    print("jumps per minute {:.1f}, fire share {:.2f}".format(jumps / (frames * DT / 60), fire / frames))
    print("forward key (back / none / forward):", np.round(counts.sum(1) / counts.sum(), 2),
          " strafe key (left / none / right):", np.round(counts.sum(0) / counts.sum(), 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--check", default=None)
    ap.add_argument("--lite", action="store_true", help="only the facts tools/pro_tables.py counts (health, armor, weapons, enemy, fire), into sets_lite/<map>: much faster")
    a = ap.parse_args()
    if a.check:
        return check(a.check)
    import multiprocessing as mp_
    files = sorted(f for f in glob.glob(os.path.join(demo_root(), "demos", a.map, "*.dm_*")) if not f.endswith(".part"))
    if a.limit:
        files = files[:: max(1, len(files) // a.limit)][:a.limit]
    out_dir = os.path.join(demo_root(), "sets_lite" if a.lite else "sets", a.map)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    chunks = [(a.map, files[k::a.procs], out_dir, k, a.lite) for k in range(a.procs)]
    with mp_.Pool(a.procs) as pool:
        res = [x for r in pool.map(worker, chunks) for x in r]
    kept = sum(n for n, _ in res)
    total = sum(t for _, t in res)
    print("{}: {} demos, {} of {} frames kept ({:.0f}%), {:.1f} hours of play, {:.0f} s".format(
        a.map, len(res), kept, total, 100.0 * kept / max(1, total), kept * DT / 3600, time.time() - t0))


if __name__ == "__main__":
    main()
