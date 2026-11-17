"""2.2a (docs/runs/2.2/DESIGN.md): its parts outside the trainer, in the real simulator (made from tools/run/out_playtest.py).

  sample  a network (2.1d's end) plays every seat of a few matches on one map through test_suite.Policy (the run's settings from its command,
          DESC_OX=1, FIGHT_TRUTH=1, CONTROL_TRUTH=1): every frame recorded (for `same`), and at each keep reading the desc outlook's RAW inputs
          (sim/desc22.py raw_inputs: the simulator's description, the map sense of the start file, the brain's chances of the enemy's weapons;
          the tracker's outputs left at 0: their spread is set by design from the base rates of their labels, measured here) and the truths the
          base rates come from (his and the enemy's deaths, contact, the fight labels, the enemy's health and armor). -> <out>.npz
  same    tools/out22_init.py's file against its source on the recorded frames: actions, keep column and memory, at out_g 0 and at out_g 1 with
          each source (out_src 0, 1; the last layers at zero): 0 frames may differ
  desc    the desc term end to end: a test file (out_src 1, out_g 1.0, held share 0.5, pull 1.0, desc's last layer made non-zero by a fixed seed)
          plays; its frames replayed through test_suite.Policy and through plugins/netpass.py on its export: 0 frames may differ (actions, keep
          column, memory, the held desc term); the trainer's torch sums (sim/desc22.py inputs/term, the tracker, the map sense's torch_fwd) on
          the recorded readings against the readers' numpy: the largest difference of the term
    QLBOT_ROOT=<the checkout with data> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python tools/run/play22.py <cmd> ...
One simulator in this process. Nothing deleted."""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CMD21D = os.path.join(ROOT, "docs", "runs", "2.1", "2.1d", "train.cmd")


def setup(cmd, extra):
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    import keep21_simtest as ks_
    ev = ks_.cmd_env(cmd, os.environ.get("QLBOT_ROOT") or ROOT)
    ev.update(extra)
    os.environ.update(ev)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    sys.path.insert(0, os.path.join(ROOT, "plugins"))


def make_env(E, pol, mp, matches, seed=7):
    nav_ = os.path.join(DATA, "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(DATA, "maps", mp + ".bsp"), n_matches=matches, seed=seed, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    import test_suite as T
    T.set_delays(E, env, [(np.arange(0, env.n), pol.react_ms, pol.acquire_ms)])
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
    if getattr(E, "BRAIN_READ", False):                      # (as tools/duel_eval.py: the simulator's readers on the brain's answer, every
        env.set_brain_g(np.full(env.n, pol.rfg if getattr(pol, "rf_read", False) else 0.0, np.float32))   # life drawn at the network's fade)
        env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))
    return env


def col_idx(pol):
    import csv
    now = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    return np.array([now.index(tuple(x_)) for x_ in pol.names]) if pol.names else np.arange(len(pol.mean))


