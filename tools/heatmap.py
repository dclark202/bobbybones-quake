"""Where he goes and what he takes: a few minutes of self-play on arena1 in the simulator, drawn as a heat map of his
positions (top view), with the items, his deaths, and a table of the items: pickups per player-minute, share of the
time each one lies there untaken, mean time it lies before someone takes it.

    python tools/heatmap.py --run duel_gru_v7 [--group 3] [--minutes 4] [--out videos/heat.png]   (Anaconda Python)

Held positions show as hot spots; a player who wanders or hides shows as an even smear or one bright dot.
"""
import argparse
import importlib
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import test_suite as T               # noqa: E402

CELL = 32


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--policy", default=None)
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--group", type=int, default=3)
    ap.add_argument("--groups", type=int, default=8, help="groups played at once")
    ap.add_argument("--map", default="arena1")
    ap.add_argument("--minutes", type=float, default=4.0, help="minutes of play per group")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    E = importlib.import_module(a.env)
    pol = T.Policy(a.policy or os.path.join(ROOT, "data", "sim_runs", a.run, "policy.pt"), seed=7)
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=a.groups, seed=11, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None, **(dict(group=a.group) if a.group != 2 else {}))
    env.react_frames = round(pol.react_ms / 25)
    if os.environ.get("ARENA_STACK", "0") == "0":
        env.arena_stack = False
    sets = os.environ.get("ARENA_SETS", "mg;rl;rg;lg;rl,rg;rl,lg;rg,lg;rl,rg,lg")
    env.arena_sets = [tuple(E.WEAPONS.index(x) for x in s_.split(",")) for s_ in sets.split(";")]
    env.arena_len = 180.0
    env.lab_force = dict(kind=E.NORMAL, arena=3)
    env.round_t[:] = 1e9
    h = pol.zeros(env.n)
    nin = len(pol.mean)
    obs, _, done, _ = env.step(np.zeros((env.n, len(pol.dims)), np.int64))
    lo, hi = env.lo.copy(), env.hi.copy()
    dims = (np.ceil((hi[:2] - lo[:2]) / CELL).astype(int) + 1)
    heat = np.zeros((dims[1], dims[0]), np.float64)
    deaths = []
    nI = len(env.item_def)
    up_frames = np.zeros(nI)
    taken = np.zeros(nI)
    steps = int(a.minutes * 60 / E.DT)
    for t in range(steps):
        s = env.state
        alive = env.hp > 0
        cx = np.clip(((s[:, 0] - lo[0]) / CELL).astype(int), 0, dims[0] - 1)
        cy = np.clip(((s[:, 1] - lo[1]) / CELL).astype(int), 0, dims[1] - 1)
        np.add.at(heat, (cy[alive], cx[alive]), 1.0)
        was_up = env.item_up.copy()
        act, h = pol.act(obs[:, :nin], h)
        obs, r, done, info = env.step(act)
        h[done] = 0.0
        for e in info.get("events", []) if isinstance(info, dict) else []:
            v = e["victim"]
            deaths.append((float(s[v, 0]), float(s[v, 1]), e["killer"] >= 0 and e["killer"] != v))
        up_frames += env.item_up.sum(0)
        gone = was_up & ~env.item_up                           # taken this frame
        taken += gone.sum(0)
        if t and t % int(60 / E.DT) == 0:
            print("  {:.0f} min".format(t * E.DT / 60), flush=True)
    # the lay time: how long each item had been up when taken (the simulator keeps that in item_up_t)
    pm = a.groups * a.group * a.minutes                        # player-minutes
    rows = []
    for k, d in enumerate(env.item_def):
        kind, val, resp, cap, lab = d
        name = {"MH": "mega", "RA": "red armor"}.get(lab) or (E.WEAPONS[int(val)] if kind == "wp" else "{}{}".format("+", int(val)) if kind in ("hp", "ar") else kind)
        rows.append((name, taken[k] / pm, up_frames[k] / (a.groups * steps)))
    big = {k_: v for k_, v in zip(("mega", "red armor"), (env.stats["big_wait"] / np.maximum(1, env.stats["big_taken"])))}
    print("items ({:.0f} player-minutes, groups of {}):".format(pm, a.group))
    print("  {:14s} {:>12s} {:>10s} {:>12s}".format("item", "per pl-min", "lying", "mean lay s"))
    for name, rate, share in rows:
        print("  {:14s} {:12.3f} {:9.0%} {:>12s}".format(name, rate, share, "{:.0f}".format(big[name]) if name in big else ""))
    void = sum(1 for d_ in deaths if not d_[2])
    print("deaths {} ({} by hazards or own hand), per player-min {:.2f}".format(len(deaths), void, len(deaths) / pm))
    # share of time in the top cells: how concentrated he is
    flat = np.sort(heat.ravel())[::-1]
    tot = flat.sum()
    k10 = int(np.searchsorted(np.cumsum(flat), 0.5 * tot)) + 1
    print("half of his time is spent in {} cells of {} x {} units ({:.0%} of the cells he visited)".format(
        k10, CELL, CELL, k10 / max(1, (heat > 0).sum())))
    np.save(os.path.splitext(a.out or os.path.join(ROOT, "videos", "{}_{:04d}".format(a.run, int(pol.minutes)), "heat_{}.png".format(a.map)))[0] + ".npy", heat)
    # draw: S pixels per cell, a linear ramp black -> red -> yellow -> white, capped at the 98th busiest cell
    S = 8
    cap = max(1e-9, np.percentile(heat[heat > 0], 98)) if (heat > 0).any() else 1.0
    hm = np.clip(heat / cap, 0, 1)
    col = np.stack([np.clip(hm * 3, 0, 1), np.clip(hm * 3 - 1, 0, 1), np.clip(hm * 3 - 2, 0, 1)], 2)
    col = (col * 255).astype(np.uint8)
    col[heat == 0] = (18, 18, 24)
    if env.route is not None:                                  # the walkable floor, faint
        nd = env.route.nodes
        cx = np.clip(((nd[:, 0] - lo[0]) / CELL).astype(int), 0, dims[0] - 1)
        cy = np.clip(((nd[:, 1] - lo[1]) / CELL).astype(int), 0, dims[1] - 1)
        floor = np.zeros_like(heat, bool)
        floor[cy, cx] = True
        col[floor & (heat == 0)] = (44, 46, 58)
    img = np.kron(col, np.ones((S, S, 1), np.uint8))[::-1]      # y up
    im = Image.fromarray(np.ascontiguousarray(img))
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arialbd.ttf", 16)
    except OSError:
        font = ImageFont.load_default()

    def px(x, y):
        return ((x - lo[0]) / CELL * S, (dims[1] - (y - lo[1]) / CELL) * S)
    for x, y, byfoe in deaths:
        X, Y = px(x, y)
        d.ellipse([X - 3, Y - 3, X + 3, Y + 3], outline=(255, 255, 255) if byfoe else (120, 160, 255))
    for k, dfn in enumerate(env.item_def):
        kind, val, resp, cap, lab = dfn
        name = {"MH": "MEGA", "RA": "RED"}.get(lab) or (E.WEAPONS[int(val)].upper() if kind == "wp" else "+{}".format(int(val)) if kind in ("hp", "ar") else "")
        if not name:
            continue
        X, Y = px(env.item_pos[k][0], env.item_pos[k][1])
        d.rectangle([X - 7, Y - 7, X + 7, Y + 7], outline=(90, 255, 120), width=2)
        d.text((X + 10, Y - 9), name, fill=(90, 255, 120), font=font)
    d.text((6, 4), "{}  {:.0f} min  groups of {}  (white: killed, blue: fell or own hand)".format(a.run, pol.minutes, a.group),
           fill=(230, 230, 230), font=font)
    out = a.out or os.path.join(ROOT, "videos", "{}_{:04d}".format(a.run, int(pol.minutes)), "heat_{}.png".format(a.map))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out)
    print("->", out)


if __name__ == "__main__":
    main()
