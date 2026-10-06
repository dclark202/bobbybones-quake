"""The aim reflex test: what a player's hands and eyes can do, measured the same way for people and for BobbyBones.

People run `!reflex` on the play-test server (map testlab): four short rooms in the aim box, one kind of aim each.
  slow   (20 s, lightning gun): the target walks slowly from side to side. -> steadiness: aim error, hand jitter
  track  (40 s, lightning gun): it strafes, turning at random.   -> tracking lag, reaction to a turn, aim error, hit rate
  flick  (45 s, railgun): it jumps to a new place every 2-3 s.   -> reaction time, flick speed, time to the shot, hit rate
  rocket (30 s, rockets): it strafes, turning at random.         -> damage a rocket, rockets that hurt, how far ahead he aims

    python tools/reflex_report.py                        every session with reflex rooms in data/duellive/sessions
    python tools/reflex_report.py --sessions <folder>    another sessions folder
    python tools/reflex_report.py --bobby duel_gru_v5    also run a checkpoint through the same rooms in the simulator
                                                         (Anaconda Python; add --policy <file> for a specific one)

People are listed by an anonymous id (a salted hash made on the server). Results go to data/reflex/report.json.
In track, flick and rocket the target shoots back (machine gun) for the second 20 seconds: every measure is
taken for the calm half and for the half under fire, and the difference is what being shot at costs.
Frames are 25 ms apart, so single times are no finer than that; the medians over many events are.
"""
import argparse
import csv
import glob
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DT = 0.025
VIEW_H = 26.0
ROOMS = ("slow", "track", "flick", "rocket")


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def cut(d, a, b):
    """frames a..b of a room's arrays"""
    out = {k: v[a:b] for k, v in d.items() if k != "hops"}
    out["hops"] = [h - a for h in d["hops"] if a <= h < b]
    return out


def halves(room, d, split):
    """the room as (name, measures): the whole of it, or the calm half and the half under fire"""
    if split is None or split < 200 or split > len(d["yaw"]) - 200:
        return [(room, measure(room, d))]
    return [(room, measure(room, cut(d, 0, split))), (room + "_fire", measure(room, cut(d, split, len(d["yaw"]))))]


