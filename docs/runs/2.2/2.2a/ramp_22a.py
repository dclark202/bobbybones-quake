"""2.2a's dials (docs/runs/2.2/DESIGN.md "2.2a in detail"; made from 2.1f's ramp), on the clock of updates done = the LINES of metrics.jsonl (never the
trainer's own "update": a --resume restarts it at 1).
  OUT_TRIAL  0 -> 0.03 in a straight line over updates 0 to 10, then held (the brief, part H)
  OUT_G      the outlook's term. THE OWNER'S MARK WINS ALWAYS: while <run>/watch/out_mark.json exists ({"mark": 0 .. 20, "from": u, "to": u,
             optional "src": 0 or 1}), OUT_G = mark x (clock - from) / (to - from) between from and to (and OUT_SRC = src if given), at any update,
             a mark of 0 included (shut). Without it: THE AUTOMATIC MARK (owner, 2026-11-16 night), decided ONCE when update `at` is logged, every
             number from <run>/watch/auto_mark.json (a copy of docs/runs/2.2/2.2a/auto_mark.json; defaults AUTO):
               1. the gate: for each candidate (desc and the built 17-output outlook), kind seg, its prequential gain over its own goal-blind
                  yardstick at DECISION readings and at STAY readings over the last `window` updates up to `at`: it passes if both means are
                  above 0 AND the decision gain is above 0 in at least `min_pos` of those updates (a missing reading counts as not above 0).
                  None passes: the dial stays 0, a MAJOR line "THE OUTLOOK DID NOT PASS ITS GATE: the dial stays shut", the silent parts go on
               2. the source (OUT_SRC): of those that pass, desc if its mean decision gain is at least the built one's x desc_pref (0.9), else the
                  built one; OUT_PICK stays seg (0)
               3. the mark: the chosen outlook's first-order replay (the share of his choices the term would change at 0.5, 1, 2, 4, 8; mean over
                  the same window): the largest strength whose share is at most max_share (0.10); if even 0.5's is above it, 0.5 x max_share / that
                  share, floored at min_mark (0.1)
               4. OUT_SRC set at once (OUT_G still 0), then OUT_G 0 -> the mark in a straight line over open_updates (40) updates, then held
               5. the decision to <run>/watch/out_mark_auto.json and one line to watch.log; a ramp restart (--resume) reads it and never decides twice
  OUT_PICK, PULL_G, HELD_G: never written. The clock never holds or steps back by itself (CLAUDE.md rule 6); every check logged, one under 40% a
  MAJOR PROBLEM. Kept with their optimizers: keep/policy_u<N>.pt + opt_u<N>.pt at the first save at or past updates 10, 60 (the save the automatic
  mark is decided on), 100, 140, and at the trainer's end (+ keep/policy_end_22a.pt, opt_end_22a.pt, never written over). Logged every update:
  2.1f's lines (the held draw, the slow plan, the pull and its proof, the kinds of his changes of mind, the outlook by kind, what plays), and
  2.2a's: the desc outlooks by sibling, the facts, the tracker, the map sense, the second value, the attack readouts, the sizes (rule 11: a FLAG
  over 40). NO flag or threshold on any count of trips, changes or interrupts.
    python docs/runs/2.2/2.2a/ramp_22a.py <run> [--poll S] [--settle S] [--dir D] [--resume] [--once]
tools/run/live_accept.py reads values(clock) and DIALS at the mark RAMP22A_MARK="mark,from,to" (default 20,60,100) and the source RAMP22A_SRC
(default 1), so every file the ramp could write for that mark and source is checked."""
import argparse
import json
import os
import shutil
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
SCHEDULE = {"OUT_TRIAL": [(0, 0.0), (10, 0.03)]}
UNSCHEDULED = ("OUT_PICK", "PULL_G", "HELD_G")               # (never written by the ramp)
MARKS = (10, 60, 100, 140)
MARK_MAX = 20.0                                              # (live OUT_G's range in the trainer: 0 .. 20)
MARK_FROM, MARK_TO = 60, 100                                 # (the owner's mark file's defaults)
AUTO = dict(at=60, window=10, min_pos=8, desc_pref=0.9, max_share=0.10, min_mark=0.1, open_updates=40, kind="seg")
AUTO_RANGE = dict(at=(1, 10000), window=(1, 1000), min_pos=(0, 1000), desc_pref=(0.0, 10.0), max_share=(0.0, 1.0), min_mark=(0.0, MARK_MAX),
                  open_updates=(1, 10000))
