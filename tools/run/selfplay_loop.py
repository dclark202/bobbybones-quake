"""The B data beside a run (owner, 2026-10-28: "log what we need during the training to run fit B"): every EVERY-th kept save
of the run (keep/policy_<update>.pt) plays GAMES self-play games a map on the ten maps, logged once a second
(tools/run/selfplay_log.py: the score, both stacks, the big weapons owned, who is dead, his own win value), at low priority on
the performance cores. Nothing here touches the run: it only reads its saves. Rows go to data/sim_runs/<run>/selfplay/u<update>/.
Before the first games, the settings check: the games' settings (selfplay_log's meta.json) against the run's command.

    python tools/run/selfplay_loop.py <run> [--every 40] [--games 5] [--par 2] [--procs 2]"""
import argparse
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.environ.get("BB_PY") or r"C:\Users\dacla\anaconda3\python.exe"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--every", type=int, default=40)
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--par", type=int, default=2)
    ap.add_argument("--procs", type=int, default=2)
    a = ap.parse_args()
    keep = os.path.join(ROOT, "data", "sim_runs", a.run, "keep")
    out = os.path.join(ROOT, "data", "sim_runs", a.run, "selfplay")
    os.makedirs(out, exist_ok=True)
    log = open(os.path.join(out, "loop.log"), "a")
    env = dict(os.environ, PANEL_RUN=a.run, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    done = set(os.listdir(out))
    while True:
        saves = sorted((int(m.group(1)), f) for f in os.listdir(keep) if (m := re.match(r"policy_(\d+)\.pt$", f)))
        todo = [(u, f) for u, f in saves if u % a.every == 0 and "u{}".format(u) not in done]
        if not todo:
            time.sleep(120)
            continue
        u, f = todo[-1]                                      # (the newest due save first; older ones are skipped, not queued)
        tag = "u{}".format(u)
        done.add(tag)
        t0 = time.time()
        r = subprocess.run([PY, os.path.join(HERE, "selfplay_log.py"), "--run", a.run, "--policy", os.path.join(keep, f), "--tag", tag,
                            "--games", str(a.games), "--par", str(a.par), "--procs", str(a.procs)],
                           cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=0x4000)   # (BELOW_NORMAL priority)
        log.write("{} {} exit {} in {:.0f} min\n".format(time.strftime("%m-%d %H:%M"), tag, r.returncode, (time.time() - t0) / 60))
        log.flush()


if __name__ == "__main__":
    sys.exit(main())
