"""1.8a's tests (owner, 2026-11-11; docs/runs/1.8/1.8a/CARD.md); 2.0c's tests with 1.8a's start and dials. Nothing of a real run is touched:
scratch run folders only (data/sim_runs/scratch_18a_*), nothing deleted. CPU only, below normal; no run trains meanwhile. S0 = b1.2d's end
(keep/policy_end_b12d.pt, with opt_end_b12d.pt, 980 inputs); S1 = 1.8a's start: S0 widened to today's 1,053 inputs with zero weights
(tools/b18_init.py widen), the strategy head added as 1.3b's (tools/head2_init.py add --add 1 --chrono-lo 1 --gate 0 --ctrl-src belief) and
the keep choice as 1.7a's (tools/keep_init.py add), both at zero effect.

  start   S1 against S0: every weight S0 has is in S1 unchanged (the encoder's first layer: its first 980 columns, the rest zero); the new
          tokens shut; the head's target layer zero, its add 1, the keep choice's share 0, no weapon part, no order; 0 actions differ
          (the new inputs random too)
  ident   the trainer at a fixed seed (--seed 7, --max-updates 2, --dump-acts), 2 simulators x 8 matches x 96 frames, phase 1's command
          made small, on S1 with 1.3b's anchors widened:
            z0, z0b  the start's live.json: it repeats itself to the bit
            z2       DMG_REWARD 0.0055 (b1.2d's; the start is 0.005): update 1's actions and log p the SAME as z0 to the bit, update 2's
                     differ; update 1's damage dealt pays 0.0055/0.005 of z0's, frags, deaths and the win part unchanged
            z3       AIM3's END dials: update 1's actions DIFFER from z0's (the dials reach the simulators)
            z4       H2_PG 1 (the head's credit): update 1's actions the SAME as z0's (the credit is in the learning step only), update 2's differ
  smoke   phase 1's command made small, every dial stepped by hand over 10 updates (AIM3 to its end by update 3, the head's credit to 1 by
          update 6): no NaN; the head's part grows from zero; then the RESTART: phase 2's switches (INTENT_SWITCH 0, WEAPON_OWN 1), the
          teacher and the speed pay out and the keep choice at 0.975, 3 more updates from the save with its optimizer; a one-map check of
          the save against S0 and against 1.7a's update 90
  live    the real trainer with start.ps1's live.json: applied before the first rollout; mid values of every dial written after update 1
          are in live_applied.json by the end (from_update at most 4) and in the save's record of what the simulators played
Each prints PASS / FAIL lines and ALL PASSED or FAILED.
    python docs/runs/1.8/1.8a/tests.py start|ident|smoke|live"""
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
RB = os.path.join(ROOT, "data", "sim_runs", "duel_gru_b1_2d")
S0, S0O = os.path.join(RB, "keep", "policy_end_b12d.pt"), os.path.join(RB, "keep", "opt_end_b12d.pt")
C17 = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "keep", "policy_end_17a.pt")
ANCH = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_3b", "snapshots")   # 1.3b's league: b1.2d's end, b1.1, v0.6.0's end (980 inputs)
ST = os.path.join(ROOT, "data", "sim_runs", "scratch_18a_start")
S1, S1O = os.path.join(ST, "s1.pt"), os.path.join(ST, "s1_opt.pt")
CMD = os.path.join(HERE, "train.cmd")
OK = [True]
TAG = os.environ.get("TEST_TAG", "")                     # (a re-run: new scratch folders beside the old, nothing deleted)
AIM_END = dict(AIM3_W=1.0, AIM3_SIZE_A=0.39, AIM3_SIZE_B=0.355)
START_DIALS = dict(DMG_REWARD=0.005, DMG_TAKEN_W=1.0, WIN_ADD=0.33, AIM3_W=0.0, AIM3_SIZE_A=1.0, AIM3_SIZE_B=0.0, H2_PG=0.0, KEEP_G=0.0,
                   INTENT_TEACH_W=1.0, SPEED_PAY=0.125, COST_FIRE_W=0.0, H2_WPG=0.0, HABIT_P=0.0)


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


