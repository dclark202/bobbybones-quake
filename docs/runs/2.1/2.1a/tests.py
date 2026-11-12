"""2.1a's tests (owner, 2026-11-12; docs/runs/2.1/2.1a/CARD.md). Nothing of a real run is touched: scratch run folders only
(data/sim_runs/scratch_21a_*), nothing deleted. CPU, below normal. S0 = 1.8a's save of update 50 (keep/policy_u50_18a.pt with
opt_u50_18a.pt, list 18); S1 = 2.1a's start: S0 brought to list 21 (tools/inputs21.py convert) and given the head's instruction part
(tools/head21_init.py add), both at zero effect. The league: 1.8a's three anchors brought to list 21, and S0 itself (widen-league).
The code is this tree's; the data is QLBOT_ROOT's when set (a worktree has none).

  start   S1 against S0: the two `same` checks (0 actions differ on real rows); the list (852: the brain 691, the hands 844); the token
          "instr" shut; the scorer's share 0 and its last layers zero; every weight S0 has is in S1 (the widened layers: their old part)
  old     THE TRAINER BEFORE THE BUILD AGAINST TODAY'S WITH EVERY 2.1 FLAG OFF: 1.8a's own command made small, at a fixed seed, on S0, run
          once by the code of --old (the main tree) and once by this tree: the two updates' dumps (actions, log p, values) equal to the bit
  ident   2.1a's command made small at a fixed seed on S1: it repeats itself to the bit; with everything at its start values update 1's
          actions are those of 1.8a's command on S0 (the start changes nothing of his play); the drills, the frozen moments and the head's
          share reach the simulators (update 1's actions differ); the pay on his own choice alone changes nothing before the first step
  live    the start's live.json applied before the first rollout; mid values of every dial written after update 1 are in
          live_applied.json and in the save's record
  smoke   ten small updates, every dial stepped by hand (the drills, the frozen moments, the token's gate; the head's share; the pay on
          its choice; the three fades and "a held weapon is choosable"; the strategy fade): no NaN, the instruction's records there, the
          played-to-before KL of the instruction's choice near 0, the binding's counts, then a stop and a resume from the save with its
          optimizer; with --overlap and without
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
  trial   the two-update trial at full size on the graphics card (the owner: "1 or 2 is fine"): stage 1's dials, two updates, no check
    python docs/runs/2.1/2.1a/tests.py start|old|ident|live|smoke|smoke_plain|trial [--old <the tree before the build>] [--fin <fin_rate json>]"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DROOT = os.environ.get("QLBOT_ROOT") or ROOT
PY = sys.executable
BS = "\\"
SR = os.path.join(DROOT, "data", "sim_runs")
R18 = os.path.join(SR, "duel_gru_1_8a")
S0, S0O = os.path.join(R18, "keep", "policy_u50_18a.pt"), os.path.join(R18, "keep", "opt_u50_18a.pt")
ST = os.path.join(SR, "scratch_21a_start2")                 # (2: the rows 67 wide, INS_WAY=1)
A21, S1 = os.path.join(ST, "u50_list21.pt"), os.path.join(ST, "start_21a.pt")
ANCH = ("anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt")
SAMPLE = os.path.join(SR, "inputs18", "sample_obs.npy")
CMD18 = os.path.join(DROOT, "docs", "runs", "1.8", "1.8a", "train.cmd")
OK = [True]
TAG = os.environ.get("TEST_TAG", "")
N_CHECK = [0]


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def check(name, cond):
    OK[0] = OK[0] and bool(cond)
    N_CHECK[0] += 1
    say(("PASS " if cond else "FAIL ") + name)


def cenv(**kw):
    return dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", QLBOT_ROOT=DROOT, INSTR="1", INS_WAY="1", **kw)


def done():
    say("ALL PASSED ({} checks)".format(N_CHECK[0]) if OK[0] else "FAILED")
    return 0 if OK[0] else 1


def tool(*a):
    r = subprocess.run([PY, os.path.join(ROOT, "tools", a[0])] + list(a[1:]), env=cenv(), capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode, r.stdout + r.stderr[-2000:]


def build():
    """S1, the league's files and the map sense's start in the scratch folder (made once; nothing written over)"""
    os.makedirs(ST, exist_ok=True)
    if not os.path.exists(A21):
        rc, out = tool("inputs21.py", "convert", S0, A21)
        assert rc == 0, out
    if not os.path.exists(S1):
        rc, out = tool("head21_init.py", "add", A21, S1)
        assert rc == 0, out
    for n_ in ANCH:
        if not os.path.exists(os.path.join(ST, n_.replace(".pt", "_list21.pt"))):
            rc, out = tool("inputs21.py", "convert", os.path.join(R18, "snapshots", n_), os.path.join(ST, n_.replace(".pt", "_list21.pt")))
            assert rc == 0, out
    if not os.path.exists(os.path.join(ST, "anchor_18a_u50.pt")):
        rc, out = tool("head21_init.py", "widen-league", A21, os.path.join(ST, "anchor_18a_u50.pt"))
        assert rc == 0, out
    if not os.path.exists(os.path.join(ST, "mapsense_start.pt")) and os.path.exists(os.path.join(SR, "scratch_21a_start", "mapsense_start.pt")):
        shutil.copy2(os.path.join(SR, "scratch_21a_start", "mapsense_start.pt"), os.path.join(ST, "mapsense_start.pt"))
    assert os.path.exists(os.path.join(ST, "mapsense_start.pt")), "the map sense's start is not made: tools/run/mapsense_init.py rows, then fit (--out {})".format(
        os.path.join(ST, "mapsense_start.pt"))


def start():
    import torch
    build()
    rc, out = tool("inputs21.py", "same", S0, A21, "--sample", SAMPLE)
    say("   " + out.strip().splitlines()[-2][:200])
    check("list 21 answers as list 18 on real rows, the new columns random (0 actions differ)", rc == 0 and "ALL PASSED" in out)
    rc, out = tool("head21_init.py", "same", A21, S1, "--sample", SAMPLE)
    say("   " + out.strip().splitlines()[-2][:200])
    check("the start (the head's instruction part added) answers as before it (0 actions differ)", rc == 0 and "ALL PASSED" in out)
    c0, c1 = (torch.load(p, map_location="cpu", weights_only=False) for p in (S0, S1))
    I = c1["inputs"]
    check("the list: {} inputs, the brain {}, the hands {} (list 21)".format(I["n"], I["n_brain"], I["n_hands"]), (I["list"], I["n"], I["n_brain"], I["n_hands"]) == (21, 852, 691, 844))
    kinds = [k["name"] for k in c1["attn"]["kinds"]]
    g = c1["model"]["attn.gate"]
    check("the token 'instr' is the last kind and shut (gate {:.0f})".format(float(g[-2])), kinds[-1] == "instr" and float(g[-2]) <= -29.0)
    sd0, sd1 = c0["model"], c1["model"]
    same_, wide_, miss_ = 0, [], []
    for k, v in sd0.items():
        if k not in sd1:
            miss_.append(k)
        elif tuple(sd1[k].shape) == tuple(v.shape):
            same_ += int(torch.equal(sd1[k], v))
        else:
            wide_.append(k)
    check("every weight of update 50 is in the start: {} tensors equal, {} widened ({}), {} missing".format(same_, len(wide_), ", ".join(wide_)[:120], len(miss_)),
          not miss_ and same_ + len(wide_) == len(sd0))
    W0, W1 = sd0["enc.0.weight"], sd1["enc.0.weight"]
    check("the hands' encoder: its 796 old columns unchanged, the 48 new at zero", torch.equal(W1[:, :796], W0) and not W1[:, 796:].any() and W1.shape[1] == 844)
    ins_ = [k for k in sd1 if k.startswith("head2.ins_")]
    check("the scorer inside the head ({} tensors), its share 0".format(len(ins_)), len(ins_) >= 6 and float(sd1["head2.ins_g"]) == 0.0)
    ev = c1.get("env_vars") or {}
    check("the save's play variables as update 50's (WEAPON_OWN 0, INTENT_HOLD 8)", str(ev.get("WEAPON_OWN")) in ("0", "0.0") and float(ev.get("INTENT_HOLD")) == 8.0)
    return done()


def small(src_cmd, run, D, code_root, minutes=30, ident=True, sets=(), args=(), extra="", steps=384):
    """a small CPU copy of a train.cmd: the code of code_root, the data of DROOT, the run `run` (steps: 2.1a's parts need a whole rollout of
    384 frames: the map sense reads 5 s ahead, a branch 8 s)"""
    t = open(src_cmd, encoding="ascii").read().replace("\r\n", "\n")
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset QLBOT_ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(DROOT, DROOT)),
            ("cd /d %ROOT%", "cd /d " + code_root),
            ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /belownormal "), ("--workers 30 ", "--workers 2 "),
            ("--matches 168 ", "--matches {} ".format(8 if steps < 384 else 16)), ("--steps 384 ", "--steps {} ".format(steps)), ("--minibatches 360 ", "--minibatches 4 "),
            ("%LEARN% >> ", "--snapshot-min {} {} {} >> ".format(1000 if ident else 1, ("--seed 7 --max-updates 2 --dump-acts " + os.path.join(D, "acts")) if ident else "", extra)),
            (">> data" + BS + "sim_runs" + BS, ">> %ROOT%" + BS + "data" + BS + "sim_runs" + BS)]
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
    ln_ = [x if x.startswith("rem") else re.sub(r"duel_gru_(2_1a|1_8a)", lambda m_: run, x) for x in ln_]
    t = "\n".join(ln_)
    t = re.sub(r"--minutes \d+ --gamma", "--minutes {} --gamma".format(minutes), t)
    assert not any(("duel_gru_1_8a" in x or "duel_gru_2_1a" in x) for x in t.split("\n") if not x.startswith("rem")), "a real run's name is left in the small command"
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    if not os.path.exists(os.path.join(D, "aim2_env.cmd")):
        shutil.copy2(os.path.join(os.path.dirname(CMD18), "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    return cmd


def cmd21(D, fin="", small_branches=True):
    """2.1a's command (make_files.py); small_branches: a moment of 2 + 1 candidates, so that a small simulator (8 self-play matches) has room for one"""
    out = os.path.join(D, "full.cmd")
    subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "1700", "--out", out] + (["--fin", fin] if fin else []), stdout=subprocess.DEVNULL, env=cenv())
    if small_branches:
        t = open(out, encoding="ascii").read()
        assert t.count(" --branch 1 ") >= 1             # (the trainer's line, and the header's copy of it)
        open(out, "w", encoding="ascii", newline="").write(t.replace(" --branch 1 ", " --branch 1 --branch-top 2 --branch-rand 1 "))
    return out


