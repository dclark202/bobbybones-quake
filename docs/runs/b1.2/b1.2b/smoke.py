"""b1.2b's smoke run (2026-11-01): its train.cmd made small (2 workers, 8 matches, 96 steps, ~12 min, the CPU, the four E cores), from b1.1,
with every dial at its end value (the table on, contact free, the firing costs and the jerk at 0), into data/sim_runs/scratch_b12b_smoke. It may run beside a trainer. Checks: the trainer exited 0 on the CPU, 10 updates or more; no head;
the ledger as the dials say; the counters by item; the dials in the last save; a save loads for the checks; a one-map check with each seat's own contact finishes.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.2\\b1.2b\\smoke.py > docs\\runs\\b1.2\\b1.2b\\smoke.log"""
import json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_b1_1a")
RUN = "scratch_b12b_smoke"
D = os.path.join(SR, RUN)
BS = "\\"


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    END, OPT = os.path.join(R0, "keep", "policy_b1.1.pt"), os.path.join(R0, "keep", "opt_b1.1.pt")
    say("from " + END)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    os.makedirs(os.path.join(D, "snapshots"))
    os.makedirs(os.path.join(D, "keep"))
    os.makedirs(os.path.join(D, "watch"))
    shutil.copy2(END, os.path.join(D, "policy.pt"))
    shutil.copy2(OPT, os.path.join(D, "opt.pt"))
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_b11.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(INTENT_TEACH_W=1.0, VALUE_WARM=0, BRAIN_FADE=1.0, LEVEL_PULL=1.0, INTENT_HOLD=8.0, ITEM_RATE_HP=0.0025, ITEM_RATE_AR=0.002, COST_FIRE_W=0.0, COST_JERK_W=0.0, CONTACT_FREE=1.0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("/affinity C3FFF", "/affinity 3C000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_b1_2b ", "--run " + RUN + " "),
            ("--minutes 1150 --gamma", "--minutes 12 --gamma"),
            ("data" + BS + "sim_runs" + BS + "duel_gru_b1_2b.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    cmd = os.path.join(D, "smoke.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    say("the smoke trainer started")
    t0 = time.time()
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(10)
    if tr.poll() is None:
        say("the trainer still runs after 40 min: left running, FAILED")
        return 1
    return checks(cenv)


def checks(cenv):
    log = open(os.path.join(SR, RUN + ".log"), encoding="utf-8", errors="replace").read()
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        say(("PASS " if cond else "FAIL ") + name)

    check("the trainer exited 0", log.rstrip().splitlines()[-1].strip() == "exit 0")
    check("on the CPU", "device cpu" in log)
    M = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    check("10 or more updates ({})".format(len(M)), len(M) >= 10)
    C = [m.get("contact") or [0] * 5 for m in M[-10:]]
    say("contact, the last 10 updates (begun, free, readings, changes, to the enemy): {}".format(C))
    check("contacts begun and all free", sum(c[0] for c in C) > 0 and all(c[0] == c[1] for c in C))
    check("readings and changes in them", sum(c[2] for c in C) > 0 and sum(c[3] for c in C) > 0)
    P = [m["pay_terms"]["per_player_min"] for m in M[-5:] if m.get("pay_terms")]
    say("the ledger, the last update: {}".format(P[-1] if P else None))
    check("no shot price, fire toggle, weapon switch or jerk in the ledger", P and all(abs(p.get(k, 0)) < 1e-9 for p in P for k in ("shot_price", "fire_toggle", "weapon_switch", "jerk")))
    check("the small items paid (item_flat_other in the ledger)", any(p.get("item_flat_other", 0) != 0 or p.get("items_other", 0) != 0 for p in P))
    say("pickups by item, the last update: {}".format(M[-1].get("pick_by")))
    check("the counters by item", bool(M[-1].get("pick_by")) and sum(v[0] for v in M[-1]["pick_by"].values()) > 0)
    check("the rule at its floor in force", all((m.get("intent_teach") or [0])[0] > 0 for m in M[-5:]))
    import torch
    last_ = os.path.join(D, "policy.pt")
    ck = torch.load(last_, map_location="cpu", weights_only=False)
    ev = ck.get("env_vars") or {}
    say("the last save's dials: {}".format({k: ev.get(k) for k in ("INTENT_HOLD", "ITEM_RATE_HP", "ITEM_RATE_AR", "COST_FIRE_W", "COST_JERK_W", "CONTACT_FREE")}))
    check("the last save: no head, the lock at 8 s, contact 1", ck.get("head2") is None and float(ev.get("INTENT_HOLD", -1)) == 8.0 and float(ev.get("CONTACT_FREE", -1)) == 1.0)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import test_suite
    check("test_suite.Policy loads it", test_suite.Policy(last_) is not None)
    opp = os.path.join(R0, "keep", "policy_b1.1.pt")
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "head2head.py"), "smoke", RUN, last_, "8", opp, "8", "--maps", "bloodrun", "--games", "2", "--contact-a", "1", "--contact-b", "0"], cwd=ROOT, env=cenv, capture_output=True, text=True)
    say(r.stdout[-300:].strip())
    check("a check with each seat's contact finishes", r.returncode == 0 and "ERROR" not in r.stdout)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