def tool(*a):
    r = subprocess.run([PY, os.path.join(ROOT, "tools", a[0])] + list(a[1:]), env=cenv(), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr[-2000:]


def widen(src, dst):
    if not os.path.exists(dst):
        rc, out = tool("b18_init.py", "widen", src, dst)
        assert rc == 0, out


def build():
    """S1 and its optimizer file, as start.ps1 makes them"""
    os.makedirs(ST, exist_ok=True)
    if os.path.exists(S1) and os.path.exists(S1O):
        return
    w_, h_ = os.path.join(ST, "w.pt"), os.path.join(ST, "h.pt")
    widen(S0, w_)
    rc, out = tool("head2_init.py", "add", w_, h_, "--add", "1", "--chrono-lo", "1", "--gate", "0", "--ctrl-src", "belief")
    assert rc == 0, out
    rc, out = tool("keep_init.py", "add", h_, S1, "--opt", S0O, S1O)
    assert rc == 0, out


def start():
    import torch
    build()
    a_, g_ = torch.load(S0, map_location="cpu", weights_only=False)["model"], torch.load(S1, map_location="cpu", weights_only=False)
    b_ = g_["model"]
    dif = [k_ for k_ in a_ if not k_.startswith("attn.") and k_ != "enc.0.weight" and not (k_ in b_ and a_[k_].shape == b_[k_].shape and torch.equal(a_[k_], b_[k_]))]
    w0, w1 = a_["enc.0.weight"], b_["enc.0.weight"]
    check("every weight of b1.2d's end outside the attention part and the encoder's first layer is in the start unchanged ({} differ); the first 980 "
          "input columns equal, the other {} zero".format(len(dif), w1.shape[1] - w0.shape[1]),
          not dif and w1.shape[1] == 1053 and torch.equal(w1[:, :980], w0) and float(w1[:, 980:].abs().max()) == 0.0)
    new_ = sorted({k_.split(".")[0] for k_ in b_} - {k_.split(".")[0] for k_ in a_})
    check("the only new parts are the strategy head's ({})".format(new_), new_ == ["head2"])
    L = g_.get("head2") or {}
    check("the head: its add 1, its gate 0, its target layer zero, the keep choice (2) at share 0, no weapon part, no order, no fire push ({})".format(
        {k_: L.get(k_) for k_ in ("keep", "weapon", "cmb", "fire")}),
        float(b_["head2.add"]) == 1.0 and float(b_["head2.gate"]) == 0.0 and float(b_["head2.target.weight"].abs().max()) == 0.0 and
        int(L.get("keep") or 0) == 2 and float(b_["head2.keep_g"]) == 0.0 and not L.get("weapon") and not L.get("cmb") and not L.get("fire"))
    gate_, r_ = {}, 0
    for k_ in g_["attn"]["kinds"]:                           # (a kind's tokens: len(idx) rows of the gate, in order)
        gg_ = b_["attn.gate"][r_:r_ + len(k_["idx"])]
        r_ += len(k_["idx"])
        if float(gg_.min()) < 0:
            gate_[k_["name"]] = float(gg_.min())
    check("the start's shut tokens are the order, the timers, space and targets ({})".format(gate_), sorted(gate_) == ["order", "space", "targets", "timers"])
    rc, out = tool("b18_init.py", "same", S0, S1)
    print(out, flush=True)
    check("the start answers as b1.2d's end: 0 actions differ (400 frames, 8 seats, the new inputs random too, the head's whole path run)", rc == 0 and "ALL PASSED" in out)
    rc, out = tool("keep_init.py", "same", os.path.join(ST, "h.pt"), S1)
    print(out[-900:], flush=True)
    check("keep_init same: share 0 answers as without the keep choice; at share 1 the start is the lock made soft", rc == 0 and "ALL PASSED" in out)
    return done()


def make_cmd(run, D, minutes, ident=False, sets=(), args=()):
    """a small CPU copy of phase 1's train.cmd: sets (NAME, VALUE) replace its set lines, args (flag, value) its arguments"""
    subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "1700", "1"], stdout=subprocess.DEVNULL)
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
    if not os.path.exists(os.path.join(D, "aim2_env.cmd")):
        shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))   # (the command calls it beside itself: the aim settings)
    return cmd


