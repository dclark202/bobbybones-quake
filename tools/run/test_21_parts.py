"""2.1: unit tests of the trainer's new parts on made-up arrays (sim/mapsense.py, sim/appraise.py, sim/branch.py). CPU only, one
thread, a few seconds; no simulator, no trainer, no run's data.

    set CUDA_VISIBLE_DEVICES=-1 & set OMP_NUM_THREADS=1 & set OPENBLAS_NUM_THREADS=1
    <anaconda python> tools/run/test_21_parts.py

What it does NOT show (needs the simulator and the card, after 1.8): the worker's copy of a moment, the trainer's rows of the copy,
identity with the three parts off, a rollout with them on."""
import io
import json
import os
import sys
import tempfile

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import appraise as AP  # noqa: E402
import branch as BR  # noqa: E402
import mapsense as MS  # noqa: E402

torch.set_num_threads(1)
N_OK = [0]


def check(name, cond, note=None):
    print("{} {}{}".format("ok  " if cond else "FAIL", name, " (" + str(note) + ")" if note is not None else ""))
    assert cond, name
    N_OK[0] += 1


def fake_table(path, n=60, seed=0):
    r = np.random.default_rng(seed)
    P = r.uniform(-400, 400, (n, 3)).astype(np.float32)       # (every pair within the map sense's "near")
    P[:, 2] = r.uniform(0, 200, n)
    np.savez(path, nodes=P, B=r.uniform(0, 3, n).astype(np.float32), cov8=r.integers(0, 240, (n, n)).astype(np.uint8),
             seeb8=r.integers(0, 255, (3, n, n)).astype(np.uint8))
    return P


AUX = ("en_alive", "dmg_dealt", "dmg_taken", "frag", "fragged", "x", "y", "z", "died", "en_target", "en_weapon", "mega_take", "red_take")
IX = {k: i for i, k in enumerate(AUX)}


