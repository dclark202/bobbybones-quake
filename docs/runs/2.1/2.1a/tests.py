"""2.1a's tests (the blend, owner 2026-11-13; docs/runs/2.1/2.1a/CARD.md "Before the go"); 2.0d's tests with the instruction's parts and
the frozen decisions. Nothing of a real run is touched: scratch run folders only (data/sim_runs/scratch_21a_*), nothing deleted. CPU only,
below normal; no run trains meanwhile. S0 = 1.7a's update 90 (keep/policy_u90_17a.pt, opt_u90_17a.pt); S1 = S0 brought to list 20d
(tools/inputs20d.py, with the optimizer), to list 21d (tools/inputs21.py --old 20d --new 21d) and given the head's instruction part
(tools/head21_init.py add).

  start   each step answers as the one before (inputs20d same, inputs21 same, head21_init same); S1's shape: 869 inputs, the hands 861, the
          tokens order, dodge and instr shut, the head's part "ins" at zero, its share 0
  ident   the trainer at a fixed seed (--seed 7, --max-updates 2, --dump-acts), 2 simulators x 8 matches x 96 frames, 2.1a's command made
          small, on S1 with converted anchors:
            z0, z0b  the start's live.json: it repeats itself to the bit
            z3       AIM3's END dials: update 1's actions differ from z0's
            zi       DODGE_G 1 and the instruction's silent parts at their ends (frozen moments, drills, the token): update 1's actions differ
          and in every arm: the frozen decisions' weights (his target's rows and the head's target scores, the weapon key's rows and the head's
          weapon scores, the keep choice) the same to the bit after two updates of learning
  smoke   2.1a's command made small, from S1, ALL the END dials from update 0, 10 updates: no NaN; the ledger zero-sum; the dodge gate and the
          frozen record on every update; drills, frozen moments and the instruction's records there; the frozen weights the same to the bit
          after 10 updates; the save loads with its optimizer for one more update; a one-map check of the save against S0 finishes
  live    the real trainer with start.ps1's live.json: applied before the first rollout; mid values of every dial written after update 1 are
          in live_applied.json by the end, in the save's record, and the dodge token's gate is log(0.5)
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
    python docs/runs/2.1/2.1a/tests.py start|ident|smoke|live"""
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
ANCH = os.path.join(R7A, "snapshots")
SAMPLE = os.path.join(ROOT, "data", "sim_runs", "inputs20d", "sample_obs.npy")
MS = os.path.join(ROOT, "data", "sim_runs", "space", "mapsense_start.pt")
TAG = os.environ.get("TEST_TAG", "")
ST = os.path.join(ROOT, "data", "sim_runs", "scratch_21a_t")   # (the converted start, shared by every tag)
A20, O20, A21, S1 = (os.path.join(ST, f_) for f_ in ("a20.pt", "a20_opt.pt", "a21.pt", "s1.pt"))
CMD = os.path.join(HERE, "train.cmd")
OK = [True]
AIM_END = dict(AIM3_W=1.0, AIM3_SIZE_A=0.39, AIM3_SIZE_B=0.355, AIM3_LEAD=1.0, AIM3_RELOAD=0.0)
INS_END = dict(DODGE_G=1.0, BRANCH_P=0.15, DRILL_INS_P=0.25, DRILL_INS_RATE=0.02, INS_GATE=0.0, BRANCH_WPN_P=0.3)
START = dict(DMG_REWARD=0.005, DMG_TAKEN_W=1.0, RAIL_FAR_PAY=0.1, KEEP_G=1.0, HABIT_P=0.0, WIN_ADD=0.33, AIM3_W=0.0, AIM3_SIZE_A=1.0,
             AIM3_SIZE_B=0.0, AIM3_LEAD=0.0, AIM3_RELOAD=1.0, DODGE_G=0.0, BRANCH_P=0.0, DRILL_INS_P=0.0, DRILL_INS_RATE=0.0, INS_GATE=-30.0,
             INS_G=0.0, BRANCH_WPN_P=0.0, H2_INS_PG=0.0)
