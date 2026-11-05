"""1.5a's tests (owner, 2026-11-04 evening: "Please start with the code build now, and run any tests you think are appropriate"; the
computer is free after 1.4b's end). The start is 1.3b's end. Nothing of a real run is touched: scratch run folders only
(data/sim_runs/scratch_15a_* of the checkout that plays), their own league tables, nothing deleted.

  start   S0 = 1.3b's end; S1 = S0 given the head's weapon scores at zero (tools/weapon_init.py add); S1r = S1 with its weapon scores made
          random (a network whose head's part is not zero); then weapon_init same S0 S1: 0 actions differ, memory and head state the same
          to the bit; random scores reach the weapon key alone; at add 0 the same again
  ident   the trainer at a fixed seed (--seed 7, --max-updates 2, --dump-acts; no --overlap), 2 simulators x 8 matches x 96 frames, 1.3b's
          command:
            base, base2  the code under 1.5a's (the BobbyBones-14b checkout, branch b14c: 1.3b's play with its own settings unset) on S0,
                         twice: the trainer repeats itself to the bit
            a1           1.5a's code on S0, nothing new set: every action and log p of both updates the same as base
            a2           1.5a's code on S1 (the head's weapon scores at zero), --head2-wpg 0: update 1 the same as base (update 2 may
                         differ: the scores and the hands' weapon rows learn from update 1 on, and the L2 reaches the rows)
            a3           a2 with --habit-p 0: the same as a2 in both updates
            a4           a2 with --habit-p 1: update 1's self-play matches the same as a2's; the league seats' weapon key differs
  l2      the L2 reaches both parts of the weapon key, as it does the target's: two arms from S1r at a fixed seed, --head2-wpg 1, 2 updates,
          --head2-l2 50 against --head2-l2 0: the hands' weapon rows, the head's weapon scores and (as before) the target's two parts
          each end smaller with it by about (1 - lr x 50) a step; the rest of the network about the same
  smoke   1.5a's command made small (2 simulators, 8 matches, 96 frames, the CPU, --overlap as the run), from S1 with 1.3b's optimizer, all
          three pieces on from update 0 (live H2_WPG 1, HABIT_P 1), a league with networks without the weapon scores (the anchors) and one
          with its own (S1r), about 30 minutes: every update's weapon record at credit 1, its step finite and small, the weapon scores off
          zero and growing, the habits' league frames by kind and his frags against them counted, no NaN; the save carries the part;
          a one-map check of the save against S0 and one with its weapon scores switched off (--head2-wadd 0) finish
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
    %USERPROFILE%\\anaconda3\\python.exe docs\\runs\\1.5\\1.5a\\tests.py start|ident|l2|smoke"""
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
WT14 = os.path.join(GH, "BobbyBones-14b")
PY = sys.executable
BS = "\\"
R3B = os.path.join(MAIN, "data", "sim_runs", "duel_gru_1_3b")
S0, S0O = os.path.join(R3B, "keep", "policy_end_13b.pt"), os.path.join(R3B, "keep", "opt_end_13b.pt")
ST = os.path.join(ROOT, "data", "sim_runs", "scratch_15a_start")
S1, S1R = os.path.join(ST, "s1.pt"), os.path.join(ST, "s1_random.pt")
C13 = os.path.join(HERE, "..", "..", "b1.3", "1.3b", "train.cmd")
C13_14 = os.path.join(WT14, "docs", "runs", "b1.3", "1.3b", "train.cmd")
HAB = "--habit-push 2 --habit-kinds pro:1,rg:1,rl:1"
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
    import torch
    os.makedirs(ST, exist_ok=True)
    if not os.path.exists(S1):
        subprocess.check_call([PY, os.path.join(ROOT, "tools", "weapon_init.py"), "add", S0, S1], env=cenv())
    if not os.path.exists(S1R):
        ck = torch.load(S1, map_location="cpu", weights_only=False)
        g = torch.Generator().manual_seed(5)
        ck["model"]["head2.wsc.weight"] = torch.randn(ck["model"]["head2.wsc.weight"].shape, generator=g) * 0.05
        ck["model"]["head2.wsc.bias"] = torch.randn(ck["model"]["head2.wsc.bias"].shape, generator=g) * 0.5
        torch.save(ck, S1R)
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "weapon_init.py"), "same", S0, S1], env=cenv(), capture_output=True, text=True)
    print(r.stdout + r.stderr, flush=True)
    check("weapon_init same, 1.3b's end against it given the head's weapon scores", r.returncode == 0 and "ALL PASSED" in r.stdout)
    return done()


