"""2.1e's dials (the head's slow halves; docs/runs/2.1/2.1e/CARD.md "The run"), on the clock of updates done = the LINES of metrics.jsonl
(never the trainer's own "update": a --resume restarts it at 1), straight lines between each name's knots (SCHEDULE, the one table below):
  SLOW_MIX  (the pull's source: the fast plan's log-odds -> the picked slow half's)    0 to update 20, 0 -> 1 over 20 to 50, 1 after
  SLOW_BACK (the read-back's gate: the picked slow half's state into the head's input) 0 to update 50, 0 -> 1 over 50 to 80, 1 after
SLOW_PICK, PULL_G and HELD_G are NOT scheduled: the ramp never writes them (each write re-reads live.json and sets only the two names above).
SLOW_PICK is the owner's, by hand at update 20 (the card: "At update 20 the owner picks one"); PULL_G and HELD_G stay where 2.1d ends.
Written to live.json after each new update; the clock never holds or steps back (CLAUDE.md rule 6); every check logged, one under 40% as a
MAJOR PROBLEM. Kept with their optimizers: the first saves at or past the marks 20, 50, 80 (keep/policy_u<update>_21e.pt). Logged every update:
2.1d's lines (the held draw, the slow plan, the flicker line: the share of his mid-trip changes taken back within 2 seconds, no flag; the pull
with its proof, trips, reached, the ledger) and the slow halves': what played (mix, back, pick, the read-back's weight size), and per half its
ticks a seat-minute by cause (clock, trip end, change of mind), how far its odds move at a tick beside the fast plan's at a refresh, its
forecast's kl and top-1 per horizon beside the fast plan's and his odds now on the same rows, the replayed pull's changes beside the fast
plan's, its loss and last layer's size. Flagged as ramp_21d (the trainer refusing live.json, a dial applied not as written, a check under
40%, no held, plan or pull record, the dodge gate, frags, targets reached under 0.7x of the first five updates, speed on trips, the win part,
a part of a sum over 40, a firing cost, the pull's proof: MAJOR over PROOF_MAX = 0.01, FLAG over 0.003, FLAG not measured), and: no slow record
(MAJOR: the run has no --slow-half 1); the halves' readouts or lesson off (MAJOR: they failed in the trainer); the mix or the back played none of
the last written (MAJOR); the half played not the live file's SLOW_PICK (MAJOR); a half's last layer or the read-back's weights over 40 (FLAG,
rule 11); the picked half ticking mostly on changes of mind (FLAG: then it is not slow, the card's red team). A crash of the flag thread is
logged as a MAJOR PROBLEM and the thread starts again (1.9a).
    python docs/runs/2.1/2.1e/ramp_21e.py <run> [--poll S] [--settle S] [--dir D] [--resume] [--once]
--once: one pass of the flags over the metrics there is, then out (the smoke's check of this file; nothing written to live.json)."""
import argparse
import json
import os
import shutil
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
# ---- THE SCHEDULE (the card's, 2026-11-15): name -> knots (update, value); "start": the start file's value of that name. Before the first
#      knot its value, after the last its value, straight lines between
SCHEDULE = {"SLOW_MIX": ((20, 0.0), (50, 1.0)),
            "SLOW_BACK": ((50, 0.0), (80, 1.0))}
UNSCHEDULED = ("SLOW_PICK", "PULL_G", "HELD_G")              # (never written by the ramp: the owner's, or 2.1d's end values; read from live.json)
MARKS = (20, 50, 80)
START = {}                                                   # ("start" values: none in this schedule)
SIZE_FLAG = 40.0
CHANGE_SHARE_FLAG = 0.5                                      # (the picked half's ticks on a change of mind over this share of its ticks: not slow)
MAJOR = 0.40
FRAGS_MIN = 1.5
PROOF_MAX = 0.01                                             # (the pull's proof first_err: as 2.1d's now: the card's floor at pull 0 in mixed
#                                                             precision 0.0011 to 0.0014; a wiring fault scales with the pull, ~4.6 at 1)
PROOF_FLOOR_FLAG = 0.003                                     # (over it, under PROOF_MAX: a FLAG)


def knots(name):
    return [(float(u_), float(START[name]) if v_ == "start" else float(v_)) for u_, v_ in SCHEDULE[name]]


def value(name, clock):
    k_ = knots(name)
    if clock <= k_[0][0]:
        return k_[0][1]
    if clock >= k_[-1][0]:
        return k_[-1][1]
    for (u0_, y0_), (u1_, y1_) in zip(k_[:-1], k_[1:]):
        if u0_ <= clock <= u1_:
            return y0_ + (y1_ - y0_) * (clock - u0_) / float(u1_ - u0_)
    return k_[-1][1]


