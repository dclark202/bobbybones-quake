"""2.0b's dry run (CLAUDE.md: a new part of the network and a new pay pass ten updates and a check against the control before a start): the
run's own command at full size on the card, in a scratch folder (data/sim_runs/scratch_20b_dry<TAG>; nothing of a real run touched, nothing
deleted), from the start (2.0a's end given 2.0b's parts) with its optimizer and the league's files, with everything OPEN from update 0 (the
run's end state, the worst case for the first step): SPACE_GATE 1, EDGE_PAY 0.0005, the two new tokens' gate open (--gate-start 0).

    python docs/runs/2.0/2.0b/dry.py train [--updates 10]     ten updates; prints each update's step (kl), ledger and readout
    python docs/runs/2.0/2.0b/dry.py check [--games 20]       the last save against 1.7a's update 90 (the control) and against the start
                                                             (2.0a's end), 20 games a map on the ten maps, as the run's checks play them
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tests as T                                             # noqa: E402  (its scratch helpers; nothing of it runs at import)

ROOT, PY, BS = T.ROOT, T.PY, "\\"
RUN = "scratch_20b_dry" + T.TAG
D = os.path.join(ROOT, "data", "sim_runs", RUN)
ANCH = ("anchor_17a.pt", "anchor_16a.pt", "anchor_15a.pt", "anchor_13b.pt", "anchor_b12d.pt", "anchor_b11.pt", "anchor_v060_end.pt")
CTRL = os.path.join(ROOT, "data", "sim_runs", "duel_gru_1_7a", "keep", "policy_end_17a.pt")
MAPS = "bloodrun,aerowalk,lostworld,sinister,furiousheights,battleforged,campgrounds,hektik,toxicity,cure".split(",")


def train(a):
    if os.path.exists(D):
        raise SystemExit(D + " is there: not started (nothing deleted; TEST_TAG for another)")
    os.makedirs(T.ST, exist_ok=True)
    T.widen(T.S0, T.S1, "add")
    for d_ in ("snapshots", "keep", "watch"):
        os.makedirs(os.path.join(D, d_))
    shutil.copy2(T.S1, os.path.join(D, "policy.pt"))
    shutil.copy2(T.S0O, os.path.join(D, "opt.pt"))
    for name, src in [(n, os.path.join(T.ANCH, n)) for n in ANCH] + [("anchor_20a.pt", T.S0)]:
        w_ = os.path.join(T.ST, "w_" + name)
        T.widen(src, w_)
        shutil.copy2(w_, os.path.join(D, "snapshots", name))
    shutil.copy2(os.path.join(T.R0, "live_settings.env"), os.path.join(D, "live_settings.env"))
    out = os.path.join(D, "live.json")
    subprocess.check_call([PY, os.path.join(HERE, "start_live.py"), os.path.join(T.R0, "live.json"), os.path.join(T.R0, "live_applied.json"), out],
                          env=T.cenv(), stdout=subprocess.DEVNULL)
    lv = json.load(open(out, encoding="utf-8"))
    lv.update(T.END_DIALS)
    json.dump(lv, open(out, "w", encoding="utf-8"))
    t = open(T.CMD, encoding="ascii").read().replace("\r\n", "\n")
    for a_, b_ in (("set ROOT=%~dp0.." + BS + ".." + BS + ".." + BS + "..", "set ROOT=" + ROOT), ("%LEARN% >> ", "%LEARN% --max-updates {} >> ".format(a.updates))):
        assert t.count(a_) == 1, a_
        t = t.replace(a_, b_)
    t = re.sub(r"--run duel_gru_\S+ ", "--run {} ".format(RUN), t)
    t = re.sub(r"--gate-start [0-9.]+ ", "--gate-start 0 ", t)
    t = re.sub(r"--minutes \d+ --gamma", "--minutes 99999 --gamma", t)
    t = re.sub(r"data\\sim_runs\\duel_gru_[0-9a-z_]+\.log", lambda m_: "data" + BS + "sim_runs" + BS + RUN + ".log", t)
    assert not any("duel_gru_2_0b" in x for x in t.split("\n") if not x.startswith("rem")), "the real run's name is left in the dry command"
    cmd = os.path.join(D, "dry.cmd")
    open(cmd, "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
    shutil.copy2(os.path.join(HERE, "aim2_env.cmd"), os.path.join(D, "aim2_env.cmd"))
    t0 = time.time()
    tr = subprocess.Popen(["cmd.exe", "/c", cmd], cwd=ROOT, env=dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1"), stdin=subprocess.DEVNULL)
    seen = 0
    while tr.poll() is None:
        time.sleep(20)
        M = T.metrics(D)
        for m in M[seen:]:
            p_ = T.pm(m)
            T.say("update {} ({:.0f} min): kl {} entropy {} | frags a match-minute {} | dmg {} frag {} death {} win {} edge {} (share {}) | space {} thr>20 {} | keep {}".format(
                m["update"], (time.time() - t0) / 60, m.get("kl"), m.get("entropy"), m.get("frags_per_match_min"), p_.get("dmg_dealt"), p_.get("frag"),
                p_.get("death"), p_.get("win_part"), p_.get("edge"), T.ss(m).get("edge"), T.space_line(m), (m.get("space") or {}).get("thr_over20"),
                {k_: (m.get("keep") or {}).get(k_) for k_ in ("g", "kl")}))
        seen = len(M)
    log = open(os.path.join(ROOT, "data", "sim_runs", RUN + ".log"), encoding="utf-8", errors="replace").read()
    T.say("the trainer ended after {:.0f} min: {}".format((time.time() - t0) / 60, log.rstrip().splitlines()[-1]))
    for pat in ("optimizer: ", "gate: ", "space (2.0b)", "space: the ring", "REFUSED", "device "):
        for ln in [x for x in log.split("\n") if pat in x][:4]:
            T.say("log: " + ln[:260])
    M = T.metrics(D)
    T.check("{} updates, the trainer exited 0".format(len(M)), len(M) >= a.updates and log.rstrip().splitlines()[-1].strip() == "exit 0")
    T.check("no REFUSED live file; the optimizer loaded, no cold start", "REFUSED" not in log and "optimizer: its state loaded from opt.pt" in log and "cold start" not in log)
    kls = [float(m.get("kl") or 0.0) for m in M]
    T.say("the step by update (kl): {}; 2.0a's last updates read about 0.029".format(kls))
    T.check("the step never over three times 2.0a's (kl under 0.09 on every update)", kls and max(kls) < 0.09)
    return T.done()


def check(a):
    sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
    os.environ["PANEL_RUN"] = RUN
    import panel as P
    pol = os.path.join(D, "policy.pt")
    sets_ = P.settings(0.0, pol)
    T.say("the check's settings of 2.0b: {}".format([x for x in sets_ if x.split("=")[0].startswith(("SPACE", "EDGE", "COVER"))]))
    res = {}
    for opp, nm in [x for x in ((CTRL, "the control (1.7a's update 90)"), (T.S0, "the start (2.0a's end)")) if a.opps == "both" or x[0] == CTRL]:
        jobs = []
        for mp in MAPS:
            js = os.path.join(D, "watch", "dry_{}_{}.json".format("ctrl" if opp == CTRL else "start", mp))
            cmd = [PY, "tools/duel_eval.py", "--run", RUN, "--policy", pol, "--opp", "policy:" + opp, "--opp-inputs", os.path.join(ROOT, "docs", "INPUTS.csv"),
                   "--map", mp, "--games", str(a.games), "--minutes", "10", "--procs", "2", "--swap", "--json", js, "--react-ms", "125", "--acquire-ms", "225",
                   "--opp-react-ms", "125", "--opp-acquire-ms", "225", "--round", "600", "--opp-round", "600"]
            cmd += [x for s_ in sets_ for x in ("--set", s_)]
            jobs.append((mp, js, cmd))
        run_, won, lost = [], 0, 0
        for mp, js, cmd in jobs:
            while sum(p.poll() is None for _, _, p in run_) >= a.par:
                time.sleep(5)
            p = subprocess.Popen(cmd, cwd=ROOT, env=T.cenv(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                 creationflags=0x4000)
            try:
                import ctypes
                h = ctypes.windll.kernel32.OpenProcess(0x0200 | 0x0400, False, p.pid)
                ctypes.windll.kernel32.SetProcessAffinityMask(ctypes.c_void_p(h), ctypes.c_size_t(int(a.mask, 16)))   # (--mask: 3C3C the 8 efficiency cores beside a run; C3FFF 16 cores with nothing running)
            except Exception:                                 # noqa: BLE001
                pass
            run_.append((mp, js, p))
        for mp, js, p in run_:
            p.wait()
            v = ((json.load(open(js)).get("maps") or {}).get(mp) or {}) if os.path.exists(js) else {}
            T.say("{}: {} {}-{}".format(nm, mp, v.get("won"), v.get("lost")))
            won += int(v.get("won") or 0)
            lost += int(v.get("lost") or 0)
        res[nm] = (won, lost)
        T.say("AGAINST {}: {}-{} = {:.1%} of decided games".format(nm, won, lost, won / max(1, won + lost)))
    w, l_ = res["the control (1.7a's update 90)"]
    T.check("against the control not under the start's own level less the noise (2.0a's end read 42%; here {:.1%}; the alarm is under 35%)".format(w / max(1, w + l_)),
            w / max(1, w + l_) >= 0.35)
    return T.done()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("train", "check"))
    ap.add_argument("--updates", type=int, default=10)
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--par", type=int, default=4)
    ap.add_argument("--opps", default="both", choices=("both", "control"))
    ap.add_argument("--mask", default="3C3C")
    a_ = ap.parse_args()
    sys.exit({"train": train, "check": check}[a_.cmd](a_))