def make_cmd(code, src_cmd, run, D, minutes, extra, ident=False):
    """a small CPU copy of 1.3b's train.cmd (1.5a's flags in `extra`): the code at `code`, data the checkout lacks from the main one,
    the cores given by the caller (inherited), idle priority"""
    t = open(src_cmd, encoding="ascii").read().replace("\r\n", "\n")
    if "--head2-l2 " in extra:                               # (the l2 test: its own coefficient in place of 1.3b's 0.01)
        t = re.sub(r" --head2-l2 \S+", "", t)
    subs = [("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}\nset CUDA_VISIBLE_DEVICES=-1\nset OMP_NUM_THREADS=1".format(code)),
            ("call %~dp0aim2_env.cmd", "call " + os.path.join(os.path.dirname(os.path.abspath(src_cmd)), "aim2_env.cmd")),
            ("set WIN_JUDGE=%ROOT%" + BS, "set WIN_JUDGE=" + MAIN + BS),
            ("--brain-human %ROOT%" + BS, "--brain-human " + MAIN + BS),
            ("start \"\" /b /wait /affinity C03C3 ", "start \"\" /b /wait /low "), ("--workers 30 ", "--workers 2 "), ("--matches 168 ", "--matches 8 "),
            ("--steps 384 ", "--steps 96 "), ("--minibatches 360 ", "--minibatches 4 "),
            ("%LEARN% >> ", "{} --snapshot-min {} {} >> ".format(
                extra, 1000 if ident else 1, "--seed 7 --max-updates 2 --dump-acts " + os.path.join(D, "acts") if ident else "--overlap 1 --learn-nosync 1"))]
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
    """a scratch run folder at code/data/sim_runs/<run>: the start, its optimizer, 1.3b's live dials at its end, 1.3b's anchors and its end"""
    D = os.path.join(code, "data", "sim_runs", run)
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (look at it first; nothing deleted)")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(start_pt, os.path.join(D, "policy.pt"))
    shutil.copy2(start_opt, os.path.join(D, "opt.pt"))
    shutil.copy2(S0, os.path.join(D, "snapshots", "anchor_13b.pt"))
    shutil.copy2(os.path.join(R3B, "snapshots", "anchor_b12d.pt"), os.path.join(D, "snapshots", "anchor_b12d.pt"))
    for name, p_ in snaps:
        shutil.copy2(p_, os.path.join(D, "snapshots", name))
    shutil.copy2(os.path.join(R3B, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = json.load(open(os.path.join(R3B, "live.json"), encoding="utf-8"))
    lv.update(VALUE_WARM=0, **(live_extra or {}))
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
    arms = [("base", WT14, C13_14, S0, ""), ("base2", WT14, C13_14, S0, ""), ("a1", ROOT, C13, S0, ""),
            ("a2", ROOT, C13, S1, "--head2-wpg 0"), ("a3", ROOT, C13, S1, "--head2-wpg 0 --habit-p 0 " + HAB),
            ("a4", ROOT, C13, S1, "--head2-wpg 0 --habit-p 1 " + HAB)]
    acts = {}
    for name, code, src, st, extra in arms:
        run = "scratch_15a_id_" + name + TAG
        D = lay_out(code, run, st, S0O, snaps=(("snap_0001.pt", S0),))   # (a snapshot: league matches from update 1 in every arm alike)
        log = trainer(code, make_cmd(code, src, run, D, 30, extra, ident=True), run, 25)
        dumps = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(dumps), "" if log else ", NO LOG"), log is not None and len(dumps) >= 2)
        acts[name] = [torch.load(f, map_location="cpu") for f in dumps[:2]]
        if name == "a2" and log:
            check("a2 announced the weapon part and its credit", "weapon part (1.5a)" in log and "weapon key's credit (1.5a, part B)" in log)
        if name == "a4" and log:
            check("a4 announced the habits", "habits (1.5a, part C)" in log)
    if not all(len(acts.get(n, [])) >= 2 for n, *_ in arms):
        check("every arm dumped its updates", False)
        return done()

    def same(x, y, k, u, sel=None):
        a_, b_ = acts[x][u][k], acts[y][u][k]
        if sel is not None:
            a_, b_ = a_[:, sel], b_[:, sel]
        return a_.shape == b_.shape and bool(torch.equal(a_, b_))

    check("the trainer repeats itself at a fixed seed (base = base2, both updates, actions and log p)",
          all(same("base", "base2", k, u) for k in ("act", "logp") for u in (0, 1)))
    check("1.5a's code with nothing new set = the code under it (a1 = base, both updates)", all(same("a1", "base", k, u) for k in ("act", "logp") for u in (0, 1)))
    check("the head's weapon scores at zero, credit 0: update 1 = 1.3b's play (a2 = base, actions and log p)", all(same("a2", "base", k, 0) for k in ("act", "logp")))
    d2 = float((acts["a2"][1]["act"] != acts["base"][1]["act"]).float().mean())
    say("  (update 2: a2 against base, actions that differ {:.4f}: the scores and the hands' weapon rows learnt from update 1)".format(d2))
    check("habits at share 0 = none (a3 = a2, both updates)", all(same("a3", "a2", k, u) for k in ("act", "logp") for u in (0, 1)))
    N = acts["a2"][0]["act"].shape[1]
    w_n, half = N // 2, N // 4                               # (2 simulators of 8 matches of 2: each one's second half are league matches)
    selfplay = torch.tensor([(i % w_n) < half for i in range(N)])
    league_odd = torch.tensor([(i % w_n) >= half and i % 2 == 1 for i in range(N)])
    check("habits at share 1: update 1's self-play matches = a2's (a4 = a2 there)", same("a4", "a2", "act", 0, selfplay))
    wk_ = (acts["a4"][0]["act"][:, league_odd, 6] != acts["a2"][0]["act"][:, league_odd, 6]).float().mean()
    check("habits at share 1: the league seats' weapon key differs ({:.4f} of their frames)".format(float(wk_)), float(wk_) > 0)
    return done()


