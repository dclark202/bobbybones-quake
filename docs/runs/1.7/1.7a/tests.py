"""1.7a's tests (owner, 2026-11-05: "start with the code build for 1.7 ... Aim to have it ready to go today"; the tests on cores 14-17,
0x3C000, while 1.6a trains: "Be mindful of the 1.6a run, give it priority"). Run under the scratchpad's run17.cmd (those cores, below
normal, CPU only); every child inherits them. The start is 1.6a's end; until it exists 1.5a's end stands in (the same network: 1.6a
changed dials only). Nothing of a real run is touched: scratch run folders only (data/sim_runs/scratch_17a_* of the checkout that
plays: the main one for the code under 1.7a's, this worktree's own data folder, a plain copy of the maps, for 1.7a's), nothing deleted.

  start   S0 = the start (1.6a's end, or 1.5a's); S1k = S0 given the keep choice at share 0 (tools/keep_init.py add); S1 = S1k given
          every other part of the order (tools/order_init.py add, with the pros' fit order_fit.json when it is there; owner 11-05: "build
          1.7 CORRECTLY as one branch"); keep_init same S0 S1k and order_init same S0 S1: 0 actions differ at share 0; at share 1 their
          columns as the start says
  ident   the trainer at a fixed seed (--seed 7, --max-updates 2, --dump-acts; no --overlap), 2 simulators x 8 matches x 96 frames, 1.6a's
          command:
            base, base2  the code under 1.7a's (the main checkout: 1.6a's) on S0, twice: the trainer repeats itself to the bit
            a1           1.7's code on S0 given only the order's 10 inputs and token at zero (order_init widen-league: 1.7's simulator
                         always has them), the league widened so, COMBAT off: every action and log p of both updates the same as base
            a2           1.7's code on S1 with COMBAT=1, the keep choice and the order at share 0, the pointer's adds, the fire push and
                         its credit at 0, the order's token shut, the brain's pass lesson on (its own layers: it moves nothing else),
                         the league's files widened (order_init widen-league): both updates the same as base to the bit; the
                         optimizer's state loaded from S0's (1.6a's groups, the widened inputs carried over by --opt-small-items; the
                         keep choice's, the order's and the pass readout's added after the load), not a cold start
            a3           a2 with every share and add 1 and the token open: the actions differ from update 1 on
  smoke   1.7's command made small (2 simulators, 8 matches, 96 frames, the CPU, --overlap as the run), from S1 with S0's optimizer, the
          keep choice and the combat order at share 1 and the fire push at add 1 from update 0 (live KEEP_G, CMB_G, FADD 1), 1.6a's end
          dials, about 30 minutes: every update's keep record (its readings, about five a second in its seconds, the parts of its
          logit, arrivals) and order record (asked, every kind drawn and followed, arrivals, the fire scores growing), their steps
          finite, no NaN; the save carries them (layout keep 2, cmb 1, fire 1, shares 1); a restart from the save with its optimizer
          loads it (one more update, no cold start); a one-map check of the save against S0 finishes
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
    run17.cmd docs\\runs\\1.7\\1.7a\\tests.py start|ident|smoke"""
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
GH = os.path.dirname(ROOT)
MAIN = os.path.join(GH, "BobbyBones")
PY = sys.executable
BS = "\\"
R6A = os.path.join(MAIN, "data", "sim_runs", "duel_gru_1_6a")
R5A = os.path.join(MAIN, "data", "sim_runs", "duel_gru_1_5a")
if os.path.exists(os.path.join(R6A, "keep", "policy_end_16a.pt")):
    S0, S0O = os.path.join(R6A, "keep", "policy_end_16a.pt"), os.path.join(R6A, "keep", "opt_end_16a.pt")
else:                                                        # (1.6a trains: 1.5a's end stands in, the same network)
    S0, S0O = os.path.join(R5A, "keep", "policy_end_15a.pt"), os.path.join(R5A, "keep", "opt_end_15a.pt")
