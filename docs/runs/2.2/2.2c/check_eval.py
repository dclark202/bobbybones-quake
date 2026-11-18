"""2.2c, the build: the checks' tools on a save, as the watcher runs them (tools/run/watch.py's command: tools/duel_eval.py with the panel's
settings for the save and the held-draw arguments), short: a few games on one map against 2.2a's update 90. For a save of 2.2c (the lever) and
one of 2.2b (the four options: older checkpoints keep working). Prints the record and the json's path.
    QLBOT_ROOT=<checkout> python docs/runs/2.2/2.2c/check_eval.py <save.pt> <out.json> [--map bloodrun] [--games 2] [--tool duel_eval|ws_eval]"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("save")
    ap.add_argument("out")
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--games", type=int, default=2)
    ap.add_argument("--ctrl", default=os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data", "sim_runs", "duel_gru_2_2a", "keep", "policy_90.pt"))
    a = ap.parse_args()
    os.environ.setdefault("PANEL_SETS", "FIGHT=1,OUT_LIVE=1.5,AHEAD_IN=1")
    import panel as P
    import watch as W
    sets = P.settings(0.0, a.save)
    cmd = [sys.executable, os.path.join(ROOT, "tools", "duel_eval.py"), "--run", "scratch_22c_build", "--policy", a.save, "--opp", "policy:" + a.ctrl,
           "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", a.map, "--games", str(a.games), "--minutes", "2", "--procs", "2", "--swap",
           "--json", a.out, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "120", "--opp-round", "120"]
    cmd += [x for s_ in sets for x in ("--set", s_)]
    cmd += W.hold_args(a.save, a.ctrl)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1")
    r_ = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, creationflags=NOWIN)
    print("exit {}".format(r_.returncode))
    if r_.returncode != 0:
        print((r_.stdout + r_.stderr)[-2500:])
        sys.exit(1)
    v = json.load(open(a.out))["maps"][a.map]
    print("{} on {}: {}-{} against 2.2a's update 90, frag share {:.3f}; the settings: {}".format(os.path.basename(a.save), a.map, v["won"], v["lost"],
                                                                                             v["frag_share"], [s_ for s_ in sets if s_.split("=")[0] in ("FIGHT", "AHEAD_IN", "OUT_LIVE")]))


if __name__ == "__main__":
    main()
