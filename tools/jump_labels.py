"""Which of the pros' jumps the movement teacher may label (v15, BACKLOG B-209): per jump, a player alone in jump runs
who presses exactly the teacher's labels with his hands (as tools/label_check.py, with JUMP_ALL: every jump that has
tries). A jump at which he comes to the take-off in less than --min-edge of the tries is written to
sim/jump_labels.json: the teacher's own way goes round that jump from where his tries begin, and in the simulator it then
gives no labels before that jump's landing; he learns the try by the pay alone. A jump the pupil goes for and seldom
lands keeps its labels (owner, 2026-10-10: "the jumps don't need to be exact ... he should be taught the general path,
there's many ways to execute them").

    python tools/jump_labels.py --teacher move_v15i            measure the ten maps (a process a map), write the list
    python tools/jump_labels.py --teacher move_v15i --check    the same test with the list applied: what is left

A table per map: tries at how many jumps, how many the teacher labels, the pupil's rate over those.
"""
import argparse
import json
import os
import subprocess
import sys

for k_ in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(k_, "2")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("QLBOT_ROOT") or os.path.dirname(HERE)
SIM = os.path.join(os.path.dirname(HERE), "sim")
OUT = os.path.join(SIM, "jump_labels.json")
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure"
VARS = dict(RUNNER_P="0", COLLECT_FIGHT_P="0", INTENT_HOLD="8", STYLE_P="0", PRO_ITEMS="1", ITEM_BELIEF="1", AMMO_PACKS="0",
            AIM_LEVEL="3", KEY_RATE="8", GROUND_SENSE="1", DROPS="1", SHOT_MASK="1", LAVA="1", WALK_FIX="1", QL_MOVE="1",
            ITEM_DROP="1", SOLIDS="1", PRO_WAYS="1", NEAREST="1", RULE_WALK="1", RUN_TEACHER="1", STACK_KEYS="0",
            TEACH_KEYS_ONLY="0", JUMPS="1", JUMP_ALL="1", PROJ_SEE="1", GL_QL="1", ITEM_RUN_P="0", JUMP_RUN_P="1.0")


def one(mapname, teacher, steps, use_list):
    """one map in this process: a JSON line"""
    os.environ.update(VARS)
    sys.path.insert(0, SIM)
    import numpy as np
    import duel_env_ffa as E
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mapname + ".bsp"), n_matches=32, seed=1,
                    nav=os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mapname)), close_p=1.0, loadout="all",
                    teacher=os.path.join(ROOT, "data", "sim_runs", teacher, "policy.npz"))
    env.item_reward, env.intent_seek, env.item_loss, env.dmg_reward = 0.75, 1.0, 0.5, 0.005
    env.kind_p, env.bot_p, env.runner_p = (1.0, 0.0, 0.0, 0.0), 0.0, 0.0
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    if not use_list:
        env.jump_lab_off[:] = False                         # the measurement: its labels at every jump
    env.round_t[:] = 1e9
    n = env.n
    base = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
    base[:, 0], base[:, 1] = 1, 1                            # no forward or strafe key where there is no label
    base[:, 3], base[:, 4] = len(E.TURN) // 2, len(E.PITCH) // 2
    env.step(base.copy())
    h0 = float(env.stats["hurt_dmg"])
    edge, was = np.zeros(len(env.jumps)), np.zeros(n, bool)
    for _ in range(steps):
        act = base.copy()
        lab = env.teach[:, :4]
        on = env.jrun & (env.hp > 0)
        for j in range(4):
            act[:, j] = np.where(on & (lab[:, j] >= 0), lab[:, j], act[:, j])
        env.step(act)
        now = env.jrun & env.jrun_edge                       # came to the take-off in this try (counted once a try)
        np.add.at(edge, env.jrun_k[now & ~was], 1)
        was = now
    K = len(env.jumps)
    tr, ov, sh = (env.stats[k][:K] for k in ("jump_tries", "jump_over", "jump_short"))
    print(json.dumps(dict(map=mapname, lava_per_min=round((float(env.stats["hurt_dmg"]) - h0) / (steps * n * E.DT / 60.0), 1),
                          jumps=[dict(id=int(j["id"]), need=int(j["need"]), tries=int(tr[k]), over=round(float(ov[k] / max(1.0, tr[k])), 3),
                                      short=round(float(sh[k] / max(1.0, tr[k])), 3), edge=round(float(min(1.0, edge[k] / max(1.0, tr[k]))), 3), off=bool(env.jump_lab_off[k]),
                                      has=k in env.jump_tries) for k, j in enumerate(env.jumps)])), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True, help="a movement run with a policy.npz (sim/export_policy.py)")
    ap.add_argument("--map", default=MAPS)
    ap.add_argument("--steps", type=int, default=2400)
    ap.add_argument("--min-edge", type=float, default=0.5, help="at the take-off in under this share of --min-tries tries or more: no labels")
    ap.add_argument("--min-tries", type=int, default=15)
    ap.add_argument("--check", action="store_true", help="test with the list applied; nothing is written")
    ap.add_argument("--one", default="", help="(a map in this process)")
    ap.add_argument("--procs", type=int, default=5)
    a = ap.parse_args()
    if a.one:
        one(a.one, a.teacher, a.steps, a.check)
        return
    maps, res, running = a.map.split(","), {}, []
    todo = list(maps)
    while todo or running:
        while todo and len(running) < a.procs:
            m = todo.pop(0)
            cmd = [sys.executable, os.path.abspath(__file__), "--teacher", a.teacher, "--steps", str(a.steps), "--one", m] + (["--check"] if a.check else [])
            running.append((m, subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)))
        m, p = running.pop(0)
        out = p.communicate()[0].strip().splitlines()
        res[m] = json.loads(out[-1]) if out and out[-1].startswith("{") else None
    off, rates, tot = {}, {}, [0, 0, 0]
    print("{:15s} | tries at | the teacher labels | his pupil over, at those | goes for it and lands under 15% | no labels at (its way goes round) | no tries at".format("map"))
    for m in maps:
        r = res.get(m)
        if r is None:
            print("{:15s} | FAILED".format(m))
            continue
        J = [j for j in r["jumps"] if j["has"]]
        low = [j for j in J if (j["off"] if a.check else (j["tries"] >= a.min_tries and j["edge"] < a.min_edge))]
        lab = [j for j in J if j not in low]
        off[m] = sorted(j["id"] for j in low)
        rates[m] = {str(j["id"]): dict(tries=j["tries"], at_take_off=j["edge"], over=j["over"], short=j["short"]) for j in J}
        tot[0] += len(r["jumps"]); tot[1] += len(J); tot[2] += len(lab)
        print("{:15s} | {:2d} of {:2d} | {:2d} | {:.0%} of {} tries | {} | {} | {}".format(
            m, len(J), len(r["jumps"]), len(lab), sum(j["over"] * j["tries"] for j in lab) / max(1, sum(j["tries"] for j in lab)),
            sum(j["tries"] for j in lab), " ".join("{}:{:.0%}".format(j["id"], j["over"]) for j in lab if j["over"] < 0.15) or "-",
            " ".join(str(i) for i in off[m]) or "-", " ".join(str(j["id"]) for j in r["jumps"] if not j["has"]) or "-"))
    print("jumps in use {}, with tries for him {}, labelled by the teacher {}".format(*tot))
    if not a.check:
        json.dump(dict(teacher=a.teacher, min_edge=a.min_edge, min_tries=a.min_tries, steps=a.steps, off=off, rates=rates), open(OUT, "w"), indent=1)
        print("wrote", OUT)


if __name__ == "__main__":
    main()