ANCH = os.path.join(R5A, "snapshots")
ST = os.path.join(ROOT, "data", "sim_runs", "scratch_17a_start_" + os.path.splitext(os.path.basename(S0))[0])   # (the starts made from this S0)
S1K, S1 = os.path.join(ST, "s1_keep.pt"), os.path.join(ST, "s1_order.pt")
S0W = os.path.join(ST, "s0_wide.pt")                         # (S0 with the order's inputs and token only, at zero)
FIT = os.path.join(HERE, "order_fit.json")
NEW0 = "--keep-g 0 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0 --pass-odds 0.3 --pass-warm 0"      # (make_files.py's)
OPEN = dict(KEEP_G=1.0, CMB_G=1.0, PADD=1.0, ORD_GATE=0.0, FADD=1.0, H2_FPG=1.0)
C16 = os.path.join(MAIN, "docs", "runs", "1.6", "1.6a", "train.cmd")
END_DIALS = dict(INTENT_TEACH_W=0.0, SPEED_PAY=0.0)        # (1.6a's dials at its end)
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
    say("the start: {}".format(S0))
    if not os.path.exists(S1K):
        subprocess.check_call([PY, os.path.join(ROOT, "tools", "keep_init.py"), "add", S0, S1K], env=cenv())
    if not os.path.exists(S1):
        subprocess.check_call([PY, os.path.join(ROOT, "tools", "order_init.py"), "add", S1K, S1] + (["--fit", FIT] if os.path.exists(FIT) else []),
                              env=cenv())
    say("the order's start: {}".format("the pros' fit " + FIT if os.path.exists(FIT) else "a flat start (no fit yet)"))
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "keep_init.py"), "same", S0, S1K], env=cenv(), capture_output=True, text=True)
    print(r.stdout + r.stderr, flush=True)
    check("keep_init same, the start against it given the keep choice", r.returncode == 0 and "ALL PASSED" in r.stdout)
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "order_init.py"), "same", S0, S1], env=cenv(), capture_output=True, text=True)
    print(r.stdout + r.stderr, flush=True)
    check("order_init same, the start against it given the keep choice and the whole order", r.returncode == 0 and "ALL PASSED" in r.stdout)
    return done()


def make_cmd(code, run, D, minutes, extra, ident=False, combat=False):
    """a small CPU copy of 1.6a's train.cmd (1.7a's flags in `extra`): the code at `code`, data the checkout lacks from the main one,
    the cores inherited from the caller (run17.cmd: 14 to 17), below normal"""
    t = open(C16, encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(code)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(os.path.dirname(C16), "aim2_env.cmd")),
            ("set WIN_JUDGE=%ROOT%" + BS, "set WIN_JUDGE=" + MAIN + BS),
            ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal "), ("--workers 30 ", "--workers 2 "),
            ("--matches 168 ", "--matches 8 "), ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "),
            ("%LEARN% >> ", "{} --snapshot-min {} {} >> ".format(
                extra, 1000 if ident else 1, "--seed 7 --max-updates 2 --dump-acts " + os.path.join(D, "acts") if ident else "--overlap 1 --learn-nosync 1"))]
    if "--brain-human %ROOT%" + BS in t:
        subs.append(("--brain-human %ROOT%" + BS, "--brain-human " + MAIN + BS))
    if combat:                                               # (1.7) the combat order in the simulators
        subs.append(("set WEAPON_FREE=1\n", "set WEAPON_FREE=1\nset COMBAT=1\n"))
    for a, b in subs:
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    t = re.sub(r"--run duel_gru_\S+ ", "--run {} ".format(run), t)
    t = re.sub(r"--minutes \d+ --gamma", "--minutes {} --gamma".format(minutes), t)
    t = re.sub(r"data\\sim_runs\\duel_gru_[0-9a-z_]+\.log", lambda m_: "data" + BS + "sim_runs" + BS + run + ".log", t)
    live_ = [x for x in t.split("\n") if not x.startswith("rem")]
    assert not any("duel_gru_1_" in x for x in live_), "a real run's name is left in the small command"
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    return cmd


