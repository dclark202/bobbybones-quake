"""The drift check: how far has a newer network's behaviour moved from a reference network's on the SAME situations, and
where (which outputs; the enemy in view or not)?

    python tools/drift_check.py --ref <ref.pt> --other <a.pt> [--other <b.pt> ...] --record <dir> --map bloodrun,aerowalk \
        --games 1 --minutes 10 --procs 2 --round 600 --opp-round 600 --opp-react-ms 100 --opp-acquire-ms 160 --set OVERTIME=1 \
        --set ... --json data/drift/<name>.json            (Anaconda Python; a .txt table is written beside the json)

1 record (once; kept in --record, one file a map, reused while the reference, the maps, the games, the minutes, the seed and
  the settings are the same; --rerecord makes them again): the checks' games (tools/duel_eval.py's play(): whole games
  with --round 600, the seats' delays and clocks, overtime with --set OVERTIME=1) with the reference on both seats
  (--rec-opp <pt>: the reference against that network, only the reference's seats kept). For every frame and every seat
  of the reference: exactly what its act() was given (the inputs, the legs' branch inputs xl when the network takes
  them, the head's events), the choice it drew, the frames its memory was cleared, and the flags at that moment: alive,
  the enemy alive, the enemy in his sight (env.visible: the fact, not what he noticed).
2 replay: every network (the reference first) is stepped through those exact input sequences, its memory from zero at
  each sequence's start and cleared where the game cleared the reference's; at every frame the logits of each output
  (test_suite.Policy's own maths up to the draw: attention, the legs' door and gate, the switch's fade; the readout
  track.* and the aux layers are not part of it). Per output: KL(ref || other) of the two categorical distributions and
  whether the most likely choice is the same. The reference's replay also redraws its choices with the play's own
  random stream: they must be the recorded choices (the identity check: the replay sees what the play saw).
  Results per (network file, map) are cached in --record (keyed by the file's size and time): a later save costs one
  replay.
Splits (frames he is alive): in view (the enemy alive and in his sight), out of view (everything else alive; also cut
  into "lost < 3 s" = he saw the enemy alive within the last 3 s, and "unseen 3 s+"); frames he is dead are left out.
  Every output is counted on every frame, also on frames the simulator does not read it (the movement keys one frame in
  four, the intention every INTENT_EVERY): a measure of the network, not of the game. Output 11 (the legs' switch) is
  forced off under NO_SWITCH: its row is shown but means nothing there.
"""
import argparse
import hashlib
import json
import multiprocessing as mp_
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import duel_eval as DE  # noqa: E402
import pin  # noqa: E402

HEAD_NAMES = ("forward", "sideways", "jump/crouch", "turn", "pitch", "fire", "weapon", "walk", "zoom", "lift mouse",
              "intention", "legs switch", "way", "turn add")
LOST_S = 3.0
SPLITS = ("all", "in_view", "out_of_view", "lost_lt3s", "unseen_3s")
CACHE_V = 1


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def head_names(n):
    return [HEAD_NAMES[j] if j < len(HEAD_NAMES) else "out{}".format(j) for j in range(n)]


