"""1.7a's dials (owner, 2026-11-04 night: "start the lock handover ... and let it go for 80 updates"; CARD.md), on the clock of updates done:
  KEEP_G          0 -> 1      over updates 10 to 90    (the hand-over: the share of his seconds the keep choice decides; the lock rule the rest)
  CMB_G           0 -> 1      over updates 90 to 170   (1.7, the order: the share of his readings the head's combat order is asked at)
  PADD            0 -> 0.3    over updates 90 to 170   (... the pointer's scores on his targets' and his way's: held at 0.3 after: the level
                                                         checks' (11-05: at 1 30.5%, at 0.3 53.5% against 1.6a's end))
  ORD_GATE  -30, -12 -> 0     over updates 90 to 170   (... the order's attention token: shut until 90, then from -12 to open)
  FADD            0 -> 1      over updates 90 to 170   (1.7, the fire push: its add on the fire key)
  H2_FPG          0 -> 0.5    over updates 90 to 170   (... half the fire key's credit on the head's clock, half kept by the hands)
then held to the run's end (owner, 11-05: the lock first, then the new choice and its say on firing together; the trigger's credit only
halfway in this run). The owner's rule: two new things open one after the other (2026-10-24): the order once the keep choice has the lock's
place.
The brain's pass lesson runs from update 0 (--pass-odds; no dial). Written to live.json (read between rollouts) after each new update. The
clock never holds or steps back (owner, 2026-11-04; CLAUDE.md rule 6): every check is logged with its win rate, one under 40% as a MAJOR
PROBLEM, and the owner decides. Kept with their optimizers: the first saves at or past the marks (keep/policy_u<update>_17a.pt). Logged in watch.log each update: the keep choice's record (its share, readings a second in its seconds,
re-decisions in contact, heard, quiet and at arrivals, the parts of its logit: the head's state against its own numbers, i.e. whose decision
it is), trips and targets reached, speed, big weapons owned, his weapon in hand, the firing cost. Flagged: targets reached 30% under the run's
first five updates or trips a minute 50% over (b1.1a's flicker), speed 10% under, big weapons owned 0.05 under, the keep choice's step on
the head's term over 0.05, a part of his target or weapon scores over 40, any firing cost above zero (the owner's rule: none at all).
Nothing here stops the run.
    python docs/runs/1.7/1.7a/ramp_17a.py <run> [--poll S] [--settle S] [--dir D] [--resume]"""
import argparse
import json
import os
import shutil
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DIALS = (("KEEP_G", 10, 90, 0.0, 1.0, 0.0),                 # (name, from update, to update, its value there, at the end, before)
         ("CMB_G", 90, 170, 0.0, 1.0, 0.0), ("PADD", 90, 170, 0.0, 0.3, 0.0), ("ORD_GATE", 90, 170, -12.0, 0.0, -30.0),
         ("FADD", 90, 170, 0.0, 1.0, 0.0), ("H2_FPG", 90, 170, 0.0, 0.5, 0.0))
END = max(d[2] for d in DIALS)
MARKS = (10, 50, 90, 130, 170)
SIZE_FLAG = 40.0
MAJOR = 0.40


