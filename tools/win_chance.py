"""The pros' games -> sim/win_chance.json: a duel player's chance of winning the game by the score difference and the
time left (stage B part 4, docs/design/V02_STAGE_B.md; the simulator's WIN_PAY reads it).

    python tools/win_chance.py collect --limit 40          # read demos (about 0.4 s each, one process) into the cache
    python tools/win_chance.py collect                     # ... the whole archive (it goes on where the cache ends)
    python tools/win_chance.py table                       # the cache -> sim/win_chance.json, and the table printed
    python tools/win_chance.py table --out <file> --prior 200
    python tools/win_chance.py show [--file sim/win_chance.json]

What a game is here: a recording with the game's start and end in it, a clock that is known through timeouts (the
server's own level start time: tools/pro_yardsticks.py), exactly two players, and a final score by the deaths that equals
the score the recording shows for the player followed at the end. From every such game: the times of every change of the
score on the game's clock (a frag is a point for the killer; a death by his own hand or by the world takes a point off
the victim) and who it was for. Overtimes are not used: the result is who is ahead at ten minutes. A third of the pros'
games end before that because a player gives up: those count as a win for the other one (the one the game does not mark
as having forfeited, else the one ahead) from every moment up to there, and not after; left out they would take the
one-sided games out of the table. Two recordings of one game count once. No names are read or kept: a recording is known
by a hash of its file name; the cache keeps what was read, and what counts is judged when the table is made.

The table: p[time left][score difference], time left 0, 30, ..., 600 s, difference -10..10 (a larger lead counts as 10),
the chance of winning for the player who is that many frags ahead; "winning" is being ahead when the ten minutes are over,
level then is half a win (the simulator's whole games have no overtime). How it is made:
  1. Counts. For each game, each player and each time step: his lead at that moment and how the ten minutes ended for
     him (1, 0.5, 0). Both players of a game are counted, so the counts are symmetric.
  2. A model with two numbers, fitted to the counts by likelihood. The frags still to come are a random walk (their
     difference has variance v a second), and a lead says who the better player is: the two players' strengths differ by a
     rate s (frags a second) with variance k over the pros' pairings, and a lead of d after e seconds moves the belief in
     s to d k / (k e + v). So with t seconds left: p = Phi((d + t d k / (k e + v)) / sqrt(v t + t^2 k v / (k e + v))).
     It is symmetric, 0.5 when level, rises with the lead, and is 1 / 0.5 / 0 at the limit by itself. It is also what
     gives the row "600 s left": no game has a lead before its first second, and a frag at 0:0 with ten minutes left is
     the frag the simulator's scale is set by.
  3. Each cell is the count's share drawn toward the model: (wins + prior x model) / (n + prior). With a few hundred games
     the model stands nearly alone; with the whole archive the busy cells are the pros' own shares.
  4. Put in order: never lower for a larger lead, never lower for the same lead with less time left (pooling neighbours
     that break it, by their weights), mirrored so that p(-d) = 1 - p(d), level = 0.5, and the limit's row 1 / 0.5 / 0.
"""
import argparse
import glob
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE))
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure,houseofdecay,dismemberment"
GAME_S, STEP_S, MAX_D = 600.0, 30.0, 10
LEFT = np.arange(0.0, GAME_S + 1.0, STEP_S)                 # seconds left: 0, 30, ..., 600
DIFFS = np.arange(-MAX_D, MAX_D + 1)


def yardsticks():
    """tools/pro_yardsticks.py, whose reading of a demo this tool uses (the game's start and end, the clock, the deaths)"""
    for p in (os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "demodump")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import pro_yardsticks as Y
    return Y


def default_cache():
    return os.path.join(ROOT, "data", "win_chance", "games.jsonl")