# ---------------------------------------------------------------- the network's logits (test_suite.Policy.act up to the draw)
def step_logits(pol, obs, h, xl=None, pose=None, zmap=None):
    """one frame of a test_suite.Policy: -> (logits [B, sum(dims)] float32, the new memory). The same maths as act() without
    the draw (the head of v0.4 and ordered outputs are refused: their logits depend on draws)."""
    assert pol.head is None and not pol.order, "drift_check: networks with the v0.4 head or ordered outputs are not handled"
    dadd = gadd = h2_ = lgl_ = ok_ = None
    hb = None
    if getattr(pol, "brain_at", None) is not None:          # (v0.4.1) the brain's packed state at the end of the array
        hb, h = h[:, pol.brain_at:], h[:, :pol.brain_at]
    if pol.needs_xl:
        import legs_unify as LU_
        assert xl is not None, "this network takes the legs' branch inputs: the recording has none"
        ok_ = LU_.np_way(xl)
        h2_, lgl_ = LU_.np_branch(pol.legsP, xl)
        dadd = LU_.np_door(pol.uniD[0], pol.uniD[1], h2_, ok_) if pol.uniD is not None else None
        gadd = LU_.np_guide_add(pol.uni, pol.uniG, lgl_, ok_, sum(pol.dims)) if pol.uniG is not None else None
    hf = h
    if pol.slow is not None:
        h = hf[:, :pol.H]
    if obs.shape[1] > len(pol.mean):
        obs = obs[:, :len(pol.mean)]
    x = np.clip((obs - pol.mean) / np.sqrt(pol.var + 1e-8), -10, 10).astype(np.float32)
    xa = x
    bt, bst = pol.token_pre(obs, pose, zmap, hb) if hb is not None else (None, None)   # (v0.4.1) the brain's token, if its gate is open
    xh = xa
    if getattr(pol, "rfg", 0.0) > 0 and len(pol.rf_cols):    # (v0.4.2a) the hands' inputs: the rule-made columns faded (test_suite's act)
        import rule_fade as rfade_
        xh = x = rfade_.apply_np(x, pol.rf_cols, pol.rfg)
    if pol.cell is not None:
        ids = np.clip(obs[:, -2:].astype(np.int64), 0, len(pol.cell) - 1)
        x = np.concatenate([x[:, :-2], pol.cell[ids[:, 0]], pol.cell[ids[:, 1]]], 1)
    x = np.tanh(x @ pol.w0.T + pol.b0)
    x = np.tanh(x @ pol.w1.T + pol.b1)
    if pol.attP is not None:
        bta = bt if pol.bgate > 0 else None
        x = x + pol.attn_fwd(pol.attn, pol.attP, xh, hm=h, bt=bta, bg=pol.bgate if bta is not None else 0.0)
    if bt is not None:
        hb = pol.token_post(xa, pose, zmap, bst)
    xf = x
    if dadd is not None:
        xf = xf + dadd
    gi = xf @ pol.wih.T + pol.bih
    gh = h @ pol.whh.T + pol.bhh
    H = pol.H
    r = sig(gi[:, :H] + gh[:, :H])
    z = sig(gi[:, H:2 * H] + gh[:, H:2 * H])
    nn_ = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
    h = ((1 - z) * nn_ + z * h).astype(np.float32)
    zo = h
    if pol.slow is not None:
        zo, h = pol.slow_step(pol.slowP, pol.slow, x, h, hf)
    logits = zo @ pol.wp.T + pol.bp
    if gadd is not None:
        logits = logits + gadd
    if pol.uniT is not None:
        import legs_unify as LU_
        logits = logits + LU_.np_gate_add(pol.uni, *pol.uniT, zo, h2_, lgl_, ok_, sum(pol.dims))
    if pol.fade:
        o_ = np.concatenate([[0], np.cumsum(pol.dims)]).astype(int)
        logits = logits.copy()
        logits[:, int(o_[11]) + 1] -= pol.fade
    if hb is not None:
        h = np.concatenate([h, hb.astype(np.float32)], 1)
    return np.asarray(logits, np.float32), h


def draw(pol, logits):
    """act()'s draw from these logits with pol.rng (the same stream: one number a player and output, in order)"""
    o_ = np.concatenate([[0], np.cumsum(pol.dims)]).astype(int)
    u_ = [pol.rng.random((len(logits), 1)) for _ in pol.dims]
    out = np.zeros((len(logits), len(pol.dims)), np.int64)
    for j in range(len(pol.dims)):
        l = logits[:, o_[j]:o_[j + 1]]
        p = np.exp(l - l.max(1, keepdims=True))
        p /= p.sum(1, keepdims=True)
        out[:, j] = (p.cumsum(1) > u_[j]).argmax(1)
    if pol.no_switch and out.shape[1] > 11:
        out[:, 11] = 0
    return out


