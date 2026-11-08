"""1.7c's tests (owner, 2026-11-07 evening: "ok let's do it then. start it when it's ready"; docs/runs/1.7/1.7c/TRAIN_UNDER_TABLE.md). Nothing
of a real run is touched: scratch run folders only (data/sim_runs/scratch_17c_*), nothing deleted. CPU only, below normal; no run trains
meanwhile. S0 = 1.7a's result (its save of update 90, keep/policy_end_17a.pt, with opt_end_17a.pt), used as it is (no conversion).

  ident   the trainer at a fixed seed (--seed 7, --max-updates 2, --dump-acts; no --overlap), 2 simulators x 8 matches x 96 frames, 1.7c's
          command made small, on S0 with 1.7a's anchors:
            z0, z0b  the rule off (--wrule -1 --keep-freeze 0): the trainer as before 1.7c; it repeats itself to the bit
            z1       --wrule 0 (on, the share 0) --keep-freeze 0: both updates' actions, log p and values the same as z0 to the bit (the
                     rule at share 0 and the copy loss on no frame move nothing; the optimizer's state loaded, not a cold start)
            z2       1.7c as it runs after its ramp: WRULE_P 1, --keep-freeze 1: the actions differ from z1 from update 1 on; every seat
                     under the table (wrule.lives 1), the key set by it on most frames
  smoke   1.7c's command made small (2 simulators, 8 matches, 96 frames, the CPU, --overlap as the run), from S0 with its optimizer, WRULE_P 1
          from update 0, about 30 minutes: the table's share 1 and the key set by it over half the frames; the copy loss finite and falling,
          his own key's agreement with the table rising; the keep choice's log-probability out (its mask zero); no NaN; the save carries
          `wrule`; a restart from the save with its optimizer loads it (one more update, no cold start); a one-map check of the save UNDER
          the table against S0 plain finishes (the checks' player with the replace form)
  live    the real trainer with start.ps1's live.json (WRULE_P 0): applied before the first rollout; WRULE_P 0.5 written after update 1 is
          played by the last update (wrule.p 0.5)
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
    python docs/runs/1.7/1.7c/tests.py ident|smoke|live"""
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
PY = sys.executable
BS = "\\"
R7A = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a")
S0, S0O = os.path.join(R7A, "keep", "policy_end_17a.pt"), os.path.join(R7A, "keep", "opt_end_17a.pt")
ANCH = os.path.join(R7A, "snapshots")
ST = os.path.join(ROOT, "data", "sim_runs", "scratch_17c_start")
S1 = os.path.join(ST, "s1.pt")                           # S0 widened to today's 994 inputs with zero weights (tools/b17b_init.py widen-league:
C17C = os.path.join(HERE, "train.cmd")                   # 1.7b's four timer inputs; it answers as S0: `same`)
OK = [True]
TAG = os.environ.get("TEST_TAG", "")                     # (a re-run: new scratch folders beside the old, nothing deleted)


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def check(name, cond):
    OK[0] = OK[0] and bool(cond)
    say(("PASS " if cond else "FAIL ") + name)


def cenv():
    return dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1")


def done():
    say("ALL PASSED" if OK[0] else "FAILED")
    return 0 if OK[0] else 1


def widen(src, dst):
    """a 990-input file (1.7a's) to today's 994 inputs, zero weights on the new ones (b17b_init widen-league)"""
    if not os.path.exists(dst):
        subprocess.check_call([PY, os.path.join(ROOT, "tools", "b17b_init.py"), "widen-league", src, dst], env=cenv(), stdout=subprocess.DEVNULL)


def start():
    os.makedirs(ST, exist_ok=True)
    widen(S0, S1)
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "b17b_init.py"), "same", S0, S1], env=cenv(), capture_output=True, text=True)
    print(r.stdout + r.stderr[-2000:], flush=True)
    check("b17b_init same: the widened start answers as 1.7a's update 90 (0 actions differ)", r.returncode == 0 and "ALL PASSED" in r.stdout)
    return done()


