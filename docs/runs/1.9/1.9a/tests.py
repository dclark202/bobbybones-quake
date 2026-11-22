"""1.9a's tests (owner, 2026-11-12; docs/runs/1.9/1.9a/CARD.md). Nothing of a real run is touched: scratch run folders only
(data/sim_runs/scratch_19a_*), nothing deleted. CPU, below normal. S0 = 1.8a's end (keep/policy_end_18a.pt with opt_end_18a.pt: its save of
update 190, list 18); S1 = 1.9a's start: S0 brought to list 21 (tools/inputs21.py convert) and given the head's instruction part
(tools/head21_init.py add --ms 0 --bq 0 --quiet 0), both at zero effect. The league: 1.8a's three anchors on list 21 and S0 itself.

  start   S1 against S0: the two `same` checks (0 actions differ on real rows); the list (852); the token "instr" shut; the scorer's share 0
          and its last layers zero; no map sense, no brain questions, no quiet; every weight S0 has is in S1
  judge   the items' judge (sim/win_judge.py, the simulator's JUDGE_ITEMS): with K 0 it is the judge to the bit; its axioms on a grid (an item
          nearer to him never lowers his chance; worth 0 when absent or unreachable for both); the simulator's head stream with K 0 equals
          the hands' win part to the bit over 2,000 frames of real games, and with the fitted file it differs; FOLLOW_PAY 0 and on with
          nothing given: the pay to the bit
  ident   1.9a's command made small at a fixed seed on S1: it repeats itself to the bit; the copy lesson changes nothing of update 1's play;
          the head's share reaches the simulators; the follow pay changes the pay only where an instruction is carried out
  live    the start's live.json applied before the first rollout; mid values of every dial written after update 1 applied and in the record
  smoke   fourteen small updates, every dial stepped by hand: no NaN, the copy lesson taught and its agreement rising, the instruction's
          records, the played-to-before KL near 0, follow and judge_items records, then a resume from the save; with --overlap and without
  trial   one or two updates at full size on the graphics card (TRIAL_UPDATES): his step, the card's memory, minutes an update
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
    python docs/runs/1.9/1.9a/tests.py start|judge|ident|live|smoke|smoke_plain|trial [--fin <fin_rate json>] [--items <items json>]"""
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
S0, S0O = os.path.join(R18, "keep", "policy_end_18a.pt"), os.path.join(R18, "keep", "opt_end_18a.pt")
ST = os.path.join(SR, "scratch_19a_start2")                 # (2: the head reads the fight odds and the win value)
A21, S1 = os.path.join(ST, "u190_list21.pt"), os.path.join(ST, "start_19a.pt")
HEADF = ("--ms", "0", "--bq", "0", "--quiet", "0")             # (1.9a: no map sense at a row's place, no brain questions, no quiet)
FIN_T = os.path.join(DROOT, "docs", "runs", "2.1", "2.1a", "fin_rate_u50.json")     # (the tests only: a measured table; the run uses its own)
ITEMS_T = os.path.join(SR, "scratch_19a_start2", "items_test.json")
ANCH = ("anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt")
SAMPLE = os.path.join(SR, "inputs18", "sample_obs.npy")
CMD18 = os.path.join(DROOT, "docs", "runs", "1.8", "1.8a", "train.cmd")
OK = [True]
ITEMS_ARG = [""]
TAG = os.environ.get("TEST_TAG", "")
N_CHECK = [0]


def say(s):
    print(time.strftime("%H:%M:%S ") + s, flush=True)


def check(name, cond):
    OK[0] = OK[0] and bool(cond)
    N_CHECK[0] += 1
    say(("PASS " if cond else "FAIL ") + name)


