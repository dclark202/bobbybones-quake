"""v0.6.1's end against its save before the pull toward level was faded (owner, 2026-10-29): two head-to-head checks of 160 games
(ten maps of 16, seats swapped), the checks' own settings, the pull for both seats at --levels (default 1.0: the condition he
ends in; 0.95: his old one). Results to <run>/watch/cmp_level_<L>_<map>.json and one line a level to watch.log.

    python tools/run/compare_level.py <run> <a.pt> <b.pt> [--levels 1.0,0.95] [--label-a ...] [--label-b ...]"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panel as P                                            # noqa: E402

MAPS = ["bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--levels", default="1.0,0.95")
    ap.add_argument("--label-a", default="a")
    ap.add_argument("--label-b", default="b")
    ap.add_argument("--par", type=int, default=5, help="maps at once")
    ap.add_argument("--dry", action="store_true", help="print the commands only")
    a = ap.parse_args()
    WD = os.path.join(P.ROOT_, "data", "sim_runs", a.run, "watch")
    os.makedirs(WD, exist_ok=True)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1")
    for lv in a.levels.split(","):
        sets = [s for s in P.settings(0.0) if not s.startswith("LEVEL_PULL=")] + ["LEVEL_PULL=" + lv]
        res = {}
        for w in range(0, len(MAPS), a.par):
            jobs = []
            for mp in MAPS[w:w + a.par]:
                js = os.path.join(WD, "cmp_level_{}_{}.json".format(lv, mp))
                cmd = [sys.executable, "tools/duel_eval.py", "--run", a.run, "--policy", a.a, "--opp", "policy:" + a.b, "--opp-inputs",
                       os.path.join(P.CODE, "docs", "INPUTS.csv"), "--map", mp, "--games", "16", "--minutes", "10", "--procs", "2", "--swap",
                       "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225",
                       "--round", "600", "--opp-round", "600"] + [x for s_ in sets for x in ("--set", s_)]
                if a.dry:
                    print(" ".join(cmd))
                    continue
                jobs.append((mp, js, subprocess.Popen(cmd, cwd=P.CODE, env=env, stdout=open(js + ".log", "w"), stderr=subprocess.STDOUT)))
            for mp, js, p in jobs:
                p.wait()
                try:
                    v = json.load(open(js))["maps"][mp]
                    res[mp] = (int(v["won"]), int(v["lost"]), float(v["frag_share"]))
                except Exception as e:                       # noqa: BLE001
                    res[mp] = None
                    print("map", mp, "failed:", e, flush=True)
        if a.dry:
            continue
        W = sum(r[0] for r in res.values() if r)
        L = sum(r[1] for r in res.values() if r)
        line = "{} compare at LEVEL_PULL {}: {} against {}: {}-{} win rate {:.1%} | {}".format(
            time.strftime("%m-%d %H:%M:%S"), lv, a.label_a, a.label_b, W, L, W / max(1, W + L),
            {m: "{}-{}".format(r[0], r[1]) for m, r in res.items() if r})
        print(line, flush=True)
        with open(os.path.join(WD, "watch.log"), "a") as f:
            f.write(line + "\n")


if __name__ == "__main__":
    main()