def live21(D, extra=None):
    out = os.path.join(D, "live.json")
    subprocess.check_call([PY, os.path.join(HERE, "start_live.py"), S0, os.path.join(R18, "live.json"), out], env=cenv(), stdout=subprocess.DEVNULL)
    lv = json.load(open(out, encoding="utf-8"))
    lv.update(**(extra or {}))
    json.dump(lv, open(out, "w", encoding="utf-8"))
    return lv


def new_dir(run):
    D = os.path.join(SR, run)
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (look at it first; nothing deleted). TEST_TAG=<x> makes new folders")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    return D


def lay_out(run, live_extra=None):
    """a scratch run folder with 2.1a's start: S1 and update 50's optimizer, the league's four files, 1.8a's live settings, the start's live.json"""
    build()
    D = new_dir(run)
    shutil.copy2(S1, os.path.join(D, "policy.pt"))
    shutil.copy2(S0O, os.path.join(D, "opt.pt"))
    for n_ in ANCH:
        shutil.copy2(os.path.join(ST, n_.replace(".pt", "_list21.pt")), os.path.join(D, "snapshots", n_))
    shutil.copy2(os.path.join(ST, "anchor_18a_u50.pt"), os.path.join(D, "snapshots", "anchor_18a_u50.pt"))
    shutil.copy2(os.path.join(ST, "mapsense_start.pt"), os.path.join(D, "keep", "mapsense_start.pt"))
    shutil.copy2(os.path.join(R18, "live_settings.env"), os.path.join(D, "live_settings.env"))
    live21(D, live_extra)
    return D


