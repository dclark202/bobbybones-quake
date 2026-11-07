"""The measures of docs/design/CYPHER.md (owner, 2026-11-06: "Go ahead and start the checks"): a network's self-play games played
exactly as the checks play them (tools/duel_eval.py's play, today's code; tools/run/panel.py's settings for the run; 125 / 225 ms;
whole games with overtime; seats swapped every second job), every frame recorded, and the tables read from the records beside the
pros' (data/sim_runs/judge/pro_rows: tools/run/pro_judge_rows.py; sim/pro_moments: tools/pro_moments.py).

    python tools/run/cypher_measure.py check --run duel_gru_1_7a --policy <pt> --cmd docs/runs/1.7/1.7a/train.cmd
    python tools/run/cypher_measure.py sim   --run duel_gru_1_7a --policy <pt> --out <dir> [--games 8] [--procs 2] [--par 6]
    python tools/run/cypher_measure.py stack <dir>     (B-304: fights by the stack ratio, his weapon by the fight's phase; B-306's ledger)
    python tools/run/cypher_measure.py items <dir>     (B-307: how long the mega and the armors lie, who takes them; B-310: the starts)
    python tools/run/cypher_measure.py check <dir> [--update N] [--out <jsonl>]   (1.7b: the summaries a check's games wrote with CY_REC:
                                                       the learner's (side 0) and the control's (side 1) fights by the stack ratio, the
                                                       big items' times, the trade bonus; one line into --out)

What a record holds (one npz a job, <dir>/rec_<map>_<k>.npz), every frame of the game, every seat (seat 2m and 2m + 1 are match m):
  hp, ar (health, armor), alive, weapon (in hand), vis (he has the enemy in view: env.visible), pos (float16), dealt (damage he
  dealt this frame: the rise of env.dmg_life), up (the match's mega, red and yellow armors: there or not, columns `big`), kills
  (t, victim, killer), side (0: the network under test, 1: its opponent; in self-play both are the same network).
Nothing here touches a run: it reads a save and plays it on the cores it is started on."""
import argparse
import glob
import json
import multiprocessing as mp_
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "sim"))
SR = os.path.join(ROOT, "data", "sim_runs")
MAPS = ["bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure"]
BIG = ("MH", "RA", "YA")
_REC = {}


def _recorder(E):
    """wraps E.DuelEnv.step once: every step's state kept in _REC (tools/aim2_measure.py's way)"""
    if getattr(E.DuelEnv, "_cy_rec", False):
        return
    step0 = E.DuelEnv.step

    def step(self, a):
        out = step0(self, a)
        R = _REC.setdefault("R", {k: [] for k in ("hp", "ar", "alive", "weapon", "vis", "pos", "dealt", "up")})
        if "big" not in _REC:
            _REC["big"] = [k for k, d in enumerate(self.item_def) if d[4] in BIG]
            _REC["big_lab"] = [self.item_def[k][4] for k in _REC["big"]]
            _REC["big_pos"] = self.item_pos[_REC["big"]].copy()
            _REC["dl0"] = np.asarray(self.dmg_life, np.float32).copy()
            _REC["t"] = 0
        _REC["t"] += 1
        dl = np.asarray(self.dmg_life, np.float32)
        R["dealt"].append(np.maximum(0.0, dl - _REC["dl0"]).astype(np.float32))
        _REC["dl0"] = dl.copy()
        R["hp"].append(np.asarray(self.hp, np.float32).astype(np.float16))
        R["ar"].append(np.asarray(self.armor, np.float32).astype(np.float16))
        R["alive"].append(np.asarray(self.hp > 0))
        R["weapon"].append(np.asarray(self.weapon).astype(np.int8))
        R["vis"].append(np.asarray(self.visible, bool).copy())
        R["pos"].append(self.state[:, :3].astype(np.float16))
        R["up"].append(self.item_up[:, _REC["big"]].copy())
        for e in out[3]["events"]:
            _REC.setdefault("kills", []).append((_REC["t"], int(e["victim"]), int(e["killer"])))
        return out
    E.DuelEnv.step = step
    E.DuelEnv._cy_rec = True


