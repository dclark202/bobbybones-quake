"""v0.6.1's watch (from v0.5.1's, scratchpad v050/watch_v051.py). Every save is kept (keep/policy_<n>.pt, n = the metrics line).
  1. games: 160 ten-minute games on ten maps, seats swapped, against the previous best (CTRL_PREV, default v0.6.0's end; every
     fourth check the reference CTRL_REF, default v0.4.2b's end), both seats at !aim default with the panel's settings
     (panel_v061.settings: the run's live PERCEPT_SPEED and caps, PANEL_SETS for v0.6.0's aim switches); the first at update 10,
     then one every CHECK_EVERY (10) updates when none still runs. Written to checks_prev.jsonl / checks_ref.jsonl; the stop rule (under 45%, or two under 50%).
  2. the behaviour panel (panel_v061.py) at EVERY save.
The fix against v0.5.1's watch (owner, 2026-10-27: panels were skipped while a check ran, so the ramp, which waits for a panel
of a save after its step, waited for the check's end): the games and the panel run in threads of their own, each skipped only
while one of its own kind still runs; a panel that starts while a check plays runs at PANEL_PAR_BUSY (3) games at once instead
of 6, and the fixed control's panel is played once per PERCEPT_SPEED (panel_v061: cached), so a panel costs half of v0.5.1's.
A save whose panel was skipped is written down ("panel skipped: a panel still runs").
Usage: watch_v061.py [run] (default duel_gru_v0_6_1)."""
import importlib, json, os, shutil, subprocess, sys, threading, time
ROOT_ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (the repo root: tools/run/ is two down)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panel as P

SR = os.path.join(ROOT_, "data", "sim_runs")
RUN = sys.argv[1] if len(sys.argv) > 1 else "duel_gru_v0_6_0"
OUT = os.path.join(SR, RUN)
PY = (os.environ.get("BB_PY") or r"C:\Users\dacla\anaconda3\python.exe")
CTRL_PREV = os.environ.get("CTRL_PREV") or os.path.join(SR, "duel_gru_v0_4_2", "keep", "policy_end_v042.pt")
CTRL_REF = os.environ.get("CTRL_REF") or os.path.join(SR, "duel_gru_v0_4_2", "keep", "policy_end_v042.pt")
PREV_LABEL = os.environ.get("CTRL_PREV_LABEL") or "v0.4.2b's end (the start, both at the new default)"
REF_LABEL = os.environ.get("CTRL_REF_LABEL") or "v0.4.2b's end (reference)"
PAR_BUSY = int(os.environ.get("PANEL_PAR_BUSY") or 3)
CHECK_EVERY = int(os.environ.get("CHECK_EVERY") or 20)   # (v0.6.1: the ramp steps every 10 updates and waits for a check after its step)
MAPS = ["bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure"]
WD = os.path.join(SR, RUN, "watch")
os.makedirs(WD, exist_ok=True)
LOCK = threading.Lock()