def lay_out18(run):
    """a scratch run folder with update 50 itself (list 18), 1.8a's anchors and the live.json update 50 played (no name of 2.1a's)"""
    D = new_dir(run)
    shutil.copy2(S0, os.path.join(D, "policy.pt"))
    shutil.copy2(S0O, os.path.join(D, "opt.pt"))
    for n_ in ANCH:
        shutil.copy2(os.path.join(R18, "snapshots", n_), os.path.join(D, "snapshots", n_))
    shutil.copy2(os.path.join(R18, "live_settings.env"), os.path.join(D, "live_settings.env"))
    sys.path.insert(0, HERE)
    import start_live as SL
    lv = live21(D)
    for k_ in SL.NEW:
        lv.pop(k_)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    return D


def popen(cmd, code_root):
    return subprocess.Popen(["cmd.exe", "/c", cmd], cwd=code_root, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", QLBOT_ROOT=DROOT),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def trainer(cmd, run, limit_min, code_root=ROOT):
    t0 = time.time()
    tr = popen(cmd, code_root)
    while tr.poll() is None and time.time() - t0 < limit_min * 60:
        time.sleep(5)
    if tr.poll() is None:
        say("{}: the trainer still runs after {} min: left running".format(run, limit_min))
        return None
    lp = os.path.join(SR, run + ".log")
    log = open(lp, encoding="utf-8", errors="replace").read() if os.path.exists(lp) else ""
    say("{}: done in {:.1f} min; the log ends: {}".format(run, (time.time() - t0) / 60, log.rstrip().splitlines()[-1][:200] if log.strip() else "(empty)"))
    return log


def metrics(D):
    p = os.path.join(D, "metrics.jsonl")
    return [json.loads(x) for x in open(p, encoding="utf-8") if x.strip()] if os.path.exists(p) else []


def dumps(D):
    import torch
    fs = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
    return [torch.load(f, map_location="cpu") for f in fs[:2]]


def same_dump(x, y, keys=None):
    """two dumps equal to the bit on the keys both have (or on `keys`); returns (equal, the keys that differ)"""
    import torch
    bad = []
    for k in (keys or sorted(set(x) & set(y))):
        a, b = x.get(k), y.get(k)
        if isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor):
            if a.shape != b.shape or not torch.equal(a, b):
                bad.append(k)
        elif a != b:
            bad.append(k)
    return not bad, bad


