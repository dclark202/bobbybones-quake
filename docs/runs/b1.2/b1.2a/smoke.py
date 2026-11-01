"""b1.2a's smoke run (2026-10-31): its train.cmd made small (2 workers, 8 matches, 96 steps, ~12 min, the CPU, the four E cores, none of the trainer's), from b1.0a's end given the head with its gate forced open and the three dials at
their ends (brain 1, pull 1, lock 1 s), as b1.1a should leave him, into data/sim_runs/scratch_b12a_smoke. It may run beside a trainer. Checks: the trainer exited 0 on the CPU; the head's value and lesson finite, its links up from zero, its bias a share of his
target choice; its pay is combat plus win, smaller than his whole pay and not equal to it; the win pay in force; the last save loads, with the head, the dial at 1 and the lock at 1 s. Refuses if the folder is there.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.2\\b1.2a\\smoke.py > docs\\runs\\b1.2\\b1.2a\\smoke.log"""
import json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_b1_0a")
RUN = "scratch_b12a_smoke"
D = os.path.join(SR, RUN)
BS = "\\"


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    END = os.path.join(R0, "keep", "policy_end_b10a.pt")
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    os.makedirs(os.path.join(D, "snapshots"))
    os.makedirs(os.path.join(D, "keep"))
    os.makedirs(os.path.join(D, "watch"))
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "head2_init.py"), "add", END, os.path.join(D, "policy.pt"), "--gate", "1", "--ctrl-src", "belief",
                        "--opt", os.path.join(R0, "keep", "opt_end_b10a.pt"), os.path.join(D, "opt.pt")], cwd=ROOT, env=cenv)
    if r.returncode:
        say("head2_init add failed")
        return 1
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_b10a.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(H2_GATE_CAP=1.0, H2_GATE_OPEN=1.0, INTENT_TEACH_W=1.0, VALUE_WARM=0, BRAIN_FADE=1.0, LEVEL_PULL=1.0, INTENT_HOLD=1.0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("/affinity C3FFF", "/affinity 3C000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_b1_2a ", "--run " + RUN + " "),
            ("--minutes 1440 --gamma", "--minutes 12 --gamma"), ("--head2-cap 0 --head2-gate 0 ", "--head2-cap 1 --head2-gate 1 "),
            ("data" + BS + "sim_runs" + BS + "duel_gru_b1_2a.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
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
    check("20 or more updates ({})".format(len(M)), len(M) >= 20)
    h0, h1 = M[0].get("head2") or {}, M[-1].get("head2") or {}
    say("head2 first: {}".format(h0))
    say("head2 last:  {}".format(h1))
    check("the head's gate open", h1.get("gate") == 1.0)
    check("the head's value and lesson finite", all(isinstance(h1.get(k), (int, float)) and abs(h1[k]) < 1e6 for k in ("v_loss", "pg_loss")))
    check("its links rose from zero (plan_in {}, target {})".format(h1.get("plan_in_w"), h1.get("target_w")), (h1.get("plan_in_w") or 0) > 0 and (h1.get("target_w") or 0) > 0)
    check("its bias a share of his target choice ({})".format(h1.get("bias_share")), (h1.get("bias_share") or 0) > 0)
    pa = [(m.get("head2") or {}).get("pay_abs") for m in M[-10:]]
    check("its pay is combat_win", all((m.get("head2") or {}).get("pay") == "combat_win" for m in M))
    pa = [x for x in pa if x]
    hs, ms = sum(x[0] for x in pa) / max(1, len(pa)), sum(x[1] for x in pa) / max(1, len(pa))
    say("a frame's |pay|, the last 10 updates: the head's {:.5f}, his {:.5f}".format(hs, ms))
    check("the head's pay is not his whole pay and not zero", 0 < hs and abs(hs - ms) > 1e-5)
    check("the win pay in force", all((m.get("win_blend") or {}).get("blend_frames", 0) > 0 for m in M[-5:]))
    lv2 = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    check("the dials as set (WIN_ADD {}, rule {})".format(lv2.get("WIN_ADD"), lv2.get("INTENT_TEACH_W")), lv2.get("WIN_ADD", 0) > 0 and lv2.get("INTENT_TEACH_W") == 1.0)
    import torch
    last_ = os.path.join(D, "policy.pt")
    ck = torch.load(last_, map_location="cpu", weights_only=False)
    fd = (ck.get("belief") or {}).get("fade") or {}
    check("the last save: the head, the brain's dial at 1, the lock at 1 s", ck.get("head2") is not None and fd.get("g") == 1.0 and float((ck.get("env_vars") or {}).get("INTENT_HOLD", -1)) == 1.0)
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "brain_fade_check.py"), ROOT, last_], cwd=ROOT, env=cenv)
    check("brain_fade_check on that save", r.returncode == 0)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import test_suite
    check("test_suite.Policy loads it", test_suite.Policy(last_) is not None)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
