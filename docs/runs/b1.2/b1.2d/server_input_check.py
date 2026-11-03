"""b1.2d's inputs on a real server against the simulator's (2026-11-02, before the public servers): tools/input_check.py with b1.2d's
command's switches set first (SM_ITEMS and the rest: the simulator module reads them at import), its end save, Blood Run, against
a recording made with OBSDUMP=1 in a private spar on the Amsterdam server (image qlbot:pub-abf5930).
    python docs/runs/b1.2/b1.2d/server_input_check.py <obs_dump.npy> > docs/runs/b1.2/b1.2d/server_input_check.log"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import winpay_games as WG

envv, _ = WG.run_env(os.path.join(HERE, "train.cmd"), os.path.join(ROOT, "data", "sim_runs", "duel_gru_b1_2d"))
envv["LEGS_NET"] = os.path.join(ROOT, "data", "sim_runs", "move_v17_look", "policy.npz")    # (as tools/run/panel.py: his legs' branch inputs)
envv.update(CONTACT_FREE="1", LEVEL_PULL="1", ITEM_PT_MIX="1", SPEED_PAY="0.125", STACK_DIFF="0", RAIL_FAR_PAY="0.25")
os.environ.update(envv)
print("switches:", {k: envv[k] for k in sorted(envv) if k in ("SM_ITEMS", "CONTACT_FREE", "INTENT_HOLD", "AIM2", "BRAIN_READ", "HUNT")}, flush=True)
import input_check as IC
import duel_env_ffa as E
import test_suite as T

# (input_check.py predates the legs branch: act() wants the branch's inputs, the simulator's legs_prep() rows of his seats)
_ENV = []
_init, _act = E.DuelEnv.__init__, T.Policy.act


def _init_keep(self, *a, **k):
    _init(self, *a, **k)
    _ENV.append(self)


def _act_xl(self, obs, h, *a, **k):
    if k.get("xl") is None and _ENV:
        me_ = _ENV[-1].script == 0
        k["xl"] = _ENV[-1].legs_prep()[me_]
        if getattr(self, "needs_pose", False) and k.get("pose") is None:      # (the brain is stepped: its pose and zones, as duel_eval)
            import btoken as BT
            pz_, zz_ = BT.pose_from_env(_ENV[-1], "bloodrun")
            k["pose"], k["zmap"] = pz_[me_], zz_[me_]
    return _act(self, obs, h, *a, **k)


E.DuelEnv.__init__, T.Policy.act = _init_keep, _act_xl
sys.argv = ["input_check.py", "--policy", os.path.join(ROOT, "data", "sim_runs", "duel_gru_b1_2d", "keep", "policy_end_b12d.pt"),
            "--env", "duel_env_ffa", "--map", "bloodrun", "--games", "4", "--minutes", "4", "--real", sys.argv[1], "--skip", "400"]
IC.main()