def start_live(D):
    out = os.path.join(D, "live.json")
    subprocess.check_call([PY, os.path.join(HERE, "start_live.py"), S0, os.path.join(RB, "live.json"), out], env=cenv(), stdout=subprocess.DEVNULL)
    return json.load(open(out, encoding="utf-8"))


def lay_out(run, live_extra=None):
    """a scratch run folder: S1 and its optimizer file, 1.3b's anchors widened, b1.2d's live settings, the start's live.json"""
    D = os.path.join(ROOT, "data", "sim_runs", run)
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (look at it first; nothing deleted)")
    build()
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(S1, os.path.join(D, "policy.pt"))
    shutil.copy2(S1O, os.path.join(D, "opt.pt"))
    for name in ("anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt"):
        w_ = os.path.join(ST, "w_" + name)
        widen(os.path.join(ANCH, name), w_)
        shutil.copy2(w_, os.path.join(D, "snapshots", name))
    shutil.copy2(os.path.join(RB, "live_settings.env"), os.path.join(D, "live_settings.env"))
    lv = start_live(D)
    lv.update(**(live_extra or {}))
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    return D


def trainer(cmd, run, limit_min):
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"),
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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
    arms = [("z0", None), ("z0b", None), ("z2", dict(DMG_REWARD=0.0055)), ("z3", dict(AIM_END)), ("z4", dict(H2_PG=1.0)), ("z5", dict(DMG_TAKEN_W=0.8))]
    acts, mets = {}, {}
    for name, lv in arms:
        run = "scratch_18a_id_" + name + TAG
        D = lay_out(run, live_extra=lv)
        log = trainer(make_cmd(run, D, 30, ident=True), run, 60)
        dumps = sorted(glob.glob(os.path.join(D, "acts_*.pt")), key=lambda f: int(re.findall(r"_(\d+)\.pt$", f)[0]))
        check("{}: the trainer ran 2 updates and dumped them ({} dumps{})".format(name, len(dumps), "" if log else ", NO LOG"), log is not None and len(dumps) >= 2)
        acts[name] = [torch.load(f, map_location="cpu") for f in dumps[:2]]
        mets[name] = metrics(D)
        if log:
            check("{}: the optimizer's state loaded from opt.pt, not a cold start; its moments carried over the widened inputs".format(name),
                  "optimizer: its state loaded from opt.pt" in log and "cold start" not in log and "optimizer: enc.0.weight carried over" in log)
            check("{}: no weapon table, no REFUSED live file, no order".format(name), "the pros' weapon table (1.7c)" not in log and "REFUSED" not in log)
            check("{}: the gates left as the file has them (no opening)".format(name), "open from" not in log)
            for ln_ in [x for x in log.splitlines() if any(w_ in x for w_ in ("optimizer: ", "keep choice", "strategy head", "combat order", "habit"))][:8]:
                say("   " + ln_[:240])
    if not all(len(acts.get(n, [])) >= 2 for n, _ in arms):
        check("every arm dumped its updates", False)
        return done()

    def same(x, y, k, u):
        a_, b_ = acts[x][u][k], acts[y][u][k]
        return a_.shape == b_.shape and bool(torch.equal(a_, b_))

    check("the trainer repeats itself at a fixed seed (z0 = z0b, both updates, actions and log p)", all(same("z0", "z0b", k, u) for k in ("act", "logp") for u in (0, 1)))
    d3 = float((acts["z3"][0]["act"] != acts["z0"][0]["act"]).float().mean())
    check("AIM3's END dials reach the simulators: update 1's actions differ from z0's ({:.4f} of them)".format(d3), d3 > 0)
    check("the damage pay changes nothing before the first learning step (z2 = z0: update 1's actions and log p, to the bit)",
          all(same("z2", "z0", k, 0) for k in ("act", "logp")))
    d2 = float((acts["z2"][1]["act"] != acts["z0"][1]["act"]).float().mean())
    check("... and update 2's actions differ ({:.4f} of them): the pay reached the learning step".format(d2), d2 > 0)
    check("the head's credit changes nothing before the first learning step (z4 = z0: update 1's actions and log p, to the bit)",
          all(same("z4", "z0", k, 0) for k in ("act", "logp")))
    d4 = float((acts["z4"][1]["act"] != acts["z0"][1]["act"]).float().mean())
    check("... and update 2's actions differ ({:.4f} of them): the credit reached the learning step".format(d4), d4 > 0)
    h0, h4 = (mets["z0"][0].get("head2") or {}) if mets["z0"] else {}, (mets["z4"][0].get("head2") or {}) if mets["z4"] else {}
    check("the head's credit as written: z0 {} , z4 {}".format(h0.get("credit"), h4.get("credit")), h0.get("credit") == 0.0 and h4.get("credit") == 1.0)
    p0, p2 = pm(mets["z0"][0]) if mets["z0"] else {}, pm(mets["z2"][0]) if mets["z2"] else {}
    say("update 1's ledger z0 (0.005): {}".format({k_: p0.get(k_) for k_ in ("dmg_dealt", "dmg_taken", "frag", "death", "win_part")}))
    say("update 1's ledger z2 (0.0055): {}".format({k_: p2.get(k_) for k_ in ("dmg_dealt", "dmg_taken", "frag", "death", "win_part")}))

    def ratio(k):
        a_, b_ = p0.get(k), p2.get(k)
        if not a_ and not b_:
            return 1.0
        return (b_ / a_) if (a_ not in (None, 0) and b_ is not None) else float("nan")

    def near(x, y, tol=0.02):
        return math.isfinite(x) and abs(x - y) <= tol * max(1.0, abs(y))

    check("the start pays damage at 0.005: z2's damage dealt and taken are 0.0055/0.005 of z0's ({:.4f}, {:.4f}; wanted {:.4f})".format(
        ratio("dmg_dealt"), ratio("dmg_taken"), 0.0055 / 0.005), near(ratio("dmg_dealt"), 1.1) and near(ratio("dmg_taken"), 1.1))
    check("update 1's win part, frags and deaths unchanged ({:.4f}, {}, {})".format(ratio("win_part"), ratio("frag"), ratio("death")),
          near(ratio("win_part"), 1.0, 1e-3) and near(ratio("frag"), 1.0, 1e-6) and near(ratio("death"), 1.0, 1e-6))
    p5 = pm(mets["z5"][0]) if mets["z5"] else {}
    r5 = (p5.get("dmg_taken") / p0.get("dmg_taken")) if p0.get("dmg_taken") and p5.get("dmg_taken") is not None else float("nan")
    check("the start weighs damage taken as dealt (zero-sum): at b1.2d's 0.8 (z5) update 1's actions are the same, damage dealt pays the same and damage "
          "taken between 0.8 and 1 of z0's ({:.4f}: his own splash and falls cost the full price at either weight, DMG_ENEMY_ONLY)".format(r5),
          all(same("z5", "z0", k, 0) for k in ("act", "logp")) and near(p5.get("dmg_dealt") or 0, p0.get("dmg_dealt") or -1, 1e-6) and 0.8 - 1e-3 <= r5 <= 1.0)
    fc_ = {k_: v_ for k_, v_ in p0.items() if any(w_ in k_ for w_ in ("shot", "fire", "switch", "blind")) and v_}
    check("no firing cost in the ledger ({}; shot cost a player-minute {})".format(fc_, mets["z0"][0].get("shot_cost_per_player_min") if mets["z0"] else None),
          not any(k_ != "switch" and "intent" not in k_ and v_ for k_, v_ in fc_.items() if "switch" not in k_) and not (mets["z0"][0].get("shot_cost_per_player_min") or 0))
    return done()