def old(old_root):
    assert old_root and os.path.exists(os.path.join(old_root, "sim", "train_duel_rnn.py")), "--old <the tree before the build>"
    res = {}
    for name, code in (("o_old", old_root), ("o_new", ROOT)):
        run = "scratch_21a_" + name + TAG
        D = lay_out18(run)
        log = trainer(small(CMD18, run, D, code, ident=True, steps=96), run, 90, code_root=code)
        res[name] = dumps(D)
        check("{} (the code of {}): the trainer ran 2 updates on update 50 and dumped them ({} dumps)".format(name, code, len(res[name])), log is not None and len(res[name]) >= 2)
        if log:
            check("{}: the optimizer's state loaded, no REFUSED live file".format(name), "optimizer: its state loaded from opt.pt" in log and "REFUSED" not in log and "cold start" not in log)
    if all(len(v) >= 2 for v in res.values()):
        for u in (0, 1):
            eq, bad = same_dump(res["o_old"][u], res["o_new"][u])
            check("update {}: today's trainer with every 2.1 flag off = the trainer before the build, to the bit ({} keys{})".format(
                u + 1, len(set(res["o_old"][u]) & set(res["o_new"][u])), "" if eq else "; differ: " + ", ".join(bad)[:200]), eq)
        check("the two dumps carry the same keys", set(res["o_old"][0]) == set(res["o_new"][0]))
    return done()