def _play(job):
    import importlib
    import duel_eval as DE
    out, k_ = job[-2], job[-1]
    job = job[:-2]
    os.environ.update(job[1])
    E = importlib.import_module(job[0])
    _recorder(E)
    _REC.clear()
    res = DE.play(job)
    R = {k: np.stack(v) for k, v in _REC["R"].items()}
    sw_ = bool(job[12]) and job[9] is not None
    n = R["hp"].shape[1]
    side = ((np.arange(n) + int(sw_)) % 2).astype(np.int8)
    kills = np.array(_REC.get("kills", []), np.int64).reshape(-1, 3)
    f_ = os.path.join(out, "rec_{}_{}.npz".format(job[2], k_))
    np.savez_compressed(f_, side=side, kills=kills, big=np.array(_REC["big_lab"]), big_pos=_REC["big_pos"], dt=float(E.DT),
                        result=np.array(json.dumps(dict(score=res["score"], kills=res["kills"], overtime=res["overtime_periods"]))), **R)
    return job[2], k_, f_, res["score"]


def _settings(run, policy):
    os.environ["PANEL_RUN"] = run
    import panel as P
    ps = float(json.load(open(os.path.join(SR, run, "live.json"))).get("PERCEPT_SPEED") or 0.0)
    return P.settings(ps, policy)


def cmd_env(path, seen=None):
    """the set NAME=VALUE lines of a .cmd and of the .cmd files it calls (its aim2 block)"""
    env, seen = {}, seen or set()
    seen.add(os.path.abspath(path))
    for ln in open(path, encoding="utf-8", errors="replace"):
        s = ln.strip()
        if s.lower().startswith("set ") and "=" in s:
            k, v = s[4:].split("=", 1)
            env[k.strip()] = v.strip()
        elif s.lower().startswith("call "):
            p_ = s[5:].strip().strip('"').replace("%~dp0", os.path.dirname(os.path.abspath(path)) + os.sep)
            if os.path.exists(p_) and os.path.abspath(p_) not in seen:
                env.update(cmd_env(p_, seen))
    return env


def check(a):
    """the games' settings against the run's command, its live.json and the save's env_vars: every difference listed"""
    import torch
    S = dict(x.split("=", 1) for x in _settings(a.run, a.policy))
    C = cmd_env(a.cmd)
    L = {k: str(v) for k, v in json.load(open(os.path.join(SR, a.run, "live.json"))).items()}
    V = {k: str(v) for k, v in (torch.load(a.policy, map_location="cpu", weights_only=False).get("env_vars") or {}).items()}
    bad = 0
    for k, v in sorted(S.items()):
        src = [("live", L.get(k)), ("cmd", C.get(k)), ("save", V.get(k))]
        diff = [(nm, x) for nm, x in src if x is not None and not _same(x, v)]
        if diff:
            bad += 1
            print("DIFF {} = {} in the games; {}".format(k, v, ", ".join("{} {}".format(nm, x) for nm, x in diff)))
    miss = sorted(k for k in V if k not in S and k in C and not _same(C[k], V[k]))
    for k in miss:
        print("SAVE-ONLY {}: save {} cmd {}".format(k, V[k], C[k]))
    print("{} settings in the games, {} differ from the run's command / live / save".format(len(S), bad))


def _same(x, y):
    try:
        return abs(float(x) - float(y)) < 1e-9
    except ValueError:
        return os.path.normcase(os.path.normpath(str(x))) == os.path.normcase(os.path.normpath(str(y))) or str(x) == str(y)