def measure(room, d):
    """d: per-frame arrays for one room. pos (subject), yaw, pitch, tpos (target), tvel, shot, dmg; hops (frame numbers)."""
    eye = d["pos"] + np.array([0, 0, VIEW_H])
    to = d["tpos"] + np.array([0, 0, 4.0]) - eye
    dist = np.linalg.norm(to, axis=1) + 1e-6
    bear = np.degrees(np.arctan2(to[:, 1], to[:, 0]))
    elev = -np.degrees(np.arctan2(to[:, 2], np.hypot(to[:, 0], to[:, 1])))
    ey, ep = wrap(bear - d["yaw"]), elev - d["pitch"]
    err = np.degrees(np.arccos(np.clip(np.cos(np.radians(ey)) * np.cos(np.radians(ep)), -1, 1)))
    half = np.degrees(np.arctan2(15.0, dist))                 # half the width of a player as seen from there
    on = (np.abs(ey) < half) & (np.abs(ep) < np.degrees(np.arctan2(28.0, dist)))
    vy = np.concatenate([[0.0], wrap(np.diff(d["yaw"]))])     # view turn per frame, degrees
    vp = np.concatenate([[0.0], np.diff(d["pitch"])])
    vb = np.concatenate([[0.0], wrap(np.diff(bear))])         # how the direction to the target changes per frame
    sm = lambda v, k=5: np.convolve(v, np.ones(k) / k, mode="same")          # noqa: E731
    own = np.concatenate([[0.0], np.linalg.norm(np.diff(d["pos"][:, :2], axis=0), axis=1)]) / DT
    out = dict(frames=int(len(err)), distance=round(float(np.median(dist))), own_speed=round(float(np.median(own))))
    shots = int(d["shot"].sum())
    if room in ("slow", "track"):
        k = slice(int(2.0 / DT), None)                        # the first two seconds are for finding the target
        out.update(aim_error_deg=round(float(np.median(err[k])), 2), on_target=round(float(np.mean(on[k])), 3),
                   damage_per_s=round(float(d["dmg"][k].sum() / max(1, len(err[k])) / DT), 1))
    if room == "slow":                                        # view movement that the target's movement does not explain
        k = slice(int(2.0 / DT), None)
        out["jitter_deg_per_frame"] = round(float(np.sqrt(np.mean((vy[k] - sm(vb)[k]) ** 2 + vp[k] ** 2))), 3)
    if room == "track":
        # Good players aim by moving as much as with the mouse, so the view's own turning says little. What counts
        # is the gap between crosshair and target, however it is closed. The crosshair trails the target's own
        # sideways movement: gap = lag x how fast the target moves across the view. The lag is that slope.
        k0 = int(2.0 / DT)
        nxt = np.vstack([d["tpos"][1:], d["tpos"][-1:]]) + np.array([0, 0, 4.0]) - eye       # target one frame on, eye held
        w_t = wrap(np.degrees(np.arctan2(nxt[:, 1], nxt[:, 0])) - bear) / DT                   # degrees a second, his doing only
        w_t = sm(w_t, 3)
        e_, w_ = ey[k0:], w_t[k0:]
        ok = np.abs(w_) < 200                                # (not the frames where the target is put somewhere new)
        out["tracking_lag_ms"] = round(float((e_[ok] * w_[ok]).sum() / max(1e-6, (w_[ok] ** 2).sum()) * 1000))
        # turns: the target reverses; the gap then grows on the new side until the player has caught on
        sgn = np.sign(np.where(np.abs(w_t) > 8.0, w_t, 0.0))
        turns, last = [], 0.0
        for i in range(k0, len(sgn) - 30):
            if sgn[i] != 0 and last != 0 and sgn[i] != last and (sgn[i + 1:i + 6] == sgn[i]).all():
                g = sm(ey, 3)[i:i + 24] * sgn[i]
                turns.append(int(np.argmax(g)) * DT * 1000)
            if sgn[i] != 0:
                last = sgn[i]
        out["turn_reaction_ms"] = round(float(np.median(turns))) if turns else None
        out["turns"] = len(turns)
    if room == "flick":
        react, t_on, t_shot, peak, hit, size = [], [], [], [], [], []
        hops = [h for h in d["hops"] if h + 5 < len(err)]
        for n_, h in enumerate(hops):
            end = min(len(err), hops[n_ + 1] if n_ + 1 < len(hops) else len(err), h + int(1.8 / DT))
            sp = np.hypot(vy[h:end], vp[h:end])
            size.append(float(err[min(h + 1, len(err) - 1)]))
            e0 = float(err[min(h + 1, len(err) - 1)])         # he is on his way to the new place:
            gap = err[h + 1:end]                              # ... a third of the way, and staying there
            mv = np.nonzero((gap[:-1] < 0.67 * e0) & (gap[1:] < 0.67 * e0))[0]
            if len(mv) and e0 > 3.0:
                react.append((mv[0] + 1) * DT * 1000)
            o_ = np.nonzero(on[h + 1:end])[0]
            if len(o_):
                t_on.append((o_[0] + 1) * DT * 1000)
            peak.append(float(sp.max()) / DT)
            s_ = np.nonzero(d["shot"][h + 1:end])[0]
            if len(s_):
                t_shot.append((s_[0] + 1) * DT * 1000)
                f = h + 1 + s_[0]
                hit.append(bool(d["dmg"][f:f + 5].sum() > 0))
        med = lambda v: round(float(np.median(v))) if len(v) else None     # noqa: E731
        out.update(flicks=len(hops), flick_size_deg=round(float(np.median(size)), 1) if size else None,
                   reaction_ms=med(react), time_on_target_ms=med(t_on), time_to_shot_ms=med(t_shot),
                   peak_speed_deg_per_s=med(peak), first_shot_hits=round(float(np.mean(hit)), 3) if hit else None,
                   reached_target=round(len(t_on) / max(1, len(hops)), 3))
    if room == "rocket":
        sh = np.nonzero(d["shot"])[0]
        lead = -ey[sh] * np.sign(sm(vb)[sh])                  # positive: the crosshair is ahead of the target's movement
        out.update(damage_per_rocket=round(float(d["dmg"].sum() / max(1, shots)), 1),
                   rockets_that_hurt=round(float((d["dmg"] > 0).sum() / max(1, shots)), 3),
                   lead_deg=round(float(np.median(lead)), 2) if len(sh) else None,
                   aim_below_centre_deg=round(float(-np.median(ep[sh])), 2) if len(sh) else None)
    out["shots"] = shots
    return out


