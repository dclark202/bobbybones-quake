"""Does each shaping pay pull toward winning? For every term of his pay (the simulator's split, PAY_SPLIT): does what it
pays predict the change in his chance of winning over the next 30, 60, 120 s and the game's result (v0.4.3's
cross-fade and the fades after it; the owner, 2026-10-23)?

    python tools/pay_align.py <games_*.npz ...> [--block 5] [--boot 300] [--json <file>]
    (any Python with numpy; the games from tools/winpay_games.py)

The chance of winning is the pros' table (sim/win_chance.json, as WIN_PAY reads it, with overtime), in WIN_PAY's units:
the shadow WIN_PAY summed over a stretch is WIN_SCALE x (the chance at its end - the chance at its start); a game's end
counts as its result. Measures, each with a 90% interval by resampling whole games:
  game     between the two seats of a game: corr(term's sum seat 0 - seat 1, result seat 0 - seat 1), the game's result
           after overtime (1 / 0.5 / 0): does the seat that earns more of it win?
  then+H   blocks of --block seconds per seat: corr(the term's pay in the block, the change of his chance from the block's
           start to H s after its end)
  next+H   the same from the block's end on (what comes after the pay: for frags, not the frag itself)
  slope60  the change of his chance (WIN_PAY units) in the 60 s after the block per unit of the term's pay in it
Aligned: the term's pay goes with winning (game or next+60 above 0, the interval clear of 0); misaligned: against it; else
unclear. A term that is aligned is one the value may carry once it is faded out; a misaligned one pays for habits that do
not win and is the first to fade or to watch. Correlation is not cause: a term that pays for being ahead (the stack
difference) is aligned because leaders win.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import winpay_games as WG  # noqa: E402

HS = (30, 60, 120)


def corr(x, y):
    x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
    if len(x) < 3 or x.std() <= 0 or y.std() <= 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="+")
    ap.add_argument("--block", type=float, default=5.0)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--min-share", type=float, default=0.001, help="terms under this share of the pay's size are listed as negligible only")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    terms = None
    GD, GR = [], []                                          # per game: term sums seat 0 - seat 1; result difference
    BX, BYn, BYt, BG = [], {h: [] for h in HS}, {h: [] for h in HS}, []    # blocks: term pay, next change, then change, game index
    gi = 0
    for g in WG.iter_games(a.games):
        terms = g["terms"]
        P = g["pay"].astype(np.float64)                      # [F, 2, K]
        W = g["wshadow"].astype(np.float64)                  # [F, 2]
        F = P.shape[0]
        S = P.sum(0)
        GD.append(S[0] - S[1])
        GR.append(2.0 * g["res_ot"] - 1.0)
        L = int(round(a.block / g["dt"]))
        cw = np.vstack([np.zeros((1, 2)), np.cumsum(W, 0)])  # cumulative shadow: cw[t] = sum of frames < t
        nb = F // L
        for b in range(nb):
            t0, t1 = b * L, (b + 1) * L
            x = P[t0:t1].sum(0)                              # [2, K]
            for s in (0, 1):
                BX.append(x[s])
                BG.append(gi)
                for h in HS:
                    e = min(F, t1 + int(round(h / g["dt"])))
                    BYn[h].append(cw[e, s] - cw[t1, s])
                    BYt[h].append(cw[e, s] - cw[t0, s])
        gi += 1
    assert gi, "no games"
    K = len(terms)
    GD, GR = np.array(GD), np.array(GR)
    BX, BG = np.array(BX), np.array(BG)
    BYn = {h: np.array(v) for h, v in BYn.items()}
    BYt = {h: np.array(v) for h, v in BYt.items()}
    rng = np.random.default_rng(0)
    idx_by_g = [np.nonzero(BG == j)[0] for j in range(gi)]
    boots = [rng.integers(0, gi, gi) for _ in range(a.boot)]
    boot_rows = [np.concatenate([idx_by_g[j] for j in bs]) for bs in boots]

    def ci(f):
        v = np.array([f(bs, br) for bs, br in zip(boots, boot_rows)])
        v = v[np.isfinite(v)]
        return (float(np.percentile(v, 5)), float(np.percentile(v, 95))) if len(v) > 10 else (float("nan"), float("nan"))
    tot_abs = np.abs(BX).sum(0)
    rows = []
    small = [terms[k] for k in range(K) if 0 < tot_abs[k] < a.min_share * tot_abs.sum()]
    for k in range(K):
        if tot_abs[k] < a.min_share * tot_abs.sum() or tot_abs[k] <= 0:
            continue
        x = BX[:, k]
        r = dict(term=terms[k], size_share=float(tot_abs[k] / tot_abs.sum()), blocks_paid=float((x != 0).mean()))
        r["game"] = corr(GD[:, k], GR)
        r["game_ci"] = ci(lambda bs, br: corr(GD[bs, k], GR[bs]))
        for h in HS:
            r["next%d" % h] = corr(x, BYn[h])
            r["then%d" % h] = corr(x, BYt[h])
        r["next60_ci"] = ci(lambda bs, br: corr(x[br], BYn[60][br]))
        r["slope60"] = float(np.polyfit(x, BYn[60], 1)[0]) if x.std() > 0 else float("nan")
        g_ok = r["game_ci"][0] > 0
        n_ok = r["next60_ci"][0] > 0
        g_bad = r["game_ci"][1] < 0
        n_bad = r["next60_ci"][1] < 0
        r["verdict"] = "misaligned" if (g_bad or n_bad) and not (g_ok or n_ok) else "aligned" if (g_ok or n_ok) and not (g_bad or n_bad) \
            else "mixed" if (g_ok or n_ok) else "unclear"
        rows.append(r)
    order = {"aligned": 0, "mixed": 1, "unclear": 2, "misaligned": 3}
    rows.sort(key=lambda r: (order[r["verdict"]], -(r["next60"] if np.isfinite(r["next60"]) else -9)))
    print("{} games, {} blocks of {:g} s per seat; intervals: 90% by resampling games ({}x)".format(gi, len(BX), a.block, a.boot))
    print("\n{:16s} {:>6s} {:>16s} {:>7s} {:>7s} {:>7s} {:>16s} {:>7s} {:>7s} {:>8s}  {}".format(
        "term", "size%", "game [90%]", "then30", "then60", "next30", "next60 [90%]", "next120", "paid%", "slope60", "verdict"))
    for r in rows:
        print("{:16s} {:5.1f}% {:+6.2f} [{:+.2f},{:+.2f}] {:+7.3f} {:+7.3f} {:+7.3f} {:+6.3f} [{:+.3f},{:+.3f}] {:+7.3f} {:6.1f}% {:+8.3f}  {}".format(
            r["term"], 100 * r["size_share"], r["game"], r["game_ci"][0], r["game_ci"][1], r["then30"], r["then60"], r["next30"],
            r["next60"], r["next60_ci"][0], r["next60_ci"][1], r["next120"], 100 * r["blocks_paid"], r["slope60"], r["verdict"]))
    print("negligible (under {:.1%} of the pay's size): {}".format(a.min_share, ", ".join(small) or "none"))
    print("(a cost term (jerk, shot price, ...) that is misaligned costs what goes with winning: the seat that pays more of it wins more)")
    # the groups of the ledger
    import pay_ledger as PL
    print("\nby group (the ledger's): game corr, next60 corr, slope60")
    grp = []
    for nm, ks in PL.GROUPS:
        ix = [terms.index(k_) for k_ in ks if k_ in terms]
        if not ix or tot_abs[ix].sum() <= 0:
            continue
        x = BX[:, ix].sum(1)
        gd = GD[:, ix].sum(1)
        gr = dict(group=nm, game=corr(gd, GR), game_ci=ci(lambda bs, br: corr(gd[bs], GR[bs])), next60=corr(x, BYn[60]),
                  next60_ci=ci(lambda bs, br: corr(x[br], BYn[60][br])), next120=corr(x, BYn[120]),
                  slope60=float(np.polyfit(x, BYn[60], 1)[0]) if x.std() > 0 else float("nan"))
        grp.append(gr)
        print("  {:28s} game {:+.2f} [{:+.2f},{:+.2f}] | next60 {:+.3f} [{:+.3f},{:+.3f}] | next120 {:+.3f} | slope60 {:+.3f}".format(
            nm, gr["game"], gr["game_ci"][0], gr["game_ci"][1], gr["next60"], gr["next60_ci"][0], gr["next60_ci"][1], gr["next120"], gr["slope60"]))
    # the whole pay without the flat frag pay: how it goes with winning
    ex = [terms.index(k_) for k_ in ("frag", "death", "deaths_other") if k_ in terms]
    keep = [k for k in range(K) if k not in ex]
    xs = BX[:, keep].sum(1)
    print("\nall the shaping (everything but frag/death): game {:+.2f}, next60 {:+.3f}, next120 {:+.3f}; the flat frag pay: game {:+.2f}, "
          "then60 {:+.3f}, next60 {:+.3f}".format(corr(GD[:, keep].sum(1), GR), corr(xs, BYn[60]), corr(xs, BYn[120]),
                                                  corr(GD[:, ex].sum(1), GR), corr(BX[:, ex].sum(1), BYt[60]), corr(BX[:, ex].sum(1), BYn[60])))
    if a.json:
        json.dump(dict(games=gi, block=a.block, terms=rows, groups=grp), open(a.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
