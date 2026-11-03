"""1.3b's dry run (owner, 2026-11-03: "start with the builds"; CARD.md, "Before the start"): 1.3b's own train.cmd at full size (the card, the
8 performance cores) for 10 updates on a scratch copy, from b1.2d's end with the head added as start.ps1 adds it, into
data/sim_runs/scratch_13b_dry (new). The credit dial H2_PG is 0 for updates 1 to 4, 0.5 for 5 to 7 and 1 from 8 (faster than the ramp, to see
both ends). No watcher, no ramp, no checks.
Passes when: exit 0; 10 updates, each within 12 minutes (no stall); the add on; no NaN, no piece skipped; the credit reached 1; the head's own
scores' centred length under 60 (the tripwire) and the hands' target logits' under 60; his whole step (kl) under 0.1 every update; the head's
clip share under 0.3; the save loads for the checks (test_suite.Policy) with add 1.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\b1.3\\1.3b\\dryrun_13b.py > docs\\runs\\b1.3\\1.3b\\dryrun_13b.log"""
import json, os, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
SR = os.path.join(ROOT, "data", "sim_runs")
R0 = os.path.join(SR, "duel_gru_b1_2d")
RUN = sys.argv[1] if len(sys.argv) > 1 else "scratch_13b_dry"
D = os.path.join(SR, RUN)
BS = "\\"
DIAL = {0: 0.0, 4: 0.5, 7: 1.0}                                  # after update n is recorded: H2_PG (read three or so rollouts later)


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def main():
    if os.path.exists(D):
        say(D + " is there: not started (look at it first; nothing deleted)")
        return 1
    ps_ = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | Select-Object -ExpandProperty CommandLine"],
                         capture_output=True, text=True).stdout
    if any("train_duel_rnn" in l and "dryrun_13b" not in l for l in ps_.splitlines()):
        say("a trainer is running: not started")
        return 1
    END, OPT = os.path.join(R0, "keep", "policy_end_b12d.pt"), os.path.join(R0, "keep", "opt_end_b12d.pt")
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1")
    cenv = dict(env, CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")
    for s_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, s_))
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "head2_init.py"), "add", END, os.path.join(D, "policy.pt"), "--gate", "0", "--ctrl-src", "belief",
                        "--add", "1", "--chrono-lo", "1", "--opt", OPT, os.path.join(D, "opt.pt")], cwd=ROOT, env=cenv, capture_output=True, text=True)
    say(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
    assert r.returncode == 0
    shutil.copy2(os.path.join(D, "policy.pt"), os.path.join(D, "keep", "policy_start.pt"))
    shutil.copy2(END, os.path.join(D, "snapshots", "anchor_b12d.pt"))
    shutil.copy2(os.path.join(R0, "keep", "control_b11.pt"), os.path.join(D, "snapshots", "anchor_b11.pt"))
    shutil.copy2(os.path.join(SR, "duel_gru_b1_2c", "keep", "control_v060_end.pt"), os.path.join(D, "snapshots", "anchor_v060_end.pt"))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R0, "live.json"), encoding="utf-8"))
    lv.update(H2_GATE_CAP=0.0, H2_GATE_OPEN=0.0, H2_PG=0.0, H2_MIX=0.0, H2_COPY=0.0, VALUE_WARM=0)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    subprocess.run([PY, os.path.join(HERE, "make_files.py"), "720"], cwd=ROOT, env=env, check=True)
    t = open(os.path.join(HERE, "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")
    t = re.sub(r"--minutes \d+ --gamma", "--minutes 150 --max-updates 10 --gamma", t)
    for a_, b_ in (("--run duel_gru_1_3b ", "--run " + RUN + " "), ("data" + BS + "sim_runs" + BS + "duel_gru_1_3b.log", "data" + BS + "sim_runs" + BS + RUN + ".log"),
                   ("call %~dp0aim2_env.cmd", "call " + os.path.join(HERE, "aim2_env.cmd")),
                   ("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT=" + ROOT)):
        assert t.count(a_) >= 1, a_
        t = t.replace(a_, b_)
    cmd = os.path.join(D, "dry.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=env)
    say("the dry run's trainer started (10 updates, full size)")
    mp = os.path.join(D, "metrics.jsonl")
    seen, t0, t_last = 0, time.time(), time.time()
    stall = False
    while tr.poll() is None and time.time() - t0 < 150 * 60:
        n_ = sum(1 for x in open(mp, encoding="utf-8") if x.strip()) if os.path.exists(mp) else 0
        if n_ > seen:
            seen, t_last = n_, time.time()
            if n_ in DIAL:
                lv["H2_PG"] = DIAL[n_]
                json.dump(lv, open(os.path.join(D, "live.json.tmp"), "w", encoding="utf-8"))
                os.replace(os.path.join(D, "live.json.tmp"), os.path.join(D, "live.json"))
            say("update {} recorded; H2_PG in the file {}".format(n_, lv["H2_PG"]))
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
    check("the add on", "head2: add 1 (1.3b)" in log)
    M = [json.loads(x.replace("NaN", "null")) for x in open(mp, encoding="utf-8") if x.strip()]
    H = [m.get("head2") or {} for m in M]
    check("10 updates ({})".format(len(M)), len(M) >= 10)
    for m, h in zip(M, H):
        say("update {}: credit {} raw {} hands {} sum {} cos {} l2 {} cap {} kl {} head clip {} pg {} v {}".format(
            m["update"], h.get("credit"), h.get("raw"), h.get("hands"), h.get("sum"), h.get("cos"), h.get("l2"), h.get("norm_cap"), m.get("kl"),
            h.get("clip_share"), h.get("pg_loss"), h.get("v_loss")))
    check("no NaN", all(isinstance(h.get("pg_loss"), (int, float)) and isinstance(h.get("v_loss"), (int, float)) and isinstance(m.get("kl"), (int, float)) for m, h in zip(M, H)))
    check("no piece skipped", not any(h.get("skipped") for h in H))
    check("the credit reached 1", any(h.get("credit") == 1.0 for h in H))
    check("the head's own scores under 60", all((h.get("raw") or 0) < 60 for h in H))
    check("the hands' target logits under 60", all((h.get("hands") or 0) < 60 for h in H))
    check("his step (kl) under 0.1 every update", all((m.get("kl") or 0) < 0.1 for m in M))
    check("the head's clip share under 0.3", all((h.get("clip_share") or 0) < 0.3 for h in H))
    g_ = [(H[i]["raw"] - H[i - 1]["raw"]) for i in range(len(H) - 3, len(H))] if len(H) >= 4 else [9.0]
    check("the head's part levels off: under 0.5 an update over the last three ({})".format([round(x, 2) for x in g_]), max(g_) < 0.5)
    check("the hands' part under 30 ({})".format(H[-1].get("hands")), (H[-1].get("hands") or 99) < 30)
    check("the hands' part not shrunk: over 19 at every update (b1.2d's about 22; dry run 1 without the L2: 21.6 to 24.1) ({})".format([h.get("hands") for h in H]),
          all((h.get("hands") or 0) > 19 for h in H))
    r = subprocess.run([PY, "-c", "import sys; sys.path.insert(0, 'sim'); import test_suite as T; p = T.Policy(sys.argv[1]); print('add', float(p.h2W['add']), 'live', p.h2_live)",
                        os.path.join(D, "policy.pt")], cwd=ROOT, env=cenv, capture_output=True, text=True)
    say(r.stdout.strip()[-200:] or r.stderr[-300:])
    check("the save loads for the checks with add 1", r.returncode == 0 and "add 1.0 live True" in r.stdout)
    say("ALL PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