# ---------------------------------------------------------------- people: the play-test server's session logs
def sessions(folder):
    res = {}
    for sd in sorted(glob.glob(os.path.join(folder, "*"))):
        ev_p, fr_p = os.path.join(sd, "events.jsonl"), os.path.join(sd, "frames.csv")
        if not (os.path.exists(ev_p) and os.path.exists(fr_p)):
            continue
        ev = [json.loads(l) for l in open(ev_p) if l.strip()]
        if not any(e.get("event") == "room_start" and str(e.get("room", "")).startswith("reflex/") for e in ev):
            continue
        rows = list(csv.DictReader(open(fr_p)))
        tags = np.array([r["drill"] for r in rows])
        t = np.array([float(r["t"]) for r in rows])
        subject, is_bot = "unknown", False
        for e in ev:
            if e.get("event") == "room_start" and str(e.get("room", "")).startswith("reflex/"):
                subject, is_bot = e.get("subject", "unknown"), bool(e.get("subject_is_bot"))
        hits = [(e["t"], e["dmg"]) for e in ev if e.get("event") == "hit" and e.get("victim") == "bobby"]
        hop_t = [e["frame_t"] for e in ev if e.get("event") == "hop"]
        fire_t = [e["frame_t"] for e in ev if e.get("event") == "fire_phase"]
        for room in ROOMS:
            idx = np.nonzero(tags == "room:reflex/" + room)[0]
            if len(idx) < 200:
                continue
            # several runs of the room in one session: split where the frame numbers jump
            for part in np.split(idx, np.nonzero(np.diff(idx) > 40)[0] + 1):
                if len(part) < 200:
                    continue
                R = [rows[i] for i in part]
                f = lambda c: np.array([float(r[c]) for r in R])             # noqa: E731
                tt = t[part]
                ammo = f({"flick": "o_ammo_rg", "rocket": "o_ammo_rl"}.get(room, "o_ammo_lg"))
                d = dict(pos=np.stack([f("o_x"), f("o_y"), f("o_z")], 1), yaw=f("o_yaw"), pitch=f("o_pitch"),
                         tpos=np.stack([f("b_x"), f("b_y"), f("b_z")], 1),
                         shot=np.concatenate([[False], (np.diff(ammo) < 0) & (np.diff(ammo) > -5)]),
                         dmg=np.zeros(len(part)), hops=[])
                for ht, dm in hits:
                    if tt[0] <= ht <= tt[-1] + 0.2:
                        d["dmg"][min(len(tt) - 1, int(np.searchsorted(tt, ht)))] += dm
                d["hops"] = [int(np.searchsorted(tt, h)) for h in hop_t if tt[0] <= h <= tt[-1]]
                key = ("game bot " if is_bot else "player ") + subject
                sp = [int(np.searchsorted(tt, f_)) for f_ in fire_t if tt[0] <= f_ <= tt[-1]]
                for name, m_ in halves(room, d, sp[0] if sp else None):
                    res.setdefault(key, {}).setdefault(name, []).append(m_)
    return res


