"""Coach: tune BobbyBones' Nightmare brain (bot character + item desire) by trial and error.

Each generation gives every training server a candidate set of knobs, written as loose bot files
(/tmp/train/c<i>/botfiles/bots/bones_c.c and bones_i.c, mounted into the server), and asks that server
to restart (bot files are cached by the game). Fitness = mean frag difference over the candidate's
matches vs rotating Nightmare bots: WIN RATE (a draw = half a win), frag diff only breaks ties. Cross-entropy method: the best ELITE candidates set the next
generation's distribution. Candidate 0 of every generation is the unmodified Nightmare Bones (baseline).

With more trainers than candidates (POP), each candidate runs on several trainers (trainer i plays
candidate (i-1) % POP) and fitness pools all its matches, which cuts best-of-N selection noise.

Runs in its own container:  python3 /tools/tune_coach.py <n_trainers> [pop]
Writes /tmp/train/tune/{log.jsonl, state.json, best.json}
"""
import json
import math
import os
import random
import re
import sys
import time
import zipfile

T = "/tmp/train"
OUT = os.path.join(T, "tune")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 16
POP = int(sys.argv[2]) if len(sys.argv) > 2 else N   # candidates per generation (incl. baseline)
POP = max(2, min(POP, N))
MATCHES = 3                 # matches per trainer per generation (~30 min)
MAX_WAIT = 60 * 60          # don't wait forever on a slow/broken trainer
BATCH = int(os.environ.get("COACH_BATCH", "60"))       # restart this many trainers at a time ...
BATCH_GAP = float(os.environ.get("COACH_GAP", "120"))  # ... this many seconds apart (boot storms lag the public server)
ELITE = max(4, POP // 6)
SPACE = {                   # name: (low, high)
    "AGGRESSION": (0.0, 1.0), "SELFPRESERVATION": (0.0, 1.0), "CAMPER": (0.0, 1.0), "ALERTNESS": (0.0, 1.0),
    "JUMPER": (0.0, 1.0), "WEAPONJUMPING": (0.0, 1.0), "EASY_FRAGGER": (0.0, 1.0),
    "FS_HEALTH": (0.5, 5.0), "FS_ARMOR": (0.5, 5.0),
    # fair aim (human-like limits)
    "AIM_REACT": (120.0, 300.0), "AIM_GAIN_X": (0.6, 1.6), "AIM_DRIFT_X": (0.4, 1.6),
    "AIM_SETTLE": (1.5, 5.0), "AIM_DPS": (500.0, 1100.0),
    # trainable layers in itemrun.py (switches: on above 0.5)
    "W_DUEL": (0.0, 1.0), "W_LG_MAX": (250.0, 800.0), "W_RG_MIN": (500.0, 1500.0), "W_POLICY": (0.0, 1.0),
    "PF_ON": (0.0, 1.0), "PF_WINDOW": (300.0, 2500.0),
    "T_ON": (0.0, 1.0), "T_LEAD": (3.0, 20.0), "T_DENY": (1.0, 4.0),
    "S_LEAD": (0.0, 1.0), "S_TRAIL": (0.0, 1.0),
    "P_HOLD": (0.0, 1.0), "P_LEAD": (1.0, 5.0),
}
AIM_DEFAULTS = dict(AIM_REACT=170.0, AIM_GAIN_X=1.0, AIM_DRIFT_X=1.0, AIM_SETTLE=2.5, AIM_DPS=720.0)
# layer defaults = old behaviour (what the baseline candidate plays); switches start the search at 50/50
LAYER_DEFAULTS = dict(W_DUEL=0.0, W_LG_MAX=450.0, W_RG_MIN=800.0, W_POLICY=1.0, PF_ON=0.0, PF_WINDOW=1200.0,
                      T_ON=0.0, T_LEAD=8.0, T_DENY=1.0, S_LEAD=0.0, S_TRAIL=0.0, P_HOLD=0.0, P_LEAD=2.0)
SWITCHES = {"W_DUEL", "W_POLICY", "PF_ON", "T_ON", "S_LEAD", "S_TRAIL", "P_HOLD"}
# knob groups; COACH_GROUPS (comma list, default all) picks which ones are searched, the rest stay at baseline
GROUPS = {
    "character": ["AGGRESSION", "SELFPRESERVATION", "CAMPER", "ALERTNESS", "JUMPER", "WEAPONJUMPING", "EASY_FRAGGER"],
    "items": ["FS_HEALTH", "FS_ARMOR"],
    "aim": ["AIM_REACT", "AIM_GAIN_X", "AIM_DRIFT_X", "AIM_SETTLE", "AIM_DPS"],
    "weapons": ["W_DUEL", "W_LG_MAX", "W_RG_MIN", "W_POLICY"],
    "prefire": ["PF_ON", "PF_WINDOW"],
    "timing": ["T_ON", "T_LEAD", "T_DENY"],
    "score": ["S_LEAD", "S_TRAIL"],
    "position": ["P_HOLD", "P_LEAD"],
}
ACTIVE = {k for g in (os.environ.get("COACH_GROUPS") or ",".join(GROUPS)).split(",") for k in GROUPS.get(g.strip(), [])}
os.makedirs(OUT, exist_ok=True)
pak = zipfile.ZipFile("/ql/baseq3/pak00.pk3")
ORIG_C = pak.read("botfiles/bots/bones_c.c").decode("latin1")
ORIG_I = pak.read("botfiles/bots/bones_i.c").decode("latin1")


def log(msg):
    line = "{} {}".format(time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(os.path.join(OUT, "coach.log"), "a") as f:
        f.write(line + "\n")


def original_params():
    """the Nightmare values: the skill-4+ block of bones_c.c and the #defines of bones_i.c"""
    p = {}
    block = ORIG_C[ORIG_C.index("skill 4"):]
    for k in SPACE:
        m = re.search(r"CHARACTERISTIC_" + k + r"\s+([0-9.]+)", block)
        if m:
            p[k] = float(m.group(1))
        m = re.search(r"#define\s+" + k + r"\s+([0-9.]+)", ORIG_I)
        if m:
            p[k] = float(m.group(1))
    return p


def write_candidate(i, gen, cid, params):
    d = os.path.join(T, "c{}".format(i), "botfiles", "bots")
    os.makedirs(d, exist_ok=True)
    c = ORIG_C
    head, tail = c[:c.index("skill 4")], c[c.index("skill 4"):]
    for k, v in params.items():
        tail = re.sub(r"(CHARACTERISTIC_" + k + r"\s+)[0-9.]+", lambda m: m.group(1) + "{:.3f}".format(v), tail)
    it = ORIG_I
    for k, v in params.items():
        it = re.sub(r"(#define\s+" + k + r"\s+)[0-9.]+", lambda m: m.group(1) + "{:.3f}".format(v), it)
    open(os.path.join(d, "bones_c.c"), "w", encoding="latin1").write(head + tail)
    open(os.path.join(d, "bones_i.c"), "w", encoding="latin1").write(it)
    json.dump(dict(gen=gen, id=cid, params=params, t=time.time()),
              open(os.path.join(T, "c{}".format(i), "candidate.json"), "w"))
    open(os.path.join(T, "c{}".format(i), "restart.flag"), "w").write("1")


def matches_for(i, gen, cid, since):
    out = []
    f = os.path.join(T, "c{}".format(i), "results.jsonl")
    if os.path.exists(f):
        for line in open(f):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("t", 0) >= since and r.get("cand") == [gen, cid]:
                out.append(r)
    return out


base = original_params()
base.update(AIM_DEFAULTS)
base.update(LAYER_DEFAULTS)
state_f = os.path.join(OUT, "state.json")
if os.path.exists(state_f):
    st = json.load(open(state_f))
    mu, sigma, gen = st["mu"], st["sigma"], st["gen"]
    for k, (lo, hi) in SPACE.items():                     # knobs added since the last run
        mu.setdefault(k, (lo + hi) / 2 if k in SWITCHES else base.get(k, (lo + hi) / 2))
        sigma.setdefault(k, (hi - lo) / 4)
else:
    mu = {k: (lo + hi) / 2 if k in SWITCHES else base.get(k, (lo + hi) / 2) for k, (lo, hi) in SPACE.items()}
    sigma = {k: (hi - lo) / 4 for k, (lo, hi) in SPACE.items()}
    gen = 0
log("coach start: {} trainers, {} candidates/gen, tuning {}, baseline {}".format(N, POP, sorted(ACTIVE), base))

while True:
    cands = [dict(base)]                                   # candidate 0: unmodified Nightmare Bones
    while len(cands) < POP:
        cands.append({k: round(min(hi, max(lo, random.gauss(mu[k], sigma[k]))), 3) if k in ACTIVE else base.get(k, mu[k])
                      for k, (lo, hi) in SPACE.items()})
    t0 = time.time()
    for i in range(1, N + 1):
        write_candidate(i, gen, (i - 1) % POP, cands[(i - 1) % POP])
        if i % BATCH == 0 and i < N:
            time.sleep(BATCH_GAP)
    log("gen {} started with {} candidates on {} trainers".format(gen, len(cands), N))
    while True:
        time.sleep(60)
        counts = [len(matches_for(i, gen, (i - 1) % POP, t0)) for i in range(1, N + 1)]
        done = sum(1 for c in counts if c >= MATCHES)
        if done >= 0.9 * N or time.time() - t0 > MAX_WAIT:   # don't let a few slow trainers stall a gen
            break
    results = []
    for cid, p in enumerate(cands):
        ms = [m for i in range(cid + 1, N + 1, POP) for m in matches_for(i, gen, cid, t0)]
        if not ms:
            continue
        diff = sum(r["bobby_score"] - r["opp_score"] for r in ms) / len(ms)
        frags = sum(r["bobby_score"] for r in ms) / len(ms)
        win = sum(1.0 if r["bobby_score"] > r["opp_score"] else 0.5 if r["bobby_score"] == r["opp_score"] else 0.0
                  for r in ms) / len(ms)
        results.append(dict(gen=gen, id=cid, params=p, n=len(ms), win=win, diff=diff, frags=frags,
                            fitness=win + 0.001 * diff, baseline=(cid == 0)))
    with open(os.path.join(OUT, "log.jsonl"), "a") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    tuned = sorted([r for r in results if not r["baseline"]], key=lambda r: -r["fitness"])
    basel = [r for r in results if r["baseline"]]
    if tuned:
        elite = tuned[:ELITE]
        for k, (lo, hi) in SPACE.items():
            if k not in ACTIVE:
                continue
            vals = [e["params"][k] for e in elite]
            m = sum(vals) / len(vals)
            sd = math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))
            mu[k] = m
            sigma[k] = max(sd, (hi - lo) * 0.05)
        best = tuned[0]
        prev = json.load(open(os.path.join(OUT, "best.json"))) if os.path.exists(os.path.join(OUT, "best.json")) else None
        if prev is None or best["fitness"] > prev.get("fitness", -1e9):
            json.dump(best, open(os.path.join(OUT, "best.json"), "w"), indent=1)
        log("gen {} done: best tuned win {:.0%} diff {:+.1f} (n {}) | baseline win {} | mean tuned win {:.0%}".format(
            gen, best["win"], best["diff"], best["n"],
            "{:.0%} diff {:+.1f}".format(basel[0]["win"], basel[0]["diff"]) if basel else "n/a",
            sum(r["win"] for r in tuned) / len(tuned)))
    gen += 1
    json.dump(dict(mu=mu, sigma=sigma, gen=gen), open(state_f, "w"))
