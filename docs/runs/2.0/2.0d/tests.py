"""2.0d's tests (docs/runs/2.0/2.0d/CARD.md "Before the go" 7); 2.0c's tests with 2.0d's start and dials. Nothing of a real run is touched:
scratch run folders only (data/sim_runs/scratch_20d_*), nothing deleted. CPU only, below normal; no run trains meanwhile. S0 = 1.7a's update 90
(keep/policy_u90_17a.pt, opt_u90_17a.pt); S1 = S0 brought to list 20d (tools/inputs20d.py convert, the sample data/sim_runs/inputs20d).

  start   S1 answers as S0 (inputs20d same: 0 actions differ with the brain's rounding off); S1's shape: 821 inputs, the hands 813, the
          dodge columns and token at zero, the token and the order's shut, the head's 79 columns
  ident   the trainer at a fixed seed (--seed 7, --max-updates 2, --dump-acts), 2 simulators x 8 matches x 96 frames, 2.0d's command made
          small, on S1 with converted anchors:
            z0, z0b  the start's live.json: it repeats itself to the bit
            z3       the AIM3 dials at their END: update 1's actions DIFFER from z0's (the dials reach the simulators)
            zg       DODGE_G 1: update 1's actions DIFFER from z0's (the token, opened, is in the attention); its gate log(1) = 0 in the metrics
  smoke   2.0d's command made small, from S1 with its optimizer, ALL the END dials from update 0, 10 updates: no NaN; the ledger
          zero-sum; the dodge gate in the metrics; the encoder's dodge columns learn (not zero after); the save loads with its optimizer
          for one more update; a one-map check of the save against S0 finishes
  live    the real trainer with start.ps1's live.json: applied before the first rollout; mid values of the dials written after update 1
          are in live_applied.json by the end, in the save's record, and the dodge token's gate is log(0.5) in the metrics
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
    python docs/runs/2.0/2.0d/tests.py start|ident|smoke|live"""
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
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
R7A = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a")
S0, S0O = os.path.join(R7A, "keep", "policy_u90_17a.pt"), os.path.join(R7A, "keep", "opt_u90_17a.pt")
ANCH = os.path.join(R7A, "snapshots")                     # 1.7a's anchors (990 inputs)
SAMPLE = os.path.join(ROOT, "data", "sim_runs", "inputs20d", "sample_obs.npy")
TAG = os.environ.get("TEST_TAG", "")                     # (a re-run: new scratch folders beside the old, nothing deleted)
ST = os.path.join(ROOT, "data", "sim_runs", "scratch_20d_start" + TAG)
S1, S1O = os.path.join(ST, "s1.pt"), os.path.join(ST, "s1_opt.pt")
CMD = os.path.join(HERE, "train.cmd")
OK = [True]
AIM_END = dict(AIM3_W=1.0, AIM3_SIZE_A=0.39, AIM3_SIZE_B=0.355, AIM3_LEAD=1.0, AIM3_RELOAD=0.0)
START = dict(DMG_REWARD=0.005, DMG_TAKEN_W=1.0, RAIL_FAR_PAY=0.1, KEEP_G=1.0, HABIT_P=0.0, WIN_ADD=0.33, AIM3_W=0.0, AIM3_SIZE_A=1.0,
             AIM3_SIZE_B=0.0, AIM3_LEAD=0.0, AIM3_RELOAD=1.0, DODGE_G=0.0)


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


def conv(src, dst, league=False, opt=None):
    if not os.path.exists(dst):
        cmd = [PY, os.path.join(ROOT, "tools", "inputs20d.py"), "convert", src, dst, "--sample", SAMPLE] + (["--league"] if league else []) + \
            (["--opt", opt[0], opt[1]] if opt else [])
        r = subprocess.run(cmd, env=cenv(), capture_output=True, text=True, creationflags=NOWIN)
        print(r.stdout[-3000:] + r.stderr[-2000:], flush=True)
        assert r.returncode == 0, "inputs20d convert failed: " + src