FROZEN_HEAD2 = ("head2.target.", "head2.wsc.", "head2.keep.")


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def check(name, cond):
    OK[0] = OK[0] and bool(cond)
    say(("PASS " if cond else "FAIL ") + name)


def cenv(**kw):
    return dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", **kw)


def done():
    say("ALL PASSED" if OK[0] else "FAILED")
    return 0 if OK[0] else 1


def tool(*args):
    r = subprocess.run([PY] + [str(x) for x in args], env=cenv(INSTR="1", INS_WAY="1"), capture_output=True, text=True, creationflags=NOWIN, cwd=ROOT)
    print(r.stdout[-2500:] + r.stderr[-1500:], flush=True)
    return r.returncode


def conv_league(src, dst):
    """a league file: list 20d, list 21d, and (with a head) the head widened to the learner's"""
    if os.path.exists(dst):
        return
    b20, b21 = dst + ".20d.pt", dst + ".21d.pt"
    assert tool("tools/inputs20d.py", "convert", src, b20, "--sample", SAMPLE, "--league") == 0
    assert tool("tools/inputs21.py", "--old", "20d", "--new", "21d", "convert", b20, b21) == 0
    import torch
    if torch.load(b21, map_location="cpu", weights_only=False).get("head2"):
        assert tool("tools/head21_init.py", "widen-league", b21, dst) == 0
    else:
        shutil.copy2(b21, dst)


def frozen(path):
    """the frozen decisions' weights of a save: the pi rows of his target and the weapon key, the head's target, weapon and keep layers"""
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=False)
    sd, ad = ck["model"], list(ck["action_dims"])
    ih, hh = len(ad) - 1, 6                                   # (the trainer: I_HEAD the last output, HAND_HEAD 6)
    oi, oh = sum(ad[:ih]), sum(ad[:hh])
    out = {"pi.w.target": sd["pi.weight"][oi:oi + ad[ih]], "pi.b.target": sd["pi.bias"][oi:oi + ad[ih]],
           "pi.w.weapon": sd["pi.weight"][oh:oh + ad[hh]], "pi.b.weapon": sd["pi.bias"][oh:oh + ad[hh]]}
    out.update({k_: v_ for k_, v_ in sd.items() if k_.startswith(FROZEN_HEAD2)})
    return out


def same_frozen(a, b):
    import torch
    fa, fb = frozen(a), frozen(b)
    bad = [k_ for k_ in fa if k_ not in fb or fa[k_].shape != fb[k_].shape or not torch.equal(fa[k_], fb[k_])]
    return not bad and len(fa) >= 8, bad, sorted(fa)


