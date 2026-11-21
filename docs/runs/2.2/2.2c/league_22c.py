"""2.2c's league at its start (start.ps1), as 2.2b's (docs/runs/2.2/2.2b/league_22b.py): 2.2a's league as it stood at its update 90, brought to list
22c in two steps (tools/inputs21.py --old 20e --new 22b --group "b22b fight" --token fight22 convert, then tools/inputs22c.py convert: the hands'
new columns at zero weights, the new token shut; no fight network: a league file without one plays its item picker alone, its lever 0):
  * every anchor of 2.2a's snapshots\\ (anchor_*.pt), as anchor_<name>.pt
  * the control, 2.2a's update 90 itself, as anchor_22a90.pt
  * 2.2a's own snapshots up to update 90: the last 8 whose minute is at most policy_90's
The first step's files are kept in <mid> (nothing is deleted). A file already in the out folder (or in <mid>) is refused (nothing overwritten).
    python docs/runs/2.2/2.2c/league_22c.py <2.2a run folder> <policy_90.pt> <out snapshots folder> <mid folder>"""
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CONV1 = [sys.executable, os.path.join(ROOT, "tools", "inputs21.py"), "--old", "20e", "--new", "22b", "--group", "b22b fight", "--token", "fight22", "convert"]
CONV2 = [sys.executable, os.path.join(ROOT, "tools", "inputs22c.py"), "convert"]


def minute_of(f_):
    return int((re.findall(r"\d+", os.path.basename(f_)) or ["0"])[0])


def main():
    src, p90, out, mid = sys.argv[1:5]
    import torch
    m90 = float(torch.load(p90, map_location="cpu", weights_only=False)["minutes"])
    sn_ = sorted(glob.glob(os.path.join(src, "snapshots", "snap_*.pt")), key=lambda f_: (minute_of(f_), f_))
    sn_ = [f_ for f_ in sn_ if minute_of(f_) <= m90][-8:]
    an_ = sorted(glob.glob(os.path.join(src, "snapshots", "anchor_*.pt")))
    assert an_, "no anchors in " + src
    jobs = [(f_, os.path.join(mid, os.path.basename(f_)), os.path.join(out, os.path.basename(f_))) for f_ in an_ + sn_] + \
        [(p90, os.path.join(mid, "anchor_22a90.pt"), os.path.join(out, "anchor_22a90.pt"))]
    for _, m_, o_ in jobs:
        for x_ in (m_, o_):
            if os.path.exists(x_):
                raise SystemExit("REFUSED: {} is there already (nothing overwritten)".format(x_))
    os.makedirs(out, exist_ok=True)
    os.makedirs(mid, exist_ok=True)
    for f_, m_, o_ in jobs:
        for cv_, a_, b_ in ((CONV1, f_, m_), (CONV2, m_, o_)):
            r_ = subprocess.run(cv_ + [a_, b_], capture_output=True, text=True, creationflags=NOWIN)
            if r_.returncode != 0 or not os.path.exists(b_):
                raise SystemExit("convert FAILED for {}: {}".format(a_, (r_.stdout + r_.stderr)[-800:]))
        print("{} -> {}".format(os.path.basename(f_), os.path.basename(o_)), flush=True)
    print("league (list 22c): {} anchors and the control (anchor_22a90.pt), {} snapshots of 2.2a up to minute {:.0f} (update 90): {}".format(
        len(an_), len(sn_), m90, ", ".join(os.path.basename(f_) for f_ in sn_)))


if __name__ == "__main__":
    main()