# ---------------------------------------------------------------- BobbyBones: the same rooms in the simulator
def bobby(run, policy=None, repeats=4, react_ms=None, percept=None, flinch=None):
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import duel_env as E
    import test_suite as T
    pol = T.Policy(policy or os.path.join(ROOT, "data", "sim_runs", run, "policy.pt"), seed=5)
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", "testlab.bsp"), n_matches=repeats, seed=21, loadout="all")
    env.react_frames = round((react_ms or pol.react_ms) / 25)
    env.no_walk, env.inf_ammo = True, True
    if percept is not None:
        env.percept_sigma = percept
    if flinch is not None:
        E.FLINCH_PER_DMG = flinch
    A = env.lab["aim"]
    rng = np.random.default_rng(3)
    subj = np.arange(0, env.n, 2)
    tgt = subj + 1
    res = {}
    plain = env._script_actions
    for room, secs, wpn in (("slow", 20, E.LG), ("track", 40, E.LG), ("flick", 40, E.RG), ("rocket", 40, E.RL)):
        env.lab_aim_len = secs + 5.0
        env.lab_force = dict(kind=E.AIM, weapon=wpn, where="aim", jump=False)
        env.sc_style = 1 if room == "flick" else 0
        tick = [0]
        firing = [False]                                         # second half of the room: the target shoots back
        near = room != "flick"                                   # lightning and rockets: the nearer target zone
        z = A["zone_lg"] if (near and "zone_lg" in A) else A["zone"]

        def script(idx, room=room):
            out = plain(idx)
            if room == "slow":                                   # a slow walk from side to side, turning every 2.5 s
                tick[0] += 1
                out[:, 0], out[:, 2] = 1, 0
                out[:, 1] = (2 if int(tick[0] * DT / 2.5) % 2 else 0) if tick[0] % 3 == 0 else 1
            if room in ("track", "rocket"):                      # sideways only, turning at random moments
                p_ = env.state[idx, :3]                          # (near the edge of its zone it walks back in, as always)
                inside = (z[0] + 120 <= p_[:, 0]) & (p_[:, 0] <= z[2] - 120) & (z[1] + 120 <= p_[:, 1]) & (p_[:, 1] <= z[3] - 120)
                out[:, 0] = np.where(inside, 1, out[:, 0])
                still_ = (out[:, 1] == 1) & inside
                if still_.any():
                    env.sc_dir[idx[still_]] = rng.choice([-1, 1], int(still_.sum()))
                    out[still_, 1] = env.sc_dir[idx[still_]] + 1
            if firing[0]:                                        # machine gun at the subject, not every bullet on him
                s_ = env.state
                me, him = idx, idx - 1
                to = s_[him, :3] - s_[me, :3]
                ey = (np.degrees(np.arctan2(to[:, 1], to[:, 0])) - env.yaw[me] + 180.0) % 360.0 - 180.0 + rng.normal(0, 1.2, len(me))
                ep = -np.degrees(np.arctan2(to[:, 2], np.hypot(to[:, 0], to[:, 1]) + 1e-6)) - env.pitch[me] + rng.normal(0, 1.2, len(me))
                out[:, 3] = np.abs(E.TURN[None, :] - np.clip(ey, -20, 20)[:, None]).argmin(1)
                out[:, 4] = np.abs(E.PITCH[None, :] - np.clip(ep, -10, 10)[:, None]).argmin(1)
                out[:, 5] = 1
                out[:, 6] = np.where(env.weapon[me] != E.MG, E.MG + 1, 0)
                env.has[me, E.MG], env.ammo[me, E.MG] = True, 100
            return out
        env._script_actions = script
        env.round_t[:] = 1e9
        h = pol.zeros(env.n)
        obs, _, done, _ = env.step(np.zeros((env.n, len(pol.dims)), np.int64))
        for i in tgt:                                            # the target faces the subject: its strafe is sideways to him
            s = env.state
            home = np.array(A["target_lg"] if (near and "target_lg" in A) else A["target"], np.float32)
            env.lab_zone[i // 2], env.lab_home[i // 2] = z, home
            yaw = math.degrees(math.atan2(s[i - 1, 1] - home[1], s[i - 1, 0] - home[0]))
            env.w.reset(int(i), (float(home[0]), float(home[1]), float(home[2]) + 2.0), (0, 0, 0), yaw)
            env.yaw[i] = yaw
        env.state = env.w.state()
        n_fr = int(secs / DT)
        rec = {int(i): dict(pos=[], yaw=[], pitch=[], tpos=[], shot=[], dmg=[], hops=[]) for i in subj}
        hop_t = np.full(len(subj), 1.5)

        for t in range(n_fr):
            firing[0] = room != "slow" and t >= n_fr // 2
            if room == "flick":
                for k, i in enumerate(subj):
                    if t * DT >= hop_t[k]:
                        s = env.state
                        for _ in range(20):
                            p = np.array([rng.uniform(z[0] + 140, z[2] - 140), rng.uniform(z[1] + 140, z[3] - 140), s[i + 1, 2]])
                            if math.hypot(p[0] - s[i + 1, 0], p[1] - s[i + 1, 1]) > 150:
                                break
                        env.w.reset(int(i + 1), (float(p[0]), float(p[1]), float(p[2]) + 1.0), (0, 0, 0),
                                    math.degrees(math.atan2(s[i, 1] - p[1], s[i, 0] - p[0])))
                        hop_t[k] = t * DT + rng.uniform(1.8, 3.2)
                        rec[int(i)]["hops"].append(t)
                env.state = env.w.state()
            s = env.state
            for i in subj:
                r = rec[int(i)]
                r["pos"].append(s[i, :3].copy()), r["yaw"].append(float(env.yaw[i])), r["pitch"].append(float(env.pitch[i]))
                r["tpos"].append(s[i + 1, :3].copy())
            act, h = pol.act(obs, h)
            if room == "flick":
                pin = env.state[tgt, :3].copy()
            obs, _, done, _ = env.step(act)
            h[done] = 0.0
            if room == "flick":                                  # the standing target is not pushed around by the hits
                for k_, i in enumerate(tgt):
                    env.w.reset(int(i), tuple(float(v) for v in pin[k_]), (0, 0, 0), float(env.yaw[i]))
                env.state = env.w.state()
            for i in subj:
                rec[int(i)]["shot"].append(bool(env.fire_q[i]))
                rec[int(i)]["dmg"].append(float(env.fb[i, 0]) * 100.0)
            env.hp[tgt], env.armor[tgt] = 200.0, 0.0             # the target does not die
            env.hp[subj], env.armor[subj] = 200.0, 0.0           # nor does he
        for i in subj:
            r = rec[int(i)]
            d = dict(pos=np.array(r["pos"]), yaw=np.array(r["yaw"]), pitch=np.array(r["pitch"]), tpos=np.array(r["tpos"]),
                     shot=np.array(r["shot"]), dmg=np.array(r["dmg"]), hops=r["hops"])
            for name, m_ in halves(room, d, n_fr // 2 if room != "slow" else None):
                res.setdefault(name, []).append(m_)
    env._script_actions = plain
    return "BobbyBones {} ({:.0f} min)".format(run, pol.minutes), res


def mean_of(runs):
    out = {}
    for k in runs[0]:
        v = [r[k] for r in runs if r.get(k) is not None]
        out[k] = round(float(np.mean(v)), 3) if v else None
    out["runs"] = len(runs)
    return out


LINES = (("slow", "own_speed", "Slow target: his own speed"),
         ("slow", "aim_error_deg", "Slow target: aim error (degrees)"),
         ("slow", "jitter_deg_per_frame", "Slow target: hand jitter (degrees a frame)"),
         ("slow", "on_target", "Slow target: share of time on it"),
         ("track", "aim_error_deg", "Strafing target: aim error (degrees)"),
         ("track", "on_target", "Strafing target: share of time on it"),
         ("track", "tracking_lag_ms", "Strafing target: crosshair trails it by (ms)"),
         ("track", "turn_reaction_ms", "Strafing target: catches a turn after (ms)"),
         ("track", "damage_per_s", "Strafing target: lightning damage a second"),
         ("flick", "reaction_ms", "Jumping target: a third of the way there after (ms)"),
         ("flick", "time_on_target_ms", "Jumping target: on it after (ms)"),
         ("flick", "time_to_shot_ms", "Jumping target: shot after (ms)"),
         ("flick", "peak_speed_deg_per_s", "Jumping target: fastest turn (degrees a second)"),
         ("flick", "first_shot_hits", "Jumping target: first shot hits"),
         ("flick", "flick_size_deg", "Jumping target: size of the jump (degrees)"),
         ("rocket", "damage_per_rocket", "Rockets at a strafing target: damage a rocket"),
         ("rocket", "rockets_that_hurt", "Rockets: share that hurt the target"),
         ("rocket", "lead_deg", "Rockets: aims ahead of the target by (degrees)"),
         ("rocket", "aim_below_centre_deg", "Rockets: aims below his middle by (degrees)"))


FIRE = (("track", "aim_error_deg", "Strafing target: aim error (degrees)"),
        ("track", "on_target", "Strafing target: share of time on it"),
        ("track", "tracking_lag_ms", "Strafing target: crosshair trails it by (ms)"),
        ("track", "damage_per_s", "Strafing target: lightning damage a second"),
        ("flick", "reaction_ms", "Jumping target: a third of the way there after (ms)"),
        ("flick", "time_on_target_ms", "Jumping target: on it after (ms)"),
        ("flick", "first_shot_hits", "Jumping target: first shot hits"),
        ("rocket", "rockets_that_hurt", "Rockets: share that hurt the target"),
        ("rocket", "damage_per_rocket", "Rockets: damage a rocket"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", default=os.path.join(ROOT, "data", "duellive", "sessions"))
    ap.add_argument("--bobby", default="", help="run name: also measure this checkpoint in the simulator")
    ap.add_argument("--policy", default=None)
    ap.add_argument("--percept", type=float, default=None, help="measure him with this error on the seen direction (degrees)")
    ap.add_argument("--flinch", type=float, default=None, help="measure him with this flinch (degrees per point of damage)")
    ap.add_argument("--last", action="store_true", help="people: only each player's latest run of each room (default: the mean of all)")
    ap.add_argument("--react-ms", type=float, default=None, help="measure him with this tracking delay (default: the one he trained with)")
    a = ap.parse_args()
    table = {}
    for who, rooms in sessions(a.sessions).items():
        table[who] = {room: mean_of(runs[-1:] if a.last else runs) for room, runs in rooms.items()}
    if a.bobby:
        name, rooms = bobby(a.bobby, a.policy, react_ms=a.react_ms, percept=a.percept, flinch=a.flinch)
        table[name] = {room: mean_of(runs) for room, runs in rooms.items()}
    if not table:
        print("no reflex rooms found in", a.sessions)
        return
    people = [w for w in table if w.startswith("player ")]
    if len(people) > 1:                                       # the middle of the people measured so far
        table["people, median of {}".format(len(people))] = {
            room: {k: (round(float(np.median([table[w][room][k] for w in people if room in table[w] and table[w][room].get(k) is not None])), 3)
                       if any(room in table[w] and table[w][room].get(k) is not None for w in people) else None)
                   for _, k, _ in [x for x in LINES if x[0] == room.replace("_fire", "")]}
            for room in ROOMS + tuple(r_ + "_fire" for r_ in ROOMS[1:])}
    bm = os.path.join(ROOT, "docs", "reflex_benchmark.json")       # what his limits are being set to reach
    if os.path.exists(bm):
        table["benchmark"] = json.load(open(bm))["target"]
    cols = list(table)
    print("{:<50}".format("") + "".join("{:>26}".format(c[:25]) for c in cols))
    for room, key, label in LINES:
        print("{:<50}".format(label) + "".join("{:>26}".format(str(table[c].get(room, {}).get(key, "-"))) for c in cols))
    print()
    print("{:<50}".format("UNDER FIRE (second half), and the change from calm"))
    for room, key, label in FIRE:
        cells = []
        for c in cols:
            a_, b_ = table[c].get(room, {}).get(key), table[c].get(room + "_fire", {}).get(key)
            cells.append("-" if a_ is None or b_ is None else "{:g} ({:+.0f}%)".format(b_, 100.0 * (b_ - a_) / a_ if a_ else 0.0))
        print("{:<50}".format(label) + "".join("{:>26}".format(v) for v in cells))
    print("{:<50}".format("runs (slow / track / flick / rocket)") + "".join(
        "{:>26}".format(" / ".join(str(table[c].get(r, {}).get("runs", 0)) for r in ROOMS)) for c in cols))
    os.makedirs(os.path.join(ROOT, "data", "reflex"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "reflex", "report.json"), "w") as f:
        json.dump(table, f, indent=1)


if __name__ == "__main__":
    main()
