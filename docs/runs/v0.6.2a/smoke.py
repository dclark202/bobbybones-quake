"""v0.6.2a's smoke run on v0.6.1c's end (owner, 2026-10-29: "Just do this after training ends tomorrow morning"): the strategy head
training on a brain faded to 1, never run before. v0.6.2a's train.cmd made small (2 workers, 8 matches, 96 steps, 12 min, the CPU,
the four E cores), from v0.6.1c's end given the head with its gate forced open (so its whole learning path runs), into
data/sim_runs/scratch_v062a_smoke. Refuses while a trainer runs or before v0.6.1c's log ends in "exit". Checks: the trainer exited
0 on the CPU; 20+ updates; the brain's dial at 1 in every update; the head learnt (its value and lesson, its links rose from zero,
its bias a share of his target choice); the last save keeps the dial at 1 and passes brain_fade_check; test_suite.Policy loads it.
Usage: %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\v0.6.2a\\smoke.py"""
import json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PY = sys.executable
R0 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_v0_6_1c")
RUN = "scratch_v062a_smoke"
D = os.path.join(ROOT, "data", "sim_runs", RUN)


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*train_duel_rnn*' } | Measure-Object).Count"],
                         capture_output=True, text=True).stdout.strip()
    if out != "0":
        say("a trainer is running ({}): not started".format(out))
        return 1
    last = open(os.path.join(ROOT, "data", "sim_runs", "duel_gru_v0_6_1c.log"), encoding="utf-8", errors="replace").read().splitlines()[-1:]
    if not last or not last[0].startswith("exit"):
        say("v0.6.1c's log does not end in exit: not started")
        return 1
    if os.path.exists(os.path.join(D, "policy.pt")):
        say(D + " already has a policy.pt: not started (look at it first; nothing deleted)")
        return 1
    END = os.path.join(R0, "keep", "policy_end_v061c.pt")
    if not os.path.exists(END):
        END = os.path.join(R0, "policy.pt")            # (v0.6.2a's start.ps1 keeps it as keep\policy_end_v061c.pt; here only read)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    os.makedirs(os.path.join(D, "snapshots"))
    os.makedirs(os.path.join(D, "keep"))
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "head2_init.py"), "add", END, os.path.join(D, "policy.pt"),
                        "--gate", "1", "--ctrl-src", "belief"], cwd=ROOT, env=cenv)
    if r.returncode:
        say("head2_init add failed")
        return 1
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_v061c_end.pt"))
    shutil.copy2(os.path.join(ROOT, "data", "sim_runs", "duel_gru_v0_6_0", "keep", "policy_end_v060.pt"), os.path.join(D, "snapshots", "anchor_v060_end.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(H2_GATE_CAP=1.0, H2_GATE_OPEN=1.0, INTENT_TEACH_W=0.5, VALUE_WARM=0, BRAIN_FADE=1.0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    t = open(os.path.join(HERE, "train.cmd"), encoding="utf-8").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0..\\..\\..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call {}\\docs\\runs\\v0.6.2a\\aim2_env.cmd".format(ROOT)),
            ("/affinity C3FFF", "/affinity 3C000"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_v0_6_2a ", "--run " + RUN + " "),
            ("--minutes 720 ", "--minutes 12 "), ("--head2-cap 0 --head2-gate 0 ", "--head2-cap 1 --head2-gate 1 "),
            ("data\\sim_runs\\duel_gru_v0_6_2a.log", "data\\sim_runs\\" + RUN + ".log")]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    cmd = os.path.join(D, "smoke.cmd")
    open(cmd, "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n"))
    say("the smoke trainer starts (12 min of training)")
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    t0 = time.time()
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(20)
    if tr.poll() is None:
        say("the trainer still runs after 40 min: left running, the smoke run FAILED")
        return 1
    log = open(os.path.join(ROOT, "data", "sim_runs", RUN + ".log"), encoding="utf-8", errors="replace").read()
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        say(("PASS " if cond else "FAIL ") + name)

    check("the trainer exited 0", log.rstrip().splitlines()[-1].strip() == "exit 0")
    check("on the CPU", "device cpu" in log)
    M = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    check("20 or more updates ({})".format(len(M)), len(M) >= 20)
    gs = sorted(set(m.get("brain_fade", {}).get("g") for m in M))
    check("the brain's dial at 1 in every update ({})".format(gs), gs == [1.0])
    h0, h1 = M[0].get("head2") or {}, M[-1].get("head2") or {}
    say("head2 first: {}".format(h0))
    say("head2 last:  {}".format(h1))
    check("the head's gate open", h1.get("gate") == 1.0)
    check("the head's value and lesson finite", all(isinstance(h1.get(k), (int, float)) and abs(h1[k]) < 1e6 for k in ("v_loss", "pg_loss")))
    check("its links rose from zero (plan_in {}, target {})".format(h1.get("plan_in_w"), h1.get("target_w")),
          (h1.get("plan_in_w") or 0) > 0 and (h1.get("target_w") or 0) > 0)
    check("its bias a share of his target choice ({})".format(h1.get("bias_share")), (h1.get("bias_share") or 0) > 0)
    ap_ = [m.get("adv_pay") for m in M]
    say("adv_pay first {} last {}".format(ap_[0], ap_[-1]))
    check("adv_pay in every update", None not in ap_)
    if None not in ap_:
        check("the factor above 1 from the first update (no opening: {})".format(ap_[0]["k"]), ap_[0]["k"] > 1.0)
        check("the target 10 throughout", all(x["ref"] == 10.0 for x in ap_))
    import torch
    last_ = os.path.join(D, "policy.pt")
    ck = torch.load(last_, map_location="cpu", weights_only=False)
    fd = (ck.get("belief") or {}).get("fade") or {}
    check("the last save keeps the brain's dial at 1 ({} columns)".format(len(fd.get("cols", []))), fd.get("g") == 1.0 and ck.get("head2") is not None)
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "brain_fade_check.py"), ROOT, last_], cwd=ROOT, env=cenv)
    check("brain_fade_check on that save", r.returncode == 0)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import test_suite
    check("test_suite.Policy loads it", test_suite.Policy(last_) is not None)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
