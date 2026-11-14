"""2.0e's dials (owner, 2026-11-14; docs/runs/2.0/2.0e/CARD.md), on the clock of updates done, straight lines, held after; one after the other:
  AIM3_W 0 -> 1, AIM3_SIZE_A 1 -> 0.39, AIM3_SIZE_B 0 -> 0.355, AIM3_LEAD 0 -> 1, AIM3_RELOAD 1 -> 0     updates 0 to 25    AIM3 (11-11 tuning)
  DMG_REWARD 0.0055 -> 0.005, DMG_TAKEN_W 0.8 -> 1.0 (zero-sum), RAIL_FAR_PAY 0.25 -> 0.1                 updates 25 to 35   the pay
  DODGE_G 0 -> 1                                                                                          updates 35 to 60   the dodge inputs' gate
Held 60 to 80 (the trainer stops itself: --max-updates 80). Fixed in live.json (start_live.py): HABIT_P 0, WIN_ADD 0.33, INTENT_HOLD 8 (the
lock, as 1.6a), no firing cost. 2.0d's ramp otherwise: written to live.json after each new update; the clock never holds or steps back
(CLAUDE.md rule 6); every check logged, one under 40% as a MAJOR PROBLEM. Kept with their optimizers: the first saves at or past the marks
10, 25, 35, 60 (keep/policy_u<update>_20e.pt). Flagged: the trainer refusing live.json (MAJOR); dials applied not as written (MAJOR); a check
under 40% (MAJOR); the dodge token's gate not log(DODGE_G) (MAJOR); frags a match-minute under 1.5; trips up 1.5x or targets reached down to
0.7x of the first five updates (the lock's measures: they must not move); the win part over 0.6 of the pay; a part of his weapon or target
scores over 40 (rule 11); a firing cost (MAJOR). A crash of the flag thread is logged as a MAJOR PROBLEM and the thread starts again (1.9a).
    python docs/runs/2.0/2.0e/ramp_20e.py <run> [--poll S] [--settle S] [--dir D] [--resume]"""
import argparse
import json
import os
import shutil
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DIALS = (("AIM3_W", 0, 25, 0.0, 1.0, 0.0),                  # (name, from update, to update, its value there, at the end, before)
         ("AIM3_SIZE_A", 0, 25, 1.0, 0.39, 1.0),
         ("AIM3_SIZE_B", 0, 25, 0.0, 0.355, 0.0),
         ("AIM3_LEAD", 0, 25, 0.0, 1.0, 0.0),
         ("AIM3_RELOAD", 0, 25, 1.0, 0.0, 1.0),
         ("DMG_REWARD", 25, 35, 0.0055, 0.005, 0.0055),
         ("DMG_TAKEN_W", 25, 35, 0.8, 1.0, 0.8),
         ("RAIL_FAR_PAY", 25, 35, 0.25, 0.1, 0.25),
         ("DODGE_G", 35, 60, 0.0, 1.0, 0.0))
END = max(d[2] for d in DIALS)
MARKS = (10, 25, 35, 60)
SIZE_FLAG = 40.0
MAJOR = 0.40
FRAGS_MIN = 1.5
QUIET_MAX = 0.08
TRIPS_MAX, REACHED_MIN = 1e9, -1.0                           # (2.0e: the lock; trips and reached are flagged against the run's first five updates)


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
        names = {"checks_prev.jsonl": "the control (1.6a's end)", "checks_ref.jsonl": "1.7a's update 90 (a readout)"}
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
                    if (ss_.get("win_part") or 0) > 0.6:
                        log("FLAG update {}: the win part is {} of the pay's size (over 0.6): the judge's noise".format(u_, ss_.get("win_part")))
                dg_ = m_.get("dodge_gate") or {}                    # (2.0d) the dodge inputs' gate: the columns' and the token's
                if dg_:
                    import math as math_
                    tk_ = max(-30.0, math_.log(dg_["cols"])) if (dg_.get("cols") or 0) > 0 else -30.0
                    log("update {}: dodge gate: columns {} token {}".format(u_, dg_.get("cols"), dg_.get("token")))
                    if abs(float(dg_.get("token", 0.0)) - tk_) > 1e-3:
                        log("MAJOR PROBLEM update {}: the dodge token's gate {} is not log(DODGE_G {}) = {:.3f}".format(u_, dg_.get("token"), dg_.get("cols"), tk_))
                elif u_:
                    log("MAJOR PROBLEM update {}: no dodge gate in the metrics (the network has no dodge token?)".format(u_))
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
                if now_[2] > TRIPS_MAX or now_[3] < REACHED_MIN:
                    log("FLAG update {}: the keep choice's flicker: trips a player-minute {} (over {}?), reached {} (under {}?)".format(
                        u_, now_[2], TRIPS_MAX, now_[3], REACHED_MIN))
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
    def flags_guard():                                       # (1.9a: a crashed flag thread went silent all night)
        import traceback
        while True:
            try:
                flags()
            except Exception:
                log("MAJOR PROBLEM: THE RAMP'S FLAG THREAD CRASHED (it starts again; lines may repeat): " + traceback.format_exc().replace(chr(10), " | ")[-1500:])
                time.sleep(60)

    threading.Thread(target=flags_guard, daemon=True).start()
    log("ramp_20e on for {}: {}; FREE: the clock never holds or steps back, a check under 40% is a MAJOR PROBLEM{}".format(
        a.run, ", ".join("{} {} -> {} over updates {} to {} ({} before)".format(n_, v0, v1, lo, hi, pre) for n_, lo, hi, v0, v1, pre in DIALS),
        " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = int(L0[-1]["update"]) if (a.resume and L0) else 0
    seen, marked = mtime(), set()
    if a.resume:
        marked = {k_ for k_ in MARKS if any(f_.startswith("policy_u") and f_.endswith("_20e.pt") and int(f_[8:-7]) >= k_
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
                    keep("policy_u{}_20e.pt".format(n))
                    log("kept keep/policy_u{}_20e.pt with its optimizer (the mark {})".format(n, k_))


if __name__ == "__main__":
    main()
