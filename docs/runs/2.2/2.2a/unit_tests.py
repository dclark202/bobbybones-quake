"""2.2a's unit tests (CPU, no simulator, no run): every new label by brute force on made-up rollouts, the quantiles' coverage on a synthetic case,
the desc outlooks' sums (torch against numpy, the goal-blind row, the siblings' masks), the automatic mark's rule on made-up readout histories, and
the ramp itself on a scratch folder (the decision once, a restart that does not decide twice, the owner's mark winning, OUT_TRIAL's line).
    <anaconda python> docs/runs/2.2/2.2a/unit_tests.py [--scratch <a new folder>]
Nothing deleted; the ramp processes it starts are stopped by their own process handle."""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(CODE, "sim"))
import outlook as OL                                         # noqa: E402
import tracker as TR                                         # noqa: E402
import desc22 as D                                           # noqa: E402

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
OK = [True]


def chk(name, good, more=""):
    OK[0] = OK[0] and bool(good)
    print(("PASS  " if good else "FAIL  ") + name + (" | " + str(more)[:600] if more != "" else ""), flush=True)


def test_kinds():
    """segw and winit8 by brute force: segw = seg's sum over the items' stream bootstrapped by the second value; winit8 = 320 frames of it"""
    g = torch.Generator().manual_seed(1)
    T, N, gam = 400, 3, 0.999
    pw = torch.randn(T, N, generator=g) * 0.01
    pa = torch.randn(T, N, generator=g) * 0.01
    dn = (torch.rand(T, N, generator=g) < 0.004).float()
    vw = torch.randn(T + 1, N, generator=g)
    vh = torch.randn(T + 1, N, generator=g)
    rt = torch.tensor([3, 10, 50, 70], dtype=torch.long)
    ri = torch.tensor([0, 1, 2, 0], dtype=torch.long)
    se = torch.tensor([40, 200, T, 72], dtype=torch.long)
    Y, OKk, _ = OL.labels(OL.KINDS22, rt, ri, ret=torch.zeros(T, N), pay_all=pa, pay_win=pa, done=dn, gamma=gam, val=vh, seg_end=se, pay_wit=pw, val_w=vw)
    ks = list(OL.KINDS22)
    bad = 0
    for r in range(4):
        t0, i, e = int(rt[r]), int(ri[r]), int(se[r])
        s, cut = 0.0, False
        for f in range(t0, e):
            s += gam ** (f - t0) * float(pw[f, i])
            if dn[f, i] > 0:
                cut = True
                break
        if not cut:
            s += gam ** (e - t0) * float(vw[e, i])
        bad += abs(s - float(Y[r, ks.index("segw")])) > 1e-4
        if t0 + 320 <= T:
            s2 = 0.0
            for f in range(t0, t0 + 320):
                s2 += gam ** (f - t0) * float(pw[f, i])
                if dn[f, i] > 0:
                    break
            bad += abs(s2 - float(Y[r, ks.index("winit8")])) > 1e-4 or not bool(OKk[r, ks.index("winit8")])
        else:
            bad += bool(OKk[r, ks.index("winit8")])
    chk("segw and winit8 against brute force (4 rows, a cut, past the end)", bad == 0, bad)


def test_facts():
    T, N = 50, 4
    done = torch.zeros(T, N)
    dme = torch.zeros(T, N, dtype=torch.bool)
    reach = torch.zeros(T, N, dtype=torch.bool)
    hp = torch.zeros(T, N, 2)
    hp[..., 0], hp[..., 1] = 100.0, 50.0
    dme[20, 1] = True                                        # seat 1 dies in the step of frame 20 (seat 0's enemy)
    done[20, 1] = 1.0
    hp[20:, 1, 0] = -5.0
    reach[12, 0] = True
    hp[29, 0, 0], hp[29, 0, 1] = 80.0, 10.0
    foe = np.arange(N) ^ 1
    den = dme[:, torch.from_numpy(foe)]
    rt = torch.tensor([10, 10, 30, 5], dtype=torch.long)
    ri = torch.tensor([0, 1, 0, 2], dtype=torch.long)
    se = torch.tensor([30, 40, T, 15], dtype=torch.long)
    FY, FM = OL.fact_labels(rt, ri, se, done, dme, den, reach, hp, foe)
    exp0 = [1.0, 0.0, 1.0, 0.8, 0.1, 0.0, 0.0]               # seat 0, 10..29: the enemy (1) died at 20, he took his target at 12, his stack at 29
    exp1 = [0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.5]               # seat 1, 10.. cut at his death (20): he dies; his stack 0; the enemy's at 20
    ok_ = (np.allclose(FY[0].numpy(), exp0) and bool(FM[0].all()) and np.allclose(FY[1].numpy(), exp1) and bool(FM[1].all())
           and not bool(FM[2].any()) and bool(FM[3].all()) and float(FY[3, 0]) == 0.0)
    chk("the facts by hand (the enemy's death, his own and its cut, took, the stacks at the end, unknown past the rollout's end)", ok_,
        (FY.numpy().round(3).tolist(), FM.numpy().tolist()))


