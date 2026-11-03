"""b1.1a's smoke run (2026-10-31): its train.cmd made small (2 workers, 8 matches, 96 steps, ~12 min, the CPU, the four E cores, none of the trainer's), from b1.0a's latest save, into
data/sim_runs/scratch_b11a_smoke3, the two fades in two steps each. Checks: the trainer exited 0 on the CPU; WIN_ADD, WIN_W, FADE_V as b1.0a left them; the brain out first, then the pull, then the lock, all at their ends;
the saves before each fade kept; the last save passes brain_fade_check and loads. It may run beside a trainer (no shared core, no card). Refuses if the folder is there.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.1\\b1.1a\\smoke.py > docs\\runs\\b1.1\\b1.1a\\smoke.log"""
import json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_b1_0a")
RUN = "scratch_b11a_smoke3"
D = os.path.join(SR, RUN)
BS = "\\"


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    os.makedirs(os.path.join(D, "snapshots"))
    os.makedirs(os.path.join(D, "keep"))
    for a, b in (("policy.pt", "policy.pt"), ("opt.pt", "opt.pt"), ("live_settings.env", "live_settings.env")):
        shutil.copy2(os.path.join(R0, a), os.path.join(D, b))
    shutil.copy2(os.path.join(D, "policy.pt"), os.path.join(D, "snapshots", "anchor_b10a.pt"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(LEVEL_PULL=0.95, BRAIN_FADE=0.0, INTENT_HOLD=8.0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("/affinity C3FFF", "/affinity 3C000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_b1_1a ", "--run " + RUN + " "),
            ("--minutes 855 --gamma", "--minutes 12 --gamma"),
            ("data" + BS + "sim_runs" + BS + "duel_gru_b1_1a.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    cmd = os.path.join(D, "smoke.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    rp = subprocess.Popen([PY, os.path.join(HERE, "ramp_b11.py"), RUN, "--shut", "1", "--hold-pull", "1", "--hold-lock", "1", "--brain-steps", "2", "--pull-steps", "2", "--min-s", "0", "--poll", "5"], cwd=ROOT, env=env)
    say("the smoke trainer and the ramp started")
    t0 = time.time()
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(10)
    if tr.poll() is None:
        say("the trainer still runs after 40 min: left running, FAILED")
        return 1
    rp.terminate()
    return checks(lv)


def checks(lv):
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
    lv2 = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    check("LEVEL_PULL 1, BRAIN_FADE 1, INTENT_HOLD 1 at the end ({}, {}, {})".format(lv2.get("LEVEL_PULL"), lv2.get("BRAIN_FADE"), lv2.get("INTENT_HOLD")), lv2.get("LEVEL_PULL") == 1.0 and lv2.get("BRAIN_FADE") == 1.0 and lv2.get("INTENT_HOLD") == 1.0)
    check("the pay untouched (WIN_ADD {})".format(lv2.get("WIN_ADD")), all(lv2.get(k) == lv.get(k) for k in ("WIN_ADD", "WIN_W", "FADE_V", "WIN_GAIN")) and lv.get("WIN_ADD", 0) > 0)
    R = open(os.path.join(D, "watch", "ramp.log")).read()
    check("the brain, then the pull, then the lock", 0 < R.find("ramp_live done: BRAIN_FADE") < R.find("RAMP LEVEL_PULL") and R.find("ramp_live done: LEVEL_PULL") < R.find("RAMP INTENT_HOLD") and "ramp_live done: INTENT_HOLD at 1.0" in R)
    check("the lock's steps 4, 2, 1", all("RAMP INTENT_HOLD " + x in R for x in ("4.0", "2.0", "1.0")))
    check("the lock taken live", "'INTENT_HOLD': '1.0'" in log)
    import torch
    ev_ = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False).get("env_vars") or {}
    check("the last save carries the lock ({})".format(ev_.get("INTENT_HOLD")), float(ev_.get("INTENT_HOLD", -1)) == 1.0)
    gs = [m.get("brain_fade", {}).get("g") for m in M]
    check("the brain's dial went 0 -> 1 ({})".format(sorted(set(gs), key=lambda x: -1 if x is None else x)), gs[0] == 0.0 and gs[-1] == 1.0)
    check("the saves before each fade kept", all(os.path.exists(os.path.join(D, "keep", f)) for f in ("policy_prebrain_b11a.pt", "policy_nobrain_b11a.pt", "policy_nopull_b11a.pt")))
    check("win pay still in force in the last updates", all((m.get("win_blend") or {}).get("blend_frames", 0) > 0 for m in M[-5:]))
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "brain_fade_check.py"), ROOT, os.path.join(D, "policy.pt")], cwd=ROOT, env=env)
    check("brain_fade_check on the last save", r.returncode == 0)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import test_suite
    check("test_suite.Policy loads the last save", test_suite.Policy(os.path.join(D, "policy.pt")) is not None)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