def read_cache(path):
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def raw_of(rec, info):
    """a parsed demo (tools/pro_yardsticks.parse) -> what the cache keeps of it: every change of the score on the game's
    clock [[seconds, player 0 or 1, +1 or -1], ...] (overtimes too), where the clock ends, the score the recording shows at
    its end for whoever it followed; or the reason it could not be read"""
    if rec is None:
        return dict(skip=info.get("why", "not read"))
    if not (info.get("has_start") and info.get("has_end")):
        return dict(skip="no start or no end")
    ob = rec.get("obits")
    if ob is None:
        return dict(skip="no deaths list")
    t = np.asarray(rec["t"], np.float64)
    cl = rec.get("clock_exact")
    if cl is None or np.isfinite(cl).mean() < 0.9:              # (no events file, or no level start time: the plain clock, if no timeout stopped it)
        cl = rec["clock"]
    cl = np.asarray(cl, np.float64)
    ok = np.isfinite(cl)
    if ok.sum() < 800:
        return dict(skip="no clock")
    ob = ob[(ob[:, 0] >= t[0] - 0.5) & (ob[:, 0] <= t[-1] + 2.0)]
    oc = np.interp(ob[:, 0], t[ok], cl[ok])                     # each death on the game's clock
    who = sorted({int(x) for x in ob[:, 1]} | {int(x) for x in ob[:, 2] if x >= 0})
    if len(who) != 2:
        return dict(skip="{} players in the deaths".format(len(who)))
    ev = []
    for c, (_, v, k) in zip(oc, ob):
        v, k = int(v), int(k)
        p, d = (who.index(k), 1) if (k >= 0 and k != v) else (who.index(v), -1)
        ev.append([round(float(c), 3), p, d])
    seen = {str(who.index(int(c_))): int(s_) for c_, s_ in (info.get("final") or {}).items() if int(c_) in who}
    return dict(ev=ev, seen=seen, clock_end=round(float(cl[ok].max()), 2))


def judge(r):
    """a line of the cache -> (the game: its score changes inside the ten minutes, where it ended, who won if it ended
    early) or (None, the reason it does not count)"""
    if "ev" not in r:
        return None, r.get("skip", "?")
    L = float(r.get("len") or 0.0)
    all_ev = r["ev"]
    gave_up = [int(p) for p, s_ in r["seen"].items() if s_ <= -900]     # (the game puts a player who forfeits at -999)
    if L < GAME_S - 0.5 and all_ev and all_ev[-1][2] == -1 and all_ev[-1][0] >= r["clock_end"] - 1.5:
        gave_up = gave_up or [all_ev[-1][1]]                    # the game's last moment is his leaving (it takes a point off him:
        all_ev = all_ev[:-1]                                    # no part of the play, and not in the score the recording shows)
    final = [0, 0]
    for _, p, d in all_ev:
        final[p] += d
    for p, s_ in r["seen"].items():
        if s_ > -900 and s_ != final[int(p)]:
            return None, "the deaths do not make the score"
    if not r["seen"]:
        return None, "no score to check against"
    ev = [e for e in all_ev if 0.0 < e[0] <= GAME_S]
    if L >= GAME_S - 0.5:
        if r["clock_end"] < GAME_S - 1.0:
            return None, "the clock ends early"
        return dict(map=r["map"], ev=ev, end=GAME_S, win=None), None
    # ended before the ten minutes were over: a player gave up. He is the one the game marks, else the one behind
    end = min(float(r["clock_end"]), L)
    if gave_up:
        win = 1 - gave_up[0]
    elif final[0] != final[1]:
        win = 0 if final[0] > final[1] else 1
    else:
        return None, "ended early and level"
    return dict(map=r["map"], ev=ev, end=end, win=win), None