def test_near():
    n, F = 2, 900
    H = TR.History(n, F)
    for g in range(800):
        ev = torch.zeros(n, dtype=torch.uint8)
        if g == 150:
            ev[0] |= 1                                       # seat 0 dies at frame 150
            ev[1] |= 2
        if g == 130:
            ev[1] |= 4                                       # seat 1 sees the enemy at 130
        if g == 300:
            ev[:] |= 8                                       # a round's end at 300 (no death)
        fo = torch.full((n, 2), -1, dtype=torch.int8)
        if g == 100 + 200:
            fo[0] = torch.tensor([0, 1], dtype=torch.int8)   # the fight label of frame 100 (carried 200 frames on)
        H.put(g, ev, fo, torch.full((n,), -1.0, dtype=torch.float16))
    Y, M = TR.near_labels(H, 100, TR.WIN_F, 200)
    o = list(TR.OUTS)
    exp = {(0, "idie5"): 1, (0, "idie10"): 1, (1, "hedie5"): 1, (1, "idie5"): 0, (0, "con2"): 0, (1, "con2"): 1, (0, "fo_lose"): 1, (0, "fo_win"): 0}
    bad = [k_ for k_, v_ in exp.items() if float(Y[k_[0], o.index(k_[1])]) != v_]
    Y2, M2 = TR.near_labels(H, 30, TR.WIN_F, 200)
    bad2 = float(Y2[1, o.index("con2")]) != 0 or float(Y2[1, o.index("con5")]) != 1     # contact at 130: 100 frames on: within 5 s, not within 2 s
    Y3, M3 = TR.near_labels(H, 280, TR.WIN_F, 200)
    bad3 = float(Y3[0, o.index("idie10")]) != 0               # the round ends at 300 before any death: not within 10 s
    chk("the tracker's near labels by hand (deaths within 5 / 10 s, contact within 2 / 5 s and its cut, a round's end cuts, the fight label "
        "fight_d frames on, unknown elsewhere)", not bad and not bad2 and not bad3 and not bool(M[1, 4]) and bool(M[0, 4]), (bad, bad2, bad3))


def test_quantiles():
    """the pinball lesson finds the quantiles of a synthetic stack (constant input): coverage near 0.8, the middle near the median"""
    g = torch.Generator().manual_seed(4)
    L = TR.layout(list(range(4)), ["a"] * 4, bel=4, hid=32)
    m = TR.make_module(L)
    opt = torch.optim.Adam(m.parameters(), lr=3e-3)
    n = 20000
    X = torch.zeros(n, L["width"]).half()
    yh = 1.0 + 0.5 * torch.randn(n, generator=g)
    ya = (0.5 * torch.rand(n, generator=g)) ** 2 * 4
    Y = torch.zeros(n, len(TR.OUTS))
    M = torch.zeros(n, len(TR.OUTS), dtype=torch.bool)
    Y[:, TR.ENH], Y[:, TR.ENA] = yh[:, None], ya[:, None]
    M[:, TR.ENH] = M[:, TR.ENA] = True
    for _ in range(25):
        TR.learn(m, opt, X, Y, M, 3e-3, "cpu", g, mb=2000)
    P = TR.predict(m, X[:5000], "cpu")
    yt = 1.0 + 0.5 * torch.randn(5000, generator=g)
    acc = TR.Acc()
    acc.add_q("all", "health", P[:, TR.ENH].numpy(), yt.numpy(), np.full(5000, 1.0), np.full(5000, 2.0))
    r = acc.record()["all"]["stack_health"]
    q = P[0, TR.ENH].numpy()
    true_ = np.array([1.0 - 1.2816 * 0.5, 1.0, 1.0 + 1.2816 * 0.5])
    chk("the quantiles' lesson on a synthetic normal stack: coverage {} (near 0.8), quantiles {} (true {}), the middle's error {} (points)".format(
        r["inside"], q.round(3), true_.round(3), r["mid_err"]), abs(r["inside"] - 0.8) < 0.04 and np.abs(q - true_).max() < 0.08, r)
    a2 = TR.Acc()
    p_ = np.array([[0.9], [0.1], [0.5], [0.5]])
    y_ = np.array([[1.0], [0.0], [1.0], [0.0]])
    pp = np.zeros((4, TR.NB))
    yy = np.zeros((4, TR.NB))
    mm = np.zeros((4, TR.NB), bool)
    pp[:, 6], yy[:, 6], mm[:, 6] = p_[:, 0], y_[:, 0], True
    a2.add_b("all", pp, yy, mm)
    rr = a2.record()["all"]["idie5"]
    br = ((p_ - y_) ** 2).mean()
    chk("Brier skill and AUC by hand (Brier {:.4f}, constant 0.25)".format(br), abs(rr["brier"] - br) < 1e-4 and abs(rr["skill"] - (1 - br / 0.25)) < 1e-3
        and abs(rr["auc"] - 0.875) < 1e-6, rr)


