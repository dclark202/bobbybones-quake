"""2.2b's dials (docs/runs/2.2/2.2b/CARD.md "The stages"; made from 2.2a's ramp: its generic lines, flags, keeps and main loop), on the clock of
updates done = the LINES of metrics.jsonl (never the trainer's own "update": a --resume restarts it at 1). A straight line between the points:
  PRACTICE_P   0 -> 0.12 over updates 0 to 20, held to 60, then 0.05 to the end (change 5)
  NEAR_PAY     0 -> 5 (points of damage: the best near miss pays what 5 points of damage pay) over updates 0 to 20 (change 13); NEAR_OUT never written
  FGT_GATE     -30 (shut) at the start, -12 from the first update -> 0 at update 20: the hands' new token "fight22" (change 4)
  FGT_G        0 -> 1 over updates 60 to 100: the share of his new trips whose list has the four fight options (change 10)
  FGT_W        0 -> 1 over updates 60 to 100: the fight network's weapon nudge opens ...
  H2_WADD      1 -> 0 written over clocks 0 to 7, then 0 to the end (THE RESTART, 11-17: it was 60 to 100): a written value plays 2 to 3
               updates later, so 0 PLAYS by update 10, inside the window in which the item picker is frozen (--h2-freeze); its weapon scores
               never learn (--h2-wsc-freeze). H2_WPG is never written: 0 from the start (start_live.py, --head2-wpg 0), the weapon key's credit
               the hands' own
  THE RESTART's two alarms (alarms_22b.py), every update from update 1, each a MAJOR line: the gauntlet in hand (v14.in_hand.g) over 0.05;
  the weapon choice's speed (weapon.kl) over 0.045 (three times its normal 0.015). And every update the freeze's proof (the trainer's
  h2_freeze block) in one plain line, MAJOR if a held parameter moved.
  FGT_BIAS     THE ONE NUMBER, written ONCE when update 60 is logged (change 10): the mean of the fight block's "bias_to_set" over updates 51 to
               60 (the bias on the four scores at which their share of his decisions is what "the enemy" and the places hold then); decided once
               (watch/fgt_bias.json: a resume never decides twice); none to be had: not written, a MAJOR line
  AT UPDATE 60 a plain-words line (change 11): for each option, whether the hands carry it out (over updates 51 to 60: he reached the place or
  met the enemy on at least half of its practice trips, and dealt at least as much for what he took there as on his own choices) and how much
  practice it has had. Reported, never obeyed: nothing holds or steps back on its own (CLAUDE.md rule 6); every check logged, one under 40% a
  MAJOR PROBLEM. Kept with their optimizers: keep/policy_u<N>.pt + opt_u<N>.pt at the first save at or past updates 10, 60, 100 and every 20 after,
  and at the trainer's end (+ keep/policy_end_22b.pt, opt_end_22b.pt, never written over). Logged every update: 2.2a's generic lines (the ledger,
  the held draw, the slow plan, the pull and its proof, frags, weapons) and the fight block (practice trips by option and how they ended, damage
  on them against his own choices, the share of his decisions each destination wins, near misses, projectiles, the forecasts, the win scale and
  the sizes: a FLAG over 40, a FLAG for a win scale under 1, a MAJOR line for a non-finite number). NO flag on any count of trips or changes.
    python docs/runs/2.2/2.2b/ramp_22b.py <run> [--poll S] [--settle S] [--dir D] [--resume] [--once] [--scale K]
--scale K (the smoke only): every update number of the schedule divided by K (the stages walked K times faster).
tools/run/live_accept.py reads values(clock) and DIALS (every file the ramp could write; FGT_BIAS at the ends of its range)."""
import argparse
import json
import os
import shutil
import threading
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import alarms_22b  # noqa: E402  (the restart's two alarms and the freeze's proof line)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
SCHEDULE = {"PRACTICE_P": [(0, 0.0), (20, 0.12), (60, 0.12), (60.001, 0.05)], "NEAR_PAY": [(0, 0.0), (20, 5.0)],
            "FGT_GATE": [(0, -30.0), (0.001, -12.0), (20, 0.0)], "FGT_G": [(60, 0.0), (100, 1.0)], "FGT_W": [(60, 0.0), (100, 1.0)],
            "H2_WADD": [(0, 1.0), (7, 0.0)]}                     # (the restart, 11-17: written 0 at clock 7 so that 0 PLAYS by update 10: a
