"""His pay split by term over recorded whole games, and what WIN_PAY would have paid in the same games beside the flat
frag pay it takes out (v0.4.3's cross-fade; the owner, 2026-10-23).

    python tools/pay_ledger.py <games_*.npz ...> [--json <file>]
    (any Python with numpy; the games from tools/winpay_games.py, the terms from the simulator's own split: PAY_SPLIT)

Per term, over both seats of every kept game (each seat is the network):
  per min      the term's pay a player-minute (signed)
  +/min, -/min what it pays and what it costs a player-minute
  size %       the share of the pay's size: |x| summed frame by frame
  game sd      the spread of one seat's sum over a game (between games: what can tell one game from another)
  var %        the share of the variance of a seat's whole-game pay: cov(term, total) / var(total) (sums to 100)
  zero-sum     the two seats' game sums against each other: -1.00 = what one gets the other loses
Then the flat frag pay (frag + death), the shadow WIN_PAY (what WIN_PAY would pay: the frames of the game, its overtime
included) and their sizes a game; the check that a seat's shadow sums to scale x (result - 0.5) over a game.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import winpay_games as WG  # noqa: E402

GROUPS = [("frags and deaths (flat)", ("frag", "death", "deaths_other")),
          ("damage", ("dmg_dealt", "dmg_taken", "high")),
          ("items: flat pickups", ("item_MH", "item_RA", "item_YA", "item_flat_other")),
          ("items: big-weapon order", ("big_order", "drops", "item_points", "item_loss", "items_other", "item_seek")),
          ("stack difference", ("stack_diff",)),
          ("stack kept (bare cost)", ("stack_keep",)),
          ("way and speed", ("way", "way_claw", "speed", "speed_run", "intent_switch", "runs", "hop")),
          ("watching, pre-aim", ("watch", "preaim")),
          ("knowing where he is", ("know",)),
          ("rail", ("rail",)),
          ("costs of the hands", ("jerk", "weapon_switch", "fire_toggle", "shot_price", "blind_fire", "blind_rocket", "lg_quiet")),
          ("other", ("move_round", "course", "style", "win_pay"))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="+")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    G, frames, terms = [], 0, None
    tot_abs = None
    sh_chk = []
    scale = 0.0
    win_g, flat_g, ws_abs, fl_abs, frag_n = [], [], [], [], []
    for g in WG.iter_games(a.games):
        terms, scale = g["terms"], g["scale"]
        P = g["pay"].astype(np.float64)                      # [F, 2, K]
        F = P.shape[0]
        frames += F
        sums = P.sum(0)                                      # [2, K]
        pos = np.clip(P, 0, None).sum(0)
        neg = np.clip(P, None, 0).sum(0)
        ab = np.abs(P).sum(0)
        tot_abs = ab if tot_abs is None else tot_abs + ab
        ws = g["wshadow"].astype(np.float64).sum(0)
        fl = g["flat"].astype(np.float64).sum(0)
        for s in (0, 1):
            res = g["res_ot"] if s == 0 else 1.0 - g["res_ot"]
            sh_chk.append(ws[s] - g["scale"] * (res - 0.5))
            G.append(dict(sums=sums[s], pos=pos[s], neg=neg[s], F=F, res=res, map=g["map"], ws=ws[s], fl=fl[s]))
        win_g.append(ws[0])
        flat_g.append(fl[0])
        ws_abs.append(np.abs(g["wshadow"].astype(np.float64)).sum(0).mean())
        fl_abs.append(np.abs(g["flat"].astype(np.float64)).sum(0).mean())
        frag_n.append(float((g["pay"][:, :, terms.index("frag")] > 0).sum()))
    assert G, "no games"
    K = len(terms)
    S = np.array([x["sums"] for x in G])                    # [seat-games, K]
    PO = np.array([x["pos"] for x in G]).sum(0)
    NE = np.array([x["neg"] for x in G]).sum(0)
    pmin = frames * 2 * 0.025 / 60.0                        # player-minutes: frames x 2 seats
    tot = S.sum(1)
    vt = tot.var()
    cov = np.array([np.cov(S[:, k], tot)[0, 1] if S[:, k].std() > 0 else 0.0 for k in range(K)])
    zs = []
    for k in range(K):
        x0, x1 = S[0::2, k], S[1::2, k]
        zs.append(float(np.corrcoef(x0, x1)[0, 1]) if x0.std() > 0 and x1.std() > 0 else float("nan"))
    size = tot_abs.sum(0)
    rows = []
    for k in range(K):
        if size[k] <= 0:
            continue
        rows.append(dict(term=terms[k], per_min=float(S[:, k].sum() / pmin), plus=float(PO[k] / pmin), minus=float(NE[k] / pmin),
                         size_share=float(size[k] / size.sum()), game_sd=float(S[:, k].std()), var_share=float(cov[k] / vt),
                         zero_sum=zs[k], per_game=float(S[:, k].mean())))
    rows.sort(key=lambda r: -r["size_share"])
    n_g = len(G) // 2
    mins = frames * 0.025 / 60.0 / n_g
    print("{} whole games ({} seat-games), {:.1f} game-minutes each on average (overtime included), {:.0f} player-minutes".format(
        n_g, len(G), mins, pmin))
    print("his total pay a player-minute: {:+.4f}; a seat's whole-game pay: mean {:+.3f}, sd {:.3f}".format(tot.sum() / pmin, tot.mean(), tot.std()))
    print("\n{:18s} {:>9s} {:>9s} {:>9s} {:>7s} {:>8s} {:>7s} {:>8s}".format("term", "per min", "+/min", "-/min", "size%", "game sd", "var%", "zero-sum"))
    for r in rows:
        print("{:18s} {:+9.4f} {:9.4f} {:9.4f} {:6.1f}% {:8.3f} {:6.1f}% {:8.2f}".format(
            r["term"], r["per_min"], r["plus"], r["minus"], 100 * r["size_share"], r["game_sd"], 100 * r["var_share"], r["zero_sum"]))
    print("\nby group (size share | var share | +/min of what it pays):")
    grp = []
    for nm, ks in GROUPS:
        ix = [terms.index(k) for k in ks if k in terms]
        sz = float(size[ix].sum() / size.sum())
        vs = float(sum(cov[i] for i in ix) / vt)
        Sg = S[:, ix].sum(1)
        grp.append(dict(group=nm, size_share=sz, var_share=vs, plus=float(PO[ix].sum() / pmin), minus=float(NE[ix].sum() / pmin),
                        game_sd=float(Sg.std())))
        print("  {:28s} {:6.1f}% | {:6.1f}% | +{:.3f} -{:.3f} a minute | game sd {:.3f}".format(nm, 100 * sz, 100 * vs, PO[ix].sum() / pmin,
                                                                                         -NE[ix].sum() / pmin, Sg.std()))
    fl = np.array([x["fl"] for x in G])
    ws = np.array([x["ws"] for x in G])
    fi = terms.index("frag")
    di = terms.index("death")
    print("\nthe flat frag pay and WIN_PAY in the same games (a seat's game):")
    print("  flat (frag + death) sum: mean {:+.3f}, sd {:.2f}; frags a seat-game {:.1f}, deaths {:.1f}".format(
        fl.mean(), fl.std(), S[:, fi].mean(), -S[:, di].mean()))
    print("  shadow WIN_PAY sum: mean {:+.3f}, sd {:.2f} (= scale x (result - 0.5): +-{:.2f} a decided game, 0 a draw)".format(
        ws.mean(), ws.std(), 0.5 * scale))
    print("  size frame by frame (|x| summed, a seat-game): flat {:.2f}, WIN_PAY {:.2f} (ratio {:.2f})".format(
        np.mean(fl_abs), np.mean(ws_abs), np.mean(ws_abs) / max(1e-9, np.mean(fl_abs))))
    print("  corr of a seat's game sum with its result: flat {:.3f}, WIN_PAY {:.3f}".format(
        np.corrcoef(fl, [x["res"] for x in G])[0, 1], np.corrcoef(ws, [x["res"] for x in G])[0, 1]))
    print("  WIN_PAY sum minus scale x (result - 0.5), a seat-game: max |.| {:.2e} (0: the path does not matter)".format(np.abs(sh_chk).max()))
    print("  WIN_PAY's size against the rest of his pay a player-minute: WIN_PAY {:.3f}, flat {:.3f}, all the other terms {:.3f}".format(
        np.sum(ws_abs) * 2 / pmin, np.sum(fl_abs) * 2 / pmin, (size.sum() - size[fi] - size[di]) / pmin))
    res = np.array([x["res"] for x in G])
    print("  results: seat 0 won {}, drew {}, lost {} of {}".format(int((res[0::2] == 1).sum()), int((res[0::2] == 0.5).sum()),
                                                                  int((res[0::2] == 0).sum()), n_g))
    if a.json:
        json.dump(dict(games=n_g, player_minutes=pmin, terms=rows, groups=grp,
                       flat=dict(mean=float(fl.mean()), sd=float(fl.std()), size=float(np.mean(fl_abs))),
                       win=dict(mean=float(ws.mean()), sd=float(ws.std()), size=float(np.mean(ws_abs)), check=float(np.abs(sh_chk).max()))),
                  open(a.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