def test_desc():
    L = D.layout(OL.KINDS22, OL.FACTS)
    mods = D.make_module(L)
    g = torch.Generator().manual_seed(7)
    with torch.no_grad():
        for s_ in L["sibs"]:
            for p_ in mods[s_].parameters():
                p_.copy_(torch.randn(p_.shape, generator=g) * 0.1)
    B = 6
    s = torch.randn(B, 256, generator=g)
    sit = torch.randn(B, len(L["sit"]), generator=g).half().float()
    tgt = torch.randn(B, 17, len(L["tgt"]), generator=g).half().float()
    W = {"dsc." + k_: v_.detach().numpy() for k_, v_ in mods.state_dict().items()}
    ok_ = True
    for s_ in L["sibs"]:
        with torch.no_grad():
            o_t, f_t = D.forward(mods, L, s_, s, sit, tgt)
        o_n, f_n = D.np_forward(D.np_params(W, s_), L, s.numpy(), sit.numpy(), tgt.numpy(), sib=s_)
        ok_ = ok_ and np.abs(o_t.numpy() - o_n).max() < 1e-4 and np.abs(f_t.numpy() - f_n).max() < 1e-4
    with torch.no_grad():
        o1, _ = D.forward(mods, L, "desc", s, sit, tgt)
        o2, _ = D.forward(mods, L, "desc", s, sit, tgt * 0 + 5.0)
        o3, _ = D.forward(mods, L, "desc_nomap", s, sit, tgt)
        sit2, tgt2 = sit.clone(), tgt.clone()
        mg = D.groups()
        sit2[:, mg["sit_map"]] += 3.0
        tgt2[..., mg["tgt_map"]] -= 2.0
        o4, _ = D.forward(mods, L, "desc_nomap", s, sit2, tgt2)
        o5, _ = D.forward(mods, L, "desc_notrk", s, sit, tgt)
        sit3 = sit.clone()
        sit3[:, mg["sit_trk"]] += 4.0
        o6, _ = D.forward(mods, L, "desc_notrk", s, sit3, tgt)
    chk("desc: torch and numpy the same (every sibling, kinds and facts); the goal-blind row does not read the targets; desc_nomap does not read "
        "the map sense; desc_notrk does not read the tracker", ok_ and torch.equal(o1[..., -1], o2[..., -1]) and torch.equal(o3, o4) and torch.equal(o5, o6)
        and not torch.equal(o1[..., 0], o2[..., 0]))
    T1 = D.term(mods, L, s, sit, tgt, 2.0, 0)
    T2 = D.np_term(D.np_params(W, "desc"), L, s.numpy(), sit.numpy(), tgt.numpy(), 2.0, 0)
    chk("desc's term: torch = numpy (half precision), centred over the targets", np.abs(T1.numpy() - T2).max() < 2e-3
        and abs(float(T1.mean(-1).abs().max())) < 0.05, float(np.abs(T1.numpy() - T2).max()))