def make_cmd(run, D, minutes, ident=False, sets=(), args=()):
    """a small CPU copy of 1.7c's train.cmd: sets (NAME, VALUE) replace its set lines, args (flag, value) its arguments"""
    if not os.path.exists(C17C):
        subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "840"])
    t = open(C17C, encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal "), ("--workers 30 ", "--workers 2 "),
            ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "),
            ("%LEARN% >> ", "--snapshot-min {} {} >> ".format(1000 if ident else 1, "--seed 7 --max-updates 2 --dump-acts " + os.path.join(D, "acts")
                                                               if ident else "--overlap 1 --learn-nosync 1"))]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    for n_, v_ in sets:
        assert len(re.findall(r"^set {}=.*$".format(n_), t, re.M)) == 1, n_
        t = re.sub(r"^set {}=.*$".format(n_), "set {}={}".format(n_, v_), t, flags=re.M)
    ln_ = t.split("\n")                                      # (the arguments: the trainer's command line only, not its rem lines)
    ci_ = [i for i, x in enumerate(ln_) if "train_duel_rnn.py" in x and not x.startswith("rem")]
    assert len(ci_) == 1
    for f_, v_ in args:
        assert len(re.findall(r" {} \S+ ".format(re.escape(f_)), ln_[ci_[0]])) == 1, f_
        ln_[ci_[0]] = re.sub(r" {} \S+ ".format(re.escape(f_)), " {} {} ".format(f_, v_), ln_[ci_[0]])
    t = "\n".join(ln_)
    t = re.sub(r"--run duel_gru_\S+ ", "--run {} ".format(run), t)
    t = re.sub(r"--minutes \d+ --gamma", "--minutes {} --gamma".format(minutes), t)
    t = re.sub(r"data\\sim_runs\\duel_gru_[0-9a-z_]+\.log", lambda m_: "data" + BS + "sim_runs" + BS + run + ".log", t)
    live_ = [x for x in t.split("\n") if not x.startswith("rem")]
    assert not any("duel_gru_1_" in x for x in live_), "a real run's name is left in the small command"
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    if os.path.exists(os.path.join(HERE, "aim2_env.cmd")) and not os.path.exists(os.path.join(D, "aim2_env.cmd")):
        shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))   # (the command calls it beside itself: the aim settings)
    return cmd


def start_live(D):
    """start.ps1's live.json (start_live.py: the save's own live values with 1.7c's changes)"""
    out = os.path.join(D, "live.json")
    subprocess.check_call([PY, os.path.join(HERE, "start_live.py"), S0, os.path.join(R7A, "live.json"), out], env=cenv(), stdout=subprocess.DEVNULL)
    return json.load(open(out, encoding="utf-8"))


