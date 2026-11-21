"""2.2b: will the trainer accept the start's live.json and every file ramp_22b.py may write? tools/run/live_accept.py with the simulator imported under
2.2b's command's own environment (train.cmd and aim2_env.cmd, as the trainer's process has it), the ramp's dials at every clock, and FGT_BIAS (written
once at update 60) at the ends of its range and 0 (RAMP22B_BIAS -30, 0, 30). Exit 1 on any refusal.
    python docs/runs/2.2/2.2b/accept_22b.py <live.json> [<train.cmd>]"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)
import ident_sim as IS  # noqa: E402

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def main():
    live = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "train.cmd")
    root = os.environ.get("QLBOT_ROOT") or ROOT
    ev = dict(os.environ)
    ev.update(IS.cmd_env(cmd, root))
    ev.update(IS.cmd_env(os.path.join(os.path.dirname(cmd), "aim2_env.cmd"), root))
    ev.update(CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", QLBOT_ROOT=root)
    bad = 0
    for b_ in ("-30", "0", "30"):
        ev["RAMP22B_BIAS"] = b_
        r_ = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "run", "live_accept.py"), live, "--env", "duel_env_ffa22b", "--ramp",
                             os.path.join(HERE, "ramp_22b.py")], env=ev, capture_output=True, text=True, creationflags=NOWIN)
        tail_ = [x for x in (r_.stdout + r_.stderr).strip().split("\n") if x.strip()][-1:]
        print("FGT_BIAS {}: exit {}; {}".format(b_, r_.returncode, tail_[0] if tail_ else ""), flush=True)
        bad |= r_.returncode != 0
    print("ALL ACCEPTED" if not bad else "REFUSED")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
