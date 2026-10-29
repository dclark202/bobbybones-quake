"""v0.6.2's ramp (owner, 2026-10-29; docs/runs/v0.6.2/CARD.md): the strategy head replaces the item rule, one after the other,
on the clock (the owner: "keep going unless a collapse"), the checks and the behaviour panel only logged.
  shut     the head's gate held at 0 (live H2_GATE_CAP 0) for RAMP_SHUT_N updates (10): its own value learns the win pay
           while it changes nothing
  phase 1  H2_GATE_CAP 0.1 a step to 1.0 (the trainer's --head2-open 1: the gate follows the cap within a minute), the item
           rule at full weight (INTENT_TEACH_W 1)
  open     the first save (keep/policy_<N>.pt, every 10 updates) a full RAMP_EVERY_N updates after the cap reached 1 is kept
           as keep/policy_head_open_v062.pt: the owner's play test of the head open; training goes on, and phase 2 starts
  phase 2  INTENT_TEACH_W 0.1 a step down to 0 (the item rule's label and its floor), the head open
A step every RAMP_EVERY_N (10) updates and at least RAMP_MIN_S (25 min) since the last. RAMP_START_CAP / RAMP_START_IT resume
at a step (live.json must already be there). Logs <run>/watch/ramp.log and a RAMP line in watch.log.
    python tools/run/ramp_head.py [run]"""
import json
import os
import shutil
import sys
import time

RUN = sys.argv[1] if len(sys.argv) > 1 else "duel_gru_v0_6_2"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.environ.get("RAMP_DIR") or os.path.join(ROOT, "data", "sim_runs", RUN)
LIVE, MET, KEEP = os.path.join(D, "live.json"), os.path.join(D, "metrics.jsonl"), os.path.join(D, "keep")
WD = os.environ.get("RAMP_WD") or os.path.join(D, "watch")
CHK = os.path.join(WD, "checks_prev.jsonl")
EVERY_N = int(os.environ.get("RAMP_EVERY_N") or 10)
EVERY_S = int(float(os.environ.get("RAMP_MIN_S") or 25 * 60))
SHUT_N = int(os.environ.get("RAMP_SHUT_N") or 10)
SLEEP = float(os.environ.get("RAMP_SLEEP") or 60)
STEP = 0.1


def log(s):
    line = time.strftime("%m-%d %H:%M:%S ") + s
    os.makedirs(WD, exist_ok=True)
    for f in ("ramp.log", "watch.log"):
        with open(os.path.join(WD, f), "a") as fh:
            fh.write(line + "\n")


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


def last_check():
    c = jl(CHK)
    return "{:.1%} at u{}".format(c[-1]["won"] / max(1, c[-1]["won"] + c[-1]["lost"]), c[-1].get("update")) if c else "none yet"


def updates():
    L = jl(MET)
    return int(L[-1]["update"]) if L else 0


cap = round(float(os.environ.get("RAMP_START_CAP") or 0.0), 2)
it = round(float(os.environ.get("RAMP_START_IT") or 1.0), 2)
cur = json.load(open(LIVE, encoding="utf-8"))
assert round(float(cur.get("H2_GATE_CAP", -1)), 2) == cap and round(float(cur.get("INTENT_TEACH_W", -1)), 2) == it, \
    "the run is not at its step: " + str(cur)
log("ramp_head on for {}: shut {} updates, then H2_GATE_CAP +{} and then INTENT_TEACH_W -{} a step every {} updates and at least "
    "{} min, on the clock; now cap {} rule {}".format(RUN, SHUT_N, STEP, STEP, EVERY_N, EVERY_S // 60, cap, it))
u0 = updates()
n_last, t_last = u0 + (SHUT_N - EVERY_N if cap == 0 and it == 1.0 else 0), time.time() - (EVERY_S if cap == 0 and it == 1.0 else 0)
open_at = None                                               # (the update at which the cap reached 1: the head-open save follows)
kept = os.path.exists(os.path.join(KEEP, "policy_head_open_v062.pt"))
while it > 0 or not kept:
    time.sleep(SLEEP)
    n = updates()
    if cap >= 1.0 and not kept and open_at is not None:
        tag = -(-(open_at + EVERY_N) // 10) * 10              # (the first save, every 10 updates, a full EVERY_N updates on)
        src = os.path.join(KEEP, "policy_{}.pt".format(tag))
        if os.path.exists(src) and n > tag:
            shutil.copy2(src, os.path.join(KEEP, "policy_head_open_v062.pt"))
            log("the head open: keep/policy_{}.pt kept as keep/policy_head_open_v062.pt (the owner's play test; training goes on)".format(tag))
            kept = True
    if n < n_last + EVERY_N or time.time() - t_last < EVERY_S:
        continue
    if cap < 1.0:
        cap = round(min(1.0, cap + STEP), 2)
        put(H2_GATE_CAP=cap)
        log("RAMP head gate cap {} (u{}, {} updates, {} min since the last step); last check {}".format(cap, n, n - n_last, int((time.time() - t_last) // 60), last_check()))
        if cap >= 1.0:
            open_at = n
    elif it > 0 and kept:
        it = round(max(0.0, it - STEP), 2)
        put(INTENT_TEACH_W=it)
        log("RAMP item rule {} (u{}, {} updates, {} min since the last step); last check {}".format(it, n, n - n_last, int((time.time() - t_last) // 60), last_check()))
    else:
        continue
    n_last, t_last = n, time.time()
log("ramp_head done: the head open (cap {}), the item rule at {}".format(cap, it))