def lay_out(run, live_extra=None):
    """a scratch run folder: S0 and its optimizer, two of 1.7a's anchors and S0 as a snapshot, 1.7a's live settings, the start's live.json"""
    D = os.path.join(ROOT, "data", "sim_runs", run)
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (look at it first; nothing deleted)")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    if not os.path.exists(S1):
        raise SystemExit("no widened start: run `start` first")
    shutil.copy2(S1, os.path.join(D, "policy.pt"))
    shutil.copy2(S0O, os.path.join(D, "opt.pt"))
    for name, p_ in (("anchor_16a.pt", os.path.join(ANCH, "anchor_16a.pt")), ("anchor_b12d.pt", os.path.join(ANCH, "anchor_b12d.pt")), ("snap_0001.pt", S0)):
        w_ = os.path.join(ST, "w_" + name)
        widen(p_, w_)
        shutil.copy2(w_, os.path.join(D, "snapshots", name))
    shutil.copy2(os.path.join(R7A, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = start_live(D)
    lv.update(**(live_extra or {}))
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    return D


def trainer(cmd, run, limit_min):
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"))
    while tr.poll() is None and time.time() - t0 < limit_min * 60:
        time.sleep(10)
    if tr.poll() is None:
        say("{}: the trainer still runs after {} min: left running".format(run, limit_min))
        return None
    log = open(os.path.join(ROOT, "data", "sim_runs", run + ".log"), encoding="utf-8", errors="replace").read()
    say("{}: done in {:.1f} min; the log ends: {}".format(run, (time.time() - t0) / 60, log.rstrip().splitlines()[-1] if log.strip() else "(empty)"))
    return log


def metrics(D):
    p = os.path.join(D, "metrics.jsonl")
    return [json.loads(x) for x in open(p, encoding="utf-8") if x.strip()] if os.path.exists(p) else []


OFF = dict(args=(("--wrule", "-1"), ("--keep-freeze", "0")))
Z1 = dict(args=(("--keep-freeze", "0"),))


def ident():
    import torch
    arms = [("z0", OFF, None), ("z0b", OFF, None), ("z1", Z1, None), ("z2", dict(args=()), dict(WRULE_P=1.0))]
    acts, mets = {}, {}
    for name, ov, lv in arms:
        run = "scratch_17c_id_" + name + TAG
        D = lay_out(run, live_extra=lv)
        log = trainer(make_cmd(run, D, 30, ident=True, **ov), run, 60)
        dumps = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(dumps), "" if log else ", NO LOG"), log is not None and len(dumps) >= 2)
        acts[name] = [torch.load(f, map_location="cpu") for f in dumps[:2]]
        mets[name] = metrics(D)
        if log:
            check("{}: the optimizer's state loaded from opt.pt, not a cold start; its moments carried over the widened inputs".format(name),
                  "optimizer: its state loaded from opt.pt" in log and "cold start" not in log and "optimizer: enc.0.weight carried over" in log)
            if name != "z0b":
                check("{}: the pros' weapon table announced {}".format(name, "(on)" if name != "z0" else "not at all (off)"),
                      ("the pros' weapon table (1.7c)" in log) == (name != "z0"))
    if not all(len(acts.get(n, [])) >= 2 for n, *_ in arms):
        check("every arm dumped its updates", False)
        return done()

    def same(x, y, k, u):
        a_, b_ = acts[x][u][k], acts[y][u][k]
        return a_.shape == b_.shape and bool(torch.equal(a_, b_))

    check("the trainer repeats itself at a fixed seed (z0 = z0b, both updates, actions and log p)", all(same("z0", "z0b", k, u) for k in ("act", "logp") for u in (0, 1)))
    check("1.7c's rule on at share 0 = the trainer before it, to the bit, both updates (z1 = z0: actions, log p, value)",
          all(same("z1", "z0", k, u) for k in ("act", "logp", "val") for u in (0, 1)))
    d2 = float((acts["z2"][0]["act"] != acts["z1"][0]["act"]).float().mean())
    check("under the table: update 1's actions differ from z1 ({:.4f} of them)".format(d2), d2 > 0)
    w2 = [(m.get("wrule") or {}) for m in mets["z2"]]
    say("z2 wrule: {}".format(w2))
    check("z2: every seat under the table (lives 1), the key set by it on most frames, the copy loss on frames and finite",
          w2 and all(w.get("lives") == 1.0 and (w.get("set") or 0) > 0.5 and (w.get("frames") or 0) > 0 and math.isfinite(w.get("loss") or float("nan")) for w in w2))
    w1 = [(m.get("wrule") or {}) for m in mets["z1"]]
    check("z1: the share 0 played (lives 0, the key never set, no copy frames)", w1 and all(w.get("lives") == 0.0 and w.get("set") == 0.0 and w.get("frames") == 0 for w in w1))
    return done()


