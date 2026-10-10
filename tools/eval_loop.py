"""Duels from the latest save of a run, again and again while it trains (below normal priority, on the cores the trainer
leaves idle: one trainer uses about a quarter of the PC): first head to head against the control (the last best
network; the owner's rule of 2026-10-10: in every check of every run), then against the Nightmare stand-in. One line
per check in data/sim_runs/<run>/evals_h2h.jsonl and evals.jsonl; the full cards in <run>/evals/.

    python tools/eval_loop.py <run> [games=48] [procs=8] [pause_min=10] [NAME=VALUE ...]      (Anaconda Python)

NAME=VALUE: the simulator switches the run plays with (as duel_eval's --set), for example
    AIM_LEVEL=3 ITEM_BELIEF=1 STYLE_P=0.75 INTENT_HOLD=8 KEY_RATE=8 AMMO_PACKS=0 GROUND_SENSE=1 DROPS=1
and three names of its own:
    MAPS=bloodrun,aerowalk,...        the stand-in's maps (default arena1,bloodrun,aerowalk)
    CONTROL=<policy file>             the control (default: the run folder's policy_start_*.pt, the network the run began
                                      from; "none" = no such check). It must take the same inputs as the run's network.
    CONTROL_MAPS=bloodrun,aerowalk    the maps of the duel against it
Started detached beside a run (a .cmd file, as the trainer is), it ends by itself 20 minutes after the run's last
update. The starting network is checked against the stand-in first if the run folder has a policy_start_*.pt. A check
is named by the minute of training at which it began (m6079: the update counter starts over at every resume) and plays
the trainer's latest save, which is up to ten updates older. Every fourth copy of the network is kept in <run>/evals
(for videos and heat maps). The stand-in is for checks only, never a training opponent.

Why the control: v14's second start took 53% of the frags from its own last eight snapshots all night, held 55 to 58%
against the stand-in, and lost to the network it began from 137 games to 41 (RESULTS 2026-10-10 06:30).
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
OWN = ("MAPS", "CONTROL", "CONTROL_MAPS")
own = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a and a.split("=", 1)[0] in OWN)
SETS = [a for a in sys.argv[1:] if "=" in a and a.split("=", 1)[0] not in OWN]
run = args[0]
games = args[1] if len(args) > 1 else "48"
procs = args[2] if len(args) > 2 else "8"
pause = float(args[3]) if len(args) > 3 else 10.0
D = os.path.join(ROOT, "data", "sim_runs", run)
E = os.path.join(D, "evals")
os.makedirs(E, exist_ok=True)
LOW = 0x00004000 if os.name == "nt" else 0                   # below normal priority: the trainer goes first
MAPS = own.get("MAPS", "arena1,bloodrun,aerowalk")
start = sorted(glob.glob(os.path.join(D, "policy_start_*.pt")))
CONTROL = own.get("CONTROL", start[0] if start else "none")
CONTROL_MAPS = own.get("CONTROL_MAPS", "bloodrun,aerowalk")


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


def duels(policy, opp, maps, out):
    cmd = [PY, "tools/duel_eval.py", "--run", run, "--policy", policy, "--opp", opp, "--map", maps,
           "--games", games, "--minutes", "10", "--procs", procs, "--json", out]
    for s in SETS:
        cmd += ["--set", s]
    r = subprocess.run(cmd, cwd=ROOT, creationflags=LOW, stdout=open(os.path.join(E, "eval_loop.log"), "a"), stderr=subprocess.STDOUT)
    return json.load(open(out)) if r.returncode == 0 and os.path.exists(out) else None


def head_to_head(policy, label, update, minutes):
    """the save against the control, the same games and seeds every time"""
    d = duels(policy, "policy:" + CONTROL, CONTROL_MAPS, os.path.join(E, "h2h_{}.json".format(label)))
    if d is None:
        return
    with open(os.path.join(D, "evals_h2h.jsonl"), "a") as f:
        f.write(json.dumps(dict(label=label, update=update, minutes=minutes, wall=time.strftime("%Y-%m-%d %H:%M:%S"), against=os.path.basename(CONTROL),
                                maps={mp: dict(frag_share=v["frag_share"], won=v["won"], drawn=v["drawn"], lost=v["lost"])
                                      for mp, v in d["maps"].items()})) + "\n")


def check(policy, label, update, minutes):
    if label != "start" and CONTROL != "none":               # the control first: it is the number a run stands or falls by
        try:
            head_to_head(policy, label, update, minutes)
        except Exception:                                    # noqa: BLE001
            pass
    t0 = time.time()
    d = duels(policy, "nightmare", MAPS, os.path.join(E, "eval_{}.json".format(label)))
    if d is None:
        return False
    rec = dict(label=label, update=update, minutes=minutes, wall=time.strftime("%Y-%m-%d %H:%M:%S"), took_min=round((time.time() - t0) / 60, 1),
               games=int(games), maps={})
    for mp, v in d["maps"].items():
        h, o = v["he"], v["opponent"]
        rec["maps"][mp] = dict(frag_share=v["frag_share"], ci=v["frag_share_95"], score=[h["score"], o["score"]], kills=[h["kills"], o["kills"]],
                               won=v["won"], drawn=v["drawn"], lost=v["lost"], bare=h["time_bare"], stack150=h["stack_150_up"],
                               speed=h["speed"], mega=h["mega_share"], red=h["red_share"], yellow=h["yellow_per_min"],
                               weapons=h["weapons_per_min"], own_deaths=h["own_deaths"], first_weapon_s=h["first_weapon_s"],
                               in_view=h["in_view"], firing_in_view=h["firing_in_view"], opp_red=o["red_share"], opp_mega=o["mega_share"],
                               opp_stack150=o["stack_150_up"], lower=h.get("lower"), higher=h.get("higher"))
    with open(os.path.join(D, "evals.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return True


if start and not os.path.exists(os.path.join(E, "eval_start.json")):
    check(start[0], "start", 0, 0.0)
kept = 0
while True:
    upd, mins = last_metrics()
    mp_ = os.path.join(D, "metrics.jsonl")
    age = time.time() - os.path.getmtime(mp_) if os.path.exists(mp_) else 0
    label = "m{:04d}".format(int(mins))
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
