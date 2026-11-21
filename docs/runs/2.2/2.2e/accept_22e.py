"""2.2e (2.2d's accept_22d.py, for 2.2e's command and ramp): will the trainer accept the start's live.json and every file ramp_22e.py may write? tools/run/live_accept.py
with the simulator imported under 2.2e's command's own environment (train.cmd and aim2_env.cmd, as the trainer's process has it) and the ramp's dials at
every clock (RDRILL_P among them: 0.10 to clock 40, to 0 at 60). Then the same start file with each live name 2.2c to 2.2e brought (LEV_G, CONTEST_W,
CEDE_W, RAIL_PICK_PAY, RAIL_LINE_PAY, RAIL_FAR_PAY, NEAR_PAY; 2.2e: RDRILL_P, and aim4's live names AIM3_SIZE_A, AIM3_SIZE_B, AIM3_PURSUIT_TAU) at both
ends of its range (the owner may set any of them by hand). Exit 1 on any refusal.
    python docs/runs/2.2/2.2e/accept_22e.py <live.json> [<train.cmd>]"""
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
        "NEAR_PAY": (0.0, 10.0), "RDRILL_P": (0.0, 0.5),           # (2.2e: the drill's share; the trainer's LIVE_RANGE and the simulator's 0 .. 0.5)
        "AIM3_SIZE_A": (0.0, 1.0), "AIM3_SIZE_B": (0.0, 1.0), "AIM3_PURSUIT_TAU": (0.05, 0.5)}   # (aim4's live names: a sensible span, not a range of
#                                                             theirs; the eye's lag must be above 0: the simulator refuses 0)


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
    tmp = tempfile.mkdtemp(prefix="acc22e_")
    d0 = json.load(open(live, encoding="utf-8"))
    for k_, (lo_, hi_) in ENDS.items():
        for v_ in (lo_, hi_):
            p_ = os.path.join(tmp, "live_{}_{}.json".format(k_, v_))
            json.dump(dict(d0, **{k_: v_}), open(p_, "w", encoding="utf-8"))
            files.append(("{} at {}".format(k_, v_), p_, False))
    p_ = os.path.join(tmp, "live_RDRILL_P_over.json")                # (a refusal it must give: the drill's share above its range)
    json.dump(dict(d0, RDRILL_P=0.6), open(p_, "w", encoding="utf-8"))
    for nm_, p_, ramp_ in files + [("RDRILL_P at 0.6 (must be REFUSED)", p_, None)]:
        r_ = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "run", "live_accept.py"), p_, "--env", "duel_env_ffa22c"]
                            + (["--ramp", os.path.join(HERE, "ramp_22e.py")] if ramp_ else []), env=ev, capture_output=True, text=True, creationflags=NOWIN)
        tail_ = [x for x in (r_.stdout + r_.stderr).strip().split("\n") if x.strip()][-1:]
        print("{}: exit {}; {}".format(nm_, r_.returncode, tail_[0] if tail_ else ""), flush=True)
        bad |= (r_.returncode != 0) if ramp_ is not None else (r_.returncode == 0)
    print("ALL ACCEPTED (and the over-range share refused)" if not bad else "REFUSED")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