def start():
    import torch
    os.makedirs(ST, exist_ok=True)
    if not os.path.exists(S1):
        assert tool("tools/inputs20d.py", "convert", S0, A20, "--sample", SAMPLE, "--opt", S0O, O20) == 0
        assert tool("tools/inputs21.py", "--old", "20d", "--new", "21d", "convert", A20, A21) == 0
        assert tool("tools/head21_init.py", "add", A21, S1) == 0
    check("inputs20d same: list 20d answers as 1.7a's update 90", tool("tools/inputs20d.py", "same", S0, A20, "--sample", SAMPLE) == 0)
    check("inputs21 same: list 21d answers as list 20d", tool("tools/inputs21.py", "--old", "20d", "--new", "21d", "same", A20, A21, "--sample", SAMPLE) == 0)
    check("head21_init same: the head's instruction part at zero effect", tool("tools/head21_init.py", "same", A21, S1, "--sample", SAMPLE) == 0)
    g_ = torch.load(S1, map_location="cpu", weights_only=False)
    sd_ = g_["model"]
    gate_, r_ = {}, 0
    for k_ in g_["attn"]["kinds"]:
        gg_ = sd_["attn.gate"][r_:r_ + len(k_["idx"])]
        r_ += len(k_["idx"])
        if float(gg_.min()) < 0:
            gate_[k_["name"]] = float(gg_.min())
    check("the shut tokens: the order, the dodge, the instruction, at -30 ({})".format(gate_), gate_ == {"order": -30.0, "dodge": -30.0, "instr": -30.0})
    I = g_.get("inputs") or {}
    check("list 21d: {} inputs, the hands {}, the brain {}; the dodge columns kept ({})".format(I.get("n"), I.get("n_hands"), I.get("n_brain"), I.get("dodge")),
          (I.get("n"), I.get("n_hands"), I.get("n_brain")) == (869, 861, 691) and sd_["enc.0.weight"].shape[1] == 861 and I.get("dodge") == [806, 813])
    check("the instruction's 48 columns and the dodge's 7 at zero in the encoder", float(sd_["enc.0.weight"][:, 806:861].abs().max()) == 0.0)
    check("the head's part 'ins' at zero, its share 0", g_.get("ins") is not None and float(sd_["head2.ins_g"]) == 0.0)
    check("the env module duel_env_ffa21d", g_.get("env_module") == "duel_env_ffa21d")
    for n_ in ("anchor_16a.pt", "anchor_b12d.pt"):
        conv_league(os.path.join(ANCH, n_), os.path.join(ST, "w_" + n_))
    conv_league(S0, os.path.join(ST, "w_snap_0001.pt"))
    check("three league files converted (two anchors and 1.7a's update 90)", all(os.path.exists(os.path.join(ST, "w_" + n_)) for n_ in ("anchor_16a.pt", "anchor_b12d.pt", "snap_0001.pt")))
    return done()


def make_cmd(run, D, minutes, ident=False):
    """a small CPU copy of 2.1a's train.cmd (the whole rollout of 384 steps: the map sense's horizon and the frozen moments need it)"""
    if not os.path.exists(CMD):
        subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "720"])
    t = open(CMD, encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(ROOT)),
            ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal "), ("--workers 30 ", "--workers 2 "),
            ("--matches 168 ", "--matches 8 "), ("--minibatches 360 ", "--minibatches 4 "),
            ("%ROOT%\\data\\sim_runs\\duel_gru_2_1a\\keep\\mapsense_start.pt", os.path.join(D, "keep", "mapsense_start.pt")),
            ("%LEARN% >> ", "--snapshot-min {} {} >> ".format(1000 if ident else 1, "--seed 7 --max-updates 2 --dump-acts " + os.path.join(D, "acts")
                                                               if ident else "--overlap 1 --learn-nosync 1"))]
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
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
    D = os.path.join(ROOT, "data", "sim_runs", run)
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (look at it first; nothing deleted)")
    if not os.path.exists(S1):
        raise SystemExit("no converted start: run `start` first")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(S1, os.path.join(D, "policy.pt"))
    shutil.copy2(O20, os.path.join(D, "opt.pt"))
    shutil.copy2(MS, os.path.join(D, "keep", "mapsense_start.pt"))
    for n_ in ("anchor_16a.pt", "anchor_b12d.pt", "snap_0001.pt"):
        shutil.copy2(os.path.join(ST, "w_" + n_), os.path.join(D, "snapshots", n_))
    shutil.copy2(os.path.join(R7A, "live_settings.env"), os.path.join(D, "live_settings.env"))
    out = os.path.join(D, "live.json")
    subprocess.check_call([PY, os.path.join(HERE, "start_live.py"), S0, os.path.join(R7A, "live.json"), out], env=cenv(), stdout=subprocess.DEVNULL, creationflags=NOWIN)
    lv = json.load(open(out, encoding="utf-8"))
    lv.update(**(live_extra or {}))
    json.dump(lv, open(out, "w", encoding="utf-8"))
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
    arms = [("z0", None), ("z0b", None), ("z3", dict(AIM_END)), ("zi", dict(INS_END))]
    acts = {}
    for name, lv in arms:
        run = "scratch_21a_id_" + name + TAG
        D = lay_out(run, live_extra=lv)
        log = trainer(make_cmd(run, D, 30, ident=True), run, 60)
        dumps = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(dumps), "" if log else ", NO LOG"), log is not None and len(dumps) >= 2)
        acts[name] = [torch.load(f, map_location="cpu") for f in dumps[:2]]
        if log:
            check("{}: the optimizer loaded, not cold; the new tokens fresh; --freeze-choice on; the dodge token found; no REFUSED".format(name),
                  "optimizer: its state loaded from opt.pt" in log and "cold start" not in log and "first layer starts fresh" in log
                  and "--freeze-choice (2.1a)" in log and "the dodge token (2.0d)" in log and "REFUSED" not in log)
            ok_, bad_, keys_ = same_frozen(S1, os.path.join(D, "policy.pt"))
            check("{}: the frozen decisions' weights the same to the bit after 2 updates ({} tensors; moved: {})".format(name, len(keys_), bad_), ok_)
    if not all(len(acts.get(n, [])) >= 2 for n, _ in arms):
        check("every arm dumped its updates", False)
        return done()

    def same(x, y, k, u):
        a_, b_ = acts[x][u][k], acts[y][u][k]
        return a_.shape == b_.shape and bool(torch.equal(a_, b_))

    check("the trainer repeats itself at a fixed seed (z0 = z0b, both updates, actions and log p)", all(same("z0", "z0b", k, u) for k in ("act", "logp") for u in (0, 1)))
    for nm_ in ("z3", "zi"):
        d_ = float((acts[nm_][0]["act"] != acts["z0"][0]["act"]).float().mean())
        check("{}'s dials reach play: update 1's actions differ from z0's ({:.4f} of them)".format(nm_, d_), d_ > 0)
    return done()