def lay_out(code, run, start_pt, start_opt, live_extra=None, snaps=(), widen=False):
    """a scratch run folder at code/data/sim_runs/<run>: the start, its optimizer, 1.6a's live dials at its end, the league's anchors
    (widen: given the order's inputs at zero, tools/order_init.py widen-league, as start.ps1 does)"""
    D = os.path.join(code, "data", "sim_runs", run)
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (look at it first; nothing deleted)")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(start_pt, os.path.join(D, "policy.pt"))
    shutil.copy2(start_opt, os.path.join(D, "opt.pt"))
    for name, p_ in [(n_, os.path.join(ANCH, n_)) for n_ in ("anchor_13b.pt", "anchor_b12d.pt")] + list(snaps):
        if widen:
            subprocess.check_call([PY, os.path.join(ROOT, "tools", "order_init.py"), "widen-league", p_, os.path.join(D, "snapshots", name)],
                                  env=cenv(), stdout=subprocess.DEVNULL)
        else:
            shutil.copy2(p_, os.path.join(D, "snapshots", name))
    shutil.copy2(os.path.join(R6A, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R6A, "live.json"), encoding="utf-8"))
    lv.update(VALUE_WARM=0, **END_DIALS)
    lv.update(**(live_extra or {}))
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    return D


def trainer(code, cmd, run, limit_min):
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=code, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"))
    while tr.poll() is None and time.time() - t0 < limit_min * 60:
        time.sleep(10)
    if tr.poll() is None:
        say("{}: the trainer still runs after {} min: left running".format(run, limit_min))
        return None
    log = open(os.path.join(code, "data", "sim_runs", run + ".log"), encoding="utf-8", errors="replace").read()
    say("{}: done in {:.1f} min; the log ends: {}".format(run, (time.time() - t0) / 60, log.rstrip().splitlines()[-1] if log.strip() else "(empty)"))
    return log


