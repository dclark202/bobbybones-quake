"""The yardstick for the lesson of his legs (stage C part 1, docs/design/V02_STAGE_C.md): how often the movement network
agrees with itself, beside how often he agrees with it.

    set the run's switches (the `set` lines of its .cmd: LEGS=1, LEGS_EVERY, LEGS_OFF, ...), then
    python tools/legs_agree.py --map bloodrun --policy data/sim_runs/<run>/policy.pt [--steps 1500] [--legs move_v15n]

The plan weans his switch once "his own choice is the label's about as often as two runs of the movement network agree
with each other". The label of a frame is a SAMPLE of the movement network's choices (sim/duel_env.py, _move_labels:
sampled unless TEACH_BEST=1, then its likeliest choice and every number here is 100%), so two things are measured on
the frames his legs carry him, by output (forward and back, sideways, jump and crouch, the view's turn):
  two_samples      a second sample of the movement network's choices, made from the same inputs, is the label's
                   (its own noise level; what the trainer's legs_teach.p_label reaches when his output is the movement
                   network's, chance for chance)
  best_is_sample   the movement network's likeliest choice is the label's (the most the trainer's legs_teach.agree can
                   reach: nobody's likeliest choice agrees with a sampled label more often than its own maker's)
and of the network that plays (every seat is his; he chooses his legs as in a game):
  his_best, his_p  his own likeliest choice is the label's, and the chance his output gives the label: the trainer's
                   legs_teach.agree and legs_teach.p_label, before any lesson
The three key outputs are counted on the frames his hand reads them (one in four: the trainer's lesson counts them
there only; on the other frames the movement network's key choice is never used), the view's turn on every frame; the
keys on all frames are given beside them. The simulator is not changed: the label's maker is called three times on a
frame (the extra calls draw random numbers, so this is not a fixed run of anything). One JSON line a map; low priority,
one process, no graphics card."""
import argparse
import ctypes
import json
import os
import sys

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "2")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")           # (not an empty string: on Windows that hides nothing)
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sim")
NAMES = ("forward", "sideways", "jump", "turn")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--policy", required=True)
    ap.add_argument("--steps", type=int, default=1500, help="frames (40 a second)")
    ap.add_argument("--players", type=int, default=48)
    ap.add_argument("--group", type=int, default=2)
    ap.add_argument("--legs", default="move_v15n", help="the movement run whose policy.npz is his legs")
    ap.add_argument("--kind-p", default="0.829,0,0.171,0", help="the rounds' kinds, as the run has them")
    ap.add_argument("--drill-weapons", default="rl,rl,rl,rl,pg,pg,gl,gl,sg")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    if os.name == "nt":
        k32_ = ctypes.windll.kernel32                         # (with ctypes' default types the handle is cut to 32 bits and the call fails silently)
        k32_.GetCurrentProcess.restype = ctypes.c_void_p
        k32_.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k32_.SetPriorityClass(k32_.GetCurrentProcess(), 0x4000)
    sys.path.insert(0, SIM)
    import numpy as np
    import duel_env_ffa as E
    import test_suite as T
    assert os.path.normcase(os.path.dirname(os.path.abspath(E.__file__))) == os.path.normcase(SIM), E.__file__
    assert E.LEGS, "set the run's switches first (LEGS=1 and the rest of its .cmd)"
    pol = T.Policy(a.policy, seed=a.seed)
    assert len(pol.dims) > E.LEGS_HEAD, "this network has no switch to his legs"
    for mp in a.map.split(","):                               # (one map a process is the rule for the simulator: give one map)
        env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=max(1, a.players // a.group), seed=a.seed,
                        nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp)), close_p=1.0, loadout="all",
                        teacher=os.path.join(ROOT, "data", "sim_runs", a.legs, "policy.npz"), group=a.group)
        assert env.teacher is not None, "no movement network at data/sim_runs/{}/policy.npz".format(a.legs)
        env.item_reward, env.intent_seek, env.item_loss, env.dmg_reward, env.dmg_taken_w = 0.75, 1.0, 0.5, 0.005, 1.0
        env.react_frames, env.acquire_frames = round(pol.react_ms / 25), 8
        env.kind_p, env.bot_p = tuple(float(x_) for x_ in a.kind_p.split(",")), 0.0
        env.loadout_p = (0.0, 1.0, 0.0, 0.0)
        env.drill_weapons = tuple(E.WEAPONS.index(w_) for w_ in a.drill_weapons.split(","))
        env.close_p, env.round_len = 0.0, 120.0
        env.round_t[:] = 1e9
        n = env.n
        best_was = bool(E.TEACH_BEST)
        cap = dict(b=np.full((n, 4), -1, np.int64), c=np.full((n, 4), -1, np.int64))
        orig = E.DuelEnv._move_labels

        def thrice(self, ri, R, land=False, k=None, into=None):
            """his legs' labels: a second sample and the likeliest choice are kept beside the one that moves him"""
            if into is None:
                return orig(self, ri, R, land=land, k=k, into=into)
            b_, c_ = np.full_like(into, -1), np.full_like(into, -1)
            orig(self, ri, R, land=land, k=k, into=b_)
            E.TEACH_BEST = True
            try:
                orig(self, ri, R, land=land, k=k, into=c_)
            finally:
                E.TEACH_BEST = best_was
            orig(self, ri, R, land=land, k=k, into=into)
            got = b_[:, 0] >= 0
            cap["b"][got], cap["c"][got] = b_[got], c_[got]
        E.DuelEnv._move_labels = thrice
        spy = {}
        lk_ = env.limit_keys

        def keys_spy(a_, who=None):                           # (the actions after _legs_step: what his legs put in place of his own)
            spy["a"] = a_.copy()
            return lk_(a_, who)
        env.limit_keys = keys_spy
        obs, _, _, _ = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
        h = pol.zeros(n)
        cut = np.cumsum([0] + list(pol.dims))
        S = {k_: np.zeros((2, 4)) for k_ in ("n", "two", "best", "his_best", "his_p", "his_sample")}       # rows: the trainer's frames, every frame
        fr, on_fr, sp_on = 0, 0, 0.0
        for _ in range(a.steps):
            act, h = pol.act(obs, h)
            lg = h @ pol.wp.T + pol.bp                        # (his outputs for this frame, from his memory after it)
            cap["b"][:], cap["c"][:] = -1, -1
            own = (env.script == 0) & (env.hp > 0)
            sp = np.hypot(env.state[:, 3], env.state[:, 4])
            obs, r, d, info = env.step(act)
            h[np.asarray(d) > 0] = 0.0
            on = env.legs_on & (cap["b"][:, 0] >= 0)
            lab = spy["a"][:, :4]                             # on those frames: the movement network's sample that moved him
            fr += int(own.sum())
            on_fr += int(on.sum())
            sp_on += float(sp[on].sum())
            for j in range(4):
                l_ = lg[:, cut[j]:cut[j + 1]]
                p_ = np.exp(l_ - l_.max(1, keepdims=True))
                p_ /= p_.sum(1, keepdims=True)
                for row, m in ((0, on & (env.key_dec if j < 3 else True)), (1, on)):
                    lj = lab[m, j]
                    S["n"][row, j] += int(m.sum())
                    S["two"][row, j] += int((cap["b"][m, j] == lj).sum())
                    S["best"][row, j] += int((cap["c"][m, j] == lj).sum())
                    S["his_best"][row, j] += int((l_[m].argmax(1) == lj).sum())
                    S["his_p"][row, j] += float(p_[m, lj].sum())
                    S["his_sample"][row, j] += int((act[m, j] == lj).sum())
        E.DuelEnv._move_labels = orig

        def by(key, row):
            return dict(zip(NAMES, [round(float(x_), 4) for x_ in S[key][row] / np.maximum(1.0, S["n"][row])]))
        print(json.dumps(dict(map=mp, policy=os.path.basename(os.path.dirname(os.path.abspath(a.policy))) + "/" + os.path.basename(a.policy), legs=a.legs,
                              labels="the likeliest choice (TEACH_BEST=1): every number is 100%" if best_was else "sampled",
                              player_min=round(fr * E.DT / 60.0, 1), on_legs=round(on_fr / max(1, fr), 4), speed_on_legs=round(sp_on / max(1, on_fr)),
                              frames=dict(zip(NAMES, [int(x_) for x_ in S["n"][0]])),
                              two_samples=by("two", 0), best_is_sample=by("best", 0),
                              his_best=by("his_best", 0), his_p=by("his_p", 0), his_sample=by("his_sample", 0),
                              keys_on_every_frame=dict(frames=int(S["n"][1, 0]), two_samples=by("two", 1), best_is_sample=by("best", 1),
                                                       his_best=by("his_best", 1), his_p=by("his_p", 1)))), flush=True)


if __name__ == "__main__":
    main()
