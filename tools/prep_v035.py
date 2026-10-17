"""v0.3.5 (one movement network, step 6: the switch to his legs retired) from a save of v0.3.4 (read only): the run's folder.

    python tools/prep_v035.py --from <v0.3.4's save .pt> --league <v0.3.4's snapshots folder> [--run duel_gru_v0_3_5]
                              [--cmd-template <.cmd with {MINUTES}> --cmd-out <.cmd> --until "2026-10-18 12:00" --setup-min 10]

  - data/sim_runs/<run>/policy.pt: the save with NO_SWITCH=1 in its env_vars (test_suite, netpass and the plugins then set
    the switch off after drawing it, so every other output's draw is as before) and without switch_fade (nothing left to
    fade); every weight as it is: the residual (B) and the turn correction stay (unused while the legs never drive; kept so
    that the file loads beside the league's and a step back is a change of switches only);
  - keep/policy_start.pt: the same file, kept;
  - snapshots/: the league's last eight snap_*.pt by the minute in their names and every anchor_*.pt, as they are;
  - with --cmd-template: the run's .cmd with --minutes from now (less --setup-min) to --until.
Refuses to write into a run folder that has a policy.pt (--force replaces the files it writes, nothing else).
"""
import argparse
import datetime
import glob
import os
import re
import shutil

import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="src", required=True)
ap.add_argument("--league", required=True)
ap.add_argument("--run", default="duel_gru_v0_3_5")
ap.add_argument("--force", action="store_true")
ap.add_argument("--cmd-template", action="append", default=[])
ap.add_argument("--cmd-out", action="append", default=[])
ap.add_argument("--until", default="2026-10-18 12:00")
ap.add_argument("--setup-min", type=float, default=10.0)
a = ap.parse_args()


def convert(src, dst):
    """a v0.3.4 network -> step 6's: NO_SWITCH=1, no fade; the weights untouched"""
    ck = torch.load(src, weights_only=False, map_location="cpu")
    lay = ck.get("legs_unify") or {}
    assert "legs.0.weight" in ck["model"] and (lay.get("feat") or lay.get("gate")), \
        "not a v0.3.4 network (its legs' branch inside, legs_door or the gate): the branch learns only through them after step 6"
    ck["env_vars"] = dict(ck.get("env_vars") or {}, NO_SWITCH="1")
    fade = ck.pop("switch_fade", None)
    torch.save(ck, dst)
    return ck, fade


if __name__ == "__main__":
    out = os.path.join(ROOT, "data", "sim_runs", a.run)
    assert a.force or not os.path.exists(os.path.join(out, "policy.pt")), "{} has a policy.pt already (--force)".format(out)
    os.makedirs(os.path.join(out, "keep"), exist_ok=True)
    os.makedirs(os.path.join(out, "snapshots"), exist_ok=True)
    ck, fade = convert(a.src, os.path.join(out, "policy.pt"))
    shutil.copy(os.path.join(out, "policy.pt"), os.path.join(out, "keep", "policy_start.pt"))
    print("start: {} min, {} outputs, the switch retired (NO_SWITCH=1; the fade it had: {})".format(
        round(float(ck.get("minutes", 0.0)), 2), len(ck["action_dims"]), fade))

    def num(f_):
        return int((re.findall(r"\d+", os.path.basename(f_)) or ["0"])[0])
    snaps = sorted(glob.glob(os.path.join(a.league, "snap_*.pt")), key=lambda f_: (num(f_), f_))[-8:]
    anchors = sorted(glob.glob(os.path.join(a.league, "anchor_*.pt")))
    assert snaps and anchors, "no snapshots or no anchor in {}".format(a.league)
    for f_ in snaps + anchors:
        sd = torch.load(f_, weights_only=False, map_location="cpu")["model"]
        assert sd["enc.0.weight"].shape == ck["model"]["enc.0.weight"].shape, "{}: another encoder".format(f_)
        assert 0 < int(sd["legs.0.weight"].shape[1]) <= int(ck["model"]["legs.0.weight"].shape[1]), "{}: its legs' branch".format(f_)
        shutil.copy(f_, os.path.join(out, "snapshots", os.path.basename(f_)))
        print("league: {} ({} output rows)".format(os.path.basename(f_), int(sd["pi.weight"].shape[0])))
    assert len(a.cmd_template) == len(a.cmd_out)
    for tp_, op_ in zip(a.cmd_template, a.cmd_out):
        mins = int((datetime.datetime.strptime(a.until, "%Y-%m-%d %H:%M") - datetime.datetime.now()).total_seconds() / 60.0 - a.setup_min)
        assert mins > 30, "--until is {} minutes away".format(mins)
        t_ = open(tp_, encoding="utf-8").read()
        assert "{MINUTES}" in t_
        open(op_, "w", encoding="utf-8", newline=chr(13) + chr(10)).write(t_.replace("{MINUTES}", str(mins)))
        print("wrote {} (--minutes {}: to {})".format(op_, mins, a.until))
    print("ready:", out)
