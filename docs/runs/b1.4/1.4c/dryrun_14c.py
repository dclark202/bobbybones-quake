"""1.4c's dry run (owner's rule: a new part of the network gets one; CARD.md, "Before the start"): 1.4c's own train.cmd at full size (the card,
the 8 performance cores, the graphics card) for 10 updates on a scratch copy, from 1.4b's end given the keep choice as start.ps1 gives it, the
keep choice at share 0.5 from the start (live KEEP_G 0.5: the middle of the ramp, held), into data/sim_runs/scratch_14c_dry (new). The league as
the start's: 1.4b's end (the fixed share), 1.3b's end, b1.2d's end, b1.1, v0.6.0's end. No watcher, no ramp, no checks. Run only with no
trainer running (1.4b stopped).
Passes when: exit 0; 10 updates, each within 12 minutes (no stall); the keep choice announced; no NaN, no piece skipped; the keep record at share
0.5 from the third update, its readings counted, its step (kl) under 0.05 every update; his whole step (kl) under 0.1 every update; the head's own
scores' and the hands' target logits' centred lengths under 60; the head's clip share under 0.3; his trips a player-minute not over 1.5 times, his
targets reached not under 0.7 times 1.4b's last five updates (b1.1a's flicker); the save loads for the checks (test_suite.Policy) with the keep
choice at share 0.5.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.4\\1.4c\\dryrun_14c.py > docs\\runs\\b1.4\\1.4c\\dryrun_14c.log"""
import json, os, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_1_4b")
RUN = sys.argv[1] if len(sys.argv) > 1 else "scratch_14c_dry"
D = os.path.join(SR, RUN)
BS = "\\"
G = 0.5


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    ps_ = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | Select-Object -ExpandProperty CommandLine"],
                         capture_output=True, text=True).stdout
    if any("train_duel_rnn" in l and "dryrun_14c" not in l for l in ps_.splitlines()):
        say("a trainer is running: not started")
        return 1
    END, OPT = os.path.join(R0, "keep", "policy_end_14b.pt"), os.path.join(R0, "keep", "opt_end_14b.pt")
    for p_ in (END, OPT):
        if not os.path.exists(p_):
            say("MISSING " + p_ + ": not started")
            return 1
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    for s_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, s_))
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "keep_init.py"), "add", END, os.path.join(D, "policy.pt"), "--opt", OPT, os.path.join(D, "opt.pt")],
                       cwd=ROOT, env=cenv, capture_output=True, text=True)
    say(r.stdout.strip().splitlines()[1] if r.stdout.strip() else r.stderr[-300:])
    assert r.returncode == 0
    shutil.copy2(os.path.join(D, "policy.pt"), os.path.join(D, "keep", "policy_start.pt"))
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_14b.pt"))
    for f_ in ("anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt"):
        shutil.copy2(os.path.join(R0, "snapshots", f_), os.path.join(D, "snapshots", f_))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(KEEP_G=G, VALUE_WARM=0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    say("live.json: {}".format(lv))
    M0 = [json.loads(x.replace("NaN", "null")) for x in open(os.path.join(R0, "metrics.jsonl"), encoding="utf-8") if x.strip()][-5:]
    base_trips = sum((m.get("intent") or {}).get("trips_per_player_min") or 0 for m in M0) / max(1, len(M0))
    base_reach = sum((m.get("intent") or {}).get("reached") or 0 for m in M0) / max(1, len(M0))
    say("1.4b's last five updates: trips a player-minute {:.2f}, targets reached {:.3f}".format(base_trips, base_reach))
    subprocess.run([PY, os.path.join(HERE, "make_files.py"), "720"], cwd=ROOT, env=env, check=True)
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    t = re.sub(r"--minutes \d+ --gamma", "--minutes 150 --max-updates 10 --gamma", t)
    for a_, b_ in (("--run duel_gru_1_4c ", "--run " + RUN + " "), ("data" + BS + "sim_runs" + BS + "duel_gru_1_4c.log", "data" + BS + "sim_runs" + BS + RUN + ".log"),
                   ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
                   ("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT=" + ROOT)):
        assert t.count(a_) >= 1, a_
        t = t.replace(a_, b_)
    cmd = os.path.join(D, "dry.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    say("the dry run's trainer started (10 updates, full size, the keep choice at share {})".format(G))
    mp = os.path.join(D, "metrics.jsonl")
    seen, t0, t_last = 0, time.time(), time.time()
    stall = False
    while tr.poll() is None and time.time() - t0 < 150 * 60:
        n_ = sum(1 for x in open(mp, encoding="utf-8") if x.strip()) if os.path.exists(mp) else 0
        if n_ > seen:
            seen, t_last = n_, time.time()
            say("update {} recorded".format(n_))
        elif time.time() - t_last > (20 if seen == 0 else 12) * 60:
            stall = True
            say("STALL: no new update for {:.0f} min".format((time.time() - t_last) / 60))
            break
        time.sleep(15)
    if tr.poll() is None:
        say("the trainer still runs: left running, FAILED")
        return 1
    log = open(os.path.join(SR, RUN + ".log"), encoding="utf-8", errors="replace").read()
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        say(("PASS " if cond else "FAIL ") + name)
    check("the trainer exited 0", log.rstrip().splitlines()[-1].strip() == "exit 0")
    check("no stall", not stall)
    check("the keep choice announced", "keep choice (1.4c)" in log)
    M = [json.loads(x.replace("NaN", "null")) for x in open(mp, encoding="utf-8") if x.strip()]
    H = [m.get("head2") or {} for m in M]
    K = [m.get("keep") or {} for m in M]
    I = [m.get("intent") or {} for m in M]
    check("10 updates ({})".format(len(M)), len(M) >= 10)
    for m, h, k, i in zip(M, H, K, I):
        say("update {}: kl {} | keep g {} readings {} p {} (contact {} out {}) kl {} w {} | sim {} | blinders {} | trips {} reached {} | head raw {} hands {} clip {} pg {} v {}".format(
            m["update"], m.get("kl"), k.get("g"), k.get("readings"), k.get("p"), k.get("p_contact"), k.get("p_out"), k.get("kl"), k.get("w"), k.get("sim"),
            k.get("blinders"), i.get("trips_per_player_min"), i.get("reached"), h.get("raw"), h.get("hands"), h.get("clip_share"), h.get("pg_loss"), h.get("v_loss")))
    check("no NaN", all(isinstance(h.get("pg_loss"), (int, float)) and isinstance(h.get("v_loss"), (int, float)) and isinstance(m.get("kl"), (int, float))
                        and isinstance(k.get("kl"), (int, float)) for m, h, k in zip(M, H, K)))
    check("no piece skipped", not any(h.get("skipped") for h in H))
    check("the keep choice at share {} from the third update ({})".format(G, [k.get("g") for k in K]), all(k.get("g") == G for k in K[2:]))
    check("its readings counted", all((k.get("readings") or 0) > 0 for k in K[2:]))
    check("its step under 0.05 every update ({})".format([k.get("kl") for k in K]), all(abs(k.get("kl") or 0) < 0.05 for k in K))
    check("his step (kl) under 0.1 every update", all((m.get("kl") or 0) < 0.1 for m in M))
    check("the head's own scores and the hands' target logits under 60", all((h.get("raw") or 0) < 60 and (h.get("hands") or 0) < 60 for h in H))
    check("the head's clip share under 0.3", all((h.get("clip_share") or 0) < 0.3 for h in H))
    tr_ = [i.get("trips_per_player_min") or 0 for i in I[-5:]]
    re_ = [i.get("reached") or 0 for i in I[-5:]]
    check("no flicker: trips a player-minute {} (1.4b's {:.2f}; at most 1.5 times)".format(tr_, base_trips), max(tr_) <= 1.5 * base_trips)
    check("no flicker: targets reached {} (1.4b's {:.3f}; at least 0.7 times)".format(re_, base_reach), min(re_) >= 0.7 * base_reach)
    r = subprocess.run([PY, "-c", "import sys; sys.path.insert(0, 'sim'); import test_suite as T; p = T.Policy(sys.argv[1]); print('keep_g', p.keep_g, 'on', p.keep_on)",
                        os.path.join(D, "policy.pt")], cwd=ROOT, env=cenv, capture_output=True, text=True)
    say(r.stdout.strip()[-200:] or r.stderr[-300:])
    check("the save loads for the checks with the keep choice at share {}".format(G), r.returncode == 0 and "keep_g {} on True".format(G) in r.stdout)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
