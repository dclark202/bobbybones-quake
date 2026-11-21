"""2.2d's plays of the start in the simulator (2.2c's play22c.py with 2.2d's command: its `set` lines and aim2_env.cmd; the start's live.json for the live names), every
seat played by the checks' player (sim/test_suite.py Policy: the brain and its answer WITH the places ahead, the held draw, the pull, the lever
as the trainer plays them), whole games on the ten maps:

    sample <policy.pt> <out.npz> [--maps ...] [--frames 2000] [--matches 16]
        the hands' new inputs "b22c ahead" (13 columns of the full list) on every living seat's frames: tools/inputs22c.py stats' rows
    ident <old.pt> <new.pt> [--maps bloodrun,toxicity] [--frames 1200] [--matches 16]
        THE START ANSWERS AS 2.2a's UPDATE 90: <old> plays every seat (its places ahead sent: the new columns real), every frame recorded; then <old>
        and <new> replay the recording from the same seeds; <new> also at the lever's share 1 (its last layer at zero: the same). PASS: 0 differ
    pay <policy.pt> <out.json> [--maps ...] [--frames 4000] [--matches 16]
        the pay by term and by learner on game frames (2.2c's split, FIGHT_SPLIT=22c), the win part under both judges, frags' signs, margins:
        docs/runs/2.2/2.2d/win_scale.py's input (as 2.2b's legs_test.py --pay); and the contest pay's counters (stats["contest"])
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2d/play22d.py <cmd> ...
    (PLAY_CMD=<a command> plays under another command; PLAY_LIVE=<live.json> lays a live file over it; PLAY_SET=NAME=v,... more)"""
import argparse
import csv
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DATA = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data")
CMD = os.environ.get("PLAY_CMD") or os.path.join(HERE, "train.cmd")
MAPS10 = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure"


def cmd_env(path, root):
    out = {}
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*set\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$", ln.rstrip("\r\n"), re.I)
        if m and m.group(1) not in ("ROOT", "GPU_MEM_FRACTION", "TRAINER_MASK", "LEARN"):
            out[m.group(1)] = m.group(2).replace("%ROOT%", root).replace("%~dp0..\\..\\..\\..", root)
    return out


def setup():
    root_ = os.environ.get("QLBOT_ROOT") or ROOT
    ev = cmd_env(CMD, root_)
    ev.update(cmd_env(os.path.join(os.path.dirname(CMD), "aim2_env.cmd"), root_))
    ev.update(dict(x_.split("=", 1) for x_ in (os.environ.get("PLAY_SET") or "").split(",") if "=" in x_))
    os.environ.update(ev)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))


def make_env(mp, matches, seed, pol):
    import importlib
    import test_suite as T
    E = importlib.import_module("duel_env_ffa")
    nav_ = os.path.join(DATA, "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(DATA, "maps", mp + ".bsp"), n_matches=matches, seed=seed, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    T.set_delays(E, env, [(np.arange(0, env.n), pol.react_ms, pol.acquire_ms)])
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
    if os.environ.get("PLAY_LIVE"):                          # (the pay as the trainer's workers set it: the command's arguments, then the live file)
        import check_settings as CS
        _, args_ = CS.read_cmd(CMD)
        lv_ = json.load(open(os.environ["PLAY_LIVE"], encoding="utf-8"))
        E.live_set({k_: str(v_) for k_, v_ in lv_.items() if k_ in E.LIVE_VARS})
        f_ = lambda n_, d_: float(args_.get(n_, d_) or d_)   # noqa: E731
        env.item_reward, env.item_loss, env.intent_seek = f_("--item-reward", 0.3), f_("--item-loss", 0.5), f_("--intent-seek", 1.0)
        env.stack_p, env.near_item_p = f_("--stack-p", 0.0), f_("--near-item-p", 0.0)
        env.dmg_reward = float(lv_.get("DMG_REWARD", f_("--dmg-reward", 0.004)))
        env.dmg_taken_w = float(lv_.get("DMG_TAKEN_W", f_("--dmg-taken-w", 1.0)))
    if getattr(E, "BRAIN_READ", False):
        env.set_brain_g(np.full(env.n, pol.rfg if getattr(pol, "rf_read", False) else 0.0, np.float32))
        env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))
    return E, env


