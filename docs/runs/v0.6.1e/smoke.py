"""v0.6.1e's smoke run (2026-10-30): its train.cmd made small (2 workers, 8 matches, 96 steps, ~12 min, the CPU, the four E cores), from
v0.6.1's save of update 90 with v0.6.1's end's optimizer, into data/sim_runs/scratch_v061e_smoke, the rescale opened over 3 minutes.
Checks: the trainer exited 0 on the CPU; 20+ updates; the blend taken live; adv_pay in every update, above 1 after the opening at the
target 10; the pull and the brain's dial stepped to 1 together; the last save carries the dial and passes brain_fade_check; the old pay and the win pay measured (a smoke run's games are few: printed, and within a factor of 2.5); the save loads.
Refuses while a trainer runs or if the folder is there.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\v0.6.1e\\smoke.py > docs\\runs\\v0.6.1e\\smoke.log"""
import json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
K1 = os.path.join(SR, "duel_gru_v0_6_1", "keep")
RUN = "scratch_v061e_smoke"
D = os.path.join(SR, RUN)
BS = "\\"
W, V, G = 0.5, 0.5, 0.87


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
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
    shutil.copy2(os.path.join(K1, "policy_90.pt"), os.path.join(D, "policy.pt"))
    shutil.copy2(os.path.join(K1, "opt_end_v061.pt"), os.path.join(D, "opt.pt"))
    shutil.copy2(os.path.join(K1, "policy_90.pt"), os.path.join(D, "snapshots", "anchor_v061_u90.pt"))
    shutil.copy2(os.path.join(SR, "duel_gru_v0_6_0", "keep", "policy_end_v060.pt"), os.path.join(D, "snapshots", "anchor_v060_end.pt"))
    shutil.copy2(os.path.join(SR, "duel_gru_v0_6_1", "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(SR, "duel_gru_v0_6_1", "live.json"), encoding="utf-8"))
    lv.update(WIN_W=W, FADE_V=0.125, WIN_GAIN=0.33, ADV_PAY_REF=10.0, LEVEL_PULL=0.95, BRAIN_FADE=0.0, VALUE_WARM=0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("/affinity C3FFF", "/affinity 3C000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_v0_6_1e ", "--run " + RUN + " "),
            ("--minutes 720 --gamma", "--minutes 12 --gamma"), ("--adv-pay-warm 30 ", "--adv-pay-warm 3 "),
            ("data" + BS + "sim_runs" + BS + "duel_gru_v0_6_1e.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    cmd = os.path.join(D, "smoke.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    rp = subprocess.Popen([PY, os.path.join(HERE, "ramp_fades.py"), RUN, "--pay-steps", "5", "--pay-every", "1", "--poll", "5", "--min-s", "0", "--sleep", "5"], cwd=ROOT, env=env)
    say("the smoke trainer and the fades started")
    t0 = time.time()
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(10)
    if tr.poll() is None:
        say("the trainer still runs after 40 min: left running, FAILED")
        return 1
    if rp.poll() is None:
        rp.terminate()
    return checks()


def checks():
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
    check("the blend taken live", "'WIN_W': 0.5" in log and "'FADE_V': 0.5" in log and "'WIN_GAIN': 0.87" in log)
    ap_ = [m.get("adv_pay") for m in M]
    check("adv_pay in every update", None not in ap_)
    if None not in ap_:
        say("adv_pay first {} last {}".format(ap_[0], ap_[-1]))
        check("above 1 after the opening, the target 10", ap_[-1]["k"] > 1.0 and all(x["ref"] == 10.0 for x in ap_))
    B = [m["win_blend"] for m in M[-10:] if m.get("win_blend")]
    mean = lambda k: sum(b[k] for b in B) / max(1, len(B))  # noqa: E731
    win_, old_ = W * G * mean("win_g1_size"), (1 - W) * mean("combat_size") + (1 - V) * mean("other_size")
    say("sizes over the last 10 updates: win paid {:.2f} (gain 1 {:.2f}), old paid {:.2f} (combat {:.2f}, other {:.2f}), paid {:.2f}".format(
        win_, mean("win_g1_size"), old_, mean("combat_size"), mean("other_size"), mean("paid_size")))
    check("the win pay and the old pay within a factor of 2.5", old_ > 0 and win_ > 0 and 0.4 < win_ / old_ < 2.5)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    gs = [m.get("brain_fade", {}).get("g") for m in M]
    check("the brain's dial went 0 -> 1 ({})".format(sorted(set(gs), key=lambda x: -1 if x is None else x)), gs[0] == 0.0 and gs[-1] == 1.0)
    lv2 = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    check("live.json ended at BRAIN_FADE 1, LEVEL_PULL 1", lv2.get("BRAIN_FADE") == 1.0 and lv2.get("LEVEL_PULL") == 1.0)
    check("the blend still held at the end", lv2.get("WIN_W") == W and lv2.get("FADE_V") == V and lv2.get("WIN_GAIN") == G)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "brain_fade_check.py"), ROOT, os.path.join(D, "policy.pt")], cwd=ROOT, env=env)
    check("brain_fade_check on the last save", r.returncode == 0)
    import test_suite
    check("test_suite.Policy loads the last save", test_suite.Policy(os.path.join(D, "policy.pt")) is not None)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
