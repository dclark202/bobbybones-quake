"""v0.3.3's start from a save of v0.3.2 (read only): the run's folder ready for its .cmd (the trainer with --resume).

    python tools/prep_v033.py --from <v0.3.2's save .pt> --league <v0.3.2's snapshots folder> [--run duel_gru_v0_3_3]

  - data/sim_runs/<run>/policy.pt: the save converted by tools/unify_init.py: legs_door at zero (--legs-feat, step 3), the
    guide not added (--legs-guide stays off; a resume with it adds it at zero), LEGS_KEYS_ADD's five choices shut (step 2);
  - keep/policy_start.pt: the same file, kept;
  - snapshots/: the league's last eight snap_*.pt by the minute in their names, and every anchor_*.pt (v0.3.1's end), as
    they are: the trainer's load_net gives a league file what it lacks (the door at zero, the five shut, the turn
    correction shut, a narrower branch widened at zero weight). Each is checked here for those shapes.
Refuses to write into a run folder that has a policy.pt (--force replaces the files it writes, nothing else).
Run it with the run's switches set (LEGS=1 LEGS_IN=1 LEGS_LOOK=1 LEGS_TURN_ADD=1 LEGS_KEYS_ADD=1): it imports the simulator.
"""
import argparse
import glob
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))

ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="src", required=True)
ap.add_argument("--league", required=True)
ap.add_argument("--run", default="duel_gru_v0_3_3")
ap.add_argument("--force", action="store_true")
a = ap.parse_args()
for k_ in ("LEGS", "LEGS_IN", "LEGS_TURN_ADD", "LEGS_KEYS_ADD"):
    assert os.environ.get(k_) == "1", "set the run's switches first ({}=1 and the others of its .cmd)".format(k_)

import numpy as np  # noqa: E402
import torch  # noqa: E402
import unify_init as U  # noqa: E402
import duel_env as E  # noqa: E402

out = os.path.join(ROOT, "data", "sim_runs", a.run)
assert a.force or not os.path.exists(os.path.join(out, "policy.pt")), "{} has a policy.pt already (--force)".format(out)
os.makedirs(os.path.join(out, "keep"), exist_ok=True)
os.makedirs(os.path.join(out, "snapshots"), exist_ok=True)

ck0 = torch.load(a.src, weights_only=False, map_location="cpu")
dims0 = [int(d) for d in ck0["action_dims"]]
assert len(dims0) == 14 and dims0[-1] == len(E.TA_BINS), "not a save of v0.3.2's shape (14 outputs, the turn correction last): {}".format(dims0)
tb_ = ck0["model"]["pi.bias"][sum(dims0[:13]):]
print("v0.3.2's save: {} min, the turn correction's bias of 0 over the others {:.3f} (the opening's end, --turn-add-to: 4.68; at the first "
      "update the trainer holds it at or under that)".format(round(float(ck0.get("minutes", 0.0)), 1), float(tb_[0] - tb_[1:].mean())))
dst = os.path.join(out, "policy.pt")
U.widen(a.src, dst, feat=True, guide=False, keys=True)
shutil.copy(dst, os.path.join(out, "keep", "policy_start.pt"))
ck = torch.load(dst, weights_only=False, map_location="cpu")
print("start: {} outputs {}, legs_unify feat {} guide {}, the branch {} inputs".format(
    len(ck["action_dims"]), list(ck["action_dims"]), ck["legs_unify"]["feat"], ck["legs_unify"]["guide"], ck["model"]["legs.0.weight"].shape[1]))

KA_O = sum(int(d) for d in ck["action_dims"][:E.KA_HEAD])
TA_O = sum(int(d) for d in ck["action_dims"][:E.TA_HEAD])


def num(f_):
    return int((re.findall(r"\d+", os.path.basename(f_)) or ["0"])[0])


snaps = sorted(glob.glob(os.path.join(a.league, "snap_*.pt")), key=lambda f_: (num(f_), f_))[-8:]
anchors = sorted(glob.glob(os.path.join(a.league, "anchor_*.pt")))
assert snaps and anchors, "no snapshots or no anchor in {}".format(a.league)
for f_ in snaps + anchors:
    sd = torch.load(f_, weights_only=False, map_location="cpu")["model"]
    rows, wl = int(sd["pi.weight"].shape[0]), int(sd["legs.0.weight"].shape[1]) if "legs.0.weight" in sd else -1
    assert rows in (TA_O, KA_O, KA_O + 2 * len(E.KA_COLS)), "{}: {} output rows (the trainer fills {} or {})".format(f_, rows, TA_O, KA_O)
    assert 0 < wl <= int(ck["model"]["legs.0.weight"].shape[1]), "{}: a branch of {} inputs".format(f_, wl)
    assert sd["enc.0.weight"].shape == ck["model"]["enc.0.weight"].shape, "{}: another encoder".format(f_)
    shutil.copy(f_, os.path.join(out, "snapshots", os.path.basename(f_)))
    print("league: {} ({} output rows, the branch {} inputs{})".format(os.path.basename(f_), rows, wl,
                                                                       ", the turn correction added shut at load" if rows == TA_O else ""))
print("ready:", out)