def log_softmax(l):
    m = l.max(-1, keepdims=True)
    return l - m - np.log(np.exp(l - m).sum(-1, keepdims=True))


# ---------------------------------------------------------------- 1: recording
def work_record(job):
    """a pool worker: duel_eval.play() with the reference's act() and the simulator's step watched; -> the file written"""
    out_path = job[-1]
    job = job[:-1]
    envmod, envvars = job[0], job[1]
    os.environ.update(envvars)
    import importlib
    import test_suite as T
    E = importlib.import_module(envmod)
    pol, opp_pol, two_ref = job[6], job[9], job[14]
    job = job[:14]
    swap = bool(job[12]) and opp_pol is not None
    keep = [pol] + ([opp_pol] if two_ref else [])
    rec = {id(p): dict(obs=[], xl=[], ev=[], act=[], vis=[], alive=[], en_alive=[], resets=[], pose=[], zmap=[]) for p in keep}
    st = {"env": None, "t": -1}
    act0, clear0, step0 = T.Policy.act, T.Policy.clear, E.DuelEnv.step

    def rows_of(p):
        n = st["env"].n
        sw = int(swap)
        return np.arange(sw, n, 2) if p is pol else np.arange(1 - sw, n, 2)

    def act(self, obs, h, events=None, xl=None, **kw):
        out, h2 = act0(self, obs, h, events, xl, **kw)
        R = rec.get(id(self))
        if R is not None:
            env = st["env"]
            rw = rows_of(self)
            al = np.asarray(env.hp, np.float64) > 0
            R["obs"].append(np.asarray(obs, np.float32).copy())
            R["xl"].append(None if xl is None else np.asarray(xl, np.float32).copy())
            R["ev"].append(None if events is None else np.asarray(events, np.float32).copy())
            R["act"].append(out.astype(np.int16))
            R["vis"].append(np.asarray(env.visible, bool)[:env.n][rw].copy())
            R["alive"].append(al[rw])
            R["en_alive"].append(al[rw ^ 1])
            import btoken as btoken_                         # (v0.4.1) his pose, for a network whose brain token is open
            pz_, zz_ = btoken_.pose_from_env(env, job[2])
            R["pose"].append(pz_[rw])
            R["zmap"].append(zz_[rw])
        return out, h2

    def clear(self, h, rows=None):
        R = rec.get(id(self))
        if R is not None:
            R["resets"].append((len(R["obs"]) - 1, -1 if rows is None else rows))
        return clear0(self, h, rows)

    def step(self, a):
        st["env"] = self
        return step0(self, a)
    T.Policy.act, T.Policy.clear, E.DuelEnv.step = act, clear, step
    try:
        res = DE.play(job)
    finally:
        T.Policy.act, T.Policy.clear, E.DuelEnv.step = act0, clear0, step0
    seed = int(job[5])
    D = dict(score=np.array(res["score"]), games=int(res["games"]), n_seq=len(keep))
    for k, p in enumerate(keep):
        R = rec[id(p)]
        D["obs{}".format(k)] = np.stack(R["obs"])
        if all(x is not None for x in R["xl"]):
            D["xl{}".format(k)] = np.stack(R["xl"])
        assert all(x is None for x in R["ev"]), "head events: not handled"
        D["act{}".format(k)] = np.stack(R["act"])
        for nm in ("vis", "alive", "en_alive", "pose", "zmap"):
            D[nm + str(k)] = np.stack(R[nm])
        rs = []                                              # (t, row): memory cleared after frame t; row -1: every row
        for t_, rows in R["resets"]:
            rows = np.arange(D["obs{}".format(k)].shape[1]) if (isinstance(rows, int) and rows == -1) else np.atleast_1d(np.asarray(rows))
            rs += [(t_, int(r_)) for r_ in rows]
        D["resets{}".format(k)] = np.array(rs, np.int64).reshape(-1, 2)
        D["seed{}".format(k)] = np.array(seed if p is pol else seed + 1)
    tmp = out_path + ".tmp.npz"
    np.savez_compressed(tmp, **D)
    os.replace(tmp, out_path)
    return out_path


