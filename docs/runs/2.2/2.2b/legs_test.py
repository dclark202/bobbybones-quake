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
    cmd_ = os.environ.get("LEGS_CMD") or IS.CMD22A                # (LEGS_CMD: another run's command, e.g. 2.2b's train.cmd, with its aim2_env.cmd)
    ev = IS.cmd_env(cmd_, os.environ.get("QLBOT_ROOT") or ROOT)
    ev.update(IS.cmd_env(os.path.join(os.path.dirname(cmd_), "aim2_env.cmd"), os.environ.get("QLBOT_ROOT") or ROOT))
    ev.update(dict(FIGHT="1", OUT_LIVE="1.5"))
    ev.update(dict(x_.split("=", 1) for x_ in (os.environ.get("LEGS_SET") or "").split(",") if "=" in x_))   # (e.g. win_scale: JUDGE_PAY=1, ...)
    os.environ.update(ev)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    sys.path.insert(0, os.path.join(ROOT, "plugins"))


def pass_odds(pol, sb, xa, Xc):
    """the network's own pass odds [n, FG_NC, 3] of cut off's candidates (tracker on the brain's state; desc's order norm)"""
    import tracker as TR
    import desc22 as D
    import duel_env as E
    TL = pol.h2["trk22"]
    PW, PP = TR.np_params(pol.h2W), TR.np_pass_params(pol.h2W)
    h_ = TR.np_trunk(PW, TR.np_inp(TL, sb, xa))
    if pol.h2.get("desc22") is None:                         # (a 2.2b network: the pass scorer's norm in its fight network's layout)
        import fightnet as FN
        return TR.np_pass(PP, h_, FN.pass_in(pol.fgt.L, Xc))
    ti_ = [list(E.CMB_FEAT).index(c_) for c_ in D.TGT_COLS]
    return TR.np_pass(PP, h_, D.order_norm(pol.h2["desc22"], np.asarray(Xc, np.float32)[..., ti_]))


