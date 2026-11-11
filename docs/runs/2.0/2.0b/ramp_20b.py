"""2.0b's dials (owner, 2026-11-09: "continue the build and start it when it's ready"; docs/runs/2.0/2.0b/CARD.md), on the clock of updates done,
straight lines, held before and after:
  SPACE_GATE    0 -> 1        over updates 30 to 60: the inputs of the map's table against his belief (part 2)
  EDGE_PAY      0 -> 0.0005   over updates 60 to 100: a second pays it times the edge, zero-sum (part 3; sized on the card: a tenth of the frags')
Fixed from the start in live.json: SPACE_W 1 (the readout's lesson, part 1, from update 0), COVER_PAY 0 (built, not opened), and 2.0a's end's
dials (DMG_REWARD 0.001, DMG_TAKEN_W 1.0, WIN_ADD 0.6, KEEP_G 0.975, the order shut, no firing cost). Written to live.json (read between
rollouts) after each new update. The clock never holds or steps back (owner, 2026-11-04; CLAUDE.md rule 6): the gate opens at update 30 whatever
the readout reads; a readout not above its base rate then is logged as a MAJOR PROBLEM, every check with its win rate, one under 40% as a MAJOR
PROBLEM, and the owner decides. Kept with their optimizers: the first saves at or past the marks (keep/policy_u<update>_20b.pt).
Logged in watch.log each update: 2.0a's lines (the ledger, frags a match-minute, the keep choice, speed, weapons, the firing cost) and 2.0b's:
the readout's skill by group (the threat on him, what he puts on the enemy, the map's cover, the zones), the ledger's terms "edge" and "cover" with
their size shares. Flagged beside 2.0a's flags: the readout's skill not above 0 from update 30 (MAJOR); the edge term not zero before update 60 or
zero from update 70 (MAJOR); the cover term not zero (MAJOR); the edge's size share over 0.25 (the card's rule). Nothing here stops the run.
    python docs/runs/2.0/2.0b/ramp_20b.py <run> [--poll S] [--settle S] [--dir D] [--resume]"""
import argparse
import json
import os
import shutil
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DIALS = (("SPACE_GATE", 30, 60, 0.0, 1.0, 0.0),              # (name, from update, to update, its value there, at the end, before)
         ("EDGE_PAY", 60, 100, 0.0, 0.0005, 0.0))