def play_rec(E, pol, env, mp, frames, desc=False, brain=False):
    """the policy on every seat; every frame recorded; at a keep reading (pol.k_r before act) the simulator's description (ox) and, with
    brain=True, the brain's state, his normalised inputs and the token's place, valid, hand of those rows"""
    import head2 as H2
    import btoken as BT
    import desc22 as D
    idx = col_idx(pol)
    n = env.n
    nA = len(E.ACTION_DIMS)
    obs = env.observe()
    h = pol.zeros(n)
    rec = dict(obs=[], kf=[], pose=[], zmap=[], xl=[], clr=[], act=[], ox=[], kr=[], aux=[], hp=[], pos=[])
    rd = dict(t=[], i=[], sb=[], xa=[], P=[], ok=[], hand=[], ox=[])
    pol.set_maps(mp) if hasattr(pol, "set_maps") else None
    for t in range(frames):
        kf = H2.np_kf_end(env)
        pz, zz = BT.pose_from_env(env, mp)
        xl = env.legs_prep() if pol.needs_xl else None
        kr = None if pol.k_r is None else np.asarray(pol.k_r, bool).copy()
        ox = D.env_ox(env) if (kr is not None and kr.any() and (desc or brain)) else None
        if brain and ox is not None:
            ob_ = np.asarray(obs)[:, idx]
            br_, tk_ = BT.unpack(pol.brainP, pol.btok, h[:, pol.brain_at:])
            tk_.see(ob_)
            r_ = np.nonzero(kr)[0]
            rd["t"].append(np.full(len(r_), t))
            rd["i"].append(r_)
            rd["sb"].append(np.asarray(br_.s, np.float32)[r_])
            rd["xa"].append(pol.norm(ob_)[r_])
            rd["P"].append(np.asarray(tk_.P, np.float32)[r_])
            rd["ok"].append(np.asarray(tk_.valid, bool)[r_])
            rd["hand"].append(np.asarray(tk_.hand)[r_].argmax(1))
            rd["ox"].append(tuple(np.asarray(v_)[r_] for v_ in ox))
        ac, h = pol.act(np.asarray(obs)[:, idx], h, xl=xl, pose=pz, zmap=zz, kf=kf, **({"ox": ox} if ox is not None else {}))
        act = np.concatenate([ac[:, :nA], ac[:, -1:]], 1)
        for k_, v_ in (("obs", obs), ("kf", kf), ("pose", pz), ("zmap", zz), ("xl", xl), ("act", ac), ("ox", ox), ("kr", kr)):
            rec[k_].append(None if v_ is None else (tuple(np.array(x_).copy() for x_ in v_) if isinstance(v_, tuple) else np.array(v_).copy()))
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
            env.legs_lg = pol.legs_logits(env.legs_prep())
        an_ = pol.brain_answer(h)                            # (BRAIN_READ: the brain's answer of this frame to the simulator, as the trainer
        if an_ is not None:                                  # and tools/duel_eval.py give it: its belief is the brain's)
            env.brain_in({k_: an_[k_] for k_ in ("bel", "ok", "band", "ztop") if k_ in an_})
        obs, r_, done, info = env.step(act)
        rec["aux"].append(np.asarray(info["aux"], np.float32).copy() if "aux" in info else None)
        rec["hp"].append(np.stack([np.asarray(env.hp[:n], np.float32), np.asarray(env.armor[:n], np.float32)], 1))
        rec["pos"].append(np.asarray(env.state[:n, :3], np.float32).copy())   # (2.2a: every seat's place after the step: the pass odds' base rates)
        d = np.asarray(done, bool).copy()
        rec["clr"].append(d)
        if d.any():
            pol.clear(h, d)
    return rec, rd


