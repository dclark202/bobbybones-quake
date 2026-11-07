"""1.7b's tests (owner, 2026-11-06 evening: "let's start 1.7b now", once built and tested; docs/runs/1.7/1.7b/BUILD.md). Nothing of a real
run is touched: scratch run folders only (data/sim_runs/scratch_17b_*), nothing deleted. CPU only, below normal; no run trains meanwhile.
S0 = 1.7a's result (its save of update 90, keep/policy_end_17a.pt, with opt_end_17a.pt); S1 = S0 given 1.7b's parts (tools/b17b_init.py add).

  start   S1 made; b17b_init same S0 S1: 0 actions differ at the files' shares and at the keep choice's and the order's share 1
  ident   the trainer at a fixed seed (--seed 7, --max-updates 2, --dump-acts; no --overlap), 2 simulators x 8 matches x 96 frames, 1.7b's
          command made small, on S1, the league's files widened (b17b_init widen-league):
            z0, z0b  the fight odds' lesson off (--fight-odds 0), FIGHT_TRUTH and OUT_LIVE off, everything else at 1.7b's start values:
                     the trainer repeats itself to the bit
            z1       1.7b's start as it is (the fight odds' lesson on, FIGHT_TRUTH=1, OUT_LIVE=1.5, H2_OPG 0, ORD_KL 0, CMB_G 0): both
                     updates' actions, log p and values the same as z0 to the bit (the new parts at zero move nothing); the optimizer's
                     state loaded, its moments carried over the widened inputs (the encoder, the marks, the timers' first layer, the
                     head's inp by the file's map), not a cold start
            z2       z1 with the order asked (CMB_G 1), its token open, the head learning it (H2_OPG 1) and the KL on (ORD_KL 1): the
                     actions differ from z1 from update 1 on
  smoke   1.7b's command made small (2 simulators, 8 matches, 96 frames, the CPU, --overlap as the run), from S1 with S0's optimizer, every
          dial open from update 0 (DMG_TAKEN_W 1, CMB_G 1, ORD_GATE 0, H2_OPG 1, ORD_KL 1), about 30 minutes: the fight odds learn (labels
          every update past the first FIGHT_D rows, its Brier finite, under the best constant's by the end), the order's KL recorded
          (divergence above 0, the two pulls), the order asked and every kind followed, break off reached by living (arrivals counted),
          no NaN; the save carries the readout, the reference, the head's part; a restart from the save with its optimizer loads it (one
          more update, no cold start); a one-map check of the save (every part open) against S0 finishes (the checks' player with the
          fight part and the order)
  live    the real trainer with start.ps1's live.json: applied before the first rollout; the dials written after update 1 (H2_OPG 0.5,
          ORD_KL 0.3, FIGHT_W 0.5, DMG_TAKEN_W 0.9) played by the last update
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
    python docs/runs/1.7/1.7b/tests.py start|ident|smoke|live"""
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
ST = os.path.join(ROOT, "data", "sim_runs", "scratch_17b_start")
S1 = os.path.join(ST, "s1.pt")
C17B = os.path.join(HERE, "train.cmd")
START_LIVE = dict(KEEP_G=1.0, CMB_G=0.0, PADD=0.0, ORD_GATE=-30.0, FADD=0.0, H2_FPG=0.0, DMG_TAKEN_W=0.8, H2_OPG=0.0, ORD_KL=0.0, FIGHT_W=1.0,
                  VALUE_WARM=0)                              # (start.ps1's live.json at the start)
OPEN = dict(START_LIVE, CMB_G=1.0, ORD_GATE=0.0, H2_OPG=1.0, ORD_KL=1.0, DMG_TAKEN_W=1.0)
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


def start():
    os.makedirs(ST, exist_ok=True)
    if not os.path.exists(S1):
        subprocess.check_call([PY, os.path.join(ROOT, "tools", "b17b_init.py"), "add", S0, S1, "--ref", os.path.join(R7A, "keep", "policy_10.pt")],
                              env=cenv())
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "b17b_init.py"), "same", S0, S1], env=cenv(), capture_output=True, text=True)
    print(r.stdout + r.stderr[-2000:], flush=True)
    check("b17b_init same: the start against 1.7a's update 90", r.returncode == 0 and "ALL PASSED" in r.stdout)
    return done()


