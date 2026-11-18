"""2.2c's dials (docs/runs/2.2/2.2c/CARD.md "The schedule"; made from 2.2b's ramp: its generic lines, flags, keeps and main loop), on the clock of
updates done = the LINES of metrics.jsonl (never the trainer's own "update": a --resume restarts it at 1). A straight line between the points:
  H2_WADD      1 -> 0 written over clocks 0 to 7, then 0 to the end (kept from 2.2b's restart): a written value plays 2 to 3 updates later, so
               0 PLAYS by update 10, inside the window in which the item picker is frozen (--h2-freeze); its weapon scores never learn
               (--h2-wsc-freeze). H2_WPG is never written: 0 from the start (start_live.py, --head2-wpg 0), the weapon key the hands' own
  FGT_GATE     -30 (shut) to clock 8, then -> 0 at clock 17 (written; played 2 to 3 updates later: the hands are shown the lever, its gate
               opening over updates 10 to 20, the card)
  NOT WRITTEN  LEV_G (1 from the start's live.json: the trainer plays the lever at 0 on the rollouts of the run's first 10 updates by its own
               count, --lev-from 10, and at LEV_G from update 11's), the contest pay's and the rail chain's dials (CONTEST_W 0.8, CEDE_W 0.1,
               RAIL_PICK_PAY 0.15, RAIL_LINE_PAY 0.10, RAIL_FAR_PAY 0.5: full from update 0), NEAR_PAY 5 (2.2b's size from update 0),
               PULL_G, HELD_G, NEAR_OUT, H2_WPG. Every one stays live: the owner may set it by hand.
  The two alarms (alarms_22c.py), every update from update 1, each a MAJOR line: the gauntlet in hand (v14.in_hand.g) over 0.05; the hands'
  weapon choice's speed (kl_heads[6], FIXED: 2.2b read the switched-off weapon.kl) over three times its normal. And every update the freeze's
  proof (the trainer's h2_freeze block) in one plain line, MAJOR if a held parameter moved.
  Every update (the card's "Reported every update"): the lever (its share played, which must be 0 to update 10 and LEV_G from update 11; its
  size, flagged over 40 by rule 13; its average when he is ahead, level and behind on stack and just after a frag, and how often he heads for
  the enemy in each); the contest pay (the enemy's big pickups under pressure, the pressure, steals, free pickups and how far he was, the pay
  to and from him at the pickups and by the second, the cap, his own big pickups); his shells at items (in and out of view, by weapon; those
  that burst near an item nobody took, those 4 to 8 s before a pickup); the rail (in hand, shots and far hits a minute, the chain's pays);
  every new pay term's size and share of his pay; frags and damage a minute; the lever's lesson. Reported, never obeyed: nothing holds or
  steps back on its own (CLAUDE.md rule 6); every check logged, one under 40% a MAJOR PROBLEM. Kept with their optimizers: keep/policy_u<N>.pt +
  opt_u<N>.pt at the first save at or past updates 10, 20 and every 20 after, and at the trainer's end (+ keep/policy_end_22c.pt, opt_end_22c.pt,
  never written over). NO flag on any count of trips, pickups or changes.
    python docs/runs/2.2/2.2c/ramp_22c.py <run> [--poll S] [--settle S] [--dir D] [--resume] [--once] [--scale K]
--scale K (the smoke only): every update number of the schedule divided by K (the stages walked K times faster).
start.ps1's live accept reads values(clock) and DIALS (every file the ramp could write)."""
import argparse
import json
import os
import shutil
import threading
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import alarms_22c  # noqa: E402  (the two alarms, the speed one fixed, and the freeze's proof line)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
SCHEDULE = {"FGT_GATE": [(0, -30.0), (8, -30.0), (17, 0.0)], "H2_WADD": [(0, 1.0), (7, 0.0)]}   # (written at clock c, a value plays at about c + 2:
#                                                                       the gate opens over updates 10 to 20, H2_WADD 0 plays by update 10)
UNSCHEDULED = ("PULL_G", "HELD_G", "NEAR_OUT", "H2_WPG", "NEAR_PAY", "LEV_G", "CONTEST_W", "CEDE_W", "RAIL_PICK_PAY", "RAIL_LINE_PAY",
               "RAIL_FAR_PAY")                       # (never written by the ramp: live, at the start file's values)
