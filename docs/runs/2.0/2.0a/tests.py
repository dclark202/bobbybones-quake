"""2.0a's tests (owner, 2026-11-08: "If you think you have something to try tonight try it"; docs/runs/2.0/2.0a/CARD.md). Nothing of a real run is
touched: scratch run folders only (data/sim_runs/scratch_20a_*), nothing deleted. CPU only, below normal; no run trains meanwhile. S0 = 1.7a's
result (its save of update 90, keep/policy_end_17a.pt, with opt_end_17a.pt), widened to today's 994 inputs (S1).

  start   S1 answers as S0 (b17b_init same: 0 actions differ)
  ident   the trainer at a fixed seed (--seed 7, --max-updates 2, --dump-acts; no --overlap), 2 simulators x 8 matches x 96 frames, 2.0a's command
          made small, on S1 with 1.7a's anchors:
            z0, z0b  the start's live.json (the save's own values: DMG_REWARD 0.0055, DMG_TAKEN_W 0.8, WIN_ADD 0.33): it repeats itself to the bit
            z2       the ramp's END dials (0.001, 1.0, 0.6): update 1's actions and log p the SAME as z0 to the bit (the same network, the same
                     draws: the pay changes nothing before the first learning step); update 2's actions differ; and update 1's ledger is exactly
                     the dials' arithmetic: dmg_dealt x 0.001/0.0055, dmg_taken x (1.0 x 0.001)/(0.8 x 0.0055), win_part x 0.6/0.33, frag and
                     death unchanged (the same frames, priced anew)
  smoke   2.0a's command made small (2 simulators, 8 matches, 96 frames, the CPU, --overlap as the run), from S1 with its optimizer, the END dials
          from update 0, 10 updates (about 30 minutes): no NaN; the ledger carries the floor (dmg_dealt a player-minute under 0.6 x frags'); the
          win part's size share above the damage's; the save loads with its optimizer for one more update (no cold start); a one-map check of the
          save against S0 finishes
  live    the real trainer with start.ps1's live.json: applied before the first rollout; DMG_REWARD 0.003, DMG_TAKEN_W 0.9, WIN_ADD 0.5 written
          after update 1 are in live_applied.json by the end (from_update at most 4) and the ledger's dmg_dealt per frag falls against update 1's
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
    python docs/runs/2.0/2.0a/tests.py start|ident|smoke|live"""
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
ST = os.path.join(ROOT, "data", "sim_runs", "scratch_20a_start")
S1 = os.path.join(ST, "s1.pt")                           # S0 widened to today's 994 inputs with zero weights (tools/b17b_init.py widen-league)
CMD = os.path.join(HERE, "train.cmd")
OK = [True]
TAG = os.environ.get("TEST_TAG", "")                     # (a re-run: new scratch folders beside the old, nothing deleted)
END_DIALS = dict(DMG_REWARD=0.001, DMG_TAKEN_W=1.0, WIN_ADD=0.6)
START_DIALS = dict(DMG_REWARD=0.0055, DMG_TAKEN_W=0.8, WIN_ADD=0.33)


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
    """a small CPU copy of 2.0a's train.cmd: sets (NAME, VALUE) replace its set lines, args (flag, value) its arguments"""
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
    assert not any(("duel_gru_1_" in x or "duel_gru_2_" in x) for x in live_), "a real run's name is left in the small command"
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    if os.path.exists(os.path.join(HERE, "aim2_env.cmd")) and not os.path.exists(os.path.join(D, "aim2_env.cmd")):
        shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))   # (the command calls it beside itself: the aim settings)
    return cmd


def start_live(D):
    """start.ps1's live.json (start_live.py: the save's own live values with 2.0a's start values)"""
    out = os.path.join(D, "live.json")
    subprocess.check_call([PY, os.path.join(HERE, "start_live.py"), S0, os.path.join(R7A, "live.json"), out], env=cenv(), stdout=subprocess.DEVNULL)
    return json.load(open(out, encoding="utf-8"))


def lay_out(run, live_extra=None):
    """a scratch run folder: S1 and S0's optimizer, two of 1.7a's anchors and S0 as a snapshot, 1.7a's live settings, the start's live.json"""
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


def pm(m):
    return ((m.get("pay_terms") or {}).get("per_player_min") or {})