def make_cmd(run, D, minutes, ident=False, sets=(), args=()):
    """a small CPU copy of 1.7b's train.cmd: sets (NAME, VALUE) replace its set lines, args (flag, value) its arguments"""
    if not os.path.exists(C17B):
        subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "1080"])
    t = open(C17B, encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal "), ("--workers 30 ", "--workers 2 "),
            ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "),
            (" --max-updates 150 ", " "),
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
    return cmd


def lay_out(run, live_extra=None):
    """a scratch run folder: S1, S0's optimizer, 1.7a's live dials with 1.7b's start values, two anchors and a snapshot widened"""
    D = os.path.join(ROOT, "data", "sim_runs", run)
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (look at it first; nothing deleted)")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(S1, os.path.join(D, "policy.pt"))
    shutil.copy2(S0O, os.path.join(D, "opt.pt"))
    for name, p_ in (("anchor_16a.pt", os.path.join(ANCH, "anchor_16a.pt")), ("anchor_b12d.pt", os.path.join(ANCH, "anchor_b12d.pt")),
                     ("snap_0001.pt", S0)):
        subprocess.check_call([PY, os.path.join(ROOT, "tools", "b17b_init.py"), "widen-league", p_, os.path.join(D, "snapshots", name)],
                              env=cenv(), stdout=subprocess.DEVNULL)
    shutil.copy2(os.path.join(R7A, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R7A, "live.json"), encoding="utf-8"))
    lv.update(START_LIVE)
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


OFF = dict(sets=(("FIGHT_TRUTH", "0"), ("OUT_LIVE", "0")), args=(("--fight-odds", "0"),))


def ident():
    import torch
    if not os.path.exists(S1):
        say("no test start: run `start` first")
        return 1
    arms = [("z0", OFF, None), ("z0b", OFF, None), ("z1", dict(sets=(), args=()), None),
            ("z2", dict(sets=(), args=()), dict(CMB_G=1.0, ORD_GATE=0.0, H2_OPG=1.0, ORD_KL=1.0))]
    acts = {}
    for name, ov, lv in arms:
        run = "scratch_17b_id_" + name + TAG
        D = lay_out(run, live_extra=lv)
        log = trainer(make_cmd(run, D, 30, ident=True, **ov), run, 60)
        dumps = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(dumps), "" if log else ", NO LOG"), log is not None and len(dumps) >= 2)
        acts[name] = [torch.load(f, map_location="cpu") for f in dumps[:2]]
        if log:
            check("{}: the optimizer's state loaded from opt.pt, not a cold start".format(name), "optimizer: its state loaded from opt.pt" in log and "cold start" not in log)
            check("{}: the optimizer's moments carried over the widened inputs (the encoder, the marks, the head's inp)".format(name),
                  "optimizer: enc.0.weight carried over" in log and "optimizer: attn.mark carried over" in log and "optimizer: head2.inp.weight carried over" in log)
            if name in ("z1", "z2"):
                check("{}: the fight odds announced (from the network, its lesson on) and the order's KL reference".format(name),
                      "fight odds (1.7b)" in log and "from the network" in log.split("fight odds (1.7b)")[1][:400] and "order KL (1.7b)" in log)
    if not all(len(acts.get(n, [])) >= 2 for n, *_ in arms):
        check("every arm dumped its updates", False)
        return done()

    def same(x, y, k, u):
        a_, b_ = acts[x][u][k], acts[y][u][k]
        return a_.shape == b_.shape and bool(torch.equal(a_, b_))

    check("the trainer repeats itself at a fixed seed (z0 = z0b, both updates, actions and log p)", all(same("z0", "z0b", k, u) for k in ("act", "logp") for u in (0, 1)))
    check("1.7b's start as it is = without the fight odds, the labels and break off's new rule, to the bit, both updates (z1 = z0: actions, log p, value)",
          all(same("z1", "z0", k, u) for k in ("act", "logp", "val") for u in (0, 1)))
    d2 = float((acts["z2"][0]["act"] != acts["z1"][0]["act"]).float().mean())
    check("the order asked and learnt: update 1's actions differ from z1 ({:.4f} of them)".format(d2), d2 > 0)
    return done()