def sample(a):
    setup(a.cmd, dict(DESC_OX="1", FIGHT_TRUTH="1", CONTROL_TRUTH="1"))
    import importlib
    import torch
    E = importlib.import_module("duel_env_ffa")
    import test_suite as T
    import desc22 as D
    import tracker as TR
    import mapsense as MS
    pol = T.Policy(a.src, seed=0)
    env = make_env(E, pol, a.map, a.matches)
    rec, rd = play_rec(E, pol, env, a.map, a.frames, brain=True)
    n = env.n
    # the raw inputs of every keep reading (the map sense of the start file; the tracker's outputs 0)
    tabs, _ = MS.load_tables(os.environ.get("QLBOT_ROOT") or ROOT, [a.map])
    msL = MS.layout(tabs)
    msm = MS.make_module(msL)
    MS.load_start(msm, a.ms_start)
    msP = {k_: v_.detach().numpy() for k_, v_ in msm.state_dict().items()}
    L = D.layout(["seg"], ["he_dies"], cmb_feat=E.CMB_FEAT, cmb_ctx=E.CMB_CTX)
    SB, OX = np.concatenate(rd["sb"]), tuple(np.concatenate([o_[k_] for o_ in rd["ox"]]) for k_ in range(5))
    trk_b = __import__("btoken").np_mlp(pol.brainP["trk"], SB)
    eo = 1.0 / (1.0 + np.exp(-trk_b[:, D.TRK_OWN]))
    sit, tgt = D.raw_inputs(L, OX[0], OX[1], OX[2], OX[3], OX[4], eo, np.zeros((len(SB), len(TR.OUTS)), np.float32), np.concatenate(rd["P"]),
                            np.concatenate(rd["ok"]), np.concatenate(rd["hand"]), lambda x_, r_: MS.np_forward(msP, x_, r_), msL, tabs,
                            np.full(len(SB), a.map))
    # the truths of the base rates: per frame and seat
    ax = np.stack(rec["aux"])                                # [F, n, C] after each step
    C = {c_: list(E.AUX_COLS).index(c_) for c_ in ("died", "en_in_view", "en_alive", "fo_win", "fo_lose")}
    hp = np.stack(rec["hp"])                                 # [F, n, 2] after each step
    foe = np.arange(n) ^ 1
    np.savez_compressed(a.out, sit=sit, tgt=tgt, died=ax[:, :, C["died"]] > 0.5, con=ax[:, :, C["en_in_view"]] > 0.5,
                        alive=ax[:, :, C["en_alive"]][:, foe] > 0.5, en_alive=ax[:, :, C["en_alive"]] > 0.5, fo_win=ax[:, :, C["fo_win"]],
                        fo_lose=ax[:, :, C["fo_lose"]], hp=hp, clr=np.stack(rec["clr"]), rt=np.concatenate(rd["t"]), ri=np.concatenate(rd["i"]),
                        pos=np.stack(rec["pos"]), pts=OX[2][:, :17].astype(np.float32),
                        map=a.map, frames=a.frames)
    # the frames for `same`
    rp = os.path.splitext(a.out)[0] + "_frames.npz"
    np.savez_compressed(rp, obs=np.stack(rec["obs"]), kf=np.stack(rec["kf"]), pose=np.stack(rec["pose"]), zmap=np.stack(rec["zmap"]),
                        clr=np.stack(rec["clr"]), act=np.stack(rec["act"]), kr=np.stack([k_ if k_ is not None else np.zeros(n, bool) for k_ in rec["kr"]]),
                        xl=np.stack(rec["xl"]) if rec["xl"][0] is not None else np.zeros(1),
                        **{"ox{}".format(k_): np.stack([o_[k_] if o_ is not None else np.zeros_like(next(x_ for x_ in rec["ox"] if x_ is not None)[k_])
                                                        for o_ in rec["ox"]]) for k_ in range(5)},
                        oxm=np.array([o_ is not None for o_ in rec["ox"]]), map=a.map)
    print("sample: {} frames x {} seats on {}: {} keep-reading rows; written {} and {}".format(a.frames, n, a.map, len(sit), a.out, rp), flush=True)


def load_frames(p):
    z = np.load(p)
    F = len(z["obs"])
    ox = [tuple(z["ox{}".format(k_)][t] for k_ in range(5)) if z["oxm"][t] else None for t in range(F)]
    return dict(obs=z["obs"], kf=z["kf"], pose=z["pose"], zmap=z["zmap"], clr=z["clr"], act=z["act"], kr=z["kr"],
                xl=z["xl"] if z["xl"].ndim > 1 else None, ox=ox, map=str(z["map"]), F=F)