def test_nonfinite():
    o = torch.randn(4, 18)
    o[1, 3] = float("nan")
    o[2, 5] = float("inf")
    t = OL.term(o, 1.0)
    tn = OL.np_term(o.numpy(), 1.0)
    chk("a non-finite outlook gives a term of 0 for that seat (torch and numpy), the others as before; counted {}".format(OL.nonfinite_rows(o)),
        bool(torch.isfinite(t).all()) and float(t[1].abs().sum()) == 0 and float(t[2].abs().sum()) == 0 and np.isfinite(tn).all()
        and np.abs(tn[[1, 2]]).sum() == 0 and torch.equal(t[[0, 3]], OL.term(o[[0, 3]], 1.0)) and OL.nonfinite_rows(o) == 2)
    sr = np.zeros((2, len(D.sit_names())), np.float32)
    sr[0, 0] = 1e6
    L = D.layout(OL.KINDS22, OL.FACTS)
    si, tg = D.np_inputs(L, sr, np.zeros((2, 17, len(D.tgt_names())), np.float32))
    si2, tg2 = D.inputs(L, torch.from_numpy(sr), torch.zeros(2, 17, len(D.tgt_names())))
    chk("the new inputs clipped to +- {} before the rounding, the same in torch and numpy".format(D.IN_CLIP), float(si.max()) == D.IN_CLIP
        and np.array_equal(si, si2.numpy()))
    X = np.zeros((3, 17, 34), np.float16)
    try:
        D.check_blank(X)
        chk("a blank description raises", False)
    except RuntimeError:
        chk("a blank description (the simulator without its map numbers) raises", True)


def ramp_module():
    sp = importlib.util.spec_from_file_location("ramp22a", os.path.join(HERE, "ramp_22a.py"))
    R = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(R)
    return R


def fake_lines(n, built_dec, built_stay, desc_dec, desc_stay, built_rep, desc_rep):
    out = []
    for u in range(1, n + 1):
        k = dict(decision=dict(gain=built_dec(u)), stay=dict(gain=built_stay(u)), replay=built_rep)
        kd = dict(decision=dict(gain=desc_dec(u)), stay=dict(gain=desc_stay(u)), replay=desc_rep)
        out.append(dict(update=u, outlook=dict(kind=dict(seg=k), g=0.0, pick=0, trial=0.03), out22=dict(src=0, desc=dict(desc=dict(kind=dict(seg=kd))))))
    return out