def ident():
    import torch
    arms = [("z0", None), ("z0b", None), ("z2", dict(END_DIALS))]
    acts, mets = {}, {}
    for name, lv in arms:
        run = "scratch_20a_id_" + name + TAG
        D = lay_out(run, live_extra=lv)
        log = trainer(make_cmd(run, D, 30, ident=True), run, 60)
        dumps = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(dumps), "" if log else ", NO LOG"), log is not None and len(dumps) >= 2)
        acts[name] = [torch.load(f, map_location="cpu") for f in dumps[:2]]
        mets[name] = metrics(D)
        if log:
            check("{}: the optimizer's state loaded from opt.pt, not a cold start; its moments carried over the widened inputs".format(name),
                  "optimizer: its state loaded from opt.pt" in log and "cold start" not in log and "optimizer: enc.0.weight carried over" in log)
            check("{}: no weapon table, no REFUSED live file".format(name), "the pros' weapon table (1.7c)" not in log and "REFUSED" not in log)
    if not all(len(acts.get(n, [])) >= 2 for n, _ in arms):
        check("every arm dumped its updates", False)
        return done()

    def same(x, y, k, u):
        a_, b_ = acts[x][u][k], acts[y][u][k]
        return a_.shape == b_.shape and bool(torch.equal(a_, b_))

    check("the trainer repeats itself at a fixed seed (z0 = z0b, both updates, actions and log p)", all(same("z0", "z0b", k, u) for k in ("act", "logp") for u in (0, 1)))
    check("the END dials change nothing before the first learning step (z2 = z0: update 1's actions and log p, to the bit)",
          all(same("z2", "z0", k, 0) for k in ("act", "logp")))
    d2 = float((acts["z2"][1]["act"] != acts["z0"][1]["act"]).float().mean())
    check("... and update 2's actions differ ({:.4f} of them): the pay reached the learning step".format(d2), d2 > 0)
    p0, p2 = pm(mets["z0"][0]) if mets["z0"] else {}, pm(mets["z2"][0]) if mets["z2"] else {}
    say("update 1's ledger z0: {}".format({k_: p0.get(k_) for k_ in ("dmg_dealt", "dmg_taken", "frag", "death", "win_part")}))
    say("update 1's ledger z2: {}".format({k_: p2.get(k_) for k_ in ("dmg_dealt", "dmg_taken", "frag", "death", "win_part")}))

    def ratio(k):
        a_, b_ = p0.get(k), p2.get(k)
        if not a_ and not b_:                                # (a term absent or zero on both sides, a tiny run without a death: unchanged)
            return 1.0
        return (b_ / a_) if (a_ not in (None, 0) and b_ is not None) else float("nan")

    def near(x, y, tol=0.02):
        return math.isfinite(x) and abs(x - y) <= tol * max(1.0, abs(y))

    check("update 1's damage dealt pays 0.001/0.0055 of z0's ({:.4f}, wanted {:.4f})".format(ratio("dmg_dealt"), 0.001 / 0.0055), near(ratio("dmg_dealt"), 0.001 / 0.0055))
    check("update 1's damage taken pays (1.0 x 0.001)/(0.8 x 0.0055) of z0's ({:.4f}, wanted {:.4f})".format(ratio("dmg_taken"), 0.001 / (0.8 * 0.0055)),
          near(ratio("dmg_taken"), 0.001 / (0.8 * 0.0055)))
    check("update 1's win part pays 0.6/0.33 of z0's ({:.4f}, wanted {:.4f})".format(ratio("win_part"), 0.6 / 0.33), near(ratio("win_part"), 0.6 / 0.33))
    check("update 1's frags and deaths unchanged ({}, {})".format(ratio("frag"), ratio("death")), near(ratio("frag"), 1.0, 1e-6) and near(ratio("death"), 1.0, 1e-6))
    return done()