def step_live(D, tr, plan, limit_min):
    """while the trainer runs: after update n is in metrics.jsonl, write plan[n] (a dict) into live.json"""
    MET, t0, done_n = os.path.join(D, "metrics.jsonl"), time.time(), 0
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


def popen(cmd):
    return subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def smoke():
    import torch
    run = "scratch_18a_smoke" + TAG
    D = lay_out(run)
    c_ = make_cmd(run, D, 30000)                             # (--minutes counts the resumed run's minutes: --max-updates ends it)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 10")
    open(c_, "w", encoding="ascii", newline="").write(t_)
    plan = {1: dict(AIM3_W=0.5, AIM3_SIZE_A=0.7, AIM3_SIZE_B=0.18), 2: dict(AIM_END), 3: dict(H2_PG=0.33), 4: dict(H2_PG=0.67), 5: dict(H2_PG=1.0)}
    ok_ = step_live(D, popen(c_), plan, 90)
    log = open(os.path.join(ROOT, "data", "sim_runs", run + ".log"), encoding="utf-8", errors="replace").read() if ok_ else None
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    check("on the CPU", "device cpu" in log)
    check("the optimizer's state loaded from b1.2d's opt.pt", "optimizer: its state loaded from opt.pt" in log and "cold start" not in log)
    check("no weapon table, the keep choice not frozen, no REFUSED", "the pros' weapon table (1.7c)" not in log and "keep choice FROZEN" not in log and "REFUSED" not in log)
    M = metrics(D)
    check("8 or more updates ({})".format(len(M)), len(M) >= 8)
    for m in M:
        p_, h_ = pm(m), m.get("head2") or {}
        say("update {}: dmg {} / {} frag {} win {} | frags a match-minute {} | kl {} | head: credit {} hands {} raw {} cos {} | keep {}".format(
            m["update"], p_.get("dmg_dealt"), p_.get("dmg_taken"), p_.get("frag"), p_.get("win_part"), m.get("frags_per_match_min"), m.get("kl"),
            h_.get("credit"), h_.get("hands"), h_.get("raw"), h_.get("cos"), {k_: (m.get("keep") or {}).get(k_) for k_ in ("g", "kl")}))
    hd = [m.get("head2") or {} for m in M]
    check("the ledger on every update", all(pm(m) for m in M))
    check("no NaN in the head's lessons or the trainer's kl and entropy",
          all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd) and
          all(math.isfinite(float(m.get("kl") or 0.0)) and math.isfinite(float(m.get("entropy") or 0.0)) for m in M))
    check("the head's credit followed the dial to 1 ({})".format([h.get("credit") for h in hd]), hd and hd[0].get("credit") == 0.0 and hd[-1].get("credit") == 1.0)
    check("the head's own scores grew from zero and stay under 60 ({})".format([h.get("raw") for h in hd]),
          hd and (hd[-1].get("raw") or 0) > 0 and all((h.get("raw") or 0) < 60 for h in hd))
    check("the keep choice's share 0 in phase 1 ({})".format(sorted({(m.get("keep") or {}).get("g") for m in M})), all(((m.get("keep") or {}).get("g") or 0) == 0 for m in M))
    ck = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    L = ck.get("head2") or {}
    check("the save: the head with its add, the keep choice, no weapon part, no order; env WEAPON_OWN {}".format((ck.get("env_vars") or {}).get("WEAPON_OWN")),
          int(L.get("keep") or 0) == 2 and not L.get("weapon") and not L.get("cmb") and float(ck["model"]["head2.add"]) == 1.0)
    w_ = ck["model"]["enc.0.weight"][:, 980:]
    e_ = [float(ck["model"]["attn.emb.{}.weight".format(i_)].abs().max()) for i_, k_ in enumerate(ck["attn"]["kinds"]) if k_["name"] in ("order", "timers", "space", "targets")]
    say("after 10 updates: the hands' weights on the 73 newer inputs: order (10) {:.2e}, timers (4) {:.2e}, space and targets (59) {:.2e}; their tokens' first layers {}".format(
        float(w_[:, :10].abs().max()), float(w_[:, 10:14].abs().max()), float(w_[:, 14:].abs().max()), e_))
    check("the hands' weights on the order's and the map's inputs are still zero (COMBAT and SPACE_IN off: those inputs read zeros), so a check played "
          "with COMBAT on for 1.7a's update 90 changes nothing for him", float(w_[:, :10].abs().max()) == 0.0 and float(w_[:, 14:].abs().max()) == 0.0)
    # ---- the restart (the card's update 150): phase 2's switches, then the last two stages' dials at their ends
    n0 = len(M)
    lv = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    lv.update(INTENT_TEACH_W=0.0, SPEED_PAY=0.0, KEEP_G=0.975)
    json.dump(lv, open(os.path.join(D, "live.json"), "w", encoding="utf-8"))
    t2 = make_cmd(run, D, 30000, sets=(("INTENT_SWITCH", "0"), ("WEAPON_OWN", "1")))
    t_ = open(t2, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 3")
    open(t2, "w", encoding="ascii", newline="").write(t_)
    log2 = trainer(t2, run, 40)
    tail_ = (log2 or "")[len(log):] if log2 and log2.startswith(log[:200]) else (log2 or "")
    M2 = metrics(D)
    check("the restart from the save with its optimizer: loaded, no cold start, 3 more updates ({} -> {}), no REFUSED".format(n0, len(M2)),
          log2 is not None and "optimizer: its state loaded from opt.pt" in tail_ and "cold start" not in tail_ and len(M2) == n0 + 3 and "REFUSED" not in tail_)
    for m in M2[n0:]:
        k_ = m.get("keep") or {}
        say("update {}: kl {} | keep share {} re-decide {} quiet {} | head credit {} raw {}".format(
            m["update"], m.get("kl"), k_.get("g"), (k_.get("sim2") or {}).get("redecide"), (k_.get("sim2") or {}).get("redecide_quiet"),
            (m.get("head2") or {}).get("credit"), (m.get("head2") or {}).get("raw")))
    check("after the restart the keep choice decides at its share ({}) and nothing is NaN".format([(m.get("keep") or {}).get("g") for m in M2[n0:]]),
          M2[n0:] and all(abs(((m.get("keep") or {}).get("g") or 0) - 0.975) < 1e-6 for m in M2[n0 + 1:]) and
          all(math.isfinite(float(m.get("kl") or 0.0)) for m in M2[n0:]))
    ck2 = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False)
    check("the save after the restart records WEAPON_OWN 1 ({})".format((ck2.get("env_vars") or {}).get("WEAPON_OWN")), str((ck2.get("env_vars") or {}).get("WEAPON_OWN")) in ("1", "1.0"))
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    os.environ["PANEL_RUN"] = run
    import panel as P
    for tag_, opp_ in (("b12d", S0), ("17a", C17)):
        js = os.path.join(D, "watch", "chk_smoke_{}.json".format(tag_))
        cmd = [PY, "tools/duel_eval.py", "--run", run, "--policy", os.path.join(D, "policy.pt"), "--opp", "policy:" + opp_,
               "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"), "--map", "bloodrun", "--games", "2", "--minutes", "2", "--procs", "1", "--swap",
               "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600",
               "--opp-round", "600"]
        cmd += [x for s_ in P.settings(0.0, os.path.join(D, "policy.pt")) for x in ("--set", s_)]
        r = subprocess.run(cmd, cwd=ROOT, env=cenv(), capture_output=True, text=True)
        jv = json.load(open(js)) if os.path.exists(js) else {}
        v = (jv.get("maps") or {}).get("bloodrun") or {}
        say("check against {}: exit {}; {}".format(tag_, r.returncode, (r.stdout + r.stderr)[-400:]))
        check("a one-map check of the save against {} finished ({}-{})".format(tag_, v.get("won"), v.get("lost")), r.returncode == 0 and "won" in v)
    return done()


