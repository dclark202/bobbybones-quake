"""2.1f's dial (the outlook inside the head; docs/runs/2.1/2.1f/CARD.md "The run"), on the clock of updates done = the LINES of metrics.jsonl
(never the trainer's own "update": a --resume restarts it at 1).
  OUT_G (the outlook's term on his target scores) is written ONLY once the owner's mark exists: <run>/watch/out_mark.json
        {"mark": <0 .. 20>, "from": <update>, "to": <update>} (from and to default 30 and 70), read on every poll. While the file is absent OUT_G
        is never written (it stays at the live file's value: 0 from start_live.py). Once present, OUT_G = mark x (clock - from) / (to - from)
        between from and to (0 before, the mark after). A mark outside 0 .. 20, or to <= from: refused, a FLAG, nothing written. A later mark that
        would give less than the ramp already wrote: logged, the larger value held (the ramp never steps back: the owner decides by writing
        live.json himself, with the mark file removed so the ramp stops writing).
OUT_PICK, OUT_TRIAL, PULL_G and HELD_G are NOT scheduled: the ramp never writes them (each write re-reads live.json and sets OUT_G alone).
Written to live.json after each new update while a mark exists; the clock never holds or steps back (CLAUDE.md rule 6); every check logged, one
under 40% as a MAJOR PROBLEM. Kept with their optimizers: the first saves at or past the marks 30 and 70 (keep/policy_u<update>_21f.pt). Logged
every update: 2.1d's lines (the held draw, the slow plan, the flicker line, the pull with its proof, trips, reached, the ledger), the kinds of his
changes mid-trip (b22r, plain numbers), and the outlook's: one line per label kind with its skill (prequential R2 of the goal's number and of the
goal-blind one, the gain, overall and at decision and at stay readings) and one line for what plays (strength, kind, the term's size, the share
of his readings it changed, the replay at 0.5 to 8 of the kind that plays, z's size, the trial trips, the last layer). Flagged as ramp_21d (the
trainer refusing live.json, a dial applied not as written, a check under 40%, no held, plan or pull record, the dodge gate, the win part, a part
of a sum over 40, a firing cost, the pull's proof: MAJOR over PROOF_MAX = 0.01, FLAG over 0.003, FLAG not measured), and: no outlook record or the
outlook's lesson off (MAJOR); its strength, kind or trial share played none of the start's, the last written or the live file's (MAJOR); its last
layer or the term's largest value over 40 (FLAG, rule 11). NO flag or threshold on any count of trips, changes or interrupts. A crash of the flag
thread is logged as a MAJOR PROBLEM and the thread starts again (1.9a). The pull's proof line carries its worst frame (rec pull.worst,
worst_half: the step, a keep reading, the seat's marks, the two log-probabilities, the target, the largest pull, a sequence's edge, the 99.9th
percentile, the frames over 0.003 and 0.01) only when first_err is above 0.003 (no flag changes).
    python docs/runs/2.1/2.1f/ramp_21f.py <run> [--poll S] [--settle S] [--dir D] [--resume] [--once]
--once: one pass of the flags over the metrics there is, then out (the smoke's check of this file; nothing written to live.json).
tools/run/live_accept.py reads values(clock) and DIALS of this module at the mark named by RAMP21F_MARK="mark,from,to" (default 20,30,70: the
largest mark), so every file the ramp could write is checked for each mark given."""
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
SCHEDULE = {}                                                # (2.1f: no fixed schedule: OUT_G only from the owner's mark file)
UNSCHEDULED = ("OUT_PICK", "OUT_TRIAL", "PULL_G", "HELD_G")  # (never written by the ramp: the owner's, or 2.1d's end values; read from live.json)
MARKS = (30, 70)
MARK_MAX = 20.0                                              # (live OUT_G's range in the trainer: 0 .. 20)
MARK_FROM, MARK_TO = 30, 70                                  # (the mark file's defaults)
START = {}                                                   # ("start" values: none in this schedule)
SIZE_FLAG = 40.0
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


def out_g_at(clock, mk):
    """OUT_G at this clock for the mark (mark, from, to)"""
    m_, f_, t_ = mk
    if clock <= f_:
        return 0.0
    if clock >= t_:
        return float(m_)
    return float(m_) * (clock - f_) / float(t_ - f_)


def mark_check(d):
    """the mark file's content -> ((mark, from, to), None) or (None, why)"""
    try:
        m_ = float(d["mark"])
        f_ = int(d.get("from", MARK_FROM))
        t_ = int(d.get("to", MARK_TO))
    except (KeyError, TypeError, ValueError) as e_:
        return None, "not {{\"mark\": x, \"from\": u, \"to\": u}}: {}".format(e_)
    if not (0.0 <= m_ <= MARK_MAX):
        return None, "mark {} outside 0 .. {}".format(m_, MARK_MAX)
    if t_ <= f_ or f_ < 0:
        return None, "to {} not after from {}".format(t_, f_)
    return (m_, f_, t_), None