#                                                                       written value plays 2 to 3 updates later; then 0 for the run)
UNSCHEDULED = ("PULL_G", "HELD_G", "NEAR_OUT", "H2_WPG")     # (H2_WPG: 0 from start_live.py, never written: the weapon key the hands' own)               # (never written by the ramp)
BIAS_AT, BIAS_WIN = 60, 10
REPORT_AT = 60
SIZE_FLAG = 40.0
MAJOR = 0.40
FRAGS_MIN = 1.5
PROOF_MAX = 0.01
PROOF_FLOOR_FLAG = 0.003
RUN_TAG = "22b"
SCALE = [1.0]
OPTS = ("him", "cut", "angle", "away")
OPT_WORDS = dict(him="going at him", cut="cutting him off", angle="holding an angle on his path", away="backing off")


def value(name, clock):
    k_ = [(u_ / SCALE[0], y_) for u_, y_ in SCHEDULE[name]]
    if clock <= k_[0][0]:
        return float(k_[0][1])
    if clock >= k_[-1][0]:
        return float(k_[-1][1])
    for (u0_, y0_), (u1_, y1_) in zip(k_[:-1], k_[1:]):
        if u0_ <= clock <= u1_:
            return y0_ + (y1_ - y0_) * (clock - u0_) / float(u1_ - u0_)
    return float(k_[-1][1])


def sched(clock):
    """{name: its value at this clock}: the schedule's dials (the ramp writes these, and FGT_BIAS once decided)"""
    return {n_: round(value(n_, float(clock)), 6) for n_ in SCHEDULE}


TEST_BIAS = float(os.environ.get("RAMP22B_BIAS") or 0.0)


def values(clock):
    """(tools/run/live_accept.py) every file the ramp could write: the schedule's dials, and from update 60 FGT_BIAS at RAMP22B_BIAS (start.ps1
    checks its range's ends and 0)"""
    v_ = sched(clock)
    if float(clock) >= BIAS_AT / SCALE[0]:
        v_["FGT_BIAS"] = TEST_BIAS
    return v_


DIALS = tuple((n_, 0, 100, None, None, None) for n_ in SCHEDULE) + (("FGT_BIAS", 60, 60, -30.0, 30.0, 0.0),)
END = 100


def marks_now(n):
    """the marks (update numbers) a save is kept at, up to n: 10, 60, 100 and every 20 after"""
    s_ = SCALE[0]
    return sorted(set([int(round(10 / s_)), int(round(60 / s_)), int(round(100 / s_))] + [int(round(u_ / s_)) for u_ in range(120, max(120, int(n * s_) + 21), 20)]))


def bias_decide(lines, at=BIAS_AT, win=BIAS_WIN):
    """the one number: the mean bias_to_set of the fight blocks of updates at - win + 1 .. at (lines: the metrics in order) -> (value or None, the values)"""
    v_ = [_dig(m_, ("fight", "decisions", "bias_to_set")) for m_ in lines[max(0, at - win):at]]
    k_ = [float(x_) for x_ in v_ if isinstance(x_, (int, float))]
    return (round(min(30.0, max(-30.0, sum(k_) / len(k_))), 6) if k_ else None), v_