def smoke():
    run = "scratch_21a_smoke" + TAG
    D = lay_out(run, live_extra=dict(AIM_END, **INS_END))
    c_ = make_cmd(run, D, 30000)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 10")
    open(c_, "w", encoding="ascii", newline="").write(t_)
    log = trainer(c_, run, 120)
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    check("the optimizer's state loaded, no REFUSED", "optimizer: its state loaded from opt.pt" in log and "REFUSED" not in log)
    M = metrics(D)
    check("8 or more updates ({})".format(len(M)), len(M) >= 8)
    for m in M:
        p_ = pm(m)
        say("update {}: dmg {} / {} frag {} | frags a match-minute {} | dodge {} | branch {} | drill {}".format(
            m["update"], p_.get("dmg_dealt"), p_.get("dmg_taken"), p_.get("frag"), m.get("frags_per_match_min"), m.get("dodge_gate"),
            json.dumps(m.get("branch"), default=str)[:120], json.dumps(m.get("drill_ins"), default=str)[:120]))
    P_ = [pm(m) for m in M if pm(m)]
    check("damage taken weighs as dealt (zero-sum): within 15% over the run",
          bool(P_) and abs(sum(p_.get("dmg_dealt") or 0 for p_ in P_) + sum(p_.get("dmg_taken") or 0 for p_ in P_)) < 0.15 * sum(p_.get("dmg_dealt") or 0 for p_ in P_))
    check("the dodge gate open and the frozen record on every update",
          bool(M) and all((m.get("dodge_gate") or {}).get("cols") == 1.0 and m.get("frozen_choice") for m in M))
    fz_ = [m.get("frozen_choice") for m in M]
    check("the frozen record never moves", bool(fz_) and all(f_ == fz_[0] for f_ in fz_))
    check("the instruction's records: ins, branch, drill_ins there", any(m.get("ins") for m in M) and any(m.get("branch") for m in M) and any(m.get("drill_ins") for m in M))
    check("no NaN in the trainer's kl and entropy", bool(M) and all(math.isfinite(float(m.get("kl") or 0.0)) and math.isfinite(float(m.get("entropy") or 0.0)) for m in M))
    ok_, bad_, keys_ = same_frozen(S1, os.path.join(D, "policy.pt"))
    check("(after {} updates) the frozen decisions' weights the same to the bit ({} tensors; moved: {})".format(len(M), len(keys_), bad_), ok_ and len(M) >= 8)
    import torch
    sd0, sd1 = torch.load(S1, map_location="cpu", weights_only=False)["model"], torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)["model"]
    mv_ = [k_ for k_ in ("enc.0.weight", "gru.weight_hh", "head2.gru.weight_hh") if k_ in sd0 and not torch.equal(sd0[k_], sd1[k_])]
    check("the rest learns: the hands' encoder, his memory and the head's memory moved ({})".format(mv_), len(mv_) == 3)
    n0 = len(M)
    t2 = make_cmd(run, D, 30000)
    t_ = open(t2, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 1")
    open(t2, "w", encoding="ascii", newline="").write(t_)
    log2 = trainer(t2, run, 30)
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
           "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600", "--opp-round", "600"]
    cmd += [x for s_ in P.settings(0.0, os.path.join(D, "policy.pt")) for x in ("--set", s_)]
    r = subprocess.run(cmd, cwd=ROOT, env=cenv(), capture_output=True, text=True, creationflags=NOWIN)
    jv = json.load(open(js)) if os.path.exists(js) else {}
    v = (jv.get("maps") or {}).get("bloodrun") or {}
    say("check: exit {}; {}".format(r.returncode, (r.stdout + r.stderr)[-600:]))
    check("a one-map check of the save against S0 finished ({}-{})".format(v.get("won"), v.get("lost")), r.returncode == 0 and "won" in v)
    return done()