def smoke():
    import torch
    run = "scratch_17c_smoke" + TAG
    D = lay_out(run, live_extra=dict(WRULE_P=1.0))
    c_ = make_cmd(run, D, 30000)                             # (--minutes counts the resumed run's minutes: --max-updates ends it)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 10")
    open(c_, "w", encoding="ascii", newline="").write(t_)
    log = trainer(c_, run, 60)
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    check("on the CPU", "device cpu" in log)
    check("the optimizer's state loaded from S0's opt.pt", "optimizer: its state loaded from opt.pt" in log)
    check("the pros' weapon table announced, the keep choice frozen", "the pros' weapon table (1.7c)" in log and "keep choice FROZEN" in log)
    M = metrics(D)
    check("8 or more updates ({})".format(len(M)), len(M) >= 8)
    W = [m.get("wrule") or {} for m in M]
    for m, w in zip(M, W):
        say("update {}: wrule {} | keep {}".format(m["update"], w, {k_: (m.get("keep") or {}).get(k_) for k_ in ("g", "kl")}))
    check("every seat under the table (lives 1) and the key set by it on over half the frames", W and all(w.get("lives") == 1.0 and (w.get("set") or 0) > 0.5 for w in W))
    L = [w.get("loss") for w in W if w.get("frames")]
    A = [w.get("agree") for w in W if w.get("frames")]
    check("the copy loss finite on every update and lower at the end than at the start ({} -> {}); the agreement rising ({} -> {})".format(
        L[0] if L else None, L[-1] if L else None, A[0] if A else None, A[-1] if A else None),
        len(L) >= 4 and all(math.isfinite(x) for x in L) and L[-1] < L[0] and A[-1] > A[0])
    hd = [m.get("head2") or {} for m in M]
    check("no NaN in the head's lessons", all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd))
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    check("the save carries wrule (the checks play it under the table)", ck.get("wrule") == 1)
    n0 = len(M)
    t2 = make_cmd(run, D, 30000)
    t_ = open(t2, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 1")
    open(t2, "w", encoding="ascii", newline="").write(t_)
    log2 = trainer(t2, run, 15)
    tail_ = (log2 or "")[len(log):] if log2 and log2.startswith(log[:200]) else (log2 or "")
    M2 = metrics(D)
    check("a restart from the save with its optimizer: loaded, no cold start, one more update ({} -> {})".format(n0, len(M2)),
          log2 is not None and "optimizer: its state loaded from opt.pt" in tail_ and "cold start" not in tail_ and len(M2) == n0 + 1)
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    os.environ["PANEL_RUN"] = run
    import panel as P
    js = os.path.join(D, "watch", "chk_smoke.json")
    cmd = [PY, "tools/duel_eval.py", "--run", run, "--policy", os.path.join(D, "policy.pt"), "--opp", "policy:" + S0,
           "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", "bloodrun", "--games", "2", "--minutes", "2", "--procs", "1", "--swap",
           "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600",
           "--opp-round", "600", "--wpush", "1", "--wpush-form", "replace"]
    cmd += [x for s_ in P.settings(0.0, os.path.join(D, "policy.pt")) for x in ("--set", s_)]
    r = subprocess.run(cmd, cwd=ROOT, env=cenv(), capture_output=True, text=True)
    jv = json.load(open(js)) if os.path.exists(js) else {}
    v = (jv.get("maps") or {}).get("bloodrun") or {}
    say("check: exit {}; {}".format(r.returncode, (r.stdout + r.stderr)[-600:]))
    check("a one-map check of the save under the table against S0 plain finished ({}-{}; owned {})".format(v.get("won"), v.get("lost"), (v.get("he") or {}).get("weapons_owned")),
          r.returncode == 0 and "won" in v and "weapons_owned" in (v.get("he") or {}))
    return done()


def live():
    run = "scratch_17c_live" + TAG
    D = lay_out(run)
    c_ = make_cmd(run, D, 30000)                             # (--minutes counts the resumed run's minutes, 24,886 at update 90: --max-updates ends it)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 5")   # (a dial written after
    open(c_, "w", encoding="ascii", newline="").write(t_)                                                                              # update 1 is played by 4)
    tr = subprocess.Popen(["cmd.exe", "/c", c_], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"))
    MET, wrote, t0 = os.path.join(D, "metrics.jsonl"), False, time.time()
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(5)
        if not wrote and os.path.exists(MET) and os.path.getsize(MET) > 0:
            lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
            lv.update(WRULE_P=0.5)
            json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
            wrote = True
            say("after update 1: live.json WRULE_P 0.5")
    if tr.poll() is None:
        say("the trainer still runs after 40 min: left running")
        return done()
    log = open(os.path.join(ROOT, "data", "sim_runs", run + ".log"), encoding="utf-8", errors="replace").read()
    st = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_status.json")) else {}
    M = metrics(D)
    check("no refusal in the log", "REFUSED" not in log)
    check("live_status.json says applied ({})".format(st), st.get("status") == "applied")
    check("3 updates or more ({})".format(len(M)), len(M) >= 3)
    for m in M:
        say("update {}: wrule {} | live in force {}".format(m["update"], m.get("wrule"), {k_: ((m.get("live") or {}).get("in_force") or {}).get(k_) for k_ in ("WRULE_P", "HABIT_P", "KEEP_G")}))
    w0, w1 = (M[0].get("wrule") or {}) if M else {}, (M[-1].get("wrule") or {}) if M else {}
    check("update 1 at WRULE_P 0 ({})".format(w0.get("p")), w0.get("p") == 0.0)
    check("WRULE_P 0.5 written after update 1 played by the last update ({})".format(w1.get("p")), w1.get("p") == 0.5)
    return done()


if __name__ == "__main__":
    sys.exit({"start": start, "ident": ident, "smoke": smoke, "live": live}[sys.argv[1]]())