def l2():
    import torch
    if not os.path.exists(S1R):
        say("no test starts: run `start` first")
        return 1
    W = {}
    for name, wd in (("l2on", 50.0), ("l2off", 0.0)):
        run = "scratch_15a_" + name + TAG
        D = lay_out(ROOT, run, S1R, S0O)
        log = trainer(ROOT, make_cmd(ROOT, C13, run, D, 30, "--head2-wpg 1 --head2-l2 {:g}".format(wd), ident=True), run, 25)
        check("{}: ran (--head2-l2 {:g})".format(name, wd), log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
        W[name] = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)["model"]
    ck = torch.load(S1R, map_location="cpu", weights_only=False)
    o6 = sum(int(x) for x in ck["action_dims"][:6]) if "action_dims" in ck else None
    if o6 is None:
        import importlib
        sys.path.insert(0, os.path.join(ROOT, "sim"))
        E = importlib.import_module("duel_env")
        o6, n6 = int(sum(E.ACTION_DIMS[:6])), int(E.ACTION_DIMS[6])
        o10, n10 = int(sum(E.ACTION_DIMS[:10])), int(E.ACTION_DIMS[10])
    else:
        n6 = int(ck["action_dims"][6])
        o10, n10 = sum(int(x) for x in ck["action_dims"][:10]), int(ck["action_dims"][10])
    parts = {"the hands' weapon-key rows": lambda m: m["pi.weight"][o6:o6 + n6], "the head's weapon scores": lambda m: m["head2.wsc.weight"],
             "the hands' target rows": lambda m: m["pi.weight"][o10:o10 + n10], "the head's target scores": lambda m: m["head2.target.weight"],
             "the hands' other rows (no L2)": lambda m: torch.cat([m["pi.weight"][:o6], m["pi.weight"][o6 + n6:o10]]),
             "the head's value (no L2)": lambda m: m["head2.v.weight"]}
    for k, f in parts.items():
        a_, b_, s_ = float(f(W["l2on"]).norm()), float(f(W["l2off"]).norm()), float(f(ck["model"]).norm())
        r_ = a_ / max(b_, 1e-12)
        say("  {}: start {:.4f}, with L2 {:.4f}, without {:.4f}: ratio {:.4f}".format(k, s_, a_, b_, r_))
        if "(no L2)" in k:
            check("{} about the same with and without ({:.4f})".format(k, r_), 0.97 < r_ < 1.03)
        else:
            check("the L2 reaches {} ({:.4f}, about 0.89 expected for 24 steps)".format(k, r_), 0.80 < r_ < 0.95)
    return done()