def live():
    import torch
    run = "scratch_21a_live" + TAG
    D = lay_out(run)
    lv0 = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    check("the start's live.json carries 2.1a's start ({})".format({k_: lv0.get(k_) for k_ in START}), all(lv0.get(k_) == v_ for k_, v_ in START.items()))
    c_ = make_cmd(run, D, 30000)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 5")
    open(c_, "w", encoding="ascii", newline="").write(t_)
    MID = dict(AIM3_W=0.5, AIM3_SIZE_A=0.7, AIM3_SIZE_B=0.18, AIM3_LEAD=0.5, AIM3_RELOAD=0.5, DODGE_G=0.5, BRANCH_P=0.075, DRILL_INS_P=0.125,
               DRILL_INS_RATE=0.01, INS_GATE=-6.0, BRANCH_WPN_P=0.15)
    tr = subprocess.Popen(["cmd.exe", "/c", c_], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"), creationflags=NOWIN)
    MET, wrote, t0 = os.path.join(D, "metrics.jsonl"), False, time.time()
    while tr.poll() is None and time.time() - t0 < 50 * 60:
        time.sleep(5)
        if not wrote and os.path.exists(MET) and os.path.getsize(MET) > 0:
            lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
            lv.update(MID)
            json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
            wrote = True
            say("after update 1: live.json {}".format(MID))
    if tr.poll() is None:
        say("the trainer still runs after 50 min: left running")
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
    rec_ = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False).get("live") or {}
    both_ = dict(rec_.get("sim") or {}, **(rec_.get("trainer") or {}))
    check("the save's record carries the mid values ({})".format({k_: both_.get(k_) for k_ in MID}),
          all(both_.get(k_) is not None and abs(float(both_[k_]) - v_) < 1e-9 for k_, v_ in MID.items()))
    gl = (M[-1].get("dodge_gate") or {}) if M else {}
    check("the last update's dodge gate: columns 0.5, token log(0.5) ({})".format(gl), gl.get("cols") == 0.5 and abs((gl.get("token") or 0) - math.log(0.5)) < 1e-3)
    return done()


if __name__ == "__main__":
    sys.exit({"start": start, "ident": ident, "smoke": smoke, "live": live}[sys.argv[1]]())
