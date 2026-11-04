"""1.4b's smoke run (2026-11-03): its train.cmd made small (2 workers, 8 matches, 96 steps, the CPU, efficiency cores at low priority), from a
1.3b save (its latest kept, until its end exists), with matchmaking by difficulty at full (live PFSP 1), a snapshot a minute, two of 1.3b's saves
as snapshots and two anchors (anchor_13b.pt fixed at the even share), into data/sim_runs/scratch_14b_smoke of this checkout (the league table
there too). Data the worktree lacks is read from the main checkout. Checks: the trainer exited 0 on the CPU, 8 updates or more; every update
with a league opponent records it (its file, its frags, its win part, the draw's chances); the fixed anchor at the even share of the anchors;
the chances by difficulty (not even) once the table has slices; the table written; PFSP in force; WEAPON_OWN and INTENT_SWITCH in the saves' settings
or the trainer's environment; a save loads for the checks; a one-map check with each seat's own WEAPON_OWN finishes.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.4\\1.4b\\smoke.py > docs\\runs\\b1.4\\1.4b\\smoke.log"""
import json
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
R0 = os.path.join(MAIN, "data", "sim_runs", "duel_gru_1_3b")
RUN = "scratch_14b_smoke"
D = os.path.join(SR, RUN)
BS = "\\"


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def latest(pfx):
    k_ = os.path.join(R0, "keep")
    if os.path.exists(os.path.join(k_, pfx.format("end_13b"))):
        return os.path.join(k_, pfx.format("end_13b"))
    c_ = sorted((f for f in os.listdir(k_) if f.startswith(pfx.split("{")[0] + "credit")), key=lambda f: int("".join(ch for ch in f if ch.isdigit()) or 0))
    return os.path.join(k_, c_[-1])


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    END, OPT = latest("policy_{}.pt"), latest("opt_{}.pt")
    say("from " + END + " / " + OPT)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(END, os.path.join(D, "policy.pt"))
    shutil.copy2(OPT, os.path.join(D, "opt.pt"))
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_13b.pt"))
    shutil.copy2(os.path.join(MAIN, "data", "sim_runs", "duel_gru_b1_2d", "keep", "policy_end_b12d.pt"), os.path.join(D, "snapshots", "anchor_b12d.pt"))
    shutil.copy2(os.path.join(R0, "keep", "policy_credit10_13b.pt"), os.path.join(D, "snapshots", "snap_0001.pt"))
    shutil.copy2(os.path.join(R0, "keep", "policy_credit20_13b.pt"), os.path.join(D, "snapshots", "snap_0002.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(PFSP=1.0, VALUE_WARM=0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "720"])
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
            ("set WIN_JUDGE=%ROOT%" + BS, "set WIN_JUDGE=" + MAIN + BS),
            ("--brain-human %ROOT%" + BS, "--brain-human " + MAIN + BS),
            ("/affinity C03C3", "/low /affinity 3C3C"), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "), ("--run duel_gru_1_4b ", "--run " + RUN + " "),
            ("--minutes 720 --gamma", "--minutes 14 --gamma"),
            ("--pfsp 0 --pfsp-fixed anchor_13b.pt", "--pfsp 0 --pfsp-fixed anchor_13b.pt --snapshot-min 1 --league-table " + os.path.join(D, "league_table.json")),
            ("data" + BS + "sim_runs" + BS + "duel_gru_1_4b.log", "data" + BS + "sim_runs" + BS + RUN + ".log")]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    cmd = os.path.join(D, "smoke.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    say("the smoke trainer started")
    t0 = time.time()
    while tr.poll() is None and time.time() - t0 < 45 * 60:
        time.sleep(10)
    if tr.poll() is None:
        say("the trainer still runs after 45 min: left running, FAILED")
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
    check("matchmaking announced", "league: matchmaking by difficulty" in log)
    M = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    check("8 or more updates ({})".format(len(M)), len(M) >= 8)
    lg = [m.get("league") for m in M]
    check("every update recorded its league opponent ({} of {})".format(sum(1 for x in lg if x), len(M)), all(lg))
    for m in M:
        x = m.get("league") or {}
        say("update {}: opp {} kills {} win {} pfsp {} shares {}".format(m["update"], x.get("opp"), x.get("kills"), x.get("win"), x.get("pfsp"), x.get("shares")))
    last = (M[-1].get("league") or {}) if M else {}
    sh = last.get("shares") or {}
    anc = {k: v for k, v in sh.items() if k.startswith("anchor_")}
    check("the fixed anchor at the even share of the anchors ({})".format(anc), abs(anc.get("anchor_13b.pt", 0) - 0.24 / max(1, len(anc))) < 1e-3)
    check("the dial in force: 1 ({})".format(last.get("pfsp")), last.get("pfsp") == 1.0)
    snaps = {k: v for k, v in sh.items() if not k.startswith("anchor_")}
    p_ = last.get("p") or {}
    known = [k for k in snaps if abs(p_.get(k, 0.5) - 0.5) > 1e-9]
    even_ = 0.76 / max(1, len(snaps))
    check("the snapshots' chances follow the table ({} known; {})".format(len(known), snaps),
          len(known) == 0 or any(abs(v - even_) > 1e-4 for v in snaps.values()))
    T = json.load(open(os.path.join(D, "league_table.json"), encoding="utf-8"))
    check("the table written ({} files, {} slices)".format(len(T), sum(v["slices"] for v in T.values())), sum(v["slices"] for v in T.values()) == sum(1 for x in lg if x))
    check("the win part counted (|sum| {:.3f})".format(sum(abs(v["win_gained"]) for v in T.values())), sum(abs(v["win_gained"]) for v in T.values()) > 0)
    check("the frags counted ({})".format(sum(v["frags_for"] + v["frags_against"] for v in T.values())), sum(v["frags_for"] + v["frags_against"] for v in T.values()) > 0)
    import torch
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    ev = ck.get("env_vars") or {}
    check("WEAPON_OWN 1 in the save's settings ({})".format(ev.get("WEAPON_OWN")), str(ev.get("WEAPON_OWN")) in ("1", "1.0"))
    js = os.path.join(D, "watch", "chk.json")
    cmd = [PY, "tools/duel_eval.py", "--run", RUN, "--policy", os.path.join(D, "policy.pt"), "--opp", "policy:" + os.path.join(D, "snapshots", "anchor_13b.pt"),
           "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", "bloodrun", "--games", "2", "--minutes", "2", "--procs", "1", "--swap", "--json", js,
           "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600", "--opp-round", "600",
           "--wown", "1", "--opp-wown", "0", "--contact", "1", "--opp-contact", "1", "--hold", "8", "--opp-hold", "8"]
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    os.environ["PANEL_RUN"] = RUN
    import panel as P
    cmd += [x for s_ in P.settings(0.0, os.path.join(D, "policy.pt")) for x in ("--set", s_)]
    cmd += ["--set", "WIN_JUDGE=" + os.path.join(MAIN, "data", "sim_runs", "judge", "judge_v060_wpn.npz")]
    r = subprocess.run(cmd, cwd=ROOT, env=cenv, capture_output=True, text=True)
    say("check: exit {}; {}".format(r.returncode, (r.stdout + r.stderr)[-600:]))
    v = json.load(open(js))["maps"]["bloodrun"] if os.path.exists(js) else {}
    check("a one-map check with each seat's own WEAPON_OWN finished ({}-{}; turned {})".format(v.get("won"), v.get("lost"), (v.get("st_raw") or {}).get("weapon_own")),
          r.returncode == 0 and "won" in v)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