def start():
    import torch
    os.makedirs(ST, exist_ok=True)
    conv(S0, S1, opt=(S0O, S1O))
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "inputs20d.py"), "same", S0, S1, "--sample", SAMPLE], env=cenv(), capture_output=True,
                       text=True, creationflags=NOWIN)
    print(r.stdout + r.stderr[-2000:], flush=True)
    check("inputs20d same: S1 answers as 1.7a's update 90", r.returncode == 0)
    g_ = torch.load(S1, map_location="cpu", weights_only=False)
    sd_ = g_["model"]
    gate_, r_ = {}, 0
    for k_ in g_["attn"]["kinds"]:
        gg_ = sd_["attn.gate"][r_:r_ + len(k_["idx"])]
        r_ += len(k_["idx"])
        if float(gg_.min()) < 0:
            gate_[k_["name"]] = float(gg_.min())
    check("the shut tokens are the order and the dodge, at -30 ({})".format(gate_), gate_ == {"order": -30.0, "dodge": -30.0})
    I = g_.get("inputs") or {}
    check("list 20d: {} inputs, the hands {}, the brain {}".format(I.get("n"), I.get("n_hands"), I.get("n_brain")),
          (I.get("n"), I.get("n_hands"), I.get("n_brain")) == (821, 813, 691) and sd_["enc.0.weight"].shape[1] == 813)
    d0, d1 = I.get("dodge") or (0, 0)
    ki = [i_ for i_, k_ in enumerate(g_["attn"]["kinds"]) if k_["name"] == "dodge"]
    check("the dodge columns {}..{} at zero weights in the encoder and the token".format(d0, d1 - 1),
          (d0, d1) == (806, 813) and float(sd_["enc.0.weight"][:, d0:d1].abs().max()) == 0.0 and len(ki) == 1 and
          float(sd_["attn.emb.{}.weight".format(ki[0])].abs().max()) == 0.0)
    check("the head's 79 columns, its weapon part's 45", len(g_["head2"]["obs_cols"]) == 79 and sd_["head2.inp.weight"].shape[1] == 948 and
          len(g_["head2"]["wobs_cols"]) == 45)
    ev_ = g_.get("env_vars") or {}
    check("the file plays at DODGE_G 0 with DODGE_IN 1 ({})".format({k_: ev_.get(k_) for k_ in ("DODGE_IN", "DODGE_G")}),
          ev_.get("DODGE_IN") == "1" and ev_.get("DODGE_G") == "0")
    o_ = torch.load(S1O, map_location="cpu", weights_only=False)
    check("the optimizer converted ({} moments)".format(len(o_["state"])), len(o_["state"]) > 0)
    return done()


def make_cmd(run, D, minutes, ident=False, sets=(), args=()):
    """a small CPU copy of 2.0d's train.cmd: sets (NAME, VALUE) replace its set lines, args (flag, value) its arguments"""
    if not os.path.exists(CMD):
        subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "720"])
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


def start_live(D):
    out = os.path.join(D, "live.json")
    subprocess.check_call([PY, os.path.join(HERE, "start_live.py"), S0, os.path.join(R7A, "live.json"), out], env=cenv(), stdout=subprocess.DEVNULL,
                          creationflags=NOWIN)
    return json.load(open(out, encoding="utf-8"))


