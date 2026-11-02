"""b1.3a's smoke run (2026-11-01): its train.cmd made small (2 workers, 8 matches, 96 steps, ~12 min, the CPU, the four E cores, none of the trainer's), from b1.2a's end (or, before it exists, its latest save),
with every dial at its end value (contact 1, damage taken 0.65, the rule 0), into data/sim_runs/scratch_b13a_smoke. It may run beside a trainer. Checks: the trainer exited 0 on the CPU, 10 updates or more; the head loaded and its gate open;
contacts counted and free; the pay's damage term as the dial says; the dials in force and in the last save; a save loads for the checks; a one-map check with each seat's own contact finishes.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.3\\b1.3a\\smoke.py > docs\\runs\\b1.3\\b1.3a\\smoke.log"""
import json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_b1_2a")
RUN = "scratch_b13a_smoke"
D = os.path.join(SR, RUN)
BS = "\\"


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    END, OPT = os.path.join(R0, "keep", "policy_end_b12a.pt"), os.path.join(R0, "keep", "opt_end_b12a.pt")
    if not os.path.exists(END):
        END, OPT = os.path.join(R0, "policy.pt"), os.path.join(R0, "opt.pt")
    say("from " + END)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    os.makedirs(os.path.join(D, "snapshots"))
    os.makedirs(os.path.join(D, "keep"))
    os.makedirs(os.path.join(D, "watch"))
    shutil.copy2(END, os.path.join(D, "policy.pt"))
    shutil.copy2(OPT, os.path.join(D, "opt.pt"))
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_b12a.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(H2_GATE_CAP=1.0, H2_GATE_OPEN=1.0, INTENT_TEACH_W=0.0, VALUE_WARM=0, BRAIN_FADE=1.0, LEVEL_PULL=1.0, INTENT_HOLD=8.0, CONTACT_FREE=1.0, DMG_TAKEN_W=0.65)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("/affinity C3FFF", "/affinity 3C000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_b1_3a ", "--run " + RUN + " "),
            ("--minutes 1440 --gamma", "--minutes 12 --gamma"),
            ("data" + BS + "sim_runs" + BS + "duel_gru_b1_3a.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
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
    h1 = M[-1].get("head2") or {}
    say("head2 last: {}".format(h1))
    check("the head's gate open", h1.get("gate") == 1.0)
    check("its links not zero (plan_in {}, target {})".format(h1.get("plan_in_w"), h1.get("target_w")), (h1.get("plan_in_w") or 0) > 0 and (h1.get("target_w") or 0) > 0)
    C = [m.get("contact") or [0] * 5 for m in M[-10:]]
    say("contact, the last 10 updates (begun, free, readings, changes, to the enemy): {}".format(C))
    check("contacts begun and all free", sum(c[0] for c in C) > 0 and all(c[0] == c[1] for c in C))
    check("readings and changes in them", sum(c[2] for c in C) > 0 and sum(c[3] for c in C) > 0)
    P = [m["pay_terms"]["per_player_min"] for m in M[-10:] if m.get("pay_terms")]
    dd, dt = sum(p.get("dmg_dealt", 0) for p in P), sum(p.get("dmg_taken", 0) for p in P)
    say("damage pay, the last 10 updates: dealt {:.3f}, taken {:.3f}".format(dd, dt))
    check("damage taken costs less than damage dealt pays, and more than 0.65 of it less a margin", dd > 0 and 0.5 * dd < -dt < 0.98 * dd)
    check("the rule at 0 in force", all((m.get("intent_teach") or [1])[0] == 0 for m in M[-5:]))
    import torch
    last_ = os.path.join(D, "policy.pt")
    ck = torch.load(last_, map_location="cpu", weights_only=False)
    ev = ck.get("env_vars") or {}
    check("the last save: the head, contact 1, the lock at 8 s", ck.get("head2") is not None and float(ev.get("CONTACT_FREE", -1)) == 1.0 and float(ev.get("INTENT_HOLD", -1)) == 8.0)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import test_suite
    check("test_suite.Policy loads it", test_suite.Policy(last_) is not None)
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "head2head.py"), "smoke", RUN, last_, "8", os.path.join(R0, "keep", "policy_30.pt"), "8", "--maps", "bloodrun", "--games", "2", "--contact-a", "1", "--contact-b", "0"], cwd=ROOT, env=cenv, capture_output=True, text=True)
    say(r.stdout[-300:].strip())
    check("a check with each seat's own contact finishes", r.returncode == 0 and "ERROR" not in r.stdout)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
