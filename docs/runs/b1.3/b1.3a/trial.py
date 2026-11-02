"""b1.3a's trial (2026-11-01), on the CPU, with no trainer needed on the card: the run's train.cmd made small (2 workers, 8 matches, 96 steps) from b1.2c's end given the head, gate open at once, for --minutes (default 40), into data/sim_runs/scratch_b13a_trial. It must run after b1.2c has ended.
Passes when: exit 0 on the CPU, 40 updates or more; no NaN and no piece skipped; the hands' target rows of pi the same to the bit from start to end, other rows of pi moved, the head's target layer moved; the hands' target length steady (within 25%); the bias's length levels off (the last quarter's mean under 1.5 x the third quarter's); a check with a head in both seats finishes.
Prints all of it: read it beside the card's blowup. Then `start.ps1` may run.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.3\\b1.3a\\trial.py [minutes] > docs\\runs\\b1.3\\b1.3a\\trial.log"""
import json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_b1_2c")
RUN = "scratch_b13a_trial"
D = os.path.join(SR, RUN)
BS = "\\"
MINS = sys.argv[1] if len(sys.argv) > 1 else "40"


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    END, OPT = os.path.join(R0, "keep", "policy_end_b12c.pt"), os.path.join(R0, "keep", "opt_end_b12c.pt")
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    for s_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, s_))
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "head2_init.py"), "add", END, os.path.join(D, "policy.pt"), "--gate", "1", "--ctrl-src", "belief", "--opt", OPT, os.path.join(D, "opt.pt")], cwd=ROOT, env=cenv)
    if r.returncode:
        say("head2_init add failed")
        return 1
    shutil.copy2(os.path.join(D, "policy.pt"), os.path.join(D, "keep", "policy_start.pt"))
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_b12c.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(H2_GATE_CAP=1.0, H2_GATE_OPEN=1.0, VALUE_WARM=0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    M0 = [x for x in t.split() if x.isdigit()]
    import re
    t = re.sub(r"--minutes \d+ --gamma", "--minutes {} --gamma".format(MINS), t)
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("/affinity C3FFF", "/affinity 3C000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_b1_3a ", "--run " + RUN + " "),
            ("--head2-cap 0 --head2-gate 0 ", "--head2-cap 1 --head2-gate 1 "),
            ("data" + BS + "sim_runs" + BS + "duel_gru_b1_3a.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    cmd = os.path.join(D, "trial.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    say("the trial trainer started, {} minutes".format(MINS))
    t0 = time.time()
    while tr.poll() is None and time.time() - t0 < (float(MINS) + 30) * 60:
        time.sleep(10)
    if tr.poll() is None:
        say("the trainer still runs: left running, FAILED")
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
    check("the head alone learns", "head2-sole:" in log)
    M = [json.loads(x.replace("NaN", "null")) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    H = [m.get("head2") or {} for m in M]
    check("40 updates or more ({})".format(len(M)), len(M) >= 40)
    check("no NaN", all(h.get("bias") is not None and h.get("hands") is not None for h in H))
    check("no piece skipped", H[-1].get("skipped") == 0)
    for i_ in range(0, len(H), max(1, len(H) // 12)):
        say("update {}: bias {} hands {} target_w {} share {} grad {}".format(M[i_]["update"], H[i_].get("bias"), H[i_].get("hands"), H[i_].get("target_w"), H[i_].get("bias_share"), H[i_].get("grad")))
    q = max(1, len(H) // 4)
    mean = lambda x_: sum(x_) / max(1, len(x_))  # noqa: E731
    b3, b4 = mean([h["bias"] for h in H[-2 * q:-q]]), mean([h["bias"] for h in H[-q:]])
    h1, h4 = mean([h["hands"] for h in H[:q]]), mean([h["hands"] for h in H[-q:]])
    check("the bias's length levels off: third quarter {:.2f}, last {:.2f}".format(b3, b4), b4 < 1.5 * b3)
    check("the hands' target length steady: first quarter {:.2f}, last {:.2f}".format(h1, h4), abs(h4 - h1) < 0.25 * h1)
    import torch
    a_ = torch.load(os.path.join(D, "keep", "policy_start.pt"), map_location="cpu", weights_only=False)
    b_ = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    sa, sb = a_["model"], b_["model"]
    n_ = int(a_["head2"]["n_target"])
    dims = list(a_["action_dims"])
    i0 = sum(dims[:10])
    check("the hands' target rows the same to the bit", torch.equal(sa["pi.weight"][i0:i0 + n_], sb["pi.weight"][i0:i0 + n_]) and torch.equal(sa["pi.bias"][i0:i0 + n_], sb["pi.bias"][i0:i0 + n_]))
    check("the hands' other rows moved", not torch.equal(sa["pi.weight"][:i0], sb["pi.weight"][:i0]))
    check("the head's target layer moved", not torch.equal(sa["head2.target.weight"], sb["head2.target.weight"]))
    last_ = os.path.join(D, "policy.pt")
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "head2head.py"), "trial", RUN, last_, "8", last_, "8", "--maps", "bloodrun", "--games", "2"], cwd=ROOT, env=cenv, capture_output=True, text=True)
    say(r.stdout[-300:].strip())
    check("a check with a head in both seats finishes", r.returncode == 0 and "ERROR" not in r.stdout)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
