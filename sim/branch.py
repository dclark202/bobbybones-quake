"""2.1 (docs/runs/2.1/DESIGN.md "The frozen moment"; the trainer's --branch-p): frozen-moment rounds in training. Between two
rollouts a moment of a self-play match (the source) is copied into other self-play matches of the same simulator (the destinations),
with both networks' memories; in each destination his first choice of a target is forced for `hold` frames (1 s), then he plays on
freely; the source plays on untouched (the free-play reference). What each brought over the next `win` frames (8 s) is read from the
rollout's own buffers and taught to the appraisals (sim/appraise.py). Tested as a measurement by tools/run/branch_test.py (test 4:
one moment's branches are too noisy to rank its options; many moments with a few branches each teach a forecast).

How it stays out of his learning: the copy is made at a rollout's boundary, so the rollout's kept starting memories already hold
it and the learning step replays it exactly; on the forced frames the simulator reports the destination's intention and keep choice
as "not read" (the forced seat's drawn target is not what was played), so they are not in the PPO terms; everything after the hold
is his own play and is learnt from as any other frame. Sources and destinations are self-play matches only: the league's counts
(games against a league network) are untouched.

Its own random stream (the trainer's BR_RNG); off (BRANCH_P 0): nothing is drawn, nothing is sent to a simulator, nothing kept.
What a copy cannot carry is switched off for the destination seats: the simulator's hindsight books of the fight odds (fo_okq)
and of "in control" (ctl_q_ok) for the frames before the copy.
"""
import json

import numpy as np

# ---------------------------------------------------------------------------------------------------------------- the plan