def collect(a):
    Y = yardsticks()
    Y.low_priority()
    cache = a.cache or default_cache()
    os.makedirs(os.path.dirname(os.path.abspath(cache)), exist_ok=True)
    have = {r["k"] for r in read_cache(cache)}
    tmp = tempfile.mkdtemp(prefix="winchance_", dir=a.tmp or None)   # the parsed demo of the moment (18 MB), removed after each
    n_new, t0 = 0, time.time()
    with open(cache, "a", encoding="utf-8") as out:
        for mp in a.maps.split(","):
            files = sorted(f for f in glob.glob(os.path.join(Y.demo_root(), "demos", mp, "*.dm_*")) if not f.endswith(".part"))
            if a.limit:
                files = files[::max(1, len(files) // a.limit)][:a.limit]
            for f in files:
                key = hashlib.sha1(os.path.basename(f).encode("utf-8", "replace")).hexdigest()[:16]
                if key in have:
                    continue
                try:
                    rec, info = Y.parse(f, tmp)
                    raw = raw_of(rec, info)
                except Exception as e:                           # noqa: BLE001 (a broken demo must not stop the batch)
                    raw, info = dict(skip="error " + type(e).__name__), {}
                row = dict(k=key, map=mp, len=info.get("length_s"))
                row.update(raw)
                out.write(json.dumps(row) + "\n")
                out.flush()
                have.add(key)
                n_new += 1
            print("{}: {} demos in the list, {} read so far in this call, {:.0f} s".format(mp, len(files), n_new, time.time() - t0), file=sys.stderr, flush=True)
    secs = time.time() - t0
    shutil.rmtree(tmp, ignore_errors=True)
    print("read {} demos in {:.0f} s ({:.2f} s a demo) into {}".format(n_new, secs, secs / max(1, n_new), cache))


def games(cache):
    """the cache -> the games that count, one of two recordings of the same game left out, and what was left out"""
    rows = read_cache(cache)
    out, seen, skips = [], set(), {}
    for r in rows:
        g, why = judge(r)
        if g is None:
            skips[why] = skips.get(why, 0) + 1
            continue
        sig = (g["map"], tuple((int(round(c * 10)), p, d) for c, p, d in g["ev"]))
        if sig in seen:
            skips["the same game again"] = skips.get("the same game again", 0) + 1
            continue
        seen.add(sig)
        out.append(g)
    return out, skips, len(rows)


def counts(gs):
    """(n, wins) by time left and lead, both players of every game; for the games played out their end and score changes"""
    n = np.zeros((len(LEFT), len(DIFFS)))
    w = np.zeros((len(LEFT), len(DIFFS)))
    ends = []
    for g in gs:
        ev = sorted(g["ev"])
        tc = np.array([e[0] for e in ev], np.float64)
        dd = np.array([e[2] if e[1] == 0 else -e[2] for e in ev], np.float64)     # the change of player 0's lead
        cum = np.concatenate([[0.0], np.cumsum(dd)])
        end = cum[-1]
        if g["win"] is None:                                     # played out: ahead at ten minutes, level is half
            res = 1.0 if end > 0 else 0.0 if end < 0 else 0.5
            ends.append((end, len(ev)))
        else:                                                    # a player gave up: the other one's win, from every moment before
            res = 1.0 if g["win"] == 0 else 0.0
        for i, left in enumerate(LEFT):
            if GAME_S - left > g["end"]:                         # (after he gave up there is no game)
                continue
            d = int(cum[int(np.searchsorted(tc, GAME_S - left, side="right"))])
            for sgn, r in ((1, res), (-1, 1.0 - res)):
                j = int(np.clip(sgn * d, -MAX_D, MAX_D)) + MAX_D
                n[i, j] += 1
                w[i, j] += r
    return n, w, ends


def _phi(x):
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(x, np.float64) / math.sqrt(2.0)))


def model(v, k, left=LEFT, diffs=DIFFS):
    """the two-number model's table (see the top of the file): v the variance of the frag difference a second, k the
    variance of the two players' difference in strength (frags a second) over the pairings"""
    t = np.asarray(left, np.float64)[:, None]
    d = np.asarray(diffs, np.float64)[None, :]
    e = GAME_S - t
    shift = k / (k * e + v)                                      # what a frag of lead moves the believed difference in strength by
    mean = d * (1.0 + t * shift)
    var = v * t + t * t * shift * v + 0.0 * d
    z = mean / np.sqrt(np.maximum(var, 1e-300))
    p = np.where(var > 0, _phi(np.clip(z, -40.0, 40.0)), np.where(mean > 0, 1.0, 0.0))
    return np.where(d == 0, 0.5, p)