SAMPLE = None
NEWC = None
PAY = None


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
    if os.environ.get("LEGS_LIVE"):                          # (win_scale: the pay as the trainer's workers set it: the command's pay
        sys.path.insert(0, os.path.join(ROOT, "tools", "run"))   # arguments, then the start's live.json, as the trainer applies it)
        import check_settings as CS
        _, args_ = CS.read_cmd(os.environ.get("LEGS_CMD") or IS.CMD22A)
        lv_ = json.load(open(os.environ["LEGS_LIVE"], encoding="utf-8"))
        E.live_set({k_: str(v_) for k_, v_ in lv_.items() if k_ in E.LIVE_VARS})
        f_ = lambda n_, d_: float(args_.get(n_, d_) or d_)   # noqa: E731
        env.item_reward, env.item_loss, env.intent_seek = f_("--item-reward", 0.3), f_("--item-loss", 0.5), f_("--intent-seek", 1.0)
        env.stack_p, env.near_item_p = f_("--stack-p", 0.0), f_("--near-item-p", 0.0)
        env.dmg_reward = float(lv_.get("DMG_REWARD", f_("--dmg-reward", 0.004)))
        env.dmg_taken_w = float(lv_.get("DMG_TAKEN_W", f_("--dmg-taken-w", 1.0)))
        if mp == a.maps.split(",")[0]:
            print("pay as the trainer sets it: item_reward {} item_loss {} intent_seek {} dmg_reward {} dmg_taken_w {}; live: {}".format(
                env.item_reward, env.item_loss, env.intent_seek, env.dmg_reward, env.dmg_taken_w, E.live_now()), flush=True)
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
        fx_ = None
        if getattr(pol, "fight_due", False):                 # (a 2.2b network: its fight network reads at a keep reading)
            import fight22 as F22
            fx_ = F22.reader_fx(env)
        ac, h = pol.act(np.asarray(obs)[:, idx], h, xl=xl, pose=pz, zmap=zz, kf=kf, **({"fx": fx_} if fx_ is not None else {}))
        if getattr(pol, "fgt", None) is not None:
            env.fg_score = pol.fight_scores()
            if SAMPLE is not None and fx_ is not None and pol.fg_last is not None:
                SAMPLE["fx"].append(np.asarray(pol.fg_last[1]["x"], np.float32))
        if SAMPLE is not None and t % 8 == 3:
            SAMPLE["rows"].append(np.asarray(obs, np.float32)[:, NEWC])
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
        if PAY is not None:                                  # (win_scale: the pay by part on the frames of whole games; both judges' win part)
            import fight22 as F22
            p4_ = F22.pay_parts(E, info).astype(np.float64)
            gm_ = np.asarray(env.wb_gm[:n], bool)
            wa_ = float(E.WIN_ADD)
            for k_, j_ in (("items", 0), ("fight", 1), ("win", 2), ("other", 3)):
                PAY["abs_" + k_] += float(np.abs(p4_[gm_, j_]).sum())
            for k_, x_ in (("blind", wa_ * np.asarray(env.wb_raw[:n], np.float64)), ("items_judge", wa_ * np.asarray(env.wh_raw[:n], np.float64))):
                PAY[k_][0] += float(gm_.sum())
                PAY[k_][1] += float(x_[gm_].sum())
                PAY[k_][2] += float((x_[gm_] ** 2).sum())
            PAY["frames"] += int(gm_.sum())
            pt_ = np.asarray(info["pay_terms"], np.float64)[gm_]
            for j_, k_ in enumerate(E.PAY_TERMS):                # (the ledger: each term's sum and its size, game frames)
                t_ = PAY["terms"].setdefault(k_, [0.0, 0.0, 0.0, 0.0])
                t_[0] += float(pt_[:, j_].sum())
                t_[1] += float(np.abs(pt_[:, j_]).sum())
                t_[2] += float(np.minimum(pt_[:, j_], 0.0).sum())
                t_[3] += float(np.maximum(pt_[:, j_], 0.0).sum())
            ptk_ = np.asarray(info["pay_terms"], np.float64)
            for e_ in info["events"]:
                kk_, vv_ = int(e_["killer"]), int(e_["victim"])
                if 0 <= kk_ < n and kk_ != vv_ and gm_[kk_]:
                    PAY["frags"] += 1
                    PAY["frag_win_le0"] += int(env.wh_raw[kk_] <= 0)
                    PAY["frag_total_le0"] += int(float(r_[kk_]) <= 0)
                    PAY["frag_blind_le0"] += int(env.wb_raw[kk_] <= 0)
                    fi_ = [E.PAY_TERMS.index(x_) for x_ in ("frag", "death") if x_ in E.PAY_TERMS]
                    PAY["frag_term_le0"] += int(ptk_[kk_, fi_[0]] <= 0)
                    PAY["victim_total_ge0"] += int(0 <= vv_ < n and float(r_[vv_]) >= 0)
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
    if PAY is not None:
        g_ = env._others_arr().shape[1] + 1
        for m_ in range(env.M):
            if env.game[m_]:
                PAY["margins"].append(float(env.frags_r[m_ * g_] - env.frags_r[m_ * g_ + 1]))
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
    ap.add_argument("--pay", default="", help="(win_scale) <out.json>: the pay by part on game frames, both judges' win part, frags' signs, margins")
    ap.add_argument("--sample", default="", help="(tools/fight22_init.py norm) <out.npz>: the fight network's raw inputs at its readings, the "
                                                 "hands' new columns every 8 frames (a 2.2b network from `layout`)")
    a = ap.parse_args()
    setup()
    global SAMPLE, NEWC, PAY
    if a.pay:
        PAY = dict(abs_items=0.0, abs_fight=0.0, abs_win=0.0, abs_other=0.0, blind=[0.0, 0.0, 0.0], items_judge=[0.0, 0.0, 0.0], frames=0, frags=0,
                   frag_win_le0=0, frag_total_le0=0, frag_blind_le0=0, frag_term_le0=0, victim_total_ge0=0, margins=[], terms={})
    if a.sample:
        import csv
        now_ = [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]
        NEWC = np.array([i_ for i_, (g_, _) in enumerate(now_) if g_ == "b22b fight"])
        SAMPLE = dict(fx=[], rows=[])
    import test_suite as T
    pol = T.Policy(a.policy, seed=a.seed)
    out = {}
    for mp in a.maps.split(","):
        acc = {k_: dict(trips=0, arrived=0, met=0, timeout=0, died=0, passed=0, sec=0.0, dealt=0.0, taken=0.0, applied_frames=0) for k_ in KINDS}
        acc["own"] = dict(sec=0.0, dealt=0.0, taken=0.0)
        acc["valid"] = dict(readings=0, **{k_: 0 for k_ in KINDS})
        env_m = run_map(pol, mp, a, acc)
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
    if PAY is not None:
        json.dump(PAY, open(a.pay, "w"), indent=1)
        print("pay: " + json.dumps({k_: v_ for k_, v_ in PAY.items() if k_ not in ("margins", "terms")}))
    if SAMPLE is not None:
        np.savez_compressed(a.sample, fx=np.concatenate(SAMPLE["fx"]) if SAMPLE["fx"] else np.zeros((0, 0), np.float32),
                            rows=np.concatenate(SAMPLE["rows"]))
        print("sample: {} readings, {} rows -> {}".format(sum(len(x_) for x_ in SAMPLE["fx"]), sum(len(x_) for x_ in SAMPLE["rows"]), a.sample))
    for k_ in KINDS + ("own", "valid"):
        print(k_, json.dumps(tot[k_]))


if __name__ == "__main__":
    main()