def smoke():
    import torch
    run = "scratch_20a_smoke" + TAG
    D = lay_out(run, live_extra=dict(END_DIALS))
    c_ = make_cmd(run, D, 30000)                             # (--minutes counts the resumed run's minutes: --max-updates ends it)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 10")
    open(c_, "w", encoding="ascii", newline="").write(t_)
    log = trainer(c_, run, 60)
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
        say("update {}: dmg {} / {} frag {} death {} win {} (share {}) | frags a match-minute {} | keep {}".format(
            m["update"], p_.get("dmg_dealt"), p_.get("dmg_taken"), p_.get("frag"), p_.get("death"), p_.get("win_part"),
            ((m.get("pay_terms") or {}).get("size_share") or {}).get("win_part"), m.get("frags_per_match_min"), {k_: (m.get("keep") or {}).get(k_) for k_ in ("g", "kl")}))
    P_ = [pm(m) for m in M if pm(m)]
    check("the ledger on every update", len(P_) == len(M))
    check("the damage pay carries the floor: dmg_dealt under 0.6 x frags' pay on every update with frags",
          P_ and all((p_.get("dmg_dealt") or 0) < 0.6 * (p_.get("frag") or 0) for p_ in P_ if (p_.get("frag") or 0) > 0.2))
    S_ = [((m.get("pay_terms") or {}).get("size_share") or {}) for m in M]
    check("the win part's size share above the damage dealt's on every update", S_ and all((s_.get("win_part") or 0) > (s_.get("dmg_dealt") or 0) for s_ in S_))
    hd = [m.get("head2") or {} for m in M]
    check("no NaN in the head's lessons or the trainer's kl and entropy",
          all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd) and
          all(math.isfinite(float(m.get("kl") or 0.0)) and math.isfinite(float(m.get("entropy") or 0.0)) for m in M))
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    check("the save carries no wrule", not ck.get("wrule"))
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
           "--opp-round", "600"]
    cmd += [x for s_ in P.settings(0.0, os.path.join(D, "policy.pt")) for x in ("--set", s_)]
    r = subprocess.run(cmd, cwd=ROOT, env=cenv(), capture_output=True, text=True)
    jv = json.load(open(js)) if os.path.exists(js) else {}
    v = (jv.get("maps") or {}).get("bloodrun") or {}
    say("check: exit {}; {}".format(r.returncode, (r.stdout + r.stderr)[-600:]))
    check("a one-map check of the save against S0 finished ({}-{})".format(v.get("won"), v.get("lost")), r.returncode == 0 and "won" in v)
    return done()


def live():
    run = "scratch_20a_live" + TAG
    D = lay_out(run)
    lv0 = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    check("the start's live.json carries the save's values ({})".format({k_: lv0.get(k_) for k_ in START_DIALS}), all(lv0.get(k_) == v_ for k_, v_ in START_DIALS.items()))
    c_ = make_cmd(run, D, 30000)                             # (--minutes counts the resumed run's minutes, 24,886 at update 90: --max-updates ends it)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 5")   # (a dial written after
    open(c_, "w", encoding="ascii", newline="").write(t_)                                                                              # update 1 is played by 4)
    MID = dict(DMG_REWARD=0.003, DMG_TAKEN_W=0.9, WIN_ADD=0.5)
    tr = subprocess.Popen(["cmd.exe", "/c", c_], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"))
    MET, wrote, t0 = os.path.join(D, "metrics.jsonl"), False, time.time()
    while tr.poll() is None and time.time() - t0 < 40 * 60:
        time.sleep(5)
        if not wrote and os.path.exists(MET) and os.path.getsize(MET) > 0:
            lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
            lv.update(MID)
            json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
            wrote = True
            say("after update 1: live.json {}".format(MID))
    if tr.poll() is None:
        say("the trainer still runs after 40 min: left running")
        return done()
    log = open(os.path.join(ROOT, "data", "sim_runs", run + ".log"), encoding="utf-8", errors="replace").read()
    st = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_status.json")) else {}
    ap = json.load(open(os.path.join(D, "live_applied.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_applied.json")) else {}
    M = metrics(D)
    check("no refusal in the log", "REFUSED" not in log)
    check("live_status.json says applied ({})".format(st), st.get("status") == "applied")
    check("3 updates or more ({})".format(len(M)), len(M) >= 3)
    for m in M:
        p_ = pm(m)
        say("update {}: dmg {} / {} frag {} death {} win {}".format(m["update"], p_.get("dmg_dealt"), p_.get("dmg_taken"), p_.get("frag"), p_.get("death"), p_.get("win_part")))
    got = {k_: (ap.get("file") or {}).get(k_) for k_ in MID}
    check("live_applied.json carries the mid values by the end ({}, from update {})".format(got, ap.get("from_update")),
          all(got.get(k_) == v_ for k_, v_ in MID.items()) and (ap.get("from_update") or 99) <= 4)
    r0 = (pm(M[0]).get("dmg_dealt") or 0) / max(1e-9, pm(M[0]).get("frag") or 1e-9) if M else float("nan")
    r1 = (pm(M[-1]).get("dmg_dealt") or 0) / max(1e-9, pm(M[-1]).get("frag") or 1e-9) if M else float("nan")
    check("the ledger's damage dealt per frag fell from update 1 to the last ({:.3f} -> {:.3f})".format(r0, r1), M and r1 < r0)
    return done()


if __name__ == "__main__":
    sys.exit({"start": start, "ident": ident, "smoke": smoke, "live": live}[sys.argv[1]]())