def ident():
    import torch
    if not os.path.exists(S1):
        say("no test starts: run `start` first")
        return 1
    if not os.path.exists(S0W):
        subprocess.check_call([PY, os.path.join(ROOT, "tools", "order_init.py"), "widen-league", S0, S0W], env=cenv())
    arms = [("base", MAIN, S0, ""), ("base2", MAIN, S0, ""), ("a1", ROOT, S0W, ""), ("a2", ROOT, S1, NEW0),
            ("a3", ROOT, S1, NEW0.replace("--keep-g 0 --cmb-g 0 --padd 0 --fadd 0 --head2-fpg 0", "--keep-g 1 --cmb-g 1 --padd 1 --fadd 1 --head2-fpg 1"))]
    acts, logs = {}, {}
    for name, code, st, extra in arms:
        run = "scratch_17a_id_" + name + TAG
        D = lay_out(code, run, st, S0O, snaps=(("snap_0001.pt", S0),), widen=name in ("a1", "a2", "a3"),     # (a snapshot: league matches from
                    live_extra=dict(ORD_GATE=0.0) if name == "a3" else None)                         # update 1 in every arm alike)
        log = trainer(code, make_cmd(code, run, D, 30, extra, ident=True, combat=name in ("a2", "a3")), run, 60)
        logs[name] = log or ""
        dumps = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(dumps), "" if log else ", NO LOG"), log is not None and len(dumps) >= 2)
        acts[name] = [torch.load(f, map_location="cpu") for f in dumps[:2]]
        if log:
            check("{}: the optimizer's state loaded from opt.pt, not a cold start".format(name), "optimizer: its state loaded from opt.pt" in log and "cold start" not in log)
        if name in ("a2", "a3") and log:
            check("{} announced the keep choice, the combat order, the fire push, the order's token and the pass odds".format(name),
                  "keep choice (1.4c)" in log and "combat order (1.7)" in log and "fire push (1.7)" in log and "the order's token (1.7)" in log
                  and "pass odds (1.7)" in log)
            check("{}: the optimizer's moments carried over the widened inputs (the encoder, the marks, the head's inputs)".format(name),
                  "optimizer: enc.0.weight carried over" in log and "optimizer: attn.mark carried over" in log
                  and "optimizer: head2.inp.weight carried over" in log and "optimizer: head2.winp.weight carried over" in log)
    if not all(len(acts.get(n, [])) >= 2 for n, *_ in arms):
        check("every arm dumped its updates", False)
        return done()

    def same(x, y, k, u):
        a_, b_ = acts[x][u][k], acts[y][u][k]
        return a_.shape == b_.shape and bool(torch.equal(a_, b_))

    check("the trainer repeats itself at a fixed seed (base = base2, both updates, actions and log p)",
          all(same("base", "base2", k, u) for k in ("act", "logp") for u in (0, 1)))
    def gap(x, y, u):
        """(actions that differ, the largest log p and value differences) of arm x against y in update u"""
        A_, B_ = acts[x][u], acts[y][u]
        return (float((A_["act"] != B_["act"]).float().mean()), float((A_["logp"].float() - B_["logp"].float()).abs().max()),
                float((A_["val"].float() - B_["val"].float()).abs().max()))
    # (1.7) the first layer reads 990 inputs, not 980: its sums run over 10 more columns (zeros), which moves the last bits of what
    # they add up to (1e-7 at the first frame); so 1.7's code against 1.6a's is the same play up to that rounding, and to the bit
    # among 1.7's own arms
    for u in (0, 1):
        g_ = gap("a1", "base", u)
        check("1.7's code, its inputs widened, nothing else set = 1.6a's code up to the rounding of the wider first layer (a1 against base, "
              "update {}: actions that differ {:.5f}, log p within {:.2g}, value within {:.2g})".format(u + 1, *g_),
              g_[0] == 0.0 and g_[1] < 1e-3 and g_[2] < 1e-3)
    check("the keep choice and the order at share 0, the adds and the fire push at 0, the token shut, the pass lesson on, COMBAT=1 = the "
          "same network without them, to the bit, in its first update (a2 = a1, actions, log p and value)",
          all(same("a2", "a1", k, 0) for k in ("act", "logp", "val")))
    g_ = gap("a2", "a1", 1)
    say("a2 against a1 in update 2 (the hands' and the head's new input columns learnt in update 1 from the order's inputs, which COMBAT "
        "fills; the pass lesson on its own layers): actions that differ {:.5f}, log p within {:.3g}, value within {:.3g}".format(*g_))
    A_, B_ = acts["a2"][1], acts["a1"][1]                    # (a game is chaotic: one flipped draw and the frames after differ; so the
    s0_ = (A_["act"][0] == B_["act"][0]).all(1)               # size is read on the update's first frame)
    v0_ = float((A_["val"][0].float() - B_["val"][0].float()).abs().max())
    l0_ = float((A_["logp"][0][s0_].float() - B_["logp"][0][s0_].float()).abs().max()) if s0_.any() else 0.0
    check("... and in its second update only what the new inputs' first learning moves: on its first frame value within {:.3g}, log p of the "
          "same actions within {:.3g} (under 1e-3 and 0.05)".format(v0_, l0_), v0_ < 1e-3 and l0_ < 0.05)
    d3 = float((acts["a3"][0]["act"] != acts["base"][0]["act"]).float().mean())
    check("at share 1 they decide: update 1's actions differ from base ({:.4f} of them)".format(d3), d3 > 0)
    return done()