def sim(a):
    import duel_eval as DE
    import pin
    import test_suite as T
    os.makedirs(a.out, exist_ok=True)
    sets = _settings(a.run, a.policy)
    envvars = dict(x.split("=", 1) for x in sets)
    envvars.update(OPENBLAS_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1", PYTHONFAULTHANDLER="1", OMP_NUM_THREADS="1")
    pol = T.Policy(a.policy, seed=1)
    opp = T.Policy(a.policy, seed=2)
    if any(getattr(p_, "rf_read", False) and p_.rfg > 0 for p_ in (pol, opp)) and "BRAIN_READ" not in envvars:
        envvars["BRAIN_READ"] = "1"
    now = DE.names(os.path.join(ROOT, "docs", "INPUTS.csv"))
    idx = np.array([now.index(x) for x in DE.fit_list(now, len(pol.mean))])
    delays = (125.0, 225.0, 125.0, 225.0)
    json.dump(dict(policy=a.policy, run=a.run, sets=sets, games=a.games, procs=a.procs, maps=a.maps, delays=delays,
                   started=time.strftime("%Y-%m-%d %H:%M")), open(os.path.join(a.out, "meta.json"), "w"), indent=1)
    jobs = []
    for q, mp in enumerate(a.maps.split(",")):
        per = [a.games // a.procs + (1 if k < a.games % a.procs else 0) for k in range(a.procs)]
        for k, g in enumerate(per):
            if g > 0 and not os.path.exists(os.path.join(a.out, "rec_{}_{}.npz".format(mp, k))):
                jobs.append(("duel_env_ffa", envvars, mp, g, 10.0, a.seed + 1000 * q + 17 * k, pol, idx, "policy", opp, idx,
                             (DE.round_of(600.0, pol, mp), DE.round_of(600.0, opp, mp), False), k % 2 == 1, delays, a.out, k))
    t0 = time.time()
    with mp_.Pool(min(a.par, len(jobs)), initializer=pin.pin_pool_worker, maxtasksperchild=1) as pool:
        for mp, k, f_, sc in pool.imap_unordered(_play, jobs):
            print("{:.0f} min {} job {}: {}".format((time.time() - t0) / 60, mp, k, sc), flush=True)
    print("all done", flush=True)


# ------------------------------------------------------------------------------------------------ B-304: the stack table
def eff(hp, ar):
    """the effective stack: health plus the armor it can use (armor soaks 2/3: up to twice the health; sim/win_judge.py's rule)"""
    hp = np.maximum(hp, 0.0)
    return hp + np.minimum(ar, 2.0 * hp)


MIN_DMG = 40.0                                                 # a fight: at least this much damage, both sides together
BANDS = (0.0, 0.67, 0.9, 1.1, 1.5, 1e9)
BAND_NAMES = ("under 0.67", "0.67-0.9", "0.9-1.1", "1.1-1.5", "over 1.5")


def fights_rows(my, op, dead_m, dead_o, dt, gap=2.0):
    """fights from a match's per-step stacks (my, op: effective; dead_*: dead flags), a step dt seconds: contact = either side's
    stack fell by 5 or more beyond the decay above 100 (1 a second); a fight = contact steps no more than `gap` s apart; at its
    first step: the stack ratio (the step before), who hit first; its result: who died within it or 2 s after (first death)"""
    T = len(my)
    dec = dt * 2.0                                            # (health and armor above 100 each tick down 1 a second)
    dm = np.zeros(T)
    do = np.zeros(T)
    dm[1:] = my[:-1] - my[1:]
    do[1:] = op[:-1] - op[1:]
    alive = ~dead_m & ~dead_o
    al2 = alive & np.concatenate([[False], alive[:-1]])
    hm = al2 & (dm >= 5.0 + dec)                              # he was hit
    ho = al2 & (do >= 5.0 + dec)                              # the enemy was hit
    c = np.nonzero(hm | ho)[0]
    F = []
    if not len(c):
        return F
    g = int(round(gap / dt))
    st = [c[0]]
    for i in range(1, len(c)):
        if c[i] - c[i - 1] > g:
            st.append(c[i])
    ends = [c[np.searchsorted(c, s_, side="left"):][np.r_[np.diff(c[np.searchsorted(c, s_, side="left"):]) > g, True]][0] for s_ in st]
    for s_, e_ in zip(st, ends):
        if (np.where(hm, dm, 0.0)[s_:e_ + 1].sum() + np.where(ho, do, 0.0)[s_:e_ + 1].sum()) < MIN_DMG:
            continue                                          # (a lone chip, or the pros' worked-out stack stepping: not a fight)
        w_ = slice(s_, min(T, e_ + g + 1))
        dmf = np.nonzero(dead_m[w_] & ~np.concatenate([[False], dead_m[w_][:-1]]))[0]
        dof = np.nonzero(dead_o[w_] & ~np.concatenate([[False], dead_o[w_][:-1]]))[0]
        if len(dmf) and (not len(dof) or dmf[0] < dof[0]):
            res = -1
        elif len(dof):
            res = 1
        else:
            res = 0
        first = 1 if ho[s_] and not hm[s_] else (-1 if hm[s_] and not ho[s_] else 0)
        F.append((my[max(0, s_ - 1)], op[max(0, s_ - 1)], first, res, (e_ - s_) * dt))
    return F


def stack_table(F, label):
    F = np.array(F, np.float64).reshape(-1, 5)
    r = F[:, 0] / np.maximum(F[:, 1], 1.0)
    b = np.digitize(r, BANDS) - 1
    print("\n{}: {} fights (each seen from both sides)".format(label, len(F)))
    print("  {:>11} | {:>6} | {:>6} {:>6} {:>6} | {:>9} | {:>8}".format("his / enemy", "share", "win", "lose", "none", "he hit 1st", "seconds"))
    for j, nm in enumerate(BAND_NAMES):
        m = b == j
        if not m.any():
            continue
        print("  {:>11} | {:>5.1f}% | {:>5.1f}% {:>5.1f}% {:>5.1f}% | {:>9.1f}% | {:>8.1f}".format(
            nm, 100 * m.mean(), 100 * (F[m, 3] == 1).mean(), 100 * (F[m, 3] == -1).mean(), 100 * (F[m, 3] == 0).mean(),
            100 * (F[m, 2] == 1).mean(), np.median(F[m, 4])))
    dec = F[:, 3] != 0
    ahead = r > 1.1
    if (dec & ahead).any():
        print("  decided fights: the bigger stack (over 1.1) won {:.1f}% of {}; with 1.5 or more {:.1f}%".format(
            100 * (F[dec & ahead, 3] == 1).mean(), int((dec & ahead).sum()), 100 * (F[dec & (r > 1.5), 3] == 1).mean()))
    lo_ = (r < 0.9) & (F[:, 2] == 1)                          # the weaker player hit first: how it ended
    if lo_.any():
        print("  the weaker side (under 0.9) hit first in {:.1f}% of fights; then it won {:.1f}%, lost {:.1f}%, nobody died {:.1f}%".format(
            100 * lo_.sum() / max(1, (r < 0.9).sum()), 100 * (F[lo_, 3] == 1).mean(), 100 * (F[lo_, 3] == -1).mean(), 100 * (F[lo_, 3] == 0).mean()))
    return F


def _sym(F):
    """each fight from both sides (a match's two seats, or the pros' demo player and his enemy)"""
    G = [(o, m, -f, -r, s) for m, o, f, r, s in F]
    return F + G


def stack(a):
    recs = sorted(glob.glob(os.path.join(a.dir, "rec_*.npz")))
    F, led, phase = [], dict(dealt=0.0, minutes=0.0), {}
    for f_ in recs:
        R = np.load(f_)
        dt = float(R["dt"])
        hp, ar = R["hp"].astype(np.float32), R["ar"].astype(np.float32)
        alive = R["alive"]
        E_ = np.where(alive, eff(hp, ar), 0.0)
        n = hp.shape[1]
        led["dealt"] += float(R["dealt"].sum())
        led["minutes"] += n * hp.shape[0] * dt / 60.0
        for m in range(n // 2):
            p, o = 2 * m, 2 * m + 1
            F += _sym(fights_rows(E_[:, p], E_[:, o], ~alive[:, p], ~alive[:, o], dt))
        _phase(R, phase)
    Fs = stack_table(F, "Bobby ({} records, {})".format(len(recs), a.dir))
    P = []
    for f_ in sorted(glob.glob(os.path.join(SR, "judge", "pro_rows", "*", "rows_*.json"))):
        d = json.load(open(f_))
        C = d["cols"]
        X = np.array([r for g in d["rows"] for r in g], np.float64) if d["rows"] and isinstance(d["rows"][0][0], list) else np.array(d["rows"], np.float64)
        ci = {c: C.index(c) for c in C}
        for key in np.unique(X[:, ci["seed"]] * 1000 + X[:, ci["match"]]):
            g = X[(X[:, ci["seed"]] * 1000 + X[:, ci["match"]]) == key]
            g = g[np.argsort(g[:, ci["t"]])]
            dm, do = g[:, ci["my_dead"]] > 0.5, g[:, ci["op_dead"]] > 0.5
            my = np.where(dm, 0.0, eff(g[:, ci["my_hp"]], g[:, ci["my_ar"]]))
            op = np.where(do, 0.0, eff(g[:, ci["op_hp"]], g[:, ci["op_ar"]]))
            P += _sym(fights_rows(my, op, dm, do, 1.0, gap=2.0))
    stack_table(P, "the pros (pro_rows, one row a second; the enemy's stack worked out)")
    # the same rule on his games read once a second, as the pros' rows are
    F1 = []
    for f_ in recs:
        R = np.load(f_)
        dt = float(R["dt"])
        k = int(round(1.0 / dt))
        alive = R["alive"][::k]
        E_ = np.where(alive, eff(R["hp"][::k].astype(np.float32), R["ar"][::k].astype(np.float32)), 0.0)
        for m in range(E_.shape[1] // 2):
            F1 += _sym(fights_rows(E_[:, 2 * m], E_[:, 2 * m + 1], ~alive[:, 2 * m], ~alive[:, 2 * m + 1], 1.0, gap=2.0))
    stack_table(F1, "Bobby read once a second (the pros' rule)")
    # B-306: the ledger's positive-sum part (dmg_reward 0.0055, DMG_TAKEN_W 0.8)
    pm = max(1e-9, led["minutes"])
    print("\nB-306: damage dealt to the enemy {:.0f} a player-minute; the trade bonus (1 - 0.8) x 0.0055 x that = {:.3f} a player-minute "
          "({:.2f} a ten-minute game a player)".format(led["dealt"] / pm, 0.2 * 0.0055 * led["dealt"] / pm, 0.2 * 0.0055 * led["dealt"] / pm * 10))
    _phase_report(phase)


def _phase(R, acc):
    """his weapon in hand by the fight's phase: in view not in contact (the opening), in contact (damage within 1 s), backing off
    (in contact and moving away from the enemy), by distance band"""
    dt = float(R["dt"])
    w, vis, alive = R["weapon"], R["vis"], R["alive"]
    pos = R["pos"].astype(np.float32)
    T, n = w.shape
    k = int(round(1.0 / dt))
    dealt = R["dealt"]
    hit = np.zeros((T, n), bool)
    for p in range(n):
        o = p ^ 1
        x = (dealt[:, p] > 0) | (dealt[:, o] > 0)
        c = np.convolve(x.astype(np.float32), np.ones(k), "full")[:T] > 0
        hit[:, p] = c
    d = np.linalg.norm(pos - pos[:, np.arange(n) ^ 1], axis=2)
    dd = np.zeros_like(d)
    dd[k:] = d[k:] - d[:-k]
    for p in range(n):
        ok = vis[:, p] & alive[:, p] & alive[:, p ^ 1]
        for ph, m in (("opening", ok & ~hit[:, p]), ("contact", ok & hit[:, p] & (dd[:, p] <= 50)), ("backing off", ok & hit[:, p] & (dd[:, p] > 50))):
            for bn, lo, hi in (("under 300", 0, 300), ("300-700", 300, 700), ("over 700", 700, 1e9)):
                mm = m & (d[:, p] >= lo) & (d[:, p] < hi)
                v = acc.setdefault((ph, bn), np.zeros(10))
                v[:9] += np.bincount(w[mm, p].astype(np.int64), minlength=9)[:9]
                v[9] += mm.sum()


def _phase_report(acc):
    import duel_env as E
    NM = list(E.WEAPONS)
    print("\nhis weapon in hand with the enemy in view, by the fight's phase and the distance (share of frames: rockets / lightning / rail)")
    for (ph, bn), v in sorted(acc.items()):
        tot = max(1.0, v[9])
        print("  {:>12} {:>9}: {:>5.1f}% / {:>5.1f}% / {:>5.1f}%   ({:.0f} s)".format(ph, bn, 100 * v[NM.index("rl")] / tot,
              100 * v[NM.index("lg")] / tot, 100 * v[NM.index("rg")] / tot, tot * 0.025))


# --------------------------------------------------------------------------------------------- B-307 / B-310: the items
def items(a):
    recs = sorted(glob.glob(os.path.join(a.dir, "rec_*.npz")))
    lie, up_share, taker = {}, {}, {}
    for f_ in recs:
        R = np.load(f_)
        dt = float(R["dt"])
        up = R["up"]                                          # (T, matches, k)
        lab = list(R["big"])
        pos = R["pos"].astype(np.float32)
        bp = R["big_pos"]
        E_ = np.where(R["alive"], eff(R["hp"].astype(np.float32), R["ar"].astype(np.float32)), 0.0)
        T, M, K = up.shape
        for j in range(K):
            L = lab[j]
            u = up[:, :, j]
            up_share.setdefault(L, []).append(u.mean())
            for m in range(M):
                x = u[:, m].astype(np.int8)
                on = np.nonzero(np.diff(x) == 1)[0] + 1          # spawns
                off = np.nonzero(np.diff(x) == -1)[0] + 1        # pickups
                for s_ in on:
                    nx = off[off > s_]
                    lie.setdefault(L, []).append((nx[0] - s_) * dt if len(nx) else np.nan)
                for t_ in off:
                    dp = np.linalg.norm(pos[t_, [2 * m, 2 * m + 1]] - bp[j], axis=1)
                    who = int(np.argmin(dp))
                    me, op = E_[max(0, t_ - 1), 2 * m + who], E_[max(0, t_ - 1), 2 * m + (1 - who)]
                    taker.setdefault(L, []).append(1 if me > op + 25 else (-1 if me < op - 25 else 0))
    print("Bobby ({} records): how long the big items lie after a spawn, and who takes them".format(len(recs)))
    for L in BIG:
        if L not in lie:
            continue
        v = np.array(lie[L])
        t = np.array(taker[L])
        print("  {}: there {:.0f}% of the time; after a spawn taken within 1 s {:.0f}%, within 5 s {:.0f}%, median {:.1f} s, not taken {:.0f}% "
              "({} spawns); taken by the player ahead in stack {:.0f}%, level {:.0f}%, behind {:.0f}%".format(
                  L, 100 * np.mean(up_share[L]), 100 * np.nanmean(v <= 1.0), 100 * np.nanmean(v <= 5.0), np.nanmedian(v),
                  100 * np.isnan(v).mean(), len(v), 100 * (t == 1).mean(), 100 * (t == 0).mean(), 100 * (t == -1).mean()))
    _pro_items()


def _pro_items():
    """the pros (sim/pro_moments/<map>.npz): the share of moments each big item is there; who took it last (seat 0 the demo's
    player); B-310: the share of moments with one player 100 or more ahead in effective stack"""
    fs = sorted(glob.glob(os.path.join(ROOT, "sim", "pro_moments", "*.npz")))
    if not fs:
        print("no sim/pro_moments files")
        return
    import duel_env as E
    there, n_m, diff = {}, 0, []
    for f_ in fs:
        Z = np.load(f_, allow_pickle=True)
        keys = list(Z.keys())
        if "item_left" not in keys:
            print("  {}: no item_left ({})".format(os.path.basename(f_), keys[:12]))
            continue
        il = Z["item_left"]
        labs = [E.ITEM_DEFS[str(c)][4] for c in Z["item_cls"]]
        if len(labs) == il.shape[1]:
            for j, L in enumerate(labs):
                if L in BIG:
                    there.setdefault(L, []).append((il[:, j] <= 0).mean())
        if "hp" in keys and "armor" in keys:
            hp, ar = Z["hp"].astype(np.float32), Z["armor"].astype(np.float32)
            e0, e1 = eff(hp[:, 0], ar[:, 0]), eff(hp[:, 1], ar[:, 1])
            diff.append(np.abs(e0 - e1))
        n_m += len(il)
    print("the pros ({} moments, {} maps):".format(n_m, len(fs)))
    for L in BIG:
        if L in there:
            print("  {}: there {:.0f}% of the moments".format(L, 100 * np.mean(there[L])))
    if diff:
        d = np.concatenate(diff)
        print("B-310: moments (the pro starts' pool) with one player 100 or more ahead in effective stack: {:.0f}%; 200 or more: {:.0f}%".format(
            100 * (d >= 100).mean(), 100 * (d >= 200).mean()))


def _labels_for(mp, E):
    """the simulator's item list of a map (its labels: MH, RA, YA, ...), in the order of item_left's columns"""
    try:
        from qsim import World
        import duel_env as D
        bsp = os.path.join(ROOT, "data", "maps", mp + ".bsp")
        env = D.DuelEnv(bsp, n_matches=1, seed=0)
        return [d[4] for d in env.item_def]
    except Exception as e:                                   # noqa: BLE001
        print("  {}: the item list not read ({})".format(mp, e))
        return None


def summarize(R, side):
    """(1.7b, CY_REC) one job's records (arrays as _recorder keeps them) -> a small summary: every fight seen from each seat, read once a
    second as the pros' rows (his stack, the enemy's, who hit first, the result, seconds, the seat's side), the big items' spawns (label,
    seconds lying, the taker's side and stack edge), the damage dealt and the player-minutes by side"""
    dt = float(R["dt"])
    k = int(round(1.0 / dt))
    alive = np.asarray(R["alive"])[::k]
    E_ = np.where(alive, eff(np.asarray(R["hp"], np.float32)[::k], np.asarray(R["ar"], np.float32)[::k]), 0.0)
    n = E_.shape[1]
    side = np.asarray(side)
    F = []
    for m in range(n // 2):
        for p, o in ((2 * m, 2 * m + 1), (2 * m + 1, 2 * m)):
            for f_ in fights_rows(E_[:, p], E_[:, o], ~alive[:, p], ~alive[:, o], 1.0, gap=2.0):
                F.append([float(x) for x in f_] + [int(side[p])])
    dl = np.asarray(R["dealt"], np.float64)
    out = dict(fights=F, dealt=[float(dl[:, side == s].sum()) for s in (0, 1)],
               minutes=[float((side == s).sum() * dl.shape[0] * dt / 60.0) for s in (0, 1)], items=[])
    up = np.asarray(R["up"])
    if up.ndim == 3:
        pos = np.asarray(R["pos"], np.float32)
        bp = np.asarray(R["big_pos"], np.float32)
        Ef = np.where(np.asarray(R["alive"]), eff(np.asarray(R["hp"], np.float32), np.asarray(R["ar"], np.float32)), 0.0)
        T, M, K = up.shape
        for j in range(K):
            for m in range(M):
                x = up[:, m, j].astype(np.int8)
                on = np.nonzero(np.diff(x) == 1)[0] + 1
                off = np.nonzero(np.diff(x) == -1)[0] + 1
                for s_ in on:
                    nx = off[off > s_]
                    if not len(nx):
                        continue
                    t_ = int(nx[0])
                    dp = np.linalg.norm(pos[t_, [2 * m, 2 * m + 1]] - bp[j], axis=1)
                    w_ = int(np.argmin(dp))
                    q_ = 2 * m + w_
                    out["items"].append([str(R["big"][j]), (t_ - s_) * dt, int(side[q_]), float(Ef[max(0, t_ - 1), q_] - Ef[max(0, t_ - 1), q_ ^ 1])])
    return out


def check_mode(a):
    """the summaries of one check (CY_REC) -> the learner's and the control's tables; a line into --out"""
    fs = sorted(glob.glob(os.path.join(a.dir, "cy_*.json")))
    F, dealt, mins, IT = [], [0.0, 0.0], [0.0, 0.0], []
    for f_ in fs:
        d = json.load(open(f_))
        F += d["fights"]
        dealt = [x + y for x, y in zip(dealt, d["dealt"])]
        mins = [x + y for x, y in zip(mins, d["minutes"])]
        IT += d["items"]
    F = np.array(F, np.float64).reshape(-1, 6)
    rec = dict(update=a.update, jobs=len(fs))
    for s, nm in ((0, "he"), (1, "control")):
        G = F[F[:, 5] == s]
        r = G[:, 0] / np.maximum(G[:, 1], 1.0)
        low, wk, big = r < 0.67, r < 0.9, r > 1.1
        dec = G[:, 3] != 0
        rec[nm] = dict(fights=int(len(G)), outstacked=int(low.sum()),
                       out_dies=round(float((G[low, 3] == -1).mean()), 4) if low.any() else None,
                       out_escapes=round(float((G[low, 3] == 0).mean()), 4) if low.any() else None,
                       weaker_hits_first=round(float((G[wk, 2] == 1).mean()), 4) if wk.any() else None,
                       bigger_wins=round(float((G[dec & big, 3] == 1).mean()), 4) if (dec & big).any() else None,
                       dealt_per_min=round(dealt[s] / max(1e-9, mins[s]), 1))
        I = [x for x in IT if x[2] == s]
        rec[nm]["items"] = {L: dict(taken=sum(1 for x in I if x[0] == L), median_s=round(float(np.median([x[1] for x in I if x[0] == L])), 2)
                                    if any(x[0] == L for x in I) else None) for L in BIG}
    rec["pros"] = dict(out_dies=0.299, out_escapes=0.639, weaker_hits_first=0.469, bigger_wins=0.775)      # (docs/design/CYPHER.md)
    print(json.dumps(rec))
    if a.out:
        with open(a.out, "a") as fh:
            fh.write(json.dumps(rec) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("check", "sim", "stack", "items"))
    ap.add_argument("--update", type=int, default=-1)
    ap.add_argument("--out_", dest="out_jsonl", default="")
    ap.add_argument("dir", nargs="?", default="")
    ap.add_argument("--run", default="duel_gru_1_7a")
    ap.add_argument("--policy", default="")
    ap.add_argument("--cmd", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--maps", default=",".join(MAPS))
    ap.add_argument("--games", type=int, default=8, help="games a map")
    ap.add_argument("--procs", type=int, default=2, help="jobs a map (seats swapped every second)")
    ap.add_argument("--par", type=int, default=6, help="jobs at once")
    ap.add_argument("--seed", type=int, default=4100)
    a = ap.parse_args()
    if a.mode == "check" and a.dir:                          # (1.7b: a check's summaries; without a dir: the settings check)
        a.out = a.out_jsonl
        return check_mode(a)
    {"check": check, "sim": sim, "stack": stack, "items": items}[a.mode](a)


if __name__ == "__main__":
    main()