def fit(n, w):
    """the model's two numbers by likelihood on the counts (no optimiser at hand in this Python: a grid, three times finer)"""
    use = np.ones_like(n, bool)
    use[0, :] = False                                            # the limit's row is 1 / 0.5 / 0 whatever the numbers
    use[:, MAX_D] = False                                        # level is 0.5

    def nll(v, k):
        p = np.clip(model(v, k), 1e-6, 1.0 - 1e-6)
        return -float((w * np.log(p) + (n - w) * np.log(1.0 - p))[use].sum())

    lv, lk = np.linspace(-3.5, -0.5, 25), np.linspace(-9.0, -2.0, 29)
    best = (1e300, 0.02, 0.0)
    for _ in range(3):
        for a_ in lv:
            for b_ in list(lk) + [None]:
                v, k = 10.0 ** a_, (0.0 if b_ is None else 10.0 ** b_)
                x = nll(v, k)
                if x < best[0]:
                    best = (x, v, k)
        cv, ck = math.log10(best[1]), (math.log10(best[2]) if best[2] > 0 else -9.0)
        sv, sk = (lv[1] - lv[0]), (lk[1] - lk[0])
        lv, lk = np.linspace(cv - sv, cv + sv, 13), np.linspace(ck - sk, ck + sk, 13)
    return best[1], best[2], best[0], min(nll(10.0 ** a_, 0.0) for a_ in np.linspace(-3.5, -0.5, 121))