def smoke():
    import torch
    if not os.path.exists(S1):
        say("no test start: run `start` first")
        return 1
    run = "scratch_17b_smoke" + TAG
    D = lay_out(run, live_extra=OPEN)
    log = trainer(make_cmd(run, D, 30), run, 45)
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    check("on the CPU", "device cpu" in log)
    check("the optimizer's state loaded from S0's opt.pt", "optimizer: its state loaded from opt.pt" in log)
    check("the fight odds and the order's KL announced", "fight odds (1.7b)" in log and "order KL (1.7b)" in log)
    M = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    check("8 or more updates ({})".format(len(M)), len(M) >= 8)
    F = [m.get("fight") or {} for m in M]
    for m, f in zip(M, F):
        b_ = f.get("both") or {}
        say("update {}: fight odds w {} frames {} pos {} Brier {} (constant {}) skill {} auc {} | ordkl {}".format(
            m["update"], f.get("w"), f.get("frames"), f.get("pos"), b_.get("brier"), f.get("brier_const"), b_.get("skill"), b_.get("auc"), m.get("ordkl")))
    lf = [f for f in F if (f.get("frames") or [0])[0] > 0]
    check("the fight odds labelled and scored ({} updates with labels)".format(len(lf)), len(lf) >= 3)
    check("its Brier finite", lf and all(all(math.isfinite(x) for x in (f.get("both") or {}).get("brier", [float("nan")])) for f in lf))
    if len(lf) >= 3:
        b0, b1 = (lf[0].get("both") or {}).get("brier"), (lf[-1].get("both") or {}).get("brier")
        c1 = lf[-1].get("brier_const")
        check("it learns: the last update's Brier under the first's and under the best constant's ({} -> {}; constant {})".format(b0, b1, c1),
              b0 and b1 and c1 and sum(b1) < sum(b0) and sum(b1) < sum(c1))
    OKL = [m.get("ordkl") or {} for m in M]
    lk = [o for o in OKL[1:] if (o.get("frames") or 0) > 0]
    check("the order's KL recorded: asked frames, a divergence above 0 and both pulls ({})".format([(o.get("kl"), o.get("g_kl"), o.get("g_pg")) for o in lk][-3:]),
          lk and any((o.get("kl") or 0) > 0 for o in lk) and any((o.get("g_kl") or 0) > 0 and (o.get("g_pg") or 0) > 0 for o in lk)
          and all(o.get("opg") == 1.0 and o.get("w") == 1.0 for o in lk))
    C = [m.get("cmb") or {} for m in M]
    lc_ = [c for c in C[1:] if c]
    ch_, ar_ = {}, {}
    for c in lc_:
        for k_, v_ in ((c.get("sim") or {}).get("frames") or {}).items():
            ch_[k_] = ch_.get(k_, 0) + v_
        for k_, v_ in ((c.get("sim") or {}).get("arrived") or {}).items():
            ar_[k_] = ar_.get(k_, 0) + v_
    check("the order asked at share 1 and every kind followed ({})".format(ch_), lc_ and all(c.get("g") == 1.0 for c in lc_)
          and all(ch_.get(k_, 0) > 0 for k_ in ("target", "cut", "spam", "out")))
    check("break off reached by living through it, cut off and spam arrived ({})".format(ar_), ar_.get("out", 0) > 0 and ar_.get("cut", 0) > 0 and ar_.get("spam", 0) > 0)
    hd = [m.get("head2") or {} for m in M]
    check("no NaN in the head's lessons", all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd))
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    L_ = ck.get("head2") or {}
    sd_ = ck["model"]
    check("the save carries the fight odds (layout, weights), the order's reference and the head's part fight (2)",
          ck.get("fightodds") is not None and "fight.both.0.weight" in sd_ and ck.get("order_ref") is not None and int(L_["widths"].get("fight", 0)) == 2)
    n0 = len(M)
    log2 = trainer(make_cmd(run, D, 30, args=(("--ord-kl", "0"),)).replace("small.cmd", "small.cmd"), run, 15) if False else None
    t2 = make_cmd(run, D, 30)
    t_ = open(t2, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 1")
    open(t2, "w", encoding="ascii", newline="").write(t_)
    log2 = trainer(t2, run, 15)
    tail_ = (log2 or "")[len(log):] if log2 and log2.startswith(log[:200]) else (log2 or "")
    M2 = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    check("a restart from the save with its optimizer: loaded, no cold start, one more update ({} -> {})".format(n0, len(M2)),
          log2 is not None and "optimizer: its state loaded from opt.pt" in tail_ and "cold start" not in tail_ and len(M2) == n0 + 1)
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    os.environ["PANEL_RUN"] = run
    import panel as P
    js = os.path.join(D, "watch", "chk_smoke.json")
    cmd = [PY, "tools/duel_eval.py", "--run", run, "--policy", os.path.join(D, "policy.pt"), "--opp", "policy:" + S0,
           "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", "bloodrun", "--games", "2", "--minutes", "2", "--procs", "1", "--swap",
           "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600",
           "--opp-round", "600"]
    cmd += [x for s_ in P.settings(0.0, os.path.join(D, "policy.pt")) for x in ("--set", s_)]
    r = subprocess.run(cmd, cwd=ROOT, env=cenv(), capture_output=True, text=True)
    jv = json.load(open(js)) if os.path.exists(js) else {}
    v = (jv.get("maps") or {}).get("bloodrun") or {}
    say("check: exit {}; {}".format(r.returncode, (r.stdout + r.stderr)[-600:]))
    check("a one-map check of the save (every part open) against S0 finished ({}-{})".format(v.get("won"), v.get("lost")), r.returncode == 0 and "won" in v)
    return done()


def live():
    if not os.path.exists(S1):
        say("no test start: run `start` first")
        return 1
    run = "scratch_17b_live" + TAG
    D = lay_out(run)
    tr = subprocess.Popen(["cmd.exe", "/c", make_cmd(run, D, 8)], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"))
    MET, wrote, t0 = os.path.join(D, "metrics.jsonl"), False, time.time()
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(5)
        if not wrote and os.path.exists(MET) and os.path.getsize(MET) > 0:
            lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
            lv.update(H2_OPG=0.5, ORD_KL=0.3, FIGHT_W=0.5, DMG_TAKEN_W=0.9)
            json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
            wrote = True
            say("after update 1: live.json H2_OPG 0.5, ORD_KL 0.3, FIGHT_W 0.5, DMG_TAKEN_W 0.9")
    if tr.poll() is None:
        say("the trainer still runs after 40 min: left running")
        return done()
    log = open(os.path.join(ROOT, "data", "sim_runs", run + ".log"), encoding="utf-8", errors="replace").read()
    st = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_status.json")) else {}
    M = [json.loads(x) for x in open(MET, encoding="utf-8") if x.strip()] if os.path.exists(MET) else []
    check("no refusal in the log", "REFUSED" not in log)
    check("live_status.json says applied ({})".format(st), st.get("status") == "applied")
    check("3 updates or more ({})".format(len(M)), len(M) >= 3)
    for m in M:
        say("update {}: ordkl {} | fight w {} | live in force {}".format(m["update"], m.get("ordkl"), (m.get("fight") or {}).get("w"),
                                                                       {k_: ((m.get("live") or {}).get("in_force") or {}).get(k_) for k_ in ("DMG_TAKEN_W", "H2_OPG", "ORD_KL", "FIGHT_W")}))
    o0, o1 = (M[0].get("ordkl") or {}) if M else {}, (M[-1].get("ordkl") or {}) if M else {}
    check("update 1 at H2_OPG 0, ORD_KL 0 ({})".format(o0), o0.get("opg") == 0.0 and o0.get("w") == 0.0)
    check("the dials written after update 1 played by the last update (H2_OPG 0.5, ORD_KL 0.3, FIGHT_W 0.5: {}, fight w {})".format(
        o1, (M[-1].get("fight") or {}).get("w") if M else None), o1.get("opg") == 0.5 and o1.get("w") == 0.3 and (M[-1].get("fight") or {}).get("w") == 0.5)
    return done()


if __name__ == "__main__":
    sys.exit({"start": start, "ident": ident, "smoke": smoke, "live": live}[sys.argv[1]]())
