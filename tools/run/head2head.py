"""Two saves head to head, each at its own target lock (b1.2, 2026-11-01): 160 ten-minute games on ten maps, seats swapped, with the checks' settings. Nothing but the settings differs from a watcher's check, and the lock is a seat's.
    python tools/run/head2head.py <label> <run> <save A> <lock A> <save B> <lock B> [--out D] [--games 16]     (saves: full paths; prints A's record)"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAPS = ["bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure"]


def main():
    ap = argparse.ArgumentParser()
    for n_ in ("label", "run", "a", "hold_a", "b", "hold_b"):
        ap.add_argument(n_)
    ap.add_argument("--out", default="")
    ap.add_argument("--games", type=int, default=16)
    ap.add_argument("--maps", default=",".join(MAPS))
    ap.add_argument("--batch", type=int, default=4)
    a = ap.parse_args()
    os.environ["PANEL_RUN"] = a.run
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    import panel as P
    sets = [s for s in P.settings(0.0, a.a) if not s.startswith("INTENT_HOLD=")] + ["INTENT_HOLD=8"]
    out = a.out or os.path.join(ROOT, "data", "sim_runs", a.run, "watch", "h2h_" + a.label)
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1")
    res = {}
    M = a.maps.split(",")
    for w in range(0, len(M), a.batch):
        jobs = []
        for mp in M[w:w + a.batch]:
            js = os.path.join(out, mp + ".json")
            cmd = [sys.executable, "tools/duel_eval.py", "--run", a.run, "--policy", a.a, "--opp", "policy:" + a.b, "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", mp, "--games", str(a.games),
                   "--minutes", "10", "--procs", "2", "--swap", "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600", "--opp-round", "600",
                   "--hold", a.hold_a, "--opp-hold", a.hold_b]
            cmd += [x for s_ in sets for x in ("--set", s_)]
            jobs.append((mp, js, subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=open(js + ".log", "w"), stderr=subprocess.STDOUT)))
        for mp, js, p in jobs:
            p.wait()
            try:
                v = json.load(open(js))["maps"][mp]
                res[mp] = (v["won"], v["lost"], v["frag_share"])
            except Exception as e:  # noqa: BLE001
                res[mp] = (0, 0, 0.0)
                print(mp, "ERROR", e, flush=True)
        print(time.strftime("%H:%M:%S"), {k: "{}-{} {:.0%}".format(*v) for k, v in res.items()}, flush=True)
    W, L = sum(v[0] for v in res.values()), sum(v[1] for v in res.values())
    print("{}: A {} at {} s against B {} at {} s: {}-{}, win rate {:.1%}, frag share {:.1%}".format(a.label, os.path.basename(a.a), a.hold_a, os.path.basename(a.b), a.hold_b, W, L, W / max(1, W + L), sum(v[2] for v in res.values()) / max(1, len(res))), flush=True)


if __name__ == "__main__":
    main()
