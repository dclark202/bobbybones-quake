"""1.4c's smoke run (2026-11-04): its train.cmd made small (2 workers, 8 matches, 96 steps, the CPU, efficiency cores at low priority), from
1.4b's save of update 10 given the keep choice (tools/keep_init.py add) with its optimizer, the keep choice at full share (live KEEP_G 1) and
matchmaking by difficulty (live PFSP 1), a snapshot a minute; the anchors 1.4b's update 10 (anchor_14b.pt, no keep choice: the lock rule) and
b1.2d's end, a 1.4b snapshot, and the start with the keep choice at share 0.5 (snap_0003: the league's own keep choice drawn), into
data/sim_runs/scratch_14c_smoke of this checkout. Data the worktree lacks is read from the main checkout. Checks: the trainer exited 0 on the CPU,
8 updates or more; the keep choice announced; every update's keep record at share 1 once live; its readings counted, its chance between 0 and 1,
its step (kl) finite and small; its weights on the memories moved off zero; no NaN in the head's lesson; the save carries the keep choice at
share 1; a one-map check of the save (keep choice on) against anchor_14b.pt (none) finishes, and his keep choice decided readings there.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.4\\1.4c\\smoke.py > docs\\runs\\b1.4\\1.4c\\smoke.log"""
import json
import math
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
MAIN = os.path.join(os.path.dirname(ROOT), "BobbyBones")
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(MAIN, "data", "sim_runs", "duel_gru_1_4b")
RUN = "scratch_14c_smoke"
D = os.path.join(SR, RUN)
BS = "\\"


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    END, OPT = os.path.join(R0, "keep", "policy_u10_14b.pt"), os.path.join(R0, "keep", "opt_u10_14b.pt")
    say("from " + END + " / " + OPT)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    subprocess.check_call([PY, os.path.join(ROOT, "tools", "keep_init.py"), "add", END, os.path.join(D, "policy.pt"),
                           "--opt", OPT, os.path.join(D, "opt.pt")], env=cenv)
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_14b.pt"))
    shutil.copy2(os.path.join(MAIN, "data", "sim_runs", "duel_gru_b1_2d", "keep", "policy_end_b12d.pt"), os.path.join(D, "snapshots", "anchor_b12d.pt"))
    sn_ = sorted(f for f in os.listdir(os.path.join(R0, "snapshots")) if f.startswith("snap_"))
    shutil.copy2(os.path.join(R0, "snapshots", sn_[0]), os.path.join(D, "snapshots", "snap_0001.pt"))
    import torch
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    ck["model"]["head2.keep_g"] = torch.tensor(0.5)
    torch.save(ck, os.path.join(D, "snapshots", "snap_0003.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(PFSP=1.0, VALUE_WARM=0, KEEP_G=1.0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "720"])
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("set WIN_JUDGE=%ROOT%" + BS, "set WIN_JUDGE=" + MAIN + BS),
            ("--brain-human %ROOT%" + BS, "--brain-human " + MAIN + BS),
            ("/affinity C03C3", "/low /affinity 3C3C"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_1_4c ", "--run " + RUN + " "),
            ("--minutes 720 --gamma", "--minutes 16 --gamma"),
            ("--pfsp-fixed anchor_14b.pt", "--pfsp-fixed anchor_14b.pt --snapshot-min 1 --league-table " + os.path.join(D, "league_table.json")),
            ("data" + BS + "sim_runs" + BS + "duel_gru_1_4c.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    cmd = os.path.join(D, "smoke.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    say("the smoke trainer started")
    t0 = time.time()
    while tr.poll() is None and time.time() - t0 < 50 * 60:
        time.sleep(10)
    if tr.poll() is None:
        say("the trainer still runs after 50 min: left running, FAILED")
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
    check("the keep choice announced", "keep choice (1.4c)" in log)
    M = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    check("8 or more updates ({})".format(len(M)), len(M) >= 8)
    K = [m.get("keep") for m in M]
    check("every update recorded the keep choice ({} of {})".format(sum(1 for x in K if x), len(M)), all(K))
    for m in M:
        k = m.get("keep") or {}
        h2 = m.get("head2") or {}
        say("update {}: g {} readings {} p {} (contact {} out {}) kl {} w {} sim {} blinders {} | head2 pg {} v {} clip {}".format(
            m["update"], k.get("g"), k.get("readings"), k.get("p"), k.get("p_contact"), k.get("p_out"), k.get("kl"), k.get("w"), k.get("sim"),
            k.get("blinders"), h2.get("pg_loss"), h2.get("v_loss"), h2.get("clip_share")))
    late = [k for k in K[3:] if k]
    check("the share 1 once live ({})".format([k.get("g") for k in late]), late and all(k.get("g") == 1.0 for k in late))
    check("his keep choice decided readings ({})".format([k.get("readings") for k in late]), late and all((k.get("readings") or 0) > 0 for k in late))
    check("its chance between 0 and 1", late and all(0.0 < (k.get("p") or 0) < 1.0 for k in late))
    kls = [k.get("kl") for k in late]
    check("its step finite and small ({})".format(kls), all(x is not None and math.isfinite(x) and abs(x) < 0.5 for x in kls))
    wl = (late[-1].get("w") or {}) if late else {}
    check("its weights on the memories moved off zero ({})".format(wl), (wl.get("s") or 0) > 0 and (wl.get("hands") or 0) > 0)
    hd = [m.get("head2") or {} for m in M]
    check("no NaN in the head's lesson", all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd))
    sim_ = [((k.get("sim") or {}).get("his_readings") or 0) for k in late]
    check("the simulators counted his decided readings ({})".format(sim_), all(x > 0 for x in sim_))
    import torch
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    check("the save carries the keep choice at share 1 ({}, {})".format((ck.get("head2") or {}).get("keep"), float(ck["model"].get("head2.keep_g", -1))),
          (ck.get("head2") or {}).get("keep") == 1 and abs(float(ck["model"]["head2.keep_g"]) - 1.0) < 1e-6)
    check("the trainer's own snapshots carry it", any(f.startswith("snap_") and f not in ("snap_0001.pt", "snap_0003.pt") for f in os.listdir(os.path.join(D, "snapshots"))))
    js = os.path.join(D, "watch", "chk.json")
    cmd = [PY, "tools/duel_eval.py", "--run", RUN, "--policy", os.path.join(D, "policy.pt"), "--opp", "policy:" + os.path.join(D, "snapshots", "anchor_14b.pt"),
           "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", "bloodrun", "--games", "2", "--minutes", "2", "--procs", "1", "--swap", "--json", js,
           "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600", "--opp-round", "600",
           "--wown", "1", "--opp-wown", "1", "--contact", "1", "--opp-contact", "1", "--hold", "8", "--opp-hold", "8"]
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    os.environ["PANEL_RUN"] = RUN
    import panel as P
    cmd += [x for s_ in P.settings(0.0, os.path.join(D, "policy.pt")) for x in ("--set", s_)]
    cmd += ["--set", "WIN_JUDGE=" + os.path.join(MAIN, "data", "sim_runs", "judge", "judge_v060_wpn.npz")]
    r = subprocess.run(cmd, cwd=ROOT, env=cenv, capture_output=True, text=True)
    say("check: exit {}; {}".format(r.returncode, (r.stdout + r.stderr)[-600:]))
    v = json.load(open(js))["maps"]["bloodrun"] if os.path.exists(js) else {}
    kp_ = (v.get("st_raw") or {}).get("keep")
    check("a one-map check, keep choice on against none, finished ({}-{}; stats keep {})".format(v.get("won"), v.get("lost"), kp_),
          r.returncode == 0 and "won" in v)
    check("his keep choice decided readings in the check", kp_ is not None and len(kp_) == 16 and kp_[3] > 0)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
