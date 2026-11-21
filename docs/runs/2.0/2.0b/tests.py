"""2.0b's tests (owner, 2026-11-09: "continue the build and start it when it's ready"; docs/runs/2.0/2.0b/CARD.md). Nothing of a real run is
touched: scratch run folders only (data/sim_runs/scratch_20b_*), nothing deleted. CPU only, below normal; no run trains meanwhile. S0 = 2.0a's
end (keep/policy_end_20a.pt, with opt_end_20a.pt); S1 = S0 given 2.0b's parts (tools/b20b_init.py add). The simulator alone: tests_env.py.

  start   S1 answers as S0 (b20b_init same: 0 actions differ)
  ident   the trainer at a fixed seed (--seed 7, --max-updates 2, --dump-acts; no --overlap), 2 simulators x 8 matches x 96 frames, 2.0b's command
          made small, on S1 with 2.0a's anchors:
            z0, z0b  the start's live.json (every part shut): it repeats itself to the bit
            z2       EDGE_PAY 0.0005 and COVER_PAY 0.002, the gate shut: update 1's actions and log p the SAME as z0 to the bit (the pay changes
                     nothing before the first learning step); update 2's actions differ; update 1's ledger carries the two terms, zero-sum
                     (his counted seats net near nothing beside their size), and every old term as z0's
            z3       SPACE_GATE 1, no pay: update 1's actions and log p the SAME as z0 to the bit (the new inputs enter at zero weight: the
                     encoder's columns, the head's, and the two tokens' first layer); the ledger as z0's
  smoke   2.0b's command made small (the CPU, --overlap as the run), from S1 with its optimizer, the END dials from update 0 (SPACE_GATE 1,
          EDGE_PAY 0.0005), 10 updates: no NaN; the readout's record on every update, its skill above 0 for the threat and the zones by the
          last; the ledger carries the edge, no cover; the save carries SPACE_IN and SPACE_GATE (a check plays at the gate it trained at) and
          the readout's layers; it loads with its optimizer for one more update; a one-map check of the save against S0 finishes
  live    the real trainer with start.ps1's live.json: applied before the first rollout; SPACE_GATE 0.5 and EDGE_PAY 0.00025 written after
          update 1 are in live_applied.json by the end (from_update at most 4); the ledger's edge is zero at update 1 and there at the last
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
    python docs/runs/2.0/2.0b/tests.py start|ident|smoke|live"""
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
R0 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_2_0a")
S0, S0O = os.path.join(R0, "keep", "policy_end_20a.pt"), os.path.join(R0, "keep", "opt_end_20a.pt")
ANCH = os.path.join(R0, "snapshots")
TAG = os.environ.get("TEST_TAG", "")                     # (a re-run: new scratch folders beside the old, nothing deleted)
ST = os.path.join(ROOT, "data", "sim_runs", "scratch_20b_start" + TAG)
S1 = os.path.join(ST, "s1.pt")
CMD = os.path.join(HERE, "train.cmd")
INIT = os.path.join(ROOT, "tools", "b20b_init.py")
OK = [True]
END_DIALS = dict(SPACE_GATE=1.0, EDGE_PAY=0.0005)
OLD_TERMS = ("dmg_dealt", "dmg_taken", "frag", "death", "win_part")


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


def widen(src, dst, how="widen-league"):
    if not os.path.exists(dst):
        subprocess.check_call([PY, INIT, how, src, dst], env=cenv(), stdout=subprocess.DEVNULL)


def start():
    os.makedirs(ST, exist_ok=True)
    widen(S0, S1, "add")
    r = subprocess.run([PY, INIT, "same", S0, S1, "--seats", "8"], env=cenv(), capture_output=True, text=True)
    print(r.stdout + r.stderr[-2000:], flush=True)
    check("b20b_init same: the start answers as 2.0a's end (0 actions differ)", r.returncode == 0 and "ALL PASSED" in r.stdout)
    return done()