GATE_AT, PAY_AT = 30, 60
EDGE_SHARE = 0.25
END = max(d[2] for d in DIALS)
MARKS = (10, 30, 50, 70, 90, 110, 130, 150, 170)
SIZE_FLAG = 40.0
MAJOR = 0.40
FRAGS_MIN = 1.5
QUIET_MAX = 0.08
DMG_AFTER = 0.6                                              # dmg_dealt a player-minute allowed from update 75 (the start pays about 1.8; at 0.001 about 0.33)


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
        names = {"checks_prev.jsonl": "the control (1.7a's update 90)", "checks_ref.jsonl": "1.6a's end (the long-term control)"}
        if a.resume:
            seen = {f_: len(jl(os.path.join(WD, f_))) for f_ in seen}
        seen_m, base = [len(jl(MET)) if a.resume else 0], []
        seen_st, seen_ap = [None], [None]
        while True:
            for f_, n_ in seen.items():
                R = jl(os.path.join(WD, f_))
                for d in R[n_:]:
                    log(("MAJOR PROBLEM " if wr(d) < MAJOR else "") + "check update {} against {}: {}-{} = {:.1%}{}".format(
                        d["update"], names[f_], d["won"], d["lost"], wr(d), " (under 40%)" if wr(d) < MAJOR else ""))
                    cy_ = d.get("cypher")
                    if cy_:
                        log("check update {}: Cypher's measures {}".format(d["update"], cy_))
                seen[f_] = len(R)
            st_ = {}                                         # (1.7a's false start) the trainer's last read of live.json
            try:
                st_ = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8"))
            except (OSError, ValueError):
                pass
            if st_.get("status") == "refused" and st_.get("update") != seen_st[0]:
                seen_st[0] = st_.get("update")
                log("MAJOR PROBLEM update {}: THE TRAINER REFUSED live.json, nothing applied: {}".format(st_.get("update"), st_.get("reason")))
            ap_ = {}                                         # the trainer's own record of the file it applied (live_applied.json)
            try:
                ap_ = json.load(open(os.path.join(D, "live_applied.json"), encoding="utf-8"))
            except (OSError, ValueError):
                pass
            if ap_.get("from_update") is not None and ap_.get("from_update") != seen_ap[0]:
                seen_ap[0] = ap_.get("from_update")
                got_ = {n2_: (ap_.get("file") or {}).get(n2_) for n2_, *_ in DIALS}
                with WLOCK:
                    cand_ = [v2_ for w2_, v2_ in WRITES]
                    cand_ = [dict(WRITES0)] + cand_[-4:]
                off_ = {n2_: g2_ for n2_, g2_ in got_.items() if g2_ is None or
                        not any(abs(float(g2_) - float(c2_.get(n2_, g2_))) < 1e-6 for c2_ in cand_)}
                if off_:
                    log("MAJOR PROBLEM: the trainer applied dials that were not written (from update {}): {} applied, the last writes {}".format(
                        ap_.get("from_update"), off_, {n2_: [c2_.get(n2_) for c2_ in cand_] for n2_ in off_}))
                else:
                    log("live applied from update {}: {}".format(ap_.get("from_update"), got_))
            for m_ in jl(MET)[seen_m[0]:]:
                seen_m[0] += 1
                u_ = m_.get("update")
                pt_ = m_.get("pay_terms") or {}
                pm_, ss_ = pt_.get("per_player_min") or {}, pt_.get("size_share") or {}
                if pm_:
                    log("update {}: ledger a player-minute: damage dealt {} taken {} | frags {} deaths {} | win part {} (size share {}) | items MH {} RA {} YA {} "
                        "points {} decay {} | total {}".format(
                            u_, pm_.get("dmg_dealt"), pm_.get("dmg_taken"), pm_.get("frag"), pm_.get("death"), pm_.get("win_part"), ss_.get("win_part"),
                            pm_.get("item_MH"), pm_.get("item_RA"), pm_.get("item_YA"), pm_.get("item_points"), pm_.get("item_decay"),
                            pt_.get("total_per_player_min")))
                    if (pm_.get("dmg_dealt") or 0) > DMG_AFTER:
                        log("MAJOR PROBLEM update {}: the damage pay is not at 2.0a's floor (dmg_dealt {} a player-minute, over {})".format(
                            u_, pm_.get("dmg_dealt"), DMG_AFTER))
                    e_, c_ = pm_.get("edge"), pm_.get("cover")
                    log("update {}: ledger: edge {} (size share {}) cover {} (size share {})".format(u_, e_, ss_.get("edge"), c_, ss_.get("cover")))
                    if (ss_.get("cover") or 0) > 0:
                        log("MAJOR PROBLEM update {}: the cover pay is paid (size share {}): COVER_PAY is not 0".format(u_, ss_.get("cover")))
                    if (u_ or 0) < PAY_AT and (ss_.get("edge") or 0) > 0:
                        log("MAJOR PROBLEM update {}: the edge pay is paid before update {} (size share {})".format(u_, PAY_AT, ss_.get("edge")))
                    if (u_ or 0) >= PAY_AT + 10 and not (ss_.get("edge") or 0) > 0:
                        log("MAJOR PROBLEM update {}: the edge pay is not in the ledger (size share {})".format(u_, ss_.get("edge")))
                    if (ss_.get("edge") or 0) > EDGE_SHARE:
                        log("FLAG update {}: the edge pay is {} of the pay's size (over {}: the card's rule)".format(u_, ss_.get("edge"), EDGE_SHARE))
                    if (ss_.get("win_part") or 0) > 0.6:
                        log("FLAG update {}: the win part is {} of the pay's size (over 0.6): the judge's noise".format(u_, ss_.get("win_part")))
                sp_ = m_.get("space") or {}
                sb_ = sp_.get("both") or {}
                if sp_:
                    sk_ = {g_: (sb_.get(g_) or {}).get("skill") for g_ in ("thr", "put", "agg", "zones")}
                    log("update {}: under a threat over 20 damage a second in {} of his frames with the enemy alive, the edge under -10 in {} (the truth; every seat)".format(
                        u_, sp_.get("thr_over20"), sp_.get("edge_under10")))
                    log("update {}: the readout 'space': frames {} weight {} | skill (1 - its error over the best constant's): the threat on him {} "
                        "what he puts {} the map's cover {} the zones {}".format(u_, sp_.get("frames"), sp_.get("w"), sk_["thr"], sk_["put"], sk_["agg"], sk_["zones"]))
                    if (u_ or 0) >= GATE_AT and sp_.get("frames") and not all((sk_[g_] or 0) > 0 for g_ in ("thr", "zones")):
                        log("MAJOR PROBLEM update {}: the readout 'space' is not above its base rate (skill {}) and the inputs' gate is opening".format(u_, sk_))
                else:
                    log("MAJOR PROBLEM update {}: no 'space' record in metrics.jsonl: the readout's lesson is not running".format(u_))
                fm_ = m_.get("frags_per_match_min")
                if fm_ is not None:
                    log("update {}: frags a match-minute {}{}".format(u_, fm_, " FLAG: under {} (passivity, the card's alarm)".format(FRAGS_MIN) if fm_ < FRAGS_MIN else ""))
                k_ = m_.get("keep") or {}
                s2_ = k_.get("sim2") or {}
                pl_ = k_.get("pull") or {}
                ar_ = k_.get("arrived") or {}
                cm_ = m_.get("cmb") or {}
                if cm_:
                    sm_ = cm_.get("sums") or {}                       # (owner, 11-05) a sum of two outputs: each part's size
                    big3_ = {"{} {}".format(k1_, k2_): v2_ for k1_ in ("fire", "targets") for k2_, v2_ in (sm_.get(k1_) or {}).items()
                             if k2_ in ("hands", "head", "add", "way_add") and (v2_ or 0) > SIZE_FLAG}
                    if big3_:
                        log("FLAG update {}: a part of a sum over {}: {}".format(u_, SIZE_FLAG, big3_))
                    if (cm_.get("g") or 0) > 0 or (cm_.get("padd") or 0) > 0:
                        log("MAJOR PROBLEM update {}: the order is not shut (share {}, adds {})".format(u_, cm_.get("g"), cm_.get("padd")))
                log("update {}: keep share {} | its seconds {} readings a second {} decided {} re-decide {} (contact {}, heard {}, quiet {}, "
                    "arrived {}) | pull: head state {} hands {} own numbers {} | kl {} | arrivals {} p {}".format(
                        u_, k_.get("g"), s2_.get("seconds"), s2_.get("readings_a_second"), s2_.get("decided"), s2_.get("redecide"),
                        s2_.get("redecide_contact"), s2_.get("redecide_heard"), s2_.get("redecide_quiet"), s2_.get("redecide_arrived"),
                        pl_.get("s"), pl_.get("hands"), pl_.get("own"), k_.get("kl"), ar_.get("share"), ar_.get("p")))
                if (s2_.get("redecide_quiet") or 0) > QUIET_MAX:
                    log("FLAG update {}: the keep choice's quiet re-decisions {} a reading (over {}: 1.7a's slide began there)".format(u_, s2_.get("redecide_quiet"), QUIET_MAX))
                if (k_.get("kl") or 0) > 0.05:
                    log("FLAG update {}: the keep choice's step on the head's term {} (over 0.05)".format(u_, k_.get("kl")))
                ih_ = (m_.get("v15") or {}).get("in_hand_games") or {}
                wp_ = m_.get("weapon") or {}
                bw_ = (m_.get("stack") or {}).get("big_weapons")
                sc_ = m_.get("shot_cost_per_player_min")
                fc_ = {k2_: v_ for k2_, v_ in pm_.items() if any(w_ in k2_ for w_ in ("shot", "fire", "switch", "blind")) and v_}
                log("update {}: big weapons owned {} | in hand in games rockets {} lightning {} rail {} | firing cost {} {}".format(
                    u_, bw_, ih_.get("rl"), ih_.get("lg"), ih_.get("rg"), sc_, fc_ or ""))
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
                if len(base) < 5:                            # the run's first five updates
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
    log("ramp_20b on for {}: {}; FREE: the clock never holds or steps back, a check under 40% is a MAJOR PROBLEM{}".format(
        a.run, ", ".join("{} {} -> {} over updates {} to {} ({} before)".format(n_, v0, v1, lo, hi, pre) for n_, lo, hi, v0, v1, pre in DIALS),
        " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = int(L0[-1]["update"]) if (a.resume and L0) else 0
    seen, marked = mtime(), set()
    if a.resume:
        marked = {k_ for k_ in MARKS if any(f_.startswith("policy_u") and f_.endswith("_20b.pt") and int(f_[8:-7]) >= k_
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
                    keep("policy_u{}_20b.pt".format(n))
                    log("kept keep/policy_u{}_20b.pt with its optimizer (the mark {})".format(n, k_))


if __name__ == "__main__":
    main()
