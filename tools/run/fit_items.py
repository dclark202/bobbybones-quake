"""(1.9a; owner, 2026-11-12: "Judge with items. As long as the head understands the value of items, we're good"; "the judge just pays the
head") fits the items' part of the head's judge (sim/win_judge.py items_term / chance_items) on his own self-play games recorded with the
items' race (tools/run/selfplay_log.py with WS_ITEMS=1: each second, both players' route-field seconds to the mega and the red armor, the
seconds until each is back, and how many each has taken: the truth).

  tau       the race: P(he takes it first) = sigmoid((T_op - T_me) / tau), T = max(his seconds to it, seconds until it is back); fitted by
            maximum likelihood on who really took it next (every second with the item back within 15 s and a later take in the same game)
  K         1 for both (decided here): an item is worth exactly the stack the judge itself says it brings, weighted by the race; a free K
            is fitted beside it as a readout only (game outcomes are too noisy to set it)
  horizon   how soon a respawn counts (exp(-t / horizon)): chosen on how games ended, by held-out log loss (folds by game), the judge's own
            numbers fixed (WIN_JUDGE)
Reported: the race's reliability (bins of p against how often he took it); the held-out log loss of the judge alone and with the items, the
difference with a 95% interval (games resampled); the items' worth in a few states (a mega up and nearer to him or to the enemy, by stack).
ACCEPTANCE (the card): at least 80 games and 2,000 race rows; the race calibrated (every bin with 200 rows or more within 0.07 of its p); the judge with the items no worse on held-out
games than without (the difference's interval reaches 0 or below); the axioms hold (K >= 0; an item nearer to him never lowers his chance).
A file that fails is written with "accepted": false and the run's start refuses it.
    python tools/run/fit_items.py <selfplay folder> [<folder> ...] --judge <judge.npz> --out <items.json> [--boot 200]"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, HERE)
import win_judge as WJ                                       # noqa: E402
import fit_b as FB                                           # noqa: E402

FAR, DEAD_WALK, RACE_TSP = 60.0, 8.0, 15.0
MIN_GAMES, MIN_RACE = 80, 2000                               # (the acceptance's least data: whole games, rows of a race with a known winner)
KS = np.round(np.arange(0.0, 2.01, 0.25), 3)
HS = (3.0, 6.0, 10.0, 15.0, 25.0, 40.0)


def race(R, j, tau=None):
    """the race of item j (0 mega, 1 red armor) at every row: T_me, T_op, w-free p (with tau), and the label (1: he takes it next, 0: the
    enemy, nan: nobody does in this game or the item is not there)"""
    it = ("mh", "ra")[j]
    pres = R[it + "_present"] > 0.5
    tsp = R[it + "_tsp"]
    wm, wo = np.minimum(R[it + "_my_walk"], FAR), np.minimum(R[it + "_op_walk"], FAR)
    Tm, To = np.maximum(wm, tsp), np.maximum(wo, tsp)
    y = np.full(len(tsp), np.nan)
    g = R["g"]
    km, ko = R[it + "_my_took"], R[it + "_op_took"]
    for g_ in np.unique(g):
        ix = np.nonzero(g == g_)[0]
        a, b = km[ix], ko[ix]
        nxt = np.full(len(ix), np.nan)
        later = np.nan
        for q in range(len(ix) - 1, -1, -1):              # (from the end: who took it at the first row after q where a count rose)
            if q + 1 < len(ix):
                da, db = a[q + 1] - a[q], b[q + 1] - b[q]
                if da > 0 and db <= 0:
                    later = 1.0
                elif db > 0 and da <= 0:
                    later = 0.0
                elif da > 0 and db > 0:
                    later = np.nan
            nxt[q] = later
        y[ix] = nxt
    reach = (wm < FAR) | (wo < FAR)
    y = np.where(pres & reach, y, np.nan)
    return Tm, To, tsp, pres & reach, y


def fit_tau(R):
    xs, ys = [], []
    for j in range(2):
        Tm, To, tsp, ok, y = race(R, j)
        m = ok & np.isfinite(y) & (tsp <= RACE_TSP)
        xs.append((To - Tm)[m])
        ys.append(y[m])
    x, y = np.concatenate(xs), np.concatenate(ys)
    best = None
    for tau in np.exp(np.linspace(np.log(0.1), np.log(30.0), 200)):
        p = np.clip(1.0 / (1.0 + np.exp(-np.clip(x / tau, -40, 40))), 1e-9, 1 - 1e-9)
        nll = -float(np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
        if best is None or nll < best[1]:
            best = (float(tau), nll)
    tau = best[0]
    p = 1.0 / (1.0 + np.exp(-np.clip(x / tau, -40, 40)))
    bins = []
    for lo in np.arange(0.0, 1.0, 0.1):
        m = (p >= lo) & (p < lo + 0.1 + (1e-9 if lo >= 0.9 else 0))
        if m.sum():
            bins.append(dict(p=round(float(p[m].mean()), 3), took=round(float(y[m].mean()), 3), rows=int(m.sum())))
    base = -float(np.mean(y * np.log(0.5) + (1 - y) * np.log(0.5)))
    return tau, dict(rows=int(len(y)), nll=round(best[1], 4), nll_half=round(base, 4), bins=bins)


def parts(R):
    """the judge's inputs at every row and each item's gain to each player (the judge's own value of a stack)"""
    dm, do = R["my_dead"] > 0.5, R["op_dead"] > 0.5
    own = lambda p, d: np.stack([np.where(d, 0.0, (R[p + "_" + w] > 0.5).astype(float)) for w in ("rl", "lg", "rg")], 1)   # noqa: E731
    return dict(d=R["my_score"] - R["op_score"], left=np.maximum(R["left"], 0.0), hpa=R["my_hp"], ara=R["my_ar"], da=dm, wa=own("my", dm),
                hpb=R["op_hp"], arb=R["op_ar"], db=do, wb=own("op", do))


def terms(P, X, R, tau):
    """per item: w-free contribution pieces: p [n], gain a [n], gain b [n], tsp [n], reach&present [n]"""
    t = np.maximum(X["left"], 0.0) / WJ.GAME_LEN
    Sa, Sb = WJ.parts(X["hpa"], X["ara"], X["da"]), WJ.parts(X["hpb"], X["arb"], X["db"])
    ha, hb = WJ.value(P, Sa, X["wa"], t), WJ.value(P, Sb, X["wb"], t)
    out = []
    for j in range(2):
        Tm, To, tsp, ok, _ = race(R, j)
        p = 1.0 / (1.0 + np.exp(-np.clip((To - Tm) / tau, -40, 40)))
        ga = np.maximum(WJ.value(P, WJ._with_item(X["hpa"], X["ara"], X["da"], j), X["wa"], t) - ha, 0.0)
        gb = np.maximum(WJ.value(P, WJ._with_item(X["hpb"], X["arb"], X["db"], j), X["wb"], t) - hb, 0.0)
        out.append((p, ga, gb, tsp, ok & (tsp < X["left"])))
    s = np.sqrt(0.02 + X["left"] * WJ._sp(WJ._mlp(P, "s", t, np)[..., 0], np))
    mu = ha - hb
    return out, mu, s


def chance(mu, s, d, T, K, H):
    I = np.zeros_like(mu)
    for j, (p, ga, gb, tsp, ok) in enumerate(T):
        I = I + K[j] * ok * np.exp(-tsp / H) * (p * ga - (1.0 - p) * gb)
    return np.clip(1.0 / (1.0 + np.exp(-(d + mu + I) / s)), 1e-9, 1 - 1e-9)


def nll_rows(p, y):
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--judge", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--folds", type=int, default=5)
    a = ap.parse_args()
    P, meta = WJ.load(a.judge)
    R = FB.rows(a.folders)
    need = [c for c in ("mh_present", "mh_tsp", "mh_my_walk", "mh_op_walk", "mh_my_took", "mh_op_took") if c not in R]
    assert not need, "the rows have no items' race (record with WS_ITEMS=1): {}".format(need)
    reg = R["t"] < FB.GF                                    # (as fit_b: regulation of games decided in it, overtime rows of the others)
    use = np.where(R["ot_game"] > 0.5, ~reg, reg)
    y = np.where(R["final_my"] > R["final_op"], 1.0, np.where(R["final_my"] < R["final_op"], 0.0, 0.5))
    tau, rrep = fit_tau(R)
    print("the race: tau {:.3f} s on {} rows (log loss {} against a coin's {})".format(tau, rrep["rows"], rrep["nll"], rrep["nll_half"]))
    for b in rrep["bins"]:
        print("   p {:.3f}  took {:.3f}  ({} rows)".format(b["p"], b["took"], b["rows"]))
    X = parts(R)
    T, mu, s = terms(P, X, R, tau)
    d = X["d"]
    g = R["g"]
    games = np.unique(g[use])
    rng = np.random.default_rng(7)
    fold = dict(zip(games, rng.permutation(len(games)) % a.folds))
    gf = np.array([fold.get(x, -1) for x in g])
    p0 = chance(mu, s, d, T, (0.0, 0.0), 10.0)
    # (decided here, 1.9a) K = 1 for both items: an item is worth to each player exactly the stack the judge itself says it brings, weighted by
    # the race; only the horizon is chosen on how games ended (held out by game). The free K of a grid is fitted beside it as a readout only:
    # game outcomes are too noisy to set it (the smoke test's folds chose 2.0 and 1.5 for the mega, 0 for the red armor).
    K1 = (1.0, 1.0)

    def pick(rows_, grid_):
        bf = None
        for k_, H_ in grid_:
            v = float(nll_rows(chance(mu, s, d, T, k_, H_), y)[rows_].mean())
            if bf is None or v < bf[1]:
                bf = ((k_, H_), v)
        return bf[0]
    gridH = [(K1, H_) for H_ in HS]
    gridK = [((k1_, k2_), H_) for k1_ in KS for k2_ in KS for H_ in HS]
    (_, H) = pick(use, gridH)
    (kf_, Hf_) = pick(use, gridK)
    ho1, hof = np.zeros(len(y)), np.zeros(len(y))
    chosen, chosen_f = [], []
    for f in range(a.folds):
        tr, te = use & (gf != f), use & (gf == f)
        c_ = pick(tr, gridH)
        chosen.append(c_[1])
        ho1[te] = nll_rows(chance(mu, s, d, T, K1, c_[1]), y)[te]
        cf_ = pick(tr, gridK)
        chosen_f.append([float(cf_[0][0]), float(cf_[0][1]), float(cf_[1])])
        hof[te] = nll_rows(chance(mu, s, d, T, cf_[0], cf_[1]), y)[te]
    ho0 = nll_rows(p0, y)
    gu = g[use]
    per0 = {x: ho0[use][gu == x].mean() for x in games}
    per1 = {x: ho1[use][gu == x].mean() for x in games}
    wts = {x: int((gu == x).sum()) for x in games}
    diffs = []
    for _ in range(a.boot):
        pk_ = rng.choice(games, len(games))
        w_ = np.array([wts[x] for x in pk_], float)
        diffs.append(float((np.array([per1[x] - per0[x] for x in pk_]) * w_).sum() / w_.sum()))
    dlo, dhi = float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))
    l0, l1, lf = float(ho0[use].mean()), float(ho1[use].mean()), float(hof[use].mean())
    k1, k2 = K1
    print("held out by game ({} games, {} rows): log loss judge {:.5f}, with the items (K 1) {:.5f}, difference {:+.5f} (95% {:+.5f} .. {:+.5f}); "
          "the folds chose the horizons {}".format(len(games), int(use.sum()), l0, l1, l1 - l0, dlo, dhi, chosen))
    print("readout only: K free on a grid {:.5f} held out (the folds chose {}; on all games K {} horizon {})".format(lf, chosen_f, kf_, Hf_))
    print("on all games: K mega 1, K red 1, horizon {} s".format(H))
    # the items' worth in a few states (a's chance with less without), 300 s left, level score
    IP = dict(version=1, tau=tau, horizon=H, k=[float(k1), float(k2)], dead_walk=DEAD_WALK, far=FAR)
    ex = []
    for (hp_a, ar_a, hp_b, ar_b) in ((100, 0, 100, 0), (125, 50, 125, 50), (50, 0, 150, 100), (150, 100, 50, 0)):
        for (wa_, wb_) in ((2.0, 6.0), (6.0, 2.0), (4.0, 4.0)):
            z = lambda v: np.array([float(v)])            # noqa: E731
            ra = dict(present=np.array([[True, False]]), tsp=np.zeros((1, 2)), walk=np.array([[wa_, FAR]]))
            rb = dict(present=np.array([[True, False]]), tsp=np.zeros((1, 2)), walk=np.array([[wb_, FAR]]))
            w0 = np.array([[1.0, 1.0, 0.0]])
            c1 = float(WJ.chance_items(P, IP, z(0), z(300), z(hp_a), z(ar_a), np.array([False]), w0, z(hp_b), z(ar_b), np.array([False]), w0, ra, rb)[0])
            c0 = float(WJ.chance(P, z(0), z(300), WJ.parts(z(hp_a), z(ar_a), np.array([False])), w0, WJ.parts(z(hp_b), z(ar_b), np.array([False])), w0)[0])
            ex.append(dict(me=[hp_a, ar_a], him=[hp_b, ar_b], mega_up_me_s=wa_, him_s=wb_, chance=round(c1, 4), without=round(c0, 4), worth=round(c1 - c0, 4)))
            print("   me {}/{} him {}/{}, the mega up, me {:.0f} s him {:.0f} s: chance {:.4f} (without the items {:.4f}: {:+.4f})".format(
                hp_a, ar_a, hp_b, ar_b, wa_, wb_, c1, c0, c1 - c0))
    # axioms: K >= 0 by the grid; nearer never lowers his chance (checked on the rows: him 1 s nearer to each item)
    bad = 0
    for j in range(2):
        Tn = [list(x) for x in T]
        Tm, To, _, _, _ = race(R, j)
        Tn[j][0] = 1.0 / (1.0 + np.exp(-np.clip((To - (Tm - 1.0)) / tau, -40, 40)))     # (him a second nearer)
        bad += int((chance(mu, s, d, Tn, (k1, k2), H) < chance(mu, s, d, T, (k1, k2), H) - 1e-12).sum())
    cal_ok = all(abs(b["p"] - b["took"]) <= 0.07 for b in rrep["bins"] if b["rows"] >= 200)
    enough = len(games) >= MIN_GAMES and rrep["rows"] >= MIN_RACE
    acc = bool(enough and cal_ok and dlo <= 0.0 and bad == 0 and k1 >= 0 and k2 >= 0)
    rep = dict(IP, judge=os.path.abspath(a.judge), accepted=acc, race=rrep, heldout=dict(games=int(len(games)), rows=int(use.sum()), judge=round(l0, 6),
               with_items=round(l1, 6), diff=round(l1 - l0, 6), diff_95=[round(dlo, 6), round(dhi, 6)], folds_chose=[float(c) for c in chosen]),
               free_k=dict(heldout=round(lf, 6), folds_chose=chosen_f, all_games=[[float(x) for x in kf_], float(Hf_)]), enough_data=enough,
               examples=ex, axiom_failures=bad, calibrated=cal_ok, folders=[os.path.abspath(f) for f in a.folders])
    json.dump(rep, open(a.out, "w", encoding="utf-8"), indent=1)
    print("ACCEPTED" if acc else "NOT ACCEPTED (enough data {} ({} games of {}, {} race rows of {}), calibrated {}, held-out difference's interval "
          "reaches 0 or below {}, axiom failures {})".format(enough, len(games), MIN_GAMES, rrep["rows"], MIN_RACE, cal_ok, dlo <= 0.0, bad))
    print("written: " + a.out)
    return 0 if acc else 1


if __name__ == "__main__":
    sys.exit(main())
