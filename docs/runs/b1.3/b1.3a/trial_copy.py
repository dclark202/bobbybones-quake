"""b1.3a's copy trial (2026-11-02 evening, the copy design; trial.py was the sole-learner design's), on the CPU, with no trainer needed on the card: the run's
train.cmd made small (2 workers, 8 matches, 96 steps) from a b1.2d save given the head (default b1.2d's end; any save kept with its optimizer), the gate SHUT all
run (as b1.3a plays), the copy lesson on, b1.2d's end dials, for --minutes (default 40), into data/sim_runs/scratch_b13a_copy.
On 2 of the owner's efficiency cores (16, 17: 0x30000; owner 11-02: "2 of my 4 E cores, to test anything").
Passes when: exit 0 on the CPU, 40 updates or more; the copy's gradient reaches the head only (the trainer's own check at its first piece); the gate 0
throughout and in the save; the copy's KL a number every update and falling (last quarter under the first); its agreement with the hands rising; the hands'
target rows moved (they learn as in b1.2d); the head's target layer moved; a check with the save finishes.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.3\\b1.3a\\trial_copy.py [minutes] [policy save] > docs\\runs\\b1.3\\b1.3a\\trial_copy.log"""
import json, os, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_b1_2d")
RUN = "scratch_b13a_copy"
D = os.path.join(SR, RUN)
BS = "\\"
MINS = sys.argv[1] if len(sys.argv) > 1 else "40"
FROM = sys.argv[2] if len(sys.argv) > 2 else os.path.join(R0, "keep", "policy_end_b12d.pt")
END_DIALS = dict(ITEM_PT_MIX=1.0, SPEED_PAY=0.125, DMG_TAKEN_W=0.8, STACK_DIFF=0.0, RAIL_FAR_PAY=0.25)   # b1.2d's end values (its card)


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
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
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "head2_init.py"), "add", END, os.path.join(D, "policy.pt"), "--gate", "0", "--ctrl-src", "belief", "--opt", OPT, os.path.join(D, "opt.pt")], cwd=ROOT, env=cenv)
    if r.returncode:
        say("head2_init add failed")
        return 1
    shutil.copy2(os.path.join(D, "policy.pt"), os.path.join(D, "keep", "policy_start.pt"))
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_b12d.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(END_DIALS, H2_GATE_CAP=0.0, H2_GATE_OPEN=0.0, VALUE_WARM=0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    assert "--head2-copy 1 " in t and "--head2-cap 0 --head2-gate 0 " in t and "--head2-pg 0 " in t, "train.cmd is not the copy design: run make_files.py first"
    t = re.sub(r"--minutes \d+ --gamma", "--minutes {} --gamma".format(MINS), t)
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("/affinity C03C3", "/affinity 30000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_b1_3a ", "--run " + RUN + " "),
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
    check("the copy lesson on", "head2-copy: the head learns" in log)
    ln_ = [x for x in log.splitlines() if "head2-copy: its gradient reaches" in x]
    say(ln_[0] if ln_ else "(no gradient line)")
    check("its gradient reaches the head only", bool(ln_) and " and 0 others " in ln_[0])
    M = [json.loads(x.replace("NaN", "null")) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    H = [m.get("head2") or {} for m in M]
    C = [h.get("copy") or {} for h in H]
    check("40 updates or more ({})".format(len(M)), len(M) >= 40)
    if len(M) < 4:
        say("FAILED")
        return 1
    check("the gate 0 throughout", all(h.get("gate") == 0 for h in H))
    check("the copy's KL a number every update", all(isinstance(c.get("kl"), (int, float)) for c in C))
    for i_ in range(0, len(C), max(1, len(C) // 12)):
        say("update {}: kl {} agree {} head_played {} hands_played {} frames {} v_loss {} grad {}".format(
            M[i_]["update"], C[i_].get("kl"), C[i_].get("agree"), C[i_].get("head_played"), C[i_].get("hands_played"), C[i_].get("frames"), H[i_].get("v_loss"), H[i_].get("grad")))
    q = max(1, len(C) // 4)
    mean = lambda x_: sum(x_) / max(1, len(x_))  # noqa: E731
    k1, k4 = mean([c.get("kl") or 0 for c in C[:q]]), mean([c.get("kl") or 0 for c in C[-q:]])
    a1, a4 = mean([c.get("agree") or 0 for c in C[:q]]), mean([c.get("agree") or 0 for c in C[-q:]])
    check("the copy's KL falls: first quarter {:.3f}, last {:.3f}".format(k1, k4), k4 < k1)
    check("its agreement rises: first quarter {:.3f}, last {:.3f}".format(a1, a4), a4 > a1)
    import torch
    a_ = torch.load(os.path.join(D, "keep", "policy_start.pt"), map_location="cpu", weights_only=False)
    b_ = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    sa, sb = a_["model"], b_["model"]
    n_ = int(a_["head2"]["n_target"])
    dims = list(a_["action_dims"])
    i0 = sum(dims[:10])
    check("the hands' target rows moved (they learn as in b1.2d)", not torch.equal(sa["pi.weight"][i0:i0 + n_], sb["pi.weight"][i0:i0 + n_]))
    check("the gate 0 in the save", float(sb["head2.gate"]) == 0.0)
    check("the head's target layer moved", not torch.equal(sa["head2.target.weight"], sb["head2.target.weight"]))
    last_ = os.path.join(D, "policy.pt")
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "head2head.py"), "trial", RUN, last_, "8", last_, "8", "--maps", "bloodrun", "--games", "2"], cwd=ROOT, env=cenv, capture_output=True, text=True)
    say(r.stdout[-300:].strip())
    check("a check with the save finishes", r.returncode == 0 and "ERROR" not in r.stdout)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
