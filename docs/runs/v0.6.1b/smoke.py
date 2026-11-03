"""v0.6.1b's smoke run, before its start (after v0.6.1 has ended: it takes the CPU for ~20 min). v0.6.1b's own train.cmd made
small (2 workers, 8 matches, 96 steps, 4 pieces, 25 min) on the CPU (CUDA_VISIBLE_DEVICES=-1), from v0.6.1's end, in a new folder
data/sim_runs/scratch_v061b_smoke (refuses if it exists: nothing is overwritten or deleted). tools/run/ramp_live.py steps
BRAIN_FADE 0 -> 0.5 -> 1.0 right after the saves of updates 10 and 20 (no wait). Passes when: the trainer ran 30+ updates and
exited 0; metrics.jsonl's brain_fade.g went 0 -> 0.5 -> 1.0 (each rollout played and learnt at one g); the save of update 30
carries belief.fade with g 1.0 and the rule fade's columns; tools/run/brain_fade_check.py passes on it; test_suite.Policy loads it
and its numpy brain reads the faded weights. Exit 0 = passed.

    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\v0.6.1b\\smoke.py"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PY = sys.executable
R0 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_v0_6_1")
RUN = "scratch_v061b_smoke"
D = os.path.join(ROOT, "data", "sim_runs", RUN)
END = os.path.join(R0, "keep", "policy_end_v061.pt")
START = END if os.path.exists(END) else os.path.join(R0, "policy.pt")
OPT = os.path.join(R0, "keep", "opt_end_v061.pt") if os.path.exists(END) else os.path.join(R0, "opt.pt")


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    assert not os.path.exists(D), D + " exists: nothing overwritten (use another name)"
    last = open(os.path.join(ROOT, "data", "sim_runs", "duel_gru_v0_6_1.log"), encoding="utf-8", errors="replace").read().splitlines()[-1:]
    assert last and last[0].startswith("exit"), "v0.6.1 has not ended (its log does not end in exit): the smoke run waits"
    os.makedirs(os.path.join(D, "snapshots"))
    os.makedirs(os.path.join(D, "keep"))
    shutil.copy(START, os.path.join(D, "policy.pt"))
    shutil.copy(OPT, os.path.join(D, "opt.pt"))
    shutil.copy(os.path.join(R0, "snapshots", "anchor_v060_end.pt"), os.path.join(D, "snapshots", "anchor_v060_end.pt"))
    shutil.copy(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(BRAIN_FADE=0.0, VALUE_WARM=0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("start " + START)
    t = open(os.path.join(HERE, "train.cmd"), encoding="utf-8").read()
    rep = [("--run duel_gru_v0_6_1b ", "--run {} ".format(RUN)), ("data\\sim_runs\\duel_gru_v0_6_1b.log", "data\\sim_runs\\{}.log".format(RUN)),
           ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps 96 "),
           ("--minibatches 360 ", "--minibatches 4 "), ("--resume --minutes 780 ", "--resume --minutes 25 "),
           ("set ROOT=%~dp0..\\..\\..", "set ROOT={}".format(ROOT))]
    for a_, b_ in rep:
        assert a_ in t, a_
        t = t.replace(a_, b_)
    t = t.replace("call %~dp0aim2_env.cmd", "call {}".format(os.path.join(HERE, "aim2_env.cmd")))
    t = t.replace("@echo off", "@echo off\r\nset CUDA_VISIBLE_DEVICES=-1\r\nset OMP_NUM_THREADS=1", 1)
    cmd = os.path.join(D, "smoke.cmd")
    open(cmd, "w", encoding="utf-8", newline="").write(t.replace("\r\n", "\n").replace("\n", "\r\n"))
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    rp = subprocess.Popen([PY, os.path.join(ROOT, "tools", "run", "ramp_live.py"), RUN, "BRAIN_FADE", "0", "1", "0.5", "--min-s", "0", "--sleep", "5"],
                          cwd=ROOT, env=env)
    t0 = time.time()
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(20)
    if tr.poll() is None:
        say("the trainer still runs after 40 min: left running, the smoke run FAILED")
        return 1
    if rp.poll() is None:
        rp.terminate()
    log = open(os.path.join(ROOT, "data", "sim_runs", RUN + ".log"), encoding="utf-8", errors="replace").read()
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        say(("PASS " if cond else "FAIL ") + name)

    check("the trainer exited 0", log.rstrip().splitlines()[-1].strip() == "exit 0")
    check("on the CPU", "device cpu" in log)
    M = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    gs = [m.get("brain_fade", {}).get("g") for m in M]
    say("updates {}; brain_fade.g by update: {}".format(len(M), gs))
    check("30 or more updates", len(M) >= 30)
    check("the gate went 0 -> 0.5 -> 1.0", None not in gs and gs[0] == 0.0 and 0.5 in gs and gs[-1] == 1.0
          and all(b_ >= a_ for a_, b_ in zip(gs, gs[1:])))
    import torch
    keep = sorted([f for f in os.listdir(os.path.join(D, "keep")) if f.startswith("policy_") and f[7:-3].isdigit()], key=lambda f: int(f[7:-3]))
    last_ = os.path.join(D, "keep", keep[-1]) if keep else os.path.join(D, "policy.pt")   # (no watcher here: the trainer's own last save)
    keep = [os.path.basename(last_)] if not keep else keep
    ck = torch.load(last_, map_location="cpu", weights_only=False)
    fd = (ck.get("belief") or {}).get("fade") or {}
    check("the last save ({}) carries belief.fade at g {}".format(keep[-1], fd.get("g")), fd.get("g") == 1.0
          and sorted(fd.get("cols", [])) == sorted(ck["rule_fade"]["cols"]))
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "brain_fade_check.py"), ROOT, last_],
                       cwd=ROOT, env=dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1"))
    check("brain_fade_check on that save", r.returncode == 0)
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import numpy as np
    import test_suite
    P = test_suite.Policy(last_)
    w = getattr(P, "brainP", None)
    check("test_suite.Policy loads it with its brain", w is not None)
    if w is not None:
        check("its numpy brain reads the faded columns as nothing", float(np.abs(w["inp_w"][:, fd["cols"]]).max()) == 0.0)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
