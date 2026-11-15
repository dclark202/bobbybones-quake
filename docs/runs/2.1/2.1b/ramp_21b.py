"""2.1b's ramp (owner, 2026-11-14; docs/runs/2.1/2.1b/CARD.md): the lock's replacement opened step by step, ONLY when the owner names the step.
It never opens anything on a schedule of its own, never holds, never steps back (CLAUDE.md rule 6): it reads <run folder>/steps.json, which
the owner edits,
    {"B": null | <update>, "C": null | <update>, "D": null | <update>, "B_over": 20, "C_over": 30}
and after each new update writes into live.json only the two shares it computes (every other value kept as it is):
  A  (always, from the start)  the keep forks, the stay value's lesson, the keep choice's silent lesson; both shares 0: the lock decides
  B  KEEP_G 0 -> 1, a straight line over B_over updates from the update named (the keep choice's zone layer: contact and arrivals; quiet
     stays the lock)
  C  KEEPQ_G 0 -> 1 over C_over updates from the update named (the quiet layer's share of the quiet readings; it decides there only where
     KEEP_G's coin also gave the keep choice the second: the quiet layer's real share is KEEP_G x KEEPQ_G)
  D  nothing automatic: when both shares are 1 it records "D: the lock decides nowhere"; the update named is only recorded
An update named in the past (steps.json edited late) opens from the first update the ramp saw it at, never with a jump; it is logged.
Kept with their optimizers: the first saves at or past update 10 and at each step's start and end (keep/policy_u<update>_21b.pt).

Flagged to watch.log (each line "FLAG ..." or "MAJOR PROBLEM ..."; nothing acts on them; the owner decides):
  every check against the control (2.0e's end) and the long-term control (1.6a's end), one under 40% a MAJOR PROBLEM; the trainer refusing
  live.json (MAJOR); shares applied not as written (MAJOR); quiet re-decisions a reading (rec.keep.zone.quiet_changed) over 1.25x their
  mean over updates 1 to 5 (the lock's baseline in this run); trips a player-minute or targets reached more than 25% off their mean over
  updates 1 to 5; the stay value's labels under 50 an update, its held-out sign right at or under 0.5; the keep lesson's p more than 0.15
  from its target (zone and quiet); a weight of the keep choice's zone or quiet layer over 40 (rule 11 style); a stall (no new line in
  metrics.jsonl for 10 minutes); kept from 2.0e's ramp: a firing cost (MAJOR), the weapon or target scores' parts over 40, frags a
  match-minute under 1.5, the win part over 0.6 of the pay, the dodge token's gate not log(DODGE_G) (MAJOR); a missing map_sense record (the
  map sense learns silently: its skill, R2 by output, is reported every update). Plus one summary line an update.
A crash of a flag thread is logged as a MAJOR PROBLEM and the thread starts again (1.9a).
    python docs/runs/2.1/2.1b/ramp_21b.py <run> [--poll S] [--settle S] [--dir D] [--resume]

DIALS / dial_at: the two shares over a nominal clock, ONLY for tools/run/live_accept.py (it writes every value the shares can take into a
copy of live.json and reads it with the trainer's reader). The ramp's own clock is steps.json."""
import argparse
import json
import math
import os
import shutil
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DIALS = (("KEEP_G", 0, 20, 0.0, 1.0, 0.0),                  # (name, from, to, its value there, at the end, before): live_accept's nominal clock
         ("KEEPQ_G", 20, 50, 0.0, 1.0, 0.0))
NAMES = ("KEEP_G", "KEEPQ_G")
STEPS0 = {"B": None, "C": None, "D": None, "B_over": 20, "C_over": 30}
MARK_FIRST = 10
SIZE_FLAG = 40.0
MAJOR = 0.40
FRAGS_MIN = 1.5
QUIET_UP = 1.25                                               # (the brief: quiet re-decisions over 1.25x the run's first five updates)
MOVE_MAX = 0.25                                               # (trips, reached: more than 25% off the first five updates)
LABELS_MIN = 50
SIGN_MIN = 0.5
TEACH_GAP = 0.15                                              # (a hand-set alarm, not a target: the lesson's p this far from its target)
STALL_S = 600.0
BASE_N = 5


