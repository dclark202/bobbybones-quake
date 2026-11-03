"""b1.4a's trial (2026-11-02 night), on the CPU, with no trainer needed on the card: b1.4a's train.cmd made small (2 workers, 8 matches, 96 steps)
from a save with a copying head (default b1.3a's newest kept save; any save kept with its optimizer), the whole schedule run by ramp_b14a.py at
--scale 0.25 from update 2 (A: the mix 0 -> 1 over updates 2 to 12, the copy out by 17; B: the lock out over 12 to 19.5; C: the way pay out over
19.5 to 27), for --minutes (default 60), into data/sim_runs/scratch_b14a_trial. On 2 of the owner's efficiency cores (16, 17: 0x30000).
Passes when: exit 0 on the CPU; 40 updates or more; the mix reached 1, the lock 0 and the way pay's factor 0 in the trainer's own record; no
NaN, no piece skipped, no TRIPWIRE; the hands' target rows of pi the same to the bit from start to end, other rows moved; the head's target
layer moved; the save's mix 1; a check with the save (at its own mix) finishes.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.4\\b1.4a\\trial_b14a.py [minutes] [policy save] > docs\\runs\\b1.4\\b1.4a\\trial_b14a.log"""
import glob, json, os, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_b1_3a")
RUN = "scratch_b14a_trial"
D = os.path.join(SR, RUN)
BS = "\\"
MINS = sys.argv[1] if len(sys.argv) > 1 else "60"


def newest_kept():
    c_ = [p for p in glob.glob(os.path.join(R0, "keep", "policy_*.pt")) if "start" not in os.path.basename(p) and "control" not in os.path.basename(p)
          and os.path.exists(os.path.join(R0, "keep", os.path.basename(p).replace("policy_", "opt_", 1)))]
    return max(c_, key=os.path.getmtime) if c_ else None


FROM = sys.argv[2] if len(sys.argv) > 2 else newest_kept()


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    if not FROM:
        say("no kept save of b1.3a with its optimizer: give one")
        return 1
    END = FROM
    OPT = os.path.join(os.path.dirname(END), os.path.basename(END).replace("policy_", "opt_", 1))
    if not (os.path.exists(END) and os.path.exists(OPT)):
        say("missing {} or {}: not started".format(END, OPT))
        return 1
    say("from {} with {}".format(END, OPT))
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    for s_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, s_))
    shutil.copy2(END, os.path.join(D, "policy.pt"))
    shutil.copy2(OPT, os.path.join(D, "opt.pt"))
    shutil.copy2(END, os.path.join(D, "keep", "policy_start.pt"))
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_b13a.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(H2_GATE_CAP=0.0, H2_GATE_OPEN=0.0, H2_MIX=0.0, H2_COPY=1.0, INTENT_HOLD=8.0, INTENT_SEEK_W=1.0, VALUE_WARM=0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    r = subprocess.run([PY, os.path.join(HERE, "make_files.py"), "720"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    t = re.sub(r"--minutes \d+ --gamma", "--minutes {} --gamma".format(MINS), t)
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("/affinity C03C3", "/affinity 30000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_b1_4a ", "--run " + RUN + " "),
            ("data" + BS + "sim_runs" + BS + "duel_gru_b1_4a.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    cmd = os.path.join(D, "trial.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    rp = subprocess.Popen([PY, os.path.join(HERE, "ramp_b14a.py"), RUN, "--start", "2", "--scale", "0.25", "--poll", "5", "--settle", "5"], cwd=ROOT, env=env)
    say("the trial trainer and the ramp started, {} minutes".format(MINS))
    t0 = time.time()
    while tr.poll() is None and time.time() - t0 < (float(MINS) + 30) * 60:
        time.sleep(10)
    time.sleep(15)
    rp.terminate()
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
    check("the head alone learns his target", "head2-sole:" in log)
    M = [json.loads(x.replace("NaN", "null")) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    H = [m.get("head2") or {} for m in M]
    C = [h.get("copy") or {} for h in H]
    check("40 updates or more ({})".format(len(M)), len(M) >= 40)
    if len(M) < 4:
        say("FAILED")
        return 1
    for i_ in range(0, len(M), max(1, len(M) // 14)):
        say("update {}: mix {} seek_w {} copy_w {} agree {} raw {} hands {} pg_loss {} v_loss {} no_state {}".format(
            M[i_]["update"], H[i_].get("mix"), H[i_].get("seek_w"), C[i_].get("w"), C[i_].get("agree"), C[i_].get("raw"), H[i_].get("hands"),
            H[i_].get("pg_loss"), H[i_].get("v_loss"), C[i_].get("no_state")))
    check("the mix reached 1", any(h.get("mix") == 1.0 for h in H))
    check("the way pay's factor reached 0", any(h.get("seek_w") == 0.0 for h in H))
    la_ = json.load(open(os.path.join(D, "live_applied.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_applied.json")) else {}
    check("the lock reached 0 in the simulators (live_applied: {})".format(la_.get("in_force", {}).get("INTENT_HOLD")), float(la_.get("in_force", {}).get("INTENT_HOLD", -1)) == 0.0)
    check("no NaN", all(isinstance(h.get("pg_loss"), (int, float)) and isinstance(c.get("raw"), (int, float)) for h, c in zip(H, C)))
    check("no piece skipped", not H[-1].get("skipped"))
    rl_ = open(os.path.join(D, "watch", "ramp.log"), encoding="utf-8").read() if os.path.exists(os.path.join(D, "watch", "ramp.log")) else ""
    check("no TRIPWIRE", "TRIPWIRE" not in rl_)
    check("the ramp kept the fades' saves", all(os.path.exists(os.path.join(D, "keep", "policy_{}done_b14a.pt".format(x_))) for x_ in "ABC"))
    import torch
    a_ = torch.load(os.path.join(D, "keep", "policy_start.pt"), map_location="cpu", weights_only=False)
    b_ = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    sa, sb = a_["model"], b_["model"]
    n_ = int(a_["head2"]["n_target"])
    i0 = sum(list(a_["action_dims"])[:10])
    check("the hands' target rows the same to the bit", torch.equal(sa["pi.weight"][i0:i0 + n_], sb["pi.weight"][i0:i0 + n_]) and torch.equal(sa["pi.bias"][i0:i0 + n_], sb["pi.bias"][i0:i0 + n_]))
    check("the hands' other rows moved", not torch.equal(sa["pi.weight"][:i0], sb["pi.weight"][:i0]))
    check("the head's target layer moved", not torch.equal(sa["head2.target.weight"], sb["head2.target.weight"]))
    check("the save's mix 1 ({})".format(float(sb["head2.mix"])), float(sb["head2.mix"]) == 1.0)
    last_ = os.path.join(D, "policy.pt")
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "head2head.py"), "trial", RUN, last_, "8", os.path.join(D, "keep", "policy_start.pt"), "8", "--maps", "bloodrun", "--games", "2"],
                       cwd=ROOT, env=cenv, capture_output=True, text=True)
    say(r.stdout[-300:].strip())
    check("a check with the save at its mix finishes", r.returncode == 0 and "ERROR" not in r.stdout)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
