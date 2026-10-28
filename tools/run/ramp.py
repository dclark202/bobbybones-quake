"""v0.6.1's ramp (the scratchpad's ramp_v061.py of 2026-10-28, its paths made the repo's; docs/runs/v0.6.1/WINPAY_v0.6.1.md): pay by win chance only, the same two overlapping fades as v0.5.1,
with the critic's warm-up first, the shaping beside the win part, and the checks in the gate.
  step k:  WIN_W = min(1, 0.1 k)            (the fight's pay -> the change in his chance of winning)
           FADE_V = clip(0.125 (k - 4), 0, 1)   (every other game pay; from step 5)
           WIN_SHAPE_K = RAMP_K x WIN_W     (the shaping grows with the win part: at every step a 100-damage hit pays about
                                             0.55 of a frag, as under the flat pay; RAMP_K 1.0, the ledger's choice)
  k = 0 .. 12.
WIN_GAIN: RAMP_GAIN (set from v0.6.0's settled counters before the start, tools winsize_v061.py) or, unset, sized here from the
run's own win_blend counters after RAMP_SKIP (20) updates (the start-up transient: v0.5.1 read 5.1 -> 3.1 in its first 10),
the mean of the next 10; kept within 0.25 .. 4.
Step 1 is taken with the critic's warm-up: WIN_W 0.1, WIN_SHAPE_K 0.1 x RAMP_K and VALUE_WARM = RAMP_WARM (10) at once, so the
value outputs learn the new pay for 10 updates while the policy stands still; the ramp writes VALUE_WARM back to 0 when the
metrics say the warm-up is over (value_warm.left 0) so a restart does not start it again. RAMP_WARM_EVERY=1: a warm-up at every
step (off by default).
The gate for the next step: RAMP_EVERY_N (10) updates and RAMP_MIN_S (25 min, the owner's "original 25 m") since the last
step (the warm-up's updates do not count), a behaviour panel of a save made after the step (red on the rockets flag only does
not hold: owner 2026-10-27 12:50), and the games against the previous best (the watcher's checks_prev.jsonl), read when a check
of a save after the step is there:
  GREEN panel and the last check >= 50%                  -> step up
  RED panel (other than rockets) once, or last check < 50% -> hold
  RED twice with a reason of the same kind, or the last check < 45%, or two checks in a row < 50% -> one step back.
No check after the step yet: the panel alone decides a step up only while RAMP_PANEL_ONLY=1 (default 0: wait for the check).
Logs data/sim_runs/<run>/watch/ramp.log and a RAMP line in the watcher's watch.log (tools/run/watch.py's folder: behaviour.jsonl,
checks_prev.jsonl). Usage: python tools/run/ramp.py [run]"""
import json, os, sys, time

RUN = sys.argv[1] if len(sys.argv) > 1 else "duel_gru_v0_6_1"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.environ.get("RAMP_DIR") or os.path.join(ROOT, "data", "sim_runs", RUN)
LIVE, MET = os.path.join(D, "live.json"), os.path.join(D, "metrics.jsonl")
WD = os.environ.get("RAMP_WD") or os.path.join(D, "watch")
BEH, CHK = os.path.join(WD, "behaviour.jsonl"), os.path.join(WD, "checks_prev.jsonl")
EVERY_N, EVERY_S, LAST = int(os.environ.get("RAMP_EVERY_N") or 10), int(float(os.environ.get("RAMP_MIN_S") or 25 * 60)), 12
SLEEP = float(os.environ.get("RAMP_SLEEP") or 60)
K_FULL = float(os.environ.get("RAMP_K") or 1.0)
WARM = int(os.environ.get("RAMP_WARM") or 10)
WARM_EVERY = os.environ.get("RAMP_WARM_EVERY") == "1"
SKIP = int(os.environ.get("RAMP_SKIP") or 20)
PANEL_ONLY = os.environ.get("RAMP_PANEL_ONLY") == "1"
ALWAYS = os.environ.get("RAMP_ALWAYS") == "1"                 # (owner, 2026-10-27: "Keep the fade going, unless we get a collapse in
                                                            # performance"; "just don't ever stop the run"): step 1 at once, then a step
                                                            # every EVERY_N updates and EVERY_S whatever the panel and the checks say;
                                                            # the checks are only logged (the owner decides on a flag)
KINDS = ("targets", "camping", "roaming", "hunting", "items", "rockets", "passive")
IGNORE = {"rockets"}                                        # (owner, 10-27 12:50: the rockets flag predates the win pay; it does not hold the ramp)


def sched(k):
    w = round(min(1.0, 0.1 * k), 4)
    return w, round(min(1.0, max(0.0, 0.125 * (k - 4))), 4), round(K_FULL * w, 4)


def log(s):
    line = time.strftime("%m-%d %H:%M:%S ") + s
    os.makedirs(WD, exist_ok=True)
    with open(os.path.join(WD, "ramp.log"), "a") as f:
        f.write(line + "\n")
    with open(os.path.join(WD, "watch.log"), "a") as f:
        f.write(line + "\n")


def jl(p):
    try:
        return [json.loads(x) for x in open(p) if x.strip()]
    except FileNotFoundError:
        return []


def put(**kw):
    d = json.load(open(LIVE, encoding="utf-8"))
    d.update(kw)
    open(LIVE + ".tmp", "w", encoding="utf-8").write(json.dumps(d))
    os.replace(LIVE + ".tmp", LIVE)


def kinds(p):
    return {k for k in KINDS for r in p.get("reasons", []) if r.startswith(k)}