def carried_report(lines, at=REPORT_AT, win=BIAS_WIN):
    """(change 11) the plain-words lines at update 60: for each option over updates at - win + 1 .. at: its practice trips, how they ended, the
    damage dealt for the damage taken on practice trips against his own choices -> (lines of text, {option: carried?})"""
    w_ = lines[max(0, at - win):at]
    tot_ = {o_: dict(dealt=0, attempted=0, arrived=0, met=0, died=0, timed_out=0, held_to_the_end=0, arrived_trips=0, sighted_while_holding=0)
            for o_ in OPTS}
    hs_ = 0.0
    allp_ = {o_: 0 for o_ in OPTS}
    dm_ = dict(pd=0.0, pt=0.0, od=0.0, ot=0.0)
    for m_ in lines[:at]:
        for o_ in OPTS:
            allp_[o_] += int(_dig(m_, ("fight", "practice", o_, "dealt")) or 0)
    for m_ in w_:
        for o_ in OPTS:
            for k_ in tot_[o_]:
                tot_[o_][k_] += int(_dig(m_, ("fight", "practice", o_, k_)) or 0)
        hs_ += float(_dig(m_, ("fight", "practice", "angle", "held_s_after_arrival")) or 0.0)
        d_ = _dig(m_, ("fight", "damage")) or {}
        for k_, (a_, b_) in (("pd", ("practice", "dealt_s")), ("pt", ("practice", "taken_s")), ("od", ("own", "dealt_s")), ("ot", ("own", "taken_s"))):
            sec_ = float(_dig(d_, (a_, "seconds")) or 0.0)
            dm_[k_] += float(_dig(d_, (a_, b_)) or 0.0) * sec_
        dm_["ps"] = dm_.get("ps", 0.0) + float(_dig(d_, ("practice", "seconds")) or 0.0)
        dm_["os"] = dm_.get("os", 0.0) + float(_dig(d_, ("own", "seconds")) or 0.0)
    rp_ = dm_["pd"] / dm_["pt"] if dm_["pt"] > 0 else None
    ro_ = dm_["od"] / dm_["ot"] if dm_["ot"] > 0 else None
    out, ok = [], {}
    out.append("UPDATE {}: WHAT THE HANDS DO WITH THE FIGHT OPTIONS (updates {} to {}; from now on the four options enter his own list, their "
               "share 0 -> 1 over 40 updates, whatever these numbers say). On practice trips he dealt {} points of damage for each point he took; "
               "on his own choices {}.".format(at, at - win + 1, at, "{:.2f}".format(rp_) if rp_ is not None else "an unknown number",
                                               "{:.2f}".format(ro_) if ro_ is not None else "an unknown number"))
    dl_ = sum(tot_[o_]["dealt"] for o_ in OPTS)
    out.append("  Practice dealt in these ten updates: {} trips ({}); each kind is drawn equally often and dealt only when it is possible at that "
               "moment (attempted: {}).".format(dl_, ", ".join("{} {} ({:.0%})".format(OPT_WORDS[o_], tot_[o_]["dealt"], tot_[o_]["dealt"] / max(1, dl_))
                                                               for o_ in OPTS), ", ".join("{} {}".format(o_, tot_[o_]["attempted"]) for o_ in OPTS)))
    for o_ in OPTS:
        t_ = tot_[o_]
        e_ = t_["arrived"] + t_["met"] + t_["died"] + t_["timed_out"]
        rch_ = t_["arrived"] + t_["met"] + (t_["held_to_the_end"] if o_ == "angle" else 0)   # (an angle trip holds after arriving: reached)
        rm_ = rch_ / e_ if e_ else None
        ok[o_] = bool(rm_ is not None and rm_ >= 0.5 and (rp_ is None or ro_ is None or rp_ >= ro_))
        out.append("  {}: {} practice trips so far ({} in these ten updates); of those that ended he {} on {} ({}), was killed on {}, ran out of "
                   "time on {}. {}".format(
                       OPT_WORDS[o_].capitalize(), allp_[o_], t_["dealt"], "got there or met the enemy" if o_ != "away" else "got away or met the enemy",
                       rch_, "{:.0%}".format(rm_) if rm_ is not None else "none ended", t_["died"], t_["timed_out"],
                       "THE HANDS CARRY IT OUT." if ok[o_] else "THE HANDS DO NOT CARRY IT OUT (the card's mark: at least half reached or met, and "
                       "the damage trade no worse than on his own choices): it enters his list anyway and may be learnt away as in 1.7a; the owner "
                       "may lengthen the practice or stop.") + (" At the angle (a trip holds there until he sees the enemy, 4 s from its start, or "
                       "death): he arrived on {} trips, held {:.1f} s on average after arriving, saw the enemy come while holding on {}, and held "
                       "to the end without a sighting on {} (counted as reached).".format(t_["arrived_trips"], hs_ / max(1, t_["arrived_trips"]),
                                                                                         t_["sighted_while_holding"], t_["held_to_the_end"]) if o_ == "angle" else ""))
    return out, ok