def smoke():
    import torch
    if not os.path.exists(S1R):
        say("no test starts: run `start` first")
        return 1
    run = "scratch_15a_smoke" + TAG
    D = lay_out(ROOT, run, S1, S0O, live_extra=dict(H2_WPG=1.0, HABIT_P=1.0), snaps=(("snap_0001.pt", S1R),))
    log = trainer(ROOT, make_cmd(ROOT, C13, run, D, 30, "--head2-wpg 0 --habit-p 0.3 " + HAB), run, 45)
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    check("on the CPU", "device cpu" in log)
    check("the weapon part announced", "weapon part (1.5a)" in log)
    check("the habits announced", "habits (1.5a, part C)" in log)
    M = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    check("8 or more updates ({})".format(len(M)), len(M) >= 8)
    W = [m.get("weapon") or {} for m in M]
    H = [m.get("habit") or {} for m in M]
    for m, w, h in zip(M, W, H):
        say("update {}: weapon credit {} frames {} pg {} clip {} kl {} | head {} hands {} cos {} top his {} | w {} | habits {} frags {}".format(
            m["update"], w.get("credit"), w.get("frames"), w.get("pg"), w.get("clip_share"), w.get("kl"), w.get("head"), w.get("hands"),
            w.get("cos"), w.get("head_top_his"), w.get("w"), h.get("frames"), h.get("frags")))
    late = [w for w in W[3:] if w]
    check("every update recorded the weapon key's credit at 1 once live", late and all(w.get("credit") == 1.0 for w in late))
    check("its frames counted", late and all((w.get("frames") or 0) > 0 for w in late))
    kls = [w.get("kl") for w in late]
    check("its step finite and small ({})".format(kls[-5:]), all(x is not None and math.isfinite(x) and abs(x) < 0.5 for x in kls))
    check("its term finite", all(x is not None and math.isfinite(x) for x in (w.get("pg") for w in late)))
    w0, w1 = (late[0].get("w") or {}) if late else {}, (late[-1].get("w") or {}) if late else {}
    check("the head's weapon scores and its inputs' layer off zero and growing ({} -> {})".format(w0, w1),
          (w1.get("wsc") or 0) > (w0.get("wsc") or 0) > 0 and (w1.get("winp") or 0) > 0)
    check("the head's part has a size on the key's frames ({})".format(late[-1].get("head") if late else None), late and (late[-1].get("head") or 0) > 0)
    fr, fg = {}, {}
    for h in H:
        for k, v in (h.get("frames") or {}).items():
            fr[k] = fr.get(k, 0) + v
        for k, v in (h.get("frags") or {}).items():
            fg[k] = [fg.get(k, [0, 0])[0] + v[0], fg.get(k, [0, 0])[1] + v[1]]
    check("each habit played league frames ({})".format(fr), all(fr.get(k, 0) > 0 for k in ("pro", "rg", "rl")))
    say("  his frags for and against, by the league seat's habit: {}".format(fg))
    hd = [m.get("head2") or {} for m in M]
    check("no NaN in the head's lessons", all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd))
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    check("the save carries the weapon part (wadd {}, layout weapon {})".format(float(ck["model"].get("head2.wadd", -1)), (ck.get("head2") or {}).get("weapon")),
          (ck.get("head2") or {}).get("weapon") == 10 and abs(float(ck["model"]["head2.wadd"]) - 1.0) < 1e-6 and "head2.winp.weight" in ck["model"])
    check("the trainer's own snapshots carry it", any(f.startswith("snap_") and f != "snap_0001.pt" for f in os.listdir(os.path.join(D, "snapshots"))))
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    os.environ["PANEL_RUN"] = run
    import panel as P
    for tag, extra in (("check", []), ("check with the head's weapon scores off", ["--head2-wadd", "0"])):
        js = os.path.join(D, "watch", "chk_{}.json".format(len(extra)))
        cmd = [PY, "tools/duel_eval.py", "--run", run, "--policy", os.path.join(D, "policy.pt"), "--opp", "policy:" + S0,
               "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", "bloodrun", "--games", "2", "--minutes", "2", "--procs", "1", "--swap",
               "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600",
               "--opp-round", "600", "--hold", "8", "--opp-hold", "8", "--contact", "1", "--opp-contact", "1"] + extra
        cmd += [x for s_ in P.settings(0.0, os.path.join(D, "policy.pt")) for x in ("--set", s_)]
        cmd += ["--set", "WIN_JUDGE=" + os.path.join(MAIN, "data", "sim_runs", "judge", "judge_v060_wpn.npz")]
        r = subprocess.run(cmd, cwd=ROOT, env=cenv(), capture_output=True, text=True)
        v = json.load(open(js))["maps"]["bloodrun"] if os.path.exists(js) else {}
        say("{}: exit {}; {}".format(tag, r.returncode, (r.stdout + r.stderr)[-400:]))
        check("a one-map {} of the save against 1.3b's end finished ({}-{})".format(tag, v.get("won"), v.get("lost")), r.returncode == 0 and "won" in v)
    return done()


