"""The judge: his chance of winning, fitted on how his own games ended (owner, 2026-10-28: "frag good, death bad, deal damage
good, take damage bad"; "Freeze now, train later"). The model is sim/win_judge.py (its four axioms are in its shape); this tool
fits it, sets it beside the other forms, checks it and writes it for the simulator's win pay (WIN_JUDGE=<file>).

Data: tools/run/selfplay_loop.py's games (data/sim_runs/<run>/selfplay/<tag>/rows_<map>.json: one row a second, the score, both
players' health, armor, big weapons owned, who is dead), label = the game's result for seat 0 (won 1, lost 0, level 0.5).
Overtime is a short game of its own (the review of 2026-10-28): a game that went to overtime gives its overtime rows (the
period's clock, as the simulator's pay reads it) and not its regulation rows (their label is the overtime's winner, which
taught the old fit that a stack at 0:01 never fades). A game is one outcome: every interval is by whole games resampled.

Forms set beside each other, on the same rows and held-out games (folds by game):
  table   the pro table W(lead, left) (sim/win_chance.json), no stacks
  A       the simulator's formula today: the pro table + the 2026-10-26 next-frag stack term (not fitted)
  A-fit   the same, its numbers fitted on these results
  B2      the hand-shaped formula of 2026-10-28 (stack above / below a respawn, a fixed fade, weapons >= 0)
  judge   sim/win_judge.py, the one that is used
  flex    a small free network with no structure (a reference for what the structure costs)
Reported: held-out log loss and Brier (all, by time left) with the difference to the judge (95%, games resampled); the
judge's value table (a hit, a frag, a death, a mega, a red armor, the weapons, at several leads and times) with 95% intervals
from refits on games resampled; the judge per save (drift); its reliability; the four axioms checked on a fine grid (they hold
by construction: a failure here is a bug). Acceptance (docs/runs/v0.6.1/CARD.md): the judge's held-out log loss no worse than
B2's interval, better than A; no axiom failure.
    python tools/run/fit_b.py <run> [tags u40,u60,...; default every u<N> folder] [--boot 30] [--out judge.npz] [--json r.json]
"""
import argparse
import glob
import json
import math
import os
import sys
import time

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SR = os.path.join(ROOT, "data", "sim_runs")
sys.path.insert(0, os.path.join(ROOT, "sim"))
import win_judge as WJ                                       # noqa: E402

torch.set_num_threads(4)
DT, GF, OTF, OT_LEN, GAME_LEN, SPAWN = 0.025, 24000, 4800, 120.0, 600.0, 125.0   # (frames: regulation 24,000, an overtime period 4,800)
TBINS = ((600, 450), (450, 300), (300, 180), (180, 60), (60, 0))
F1026 = dict(PA=2.7546, PRL=0.4277, PLG=0.4485, PRG=0.2922)
CELLS = ((0, 590), (0, 300), (0, 60), (3, 300), (3, 60), (-3, 60), (5, 300))


def rows(folders):
    """every game's rows from the folders, one game id per (file, seed, match); 'left' as the win pay reads it"""
    R, g0 = {}, 0
    for k_, fo in enumerate(folders):
        for fn in sorted(glob.glob(os.path.join(fo, "rows_*.json"))):
            d = json.load(open(fn))
            cols = d["cols"]
            A = np.array([x for blk in d["rows"] for x in blk], np.float64) if d["rows"] and isinstance(d["rows"][0][0], list) else np.array(d["rows"], np.float64)
            C = {c: A[:, i] for i, c in enumerate(cols)}
            for s_, fl_ in zip(d["seeds"], d["final"]):
                for m_, _ in enumerate(fl_):
                    idx = np.nonzero((C["seed"] == s_) & (C["match"] == m_))[0]
                    idx = idx[np.argsort(C["t"][idx])]
                    if not len(idx):
                        continue
                    part = {c: C[c][idx] for c in cols}
                    part["g"] = np.full(len(idx), g0)
                    part["save"] = np.full(len(idx), k_)
                    part["final_my"] = np.full(len(idx), part["my_score"][-1])
                    part["final_op"] = np.full(len(idx), part["op_score"][-1])
                    part["ot_game"] = np.full(len(idx), float((part["t"] >= GF).any()))
                    g0 += 1
                    for k, v in part.items():
                        R.setdefault(k, []).append(v)
    if not R:
        sys.exit("no rows in " + ", ".join(folders))
    R = {k: np.concatenate(v) for k, v in R.items()}
    t = R["t"]
    R["left"] = np.where(t >= GF, OT_LEN - ((t - GF) % OTF) * DT, GAME_LEN - t * DT)
    return R