LEV_FROM = 10                                         # (the trainer's --lev-from: the lever plays at 0 on the rollouts of updates 1 to 10)
LEV_ON = 1.0                                          # (live LEV_G from the start: what plays from update 11)
BIAS_AT, BIAS_WIN = 10 ** 9, 10                      # (2.2c: no one number and no update-60 report: no fight options)
REPORT_AT = 10 ** 9
SIZE_FLAG = 40.0
MAJOR = 0.40
FRAGS_MIN = 1.5
PROOF_MAX = 0.01
PROOF_FLOOR_FLAG = 0.003
RUN_TAG = "22c"
SCALE = [1.0]


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


TEST_BIAS = 0.0


def values(clock):
    """(start.ps1's live accept) every file the ramp could write: the schedule's dials"""
    return sched(clock)


DIALS = tuple((n_, 0, 100, None, None, None) for n_ in SCHEDULE)
END = 100


def marks_now(n):
    """the marks (update numbers) a save is kept at, up to n: 10, then every 20 (20, 40, ...)"""
    s_ = SCALE[0]
    return sorted(set([int(round(10 / s_))] + [int(round(u_ / s_)) for u_ in range(20, max(20, int(n * s_) + 21), 20)]))


def fight_lines(m_, u_, log):
    """(2.2c) the update's fight block (the lever, the contest pay, the rail, the pays' sizes) in lines; the flags (the lever's size over 40,
    a win scale under 1), the MAJOR lines (no block, a non-finite number, the lever played at a share it should not)"""
    f_ = m_.get("fight")
    if not f_:
        if u_:
            log("MAJOR PROBLEM update {}: no fight block in the metrics (the run has no --fight22 1 --lever 1, or its record failed)".format(u_))
        return
    if f_.get("record_error"):
        log("MAJOR PROBLEM update {}: the fight block's record failed: {}".format(u_, f_["record_error"]))
        return
    pl_, lv_, py_ = f_.get("played") or {}, f_.get("lever") or {}, f_.get("play") or {}
    bs_, sz_ = lv_.get("by_state") or {}, lv_.get("sizes") or {}
    want_ = 0.0 if u_ <= int(round(LEV_FROM / SCALE[0])) else None
    g_ = pl_.get("LEV_G")
    log("update {}: lever: played at share {} (H2_WADD {}, the hands' token gate {}; the league with its own {} at {}) | its size: |lever| {} (largest {}), "
        "what it adds {} | by his state (readings, the lever, how often headed for the enemy): {}".format(
            u_, g_, pl_.get("h2_wadd"), pl_.get("gate"), pl_.get("league_fight"), pl_.get("league_lev_g"), sz_.get("lever_abs"), sz_.get("lever_max"),
            sz_.get("lever_add_abs"), " | ".join("{} {} {} {}".format(k_, (bs_.get(k_) or {}).get("readings"), (bs_.get(k_) or {}).get("lever_mean"),
                                                                       (bs_.get(k_) or {}).get("headed_for_enemy"))
                                                 for k_ in ("ahead", "level", "behind", "after_frag_5s", "all"))))
    if want_ is not None and g_ is not None and abs(float(g_) - want_) > 1e-9:
        log("MAJOR PROBLEM update {}: THE LEVER PLAYED AT SHARE {} on update {} (it must be 0 to update {}: --lev-from)".format(u_, g_, u_, LEV_FROM))
    if want_ is None and u_ >= int(round((LEV_FROM + 2) / SCALE[0])) and g_ is not None and abs(float(g_) - LEV_ON) > 1e-9:
        log("FLAG update {}: the lever played at share {} (the start's LEV_G is {}: set by hand?)".format(u_, g_, LEV_ON))
    log("update {}: play: frags a seat-minute {} damage a seat-minute {} | headed for the enemy {} of his living frames | projectiles a seat-minute "
        "(in view / out of view / hits): {}".format(u_, py_.get("frags_min"), py_.get("damage_min"), py_.get("headed_for_enemy"),
                                                    " ".join("{} {}/{}/{}".format(w_, ((f_.get("projectiles") or {}).get(w_) or {}).get("fired_min_in_view"),
                                                                                  ((f_.get("projectiles") or {}).get(w_) or {}).get("fired_min_out_of_view"),
                                                                                  ((f_.get("projectiles") or {}).get(w_) or {}).get("hits_min"))
                                                             for w_ in ("rl", "gl", "pg"))))
    c_ = f_.get("contest") or {}
    if c_:
        log("update {}: contest: the enemy's big pickups {}, under pressure {} (mean pressure {}: set on it {}, shells {}, damage {}, less taken {}) | "
            "free {} (his distance from the item {} units on average; under 1000 {}, 1000 to 2000 {}, over 2000 {}) | weapons {} under pressure {} | "
            "steals {} | at the pickups to him {} from him {} | by the second to him {} from him {} ({} frames) | the cap reached {} | his own big "
            "pickups {} ({} a seat-minute)".format(
                u_, c_.get("enemy_big_pickups"), c_.get("under_pressure_share"), c_.get("pressure_mean"), c_.get("rung1_mean"), c_.get("rung2_mean"),
                c_.get("rung3_mean"), c_.get("taken_off_mean"), c_.get("free_pickups"), c_.get("free_distance_mean"),
                *[(c_.get("free_distance_bins") or {}).get(k_) for k_ in ("under_1000", "d1000_2000", "over_2000")], c_.get("enemy_weapon_pickups"),
                c_.get("weapon_under_pressure_share"), c_.get("steals"), c_.get("pickup_pay_to_him"), c_.get("pickup_pay_from_him"),
                c_.get("by_second_to_him"), c_.get("by_second_from_him"), c_.get("by_second_frames"), c_.get("cap_reached"), c_.get("his_big_pickups"),
                c_.get("his_big_pickups_min")))
        sa_ = c_.get("shells_at_items") or {}
        log("update {}: his shells within 300 units of an item (in view / out of view: up, coming in 4 s, taken in the last 4 s): {} | near an item "
            "nobody then took within 8 s {} | 4 to 8 s before the enemy took it (no pay) {}".format(
                u_, " ".join("{} {}/{}".format(w_, "{}-{}-{}".format(*[((sa_.get(w_) or {}).get("in_view") or {}).get(k_) for k_ in ("up", "coming_4s", "taken_4s")]),
                                                "{}-{}-{}".format(*[((sa_.get(w_) or {}).get("out_of_view") or {}).get(k_) for k_ in ("up", "coming_4s", "taken_4s")]))
                             for w_ in ("rl", "gl", "pg")), c_.get("bursts_near_item_nobody_took"), c_.get("bursts_4_to_8s_before_pickup")))
    elif u_:
        log("MAJOR PROBLEM update {}: no contest counters in the fight block (the simulator without CONTEST=1?)".format(u_))
    rl_ = f_.get("rail") or {}
    log("update {}: rail: in hand {} of his living frames, shots {} and far hits (500 units and more) {} a seat-minute, the far-rail pay got {} lost {} | "
        "the chain: pickups paid {}, fresh sightings from beyond 768 {} ({} with the rail in hand), the long line's pay net {} size {}".format(
            u_, rl_.get("in_hand_share"), rl_.get("shots_min"), rl_.get("far_hits_min"), rl_.get("far_pay_got"), rl_.get("far_pay_lost"),
            rl_.get("pickup_pays"), rl_.get("far_sightings"), rl_.get("far_sightings_rail_in_hand"), rl_.get("long_line_pay_net"), rl_.get("long_line_pay_size")))
    pt_ = f_.get("pay_terms") or {}
    log("update {}: pay terms (sum, size, share of his pay's size): {}".format(u_, " | ".join("{} {} {} {}".format(k_, v_.get("sum"), v_.get("size"), v_.get("share"))
                                                                                    for k_, v_ in pt_.items())))
    ls_ = f_.get("lesson") or {}
    log("update {}: the lever's lesson: rows {} decisions {} (picked the enemy {}; share as played {}; advantage on the enemy {} on an item {}) | forecast "
        "errors {} | loss value {} policy {} clipped {} KL {} | sizes {} | decay {} | win scale {} | the tracker's pass odds {} | non-finite {} | {} s".format(
            u_, ls_.get("rows"), ls_.get("events"), ls_.get("picked_enemy"), ls_.get("g_played"), ls_.get("adv_enemy"), ls_.get("adv_item"),
            ls_.get("forecast_err_before"), ls_.get("loss_value"), ls_.get("loss_pg"), ls_.get("clip_share"), ls_.get("approx_kl"), ls_.get("sizes"),
            ls_.get("decay"), ls_.get("win_scale"), (f_.get("tracker_pass") or {}).get("loss"), f_.get("nonfinite"), ls_.get("secs")))
    if f_.get("flags"):
        log("FLAG update {}: the lever or the item picker's target scores over {} (rule 13): {} (sizes {}, lesson sizes {})".format(
            u_, SIZE_FLAG, f_["flags"], sz_, ls_.get("sizes")))
    if f_.get("win_scale_below_flat"):
        ws_ = ls_.get("win_scale") or {}
        for k_, who_ in (("items_ratio", "the item picker (its flat pay: the items, the contest pay, the rail's)"),
                         ("fight_ratio", "the fight network (its flat pay: damage dealt less taken, frags, deaths)")):
            if k_ in f_["win_scale_below_flat"]:
                log("FLAG update {}: the win part is smaller than the flat pay for {}: the win part (x its scale) is {} of the flat pay's size, "
                    "under 1 (rule 14 wants it at least as large)".format(u_, who_, ws_.get(k_)))
    if (f_.get("nonfinite") or 0) > 0:
        log("MAJOR PROBLEM update {}: THE LEVER GAVE {} NON-FINITE NUMBERS (zero for those seats)".format(u_, f_.get("nonfinite")))


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
    BP_ = os.path.join(WD, "fgt_bias_never.json")              # (2.2c: never decided)
    BIAS_D = [json.load(open(BP_, encoding="utf-8")) if os.path.exists(BP_) else None]    # (a resume: never decided twice)
    REP_ = os.path.join(WD, "fight_report_never.json")
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
        for l_ in alarms_22c.lines(m_, u_):                             # (kept from 2.2b's restart; the speed alarm fixed) the two alarms and the freeze's proof, first
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
        """(2.2c: no one number and no report: no fight options)"""
        return None

    def write(clock):
        """the dials of this clock into live.json (re-read: every other name kept as the file has it)"""
        decide(clock)
        v_ = sched(clock)
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
    log("ramp_22c on for {} (scale {}): H2_WADD written 1 -> 0 over clocks 0 to 7 (0 plays by update 10); the hands' token gate -30 to clock 8, "
        "then -> 0 at clock 17 (it opens over updates 10 to 20); LEV_G never written (1 from the start; the trainer plays the lever at 0 to update "
        "10 by its own count); the contest pay, the rail chain, NEAR_PAY 5 at full size from update 0, never written; saves kept at {} ... and the "
        "end; never written: {}; FREE: the clock never holds or steps back, a check under 40% is a MAJOR PROBLEM; every update: the gauntlet in "
        "hand over 5% and the hands' weapon-key KL over three times its normal are MAJOR, the freeze's proof in a line{}".format(
            a.run, SCALE[0], marks_now(100), UNSCHEDULED, " (resumed)" if a.resume else ""))
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
                    log("kept keep/policy_u{}.pt with its optimizer (the mark {}{})".format(n, k_, ": the save the lever starts from" if k_ == 10 else ""))
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