def lay_out(run, live_extra=None):
    """a scratch run folder: S1 and its converted optimizer, two of 1.7a's anchors and S0 as a snapshot (list 20d), 1.7a's live settings,
    the start's live.json"""
    D = os.path.join(ROOT, "data", "sim_runs", run)
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (look at it first; nothing deleted)")
    if not os.path.exists(S1):
        raise SystemExit("no converted start: run `start` first")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(S1, os.path.join(D, "policy.pt"))
    shutil.copy2(S1O, os.path.join(D, "opt.pt"))
    for name, p_ in (("anchor_16a.pt", os.path.join(ANCH, "anchor_16a.pt")), ("anchor_b12d.pt", os.path.join(ANCH, "anchor_b12d.pt")), ("snap_0001.pt", S0)):
        w_ = os.path.join(ST, "w_" + name)
        conv(p_, w_, league=True)
        shutil.copy2(w_, os.path.join(D, "snapshots", name))
    shutil.copy2(os.path.join(R7A, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = start_live(D)
    lv.update(**(live_extra or {}))
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    return D


def trainer(cmd, run, limit_min):
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"), creationflags=NOWIN)
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
    arms = [("z0", None), ("z0b", None), ("z3", dict(AIM_END)), ("zg", dict(DODGE_G=1.0))]
    acts, mets = {}, {}
    for name, lv in arms:
        run = "scratch_20d_id_" + name + TAG
        D = lay_out(run, live_extra=lv)
        log = trainer(make_cmd(run, D, 30, ident=True), run, 60)
        dumps = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(dumps), "" if log else ", NO LOG"), log is not None and len(dumps) >= 2)
        acts[name] = [torch.load(f, map_location="cpu") for f in dumps[:2]]
        mets[name] = metrics(D)
        if log:
            check("{}: the optimizer's state loaded, not a cold start; the dodge token's first layer fresh, the encoder carried over".format(name),
                  "optimizer: its state loaded from opt.pt" in log and "cold start" not in log and "first layer starts fresh" in log
                  and "optimizer: enc.0.weight carried over" in log)
            check("{}: the dodge token found, no REFUSED live file, no opening of the other gates".format(name),
                  "the dodge token (2.0d)" in log and "REFUSED" not in log and "open from" not in log)
    if not all(len(acts.get(n, [])) >= 2 for n, _ in arms):
        check("every arm dumped its updates", False)
        return done()

    def same(x, y, k, u):
        a_, b_ = acts[x][u][k], acts[y][u][k]
        return a_.shape == b_.shape and bool(torch.equal(a_, b_))

    check("the trainer repeats itself at a fixed seed (z0 = z0b, both updates, actions and log p)",
          all(same("z0", "z0b", k, u) for k in ("act", "logp") for u in (0, 1)))
    d3 = float((acts["z3"][0]["act"] != acts["z0"][0]["act"]).float().mean())
    check("the END AIM dials reach the simulators: update 1's actions differ from z0's ({:.4f} of them)".format(d3), d3 > 0)
    dg = float((acts["zg"][0]["act"] != acts["z0"][0]["act"]).float().mean())
    check("DODGE_G 1 reaches the network (the token in the attention): update 1's actions differ from z0's ({:.4f} of them)".format(dg), dg > 0)
    g0 = [(m.get("dodge_gate") or {}) for m in mets["z0"]]
    g1 = [(m.get("dodge_gate") or {}) for m in mets["zg"]]
    check("the metrics' dodge gate: z0 columns 0 token -30, zg columns 1 token 0 ({} / {})".format(g0[:1], g1[:1]),
          bool(g0 and g1) and g0[0].get("cols") == 0.0 and g0[0].get("token") == -30.0 and g1[0].get("cols") == 1.0 and g1[0].get("token") == 0.0)
    return done()


