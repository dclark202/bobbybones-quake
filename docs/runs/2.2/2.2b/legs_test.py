"""2.2b, the build's first test (CARD.md red team, last row; the brief: "do his legs take him to a fight option?"): the start network (2.2a's
update 90) plays every seat of a few matches in the simulator (2.2a's settings, FIGHT=1, OUT_LIVE=1.5) through test_suite.Policy, his own
network driving every frame (nothing else moves him). At a keep reading a seat not on a trip is sent, with chance --p, on a fight option
valid for it at that moment (the four dealt evenly among the valid ones): the target "the enemy" with the option's kind and candidate in the
keep column, cut off's place the candidate of highest pass odds at 2 or 4 s (the network's own tracker on its brain's state) among those he
reaches before the enemy, an angle's the same place's standing point. The option is held until he arrives, meets the enemy (in view) or 4 s
pass, then his own choices resume. Per option: trips, arrived, met the enemy, timed out, died, the enemy passed the place; damage dealt and
taken a second on the trips against the same seats' own choices.

    QLBOT_ROOT=<checkout with data> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2b/legs_test.py <policy.pt> <out.json>
        [--maps bloodrun,aerowalk] [--frames 4000] [--matches 16] [--p 0.12]
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, HERE)
import ident_sim as IS  # noqa: E402

DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")
KINDS = ("him", "cut", "angle", "away")


def setup():
    ev = IS.cmd_env(IS.CMD22A, os.environ.get("QLBOT_ROOT") or ROOT)
    ev.update(IS.cmd_env(os.path.join(ROOT, "docs", "runs", "2.2", "2.2a", "aim2_env.cmd"), os.environ.get("QLBOT_ROOT") or ROOT))
    ev.update(dict(FIGHT="1", OUT_LIVE="1.5"))
    os.environ.update(ev)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    sys.path.insert(0, os.path.join(ROOT, "plugins"))


def pass_odds(pol, sb, xa, Xc):
    """the network's own pass odds [n, FG_NC, 3] of cut off's candidates (tracker on the brain's state; desc's order norm)"""
    import tracker as TR
    import desc22 as D
    import duel_env as E
    TL, DL = pol.h2["trk22"], pol.h2["desc22"]
    PW, PP = TR.np_params(pol.h2W), TR.np_pass_params(pol.h2W)
    h_ = TR.np_trunk(PW, TR.np_inp(TL, sb, xa))
    ti_ = [list(E.CMB_FEAT).index(c_) for c_ in D.TGT_COLS]
    return TR.np_pass(PP, h_, D.order_norm(DL, np.asarray(Xc, np.float32)[..., ti_]))


def run_map(pol, mp, a, acc):
    import importlib
    import btoken as BT
    import head2 as H2
    import test_suite as T
    E = importlib.import_module("duel_env_ffa")
    import csv
    now = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
    idx = np.array([now.index(tuple(x_)) for x_ in pol.names])
    nav_ = os.path.join(DATA, "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(DATA, "maps", mp + ".bsp"), n_matches=a.matches, seed=a.seed, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    T.set_delays(E, env, [(np.arange(0, env.n), pol.react_ms, pol.acquire_ms)])
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
    if getattr(E, "BRAIN_READ", False):
        env.set_brain_g(np.full(env.n, pol.rfg if getattr(pol, "rf_read", False) else 0.0, np.float32))
        env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))
    rng = np.random.default_rng(a.seed + 5)
    n = env.n
    obs = env.observe()
    h = pol.zeros(n)
    trip_k = np.full(n, -1, np.int64)                       # the option a seat is sent on (-1: his own choices)
    trip_c = np.zeros(n, np.int64)
    trip_t = np.zeros(n, np.int64)
    met = np.zeros(n, bool)
    out_ = np.zeros(n, bool)                                 # (the enemy has been out of view since the trip began)
    F = None
    dl0 = np.asarray(env.dmg_life[:n], np.float64).copy()
    st0 = (np.asarray(env.hp[:n], np.float64) + np.asarray(env.armor[:n], np.float64)).copy()
    for t in range(a.frames):
        kf = H2.np_kf_end(env)
        pz, zz = BT.pose_from_env(env, mp)
        xl = env.legs_prep() if pol.needs_xl else None
        kr = None if pol.k_r is None else np.asarray(pol.k_r, bool).copy()
        ac, h = pol.act(np.asarray(obs)[:, idx], h, xl=xl, pose=pz, zmap=zz, kf=kf)
        nA = len(E.ACTION_DIMS)
        act = np.concatenate([ac[:, :nA], ac[:, -1:]], 1)
        if kr is not None and kr.any():                      # a keep reading: the candidates (after the frame before), new trips dealt
            F = env.fight_feat()
            br_, tk_ = BT.unpack(pol.brainP, pol.btok, h[:, pol.brain_at:])
            po_ = pass_odds(pol, np.asarray(br_.s, np.float32), pol.norm(np.asarray(obs)[:, idx]), F["Xc"])
            sc_ = np.where(F["vc"], np.maximum(po_[..., 1], po_[..., 2]), -1.0)
            cbest = sc_.argmax(1)
            ar_ = np.arange(n)
            vis0_ = np.asarray(env.visible, bool)[:n]
            valid = np.stack([F["vh"] & ~vis0_, F["vc"][ar_, cbest] & ~vis0_, F["vs"][ar_, cbest] & ~vis0_, F["va"]], 1) & (np.asarray(env.hp[:n]) > 0)[:, None]
            al_ = kr & (np.asarray(env.hp[:n]) > 0) & (env.script[:n] == 0)
            acc["valid"]["readings"] += int(al_.sum())
            for j_, k_ in enumerate(KINDS):
                acc["valid"][k_] += int((valid[:, j_] & al_).sum())
            new_ = kr & (trip_k < 0) & valid.any(1) & (rng.random(n) < a.p) & (env.script[:n] == 0)
            for i in np.nonzero(new_)[0]:
                k_ = int(rng.choice(np.nonzero(valid[i])[0]))
                trip_k[i], trip_c[i], trip_t[i], met[i], out_[i] = k_, int(cbest[i]), 0, False, not vis0_[i]
                acc[KINDS[k_]]["trips"] += 1
        on_ = trip_k >= 0
        if on_.any():
            act[on_, 10] = E.EN_INTENT
            act[on_, -1] = act[on_, -1] + E.FG_ASK + E.FG_KIND * trip_k[on_] + E.FG_CAND * trip_c[on_]
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
            env.legs_lg = pol.legs_logits(env.legs_prep())
        an_ = pol.brain_answer(h)
        if an_ is not None:
            env.brain_in({k_: an_[k_] for k_ in ("bel", "ok", "band", "ztop") if k_ in an_})
        obs, r_, done, info = env.step(act)
        fs = env.fg_state()
        dl1 = np.asarray(env.dmg_life[:n], np.float64)
        st1 = np.asarray(env.hp[:n], np.float64) + np.asarray(env.armor[:n], np.float64)
        dealt = np.maximum(dl1 - dl0, 0.0)
        taken = np.maximum(st0 - st1, 0.0)
        dl0, st0 = dl1.copy(), st1.copy()
        d = np.asarray(done, bool)
        own = (trip_k < 0) & (env.script[:n] == 0)
        acc["own"]["sec"] += float(own.sum()) * 0.025
        acc["own"]["dealt"] += float(dealt[own].sum())
        acc["own"]["taken"] += float(taken[own].sum())
        for i in np.nonzero(trip_k >= 0)[0]:
            k_ = KINDS[trip_k[i]]
            A = acc[k_]
            A["sec"] += 0.025
            A["dealt"] += float(dealt[i])
            A["taken"] += float(taken[i])
            trip_t[i] += 1
            on_k = int(fs[i, 0]) == trip_k[i] + 1
            A["applied_frames"] += int(on_k)
            if fs[i, 2] > 0 and out_[i]:                    # (met: the enemy in view after being out of view during the trip)
                met[i] = True
            if fs[i, 2] <= 0:
                out_[i] = True
            end = None
            if d[i] or fs[i, 5] <= 0:
                end = "died"
            elif on_k and fs[i, 1] > 0 and not met[i]:
                end = "arrived"
            elif met[i]:
                end = "met"
            elif trip_t[i] >= 160:
                end = "timeout"
            if end is not None:
                if os.environ.get("LEGS_DEBUG") and k_ == "away" and end == "arrived" and A["arrived"] < 5:
                    print("DEBUG away arrived: t", trip_t[i], "intent_t", float(env.intent_t[i]), "out_qt", float(env.out_qt[i]), "cmb_k", int(env.cmb_k[i]),
                          "fgt_k", int(env.fgt_k[i]), "arr", bool(env.intent_arr[i]), "done", bool(env.intent_done[i]), "intent", int(env.intent[i]), flush=True)
                A[end] += 1
                A["passed"] += int(fs[i, 3] > 0)
                trip_k[i] = -1
        if d.any():
            pol.clear(h, d)
    return acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("policy")
    ap.add_argument("out")
    ap.add_argument("--maps", default="bloodrun,aerowalk,toxicity")
    ap.add_argument("--frames", type=int, default=4000)
    ap.add_argument("--matches", type=int, default=16)
    ap.add_argument("--p", type=float, default=0.12)
    ap.add_argument("--seed", type=int, default=21)
    a = ap.parse_args()
    setup()
    import test_suite as T
    pol = T.Policy(a.policy, seed=a.seed)
    out = {}
    for mp in a.maps.split(","):
        acc = {k_: dict(trips=0, arrived=0, met=0, timeout=0, died=0, passed=0, sec=0.0, dealt=0.0, taken=0.0, applied_frames=0) for k_ in KINDS}
        acc["own"] = dict(sec=0.0, dealt=0.0, taken=0.0)
        acc["valid"] = dict(readings=0, **{k_: 0 for k_ in KINDS})
        run_map(pol, mp, a, acc)
        out[mp] = acc
        print(mp, json.dumps(acc), flush=True)
    tot = {k_: {} for k_ in KINDS + ("own", "valid")}
    for k_ in tot:
        for mp in out:
            for q_, v_ in out[mp][k_].items():
                tot[k_][q_] = tot[k_].get(q_, 0) + v_
    for k_ in KINDS:
        A = tot[k_]
        A["reached_or_met"] = round((A["arrived"] + A["met"]) / max(1, A["trips"] - A.get("open", 0)), 3)
        A["dealt_per_s"] = round(A["dealt"] / max(1e-9, A["sec"]), 2)
        A["taken_per_s"] = round(A["taken"] / max(1e-9, A["sec"]), 2)
    tot["own"]["dealt_per_s"] = round(tot["own"]["dealt"] / max(1e-9, tot["own"]["sec"]), 2)
    tot["own"]["taken_per_s"] = round(tot["own"]["taken"] / max(1e-9, tot["own"]["sec"]), 2)
    json.dump(dict(maps=out, total=tot, args=vars(a)), open(a.out, "w"), indent=1)
    for k_ in KINDS + ("own", "valid"):
        print(k_, json.dumps(tot[k_]))


if __name__ == "__main__":
    main()