def say(*a):
    line = time.strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    with LOCK:
        print(line, flush=True)
        with open(os.path.join(WD, "watch.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")


def lines():
    p = os.path.join(OUT, "metrics.jsonl")
    return [json.loads(x) for x in open(p) if x.strip()] if os.path.exists(p) else []


def live_ps():
    try:
        return float(json.load(open(os.path.join(OUT, "live.json"))).get("PERCEPT_SPEED") or 0.0)
    except Exception:
        return 0.0


def games(pol, upd, ctrl, label, ps):
    sets = P.settings(ps)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1")
    res = {}
    tag = "prev" if ctrl == CTRL_PREV else "ref"
    for w in range(0, len(MAPS), 5):
        jobs = []
        for mp in MAPS[w:w + 5]:
            js = os.path.join(WD, "chk_{}_{}_{}.json".format(upd, tag, mp))
            cmd = [PY, "tools/duel_eval.py", "--run", RUN, "--policy", pol, "--opp", "policy:" + ctrl, "--opp-inputs",
                   os.path.join(P.CODE, "docs", "INPUTS.csv"), "--map", mp, "--games", "16", "--minutes", "10", "--procs", "2", "--swap",
                   "--json", js, "--react-ms", "125", "--acquire-ms", "225", "--opp-react-ms", "125", "--opp-acquire-ms", "225",
                   "--round", "600", "--opp-round", "600"]
            cmd += [x for s_ in sets for x in ("--set", s_)]
            jobs.append((mp, js, subprocess.Popen(cmd, cwd=P.CODE, env=env, creationflags=0x4000 | 0x08000000, stdout=open(js + ".log", "w"),
                                                  stderr=subprocess.STDOUT)))
        for mp, js, p in jobs:
            p.wait()
            try:
                v = json.load(open(js))["maps"][mp]
                res[mp] = dict(share=v["frag_share"], won=v["won"], lost=v["lost"], hit=v["he"]["hit_rate"], spm=v["he"]["shots_per_min"])
            except Exception as e:                           # noqa: BLE001
                res[mp] = dict(error=str(e))
    ok = [v for v in res.values() if "share" in v]
    mean = sum(v["share"] for v in ok) / max(1, len(ok))
    W_, L_ = sum(v["won"] for v in ok), sum(v["lost"] for v in ok)
    say("check update", upd, "against", label, "(ten maps, PERCEPT_SPEED {}):".format(ps), "record {}-{}".format(W_, L_),
        "win rate {:.1%}".format(W_ / max(1, W_ + L_)), "frag share {:.1%}".format(mean),
        "|", {k: "{}-{} {:.0%}".format(v["won"], v["lost"], v["share"]) for k, v in res.items() if "share" in v})
    with open(os.path.join(WD, "checks_prev.jsonl" if ctrl == CTRL_PREV else "checks_ref.jsonl"), "a") as f:
        f.write(json.dumps(dict(update=upd, mean=mean, won=W_, lost=L_, percept_speed=ps, maps=res)) + "\n")


def rule():
    p = os.path.join(WD, "checks_prev.jsonl")
    if not os.path.exists(p):
        return
    wr = [d["won"] / max(1, d["won"] + d["lost"]) for d in (json.loads(x) for x in open(p))]
    why = []
    if wr and wr[-1] < 0.45:
        why.append("the last check under 45% against the previous best")
    if len(wr) >= 2 and wr[-1] < 0.5 and wr[-2] < 0.5:
        why.append("two checks in a row under 50%")
    if why:
        say("STOP RULE:", "; ".join(why), "(written down: the ramp steps back; the owner and Claude decide the rest)")


def check_games(pol, upd, ctrl, label):
    games(pol, upd, ctrl, label, live_ps())
    if ctrl == CTRL_PREV:
        rule()


def check_panel(pol, upd, busy):
    ps = live_ps()
    importlib.reload(P)                                      # (the panel's triggers can change between checks)
    P.PAR = PAR_BUSY if busy() else P.PAR
    r = P.run(pol, "u{}".format(upd), ps, root=os.path.join(WD, "panel"))
    with open(os.path.join(WD, "behaviour.jsonl"), "a") as f:
        f.write(json.dumps(dict(update=upd, green=r["green"], reasons=r["reasons"], save=r["save"], ctrl=r["ctrl"], percept_speed=ps,
                                report=r.get("report"))) + "\n")
    if r["green"]:
        say("behaviour panel u{}: GREEN".format(upd), "|", json.dumps(r["save"])[:700], "| report", json.dumps(r.get("report"))[:600])
    else:
        say("BEHAVIOUR RED u{}:".format(upd), "; ".join(r["reasons"]), "|", json.dumps(r["save"])[:700], "| report", json.dumps(r.get("report"))[:600])


def collapse_line(L):
    if not L:
        return ""
    m = lambda f: sum(f(d) for d in L) / len(L)              # noqa: E731
    ih = {w: m(lambda d: ((d.get("hand_teach") or {}).get("in_hand") or {}).get(w, 0.0)) for w in ("rl", "rg", "lg", "pg", "mg")}
    pk = m(lambda d: sum((d.get("pickups_per_player_min") or {}).get(k_, 0.0) for k_ in ("mega", "ra")))
    wb = L[-1].get("win_blend") or {}
    ws = L[-1].get("win_shape") or {}
    vw = L[-1].get("value_warm") or {}
    return ("in hand " + " ".join("{} {:.2f}".format(w, v) for w, v in ih.items()) + " | mega+red/min {:.2f}".format(pk)
            + " | kl {:.4f}".format(L[-1].get("kl", 0.0)) + " | win part G1 size {} combat size {} | shaping size {} | value warm-up {}".format(
                wb.get("win_g1_size"), wb.get("combat_size"), ws.get("size"), vw or "off"))


def main():
    pol = os.path.join(OUT, "policy.pt")
    keep = os.path.join(OUT, "keep")
    os.makedirs(keep, exist_ok=True)
    say("watch attached to", RUN, "| previous best", CTRL_PREV, "| reference", CTRL_REF)
    mt, n, last, stalled = os.path.getmtime(pol), len(lines()), time.time(), False
    gth, pth = [], []
    last_chk, n_chk = -100, 0
    busy = lambda: any(t_.is_alive() for t_ in gth)          # noqa: E731
    while True:
        time.sleep(20)
        L = lines()
        if len(L) != n:
            n, last, stalled = len(L), time.time(), False
        if os.path.getmtime(pol) > mt + 60:
            time.sleep(20)
            mt = os.path.getmtime(pol)
            k = os.path.join(keep, "policy_{}.pt".format(n))
            shutil.copy(pol, k)
            say("update", n, collapse_line(L[-10:]))
            want_games = n == 10 or (n > 10 and n - last_chk >= CHECK_EVERY)
            if want_games and busy():
                say("save", n, "games not started: a check still runs (the next save takes its turn)")
            elif want_games:
                n_chk += 1
                ctrl_, lab_ = (CTRL_REF, REF_LABEL) if n_chk % 4 == 0 else (CTRL_PREV, PREV_LABEL)
                last_chk = n
                t = threading.Thread(target=check_games, args=(k, n, ctrl_, lab_))
                t.start()
                gth.append(t)
            if any(t_.is_alive() for t_ in pth):
                say("save", n, "panel skipped: a panel still runs")
            else:
                t = threading.Thread(target=check_panel, args=(k, n, busy))
                t.start()
                pth.append(t)
        if time.time() - last > 15 * 60 and not stalled:
            say("STALL: no new update for 15 min at update", n)
            stalled = True
        if time.time() - last > 45 * 60:
            break
    for t in gth + pth:
        t.join()
    say("watch done")


if __name__ == "__main__":
    main()