def full_names():
    return [(r_["group"], r_["input"]) for r_ in csv.DictReader(open(os.path.join(ROOT, "docs", "INPUTS.csv"), encoding="utf-8"))]


def frame(E, env, pol, obs, h, idx, mp, rec=None):
    """one frame of every seat by pol: -> (act, h)"""
    import btoken as BT
    import head2 as H2
    import fight22 as F22
    kf = H2.np_kf_end(env)
    pz, zz = BT.pose_from_env(env, mp)
    xl = env.legs_prep() if pol.needs_xl else None
    fx = F22.reader_fx(env) if getattr(pol, "fight_due", False) else None
    if rec is not None:
        rec.append(dict(obs=np.asarray(obs, np.float32).copy(), kf=kf.copy(), pz=pz.copy(), zz=np.asarray(zz).copy(),
                        xl=None if xl is None else xl.copy(), fx=fx))
    ac, h = pol.act(np.asarray(obs)[:, idx], h, xl=xl, pose=pz, zmap=zz, kf=kf, **({"fx": fx} if fx is not None else {}))
    if getattr(pol, "fgt", None) is not None and hasattr(env, "fg_score"):
        fs_ = pol.fight_scores()
        env.fg_score = fs_ if fs_ is not None else np.zeros((env.n, 4), np.float32)
    nA = len(E.ACTION_DIMS)
    act = np.concatenate([ac[:, :nA], ac[:, -1:]], 1)
    if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
        env.legs_lg = pol.legs_logits(env.legs_prep())
    an_ = pol.brain_answer(h)
    if an_ is not None:
        env.brain_in({k_: an_[k_] for k_ in ("bel", "ok", "band", "ztop", "fut") if k_ in an_})
    return act, h


def sample(a):
    setup()
    import test_suite as T
    now = full_names()
    ah_ = [j_ for j_, (g_, _) in enumerate(now) if g_ == "b22c ahead"]
    assert len(ah_) == 13
    rows = []
    for mp in a.maps.split(","):
        pol = T.Policy(a.policy, seed=a.seed)
        pol.ahead_in = True
        idx = np.array([now.index(tuple(x_)) for x_ in pol.names])
        E, env = make_env(mp, a.matches, a.seed, pol)
        obs = env.observe()
        h = pol.zeros(env.n)
        for t in range(a.frames):
            act, h = frame(E, env, pol, obs, h, idx, mp)
            obs, r_, done, info = env.step(act)
            if t % 4 == 1:
                al_ = np.asarray(env.hp[:env.n]) > 0
                rows.append(np.asarray(obs, np.float32)[al_][:, ah_])
            d = np.asarray(done, bool)
            if d.any():
                pol.clear(h, d)
        X = np.concatenate(rows)
        print("{}: {} rows so far; answer share {:.3f}; |1 s forward| mean {:.3f}".format(mp, len(X), float(X[:, 12].mean()), float(np.abs(X[:, 0]).mean())), flush=True)
    X = np.concatenate(rows)
    np.savez_compressed(a.out, ahead=X)
    print("wrote {}: {} rows x {} columns (the brain's places ahead), {} maps x {} frames x {} seats".format(a.out, len(X), X.shape[1], len(a.maps.split(",")), a.frames, 2 * a.matches))


