"""1.5a's blanked check (CARD.md, part D's measure): a save played with the head's weapon part at add 0 (the hands' weapon choice alone,
everything else as trained) against the watcher's opponent (CTRL_PREV, 1.3b's end), 200 games on the ten maps, exactly as the watcher's
checks (tools/run/watch.py games(): the panel's play settings, each seat's own lock), with --head2-wadd 0 on his seat. Read beside the
watcher's own check of the same save: if the blanked one is lower, the head's weapon part wins games. Written to
watch/checks_blank.jsonl (ramp_15a.py logs it).
    python docs/runs/1.5/1.5a/blank_check.py <run> <save.pt> <update> [--ctrl <file>]"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
MAPS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("save")
    ap.add_argument("update", type=int)
    ap.add_argument("--ctrl", default="")
    ap.add_argument("--games", type=int, default=int(os.environ.get("CHECK_GAMES") or 20))
    ap.add_argument("--batch", type=int, default=int(os.environ.get("CHECK_BATCH") or 4))
    a = ap.parse_args()
    D = os.path.join(ROOT, "data", "sim_runs", a.run)
    WD = os.path.join(D, "watch")
    ctrl = a.ctrl or os.path.join(D, "keep", "control_13b.pt")
    os.environ["PANEL_RUN"] = a.run
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    import panel as P
    import watch as W_                                       # (its hold_args: each seat at its own lock; nothing of it runs on import)
    try:
        ps = float(json.load(open(os.path.join(D, "live.json"))).get("PERCEPT_SPEED") or 0.0)
    except Exception:                                        # noqa: BLE001
        ps = 0.0
    sets = P.settings(ps, a.save)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1")
    res = {}
    t0 = time.time()
    for w in range(0, len(MAPS), a.batch):
        jobs = []
        for mp in MAPS[w:w + a.batch]:
            js = os.path.join(WD, "chk_{}_blank_{}.json".format(a.update, mp))
            cmd = [sys.executable, "tools/duel_eval.py", "--run", a.run, "--policy", a.save, "--opp", "policy:" + ctrl, "--opp-inputs",
                   os.path.join(P.CODE, "docs", "INPUTS.csv"), "--map", mp, "--games", str(a.games), "--minutes", "10", "--procs", "2", "--swap",
                   "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225",
                   "--round", "600", "--opp-round", "600", "--head2-wadd", "0"]
            cmd += [x for s_ in sets for x in ("--set", s_)]
            cmd += W_.hold_args(a.save, ctrl)
            jobs.append((mp, js, subprocess.Popen(cmd, cwd=P.CODE, env=env, creationflags=0x4000 | 0x08000000, stdout=open(js + ".log", "w"),
                                                  stderr=subprocess.STDOUT)))
        for mp, js, p in jobs:
            p.wait()
            try:
                v = json.load(open(js))["maps"][mp]
                res[mp] = dict(share=v["frag_share"], won=v["won"], lost=v["lost"], hit=v["he"]["hit_rate"])
            except Exception as e:                           # noqa: BLE001
                res[mp] = dict(error=str(e))
    ok = [v for v in res.values() if "share" in v]
    W, L = sum(v["won"] for v in ok), sum(v["lost"] for v in ok)
    mean = sum(v["share"] for v in ok) / max(1, len(ok))
    with open(os.path.join(WD, "checks_blank.jsonl"), "a") as f:
        f.write(json.dumps(dict(update=a.update, mean=mean, won=W, lost=L, percept_speed=ps, wadd=0.0, minutes=round((time.time() - t0) / 60, 1), maps=res)) + "\n")
    print("blanked check update {}: {}-{} = {:.1%}, frag share {:.1%}".format(a.update, W, L, W / max(1, W + L), mean))


if __name__ == "__main__":
    main()