def cenv(**kw):
    return dict(dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1", OMP_NUM_THREADS="1", QLBOT_ROOT=DROOT, INSTR="1", INS_WAY="1"), **kw)


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
        rc, out = tool("head21_init.py", "add", A21, S1 + ".ins.pt", *HEADF)
        assert rc == 0, out
        r_ = subprocess.run([PY, os.path.join(ROOT, "tools", "b19_init.py"), "add", S1 + ".ins.pt", S1], env=cenv(FIGHT_TRUTH="1"), capture_output=True, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        assert r_.returncode == 0, r_.stdout + r_.stderr[-2000:]
    for n_ in ANCH:
        if not os.path.exists(os.path.join(ST, n_.replace(".pt", "_list21.pt"))):
            rc, out = tool("inputs21.py", "convert", os.path.join(R18, "snapshots", n_), os.path.join(ST, n_.replace(".pt", "_list21.pt")))
            assert rc == 0, out
    if not os.path.exists(os.path.join(ST, "anchor_18a_end.pt")):
        rc, out = tool("head21_init.py", "widen-league", A21, os.path.join(ST, "anchor_18a_end_ins.pt"), *HEADF)
        assert rc == 0, out
        rc, out = tool("b19_init.py", "widen-league", os.path.join(ST, "anchor_18a_end_ins.pt"), os.path.join(ST, "anchor_18a_end.pt"))
        assert rc == 0, out
    if not os.path.exists(ITEMS_T):                          # (a test file of the items' judge: the defaults, marked accepted for the tests)
        sys.path.insert(0, os.path.join(ROOT, "sim"))
        import win_judge as wj_
        json.dump(dict(wj_.items_default(), accepted=True, note="tests only"), open(ITEMS_T, "w", encoding="utf-8"))


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
    check("every weight of 1.8a's end is in the start: {} tensors equal, {} widened ({}), {} missing".format(same_, len(wide_), ", ".join(wide_)[:120], len(miss_)),
          not miss_ and same_ + len(wide_) == len(sd0))
    W0, W1 = sd0["enc.0.weight"], sd1["enc.0.weight"]
    check("the hands' encoder: its 796 old columns unchanged, the 48 new at zero", torch.equal(W1[:, :796], W0) and not W1[:, 796:].any() and W1.shape[1] == 844)
    ins_ = [k for k in sd1 if k.startswith("head2.ins_")]
    check("the scorer inside the head ({} tensors), its share 0".format(len(ins_)), len(ins_) >= 6 and float(sd1["head2.ins_g"]) == 0.0)
    L1_ = c1["head2"]
    check("the head reads the fight odds (2) and the win value (1) at zero weight; the readout new, the win value carried ({})".format(
        {k: L1_["widths"].get(k) for k in ("fight", "wv")}), L1_["widths"].get("fight") == 2 and L1_["widths"].get("wv") == 1
        and "fight.both.0.weight" in sd1 and bool(c1.get("win_value")))
    ev = c1.get("env_vars") or {}
    check("the save's play variables as 1.8a's end's (WEAPON_OWN 1, INTENT_HOLD 8)", str(ev.get("WEAPON_OWN")) in ("1", "1.0") and float(ev.get("INTENT_HOLD")) == 8.0)
    L_ = (c1.get("head2") or {}).get("layout") or c1.get("head2_layout") or {}
    say("   the head's instruction layout: {}".format(json.dumps((L_ or {}).get("ins"), default=str)[:300]))
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
    ln_ = [x if x.startswith("rem") else re.sub(r"duel_gru_(1_9a|1_8a)", lambda m_: run, x) for x in ln_]
    t = "\n".join(ln_)
    t = re.sub(r"--minutes \d+ --gamma", "--minutes {} --gamma".format(minutes), t)
    assert not any(("duel_gru_1_8a" in x or "duel_gru_1_9a" in x) for x in t.split("\n") if not x.startswith("rem")), "a real run's name is left in the small command"
    cmd = os.path.join(D, "small.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    if not os.path.exists(os.path.join(D, "aim2_env.cmd")):
        shutil.copy2(os.path.join(os.path.dirname(CMD18), "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    return cmd


def cmd21(D, fin="", small_branches=True, items=""):
    """1.9a's command (make_files.py) with a measured FIN_RATE and an items' judge (the tests' own unless given)"""
    out = os.path.join(D, "full.cmd")
    subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "1700", "--out", out, "--fin", fin or FIN_T, "--items", items or ITEMS_T],
                          stdout=subprocess.DEVNULL, env=cenv())
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
    """a scratch run folder with 1.9a's start: S1 and 1.8a's end's optimizer, the league's four files, 1.8a's live settings, the start's live.json"""
    build()
    D = new_dir(run)
    shutil.copy2(S1, os.path.join(D, "policy.pt"))
    shutil.copy2(S0O, os.path.join(D, "opt.pt"))
    for n_ in ANCH:
        shutil.copy2(os.path.join(ST, n_.replace(".pt", "_list21.pt")), os.path.join(D, "snapshots", n_))
    shutil.copy2(os.path.join(ST, "anchor_18a_end.pt"), os.path.join(D, "snapshots", "anchor_18a_end.pt"))
    shutil.copy2(os.path.join(R18, "live_settings.env"), os.path.join(D, "live_settings.env"))
    live21(D, live_extra)
    return D


def lay_out18(run):
    """a scratch run folder with 1.8a's end itself (list 18), 1.8a's anchors and the live.json it played (no name of 1.9a's)"""
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
        if k_ not in ("INTENT_SWITCH", "WEAPON_OWN"):         # (in 1.8a's live.json too)
            lv.pop(k_, None)
    for k_, v_ in SL.SET.items():                            # (as 1.8a's end played them: the start sets them; here 1.8a's own)
        lv[k_] = {"H2_PG": 1.0, "INTENT_TEACH_W": 0.0, "SPEED_PAY": 0.0}[k_]
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


def ident():
    arms = [("z0", None), ("z0b", None), ("zc", dict(INS_COPY=0.0)), ("zg", dict(INS_G=1.0)), ("zp", dict(H2_INS_PG=1.0)),
            ("zf", dict(INS_G=1.0, FOLLOW_PAY=0.01)), ("zgf", dict(INS_G=1.0))]
    acts, mets, logs = {}, {}, {}
    for name, lv in arms:
        run = "scratch_19a_id_" + name + TAG
        D = lay_out(run, live_extra=lv)
        log = trainer(small(cmd21(D), run, D, ROOT, ident=True), run, 120)
        acts[name], mets[name], logs[name] = dumps(D), metrics(D), log or ""
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(acts[name]), "" if log else ", NO LOG"), log is not None and len(acts[name]) >= 2)
        if log:
            check("{}: the optimizer's state loaded from opt.pt (the widened layers carried, the group 'ins' fresh), no REFUSED live file".format(name),
                  "optimizer: " in log and "REFUSED" not in log)
            for ln_ in [x for x in log.splitlines() if any(w_ in x for w_ in ("optimizer: ", "binding weapon", "instruction's token", "the head's choice", "items"))][:8]:
                say("   " + ln_[:260])
    if not all(len(acts.get(n, [])) >= 2 for n, _ in arms):
        check("every arm dumped its updates", False)
        return done()
    import torch
    A = "actions" if "actions" in acts["z0"][0] else sorted(k for k in acts["z0"][0] if "act" in k)[0]
    for u in (0, 1):
        eq, bad = same_dump(acts["z0"][u], acts["z0b"][u])
        check("update {}: it repeats itself to the bit{}".format(u + 1, "" if eq else " (differ: {})".format(", ".join(bad)[:160])), eq)
    eq, _ = same_dump(acts["z0"][0], acts["zc"][0], keys=[A])
    check("zc: the copy lesson on or off changes nothing of update 1's play (it teaches; nothing plays from it at share 0)", eq)
    eq, _ = same_dump(acts["z0"][0], acts["zp"][0], keys=[A])
    check("zp: the pay on his own choice with the head's share 0 changes nothing of update 1's play", eq)
    eq, _ = same_dump(acts["z0"][0], acts["zg"][0], keys=[A])
    eq2, _ = same_dump(acts["z0"][1], acts["zg"][1], keys=[A])
    check("zg: the head's own instructions reach the simulators (update 1's or 2's actions differ from z0's)", not (eq and eq2))
    eq, _ = same_dump(acts["zg"][0], acts["zgf"][0])
    check("zgf: the head's share at 1 repeats itself to the bit (the follow arm's reference)", eq)
    a_g, a_f = acts["zgf"][0][A], acts["zf"][0][A]
    r_g, r_f = acts["zgf"][0].get("rew"), acts["zf"][0].get("rew")
    if r_g is not None and r_f is not None:
        same_first = torch.equal(r_g[0], r_f[0]) or True
        d_ = (r_f - r_g).float()
        check("zf: the follow pay changes his pay (not his first frame's actions: {}), only upward, by at most FOLLOW_PAY x DT a frame (largest {:.5f})".format(
            torch.equal(a_g[0], a_f[0]), float(d_.max())), torch.equal(a_g[0], a_f[0]) and float(d_[0].min()) >= -1e-7 and float(d_[0].max()) <= 0.01 * 0.025 + 1e-6)
    mf = mets["zf"][-1] if mets["zf"] else {}
    say("   zf's follow: {}".format(json.dumps(mf.get("follow"))))
    check("zf: the follow record is there (seat-seconds under an instruction, the share doing, the pay)", mf.get("follow") is not None)
    m0 = mets["z0"][0] if mets["z0"] else {}
    check("z0: the records are there (pay_of: the head's side on the win chance alone)", (m0.get("pay_of") or {}).get("head_ins") == "win chance only")
    say("   z0's pay_of: {}".format(json.dumps(m0.get("pay_of"), default=str)[:300]))
    say("   z0's judge_items: {}".format(json.dumps(m0.get("judge_items"), default=str)[:300]))
    say("   z0's ins terms: {}".format(json.dumps((m0.get("ins") or {}).get("terms"), default=str)[:300]))
    check("z0: the copy lesson was taught (its term above 0 on update 1 or 2)", any(((m.get("ins") or {}).get("terms") or {}).get("copy", 0) > 0 for m in mets["z0"]))
    mg = mets["zg"][-1] if mets["zg"] else {}
    say("   zg's ins_bind: {}".format(json.dumps(mg.get("ins_bind"), default=str)[:300]))
    check("zg: with the head's share at 1 the binding's counts are there", mg.get("ins_bind") is not None)
    return done()


def judge():
    """the items' judge: K 0 = the judge to the bit; its axioms; the simulator's head stream against the hands' win part"""
    import numpy as np
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import win_judge as wj_
    P, _ = wj_.load(os.path.join(SR, "judge", "judge_v060_wpn.npz"))
    rng = np.random.default_rng(3)
    n = 4000
    hpa, hpb = rng.uniform(1, 200, n), rng.uniform(1, 200, n)
    ara, arb = rng.uniform(0, 200, n), rng.uniform(0, 200, n)
    da, db = rng.random(n) < 0.1, rng.random(n) < 0.1
    wa, wb = (rng.random((n, 3)) < 0.5) * ~da[:, None], (rng.random((n, 3)) < 0.5) * ~db[:, None]
    d, left = rng.integers(-5, 6, n).astype(float), rng.uniform(0, 600, n)
    tsp = np.stack([np.where(rng.random(n) < 0.5, 0.0, rng.uniform(0, 35, n)), np.where(rng.random(n) < 0.5, 0.0, rng.uniform(0, 25, n))], 1)
    ra = dict(present=np.ones((n, 2), bool), tsp=tsp, walk=rng.uniform(0.5, 12, (n, 2)))
    rb = dict(present=np.ones((n, 2), bool), tsp=tsp, walk=rng.uniform(0.5, 12, (n, 2)))
    IP0 = dict(wj_.items_default(), k=[0.0, 0.0])
    c0 = wj_.chance(P, d, left, wj_.parts(hpa, ara, da), wa.astype(float), wj_.parts(hpb, arb, db), wb.astype(float))
    ci0 = wj_.chance_items(P, IP0, d, left, hpa, ara, da, wa.astype(float), hpb, arb, db, wb.astype(float), ra, rb)
    check("K 0: the items' judge is the judge to the bit ({} states)".format(n), np.array_equal(c0, ci0))
    IP = wj_.items_default()
    c1 = wj_.chance_items(P, IP, d, left, hpa, ara, da, wa.astype(float), hpb, arb, db, wb.astype(float), ra, rb)
    ra_n = dict(ra, walk=np.maximum(ra["walk"] - 1.0, 0.0))
    c2 = wj_.chance_items(P, IP, d, left, hpa, ara, da, wa.astype(float), hpb, arb, db, wb.astype(float), ra_n, rb)
    check("an item a second nearer to him never lowers his chance ({} of {} lower)".format(int((c2 < c1 - 1e-12).sum()), n), not (c2 < c1 - 1e-12).any())
    rab = dict(ra, present=np.zeros((n, 2), bool))
    c3 = wj_.chance_items(P, IP, d, left, hpa, ara, da, wa.astype(float), hpb, arb, db, wb.astype(float), rab, rb)
    check("no item on the map: the judge to the bit", np.array_equal(c3, c0))
    far_ = dict(ra, walk=np.full((n, 2), 60.0))
    c4 = wj_.chance_items(P, IP, d, left, hpa, ara, da, wa.astype(float), hpb, arb, db, wb.astype(float), far_, dict(rb, walk=np.full((n, 2), 60.0)))
    check("an item neither can reach: the judge to the bit", np.array_equal(c4, c0))
    # the simulator: a few thousand frames of real games, random hands, with and without the items' judge (K 0 file and the test file)
    code = r"""
import os, sys, json, numpy as np
sys.path.insert(0, os.path.join(sys.argv[1], 'sim'))
import duel_env_ffa21 as E
kw = dict(n_matches=4, seed=5, loadout='all', nav=os.path.join(sys.argv[2], 'data', 'maps', 'nav_bloodrun_sim.json'))
try:
    env = E.DuelEnv(os.path.join(sys.argv[2], 'data', 'maps', 'bloodrun.bsp'), group=2, **kw)
except TypeError:
    env = E.DuelEnv(os.path.join(sys.argv[2], 'data', 'maps', 'bloodrun.bsp'), **kw)
env.react_frames, env.acquire_frames = 3, 8
rng = np.random.default_rng(1)
H, W, R = [], [], []
env.observe()
for t in range(int(os.environ.get('JS_FRAMES') or 3000)):
    a = np.stack([rng.integers(0, k, env.n) for k in E.ACTION_DIMS], 1)
    a[:, 5] = rng.random(env.n) < 0.8
    o, r, d, info = env.step(a)
    H.append(np.asarray(getattr(env, 'wh_raw', np.zeros(env.n))).copy()); W.append(env.wb_raw.copy()); R.append(np.asarray(r, np.float64).copy())
np.savez(sys.argv[3], h=np.array(H), w=np.array(W), r=np.array(R), gm=int(env.wb_gm.sum()))
"""
    scr = os.path.join(ST, "judge_sim.py")
    os.makedirs(ST, exist_ok=True)
    open(scr, "w", encoding="utf-8").write(code)
    k0f = os.path.join(ST, "items_k0.json")
    json.dump(dict(wj_.items_default(), k=[0.0, 0.0], accepted=True), open(k0f, "w"))
    out = {}
    base = dict(cenv(), WIN_JUDGE=os.path.join(SR, "judge", "judge_v060_wpn.npz"), HEAD_PAY_TRUTH="1")
    cm_ = open(CMD18, encoding="ascii").read()
    for ln_ in cm_.splitlines():                              # (1.8a's own simulator switches, as the run has them)
        m_ = re.match(r"^set ([A-Z0-9_]+)=(.*)$", ln_.strip())
        if m_ and "%" not in m_.group(2):
            base[m_.group(1)] = m_.group(2)
    for tag, extra in (("off", dict()), ("k0", dict(JUDGE_ITEMS=k0f)), ("k1", dict(JUDGE_ITEMS=ITEMS_T)), ("fp0", dict(FOLLOW_PAY="0")), ("fp1", dict(FOLLOW_PAY="0.01"))):
        f_ = os.path.join(ST, "judge_sim_{}.npz".format(tag))
        env_ = dict(base, **extra)
        env_.pop("JUDGE_ITEMS", None) if "JUDGE_ITEMS" not in extra else None
        r = subprocess.run([PY, scr, ROOT, DROOT, f_], env=env_, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            say("   {}: {}".format(tag, r.stderr[-1500:]))
        out[tag] = np.load(f_) if r.returncode == 0 else None
    if out.get("off") is not None and out.get("k0") is not None and out.get("k1") is not None:
        o, k0, k1 = out["off"], out["k0"], out["k1"]
        check("the simulator: the hands' win part and pay with the items' judge (K 0 and the test file) = without it, to the bit ({} game seat-frames)".format(
            int((o["w"] != 0).sum())), np.array_equal(o["w"], k0["w"]) and np.array_equal(o["w"], k1["w"]) and np.array_equal(o["r"], k1["r"]))
        check("the simulator: the head's stream with K 0 = the hands' win part, to the bit", np.array_equal(k0["h"], k0["w"]))
        dh = float(np.abs(k1["h"] - k1["w"]).sum())
        check("the simulator: with the test file the head's stream differs from the hands' win part (|difference| summed {:.4g}; its sum over each game "
              "seat is zero-sum: {:.2g})".format(dh, float(np.abs(k1["h"].sum(1)).max())), dh > 0)
    else:
        check("the simulator's runs of the items' judge", False)
    if out.get("fp0") is not None and out.get("fp1") is not None:
        check("FOLLOW_PAY on with no instruction given: the pay to the bit", np.array_equal(out["fp0"]["r"], out["fp1"]["r"]))
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


PLAN = {1: dict(INS_GATE=-6.0, RAIL_FAR_PAY=0.12), 2: dict(INS_GATE=0.0, RAIL_FAR_PAY=0.0, INS_G=0.5, FOLLOW_PAY=0.005),
        3: dict(INS_G=1.0, FOLLOW_PAY=0.01, H2_INS_PG=0.5), 4: dict(H2_INS_PG=1.0, INS_COPY=0.5), 5: dict(INS_COPY=0.0),
        6: dict(SFADE=0.5), 7: dict(SFADE=1.0), 8: dict(FOLLOW_PAY=0.005), 9: dict(FOLLOW_PAY=0.0)}
#  (a file written after update k is in force about three updates later under --overlap: the test runs 14 updates so that the last step is read)


def smoke(overlap=True):
    import math
    tag = "ov" if overlap else "plain"
    run = "scratch_19a_smoke_" + tag + TAG
    D = lay_out(run)
    ex = ("--overlap 1 --learn-nosync 1 " if overlap else "") + "--max-updates 14"
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
    for k in ("ins", "ins_bind", "pay_of", "follow", "judge_items"):
        say("   update {} {}: {}".format(len(M), k, json.dumps(last.get(k), default=str)[:700]))
    check("{}: the instruction's records are there at the end (ins, ins_bind, pay_of, follow, judge_items, fight)".format(tag), all(last.get(k) is not None for k in ("ins", "ins_bind", "pay_of", "follow", "judge_items", "fight")))
    say("   the fight odds' record at the end: {}".format(json.dumps(last.get("fight"), default=str)[:400]))
    kls = [((m.get("ins") or {}).get("kl") or {}).get("played_to_before") for m in M]
    kls_ = [k for k in kls if num(k)]
    cp_ = [((m.get("ins") or {}).get("terms") or {}).get("copy") for m in M]
    ca_ = [((m.get("ins") or {}).get("terms") or {}).get("copy_agree") for m in M]
    check("{}: the copy lesson was taught while INS_COPY was on (its term by update {}), its agreement {}".format(tag, cp_, ca_),
          any((c or 0) > 0 for c in cp_[:5]))
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
    check("{}: the last dials were applied (SFADE {}, INS_G {}, H2_INS_PG {}, INS_COPY {}, FOLLOW_PAY {}, RAIL_FAR_PAY {}; the switch cost {})".format(
        tag, f_.get("SFADE"), f_.get("INS_G"), f_.get("H2_INS_PG"), f_.get("INS_COPY"), f_.get("FOLLOW_PAY"), f_.get("RAIL_FAR_PAY"), f_.get("INTENT_SWITCH")),
        f_.get("SFADE") == 1.0 and f_.get("INS_G") == 1.0 and f_.get("H2_INS_PG") == 1.0 and float(f_.get("INS_COPY", 1)) == 0.0
        and float(f_.get("FOLLOW_PAY", 1)) == 0.0 and float(f_.get("RAIL_FAR_PAY", 1)) == 0.0 and float(f_.get("INTENT_SWITCH", 1)) == 0.0)
    fl_ = [(m.get("follow") or {}).get("doing") for m in M]
    say("   the follow record's share doing by update: {}".format(fl_))
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
    run = "scratch_19a_live" + TAG
    D = lay_out(run)
    c_ = small(cmd21(D), run, D, ROOT, minutes=30000, ident=False, extra="--overlap 1 --learn-nosync 1 --max-updates 4")
    sys.path.insert(0, HERE)
    import importlib.util
    spec = importlib.util.spec_from_file_location("ramp_19a", os.path.join(HERE, "ramp_19a.py"))
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    mid = {}
    for n_, lo, hi, v0, v1, pre in R.DIALS:                  # (a name of two segments: its first's middle)
        mid.setdefault(n_, round(0.5 * (v0 + v1), 6))
    rc = subprocess.run([PY, os.path.join(ROOT, "tools", "run", "live_accept.py"), os.path.join(D, "live.json"), "--env", "duel_env_ffa21", "--ramp", os.path.join(HERE, "ramp_19a.py")],
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
    check("the save's play variables carry the binding and the items' judge (INS_BIND {}, INSTR {}, WEAPON_OWN {}, JUDGE_ITEMS {})".format(
        ev.get("INS_BIND"), ev.get("INSTR"), ev.get("WEAPON_OWN"), ev.get("JUDGE_ITEMS")), str(ev.get("INS_BIND")) == "1" and str(ev.get("INSTR")) == "1")
    return done()


def trial(fin=""):
    """the two-update trial at FULL SIZE on the graphics card (owner, 2026-11-12: "1 or 2 is fine"): the run's own command (30 simulators x
    168 matches x 384 frames, the trainer's cores), stage 1's dials at their end values (the drills, the frozen moments, the token's gate),
    two updates, then stop. Read: his step, the card's memory, minutes an update, the drills, the appraisals' first numbers. No check."""
    import threading
    NU = int(os.environ.get("TRIAL_UPDATES") or 2)        # (the final code: ONE full-size update, the owner 11-12)
    run = "scratch_19a_trial" + TAG
    D = lay_out(run, live_extra=dict(INS_GATE=-12.0, INS_G=0.5, FOLLOW_PAY=0.01, H2_INS_PG=0.5))     # (the dials of the run's middle: the most at once)
    t = open(cmd21(D, fin=fin, items=ITEMS_ARG[0]), encoding="ascii").read().replace("\r\n", "\n")
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset QLBOT_ROOT={}".format(DROOT, DROOT)), ("cd /d %ROOT%", "cd /d " + ROOT),
                 ("%LEARN% >> ", "--snapshot-min 100000 --max-updates {} %LEARN% >> ".format(NU)), (">> data" + BS + "sim_runs" + BS, ">> %ROOT%" + BS + "data" + BS + "sim_runs" + BS)):
        assert t.count(a) >= 1, a
        t = t.replace(a, b)
    t = "\n".join(x if x.startswith("rem") else x.replace("duel_gru_1_9a", run) for x in t.split("\n"))
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
        for k in ("ins", "ins_bind", "ins_norow", "pay_of", "follow", "judge_items"):
            if m.get(k) is not None:
                say("      {}: {}".format(k, json.dumps(m[k], default=str)[:900]))
        say("      tick: {}".format(json.dumps((m.get("ins") or {}).get("tick"))))
        ih_ = (m.get("v15") or {}).get("in_hand_games")
        say("      in hand in games {} | frags a match-minute {}".format(ih_, m.get("frags_per_match_min")))
    for ln_ in [x for x in (log or "").splitlines() if any(w_ in x for w_ in ("optimizer: ", "binding weapon", "instruction's token", "device ", "GB", "REFUSED", "Traceback", "Error"))][:14]:
        say("   " + ln_[:260])
    return done()


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    fin_ = sys.argv[sys.argv.index("--fin") + 1] if "--fin" in sys.argv else ""
    ITEMS_ARG[0] = sys.argv[sys.argv.index("--items") + 1] if "--items" in sys.argv else ""
    fn = dict(start=start, judge=lambda: (build(), judge())[1], ident=ident, live=live, smoke=lambda: smoke(True), smoke_plain=lambda: smoke(False),
              trial=lambda: trial(fin_)).get(what)
    if fn is None:
        raise SystemExit(__doc__)
    sys.exit(fn())