def ident(a):
    setup()
    import test_suite as T
    now = full_names()
    tot = diff = kd = diff1 = 0
    lmax = hmax = 0.0
    ahv_ = 0.0
    ah_ = [j_ for j_, (g_, _) in enumerate(now) if g_ == "b22c ahead"]
    for mp in a.maps.split(","):
        pol = T.Policy(a.old, seed=a.seed)
        pol.ahead_in = True                                  # (2.2a's network has the readout ahead: its places sent, the new columns real)
        idx = np.array([now.index(tuple(x_)) for x_ in pol.names])
        E, env = make_env(mp, a.matches, a.seed, pol)
        obs = env.observe()
        h = pol.zeros(env.n)
        rec = []
        for t in range(a.frames):
            act, h = frame(E, env, pol, obs, h, idx, mp, rec)
            obs, r_, done, info = env.step(act)
            rec[-1]["done"] = np.asarray(done, bool).copy()
            d = np.asarray(done, bool)
            if d.any():
                pol.clear(h, d)
        ahv_ = max(ahv_, float(np.abs(np.stack([f_["obs"][:, ah_] for f_ in rec])).max()))
        outs = []
        for nm_, g_ in (("old", None), ("new", None), ("new", 1.0)):
            p_ = T.Policy(a.old if nm_ == "old" else a.new, seed=a.seed + 1)
            if g_ is not None:
                p_.set_fight(g=g_)
            ix_ = np.array([now.index(tuple(x_)) for x_ in p_.names])
            hh = p_.zeros(len(rec[0]["obs"]))
            o_, l_, hs_ = [], [], []
            for f_ in rec:
                kw = {"fx": f_["fx"]} if (getattr(p_, "fight_due", False) and f_["fx"] is not None) else {}
                ac, hh = p_.act(f_["obs"][:, ix_], hh, xl=f_["xl"], pose=f_["pz"], zmap=f_["zz"], kf=f_["kf"], **kw)
                o_.append(ac.copy())
                l_.append(np.asarray(p_.last_logits, np.float32).copy())
                hs_.append(hh[:, :p_.H].copy())
                if f_["done"].any():
                    p_.clear(hh, f_["done"])
            outs.append((o_, l_, hs_))
        (o1, l1, h1), (o2, l2, h2), (o3, _, _) = outs
        for x_, y_, z_, la_, lb_, ha_, hb_ in zip(o1, o2, o3, l1, l2, h1, h2):
            tot += x_[:, :-1].size
            diff += int((x_[:, :-1] != y_[:, :-1]).sum())
            diff1 += int((x_[:, :-1] != z_[:, :-1]).sum())
            kd += int((x_[:, -1] != y_[:, -1]).sum())
            lmax = max(lmax, float(np.abs(la_ - lb_).max()))
            hmax = max(hmax, float(np.abs(ha_ - hb_).max()))
        print("{}: {} frames x {} seats; differ so far {} of {} (at the lever's share 1: {}); keep columns {}; largest logit difference {:.3g}; memory "
              "{:.3g}; the new columns' largest |value| in the recording {:.3g}".format(mp, a.frames, len(rec[0]["obs"]), diff, tot, diff1, kd, lmax, hmax, ahv_), flush=True)
    print("ident: actions that differ {} of {} (the lever's share 1: {}); keep columns that differ {}; the largest logit difference {:.3g}; the largest "
          "memory difference {:.3g}; the new columns were real (largest |value| {:.3g})".format(diff, tot, diff1, kd, lmax, hmax, ahv_))
    ok_ = diff == 0 and kd == 0 and diff1 == 0 and ahv_ > 0
    print("ALL PASSED" if ok_ else "FAILED")
    sys.exit(0 if ok_ else 1)