def test_mapsense():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "data", "maps"))
    P = fake_table(MS.table_path(d, "mapa"))
    T_, miss = MS.load_tables(d, ["mapa", "mapb"])
    check("map sense: a map without a table is skipped, not an error", list(T_) == ["mapa"] and miss == ["mapb"])
    S = T_["mapa"]
    check("map sense: the nearest walking point of a walking point is itself", (S.at(P[:10]) == np.arange(10)).all())
    L = MS.layout(T_, hid=16, every=5, tick=8, horizon_frames=200)
    T, N = 384, 8
    fr = MS.sample_frames(L, T)
    check("map sense: samples at ticks with a second behind and the horizon ahead", fr == [79, 119, 159] and all(t + 200 <= T and t >= 40 for t in fr), fr)
    mod = MS.make_module(L)
    x = torch.from_numpy(MS.encode(np.random.default_rng(1).uniform(0, 1, (5, 15)).astype(np.float32)))
    check("map sense: a new one forecasts 0 everywhere", float(mod(x, torch.zeros(5, dtype=torch.long)).abs().max()) == 0.0 and tuple(mod(x).shape) == (5, 2, 4))
    g0 = torch.random.get_rng_state()
    MS.make_module(L)
    check("map sense: made without a draw of the global random stream", bool((torch.random.get_rng_state() == g0).all()))
    # the labels' window: damage of step f is in aux row f + 1; cut after a round's end or his death (that step still counts)
    aux = np.zeros((T + 1, N, len(AUX)), np.float32)
    done = np.zeros((T, N), np.float32)
    aux[:, :, IX["en_alive"]] = 1.0
    seat_pos = P[np.arange(N)]
    aux[:, :, IX["x"]:IX["x"] + 3] = seat_pos[None]
    aux[1:, :, IX["dmg_dealt"]] = 1.0                        # every step: 1 dealt, 2 taken
    aux[1:, :, IX["dmg_taken"]] = 2.0
    done[100, 2] = 1.0                                       # seat 2's round ends in step 100
    aux[151, 4, IX["died"]] = 1.0                            # seat 4 dies in step 150
    aux[:, :, IX["en_weapon"]] = np.arange(N)[None] % 4      # row i: the weapon in the hand of i's enemy
    bel = np.zeros((T // 8, N, 5), np.float32)
    bel[:, :, :3] = seat_pos[np.arange(N) ^ 1][None]
    bel[:, :, 3] = 1.0
    bel[:, 6, 3] = 0.0                                       # seat 6 believes no place: no sample
    B = MS.batch(L, T_, np.array(["mapa"] * N), torch.from_numpy(aux).half(), torch.from_numpy(done), bel, IX)
    per = {t: None for t in fr}
    check("map sense: a batch of the right shapes", B["x"].shape[1] == MS.N_IN and B["y"].shape[1] == 2 and len(B["x"]) == len(B["row"]) == len(B["cls"]))
    # frame 79: seats 0..7 without 6 -> 7 rows in seat order; seat 2: steps 79..100 (22 steps); others 200 steps
    y79 = B["y"][:7] * 100.0
    check("map sense: 200 steps summed where nothing ends the stay", abs(y79[0, 0] - 200.0) < 1e-3 and abs(y79[0, 1] - 400.0) < 1e-3, y79[0])
    check("map sense: the window is cut at a round's end, its own step counted", abs(y79[2, 0] - 22.0) < 1e-3, y79[2])
    check("map sense: ... and at his death", abs(y79[4, 0] - (150 - 79 + 1)) < 1e-3, y79[4])
    check("map sense: no sample without a believed place", len(B["x"]) == 7 + 6 + 6, len(B["x"]))   # 119: seat 2's second behind holds its round's end; 159: seat 4's his death
    check("map sense: the class is the weapon in HIS hand (his enemy's row)", (B["cls"][:7] == MS.cls_of((np.arange(N) ^ 1) % 4)[[0, 1, 2, 3, 4, 5, 7]]).all())
    del per
    # the lesson moves the forecast toward the labels; the corrections decay toward zero under the pull
    opt = torch.optim.Adam(mod.parameters(), lr=1e-2)
    gen = torch.Generator().manual_seed(1)
    a0 = MS.learn(mod, opt, L, B, lr=0.0, pull=0.0, dev="cpu", gen=gen)
    check("map sense: rate 0 scores and does not learn", float(mod.corr.weight.abs().max()) == 0.0 and a0["n"] == len(B["x"]))
    for _ in range(60):
        a1 = MS.learn(mod, opt, L, B, lr=1e-2, pull=0.0, dev="cpu", gen=gen)
    check("map sense: the lesson lowers its error", float(a1["sq"].sum()) < 0.5 * float(a0["sq"].sum()), (float(a0["sq"].sum()), float(a1["sq"].sum())))
    c0 = float(mod.corr.weight.abs().mean())
    check("map sense: the corrections moved", c0 > 0)
    MS.learn(mod, opt, L, B, lr=1e-9, pull=1e8, dev="cpu", gen=gen)     # (a step of almost nothing, a pull of 10% a step)
    c1 = float(mod.corr.weight.abs().mean())
    check("map sense: the pull multiplies the corrections by 1 - rate x pull after each step", abs(c1 / c0 - 0.9) < 1e-3, c1 / c0)
    rec = MS.record(a1, 1.0, 1.0, L, skipped=miss)
    check("map sense: the record names the maps without a table", rec["maps_without_table"] == ["mapb"] and rec["frames"] == len(B["x"]))
    out = MS.read(mod, L, T_, "mapb", P[:3], P[3:6], np.zeros(3), np.zeros(3), np.zeros(3))
    check("map sense: a map without a table reads zeros", out.shape == (3, 2, 4) and float(np.abs(out).max()) == 0.0)
    check("map sense: no samples, no error", MS.batch(L, {}, np.array(["mapa"] * N), aux, done, bel, IX) is None and MS.learn(mod, opt, L, None, 1e-3, 1.0, "cpu", gen) == {})


def test_appraise():
    L = AP.layout(bel=8, mem=16, head=8, targets=17, hid=32)
    check("appraisals: the candidate's width has room for the whole instruction", L["cand"] == 8 + 17 + 10 + 8 and L["inp"] == 32 + 43)
    c = AP.cand(L, np.array([3, 16]))
    check("appraisals: a target-only candidate: no verb, the target, weapon 'none', no map sense",
          c[:, :8].sum() == 0 and c[0, 8 + 3] == 1 and c[1, 8 + 16] == 1 and (c[:, 8 + 17 + 9] == 1).all() and c[:, -8:].sum() == 0 and c.sum() == 4)
    c2 = AP.cand(L, np.array([8]), verb=np.array([4]), weapon=np.array([0]), ms=np.ones((1, 8)))
    check("appraisals: a full candidate", c2[0, 4] == 1 and c2[0, 8 + 17 + 0] == 1 and c2[0, -8:].sum() == 8)
    g0 = torch.random.get_rng_state()
    mod = AP.make_module(L)
    check("appraisals: made without a draw of the global random stream", bool((torch.random.get_rng_state() == g0).all()))
    S = torch.randn(64, L["sit"], generator=torch.Generator().manual_seed(2))
    C = torch.from_numpy(AP.cand(L, np.arange(64) % 17))
    f = AP.forecast(mod, S, C)
    check("appraisals: a new one forecasts 0 damage, chances of a half, no change", float(f[:, :2].abs().max()) == 0 and float((f[:, 2:5] - 0.5).abs().max()) == 0 and float(f[:, 5].abs().max()) == 0)
    Y = torch.zeros(64, len(AP.OUTS))
    Y[:, 0] = (torch.arange(64) % 17).float() / 10.0         # dealt depends on the target
    Y[:, 2] = (torch.arange(64) % 2).float()
    M = torch.ones(64, len(AP.OUTS))
    M[:, 5:] = 0.0                                           # no dv label (the 8 s one, the long one)
    opt = torch.optim.Adam(mod.parameters(), lr=3e-3)
    gen = torch.Generator().manual_seed(3)
    a0 = AP.learn(mod, opt, L, S.half(), C, Y, M, lr=0.0, dev="cpu", gen=gen)
    w5 = mod[4].weight[5].clone()
    for _ in range(150):
        a1 = AP.learn(mod, opt, L, S.half(), C, Y, M, lr=3e-3, dev="cpu", gen=gen)
    check("appraisals: the lesson lowers the labelled outputs' error", float(a1["sq"][0]) < 0.3 * float(a0["sq"][0]), (float(a0["sq"][0]), float(a1["sq"][0])))
    check("appraisals: an output without a label is not taught", bool((mod[4].weight[5] == w5).all()) and float(a1["n"][5]) == 0)
    r = AP.record(a1, 1.0, L)
    check("appraisals: the record", r["rows"] == 64 and "r2" in r["dealt"] and "brier" in r["he_dies"] and "dv" not in r)


def test_branch():
    rng = np.random.default_rng(5)
    el = np.ones(40, bool)
    el[:10] = False
    pl = BR.plan(rng, 40, el, 0.4, 8)
    src = [s for s, _ in pl]
    dst = [d for _, ds in pl for d in ds]
    check("branch: a share of the self-play matches are destinations, 8 a source", len(pl) == 2 and len(dst) == 16 and len(set(dst)) == 16)
    check("branch: sources are eligible and never destinations", all(s >= 10 for s in src) and not set(src) & set(dst))
    check("branch: share 0 plans nothing", BR.plan(rng, 40, el, 0.0, 8) == [] and BR.plan(rng, 40, np.zeros(40, bool), 0.5, 8) == [])
    sc = np.arange(17, dtype=np.float64)
    ok = np.ones(17, bool)
    ok[[16, 15]] = False
    c = BR.candidates(sc, ok, 5, 3, rng)
    check("branch: his five best allowed targets and three others, all distinct, never 'none'", c[:5] == [14, 13, 12, 11, 10] and len(set(c)) == 8 and 0 not in c and not {15, 16} & set(c), c)
    check("branch: fewer allowed targets, fewer candidates", len(BR.candidates(sc, np.eye(17, dtype=bool)[3], 5, 3, rng)) == 1)

    class Pipe:                                              # a stand-in for a simulator's pipe
        def __init__(self):
            self.got = []

        def send(self, x):
            self.got.append(x)

        def recv(self):
            return True
    pipes = [Pipe(), Pipe()]
    w_off = [0, 80, 160]                                     # two simulators of 40 matches of two; 20 self-play matches each
    N = 160
    scores = np.tile(np.arange(17, dtype=np.float64), (N, 1))
    elig = np.ones(N, bool)
    m = BR.start(np.random.default_rng(6), pipes, w_off, [20, 20], 2, 0.45, 5, 3, 40, scores, elig, np.ones((N, 17), bool))
    check("branch: every simulator gets its plan", all(len(p.got) == 1 and p.got[0][0] == "branch" and p.got[0][1]["hold"] == 40 for p in pipes))
    check("branch: the trainer's seats of the plan", len(m["src"]) == 2 and len(m["dst"]) == 16 and (m["dst"] % 2 == 0).all() and len(m["rows_dst"]) == 32
          and (m["rows_src"][0::2] % 2 == 0).all() and (m["rows_dst"][1::2] == m["rows_dst"][0::2] + 1).all())
    check("branch: sources and destinations are self-play seats of the same simulator",
          all((s % 80) < 40 for s in m["src"]) and all((d % 80) < 40 and d // 80 == m["src"][k] // 80 for d, k in zip(m["dst"], m["dst_src"])))
    check("branch: off, nothing is sent", BR.start(np.random.default_rng(6), [Pipe()], [0, 80], [20], 2, 0.0, 5, 3, 40, scores[:80], elig[:80], np.ones((80, 17), bool)) is None)
    # the trainer's rows of a copy
    h = torch.arange(N * 3, dtype=torch.float32).view(N, 3)
    hist = torch.arange(5 * N, dtype=torch.float32).view(5, N)
    arr = np.arange(N * 2, dtype=np.float32).reshape(N, 2)

    class Obj:
        pass
    o = Obj()
    o.s, o.name, o.L = h.clone(), "x", dict(a=1)
    BR.copy_seats((h, arr), m["rows_src"], m["rows_dst"], N)
    BR.copy_seats(hist, m["rows_src"], m["rows_dst"], N)
    BR.copy_seats(o, m["rows_src"], m["rows_dst"], N)
    BR.copy_seats(None, m["rows_src"], m["rows_dst"], N)
    check("branch: a destination's rows are its source's (tensors, arrays, a history's columns, an object's)",
          bool((h[m["rows_dst"]] == h[m["rows_src"]]).all()) and (arr[m["rows_dst"]] == arr[m["rows_src"]]).all()
          and bool((hist[:, m["rows_dst"]] == hist[:, m["rows_src"]]).all()) and bool((o.s == h).all()))
    untouched = np.setdiff1d(np.arange(N), m["rows_dst"])
    check("branch: every other seat's rows are untouched", (arr[untouched] == np.arange(N * 2, dtype=np.float32).reshape(N, 2)[untouched]).all())

    # the simulator's side, on a stand-in
    class Env:
        n = 8

        def __init__(self):
            self.x = np.arange(8.0)
            self.fo_okq = np.ones((5, 8), bool)
            self.ctl_q_ok = np.ones((3, 8), bool)

        def _seats(self, m_):
            return [2 * m_, 2 * m_ + 1]

        def _moment_take(self, m_, obs):
            return dict(x=self.x[self._seats(m_)].copy())

        def _moment_set(self, m_, mo, obs):
            self.x[self._seats(m_)] = mo["x"]
    e = Env()
    st = BR.worker_start(e, dict(jobs=[(0, [1, 3], [5, 9])], hold=2))
    check("branch: the simulator copies the moment and forces the even seat's target", (e.x == [0, 1, 0, 1, 4, 5, 0, 1]).all() and list(e.force_intent) == [-1, -1, 5, -1, -1, -1, 9, -1])
    check("branch: the hindsight books' queries of the copied seats are shut", not e.fo_okq[:, [2, 3, 6, 7]].any() and e.fo_okq[:, [0, 1, 4, 5]].all() and not e.ctl_q_ok[:, 2].any())
    il, it, kl = np.ones(8, bool), np.zeros(8, np.int64), np.ones(8, bool)
    st = BR.worker_after(st, e, il, it, kl)
    check("branch: on a forced frame the forced seats' target and keep choice count as not read", list(np.nonzero(~il)[0]) == [2, 6] and list(it[[2, 6]]) == [-1, -1] and not kl[[2, 6]].any() and kl[[0, 3]].all() and st is not None)
    st = BR.worker_after(st, e, np.ones(8, bool), np.zeros(8, np.int64), None)
    check("branch: after the hold the targets are free again", st is None and (e.force_intent == -1).all())

    # the outcomes
    T, Nn, W, H = 64, 4, 32, 5
    aux = np.zeros((T + 1, Nn, len(AUX)), np.float32)
    done = np.zeros((T, Nn), np.float32)
    hr = np.ones((T, Nn), np.float32) * 0.5
    vh = np.zeros((T + 1, Nn), np.float32)
    vh[0], vh[W] = 1.0, 3.0
    aux[1:, :, IX["dmg_dealt"]] = 2.0
    aux[1:, :, IX["dmg_taken"]] = 1.0
    aux[10, 0, IX["frag"]] = 1.0
    aux[20, 0, IX["mega_take"]] = 2.0                        # the enemy took the mega: not his
    aux[21, 2, IX["red_take"]] = 1.0
    aux[H, 1, IX["en_target"]] = 7                           # seat 0's target at the hold's end is in his enemy's row
    aux[H, 3, IX["en_target"]] = 4
    done[9, 2] = 1.0                                         # seat 2's round ends in step 9: 10 steps count
    aux[30, 2, IX["fragged"]] = 1.0                          # after the cut: not counted
    g = 0.99
    oc = BR.outcomes(np.array([0, 2]), torch.from_numpy(aux).half(), torch.from_numpy(done), torch.from_numpy(hr), torch.from_numpy(vh), IX, g, H, W,
                     ws=torch.from_numpy(hr))
    disc = g ** np.arange(W)
    check("branch: damage over the window", abs(oc["dealt"][0] - 2 * W) < 1e-6 and abs(oc["taken"][0] - W) < 1e-6)
    check("branch: the frag, the item (his own take only), his target at the hold's end", oc["he_dies"][0] == 1 and oc["item"][0] == 0 and oc["got"][0] == 7 and oc["got"][1] == 4)
    check("branch: dv = the discounted pay + gamma^W x the head's value then - its value now", abs(oc["dv"][0] - ((0.5 * disc).sum() + g ** W * 3.0 - 1.0)) < 1e-5, oc["dv"][0])
    check("branch: a round's end cuts the window: its own step counts, nothing after, no bootstrap",
          oc["cut"][1] and oc["frames"][1] == 10 and abs(oc["dealt"][1] - 20) < 1e-6 and oc["i_die"][1] == 0 and oc["item"][1] == 0
          and abs(oc["dv"][1] - ((0.5 * disc[:10]).sum() - 1.0)) < 1e-5, (oc["frames"][1], oc["dv"][1]))
    check("branch: the judge's pay summed beside it", abs(oc["judge"][0] - 0.5 * W) < 1e-5)
    oc2 = BR.outcomes(np.array([0]), aux, done, hr, None, IX, g, H, W)
    check("branch: without the head's value there is no dv", np.isnan(oc2["dv"][0]) and np.isnan(oc2["judge"][0]))
    meta = dict(src=np.array([0]), dst=np.array([0, 2]), dst_src=np.array([0, 0]), tg=np.array([7, 9]))
    si, tg, kd, Y, M = BR.rows(meta, oc, oc2, 17)
    check("branch: a forced target that did not hold is dropped; the source is a free example of his own target",
          list(tg) == [7, 7] and list(kd) == [1, 0] and list(si) == [0, 0] and M[0, 5] == 1 and M[1, 5] == 0 and abs(Y[0, 0] - 2 * W / 100.0) < 1e-6)
    p = os.path.join(tempfile.mkdtemp(), "branches.jsonl")
    BR.log_rows(p, 3, meta, oc, oc2, np.array(["mapa"] * 4))
    check("branch: the log has a line a branch and a source", len(open(p).read().splitlines()) == 3)
    r = BR.record(meta, oc, oc2, len(si), 0.1, 0.25)
    check("branch: the record", r["moments"] == 1 and r["branches"] == 2 and r["held"] == 1 and BR.record(None, None, None, 0, 0, 0.0)["branches"] == 0)


def test_off():
    """with the three flags at their defaults the trainer makes nothing: read from its source (it is not started here)"""
    src = open(os.path.join(ROOT, "sim", "train_duel_rnn.py"), encoding="utf-8").read()
    for flag in ('"--map-sense", type=float, default=0.0', '"--appraise", type=float, default=0.0', '"--branch", type=float, default=0.0',
                 '"--branch-p", type=float, default=0.0'):
        check("off: the default of {} is off".format(flag.split(",")[0]), flag in src)
    check("off: the modules are made only under their flags", "    if MS_ON:\n        assert BEL and BTOK_ON" in src.replace("\r\n", "\n")
          and "    if APR_ON:\n        assert BEL and H2" in src.replace("\r\n", "\n"))
    check("off: a simulator is sent a branch only with the rounds on and a share above 0", "        if BR_ON:" in src and "            if BR_P[0] > 0:" in src)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import importlib
    T = importlib.import_module("train_duel_rnn")
    check("live: the four new names are the trainer's, the share within 0 .. 1",
          all(k in T.LIVE_TRAINER for k in ("MAP_SENSE_W", "MAP_SENSE_PULL", "APPRAISE_W", "BRANCH_P")) and T.LIVE_RANGE["BRANCH_P"] == (0.0, 1.0))

    class E:                                                 # a stand-in simulator module with no live names of its own
        LIVE_VARS = ()

        @staticmethod
        def live_values(get):
            return {}
    import json
    p = os.path.join(tempfile.mkdtemp(), "live.json")
    json.dump(dict(MAP_SENSE_W=0.5, MAP_SENSE_PULL=2.0, APPRAISE_W=1.0, BRANCH_P=0.25), open(p, "w"))
    v, tv, why = T.live_read(p, E, {}, {})
    check("live: a file with the four names is accepted", why is None and tv["BRANCH_P"] == 0.25, why)
    json.dump(dict(BRANCH_P=1.5), open(p, "w"))
    check("live: a share above 1 is refused", T.live_read(p, E, {}, {})[2] is not None)




# ------------------------------------------------------------------------------------------ 2.1: the head's choice of an instruction
def test_ins():
    import head2 as H2
    C, F, NW = 32, 32, 9
    L0 = H2.layout(obs=list(range(20)))
    L = H2.add_ins(L0, F, NW, C)
    check("ins: the head's input grows by the part 'ins' alone, before the weapon part's",
          H2.u_width(L) == H2.u_width(L0) + H2.ins_u_width(F) and H2._offs(L)["ins"][1] == H2._offs(L)["wobs"][0])
    B = 5
    u0 = H2.feats(L, brain=torch.ones(B, 256), obs=torch.ones(B, 40), hands=torch.ones(B, 512))
    o = H2._offs(L)["ins"]
    check("ins: no instruction given: the part reads zeros, the rest as before",
          not u0[:, o[0]:o[1]].any() and torch.equal(u0[:, :o[0]], H2.feats(L0, brain=torch.ones(B, 256), obs=torch.ones(B, 40), hands=torch.ones(B, 512))))
    st0 = torch.random.get_rng_state()
    m = H2.make_module(L)                                    # (inside the head: the scorer's layers are the head's own)
    check("ins: making the head with its scorer draws nothing from the global stream", torch.equal(st0, torch.random.get_rng_state()))
    g = torch.Generator().manual_seed(1)
    s, X, A = torch.randn(B, 256, generator=g), torch.randn(B, C, F, generator=g), torch.randn(B, C, H2.INS_A, generator=g)
    ok = torch.rand(B, C, generator=g) < 0.5
    ok[:, 30] = True
    ok[4] = False
    wok = torch.rand(B, NW, generator=g) < 0.5
    wok[:, 8] = True
    sc = H2.ins_scores(m, s, X, A, ok)
    check("ins: at the start every offered row scores alike, a row not offered never",
          tuple(sc.shape) == (B, C) and float(sc[ok].abs().max()) == 0.0 and float(sc[~ok].max()) < -1e30)
    sw = H2.ins_wscores(m, s, X[:, 0], wok)
    check("ins: the weapon's scores: a weapon he cannot use never", tuple(sw.shape) == (B, NW) and float(sw[~wok].max()) < -1e30 and float(sw[wok].abs().max()) == 0.0)
    dv = torch.randn(B, C, generator=g)
    tq = H2.ins_target(dv, ok, 0.5)
    ref = torch.softmax(torch.where(ok[0], dv[0] / 0.5, torch.full_like(dv[0], -1e30)), -1)
    check("ins: the lesson's target is softmax(dV / temperature) over the offered rows; none offered: zeros",
          torch.allclose(tq[0], ref, atol=1e-6) and float(tq[:4].sum(-1).min()) > 0.999 and float(tq[4].sum()) == 0.0 and float(tq[~ok].max()) == 0.0)
    with torch.no_grad():                                    # the numpy sums are the trainer's
        for p in H2.ins_params(m):
            p.copy_(torch.randn(p.shape, generator=g) * 0.3)
    Wn = H2.np_ins_params(m.state_dict())
    d1 = np.abs(H2.np_ins_scores(Wn, s.numpy(), X.numpy(), A.numpy(), ok.numpy())[ok.numpy()] - H2.ins_scores(m, s, X, A, ok)[ok].detach().numpy()).max()
    d2 = np.abs(H2.np_ins_wscores(Wn, s.numpy(), X[:, 0].numpy(), wok.numpy())[wok.numpy()] - H2.ins_wscores(m, s, X[:, 0], wok)[wok].detach().numpy()).max()
    check("ins: the checks' numpy scorer gives the trainer's numbers", d1 < 1e-4 and d2 < 1e-4, (float(d1), float(d2)))
    # the lesson
    m = H2.make_module(L)
    opt = torch.optim.Adam(H2.ins_params(m), lr=1e-3)
    R = 512
    s, X, A = torch.randn(R, 256, generator=g), torch.randn(R, C, F, generator=g), torch.randn(R, C, H2.INS_A, generator=g)
    ok = torch.rand(R, C, generator=g) < 0.6
    ok[:, 30] = True
    wok = torch.ones(R, NW, dtype=torch.bool)
    A[..., 5] = X[..., 3]                                    # the forecast dV follows one of the row's numbers: learnable
    tq = H2.ins_target(A[..., 5], ok, 0.3)
    tw = H2.ins_target(torch.randn(R, NW, generator=g), wok, 0.3)
    c = torch.multinomial(ok.float(), 1, generator=g).squeeze(1)
    Bt = dict(s=s, X=X, A=A, ok=ok, wok=wok, xw=X[torch.arange(R), c], c=c, w=torch.zeros(R, dtype=torch.long), lp=torch.zeros(R),
              own=torch.zeros(R, dtype=torch.bool), adv=torch.randn(R, generator=g), tq=tq, tm=torch.ones(R, dtype=torch.bool), tw=tw,
              twm=torch.ones(R, dtype=torch.bool))
    gen = torch.Generator().manual_seed(2)
    a0 = H2.ins_learn(m, opt, Bt, lr=0.0, dev="cpu", gen=gen, teach_w=1.0, pg_w=0.0, ent_w=0.0)
    for _ in range(30):
        H2.ins_learn(m, opt, Bt, lr=3e-3, dev="cpu", gen=gen, teach_w=1.0, pg_w=0.0, ent_w=0.0, mb=256)
    a1 = H2.ins_learn(m, opt, Bt, lr=0.0, dev="cpu", gen=gen, teach_w=1.0, pg_w=0.0, ent_w=0.0)
    check("ins: the lesson moves the scorer toward the appraisals' order (KL to the target falls)", a1["kl"] < 0.7 * a0["kl"],
          (round(a0["kl"] / R, 4), round(a1["kl"] / R, 4)))
    m2 = H2.make_module(L)
    with torch.no_grad():
        for p in H2.ins_params(m2):
            p.copy_(torch.randn(p.shape, generator=g) * 0.1)
    w0 = [p.detach().clone() for p in m2.parameters()]
    H2.ins_learn(m2, torch.optim.Adam(m2.parameters(), lr=1e-3), dict(Bt, tm=torch.zeros(R, dtype=torch.bool), twm=torch.zeros(R, dtype=torch.bool)),
                 lr=1e-3, dev="cpu", gen=gen, teach_w=1.0, pg_w=1.0, ent_w=0.0)
    check("ins: a reading that was not his own (a drill's, a forced branch's) and may not be taught moves nothing",
          all(torch.equal(a_, b_) for a_, b_ in zip(w0, m2.parameters())))
    H2.ins_learn(m2, torch.optim.Adam(m2.parameters(), lr=1e-3), dict(Bt, own=torch.ones(R, dtype=torch.bool), tm=torch.zeros(R, dtype=torch.bool),
                                                                    twm=torch.zeros(R, dtype=torch.bool)),
                 lr=1e-3, dev="cpu", gen=gen, teach_w=0.0, pg_w=1.0, ent_w=0.0)
    check("ins: his own readings learn from the game's pay (the head's advantage)", any(not torch.equal(a_, b_) for a_, b_ in zip(w0, m2.parameters())))
    rec = H2.ins_record(a1, dict(verb=np.array([0, 3, 0, 1, 1, 0, 0, 0, 0.0]), weapon=np.ones(NW), picks=5, secs=10.0, cal_n=0,
                                 quiet=np.array([0, 1, 0, 0, 1, 0, 0, 0, 0.0]), block=np.array([3.0, 1, 1]), block_names=["go", "spush", "sspam"]),
                        L, 0.5, 1.0, 0.0, 0.3, True)
    check("ins: the record has the share, the entropy, the verbs, the weapons, the rows by block and quiet by verb",
          rec["g"] == 0.5 and "entropy" in rec and abs(sum(rec["verbs"]) - 1) < 1e-3 and rec["changes_a_second"] == 0.5
          and rec["row_blocks"] == {"go": 0.6, "spush": 0.2, "sspam": 0.2} and rec["rows"] == R and rec["quiet"] == 0.4 and rec["quiet_by_verb"][1] == round(1 / 3, 4))
    Lq = H2.add_ins(L0, F, NW, C, quiet=1)
    mq = H2.make_module(Lq)
    pq = torch.sigmoid(H2.ins_qlogit(mq, torch.randn(4, 256, generator=g), torch.randn(4, F, generator=g)))
    check("quiet: the scorer's third choice is there only where asked for, and at the start it is all but never asked",
          H2.has_quiet(mq) and not H2.has_quiet(m) and float(pq.max()) < 0.01)
    ALq = AP.layout(xf=F, quiet=1)
    cq1 = AP.cand(ALq, np.full(2, -1), weapon=np.array([0, 0]), x=np.zeros((2, F), np.float32), quiet=np.array([1, 0]))
    cq2 = AP.cand_rows(ALq, torch.zeros(2, F), torch.tensor([0, 0]), torch.tensor([1, 0])).numpy()
    check("quiet: the appraisals read the bit; the lesson's candidates and the rollout's are written alike",
          ALq["cand"] == AP.layout(xf=F)["cand"] + 1 and np.array_equal(cq1, cq2) and cq1[0].sum() == 2 and cq1[1].sum() == 1)
    Bq = dict(Bt, own=torch.ones(R, dtype=torch.bool), q=torch.zeros(R, dtype=torch.long), tqq=torch.full((R,), 0.9))
    b0 = float(mq.ins_qv.bias)
    for _ in range(20):
        H2.ins_learn(mq, torch.optim.Adam(mq.parameters(), lr=1e-2), Bq, lr=1e-2, dev="cpu", gen=gen, teach_w=1.0, pg_w=0.0, ent_w=0.0)
    check("quiet: the lesson moves the logit toward the chance the appraisals' two forecasts give", float(mq.ins_qv.bias) > b0 + 0.05, (b0, float(mq.ins_qv.bias)))
    # the seats' held instruction
    I = H2.InsState(6, L["ins"], "cpu")
    I.has[:] = True
    I.reset(torch.tensor([1.0, 0, 0, 1, 0, 0]), 1.0, torch.Generator().manual_seed(3))
    check("ins: a round's end: no instruction, the coin anew at the share", I.has.tolist() == [False, True, True, False, True, True]
          and I.own.tolist() == [True, False, False, True, False, False])
    check("ins: the part of the head's input is zero for a seat under none", not I.u()[0].any() and float(I.u()[1, -1]) == 1.0)
    # the appraisals read a row; numpy the same
    AL = AP.layout(xf=F)
    am = AP.make_module(AL)
    with torch.no_grad():
        for p in am.parameters():
            p.copy_(torch.randn(p.shape, generator=g) * 0.05)
    S = torch.randn(4, AL["sit"], generator=g)
    Xr = torch.randn(4, C, F, generator=g)
    wq = torch.randint(-1, NW, (4, C), generator=g)
    f1 = AP.forecast_rows(am, AL, S, Xr, wq)
    f2 = AP.np_forecast_rows(AP.np_params(am.state_dict()), AL, S.numpy(), Xr.numpy(), wq.numpy())
    check("appraise: a row's numbers are read; the numpy forecasts are the trainer's", tuple(f1.shape) == (4, C, len(AP.OUTS)) and float(np.abs(f1.numpy() - f2).max()) < 1e-4)
    c1 = AP.cand(AL, np.full(3, -1), weapon=np.array([0, -1, 8]), x=np.ones((3, F), np.float32))
    c2 = AP.cand_rows(AL, torch.ones(3, F), torch.tensor([0, -1, 8])).numpy()
    check("appraise: the lesson's candidates and the rollout's are written alike; no target named: none", np.array_equal(c1, c2) and not c1[:, 8:8 + 17].any())
    check("appraise: a layout without the rows (xf 0) is the one before", AP.layout()["cand"] == AP.N_VERB + 17 + AP.N_WEAPON + AP.N_MS)


def test_branch_ins():
    rng = np.random.default_rng(0)
    c = BR.candidates(np.array([5.0, 1, 2, 3, 4, 0, 0, 0]), np.array([1, 1, 1, 1, 1, 0, 1, 1], bool), 2, 2, rng, skip0=False)
    check("branch: an instruction's row 0 is a row as any other; the best first, the rest drawn", c[:2] == [0, 4] and len(set(c)) == 4 and 5 not in c)

    class Pipe:
        def __init__(self):
            self.sent = []

        def send(self, x):
            self.sent.append(x)

        def recv(self):
            return True
    N, C = 16, 32
    pipes = [Pipe()]
    sc = rng.normal(size=(N, C))
    ok = np.ones((N, C), bool)
    wb = rng.integers(0, 9, (N, C))
    bm = BR.start(rng, pipes, [0, N], [8], 2, 1.0, 2, 1, 40, sc, np.ones(N, bool), ok, wbest=wb)
    job = pipes[0].sent[0][1]["jobs"][0]
    check("branch: the plan forces instructions: a row and the weapon the head scores best for it",
          bm is not None and bm["ins"] and pipes[0].sent[0][1]["ins"] and len(job) == 4 and job[3] == [int(wb[2 * job[0], r]) for r in job[2]]
          and np.array_equal(bm["w"], wb[bm["src"][bm["dst_src"]], bm["tg"]]))

    class Env:
        n = N
        force_instr = np.full((N, 2), -1, np.int64)
        ins_v = np.zeros(N, np.int64)
        ins_drill = np.zeros(N, bool)

        def _moment_take(self, s, o):
            return s

        def _moment_set(self, d, mo, o):
            pass

        def _seats(self, m):
            return [2 * m, 2 * m + 1]
    env = Env()
    st = BR.worker_start(env, pipes[0].sent[0][1])
    d0 = int(job[1][0])
    check("branch: the simulator's seat is forced to the row and its weapon; its enemy is not",
          env.force_instr[2 * d0].tolist() == [int(job[2][0]), int(job[3][0])] and env.force_instr[2 * d0 + 1].tolist() == [-1, -1] and st["ins"])
    il, it, kl = np.ones(N, bool), np.zeros(N, np.int64), np.ones(N, bool)
    for _ in range(40):
        st = BR.worker_after(st, env, il, it, kl)
    check("branch: the hold over: the force is lifted", st is None and (env.force_instr == -1).all())
    env.ins_v[3], env.ins_drill[5], env.force_instr[7, 0] = 2, True, 4
    il, it, kl = np.ones(N, bool), np.zeros(N, np.int64), np.ones(N, bool)
    BR.worker_mask(env, il, it, kl)
    check("worker: a seat under an instruction did not play its drawn target; a drill's and a forced seat did not keep or re-decide",
          (~il).nonzero()[0].tolist() == [3] and it[3] == -1 and (~kl).nonzero()[0].tolist() == [5, 7])
    B, S = len(bm["dst"]), len(bm["src"])
    bm.update(X=rng.normal(size=(B, 32)).astype(np.float32), src_has=np.arange(S) % 2 == 0, src_X=rng.normal(size=(S, 32)).astype(np.float32),
              src_w=np.full(S, 3))

    def oc(n):
        return dict(dealt=np.full(n, 50.0), taken=np.full(n, 20.0), he_dies=np.zeros(n), i_die=np.zeros(n), item=np.ones(n),
                    dv=np.where(np.arange(n) % 3 == 0, np.nan, 0.1), judge=np.zeros(n), cut=np.zeros(n, bool), frames=np.full(n, 320.0),
                    got=np.zeros(n, np.int64))
    si, X, w, kind, Y, M = BR.rows_ins(bm, oc(B), oc(S))
    ns = int(bm["src_has"].sum())
    check("branch: an instruction branch teaches twice (with its weapon, and with none named); a source only if it was under the head's",
          len(si) == 2 * B + ns and (w[B:2 * B] == -1).all() and np.array_equal(w[:B], bm["w"]) and (w[2 * B:] == 3).all()
          and kind.tolist() == [1] * (2 * B) + [0] * ns and Y.shape == (2 * B + ns, 7) and M[0, 5] == 0 and M[1, 5] == 1 and not M[:, 6].any())
    check("branch: the record counts every forced instruction as held", BR.record(bm, oc(B), oc(S), len(si), 0.1, 0.5)["held"] == B)


def test_long():
    import head2 as H2
    rng = np.random.default_rng(5)
    T, N, W, gm = 8, 6, 20, 0.9
    seats = np.array([0, 2, 4])
    v0 = np.zeros((T + 1, N))
    v0[0, seats] = [1.0, 2.0, 3.0]
    rec = BR.long_new(seats, np.zeros((3, 4), np.float32), np.zeros((3, 5), np.float32), v0)
    hr = [rng.normal(size=(T, N)) for _ in range(3)]
    dn = [np.zeros((T, N)) for _ in range(3)]
    dn[1][3, 2] = 1.0                                        # seat 2's round ends on frame 11 of the window
    vh = [rng.normal(size=(T + 1, N)) for _ in range(3)]
    going, fin = [rec], []
    for q in range(3):
        going, f_ = BR.long_step(going, hr[q], dn[q], vh[q], gm, W, T)
        fin += f_
    allr = np.concatenate(hr)[:W]
    disc = gm ** np.arange(W)
    full0 = (allr[:, 0] * disc).sum() + gm ** W * vh[2][W - 2 * T, 0] - 1.0
    cut2 = (allr[:12, 2] * disc[:12]).sum() - 2.0
    check("long: a branch read across rollouts: the discounted pay of the whole window, the head's value at its end as the bootstrap, less its value at the copy",
          len(fin) == 1 and not going and abs(fin[0]["dv"][0] - full0) < 1e-9, (float(fin[0]["dv"][0]), float(full0)))
    check("long: cut at a round's end: that step counts, nothing after it, no bootstrap", abs(fin[0]["dv"][1] - cut2) < 1e-9, (float(fin[0]["dv"][1]), float(cut2)))
    busy = BR.long_busy([rec], [dict(long=np.array([True, False]), dst=np.array([8, 10]), src=np.array([12]), src_long=np.array([True]), dst_src=np.array([0, 0]))], 16)
    check("long: the seats of a long branch being read, and their enemies, are left alone by later plans",
          np.nonzero(busy)[0].tolist() == [0, 1, 2, 3, 4, 5, 8, 9, 12, 13])
    free = np.ones(8, bool)
    free[[1, 2]] = False
    pl = BR.plan(np.random.default_rng(1), 8, free.copy(), 1.0, 2, free=free)
    used = [s_ for s_, ds in pl] + [d for _, ds in pl for d in ds]
    check("long: a plan takes no match that is not free", pl and not ({1, 2} & set(used)) and len(set(used)) == len(used), used)

    class Pipe:
        def send(self, x):
            pass

        def recv(self):
            return True
    N2 = 32
    bm = BR.start(np.random.default_rng(2), [Pipe()], [0, N2], [16], 2, 1.0, 2, 1, 40, np.random.default_rng(3).normal(size=(N2, 17)),
                  np.ones(N2, bool), np.ones((N2, 17), bool), long_p=0.5)
    check("long: a share of a plan's branches is marked long, and the sources of those",
          bm["long"].dtype == bool and 0 < bm["long"].sum() < len(bm["long"]) and np.array_equal(np.nonzero(bm["src_long"])[0], np.unique(bm["dst_src"][bm["long"]])))
    bm0 = BR.start(np.random.default_rng(2), [Pipe()], [0, N2], [16], 2, 1.0, 2, 1, 40, np.random.default_rng(3).normal(size=(N2, 17)),
                   np.ones(N2, bool), np.ones((N2, 17), bool))
    check("long: off (share 0): the plan is the one before, nothing more is drawn", "long" not in bm0 and np.array_equal(bm0["dst"], bm["dst"]) and np.array_equal(bm0["tg"], bm["tg"]))
    A = torch.zeros(2, 3, H2.INS_A)
    A[..., H2.INS_DV], A[..., H2.INS_DVL] = 1.0, 3.0
    check("long: the lesson's number is the live mix of the two windows", float(H2.ins_dv(A, 0.0)[0, 0]) == 1.0 and float(H2.ins_dv(A, 0.5)[0, 0]) == 2.0
          and float(H2.ins_dv(A, 1.0)[0, 0]) == 3.0)
    check("long: the appraisals have the seventh output, a regression", AP.OUTS[6] == "dv_long" and 6 in AP.REG and AP.layout()["d"] == 7)
    import importlib
    import json
    T_ = importlib.import_module("train_duel_rnn")

    class E0:
        LIVE_VARS = ()

        @staticmethod
        def live_values(get):
            return {}
    p = os.path.join(tempfile.mkdtemp(), "live.json")
    json.dump(dict(BRANCH_LONG_P=0.25, INS_LONG_W=0.5), open(p, "w"))
    v, tv, why = T_.live_read(p, E0, {}, {})
    check("live: the long window's two names are accepted", why is None and tv["BRANCH_LONG_P"] == 0.25 and tv["INS_LONG_W"] == 0.5, why)
    for bad in (dict(BRANCH_LONG_P=1.1), dict(INS_LONG_W=-0.2)):
        json.dump(bad, open(p, "w"))
        check("live: {} is refused".format(bad), T_.live_read(p, E0, {}, {})[2] is not None)


def test_live_ins():
    import importlib
    import json
    T = importlib.import_module("train_duel_rnn")
    names = ("INS_G", "INS_TEACH", "H2_INS_PG", "INS_TEMP", "INS_ENT")
    check("live: the instruction's five names are the trainer's, with their ranges",
          all(k in T.LIVE_TRAINER for k in names) and T.LIVE_RANGE["INS_G"] == (0.0, 1.0) and T.LIVE_RANGE["H2_INS_PG"] == (0.0, 1.0))
    os.environ["INSTR"] = "1"
    try:
        import duel_env_ffa as E
    except Exception as e_:  # noqa: BLE001
        E = None
        print("     (the simulator's module did not import here: {}; its drill names are not checked)".format(e_))
    p = os.path.join(tempfile.mkdtemp(), "live.json")
    if E is not None:
        check("live: the drills' three names are the simulator's live names", all(k in E.LIVE_VARS for k in ("DRILL_INS_P", "INS_DRILL_SECS", "DRILL_INS_VERBS", "DRILL_INS_QUIET"))
              and "DRILL_INS_VERBS" in E.LIVE_STR)
        json.dump(dict(INS_G=0.3, INS_TEACH=1.0, H2_INS_PG=0.5, INS_TEMP=0.05, INS_ENT=0.0, DRILL_INS_P=0.1, INS_DRILL_SECS=8, DRILL_INS_VERBS="hold:2,spam:2,check:1", DRILL_INS_QUIET=0.25),
                  open(p, "w"))
        v, tv, why = T.live_read(p, E, {}, {})
        check("live: a file with the instruction's and the drills' names is accepted", why is None and tv["INS_G"] == 0.3 and v["DRILL_INS_P"] == "0.1", why)
        check("live: the simulator's shape is read from its module, not written here",
              E.INS_C == sum(m_ for _, m_ in E.INS_BLOCKS) and len(E.INS_FEAT) == E.INS_F and set(E.INS_FILL) == {"unsure", "known", "spawn_odds"})
        for bad in (dict(DRILL_INS_P=1.5), dict(INS_DRILL_SECS=0.5), dict(DRILL_INS_VERBS="dance:1"), dict(DRILL_INS_QUIET=1.5)):
            json.dump(bad, open(p, "w"))
            check("live: {} is refused".format(bad), T.live_read(p, E, {}, {})[2] is not None)

    class E0:
        LIVE_VARS = ()

        @staticmethod
        def live_values(get):
            return {}
    for bad in (dict(INS_G=1.2), dict(H2_INS_PG=-0.1), dict(INS_TEMP=0.0)):
        json.dump(bad, open(p, "w"))
        check("live: {} is refused".format(bad), T.live_read(p, E0, {}, {})[2] is not None)


# ------------------------------------------------------------------------------- 2.1: the brain's questions, the rows' fill, the reading
def test_questions():
    import importlib
    import json
    import head2 as H2
    import knownodds as KN
    import spawnodds as SP
    g = torch.Generator().manual_seed(5)
    # ---- "does the enemy know where I am"
    KL = KN.layout(bel=16, mem=24, hid=8, tick=8, every=2)
    st0 = torch.random.get_rng_state()
    km = KN.make_module(KL)
    check("known: made without a draw of the global stream", torch.equal(st0, torch.random.get_rng_state()))
    sb, hh = torch.randn(6, 16, generator=g), torch.randn(6, 40, generator=g)
    c0 = KN.chance(km, sb, hh)
    check("known: a new readout says a half for both", tuple(c0.shape) == (6, 2) and float((c0 - 0.5).abs().max()) == 0.0)
    T, N, U = 64, 10, 60
    aux_n = ("en_alive", "en_knows", "en_heard", "en_spawn", "x", "y", "z")
    ix = {k: i for i, k in enumerate(aux_n)}
    aux = torch.zeros(T + 1, N, len(aux_n))
    aux[:, :, ix["en_alive"]] = 1.0
    aux[:, :, ix["en_spawn"]] = -1.0
    U2 = torch.randn(T // 8, N, U, generator=g).half()
    U2[:, :, 0] = (torch.arange(N) % 2).half()[None, :]          # (the truth is readable from the brain's first number)
    aux[:, :, ix["en_knows"]] = (torch.arange(N) % 2).float()[None, :]
    aux[15, 3, ix["en_alive"]] = 0.0                              # (the enemy of seat 3 is dead at the first sampled tick's frame)
    Bk = KN.batch(KL, U2, (0, 16), (20, 44), aux, ix)
    check("known: a sample every second tick, the brain's and the hands' columns, none with the enemy dead",
          Bk is not None and tuple(Bk[0].shape) == (4 * N - 1, 40) and tuple(Bk[1].shape) == (4 * N - 1, 2) and float(Bk[2].min()) == 1.0
          and torch.equal(Bk[0][0, 16:].float(), U2[1, 0, 20:44].float()))
    ko = torch.optim.Adam(km.parameters(), lr=1e-2)
    a0 = KN.learn(km, ko, KL, *Bk, lr=0.0, dev="cpu", gen=g)
    for _ in range(60):
        KN.learn(km, ko, KL, *Bk, lr=1e-2, dev="cpu", gen=g)
    a1 = KN.learn(km, ko, KL, *Bk, lr=0.0, dev="cpu", gen=g)
    r0, r1 = KN.record(a0, 1.0, KL), KN.record(a1, 1.0, KL)
    check("known: rate 0 scores without learning; the lesson lowers the Brier score; the record names its two outputs",
          r0["both"]["brier"][0] == 0.25 and r1["both"]["brier"][0] < 0.05 and r1["outs"] == ["knows", "heard"] and 0.4 < r1["share"][0] < 0.6,
          (r0["both"]["brier"], r1["both"]["brier"]))
    check("known: numpy as torch", np.allclose(KN.np_chance(KN.np_params(km.state_dict()), sb.numpy(), hh.numpy()), KN.chance(km, sb, hh).numpy(), atol=2e-3))
    # ---- "where does he respawn"
    SL = SP.layout(bel=16, mem=24, hid=16, smax=8, tick=8, back=24)
    sm = SP.make_module(SL)
    nsp = torch.tensor([4, 4, 0, 6, 4, 4])
    o0 = SP.odds(sm, sb, hh, nsp)
    check("spawn: a new readout is uniform over the map's own points, zero past them, zeros for a map with none",
          torch.allclose(o0[0, :4], torch.full((4,), 0.25)) and float(o0[0, 4:].max()) < 1e-6 and float(o0[2].sum()) == 0.0 and abs(float(o0[3, :6].sum()) - 1) < 1e-5)
    check("spawn: numpy as torch", np.allclose(SP.np_odds(SP.np_params(sm.state_dict()), sb.numpy(), hh.numpy(), nsp.numpy()), o0.numpy(), atol=2e-3))
    aux2 = aux.clone()
    done = torch.zeros(T, N)
    aux2[20:41, 1, ix["en_alive"]] = 0.0                           # seat 1's enemy dead on rows 20 .. 40, back on row 41 at point 2
    aux2[41, 1, ix["en_spawn"]] = 2.0
    aux2[10:31, 5, ix["en_alive"]] = 0.0                           # seat 5's: back on row 31 at point 1, but the round ended at frame 25
    aux2[31, 5, ix["en_spawn"]] = 1.0
    done[25, 5] = 1.0
    aux2[50:57, 7, ix["en_alive"]] = 0.0                           # seat 7's map has no spawn points known: no sample
    aux2[57, 7, ix["en_spawn"]] = 0.0
    nsp_s = np.array([4, 4, 4, 4, 4, 4, 4, 0, 4, 4])
    aux2[:, :, ix["x"]] = 100.0
    tabs = np.zeros((1, 8, 3), np.float32)
    tabs[0, :4, 0] = [0.0, 50.0, 900.0, 1000.0]                    # from x = 100: the far half is points 2 and 3
    Bs = SP.batch(SL, U2, (0, 16), (20, 44), aux2, done, ix, nsp_s, tab=np.zeros(N, np.int64))
    fr = sorted(set(int(round(float(x))) for x in Bs["pos"][:, 0])) if Bs is not None else None
    check("spawn: a sample at every tick he was dead at within the wait before the respawn's row; none across a round's end or without points",
          Bs is not None and len(Bs["y"]) == 3 and set(Bs["y"].tolist()) == {2} and tuple(Bs["X"].shape) == (3, 40) and set(Bs["nsp"].tolist()) == {4},
          None if Bs is None else (len(Bs["y"]), Bs["y"].tolist()))
    check("spawn: the samples are the ticks of frames 23, 31, 39 (seat 1)", Bs is not None and all(torch.equal(Bs["X"][k, :16].float(), U2[j, 1, :16].float())
                                                                                              for k, j in enumerate((4, 3, 2))))
    p1, p3, ins = SP.prior(Bs["pos"], Bs["y"], Bs["nsp"], Bs["tab"], tabs)
    check("spawn: the rule's prior: the truth is in the far half, a guess of one in two, of both in three", float(ins.min()) == 1.0 and torch.allclose(p1, torch.full((3,), 0.5))
          and torch.allclose(p3, torch.ones(3)))
    so = torch.optim.Adam(sm.parameters(), lr=1e-2)
    b0 = SP.learn(sm, so, SL, Bs, lr=0.0, dev="cpu", gen=g, tables=tabs)
    for _ in range(80):
        SP.learn(sm, so, SL, Bs, lr=1e-2, dev="cpu", gen=g)
    b1 = SP.learn(sm, so, SL, Bs, lr=0.0, dev="cpu", gen=g, tables=tabs)
    q0, q1 = SP.record(b0, 1.0, SL), SP.record(b1, 1.0, SL)
    check("spawn: scored before it is learnt from (the uniform guess at the start); the lesson finds the point; the record has the prior",
          abs(q0["ce"] - q0["ce_uniform"]) < 1e-4 and q0["uniform_top1"] == 0.25 and q1["top1"] == 1.0 and q1["ce"] < 0.2 and q1["prior_top1"] == 0.5
          and q1["truth_in_far_half"] == 1.0 and SP.record({}, 1.0, SL)["frames"] == 0, (q0, q1))
    # ---- how sure the brain is
    zone = np.zeros((3, 6), np.float32)
    zone[0, 0] = 1.0
    zone[1, :4] = 0.25
    ah = np.zeros((3, 20), np.float32)
    ah[1, 0], ah[1, 5], ah[1, 10] = 0.0, 0.3, 0.6                 # three places in a line, 300 units apart
    ah[2, 0], ah[2, 10] = 0.0, 9.0
    uz, us = H2.np_brain_unsure(zone, ah)
    check("unsure: one zone 0, every zone alike 1, no answer 0; the places ahead: their mean distance in thousands of units, at most 2",
          uz[0] == 0.0 and abs(uz[1] - 1.0) < 1e-6 and uz[2] == 0.0 and us[0] == 0.0 and abs(us[1] - 0.4) < 1e-6 and us[2] == 2.0, (uz, us))
    check("unsure: no readouts: zeros", not H2.np_brain_unsure(None, None, 4)[0].any() and len(H2.np_brain_unsure(None, None, 4)[1]) == 4)
    # ---- the rows' fill
    C, F, NW = 6, 12, 9
    fill = dict(unsure=9, known=10, spawn_odds=11)
    X = np.random.default_rng(1).uniform(-1, 1, (3, C, F)).astype(np.float32)
    X[:, :, 9:] = 0.0
    ok = np.ones((3, C), bool)
    ok[0, 5] = False
    csp = np.full((3, C), -1)
    csp[1, 4], csp[1, 5] = 2, 0
    spo = np.zeros((3, 8), np.float32)
    spo[1, 2], spo[1, 0] = 0.7, 0.1
    ms = np.ones((3, C, 8), np.float32)
    Xf = H2.np_ins_fill(X, ok, fill, known=np.array([0.2, 0.9, 0.5]), unsure=np.array([0.1, 0.2, 0.3]), spodds=spo, cspawn=csp, ms=ms).astype(np.float32)
    check("fill: the brain's answers in every offered row, not in a row the map does not offer; the spawn rows get their point's odds; the map sense after the row's own numbers",
          Xf.shape == (3, C, F + 8) and abs(Xf[1, 0, 10] - 0.9) < 1e-3 and Xf[0, 5, 10] == 0.0 and abs(Xf[2, 3, 9] - 0.3) < 1e-3 and abs(Xf[1, 4, 11] - 0.7) < 1e-3
          and abs(Xf[1, 5, 11] - 0.1) < 1e-3 and Xf[1, 0, 11] == 0.0 and Xf[0, 5, F:].sum() == 0.0 and Xf[0, 0, F:].sum() == 8.0 and np.allclose(Xf[:, :, :9], X[:, :, :9], atol=1e-3))
    check("fill: nothing given: the rows as they came", np.allclose(H2.np_ins_fill(X, ok, fill).astype(np.float32), X, atol=1e-3))
    # ---- the layout with the map sense and the brain's questions; the head's input
    L0 = H2.layout(obs=list(range(20)))
    Lm = H2.add_ins(L0, F, NW, C, quiet=1, ms=1, bq=1)
    I = Lm["ins"]
    check("layout: a row is the simulator's numbers and the map sense's eight; the head's input has the brain's three numbers",
          I["xf"] == F + 8 and I["fx"] == F and I["ms"] == 8 and I["bq"] == 3 and Lm["widths"]["ins"] == H2.ins_u_width(F + 8, 3)
          and H2.add_ins(L0, F, NW, C)["ins"]["xf"] == F and H2.add_ins(L0, F, NW, C)["widths"]["ins"] == H2.ins_u_width(F))
    ist = H2.InsState(4, I, "cpu")
    ist.bq = torch.tensor([[0.4, 0.5, 0.6]] * 4)
    ist.has = torch.tensor([True, False, False, False])
    ist.xh = torch.ones(4, F + 8)
    u = ist.u()
    check("head: a seat under no instruction still reads the brain's three numbers; the rest of the part is zeros for him",
          tuple(u.shape) == (4, H2.ins_u_width(F + 8, 3)) and torch.equal(u[1, -3:], torch.tensor([0.4, 0.5, 0.6])) and not u[1, :-3].any() and bool(u[0, :F].all()))
    check("head: a layout without them has no such state", H2.InsState(2, H2.add_ins(L0, F, NW, C)["ins"], "cpu").bq is None)
    held = np.zeros((2, H2.ins_held_width(I)), np.float32)
    held[:, -3:] = [0.1, 0.2, 0.3]
    check("held: the checks' and the plugin's numbers of a seat give the same part as the trainer's",
          H2.ins_held_width(I) == (F + 8) + 2 * H2.INS_A + H2.INS_SIG + 4 + 3 and H2.np_ins_held_u(I, held).shape == (2, H2.ins_u_width(F + 8, 3))
          and np.allclose(H2.np_ins_held_u(I, held)[:, -3:], [0.1, 0.2, 0.3]))
    # ---- the map sense at the rows' places
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "data", "maps"))
    Pm = fake_table(MS.table_path(d, "mapa"))
    Tm, _ = MS.load_tables(d, ["mapa"])
    Lms = MS.layout(Tm, hid=16)
    mm = MS.make_module(Lms)
    with torch.no_grad():
        mm.mlp[4].weight.normal_(0, 0.1, generator=g)
        mm.corr.weight.normal_(0, 0.1, generator=g)
    Pr = np.zeros((3, C, 3), np.float32)
    Pr[:, :] = Pm[:C][None]
    pk = np.ones((3, C), bool)
    pk[0, 0] = False
    en, en_ok = np.tile(Pm[10], (3, 1)), np.array([True, True, False])
    args = (Lms, Tm, np.array(["mapa", "mapb", "mapa"]), Pr, pk, en, en_ok, np.array([0, 1, 2]), np.array([2, 2, 2]))
    r_t = MS.rows_at(MS.torch_fwd(mm, "cpu"), *args)
    r_n = MS.rows_at(lambda x, row: MS.np_forward(MS.np_params(mm.state_dict()), x, row), *args)
    check("map sense at a row's place: eight numbers a row; zeros for a row without a place, a seat without a believed place, a map without a table; numpy as torch",
          r_t.shape == (3, C, 8) and not r_t[0, 0].any() and r_t[0, 1].any() and not r_t[1].any() and not r_t[2].any() and np.allclose(r_t, r_n, atol=1e-5))
    # ---- the shared reading (the checks' player, the plugin)
    APL = AP.layout(bel=16, mem=24, head=256, xf=F + 8, quiet=1)
    apP = AP.np_params(AP.make_module(APL).state_dict())
    Wi = H2.np_ins_params(H2.make_module(Lm).state_dict())
    m_ = 6
    Xr = np.random.default_rng(2).uniform(-1, 1, (m_, C, F + 8)).astype(np.float32)
    okr = np.zeros((m_, C), bool)
    okr[:, 1:4] = True
    wok = np.zeros((m_, NW), bool)
    wok[:, [0, 2]] = True
    sg = np.zeros((m_, H2.INS_SIG), np.float32)
    dr, frc = np.array([0, 1, 0, 0, 0, 0], bool), np.array([0, 0, 1, 0, 0, 0], bool)
    cur = np.array([-1, -1, -1, 2, 2, -1])
    st = np.zeros((m_, H2.ins_held_width(I)), np.float32)
    o_i = (F + 8) + 2 * H2.INS_A + H2.INS_SIG
    st[3, o_i + 2] = st[3, o_i + 3] = 1.0                          # seat 3: on a row of his own, the keep choice says keep (no longer read)
    st[4, o_i + 2] = 1.0                                           # seat 4: on a row, his coin off
    redo = np.array([1, 1, 1, 0, 0, 1], bool)
    bq = np.full((m_, 3), 0.25, np.float32)
    st2, (c, w, who, q) = H2.np_ins_read(I, Wi, APL, apP, True, 1.0, C - 1, 8, st, np.zeros((m_, 256), np.float32), np.zeros((m_, 296), np.float32),
                                          Xr, okr, wok, sg, dr, cur, frc, redo, np.random.default_rng(3), bq)
    check("reading: a free seat picks an offered row and a usable weapon; a drill's and a forced seat pick nothing; a seat on a row of his own draws anew at this tick whatever the keep choice says (2.1a: every 0.2 s); a seat whose coin is off is cleared",
          1 <= c[0] <= 3 and w[0] in (0, 2) and who[0] and c[1] == -1 and not who[1] and c[2] == -1 and not who[2] and 1 <= c[3] <= 3 and who[3]
          and c[4] == -1 and who[4] and st2[4, o_i + 2] == 0.0 and st2[3, o_i + 2] == 1.0 and st2[0, o_i + 2] == 1.0 and q.max() == 0, (c, w, who))
    check("reading: the held numbers keep their layout and the brain's three numbers", st2.shape == st.shape and np.allclose(st2[:, -3:], 0.25)
          and np.allclose(st2[0, :F + 8], Xr[0, c[0]]) and st2[0, o_i] == w[0])
    # ---- the simulator's worker
    class Env:
        n = 4
        spawns = np.arange(15, dtype=np.float32).reshape(5, 3)
        weapon = np.array([0, 1, 2, 6])
        ins_cspawn = np.full((4, C), -1)
        ins_cp = np.ones((4, C, 3), np.float32)
        ins_cpk = np.ones((4, C), bool)
        ins_drill = np.zeros(4, bool)
        ins_cur = np.full(4, -1)
        force_instr = np.full((4, 2), -1)

        def instr_feat(self):
            return np.zeros((4, C, F), np.float32), np.ones((4, C), bool), np.ones((4, NW), bool)

        def instr_state(self):
            return np.zeros((4, H2.INS_SIG), np.float32)
    wf = BR.worker_feat(Env())
    sp_, k_ = BR.worker_spawns(Env(), 8)
    check("worker: the reply has the rows' spawn points, places, the weapon in hand and the map's spawn points' count; the spawn points padded",
          len(wf) == 13 and wf[7].shape == (4, C) and wf[8].shape == (4, C, 3) and wf[9].shape == (4, C) and wf[10].tolist() == [0, 1, 2, 6]
          and wf[11].tolist() == [5] * 4 and sp_.shape == (8, 3) and k_ == 5 and np.allclose(sp_[:5], Env.spawns) and not sp_[5:].any())
    ixs = tuple(np.asarray(v) for v in wf)
    Xp, bqp = H2.np_ins_prep(ixs, fill, dict(I, xf=F + 8, fx=F), np.zeros((4, 16), np.float32), np.zeros((4, 24), np.float32), zone=np.full((4, 4), 0.25, np.float32),
                             knP=KN.np_params(KN.make_module(KL).state_dict()), spP=None, ms=None)
    check("prep: the worker's reply through the fill: a new 'known' readout writes a half, the zones' spread 1, the map sense's place kept at zero without a table",
          Xp.shape == (4, C, F + 8) and np.allclose(Xp[:, :, 10], 0.5) and np.allclose(Xp[:, :, 9], 1.0) and not Xp[:, :, F:].any() and np.allclose(bqp[:, 0], 0.0)
          and np.allclose(bqp[:, 1], 1.0))
    # ---- off, live
    src = open(os.path.join(ROOT, "sim", "train_duel_rnn.py"), encoding="utf-8").read().replace("\r\n", "\n")
    for flag in ('"--known-odds", type=float, default=0.0', '"--spawn-odds", type=float, default=0.0', '"--ins-ms", type=float, default=0.0'):
        check("off: the default of {} is off".format(flag.split(",")[0]), flag in src)
    check("off: the two readouts are made only under their flags; the spawn points are asked for only with --spawn-odds",
          "    if KN_ON:\n        assert H2 and BEL and TRK_ON" in src and "    if SPW_ON:\n        assert H2 and BEL and TRK_ON" in src
          and "        if SPW_ON and SPW_TAB[0] is None:" in src)
    T_ = importlib.import_module("train_duel_rnn")

    class E0:
        LIVE_VARS = ()

        @staticmethod
        def live_values(get):
            return {}
    pl = os.path.join(tempfile.mkdtemp(), "live.json")
    json.dump(dict(KNOWN_W=0.5, SPAWN_W=2.0), open(pl, "w"))
    v, tv, why = T_.live_read(pl, E0, {}, {})
    check("live: KNOWN_W and SPAWN_W are the trainer's names and are accepted", all(k in T_.LIVE_TRAINER for k in ("KNOWN_W", "SPAWN_W")) and why is None
          and tv["KNOWN_W"] == 0.5 and tv["SPAWN_W"] == 2.0, why)
    for bad in (dict(KNOWN_W=-1.0), dict(SPAWN_W=101.0)):
        json.dump(bad, open(pl, "w"))
        check("live: {} is refused".format(bad), T_.live_read(pl, E0, {}, {})[2] is not None)
    for mod_ in ("knownodds", "spawnodds", "mapsense", "appraise", "head2"):
        top = open(os.path.join(ROOT, "sim", mod_ + ".py"), encoding="utf-8").read().replace("\r\n", "\n")
        check("server: sim/{}.py imports no torch at its top (a game server's plugin reads it)".format(mod_),
              "\nimport torch" not in top and "\nimport control" not in top and "\nimport fightodds" not in top)


# ------------------------------------------------------------------------- 2.1: the instruction's choice INSIDE the head (2026-11-11)
def test_inside():
    """the owner, 2026-11-11: "the point is that the head learns how to make decisions". The scorer's layers are the head's; the
    learning step recomputes the play's log-probabilities from the re-run head with the same functions (1.7c's lesson); the terms'
    gradient reaches the head's memory"""
    import head2 as H2
    C, F, NW, NONE = 10, 12, 9, 8
    L0 = H2.layout(obs=list(range(20)))
    L = H2.add_ins(L0, F, NW, C, hid=32, quiet=1)
    m = H2.make_module(L)
    names = [n_ for n_, _ in m.named_parameters()]
    ins_n = [n_ for n_ in names if n_.startswith("ins_")]
    check("inside: the scorer's layers are layers of the head's module (8 layers with quiet and the win-chance value), its share a buffer of the head",
          len(ins_n) == 18 and len(H2.ins_params(m)) == 18 and "ins_vv.weight" in ins_n and "ins_g" in m.state_dict() and H2.has_ins_layers(m) and H2.has_quiet(m)
          and not H2.has_ins_layers(H2.make_module(L0)))
    old = H2.make_module({k_: v_ for k_, v_ in L.items() if k_ != "ins"})    # (the same layout without the scorer: the layers are made after every older draw)
    check("inside: the scorer's layers are made after every older draw: the rest of the head is the head without them, to the bit",
          [n_ for n_, _ in old.named_parameters()] == [n_ for n_ in names if not n_.startswith("ins_")]
          and all(torch.equal(a_, b_) for (na_, a_), (nb_, b_) in zip(old.named_parameters(), [(n_, p_) for n_, p_ in m.named_parameters() if not n_.startswith("ins_")])))
    g = torch.Generator().manual_seed(11)
    live0 = torch.ones(3, dtype=torch.bool)
    ok0 = torch.ones(3, C, dtype=torch.bool)
    lr0 = H2.ins_row_logp(m, torch.randn(3, 256, generator=g), torch.randn(3, C, F, generator=g), torch.randn(3, C, H2.INS_A, generator=g), ok0, live0)
    lw0, qz0 = H2.ins_wq_logp(m, torch.randn(3, 256, generator=g), torch.randn(3, F, generator=g), torch.ones(3, NW, dtype=torch.bool), live0)
    check("inside: at the start every offered row and every usable weapon is alike, quiet all but never asked (zero effect)",
          float((lr0.exp() - 1.0 / C).abs().max()) < 1e-6 and float((lw0.exp() - 1.0 / NW).abs().max()) < 1e-6 and float(torch.sigmoid(qz0).max()) < 0.01)
    with torch.no_grad():
        for p_ in H2.ins_params(m):
            p_.copy_(torch.randn(p_.shape, generator=g) * 0.4)
    # ---- a made-up rollout: the head ticks every K frames; a reading on the frame after a tick draws from the ONE definition
    K, J, B = int(L["every"]), 5, 6
    T = J * K
    U = (torch.randn(J, B, H2.u_width(L), generator=g) * 0.5).half().float()
    dn = torch.ones(T, B)
    dn[11, 1] = 0.0                                          # seat 1's round ends at frame 11: his head starts again
    X = (torch.randn(J, B, C, F, generator=g)).half().float()
    A = (torch.randn(J, B, C, H2.INS_A, generator=g) * 0.3).half().float()
    ok = torch.rand(J, B, C, generator=g) < 0.6
    ok[:, :, NONE] = True
    ok[:, 3] = False
    ok[:, 3, NONE] = True                                    # seat 3: the row "none" alone is offered
    ok[:, 4] = False                                         # seat 4: no row offered (not live)
    wok = torch.rand(J, B, NW, generator=g) < 0.6
    wok[:, :, 8] = True
    wok[:, 5] = False                                        # seat 5: no usable weapon (not live)
    drill = torch.zeros(J, B, dtype=torch.bool)
    drill[:, 2] = True                                       # seat 2: in a drill
    forced = torch.zeros(J, B, dtype=torch.bool)
    forced[:2, 0] = True                                     # seat 0: a frozen moment's hold at the first two readings
    st = H2.State(B, L, "cpu")
    s0, v0 = st.snap()
    c_p, w_p, q_p, lp_p, xw = tuple(torch.zeros(J, B, dtype=torch.long) for _ in range(3)) + (torch.zeros(J, B), torch.zeros(J, B, F))
    gen = torch.Generator().manual_seed(12)
    ar = torch.arange(B)
    with torch.no_grad():
        for t in range(T):
            if t % K == 0:                                   # the reading: the state this frame's outputs read (before its tick)
                j = t // K
                live = H2.ins_live(ok[j], wok[j])
                lr = H2.ins_row_logp(m, st.s, X[j], A[j], ok[j], live)
                c_p[j] = torch.multinomial(lr.exp(), 1, generator=gen).squeeze(1)
                xw[j] = X[j][ar, c_p[j]]
                lw, qz = H2.ins_wq_logp(m, st.s, xw[j], wok[j], live)
                w_p[j] = torch.multinomial(lw.exp(), 1, generator=gen).squeeze(1)
                q_p[j] = (torch.rand(B, generator=gen) < torch.sigmoid(qz)).long()
                lp_p[j] = H2.ins_joint_logp(lr, lw, qz, c_p[j], w_p[j], q_p[j])
            if (t + 1) % K == 0:
                st.tick(m, U[t // K])
            st.reset(1.0 - dn[t])
    live_all = H2.ins_live(ok, wok)
    check("inside (play): a drawn row is an offered one and a drawn weapon a usable one, wherever the seat is live",
          bool(ok.gather(-1, c_p[..., None]).squeeze(-1)[live_all].all()) and bool(wok.gather(-1, w_p[..., None]).squeeze(-1)[live_all].all())
          and bool((c_p[:, 3] == NONE).all()))
    own = live_all & ~drill & ~forced
    tq = H2.ins_target(torch.randn(J, B, C, generator=g), ok, 0.3)
    tw = H2.ins_target(torch.randn(J, B, NW, generator=g), wok, 0.3)
    Bt = dict(X=X, A=A, ok=ok, wok=wok, xw=xw, c=c_p, w=w_p, q=q_p, lp=lp_p, own=own, adv=torch.randn(J, B, generator=g), tq=tq, tm=own, tw=tw,
              twm=own & wok.any(-1), tqq=torch.full((J, B), 0.3), em=own)
    # ---- the learning step: the head re-run over the sequence, the kept readings scored again from the re-run state
    ho = H2.seq(m, L, U, dn, s0, v0)
    s_re = ho["s_held"][torch.arange(J) * K]
    loss0, o0 = H2.ins_loss(m, s_re, Bt, 0.0, 0.0, 0.0)
    d_lp = float((o0["lp"] - lp_p).abs().max())
    check("inside (1.7c's lesson): with unchanged weights the learning step's log-probability of EVERY kept reading is the stored one: "
          "rows, weapon and quiet; masked rows, the row 'none' alone, a seat with nothing offered, a drill's, a forced one's (ratio 1, KL 0)",
          d_lp < 2e-5 and abs(float((lp_p - o0["lp"])[own].mean())) < 1e-6 and not loss0.requires_grad, d_lp)
    lr_all = H2.ins_row_logp(m, s_re, X, A, ok, live_all)
    check("inside: a seat that is not live reads every row alike and is never his own; a masked row has no chance",
          float((lr_all[:, 4].exp() - 1.0 / C).abs().max()) < 1e-6 and not bool(own[:, 4].any()) and not bool(own[:, 5].any())
          and float(lr_all.exp()[~ok & live_all[..., None].expand_as(ok)].max()) == 0.0)
    Wn = H2.np_ins_params(m.state_dict())
    Wm = H2.np_ins_params({"head2." + k_: v_ for k_, v_ in m.state_dict().items()})
    sn, j0 = s_re[1].detach().numpy(), 1
    lr_n = H2.np_ins_row_logp(Wn, sn, X[j0].numpy(), A[j0].numpy(), ok[j0].numpy(), live_all[j0].numpy())
    lw_n, qz_n = H2.np_ins_wq_logp(Wn, sn, xw[j0].numpy(), wok[j0].numpy(), live_all[j0].numpy())
    lw_t, qz_t = H2.ins_wq_logp(m, s_re[1], xw[j0], wok[j0], live_all[j0])
    okn = ok[j0].numpy() | ~live_all[j0].numpy()[:, None]
    wkn = wok[j0].numpy() | ~live_all[j0].numpy()[:, None]
    check("inside: the checks' player's and the plugin's numpy definition gives the trainer's log-probabilities; the weights are read "
          "from the head's or the whole network's names alike",
          float(np.abs(lr_n - lr_all[j0].detach().numpy())[okn].max()) < 1e-4 and float(np.abs(lw_n - lw_t.detach().numpy())[wkn].max()) < 1e-4
          and float(np.abs(qz_n - qz_t.detach().numpy()).max()) < 1e-4 and sorted(Wn) == sorted(Wm) and all(np.array_equal(Wn[k_], Wm[k_]) for k_ in Wn)
          and "is_.weight" in Wn and "qv.bias" in Wn and "ins_g" in Wn)
    # ---- a drill's and a forced seat's readings contribute nothing
    only = drill | forced | ~live_all
    Bn = dict(Bt, own=own & only, tm=own & only, twm=own & only, em=own & only)
    ln, _ = H2.ins_loss(m, s_re, Bn, 1.0, 1.0, 0.1)
    check("inside: readings that are a drill's, a forced branch's or not live put nothing into the head's loss (no gradient at all)",
          not ln.requires_grad and float(ln) == 0.0 and not bool((own & only).any()))
    # ---- the terms' gradient reaches the head's memory and its input layer
    o_ins = H2._offs(L)["ins"]
    for nm_, tw_, pw_, ew_ in (("the lesson toward the appraisals' order", 1.0, 0.0, 0.0), ("the game's pay on his own readings", 0.0, 1.0, 0.0),
                               ("the entropy bonus", 0.0, 0.0, 0.1)):
        m.zero_grad(set_to_none=True)
        ho = H2.seq(m, L, U, dn, s0, v0)
        l_, _ = H2.ins_loss(m, ho["s_held"][torch.arange(J) * K], Bt, tw_, pw_, ew_)
        l_.backward()
        check("inside: {}: its gradient reaches the head's memory (the GRU), the head's input layer (the part 'ins' too) and the scorer".format(nm_),
              float(m.gru.weight_hh.grad.norm()) > 0 and float(m.inp.weight.grad.norm()) > 0 and float(m.inp.weight.grad[:, o_ins[0]:o_ins[1]].abs().sum()) > 0
              and float(m.ins_is.weight.grad.norm()) > 0, (float(m.gru.weight_hh.grad.norm()), float(m.ins_iv.weight.grad.norm())))
    m.zero_grad(set_to_none=True)
    ho = H2.seq(m, L, U, dn, s0, v0)
    lz, _ = H2.ins_loss(m, ho["s_held"][torch.arange(J) * K], Bt, 0.0, 0.0, 0.0)
    check("inside: with the three weights at 0 nothing reaches the head (the loss has no gradient)", not lz.requires_grad and m.gru.weight_hh.grad is None)
    w_gru = m.gru.weight_hh.detach().clone()
    opt = torch.optim.Adam(m.parameters(), lr=1e-3)
    ho = H2.seq(m, L, U, dn, s0, v0)
    l_, _ = H2.ins_loss(m, ho["s_held"][torch.arange(J) * K], Bt, 1.0, 0.5, 0.0)
    opt.zero_grad(set_to_none=True)
    l_.backward()
    opt.step()
    check("inside: a step of the instruction's terms changes the head's GRU weights", not torch.equal(w_gru, m.gru.weight_hh.detach()))
    # ---- the decoupled reference and its weights; the second clip
    Bd = dict(Bt, ref=lp_p + 0.1, isw=torch.full((J, B), 0.5))
    ho = H2.seq(m, L, U, dn, s0, v0)
    s2 = ho["s_held"][torch.arange(J) * K]
    la, oa = H2.ins_loss(m, s2, Bt, 0.0, 1.0, 0.0)
    lb, ob = H2.ins_loss(m, s2, Bd, 0.0, 1.0, 0.0)
    check("inside: the pay's term clips around the given reference (decoupled PPO: the learner before the update) with its weights",
          abs(oa["pg"] - ob["pg"]) > 1e-6 and la.requires_grad and lb.requires_grad)
    # ---- the start's converter: the layers go into the network's own weights, at zero effect
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import head21_init as HI
    ck = dict(head2=L0, model={"head2." + k_: v_.clone() for k_, v_ in H2.make_module(L0).state_dict().items()})
    w_old = ck["model"]["head2.inp.weight"].clone()
    L2, k = HI.widen_head(ck, dict(xf=F, nw=NW, c=C), 32, quiet=1, ms=1, bq=1)
    new = H2.make_module(L2)
    new.load_state_dict({k_[len("head2."):]: v_ for k_, v_ in ck["model"].items()})
    check("start: the converter puts the scorer's layers into the network's own weights (head2.ins_*), the last layers at zero, the "
          "share 0, the head's old input columns as they were and the new ones zero; a head of the new layout loads it whole",
          "head2.ins_iv.weight" in ck["model"] and not ck["model"]["head2.ins_iv.weight"].any() and not ck["model"]["head2.ins_wv.weight"].any()
          and float(ck["model"]["head2.ins_g"]) == 0.0 and float(ck["model"]["head2.ins_qv.bias"]) == H2.INS_Q0
          and torch.equal(ck["model"]["head2.inp.weight"][:, :w_old.shape[1]], w_old) and not ck["model"]["head2.inp.weight"][:, w_old.shape[1]:].any()
          and k == H2.ins_u_width(F + 8, 3) and int(ck["head2_ins_weights"]) == sum(int(p_.numel()) for p_ in H2.ins_params(new)))
    # ---- the trainer's wiring, read off its source
    src = open(os.path.join(ROOT, "sim", "train_duel_rnn.py"), encoding="utf-8").read().replace("\r\n", "\n")
    check("trainer: no scorer beside the network is left (no module, no Adam of its own, no lesson after the PPO epochs)",
          "INSM" not in src and "INS_OPT" not in src and "ins_learn(" not in src and "make_ins(" not in src)
    check("trainer: the rollout draws from the one definition on the network that plays, the learning step and the proximal pass score "
          "the kept readings again with it from the re-run head, and the terms are added to the head's loss",
          "head2_.ins_row_logp(net.head2, s_keep_" in src and "head2_.ins_joint_logp(lr_i, lw_i" in src
          and "head2_.ins_loss(pol.head2, ip_[1], ip_[0]" in src and "loss = loss + li_" in src and 'ho2["s_held"][K_["fr"]]' in src
          and "head2_.ins_loss(pol.head2, ipx_[1], ipx_[0], 0.0, 0.0, 0.0)" in src)
    check("trainer: the scorer's layers are out of the head's optimizer group and in a group 'ins' of their own, added by name on a "
          "resume and after the load for a save without it; a file without them (a league's) gets the network's own, its share 0",
          '"fsc.", "ins_"))]' in src and 'GROUP_NAMES.append("ins")' in src and 'fn_["ins"] = ins_group' in src
          and "    ins_group()                                              # (2.1)" in src and '"head2.ins_iv.weight" not in sd' in src)
    check("trainer: the checkpoint's entry 'ins' holds no weights (they are in the network's)", '"ins": dict(INS_CK or {}, seen=' in src)


# ------------------------------------------------- 2.1, third pass: the finish time, the wake, the pattern's moments, the head's pay
def test_cleanup():
    import importlib
    import json
    import tempfile
    import head2 as H2
    T = importlib.import_module("train_duel_rnn")
    import duel_env_ffa as E
    NW = E.NW
    # ---- the table
    t0 = E.fin_rate_parse("")
    check("finish: the table is weapons x three distance bands; unset: the placeholder; the lightning gun's far band is 0 (its reach)",
          t0.shape == (NW, 3) and np.array_equal(t0, E.FIN_RATE_DEFAULT) and t0[E.LG, 2] == 0.0 and E.FIN_BANDS == (400.0, 768.0))
    tr = np.random.default_rng(0).uniform(0, 120, (NW, 3)).round(2)
    check("finish: a table written as FIN_RATE's string is read back", np.allclose(E.fin_rate_parse(E.fin_rate_str(tr)), tr, atol=0.006))
    for bad in ("1,2,3", ";".join(["1,2"] * NW), ";".join(["1,2,x"] * NW), ";".join(["1,2,-3"] * NW), ";".join(["1,2,999"] * NW)):
        try:
            E.fin_rate_parse(bad)
            okb = False
        except ValueError:
            okb = True
        check("finish: FIN_RATE {!r} is refused".format(bad[:14]), okb)
    check("finish: FIN_RATE is a live name (a string), a play variable; the wake's drop a play variable",
          "FIN_RATE" in E.LIVE_VARS and "FIN_RATE" in E.LIVE_STR and "FIN_RATE" in E.PLAY_VARS and "INS_WAKE_DROP" in E.PLAY_VARS)
    p = os.path.join(tempfile.mkdtemp(), "live.json")
    json.dump(dict(FIN_RATE=E.fin_rate_str(tr), BRANCH_WPN_P=0.3), open(p, "w"))
    v, tv, why = T.live_read(p, E, {}, {})
    check("live: a measured table and the pattern's share are accepted", why is None and tv["BRANCH_WPN_P"] == 0.3 and np.allclose(E.live_values(v.get)["FIN_RATE"], tr, atol=0.006), why)
    for bad in (dict(FIN_RATE="1,2,3"), dict(BRANCH_WPN_P=1.5), dict(BRANCH_WPN_P=-0.1)):
        json.dump(bad, open(p, "w"))
        check("live: {} is refused".format(bad), T.live_read(p, E, {}, {})[2] is not None)
    check("finish: the sizes: 27 numbers a candidate row after the 37, 7 more hands' inputs (48), 8 change signals, the same in the head",
          E.INS_F == 37 + 3 * NW and E.INS_FIN0 == 37 and E.N_FIN == 7 and E.N_INS == 48 and E.INS_SIG == H2.INS_SIG == 8
          and E.INS_SIG_WAKE == H2.INS_SIG_WAKE == 6 and E.INS_FEAT[37:40] == ("fin_rl", "fin_hi_rl", "fire_rl"))

    # ---- the numbers, on a made-up seat pair (no simulator: the methods on a stub)
    class Stub:
        n = 4
        G = 2
        slot = np.arange(4) % 2

        def __init__(self):
            self.hp = np.array([100.0, 100.0, 0.0, 100.0], np.float32)       # seat 2 dead
            self.armor = np.zeros(4, np.float32)
            self.has = np.ones((4, NW), bool)
            self.ammo = np.full((4, NW), 50.0, np.float32)
            self.ammo[0, E.RL] = 0.0                                         # seat 0: no rockets
            self.has[0, E.RG] = False                                        # ... and no rail
            self.weapon = np.array([E.LG, E.RL, E.LG, E.MG])
            self.state = np.zeros((4, 12), np.float32)
            self.state[1, 0] = 500.0                                         # seats 0 and 1: 500 apart (the middle band)
            self.state[3, 0] = 2000.0                                        # seats 2 and 3: 2000 apart
            self.visible = np.array([1, 1, 0, 0], bool)
            self.es_h = np.full((4, 2), 80.0, np.float32)
            self.es_a = np.full((4, 2), 20.0, np.float32)
            self.es_vh = np.full((4, 2), 300.0, np.float32)
            self.es_va = np.full((4, 2), 100.0, np.float32)
            self.brain_life = None

        def _others_arr(self):
            return (np.arange(4) ^ 1)[:, None]

        def _slot(self, j):
            return j % 2

        def _ins_bel(self):
            return np.zeros((4, 3), np.float32), np.zeros(4, bool)
    D = E.DuelEnv
    old = (E.EN_STACK, E.BRAIN_READ, E.FIN_RATE)
    try:
        E.EN_STACK, E.BRAIN_READ, E.FIN_RATE = True, False, E.FIN_RATE_DEFAULT.copy()
        s = Stub()
        s._fin_belief = lambda: D._fin_belief(s)
        st, sd, ok, band = D._fin_belief(s)
        check("finish: the belief is the stack belief's (health and armor, its spread); the band from the enemy in view, the middle one for no belief of a place",
              np.allclose(st, 100.0) and np.allclose(sd, 20.0) and ok.all() and band.tolist() == [1, 1, 1, 1])
        fin, fhi, fire, fok = D._fin(s)
        r = float(E.FIN_RATE_DEFAULT[E.LG, 1])
        check("finish: seconds to finish = the believed stack over his rate at that distance (/ 5); the cautious one adds the spread",
              abs(fin[0, E.LG] - 100.0 / r / 5.0) < 1e-5 and abs(fhi[0, E.LG] - 120.0 / r / 5.0) < 1e-5 and fhi[0, E.LG] > fin[0, E.LG])
        check("finish: a weapon without ammunition or not owned: 2 (never) and no seconds of fire; a dead seat: zeros; the gauntlet's fire: 2",
              fin[0, E.RL] == 2.0 and fire[0, E.RL] == 0.0 and fin[0, E.RG] == 2.0 and fire[0, E.RG] == 0.0 and not fin[2].any() and not fire[2].any()
              and not fok[2] and fire[1, E.G] == 2.0)
        check("finish: seconds of fire = ammunition x refire time (/ 10)", abs(fire[1, E.LG] - 50 * 0.05 / 10.0) < 1e-6 and abs(fire[1, E.RL] - 2.0) < 1e-6)
        s.hp[1], s.armor[1] = 7.0, 150.0                                     # the enemy's TRUE stack changed: nothing may move
        f2 = D._fin(s)
        check("finish: nothing of it reads the enemy's true stack", all(np.array_equal(a_, b_) for a_, b_ in zip((fin, fhi, fire, fok), f2)))
        E.FIN_RATE = E.FIN_RATE_DEFAULT * 2.0
        check("finish: a table twice as fast halves the time", abs(D._fin(s)[0][0, E.LG] - fin[0, E.LG] / 2.0) < 1e-5)
        E.FIN_RATE = E.FIN_RATE_DEFAULT.copy()
        s.visible[:] = False
        s.state[1, 0] = 3000.0                                               # (unseen, no believed place: the middle band whatever the truth)
        check("finish: an enemy out of view is not placed by the truth", D._fin_belief(s)[3].tolist() == [1, 1, 1, 1])
        E.BRAIN_READ = True                                                  # a life on the brain: its bands
        s.brain_life = np.array([1, 0, 0, 0], bool)
        s.brain_ok = np.array([1, 1, 1, 1], bool)
        s.brain_band = np.tile(np.array([[1.0, 0.0, 0.0, 0.0]], np.float32), (4, 1))
        st, sd, ok, _ = D._fin_belief(s)
        check("finish: a life on the brain reads the brain's stack band (its middle, the spread of its odds); the other seat the stack belief",
              abs(st[0] - 37.5) < 1e-4 and sd[0] < 1e-3 and abs(st[1] - 100.0) < 1e-4)
        s.brain_band[0] = (0.5, 0.5, 0.0, 0.0)
        st, sd, ok, _ = D._fin_belief(s)
        check("finish: odds over two bands: the mean between them and a spread", abs(st[0] - 68.75) < 1e-3 and abs(sd[0] - 31.25) < 1e-3)
        s.brain_ok[0] = False
        st, sd, ok, _ = D._fin_belief(s)
        fin, _, _, fok = D._fin(s)
        check("finish: a life on the brain without an answer has no belief: every finish time 2, the mark 0", not ok[0] and not fok[0] and (fin[0] == 2.0).all())
    finally:
        E.EN_STACK, E.BRAIN_READ, E.FIN_RATE = old

    # ---- the wake
    sg = np.zeros((3, H2.INS_SIG), np.float32)
    sg[1, H2.INS_SIG_WAKE] = 1.0
    sg[2, 1] = 1.0
    check("wake: the one rule: done, failed or a wake ends a keep (numpy and torch alike)",
          H2.ins_end(sg).tolist() == [False, True, True] and H2.ins_end(torch.from_numpy(sg)).tolist() == [False, True, True])
    src = open(os.path.join(ROOT, "sim", "train_duel_rnn.py"), encoding="utf-8").read().replace("\r\n", "\n")
    check("wake: the trainer's rollout and the checks' player read that one rule",
          "end_i = head2_.ins_end(sg_)" in src and "end_ = ins_end(sg)" in open(os.path.join(ROOT, "sim", "head2.py"), encoding="utf-8").read())
    F, C, MSW = 12, 6, 8
    L = H2.layout(brain=16, hands=24)
    Lm = H2.add_ins(L, F, NW, C, hid=16, quiet=1, ms=1, bq=1)
    I = Lm["ins"]
    Wi = H2.np_ins_params(H2.make_module(Lm).state_dict())
    m_ = 2
    Xr = np.random.default_rng(2).uniform(-1, 1, (m_, C, F + MSW)).astype(np.float32)
    okr = np.zeros((m_, C), bool)
    okr[:, 1:4] = True
    wok = np.zeros((m_, NW), bool)
    wok[:, [0, 2]] = True
    o_i = (F + MSW) + 2 * H2.INS_A + H2.INS_SIG
    st = np.zeros((m_, H2.ins_held_width(I)), np.float32)
    st[:, o_i + 2] = st[:, o_i + 3] = 1.0                          # both on a row of their own
    sgk = np.zeros((m_, H2.INS_SIG), np.float32)
    sgk[1, H2.INS_SIG_WAKE] = 1.0                                  # seat 1: a wake
    S_ = int(Lm["size"])
    st2, (c, w, who, q) = H2.np_ins_read(I, Wi, None, None, False, 1.0, C - 1, 8, st, np.zeros((m_, S_), np.float32), np.zeros((m_, 16 + 24 + S_), np.float32),
                                          Xr, okr, wok, sgk, np.zeros(m_, bool), np.array([2, 2]), np.zeros(m_, bool), np.zeros(m_, bool), np.random.default_rng(3),
                                          np.zeros((m_, 3), np.float32))
    check("wake (2.1a: every tick a redraw): with or without a wake both seats draw anew, whatever the keep choice says", who[0] and 1 <= c[0] <= 3 and who[1] and 1 <= c[1] <= 3, (c, who))

    # ---- the pattern's moments in the plan
    rng = np.random.default_rng(0)
    row, ws = BR.weapon_only(rng, np.arange(8.0), np.ones(8, bool), np.array([1, 0, 1, 0, 0, 0, 1, 0, 0], bool), 3, 7, 4)
    check("pattern: one row (the one he is on), each weapon he can use, no other", row == 3 and sorted(ws) == [0, 2, 6])
    row, ws = BR.weapon_only(rng, np.arange(8.0), np.ones(8, bool), np.array([1, 0, 1, 0, 0, 0, 1, 0, 0], bool), 7, 7, 2)
    check("pattern: under 'none' the head's best instruction is taken, never 'none'; at most k weapons", row == 6 and len(ws) == 2 and set(ws) <= {0, 2, 6})
    check("pattern: one usable weapon, or no instruction offered: nothing to compare",
          BR.weapon_only(rng, np.arange(8.0), np.ones(8, bool), np.array([1, 0, 0, 0, 0, 0, 0, 0, 0], bool), 3, 7, 4) == (-1, [])
          and BR.weapon_only(rng, np.arange(8.0), np.arange(8) == 7, np.ones(9, bool), 3, 7, 4) == (-1, []))
    el = np.ones(40, bool)
    pa = BR.plan(np.random.default_rng(5), 40, el, 0.5, 4)
    pb = BR.plan(np.random.default_rng(5), 40, el, 0.5, 4, prefer=np.arange(40) < 10, prefer_p=0.0)
    check("pattern: a share of 0 leaves the plan's draws as they were", pa == pb)
    ch = set()
    pc = BR.plan(np.random.default_rng(5), 40, el, 0.5, 4, prefer=np.arange(40) < 10, prefer_p=1.0, chosen=ch)
    check("pattern: a share of 1 takes every source at a pattern's moment (while there are any); sources are not destinations",
          len(pc) == 5 and all(s_ < 10 for s_, _ in pc) and ch == {s_ for s_, _ in pc} and not ({s_ for s_, _ in pc} & {d_ for _, ds_ in pc for d_ in ds_}))

    class Pipe:
        def __init__(self):
            self.sent = []

        def send(self, x):
            self.sent.append(x)

        def recv(self):
            return True
    N, Cc = 32, 32
    sc = rng.normal(size=(N, Cc))
    ok = np.ones((N, Cc), bool)
    wb = rng.integers(0, 9, (N, Cc))
    wk = np.zeros((N, 9), bool)
    wk[:, [0, 1, 2]] = True
    pat = np.zeros(N, np.int8)
    pat[0:8:2] = 1                                                 # matches 0 to 3: just after a hit
    cur = np.full(N, 5)
    pipes = [Pipe()]
    bm = BR.start(np.random.default_rng(1), pipes, [0, N], [16], 2, 0.5, 2, 1, 40, sc, np.ones(N, bool), ok, wbest=wb, quiet_p=0.5,
                  wpn_p=1.0, pat=pat, wok=wk, cur=cur, none_row=30)
    wf = bm["wpn"]
    check("pattern: the weapon-only branches keep the row he is on, differ in the weapon alone, ask no quiet; their sources are the pattern's moments",
          wf.any() and (bm["tg"][wf] == 5).all() and set(bm["w"][wf].tolist()) <= {0, 1, 2} and (bm["q"][wf] == 0).all()
          and all(len(set(bm["w"][wf & (bm["dst_src"] == j)].tolist())) == int((wf & (bm["dst_src"] == j)).sum()) for j in range(len(bm["src"])))
          and all(pat[bm["src"][j]] == 1 for j in np.unique(bm["dst_src"][wf])) and (bm["pat"][np.unique(bm["dst_src"][wf])] == 1).all())
    job = [j for j in pipes[0].sent[0][1]["jobs"] if len(set(j[2])) == 1 and len(j[2]) > 1][0]
    check("pattern: the simulator's job carries the row once a branch and a weapon each", len(set(job[3])) == len(job[3]) and set(job[2]) == {5})
    p0, p1 = [Pipe()], [Pipe()]
    ba = BR.start(np.random.default_rng(1), p0, [0, N], [16], 2, 0.5, 2, 1, 40, sc, np.ones(N, bool), ok, wbest=wb)
    bb = BR.start(np.random.default_rng(1), p1, [0, N], [16], 2, 0.5, 2, 1, 40, sc, np.ones(N, bool), ok, wbest=wb, wpn_p=0.0, pat=pat, wok=wk, cur=cur, none_row=30)
    check("pattern: the share at 0: the plan, the jobs and the keys as before", p0[0].sent == p1[0].sent and set(ba) == set(bb) and "wpn" not in bb
          and all(np.array_equal(ba[k], bb[k]) for k in ba if isinstance(ba[k], np.ndarray)))
    B = len(bm["dst"])

    def oc(n):
        return dict(dealt=np.full(n, 50.0), taken=np.full(n, 20.0), he_dies=np.zeros(n), i_die=np.zeros(n), item=np.ones(n),
                    dv=np.linspace(0.0, 1.0, n), judge=np.zeros(n), cut=np.zeros(n, bool), frames=np.full(n, 320.0), got=np.zeros(n, np.int64))
    rec = BR.record(bm, oc(B), oc(len(bm["src"])), 0, 0.1, 0.5)
    check("pattern: the record counts the weapon-only branches, their kind and what each weapon brought",
          rec["wpn"]["branches"] == int(wf.sum()) and rec["wpn"]["after_hit"] >= 1 and sum(v_["n"] for v_ in rec["wpn"]["by_weapon"].values()) == int(wf.sum()))

    class Env:
        n = 4
        weapon = np.zeros(4, np.int64)

        def instr_feat(self):
            return np.zeros((4, C, F), np.float32), np.ones((4, C), bool), np.ones((4, NW), bool)

        def instr_state(self):
            return np.zeros((4, H2.INS_SIG), np.float32)

        def instr_pattern(self):
            return np.array([0, 1, 2, 0], np.int8)
    wfe = BR.worker_feat(Env())
    check("pattern: the worker's reply carries each seat's pattern mark as its thirteenth field", len(wfe) == 13 and wfe[12].tolist() == [0, 1, 2, 0])

    # ---- the head's pay: the win chance alone
    m = H2.make_module(Lm)
    check("head pay: the head has a value of the win-chance pay of its own (ins_vv), at zero, among the scorer's parameters (the optimizer's group 'ins')",
          hasattr(m, "ins_vv") and not m.ins_vv.weight.any() and not m.ins_vv.bias.any() and any(p_ is m.ins_vv.weight for p_ in H2.ins_params(m))
          and float(H2.value_w(m, torch.randn(3, S_), torch.randn(3, 24)).abs().max()) == 0.0)
    m0 = H2.make_module(H2.add_ins(L, F, NW, C, hid=16, quiet=1, ms=1, bq=1))
    check("head pay: the new layer is made last: every older layer of the head as it was drawn before",
          all(torch.equal(v_, m0.state_dict()[k_]) for k_, v_ in m.state_dict().items()))
    Tn, Nn = 400, 6
    g = torch.Generator().manual_seed(0)
    win = torch.randn(Tn, Nn, generator=g) * 0.01                  # the win chance's stream
    tab1 = torch.randn(Tn, Nn, generator=g) * 0.1                  # two pay tables' entries (damage, items by the point, table frags)
    tab2 = tab1 * 3.0 + 0.05
    done = (torch.rand(Tn, Nn, generator=g) < 0.005).float()
    vw = torch.randn(Tn + 1, Nn, generator=g) * 0.05               # the head's value of the win chance
    vh1, vh2 = torch.randn(Tn + 1, Nn, generator=g), torch.randn(Tn + 1, Nn, generator=g)
    aw1, rw1 = H2.gae(win, vw, done, 0.9998, 0.95)
    aw2, rw2 = H2.gae(win, vw, done, 0.9998, 0.95)
    ah1, _ = H2.gae(tab1 + win, vh1, done, 0.9998, 0.95)
    ah2, _ = H2.gae(tab2 + win, vh2, done, 0.9998, 0.95)
    check("head pay: another pay table: the head's advantage and returns from the win chance do not move; the hands' whole-pay advantage does",
          torch.equal(aw1, aw2) and torch.equal(rw1, rw2) and not torch.allclose(ah1, ah2))
    aux = torch.zeros(Tn + 1, Nn, 8)
    ix = {k: i for i, k in enumerate(("dmg_dealt", "dmg_taken", "frag", "fragged", "died", "mega_take", "red_take", "en_target"))}
    seats = np.array([0, 2, 4])
    kw = dict(aux=aux, done=done, ix=ix, gamma=0.9998, hold=40, win=320)
    o1 = BR.outcomes(seats, hr=win, vh=vw, **kw)
    f1 = BR.outcomes(seats, hr=tab1 + win, vh=vh1, **kw)
    f2 = BR.outcomes(seats, hr=tab2 + win, vh=vh2, **kw)
    o2 = BR.outcomes(seats, hr=win, vh=vw, **kw)
    check("head pay: a branch's dv from the win chance is the same under either pay table; from the whole pay it is not",
          np.array_equal(o1["dv"], o2["dv"]) and not np.allclose(f1["dv"], f2["dv"]))
    rec_l = BR.long_new(seats, torch.zeros(3, 4), torch.zeros(3, 4), vw)
    going, fin_ = BR.long_step([rec_l], win, done, vw, 0.9998, 300, Tn)
    rec_m = BR.long_new(seats, torch.zeros(3, 4), torch.zeros(3, 4), vw)
    _, fin_m = BR.long_step([rec_m], win, done, vw, 0.9998, 300, Tn)
    check("head pay: the long window's dv is made of the stream and the value it is given (the win chance's)", len(fin_) == 1 and np.array_equal(fin_[0]["dv"], fin_m[0]["dv"]))
    rk = BR.rank_differs(np.array([0, 0, 0, 1, 1, 2]), np.array([0.1, 0.5, 0.2, 0.3, 0.1, 0.9]), np.array([0.6, 0.5, 0.2, 0.3, 0.1, 0.0]))
    check("head pay: the readout: over the moments with two branches or more, how often the best by win chance is another than the best by the whole pay",
          rk == dict(moments=2, differ=1, share=0.5))
    for needle, what in (('kw_ = dict(kw_, hr=R["b_hw"], vh=R["b_vw"])', "the branches' dv"), ("hr_l, vh_l = R[\"b_hw\"], R[\"b_vw\"]", "the long window"),
                         ("ADV_W, RET_W = head2_.gae(B_HW, B_VW", "the instruction's advantage"),
                         ("ins_piece(ho2_, chunk, ADV_W if ADV_W is not None else ADV_H)", "the pay on his instruction choices"),
                         ("hr_c, vh_c = (B_HW, B_VW) if (HW_INS and B_VW is not None) else (B_HR, B_VH)", "the forecast's calibration"),
                         ("b_hw[t] = torch.from_numpy(np.ascontiguousarray(aux[:, HW_IX], dtype=np.float32)).to(dev) * HW_G", "the stream: win_raw alone"),
                         ('"--ins-pay-win", type=float, default=0.0', "off by default"), ('"--branch-wpn-p", type=float, default=0.0', "the pattern off by default")):
        check("head pay: the trainer's wiring: {}".format(what), needle in src)
    check("head pay: the simulator's label is a switch of its own, off by default, and names no pay table entry",
          hasattr(E, "HEAD_PAY_TRUTH") and (("win_raw" in E.AUX_COLS) == bool(E.HEAD_PAY_TRUTH)))
    # ---- the measuring tool and the readout, on a made-up record
    import fin_rate as FR
    import goal_readout as GR
    Tq = 400
    posq = np.zeros((Tq, 2, 3), np.float16)
    posq[:, 1, 0] = 500.0                                          # 500 apart: the middle band
    posq[200:, 1, 0] = 1000.0                                      # ... then 1000: the far one
    fireq = np.zeros((Tq, 2), bool)
    fireq[0:200:2, 0] = True                                       # seat 0: 100 lightning shots in the middle band (5 s of trigger)
    wfq = np.full((Tq, 2), E.LG, np.int8)
    fireq[200:400:40, 0] = True                                    # ... 5 rail shots in the far band (7.5 s)
    wfq[200:, 0] = E.RG
    dwq = np.zeros((Tq, 2, NW), np.float16)
    dwq[0:200:5, 0, E.LG] = 6.0                                    # 40 hits of 6: 240 damage -> 48 a second
    dwq[240, 0, E.RG] = 80.0                                       # one rail hit: 80 damage in 7.5 s
    askq = np.full((Tq, 2), -1, np.int8)
    askq[0:100, 0] = E.RL                                          # the first 50 lightning shots under an instruction asking for rockets
    askq[200:, 0] = E.RG                                           # the rail shots under one asking for the rail
    fq = os.path.join(tempfile.mkdtemp(), "rec_bloodrun_0.npz")
    np.savez(fq, pos=posq, alive=np.ones((Tq, 2), bool), weapon=wfq, vis=np.ones((Tq, 2), bool), hp=np.full((Tq, 2), 100, np.float16),
             ar=np.zeros((Tq, 2), np.float16), dealt=dwq.sum(2).astype(np.float32), side=np.array([0, 1], np.int8), fire=fireq, wfire=wfq,
             dealt_w=dwq, askw=askq, dt=0.025)
    secs, dmg = np.zeros((NW, 3)), np.zeros((NW, 3))
    FR.add(np.load(fq), 0, np.asarray(E.W_REFIRE, np.float64), E.FIN_BANDS, secs, dmg)
    rate, okm = FR.table(secs, dmg, E.FIN_RATE_DEFAULT, 5.0)
    check("finish: the measuring tool: damage by the weapon that did it over the trigger's seconds, by the band; a cell with too little trigger keeps the placeholder",
          abs(secs[E.LG, 1] - 5.0) < 1e-6 and abs(dmg[E.LG, 1] - 240.0) < 1e-3 and abs(rate[E.LG, 1] - 48.0) < 1e-3 and abs(secs[E.RG, 2] - 7.5) < 1e-6
          and abs(rate[E.RG, 2] - 80.0 / 7.5) < 1e-3 and okm[E.LG, 1] and okm[E.RG, 2] and not okm[E.RL, 0] and rate[E.RL, 0] == E.FIN_RATE_DEFAULT[E.RL, 0]
          and np.allclose(E.fin_rate_parse(E.fin_rate_str(rate)), rate, atol=0.006))
    Aq = GR.new_acc()
    GR.add(Aq, GR.rows(np.load(fq), 0))
    sq = GR.summary(Aq)["asked_other"]
    check("readout: of his shots under an instruction's weapon, the share fired with another, by the weapon asked for",
          sq is not None and sq["shots"] == 55 and abs(sq["share"] - 50 / 55) < 1e-3 and sq["by_asked"] == {"rockets": 1.0, "rail": 0.0})
    import inputs21 as I21
    check("inputs: the new columns' statistics by design (a finish time, seconds of fire, the belief's mark)",
          I21.design("finish, weapon in hand: seconds to finish him", "seconds / 5, capped at 2") == (1.0, 0.5)
          and I21.design("finish, weapon asked for: seconds of fire he has", "x") == (0.5, 0.25)
          and I21.design("finish: he has a belief of the enemy's stack", "0 or 1") == (0.9, 0.09) and I21.design("quiet asked", "0 or 1") == I21.FLAG)


def test_bind():
    """2.1a: the binding weapon (INS_BIND), the one mask, the two names made live"""
    import duel_env_ffa as E
    import head2 as H2
    sys.path.insert(0, os.path.join(ROOT, "plugins"))
    import netpass as NP
    NW, RL, RG, LG, G = E.NW, E.RL, E.RG, E.LG, E.G
    n = 8
    has = np.zeros((n, NW), bool)
    ammo = np.zeros((n, NW), np.float32)
    has[:, RL] = has[:, LG] = has[:, G] = True
    ammo[:, RL], ammo[:, LG] = 10, 50
    ammo[3, RL] = 0                                           # seat 3: rockets owned, none left
    v = np.array([1, 1, 0, 1, 1, 1, 1, 1])
    w = np.array([RL, LG, RL, RL, RG, -1, G, RL])            # 0 in hand; 1 not in hand; 2 no instruction; 3 no ammo; 4 not owned; 5 none asked; 6 gauntlet; 7 dead
    hand = np.array([RL, RL, LG, LG, RL, RL, RL, LG])
    alive = np.array([1, 1, 1, 1, 1, 1, 1, 0], bool)
    b = E.ins_bind_act(v, w, has, ammo, hand, alive)
    check("bind: the asked weapon in his hand = keep, another he owns with ammunition = its key, the gauntlet needs none",
          b[0] == 0 and b[1] == 1 + LG and b[6] == 1 + G, b)
    check("bind: no instruction, no weapon asked, not owned, no ammunition, dead: his own choice stands",
          (b[[2, 3, 4, 5, 7]] == -1).all(), b)
    check("bind: a play variable, off by default; the switch cost and 'a held weapon is choosable' are live names",
          "INS_BIND" in E.PLAY_VARS and E.INS_BIND is False and "INTENT_SWITCH" in E.LIVE_VARS and "WEAPON_OWN" in E.LIVE_VARS)
    lv = E.live_values({}.get)
    lz = E.live_values({"INTENT_SWITCH": "0", "WEAPON_OWN": "1"}.get)
    bad = False
    try:
        E.live_values({"INTENT_SWITCH": "0.5"}.get)
    except ValueError:
        bad = True
    check("live: unset = the import's values (0.02, off); 0 and 1 read; a cost out of range refused",
          lv["INTENT_SWITCH"] == 0.02 and lv["WEAPON_OWN"] is False and lz["INTENT_SWITCH"] == 0.0 and lz["WEAPON_OWN"] is True and bad)

    class FakeEnv:
        def instr_bind(self):
            return b

    act = np.zeros((n, 10), np.int64)
    act[:, 6] = 1 + RG                                        # his own draw: the rail on every seat
    got = NP.bind_weapon(FakeEnv(), act)
    check("server pass: the weapon key's column set where the instruction binds, his own elsewhere",
          (got == b).all() and (act[:, 6] == np.where(b >= 0, b, 1 + RG)).all())
    act2 = np.full((2, 10), 1 + RG, np.int64)
    NP.bind_weapon(FakeEnv(), act2, rows=[1, 2])
    check("server pass: by rows", act2[0, 6] == 1 + LG and act2[1, 6] == 1 + RG)
    # the mask: the stored log-probability and the learner's recomputed one, with bound rows (1.7c's bug: one of them without it)
    g = torch.Generator().manual_seed(11)
    T_, N_, D_ = 12, 16, 10
    lg = torch.randn(T_, N_, D_, generator=g)
    own = torch.randint(0, D_, (T_, N_), generator=g)
    dec = (torch.rand(T_, N_, generator=g) < 0.25).float()
    wd = torch.where(torch.rand(T_, N_, generator=g) < 0.4, torch.randint(0, D_, (T_, N_), generator=g), torch.full((T_, N_), -1))
    lp = torch.distributions.Categorical(logits=lg).log_prob(own)
    stored = lp * H2.bound_mask(dec, wd)
    again = torch.distributions.Categorical(logits=lg.clone()).log_prob(own) * H2.bound_mask(dec, wd)
    nomask = lp * dec
    check("mask: the recomputed log-probability equals the stored one with bound rows (largest difference 0)",
          float((stored - again).abs().max()) == 0.0)
    check("mask: a bound frame counts nothing, a free one as before; without the mask the two differ (the guard has teeth)",
          float(stored[(wd >= 0)].abs().max()) == 0.0 and torch.equal(stored[wd < 0], nomask[wd < 0])
          and float((stored - nomask).abs().max()) > 0.0)
    import importlib
    T = importlib.import_module("train_duel_rnn")
    src = io.open(os.path.join(ROOT, "sim", "train_duel_rnn.py"), encoding="utf-8").read()
    check("trainer: --ins-bind; every head_masks call of the learning step passes the stored binding (wd=B_WD)",
          '"--ins-bind"' in src and "head2_.bound_mask(m, wd)" in src and src.count("wd=B_WD[:, chunk] if B_WD is not None else None") >= 6
          and "if (WR_ON or BIND_ON) else None" in src, src.count("wd=B_WD[:, chunk] if B_WD is not None else None"))
    del T


def test_prune():
    """the pruning tool on made-up branches: a group the outcome depends on passes, a group of noise does not; the split is by moment"""
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    import prune_inputs as PR
    rng = np.random.default_rng(5)
    R, bel, mem, head = 6000, 4, 4, 4
    names = ["fin_rl", "fin_hi_rl", "fire_rl", "known", "junk_a", "junk_b"]
    L = dict(sit=bel + mem + head, bel=bel, mem=mem, head=head, weapons=3, cand=2 + 2 + 3 + len(names), d=7,
             outs=["dealt", "taken", "he_dies", "i_die", "item", "dv", "dv_long"])
    meta = dict(layout=L, row0=7, names=names)
    S = rng.normal(0, 1, (R, L["sit"])).astype(np.float32)
    C = np.zeros((R, L["cand"]), np.float32)
    C[np.arange(R), 4 + rng.integers(0, 3, R)] = 1.0
    C[:, 7:] = rng.normal(0, 1, (R, len(names)))
    Y = np.zeros((R, 7), np.float32)
    Y[:, 5] = 0.8 * C[:, 7] + 0.3 * S[:, 0] + rng.normal(0, 0.5, R)          # dV: the finish time's first number and one of the brain's
    Y[:, 0] = np.abs(rng.normal(0, 0.3, R))
    Y[:, 2] = (rng.random(R) < 0.2)
    M = np.ones((R, 7), np.float32)
    M[:, 6] = 0.0
    grp = np.repeat(np.arange(R // 6), 6)                                   # six branches a moment
    fo = PR.folds_of(grp, 3, 1)
    check("prune: every branch of a moment is in one fold", all(len(set(fo[grp == g_].tolist())) == 1 for g_ in range(0, R // 6, 37)))
    n_, cj = PR.group_cols("finish", meta)
    check("prune: the group 'finish' is the row's three finish numbers; a block of the situation by name",
          cj == [L["sit"] + 7, L["sit"] + 8, L["sit"] + 9] and PR.group_cols("memory", meta)[1] == [4, 5, 6, 7] and PR.group_cols("weapon", meta)[1] == [16, 17, 18])
    res = PR.prune(S, C, Y, M, grp, meta, ["finish", "junk=junk_", "known"], folds=3, seeds=2, epochs=20, hid=32, say=lambda *_: None)
    g = res["groups"]
    check("prune: the forecast of dV has skill on unseen moments ({:.2f}); the long dV, without a label, has none".format(res["skill"]["dv"]),
          res["skill"]["dv"] > 0.4 and not np.isfinite(res["skill"]["dv_long"]))
    check("prune: the group dV depends on passes (gain {:+.3f}), a group of noise does not ({:+.4f}), nor one it does not depend on ({:+.4f})".format(
        g["finish"]["gain"]["dv"], g["junk"]["gain"]["dv"], g["known"]["gain"]["dv"]),
        g["finish"]["passes"] and g["finish"]["gain"]["dv"] > 0.3 and not g["junk"]["passes"] and not g["known"]["passes"])
    d = tempfile.mkdtemp()
    np.savez(os.path.join(d, "br_000001.npz"), S=S[:3000].astype(np.float16), C=C[:3000], Y=Y[:3000], M=M[:3000], grp=grp[:3000], meta=np.array(json.dumps(meta)))
    np.savez(os.path.join(d, "br_000002.npz"), S=S[3000:].astype(np.float16), C=C[3000:], Y=Y[3000:], M=M[3000:], grp=grp[3000:] - 500, meta=np.array(json.dumps(meta)))
    S2, C2, Y2, M2, g2, m2 = PR.load([d])
    check("prune: the dumps load as they were written; moments of two dumps never share a number",
          S2.shape == S.shape and np.array_equal(C2, C) and np.array_equal(Y2, Y) and len(np.unique(g2)) == R // 6 and m2["names"] == names)


if __name__ == "__main__":
    test_mapsense()
    test_appraise()
    test_branch()
    test_off()
    test_ins()
    test_branch_ins()
    test_long()
    test_live_ins()
    test_questions()
    test_inside()
    test_cleanup()
    test_bind()
    test_prune()
    print("ALL PASSED ({} checks)".format(N_OK[0]))