def smoke():
    import torch
    if not os.path.exists(S1):
        say("no test starts: run `start` first")
        return 1
    run = "scratch_17a_smoke" + TAG
    D = lay_out(ROOT, run, S1, S0O, live_extra=OPEN, snaps=(("snap_0001.pt", S0),), widen=True)
    log = trainer(ROOT, make_cmd(ROOT, run, D, 30, NEW0, combat=True), run, 45)
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    check("on the CPU", "device cpu" in log)
    check("the optimizer's state loaded from S0's opt.pt (1.6a's groups given the keep choice's)", "optimizer: its state loaded from opt.pt" in log)
    check("the keep choice, the combat order, the fire push, the order's token and the pass odds announced", "keep choice (1.4c)" in log
          and "combat order (1.7)" in log and "fire push (1.7)" in log and "the order's token (1.7)" in log and "pass odds (1.7)" in log)
    M = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    check("8 or more updates ({})".format(len(M)), len(M) >= 8)
    K = [m.get("keep") or {} for m in M]
    for m, k in zip(M, K):
        s2 = k.get("sim2") or {}
        say("update {}: keep g {} readings {} p {} p_contact {} p_out {} kl {} | pull {} | arrived {} | sim2 {:.0f} s, {} a s, decided {}, redecide {}, "
            "arrived {} ({}), contact {} ({}), heard {} ({}) | own {}".format(
                m["update"], k.get("g"), k.get("readings"), k.get("p"), k.get("p_contact"), k.get("p_out"), k.get("kl"), k.get("pull"), k.get("arrived"),
                s2.get("seconds", 0), s2.get("readings_a_second"), s2.get("decided"), s2.get("redecide"), s2.get("arrived"), s2.get("redecide_arrived"),
                s2.get("contact"), s2.get("redecide_contact"), s2.get("heard"), s2.get("redecide_heard"), (k.get("w") or {}).get("own")))
    late = [k for k in K[1:] if k]
    check("every update recorded the keep choice at share 1", late and all(k.get("g") == 1.0 for k in late))
    check("its readings counted", late and all((k.get("readings") or 0) > 0 for k in late))
    rs = [(k.get("sim2") or {}).get("readings_a_second") for k in late]
    check("about five readings a second in its seconds ({})".format(rs[-5:]), all(x is not None and 4.0 < x < 6.0 for x in rs))
    check("the parts of its logit recorded", all(isinstance(k.get("pull"), dict) and k["pull"].get("own") is not None for k in late))
    check("arrivals read and counted", any(((k.get("sim2") or {}).get("arrived") or 0) > 0 for k in late))
    kls = [k.get("kl") for k in late]
    check("its step finite and small ({})".format(kls[-5:]), all(x is not None and math.isfinite(x) and abs(x) < 0.5 for x in kls))
    C = [m.get("cmb") or {} for m in M]
    for m, c in zip(M, C):
        cs_ = c.get("sim") or {}
        say("update {}: order g {} padd {} token {} asked {} p(an order) {} drawn {} p {} | chosen {} frames {} arrived {} damage {} | pass {} "
            "| w {} | fire {}".format(m["update"], c.get("g"), c.get("padd"), c.get("token_gate"), c.get("asked"), c.get("p_order"), c.get("drawn"),
                                      c.get("p"), cs_.get("chosen"), cs_.get("frames"), cs_.get("arrived"), cs_.get("dealt"), c.get("passodds"),
                                      c.get("w"), c.get("fire")))
    lc_ = [c for c in C[1:] if c]
    check("every update recorded the combat order at share 1 and adds 1, asked, its token open", lc_ and all(
        c.get("g") == 1.0 and c.get("padd") == 1.0 and c.get("token_gate") == 0.0 and (c.get("asked") or 0) > 0 for c in lc_))
    pz_ = [c.get("passodds") or {} for c in lc_]
    check("the brain's pass lesson ran: questions every update, its loss finite ({})".format([p_.get("loss") for p_ in pz_][-4:]),
          pz_ and all((p_.get("questions") or 0) > 0 and math.isfinite(p_.get("loss") or float("nan")) for p_ in pz_))
    check("the pass odds learn: the last update's Brier under the first's ({} -> {}; base {})".format(
        pz_[0].get("brier") if pz_ else None, pz_[-1].get("brier") if pz_ else None, pz_[-1].get("base") if pz_ else None),
          len(pz_) > 2 and (pz_[-1].get("brier") or 9) < (pz_[0].get("brier") or 0))
    ch_ = {}
    for c in lc_:
        for k_, v_ in ((c.get("sim") or {}).get("frames") or {}).items():
            ch_[k_] = ch_.get(k_, 0) + v_
    check("every kind followed ({})".format(ch_), all(ch_.get(k_, 0) > 0 for k_ in ("target", "cut", "spam", "out")))
    ar_ = {}
    for c in lc_:
        for k_, v_ in ((c.get("sim") or {}).get("arrived") or {}).items():
            ar_[k_] = ar_.get(k_, 0) + v_
    check("cut off and spam arrived ({})".format(ar_), ar_.get("cut", 0) > 0 and ar_.get("spam", 0) > 0)
    f0_, f1_ = (lc_[0].get("fire") or {}).get("fsc", 0.0) if lc_ else 0.0, (lc_[-1].get("fire") or {}).get("fsc", 0.0) if lc_ else 0.0
    check("the fire push's scores off zero and growing ({} -> {})".format(f0_, f1_), f1_ > f0_ >= 0.0 and f1_ > 0)
    w0_, w1_ = (lc_[0].get("w") or {}) if lc_ else {}, (lc_[-1].get("w") or {}) if lc_ else {}
    check("the order's parts on his state learn from zero (ok_s {} -> {}, op_s {} -> {})".format(
        w0_.get("ok_s"), w1_.get("ok_s"), w0_.get("op_s"), w1_.get("op_s")), (w1_.get("ok_s") or 0) > (w0_.get("ok_s") or 0) and
          (w1_.get("op_s") or 0) > (w0_.get("op_s") or 0))
    hd = [m.get("head2") or {} for m in M]
    check("no NaN in the head's lessons", all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd))
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    L_ = ck.get("head2") or {}
    sd_ = ck["model"]
    og_ = None
    if ck.get("attn") is not None and "attn.gate" in sd_:
        sys.path.insert(0, os.path.join(ROOT, "sim"))
        import attn as attn_
        og_ = [float(sd_["attn.gate"][i]) for i in attn_.drop_rows(ck["attn"])]
    check("the save carries them (layout keep {}, cmb {}, fire {}; shares {}, {}, adds {}, {}; the token's gate {}; the pass readout {})".format(
        L_.get("keep"), L_.get("cmb"), L_.get("fire"), float(sd_.get("head2.keep_g", -1)), float(sd_.get("head2.cmb_g", -1)),
        float(sd_.get("head2.padd", -1)), float(sd_.get("head2.fadd", -1)), og_, ck.get("passodds") is not None),
          L_.get("keep") == 2 and L_.get("cmb") == 1 and L_.get("fire") == 1 and abs(float(sd_["head2.keep_g"]) - 1.0) < 1e-6
          and abs(float(sd_["head2.cmb_g"]) - 1.0) < 1e-6 and abs(float(sd_["head2.padd"]) - 1.0) < 1e-6 and abs(float(sd_["head2.fadd"]) - 1.0) < 1e-6
          and og_ == [0.0] and ck.get("passodds") is not None and "passr.l1.weight" in sd_
          and (ck.get("env_vars") or {}).get("COMBAT") not in (None, "", "0"))
    n0 = len(M)
    log2 = trainer(ROOT, make_cmd(ROOT, run, D, 30, NEW0 + " --max-updates 1", combat=True), run, 15)
    tail_ = (log2 or "")[len(log):] if log2 and log2.startswith(log[:200]) else (log2 or "")
    M2 = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    check("a restart from the save with its optimizer: loaded, no cold start, one more update ({} -> {})".format(n0, len(M2)),
          log2 is not None and "optimizer: its state loaded from opt.pt" in tail_ and "cold start" not in tail_ and len(M2) == n0 + 1)
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    os.environ["PANEL_RUN"] = run
    import panel as P
    js = os.path.join(D, "watch", "chk_keep.json")
    cmd = [PY, "tools/duel_eval.py", "--run", run, "--policy", os.path.join(D, "policy.pt"), "--opp", "policy:" + S0,
           "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", "bloodrun", "--games", "2", "--minutes", "2", "--procs", "1", "--swap",
           "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600",
           "--opp-round", "600", "--hold", "8", "--opp-hold", "8", "--contact", "1", "--opp-contact", "1"]
    cmd += [x for s_ in P.settings(0.0, os.path.join(D, "policy.pt")) for x in ("--set", s_)]
    cmd += ["--set", "WIN_JUDGE=" + os.path.join(MAIN, "data", "sim_runs", "judge", "judge_v060_wpn.npz")]
    r = subprocess.run(cmd, cwd=ROOT, env=cenv(), capture_output=True, text=True)
    jv = json.load(open(js)) if os.path.exists(js) else {}
    v = (jv.get("maps") or {}).get("bloodrun") or {}
    say("check: exit {}; {}".format(r.returncode, (r.stdout + r.stderr)[-600:]))
    k2 = json.dumps(jv)[:0]
    check("a one-map check of the save (every part open) against the start finished ({}-{})".format(v.get("won"), v.get("lost")), r.returncode == 0 and "won" in v)
    say("  the check's keep counters: {}".format({k_: v.get(k_) for k_ in ("keep", "keep2") if k_ in v} or k2 or "(none in the json)"))
    return done()


if __name__ == "__main__":
    sys.exit({"start": start, "ident": ident, "smoke": smoke}[sys.argv[1]]())