def fight_lines(m_, u_, log):
    """(2.2b) the update's fight block in lines; the flags (sizes over 40, a win scale under 1, a non-finite number)"""
    f_ = m_.get("fight")
    if not f_:
        if u_:
            log("MAJOR PROBLEM update {}: no fight block in the metrics (the run has no --fight22 1, or its record failed)".format(u_))
        return
    if f_.get("record_error"):
        log("MAJOR PROBLEM update {}: the fight block's record failed: {}".format(u_, f_["record_error"]))
        return
    pl_, pr_, dm_, dc_ = f_.get("played") or {}, f_.get("practice") or {}, f_.get("damage") or {}, f_.get("decisions") or {}
    log("update {}: fight: plays FGT_G {} FGT_W {} PRACTICE_P {} H2_WADD {} gate {} bias {} (applied {}) league with its own {} | practice trips ".format(
        u_, pl_.get("FGT_G"), pl_.get("FGT_W"), pl_.get("PRACTICE_P"), pl_.get("h2_wadd"), pl_.get("gate"), pl_.get("sbias"), pl_.get("bias_applied"),
        pl_.get("league_fight")) + " | ".join("{} dealt {} (own-picked {}) arrived {} met {} died {} timed out {} reached-or-met {} enemy passed {}".format(
            o_, (pr_.get(o_) or {}).get("dealt"), (pr_.get(o_) or {}).get("own_picked"), (pr_.get(o_) or {}).get("arrived"), (pr_.get(o_) or {}).get("met"),
            (pr_.get(o_) or {}).get("died"), (pr_.get(o_) or {}).get("timed_out"), (pr_.get(o_) or {}).get("reached_or_met"),
            (pr_.get(o_) or {}).get("enemy_passed")) for o_ in OPTS))
    sh_, an_ = pr_.get("share") or {}, pr_.get("angle") or {}
    log("update {}: fight: practice: attempted {} (by kind {}), dealt {} = {} of his decisions; dealt by kind {} | the angle: arrived {} trips, held {} s "
        "after arriving ({} s a trip), saw the enemy while holding {}, held to the end {}".format(
            u_, sh_.get("attempted"), {o_: (pr_.get(o_) or {}).get("attempted") for o_ in OPTS}, sh_.get("dealt"), sh_.get("practice_of_his_decisions"),
            sh_.get("dealt_by_kind"), an_.get("arrived_trips"), an_.get("held_s_after_arrival"), an_.get("held_s_per_arrival"),
            an_.get("sighted_while_holding"), an_.get("held_to_the_end")))
    log("update {}: fight: damage a second on practice trips dealt {} taken {} ({} s) | on his own choices dealt {} taken {} ({} s) | his decisions {}: "
        "the enemy and the places {} | list decisions {}: the fight side wins {} | bias to set {} (now {})".format(
            u_, _dig(dm_, ("practice", "dealt_s")), _dig(dm_, ("practice", "taken_s")), _dig(dm_, ("practice", "seconds")), _dig(dm_, ("own", "dealt_s")),
            _dig(dm_, ("own", "taken_s")), _dig(dm_, ("own", "seconds")), dc_.get("n"), dc_.get("enemy_and_places"), dc_.get("list_decisions"),
            dc_.get("fight_side_wins"), dc_.get("bias_to_set"), dc_.get("bias_now")))
    log("update {}: fight: the destinations his decisions won {}".format(u_, dc_.get("share")))
    nm_, pj_ = f_.get("near_miss") or {}, f_.get("projectiles") or {}
    log("update {}: fight: near misses paid {} (f summed {}, lost to the cap {}) of {} bursts near an unhurt enemy, of {} projectiles burst; their pay "
        "{} | projectiles a player-minute (in view / out of view / hits): {}".format(
            u_, nm_.get("paid"), nm_.get("f_sum"), nm_.get("f_capped"), nm_.get("bursts_near_unhurt"), nm_.get("projectiles_burst"), nm_.get("pay_his_seats"),
            " ".join("{} {}/{}/{}".format(w_, (pj_.get(w_) or {}).get("fired_min_in_view"), (pj_.get(w_) or {}).get("fired_min_out_of_view"),
                                          (pj_.get(w_) or {}).get("hits_min")) for w_ in ("rl", "gl", "pg"))))
    ls_ = f_.get("lesson") or {}
    log("update {}: fight: its lesson rows {} events {} forecast errors {} | loss value {} policy {} weapon {} clipped {} | sizes {} | win scale {} | "
        "weapon out of fights {} | seat-frames {} | non-finite {} | {} s".format(
            u_, ls_.get("rows"), ls_.get("events"), ls_.get("forecast_err_before"), ls_.get("loss_value"), ls_.get("loss_pg"), ls_.get("loss_weapon"),
            ls_.get("clip_share"), ls_.get("sizes"), ls_.get("win_scale"), f_.get("weapon_out_of_fights"), f_.get("seat_frames"), f_.get("nonfinite"),
            ls_.get("secs")))
    tp_ = f_.get("tracker_pass") or {}
    log("update {}: the tracker's pass odds on the fight rows: {} rows, {} questions, loss {}{}".format(
        u_, tp_.get("rows"), tp_.get("questions"), tp_.get("loss"), " SKIPPED: {}".format(tp_.get("skipped")) if tp_.get("skipped") else ""))
    sz_ = f_.get("sizes_sums") or {}
    if sz_:
        log("update {}: fight: the sums' parts (centred sizes): his list items {} fight options {} | the weapon key hands {} fight network {}".format(
            u_, sz_.get("items"), sz_.get("fight"), sz_.get("weapon_hands"), sz_.get("weapon_fight")))
    big_ = {k_: v_ for k_, v_ in list((sz_ or {}).items()) + [("lesson " + k_, v_) for k_, v_ in ((ls_.get("sizes") or {}).items())
                                                              if k_ in ("scores", "weapon", "l1", "l3")] if isinstance(v_, (int, float)) and v_ > SIZE_FLAG}
    if big_:
        log("FLAG update {}: a part of a sum or a decayed layer over {} (rule 11): {}".format(u_, SIZE_FLAG, big_))
    if f_.get("win_scale_below_flat"):
        ws_ = ls_.get("win_scale") or {}
        for k_, who_ in (("items_ratio", "the item picker (its flat pay: the items)"), ("fight_ratio", "the fight network (its flat pay: damage, frags, deaths, far rails, near misses)")):
            if k_ in f_["win_scale_below_flat"]:
                log("FLAG update {}: the win part is smaller than the flat pay for {}: the win part (x its scale) is {} of the flat pay's size, "
                    "under 1 (change 9 wants it at least as large)".format(u_, who_, ws_.get(k_)))
    if (f_.get("nonfinite") or 0) > 0:
        log("MAJOR PROBLEM update {}: THE FIGHT NETWORK GAVE {} NON-FINITE NUMBERS (zero for those seats)".format(u_, f_.get("nonfinite")))


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