REPLAY_G = ("0.5", "1.0", "2.0", "4.0", "8.0")
SIZE_FLAG = 40.0
MAJOR = 0.40
FRAGS_MIN = 1.5
PROOF_MAX = 0.01
PROOF_FLOOR_FLAG = 0.003
RUN_TAG = "22a"


def value(name, clock):
    k_ = SCHEDULE[name]
    if clock <= k_[0][0]:
        return float(k_[0][1])
    if clock >= k_[-1][0]:
        return float(k_[-1][1])
    for (u0_, y0_), (u1_, y1_) in zip(k_[:-1], k_[1:]):
        if u0_ <= clock <= u1_:
            return y0_ + (y1_ - y0_) * (clock - u0_) / float(u1_ - u0_)
    return float(k_[-1][1])


def out_g_at(clock, mk):
    """OUT_G at this clock for the mark (mark, from, to)"""
    m_, f_, t_ = mk[0], mk[1], mk[2]
    if clock <= f_:
        return 0.0
    if clock >= t_:
        return float(m_)
    return float(m_) * (clock - f_) / float(t_ - f_)


def mark_check(d):
    """the owner's mark file -> ((mark, from, to, src or None), None) or (None, why)"""
    try:
        m_ = float(d["mark"])
        f_ = int(d.get("from", MARK_FROM))
        t_ = int(d.get("to", MARK_TO))
        s_ = d.get("src")
        s_ = None if s_ is None else int(s_)
    except (KeyError, TypeError, ValueError) as e_:
        return None, "not {{\"mark\": x, \"from\": u, \"to\": u, \"src\": 0 or 1}}: {}".format(e_)
    if not (0.0 <= m_ <= MARK_MAX):
        return None, "mark {} outside 0 .. {}".format(m_, MARK_MAX)
    if t_ <= f_ or f_ < 0:
        return None, "to {} not after from {}".format(t_, f_)
    if s_ is not None and s_ not in (0, 1):
        return None, "src {} not 0 or 1".format(s_)
    return (m_, f_, t_, s_), None


def auto_check(d):
    """auto_mark.json -> (the settings, None) or (None, why): every name of AUTO, each in its range"""
    try:
        cfg = dict(AUTO)
        for k_, v_ in (d or {}).items():
            if k_.startswith("_"):
                continue
            if k_ not in AUTO:
                return None, "unknown name {}".format(k_)
            cfg[k_] = v_ if k_ == "kind" else (int(v_) if isinstance(AUTO[k_], int) else float(v_))
        for k_, (lo_, hi_) in AUTO_RANGE.items():
            if not (lo_ <= cfg[k_] <= hi_):
                return None, "{} {} outside {} .. {}".format(k_, cfg[k_], lo_, hi_)
        if cfg["min_pos"] > cfg["window"] or cfg["window"] > cfg["at"] or cfg["kind"] != "seg":
            return None, "min_pos above window, window above at, or a kind other than seg"
        return cfg, None
    except (TypeError, ValueError) as e_:
        return None, repr(e_)


def cand_numbers(m_, which, kind="seg"):
    """(the automatic mark) one update's numbers of a candidate: (decision gain, stay gain, replay {strength: share}) or Nones. which: "built"
    (rec outlook.kind.<kind>) or "desc" (rec out22.desc.desc.kind.<kind>)"""
    if which == "built":
        kd_ = ((m_.get("outlook") or {}).get("kind") or {}).get(kind) or {}
    else:
        kd_ = ((((m_.get("out22") or {}).get("desc") or {}).get("desc") or {}).get("kind") or {}).get(kind) or {}
    return (kd_.get("decision") or {}).get("gain"), (kd_.get("stay") or {}).get("gain"), kd_.get("replay") or {}


