"""v0.6.1c's smoke run (2026-10-30): its train.cmd made small (2 workers, 8 matches, 96 steps, ~12 min, the CPU, the four E cores),
from v0.6.1's save of update 250 with v0.6.1's end's optimizer, into data/sim_runs/scratch_v061c_smoke, with the paired ramp
(BRAIN_FADE 0 -> 1 and LEVEL_PULL 0.95 -> 1 in two steps) and the rescaling opened over 3 minutes. Checks: the trainer exited 0
on the CPU; 20+ updates; adv_pay in every update, its factor 1 at the start, above 1 after the opening, within 1/max .. max; the
brain's dial and the pull both stepped to 1; the last save carries the dial at 1 and passes brain_fade_check; test_suite.Policy
loads it. Refuses while a trainer runs or if the folder is there.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\v0.6.1c\\smoke.py"""
import json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
K1 = os.path.join(SR, "duel_gru_v0_6_1", "keep")
RUN = "scratch_v061c_smoke"
D = os.path.join(SR, RUN)
BS = "\\"


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if "--check-only" in sys.argv:                                  # the checks again on a finished smoke run's outputs
        return checks(None)
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*train_duel_rnn*' } | Measure-Object).Count"],
                         capture_output=True, text=True).stdout.strip()
    if out != "0":
        say("a trainer is running: not started")
        return 1
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    os.makedirs(os.path.join(D, "snapshots"))
    os.makedirs(os.path.join(D, "keep"))
    shutil.copy2(os.path.join(K1, "policy_prelevel_v061.pt"), os.path.join(D, "policy.pt"))
    shutil.copy2(os.path.join(K1, "opt_end_v061.pt"), os.path.join(D, "opt.pt"))
    shutil.copy2(os.path.join(K1, "policy_prelevel_v061.pt"), os.path.join(D, "snapshots", "anchor_v061_u250.pt"))
    shutil.copy2(os.path.join(SR, "duel_gru_v0_6_0", "keep", "policy_end_v060.pt"), os.path.join(D, "snapshots", "anchor_v060_end.pt"))
    shutil.copy2(os.path.join(SR, "duel_gru_v0_6_1", "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(SR, "duel_gru_v0_6_1", "live.json"), encoding="utf-8"))
    lv.update(LEVEL_PULL=0.95, BRAIN_FADE=0.0, VALUE_WARM=0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("/affinity C3FFF", "/affinity 3C000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_v0_6_1c ", "--run " + RUN + " "),
            ("--minutes 720 --gamma", "--minutes 12 --gamma"), ("--adv-pay-warm 30 ", "--adv-pay-warm 3 "),
            ("data" + BS + "sim_runs" + BS + "duel_gru_v0_6_1c.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    cmd = os.path.join(D, "smoke.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    rp = subprocess.Popen([PY, os.path.join(ROOT, "tools", "run", "ramp_live.py"), RUN, "BRAIN_FADE", "0", "1", "0.5",
                           "--also", "LEVEL_PULL:0.95:1.0:0.025", "--min-s", "0", "--sleep", "5"], cwd=ROOT, env=env)
    say("the smoke trainer and the paired ramp started")
    t0 = time.time()
    live_set = None
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(10)
        if live_set is None and rp.poll() is not None:              # (the ramp done: live.json is ours) ADV_PAY_REF set live
            try:
                n_ = sum(1 for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip())
            except FileNotFoundError:
                n_ = 0
            d_ = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
            d_["ADV_PAY_REF"] = 12.0
            open(os.path.join(D, "live.json.tmp"), "w", encoding="utf-8").write(json.dumps(d_))
            os.replace(os.path.join(D, "live.json.tmp"), os.path.join(D, "live.json"))
            live_set = n_
            say("ADV_PAY_REF 12 set live after update {}".format(n_))
    if tr.poll() is None:
        say("the trainer still runs after 40 min: left running, FAILED")
        return 1
    if rp.poll() is None:
        rp.terminate()
    return checks(live_set)


def checks(live_set):
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
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
    ap_ = [m.get("adv_pay") for m in M]
    ks = [None if x is None else x["k"] for x in ap_]
    say("adv_pay k by update: {}".format(ks))
    say("adv_pay first {} last {}".format(ap_[0], ap_[-1]))
    check("adv_pay in every update", None not in ap_)
    if None not in ap_:
        check("its factor near 1 at the start (the opening has begun by the first update: {})".format(ks[0]), abs(ks[0] - 1.0) < 0.05)
        check("above 1 after the opening and within 1/4 .. 4", ks[-1] > 1.0 and all(0.25 <= k <= 4.0 for k in ks))
        refs = [x["ref"] for x in ap_]
        check("ADV_PAY_REF taken live: 8.5 before, 12 at the end ({} -> {})".format(refs[0], refs[-1]),
              refs[0] == 8.5 and refs[-1] == 12.0)
    gs = [m.get("brain_fade", {}).get("g") for m in M]
    check("the brain's dial went 0 -> 1 ({})".format(sorted(set(gs), key=lambda x: -1 if x is None else x)), gs[0] == 0.0 and gs[-1] == 1.0)
    lv2 = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    check("live.json ended at BRAIN_FADE 1, LEVEL_PULL 1 ({}, {})".format(lv2.get("BRAIN_FADE"), lv2.get("LEVEL_PULL")),
          lv2.get("BRAIN_FADE") == 1.0 and lv2.get("LEVEL_PULL") == 1.0)
    check("the trainer took LEVEL_PULL 1.0 live", "'LEVEL_PULL': 1.0" in log or "'LEVEL_PULL': '1.0'" in log)
    import torch
    last_ = os.path.join(D, "policy.pt")
    ck = torch.load(last_, map_location="cpu", weights_only=False)
    fd = (ck.get("belief") or {}).get("fade") or {}
    check("the last save carries the brain's dial at 1", fd.get("g") == 1.0)
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "brain_fade_check.py"), ROOT, last_], cwd=ROOT, env=cenv)
    check("brain_fade_check on that save", r.returncode == 0)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import test_suite
    check("test_suite.Policy loads it", test_suite.Policy(last_) is not None)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