def test_rule():
    R = ramp_module()
    cfg = dict(R.AUTO)
    rep_lo = {"0.5": 0.01, "1.0": 0.03, "2.0": 0.06, "4.0": 0.12, "8.0": 0.2}
    rep_hi = {"0.5": 0.25, "1.0": 0.4, "2.0": 0.5, "4.0": 0.6, "8.0": 0.7}
    # passes: desc better
    d = R.auto_decide(fake_lines(60, lambda u: 0.01, lambda u: 0.01, lambda u: 0.02, lambda u: 0.01, rep_lo, rep_lo), cfg)
    chk("the rule: both pass, desc's gain higher: desc plays at the largest strength with a share at most 0.10 (2.0)", d["passed"] and d["src"] == 1
        and abs(d["mark"] - 2.0) < 1e-9 and d["open"] == [60, 100], {k_: d.get(k_) for k_ in ("passed", "src", "mark", "open")})
    # near tie: desc 0.0095 vs built 0.01 x 0.9 = 0.009 -> desc
    d = R.auto_decide(fake_lines(60, lambda u: 0.01, lambda u: 0.01, lambda u: 0.0095, lambda u: 0.01, rep_lo, rep_lo), cfg)
    chk("the rule: a near tie (desc at 0.95 of the built one's gain) goes to desc", d["passed"] and d["src"] == 1, d.get("src"))
    d = R.auto_decide(fake_lines(60, lambda u: 0.01, lambda u: 0.01, lambda u: 0.008, lambda u: 0.01, rep_lo, rep_lo), cfg)
    chk("the rule: desc at 0.8 of the built one's gain: the built one plays", d["passed"] and d["src"] == 0, d.get("src"))
    # gate fails: decision gains positive in only 7 of 10
    d = R.auto_decide(fake_lines(60, lambda u: 0.02 if u % 10 < 7 else -0.01, lambda u: 0.01, lambda u: -0.01, lambda u: 0.01, rep_lo, rep_lo), cfg)
    chk("the rule: positive in 7 of 10 decision readings (and desc negative): the gate fails, the dial stays 0", not d["passed"] and d["mark"] == 0.0
        and d["candidates"]["built"]["decision_positive"] == 7, (d["passed"], d["candidates"]["built"]["decision_positive"]))
    d = R.auto_decide(fake_lines(60, lambda u: 0.02, lambda u: -0.001, lambda u: None, lambda u: None, rep_lo, rep_lo), cfg)
    chk("the rule: a stay gain below 0 fails the gate; a candidate with no readout fails it too", not d["passed"], d["candidates"]["desc"]["passed"])
    # the share too large at 0.5
    d = R.auto_decide(fake_lines(60, lambda u: 0.01, lambda u: 0.01, lambda u: 0.02, lambda u: 0.01, rep_lo, rep_hi), cfg)
    chk("the rule: the share at 0.5 is 0.25 (over 0.10): the mark 0.5 x 0.10 / 0.25 = 0.2", d["passed"] and abs(d["mark"] - 0.2) < 1e-9, d.get("mark"))
    rep_vhi = dict(rep_hi, **{"0.5": 0.9})
    d = R.auto_decide(fake_lines(60, lambda u: 0.01, lambda u: 0.01, lambda u: 0.02, lambda u: 0.01, rep_lo, rep_vhi), cfg)
    chk("the rule: the share at 0.5 is 0.9: floored at 0.1", d["passed"] and abs(d["mark"] - 0.1) < 1e-9, d.get("mark"))
    d = R.auto_decide(fake_lines(55, lambda u: 0.01, lambda u: 0.01, lambda u: 0.02, lambda u: 0.01, rep_lo, rep_lo), cfg)
    chk("the rule: fewer lines than the window up to `at`: does not pass", not d["passed"])
    for bad_ in (dict(at=0), dict(window=70), dict(min_pos=11), dict(max_share=2), dict(kind="ret"), dict(foo=1)):
        c_, w_ = R.auto_check(bad_)
        if c_ is not None:
            chk("auto_mark.json refused: {}".format(bad_), False)
    chk("auto_mark.json: out-of-range or unknown settings refused (6 cases); the file of the run accepted",
        R.auto_check(json.load(open(os.path.join(HERE, "auto_mark.json"))))[0] is not None)
    chk("OUT_TRIAL's line: 0 at 0, 0.015 at 5, 0.03 at 10 and after", abs(R.value("OUT_TRIAL", 0)) < 1e-12 and abs(R.value("OUT_TRIAL", 5) - 0.015) < 1e-12
        and abs(R.value("OUT_TRIAL", 10) - 0.03) < 1e-12 and abs(R.value("OUT_TRIAL", 300) - 0.03) < 1e-12)


def run_ramp(D, args, secs):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "ramp_22a.py"), "scratch", "--dir", D, "--poll", "1", "--settle", "0"] + args,
                         creationflags=NOWIN, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(secs)
    p.terminate()
    p.wait(30)
    return p.stderr.read().decode(errors="replace")[-1500:]


