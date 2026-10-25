"""v0.4.2b: the mind view's "in control" (plugins/mindlog.py control_all, on the export's readouts) against the trainer's readout
forward in torch (sim/control.py layout 2: make_module, sigmoid, on the ring's row: the brain's state [256] at its tick, then
the hands' GRU memory [512] after that frame's step, in half precision). A game on one map is played by the exported network
on both seats through plugins/netpass.py (as the plugin plays); at every tick of the brain each seat's state is recorded, and
both readouts are worked out both ways, the "both" readout with the memory and the fallback (no memory: "belief"). Also
mindlog.build's line: ctl, ctl_src, ctl4 as the plugin writes them.

    CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python tools/control_check.py --policy <policy.pt> --npz <its export>
        [--control-py <a sim/control.py of layout 2>] [--map bloodrun] [--frames 1600]

The bar: max |diff| of the odds under 1e-5 (float32 numpy against float32 torch on the same half-precision rows)."""
import argparse
import importlib
import importlib.util
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "plugins"))

ap = argparse.ArgumentParser()
ap.add_argument("--policy", required=True)
ap.add_argument("--npz", required=True)
ap.add_argument("--control-py", default=os.path.join(ROOT, "sim", "control.py"))
ap.add_argument("--map", default="bloodrun")
ap.add_argument("--frames", type=int, default=1600)
ap.add_argument("--env", default="duel_env_ffa")
a = ap.parse_args()

P0 = dict(np.load(a.npz))
os.environ.update({k: str(v) for k, v in json.loads(str(P0.get("env_vars", "{}"))).items()})   # (as the plugins: before the module)
os.environ["LEGS_NET"] = os.path.join(os.path.dirname(os.path.abspath(a.npz)), "legs.npz")
E = importlib.import_module(a.env)
import btoken as BT  # noqa: E402
import netpass as N  # noqa: E402
import mindlog as ML  # noqa: E402
import torch  # noqa: E402

sp_ = importlib.util.spec_from_file_location("control_ref", a.control_py)
C = importlib.util.module_from_spec(sp_)
sp_.loader.exec_module(C)

ck = torch.load(a.policy, map_location="cpu", weights_only=False)
L = ck["control"]
assert int(L.get("version", 1)) == 2, "a layout of version 2 expected"
mods = C.make_module(L)
sd = {k[len("control."):]: v for k, v in ck["model"].items() if k.startswith("control.")}
mods.load_state_dict(sd, strict=True)
mods.eval()

P, A = N.load(a.npz)
R = ML.readouts(P)
assert "control" in R and isinstance(R["control"][1], dict), "the export has no readouts of layout 2"
print("readouts in the export:", sorted(R["control"][1]), "| layout", json.dumps({k: L[k] for k in ("bel", "mem", "width")}))

nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(a.map))
env = E.DuelEnv(os.path.join(ROOT, "data", "maps", a.map + ".bsp"), n_matches=1, seed=7, loadout="all", nav=nav_ if os.path.exists(nav_) else None)
env.kind_p = (1.0, 0.0, 0.0, 0.0)
env.bot_p = env.runner_p = env.jump_run_p = env.item_run_p = 0.0
env.round_t[:] = 1e9
obs, _, _, _ = env.step(np.zeros((env.n, len(E.ACTION_DIMS)), np.int64))
env.round_len = env.arena_len = 1e9
env.round_t[:] = 0.0
env.script[:] = 0
n = env.n
rng = np.random.default_rng(11)
hh = np.zeros((n, N.width(P)), np.float32)
B_, bl_, bt_, at_, _ = P["_brain"]
Hm = int(P["whh"].shape[1])
rows = []                                                    # (s [256], mem [512])
for t in range(a.frames):
    pz, zz = BT.pose_from_env(env, a.map)
    xl = env.legs_prep() if N.needs_xl(P) else None
    kw = dict(pose=pz, zmap=zz) if N.needs_pose(P) else {}
    act, hh = N.step(P, A, obs, hh, rng, xl=xl, **kw)
    N.legs_feed(P, env, E, rows=list(range(n)))              # (LEGS_IN) the legs' choices from his network's branch, as the plugin
    br_, _tk = bt_.unpack(B_, bl_, hh[:, at_:])
    for i in range(n):
        if int(br_.gv[i]) % int(B_["K"]) == 0:              # (a tick of the brain: plugins/duelbot.py mind_frame's test)
            rows.append((np.array(br_.s[i], np.float32), np.array(hh[i, :Hm], np.float32)))
    obs, r, done, info = env.step(act)
    d = np.asarray(done, bool)
    if d.any():
        N.clear(P, hh, d)
print("recorded {} brain ticks (seats x ticks) over {} frames on {}".format(len(rows), a.frames, a.map))
assert rows, "no tick of the brain recorded"

S = np.stack([r_[0] for r_ in rows])
M = np.stack([r_[1] for r_ in rows])
X = torch.from_numpy(np.concatenate([S, M], 1)).half()       # (the ring's rows: float16, the brain's state then the memory)
res = {}
with torch.no_grad():
    for r_ in L["readouts"]:
        nm, inp = r_["name"], int(r_["inp"])
        res[nm] = torch.sigmoid(mods[nm](X[:, :inp].float())).double().numpy()
worst = 0.0
for nm, mem_ in (("both", True), ("belief", False)):
    if nm not in res:
        continue
    got = np.stack([ML.control_all(R["control"][0], R["control"][1], S[k], M[k] if mem_ else None)[0] for k in range(len(S))])
    src = ML.control_src(R["control"][0], R["control"][1], M[0] if mem_ else None)
    assert src == nm, "with{} the memory the plugin used {}".format("" if mem_ else "out", src)
    dmax = float(np.abs(got - res[nm]).max())
    worst = max(worst, dmax)
    print("{:6s} (plugin {} the memory): max |diff| {:.2e} over {} rows x 4 | torch 'two' mean {:.3f} range {:.3f}..{:.3f} | "
          "sd {:.3f}".format(nm, "with" if mem_ else "without", dmax, len(S), res[nm][:, 0].mean(),
                                              res[nm][:, 0].min(), res[nm][:, 0].max(), res[nm][:, 0].std()))
# the line as the plugin writes it (mindlog.build) at the last tick
me = [float(v) for v in env.state[0, :3]] + [float(env.yaw[0])]
en = [float(v) for v in env.state[1, :3]] + [float(env.yaw[1])]
rec = ML.build(0.0, a.map, me, en, False, None, S[-1], P, {}, (0, 0), 300.0, mem=M[-1])
assert rec["ctl_src"] == "both" and abs(rec["ctl"] - res["both"][-1, 0]) <= 5e-4, rec
rec0 = ML.build(0.0, a.map, me, en, False, None, S[-1], P, {}, (0, 0), 300.0)
assert rec0["ctl_src"] == "belief" and abs(rec0["ctl"] - res["belief"][-1, 0]) <= 5e-4, rec0
print("mindlog.build: ctl {} ctl_src {} ctl4 {} | without the memory: ctl {} ({})".format(rec["ctl"], rec["ctl_src"], rec["ctl4"],
                                                                                          rec0["ctl"], rec0["ctl_src"]))
print("PASS" if worst < 1e-5 else "FAIL", "max |diff| {:.2e}".format(worst))
sys.exit(0 if worst < 1e-5 else 1)