def dial_at(clock, lo, hi, v0, v1, pre):
    if clock < lo:
        return pre
    f = min(1.0, max(0.0, (clock - lo) / float(hi - lo)))
    return v0 + (v1 - v0) * f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    WD, LIVE, POL, OPT, KEEP, MET = (os.path.join(D, "watch"), os.path.join(D, "live.json"), os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt"),
                                     os.path.join(D, "keep"), os.path.join(D, "metrics.jsonl"))
    os.makedirs(WD, exist_ok=True)
    os.makedirs(KEEP, exist_ok=True)
    WRITES, WRITES0, WLOCK = [], {}, threading.Lock()    # (1.7a's false start) the dials written after each update; at the ramp's start

    def log(s):
        line = time.strftime("%m-%d %H:%M:%S ") + s
        for f in ("ramp.log", "watch.log"):
            with open(os.path.join(WD, f), "a") as fh:
                fh.write(line + "\n")

    def jl(p):
        try:
            with open(p) as f:
                return [json.loads(x) for x in f if x.strip()]
        except FileNotFoundError:
            return []

    def wr(d):
        return d["won"] / max(1, d["won"] + d["lost"])

    def flags():
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": "the start (1.6a's end)", "checks_ref.jsonl": "b1.2d's end"}
        if a.resume:
            seen = {f_: len(jl(os.path.join(WD, f_))) for f_ in seen}
        seen_m, base, bw0 = [len(jl(MET)) if a.resume else 0], [], []
        seen_st = [None]
        while True:
            for f_, n_ in seen.items():
                R = jl(os.path.join(WD, f_))
                for d in R[n_:]:
                    log(("MAJOR PROBLEM " if wr(d) < MAJOR else "") + "check update {} against {}: {}-{} = {:.1%}{}".format(
                        d["update"], names[f_], d["won"], d["lost"], wr(d), " (under 40%)" if wr(d) < MAJOR else ""))
                seen[f_] = len(R)
            st_ = {}                                         # (1.7a's false start) the trainer's last read of live.json
            try:
                st_ = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8"))
            except (OSError, ValueError):
                pass
            if st_.get("status") == "refused" and st_.get("update") != seen_st[0]:
                seen_st[0] = st_.get("update")
                log("MAJOR PROBLEM update {}: THE TRAINER REFUSED live.json, nothing applied: {}".format(st_.get("update"), st_.get("reason")))
            for m_ in jl(MET)[seen_m[0]:]:
                seen_m[0] += 1
                u_ = m_.get("update")
                k_ = m_.get("keep") or {}
                cm0_ = m_.get("cmb") or {}                   # (1.7a's false start) what the trainer played against what was written
                got_ = {"KEEP_G": k_.get("g"), "CMB_G": cm0_.get("g"), "PADD": cm0_.get("padd")}
                with WLOCK:
                    cand_ = [v2_ for w2_, v2_ in WRITES if u_ is not None and w2_ < u_]          # (tests.py live: a dial written after
                    cand_ = ([dict(WRITES0)] if len(cand_) < 4 else []) + cand_[-4:]          # update n is played by n+3 at the latest: --overlap)
                off_ = {n2_: g2_ for n2_, g2_ in got_.items() if g2_ is not None and
                        not any(abs(float(g2_) - float(c2_.get(n2_, g2_))) < 1e-3 for c2_ in cand_)}
                if off_:
                    log("MAJOR PROBLEM update {}: the trainer did not apply the dials written ({} played, {} written)".format(
                        u_, off_, {n2_: [c2_.get(n2_) for c2_ in cand_] for n2_ in off_}))
                s2_ = k_.get("sim2") or {}
                pl_ = k_.get("pull") or {}
                ar_ = k_.get("arrived") or {}
                cm_ = m_.get("cmb") or {}
                if cm_:
                    cs_ = cm_.get("sim") or {}
                    log("update {}: combat order share {} adds {} token gate {} asked {} p(an order) {} drawn {} p {} | chosen {} frames {} arrived {} "
                        "damage {} | pass lesson {} | weights {} | fire {}".format(
                            u_, cm_.get("g"), cm_.get("padd"), cm_.get("token_gate"), cm_.get("asked"), cm_.get("p_order"), cm_.get("drawn"),
                            cm_.get("p"), cs_.get("chosen"), cs_.get("frames"), cs_.get("arrived"), cs_.get("dealt"), cm_.get("passodds"),
                            cm_.get("w"), cm_.get("fire")))
                    sm_ = cm_.get("sums") or {}                       # (owner, 11-05) a sum of two outputs: each part's size
                    big3_ = {"{} {}".format(k1_, k2_): v2_ for k1_ in ("fire", "targets") for k2_, v2_ in (sm_.get(k1_) or {}).items()
                             if k2_ in ("hands", "head", "add", "way_add") and (v2_ or 0) > SIZE_FLAG}
                    if big3_:
                        log("FLAG update {}: a part of a sum over {}: {}".format(u_, SIZE_FLAG, big3_))
                    po_ = cm_.get("passodds") or {}
                    if po_.get("brier") is not None and po_.get("base") is not None and (po_.get("questions") or 0) > 0 and                             (u_ or 0) >= 20 and po_["brier"] > po_["base"]:
                        log("FLAG update {}: the brain's pass odds no better than their base rate (Brier {} against {})".format(
                            u_, po_["brier"], po_["base"]))
                log("update {}: keep share {} | its seconds {} readings a second {} decided {} re-decide {} (contact {}, heard {}, quiet {}, "
                    "arrived {}) | pull: head state {} hands {} own numbers {} | kl {} | arrivals {} p {}".format(
                        u_, k_.get("g"), s2_.get("seconds"), s2_.get("readings_a_second"), s2_.get("decided"), s2_.get("redecide"),
                        s2_.get("redecide_contact"), s2_.get("redecide_heard"), s2_.get("redecide_quiet"), s2_.get("redecide_arrived"),
                        pl_.get("s"), pl_.get("hands"), pl_.get("own"), k_.get("kl"), ar_.get("share"), ar_.get("p")))
                if (k_.get("kl") or 0) > 0.05:
                    log("FLAG update {}: the keep choice's step on the head's term {} (over 0.05)".format(u_, k_.get("kl")))
                ih_ = (m_.get("v15") or {}).get("in_hand_games") or {}
                wp_ = m_.get("weapon") or {}
                bw_ = (m_.get("stack") or {}).get("big_weapons")
                sc_ = m_.get("shot_cost_per_player_min")
                fc_ = {k2_: v_ for k2_, v_ in ((m_.get("pay_terms") or {}).get("per_player_min") or {}).items()
                       if any(w_ in k2_ for w_ in ("shot", "fire", "switch", "blind")) and v_}
                log("update {}: big weapons owned {} | in hand in games rockets {} lightning {} rail {} | firing cost {} {}".format(
                    u_, bw_, ih_.get("rl"), ih_.get("lg"), ih_.get("rg"), sc_, fc_ or ""))
                if bw_ is not None:
                    if len(bw0) < 5:
                        bw0.append(bw_)
                    elif bw_ < sum(bw0) / len(bw0) - 0.05:
                        log("FLAG update {}: big weapons owned {} (start {:.3f}): 1.4b's drift?".format(u_, bw_, sum(bw0) / len(bw0)))
                if (sc_ or 0) > 0 or any(v_ < 0 for v_ in fc_.values()):
                    log("MAJOR PROBLEM FLAG update {}: A FIRING COST ABOVE ZERO: shot cost {} {}".format(u_, sc_, fc_))
                big_ = {k2_: wp_.get(k2_) for k2_ in ("hands", "head") if (wp_.get(k2_) or 0) > SIZE_FLAG}
                if big_:
                    log("FLAG update {}: a part of his weapon-key scores over {}: {}".format(u_, SIZE_FLAG, big_))
                h2_ = m_.get("head2") or {}
                big2_ = {k2_: h2_.get(k2_) for k2_ in ("hands", "raw") if (h2_.get(k2_) or 0) > SIZE_FLAG}
                if big2_:
                    log("FLAG update {}: a part of his target scores over {}: {}".format(u_, SIZE_FLAG, big2_))
                pc_, it_ = m_.get("pace") or {}, m_.get("intent") or {}
                now_ = (pc_.get("trip_speed"), pc_.get("over_320"), it_.get("trips_per_player_min"), it_.get("reached"))
                if None in now_:
                    continue
                log("update {}: trips a player-minute {} reached {} | speed on trips {} over 320 {}".format(u_, now_[2], now_[3], now_[0], now_[1]))
                if len(base) < 5:                            # (owner: "speed is the thing to watch") the run's first five updates
                    base.append(now_)
                    continue
                b_ = [sum(x[i] for x in base) / len(base) for i in range(4)]
                if now_[3] < 0.7 * b_[3]:
                    log("FLAG update {}: targets reached {} (start {:.3f}): flicker?".format(u_, now_[3], b_[3]))
                if now_[0] < 0.9 * b_[0] or now_[1] < 0.9 * b_[1]:
                    log("FLAG update {}: speed on trips {} (start {:.0f}), share over 320 {} (start {:.3f})".format(u_, now_[0], b_[0], now_[1], b_[1]))
                if now_[2] > 1.5 * b_[2]:
                    log("FLAG update {}: trips a player-minute {} (start {:.1f}): flicker?".format(u_, now_[2], b_[2]))
            time.sleep(a.poll)

    def mtime():
        try:
            return os.path.getmtime(POL)
        except FileNotFoundError:
            return 0.0

    def keep(name):
        shutil.copy2(POL, os.path.join(KEEP, name))
        shutil.copy2(OPT, os.path.join(KEEP, name.replace("policy_", "opt_", 1)))

    def write(clock):
        d = json.load(open(LIVE, encoding="utf-8"))
        for n_, lo, hi, v0, v1, pre in DIALS:
            d[n_] = round(dial_at(clock, lo, hi, v0, v1, pre), 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        v_ = {n_: d[n_] for n_, *_ in DIALS}
        with WLOCK:
            WRITES.append((clock, v_))
        return v_

    cur = json.load(open(LIVE, encoding="utf-8"))
    WRITES0.update({n_: cur.get(n_) for n_, *_ in DIALS})
    for n_, lo, hi, v0, v1, pre in ([] if a.resume else DIALS):
        assert abs(float(cur.get(n_, -99)) - pre) < 1e-9, "{} is {} in live.json, not {}".format(n_, cur.get(n_), pre)
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_17a on for {}: {}; FREE: the clock never holds or steps back, a check under 40% is a MAJOR PROBLEM{}".format(
        a.run, ", ".join("{} {} -> {} over updates {} to {} ({} before)".format(n_, v0, v1, lo, hi, pre) for n_, lo, hi, v0, v1, pre in DIALS),
        " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = int(L0[-1]["update"]) if (a.resume and L0) else 0
    seen, marked = mtime(), set()
    if a.resume:
        marked = {k_ for k_ in MARKS if any(f_.startswith("policy_u") and f_.endswith("_17a.pt") and int(f_[8:-7]) >= k_
                                            for f_ in os.listdir(KEEP) if f_[8:-7].isdigit())}
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        if n > done_n:
            if done_n < END or n <= END:
                v_ = write(float(n))
                log("clock {} after update {}: {}".format(min(n, END), n, v_))
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            for k_ in MARKS:
                if n >= k_ and k_ not in marked:
                    marked.add(k_)
                    keep("policy_u{}_17a.pt".format(n))
                    log("kept keep/policy_u{}_17a.pt with its optimizer (the mark {})".format(n, k_))


if __name__ == "__main__":
    main()
