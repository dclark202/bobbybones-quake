"""2.2b's league at its start (start.ps1): 2.2a's league as it stood at its update 90, brought to list 22b (tools/inputs21.py --old 20e --new 22b
--group "b22b fight" --token fight22 convert: the hands' 20 new columns at zero weights, the new token shut; the trainer leaves out of a 2.2a file
the rater's parts and plays a league file without a fight network on its item picker alone):
  * every anchor of 2.2a's snapshots\\ (anchor_*.pt: 1.3b ... 2.1d), as anchor_<name>.pt
  * the control, 2.2a's update 90 itself, as anchor_22a90.pt (in the league from the first rollout, as every run's control)
  * 2.2a's own snapshots up to update 90: the last 8 (the trainer's own window on a resume) whose minute is at most policy_90's
A file already in the out folder is refused (nothing overwritten). Nothing is deleted.
    python docs/runs/2.2/2.2b/league_22b.py <2.2a run folder> <policy_90.pt> <out snapshots folder>"""
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CONV = [sys.executable, os.path.join(ROOT, "tools", "inputs21.py"), "--old", "20e", "--new", "22b", "--group", "b22b fight", "--token", "fight22", "convert"]


def minute_of(f_):
    return int((re.findall(r"\d+", os.path.basename(f_)) or ["0"])[0])


def main():
    src, p90, out = sys.argv[1:4]
    import torch
    m90 = float(torch.load(p90, map_location="cpu", weights_only=False)["minutes"])
    sn_ = sorted(glob.glob(os.path.join(src, "snapshots", "snap_*.pt")), key=lambda f_: (minute_of(f_), f_))
    sn_ = [f_ for f_ in sn_ if minute_of(f_) <= m90][-8:]
    an_ = sorted(glob.glob(os.path.join(src, "snapshots", "anchor_*.pt")))
    assert an_, "no anchors in " + src
    jobs = [(f_, os.path.join(out, os.path.basename(f_))) for f_ in an_ + sn_] + [(p90, os.path.join(out, "anchor_22a90.pt"))]
    for _, o_ in jobs:
        if os.path.exists(o_):
            raise SystemExit("REFUSED: {} is there already (nothing overwritten)".format(o_))
    os.makedirs(out, exist_ok=True)
    for f_, o_ in jobs:
        r_ = subprocess.run(CONV + [f_, o_], capture_output=True, text=True, creationflags=NOWIN)
        if r_.returncode != 0 or not os.path.exists(o_):
            raise SystemExit("convert FAILED for {}: {}".format(f_, (r_.stdout + r_.stderr)[-800:]))
        print("{} -> {}".format(os.path.basename(f_), os.path.basename(o_)), flush=True)
    print("league: {} anchors and the control (anchor_22a90.pt), {} snapshots of 2.2a up to minute {:.0f} (update 90): {}".format(
        len(an_), len(sn_), m90, ", ".join(os.path.basename(f_) for f_ in sn_)))


if __name__ == "__main__":
    main()