def test_ramp_live(scratch):
    """the ramp on a scratch folder: decides once at 60 (desc, 2.0), OUT_SRC at once, OUT_G on its line; a restart does not decide twice; the
    owner's mark of 0 wins"""
    D = os.path.join(scratch, "ramp")
    os.makedirs(os.path.join(D, "watch"))
    os.makedirs(os.path.join(D, "keep"))
    json.dump(dict(OUT_G=0.0, OUT_TRIAL=0.0, OUT_PICK=0, PULL_G=2.0, HELD_G=1.0, OUT_SRC=0), open(os.path.join(D, "live.json"), "w"))
    json.dump(json.load(open(os.path.join(HERE, "auto_mark.json"))), open(os.path.join(D, "watch", "auto_mark.json"), "w"))
    rep = {"0.5": 0.01, "1.0": 0.03, "2.0": 0.06, "4.0": 0.12, "8.0": 0.2}
    L = fake_lines(70, lambda u: 0.01, lambda u: 0.01, lambda u: 0.02, lambda u: 0.01, rep, rep)
    with open(os.path.join(D, "metrics.jsonl"), "w") as f:
        for m in L[:59]:
            f.write(json.dumps(m) + "\n")
    e1 = run_ramp(D, [], 5)
    lv1 = json.load(open(os.path.join(D, "live.json")))
    no_dec = not os.path.exists(os.path.join(D, "watch", "out_mark_auto.json"))
    with open(os.path.join(D, "metrics.jsonl"), "a") as f:
        f.write(json.dumps(L[59]) + "\n")
    e2 = run_ramp(D, ["--resume"], 5)
    dec = json.load(open(os.path.join(D, "watch", "out_mark_auto.json")))
    lv2 = json.load(open(os.path.join(D, "live.json")))
    chk("the ramp: nothing decided at 59 (OUT_TRIAL {}); at 60 decided once: desc, mark 2.0, OUT_SRC 1 at once with OUT_G 0".format(lv1.get("OUT_TRIAL")),
        no_dec and abs(lv1["OUT_TRIAL"] - 0.03) < 1e-9 and dec["passed"] and dec["src"] == 1 and abs(dec["mark"] - 2.0) < 1e-9 and lv2["OUT_SRC"] == 1
        and abs(lv2["OUT_G"]) < 1e-9, (lv1, lv2, e1, e2))
    bad = fake_lines(70, lambda u: -0.01, lambda u: -0.01, lambda u: -0.02, lambda u: -0.01, rep, rep)
    with open(os.path.join(D, "metrics.jsonl"), "w") as f:     # (made-up histories that would fail: the decision stays the first)
        for m in bad[:70]:
            f.write(json.dumps(m) + "\n")
    e3 = run_ramp(D, ["--resume"], 5)
    dec2 = json.load(open(os.path.join(D, "watch", "out_mark_auto.json")))
    lv3 = json.load(open(os.path.join(D, "live.json")))
    chk("the ramp restarted at 70 (histories that would fail now): not decided twice; OUT_G on its line 2.0 x 10 / 40 = 0.5", dec2 == dec
        and abs(lv3["OUT_G"] - 0.5) < 1e-6 and lv3["OUT_SRC"] == 1, (lv3, e3))
    json.dump(dict(mark=0.0, **{"from": 60, "to": 100}), open(os.path.join(D, "watch", "out_mark.json"), "w"))
    with open(os.path.join(D, "metrics.jsonl"), "a") as f:
        f.write(json.dumps(bad[0]) + "\n")
    e4 = run_ramp(D, ["--resume"], 5)
    lv4 = json.load(open(os.path.join(D, "live.json")))
    chk("the owner's mark of 0 wins over the automatic one: OUT_G 0", abs(lv4["OUT_G"]) < 1e-9, (lv4, e4))
    wl = open(os.path.join(D, "watch", "watch.log")).read()
    chk("watch.log: the automatic mark's line once, the owner's mark line", wl.count("THE AUTOMATIC MARK at update 60") == 1 and "THE OWNER'S MARK" in wl)
    n_ = len(open(os.path.join(D, "metrics.jsonl")).read().splitlines())      # (the end on a mark's update: the mark's files kept)
    for nm_, tx_ in (("policy.pt", "END"), ("opt.pt", "ENDOPT"), (os.path.join("keep", "policy_u{}.pt".format(n_)), "MARK"),
                     (os.path.join("keep", "opt_u{}.pt".format(n_)), "MARKOPT")):
        open(os.path.join(D, nm_), "w").write(tx_)
    open(os.path.join(scratch, "scratch.log"), "w").write("update=1" + chr(10) + "exit 0" + chr(10))
    run_ramp(D, ["--resume"], 6)
    rd_ = lambda f_: open(os.path.join(D, "keep", f_)).read() if os.path.exists(os.path.join(D, "keep", f_)) else None    # noqa: E731
    chk("the end on a mark's update: the mark's files kept as they were, the end's own files written", rd_("policy_u{}.pt".format(n_)) == "MARK"
        and rd_("opt_u{}.pt".format(n_)) == "MARKOPT" and rd_("policy_end_22a.pt") == "END" and rd_("opt_end_22a.pt") == "ENDOPT",
        (rd_("policy_u{}.pt".format(n_)), rd_("policy_end_22a.pt")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", default="")
    a = ap.parse_args()
    test_kinds()
    test_facts()
    test_near()
    test_quantiles()
    test_desc()
    test_nonfinite()
    test_rule()
    if a.scratch:
        if os.path.exists(a.scratch):
            raise SystemExit(a.scratch + " is there: not run (nothing deleted)")
        os.makedirs(a.scratch)
        test_ramp_live(a.scratch)
    print("ALL PASSED" if OK[0] else "FAILED", flush=True)
    sys.exit(0 if OK[0] else 1)


if __name__ == "__main__":
    main()
