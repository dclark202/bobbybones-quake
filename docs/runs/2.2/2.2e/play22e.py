"""2.2e's plays of the start in the simulator: 2.2d's play22d.py (sample, ident, pay; every seat played by the checks' player) under 2.2e's command
(train.cmd and aim2_env.cmd: AIM4 for every seat) with two differences, each said:
  the delays    every seat at the command's --react-ms / --acquire-ms (aim4: 100 / 175 ms), not the network file's own (the start file carries
                2.2a's 125 / 225: it was trained under aim3); PLAY_DELAYS=react,acquire plays others (the ident proof: 125,225)
  the drill     RDRILL_P 0 in these plays (whole games only: the judge's and the pay's measurement is on the start's games; the checks never play a
                drill), whatever the live file says
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2e/play22e.py {sample|ident|pay} ...   (play22d's arguments)
    (PLAY_CMD=<a command> plays under another command; PLAY_LIVE=<live.json> lays a live file over it; PLAY_SET=NAME=v,... more)"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("PLAY_CMD", os.path.join(HERE, "train.cmd"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "2.2d"))
import play22d as P  # noqa: E402


def delays():
    if os.environ.get("PLAY_DELAYS"):
        r_, q_ = (float(x_) for x_ in os.environ["PLAY_DELAYS"].split(","))
        return r_, q_
    sys.path.insert(0, os.path.join(P.ROOT, "tools", "run"))
    import check_settings as CS
    _, a_ = CS.read_cmd(P.CMD)
    return float(a_["--react-ms"]), float(a_["--acquire-ms"])


def make_env(mp, matches, seed, pol):
    """play22d's, with the command's delays for every seat and no drill"""
    import importlib
    import test_suite as T
    E = importlib.import_module("duel_env_ffa")
    nav_ = os.path.join(P.DATA, "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(P.DATA, "maps", mp + ".bsp"), n_matches=matches, seed=seed, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
    rm_, am_ = delays()
    T.set_delays(E, env, [(np.arange(0, env.n), rm_, am_)])
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
    if os.environ.get("PLAY_LIVE"):
        import check_settings as CS
        _, args_ = CS.read_cmd(P.CMD)
        lv_ = json.load(open(os.environ["PLAY_LIVE"], encoding="utf-8"))
        E.live_set({k_: str(v_) for k_, v_ in lv_.items() if k_ in E.LIVE_VARS})
        f_ = lambda n_, d_: float(args_.get(n_, d_) or d_)   # noqa: E731
        env.item_reward, env.item_loss, env.intent_seek = f_("--item-reward", 0.3), f_("--item-loss", 0.5), f_("--intent-seek", 1.0)
        env.stack_p, env.near_item_p = f_("--stack-p", 0.0), f_("--near-item-p", 0.0)
        env.dmg_reward = float(lv_.get("DMG_REWARD", f_("--dmg-reward", 0.004)))
        env.dmg_taken_w = float(lv_.get("DMG_TAKEN_W", f_("--dmg-taken-w", 1.0)))
    if "RDRILL_P" in getattr(E, "LIVE_VARS", ()):           # (whole games only)
        E.live_set({"RDRILL_P": "0"})
    if getattr(E, "BRAIN_READ", False):
        env.set_brain_g(np.full(env.n, pol.rfg if getattr(pol, "rf_read", False) else 0.0, np.float32))
        env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))
    print("play22e: {} seats at delays {} / {} ms; RDRILL_P {}".format(env.n, rm_, am_, getattr(E, "RDRILL_P", None)), flush=True)
    return E, env


P.make_env = make_env

if __name__ == "__main__":
    P.main()