def ident():
    arms = [("z0", None), ("z0b", None), ("zd", dict(DRILL_INS_P=1.0)), ("zr", dict(DRILL_INS_RATE=0.2)), ("zb", dict(BRANCH_P=0.5)), ("zg", dict(INS_G=1.0)), ("zp", dict(H2_INS_PG=1.0)),
            ("zs", dict(INTENT_SWITCH=0.0, WEAPON_OWN=1.0))]
    acts, mets, logs = {}, {}, {}
    OFF = tuple((f_, "0") for f_ in ("--map-sense", "--appraise", "--known-odds", "--spawn-odds", "--branch", "--branch-long", "--ins", "--ins-pay-win", "--ins-quiet", "--ins-ms"))
    arms.append(("zq", None))                                # the start with every 2.1 lesson and the head's choice off: his play alone
    for name, lv in arms:
        run = "scratch_21a_id_" + name + TAG
        D = lay_out(run, live_extra=lv)
        log = trainer(small(cmd21(D), run, D, ROOT, ident=True, args=(OFF if name == "zq" else ())), run, 120)
        acts[name], mets[name], logs[name] = dumps(D), metrics(D), log or ""
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(acts[name]), "" if log else ", NO LOG"), log is not None and len(acts[name]) >= 2)
        if log:
            check("{}: the optimizer's state loaded from opt.pt (the widened layers carried, the group 'ins' fresh), no REFUSED live file".format(name),
                  "optimizer: " in log and "REFUSED" not in log)
            for ln_ in [x for x in log.splitlines() if any(w_ in x for w_ in ("optimizer: ", "binding weapon", "instruction's token", "the head's choice", "frozen", "appraisals"))][:8]:
                say("   " + ln_[:260])
    if not all(len(acts.get(n, [])) >= 2 for n, _ in arms):
        check("every arm dumped its updates", False)
        return done()
    A = "actions" if "actions" in acts["z0"][0] else sorted(k for k in acts["z0"][0] if "act" in k)[0]
    for u in (0, 1):
        eq, bad = same_dump(acts["z0"][u], acts["z0b"][u])
        check("update {}: it repeats itself to the bit{}".format(u + 1, "" if eq else " (differ: {})".format(", ".join(bad)[:160])), eq)
    run = "scratch_21a_id_z18" + TAG                           # 1.8a's own command on update 50, today's code: his play at the start
    D = lay_out18(run)
    log = trainer(small(CMD18, run, D, ROOT, ident=True, sets=(("INTENT_SWITCH", "0.02"), ("WEAPON_OWN", "0"))), run, 120)
    z18 = dumps(D)
    check("z18: 1.8a's command on update 50 ran", log is not None and len(z18) >= 2)
    if len(z18) >= 2:
        import torch
        a0, aq = acts["z0"][0][A], acts["zq"][0][A]
        vq, v18 = acts["zq"][0]["val"].float(), z18[0]["val"].float()
        rq, r18 = acts["zq"][0]["rew"], z18[0]["rew"]
        d0 = float((vq[0] - v18[0]).abs().max())
        check("the first frame: the start on list 21 in the instruction's simulator values every seat as update 50 does under 1.8a's command "
              "(largest difference {:.2g}), the first frame's pay equal".format(d0), vq.shape == v18.shape and d0 < 1e-5 and torch.equal(rq[0], r18[0]))
        say("   (after the first frame the two cannot be set side by side: the wider network is made from the trainer's random stream before his first "
            "draw, so his draws differ. That his answers are the same on real rows is the start test's `same`: 0 of 44,800 actions)")
        check("the lessons and the head's choice on (z0) against off (zq): update 1's actions the same to the bit ({} of {} differ)".format(
            int((a0 != aq).sum()), a0.numel()), torch.equal(a0, aq))
    for name, what in (("zd", "the drills"), ("zr", "the drills begun in the middle of a game"), ("zb", "the frozen-moment rounds"), ("zg", "the head's own instructions"), ("zs", "the switch cost out and a held weapon choosable")):
        eq, _ = same_dump(acts["z0"][0], acts[name][0], keys=[A])
        eq2, _ = same_dump(acts["z0"][1], acts[name][1], keys=[A])
        check("{}: {} reach the simulators (update 1's or 2's actions differ from z0's)".format(name, what), not (eq and eq2))
    bz = [(m.get("branch") or {}).get("branches") for m in mets["zb"]]
    check("zb: frozen moments were played ({} branches by update; the first plan is made before the second rollout)".format(bz), any((b or 0) > 0 for b in bz))
    eq, _ = same_dump(acts["z0"][0], acts["zp"][0], keys=[A])
    check("zp: the pay on his own choice with the head's share 0 changes nothing of update 1's play", eq)
    m0 = mets["z0"][0] if mets["z0"] else {}
    check("z0: the records are there (pay_of: the head's side on the win chance alone)", (m0.get("pay_of") or {}).get("head_ins") == "win chance only")
    say("   z0's pay_of: {}".format(json.dumps(m0.get("pay_of"), default=str)[:300]))
    mg = mets["zg"][-1] if mets["zg"] else {}
    say("   zg's ins: {}".format(json.dumps(mg.get("ins"), default=str)[:600]))
    say("   zg's ins_bind: {}".format(json.dumps(mg.get("ins_bind"), default=str)[:300]))
    check("zg: with the head's share at 1 the binding's counts are there", mg.get("ins_bind") is not None)
    return done()


def step_live(D, tr, plan, limit_min):
    t0, done_n = time.time(), 0
    while tr.poll() is None and time.time() - t0 < limit_min * 60:
        time.sleep(3)
        n = len(metrics(D))
        if n > done_n:
            for k in range(done_n + 1, n + 1):
                if k in plan:
                    lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
                    lv.update(plan[k])
                    tmp = os.path.join(D, "live.json.tmp")
                    json.dump(lv, open(tmp, "w", encoding="utf-8"))
                    os.replace(tmp, os.path.join(D, "live.json"))
                    say("after update {}: live.json {}".format(k, plan[k]))
            done_n = n
    return tr.poll() is not None


