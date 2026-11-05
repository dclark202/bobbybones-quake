"""1.7a's tests (owner, 2026-11-05: "start with the code build for 1.7 ... Aim to have it ready to go today"; the tests on cores 14-17,
0x3C000, while 1.6a trains: "Be mindful of the 1.6a run, give it priority"). Run under the scratchpad's run17.cmd (those cores, below
normal, CPU only); every child inherits them. The start is 1.6a's end; until it exists 1.5a's end stands in (the same network: 1.6a
changed dials only). Nothing of a real run is touched: scratch run folders only (data/sim_runs/scratch_17a_* of the checkout that
plays: the main one for the code under 1.7a's, this worktree's own data folder, a plain copy of the maps, for 1.7a's), nothing deleted.

  start   S0 = the start (1.6a's end, or 1.5a's); S1 = S0 given the keep choice at share 0 (tools/keep_init.py add); keep_init same S0
          S1: 0 actions differ at share 0; at share 1 its column and re-decisions as the start says
  ident   the trainer at a fixed seed (--seed 7, --max-updates 2, --dump-acts; no --overlap), 2 simulators x 8 matches x 96 frames, 1.6a's
          command:
            base, base2  the code under 1.7a's (the main checkout: 1.6a's) on S0, twice: the trainer repeats itself to the bit
            a1           1.7a's code on S0, nothing new set: every action and log p of both updates the same as base
            a2           1.7a's code on S1 (the keep choice at share 0, --keep-g 0): both updates the same as base (at share 0 it decides
                         nothing and learns nothing); the optimizer's state loaded from S0's (1.6a's groups: the head's, the weapon
                         part's; the keep choice's added after the load), not a cold start
            a3           a2 with --keep-g 1: the keep choice decides; the actions differ from update 1 on
  smoke   1.7a's command made small (2 simulators, 8 matches, 96 frames, the CPU, --overlap as the run), from S1 with S0's optimizer, the
          keep choice at share 1 from update 0 (live KEEP_G 1), 1.6a's end dials, about 30 minutes: every update's keep record (its
          readings, about five a second in its seconds, the parts of its logit, arrivals), its step finite, no NaN; the save carries the
          keep choice (layout keep 2, share 1); a restart from the save with its optimizer loads it (one more update, no cold start);
          a one-map check of the save against S0 finishes and counts the keep choice's readings
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
ST = os.path.join(ROOT, "data", "sim_runs", "scratch_17a_start")
S1 = os.path.join(ST, "s1.pt")
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
    if not os.path.exists(S1):
        subprocess.check_call([PY, os.path.join(ROOT, "tools", "keep_init.py"), "add", S0, S1], env=cenv())
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "keep_init.py"), "same", S0, S1], env=cenv(), capture_output=True, text=True)
    print(r.stdout + r.stderr, flush=True)
    check("keep_init same, the start against it given the keep choice", r.returncode == 0 and "ALL PASSED" in r.stdout)
    return done()


def make_cmd(code, run, D, minutes, extra, ident=False):
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


def lay_out(code, run, start_pt, start_opt, live_extra=None, snaps=()):
    """a scratch run folder at code/data/sim_runs/<run>: the start, its optimizer, 1.6a's live dials at its end, the league's anchors"""
    D = os.path.join(code, "data", "sim_runs", run)
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (look at it first; nothing deleted)")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(start_pt, os.path.join(D, "policy.pt"))
    shutil.copy2(start_opt, os.path.join(D, "opt.pt"))
    for n_ in ("anchor_13b.pt", "anchor_b12d.pt"):
        shutil.copy2(os.path.join(ANCH, n_), os.path.join(D, "snapshots", n_))
    for name, p_ in snaps:
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
    arms = [("base", MAIN, S0, ""), ("base2", MAIN, S0, ""), ("a1", ROOT, S0, ""), ("a2", ROOT, S1, "--keep-g 0"), ("a3", ROOT, S1, "--keep-g 1")]
    acts, logs = {}, {}
    for name, code, st, extra in arms:
        run = "scratch_17a_id_" + name + TAG
        D = lay_out(code, run, st, S0O, snaps=(("snap_0001.pt", S0),))   # (a snapshot: league matches from update 1 in every arm alike)
        log = trainer(code, make_cmd(code, run, D, 30, extra, ident=True), run, 60)
        logs[name] = log or ""
        dumps = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(dumps), "" if log else ", NO LOG"), log is not None and len(dumps) >= 2)
        acts[name] = [torch.load(f, map_location="cpu") for f in dumps[:2]]
        if log:
            check("{}: the optimizer's state loaded from opt.pt, not a cold start".format(name), "optimizer: its state loaded from opt.pt" in log and "cold start" not in log)
        if name in ("a2", "a3") and log:
            check("{} announced the keep choice".format(name), "keep choice (1.4c)" in log)
    if not all(len(acts.get(n, [])) >= 2 for n, *_ in arms):
        check("every arm dumped its updates", False)
        return done()

    def same(x, y, k, u):
        a_, b_ = acts[x][u][k], acts[y][u][k]
        return a_.shape == b_.shape and bool(torch.equal(a_, b_))

    check("the trainer repeats itself at a fixed seed (base = base2, both updates, actions and log p)",
          all(same("base", "base2", k, u) for k in ("act", "logp") for u in (0, 1)))
    check("1.7a's code with nothing new set = the code under it (a1 = base, both updates)", all(same("a1", "base", k, u) for k in ("act", "logp") for u in (0, 1)))
    check("the keep choice at share 0 = 1.6a's play (a2 = base, both updates, actions and log p)", all(same("a2", "base", k, u) for k in ("act", "logp") for u in (0, 1)))
    d3 = float((acts["a3"][0]["act"] != acts["base"][0]["act"]).float().mean())
    check("the keep choice at share 1 decides: update 1's actions differ from base ({:.4f} of them)".format(d3), d3 > 0)
    return done()


def smoke():
    import torch
    if not os.path.exists(S1):
        say("no test starts: run `start` first")
        return 1
    run = "scratch_17a_smoke" + TAG
    D = lay_out(ROOT, run, S1, S0O, live_extra=dict(KEEP_G=1.0), snaps=(("snap_0001.pt", S0),))
    log = trainer(ROOT, make_cmd(ROOT, run, D, 30, "--keep-g 0"), run, 45)
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    check("on the CPU", "device cpu" in log)
    check("the optimizer's state loaded from S0's opt.pt (1.6a's groups given the keep choice's)", "optimizer: its state loaded from opt.pt" in log)
    check("the keep choice announced", "keep choice (1.4c)" in log)
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
    hd = [m.get("head2") or {} for m in M]
    check("no NaN in the head's lessons", all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd))
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    check("the save carries the keep choice (layout keep {}, share {})".format((ck.get("head2") or {}).get("keep"), float(ck["model"].get("head2.keep_g", -1))),
          (ck.get("head2") or {}).get("keep") == 2 and abs(float(ck["model"]["head2.keep_g"]) - 1.0) < 1e-6 and "head2.keep.weight" in ck["model"])
    n0 = len(M)
    log2 = trainer(ROOT, make_cmd(ROOT, run, D, 30, "--keep-g 0 --max-updates 1").replace("small.cmd", "small.cmd"), run, 15)
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
    check("a one-map check of the save (the keep choice at share 1) against the start finished ({}-{})".format(v.get("won"), v.get("lost")), r.returncode == 0 and "won" in v)
    say("  the check's keep counters: {}".format({k_: v.get(k_) for k_ in ("keep", "keep2") if k_ in v} or k2 or "(none in the json)"))
    return done()


if __name__ == "__main__":
    sys.exit({"start": start, "ident": ident, "smoke": smoke}[sys.argv[1]]())