def live():
    run = "scratch_18a_live" + TAG
    D = lay_out(run)
    lv0 = json.load(open(os.path.join(D, "live.json"), encoding="utf-8"))
    check("the start's live.json carries the start values ({})".format({k_: lv0.get(k_) for k_ in START_DIALS}), all(lv0.get(k_) == v_ for k_, v_ in START_DIALS.items()))
    c_ = make_cmd(run, D, 30000)
    t_ = open(c_, encoding="ascii").read().replace("--overlap 1 --learn-nosync 1", "--overlap 1 --learn-nosync 1 --max-updates 5")   # (a dial written after
    open(c_, "w", encoding="ascii", newline="").write(t_)                                                                              # update 1 is played by 4)
    MID = dict(AIM3_W=0.5, AIM3_SIZE_A=0.7, AIM3_SIZE_B=0.18, H2_PG=0.4, INTENT_TEACH_W=0.5, SPEED_PAY=0.06, KEEP_G=0.5)
    ok_ = step_live(D, popen(c_), {1: MID}, 40)
    if not ok_:
        say("the trainer still runs after 40 min: left running")
        check("the trainer finished", False)
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
    import torch
    lv_ = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False).get("live") or {}
    sim_, trn_ = lv_.get("sim") or {}, lv_.get("trainer") or {}
    say("the save's record: sim {} | trainer {}".format({k_: sim_.get(k_) for k_ in MID if k_ in sim_}, {k_: trn_.get(k_) for k_ in MID if k_ in trn_}))
    check("the save's record of what was played carries every mid value (the simulators' or the trainer's part)",
          all((sim_.get(k_) is not None and abs(float(sim_[k_]) - v_) < 1e-9) or (trn_.get(k_) is not None and abs(float(trn_[k_]) - v_) < 1e-9) for k_, v_ in MID.items()))
    last = M[-1] if M else {}
    check("the last update played them: the head's credit {} the keep choice's share {}".format((last.get("head2") or {}).get("credit"), (last.get("keep") or {}).get("g")),
          abs(((last.get("head2") or {}).get("credit") or 0) - 0.4) < 1e-6 and abs(((last.get("keep") or {}).get("g") or 0) - 0.5) < 1e-6)
    return done()