# ---------------------------------------------------------------- 2: replay and compare
def file_key(path):
    s = os.stat(path)
    return "{}|{}|{}".format(os.path.abspath(path), s.st_size, int(s.st_mtime))


def work_replay(job):
    """a pool worker: one map's recording; the reference's logits, then each other network's KL and agreement.
    -> {other path: {split: dict(n, kl[j], agree[j], kl_q[j] ...)}}, identity"""
    rec_path, ref_path, others = job
    import test_suite as T
    Z = np.load(rec_path)
    ref = T.Policy(ref_path, seed=0)
    pols = {p: T.Policy(p, seed=0) for p in others}
    dims = ref.dims
    o_ = np.concatenate([[0], np.cumsum(dims)]).astype(int)
    J = len(dims)
    out = {p: {s: dict(n=0, kl=np.zeros(J), agree=np.zeros(J), kl_all=[[] for _ in range(J)]) for s in SPLITS} for p in others}
    ident = dict(frames=0, same=0, same_head=np.zeros(J))
    for k in range(int(Z["n_seq"])):
        obs, act = Z["obs{}".format(k)], Z["act{}".format(k)]
        xl = Z["xl{}".format(k)] if "xl{}".format(k) in Z.files else None
        vis, alive, en_alive = Z["vis{}".format(k)], Z["alive{}".format(k)], Z["en_alive{}".format(k)]
        resets = Z["resets{}".format(k)]
        pose = Z["pose{}".format(k)] if "pose{}".format(k) in Z.files else None      # (v0.4.1: older recordings have none)
        zmap = Z["zmap{}".format(k)] if "zmap{}".format(k) in Z.files else None
        Tn, B = obs.shape[:2]
        # the splits per frame and row
        seen = vis & alive & en_alive
        since = np.full(B, 1e9)
        lost = np.zeros((Tn, B), bool)
        dt = 0.025
        for t in range(Tn):
            since = np.where(seen[t], 0.0, since + dt)
            lost[t] = ~seen[t] & (since <= LOST_S)
        masks = dict(all=alive, in_view=seen, out_of_view=alive & ~seen, lost_lt3s=alive & ~seen & lost, unseen_3s=alive & ~seen & ~lost)
        rmap = {}
        for t_, r_ in resets:
            rmap.setdefault(int(t_), []).append(int(r_))
        # the reference: logits and the identity check
        ref.rng = np.random.default_rng(int(Z["seed{}".format(k)]))
        h = ref.zeros(B)
        LR = np.zeros((Tn, B, o_[-1]), np.float32)
        for t in range(Tn):
            lg, h = step_logits(ref, obs[t], h, None if xl is None else xl[t], None if pose is None else pose[t], None if zmap is None else zmap[t])
            LR[t] = lg
            a_ = draw(ref, lg)
            eq = a_ == act[t]
            ident["frames"] += B
            ident["same"] += int(eq.all(1).sum())
            ident["same_head"] += eq.sum(0)
            if t in rmap:
                ref.clear(h, np.array(rmap[t]))
        lpR = [log_softmax(LR[:, :, o_[j]:o_[j + 1]]) for j in range(J)]
        topR = [LR[:, :, o_[j]:o_[j + 1]].argmax(-1) for j in range(J)]
        for p, pol in pols.items():
            assert pol.dims == dims, "{}: outputs {} against the reference's {}".format(p, pol.dims, dims)
            h = pol.zeros(B)
            LO = np.zeros_like(LR)
            for t in range(Tn):
                lg, h = step_logits(pol, obs[t], h, None if xl is None else xl[t], None if pose is None else pose[t], None if zmap is None else zmap[t])
                LO[t] = lg
                if t in rmap:
                    pol.clear(h, np.array(rmap[t]))
            for j in range(J):
                lo = log_softmax(LO[:, :, o_[j]:o_[j + 1]])
                kl = (np.exp(lpR[j]) * (lpR[j] - lo)).sum(-1)               # [T, B]
                ag = LO[:, :, o_[j]:o_[j + 1]].argmax(-1) == topR[j]
                for s, m in masks.items():
                    out[p][s]["kl"][j] += float(kl[m].sum())
                    out[p][s]["agree"][j] += float(ag[m].sum())
                    out[p][s]["kl_all"][j].append(kl[m].astype(np.float32))
            for s, m in masks.items():
                out[p][s]["n"] += int(m.sum())
            del LO
        del LR, lpR, topR
    # quantiles kept as sums are not mergeable: keep a histogram of log10 KL instead
    edges = np.linspace(-8, 2, 101)
    for p in others:
        for s in SPLITS:
            d = out[p][s]
            d["hist"] = [np.histogram(np.log10(np.maximum(np.concatenate(x) if x else np.zeros(0), 1e-12)), bins=edges)[0].tolist() for x in d["kl_all"]]
            d.pop("kl_all")
            d["kl"], d["agree"] = d["kl"].tolist(), d["agree"].tolist()
    ident["same_head"] = ident["same_head"].tolist()
    return dict(res=out, ident=ident)