def same(a):
    """the init file against its source on recorded frames"""
    setup(a.cmd, dict(DESC_OX="1", FIGHT_TRUTH="1", CONTROL_TRUTH="1"))
    import test_suite as T
    R = load_frames(a.frames)
    ok = True
    for nm_, og_, src_ in (("out_g 0", 0.0, None), ("out_g 1, the built outlook (out_src 0)", 1.0, 0), ("out_g 1, desc (out_src 1)", 1.0, 1)):
        pa, pb = T.Policy(a.src, seed=0), T.Policy(a.init, seed=0)
        assert pb.dsc22 is not None and pa.outW is None
        pb.set_out_g(og_)
        if src_ is not None:
            pb.set_out_src(src_)
        pb.set_maps(R["map"])
        idx = col_idx(pa)
        n = R["obs"].shape[1]
        ha, hb = pa.zeros(n), pb.zeros(n)
        da = dh = 0
        acts = 0
        for t in range(R["F"]):
            o_ = R["obs"][t][:, idx]
            kw = dict(xl=R["xl"][t] if R["xl"] is not None else None, pose=R["pose"][t], zmap=R["zmap"][t], kf=R["kf"][t])
            x1, ha = pa.act(o_, ha, **kw)
            x2, hb = pb.act(o_, hb, **kw, **({"ox": R["ox"][t]} if R["ox"][t] is not None else {}))
            da += int(not np.array_equal(x1, x2))
            dh += int(not np.array_equal(ha, hb))
            acts += x1.size
            if R["clr"][t].any():
                pa.clear(ha, R["clr"][t])
                pb.clear(hb, R["clr"][t])
        print("same ({}): {} frames x {} seats ({} actions): frames whose actions or keep column differ {}, whose memory differs {}: {}".format(
            nm_, R["F"], n, acts, da, dh, "PASS" if da == 0 and dh == 0 else "FAIL"), flush=True)
        ok = ok and da == 0 and dh == 0
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return ok


