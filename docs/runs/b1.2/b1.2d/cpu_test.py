"""b1.2d's short test of the cores (owner, 2026-11-02: "before doing the full run, have it run a short test to make sure the CPU cores are being used effectively"), on b1.2c's end, nothing else of ours running:
b1.2d's own train.cmd (the trainer on the 8 performance cores) for --minutes into data/sim_runs/scratch_b12d_cpu, and beside it a check batch exactly as the watcher plays one (4 maps, 2 processes each, on the
8 check cores 0x3C3C, b1.2c's widened b1.1 as the opponent). Every 10 s: each logical core's load, by group (performance; check cores; the owner's 14-17), and where our processes are allowed to run.
Passes when: an update takes at most 10% more than b1.2c's (4.2 min, from its metrics); the trainer and its simulators only on the performance cores; the check's processes only on the check cores;
nothing of ours on the owner's four; the check batch finishes. It does not start a run and deletes nothing.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.2\\b1.2d\\cpu_test.py [--from <b1.2c save>] [--minutes 30] > docs\\runs\\b1.2\\b1.2d\\cpu_test.log"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
SR = os.path.join(ROOT, "data", "sim_runs")
K0 = os.path.join(SR, "duel_gru_b1_2c", "keep")
RUN = "scratch_b12d_cpu"
D = os.path.join(SR, RUN)
BS = "\\"
P_CORES = [0, 1, 6, 7, 8, 9, 18, 19]
CHK_CORES = [2, 3, 4, 5, 10, 11, 12, 13]
OWN_CORES = [14, 15, 16, 17]


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def tree(p):
    try:
        return [p] + p.children(recursive=True)
    except psutil.NoSuchProcess:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default=os.path.join(K0, "policy_nojerk_b12c.pt"))
    ap.add_argument("--minutes", default="30")
    a = ap.parse_args()
    assert not any("train_duel_rnn" in " ".join(p.info["cmdline"] or []) for p in psutil.process_iter(["cmdline"])), "a trainer runs"
    assert not os.path.exists(D), D + " is there"
    opt_ = os.path.join(os.path.dirname(a.src), re.sub(r"^policy_", "opt_", os.path.basename(a.src)) if os.path.basename(a.src) != "policy.pt" else "opt.pt")
    for s_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, s_))
    shutil.copy2(a.src, os.path.join(D, "policy.pt"))
    shutil.copy2(opt_, os.path.join(D, "opt.pt"))
    for src_, dst_ in (("control_b11.pt", "anchor_b11.pt"), ("control_v060_end.pt", "anchor_v060_end.pt")):
        shutil.copy2(os.path.join(K0, src_), os.path.join(D, "snapshots", dst_))
    shutil.copy2(a.src, os.path.join(D, "snapshots", "anchor_b12c.pt"))
    shutil.copy2(os.path.join(SR, "duel_gru_b1_2c", "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(SR, "duel_gru_b1_2c", "live.json"), encoding="utf-8"))
    lv.update(ITEM_PT_LO=0.004, ITEM_PT_HI=0.002, ITEM_DECAY=0.002, ITEM_PT_MIX=0.0, SPEED_PAY=0.25, DMG_TAKEN_W=1.0, STACK_DIFF=0.7, RAIL_FAR_PAY=0.12)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    t = re.sub(r"--minutes \d+ --gamma", "--minutes {} --gamma".format(a.minutes), t)
    for x, y in [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}".format(ROOT)), ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
                 ("--run duel_gru_b1_2d ", "--run " + RUN + " "), ("data" + BS + "sim_runs" + BS + "duel_gru_b1_2d.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]:
        assert t.count(x) >= 1, x
        t = t.replace(x, y)
    assert "/affinity C03C3 " in t
    cmd = os.path.join(D, "dry.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    say("the trainer starts on the performance cores, {} minutes, from {}".format(a.minutes, a.src))
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    trp = psutil.Process(tr.pid)
    met = os.path.join(D, "metrics.jsonl")
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    os.environ["PANEL_RUN"] = "duel_gru_b1_2c"
    import panel as P
    pol, ctrl = a.src, os.path.join(K0, "control_b11.pt")
    sets = P.settings(0.0, pol)
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1")
    chk, chk_t0, chk_t1 = [], None, None
    S = {"perf": [], "check": [], "owner": []}
    bad = set()
    upd = []
    t0 = time.time()
    psutil.cpu_percent(percpu=True)
    while tr.poll() is None:
        time.sleep(10)
        L = [json.loads(x) for x in open(met)] if os.path.exists(met) else []
        if L and not chk and chk_t0 is None:                 # the first update is in: the check batch begins beside the trainer
            chk_t0 = time.time()
            for mp in ("bloodrun", "aerowalk", "lostworld", "sinister"):
                c = [P.PY, "tools/duel_eval.py", "--run", "duel_gru_b1_2c", "--policy", pol, "--opp", "policy:" + ctrl, "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"),
                     "--map", mp, "--games", "4", "--minutes", "4", "--procs", "2", "--swap", "--json", os.path.join(D, "watch", "cpu_chk_{}.json".format(mp)),
                     "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600", "--opp-round", "600"]
                c += [x for s_ in sets for x in ("--set", s_)]
                p_ = subprocess.Popen(c, cwd=ROOT, env=cenv, creationflags=0x4000 | 0x08000000, stdout=open(os.path.join(D, "watch", "cpu_chk_{}.log".format(mp)), "w"), stderr=subprocess.STDOUT)
                psutil.Process(p_.pid).cpu_affinity(CHK_CORES)
                chk.append(p_)
            say("the check batch starts beside it: 4 maps, 2 processes each, on the check cores")
        if chk and chk_t1 is None and all(p_.poll() is not None for p_ in chk):
            chk_t1 = time.time()
            say("the check batch done in {:.1f} min, exits {}".format((chk_t1 - chk_t0) / 60, [p_.returncode for p_ in chk]))
        pc = psutil.cpu_percent(percpu=True)
        for g_, cs_ in (("perf", P_CORES), ("check", CHK_CORES), ("owner", OWN_CORES)):
            S[g_].append(sum(pc[c_] for c_ in cs_) / len(cs_))
        for p_ in tree(trp):
            try:
                aff_ = set(p_.cpu_affinity())
                if p_.name().lower().startswith("python") and not aff_ <= set(P_CORES):
                    bad.add("trainer process {} on {}".format(p_.pid, sorted(aff_)))
            except psutil.Error:
                pass
        for c in chk:
            for p_ in tree(psutil.Process(c.pid)) if c.poll() is None else []:
                try:
                    aff_ = set(p_.cpu_affinity())
                    if not aff_ <= set(CHK_CORES):
                        bad.add("check process {} on {}".format(p_.pid, sorted(aff_)))
                except psutil.Error:
                    pass
        if len(L) > len(upd):
            upd = [(x["update"], x["minutes"]) for x in L]
            say("update {} at minute {:.1f} of the run | load: performance {:.0f}%, check cores {:.0f}%, the owner's {:.0f}%".format(upd[-1][0], time.time() / 60 - t0 / 60, S["perf"][-1], S["check"][-1], S["owner"][-1]))
    C = [json.loads(x) for x in open(os.path.join(SR, "duel_gru_b1_2c", "metrics.jsonl"))]
    ref = (C[-1]["minutes"] - C[-21]["minutes"]) / (C[-1]["update"] - C[-21]["update"])
    per = [(upd[i][1] - upd[i - 1][1]) for i in range(2, len(upd))]   # (from the second update: the first includes the start)
    mean_ = sum(per) / len(per) if per else None
    av = {g_: sum(v_) / max(1, len(v_)) for g_, v_ in S.items()}
    ok = True

    def check(name, c):
        nonlocal ok
        ok = ok and bool(c)
        print(("PASS " if c else "FAIL ") + name, flush=True)

    print("load over the test: performance cores {:.0f}%, check cores {:.0f}%, the owner's four {:.0f}%".format(av["perf"], av["check"], av["owner"]), flush=True)
    check("an update {} min against b1.2c's {:.2f} (at most 10% more)".format("{:.2f}".format(mean_) if mean_ else "not measured", ref), mean_ is not None and mean_ <= 1.10 * ref)
    check("the trainer and its simulators only on the performance cores", not any(b_.startswith("trainer") for b_ in bad))
    check("the check's processes only on the check cores", not any(b_.startswith("check") for b_ in bad))
    check("the check batch finished ({})".format("{:.1f} min".format((chk_t1 - chk_t0) / 60) if chk_t1 else "no"), chk_t1 is not None and all(p_.returncode == 0 for p_ in chk))
    for b_ in sorted(bad):
        print("  " + b_, flush=True)
    print("ALL PASSED" if ok else "FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