def values(clock):
    """{name: its value at this clock} (tools/run/live_accept.py reads it)"""
    return {n_: value(n_, float(clock)) for n_ in SCHEDULE}


DIALS = tuple((n_, knots(n_)[0][0], knots(n_)[-1][0], knots(n_)[0][1], knots(n_)[-1][1], knots(n_)[0][1]) for n_ in SCHEDULE)   # (name, from,
END = max(d[2] for d in DIALS)                                                                                                   # to, there, end, before)


def dial_at(clock, lo, hi, v0, v1, pre):
    """(live_accept's older form: one segment) unused here: values() gives every name"""
    return v1 if clock >= hi else (pre if clock < lo else v0 + (v1 - v0) * (clock - lo) / float(hi - lo))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    WD, LIVE, POL, OPT, KEEP, MET = (os.path.join(D, "watch"), os.path.join(D, "live.json"), os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt"),
                                     os.path.join(D, "keep"), os.path.join(D, "metrics.jsonl"))
    os.makedirs(WD, exist_ok=True)
    os.makedirs(KEEP, exist_ok=True)
    WRITES, WRITES0, WLOCK = [], {}, threading.Lock()    # (1.7a's false start) the dials written after each update; at the ramp's start
    SP = os.path.join(WD, "ramp_start.json")                # ("start" values, kept for a resume)

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

    def live_now():
        try:
            return json.load(open(LIVE, encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def written(name):
        """the values that may have played: a scheduled name's start value and its last writes; an unscheduled one's (never written by the
        ramp) the start file's and the live file's now (SLOW_PICK: the owner's hand)"""
        if name in SCHEDULE:
            with WLOCK:
                return [dict(WRITES0).get(name)] + [v2_.get(name) for w2_, v2_ in WRITES[-4:]]
        return [dict(WRITES0).get(name), live_now().get(name)]

    cur = json.load(open(LIVE, encoding="utf-8"))
    if a.resume and os.path.exists(SP):
        START.update(json.load(open(SP, encoding="utf-8")))
    elif not a.once:
        json.dump(START, open(SP, "w", encoding="utf-8"))
    WRITES0.update({n_: cur.get(n_) for n_ in tuple(SCHEDULE) + UNSCHEDULED})
    if not a.resume and not a.once:
        for n_ in SCHEDULE:                                  # (the file at the schedule's value before its first knot)
            assert abs(float(cur.get(n_, -99)) - value(n_, 0.0)) < 1e-9, "{} is {} in live.json, not {}".format(n_, cur.get(n_), value(n_, 0.0))
        for n_ in UNSCHEDULED:
            assert n_ in cur, "{} is not in live.json (the ramp never writes it: start_live.py puts it there)".format(n_)

    def slow_lines(m_, u_):                                  # (2.1e) the slow halves' record of this update
        sl_ = m_.get("slow")
        if not sl_:
            if u_:
                log("MAJOR PROBLEM update {}: no slow record in the metrics (the run has no --slow-half 1?)".format(u_))
            return
        if sl_.get("off"):
            log("MAJOR PROBLEM update {}: THE SLOW HALVES' READOUTS OR LESSON FAILED in the trainer (off for the rest of the run; the picked half plays "
                "on with its weights as they are): see the trainer's log".format(u_))
        log("update {}: slow halves: played mix {} (next {}) back {} (next {}) pick {} (next {}) | the league's mix {} back {} pick {} (has halves {}) | "
            "read-back |w| {} | rows {} seat-minutes {} | fast plan: odds moved {} a refresh ({} refreshes) | lesson {} s".format(
                u_, sl_.get("mix"), sl_.get("mix_next"), sl_.get("back"), sl_.get("back_next"), sl_.get("pick"), sl_.get("pick_next"),
                sl_.get("mix_opp"), sl_.get("back_opp"), sl_.get("pick_opp"), sl_.get("opp_has"), sl_.get("readback_w"), sl_.get("rows"),
                sl_.get("seat_min"), (sl_.get("fast") or {}).get("tv"), (sl_.get("fast") or {}).get("tv_n"), sl_.get("secs")))
        for k_, h_ in enumerate(sl_.get("halves") or []):
            tm_ = h_.get("ticks_min") or {}
            hz_ = " | ".join("{}: n {} kl slow {} fast {} now {} top1 slow {} fast {} now {}".format(
                hk_, (h_.get(hk_) or {}).get("n"), (h_.get(hk_) or {}).get("kl_slow"), (h_.get(hk_) or {}).get("kl_fast"),
                (h_.get(hk_) or {}).get("kl_now"), (h_.get(hk_) or {}).get("top1_slow"), (h_.get(hk_) or {}).get("top1_fast"),
                (h_.get(hk_) or {}).get("top1_now")) for hk_ in sorted(k2_ for k2_ in h_ if k2_.startswith("h") and k2_[1:].isdigit()))
            log("update {}: slow half {} (clock {}{}): ticks a seat-minute {} (clock {}, trip end {}, change of mind {}) | odds moved {} a tick ({}) | "
                "{} | replayed pull's changes mid-trip a held seat-minute {} (the fast plan's {}) | loss {} | last layer {}".format(
                    u_, k_, h_.get("clock"), ", PLAYS" if k_ == sl_.get("pick") else "", tm_.get("all"), tm_.get("clock"), tm_.get("trip_end"),
                    tm_.get("change"), h_.get("tv"), h_.get("tv_n"), hz_, h_.get("pull_changes_min"), sl_.get("plan_pull_changes_min"),
                    h_.get("loss"), h_.get("l3")))
            if (h_.get("l3") or 0) > SIZE_FLAG:
                log("FLAG update {}: slow half {}'s last layer {} over {} (rule 11)".format(u_, k_, h_.get("l3"), SIZE_FLAG))
            if k_ == sl_.get("pick") and (tm_.get("all") or 0) > 0 and (tm_.get("change") or 0) / tm_["all"] > CHANGE_SHARE_FLAG:
                log("FLAG update {}: the picked half {} ticks mostly on changes of mind ({} of {} a seat-minute): it is not slow".format(
                    u_, k_, tm_.get("change"), tm_.get("all")))
        if (sl_.get("readback_w") or 0) > SIZE_FLAG:
            log("FLAG update {}: the read-back's weights {} over {} (rule 11)".format(u_, sl_.get("readback_w"), SIZE_FLAG))
        for n_, k2_ in (("SLOW_MIX", "mix"), ("SLOW_BACK", "back"), ("SLOW_PICK", "pick")):
            cand_ = written(n_)
            if sl_.get(k2_) is None or not any(c2_ is not None and abs(float(sl_[k2_]) - float(c2_)) < 1e-4 for c2_ in cand_):
                log("MAJOR PROBLEM update {}: the slow halves' {} played {} is none of {} (the start's, the last written{})".format(
                    u_, k2_, sl_.get(k2_), cand_, "; the live file's now" if n_ not in SCHEDULE else ""))

    def update_lines(m_, base, u_):                          # u_: the RUN's update = the line's 1-based place in metrics.jsonl (a --resume
        #                                                      restarts the trainer's own "update" at 1)
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
        hd_ = m_.get("held")                                 # (2.1c) the held draw's record of this rollout
        if hd_:
            log("update {}: held draw: share played {} (next {}) | seat-frames on it {} | readings a second {} | new draws a seat-minute {} | "
                "CHANGES MID-TRIP a seat-minute {}".format(u_, hd_.get("g"), hd_.get("g_next"), hd_.get("share"), hd_.get("readings_s"),
                                                            hd_.get("new_draws_min"), hd_.get("changes_min")))
            cand_h = written("HELD_G")
            if not any(c2_ is not None and abs(float(hd_.get("g", -1)) - float(c2_)) < 1e-4 for c2_ in cand_h):
                log("MAJOR PROBLEM update {}: the held share played {} is none of {} (the start's, the live file's now)".format(u_, hd_.get("g"), cand_h))
        elif u_:
            log("MAJOR PROBLEM update {}: no held record in the metrics (the run has no --held 1?)".format(u_))
        pn_ = m_.get("plan")                                 # (2.1c; 2.1d: the plan inside the head, the pull's source)
        if pn_:
            hz_ = " | ".join("{} ({} ticks): n {} kl plan {} now {} top1 plan {} now {}".format(
                k2_, (pn_.get(k2_) or {}).get("ticks"), (pn_.get(k2_) or {}).get("n"), (pn_.get(k2_) or {}).get("kl_plan"),
                (pn_.get(k2_) or {}).get("kl_now"), (pn_.get(k2_) or {}).get("top1_plan"), (pn_.get(k2_) or {}).get("top1_now"))
                for k2_ in ("h2s", "h5s") if k2_ in pn_)
            ch_ = pn_.get("changes") or {}
            log("update {}: slow plan: {} | loss after {}".format(u_, hz_, pn_.get("loss")))
            log("update {}: slow plan: the pull's changes mid-trip a seat-minute by strength (first order) {} | his changes mid-trip {}: back within "
                "2 s {} (of {}), news {}, against the plan {}".format(u_, pn_.get("pull_changes_min"), ch_.get("n"), ch_.get("back_2s"), ch_.get("n_2s"),
                                                                      ch_.get("news"), ch_.get("against_plan")))
            log("update {}: flicker: share of his mid-trip changes he took back within 2 seconds {} (of {} changes)".format(
                u_, ch_.get("back_2s"), ch_.get("n_2s")))
        elif u_ and hd_:
            log("MAJOR PROBLEM update {}: no plan record in the metrics (the run has no --plan 1, or the plan's readouts failed)".format(u_))
        pu_ = m_.get("pull")                                 # (2.1d) the pull as played
        if pu_:
            pa_ = pu_.get("parts") or {}
            log("update {}: pull: strength played {} (next {}; the league's {}) on horizon {} ({} ticks), floor {} | size {} length {} largest {} on {} "
                "frames | the target's parts: hands {} head {} pull {} | proof first_err {} (as the learner reads them: {}) "
                "| plan last layer {} decay {}".format(
                    u_, pu_.get("g"), pu_.get("g_next"), pu_.get("g_opp"), pu_.get("h"), pu_.get("ticks"), pu_.get("floor"), pu_.get("size"),
                    pu_.get("norm"), pu_.get("max"), pu_.get("frames"), pa_.get("hands"), pa_.get("head"), pa_.get("pull"), pu_.get("first_err"),
                    pu_.get("first_err_half"),
                    pu_.get("plan_w"), pu_.get("decay")))
            fe_ = pu_.get("first_err")
            if fe_ is None:
                log("FLAG update {}: the pull's proof was not measured (first_err none)".format(u_))
            elif float(fe_) > PROOF_MAX:
                log("MAJOR PROBLEM update {}: THE PULL'S PROOF FAILED: first_err {} over {} (the learner's target log-probability is not the one "
                    "played: the wiring)".format(u_, fe_, PROOF_MAX))
            elif float(fe_) > PROOF_FLOOR_FLAG:
                log("FLAG update {}: the pull's proof first_err {} (above the floor of about 0.0015 seen at pull 0; under the bar {})".format(
                    u_, fe_, PROOF_MAX))
            big_ = {k2_: v2_ for k2_, v2_ in (("size", pu_.get("size")), ("length", pu_.get("norm")), ("largest", pu_.get("max")),
                                               ("hands", pa_.get("hands")), ("head", pa_.get("head"))) if (v2_ or 0) > SIZE_FLAG}
            if big_:
                log("FLAG update {}: a part of his target scores' sum over {} (rule 11): {}".format(u_, SIZE_FLAG, big_))
            cand_p = written("PULL_G")
            if not any(c2_ is not None and abs(float(pu_.get("g", -1)) - float(c2_)) < 1e-4 for c2_ in cand_p):
                log("MAJOR PROBLEM update {}: the pull's strength played {} is none of {} (the start's, the live file's now)".format(u_, pu_.get("g"), cand_p))
        elif u_:
            log("MAJOR PROBLEM update {}: no pull record in the metrics (the run has no --pull 1?)".format(u_))
        slow_lines(m_, u_)
        fm_ = m_.get("frags_per_match_min")
        if fm_ is not None:
            log("update {}: frags a match-minute {}{}".format(u_, fm_, " FLAG: under {} (passivity, the card's alarm)".format(FRAGS_MIN) if fm_ < FRAGS_MIN else ""))
        cm_ = m_.get("cmb") or {}
        if cm_:
            sm_ = cm_.get("sums") or {}
            big3_ = {"{} {}".format(k1_, k2_): v2_ for k1_ in ("fire", "targets") for k2_, v2_ in (sm_.get(k1_) or {}).items()
                     if k2_ in ("hands", "head", "add", "way_add") and (v2_ or 0) > SIZE_FLAG}
            if big3_:
                log("FLAG update {}: a part of a sum over {}: {}".format(u_, SIZE_FLAG, big3_))
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
            return
        log("update {}: trips a player-minute {} reached {} | speed on trips {} over 320 {}".format(u_, now_[2], now_[3], now_[0], now_[1]))
        if len(base) < 5:                                    # the run's first five updates (the slow halves silent)
            base.append(now_)
            return
        b_ = [sum(x[i] for x in base) / len(base) for i in range(4)]
        if now_[3] < 0.7 * b_[3]:
            log("FLAG update {}: targets reached {} (start {:.3f}): flicker?".format(u_, now_[3], b_[3]))
        if now_[0] < 0.9 * b_[0] or now_[1] < 0.9 * b_[1]:
            log("FLAG update {}: speed on trips {} (start {:.0f}), share over 320 {} (start {:.3f})".format(u_, now_[0], b_[0], now_[1], b_[1]))
        # (no flag on trips a player-minute: more trips than on the lock is the point, owner 2026-11-15; flicker is read from back within 2 s)

    def flags(once=False):
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": "the control (2.1d's end)", "checks_ref.jsonl": "2.0e's end (the long-term control)"}
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
                got_ = {n2_: (ap_.get("file") or {}).get(n2_) for n2_ in SCHEDULE}
                off_ = {n2_: g2_ for n2_, g2_ in got_.items() if g2_ is None or
                        not any(c2_ is not None and abs(float(g2_) - float(c2_)) < 1e-6 for c2_ in written(n2_))}
                if off_ and not once:
                    log("MAJOR PROBLEM: the trainer applied dials that were not written (from update {}): {} applied, the last writes {}".format(
                        ap_.get("from_update"), off_, {n2_: written(n2_) for n2_ in off_}))
                else:
                    log("live applied from update {}: {} (unscheduled: {})".format(
                        ap_.get("from_update"), got_, {n2_: (ap_.get("file") or {}).get(n2_) for n2_ in UNSCHEDULED}))
            for m_ in jl(MET)[seen_m[0]:]:
                seen_m[0] += 1
                update_lines(m_, base, seen_m[0])
            if once:
                return
            time.sleep(a.poll)

    if a.once:                                               # (the smoke: the flags over the metrics there are, the live.json values as written)
        flags(once=True)
        return

    def mtime():
        try:
            return os.path.getmtime(POL)
        except FileNotFoundError:
            return 0.0

    def keep(name):
        shutil.copy2(POL, os.path.join(KEEP, name))
        shutil.copy2(OPT, os.path.join(KEEP, name.replace("policy_", "opt_", 1)))

    def write(clock):
        d = json.load(open(LIVE, encoding="utf-8"))          # (re-read: SLOW_PICK, PULL_G, HELD_G and every other name kept as the file has them)
        for n_, v_ in values(clock).items():
            d[n_] = round(v_, 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        v_ = {n_: d[n_] for n_ in SCHEDULE}
        with WLOCK:
            WRITES.append((clock, v_))
        return v_

    def flags_guard():                                       # (1.9a: a crashed flag thread went silent all night)
        import traceback
        while True:
            try:
                flags()
            except Exception:
                log("MAJOR PROBLEM: THE RAMP'S FLAG THREAD CRASHED (it starts again; lines may repeat): " + traceback.format_exc().replace(chr(10), " | ")[-1500:])
                time.sleep(60)

    threading.Thread(target=flags_guard, daemon=True).start()
    log("ramp_21e on for {}: {} (the card's schedule; marks {}; never written: {}); FREE: the clock never holds or steps back, a check under 40% is "
        "a MAJOR PROBLEM{}".format(a.run, "; ".join("{} knots {}".format(n_, knots(n_)) for n_ in SCHEDULE), MARKS, UNSCHEDULED,
                                   " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = len(L0) if (a.resume and L0) else 0             # (the run's clock = the lines of metrics.jsonl, as tools/run/watch.py: the
    #                                                          trainer's own "update" restarts at 1 on a --resume)
    seen, marked = mtime(), set()
    if a.resume:
        marked = {k_ for k_ in MARKS if any(f_.startswith("policy_u") and f_.endswith("_21e.pt") and int(f_[8:-7]) >= k_
                                            for f_ in os.listdir(KEEP) if f_[8:-7].isdigit())}
        if done_n:                                           # (the dials for the current update now, not at the next one)
            v_ = write(float(done_n))
            log("clock {} after update {} (resumed): {}".format(min(done_n, END), done_n, v_))
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = len(L)
        if n > done_n:
            if done_n < END or n <= END:
                v_ = write(float(n))
                log("clock {} after update {}: {}".format(min(n, END), n, v_))
            if done_n < 20 <= n:
                log("MARK update 20: the silent stage ends; THE OWNER PICKS THE HALF THAT PLAYS (live SLOW_PICK, now {}; the ramp never writes "
                    "it); SLOW_MIX opens from here".format(live_now().get("SLOW_PICK")))
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            for k_ in MARKS:
                if n >= k_ and k_ not in marked:
                    marked.add(k_)
                    keep("policy_u{}_21e.pt".format(n))
                    log("kept keep/policy_u{}_21e.pt with its optimizer (the mark {})".format(n, k_))


if __name__ == "__main__":
    main()