def dry():
    """the dry run of the head's opening in today's trainer (the card: "1.3b's recipe behaves the same in today's trainer"): phase 1's command
    at FULL size (the graphics card, the 8 performance cores) for 10 updates on a scratch copy of the start, AIM3 left at its start values
    (so the numbers stand beside 1.3b's fifth dry run, docs/runs/b1.3/1.3b/dryrun_13b.log), the credit dial as that dry run's: 0 for updates
    1 to 4, 0.5 for 5 to 7, 1 from 8. No watcher, no ramp, no checks. Passes when: exit 0; 10 updates, none over 12 minutes; no NaN; the
    credit reached 1; the head's own scores and the hands' target scores under 60; his whole step (kl) under 0.1 every update; the head's
    clip share under 0.3."""
    run = "scratch_18a_dry" + TAG
    ps_ = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | Select-Object -ExpandProperty CommandLine"],
                         capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    if any("train_duel_rnn" in l_ for l_ in ps_.splitlines()):
        say("a trainer is running: not started")
        return 1
    D = lay_out(run)
    subprocess.check_call([PY, os.path.join(HERE, "make_files.py"), "1700", "1"], stdout=subprocess.DEVNULL)
    t = open(CMD, encoding="ascii").read().replace("\r\n", "\n")
    for a, b in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT={}".format(ROOT)), ("%LEARN% >> ", "%LEARN% --max-updates 10 >> ")):
        assert t.count(a) == 1, a
        t = t.replace(a, b)
    t = re.sub(r"--run duel_gru_\S+ ", "--run {} ".format(run), t)
    t = re.sub(r"data\\sim_runs\\duel_gru_[0-9a-z_]+\.log", lambda m_: "data" + BS + "sim_runs" + BS + run + ".log", t)
    assert not any(("duel_gru_1_" in x or "duel_gru_2_" in x) for x in t.split("\n") if not x.startswith("rem")), "a real run's name is left in the command"
    c_ = os.path.join(D, "dry.cmd")
    open(c_, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    ok_ = step_live(D, popen(c_), {4: dict(H2_PG=0.5), 7: dict(H2_PG=1.0)}, 170)
    log = open(os.path.join(ROOT, "data", "sim_runs", run + ".log"), encoding="utf-8", errors="replace").read() if ok_ else None
    check("the trainer exited 0", log is not None and log.rstrip().splitlines()[-1].strip() == "exit 0")
    if log is None:
        return done()
    check("on the graphics card; the optimizer's state loaded, not a cold start; no REFUSED", "device cuda" in log and "optimizer: its state loaded from opt.pt" in log
          and "cold start" not in log and "REFUSED" not in log)
    M = metrics(D)
    check("10 updates ({})".format(len(M)), len(M) == 10)
    mins = [round(M[i]["minutes"] - M[i - 1]["minutes"], 2) for i in range(1, len(M))]
    check("no update over 12 minutes (minutes an update: {})".format(mins), mins and max(mins) < 12)
    for m in M:
        h_ = m.get("head2") or {}
        say("update {}: kl {} | credit {} | hands {} raw {} cos {} sum {} | clip share {} | frags a match-minute {} | in hand rl {} lg {} rg {}".format(
            m["update"], m.get("kl"), h_.get("credit"), h_.get("hands"), h_.get("raw"), h_.get("cos"), h_.get("sum"), h_.get("clip_share"),
            m.get("frags_per_match_min"), *[((m.get("v15") or {}).get("in_hand_games") or {}).get(w_) for w_ in ("rl", "lg", "rg")]))
    hd = [m.get("head2") or {} for m in M]
    check("no NaN", all(math.isfinite(float(m.get("kl") or 0.0)) and math.isfinite(float(m.get("entropy") or 0.0)) for m in M) and
          all(math.isfinite(h.get("pg_loss") or 0.0) and math.isfinite(h.get("v_loss") or 0.0) for h in hd))
    check("the credit reached 1 ({})".format([h.get("credit") for h in hd]), hd and hd[-1].get("credit") == 1.0)
    check("the head's own scores under 60 (largest {}) and the hands' target scores under 60 (largest {})".format(
        max((h.get("raw") or 0) for h in hd), max((h.get("hands") or 0) for h in hd)), all((h.get("raw") or 0) < 60 and (h.get("hands") or 0) < 60 for h in hd))
    check("his whole step (kl) under 0.1 every update (largest {})".format(max(float(m.get("kl") or 0) for m in M)), all(float(m.get("kl") or 0) < 0.1 for m in M))
    check("the head's clip share under 0.3 (largest {})".format(max((h.get("clip_share") or 0) for h in hd)), all((h.get("clip_share") or 0) < 0.3 for h in hd))
    say("1.3b's fifth dry run (the same dial, AIM2, the firing cost on): his step 0.031 to 0.041; the hands' part 21.6 to 22.7; the head's part 0.06 -> 2.9; the cosine -0.16 to 0")
    return done()


if __name__ == "__main__":
    sys.exit({"start": start, "ident": ident, "smoke": smoke, "live": live, "dry": dry}[sys.argv[1]]())