def make_cmd(run, D, minutes, ident=False, sets=(), args=()):
    """a small CPU copy of 2.0b's train.cmd: sets (NAME, VALUE) replace its set lines, args (flag, value) its arguments"""
    if not os.path.exists(CMD):
        subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "540"])
    t = open(CMD, encoding="ascii").read().replace("\r\n", "\n")
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
    ln_ = t.split("\n")
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
    assert not any(("duel_gru_1_" in x or "duel_gru_2_" in x) for x in live_), "a real run's name is left in the small command"
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    if os.path.exists(os.path.join(HERE, "aim2_env.cmd")) and not os.path.exists(os.path.join(D, "aim2_env.cmd")):
        shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    return cmd


def lay_out(run, live_extra=None):
    """a scratch run folder: S1 and S0's optimizer, two of 2.0a's anchors and S0 as a snapshot (all given 2.0b's inputs), 2.0a's live
    settings, the start's live.json (start_live.py)"""
    D = os.path.join(ROOT, "data", "sim_runs", run)
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (look at it first; nothing deleted)")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    if not os.path.exists(S1):
        raise SystemExit("no start: run `start` first")
    shutil.copy2(S1, os.path.join(D, "policy.pt"))
    shutil.copy2(S0O, os.path.join(D, "opt.pt"))
    for name, p_ in (("anchor_17a.pt", os.path.join(ANCH, "anchor_17a.pt")), ("anchor_16a.pt", os.path.join(ANCH, "anchor_16a.pt")), ("snap_0001.pt", S0)):
        w_ = os.path.join(ST, "w_" + name)
        widen(p_, w_)
        shutil.copy2(w_, os.path.join(D, "snapshots", name))
    shutil.copy2(os.path.join(R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    out = os.path.join(D, "live.json")
    subprocess.check_call([PY, os.path.join(HERE, "start_live.py"), os.path.join(R0, "live.json"), os.path.join(R0, "live_applied.json"), out],
                          env=cenv(), stdout=subprocess.DEVNULL)
    lv = json.load(open(out, encoding="utf-8"))
    lv.update(**(live_extra or {}))
    json.dump(lv, open(out, "w", encoding="utf-8"))
    return D


def trainer(cmd, run, limit_min):
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"),
                          stdin=subprocess.DEVNULL)
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


def pt(m):
    return m.get("pay_terms") or {}


def pm(m):
    return pt(m).get("per_player_min") or {}


def ss(m):
    return pt(m).get("size_share") or {}


def ident():
    import torch
    arms = [("z0", None), ("z0b", None), ("z2", dict(EDGE_PAY=0.0005, COVER_PAY=0.002)), ("z3", dict(SPACE_GATE=1.0))]
    acts, mets = {}, {}
    for name, lv in arms:
        run = "scratch_20b_id_" + name + TAG
        D = lay_out(run, live_extra=lv)
        log = trainer(make_cmd(run, D, 30, ident=True, args=(("--gate-start", "99999999"),)), run, 60)   # (the new tokens' gate opens by the
        #                                 wall clock: held at its first value, -12, so that a fixed seed repeats itself)
        dumps = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(dumps), "" if log else ", NO LOG"), log is not None and len(dumps) >= 2)
        acts[name] = [torch.load(f, map_location="cpu") for f in dumps[:2]]
        mets[name] = metrics(D)
        if log:
            check("{}: the optimizer's state loaded from opt.pt, not a cold start; its moments carried over the widened inputs".format(name),
                  "optimizer: its state loaded from opt.pt" in log and "cold start" not in log and "optimizer: enc.0.weight carried over" in log)
            check("{}: the readout 'space' from the network; no weapon table, no REFUSED live file".format(name),
                  "space (2.0b)" in log and "from the network" in log.split("space (2.0b)")[1][:600] and "the pros' weapon table (1.7c)" not in log and "REFUSED" not in log)
    if not all(len(acts.get(n, [])) >= 2 for n, _ in arms):
        check("every arm dumped its updates", False)
        return done()

    def same(x, y, k, u):
        a_, b_ = acts[x][u][k], acts[y][u][k]
        return a_.shape == b_.shape and bool(torch.equal(a_, b_))

    check("the trainer repeats itself at a fixed seed (z0 = z0b, both updates, actions and log p)", all(same("z0", "z0b", k, u) for k in ("act", "logp") for u in (0, 1)))
    check("the pay changes nothing before the first learning step (z2 = z0: update 1's actions and log p, to the bit)",
          all(same("z2", "z0", k, 0) for k in ("act", "logp")))
    d2 = float((acts["z2"][1]["act"] != acts["z0"][1]["act"]).float().mean())
    check("... and update 2's actions differ ({:.4f} of them): the pay reached the learning step".format(d2), d2 > 0)
    check("the open inputs' gate changes nothing before the first learning step (z3 = z0: update 1's actions and log p, to the bit): zero weight",
          all(same("z3", "z0", k, 0) for k in ("act", "logp")))
    d3 = float((acts["z3"][1]["act"] != acts["z0"][1]["act"]).float().mean())
    check("... and update 2's actions differ ({:.4f} of them): the inputs reached the learning step".format(d3), d3 > 0)
    p0, p2, p3 = (pm(mets[n][0]) if mets[n] else {} for n in ("z0", "z2", "z3"))
    s0, s2 = (ss(mets[n][0]) if mets[n] else {} for n in ("z0", "z2"))
    say("update 1's ledger z0: {} | edge {} cover {} (size shares {} {})".format({k_: p0.get(k_) for k_ in OLD_TERMS}, p0.get("edge"), p0.get("cover"), s0.get("edge"), s0.get("cover")))
    say("update 1's ledger z2: {} | edge {} cover {} (size shares {} {})".format({k_: p2.get(k_) for k_ in OLD_TERMS}, p2.get("edge"), p2.get("cover"), s2.get("edge"), s2.get("cover")))

    def eq(a_, b_):
        return all(abs((a_.get(k_) or 0.0) - (b_.get(k_) or 0.0)) <= 1e-6 * max(1.0, abs(a_.get(k_) or 0.0)) for k_ in OLD_TERMS)
    check("z0: no edge, no cover in the ledger", not (s0.get("edge") or 0) and not (s0.get("cover") or 0))
    check("z2: the edge and the cover are in the ledger (size shares {} and {})".format(s2.get("edge"), s2.get("cover")), (s2.get("edge") or 0) > 0 and (s2.get("cover") or 0) > 0)
    check("z2: every old term as z0's (the same frames, two terms more)", eq(p0, p2))
    check("z3: the ledger's old terms as z0's (the gate is no pay)", eq(p0, p3))
    return done()