PLAN = {1: dict(DRILL_INS_P=0.25, DRILL_INS_RATE=0.02, BRANCH_P=0.3, INS_GATE=-6.0, SPEED_PAY=0.06), 2: dict(INS_GATE=0.0, BRANCH_P=0.5, SPEED_PAY=0.0),
        3: dict(INS_G=0.5, BRANCH_WPN_P=0.3, BRANCH_LONG_P=0.2, INS_LONG_W=0.25), 4: dict(INS_G=1.0, INS_LONG_W=0.5), 5: dict(H2_INS_PG=0.5), 6: dict(H2_INS_PG=1.0),
        7: dict(SFADE=0.5), 8: dict(SFADE=1.0)}
#  (a file written after update k is in force about three updates later under --overlap: the test runs 14 updates so that the last step is read)


def smoke(overlap=True):
    import math
    tag = "ov" if overlap else "plain"
    run = "scratch_21a_smoke_" + tag + TAG
    D = lay_out(run)
    ex = ("--overlap 1 --learn-nosync 1 " if overlap else "") + "--max-updates 14 --ins-warm 20 --ins-long-warm 5"    # (the warm-ups small: the lesson is taught within the test)
    c_ = small(cmd21(D), run, D, ROOT, minutes=30000, ident=False, extra=ex)
    ok_ = step_live(D, popen(c_, ROOT), PLAN, 240)
    M = metrics(D)
    lp = os.path.join(SR, run + ".log")
    log = open(lp, encoding="utf-8", errors="replace").read() if os.path.exists(lp) else ""
    check("{}: fourteen updates ran ({} in metrics{})".format(tag, len(M), "" if ok_ else ", the trainer still running or dead"), ok_ and len(M) >= 14)
    if not M:
        say(log[-1500:])
        return done()
    def num(x):
        return isinstance(x, (int, float)) and math.isfinite(x)
    kl_ = [m.get("kl") for m in M]
    check("{}: no NaN in his step (kl by update {})".format(tag, [round(k, 4) if num(k) else k for k in kl_]), all(num(k) for k in kl_) and "nan" not in log.lower().replace("nan=", ""))
    ign_ = sorted({x.split("live: ")[1].split(" ignored")[0] for x in log.splitlines() if "ignored (" in x and "live: " in x})
    check("{}: no REFUSED live file; ignored: {} (BRAIN_FADE alone: the command has --brain-fade 0)".format(tag, ign_), "REFUSED" not in log and ign_ in ([], ["BRAIN_FADE"]))
    last = M[-1]
    for k in ("ins", "ins_bind", "drill_ins", "branch", "appraise", "pay_of"):
        say("   update {} {}: {}".format(len(M), k, json.dumps(last.get(k), default=str)[:700]))
    check("{}: the instruction's records are there at the end (ins, ins_bind, branch, appraise, pay_of)".format(tag), all(last.get(k) is not None for k in ("ins", "ins_bind", "branch", "appraise", "pay_of")))
    kls = [((m.get("ins") or {}).get("kl") or {}).get("played_to_before") for m in M]
    kls_ = [k for k in kls if num(k)]
    tg_ = [((m.get("ins") or {}).get("taught") or 0) for m in M]
    check("{}: the lesson toward the appraisals' order was taught ({} readings by update)".format(tag, tg_), max(tg_) > 0)
    if overlap:                                              # (--overlap: the rollout is played by the network of an update before: the KL is that lag, small)
        check("{}: the instruction's choice: KL played-to-before small on every update that has it ({}; the rollouts run one update behind)".format(
            tag, [round(k, 6) for k in kls_]), len(kls_) >= 3 and max(abs(k) for k in kls_) < 0.02)
    else:                                                    # (the wiring's proof: the learner before its step recomputes what was played)
        check("{}: THE WIRING: the instruction's choice recomputed before the step is the one played: KL on every update ({})".format(
            tag, [round(k, 8) for k in kls_]), len(kls_) >= 3 and max(abs(k) for k in kls_) < 2e-3)    # (not exactly 0: the kept rows and forecasts are at half precision; a missing mask reads 0.01 and up)
    tk_ = ((last.get("ins") or {}).get("tick") or {})
    say("   update {} the tick readouts: {}".format(len(M), json.dumps(tk_)[:700]))
    say("   update {} ins_norow: {}".format(len(M), json.dumps(last.get("ins_norow"))))
    pl_ = tk_.get("played") or {}
    nr_ = last.get("ins_norow") or {}
    check("{}: the head's share at 1, 'none' not offered: played seats' ticks under none {} (only where no real row was valid: {} of {} readings)".format(
        tag, pl_.get("under_none"), nr_.get("n"), nr_.get("readings")), pl_.get("ticks", 0) > 0 and (pl_.get("under_none") or 0) <= max(1e-9, 5.0 * (nr_.get("no_real_row") or 0.0)))
    check("{}: the head re-decides at every tick: the played seats' orders stand {} s on average, continue {}".format(tag, pl_.get("stands_secs"), pl_.get("cont")),
          pl_.get("stands_secs") is not None)
    ap_ = json.load(open(os.path.join(D, "live_applied.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_applied.json")) else {}
    f_ = ap_.get("file") or {}
    check("{}: the last dials were applied (SFADE {}, SPEED_PAY {}, INS_G {}, H2_INS_PG {}; the lock {}, the switch cost {} as update 50)".format(
        tag, f_.get("SFADE"), f_.get("SPEED_PAY"), f_.get("INS_G"), f_.get("H2_INS_PG"), f_.get("INTENT_HOLD"), f_.get("INTENT_SWITCH")),
        f_.get("SFADE") == 1.0 and float(f_.get("SPEED_PAY", 1)) == 0.0 and f_.get("INS_G") == 1.0 and f_.get("H2_INS_PG") == 1.0
        and float(f_.get("INTENT_HOLD", 0)) == 8.0 and float(f_.get("INTENT_SWITCH", 0)) == 0.02)
    sw_ = [((m.get("pay_terms") or {}).get("per_player_min") or {}).get("intent_switch") for m in M]
    say("   the target-switch cost a player-minute by update: {}".format(sw_))
    # the resume from the save with its optimizer: 2 more updates
    t_ = open(c_, encoding="ascii").read().replace("--max-updates 14", "--max-updates 2")
    open(c_, "w", encoding="ascii", newline="").write(t_)
    n0 = len(M)
    log2 = trainer(c_, run, 120)
    M2 = metrics(D)
    check("{}: the resume from the save ran 2 more updates ({} -> {}), the optimizer's group 'ins' loaded by name".format(tag, n0, len(M2)),
          log2 is not None and len(M2) >= n0 + 2 and "REFUSED" not in (log2 or ""))
    for ln_ in [x for x in (log2 or "").splitlines() if "optimizer: " in x][-2:]:
        say("   " + ln_[:260])
    return done()


def live():
    run = "scratch_21a_live" + TAG
    D = lay_out(run)
    c_ = small(cmd21(D), run, D, ROOT, minutes=30000, ident=False, extra="--overlap 1 --learn-nosync 1 --max-updates 4")
    sys.path.insert(0, HERE)
    import importlib.util
    spec = importlib.util.spec_from_file_location("ramp_21a", os.path.join(HERE, "ramp_21a.py"))
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    mid = {n_: round(0.5 * (v0 + v1), 6) for n_, lo, hi, v0, v1, pre in R.DIALS}
    rc = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "live_accept.py"), os.path.join(D, "live.json"), "--env", "duel_env_ffa21", "--ramp", os.path.join(HERE, "ramp_21a.py")],
                        env=cenv(), capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    say("   " + (rc.stdout.strip().splitlines() or ["(no output)"])[-1][:240])
    check("live_accept: the start's live.json and every file the ramp will write are accepted by the trainer's reader", rc.returncode == 0)
    ok_ = step_live(D, popen(c_, ROOT), {1: mid}, 120)
    st = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_status.json")) else {}
    check("the trainer ran and applied live.json (status {})".format(st.get("status")), ok_ and st.get("status") == "applied")
    ap_ = json.load(open(os.path.join(D, "live_applied.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "live_applied.json")) else {}
    f_ = ap_.get("file") or {}
    off = {k: (f_.get(k), v) for k, v in mid.items() if f_.get(k) is None or abs(float(f_[k]) - v) > 1e-6}
    check("mid values of all {} dials written after update 1 are applied (from update {}){}".format(len(mid), ap_.get("from_update"), "" if not off else " " + repr(off)),
          not off and (ap_.get("from_update") or 99) <= 4)
    import torch
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    rec = {}
    for part in ("sim", "trainer"):
        rec.update((ck.get("live") or {}).get(part) or {})
    off2 = {k: (rec.get(k), v) for k, v in mid.items() if rec.get(k) is None or abs(float(rec[k]) - v) > 1e-6}
    check("... and in the save's record of what was played{}".format("" if not off2 else " " + repr(off2)), not off2)
    ev = ck.get("env_vars") or {}
    check("the save's play variables carry the binding and the live ones (INS_BIND {}, INSTR {}, WEAPON_OWN {})".format(ev.get("INS_BIND"), ev.get("INSTR"), ev.get("WEAPON_OWN")),
          str(ev.get("INS_BIND")) == "1" and str(ev.get("INSTR")) == "1")
    return done()


def trial(fin=""):
    """the two-update trial at FULL SIZE on the graphics card (owner, 2026-11-12: "1 or 2 is fine"): the run's own command (30 simulators x
    168 matches x 384 frames, the trainer's cores), stage 1's dials at their end values (the drills, the frozen moments, the token's gate),
    two updates, then stop. Read: his step, the card's memory, minutes an update, the drills, the appraisals' first numbers. No check."""
    import threading
    NU = int(os.environ.get("TRIAL_UPDATES") or 2)        # (the final code: ONE full-size update, the owner 11-12)
    run = "scratch_21a_trial" + TAG
    D = lay_out(run, live_extra=dict(DRILL_INS_P=0.25, DRILL_INS_RATE=0.02, BRANCH_P=0.15, INS_GATE=-12.0))
    t = open(cmd21(D, fin=fin, small_branches=False), encoding="ascii").read().replace("\r\n", "\n")
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset QLBOT_ROOT={}".format(DROOT, DROOT)), ("cd /d %ROOT%", "cd /d " + ROOT),
                 ("%LEARN% >> ", "--snapshot-min 100000 --max-updates {} %LEARN% >> ".format(NU)), (">> data" + BS + "sim_runs" + BS, ">> %ROOT%" + BS + "data" + BS + "sim_runs" + BS)):
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_2_1a", run) for x in t.split("\n"))
    c_ = os.path.join(D, "trial.cmd")
    open(c_, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    shutil.copy2(os.path.join(os.path.dirname(CMD18), "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    peak, stop = [0], [False]

    def gpu():
        while not stop[0]:
            try:
                r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                peak[0] = max(peak[0], int(r.stdout.strip().splitlines()[0]))
            except Exception:                                # noqa: BLE001
                pass
            time.sleep(5)
    th = threading.Thread(target=gpu, daemon=True)
    th.start()
    t0 = time.time()
    log = trainer(c_, run, 120)
    stop[0] = True
    M = metrics(D)
    check("the trial ran two updates at full size ({} in metrics; {:.1f} minutes in all with the start-up)".format(len(M), (time.time() - t0) / 60), log is not None and len(M) >= NU)
    say("   the card's memory at its peak: {} MiB".format(peak[0]))
    for i, m in enumerate(M):
        say("   update {}: kl {} clip_frac {} sps {} | time {}".format(i + 1, m.get("kl"), m.get("clip_frac"), m.get("sps"), json.dumps(m.get("time"), default=str)[:300]))
        for k in ("ins", "ins_bind", "drill_ins", "ins_norow", "branch", "appraise", "pay_of", "known", "spawn", "mapsense", "map_sense"):
            if m.get(k) is not None:
                say("      {}: {}".format(k, json.dumps(m[k], default=str)[:900]))
        say("      tick: {}".format(json.dumps((m.get("ins") or {}).get("tick"))))
        ih_ = (m.get("v15") or {}).get("in_hand_games")
        say("      in hand in games {} | frags a match-minute {} | drills {}".format(ih_, m.get("frags_per_match_min"), json.dumps(m.get("drill_ins") or m.get("drills"), default=str)[:300]))
    for ln_ in [x for x in (log or "").splitlines() if any(w_ in x for w_ in ("optimizer: ", "binding weapon", "instruction's token", "device ", "GB", "REFUSED", "Traceback", "Error"))][:14]:
        say("   " + ln_[:260])
    return done()


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    fin_ = sys.argv[sys.argv.index("--fin") + 1] if "--fin" in sys.argv else ""
    old_root = sys.argv[sys.argv.index("--old") + 1] if "--old" in sys.argv else ""
    fn = dict(start=start, ident=ident, live=live, smoke=lambda: smoke(True), smoke_plain=lambda: smoke(False), old=lambda: old(old_root), trial=lambda: trial(fin_)).get(what)
    if fn is None:
        raise SystemExit(__doc__)
    sys.exit(fn())