def smoke():
    import torch
    run = "scratch_20d_smoke" + TAG
    D = lay_out(run, live_extra=dict(AIM_END, DODGE_G=1.0))
    c_ = make_cmd(run, D, 30000)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 10")
    open(c_, "w", encoding="ascii", newline="").write(t_)
    log = trainer(c_, run, 90)
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    check("on the CPU", "device cpu" in log)
    check("the optimizer's state loaded from S1's opt.pt", "optimizer: its state loaded from opt.pt" in log)
    check("the keep choice not frozen, no REFUSED", "keep choice FROZEN" not in log and "REFUSED" not in log)
    M = metrics(D)
    check("8 or more updates ({})".format(len(M)), len(M) >= 8)
    for m in M:
        p_ = pm(m)
        say("update {}: dmg {} / {} frag {} death {} win {} | frags a match-minute {} | keep {} | dodge gate {}".format(
            m["update"], p_.get("dmg_dealt"), p_.get("dmg_taken"), p_.get("frag"), p_.get("death"), p_.get("win_part"),
            m.get("frags_per_match_min"), {k_: (m.get("keep") or {}).get(k_) for k_ in ("g", "kl")}, m.get("dodge_gate")))
    P_ = [pm(m) for m in M if pm(m)]
    check("the ledger on every update", len(P_) == len(M))
    check("damage taken weighs as dealt (zero-sum): the two cancel within 15% over the run",
          bool(P_) and abs(sum(p_.get("dmg_dealt") or 0 for p_ in P_) + sum(p_.get("dmg_taken") or 0 for p_ in P_)) <
          0.15 * sum(p_.get("dmg_dealt") or 0 for p_ in P_))
    check("the dodge gate on every update, open", all((m.get("dodge_gate") or {}).get("cols") == 1.0 and (m.get("dodge_gate") or {}).get("token") == 0.0 for m in M))
    hd = [m.get("head2") or {} for m in M]
    check("no NaN in the head's lessons or the trainer's kl and entropy",
          all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd) and
          all(math.isfinite(float(m.get("kl") or 0.0)) and math.isfinite(float(m.get("entropy") or 0.0)) for m in M))
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    d0, d1 = ck["inputs"]["dodge"]
    wn = float(ck["model"]["enc.0.weight"][:, d0:d1].abs().max())
    check("the encoder's dodge columns learnt (largest weight {:.2e}, from 0)".format(wn), wn > 0)
    n0 = len(M)
    t2 = make_cmd(run, D, 30000)
    t_ = open(t2, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 1")
    open(t2, "w", encoding="ascii", newline="").write(t_)
    log2 = trainer(t2, run, 20)
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
    r = subprocess.run(cmd, cwd=ROOT, env=cenv(), capture_output=True, text=True, creationflags=NOWIN)
    jv = json.load(open(js)) if os.path.exists(js) else {}
    v = (jv.get("maps") or {}).get("bloodrun") or {}
    say("check: exit {}; {}".format(r.returncode, (r.stdout + r.stderr)[-600:]))
    check("a one-map check of the save against S0 finished ({}-{})".format(v.get("won"), v.get("lost")), r.returncode == 0 and "won" in v)
    return done()


def live():
    import torch
    run = "scratch_20d_live" + TAG
    D = lay_out(run)
    lv0 = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    check("the start's live.json carries 2.0d's start ({})".format({k_: lv0.get(k_) for k_ in START}), all(lv0.get(k_) == v_ for k_, v_ in START.items()))
    c_ = make_cmd(run, D, 30000)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 5")
    open(c_, "w", encoding="ascii", newline="").write(t_)
    MID = dict(AIM3_W=0.5, AIM3_SIZE_A=0.7, AIM3_SIZE_B=0.18, AIM3_LEAD=0.5, AIM3_RELOAD=0.5, DODGE_G=0.5)
    tr = subprocess.Popen(["cmd.exe", "/c", c_], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"), creationflags=NOWIN)
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
    got = {k_: (ap.get("file") or {}).get(k_) for k_ in MID}
    check("live_applied.json carries the mid values by the end ({}, from update {})".format(got, ap.get("from_update")),
          all(got.get(k_) == v_ for k_, v_ in MID.items()) and (ap.get("from_update") or 99) <= 4)
    sim_ = ((torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False).get("live") or {}).get("sim") or {})
    check("the save's record of what the SIMULATORS played carries the mid values ({})".format({k_: sim_.get(k_) for k_ in MID}),
          all(sim_.get(k_) is not None and abs(float(sim_[k_]) - v_) < 1e-9 for k_, v_ in MID.items()))
    gl = (M[-1].get("dodge_gate") or {}) if M else {}
    check("the last update's dodge gate: columns 0.5, token log(0.5) ({})".format(gl),
          gl.get("cols") == 0.5 and abs((gl.get("token") or 0) - math.log(0.5)) < 1e-3)
    return done()


if __name__ == "__main__":
    sys.exit({"start": start, "ident": ident, "smoke": smoke, "live": live}[sys.argv[1]]())
