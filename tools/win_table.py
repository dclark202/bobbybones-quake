"""His own win-chance table from his whole self-play games, beside the pros' (sim/win_chance.json), cell by cell; and what
it would change in what a frag pays under WIN_PAY (v0.4.3's cross-fade; the owner, 2026-10-23).

    python tools/win_table.py <games_*.npz ...> [--people T:/quake-sessions/public] [--out <his table.json>] [--prior 200]
    (any Python with numpy; the games from tools/winpay_games.py)

His table is made exactly as tools/win_chance.py makes the pros' (the same counts: both players of every game, the lead
at every 30 s step and the game's result; the same two-number model, the same prior and ordering), from:
  "ten"   the result at ten minutes, level = half a win: the pros' definition (their table has no overtime);
  "ot"    the result after overtime (the run plays OVERTIME=1: a level game goes on in periods of two minutes), level at
          the cap = half. With OVERTIME, WIN_PAY reads the table with the seconds left in the period, so "ot" is the one a
          frag in his training would be paid by.
The people's duels (duels.jsonl + frags.jsonl of the public servers; read only, no names: a person is a key) are put in
the same cells as counts only: there are few, and nearly all are one-sided.
Printed: the three tables, the counts, his minus the pros' by cell with both counts, the model's two numbers, the scale (a
frag at 0:0 with ten minutes left), a frag's pay by the two tables at chosen moments and averaged over the states his
games visit, and the share of his games' frags whose pay would change by more than 25%.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import win_chance as WC  # noqa: E402

DT = 0.025


def his_games(paths):
    """the kept games of tools/winpay_games.py's files -> win_chance's game records (ten minutes), plus the final result and the
    score changes as (frame tick, seat 0 / 1, change), and the map"""
    out = []
    for p in paths:
        d = np.load(p, allow_pickle=False)
        meta = json.loads(str(d["meta"]))
        gs = json.loads(str(d["games"]))
        fr, tick, gnum = d["frags"], d["tick"], d["gnum"]
        for g in gs:
            m = g["match"]
            rows = np.nonzero(gnum[:, m] == g["gid"])[0]
            if not len(rows) or g.get("reg") is None:
                continue
            q = [2 * m, 2 * m + 1]
            sc = fr[rows][:, q].astype(np.int64)
            prev = np.vstack([[0, 0], sc[:-1]])
            ev = []
            for r_, (s_, p_) in enumerate(zip(sc, prev)):
                for seat in (0, 1):
                    dd = int(s_[seat] - p_[seat])
                    if dd:
                        ev.append((float(tick[rows[r_], m]) * DT, seat, dd, int(tick[rows[r_], m])))
            ten = [(c, s, dd) for c, s, dd, _ in ev if c <= WC.GAME_S + 1e-9]
            fin = g["final"]
            out.append(dict(map=meta["map"], ev=ten, ev_all=ev, win=None, end=WC.GAME_S, reg=g["reg"], final=fin, ot=g.get("ot", 0),
                            src=os.path.basename(p)))
    return out


def counts_ot(gs):
    """as win_chance.counts, with the result after overtime (level at the cap: half)"""
    n = np.zeros((len(WC.LEFT), len(WC.DIFFS)))
    w = np.zeros((len(WC.LEFT), len(WC.DIFFS)))
    for g in gs:
        ev = sorted(g["ev"])
        tc = np.array([e[0] for e in ev], np.float64)
        cum = np.concatenate([[0.0], np.cumsum([e[2] if e[1] == 0 else -e[2] for e in ev])])
        f = g["final"][0] - g["final"][1]
        res = 1.0 if f > 0 else 0.0 if f < 0 else 0.5
        for i, left in enumerate(WC.LEFT):
            d = int(cum[int(np.searchsorted(tc, WC.GAME_S - left, side="right"))])
            for sgn, r in ((1, res), (-1, 1.0 - res)):
                j = int(np.clip(sgn * d, -WC.MAX_D, WC.MAX_D)) + WC.MAX_D
                n[i, j] += 1
                w[i, j] += r
    return n, w


def people_games(folder):
    """the people's whole duels against Bobby (forfeit 0) with their score changes from frags.jsonl; kept only where the
    frags give the final score (deaths by one's own hand are not in frags.jsonl: up to three a side are let go, and the
    result is the recorded score's)"""
    dp, fp = os.path.join(folder, "duels.jsonl"), os.path.join(folder, "frags.jsonl")
    if not (os.path.exists(dp) and os.path.exists(fp)):
        return [], {}
    D = [json.loads(x) for x in open(dp, encoding="utf-8") if x.strip()]
    F = [json.loads(x) for x in open(fp, encoding="utf-8") if x.strip()]
    F = [f for f in F if f.get("mode") == "duel" and f.get("state") == "in_progress"]
    out, why = [], {}
    for d in D:
        if d.get("kind") != "game" or d.get("forfeit") or float(d.get("minutes", 0)) < 10.0 - 1e-6:
            why["forfeit or short"] = why.get("forfeit or short", 0) + 1
            continue
        t1 = float(d["t"])
        t0 = t1 - 60.0 * float(d["minutes"])
        fr = [f for f in F if f["map"] == d["map"] and t0 - 2.0 <= float(f["t"]) <= t1 + 2.0]
        ev, sc = [], [0, 0]                                   # seat 0 Bobby, seat 1 the person
        for f in sorted(fr, key=lambda x: x["t"]):
            k, v = str(f["killer"]), str(f["victim"])
            c = max(0.0, float(f["t"]) - t0)
            kb, vb = k.startswith("bobby"), v.startswith("bobby")
            if k == v or k in ("", "world", "None"):
                s = 0 if vb else 1
                ev.append((c, s, -1))
                sc[s] -= 1
            else:
                s = 0 if kb else 1
                ev.append((c, s, 1))
                sc[s] += 1
        want = [int(d["score"][1]), int(d["score"][0])]          # (duels.jsonl: [the person, Bobby]; here seat 0 is Bobby)
        if any(sc[j] < want[j] or sc[j] - want[j] > 3 for j in (0, 1)):     # (deaths by his own hand are not in frags.jsonl: up to 3 a side)
            why["frags do not give the score"] = why.get("frags do not give the score", 0) + 1
            continue
        sc = want
        ten = [e for e in ev if e[0] <= WC.GAME_S]
        out.append(dict(map=d["map"], ev=ten, win=None, end=WC.GAME_S, final=sc))
    return out, why


def show_diff(ph, pp, nh, npro, title):
    print(title)
    cols = list(range(-6, 7))
    print("  left " + " ".join("{:>11d}".format(c) for c in cols))
    for i in range(len(WC.LEFT) - 1, 0, -2):
        cells = []
        for c in cols:
            j = WC.MAX_D + c
            cells.append("{:+5.1f}({:>4d})".format(100.0 * (ph[i, j] - pp[i, j]), int(nh[i, j])))
        print("{:>3d}:{:02d} ".format(int(WC.LEFT[i]) // 60, int(WC.LEFT[i]) % 60) + " ".join(cells))
    print("    (his minus the pros', points of %; in brackets his count; every second row)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="+")
    ap.add_argument("--pros", default=os.path.join(ROOT, "sim", "win_chance.json"))
    ap.add_argument("--people", default="")
    ap.add_argument("--prior", type=float, default=200.0)
    ap.add_argument("--out", default="", help="his table (\"ot\") as a win_chance.json (WIN_CHANCE=<file> plays it)")
    ap.add_argument("--json", default="", help="the comparison's numbers")
    a = ap.parse_args()
    paths = sorted({p for g in a.games for p in glob.glob(g)})
    gs = his_games(paths)
    assert gs, "no games"
    pro = json.load(open(a.pros, encoding="utf-8"))
    pp, npro = np.array(pro["p"], np.float64), np.array(pro["n"], np.float64)
    reg = np.array([g["reg"] for g in gs], np.float64)
    fin = np.array([g["final"] for g in gs], np.float64)
    ot = np.array([g["ot"] for g in gs])
    nfr = np.array([sum(1 for e in g["ev"] if e[2] > 0) for g in gs])
    print("his games: {} (from {} files; maps {}); frags+ a game in ten minutes {:.1f}; |lead| at ten minutes: mean {:.1f}, "
          "median {:.0f}; level at ten {} ({:.0%}), of those decided in overtime {}; overtime periods {}".format(
              len(gs), len(paths), sorted({g["map"] for g in gs}), nfr.mean(), np.abs(reg[:, 0] - reg[:, 1]).mean(),
              np.median(np.abs(reg[:, 0] - reg[:, 1])), int((reg[:, 0] == reg[:, 1]).sum()), float((reg[:, 0] == reg[:, 1]).mean()),
              int(((reg[:, 0] == reg[:, 1]) & (fin[:, 0] != fin[:, 1])).sum()), int(ot.sum())))
    print("pros: {} games, {} played out, {} level at ten; |lead| at ten minutes is not in the file; frags a game {}".format(
        pro["about"]["games"], pro["about"]["played_out"], pro["about"]["ended_level_at_ten_minutes"], pro["about"]["score_changes_a_game"]))
    res = {}
    for tag, (n, w) in (("ten", WC.counts(gs)[:2]), ("ot", counts_ot(gs))):
        v, k, ll, ll0 = (float(x) for x in WC.fit(n, w))
        p, m = WC.table(n, w, v, k, a.prior)
        res[tag] = dict(p=p, n=n, w=w, v=v, k=k, model=m)
        print("\n== his table, result {} == the model: frag-difference variance a minute {:.3f} (pros {}), strength-difference sd "
              "in ten minutes {:.2f} frags (pros {}); log-lik {:.1f} vs equal players {:.1f}; scale {:.3f} (pros {:.3f})".format(
                  "at ten minutes (the pros' definition)" if tag == "ten" else "after overtime (his training's)", v * 60.0,
                  pro["about"]["model"]["frag_difference_variance_a_minute"], np.sqrt(k) * WC.GAME_S,
                  pro["about"]["model"]["strength_difference_sd_frags_in_ten_minutes"], -ll, -ll0, WC.scale_of(p), WC.scale_of(pp)))
    WC.show_table(res["ten"]["p"], res["ten"]["n"], "his chance of winning at ten minutes, % (rows: time left; columns: his lead)")
    WC.show_table(pp, npro, "the pros' (sim/win_chance.json), %")
    emp = np.where(res["ten"]["n"] > 0, res["ten"]["w"] / np.maximum(res["ten"]["n"], 1), np.nan)
    WC.show_table(np.where(np.isfinite(emp), emp, 0.0), None, "his counts' own shares (ten minutes), % (0.0 where nobody was)")
    show_diff(res["ten"]["p"], pp, res["ten"]["n"], npro, "\nhis table (ten minutes) minus the pros', by cell")
    show_diff(res["ot"]["p"], pp, res["ot"]["n"], npro, "\nhis table (after overtime) minus the pros', by cell")
    # where they differ: cells both have 30+ sightings of
    for tag in ("ten", "ot"):
        both = (res[tag]["n"] >= 30) & (npro >= 30) & (WC.LEFT[:, None] > 0) & (WC.DIFFS[None, :] != 0)
        dd = (res[tag]["p"] - pp)[both]
        e_h = np.where(res[tag]["n"] > 0, res[tag]["w"] / np.maximum(res[tag]["n"], 1), np.nan)
        print("{}: cells with 30+ sightings in both: {}; his table minus the pros' there: mean {:+.3f}, mean |.| {:.3f}, largest {:+.3f}; "
              "his counts' share minus the pros' table: mean |.| {:.3f}".format(tag, int(both.sum()), float(dd.mean()) if both.any() else 0,
                                                                              float(np.abs(dd).mean()) if both.any() else 0,
                                                                              float(dd[np.abs(dd).argmax()]) if both.any() else 0,
                                                                              float(np.nanmean(np.abs(e_h - pp)[both])) if both.any() else 0))
    # what a frag pays
    fpp = WC.frag_pays(pp)
    print("\na frag's pay (WIN_SCALE x the step in the table; a frag at 0:0 with ten minutes left = 1), the pros' table / his (ten) / his (ot)")
    print("   moment                          pros    his10   hisOT")
    picks = [("level, 10:00 left", 20, 0), ("level, 5:00 left", 10, 0), ("level, 2:00 left", 4, 0), ("level, 0:30 left", 1, 0),
             ("1 ahead, 5:00", 10, 1), ("1 behind, 5:00", 10, -1), ("3 ahead, 5:00", 10, 3), ("3 behind, 5:00", 10, -3),
             ("5 ahead, 5:00", 10, 5), ("5 behind, 5:00", 10, -5), ("3 ahead, 1:00", 2, 3), ("3 behind, 1:00", 2, -3),
             ("8 ahead, 2:00", 4, 8)]
    fh = {t: WC.frag_pays(res[t]["p"]) for t in ("ten", "ot")}
    rows = []
    for nm, i, d in picks:
        j = WC.MAX_D + d
        r_ = (float(fpp[i, j]), float(fh["ten"][i, j]), float(fh["ot"][i, j]))
        rows.append((nm, r_))
        print("   {:30s} {:7.3f} {:7.3f} {:7.3f}".format(nm, *r_))
    # averaged over the moments of his frags: the lead before and the time left of every frag in his games
    fr_states = []
    for g in gs:
        cum = 0
        for c, s, dd in sorted(g["ev"]):
            if dd > 0:
                lead = cum if s == 0 else -cum                       # the scorer's lead before
                fr_states.append((min(WC.GAME_S, max(0.0, WC.GAME_S - c)), lead))
            cum += dd if s == 0 else -dd
    fs = np.array(fr_states, np.float64)

    def pay_at(fp, left, lead):
        x = np.clip(left / WC.STEP_S, 0.0, len(WC.LEFT) - 1.0)
        i0 = np.minimum(x.astype(np.int64), len(WC.LEFT) - 2)
        fr = x - i0
        j = (np.clip(lead, -WC.MAX_D, WC.MAX_D - 1) + WC.MAX_D).astype(np.int64)
        P = np.vstack([fp, fp[-1:]])
        return P[i0, j] * (1 - fr) + P[i0 + 1, j] * fr
    out_ = {}
    if len(fs):
        a_p = pay_at(fpp, fs[:, 0], fs[:, 1])
        for t in ("ten", "ot"):
            a_h = pay_at(fh[t], fs[:, 0], fs[:, 1])
            ch = np.abs(a_h - a_p) / np.maximum(a_p, 1e-6)
            out_[t] = dict(mean_pros=float(a_p.mean()), mean_his=float(a_h.mean()), corr=float(np.corrcoef(a_p, a_h)[0, 1]),
                           share_changed_25=float((ch > 0.25).mean()), share_changed_50=float((ch > 0.5).mean()),
                           his_over_pros_median=float(np.median(a_h / np.maximum(a_p, 1e-9))))
            print("over his {} frags (the lead before and the time left at each): mean pay pros {:.3f}, his-{} {:.3f}; correlation {:.3f}; "
                  "median his/pros {:.2f}; frags whose pay changes by more than 25%: {:.0%}, by more than 50%: {:.0%}".format(
                      len(fs), a_p.mean(), t, a_h.mean(), out_[t]["corr"], out_[t]["his_over_pros_median"], out_[t]["share_changed_25"],
                      out_[t]["share_changed_50"]))
        print("    (the flat pay today: 1.0 a frag everywhere; a frag's pay under the pros' table over his frags: "
              "share below 0.1: {:.0%}, above 1.5: {:.0%})".format(float((a_p < 0.1).mean()), float((a_p > 1.5).mean())))
    pg = []
    if a.people:
        pg, why = people_games(a.people)
        print("\nthe people's duels: {} whole games with their frags (left out: {})".format(len(pg), why))
        if pg:
            n3, w3, _ = WC.counts(pg)
            fin3 = np.array([g["final"] for g in pg])
            print("    Bobby won {} of {}; mean final score Bobby {:.1f} : {:.1f} the person (the people's cells below: both seats counted)".format(
                int((fin3[:, 0] > fin3[:, 1]).sum()), len(pg), fin3[:, 0].mean(), fin3[:, 1].mean()))
            e3 = np.where(n3 > 0, w3 / np.maximum(n3, 1), np.nan)
            # coarse cells: |lead| 1-2, 3-5, 6+ ahead, by time left 10-6, 6-2, 2-0 min
            print("    the leader's share of wins (people's games, both players counted) against the pros' table, coarse cells:")
            for lo, hi, nm in ((1, 2, "1-2 ahead"), (3, 5, "3-5 ahead"), (6, 10, "6+ ahead")):
                parts = []
                for t0, t1 in ((360, 600), (120, 330), (30, 90)):
                    I = (WC.LEFT >= t0) & (WC.LEFT <= t1)
                    J = (WC.DIFFS >= lo) & (WC.DIFFS <= hi)
                    nn_ = n3[np.ix_(I, J)].sum()
                    ww_ = w3[np.ix_(I, J)].sum()
                    pr_ = (pp[np.ix_(I, J)] * np.maximum(npro[np.ix_(I, J)], 1)).sum() / np.maximum(npro[np.ix_(I, J)], 1).sum()
                    parts.append("{:.0f}-{:.0f} min left: {} sightings, {:.0%} (pros {:.0%})".format(t0 / 60, t1 / 60, int(nn_),
                                                                                                    ww_ / nn_ if nn_ else float("nan"), pr_))
                print("      {:10s} ".format(nm) + " | ".join(parts))
    if a.out:
        p = res["ot"]["p"]
        res_ = dict(about=dict(what="his chance of winning (after overtime) by the time left and his lead, from his whole self-play games",
                               made_by="tools/win_table.py", games=len(gs), files=[os.path.basename(x) for x in paths],
                               model=dict(frag_difference_variance_a_minute=round(res["ot"]["v"] * 60.0, 4),
                                          strength_difference_sd_frags_in_ten_minutes=round(float(np.sqrt(res["ot"]["k"]) * WC.GAME_S), 2)),
                               prior=a.prior, scale=round(WC.scale_of(p), 6)),
                    left_s=[float(x) for x in WC.LEFT], diffs=[int(x) for x in WC.DIFFS], scale=WC.scale_of(p),
                    p=[[float(x) for x in r] for r in p], n=[[int(x) for x in r] for r in res["ot"]["n"]])
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res_, f)
        print("wrote", a.out)
    if a.json:
        json.dump(dict(games=len(gs), people=len(pg), frag_pay_moments=rows, over_his_frags=out_,
                       scale=dict(pros=WC.scale_of(pp), his_ten=WC.scale_of(res["ten"]["p"]), his_ot=WC.scale_of(res["ot"]["p"])),
                       model=dict(his_ten=[res["ten"]["v"] * 60, float(np.sqrt(res["ten"]["k"]) * WC.GAME_S)],
                                  his_ot=[res["ot"]["v"] * 60, float(np.sqrt(res["ot"]["k"]) * WC.GAME_S)])),
                  open(a.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