def space_line(m):
    b = (m.get("space") or {}).get("both") or {}
    return {g_: (b.get(g_) or {}).get("skill") for g_ in ("thr", "put", "agg", "zones")}


def smoke():
    import torch
    run = "scratch_20b_smoke" + TAG
    D = lay_out(run, live_extra=dict(END_DIALS))
    c_ = make_cmd(run, D, 30000)                             # (--minutes counts the resumed run's minutes: --max-updates ends it)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 10")
    open(c_, "w", encoding="ascii", newline="").write(t_)
    log = trainer(c_, run, 90)
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    check("on the CPU", "device cpu" in log)
    check("the optimizer's state loaded from S0's opt.pt", "optimizer: its state loaded from opt.pt" in log)
    check("no weapon table, the keep choice not frozen, no REFUSED", "the pros' weapon table (1.7c)" not in log and "keep choice FROZEN" not in log and "REFUSED" not in log)
    M = metrics(D)
    check("8 or more updates ({})".format(len(M)), len(M) >= 8)
    for m in M:
        p_ = pm(m)
        say("update {}: dmg {} / {} frag {} death {} win {} | edge {} (share {}) cover {} | frags a match-minute {} | space {} (frames {})".format(
            m["update"], p_.get("dmg_dealt"), p_.get("dmg_taken"), p_.get("frag"), p_.get("death"), p_.get("win_part"), p_.get("edge"),
            ss(m).get("edge"), ss(m).get("cover"), m.get("frags_per_match_min"), space_line(m), (m.get("space") or {}).get("frames")))
    check("the ledger on every update", all(pm(m) for m in M))
    check("the edge in the ledger on every update, under a quarter of the pay's size; no cover",
          M and all(0 < (ss(m).get("edge") or 0) < 0.25 and not (ss(m).get("cover") or 0) for m in M))
    check("the readout's record on every update, with frames", M and all(((m.get("space") or {}).get("frames") or 0) > 0 for m in M))
    last = space_line(M[-1]) if M else {}
    check("the readout above its base rate by the last update: the threat on him {} and the zones {}".format(last.get("thr"), last.get("zones")),
          (last.get("thr") or 0) > 0 and (last.get("zones") or 0) > 0)
    hd = [m.get("head2") or {} for m in M]
    check("no NaN in the head's lessons or the trainer's kl and entropy",
          all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd) and
          all(math.isfinite(float(m.get("kl") or 0.0)) and math.isfinite(float(m.get("entropy") or 0.0)) for m in M))
    say("kl by update: {}".format([m.get("kl") for m in M]))
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    ev = ck.get("env_vars") or {}
    check("the save carries SPACE_IN 1 and SPACE_GATE 1 ({} {}), the readout's layers and layout, no wrule".format(ev.get("SPACE_IN"), ev.get("SPACE_GATE")),
          float(ev.get("SPACE_IN") or 0) == 1.0 and float(ev.get("SPACE_GATE") if ev.get("SPACE_GATE") is not None else -1) == 1.0 and
          any(k_.startswith("space.") for k_ in ck["model"]) and ck.get("spaceread") is not None and not ck.get("wrule"))
    wn = ck["model"]["enc.0.weight"][:, -59:].abs().max().item()
    check("the new inputs' weights have left zero ({:.5f}): he learns from them".format(wn), wn > 0)
    n0 = len(M)
    t2 = make_cmd(run, D, 30000)
    t_ = open(t2, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 1")
    open(t2, "w", encoding="ascii", newline="").write(t_)
    log2 = trainer(t2, run, 20)
    tail_ = (log2 or "")[len(log):] if log2 and log2.startswith(log[:200]) else (log2 or "")
    M2 = metrics(D)
    check("a restart from the save with its optimizer: loaded, no cold start, the readout from the network, one more update ({} -> {})".format(n0, len(M2)),
          log2 is not None and "optimizer: its state loaded from opt.pt" in tail_ and "cold start" not in tail_ and len(M2) == n0 + 1 and "space (2.0b)" in tail_)
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    os.environ["PANEL_RUN"] = run
    import panel as P
    js = os.path.join(D, "watch", "chk_smoke.json")
    cmd = [PY, "tools/duel_eval.py", "--run", run, "--policy", os.path.join(D, "policy.pt"), "--opp", "policy:" + S0,
           "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", "bloodrun", "--games", "2", "--minutes", "2", "--procs", "1", "--swap",
           "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600",
           "--opp-round", "600"]
    sets_ = P.settings(0.0, os.path.join(D, "policy.pt"))
    say("the check's settings of 2.0b: {}".format([x for x in sets_ if x.split("=")[0] in ("SPACE_IN", "SPACE_GATE", "SPACE_TRUTH", "EDGE_PAY")]))
    check("the check plays with SPACE_IN=1 and the save's gate", any(x.startswith("SPACE_IN=1") for x in sets_) and any(x.startswith("SPACE_GATE=1") for x in sets_))
    cmd += [x for s_ in sets_ for x in ("--set", s_)]
    r = subprocess.run(cmd, cwd=ROOT, env=cenv(), capture_output=True, text=True, stdin=subprocess.DEVNULL)
    jv = json.load(open(js)) if os.path.exists(js) else {}
    v = (jv.get("maps") or {}).get("bloodrun") or {}
    say("check: exit {}; {}".format(r.returncode, (r.stdout + r.stderr)[-600:]))
    check("a one-map check of the save against S0 finished ({}-{})".format(v.get("won"), v.get("lost")), r.returncode == 0 and "won" in v)
    return done()


def live():
    run = "scratch_20b_live" + TAG
    D = lay_out(run)
    lv0 = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    check("the start's live.json: every part shut, the lesson on ({})".format({k_: lv0.get(k_) for k_ in ("SPACE_GATE", "EDGE_PAY", "COVER_PAY", "SPACE_W")}),
          lv0.get("SPACE_GATE") == 0.0 and lv0.get("EDGE_PAY") == 0.0 and lv0.get("COVER_PAY") == 0.0 and lv0.get("SPACE_W") == 1.0)
    c_ = make_cmd(run, D, 30000)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 5")
    open(c_, "w", encoding="ascii", newline="").write(t_)
    MID = dict(SPACE_GATE=0.5, EDGE_PAY=0.00025)
    tr = subprocess.Popen(["cmd.exe", "/c", c_], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"), stdin=subprocess.DEVNULL)
    MET, wrote, t0, at = os.path.join(D, "metrics.jsonl"), False, time.time(), [0]
    while tr.poll() is None and time.time() - t0 < 60 * 60:
        time.sleep(1)
        if not wrote and os.path.exists(MET) and os.path.getsize(MET) > 0:
            at[0] = len(metrics(D))                           # (the small updates take seconds: the update the file was written after)
            lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
            lv.update(MID)
            json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
            wrote = True
            say("after update {}: live.json {}".format(at[0], MID))
    if tr.poll() is None:
        say("the trainer still runs after 60 min: left running")
        return done()
    log = open(os.path.join(ROOT, "data", "sim_runs", run + ".log"), encoding="utf-8", errors="replace").read()
    st = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_status.json")) else {}
    ap = json.load(open(os.path.join(D, "live_applied.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_applied.json")) else {}
    M = metrics(D)
    check("no refusal in the log", "REFUSED" not in log)
    check("live_status.json says applied ({})".format(st), st.get("status") == "applied")
    check("3 updates or more ({})".format(len(M)), len(M) >= 3)
    for m in M:
        say("update {}: edge {} (size share {}) | space {}".format(m["update"], pm(m).get("edge"), ss(m).get("edge"), space_line(m)))
    got = {k_: (ap.get("file") or {}).get(k_) for k_ in MID}
    check("live_applied.json carries the mid values by the end ({}, from update {}; written after update {})".format(got, ap.get("from_update"), at[0]),
          all(got.get(k_) == v_ for k_, v_ in MID.items()) and (ap.get("from_update") or 99) <= at[0] + 3)
    check("the ledger's edge: none at update 1, there at the last ({} -> {})".format(ss(M[0]).get("edge") if M else None, ss(M[-1]).get("edge") if M else None),
          M and not (ss(M[0]).get("edge") or 0) and (ss(M[-1]).get("edge") or 0) > 0)
    import torch
    ev = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False).get("env_vars") or {}
    check("the save carries the gate it trained at (SPACE_GATE {})".format(ev.get("SPACE_GATE")), ev.get("SPACE_GATE") is not None and abs(float(ev["SPACE_GATE"]) - 0.5) < 1e-9)
    return done()


if __name__ == "__main__":
    sys.exit({"start": start, "ident": ident, "smoke": smoke, "live": live}[sys.argv[1]]())
