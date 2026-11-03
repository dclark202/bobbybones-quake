"""v0.6.1d's fades, together (owner, 2026-10-30: "Just keep them together"), as v0.6.1c's: BRAIN_FADE 0 -> 1 and LEVEL_PULL 0.95 -> 1 in
the same write, eight steps, by tools/run/ramp_live.py, a step right after each save and at least 25 min apart: from ~40 min to ~5.3 h.
Keeps the save before the first step. Extra arguments go to the ramp (the smoke run's --min-s, --sleep, --dir).
    python docs/runs/v0.6.1d/ramp_fades.py <run> [ramp_live arguments]"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
RAMP = os.path.join(ROOT, "tools", "run", "ramp_live.py")
run, extra = sys.argv[1], sys.argv[2:]
sys.exit(subprocess.run([sys.executable, RAMP, run, "BRAIN_FADE", "0", "1", "0.125", "--also", "LEVEL_PULL:0.95:1.0:0.00625",
                         "--keep-as", "policy_prefade_v061d.pt"] + extra, cwd=ROOT).returncode)