def data(folders):
    """-> (X, counts): the rows used (regulation of games decided in regulation, overtime rows of the others)"""
    R = rows(folders)
    reg = R["t"] < GF
    use = np.where(R["ot_game"] > 0.5, ~reg, reg)
    res = np.where(R["final_my"] > R["final_op"], 1.0, np.where(R["final_my"] < R["final_op"], 0.0, 0.5))
    dead = lambda p: R[p + "_dead"] > 0.5                    # noqa: E731
    own = lambda p: np.stack([np.where(dead(p), 0.0, (R[p + "_" + w] > 0.5).astype(float)) for w in ("rl", "lg", "rg")], 1)   # noqa: E731
    wm, wo = own("my"), own("op")
    X = dict(d=R["my_score"] - R["op_score"], left=np.maximum(R["left"], 0.0),
             ds=np.where(dead("my"), SPAWN, R["my_hp"] + R["my_ar"]) - np.where(dead("op"), SPAWN, R["op_hp"] + R["op_ar"]),
             e_my=WJ.effective(R["my_hp"], R["my_ar"], dead("my")), e_op=WJ.effective(R["op_hp"], R["op_ar"], dead("op")),
             wm=wm, wo=wo, rl=wm[:, 0] - wo[:, 0], lg=wm[:, 1] - wo[:, 1], rg=wm[:, 2] - wo[:, 2],
             dm=R["my_dead"], do=R["op_dead"], y=res, g=R["g"], save=R["save"], ot=(~reg).astype(float))
    X = {k: np.asarray(v[use], np.float64) for k, v in X.items()}
    n_g = len(np.unique(R["g"]))
    n_ot = len(np.unique(R["g"][R["ot_game"] > 0.5]))
    return X, dict(games=n_g, ot_games=n_ot, rows=int(use.sum()), rows_left_out=int((~use).sum()))


def table():
    wc_ = json.load(open(os.path.join(ROOT, "sim", "win_chance.json"), encoding="utf-8"))
    p_ = np.array(wc_["p"], np.float64)
    left_ = np.array(wc_["left_s"], np.float64)
    return p_, float(left_[1]), int(np.array(wc_["diffs"])[-1])


def T(x):
    return torch.as_tensor(x, dtype=torch.float64)


class Judge(torch.nn.Module):
    """sim/win_judge.py with torch: the same function, its numbers as parameters"""
    def __init__(self, P0=None):
        super().__init__()
        P0 = WJ.init() if P0 is None else P0
        self.P = torch.nn.ParameterDict({k: torch.nn.Parameter(T(v)) for k, v in P0.items()})

    def forward(self, X):
        return WJ.chance(self.P, X["d"], X["left"], X["e_my"], X["wm"], X["e_op"], X["wo"], xp=torch)

    def numpy(self):
        return {k: v.detach().numpy().astype(np.float64) for k, v in self.P.items()}