def plan(rng, n_self, eligible, share, k, free=None, prefer=None, prefer_p=0.0, chosen=None):
    """one simulator's plan: n_self self-play matches (0 .. n_self - 1), eligible [n_self] (a source may be taken from it), share of
    them to become destinations, k destinations a source -> [(source match, [k destination matches])]; sources are not destinations.
    free [n_self] (None: all): the matches that may be taken at all (a match of a long branch still being read is not).
    (the pattern's moments) prefer [n_self] and prefer_p > 0: each source is, with that chance, taken among the eligible matches
    that are at such a moment now (as far as there are any); those are added to the set `chosen`. prefer_p 0: the draws as before"""
    n_dst = int(float(share) * int(n_self))
    n_src = min(n_dst // max(1, int(k)), int(np.count_nonzero(eligible)))
    n_free = int(n_self) if free is None else int(np.count_nonzero(free))
    while n_src > 0 and n_src * (int(k) + 1) > n_free:
        n_src -= 1
    if n_src <= 0:
        return []
    if prefer is not None and float(prefer_p) > 0:
        pe = np.nonzero(np.asarray(eligible, bool) & np.asarray(prefer, bool))[0]
        n_p = min(int(rng.binomial(n_src, min(1.0, float(prefer_p)))), len(pe))
        sp = rng.choice(pe, size=n_p, replace=False) if n_p else np.zeros(0, np.int64)
        ot = np.setdiff1d(np.nonzero(eligible)[0], sp)
        so = rng.choice(ot, size=n_src - n_p, replace=False) if n_src - n_p else np.zeros(0, np.int64)
        src = np.concatenate([sp, so]).astype(np.int64)
        if chosen is not None:
            chosen.update(int(x) for x in sp)
    else:
        src = rng.choice(np.nonzero(eligible)[0], size=n_src, replace=False)
    rest = np.setdiff1d(np.arange(n_self) if free is None else np.nonzero(free)[0], src)
    dst = rng.choice(rest, size=n_src * int(k), replace=False).reshape(n_src, int(k))
    return [(int(s), [int(d) for d in ds]) for s, ds in zip(src, dst)]


def candidates(scores, ok, top, rand, rng, skip0=True):
    """his targets to branch on from one moment: the `top` best by his own scores and `rand` drawn from the rest, among the targets
    allowed here (ok; "none", target 0, never) -> a list of distinct targets (fewer if fewer are allowed). (2.1) skip0=False: the
    rows of an instruction's candidates (row 0 is a row as any other)"""
    ok = np.asarray(ok, bool).copy()
    if skip0:
        ok[0] = False
    idx = np.nonzero(ok)[0]
    if not len(idx):
        return []
    order = idx[np.argsort(-np.asarray(scores, np.float64)[idx], kind="stable")]
    best = [int(x) for x in order[:int(top)]]
    rest = order[int(top):]
    more = [int(x) for x in rng.choice(rest, size=min(int(rand), len(rest)), replace=False)] if len(rest) and rand > 0 else []
    return best + more


def weapon_only(rng, row_scores, ok_row, wok_row, cur, none_row, k):
    """(the pattern's moments) one moment's branches that differ only in the weapon: the row he is on (if it is an instruction the
    map still offers), else the row the head scores best among the offered instructions (never "none": it asks for no weapon), and
    up to k of the weapons he owns with ammunition, in a random order -> (row, [weapons]); (-1, []) when there is no such row or
    fewer than two weapons (nothing to compare)"""
    okr = np.asarray(ok_row, bool).copy()
    if none_row is not None and 0 <= int(none_row) < len(okr):
        okr[int(none_row)] = False
    ws = np.nonzero(np.asarray(wok_row, bool))[0]
    if not okr.any() or len(ws) < 2:
        return -1, []
    row = int(cur) if (0 <= int(cur) < len(okr) and okr[int(cur)]) else int(np.nonzero(okr)[0][np.argmax(np.asarray(row_scores, np.float64)[okr])])
    ws = rng.permutation(ws)[:int(k)]
    return row, [int(w) for w in ws]


def start(rng, pipes, w_off, n_self, G, share, top, rand, hold, scores, elig, ok, wbest=None, long_p=0.0, busy=None, quiet_p=None,
          wpn_p=0.0, pat=None, wok=None, cur=None, none_row=None, long_rows=None):
    """before a rollout: every simulator's plan, sent to it (("branch", {jobs, hold}); it answers when the copies are made).
    scores [N, targets] his own scores of each seat's targets now, elig [N] (a seat alive in a game with its enemy alive),
    ok [N, targets] the targets its map has -> None (nothing planned) or the plan's seats (the trainer's numbers):
      src [S] each source's even seat; dst [B] each destination's forced (even) seat, dst_src [B] its source's index in src,
      tg [B] its forced target; rows_src, rows_dst [2 x B..]: every seat of every destination and the source seat it is a copy of.
    (2.1) wbest [N, rows] given: the candidates are INSTRUCTIONS (scores and ok over the simulator's candidate rows; wbest: the weapon
    the head scores best for each row): forced through the simulator's force_instr; tg = the row, w [B] = its weapon, ins = True.
    (the pattern's moments; instructions only) wpn_p > 0 with pat [N] (the simulator's instr_pattern(): 1 after a chunk hit or a
    pain sound, 2 a fight's start with both stacks high), wok [N, weapons], cur [N] (the row he is on) and none_row: that share of
    the sources is taken at such moments, and their branches keep ONE row and differ only in the weapon (weapon_only); out["wpn"]
    [B] marks those branches, out["pat"] [S] each source's kind (0: an ordinary moment). wpn_p 0: every draw as before"""
    ins = wbest is not None
    wp_on = ins and float(wpn_p) > 0 and pat is not None and wok is not None and cur is not None
    wflag, pkind = [], []
    assert G == 2, "branch: duels"
    k = int(top) + int(rand)
    src, dst, dst_src, tg, rs, rd = [], [], [], [], [], []
    wsel, qsel = [], []
    sent = []
    for w, p in enumerate(pipes):
        o = int(w_off[w])
        ns = int(n_self[w])
        el = np.asarray(elig[o:o + G * ns], bool).reshape(ns, G).all(1)
        fr = None
        if busy is not None:                                 # (a long branch still being read: its match is left alone)
            fr = ~np.asarray(busy[o:o + G * ns], bool).reshape(ns, G).any(1)
            el = el & fr
        jobs = []
        pset = set()
        pl_ = (plan(rng, ns, el, share, k, free=fr, prefer=np.asarray(pat[o:o + G * ns]).reshape(ns, G)[:, 0] > 0, prefer_p=wpn_p, chosen=pset)
               if wp_on else plan(rng, ns, el, share, k, free=fr))
        for s, ds in pl_:
            seat = o + G * s
            wl_ = None
            if s in pset:                                    # a moment of the pattern: one row, each weapon
                row_, wl_ = weapon_only(rng, scores[seat], ok[seat], wok[seat], cur[seat], none_row, k)
                c = [row_] * len(wl_)
            if not wl_:
                wl_ = None
                c = candidates(scores[seat], ok[seat], top, rand, rng, skip0=not ins)
            if not c:
                continue
            ds = ds[:len(c)]
            if ins and quiet_p is not None:                  # (quiet movement forced in a share; never in a weapon's comparison)
                qs_ = [int(rng.random() < float(quiet_p)) for _ in ds] if wl_ is None else [0] * len(ds)
            else:
                qs_ = None
            wj_ = ([int(w_) for w_ in wl_[:len(ds)]] if wl_ is not None else [int(wbest[seat, r_]) for r_ in c[:len(ds)]]) if ins else None
            jobs.append((s, ds, c[:len(ds)]) + ((wj_,) if ins else ()) + ((qs_,) if qs_ is not None else ()))
            wflag += [wl_ is not None] * len(ds)
            pkind.append(int(pat[seat]) if (wp_on and wl_ is not None) else 0)
            if ins:
                wsel += wj_
            if qs_ is not None:
                qsel += qs_
            for d, t in zip(ds, c):
                dst.append(o + G * d)
                dst_src.append(len(src))
                tg.append(t)
                for j in range(G):
                    rs.append(seat + j)
                    rd.append(o + G * d + j)
            src.append(seat)
        if jobs:
            p.send(("branch", dict(jobs=jobs, hold=int(hold), ins=ins)))
            sent.append(p)
    for p in sent:
        p.recv()
    if not dst:
        return None
    out = dict(src=np.array(src, np.int64), dst=np.array(dst, np.int64), dst_src=np.array(dst_src, np.int64), tg=np.array(tg, np.int64),
               rows_src=np.array(rs, np.int64), rows_dst=np.array(rd, np.int64), hold=int(hold), ins=ins,
               **({"w": np.array(wsel, np.int64)} if ins else {}),
               **({"q": np.array(qsel, np.int64)} if (ins and quiet_p is not None) else {}),
               **({"wpn": np.array(wflag, bool), "pat": np.array(pkind, np.int64)} if wp_on else {}))
    lg = None
    if long_p > 0:                                           # (the long window) which branches are read over it, and their sources
        lg = rng.random(len(dst)) < float(long_p)
    if ins and long_rows is not None:                        # (2.1a; the owner, 2026-11-12: spam is denial, its payoff is slow) a branch whose
        sp_ = np.isin(out["tg"], np.asarray(long_rows, np.int64))   # forced row is a spam row is ALWAYS read over the long window, whatever
        out["spam_n"] = int(sp_.sum())                       # the share draws for the others. No draw is made for it: with no spam row
        if sp_.any():                                        # among the branches everything is as before
            out["long_spam"] = int((sp_ & ~lg).sum()) if lg is not None else int(sp_.sum())
            lg = sp_ if lg is None else (lg | sp_)
    if lg is not None:
        out["long"] = lg
        sl = np.zeros(len(src), bool)
        sl[out["dst_src"][out["long"]]] = True
        out["src_long"] = sl
    return out


# ------------------------------------------------------------------------------------------------------- in the simulator's worker


def worker_start(env, data):
    """in a simulator's process: the copies and the forced targets -> the countdown's state"""
    ins = bool(data.get("ins"))                              # (2.1) the first choice forced is an instruction (its row and weapon)
    if not ins and (getattr(env, "force_intent", None) is None or len(env.force_intent) != env.n):
        env.force_intent = np.full(env.n, -1, np.int64)
    if ins and (getattr(env, "force_instr", None) is None or len(env.force_instr) != env.n):
        env.force_instr = np.full((env.n, 2), -1, np.int64)
    dummy = np.zeros((env.n, 1), np.float32)                 # (the moment's inputs: the trainer copies its own rows)
    forced = []
    for job in data["jobs"]:
        s, ds, ts = job[0], job[1], job[2]
        ws = job[3] if ins else [None] * len(ds)
        qs = job[4] if (ins and len(job) > 4) else None
        if qs is not None and (getattr(env, "force_quiet", None) is None or len(env.force_quiet) != env.n):
            env.force_quiet = np.full(env.n, -1, np.int64)
        mo = env._moment_take(int(s), dummy)
        for j_, (d, t, w) in enumerate(zip(ds, ts, ws)):
            env._moment_set(int(d), mo, dummy)
            q = np.asarray(env._seats(int(d)), np.int64)
            if ins:
                env.force_instr[q] = -1
                env.force_instr[q[0]] = (int(t), int(w))
                if qs is not None:
                    env.force_quiet[q] = -1
                    env.force_quiet[q[0]] = int(qs[j_])
            else:
                env.force_intent[q] = -1
                env.force_intent[q[0]] = int(t)
            forced.append(int(q[0]))
            for nm in ("fo_okq", "ctl_q_ok"):                # (the hindsight books' queries of the frames before the copy: no label)
                b = getattr(env, nm, None)
                if isinstance(b, np.ndarray) and b.ndim == 2 and b.shape[1] == env.n:
                    b[:, q] = False
    return dict(left=int(data["hold"]), seats=np.array(forced, np.int64), ins=ins)


def worker_after(st, env, il, it, kl):
    """after a step of the simulator while a hold is on: the forced seats' intention and keep choice were not theirs (not read, no
    rule's label), in the copies of the flags that go to the trainer (il, it, kl: changed in place); the hold's last step lets them go
    -> the state, or None when it is over"""
    s = st["seats"]
    il[s] = False
    it[s] = -1
    if kl is not None:
        kl[s] = False
    st["left"] -= 1
    if st["left"] <= 0:
        if st.get("ins"):
            env.force_instr[:] = -1
            if getattr(env, "force_quiet", None) is not None:
                env.force_quiet[:] = -1
        else:
            env.force_intent[:] = -1
        return None
    return st


# ----------------------------------------------------------------------------------------------- the trainer's rows of a copy


def copy_seats(x, src, dst, N):
    """rows dst become rows src in everything that has a row a seat: an array or tensor whose first dimension is N (or, for a history
    [S, N, ..], its second), in place; a tuple or list of them; an object's attributes of that kind. Anything else is left alone"""
    if x is None:
        return
    if isinstance(x, (tuple, list)):
        for y in x:
            copy_seats(y, src, dst, N)
        return
    sh = getattr(x, "shape", None)
    if sh is not None and hasattr(x, "__setitem__"):
        a, b = _ix(x, src), _ix(x, dst)
        if len(sh) >= 1 and sh[0] == N:
            x[b] = x[a]
        elif len(sh) >= 2 and sh[1] == N:
            x[:, b] = x[:, a]
        return
    if hasattr(x, "__dict__") and not callable(x):
        for v in vars(x).values():
            if getattr(v, "shape", None) is not None or isinstance(v, (tuple, list)):
                copy_seats(v, src, dst, N)


# ----------------------------------------------------------------------------------------------------------------- the outcomes


def _ix(x, i):
    """seat numbers as an index of x (a tensor: on its device)"""
    if hasattr(x, "device") and hasattr(x, "cpu"):
        import torch
        return torch.as_tensor(np.asarray(i, np.int64), device=x.device)
    return np.asarray(i, np.int64)


def _np(x):
    return x.float().cpu().numpy().astype(np.float64) if hasattr(x, "cpu") else np.asarray(x, np.float64)


def outcomes(seats, aux, done, hr, vh, ix, gamma, hold, win, ws=None):
    """what the next `win` frames brought each seat of `seats`, from a rollout's buffers (a copy at the rollout's start: frame 0):
    aux [T + 1, N, C] (the damage of step f is in row f + 1), done [T, N], hr [T, N] his pay as the head's value counts it,
    vh [T + 1, N] the head's value (None: no dv), ws [T, N] the judge's shadow pay (None: none). Cut at a round's end (that step
    still counts; nothing after it, no bootstrap).
    -> dict of [B] arrays: dealt, taken (damage), he_dies, i_die, item (0 or 1), dv, judge, cut, frames, got (his target at the hold's end)"""
    seats = np.asarray(seats, np.int64)
    W = int(win)
    d = _np(done[:W][:, _ix(done, seats)]) > 0.5
    live = np.ones_like(d)
    live[1:] = ~(np.cumsum(d[:-1], 0) > 0)
    lv = live.astype(np.float64)

    def col(name):
        return _np(aux[1:W + 1][:, _ix(aux, seats)][..., ix[name]])
    out = dict(dealt=(col("dmg_dealt") * lv).sum(0), taken=(col("dmg_taken") * lv).sum(0),
               he_dies=((col("frag") * lv).max(0) > 0.5).astype(np.float64),
               i_die=((np.maximum(col("fragged"), col("died")) * lv).max(0) > 0.5).astype(np.float64),
               item=((((np.abs(col("mega_take") - 1.0) < 0.25) | (np.abs(col("red_take") - 1.0) < 0.25)) * lv).max(0) > 0.5).astype(np.float64),
               cut=d.any(0), frames=lv.sum(0))
    disc = float(gamma) ** np.arange(W)
    if vh is not None:
        g = (_np(hr[:W][:, _ix(hr, seats)]) * lv * disc[:, None]).sum(0)
        out["dv"] = g + np.where(out["cut"], 0.0, float(gamma) ** W * _np(vh[W][_ix(vh, seats)])) - _np(vh[0][_ix(vh, seats)])
    else:
        out["dv"] = np.full(len(seats), np.nan)
    out["judge"] = (_np(ws[:W][:, _ix(ws, seats)]) * lv).sum(0) if ws is not None else np.full(len(seats), np.nan)
    out["got"] = _np(aux[int(hold)][_ix(aux, seats ^ 1)][..., ix["en_target"]]).astype(np.int64)      # (his own target: the enemy's row holds it)
    return out


def rank_differs(dst_src, dv_a, dv_b):
    """(2.1, --ins-pay-win; a readout) one rollout's branches by their moment (dst_src [B]): how often the best option by dv_a (the
    win chance alone) is another than the best by dv_b (the whole pay), over the moments with two branches or more and both
    numbers finite -> dict(moments, differ, share)"""
    ds = np.asarray(dst_src, np.int64)
    a, b = np.asarray(dv_a, np.float64), np.asarray(dv_b, np.float64)
    n = d = 0
    for s in np.unique(ds):
        m = np.nonzero((ds == s) & np.isfinite(a) & np.isfinite(b))[0]
        if len(m) < 2:
            continue
        n += 1
        d += int(m[np.argmax(a[m])] != m[np.argmax(b[m])])
    return dict(moments=int(n), differ=int(d), share=(round(d / n, 4) if n else None))


def rows(meta, oc_dst, oc_src, n_targets):
    """the appraisals' examples of one rollout's branches: a destination whose forced target was really his at the hold's end (a
    target the map has not becomes nothing: dropped), and each source as he played it (his own target at the hold's end)
    -> (index into the kept situations [R], target [R], kind [R] (1 forced, 0 free), Y [R, 6], M [R, 6])"""
    keep_d = oc_dst["got"] == meta["tg"]
    keep_s = (oc_src["got"] >= 1) & (oc_src["got"] < int(n_targets))
    sit = np.concatenate([meta["dst_src"][keep_d], np.nonzero(keep_s)[0]])
    tg = np.concatenate([meta["tg"][keep_d], oc_src["got"][keep_s]])
    kind = np.concatenate([np.ones(int(keep_d.sum()), np.int64), np.zeros(int(keep_s.sum()), np.int64)])

    def y(oc, m):
        return np.stack([oc["dealt"][m] / 100.0, oc["taken"][m] / 100.0, oc["he_dies"][m], oc["i_die"][m], oc["item"][m],
                         np.nan_to_num(oc["dv"][m])], 1)
    Y = np.concatenate([y(oc_dst, keep_d), y(oc_src, keep_s)]).astype(np.float32)
    Y = np.concatenate([Y, np.zeros((len(Y), 1), np.float32)], 1)       # (dv over the long window: labelled when it has been played out)
    M = np.ones_like(Y)
    M[:, 5] = np.isfinite(np.concatenate([oc_dst["dv"][keep_d], oc_src["dv"][keep_s]]))
    M[:, 6] = 0.0
    return sit, tg, kind, Y, M


def rows_ins(meta, oc_dst, oc_src):
    """(2.1) the appraisals' examples of a rollout's INSTRUCTION branches: every destination with its forced row's numbers
    (meta["X"] [B, xf]) twice: once with its weapon (meta["w"]) and once with no weapon named ("this row with the weapon he would
    choose": what the scorer reads for every row); and each source that was under an instruction of the head's at the copy
    (meta["src_has"] [S], its row meta["src_X"] [S, xf], its weapon meta["src_w"] [S]) as he played it (free)
    -> (index into the kept situations [R], X [R, xf], weapon [R] (-1: none), kind [R] (1 forced, 0 free), Y [R, 7], M [R, 7]).
    With quiet movement forced in the plan (meta["q"] [B]; a source's own: meta["src_q"] [S]): rows_q(meta) gives each row's bit"""
    B = len(meta["dst"])
    hs = np.asarray(meta.get("src_has", np.zeros(len(meta["src"]), bool)), bool)
    si = np.nonzero(hs)[0]
    sit = np.concatenate([meta["dst_src"], meta["dst_src"], si])
    X = np.concatenate([meta["X"], meta["X"], np.asarray(meta["src_X"])[si]] if len(si) else [meta["X"], meta["X"]]).astype(np.float32)
    w = np.concatenate([meta["w"], np.full(B, -1, np.int64), np.asarray(meta["src_w"], np.int64)[si] if len(si) else np.zeros(0, np.int64)])
    kind = np.concatenate([np.ones(2 * B, np.int64), np.zeros(len(si), np.int64)])
    alld = np.ones(B, bool)

    def y(oc, m):
        return np.stack([oc["dealt"][m] / 100.0, oc["taken"][m] / 100.0, oc["he_dies"][m], oc["i_die"][m], oc["item"][m],
                         np.nan_to_num(oc["dv"][m])], 1)
    yd = y(oc_dst, alld)
    Y = np.concatenate([yd, yd, y(oc_src, hs)]).astype(np.float32)
    Y = np.concatenate([Y, np.zeros((len(Y), 1), np.float32)], 1)       # (dv over the long window: labelled when it has been played out)
    M = np.ones_like(Y)
    M[:, 5] = np.isfinite(np.concatenate([oc_dst["dv"], oc_dst["dv"], oc_src["dv"][hs]]))
    M[:, 6] = 0.0
    return sit, X, w, kind, Y, M


def rows_q(meta):
    """(quiet movement) the quiet bit of each of rows_ins()'s rows, in its order: a destination's forced bit (both of its rows), a
    source's own; None when the plan forced none"""
    if meta.get("q") is None:
        return None
    hs = np.asarray(meta.get("src_has", np.zeros(len(meta["src"]), bool)), bool)
    sq = np.asarray(meta.get("src_q", np.zeros(len(meta["src"]), np.int64)), np.int64)[hs]
    return np.concatenate([meta["q"], meta["q"], sq])


def log_rows(path, update, meta, oc_dst, oc_src, seat_map=None):
    """<run>/branches.jsonl: a line a branch (and a source), for reading the lesson's data beside the measurement's (branch_test.py)"""
    with open(path, "a", encoding="utf-8") as f:
        for kind, seats, oc, tg, srcs in (("forced", meta["dst"], oc_dst, meta["tg"], meta["src"][meta["dst_src"]]),
                                          ("free", meta["src"], oc_src, None, meta["src"])):
            for j, s in enumerate(seats):
                f.write(json.dumps(dict(update=int(update), kind=kind, seat=int(s), src=int(srcs[j]),
                                        map=(str(seat_map[int(s)]) if seat_map is not None else None),
                                        tg=(int(tg[j]) if tg is not None else None), got=int(oc["got"][j]),
                                        dealt=round(float(oc["dealt"][j]), 1), taken=round(float(oc["taken"][j]), 1),
                                        he_dies=int(oc["he_dies"][j]), i_die=int(oc["i_die"][j]), item=int(oc["item"][j]),
                                        dv=(None if not np.isfinite(oc["dv"][j]) else round(float(oc["dv"][j]), 4)),
                                        judge=(None if not np.isfinite(oc["judge"][j]) else round(float(oc["judge"][j]), 4)),
                                        cut=bool(oc["cut"][j]), frames=int(oc["frames"][j]))) + "\n")


def dump_rows(folder, update, L, S, C, Y, M, kind, src, names, row0):
    """(tools/run/branch_record.py, the trainer's --branch-dump) a rollout's branch rows as the appraisals read them, for
    tools/run/prune_inputs.py: S [R, sit] the situations (kept at half precision), C [R, cand] the candidates, Y, M [R, d] the labels
    and their masks, kind [R] (1 forced, 0 free), src [R] each row's moment (its source's number in this rollout), names: the row's
    numbers by name, row0: where they begin in C. One file a rollout: <folder>/br_<update>.npz"""
    import json
    import os
    os.makedirs(folder, exist_ok=True)
    meta = dict(layout={k: (v if not isinstance(v, np.generic) else v.item()) for k, v in dict(L).items()}, row0=int(row0), names=[str(n_) for n_ in names], update=int(update))
    np.savez_compressed(os.path.join(folder, "br_{:06d}.npz".format(int(update))), S=np.asarray(S, np.float32).astype(np.float16), C=np.asarray(C, np.float32),
                        Y=np.asarray(Y, np.float32), M=np.asarray(M, np.float32), kind=np.asarray(kind, np.int8),
                        grp=int(update) * 1000000 + np.asarray(src, np.int64), meta=np.array(json.dumps(meta)))


def record(meta, oc_dst, oc_src, n_rows, secs, share):
    """-> metrics.jsonl's "branch": the moments and branches of this rollout, how many forced targets held, the spread of what the
    forced branches brought beside the free ones"""
    if meta is None:
        return dict(p=round(float(share), 4), moments=0, branches=0)
    held = (oc_dst["got"] == meta["tg"]) if not meta.get("ins") else np.ones(len(meta["dst"]), bool)   # (an instruction: forced by the simulator)
    net_d, net_s = oc_dst["dealt"] - oc_dst["taken"], oc_src["dealt"] - oc_src["taken"]
    wp_ = {}
    if meta.get("wpn") is not None:                          # (the pattern's moments) the weapon-only branches: how many, of which kind,
        wf_ = np.asarray(meta["wpn"], bool)                  # and what each weapon brought there (dealt less taken; dv)
        pk_ = np.asarray(meta["pat"], np.int64)
        by_ = {}
        for w_ in np.unique(meta["w"][wf_]):
            m_ = wf_ & (meta["w"] == w_)
            by_[str(int(w_))] = dict(n=int(m_.sum()), net=round(float(net_d[m_].mean()), 2),
                                     dv=(round(float(np.nanmean(oc_dst["dv"][m_])), 4) if np.isfinite(oc_dst["dv"][m_]).any() else None))
        wp_ = dict(wpn=dict(branches=int(wf_.sum()), after_hit=int((pk_ == 1).sum()), fight_start=int((pk_ == 2).sum()), by_weapon=by_))
    return dict(p=round(float(share), 4), moments=int(len(meta["src"])), branches=int(len(meta["dst"])), held=int(held.sum()),
                rows=int(n_rows), cut=round(float(np.mean(oc_dst["cut"])), 4), **wp_,
                **({"spam": int(meta["spam_n"]), "long_spam": int(meta.get("long_spam", 0)),             # (2.1a) the branches on a spam row; of them
                    "long": int(np.sum(meta["long"])) if meta.get("long") is not None else 0}             # long by the rule alone; all the long ones
                   if meta.get("spam_n") is not None else {}),
                **({"best_by_win_vs_full": meta["rank"]} if meta.get("rank") is not None else {}),
                net_forced=round(float(net_d[held].mean()), 2) if held.any() else None, net_free=round(float(net_s.mean()), 2),
                dv_forced=(round(float(np.nanmean(oc_dst["dv"][held])), 4) if held.any() and np.isfinite(oc_dst["dv"][held]).any() else None),
                dv_free=(round(float(np.nanmean(oc_src["dv"])), 4) if np.isfinite(oc_src["dv"]).any() else None),
                secs=round(float(secs), 3))


# --------------------------------------------------------------------------------- 2.1: the instruction, in the simulator's worker


def worker_instr(env, data):
    """(the trainer's "instr" message, before a step) the head's picks of this reading given to the simulator (c [n] the candidate
    row, -1: none; w [n] the weapon; who [n] the seats whose instruction changes) -> whether the candidates of the next reading
    are wanted after this step"""
    if data.get("who") is not None and hasattr(env, "instr_pick"):
        if data.get("q") is not None and hasattr(env, "force_quiet"):      # (a simulator with the instruction's sixth field: quiet movement)
            env.instr_pick(np.asarray(data["c"], np.int64), np.asarray(data["w"], np.int64), np.asarray(data["who"], bool), np.asarray(data["q"], np.int64))
        else:
            env.instr_pick(np.asarray(data["c"], np.int64), np.asarray(data["w"], np.int64), np.asarray(data["who"], bool))
    return bool(data.get("want"))


def worker_feat(env):
    """after a tick's step: every seat's candidate rows for the next reading (X, ok, wok), the change signals (doing, done, failed,
    age, the belief's shift, the item), who is in a drill, the row he is on (-1: none), and who is forced (a drill's or a frozen
    moment's force_instr: his instruction is not the head's)"""
    X, ok, wok = env.instr_feat()
    sig = env.instr_state() if hasattr(env, "instr_state") else np.zeros((env.n, 8), np.float32)
    dr = getattr(env, "ins_drill", None)
    cur = getattr(env, "ins_cur", None)
    fi = getattr(env, "force_instr", None)
    C = np.asarray(ok).shape[1]
    cs = getattr(env, "ins_cspawn", None)                    # (fields 7 to 11, for the brain's questions and the map sense at a row's place:
    cp, cpk = getattr(env, "ins_cp", None), getattr(env, "ins_cpk", None)   # each row's spawn point (-1: none); its place and whether it
    sp = getattr(env, "spawns", None)                        # has one; the weapon in his hand; the map's spawn points' count)
    return (np.asarray(X).astype(np.float16), np.asarray(ok, bool), np.asarray(wok, bool), np.asarray(sig, np.float32),
            np.asarray(dr, bool).copy() if dr is not None else np.zeros(env.n, bool),
            np.asarray(cur, np.int64).copy() if cur is not None else np.full(env.n, -1, np.int64),
            (np.asarray(fi)[:, 0] >= 0) if fi is not None else np.zeros(env.n, bool),
            np.asarray(cs, np.int16)[:env.n].copy() if cs is not None else np.full((env.n, C), -1, np.int16),
            np.asarray(cp, np.float32)[:env.n].copy() if cp is not None else np.zeros((env.n, C, 3), np.float32),
            np.asarray(cpk, bool)[:env.n].copy() if cpk is not None else np.zeros((env.n, C), bool),
            np.asarray(env.weapon, np.int16)[:env.n].copy(),
            np.full(env.n, len(sp) if sp is not None else 0, np.int16),
            (np.asarray(env.instr_pattern(), np.int8) if hasattr(env, "instr_pattern") else np.zeros(env.n, np.int8)),   # (field 12: the pattern's moments)
            copy_rows(env, ok))                              # (field 13, 1.9a: the rows of the target his own network chose: the copy lesson)


def copy_rows(env, ok):
    """(1.9a, the copy lesson) [n, C] the offered rows whose target is the one his own network chose at its last reading (the
    simulator's ins_own_tg, kept before an instruction is put in its place); none where it chose "nothing" or no row has it"""
    ot = getattr(env, "ins_own_tg", None)
    tg = getattr(env, "ins_ctg", None)
    ok = np.asarray(ok, bool)
    if ot is None or tg is None:
        return np.zeros(ok.shape, bool)
    ot = np.asarray(ot, np.int64)[:env.n]
    return ok & (np.asarray(tg, np.int64)[:env.n] == ot[:, None]) & (ot > 0)[:, None]


def worker_spawns(env, smax):
    """(the trainer's "spawns" message, once) the map's spawn points [smax, 3] (zeros past its count) and their count"""
    sp = getattr(env, "spawns", None)
    out = np.zeros((int(smax), 3), np.float32)
    k = 0
    if sp is not None:
        p = np.asarray(sp, np.float32).reshape(len(sp), -1)[:, :3]
        k = min(len(p), int(smax))
        out[:k] = p[:k]
    return out, k


def worker_mask(env, il, it, kl):
    """after a step, in the copies of the flags that go to the trainer (changed in place): a seat under an instruction did not
    play the target its network drew (the instruction's target was read in its place): not read, no rule's label; a seat in a
    drill or forced by a frozen moment did not decide to keep or re-decide either"""
    v = getattr(env, "ins_v", None)
    if v is None:
        return
    u = np.asarray(v)[:env.n] > 0
    if u.any():
        il[u] = False
        it[u] = -1
    dr, fi = getattr(env, "ins_drill", None), getattr(env, "force_instr", None)
    if kl is not None and (dr is not None or fi is not None):
        f = (np.asarray(dr, bool) if dr is not None else np.zeros(env.n, bool)) | ((np.asarray(fi)[:, 0] >= 0) if fi is not None else False)
        if f.any():
            kl[f] = False


# ------------------------------------------------------------------------------- the long window (the score and the clock)
# A share of a rollout's branches (and their sources) is read over a long window (30 s: three rollouts and more): his pay as the
# head's value counts it, discounted, from the copy on; cut at a round's end (that step counts, nothing after, no bootstrap); at the
# window's end the head's value there as the bootstrap, less its value at the copy. The seats are left alone by later plans (busy).


def long_new(seats, S, C, vh):
    """a rollout's long branches, as they begin: seats [R] (a row an example: a destination's forced seat or a source's seat; a
    seat may stand in several rows), S [R, sit] and C [R, cand] the appraisals' rows of them, vh [T + 1, N] the head's value
    (its value at the copy: frame 0)"""
    seats = np.asarray(seats, np.int64)
    return dict(seats=seats, S=S, C=C, v0=_np(vh[0][_ix(vh, seats)]), g=np.zeros(len(seats)), alive=np.ones(len(seats), bool), k=0)


def long_step(recs, hr, done, vh, gamma, win, T):
    """one rollout's frames added to every record in recs (in place): hr [T, N] his pay, done [T, N], vh [T + 1, N]
    -> (the records still being read, the finished ones: each with dv [R] and has [R] (a label: always, cut or not))"""
    going, fin = [], []
    for r in recs:
        n = min(int(T), int(win) - int(r["k"]))
        s = r["seats"]
        d = _np(done[:n][:, _ix(done, s)]) > 0.5
        live = np.ones_like(d)
        live[1:] = ~(np.cumsum(d[:-1], 0) > 0)
        live &= r["alive"][None, :]
        disc = float(gamma) ** (int(r["k"]) + np.arange(n))
        r["g"] = r["g"] + (_np(hr[:n][:, _ix(hr, s)]) * live * disc[:, None]).sum(0)
        r["alive"] = r["alive"] & ~d.any(0)
        r["k"] = int(r["k"]) + n
        if r["k"] >= int(win):
            r["dv"] = r["g"] + np.where(r["alive"], float(gamma) ** int(win) * _np(vh[n][_ix(vh, s)]), 0.0) - r["v0"]
            fin.append(r)
        else:
            going.append(r)
    return going, fin


def long_busy(recs, metas, N):
    """the seats (and their enemies) of the long branches still being read, and of the plans whose long branches have not begun
    to be read -> [N] bool"""
    busy = np.zeros(int(N), bool)
    for r in recs:
        busy[r["seats"]] = True
        busy[r["seats"] ^ 1] = True
    for m in metas:
        if m is not None and m.get("long") is not None:
            s = np.concatenate([m["dst"][m["long"]], m["src"][m["src_long"]]])
            busy[s] = True
            busy[s ^ 1] = True
    return busy