TEST_MARK = mark_check(dict(zip(("mark", "from", "to"), (os.environ.get("RAMP21F_MARK") or "{},{},{}".format(MARK_MAX, MARK_FROM, MARK_TO)).split(","))))[0]
assert TEST_MARK is not None, "RAMP21F_MARK: mark,from,to with the mark in 0 .. {} and to after from".format(MARK_MAX)


def values(clock):
    """{name: its value at this clock} at the test mark (tools/run/live_accept.py reads it: every file the ramp could write for that mark)"""
    return {"OUT_G": out_g_at(float(clock), TEST_MARK)}


DIALS = (("OUT_G", TEST_MARK[1], TEST_MARK[2], 0.0, TEST_MARK[0], 0.0),)   # (name, from, to, there, at the end, before: live_accept's clock range)
END = max(d[2] for d in DIALS)


def dial_at(clock, lo, hi, v0, v1, pre):
    """(live_accept's older form: one segment) unused here: values() gives every name"""
    return v1 if clock >= hi else (pre if clock < lo else v0 + (v1 - v0) * (clock - lo) / float(hi - lo))


def kinds_line(ch_, u_):
    """(b22r) the kinds of his changes mid-trip in plain words (rec plan.changes; sim/change_kinds.py): no flag, no threshold"""
    if ch_.get("kinds_off"):
        return "update {}: his changes mid-trip: the kinds' readouts are off (failed in the trainer; a readout only)".format(u_)
    nk_ = ch_.get("news_kind") or {}
    bg_ = ch_.get("back_gap") or {}
    return ("update {}: his changes mid-trip (of {} judged): after news and stuck {} ({}), after news and back {} ({}), quiet and stuck {} ({}), "
            "quiet and back {} ({}) | news is present at {} of readings ({}), at {} of changes (lift {}); contact {} / {}, a sound {} / {}, "
            "a hit unseen {} / {} | of the backs, {} returned to the plan's top goal; away {} readings (median; mean {}, {} backs) | of those "
            "that stuck, {} went to the plan's top goal (plan: {}) | a held seat-minute: {} after news, {} quiet | {} changes off a keep "
            "reading").format(
        u_, ch_.get("n_2s"), ch_.get("news_stuck"), ch_.get("news_stuck_n"), ch_.get("news_back"), ch_.get("news_back_n"),
        ch_.get("quiet_stuck"), ch_.get("quiet_stuck_n"), ch_.get("quiet_back"), ch_.get("quiet_back_n"), ch_.get("news_base"), ch_.get("base_n"),
        ch_.get("news_at_change"), ch_.get("news_lift"),
        *[x_ for k_ in ("contact", "sound", "hit_unseen") for x_ in ((nk_.get(k_) or {}).get("base"), (nk_.get(k_) or {}).get("at_change"))],
        ch_.get("back_to_plan"), bg_.get("median"), bg_.get("mean"), bg_.get("n"), ch_.get("stuck_to_plan"), ch_.get("plan_src"),
        ch_.get("news_min"), ch_.get("quiet_min"), ch_.get("off_reading_n"))


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
        ramp) the start file's and the live file's now (OUT_PICK, OUT_TRIAL: the owner's hand)"""
        if name == "OUT_G":                                  # (written by the ramp once a mark exists, or by the owner's hand)
            with WLOCK:
                return [dict(WRITES0).get(name)] + [v2_.get(name) for w2_, v2_ in WRITES[-4:]] + [live_now().get(name)]
        return [dict(WRITES0).get(name), live_now().get(name)]

    cur = json.load(open(LIVE, encoding="utf-8"))
    if a.resume and os.path.exists(SP):
        START.update(json.load(open(SP, encoding="utf-8")))
    elif not a.once:
        json.dump(START, open(SP, "w", encoding="utf-8"))
    WRITES0.update({n_: cur.get(n_) for n_ in ("OUT_G",) + UNSCHEDULED})
    if not a.resume and not a.once:
        assert abs(float(cur.get("OUT_G", -99))) < 1e-9, "OUT_G is {} in live.json, not 0 (start_live.py)".format(cur.get("OUT_G"))
        for n_ in UNSCHEDULED:
            assert n_ in cur, "{} is not in live.json (the ramp never writes it: start_live.py puts it there)".format(n_)

    def out_lines(m_, u_):                                   # (2.1f) the outlook's record of this update
        ol_ = m_.get("outlook")
        if not ol_:
            if u_:
                log("MAJOR PROBLEM update {}: no outlook record in the metrics (the run has no --outlook 1?)".format(u_))
            return
        if ol_.get("off"):
            log("MAJOR PROBLEM update {}: THE OUTLOOK'S LESSON OR READOUTS FAILED in the trainer (off for the rest of the run; its term plays on with "
                "its weights as they are): see the trainer's log".format(u_))
        q_ = lambda d_, k_: (d_ or {}).get(k_)                # noqa: E731
        for kn_ in ol_.get("kinds") or []:
            kd_ = (ol_.get("kind") or {}).get(kn_) or {}
            al_, de_, sy_ = kd_.get("all") or {}, kd_.get("decision") or {}, kd_.get("stay") or {}
            log("update {}: outlook {}{} skill (prequential R2 goal / goal-blind / gain): all {} / {} / {} ({} rows) | decision readings {} / {} / {} "
                "({}) | stay readings {} / {} / {} ({}) | corr {} | top = his goal {} | spread between goals {} | label raw {}".format(
                    u_, kn_, " PLAYS" if (ol_.get("kinds") or []).index(kn_) == ol_.get("pick") else "", q_(al_, "r2_goal"), q_(al_, "r2_blind"),
                    q_(al_, "gain"), q_(al_, "rows"), q_(de_, "r2_goal"), q_(de_, "r2_blind"), q_(de_, "gain"), q_(de_, "rows"), q_(sy_, "r2_goal"),
                    q_(sy_, "r2_blind"), q_(sy_, "gain"), q_(sy_, "rows"), q_(al_, "corr"), q_(al_, "top_share"), q_(kd_.get("spread"), "mean"),
                    (ol_.get("raw") or {}).get(kn_)))
        ks_ = ol_.get("kinds") or []
        pk_ = ol_.get("pick")
        kp_ = ((ol_.get("kind") or {}).get(ks_[pk_]) if (isinstance(pk_, int) and 0 <= pk_ < len(ks_)) else None) or {}
        log("update {}: outlook plays: strength {} (next {}) kind {} (next {}) | the league's {} kind {} (plays {}) | term size {} largest {} | "
            "changed his pick at {} of his readings ({}) | replay (share of readings whose pick changes) at 0.5..8: {} | z {} | readings {} "
            "decisions {} | trial share {} (next {}): trips {} readings {} in a target lesson {} | segments (readings) {} | loss {} last layer {} | "
            "lesson {} s".format(
                u_, ol_.get("g"), ol_.get("g_next"), pk_, ol_.get("pick_next"), ol_.get("g_opp"), ol_.get("pick_opp"), ol_.get("opp_has"),
                ol_.get("size"), ol_.get("max"), ol_.get("changed"), ol_.get("changed_n"), kp_.get("replay"), kp_.get("z"), ol_.get("readings"),
                ol_.get("decisions"), ol_.get("trial"), ol_.get("trial_next"), ol_.get("trial_trips"), ol_.get("trial_readings"),
                ol_.get("trial_in_lesson"), ol_.get("seg_readings"), ol_.get("loss"), ol_.get("l3"), ol_.get("secs")))
        if (ol_.get("l3") or 0) > SIZE_FLAG:
            log("FLAG update {}: the outlook's last layer {} over {} (rule 11)".format(u_, ol_.get("l3"), SIZE_FLAG))
        if (ol_.get("max") or 0) > SIZE_FLAG:
            log("FLAG update {}: the outlook's term reached {} on his target scores, over {} (rule 11)".format(u_, ol_.get("max"), SIZE_FLAG))
        for n_, k2_ in (("OUT_G", "g"), ("OUT_PICK", "pick"), ("OUT_TRIAL", "trial")):
            cand_ = written(n_)
            if ol_.get(k2_) is None or not any(c2_ is not None and abs(float(ol_[k2_]) - float(c2_)) < 1e-4 for c2_ in cand_):
                log("MAJOR PROBLEM update {}: the outlook's {} played {} is none of {} (the start's, the last written, the live file's now)".format(
                    u_, k2_, ol_.get(k2_), cand_))

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
            if "news_back" in ch_ or ch_.get("kinds_off"):       # (b22r) the kinds of his changes: plain numbers, no flag
                log(kinds_line(ch_, u_))
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
                    pu_.get("plan_w"), pu_.get("decay")) + (
                " | the proof's worst frame: {} (as the learner reads them: {})".format(json.dumps(pu_.get("worst")), json.dumps(pu_.get("worst_half")))
                if (pu_.get("first_err") is not None and float(pu_["first_err"]) > PROOF_FLOOR_FLAG) else ""))
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
        out_lines(m_, u_)
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
        if len(base) < 5:                                    # the run's first five updates (the outlook silent)
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
                got_ = {n2_: (ap_.get("file") or {}).get(n2_) for n2_ in ("OUT_G",)}
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

    MK_ = dict(cur=None, seen=None, held=0.0)                 # (the mark in force, the file's last content seen, the largest OUT_G written)

    def read_mark():
        """the owner's mark file -> (mark, from, to) or None (absent, or refused: a FLAG once per content)"""
        p_ = os.path.join(WD, "out_mark.json")
        if not os.path.exists(p_):
            if MK_["cur"] is not None:
                log("the mark file is gone: OUT_G is no longer written by the ramp (stays at the live file's {})".format(live_now().get("OUT_G")))
            MK_["cur"], MK_["seen"] = None, None
            return None
        try:
            raw_ = open(p_, encoding="utf-8").read()
            d_ = json.loads(raw_)
            mk_, why_ = mark_check(d_ if isinstance(d_, dict) else {})
        except (OSError, ValueError) as e_:
            raw_, mk_, why_ = None, None, "not JSON: {}".format(e_)
        if raw_ != MK_["seen"]:
            MK_["seen"] = raw_
            if mk_ is None:
                log("FLAG: the mark file watch/out_mark.json refused ({}): OUT_G not written; the last mark in force: {}".format(why_, MK_["cur"]))
            else:
                log("the owner's mark: OUT_G 0 at update {} -> {} at update {} (straight line; the ramp writes it from now on)".format(mk_[1], mk_[0], mk_[2]))
                MK_["cur"] = mk_
        return MK_["cur"]

    def write(clock):
        mk_ = read_mark()
        if mk_ is None:
            return None
        g_ = out_g_at(clock, mk_)
        if g_ < MK_["held"] - 1e-9:
            log("the mark now gives OUT_G {:.4f} at clock {}, under the {:.4f} already written: held at {:.4f} (the ramp never steps back; the owner "
                "decides by writing live.json himself, with the mark file removed)".format(g_, clock, MK_["held"], MK_["held"]))
            g_ = MK_["held"]
        MK_["held"] = g_
        d = json.load(open(LIVE, encoding="utf-8"))          # (re-read: OUT_PICK, OUT_TRIAL, PULL_G, HELD_G and every other name kept as the file has them)
        d["OUT_G"] = round(g_, 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        v_ = {"OUT_G": d["OUT_G"]}
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
    log("ramp_21f on for {}: OUT_G written only from the owner's mark file watch/out_mark.json (now: {}); saves kept at {}; never written: {}; FREE: "
        "the clock never holds or steps back, a check under 40% is a MAJOR PROBLEM{}".format(
            a.run, "present" if os.path.exists(os.path.join(WD, "out_mark.json")) else "absent: OUT_G stays at the live file's {}".format(cur.get("OUT_G")),
            MARKS, UNSCHEDULED, " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = len(L0) if (a.resume and L0) else 0             # (the run's clock = the lines of metrics.jsonl, as tools/run/watch.py: the
    #                                                          trainer's own "update" restarts at 1 on a --resume)
    seen, marked = mtime(), set()
    if a.resume:
        marked = {k_ for k_ in MARKS if any(f_.startswith("policy_u") and f_.endswith("_21f.pt") and int(f_[8:-7]) >= k_
                                            for f_ in os.listdir(KEEP) if f_[8:-7].isdigit())}
        MK_["held"] = float(live_now().get("OUT_G") or 0.0) if os.path.exists(os.path.join(WD, "out_mark.json")) else 0.0
        if done_n:                                           # (the dial for the current update now, not at the next one)
            v_ = write(float(done_n))
            log("clock {} after update {} (resumed): {}".format(done_n, done_n, v_ if v_ is not None else "no mark in force (no file, or refused): nothing written"))
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = len(L)
        if n > done_n:
            v_ = write(float(n))
            if v_ is not None:
                log("clock {} after update {}: wrote {}".format(n, n, v_))
            if done_n < 30 <= n:
                log("MARK update 30: the silent stage ends; THE OWNER CHOOSES THE MARK (watch/out_mark.json {{\"mark\": x, \"from\": u, \"to\": u}}; "
                    "the outlook lines' replay gives the share of his readings each strength would change); OUT_G is {} now".format(live_now().get("OUT_G")))
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            for k_ in MARKS:
                if n >= k_ and k_ not in marked:
                    marked.add(k_)
                    keep("policy_u{}_21f.pt".format(n))
                    log("kept keep/policy_u{}_21f.pt with its optimizer (the mark {})".format(n, k_))


if __name__ == "__main__":
    main()