def merge(parts):
    """sums over maps"""
    tot = None
    for P in parts:
        if tot is None:
            tot = json.loads(json.dumps(P))
            continue
        for s in SPLITS:
            a, b = tot[s], P[s]
            a["n"] += b["n"]
            a["kl"] = [x + y for x, y in zip(a["kl"], b["kl"])]
            a["agree"] = [x + y for x, y in zip(a["agree"], b["agree"])]
            a["hist"] = [[x + y for x, y in zip(u, v)] for u, v in zip(a["hist"], b["hist"])]
    return tot


def summarise(S, names):
    """sums -> means and the median and 90th percentile of KL (from the histogram of log10 KL)"""
    edges = np.linspace(-8, 2, 101)
    out = {}
    for s in SPLITS:
        d = S[s]
        n = max(1, d["n"])
        rows = []
        for j, nm in enumerate(names):
            hc = np.cumsum(d["hist"][j])
            q = lambda f: float(10 ** edges[min(len(edges) - 1, int(np.searchsorted(hc, f * hc[-1])) + 1)]) if hc[-1] else None   # noqa: E731
            rows.append(dict(head=j, name=nm, kl_mean=d["kl"][j] / n, agree=d["agree"][j] / n, kl_median=q(0.5), kl_p90=q(0.9)))
        real = [r for r in rows if r["name"] != "legs switch"]
        out[s] = dict(frames=d["n"], kl_sum_mean=float(sum(r["kl_mean"] for r in real)), agree_mean=float(np.mean([r["agree"] for r in real])),
                      heads=rows)
    return out