def gain():
    L = [d["win_blend"] for d in jl(MET)[SKIP:] if d.get("win_blend") and d["win_blend"].get("win_g1_size")]
    if len(L) < 10:
        return None
    L = L[:10]
    c = sum(x["combat_size"] for x in L) / len(L)
    w = sum(x["win_g1_size"] for x in L) / len(L)
    return round(min(4.0, max(0.25, c / max(1e-9, w))) * 20) / 20, c, w


def warm_left():
    L = jl(MET)
    vw = (L[-1].get("value_warm") if L else None) or {}
    return vw


def step_to(k, why, warm):
    w, v, kk = sched(k)
    kw = dict(WIN_W=w, FADE_V=v, WIN_SHAPE_K=kk)
    if warm:
        kw["VALUE_WARM"] = WARM
    put(**kw)
    log("RAMP step {}: WIN_W {} FADE_V {} WIN_SHAPE_K {}{} ({})".format(k, w, v, kk, " + critic warm-up {} updates".format(WARM) if warm else "", why))


k = int(os.environ.get("RAMP_START") or 0)
w0, v0, k0 = sched(k)
cur = json.load(open(LIVE, encoding="utf-8"))
assert float(cur.get("WIN_W", 0)) == w0 and float(cur.get("FADE_V", 0)) == v0, "the run is not at its step: " + str(cur)
gain_set = k > 0 or bool(os.environ.get("RAMP_GAIN"))
if os.environ.get("RAMP_GAIN") and k == 0:
    put(WIN_GAIN=float(os.environ["RAMP_GAIN"]))
    log("WIN_GAIN -> {} (RAMP_GAIN: from v0.6.0's settled counters)".format(os.environ["RAMP_GAIN"]))
log(("ramp on for {}: a step every {} updates and at least {} min, " + ("on the clock (RAMP_ALWAYS)" if ALWAYS else "panel- and check-gated") + "; shaping {} x WIN_W; step {} = WIN_W {} FADE_V {} K {}").format(
    RUN, EVERY_N, EVERY_S // 60, K_FULL, k, w0, v0, k0))
n_last, t_last = len(jl(MET)), time.time()
last_red, warming = None, False
if ALWAYS and k == 0 and gain_set:
    k = 1
    step_to(k, "at the start (RAMP_ALWAYS)", WARM > 0)
    warming = WARM > 0
while k < LAST:
    time.sleep(SLEEP)
    n = len(jl(MET))
    if not gain_set:
        g = gain() if n >= SKIP + 10 else None
        if g is not None:
            put(WIN_GAIN=g[0])
            gain_set = True
            log("WIN_GAIN -> {} (combat size {:.3f} / the win part's at G = 1 {:.3f} a player-minute, updates {}..{})".format(g[0], g[1], g[2], SKIP + 1, SKIP + 10))
        continue
    if warming:                                             # (the critic's warm-up: the policy stands still; its updates do not count)
        vw = warm_left()
        if vw.get("n") and not vw.get("on") and int(vw.get("left", 1)) == 0:
            put(VALUE_WARM=0)
            warming = False
            n_last, t_last = n, time.time()
            log("critic warm-up over at update {} (VALUE_WARM back to 0); the step's clock starts now".format(n))
        continue
    if n < n_last + EVERY_N or time.time() - t_last < EVERY_S:
        continue
    if ALWAYS:
        allc = jl(CHK)
        last_ = "{} at u{}".format("{:.1%}".format(allc[-1]["won"] / max(1, allc[-1]["won"] + allc[-1]["lost"])), allc[-1].get("update")) if allc else "none yet"
        k += 1
        warm_ = (k == 1 or WARM_EVERY) and WARM > 0             # (step 1 always with the warm-up, also when WIN_GAIN was sized in the run)
        step_to(k, "on the clock (RAMP_ALWAYS: {} updates, {} min); last check {}".format(n - n_last, int((time.time() - t_last) // 60), last_), warm_)
        warming = warm_
        n_last, t_last = n, time.time()
        continue
    P = [p for p in jl(BEH) if int(p.get("update", 0)) > n_last]
    if not P:
        continue
    p = P[-1]
    C = [c for c in jl(CHK) if int(c.get("update", 0)) > n_last]
    allc = [c["won"] / max(1, c["won"] + c["lost"]) for c in jl(CHK)]
    wr = C[-1]["won"] / max(1, C[-1]["won"] + C[-1]["lost"]) if C else None
    if wr is None and not PANEL_ONLY:
        continue
    ks = kinds(p) - IGNORE
    green = p.get("green") or not ks
    back = (wr is not None and wr < 0.45) or (wr is not None and len(allc) >= 2 and allc[-1] < 0.5 and allc[-2] < 0.5) \
        or (not green and last_red is not None and bool(ks & last_red))
    if back and k > 0:
        k -= 1
        step_to(k, "STEP BACK: panel u{} {}, check {}".format(p["update"], "; ".join(p.get("reasons", [])) or "green",
                                                             "{:.1%}".format(wr) if wr is not None else "none"), False)
        last_red = None
    elif green and (wr is None or wr >= 0.5):
        k += 1
        warm_ = (k == 1 or WARM_EVERY) and WARM > 0
        step_to(k, "panel u{} {}, check {}".format(p["update"], "green" if p.get("green") else "red on rockets only: not held (owner)",
                                                   "{:.1%}".format(wr) if wr is not None else "none (RAMP_PANEL_ONLY)"), warm_)
        warming = warm_
        last_red = None
    else:
        log("RAMP HOLD at step {} (panel u{} {}; check {})".format(k, p["update"], "; ".join(p.get("reasons", [])) or "green",
                                                                 "{:.1%}".format(wr) if wr is not None else "none"))
        last_red = ks or last_red
    n_last, t_last = n, time.time()
log("ramp done: WIN_W {} FADE_V {} WIN_SHAPE_K {} (win chance only, with the shaping)".format(*sched(k)))