class B2(torch.nn.Module):
    """the hand-shaped formula of 2026-10-28 (a reference): mu = f(left) x [V(E_my) - V(E_op) + bRL dRL + bLG dLG + bRG dRG],
    f = 1 - exp(-left / tau), b >= 0, V(E) = c_hi tanh((E - 125) / k_hi) above 125, -c_lo tanh((125 - E) / k_lo) below"""
    def __init__(self):
        super().__init__()
        self.rv = torch.nn.Parameter(T(math.log(0.02)))
        self.rv0 = torch.nn.Parameter(T(math.log(0.5)))
        self.rtau = torch.nn.Parameter(T(math.log(20.0)))
        self.rch = torch.nn.Parameter(T(0.0))
        self.rkh = torch.nn.Parameter(T(math.log(100.0)))
        self.rcl = torch.nn.Parameter(T(0.0))
        self.rkl = torch.nn.Parameter(T(math.log(60.0)))
        self.rb = torch.nn.Parameter(T([-2.0, -2.0, -2.0]))

    def par(self):
        sp = torch.nn.functional.softplus
        return dict(c_hi=sp(self.rch), k_hi=5.0 + torch.exp(self.rkh), c_lo=0.5 * torch.sigmoid(self.rcl), k_lo=5.0 + torch.exp(self.rkl),
                    bRL=sp(self.rb[0]), bLG=sp(self.rb[1]), bRG=sp(self.rb[2]), tau=0.5 + torch.exp(self.rtau),
                    v=1e-4 + torch.exp(self.rv), v0=0.02 + torch.exp(self.rv0))

    def forward(self, X):
        p = self.par()
        V = lambda E: torch.where(E >= SPAWN, p["c_hi"] * torch.tanh((E - SPAWN) / p["k_hi"]), -p["c_lo"] * torch.tanh((SPAWN - E) / p["k_lo"]))   # noqa: E731
        u = V(X["e_my"]) - V(X["e_op"]) + p["bRL"] * X["rl"] + p["bLG"] * X["lg"] + p["bRG"] * X["rg"]
        mu = u * (1.0 - torch.exp(-X["left"] / p["tau"]))
        return torch.special.ndtr((X["d"] + mu) / torch.sqrt(p["v"] * X["left"] + p["v0"]))


class Afit(torch.nn.Module):
    """the simulator's formula today (the pro table, the expectation over the next frag), its numbers fitted on results"""
    def __init__(self, tab, init):
        super().__init__()
        self.p_, self.step, self.D = tab
        self.pa = torch.nn.Parameter(T(init["PA"]))
        self.w = torch.nn.Parameter(T([init["PRL"], init["PLG"], init["PRG"]]))
        self.rtau = torch.nn.Parameter(T(math.log(32.5)))

    def W(self, d, left):
        p = T(self.p_)
        x = torch.clamp(left / self.step, 0.0, p.shape[0] - 1.0)
        i0 = torch.clamp(x.floor().long(), max=p.shape[0] - 2)
        f = x - i0
        j = (torch.clamp(torch.round(d), -self.D, self.D) + self.D).long()
        return p[i0, j] * (1 - f) + p[i0 + 1, j] * f

    def forward(self, X):
        pn = torch.sigmoid(self.pa * torch.tanh(X["ds"] / 300.0) + self.w[0] * X["rl"] + self.w[1] * X["lg"] + self.w[2] * X["rg"])
        lam = 1.0 - torch.exp(-X["left"] / torch.exp(self.rtau))
        return (1 - lam) * self.W(X["d"], X["left"]) + lam * (pn * self.W(X["d"] + 1, X["left"]) + (1 - pn) * self.W(X["d"] - 1, X["left"]))


