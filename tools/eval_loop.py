"""Duels against the Nightmare stand-in from the latest save of a run, again and again while it trains (below normal
priority, on the cores the trainer leaves idle: one trainer uses about a quarter of the PC). One line per check in
data/sim_runs/<run>/evals.jsonl; the full cards in <run>/evals/.

    python tools/eval_loop.py <run> [games=48] [procs=8] [pause_min=10] [NAME=VALUE ...]      (Anaconda Python)

NAME=VALUE: the simulator switches the run plays with (as duel_eval's --set), for example
    AIM_LEVEL=3 ITEM_BELIEF=1 STYLE_P=0.75 INTENT_HOLD=8 KEY_RATE=8 AMMO_PACKS=0 GROUND_SENSE=1 DROPS=1
Started detached beside a run (a .cmd file, as the trainer is), it ends by itself 20 minutes after the run's last
update. The starting network is checked first if the run folder has a policy_start_*.pt. The trainer saves every ten
updates: a check labelled u0016 plays the save of update 10. Every fourth copy of the network is kept in <run>/evals
(for videos and heat maps). The stand-in is for checks only, never a training opponent.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
args = [a for a in sys.argv[1:] if "=" not in a]
SETS = [a for a in sys.argv[1:] if "=" in a]
run = args[0]
games = args[1] if len(args) > 1 else "48"
procs = args[2] if len(args) > 2 else "8"
pause = float(args[3]) if len(args) > 3 else 10.0
D = os.path.join(ROOT, "data", "sim_runs", run)
E = os.path.join(D, "evals")
os.makedirs(E, exist_ok=True)
LOW = 0x00004000 if os.name == "nt" else 0                   # below normal priority: the trainer goes first


def last_metrics():
    try:
        with open(os.path.join(D, "metrics.jsonl"), "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 60000))
            line = f.read().decode("utf-8", "replace").strip().splitlines()[-1]
        m = json.loads(line)
        return m["update"], m["minutes"]
    except Exception:                                        # noqa: BLE001
        return 0, 0.0


def check(policy, label, update, minutes):
    out = os.path.join(E, "eval_{}.json".format(label))
    cmd = [PY, "tools/duel_eval.py", "--run", run, "--policy", policy, "--opp", "nightmare", "--map", "arena1,bloodrun,aerowalk",
           "--games", games, "--minutes", "10", "--procs", procs, "--json", out]
    for s in SETS:
        cmd += ["--set", s]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=ROOT, creationflags=LOW, stdout=open(os.path.join(E, "eval_loop.log"), "a"), stderr=subprocess.STDOUT)
    if r.returncode != 0 or not os.path.exists(out):
        return False
    d = json.load(open(out))
    rec = dict(label=label, update=update, minutes=minutes, wall=time.strftime("%Y-%m-%d %H:%M:%S"), took_min=round((time.time() - t0) / 60, 1),
               games=int(games), maps={})
    for mp, v in d["maps"].items():
        h, o = v["he"], v["opponent"]
        rec["maps"][mp] = dict(frag_share=v["frag_share"], ci=v["frag_share_95"], score=[h["score"], o["score"]], kills=[h["kills"], o["kills"]],
                               won=v["won"], drawn=v["drawn"], lost=v["lost"], bare=h["time_bare"], stack150=h["stack_150_up"],
                               speed=h["speed"], mega=h["mega_share"], red=h["red_share"], yellow=h["yellow_per_min"],
                               weapons=h["weapons_per_min"], own_deaths=h["own_deaths"], first_weapon_s=h["first_weapon_s"],
                               in_view=h["in_view"], firing_in_view=h["firing_in_view"], opp_red=o["red_share"], opp_mega=o["mega_share"],
                               opp_stack150=o["stack_150_up"])
    with open(os.path.join(D, "evals.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return True


start = sorted(glob.glob(os.path.join(D, "policy_start_*.pt")))
if start and not os.path.exists(os.path.join(E, "eval_start.json")):
    check(start[0], "start", 0, 0.0)
kept = 0
while True:
    upd, mins = last_metrics()
    mp_ = os.path.join(D, "metrics.jsonl")
    age = time.time() - os.path.getmtime(mp_) if os.path.exists(mp_) else 0
    label = "u{:04d}".format(upd)
    if upd > 0 and not os.path.exists(os.path.join(E, "eval_{}.json".format(label))):
        cp = os.path.join(E, "policy_{}.pt".format(label))
        ok = False
        for attempt in range(3):
            try:
                shutil.copy(os.path.join(D, "policy.pt"), cp)
                ok = check(cp, label, upd, mins)
            except Exception:                                # noqa: BLE001
                ok = False
            if ok:
                break
            time.sleep(60)
        kept += 1
        if ok and kept % 4 != 1 and os.path.exists(cp):      # every fourth copy stays
            os.remove(cp)
    if age > 20 * 60:                                        # the trainer has stopped
        break
    time.sleep(pause * 60)
