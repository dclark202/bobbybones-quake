"""Is the network's value ready to carry the game when the shaping pays fade (v0.4.3's cross-fade; the owner, 2026-10-23)?

    python tools/value_ready.py <games_*.npz ...> [--every 10] [--json <file>]
    (Anaconda Python (scipy) or any numpy; the games from tools/winpay_games.py, which records his value outputs frame by
    frame: v, the main value at the run's gamma (0.999, the whole pay), and v2, the value of the item and stack part of
    the pay (r_long) at the fight's gamma (0.999) and at --long-gamma (0.9998); the checkpoint names them v.weight and
    v2.weight, read from the GRU state test_suite.Policy plays)

(a) How well the values predict what comes:
    calibration  each value against the return it estimates in these games (the discounted sum of the pay that came,
                 cut at the game's end as the trainer cuts it): explained variance, the slope of the return on the value
                 (1: calibrated), by situation (his lead, the time left, his stack, the enemy in view)
    the result   every 30 s of a game: the chance of winning by the pros' table at that moment (the shadow WIN_PAY's own
                 chance) and the two seats' value difference against the game's result; what the value adds to the table
                 (the correlation of the value difference with what the table leaves unexplained)
    next frags   the value difference against the frag difference of the next 30 and 60 s
(b) The implied item value: at each pickup of the mega, the red armor and a yellow armor, the jump in his values from 0.5 s
    before to 0.1 s after (with the pay that came in between), his and the enemy's: the whole value, its item-and-stack
    part (v2), its fight part (v - v2 at the same gamma); against the pickup's measured effect in these games: on his
    chance of winning in the next 30 / 60 / 120 s (WIN_PAY units: a frag at 0:0 = 1) and on the return of the fight part
    (the pay that is not items or stack), each less the mean of moments like it without a pickup (the same minute of the
    game, his lead, his stack). The effect is a comparison, not a cause: who reaches the mega first is often the stronger
    seat at that moment. Also the stack's own worth: his chance in the next 60 s against the stack difference, within
    the same moments, times what the pickup added to his stack.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import winpay_games as WG  # noqa: E402

G_MAIN, G_LONG = 0.999, 0.9998
ITEMS = ("item_MH", "item_RA", "item_YA")


def disc(x, g, chunk=4000):
    """the discounted sum from every frame on (cut at the end), along axis 0 (in chunks: g^-k stays in range)"""
    x = np.asarray(x, np.float64)
    out = np.zeros_like(x)
    carry = np.zeros(x.shape[1:])
    for e in range(len(x), 0, -chunk):
        s0 = max(0, e - chunk)
        k = np.arange(e - s0, dtype=np.float64)
        w = (g ** k).reshape((-1,) + (1,) * (x.ndim - 1))
        y = x[s0:e] * w
        suf = np.cumsum(y[::-1], 0)[::-1]
        out[s0:e] = suf / w + carry * (g ** (e - s0 - k)).reshape(w.shape)
        carry = out[s0]
    return out


def ev(y, v):
    y, v = np.asarray(y, np.float64), np.asarray(v, np.float64)
    if len(y) < 10 or y.var() <= 0:
        return dict(n=len(y), ev=float("nan"), slope=float("nan"), corr=float("nan"), bias=float("nan"))
    return dict(n=len(y), ev=float(1.0 - np.var(y - v) / np.var(y)), slope=float(np.polyfit(v, y, 1)[0]) if v.std() > 0 else float("nan"),
                corr=float(np.corrcoef(y, v)[0, 1]) if v.std() > 0 else float("nan"), bias=float((v - y).mean()))


def corr(x, y):
    x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
    return float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 and x.std() > 0 and y.std() > 0 else float("nan")


def tbin(left, ot):
    return 4 if ot else 0 if left > 420 else 1 if left > 240 else 2 if left > 60 else 3


TB = ("10-7 min left", "7-4", "4-1", "last minute", "overtime")
LB = ("3+ behind", "1-2 behind", "level", "1-2 ahead", "3+ ahead")
SB = ("stack <100", "100-149", "150-199", "200+")


def lbin(d):
    return 0 if d <= -3 else 1 if d < 0 else 2 if d == 0 else 3 if d < 3 else 4


def sbin(s):
    return 0 if s < 100 else 1 if s < 150 else 2 if s < 200 else 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="+")
    ap.add_argument("--every", type=int, default=10, help="sample every this many frames for (a)")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    C = {k: [] for k in ("v", "g1", "v20", "gl0", "v21", "gl1", "lb", "tb", "sb", "vis")}
    R = {k: [] for k in ("p", "vd", "v2d", "res", "tb", "nf30", "nf60")}
    PK = []                                                   # pickups
    CT = []                                                   # control moments: (stratum, y30, y60, y120, fight return, stackdiff, g, ...)
    gi = 0
    for g in WG.iter_games(a.games):
        terms = g["terms"]
        dt, sc = g["dt"], g["scale"]
        rew = g["rew"].astype(np.float64)
        rl = g["rlong"].astype(np.float64)
        v, v2 = g["v"].astype(np.float64), g["v2"].astype(np.float64)
        F = len(rew)
        G1, GL0, GL1 = disc(rew, G_MAIN), disc(rl, G_MAIN), disc(rl, G_LONG)
        GF = G1 - GL0                                         # the fight part's return (the pay that is not items or stack)
        W = g["wshadow"].astype(np.float64)
        cw = np.vstack([np.zeros((1, 2)), np.cumsum(W, 0)])
        p0 = 0.5 + cw[1:, 0] / sc                             # seat 0's chance after each frame (the game starts level at 0:00)
        fr = g["frags"].astype(np.int64)
        lead0 = fr[:, 0] - fr[:, 1]
        tick = g["tick"].astype(np.int64)
        ot = tick > g["game_frames"]
        left = np.where(ot, 0.0, g["game_frames"] - tick) * dt
        st = np.maximum(g["hp"].astype(np.float64), 0) + g["armor"].astype(np.float64)
        alive = g["hp"] > 0
        vis = g["vis"]
        # (a) calibration
        ix = np.arange(0, F, a.every)
        for s in (0, 1):
            ld = lead0 if s == 0 else -lead0
            m = ix[alive[ix, s]]
            C["v"] += list(v[m, s]); C["g1"] += list(G1[m, s])
            C["v20"] += list(v2[m, s, 0]); C["gl0"] += list(GL0[m, s])
            C["v21"] += list(v2[m, s, 1]); C["gl1"] += list(GL1[m, s])
            C["lb"] += [lbin(x) for x in ld[m]]
            C["tb"] += [tbin(l_, o_) for l_, o_ in zip(left[m], ot[m])]
            C["sb"] += [sbin(x) for x in st[m, s]]
            C["vis"] += list(vis[m, s])
        # the result and the next frags, every 30 s
        step = int(round(30.0 / dt))
        nf = np.zeros(F + 1)
        dl = np.diff(np.concatenate([[0], lead0]))
        nf[1:] = np.cumsum(dl)
        for t in range(step - 1, F - 1, step):
            R["p"].append(p0[t]); R["vd"].append(v[t, 0] - v[t, 1]); R["v2d"].append(v2[t, 0, 1] - v2[t, 1, 1])
            R["res"].append(g["res_ot"]); R["tb"].append(tbin(left[t], ot[t]))
            R["nf30"].append(nf[min(F, t + 1 + int(30 / dt))] - nf[t + 1]); R["nf60"].append(nf[min(F, t + 1 + int(60 / dt))] - nf[t + 1])
        # (b) pickups and the moments like them
        pk_t = {}
        for nm in ITEMS:
            if nm not in terms:
                continue
            col = g["pay"][:, :, terms.index(nm)]
            for t, s in zip(*np.nonzero(col > 0)):
                pk_t.setdefault(int(t), []).append((int(s), nm))
        near = np.zeros(F, bool)
        for t in pk_t:
            near[max(0, t - 200):t + 200] = True
        H = {h: int(round(h / dt)) for h in (30, 60, 120)}
        for t, lst in pk_t.items():
            tb_, ta_ = t - 20, t + 4
            if tb_ < 0 or ta_ >= F:
                continue
            for s, nm in lst:
                o = 1 - s
                ld = int(lead0[tb_] if s == 0 else -lead0[tb_])
                rec = dict(item=nm[5:], map=g["map"], g=gi, strat=(int(min(10, tick[t] * dt // 60)) if not ot[t] else 11, max(-3, min(3, ld)), sbin(st[tb_, s])))
                for who, q in (("him", s), ("enemy", o)):
                    rec[who + "_total"] = float(v[ta_, q] - v[tb_, q] + rew[tb_:ta_, q].sum())
                    rec[who + "_long"] = float(v2[ta_, q, 1] - v2[tb_, q, 1] + rl[tb_:ta_, q].sum())
                    rec[who + "_fight"] = float((v[ta_, q] - v2[ta_, q, 0]) - (v[tb_, q] - v2[tb_, q, 0]) + (rew - rl)[tb_:ta_, q].sum())
                rec["pay_in_window"] = float(rew[tb_:ta_, s].sum())
                rec["item_pay"] = float(g["pay"][t, s, terms.index(nm)])
                for h, n_ in H.items():
                    rec["y%d" % h] = float(cw[min(F, t + n_), s] - cw[t, s])
                rec["gf"] = float(GF[ta_, s])
                rec["stack_gain"] = float(st[ta_, s] - st[tb_, s])
                rec["stack_before"] = float(st[tb_, s])
                PK.append(rec)
        for t in range(40, F - 1, 40):
            for s in (0, 1):
                if not alive[t, s]:
                    continue
                ld = int(lead0[t] if s == 0 else -lead0[t])
                mn_ = int(min(10, tick[t] * dt // 60)) if not ot[t] else 11
                CT.append(((mn_, max(-3, min(3, ld)), sbin(st[t, s])),
                           cw[min(F, t + H[30]), s] - cw[t, s], cw[min(F, t + H[60]), s] - cw[t, s], cw[min(F, t + H[120]), s] - cw[t, s],
                           GF[t, s], (st[t, s] - st[t, 1 - s]) / 100.0, gi, float(alive[t, 1 - s]), st[t, s], st[t, 1 - s], ld, mn_,
                           v[t, s], v2[t, s, 1], v[t, s] - v2[t, s, 0], float(near[t])))
        gi += 1
    assert gi, "no games"
    out = dict(games=gi)
    C = {k: np.array(v_) for k, v_ in C.items()}
    print("{} games; (a) calibration over {} sampled frames of a living seat".format(gi, len(C["v"])))
    print("\n{:34s} {:>7s} {:>7s} {:>7s} {:>8s}".format("value against its return", "EV", "slope", "corr", "bias"))
    cal = {}
    for nm, vk, gk in (("v (all pay, 0.999)", "v", "g1"), ("v2[0] (items+stack, 0.999)", "v20", "gl0"), ("v2[1] (items+stack, 0.9998)", "v21", "gl1"),
                       ("v - v2[0] (the fight part)", None, None)):
        if vk is None:
            e = ev(C["g1"] - C["gl0"], C["v"] - C["v20"])
        else:
            e = ev(C[gk], C[vk])
        cal[nm] = e
        print("{:34s} {:7.3f} {:7.3f} {:7.3f} {:+8.3f}".format(nm, e["ev"], e["slope"], e["corr"], e["bias"]))
    print("\nby situation: EV (slope) of v | of v2[1] | of the fight part")
    sit = {}
    for key, names in (("lb", LB), ("tb", TB), ("sb", SB), ("vis", ("enemy not in view", "enemy in view"))):
        for j, nm in enumerate(names):
            m = C[key] == j
            if m.sum() < 50:
                continue
            e1, e2, e3 = ev(C["g1"][m], C["v"][m]), ev(C["gl1"][m], C["v21"][m]), ev(C["g1"][m] - C["gl0"][m], C["v"][m] - C["v20"][m])
            sit[nm] = dict(n=int(m.sum()), v=e1, v21=e2, fight=e3)
            print("  {:22s} n {:6d} | {:6.3f} ({:5.2f}) | {:6.3f} ({:5.2f}) | {:6.3f} ({:5.2f})".format(
                nm, int(m.sum()), e1["ev"], e1["slope"], e2["ev"], e2["slope"], e3["ev"], e3["slope"]))
    out["calibration"], out["by_situation"] = cal, sit
    R = {k: np.array(v_, np.float64) for k, v_ in R.items()}
    print("\nthe game's result (seat 0), every 30 s: corr with the table's chance, with the value difference, and what the value adds")
    res_rows = {}
    for j, nm in list(enumerate(TB)) + [(-1, "all")]:
        m = (R["tb"] == j) if j >= 0 else np.ones(len(R["p"]), bool)
        if m.sum() < 20:
            continue
        y, p, vd, v2d = R["res"][m], R["p"][m], R["vd"][m], R["v2d"][m]
        resid = y - np.polyval(np.polyfit(p, y, 1), p) if p.std() > 0 else y - y.mean()
        rr = dict(n=int(m.sum()), table=corr(p, y), v=corr(vd, y), v2long=corr(v2d, y), v_beyond_table=corr(vd, resid),
                  v2long_beyond_table=corr(v2d, resid), nf30_v=corr(vd, R["nf30"][m]), nf60_v=corr(vd, R["nf60"][m]),
                  nf60_table=corr(p, R["nf60"][m]))
        res_rows[nm] = rr
        print("  {:14s} n {:5d} | table {:+.3f} | v {:+.3f} | v2[1] {:+.3f} | beyond the table: v {:+.3f}, v2[1] {:+.3f} | next frags 30 s: v {:+.3f}; "
              "60 s: v {:+.3f}, table {:+.3f}".format(nm, rr["n"], rr["table"], rr["v"], rr["v2long"], rr["v_beyond_table"], rr["v2long_beyond_table"],
                                                     rr["nf30_v"], rr["nf60_v"], rr["nf60_table"]))
    out["result"] = res_rows
    # (b)
    print("\n(b) the implied item value: {} pickups".format(len(PK)))
    strat = {}
    for c in CT:
        if not c[15]:                                         # (the moments like a pickup: none within 5 s of one)
            strat.setdefault(c[0], []).append(c[1:6])
    smean = {k: np.mean(np.array(v_), 0) for k, v_ in strat.items() if len(v_) >= 5}
    allm = np.mean(np.array([c[1:6] for c in CT if not c[15]]), 0)
    # the price of stack: each value and what came after, regressed on his stack, the enemy's (per 100), the lead and the
    # minute of the game (moments with both alive)
    M_ = np.array([c[1:] for c in CT if c[7] > 0], np.float64)     # (y30, y60, y120, fight return, stack diff, game, enemy alive,
    #                                                                  his stack, the enemy's, lead, minute, v, v2[1], v - v2[0])
    X_ = np.column_stack([M_[:, 7] / 100.0, M_[:, 8] / 100.0, M_[:, 9]] + [(M_[:, 10] == j).astype(float) for j in range(12)])
    price = {}
    print("    the price of 100 stack (his / the enemy's), moments with both alive, n {}: (lead and minute of the game held)".format(len(M_)))
    for nm, col in (("v (his value, all pay)", 11), ("v2[1] (items+stack value, 0.9998)", 12), ("fight part v - v2[0]", 13),
                    ("measured: his chance, next 60 s", 1), ("measured: his chance, next 120 s", 2), ("measured: fight return (0.999)", 3)):
        c_ = np.linalg.lstsq(X_, M_[:, col], rcond=None)[0]
        price[nm] = dict(own=float(c_[0]), enemy=float(c_[1]), lead=float(c_[2]))
        print("      {:36s} his {:+.3f}  the enemy's {:+.3f}  a frag of lead {:+.3f}".format(nm, c_[0], c_[1], c_[2]))
    b_stack = price["measured: his chance, next 60 s"]["own"]
    b_stack120 = price["measured: his chance, next 120 s"]["own"]
    b_v = price["v (his value, all pay)"]["own"]
    b_vl = price["v2[1] (items+stack value, 0.9998)"]["own"]
    b_vf = price["fight part v - v2[0]"]["own"]
    items = {}
    print("\n  {:5s} {:>4s} | {:>23s} | {:>23s} | {:>23s} | {:>8s} | {:>27s} | {:>9s} | {:>8s}".format(
        "item", "n", "his value jump total", "long (v2[1])", "fight (v - v2[0])", "enemy", "measured: dWin 30/60/120 s", "fight ret", "via stack"))
    print("      (the jump is the value's surprise at the pickup: a value that saw the pickup coming jumps by little; the item's price in\n"
          "       the value is the stack price above times the stack it adds: the columns at the right of the second table)")
    for it in ("MH", "RA", "YA"):
        L_ = [r for r in PK if r["item"] == it]
        if not L_:
            continue
        def eff(key, col):
            return np.array([r[key] - smean.get(r["strat"], allm)[col] for r in L_])
        e30, e60, e120, ef = eff("y30", 0), eff("y60", 1), eff("y120", 2), eff("gf", 3)
        mean_ = lambda k_: float(np.mean([r[k_] for r in L_]))     # noqa: E731
        se = lambda x: float(np.std(x) / np.sqrt(max(1, len(x))))  # noqa: E731
        gain = mean_("stack_gain")
        d = dict(n=len(L_), him_total=mean_("him_total"), him_long=mean_("him_long"), him_fight=mean_("him_fight"),
                 enemy_total=mean_("enemy_total"), enemy_long=mean_("enemy_long"), enemy_fight=mean_("enemy_fight"),
                 item_pay=mean_("item_pay"), pay_in_window=mean_("pay_in_window"),
                 dwin30=float(e30.mean()), dwin60=float(e60.mean()), dwin120=float(e120.mean()), dwin120_se=se(e120), dwin60_se=se(e60),
                 fight_return=float(ef.mean()), fight_return_se=se(ef), stack_gain=gain, via_stack60=b_stack * gain / 100.0,
                 via_stack120=b_stack120 * gain / 100.0, stack_before=mean_("stack_before"),
                 value_price=b_v * gain / 100.0, value_price_long=b_vl * gain / 100.0, value_price_fight=b_vf * gain / 100.0)
        items[it] = d
        print("  {:5s} {:4d} | {:+.3f} (pay {:.2f} in it) | {:+.3f}                  | {:+.3f}                  | {:+.3f}   | "
              "{:+.3f} / {:+.3f} / {:+.3f} (+-{:.3f}) | {:+.3f}    | {:+.3f}".format(
                  it, d["n"], d["him_total"], d["pay_in_window"], d["him_long"], d["him_fight"], d["enemy_total"], d["dwin30"], d["dwin60"],
                  d["dwin120"], d["dwin120_se"], d["fight_return"], d["via_stack120"]))
    print("\n  the item's price: in his value (the stack price x the stack added) against what it was worth to his chance")
    print("  {:5s} {:>10s} | {:>9s} {:>9s} {:>9s} | {:>14s} {:>14s} {:>16s}".format("item", "stack add", "v", "v2[1]", "fight", "dWin 120 s pickups",
                                                                                  "dWin 120 via stack", "flat pay now"))
    for it, d in items.items():
        print("  {:5s} {:10.1f} | {:+9.3f} {:+9.3f} {:+9.3f} | {:+14.3f} {:+14.3f} {:16.2f}".format(it, d["stack_gain"], d["value_price"],
              d["value_price_long"], d["value_price_fight"], d["dwin120"], d["via_stack120"], d["item_pay"]))
    print("    (his value jump: from 0.5 s before to 0.1 s after the pickup, the pay in between added: the network's own price of the "
          "pickup in pay units, its flat item pay included; measured: the next seconds of his chance less moments like it)")
    out["items"], out["stack_price"] = items, price
    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"), indent=1, default=float)


if __name__ == "__main__":
    main()