def _dig(d, ks):
    for k_ in ks:
        if not isinstance(d, dict):
            return None
        d = d.get(k_)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--scale", type=float, default=1.0, help="(the smoke only) the schedule's update numbers divided by this")
    a = ap.parse_args()
    SCALE[0] = max(1e-6, float(a.scale))
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    WD, LIVE, POL, OPT, KEEP, MET = (os.path.join(D, "watch"), os.path.join(D, "live.json"), os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt"),
                                     os.path.join(D, "keep"), os.path.join(D, "metrics.jsonl"))
    LOGF = os.path.join(os.path.dirname(D), a.run + ".log")
    os.makedirs(WD, exist_ok=True)
    os.makedirs(KEEP, exist_ok=True)
    WRITES, WRITES0, WLOCK = [], {}, threading.Lock()
    BP_ = os.path.join(WD, "fgt_bias.json")
    BIAS_D = [json.load(open(BP_, encoding="utf-8")) if os.path.exists(BP_) else None]    # (a resume: never decided twice)
    REP_ = os.path.join(WD, "fight_report_60.json")
    REP_D = [os.path.exists(REP_)]

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
        """the values that may have played: the start file's, the last writes, the live file's now"""
        with WLOCK:
            return [dict(WRITES0).get(name)] + [v2_.get(name) for w2_, v2_ in WRITES[-4:]] + [live_now().get(name)]

    cur = json.load(open(LIVE, encoding="utf-8"))
    WRITES0.update({n_: cur.get(n_) for n_ in tuple(SCHEDULE) + ("FGT_BIAS",) + UNSCHEDULED})
    if not a.resume and not a.once:
        for n_ in SCHEDULE:
            assert abs(float(cur.get(n_, -99)) - value(n_, 0.0)) < 1e-9, "{} is {} in live.json, not its start {} (start_live.py)".format(n_, cur.get(n_), value(n_, 0.0))
        assert "FGT_BIAS" not in cur, "FGT_BIAS is in live.json at the start: it is written once, at update 60"
        for n_ in ("PULL_G", "HELD_G"):
            assert n_ in cur, "{} is not in live.json (the ramp never writes it: start_live.py puts it there)".format(n_)

    def update_lines(m_, base, u_):
        for l_ in alarms_22b.lines(m_, u_):                             # (the restart, 11-17) the two alarms and the freeze's proof, first
            log(l_)
        pt_ = m_.get("pay_terms") or {}
        pm_, ss_ = pt_.get("per_player_min") or {}, pt_.get("size_share") or {}
        if pm_:
            log("update {}: ledger a player-minute: damage dealt {} taken {} | frags {} deaths {} | win part {} (size share {}) | items MH {} RA {} YA {} "
                "points {} decay {} | total {}".format(
                    u_, pm_.get("dmg_dealt"), pm_.get("dmg_taken"), pm_.get("frag"), pm_.get("death"), pm_.get("win_part"), ss_.get("win_part"),
                    pm_.get("item_MH"), pm_.get("item_RA"), pm_.get("item_YA"), pm_.get("item_points"), pm_.get("item_decay"),
                    pt_.get("total_per_player_min")))
            # (2.2b, the coordinator's fix C: 2.2a's "win part over 0.6 of the pay's size" flag is retired: the owner wants the win part at least
            # the size of each decider's flat pay; its opposite is flagged in fight_lines, from the fight block's win scale)
        dg_ = m_.get("dodge_gate") or {}
        if dg_:
            import math as math_
            tk_ = max(-30.0, math_.log(dg_["cols"])) if (dg_.get("cols") or 0) > 0 else -30.0
            log("update {}: dodge gate: columns {} token {}".format(u_, dg_.get("cols"), dg_.get("token")))
            if abs(float(dg_.get("token", 0.0)) - tk_) > 1e-3:
                log("MAJOR PROBLEM update {}: the dodge token's gate {} is not log(DODGE_G {}) = {:.3f}".format(u_, dg_.get("token"), dg_.get("cols"), tk_))
        elif u_:
            log("MAJOR PROBLEM update {}: no dodge gate in the metrics (the network has no dodge token?)".format(u_))
        hd_ = m_.get("held")
        if hd_:
            log("update {}: held draw: share played {} (next {}) | seat-frames on it {} | readings a second {} | new draws a seat-minute {} | "
                "CHANGES MID-TRIP a seat-minute {}".format(u_, hd_.get("g"), hd_.get("g_next"), hd_.get("share"), hd_.get("readings_s"),
                                                            hd_.get("new_draws_min"), hd_.get("changes_min")))
            cand_h = written("HELD_G")
            if not any(c2_ is not None and abs(float(hd_.get("g", -1)) - float(c2_)) < 1e-4 for c2_ in cand_h):
                log("MAJOR PROBLEM update {}: the held share played {} is none of {} (the start's, the live file's now)".format(u_, hd_.get("g"), cand_h))
        elif u_:
            log("MAJOR PROBLEM update {}: no held record in the metrics (the run has no --held 1?)".format(u_))
        pn_ = m_.get("plan")
        if pn_:
            hz_ = " | ".join("{} ({} ticks): n {} kl plan {} now {} top1 plan {} now {}".format(
                k2_, (pn_.get(k2_) or {}).get("ticks"), (pn_.get(k2_) or {}).get("n"), (pn_.get(k2_) or {}).get("kl_plan"),
                (pn_.get(k2_) or {}).get("kl_now"), (pn_.get(k2_) or {}).get("top1_plan"), (pn_.get(k2_) or {}).get("top1_now"))
                for k2_ in ("h2s", "h5s") if k2_ in pn_)
            ch_ = pn_.get("changes") or {}
            log("update {}: slow plan: {} | loss after {}".format(u_, hz_, pn_.get("loss")))
            if "news_back" in ch_ or ch_.get("kinds_off"):
                log(kinds_line(ch_, u_))
        elif u_ and hd_:
            log("MAJOR PROBLEM update {}: no plan record in the metrics (the run has no --plan 1, or the plan's readouts failed)".format(u_))
        pu_ = m_.get("pull")
        if pu_:
            pa_ = pu_.get("parts") or {}
            log("update {}: pull: strength played {} (next {}; the league's {}) on horizon {} ({} ticks), floor {} | size {} length {} largest {} on {} "
                "frames | the target's parts: hands {} head {} pull {} | proof first_err {} (as the learner reads them: {}) "
                "| plan last layer {} decay {}".format(
                    u_, pu_.get("g"), pu_.get("g_next"), pu_.get("g_opp"), pu_.get("h"), pu_.get("ticks"), pu_.get("floor"), pu_.get("size"),
                    pu_.get("norm"), pu_.get("max"), pu_.get("frames"), pa_.get("hands"), pa_.get("head"), pa_.get("pull"), pu_.get("first_err"),
                    pu_.get("first_err_half"), pu_.get("plan_w"), pu_.get("decay")) + (
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
        fight_lines(m_, u_, log)
        fm_ = m_.get("frags_per_match_min")
        if fm_ is not None:
            log("update {}: frags a match-minute {}{}".format(u_, fm_, " FLAG: under {} (passivity, the card's alarm)".format(FRAGS_MIN) if fm_ < FRAGS_MIN else ""))
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
        if len(base) < 5:
            base.append(now_)
            return
        b_ = [sum(x[i] for x in base) / len(base) for i in range(4)]
        if now_[0] < 0.9 * b_[0] or now_[1] < 0.9 * b_[1]:
            log("FLAG update {}: speed on trips {} (start {:.0f}), share over 320 {} (start {:.3f})".format(u_, now_[0], b_[0], now_[1], b_[1]))
        # (no flag on trips a player-minute, on targets reached or on any count of changes of mind: owner 2026-11-15/16)

    def flags(once=False):
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": "the control (2.2a's update 90)", "checks_ref.jsonl": "2.1d's end (the long-term control)"}
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
            st_ = {}
            try:
                st_ = json.load(open(os.path.join(D, "live_status.json"), encoding="utf-8"))
            except (OSError, ValueError):
                pass
            if st_.get("status") == "refused" and st_.get("update") != seen_st[0]:
                seen_st[0] = st_.get("update")
                log("MAJOR PROBLEM update {}: THE TRAINER REFUSED live.json, nothing applied: {}".format(st_.get("update"), st_.get("reason")))
            ap_ = {}
            try:
                ap_ = json.load(open(os.path.join(D, "live_applied.json"), encoding="utf-8"))
            except (OSError, ValueError):
                pass
            if ap_.get("from_update") is not None and ap_.get("from_update") != seen_ap[0]:
                seen_ap[0] = ap_.get("from_update")
                got_ = {n2_: (ap_.get("file") or {}).get(n2_) for n2_ in tuple(SCHEDULE) + (("FGT_BIAS",) if BIAS_D[0] else ())}
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

    if a.once:
        flags(once=True)
        return

    if a.once:
        flags(once=True)
        return

    def mtime():
        try:
            return os.path.getmtime(POL)
        except FileNotFoundError:
            return 0.0

    def keep(name):
        """a save with its optimizer; NEVER written over (the review: the end on a mark's update keeps the mark's files)"""
        if os.path.exists(os.path.join(KEEP, name)) or os.path.exists(os.path.join(KEEP, name.replace("policy_", "opt_", 1))):
            log("keep/{} is there already: kept as it is (never written over)".format(name))
            return False
        shutil.copy2(POL, os.path.join(KEEP, name))
        shutil.copy2(OPT, os.path.join(KEEP, name.replace("policy_", "opt_", 1)))
        return True

    def decide(clock):
        """the one number and the plain-words report, once, when update 60 is logged"""
        L_ = None
        if BIAS_D[0] is None and clock >= BIAS_AT / SCALE[0]:
            L_ = jl(MET)
            at_ = int(round(BIAS_AT / SCALE[0]))
            b_, vals_ = bias_decide(L_, at_, max(1, int(round(BIAS_WIN / SCALE[0]))))
            d_ = dict(at=at_, bias=b_, values=vals_, when=time.strftime("%Y-%m-%d %H:%M:%S"))
            with open(BP_ + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(d_, fh, indent=1)
            os.replace(BP_ + ".tmp", BP_)
            BIAS_D[0] = d_
            if b_ is None:
                log("MAJOR PROBLEM update {}: THE ONE NUMBER (the four options' bias) could not be had (no bias_to_set in updates {} to {}): not "
                    "written; the four start at the bias they have".format(at_, at_ - BIAS_WIN + 1, at_))
            else:
                log("UPDATE {}: the four fight options' bias is set once to {} (the mean of {}): their total share of his decisions starts at what "
                    "\"the enemy\" and the places held; learnt from here".format(at_, b_, vals_))
        if not REP_D[0] and clock >= REPORT_AT / SCALE[0]:
            L_ = L_ if L_ is not None else jl(MET)
            at_ = int(round(REPORT_AT / SCALE[0]))
            lines_, ok_ = carried_report(L_, at_, max(1, int(round(BIAS_WIN / SCALE[0]))))
            for l_ in lines_:
                log(l_)
            if not all(ok_.values()):
                log("MAJOR PROBLEM update {}: THE HANDS DO NOT CARRY OUT {}: reported, not obeyed (the ramp goes on); the owner decides".format(
                    at_, [OPT_WORDS[o_] for o_, v_ in ok_.items() if not v_]))
            with open(REP_, "w", encoding="utf-8") as fh:
                json.dump(dict(at=at_, carried=ok_, lines=lines_), fh, indent=1)
            REP_D[0] = True

    def write(clock):
        """the dials of this clock into live.json (re-read: every other name kept as the file has it)"""
        decide(clock)
        v_ = sched(clock)
        if BIAS_D[0] is not None and BIAS_D[0].get("bias") is not None:
            v_["FGT_BIAS"] = float(BIAS_D[0]["bias"])
        d = json.load(open(LIVE, encoding="utf-8"))
        d.update(v_)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        with WLOCK:
            WRITES.append((clock, v_))
        return v_

    def flags_guard():
        import traceback
        while True:
            try:
                flags()
            except Exception:
                log("MAJOR PROBLEM: THE RAMP'S FLAG THREAD CRASHED (it starts again; lines may repeat): " + traceback.format_exc().replace(chr(10), " | ")[-1500:])
                time.sleep(60)

    threading.Thread(target=flags_guard, daemon=True).start()
    log("ramp_22b on for {} (scale {}): PRACTICE_P 0 -> 0.12 over updates 0 to 20, held to 60, then 0.05; NEAR_PAY 0 -> 5 over 0 to 20; the hands' "
        "token -30, then -12 -> 0 over 0 to 20; H2_WADD written 1 -> 0 over clocks 0 to 7 so that 0 plays by update 10, then 0 (the restart: the "
        "item picker's weapon push leaves while it is frozen; the weapon key is taught by the hands' own pay from the start, H2_WPG 0 never written); FGT_G and FGT_W 0 -> 1 over 60 to 100; FGT_BIAS once at 60 ({}); the report at "
        "60 ({}); saves kept at {} ... and the end; never written: {}; FREE: the clock never holds or steps back, a check under 40% is a MAJOR "
        "PROBLEM; every update: the gauntlet in hand over 5% and the weapon KL over 0.045 are MAJOR, the freeze's proof in a line{}".format(a.run, SCALE[0], "decided already: {}".format(BIAS_D[0].get("bias")) if BIAS_D[0] else "not yet",
                           "made already" if REP_D[0] else "not yet", marks_now(140), UNSCHEDULED, " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = len(L0) if (a.resume and L0) else 0
    seen, marked, ended = mtime(), set(), [False]
    if a.resume:
        marked = {k_ for k_ in marks_now(10 ** 6) if any(f_.startswith("policy_u") and f_.endswith(".pt") and f_[8:-3].isdigit() and int(f_[8:-3]) >= k_
                                            for f_ in os.listdir(KEEP))}
        if done_n:
            v_ = write(float(done_n))
            log("clock {} after update {} (resumed): wrote {}".format(done_n, done_n, v_))
    else:
        v_ = write(0.0)
        log("clock 0: wrote {}".format(v_))
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = len(L)
        if n > done_n:
            v_ = write(float(n))
            log("clock {} after update {}: wrote {}".format(n, n, v_))
            done_n = n
        m_ = mtime()
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            for k_ in marks_now(n):
                if n >= k_ and k_ not in marked:
                    marked.add(k_)
                    keep("policy_u{}.pt".format(n))
                    log("kept keep/policy_u{}.pt with its optimizer (the mark {}{})".format(n, k_, ": the save the fight options enter his list from" if k_ == 60 else ""))
        if not ended[0]:
            try:
                tail_ = open(LOGF, encoding="utf-8", errors="replace").read()[-400:].strip().splitlines()
            except OSError:
                tail_ = []
            if tail_ and tail_[-1].startswith("exit "):
                ended[0] = True
                time.sleep(a.settle)
                keep("policy_u{}.pt".format(n))
                for nm_ in ("policy_end_{}.pt".format(RUN_TAG), "opt_end_{}.pt".format(RUN_TAG)):
                    if not os.path.exists(os.path.join(KEEP, nm_)):
                        shutil.copy2(POL if nm_.startswith("policy") else OPT, os.path.join(KEEP, nm_))
                log("the trainer ended ({}): kept keep/policy_u{}.pt and policy_end_{}.pt with their optimizers (never written over)".format(tail_[-1], n, RUN_TAG))



def _r(x, k=5):
    return None if x is None else round(float(x), k)


if __name__ == "__main__":
    main()
