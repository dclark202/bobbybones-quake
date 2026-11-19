"""2.2d (2.2c's accept_22c.py, for 2.2d's command and ramp): will the trainer accept the start's live.json and every file ramp_22d.py may write? tools/run/live_accept.py with the simulator imported under
2.2d's command's own environment (train.cmd and aim2_env.cmd, as the trainer's process has it) and the ramp's dials at every clock. Then the same
start file with each of 2.2c's new live names (LEV_G, CONTEST_W, CEDE_W, RAIL_PICK_PAY, RAIL_LINE_PAY, RAIL_FAR_PAY) at both ends of its range
(the owner may set any of them by hand). Exit 1 on any refusal.
    python docs/runs/2.2/2.2d/accept_22d.py <live.json> [<train.cmd>]"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(HERE, "..", "2.2c"))
import ident_sim as IS  # noqa: E402  (2.2c's: its cmd_env reads any command's `set` lines)

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ENDS = {"LEV_G": (0.0, 1.0), "CONTEST_W": (0.0, 1.0), "CEDE_W": (0.0, 0.5), "RAIL_PICK_PAY": (0.0, 1.0), "RAIL_LINE_PAY": (0.0, 1.0), "RAIL_FAR_PAY": (0.0, 1.0),
        "NEAR_PAY": (0.0, 10.0)}                              # (2.2d: NEAR_PAY too, its start now 0)


def main():
    live = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "train.cmd")
    root = os.environ.get("QLBOT_ROOT") or ROOT
    ev = dict(os.environ)
    ev.update(IS.cmd_env(cmd, root))
    ev.update(IS.cmd_env(os.path.join(os.path.dirname(cmd), "aim2_env.cmd"), root))
    ev.update(CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", QLBOT_ROOT=root)
    bad = 0
    files = [("the start's live.json and the ramp's every clock", live, True)]
    tmp = tempfile.mkdtemp(prefix="acc22d_")
    d0 = json.load(open(live, encoding="utf-8"))
    for k_, (lo_, hi_) in ENDS.items():
        for v_ in (lo_, hi_):
            p_ = os.path.join(tmp, "live_{}_{}.json".format(k_, v_))
            json.dump(dict(d0, **{k_: v_}), open(p_, "w", encoding="utf-8"))
            files.append(("{} at {}".format(k_, v_), p_, False))
    for nm_, p_, ramp_ in files:
        r_ = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "run", "live_accept.py"), p_, "--env", "duel_env_ffa22c"]
                            + (["--ramp", os.path.join(HERE, "ramp_22d.py")] if ramp_ else []), env=ev, capture_output=True, text=True, creationflags=NOWIN)
        tail_ = [x for x in (r_.stdout + r_.stderr).strip().split("\n") if x.strip()][-1:]
        print("{}: exit {}; {}".format(nm_, r_.returncode, tail_[0] if tail_ else ""), flush=True)
        bad |= r_.returncode != 0
    print("ALL ACCEPTED" if not bad else "REFUSED")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