def pay(a):
    setup()
    import test_suite as T
    now = full_names()
    P = dict(abs_items=0.0, abs_fight=0.0, abs_win=0.0, abs_other=0.0, blind=[0.0, 0.0, 0.0], items_judge=[0.0, 0.0, 0.0], frames=0, frags=0, rail_would=None, free_see=None,
             frag_term_le0=0, frag_total_le0=0, frag_win_le0=0, frag_blind_le0=0, victim_total_ge0=0, margins=[], terms={}, contest=None, rail_chain=None,
             contest_burst=None)
    import fight22 as F22
    assert F22.SPLIT == "22c", "FIGHT_SPLIT=22c expected (2.2d's command, as 2.2c's)"
    for mp in a.maps.split(","):
        pol = T.Policy(a.policy, seed=a.seed)
        idx = np.array([now.index(tuple(x_)) for x_ in pol.names])
        E, env = make_env(mp, a.matches, a.seed, pol)
        n = env.n
        obs = env.observe()
        h = pol.zeros(n)
        for t in range(a.frames):
            act, h = frame(E, env, pol, obs, h, idx, mp)
            obs, r_, done, info = env.step(act)
            p4_ = F22.pay_parts(E, info).astype(np.float64)
            gm_ = np.asarray(env.wb_gm[:n], bool)
            wa_ = float(E.WIN_ADD)
            for k_, j_ in (("items", 0), ("fight", 1), ("win", 2), ("other", 3)):
                P["abs_" + k_] += float(np.abs(p4_[gm_, j_]).sum())
            for k_, x_ in (("blind", wa_ * np.asarray(env.wb_raw[:n], np.float64)), ("items_judge", wa_ * np.asarray(env.wh_raw[:n], np.float64))):
                P[k_][0] += float(gm_.sum())
                P[k_][1] += float(x_[gm_].sum())
                P[k_][2] += float((x_[gm_] ** 2).sum())
            P["frames"] += int(gm_.sum())
            pt_ = np.asarray(info["pay_terms"], np.float64)[gm_]
            for j_, k_ in enumerate(E.PAY_TERMS):
                t_ = P["terms"].setdefault(k_, [0.0, 0.0, 0.0, 0.0])
                t_[0] += float(pt_[:, j_].sum())
                t_[1] += float(np.abs(pt_[:, j_]).sum())
                t_[2] += float(np.minimum(pt_[:, j_], 0.0).sum())
                t_[3] += float(np.maximum(pt_[:, j_], 0.0).sum())
            ptk_ = np.asarray(info["pay_terms"], np.float64)
            fi_ = [E.PAY_TERMS.index(x_) for x_ in ("frag", "death") if x_ in E.PAY_TERMS]
            for e_ in info["events"]:
                kk_, vv_ = int(e_["killer"]), int(e_["victim"])
                if 0 <= kk_ < n and kk_ != vv_ and gm_[kk_]:
                    P["frags"] += 1
                    P["frag_win_le0"] += int(env.wh_raw[kk_] <= 0)
                    P["frag_total_le0"] += int(float(r_[kk_]) <= 0)
                    P["frag_blind_le0"] += int(env.wb_raw[kk_] <= 0)
                    P["frag_term_le0"] += int(ptk_[kk_, fi_[0]] <= 0)
                    P["victim_total_ge0"] += int(0 <= vv_ < n and float(r_[vv_]) >= 0)
            d = np.asarray(done, bool)
            if d.any():
                pol.clear(h, d)
        g_ = env._others_arr().shape[1] + 1
        for m_ in range(env.M):
            if env.game[m_]:
                P["margins"].append(float(env.frags_r[m_ * g_] - env.frags_r[m_ * g_ + 1]))
        for k_ in ("contest", "rail_chain", "contest_burst", "rail_would", "free_see"):
            v_ = env.stats.get(k_)
            if v_ is not None:
                P[k_] = (np.asarray(P[k_]) + np.asarray(v_)).tolist() if P[k_] is not None else np.asarray(v_).tolist()
        print("{}: game frames so far {}; frags {}; items {:.2f} fight {:.2f} win {:.2f}".format(mp, P["frames"], P["frags"], P["abs_items"], P["abs_fight"], P["abs_win"]), flush=True)
    P["odd"] = []
    json.dump(P, open(a.out, "w", encoding="utf-8"))
    print("wrote " + a.out)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("sample")
    p.add_argument("policy")
    p.add_argument("out")
    p.add_argument("--maps", default=MAPS10)
    p.add_argument("--frames", type=int, default=2000)
    p.add_argument("--matches", type=int, default=16)
    p.add_argument("--seed", type=int, default=41)
    p = sp.add_parser("ident")
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--maps", default="bloodrun,toxicity")
    p.add_argument("--frames", type=int, default=1200)
    p.add_argument("--matches", type=int, default=16)
    p.add_argument("--seed", type=int, default=31)
    p = sp.add_parser("pay")
    p.add_argument("policy")
    p.add_argument("out")
    p.add_argument("--maps", default=MAPS10)
    p.add_argument("--frames", type=int, default=4000)
    p.add_argument("--matches", type=int, default=16)
    p.add_argument("--seed", type=int, default=51)
    a = ap.parse_args()
    {"sample": sample, "ident": ident, "pay": pay}[a.cmd](a)


if __name__ == "__main__":
    main()