def auto_decide(lines, cfg):
    """THE AUTOMATIC MARK (a pure function of the metrics' lines and the settings): lines = the metrics.jsonl records in order (the run's
    update u is lines[u - 1]); the window is updates at - window + 1 .. at. -> the decision dict (passed, src, mark, the candidates' numbers)"""
    at_, w_ = int(cfg["at"]), int(cfg["window"])
    win_ = lines[max(0, at_ - w_):at_]
    out = dict(at=at_, window=[at_ - w_ + 1, at_], settings=dict(cfg), candidates={})
    for nm_ in ("desc", "built"):
        dec_, sty_, rp_ = [], [], []
        for m_ in win_:
            d_, s_, r_ = cand_numbers(m_, nm_, cfg["kind"])
            dec_.append(d_)
            sty_.append(s_)
            rp_.append(r_)
        dk_ = [x_ for x_ in dec_ if isinstance(x_, (int, float))]
        sk_ = [x_ for x_ in sty_ if isinstance(x_, (int, float))]
        md_ = sum(dk_) / len(dk_) if dk_ else None
        ms_ = sum(sk_) / len(sk_) if sk_ else None
        pos_ = sum(1 for x_ in dec_ if isinstance(x_, (int, float)) and x_ > 0)
        sh_ = {}
        for g_ in REPLAY_G:
            v_ = [r_.get(g_) for r_ in rp_ if isinstance(r_.get(g_), (int, float))]
            sh_[g_] = sum(v_) / len(v_) if v_ else None
        ok_ = len(win_) == w_ and md_ is not None and ms_ is not None and md_ > 0 and ms_ > 0 and pos_ >= int(cfg["min_pos"])
        out["candidates"][nm_] = dict(decision_gain_mean=md_, stay_gain_mean=ms_, decision_positive=pos_, updates=len(win_), replay=sh_, passed=ok_,
                                      decision_gains=dec_, stay_gains=sty_)
    cd_, cb_ = out["candidates"]["desc"], out["candidates"]["built"]
    if not cd_["passed"] and not cb_["passed"]:
        out.update(passed=False, src=None, mark=0.0)
        return out
    if cd_["passed"] and (not cb_["passed"] or cd_["decision_gain_mean"] >= cb_["decision_gain_mean"] * float(cfg["desc_pref"])):
        src_, ch_ = 1, cd_
    else:
        src_, ch_ = 0, cb_
    sh_ = ch_["replay"]
    ok_g = [float(g_) for g_ in REPLAY_G if sh_.get(g_) is not None and sh_[g_] <= float(cfg["max_share"])]
    if ok_g:
        mk_ = max(ok_g)
        how_ = "the largest strength whose share is at most {}".format(cfg["max_share"])
    elif sh_.get("0.5"):
        mk_ = max(float(cfg["min_mark"]), 0.5 * float(cfg["max_share"]) / float(sh_["0.5"]))
        how_ = "0.5 x {} / the share at 0.5 ({:.4f}), floored at {}".format(cfg["max_share"], sh_["0.5"], cfg["min_mark"])
    else:
        mk_ = float(cfg["min_mark"])
        how_ = "no replay readout: the floor {}".format(cfg["min_mark"])
    mk_ = min(mk_, MARK_MAX)
    out.update(passed=True, src=src_, src_name="desc" if src_ == 1 else "built", mark=round(mk_, 6), mark_how=how_,
               open=[at_, at_ + int(cfg["open_updates"])])
    return out


TEST_MARK = mark_check(dict(zip(("mark", "from", "to"), (os.environ.get("RAMP22A_MARK") or "{},{},{}".format(MARK_MAX, MARK_FROM, MARK_TO)).split(","))))[0]
assert TEST_MARK is not None, "RAMP22A_MARK: mark,from,to with the mark in 0 .. {} and to after from".format(MARK_MAX)
TEST_SRC = int(os.environ.get("RAMP22A_SRC") or 1)


def values(clock):
    """{name: its value at this clock} at the test mark and source (tools/run/live_accept.py reads it: every file the ramp could write)"""
    return {"OUT_TRIAL": value("OUT_TRIAL", float(clock)), "OUT_G": out_g_at(float(clock), TEST_MARK), "OUT_SRC": float(TEST_SRC)}


DIALS = (("OUT_TRIAL", 0, 10, 0.0, 0.03, 0.0), ("OUT_G", TEST_MARK[1], TEST_MARK[2], 0.0, TEST_MARK[0], 0.0))
END = max(d[2] for d in DIALS)


def dial_at(clock, lo, hi, v0, v1, pre):
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


