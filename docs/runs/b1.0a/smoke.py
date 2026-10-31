"""b1.0a's smoke run (2026-10-31): its train.cmd made small (2 workers, 8 matches, 96 steps, ~12 min, the CPU, the four E cores), from v0.6.0's end with its optimizer,
into data/sim_runs/scratch_b10a_smoke, ramp_win.py's whole schedule in a few updates. Checks: the trainer exited 0 on the CPU; 12+ updates; WIN_ADD taken live to 0.33;
WIN_W and FADE_V still 0; no rescale; the sizes printed, the paid size above the table's alone once the win part is in; the save loads. Refuses while a trainer runs or if the folder is there.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.0a\\smoke.py > docs\\runs\\b1.0a\\smoke.log"""
import json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
K0 = os.path.join(SR, "duel_gru_v0_6_0", "keep")
RUN = "scratch_b10a_smoke"
D = os.path.join(SR, RUN)
BS = "\\"


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
    shutil.copy2(os.path.join(K0, "policy_end_v060.pt"), os.path.join(D, "policy.pt"))
    shutil.copy2(os.path.join(K0, "opt_end_v060.pt"), os.path.join(D, "opt.pt"))
    shutil.copy2(os.path.join(K0, "policy_end_v060.pt"), os.path.join(D, "snapshots", "anchor_v060_end.pt"))
    shutil.copy2(os.path.join(SR, "duel_gru_v0_6_0", "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(SR, "duel_gru_v0_6_0", "live.json"), encoding="utf-8"))
    lv.update(WIN_ADD=0.0, WIN_W=0.0, FADE_V=0.0, WIN_GAIN=1.0, WIN_SHAPE_K=0.0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("/affinity C3FFF", "/affinity 3C000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_b1_0a ", "--run " + RUN + " "),
            ("--minutes 1320 --gamma", "--minutes 12 --gamma"),
            ("data" + BS + "sim_runs" + BS + "duel_gru_b1_0a.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    cmd = os.path.join(D, "smoke.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    rp = subprocess.Popen([PY, os.path.join(HERE, "ramp_win.py"), RUN, "--shut", "1", "--steps", "3", "--every", "1", "--pause", "1", "--poll", "5"], cwd=ROOT, env=env)
    say("the smoke trainer and the ramp started")
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
    check("12 or more updates ({})".format(len(M)), len(M) >= 12)
    check("WIN_ADD taken live to 0.33", "'WIN_ADD': '0.33'" in log or "'WIN_ADD': 0.33" in log)
    lv2 = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    check("live.json ended at WIN_ADD 0.33, WIN_W 0, FADE_V 0", lv2.get("WIN_ADD") == 0.33 and lv2.get("WIN_W") == 0.0 and lv2.get("FADE_V") == 0.0)
    check("no rescale", all(m.get("adv_pay") is None for m in M))
    first, last = M[0].get("win_blend") or {}, [m["win_blend"] for m in M[-6:] if m.get("win_blend")]
    mean = lambda k: sum(b[k] for b in last) / max(1, len(last))  # noqa: E731
    say("sizes: first update {}".format(first))
    say("sizes over the last 6 updates: win at gain 1 {:.2f}, combat {:.2f}, other {:.2f}, paid {:.2f}; 0.33 x win {:.2f}, win's share of the sum {:.0%}".format(
        mean("win_g1_size"), mean("combat_size"), mean("other_size"), mean("paid_size"), 0.33 * mean("win_g1_size"),
        0.33 * mean("win_g1_size") / max(1e-6, 0.33 * mean("win_g1_size") + mean("combat_size") + mean("other_size"))))
    check("paid size above the table's largest part", mean("paid_size") > max(mean("combat_size"), mean("other_size")))
    check("the blend's frames counted", mean("blend_frames") > 0)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import test_suite
    check("test_suite.Policy loads the last save", test_suite.Policy(os.path.join(D, "policy.pt")) is not None)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