def table(label, summ):
    L = ["== {} ==".format(label)]
    a = summ["all"]
    L.append("  frames alive {} (in view {}, out of view {}: lost < 3 s {}, unseen 3 s+ {})".format(
        a["frames"], summ["in_view"]["frames"], summ["out_of_view"]["frames"], summ["lost_lt3s"]["frames"], summ["unseen_3s"]["frames"]))
    L.append("  KL summed over outputs (switch left out) / mean top-choice agreement: " + " | ".join(
        "{} {:.4f} / {:.1%}".format(s, summ[s]["kl_sum_mean"], summ[s]["agree_mean"]) for s in SPLITS))
    L.append("    {:3s} {:12s} ".format("#", "output") + " ".join("{:>17s}".format(s) for s in SPLITS) + "   (mean KL / agreement)")
    for j in range(len(a["heads"])):
        L.append("    {:3d} {:12s} ".format(j, a["heads"][j]["name"]) + " ".join(
            "{:>9.4f} {:>6.1%}".format(summ[s]["heads"][j]["kl_mean"], summ[s]["heads"][j]["agree"]) for s in SPLITS))
    top = sorted([r for r in a["heads"] if r["name"] != "legs switch"], key=lambda r: -r["kl_mean"])[:4]
    L.append("  moved most: " + ", ".join("{} {:.4f} (in view {:.4f}, out {:.4f})".format(
        r["name"], r["kl_mean"], summ["in_view"]["heads"][r["head"]]["kl_mean"], summ["out_of_view"]["heads"][r["head"]]["kl_mean"]) for r in top))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--other", action="append", default=[])
    ap.add_argument("--label", action="append", default=[], help="a name for each --other, in order (default: the file's)")
    ap.add_argument("--record", required=True, help="the folder of the recorded situations and the cached replays")
    ap.add_argument("--rerecord", action="store_true")
    ap.add_argument("--rec-opp", default="", help="the reference's opponent while recording (default: the reference itself; both seats kept)")
    ap.add_argument("--inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--opp-inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--map", default="bloodrun,aerowalk,lostworld,sinister")
    ap.add_argument("--games", type=int, default=1, help="games a map (one simulator process a map)")
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--round", type=float, default=600.0)
    ap.add_argument("--opp-round", type=float, default=600.0)
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--seed", type=int, default=300)
    ap.add_argument("--react-ms", type=float, default=None)
    ap.add_argument("--acquire-ms", type=float, default=None)
    ap.add_argument("--opp-react-ms", type=float, default=None)
    ap.add_argument("--opp-acquire-ms", type=float, default=None)
    ap.add_argument("--no-self", action="store_true", help="leave out the reference against itself (the sanity row)")
    ap.add_argument("--json", required=True)
    a = ap.parse_args()
    import test_suite as T
    os.makedirs(a.record, exist_ok=True)
    maps = a.map.split(",")
    envvars = dict(x.split("=", 1) for x in a.set)
    two_ref = not a.rec_opp
    opp_path = a.rec_opp or a.ref
    meta = dict(v=CACHE_V, ref=file_key(a.ref), opp=file_key(opp_path), two_ref=two_ref, games=a.games, minutes=a.minutes, seed=a.seed,
                env=a.env, set=envvars, round=a.round, opp_round=a.opp_round, delays=[a.react_ms, a.acquire_ms, a.opp_react_ms, a.opp_acquire_ms])
    tag = hashlib.sha1(json.dumps(meta, sort_keys=True).encode()).hexdigest()[:10]
    with open(os.path.join(a.record, "meta_{}.json".format(tag)), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    rec_files = {mp: os.path.join(a.record, "rec_{}_{}.npz".format(tag, mp)) for mp in maps}
    todo = [mp for mp in maps if a.rerecord or not os.path.exists(rec_files[mp])]
    if todo:
        pol = T.Policy(a.ref, seed=1)
        now = DE.names(os.path.join(ROOT, "docs", "INPUTS.csv"))
        idx = np.array([now.index(x) for x in DE.names(a.inputs)])
        assert len(idx) == len(pol.mean)
        opp_pol = T.Policy(opp_path, seed=2)
        opp_idx = np.array([now.index(x) for x in DE.names(a.opp_inputs)])
        assert len(opp_idx) == len(opp_pol.mean)
        delays = (pol.react_ms if a.react_ms is None else a.react_ms, pol.acquire_ms if a.acquire_ms is None else a.acquire_ms,
                  opp_pol.react_ms if a.opp_react_ms is None else a.opp_react_ms, opp_pol.acquire_ms if a.opp_acquire_ms is None else a.opp_acquire_ms)
        rounds = (DE.round_of(a.round, pol), DE.round_of(a.opp_round, opp_pol), False)
        jobs = [(a.env, envvars, mp, a.games, a.minutes, a.seed + 17 * k, pol, idx, "policy", opp_pol, opp_idx, rounds, False, delays, two_ref, rec_files[mp])
                for k, mp in enumerate(maps) if mp in todo]
        print("recording {} map(s) with the reference ({}) ...".format(len(jobs), "both seats" if two_ref else "against " + os.path.basename(opp_path)), flush=True)
        with mp_.Pool(min(a.procs, len(jobs)), initializer=pin.pin_pool_worker) as pool:
            for p in pool.imap_unordered(work_record, jobs):
                print("  recorded", os.path.basename(p), flush=True)
    others = ([] if a.no_self else [a.ref]) + list(a.other)
    labels = ([] if a.no_self else ["self (ref vs ref)"]) + [a.label[i] if i < len(a.label) else os.path.basename(p) for i, p in enumerate(a.other)]
    # cached replays: (network, map) -> result
    cache_path = os.path.join(a.record, "replay_{}.json".format(tag))
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
    ident_key = "ident|" + file_key(a.ref)
    jobs = []
    for mp in maps:
        need = [p for p in others if "{}||{}".format(file_key(p), mp) not in cache]
        if need or "{}||{}".format(ident_key, mp) not in cache:
            jobs.append((rec_files[mp], a.ref, need, mp))
    if jobs:
        print("replaying {} map(s) ...".format(len(jobs)), flush=True)
        with mp_.Pool(min(a.procs, len(jobs)), initializer=pin.pin_pool_worker) as pool:
            for (rf, _, need, mp), r in zip(jobs, pool.imap(work_replay, [j[:3] for j in jobs])):
                for p in need:
                    cache["{}||{}".format(file_key(p), mp)] = r["res"][p]
                cache["{}||{}".format(ident_key, mp)] = r["ident"]
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f)
                print("  replayed", mp, flush=True)
    names = head_names(len(T.Policy(a.ref).dims))
    idn = [cache["{}||{}".format(ident_key, mp)] for mp in maps]
    ident = dict(frames=sum(x["frames"] for x in idn), same=sum(x["same"] for x in idn))
    ident["share_same"] = ident["same"] / max(1, ident["frames"])
    ident["per_head"] = {nm: sum(x["same_head"][j] for x in idn) / max(1, ident["frames"]) for j, nm in enumerate(names)}
    res = dict(ref=a.ref, record=a.record, tag=tag, maps=maps, games_per_map=a.games, minutes=a.minutes, set=envvars, identity=ident, compare={})
    txt = ["drift check: reference {} | maps {} | {} game(s) a map | situations: {}".format(
        os.path.basename(a.ref), ",".join(maps), a.games, "the reference on both seats" if two_ref else "the reference against " + os.path.basename(opp_path)),
        "identity: the reference's replay redraws {:.2%} of the recorded frames exactly ({} seat-frames)".format(ident["share_same"], ident["frames"])]
    for p, lab in zip(others, labels):
        per = {mp: cache["{}||{}".format(file_key(p), mp)] for mp in maps}
        S = summarise(merge(list(per.values())), names)
        res["compare"][lab] = dict(path=p, all_maps=S, maps={mp: summarise(v, names)["all"] | dict(in_view=summarise(v, names)["in_view"]["kl_sum_mean"],
                                                                                               out_of_view=summarise(v, names)["out_of_view"]["kl_sum_mean"])
                                                          for mp, v in per.items()})
        txt.append(table(lab + "  (" + os.path.basename(p) + ")", S))
        txt.append("  by map, KL summed / agreement (all | in view | out of view): " + " ; ".join(
            "{} {:.4f} / {:.1%} | {:.4f} | {:.4f}".format(mp, v["kl_sum_mean"], v["agree_mean"], v["in_view"], v["out_of_view"]) for mp, v in res["compare"][lab]["maps"].items()))
    os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
    with open(a.json, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    T_ = "\n\n".join(txt) + "\n"
    with open(os.path.splitext(a.json)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write(T_)
    print(T_, flush=True)


if __name__ == "__main__":
    main()