def desc(a):
    """desc's term end to end: the readers against each other, the trainer's torch sums against the readers' numpy"""
    import torch
    os.makedirs(a.work, exist_ok=True)
    p1 = os.path.join(a.work, "desc.pt")
    if not a.skip_make:
        ck = torch.load(a.init, weights_only=False, map_location="cpu")
        sd = ck["model"]
        sd["head2.held_g"] = torch.tensor(0.5)
        sd["head2.pull_g"] = torch.tensor(1.0)
        sd["head2.out_g"] = torch.tensor(1.0)
        sd["head2.out_pick"] = torch.tensor(0.0)
        sd["head2.out_src"] = torch.tensor(1.0)
        g_ = torch.Generator().manual_seed(2227)
        for k_ in ("head2.dsc.desc.l3.weight", "head2.trk.l3.weight") + (("head2.trk.p2.weight",) if "head2.trk.p2.weight" in sd else ()):
            w_ = sd[k_]
            sd[k_] = torch.randn(w_.shape, generator=g_) * (3.0 / float(w_.shape[1]) ** 0.5)
        sd["head2.dsc.desc.l3.bias"] = torch.randn(sd["head2.dsc.desc.l3.bias"].shape, generator=g_) * 0.3
        torch.save(ck, p1)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "sim", "export_duel.py"), "--run", "play22", "--policy", os.path.abspath(p1),
                            "--out", os.path.join(a.work, "desc.npz"), "--env", "duel_env_ffa", "--legs", a.legs], capture_output=True, text=True,
                           creationflags=NOWIN, cwd=ROOT)
        print(r.stdout.strip()[-1200:], flush=True)
        if r.returncode != 0:
            print(r.stderr[-4000:])
            raise SystemExit("export failed")
    setup(a.cmd, dict(DESC_OX="1", FIGHT_TRUTH="1", CONTROL_TRUTH="1"))
    import importlib
    E = importlib.import_module("duel_env_ffa")
    import test_suite as T
    import netpass as N
    import desc22 as D
    import tracker as TR
    import mapsense as MS
    import head2 as H2
    pol = T.Policy(p1, seed=0)
    assert pol.desc_on and pol.out_on, "desc.pt: desc's term does not play"
    env = make_env(E, pol, a.map, a.matches)
    rec, rd = play_rec(E, pol, env, a.map, a.frames, desc=True, brain=True)
    n = env.n
    idx = col_idx(pol)
    print("b. PLAY {} frames x {} seats on {} with desc's term (out_g 1, out_src 1): played; {} keep-reading rows".format(
        a.frames, n, a.map, sum(len(x_) for x_ in rd["t"])), flush=True)
    # c. the checks' player again, and the plugin's pass on the export
    pol2 = T.Policy(p1, seed=0)
    pol2.set_maps(a.map)
    h2 = pol2.zeros(n)
    P, A = N.load(os.path.join(a.work, "desc.npz"))
    assert N.desc_on(P), "desc.npz: desc's term not read"
    rng = np.random.default_rng(0)
    hn = np.zeros((n, N.width(P)), np.float32)
    bad, first = dict(replay=0, act=0, col=0, H=0, term=0), {}
    for t in range(a.frames):
        o_ = rec["obs"][t]
        kw = dict(xl=rec["xl"][t], pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t])
        oxk = {"ox": rec["ox"][t]} if rec["ox"][t] is not None else {}
        ac2, h2 = pol2.act(o_[:, idx], h2, **kw, **oxk)
        acn, hn = N.step(P, A, o_, hn, rng, xl=rec["xl"][t] if N.needs_xl(P) else None, pose=rec["pose"][t], zmap=rec["zmap"][t], kf=rec["kf"][t],
                         mapname=a.map, **oxk)
        for k_, c_ in (("replay", not np.array_equal(ac2, rec["act"][t])), ("act", not np.array_equal(acn, ac2[:, :-1])),
                       ("col", not np.array_equal(np.asarray(P["_keep"]), ac2[:, -1])), ("H", not np.array_equal(hn, h2)),
                       ("term", not np.array_equal(P["_dsc"].term(n), pol2.dsc22.term(n)))):
            if c_:
                bad[k_] += 1
                first.setdefault(k_, t)
        if rec["clr"][t].any():
            pol2.clear(h2, rec["clr"][t])
            N.clear(P, hn, rec["clr"][t])
    okc = not any(bad.values())
    nz = float(np.abs(pol2.dsc22.term(n)).max())
    print("c. SERVER = CHECKS with desc's term over {} frames: frames with a difference: Policy replay {}, actions {}, keep column {}, memory {}, "
          "the held desc term {}{} (the term's largest now {:.3f}): {}".format(a.frames, bad["replay"], bad["act"], bad["col"], bad["H"], bad["term"],
                                                                              " (first: {})".format(first) if first else "", nz, "PASS" if okc else "FAIL"),
          flush=True)
    okc = okc and nz > 0
    # d. the trainer's torch sums against the readers' numpy on the recorded readings
    ck = torch.load(p1, weights_only=False, map_location="cpu")
    hm = H2.make_module(ck["head2"])
    hm.load_state_dict({k_[len("head2."):]: v_ for k_, v_ in ck["model"].items() if k_.startswith("head2.")})
    msm = MS.make_module(ck["map_sense"]["layout"])
    msm.load_state_dict(ck["map_sense"]["model"])
    tabs = pol.dsc22.tables([a.map])
    TL, DL = ck["head2"]["trk22"], ck["head2"]["desc22"]
    SB = np.concatenate(rd["sb"])
    XA = np.concatenate(rd["xa"])
    OX = tuple(np.concatenate([o_[k_] for o_ in rd["ox"]]) for k_ in range(5))
    PP, OK, HD = np.concatenate(rd["P"]), np.concatenate(rd["ok"]), np.concatenate(rd["hand"])
    trk_b = __import__("btoken").np_mlp(pol.brainP["trk"], SB)
    si_n, tg_n, tr_n = pol.dsc22.inputs_rows(SB, XA, PP, OK, HD, trk_b, OX, np.full(len(SB), a.map))
    with torch.no_grad():
        h_t = hm.trk.trunk(TR.inp(TL, torch.from_numpy(SB), torch.from_numpy(XA)))
        trr_t = TR.readable(hm.trk.l3(h_t))
        pfn_t = (lambda g_: torch.sigmoid(hm.trk.pass_logits(h_t, torch.from_numpy(g_))).numpy()) if TL.get("pass") else None
        eo_t = torch.sigmoid(torch.from_numpy(trk_b)[:, D.TRK_OWN].float())
        sr_, tr_ = D.raw_inputs(DL, OX[0], OX[1], OX[2], OX[3], OX[4], eo_t.numpy(), trr_t.numpy(), PP, OK, HD, MS.torch_fwd(msm, "cpu"),
                                ck["map_sense"]["layout"], tabs, np.full(len(SB), a.map), pass_fn=pfn_t)
        si_t, tg_t = D.inputs(DL, torch.from_numpy(sr_), torch.from_numpy(tr_))
        S_ = torch.from_numpy(np.random.default_rng(5).normal(0, 0.5, (len(SB), int(ck["head2"]["size"]))).astype(np.float32))
        tm_t = D.term(hm.dsc, DL, S_, si_t, tg_t, 1.0, 0).numpy()
    tm_n = D.np_term(D.np_params({k_[len("head2."):]: v_.numpy() for k_, v_ in ck["model"].items() if k_.startswith("head2.")}), DL,
                     S_.numpy(), si_n, tg_n, 1.0, 0)
    d_si = float(np.abs(si_t.numpy() - si_n).max())
    d_tg = float(np.abs(tg_t.numpy() - tg_n).max())
    d_tm = float(np.abs(tm_t - tm_n).max())
    n_tm = int((tm_t != tm_n).sum())
    pc_ = [i_ for i_, n2_ in enumerate(DL["tgt"]) if n2_.startswith("pass ")]
    print("d. the pass odds in the description: torch against numpy at most {:.2e}; their spread over the places {:.3f}".format(
        float(np.abs(tg_t.numpy()[..., pc_] - tg_n[..., pc_]).max()) if pc_ else -1.0, float(np.std(tg_n[..., pc_])) if pc_ else -1.0), flush=True)
    print("d. TRAINER (torch) = READERS (numpy) on {} recorded keep readings x 17 targets: the situation's inputs differ by at most {:.2e}, the "
          "targets' by {:.2e} (half-precision steps), the term by {:.2e} ({} of {} numbers differ); the tracker's outputs by {:.2e}".format(
              len(SB), d_si, d_tg, d_tm, n_tm, tm_t.size, float(np.abs(trr_t.numpy() - tr_n).max())), flush=True)
    okd = d_tm < 0.02
    print("ALL PASSED" if (okc and okd) else "FAILED", flush=True)
    return okc and okd


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd_", required=True)
    p = sp.add_parser("sample")
    p.add_argument("--src", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--map", default="bloodrun")
    p.add_argument("--frames", type=int, default=2400)
    p.add_argument("--matches", type=int, default=8)
    p.add_argument("--ms-start", default=os.path.join(DATA, "sim_runs", "space", "mapsense_start.pt"))
    p.add_argument("--cmd", default=CMD21D)
    p = sp.add_parser("same")
    p.add_argument("--src", required=True)
    p.add_argument("--init", required=True)
    p.add_argument("--frames", required=True, help="a sample's _frames.npz")
    p.add_argument("--cmd", default=CMD21D)
    p = sp.add_parser("desc")
    p.add_argument("--init", required=True)
    p.add_argument("--work", required=True)
    p.add_argument("--map", default="bloodrun")
    p.add_argument("--frames", type=int, default=800)
    p.add_argument("--matches", type=int, default=6)
    p.add_argument("--legs", default="move_v17_look")
    p.add_argument("--skip-make", action="store_true")
    p.add_argument("--cmd", default=CMD21D)
    a = ap.parse_args()
    r = {"sample": sample, "same": same, "desc": desc}[a.cmd_](a)
    sys.exit(0 if (r is None or r) else 1)


if __name__ == "__main__":
    main()
