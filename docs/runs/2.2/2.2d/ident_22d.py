"""2.2d: the simulator's new switches (CONTEST_LOG, RAIL_WOULD, FREE_SEE) off = the tree before them, to the bit; and on = the same inputs, pay and
round ends as the tree before with the pays at 2.2d's zeros (they only count). Fixed-seed replays with docs/runs/2.2/2.2c/ident_sim.py (play: the
group module of a tree with 2.2b's command's settings and --set ones, 8 matches, random actions; cmp: every input by name, pay, ends, targets,
stacks, places equal to the bit). Each replay in its own process (hidden).
    QLBOT_ROOT=<checkout> CUDA_VISIBLE_DEVICES=-1 OPENBLAS_NUM_THREADS=1 python docs/runs/2.2/2.2d/ident_22d.py <old tree> <out folder>
<old tree>: the tree before the build (git archive of the commit before, with sim/qsim.dll copied in)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
IS = os.path.join(HERE, "..", "2.2c", "ident_sim.py")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
S22C = ["CONTEST=1", "CONTEST_W=0.8", "CEDE_W=0.1", "RAIL_CHAIN=1", "RAIL_PICK_PAY=0.15", "RAIL_LINE_PAY=0.10", "AHEAD_IN=1", "FIGHT_SPLIT=22c",
        "NEAR_PAY=5", "RAIL_FAR_PAY=0.5", "PAY_SPLIT=1"]
S22D = ["CONTEST=1", "CONTEST_W=0", "CEDE_W=0", "RAIL_CHAIN=1", "RAIL_PICK_PAY=0.15", "RAIL_LINE_PAY=0", "AHEAD_IN=1", "FIGHT_SPLIT=22c",
        "NEAR_PAY=0", "RAIL_FAR_PAY=0.5", "PAY_SPLIT=1"]
CASES = (("off: every 2.2d switch off, 2.2b's settings", "bloodrun", 800, [], []),
         ("off: every 2.2d switch off, 2.2b's settings", "hektik", 1200, [], []),
         ("off: 2.2c's switches on (the contest pay, the rail chain, the near miss paid), the new ones off", "bloodrun", 1200, S22C, S22C),
         ("on: 2.2d's pays at zero; the new tree with CONTEST_LOG, RAIL_WOULD, FREE_SEE on", "bloodrun", 1200, S22D, S22D + ["CONTEST_LOG=1", "RAIL_WOULD=1", "FREE_SEE=1"]),
         ("on: 2.2d's pays at zero; the new tree with CONTEST_LOG, RAIL_WOULD, FREE_SEE on", "toxicity", 1200, S22D, S22D + ["CONTEST_LOG=1", "RAIL_WOULD=1", "FREE_SEE=1"]))


def main():
    old, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    bad = 0
    for k_, (nm_, mp_, fr_, so_, sn_) in enumerate(CASES):
        files = []
        for tr_, set_ in ((old, so_), (ROOT, sn_)):
            f_ = os.path.join(out, "case{}_{}.npz".format(k_, "old" if tr_ == old else "new"))
            r_ = subprocess.run([sys.executable, IS, "play", tr_, f_, "--map", mp_, "--frames", str(fr_), "--seed", str(11 + k_)]
                                + [x_ for s_ in set_ for x_ in ("--set", s_)], capture_output=True, text=True, creationflags=NOWIN)
            if r_.returncode != 0:
                print("play FAILED ({}): {}".format(tr_, (r_.stdout + r_.stderr)[-1500:]))
                bad += 1
            files.append(f_)
        r_ = subprocess.run([sys.executable, IS, "cmp"] + files, capture_output=True, text=True, creationflags=NOWIN)
        print("case {}: {} | {} {} frames x 16 seats".format(k_, nm_, mp_, fr_))
        print("   " + (r_.stdout + r_.stderr).strip().replace("\n", "\n   "), flush=True)
        bad += r_.returncode != 0
    print("ALL IDENTICAL" if not bad else "FAILED")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