def pava(y, wt, rising=True):
    """the nearest sequence that never falls (or never rises), by weights: neighbours that break the order are pooled"""
    y = np.asarray(y, np.float64) * (1.0 if rising else -1.0)
    blocks = []                                                  # [mean, weight, count]
    for yi, wi in zip(y, np.asarray(wt, np.float64)):
        blocks.append([yi, wi, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0] + 1e-15:
            b2, b1 = blocks.pop(), blocks.pop()
            ws = b1[1] + b2[1]
            blocks.append([(b1[0] * b1[1] + b2[0] * b2[1]) / ws if ws > 0 else 0.5 * (b1[0] + b2[0]), ws, b1[2] + b2[2]])
    out = np.concatenate([[b[0]] * b[2] for b in blocks])
    return out * (1.0 if rising else -1.0)


def limit_row():
    return np.where(DIFFS > 0, 1.0, np.where(DIFFS < 0, 0.0, 0.5))


def table(n, w, v, k, prior):
    """counts drawn toward the model, then put in order (see the top of the file)"""
    m = model(v, k)
    wt = n + prior
    p = (w + prior * m) / np.maximum(wt, 1e-9)
    p[0] = limit_row()
    for _ in range(200):
        q = p.copy()
        for i in range(1, len(LEFT)):                            # never lower for a larger lead
            p[i] = pava(p[i], wt[i], rising=True)
        for j in range(MAX_D + 1, len(DIFFS)):                   # ahead: never lower with less time left (the rows run from the limit on)
            p[1:, j] = pava(p[1:, j], wt[1:, j], rising=False)
            p[1:, 2 * MAX_D - j] = 1.0 - p[1:, j]
        p[:, MAX_D] = 0.5
        p = 0.5 * (p + (1.0 - p[:, ::-1]))                       # the mirror
        p[0] = limit_row()
        if np.abs(p - q).max() < 1e-13:
            break
    p = np.clip(p, 0.0, 1.0)
    return tidy(p), m


def tidy(p):
    """six places, the mirror and the middle to the last digit, the order kept (rounding cannot break it: it is monotone)"""
    p = np.round(np.asarray(p, np.float64), 6)
    for j in range(MAX_D):
        p[:, j] = np.round(1.0 - p[:, 2 * MAX_D - j], 6)
    p[:, MAX_D] = 0.5
    p[0] = limit_row()
    assert (np.diff(p, axis=1) >= -1e-12).all(), "not rising with the lead"
    assert (np.diff(p[:, MAX_D + 1:], axis=0) <= 1e-12).all(), "a lead worth more with more time left"
    assert np.abs(p + p[:, ::-1] - 1.0).max() < 1e-9
    return p


def scale_of(p):
    """what makes a frag at 0:0 with ten minutes left worth 1: the simulator's WIN_SCALE"""
    return 1.0 / (float(p[-1][MAX_D + 1]) - 0.5)


def show_table(p, n=None, title="the chance of winning, % (rows: time left; columns: the lead in frags)"):
    p = np.asarray(p, np.float64)
    cols = [d for d in range(-MAX_D, MAX_D + 1)]
    print(title)
    print("  left " + " ".join("{:>5d}".format(d) for d in cols))
    for i in range(len(LEFT) - 1, -1, -1):
        print("{:>3d}:{:02d} ".format(int(LEFT[i]) // 60, int(LEFT[i]) % 60) + " ".join("{:5.1f}".format(100.0 * p[i][MAX_D + d]) for d in cols))
    if n is not None:
        print("how often a player was in that cell (both players of every game)")
        print("  left " + " ".join("{:>5d}".format(d) for d in cols))
        for i in range(len(LEFT) - 1, -1, -1):
            print("{:>3d}:{:02d} ".format(int(LEFT[i]) // 60, int(LEFT[i]) % 60) + " ".join("{:5d}".format(int(n[i][MAX_D + d])) for d in cols))


def frag_pays(p):
    """a frag's pay by the table, in today's frags: scale x (p(d + 1) - p(d)) at each time step with time left"""
    p = np.asarray(p, np.float64)
    return scale_of(p) * np.diff(p, axis=1)                      # [time left][from the lead d = -10..9 to d + 1]


def make(a):
    cache = a.cache or default_cache()
    gs, skips, rows = games(cache)
    assert gs, "no games in {}: run `collect` first".format(cache)
    n, w, ends = counts(gs)
    v, k, ll, ll0 = (float(x) for x in fit(n, w))
    p, m = table(n, w, v, k, a.prior)
    sc = scale_of(p)
    fp = frag_pays(p)
    by_map = {}
    for g in gs:
        by_map[g["map"]] = by_map.get(g["map"], 0) + 1
    ends = np.array(ends, np.float64).reshape(-1, 2)
    gave_up = sum(1 for g in gs if g["win"] is not None)
    big = (n >= 30) & (np.arange(len(LEFT))[:, None] > 0) & (DIFFS[None, :] != 0)
    emp = np.where(n > 0, w / np.maximum(n, 1), np.nan)
    about = dict(
        what="a duel player's chance of winning the game (ahead when the ten minutes are over; level then is half a win) by the time left and his lead",
        made_by="tools/win_chance.py table", games=len(gs), played_out=len(ends), a_player_gave_up=gave_up, demos_read=rows, left_out=skips,
        games_by_map=by_map, score_changes_a_game=round(float(ends[:, 1].mean()), 1) if len(ends) else None,
        ended_level_at_ten_minutes=int((ends[:, 0] == 0).sum()),
        model=dict(frag_difference_variance_a_minute=round(v * 60.0, 4), strength_difference_sd_frags_in_ten_minutes=round(math.sqrt(k) * GAME_S, 2),
                   log_likelihood=round(-ll, 1), log_likelihood_equal_players=round(-ll0, 1)),
        prior=a.prior, cells_with_30_or_more=int(big.sum()),
        mean_gap_model_to_counts_in_those=round(float(np.abs(m - emp)[big].mean()), 4) if big.any() else None,
        mean_gap_table_to_counts_in_those=round(float(np.abs(p - emp)[big].mean()), 4) if big.any() else None,
        scale=round(sc, 6), a_frag_at_level_with_30_s_left=round(float(fp[1][MAX_D]), 3),
        a_frag_when_5_ahead_with_60_s_left=round(float(fp[2][MAX_D + 5]), 4))
    res = dict(about=about, left_s=[float(x) for x in LEFT], diffs=[int(x) for x in DIFFS], scale=sc,
               p=[[float(x) for x in row] for row in p], n=[[int(x) for x in row] for row in n])
    out = a.out or os.path.join(ROOT, "sim", "win_chance.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("{\n")
        f.write(' "about": ' + json.dumps(res["about"]) + ",\n")
        f.write(' "left_s": ' + json.dumps(res["left_s"]) + ",\n")
        f.write(' "diffs": ' + json.dumps(res["diffs"]) + ",\n")
        f.write(' "scale": ' + json.dumps(res["scale"]) + ",\n")
        f.write(' "p": [\n' + ",\n".join("  " + json.dumps(r) for r in res["p"]) + "\n ],\n")
        f.write(' "n": [\n' + ",\n".join("  " + json.dumps(r) for r in res["n"]) + "\n ]\n}\n")
    print("wrote {}".format(out))
    report(res, emp, m)


def report(res, emp=None, m=None):
    p, n, ab = np.array(res["p"]), np.array(res.get("n") or np.zeros((len(LEFT), len(DIFFS)))), res["about"]
    print("games: {} ({} played out, in {} a player gave up) of {} demos read; left out: {}; by map: {}".format(
        ab["games"], ab.get("played_out"), ab.get("a_player_gave_up"), ab["demos_read"], ab["left_out"], ab["games_by_map"]))
    print("score changes in a game played out: {} (frags and deaths by his own hand), level at ten minutes in {} games".format(
        ab.get("score_changes_a_game"), ab["ended_level_at_ten_minutes"]))
    print("the model: {}; drawn toward it with the weight of {} sightings a cell".format(ab["model"], ab["prior"]))
    print("cells with 30 or more sightings: {}; mean gap there, model to counts {} and table to counts {}".format(
        ab["cells_with_30_or_more"], ab["mean_gap_model_to_counts_in_those"], ab["mean_gap_table_to_counts_in_those"]))
    show_table(p, n)
    if m is not None:
        show_table(m, None, "the model alone, %")
    if emp is not None:
        show_table(np.where(np.isfinite(emp), emp, 0.0), None, "the counts' own shares, % (0.0 where nobody was)")
    fp = frag_pays(p)
    sc = scale_of(p)
    print("the scale: {:.4f} (a frag at 0:0 with ten minutes left: {:.2f}% -> {:.2f}%, worth exactly 1)".format(sc, 50.0, 100.0 * p[-1][MAX_D + 1]))
    print("a frag's pay in today's frags (scale x the step in the table), rows: time left, columns: the lead before it")
    cols = list(range(-MAX_D, MAX_D))
    print("  left " + " ".join("{:>6d}".format(d) for d in cols))
    for i in range(len(LEFT) - 1, 0, -1):
        print("{:>3d}:{:02d} ".format(int(LEFT[i]) // 60, int(LEFT[i]) % 60) + " ".join("{:6.3f}".format(x) for x in fp[i]))
    body = fp[1:]
    i, j = np.unravel_index(int(body.argmax()), body.shape)
    print("the largest on the table's steps: {:.3f} (from {:+d} with {:.0f} s left); between the last step and the limit it rises to {:.3f} "
          "(scale x 0.5: the frag that breaks a level score in the last second)".format(float(body[i, j]), int(DIFFS[j]), LEFT[1 + i], 0.5 * sc))
    i, j = np.unravel_index(int(body.argmin()), body.shape)
    print("the smallest: {:.5f} (from {:+d} with {:.0f} s left)".format(float(body[i, j]), int(DIFFS[j]), LEFT[1 + i]))
    print("examples: level with 30 s left {:.3f}; 5 ahead with 60 s left {:.5f}; 1 behind with 60 s left {:.3f}; 3 behind with 5 minutes left {:.3f}".format(
        float(fp[1][MAX_D]), float(fp[2][MAX_D + 5]), float(fp[2][MAX_D - 1]), float(fp[10][MAX_D - 3])))
    print("a whole game: winning from 0:0 pays scale x 0.5 = {:.3f} in all, losing the same less".format(0.5 * sc))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("collect", "table", "show"))
    ap.add_argument("--maps", default=MAPS)
    ap.add_argument("--limit", type=int, default=0, help="collect: at most this many demos a map, spread over the archive (0: all)")
    ap.add_argument("--cache", default=None, help="the games read so far, a line a demo (default data/win_chance/games.jsonl)")
    ap.add_argument("--tmp", default=None, help="collect: where the parsed demo of the moment is put")
    ap.add_argument("--out", default=None, help="table: the file written (default sim/win_chance.json)")
    ap.add_argument("--prior", type=float, default=200.0, help="table: the model's weight in a cell, in sightings")
    ap.add_argument("--file", default=None, help="show: the table's file")
    a = ap.parse_args()
    if a.what == "collect":
        return collect(a)
    if a.what == "table":
        return make(a)
    with open(a.file or os.path.join(ROOT, "sim", "win_chance.json"), encoding="utf-8") as f:
        report(json.load(f))


if __name__ == "__main__":
    main()