def launch():
    """1.5a's own train.cmd (make_files.py's, the switch cost, the weapon override and the blind-fire cost out) made small, from S1 as the
    start will be (live H2_WPG 0, HABIT_P 0.3), a snapshot in the league, --overlap as the run, 3 updates: it runs, its records are there,
    the save carries the settings that are play settings"""
    import torch
    run = "scratch_15a_launch" + TAG
    D = lay_out(ROOT, run, S1, S0O, live_extra=dict(H2_WPG=0.0, HABIT_P=0.3), snaps=(("snap_0001.pt", S1R),))
    subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "720"])
    cmd = make_cmd(ROOT, os.path.join(HERE, "train.cmd"), run, D, 30, "--max-updates 3")
    txt = open(cmd, encoding="ascii").read()
    check("the small command keeps the three settings and the new flags", all(s_ in txt for s_ in (
        "set WEAPON_OWN=1", "set INTENT_SWITCH=0", "set BLIND_FIRE_W=0", "--head2-wpg 0", "--habit-p 0.3", "--head2-l2 0.01")))
    log = trainer(ROOT, cmd, run, 30)
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    M = [json.loads(x) for x in open(os.path.join(D, "metrics.jsonl"), encoding="utf-8") if x.strip()]
    check("3 updates ({})".format(len(M)), len(M) >= 3)
    W = [m.get("weapon") or {} for m in M]
    check("the weapon key's credit 0 at the start ({})".format([w.get("credit") for w in W]), all(w.get("credit") == 0.0 for w in W))
    check("the head's weapon scores learn from update 1 on the hands' credit ({})".format([(w.get("w") or {}).get("wsc") for w in W]),
          (W[-1].get("w") or {}).get("wsc", 0) > 0)
    H = [m.get("habit") or {} for m in M]
    check("habits at 0.3 ({})".format([h.get("frames") for h in H]), all(h.get("p") == 0.3 for h in H) and sum(sum((h.get("frames") or {}).values()) for h in H) > 0)
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    ev = ck.get("env_vars") or {}
    check("the save carries WEAPON_OWN=1 ({})".format(ev.get("WEAPON_OWN")), str(ev.get("WEAPON_OWN")) == "1")
    return done()


if __name__ == "__main__":
    sys.exit({"start": start, "ident": ident, "l2": l2, "smoke": smoke, "launch": launch}[sys.argv[1]]())