def out22_lines(m_, u_, log):
    """(2.2a) the update's lines of the silent parts: the desc outlooks against the built one (seg and segw at decision and stay readings), the
    facts, the tracker (every output's skill, all and in / out of control; the stack's range), the map sense, the second value, the attack
    readouts, the sizes (rule 11)"""
    o2_ = m_.get("out22")
    if not o2_:
        if u_:
            log("MAJOR PROBLEM update {}: no out22 record in the metrics (the run has no --out22 1?)".format(u_))
        return
    if o2_.get("off"):
        log("MAJOR PROBLEM update {}: 2.2a'S SILENT LESSONS OR READOUTS FAILED in the trainer (off for the rest of the run): see its log".format(u_))
    q_ = lambda d_, *ks: (lambda x_: x_)(_dig(d_, ks))        # noqa: E731
    ol_ = m_.get("outlook") or {}
    for kn_ in ("seg", "segw", "ret", "win8", "winit8"):
        parts_ = ["built {} / {}".format(q_(ol_, "kind", kn_, "decision", "gain"), q_(ol_, "kind", kn_, "stay", "gain"))]
        for s_ in ("desc", "desc_nomap", "desc_notrk"):
            parts_.append("{} {} / {}".format(s_, q_(o2_, "desc", s_, "kind", kn_, "decision", "gain"), q_(o2_, "desc", s_, "kind", kn_, "stay", "gain")))
        log("update {}: outlooks {} gain over the goal-blind (decision / stay readings; R2 goal {} desc {}): {}".format(
            u_, kn_, q_(ol_, "kind", kn_, "all", "r2_goal"), q_(o2_, "desc", "desc", "kind", kn_, "all", "r2_goal"), " | ".join(parts_)))
    fb_, fd_ = ol_.get("facts") or {}, q_(o2_, "desc", "desc", "facts") or {}
    log("update {}: facts (goal / goal-blind; Brier skill or R2): ".format(u_) + " | ".join(
        "{} built {} / {} desc {} / {}".format(f_, *[(q_(d_, f_, "all", "skill_goal") if q_(d_, f_, "all", "skill_goal") is not None
                                                      else q_(d_, f_, "all", "r2_goal")) if j_ == 0 else
                                                     (q_(d_, f_, "all", "skill_blind") if q_(d_, f_, "all", "skill_blind") is not None
                                                      else q_(d_, f_, "all", "r2_blind")) for d_ in (fb_, fd_) for j_ in (0, 1)])
        for f_ in ("he_dies", "i_die", "took", "my_h", "my_a", "en_h", "en_a")))
    tk_ = o2_.get("tracker") or {}
    for sp_ in ("all", "in", "out"):
        t2_ = tk_.get(sp_) or {}
        log("update {}: tracker ({}): ".format(u_, {"all": "all moments", "in": "in control by the truth", "out": "out of control by the truth"}[sp_]) +
            " | ".join("{} skill {} auc {} ({})".format(o_, q_(t2_, o_, "skill"), q_(t2_, o_, "auc"), q_(t2_, o_, "n"))
                       for o_ in ("ctl_two", "ctl_one", "ctl_mh", "ctl_ra", "fo_win", "fo_lose", "idie5", "idie10", "hedie5", "hedie10", "con2", "con5"))
            + " | stack health: middle's error {} rule's {} inside {} width by seen {} | armor: middle's error {} rule's {} inside {} width by seen {}".format(
                q_(t2_, "stack_health", "mid_err"), q_(t2_, "stack_health", "rule_err"), q_(t2_, "stack_health", "inside"),
                q_(t2_, "stack_health", "width_by_seen"), q_(t2_, "stack_armor", "mid_err"), q_(t2_, "stack_armor", "rule_err"),
                q_(t2_, "stack_armor", "inside"), q_(t2_, "stack_armor", "width_by_seen")))
    log("update {}: tracker rows near {} in control {} | pending the split {} (resolved {}, dropped {}) | loss {} last layer {}".format(
        u_, tk_.get("rows_near"), tk_.get("rows_ctl"), tk_.get("pending"), tk_.get("split_resolved"), tk_.get("split_dropped"), tk_.get("loss"),
        tk_.get("l3")))
    ms_ = m_.get("map_sense") or {}
    log("update {}: map sense: {} samples, R2 dealt {} taken {} exchange {} (the shared part alone {}) corrections {} / {}".format(
        u_, ms_.get("frames"), q_(ms_, "r2", "dealt"), q_(ms_, "r2", "taken"), ms_.get("r2_exchange"), ms_.get("r2_seeds"), ms_.get("corr_abs"),
        ms_.get("corr_max")))
    vw_ = o2_.get("vw") or {}
    log("update {}: the second value (the win chance with the items): loss {} -> {} | its return {} +- {} | last layer {}".format(
        u_, vw_.get("loss_before"), vw_.get("loss_after"), vw_.get("ret_mean"), vw_.get("ret_sd"), vw_.get("l2")))
    at_ = o2_.get("attack") or {}
    log("update {}: attack by the stack edge {}: readings {} | on the enemy target {} | the tracker: he dies first {} I die first {} | the "
        "played kind's centred outlook of the enemy: built {} desc {}".format(
            u_, at_.get("bins"), at_.get("readings"), at_.get("share_on_enemy"), at_.get("fight_he_dies_first"), at_.get("fight_i_die_first"),
            at_.get("outlook_built"), at_.get("outlook_desc")))
    sz_ = o2_.get("sizes") or {}
    log("update {}: sizes (rule 11): the built outlook's l3 {}, desc's {}, the tracker's {}, the second value's {} | the term plays from {} (next {})".format(
        u_, sz_.get("out_l3"), sz_.get("dsc_l3"), sz_.get("trk_l3"), sz_.get("vw_l2"), o2_.get("src"), o2_.get("src_next")))
    big_ = {k_: v_ for k_, v_ in (("out_l3", sz_.get("out_l3")), ("trk_l3", sz_.get("trk_l3"))) if (v_ or 0) > SIZE_FLAG}
    big_.update({"dsc_l3 " + k_: v_ for k_, v_ in (sz_.get("dsc_l3") or {}).items() if (v_ or 0) > SIZE_FLAG})
    if big_:
        log("FLAG update {}: a learnt part of the outlooks over {} (rule 11): {}".format(u_, SIZE_FLAG, big_))


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
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    WD, LIVE, POL, OPT, KEEP, MET = (os.path.join(D, "watch"), os.path.join(D, "live.json"), os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt"),
                                     os.path.join(D, "keep"), os.path.join(D, "metrics.jsonl"))
    LOGF = os.path.join(os.path.dirname(D), a.run + ".log")
    os.makedirs(WD, exist_ok=True)
    os.makedirs(KEEP, exist_ok=True)
    WRITES, WRITES0, WLOCK = [], {}, threading.Lock()

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
    WRITES0.update({n_: cur.get(n_) for n_ in ("OUT_G", "OUT_TRIAL", "OUT_SRC") + UNSCHEDULED})
    if not a.resume and not a.once:
        assert abs(float(cur.get("OUT_G", -99))) < 1e-9, "OUT_G is {} in live.json, not 0 (start_live.py)".format(cur.get("OUT_G"))
        assert abs(float(cur.get("OUT_TRIAL", -99))) < 1e-9, "OUT_TRIAL is {} in live.json, not 0 (start_live.py)".format(cur.get("OUT_TRIAL"))
        for n_ in UNSCHEDULED:
            assert n_ in cur, "{} is not in live.json (the ramp never writes it: start_live.py puts it there)".format(n_)

    def out_lines(m_, u_):                                   # (2.1f) the built outlook's record of this update
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
        kd2_ = _dig(m_, ("out22", "desc", "desc", "kind", ks_[pk_] if (isinstance(pk_, int) and 0 <= pk_ < len(ks_)) else "seg")) or {}
        log("update {}: outlook plays: strength {} (next {}) kind {} (next {}) source {} (next {}) | the league's {} kind {} (plays {}) | term size {} "
            "largest {} | changed his pick at {} of his readings ({}) | replay (share of readings whose pick changes) at 0.5..8: built {} desc {} | "
            "z {} | readings {} decisions {} | trial share {} (next {}): trips {} readings {} in a target lesson {} | segments (readings) {} | loss {} "
            "last layer {} | lesson {} s".format(
                u_, ol_.get("g"), ol_.get("g_next"), pk_, ol_.get("pick_next"), _dig(m_, ("out22", "src")), _dig(m_, ("out22", "src_next")),
                ol_.get("g_opp"), ol_.get("pick_opp"), ol_.get("opp_has"), ol_.get("size"), ol_.get("max"), ol_.get("changed"), ol_.get("changed_n"),
                kp_.get("replay"), kd2_.get("replay"), kp_.get("z"), ol_.get("readings"), ol_.get("decisions"), ol_.get("trial"), ol_.get("trial_next"),
                ol_.get("trial_trips"), ol_.get("trial_readings"), ol_.get("trial_in_lesson"), ol_.get("seg_readings"), ol_.get("loss"), ol_.get("l3"),
                ol_.get("secs")))
        if (ol_.get("l3") or 0) > SIZE_FLAG:
            log("FLAG update {}: the outlook's last layer {} over {} (rule 11)".format(u_, ol_.get("l3"), SIZE_FLAG))
        if (ol_.get("max") or 0) > SIZE_FLAG:
            log("FLAG update {}: the outlook's term reached {} on his target scores, over {} (rule 11)".format(u_, ol_.get("max"), SIZE_FLAG))
        if ol_.get("trial_in_lesson") not in (None, 0):
            log("MAJOR PROBLEM update {}: {} frames of trial trips were left in a target lesson (must be 0)".format(u_, ol_.get("trial_in_lesson")))
        for n_, k2_, src_ in (("OUT_G", "g", ol_), ("OUT_PICK", "pick", ol_), ("OUT_TRIAL", "trial", ol_), ("OUT_SRC", "src", m_.get("out22") or {})):
            cand_ = written(n_)
            if src_.get(k2_) is None or not any(c2_ is not None and abs(float(src_[k2_]) - float(c2_)) < 1e-4 for c2_ in cand_):
                log("MAJOR PROBLEM update {}: {} played {} is none of {} (the start's, the last written, the live file's now)".format(
                    u_, n_, src_.get(k2_), cand_))

    def update_lines(m_, base, u_):
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
        out_lines(m_, u_)
        out22_lines(m_, u_, log)
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
                got_ = {n2_: (ap_.get("file") or {}).get(n2_) for n2_ in ("OUT_G", "OUT_TRIAL", "OUT_SRC")}
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

    def mtime():
        try:
            return os.path.getmtime(POL)
        except FileNotFoundError:
            return 0.0

    def keep(name):
        shutil.copy2(POL, os.path.join(KEEP, name))
        shutil.copy2(OPT, os.path.join(KEEP, name.replace("policy_", "opt_", 1)))

    MK_ = dict(cur=None, seen=None)                           # (the owner's mark in force, the file's last content seen)
    AP_ = os.path.join(WD, "out_mark_auto.json")
    AUTO_D = [json.load(open(AP_, encoding="utf-8")) if os.path.exists(AP_) else None]   # (a resume: never decided twice)
    acfg_, why_ = auto_check(json.load(open(os.path.join(WD, "auto_mark.json"), encoding="utf-8")) if os.path.exists(os.path.join(WD, "auto_mark.json")) else {})
    if acfg_ is None:
        log("MAJOR PROBLEM: watch/auto_mark.json refused ({}): the automatic mark is OFF (the dial stays as the owner's mark file, or 0)".format(why_))
    CFG = [acfg_]

    def read_mark():
        """the owner's mark file -> (mark, from, to, src) or None (absent, or refused: a FLAG once per content)"""
        p_ = os.path.join(WD, "out_mark.json")
        if not os.path.exists(p_):
            if MK_["cur"] is not None:
                log("the owner's mark file is gone: OUT_G follows the automatic mark (if any) from now on")
            MK_["cur"], MK_["seen"] = None, None
            return None
        try:
            raw_ = open(p_, encoding="utf-8").read()
            d_ = json.loads(raw_)
            mk_, wy_ = mark_check(d_ if isinstance(d_, dict) else {})
        except (OSError, ValueError) as e_:
            raw_, mk_, wy_ = None, None, "not JSON: {}".format(e_)
        if raw_ != MK_["seen"]:
            MK_["seen"] = raw_
            if mk_ is None:
                log("FLAG: the mark file watch/out_mark.json refused ({}): not used; the last mark in force: {}".format(wy_, MK_["cur"]))
            else:
                log("THE OWNER'S MARK (it wins over the automatic one): OUT_G 0 at update {} -> {} at update {}{}".format(
                    mk_[1], mk_[0], mk_[2], "; OUT_SRC {}".format(mk_[3]) if mk_[3] is not None else ""))
                MK_["cur"] = mk_
        return MK_["cur"]

    def decide(clock):
        """the automatic mark, once, when update `at` is logged (or the first poll past it)"""
        if AUTO_D[0] is not None or CFG[0] is None or clock < int(CFG[0]["at"]):
            return
        d_ = auto_decide(jl(MET), CFG[0])
        d_.update(decided_at_clock=int(clock), when=time.strftime("%Y-%m-%d %H:%M:%S"),
                  owner_mark_present=os.path.exists(os.path.join(WD, "out_mark.json")))
        with open(AP_ + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(d_, fh, indent=1)
        os.replace(AP_ + ".tmp", AP_)
        AUTO_D[0] = d_
        c_ = d_["candidates"]
        nums_ = " | ".join("{}: decision gain {} stay gain {} (positive in {} of {}) replay {} {}".format(
            k_, _r(v_["decision_gain_mean"]), _r(v_["stay_gain_mean"]), v_["decision_positive"], v_["updates"],
            {g_: _r(s_) for g_, s_ in v_["replay"].items()}, "PASSED" if v_["passed"] else "not passed") for k_, v_ in c_.items())
        if not d_["passed"]:
            log("MAJOR PROBLEM update {}: THE OUTLOOK DID NOT PASS ITS GATE: the dial stays shut (updates {} to {}): {}".format(
                d_["at"], d_["window"][0], d_["window"][1], nums_))
        else:
            log("THE AUTOMATIC MARK at update {} (updates {} to {}): {} plays (OUT_SRC {}) at the mark {} ({}); OUT_G 0 -> {} over updates {} to {}{}: {}".format(
                d_["at"], d_["window"][0], d_["window"][1], d_["src_name"], d_["src"], d_["mark"], d_["mark_how"], d_["mark"], d_["open"][0], d_["open"][1],
                " (THE OWNER'S MARK FILE IS PRESENT: it wins)" if d_["owner_mark_present"] else "", nums_))

    def write(clock):
        """the dials of this clock into live.json (re-read: every other name kept as the file has it)"""
        decide(clock)
        v_ = {"OUT_TRIAL": round(value("OUT_TRIAL", clock), 6)}
        mk_ = read_mark()
        if mk_ is not None:
            v_["OUT_G"] = round(out_g_at(clock, mk_), 6)
            if mk_[3] is not None:
                v_["OUT_SRC"] = int(mk_[3])
        elif AUTO_D[0] is not None and AUTO_D[0].get("passed"):
            v_["OUT_SRC"] = int(AUTO_D[0]["src"])
            v_["OUT_G"] = round(out_g_at(clock, (AUTO_D[0]["mark"], AUTO_D[0]["open"][0], AUTO_D[0]["open"][1])), 6)
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
    log("ramp_22a on for {}: OUT_TRIAL 0 -> 0.03 over updates 0 to 10; OUT_G from the owner's mark file (wins; now {}) or the automatic mark at update "
        "{} ({}); saves kept at {} and the end; never written: {}; FREE: the clock never holds or steps back, a check under 40% is a MAJOR PROBLEM{}".format(
            a.run, "present" if os.path.exists(os.path.join(WD, "out_mark.json")) else "absent", (CFG[0] or {}).get("at"),
            "decided already: {}".format({k_: AUTO_D[0].get(k_) for k_ in ("passed", "src", "mark", "open")}) if AUTO_D[0] else
            ("settings {}".format(CFG[0]) if CFG[0] else "OFF"), MARKS, UNSCHEDULED, " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = len(L0) if (a.resume and L0) else 0
    seen, marked, ended = mtime(), set(), [False]
    if a.resume:
        marked = {k_ for k_ in MARKS if any(f_.startswith("policy_u") and f_.endswith(".pt") and f_[8:-3].isdigit() and int(f_[8:-3]) >= k_
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
            for k_ in MARKS:
                if n >= k_ and k_ not in marked:
                    marked.add(k_)
                    keep("policy_u{}.pt".format(n))
                    log("kept keep/policy_u{}.pt with its optimizer (the mark {}{})".format(n, k_, ": the save the automatic mark is decided on" if k_ == 60 else ""))
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
