"""Coach: tune BobbyBones' Nightmare brain (bot character + item desire) by trial and error.

Each generation gives every training server a candidate set of knobs, written as loose bot files
(/tmp/train/c<i>/botfiles/bots/bones_c.c and bones_i.c, mounted into the server), and asks that server
to restart (bot files are cached by the game). Fitness = mean frag difference over the candidate's
matches vs rotating Nightmare bots. Cross-entropy method: the best ELITE candidates set the next
generation's distribution. Candidate 0 of every generation is the unmodified Nightmare Bones (baseline).

Runs in its own container:  python3 /tools/tune_coach.py <n_trainers>
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
MATCHES = 3                 # matches per candidate per generation (~30 min)
MAX_WAIT = 50 * 60          # don't wait forever on a slow/broken trainer
ELITE = 4
SPACE = {                   # name: (low, high)
    "AGGRESSION": (0.0, 1.0), "SELFPRESERVATION": (0.0, 1.0), "CAMPER": (0.0, 1.0), "ALERTNESS": (0.0, 1.0),
    "JUMPER": (0.0, 1.0), "WEAPONJUMPING": (0.0, 1.0), "EASY_FRAGGER": (0.0, 1.0),
    "FS_HEALTH": (0.5, 5.0), "FS_ARMOR": (0.5, 5.0),
}
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
state_f = os.path.join(OUT, "state.json")
if os.path.exists(state_f):
    st = json.load(open(state_f))
    mu, sigma, gen = st["mu"], st["sigma"], st["gen"]
else:
    mu = {k: base.get(k, (lo + hi) / 2) for k, (lo, hi) in SPACE.items()}
    sigma = {k: (hi - lo) / 4 for k, (lo, hi) in SPACE.items()}
    gen = 0
log("coach start: {} trainers, baseline {}".format(N, base))

while True:
    cands = [dict(base)]                                   # candidate 0: unmodified Nightmare Bones
    while len(cands) < N:
        cands.append({k: round(min(hi, max(lo, random.gauss(mu[k], sigma[k]))), 3) for k, (lo, hi) in SPACE.items()})
    t0 = time.time()
    for i, p in enumerate(cands, start=1):
        write_candidate(i, gen, i - 1, p)
    log("gen {} started with {} candidates".format(gen, len(cands)))
    while True:
        time.sleep(60)
        counts = [len(matches_for(i, gen, i - 1, t0)) for i in range(1, N + 1)]
        if min(counts) >= MATCHES or time.time() - t0 > MAX_WAIT:
            break
    results = []
    for i, p in enumerate(cands, start=1):
        ms = matches_for(i, gen, i - 1, t0)
        if not ms:
            continue
        diff = sum(r["bobby_score"] - r["opp_score"] for r in ms) / len(ms)
        frags = sum(r["bobby_score"] for r in ms) / len(ms)
        results.append(dict(gen=gen, id=i - 1, params=p, n=len(ms), diff=diff, frags=frags,
                            baseline=(i == 1)))
    with open(os.path.join(OUT, "log.jsonl"), "a") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    tuned = sorted([r for r in results if not r["baseline"]], key=lambda r: -r["diff"])
    basel = [r for r in results if r["baseline"]]
    if tuned:
        elite = tuned[:ELITE]
        for k, (lo, hi) in SPACE.items():
            vals = [e["params"][k] for e in elite]
            m = sum(vals) / len(vals)
            sd = math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))
            mu[k] = m
            sigma[k] = max(sd, (hi - lo) * 0.05)
        best = tuned[0]
        prev = json.load(open(os.path.join(OUT, "best.json"))) if os.path.exists(os.path.join(OUT, "best.json")) else None
        if prev is None or best["diff"] > prev["diff"]:
            json.dump(best, open(os.path.join(OUT, "best.json"), "w"), indent=1)
        log("gen {} done: best tuned diff {:+.1f} (frags {:.1f}) | baseline diff {} | mean tuned {:+.1f}".format(
            gen, best["diff"], best["frags"], "{:+.1f}".format(basel[0]["diff"]) if basel else "n/a",
            sum(r["diff"] for r in tuned) / len(tuned)))
    gen += 1
    json.dump(dict(mu=mu, sigma=sigma, gen=gen), open(state_f, "w"))