class Flex(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.net = torch.nn.Sequential(torch.nn.Linear(8, 32), torch.nn.Tanh(), torch.nn.Linear(32, 32), torch.nn.Tanh(), torch.nn.Linear(32, 1)).double()

    def feats(self, X):
        return torch.stack([X["d"] / 5.0, X["left"] / 600.0, torch.tanh(X["ds"] / 300.0), X["rl"], X["lg"], X["rg"], X["dm"], X["do"]], 1)

    def forward(self, X):
        f = self.feats(X)
        fm = f.clone()
        fm[:, [0, 2, 3, 4, 5]] *= -1                        # (zero-sum: the same state seen from the other seat)
        fm[:, [6, 7]] = f[:, [7, 6]]
        return torch.sigmoid(0.5 * (self.net(f) - self.net(fm)).squeeze(1))


def nll(p, y):
    p = torch.clamp(p, 1e-6, 1 - 1e-6)
    return -(y * torch.log(p) + (1 - y) * torch.log(1 - p)).mean()


def fit(model, X, steps=400, lr=0.05):
    Xt = {k: T(v) for k, v in X.items()}
    opt = torch.optim.LBFGS(model.parameters(), lr=lr, max_iter=steps, line_search_fn="strong_wolfe")

    def closure():
        opt.zero_grad()
        loss = nll(model(Xt), Xt["y"])
        loss.backward()
        return loss
    opt.step(closure)
    return model


def fit_judge(X, P0=None, adam=600, lbfgs=200, l2=1e-4):
    """Adam to get near, then L-BFGS; a small pull of the networks' weights to nothing (the shape is sure, the data is 300 games)"""
    torch.manual_seed(0)
    m = Judge(P0)
    Xt = {k: T(v) for k, v in X.items()}
    reg = lambda: l2 * sum((p_ ** 2).sum() for n_, p_ in m.P.items() if "_w" in n_)   # noqa: E731
    opt = torch.optim.Adam(m.parameters(), lr=0.02)
    for _ in range(adam):
        opt.zero_grad()
        loss = nll(m(Xt), Xt["y"]) + reg()
        loss.backward()
        opt.step()
    opt2 = torch.optim.LBFGS(m.parameters(), lr=0.5, max_iter=lbfgs, line_search_fn="strong_wolfe")

    def closure():
        opt2.zero_grad()
        loss = nll(m(Xt), Xt["y"]) + reg()
        loss.backward()
        return loss
    opt2.step(closure)
    return m


def fit_flex(X, epochs=300):
    torch.manual_seed(0)
    m = Flex()
    Xt = {k: T(v) for k, v in X.items()}
    opt = torch.optim.Adam(m.parameters(), lr=3e-3, weight_decay=1e-4)
    for _ in range(epochs):
        opt.zero_grad()
        loss = nll(m(Xt), Xt["y"])
        loss.backward()
        opt.step()
    return m


def predict(model, X):
    with torch.no_grad():
        return model({k: T(v) for k, v in X.items()}).numpy()


def sub(X, m):
    return {k: v[m] for k, v in X.items()}


def resample(X, gi, pick):
    """the rows of the games picked (with repeats), each copy a game of its own"""
    idx = np.concatenate([gi[g] for g in pick])
    Y = {k: v[idx] for k, v in X.items()}
    Y["g"] = np.repeat(np.arange(len(pick)), [len(gi[g]) for g in pick]).astype(np.float64)
    return Y


def state(d, left, me=(100.0, 50.0), him=(100.0, 50.0), w_me=(1, 1, 0), w_him=(1, 1, 0), dead_me=0, dead_him=0):
    """one stand-in state, seat 0's view (health, armor), weapons owned (RL, LG, RG); a dead player as his respawn"""
    sm = SPAWN if dead_me else me[0] + me[1]
    sh = SPAWN if dead_him else him[0] + him[1]
    em = float(WJ.effective(me[0], me[1], bool(dead_me)))
    eh = float(WJ.effective(him[0], him[1], bool(dead_him)))
    wm = (0, 0, 0) if dead_me else w_me
    wh = (0, 0, 0) if dead_him else w_him
    return dict(d=[d], left=[left], ds=[sm - sh], e_my=[em], e_op=[eh], wm=[list(wm)], wo=[list(wh)],
                rl=[wm[0] - wh[0]], lg=[wm[1] - wh[1]], rg=[wm[2] - wh[2]], dm=[dead_me], do=[dead_him], y=[0.5])


def Pw(m, s):
    return float(predict(m, {k: np.asarray(v, np.float64) for k, v in s.items()})[0])


# the value table's events, seat 0's (before, after) at a lead L and a time left t; a stand-in duel: both 100 health + 50
# armor, both own the rocket launcher and the lightning gun, nobody the rail, unless said
EVENTS = [("10-damage hit (him 100+50 -> 100+40)", lambda L, t: (state(L, t), state(L, t, him=(100.0, 40.0)))),
          ("100-damage hit (him 100+50 -> 67+0)", lambda L, t: (state(L, t), state(L, t, him=(66.7, 0.0)))),
          ("100 damage taken (me 100+50 -> 67+0)", lambda L, t: (state(L, t), state(L, t, me=(66.7, 0.0)))),
          ("frag of a 20-hp enemy", lambda L, t: (state(L, t, him=(20.0, 0.0)), state(L + 1, t, dead_him=1))),
          ("frag of a 200+100 enemy (all at once)", lambda L, t: (state(L, t, him=(200.0, 100.0)), state(L + 1, t, dead_him=1))),
          ("death at 20 hp", lambda L, t: (state(L, t, me=(20.0, 0.0)), state(L - 1, t, dead_me=1))),
          ("mega at 100+50", lambda L, t: (state(L, t), state(L, t, me=(200.0, 50.0)))),
          ("red armor at 100+50", lambda L, t: (state(L, t), state(L, t, me=(100.0, 150.0)))),
          ("mega at 40+0", lambda L, t: (state(L, t, me=(40.0, 0.0)), state(L, t, me=(140.0, 0.0)))),
          ("red armor at 40+0", lambda L, t: (state(L, t, me=(40.0, 0.0)), state(L, t, me=(40.0, 100.0)))),
          ("rail taken", lambda L, t: (state(L, t), state(L, t, w_me=(1, 1, 1)))),
          ("rocket launcher taken", lambda L, t: (state(L, t, w_me=(0, 1, 0)), state(L, t))),
          ("lightning gun taken", lambda L, t: (state(L, t, w_me=(1, 0, 0)), state(L, t)))]


def ledger_of(m):
    out = {}
    for name, f in EVENTS:
        out[name] = []
        for L, t in CELLS:
            s0, s1 = f(L, float(t))
            out[name].append(100 * (Pw(m, s1) - Pw(m, s0)))
    return out


def axioms(m):
    """the four axioms on a fine grid of states (seat 0's view; seat 1's is the same function): a frag raises his chance, a
    death lowers it, damage dealt raises it, damage taken lowers it. -> list of failures"""
    bad = []
    HP = (1.0, 25.0, 60.0, 100.0, 150.0, 200.0)
    AR = (0.0, 50.0, 100.0, 200.0)
    WS = ((0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1))
    S, kinds = [], []
    for L in range(-6, 7):
        for t in (600.0, 450.0, 300.0, 180.0, 120.0, 60.0, 30.0, 10.0, 1.0):
            for hm in HP:
                for am in (0.0, 100.0):
                    for hh in HP:
                        for ah in AR:
                            for w in WS:
                                S.append((state(L, t, me=(hm, am), him=(hh, ah), w_him=w), state(L + 1, t, me=(hm, am), dead_him=1)))
                                kinds.append(("frag", L, t, hm, am, hh, ah, w))
                                if hh > 20:
                                    S.append((state(L, t, me=(hm, am), him=(hh, ah), w_him=w), state(L, t, me=(hm, am), him=(hh - 20.0, max(0.0, ah - 40.0)), w_him=w)))
                                    kinds.append(("damage dealt", L, t, hm, am, hh, ah, w))
    def cat(ss):
        return {k: np.concatenate([np.asarray(s[k], np.float64) for s in ss]) for k in ss[0]}
    p0 = predict(m, cat([a for a, _ in S]))
    p1 = predict(m, cat([b for _, b in S]))
    for k, a, b in zip(kinds, p0, p1):
        if b < a - 1e-12:
            bad.append(k + (round(100 * (b - a), 4),))
    # death and damage taken are the same states from the other seat: P(seat 1) = 1 - P(seat 0), checked on the grid
    s_ = cat([a for a, _ in S][:2000])
    sw = dict(s_, d=-s_["d"], e_my=s_["e_op"], e_op=s_["e_my"], wm=s_["wo"], wo=s_["wm"])
    sym = float(np.abs(predict(m, s_) + predict(m, sw) - 1.0).max())
    return bad, len(S), sym


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("tags", nargs="?", default="", help="u40,u60,... (default: every u<N> folder of the run's selfplay)")
    ap.add_argument("--dir", default="", help="read the folders under this one instead of data/sim_runs/<run>/selfplay")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--boot", type=int, default=30, help="refits of the judge on games resampled (the value table's intervals)")
    ap.add_argument("--out", default="", help="write the judge fitted on all games here (.npz) for WIN_JUDGE")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    t0 = time.time()
    base = a.dir or os.path.join(SR, a.run, "selfplay")
    tags = a.tags.split(",") if a.tags else sorted((os.path.basename(p) for p in glob.glob(os.path.join(base, "u*")) if glob.glob(os.path.join(p, "rows_*.json"))),
                                                   key=lambda s: int(s[1:]) if s[1:].isdigit() else 0)
    X, cnt = data([os.path.join(base, t) for t in tags])
    games = np.unique(X["g"]).astype(int)
    n_g = len(games)
    gi = {g: np.nonzero(X["g"] == g)[0] for g in games}
    res = np.array([X["y"][gi[g][0]] for g in games])
    print("judge fit on {} ({}): {} games ({} went to overtime: their overtime rows only), {} seat-seconds; seat 0 won {} / lost {} / level {}".format(
        a.run, ",".join(tags), cnt["games"], cnt["ot_games"], cnt["rows"], int((res == 1).sum()), int((res == 0).sum()), int((res == 0.5).sum())))
    rng = np.random.default_rng(0)
    fold_of = dict(zip(games, rng.permutation(n_g) % a.folds))
    fo = np.array([fold_of[int(g)] for g in X["g"]])
    tab = table()
    names = ["table", "A", "A-fit", "B2", "judge", "flex"]
    P = {n: np.zeros(len(X["y"])) for n in names}
    for k in range(a.folds):
        tr, te = fo != k, fo == k
        Xtr, Xte = sub(X, tr), sub(X, te)
        a0 = Afit(tab, F1026)
        with torch.no_grad():
            Xq = {q: T(v) for q, v in Xte.items()}
            P["table"][te] = a0.W(Xq["d"], Xq["left"]).numpy()
            P["A"][te] = a0(Xq).numpy()
        P["A-fit"][te] = predict(fit(Afit(tab, F1026), Xtr), Xte)
        P["B2"][te] = predict(fit(B2(), Xtr), Xte)
        P["judge"][te] = predict(fit_judge(Xtr), Xte)
        P["flex"][te] = predict(fit_flex(Xtr), Xte)
    y = X["y"]
    LL = {n: -(y * np.log(np.clip(P[n], 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - P[n], 1e-6, 1))) for n in names}
    BR = {n: (P[n] - y) ** 2 for n in names}
    out = dict(run=a.run, tags=tags, counts=cnt, models={})
    print("\nHeld-out games ({} folds by game): log loss and Brier; 95% interval of the difference to the judge, games resampled".format(a.folds))
    print("| form | log loss | Brier | log loss - judge (95%) |")
    print("|---|---|---|---|")
    boot_g = rng.integers(0, n_g, size=(400, n_g))
    sJ = np.array([LL["judge"][gi[g]].sum() for g in games])
    ng = np.array([len(gi[g]) for g in games])
    for n in names:
        s_ = np.array([LL[n][gi[g]].sum() for g in games])
        dif = [(s_[b].sum() - sJ[b].sum()) / ng[b].sum() for b in boot_g]
        lo, hi = np.percentile(dif, [2.5, 97.5])
        print("| {} | {:.4f} | {:.4f} | {:+.4f} [{:+.4f}, {:+.4f}] |".format(n, LL[n].mean(), BR[n].mean(), LL[n].mean() - LL["judge"].mean(), lo, hi))
        out["models"][n] = dict(logloss=float(LL[n].mean()), brier=float(BR[n].mean()), vs_judge=[float(lo), float(hi)])
    print("\nBy time left (log loss / Brier, held out; overtime rows by the period's clock):")
    print("| form | " + " | ".join("{}-{} s".format(h, l) for h, l in TBINS) + " |")
    print("|---|" + "---|" * len(TBINS))
    for n in names:
        cells = []
        for h, l in TBINS:
            m_ = (X["left"] <= h) & (X["left"] > l) if l > 0 else (X["left"] <= h)
            cells.append("{:.3f} / {:.3f}".format(LL[n][m_].mean(), BR[n][m_].mean()) if m_.any() else "-")
        print("| {} | ".format(n) + " | ".join(cells) + " |")
    print("\nReliability of the judge (held out): predicted -> actual (seat-seconds)")
    for lo in np.arange(0, 1, 0.1):
        m_ = (P["judge"] >= lo) & (P["judge"] < lo + 0.1)
        if m_.sum():
            print("  {:.1f}-{:.1f}: {:.3f} -> {:.3f} ({})".format(lo, lo + 0.1, P["judge"][m_].mean(), y[m_].mean(), int(m_.sum())))

    J = fit_judge(X)
    led = ledger_of(J)
    LB = []
    for i in range(a.boot):
        LB.append(ledger_of(fit_judge(resample(X, gi, rng.integers(0, n_g, n_g)), P0=J.numpy(), adam=200, lbfgs=100)))
    print("\nThe judge's value table: the change in his chance of winning in points (x100), seat 0 (the enemy gets minus it); "
          "[95% from {} refits on games resampled]".format(a.boot))
    print("| event | " + " | ".join("lead {:+d}, {}:{:02d} left".format(L, int(t) // 60, int(t) % 60) for L, t in CELLS) + " |")
    print("|---|" + "---|" * len(CELLS))
    out["ledger"] = []
    for name, _ in EVENTS:
        cells = []
        for j, (L, t) in enumerate(CELLS):
            v = led[name][j]
            lo, hi = (np.percentile([l_[name][j] for l_ in LB], [2.5, 97.5]) if LB else (float("nan"), float("nan")))
            cells.append("{:+.2f} [{:+.2f}, {:+.2f}]".format(v, lo, hi) if LB else "{:+.2f}".format(v))
            out["ledger"].append(dict(event=name, lead=L, left=t, points=v, ci=[float(lo), float(hi)]))
        print("| {} | ".format(name) + " | ".join(cells) + " |")
    if len(tags) > 1:
        print("\nThe judge per save (each fitted alone; drift): a 100-damage hit and a frag of a 20-hp enemy at a level score, 5:00 left")
        out["per_save"] = {}
        for k_, t_ in enumerate(tags):
            Xs = sub(X, X["save"] == k_)
            ng_ = len(np.unique(Xs["g"]))
            if ng_ < 10:
                print("  {}: {} games, too few".format(t_, ng_))
                continue
            ls = ledger_of(fit_judge(Xs, P0=J.numpy(), adam=200, lbfgs=100))
            out["per_save"][t_] = dict(games=ng_, hit=ls[EVENTS[1][0]][1], frag20=ls[EVENTS[3][0]][1])
            print("  {}: {} games | hit {:+.2f} | frag {:+.2f}".format(t_, ng_, ls[EVENTS[1][0]][1], ls[EVENTS[3][0]][1]))
    bad, n_s, sym = axioms(J)
    out["axioms"] = dict(states=n_s, failures=bad[:50], n_failures=len(bad), symmetry=sym)
    print("\nThe four axioms on {} state changes (frag and damage dealt; death and damage taken by the seats' symmetry, max |P + P' - 1| = {:.1e}): {}".format(
        n_s, sym, "all hold" if not bad else "{} FAILURES, e.g. {}".format(len(bad), bad[:5])))
    if a.out:
        meta = dict(run=a.run, tags=tags, counts=cnt, logloss=out["models"]["judge"]["logloss"], vs_B2=out["models"]["B2"]["logloss"],
                    vs_A=out["models"]["A"]["logloss"], axioms_ok=not bad, made=time.strftime("%Y-%m-%d %H:%M"))
        WJ.save(a.out, J.numpy(), meta)
        print("written", a.out)
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    print("({:.0f} s)".format(time.time() - t0))


if __name__ == "__main__":
    main()