def dial_at(clock, lo, hi, v0, v1, pre):
    if clock < lo:
        return pre
    f = min(1.0, max(0.0, (clock - lo) / float(hi - lo)))
    return v0 + (v1 - v0) * f


def share_at(update, start, over):
    """a share opened from the update start over `over` updates (0 before; None: not named)"""
    if start is None or update < start:
        return 0.0
    return min(1.0, max(0.0, (update - start) / float(max(1, over))))


def check_steps(d):
    """steps.json's values: (the steps, None) or (None, why)"""
    if not isinstance(d, dict):
        return None, "not an object"
    s = dict(STEPS0)
    for k_ in ("B", "C", "D"):
        v_ = d.get(k_)
        if v_ is not None and (isinstance(v_, bool) or not isinstance(v_, (int, float)) or v_ < 0 or int(v_) != v_):
            return None, "{} must be null or an update (a whole number >= 0), not {!r}".format(k_, v_)
        s[k_] = None if v_ is None else int(v_)
    for k_ in ("B_over", "C_over"):
        v_ = d.get(k_, STEPS0[k_])
        if isinstance(v_, bool) or not isinstance(v_, (int, float)) or v_ < 1 or int(v_) != v_:
            return None, "{} must be a whole number of updates >= 1, not {!r}".format(k_, v_)
        s[k_] = int(v_)
    extra_ = sorted(set(d) - set(STEPS0))
    if extra_:
        return None, "unknown names {}".format(extra_)
    return s, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--once", action="store_true", help="(the smoke) one pass of the flags over the metrics there, nothing written but the logs")
    a = ap.parse_args()
    D = a.dir or os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data", "sim_runs", a.run)
    WD, LIVE, POL, OPT, KEEP, MET, STEPS = (os.path.join(D, "watch"), os.path.join(D, "live.json"), os.path.join(D, "policy.pt"),
                                            os.path.join(D, "opt.pt"), os.path.join(D, "keep"), os.path.join(D, "metrics.jsonl"),
                                            os.path.join(D, "steps.json"))
    STATE = os.path.join(WD, "ramp_21b_state.json")             # (the effective starts of B and C, the marks kept: a resume keeps them)
    os.makedirs(WD, exist_ok=True)
    os.makedirs(KEEP, exist_ok=True)
    WRITES, WRITES0, WLOCK = [], {}, threading.Lock()
    LOGLOCK = threading.Lock()

    def log(s):
        line = time.strftime("%m-%d %H:%M:%S ") + s
        with LOGLOCK:
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

    def num(x):
        try:
            return None if x is None else float(x)
        except (TypeError, ValueError):
            return None

    def flags():
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0}
        names = {"checks_prev.jsonl": "the control (2.0e's end)", "checks_ref.jsonl": "1.6a's end (the long-term control)"}
        if a.resume:
            seen = {f_: len(jl(os.path.join(WD, f_))) for f_ in seen}
        seen_m = [len(jl(MET)) if a.resume else 0]
        base = {"quiet": [], "trips": [], "reached": []}       # (the run's first five updates)
        seen_st, seen_ap = [None], [None]
        while True:                                          # (--once: one pass over what is there, then back; the smoke)
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
                got_ = {n2_: (ap_.get("file") or {}).get(n2_) for n2_ in NAMES}
                with WLOCK:
                    cand_ = [dict(WRITES0)] + [v2_ for w2_, v2_ in WRITES][-4:]
                off_ = {n2_: g2_ for n2_, g2_ in got_.items() if g2_ is None or
                        not any(abs(float(g2_) - float(c2_.get(n2_, g2_))) < 1e-6 for c2_ in cand_)}
                if off_:
                    log("MAJOR PROBLEM: the trainer applied shares that were not written (from update {}): {} applied, the last writes {}".format(
                        ap_.get("from_update"), off_, {n2_: [c2_.get(n2_) for c2_ in cand_] for n2_ in off_}))
                else:
                    log("live applied from update {}: {}".format(ap_.get("from_update"), got_))
            for m_ in jl(MET)[seen_m[0]:]:
                seen_m[0] += 1
                one_update(m_, base)
            if a.once:
                return
            time.sleep(a.poll)

    def one_update(m_, base):
        u_ = m_.get("update")
        F = []                                                # this update's flags (each its own line)
        # ---- the ledger, the firing cost, the sums (kept from 2.0e's ramp)
        pt_ = m_.get("pay_terms") or {}
        pm_, ss_ = pt_.get("per_player_min") or {}, pt_.get("size_share") or {}
        if pm_:
            log("update {}: ledger a player-minute: damage dealt {} taken {} | frags {} deaths {} | win part {} (size share {}) | items MH {} RA {} YA {} "
                "points {} decay {} | total {}".format(
                    u_, pm_.get("dmg_dealt"), pm_.get("dmg_taken"), pm_.get("frag"), pm_.get("death"), pm_.get("win_part"), ss_.get("win_part"),
                    pm_.get("item_MH"), pm_.get("item_RA"), pm_.get("item_YA"), pm_.get("item_points"), pm_.get("item_decay"),
                    pt_.get("total_per_player_min")))
            if (ss_.get("win_part") or 0) > 0.6:
                F.append("FLAG update {}: the win part is {} of the pay's size (over 0.6): the judge's noise".format(u_, ss_.get("win_part")))
        dg_ = m_.get("dodge_gate") or {}
        if dg_:
            tk_ = max(-30.0, math.log(dg_["cols"])) if (dg_.get("cols") or 0) > 0 else -30.0
            if abs(float(dg_.get("token", 0.0)) - tk_) > 1e-3:
                F.append("MAJOR PROBLEM update {}: the dodge token's gate {} is not log(DODGE_G {}) = {:.3f}".format(u_, dg_.get("token"), dg_.get("cols"), tk_))
        fm_ = m_.get("frags_per_match_min")
        if fm_ is not None and fm_ < FRAGS_MIN:
            F.append("FLAG update {}: frags a match-minute {} under {} (passivity)".format(u_, fm_, FRAGS_MIN))
        sc_ = m_.get("shot_cost_per_player_min")
        fc_ = {k2_: v_ for k2_, v_ in pm_.items() if any(w_ in k2_ for w_ in ("shot", "fire", "switch", "blind")) and v_}
        if (sc_ or 0) > 0 or any(v_ < 0 for v_ in fc_.values()):
            F.append("MAJOR PROBLEM FLAG update {}: A FIRING COST ABOVE ZERO: shot cost {} {}".format(u_, sc_, fc_))
        wp_ = m_.get("weapon") or {}
        big_ = {k2_: wp_.get(k2_) for k2_ in ("hands", "head") if (wp_.get(k2_) or 0) > SIZE_FLAG}
        if big_:
            F.append("FLAG update {}: a part of his weapon-key scores over {}: {}".format(u_, SIZE_FLAG, big_))
        h2_ = m_.get("head2") or {}
        big2_ = {k2_: h2_.get(k2_) for k2_ in ("hands", "raw") if (h2_.get(k2_) or 0) > SIZE_FLAG}
        if big2_:
            F.append("FLAG update {}: a part of his target scores over {}: {}".format(u_, SIZE_FLAG, big2_))
        # ---- the keep choice: its shares, the guard, its layers' sizes, its lesson
        k_ = m_.get("keep") or {}
        z_ = k_.get("zone") or {}
        kq_ = k_.get("quiet") or {}
        kt_ = k_.get("teach") or {}
        qc_ = num(z_.get("quiet_changed"))
        if not k_:
            F.append("MAJOR PROBLEM update {}: no keep record in the metrics (the network has no keep choice?)".format(u_))
        elif not z_:
            F.append("FLAG update {}: no keep.zone record (KEEP_ZONE off, or no reading counted this update)".format(u_))
        kw_ = k_.get("w") or {}
        zone_sz_ = {"s": num(kw_.get("s")), "hands": num(kw_.get("hands")), "own": max([abs(x_) for x_ in (kw_.get("own") or [])] or [0.0]),
                    "bias": abs(num(kw_.get("bias")) or 0.0)}
        quiet_sz_ = {"w": max([abs(x_) for x_ in (kq_.get("w") or [])] or [0.0]), "bias": abs(num(kq_.get("bias")) or 0.0)}
        bigk_ = {"zone " + n2_: v2_ for n2_, v2_ in zone_sz_.items() if (v2_ or 0) > SIZE_FLAG}
        bigk_.update({"quiet " + n2_: v2_ for n2_, v2_ in quiet_sz_.items() if (v2_ or 0) > SIZE_FLAG})
        if bigk_:
            F.append("FLAG update {}: a weight of the keep choice over {}: {}".format(u_, SIZE_FLAG, bigk_))
        for zn_ in ("zone", "quiet"):
            t_ = kt_.get(zn_) or {}
            p_, tg_ = num(t_.get("p")), num(t_.get("target"))
            if (t_.get("n") or 0) > 0 and p_ is not None and tg_ is not None and abs(p_ - tg_) > TEACH_GAP:
                F.append("FLAG update {}: the keep lesson's {} p(re-decide) {} is {:.3f} from its target {} (over {})".format(
                    u_, zn_, p_, abs(p_ - tg_), tg_, TEACH_GAP))
        # ---- the stay value
        sy_ = m_.get("stay") or {}
        ho_ = sy_.get("held_out") or {}
        lab_ = sy_.get("labels")
        if not sy_:
            F.append("FLAG update {}: no stay record in the metrics (--stay / --branch-keep off?)".format(u_))
        elif (lab_ or 0) < LABELS_MIN:
            F.append("FLAG update {}: the stay value's labels {} this update (under {})".format(u_, lab_, LABELS_MIN))
        sg_ = num(ho_.get("sign"))
        if sg_ is not None and (ho_.get("n") or 0) >= LABELS_MIN and sg_ <= SIGN_MIN:
            F.append("FLAG update {}: the stay value's held-out sign right {} of {} (at or under {}: no skill)".format(u_, sg_, ho_.get("n"), SIGN_MIN))
        # ---- the lock's measures and the guard, against the run's first five updates
        it_ = m_.get("intent") or {}
        now_ = {"quiet": qc_, "trips": num(it_.get("trips_per_player_min")), "reached": num(it_.get("reached"))}
        b_ = {}
        for n2_, v2_ in now_.items():
            if v2_ is None:
                continue
            if len(base[n2_]) < BASE_N:
                base[n2_].append(v2_)
                continue
            b_[n2_] = sum(base[n2_]) / len(base[n2_])
        if "quiet" in b_ and b_["quiet"] > 0 and now_["quiet"] > QUIET_UP * b_["quiet"]:
            F.append("FLAG update {}: quiet re-decisions a reading {} over {}x the start's {:.4f} (the drift of 1.7a)".format(u_, now_["quiet"], QUIET_UP, b_["quiet"]))
        for n2_, w2_ in (("trips", "trips a player-minute"), ("reached", "targets reached")):
            if n2_ in b_ and b_[n2_] > 0 and abs(now_[n2_] / b_[n2_] - 1.0) > MOVE_MAX:
                F.append("FLAG update {}: {} {} moved {:+.0%} from the start's {:.3f} (over {:.0%})".format(
                    u_, w2_, now_[n2_], now_[n2_] / b_[n2_] - 1.0, b_[n2_], MOVE_MAX))
        ms_ = m_.get("map_sense")                             # (the map sense learns silently: its skill reported, flagged only when missing)
        if not ms_:
            F.append("FLAG update {}: no map_sense record in the metrics (--map-sense off?)".format(u_))
        for f_ in F:
            log(f_)
        if ms_:
            log("update {}: map sense (silent): samples {} weight {} pull {} | R2 {} (shared part alone {}) exchange {} | corrections mean {} max {}{}".format(
                u_, ms_.get("frames"), ms_.get("w"), ms_.get("pull"), ms_.get("r2"), ms_.get("r2_seeds"), ms_.get("r2_exchange"), ms_.get("corr_abs"),
                ms_.get("corr_max"), " | maps without a table {}".format(ms_["maps_without_table"]) if ms_.get("maps_without_table") else ""))
        # ---- the summary line
        br_ = m_.get("branch") or {}
        bk_ = br_.get("keep") or {}
        log("update {}: shares KEEP_G {} KEEPQ_G {} | quiet re-decisions a reading {} (start {}) {} a player-minute | zone changed {} of {} | "
            "trips {} (start {}) reached {} (start {}) | stay labels {} seen {} held-out sign {} cor {} | keep lesson w {} zone p {} / {} quiet p {} / {} | "
            "sizes zone {} quiet {} | forks: moments {} keep moments {} | frags a match-minute {} | {} flag(s)".format(
                u_, k_.get("g"), kq_.get("g"), qc_, None if "quiet" not in b_ else round(b_["quiet"], 4), z_.get("quiet_changes_a_player_min"),
                z_.get("zone_changed"), z_.get("zone_readings"), now_["trips"], None if "trips" not in b_ else round(b_["trips"], 2), now_["reached"],
                None if "reached" not in b_ else round(b_["reached"], 3), lab_, sy_.get("seen"), sg_, ho_.get("cor"), kt_.get("w"),
                (kt_.get("zone") or {}).get("p"), (kt_.get("zone") or {}).get("target"), (kt_.get("quiet") or {}).get("p"),
                (kt_.get("quiet") or {}).get("target"), {n2_: v2_ for n2_, v2_ in zone_sz_.items()}, quiet_sz_, br_.get("moments"), bk_.get("moments"),
                fm_, len(F)))

    def stall():
        last_ = [None, time.time()]                           # (the size of metrics.jsonl, when it last grew)
        said_ = [False]
        while True:
            try:
                sz_ = os.path.getsize(MET)
            except OSError:
                sz_ = -1
            if sz_ != last_[0]:
                if said_[0]:
                    log("the stall is over: metrics.jsonl grew again")
                last_[0], last_[1], said_[0] = sz_, time.time(), False
            elif not said_[0] and time.time() - last_[1] > STALL_S:
                said_[0] = True
                log("FLAG A STALL: no new line in metrics.jsonl for {:.0f} minutes{}".format(
                    (time.time() - last_[1]) / 60.0, "" if sz_ >= 0 else " (there is no metrics.jsonl yet)"))
            time.sleep(30)

    def guard(fn, name):                                      # (1.9a: a crashed flag thread went silent all night)
        while True:
            try:
                fn()
            except Exception:
                log("MAJOR PROBLEM: THE RAMP'S {} THREAD CRASHED (it starts again; lines may repeat): ".format(name) +
                    traceback.format_exc().replace(chr(10), " | ")[-1500:])
                time.sleep(60)

    def mtime():
        try:
            return os.path.getmtime(POL)
        except FileNotFoundError:
            return 0.0

    def keep(name):
        shutil.copy2(POL, os.path.join(KEEP, name))
        shutil.copy2(OPT, os.path.join(KEEP, name.replace("policy_", "opt_", 1)))

    def write(v_):
        d = json.load(open(LIVE, encoding="utf-8"))
        for n_ in NAMES:
            d[n_] = round(float(v_[n_]), 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        with WLOCK:
            WRITES.append((time.time(), {n_: d[n_] for n_ in NAMES}))

    def save_state(st):
        with open(STATE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(st))
        os.replace(STATE + ".tmp", STATE)

    cur = json.load(open(LIVE, encoding="utf-8"))
    WRITES0.update({n_: cur.get(n_) for n_ in NAMES})
    if not a.resume:
        for n_ in NAMES:
            assert abs(float(cur.get(n_, -99)) - 0.0) < 1e-9, "{} is {} in live.json, not 0".format(n_, cur.get(n_))
    st = {"B": None, "C": None, "D_said": False, "marks": []}  # B, C: {"named": u, "from": u} the effective start
    if a.resume and os.path.exists(STATE):
        st.update(json.load(open(STATE, encoding="utf-8")))
    if not os.path.exists(STEPS):
        with open(STEPS, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(STEPS0, indent=1))
    if a.once:
        log("ramp_21b --once on {}: the flags over its metrics, nothing written to live.json".format(D))
        flags()
        return
    threading.Thread(target=guard, args=(flags, "FLAG"), daemon=True).start()
    threading.Thread(target=guard, args=(stall, "STALL"), daemon=True).start()
    log("ramp_21b on for {}: the shares KEEP_G (step B) and KEEPQ_G (step C) open only on the owner's steps.json ({}); FREE: nothing opens on a "
        "schedule, nothing holds or steps back; a check under 40% is a MAJOR PROBLEM{}".format(a.run, STEPS, " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = int(L0[-1]["update"]) if (a.resume and L0) else 0
    seen, steps, bad_said = mtime(), dict(STEPS0), [None]
    last_v = {n_: float(cur.get(n_) or 0.0) for n_ in NAMES}
    while True:
        time.sleep(a.poll)
        try:                                                  # (the owner's file: read every poll; a bad file keeps the last good one)
            s_, why_ = check_steps(json.load(open(STEPS, encoding="utf-8")))
        except (OSError, ValueError) as e_:
            s_, why_ = None, str(e_)
        if s_ is None:
            if why_ != bad_said[0]:
                bad_said[0] = why_
                log("FLAG steps.json is not readable ({}): the last good one kept: {}".format(why_, steps))
        else:
            bad_said[0] = None
            if s_ != steps:
                log("steps.json (the owner's): {} (was {})".format(s_, steps))
                steps = s_
        L = jl(MET)
        n = int(L[-1]["update"]) if L else 0
        for k_ in ("B", "C"):                                 # the effective start: the update named, or the first update seen after it
            nm_ = steps[k_]
            if nm_ is None:
                if st[k_] is not None:
                    log("FLAG steps.json: the owner took step {} back out (it was named {}): its share follows his file".format(k_, st[k_]["named"]))
                    st[k_] = None
                    save_state(st)
                continue
            if st[k_] is None or st[k_]["named"] != nm_:
                fr_ = max(nm_, n)
                st[k_] = {"named": nm_, "from": fr_}
                save_state(st)
                log("step {} named at update {} by the owner: {} opens from update {}{} over {} updates".format(
                    k_, nm_, "KEEP_G" if k_ == "B" else "KEEPQ_G", fr_, " (the update named was past: no jump)" if fr_ != nm_ else "",
                    steps[k_ + "_over"]))
                if k_ == "C" and last_v["KEEP_G"] < 1.0:
                    log("FLAG step C opens with KEEP_G {} under 1: the quiet layer decides only KEEP_G x KEEPQ_G of the quiet readings".format(last_v["KEEP_G"]))
        if n > done_n:
            v_ = {"KEEP_G": share_at(n, None if st["B"] is None else st["B"]["from"], steps["B_over"]),
                  "KEEPQ_G": share_at(n, None if st["C"] is None else st["C"]["from"], steps["C_over"])}
            write(v_)
            log("after update {}: KEEP_G {} KEEPQ_G {} written (steps {})".format(n, round(v_["KEEP_G"], 6), round(v_["KEEPQ_G"], 6),
                                                                                {k2_: steps[k2_] for k2_ in ("B", "C", "D")}))
            for n_ in NAMES:
                if v_[n_] < last_v[n_] - 1e-9:
                    log("FLAG {} written {} under its last {}: the owner's steps.json moved it back".format(n_, v_[n_], last_v[n_]))
            last_v = v_
            if v_["KEEP_G"] >= 1.0 and v_["KEEPQ_G"] >= 1.0 and not st["D_said"]:
                st["D_said"] = True
                save_state(st)
                log("D: the lock decides nowhere (KEEP_G 1, KEEPQ_G 1) after update {}{}".format(
                    n, "" if steps["D"] is None else " (the owner's D: update {})".format(steps["D"])))
            if steps["D"] is not None and n >= steps["D"] and not (v_["KEEP_G"] >= 1.0 and v_["KEEPQ_G"] >= 1.0):
                log("FLAG update {}: the owner's D (update {}) is past but the shares are KEEP_G {} KEEPQ_G {}: the lock still decides".format(
                    n, steps["D"], v_["KEEP_G"], v_["KEEPQ_G"]))
            done_n = n
        m_ = mtime()                                          # the marks: update 10, each step's start and end
        if m_ > seen and time.time() - m_ >= a.settle:
            seen = m_
            want_ = [("u{}".format(MARK_FIRST), n >= MARK_FIRST)]
            for k_, nm2_ in (("B", "KEEP_G"), ("C", "KEEPQ_G")):
                if st[k_] is not None:
                    want_.append(("{}_start".format(k_), n >= st[k_]["from"]))
                    want_.append(("{}_end".format(k_), last_v[nm2_] >= 1.0))
            for tag_, due_ in want_:
                if due_ and tag_ not in st["marks"]:
                    st["marks"].append(tag_)
                    save_state(st)
                    keep("policy_u{}_21b.pt".format(n))
                    log("kept keep/policy_u{}_21b.pt with its optimizer (the mark {})".format(n, tag_))


if __name__ == "__main__":
    main()
