"""1.9a's dials (owner, 2026-11-12; docs/runs/1.9/1.9a/CARD.md), on the clock of updates done, straight lines, each held after its end.
From 1.8a's end (its save of update 190). 200 updates; most of it concurrent (owner: "it can probably go most concurrently"):
     INS_GATE      -12  -> 0     updates 0 to 20     the instruction's attention token in the hands (shut at -30 before)
     RAIL_FAR_PAY  0.25 -> 0     updates 0 to 40     the hand-built far-rail pay out
     INS_COPY      1             updates 0 to 60     the copy lesson: the head's scorer taught toward his old head's target and the weapon in his hand
                   1    -> 0     updates 60 to 100   ... and faded once the head is paid on its own choices
     INS_G         0    -> 1     updates 20 to 80    the seat's coin: on = the head's instruction every 0.2 s (no lock), never "none", the weapon bound
     FOLLOW_PAY    0    -> 0.01  updates 20 to 60    the hands' pay a second for carrying an instruction out (its state "doing")
                   0.01 -> 0     updates 150 to 180  ... out
     H2_INS_PG     0    -> 1     updates 40 to 100   the pay on the head's own choices: the judge's change in win chance with the items' race
     SFADE         0    -> 1     updates 100 to 140  the strategy inputs out of the hands
Set at the start and never moved (start_live.py): the old head's target credit H2_PG 0, the item rule's lesson 0, the speed pay 0, the switch
cost 0, a held weapon choosable, the keep choice 0 (the 8-second lock acts on no seat under the head's instruction: it goes with INS_G), no
drills, no frozen moments, AIM3 at its end values, DMG_REWARD 0.005 zero-sum, WIN_ADD 0.33 (the hands' win part: the judge without the items).
The clock is the number of lines in metrics.jsonl. Written to live.json (read between rollouts) after each new update. The clock never holds or
steps back (owner, 2026-11-04; CLAUDE.md rule 6): every check is logged with its win rate, one under 40% as a MAJOR PROBLEM, and the owner decides.
Kept with their optimizers: the first saves at or past the marks (keep/policy_u<update>_19a.pt): every 10 updates (a run of nights stops at any save in the morning).
Logged in watch.log each update: the ledger, frags a match-minute, the instruction's records (ins with the copy lesson's term and agreement,
the tick readouts, ins_bind, ins_norow, pay_of, follow, judge_items), the old head's parts, speed, big weapons owned, his weapon in hand,
the firing cost. Flagged: a refused or unapplied live.json (MAJOR); a check under 40% (MAJOR); any firing cost above zero (MAJOR); the old
head's credit above 0 (MAJOR); played seats changing order over 2.5 times a second; frags a match-minute under 1.5; weapon changes a
player-minute over 20; one block of rows over 80% of the head's picks; a part of his target scores over 40 (rule 11); the lightning in his
hand over 60% of his time in games (reported, nothing acted on). Nothing here stops the run.
    python docs/runs/1.9/1.9a/ramp_19a.py <run> [--poll S] [--settle S] [--dir D] [--resume]"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
DROOT = os.environ.get("QLBOT_ROOT") or ROOT                 # (the repo that has data/)
DIALS = (("INS_GATE", 0, 12, -12.0, 0.0, -30.0),          # (name, from update, to update, its value there, at the end, before)
         ("INS_COPY", 36, 60, 1.0, 0.0, 1.0),
         ("INS_G", 12, 48, 0.0, 1.0, 0.0),
         ("FOLLOW_PAY", 12, 36, 0.0, 0.01, 0.0),
         ("FOLLOW_PAY", 90, 108, 0.01, 0.0, 0.0),            # (a second segment of a name: from its start it is the one in force)
         ("H2_INS_PG", 24, 60, 0.0, 1.0, 0.0),
         ("SFADE", 60, 84, 0.0, 1.0, 0.0))
END = max(d[2] for d in DIALS)
MARKS = tuple(range(10, 121, 10))                           # (every save: a morning stop at any save of the night, 44 MB each)
SIZE_FLAG = 40.0
MAJOR = 0.40
FRAGS_MIN = 1.5
QUIET_MAX = 0.08
LG_SHARE = 0.6                                               # the lightning in his hand, of his time in games: reported over this (1.8a's end: 0.59)
CHG_MAX = 2.5                                                # changes of order a second on the played seats: reported over this (half of all ticks)
WPN_CHG = 20.0                                               # weapon changes a player-minute: reported over this (the binding weapon's flicker)
BLOCK_MAX = 0.8                                              # one block of rows taking this share of the head's picks: reported


def dial_at(clock, lo, hi, v0, v1, pre):
    if clock < lo:
        return pre
    f = min(1.0, max(0.0, (clock - lo) / float(hi - lo)))
    return v0 + (v1 - v0) * f


def values(clock):
    """every name's value at the clock: a name with several segments takes the last one begun (before the first: its "before")"""
    out = {}
    for n_, lo, hi, v0, v1, pre in DIALS:
        if n_ not in out or clock >= lo:
            out[n_] = dial_at(clock, lo, hi, v0, v1, pre)
    return out


def befores():
    out = {}
    for n_, lo, hi, v0, v1, pre in DIALS:
        out.setdefault(n_, pre)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    D = a.dir or os.path.join(DROOT, "data", "sim_runs", a.run)
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
        names = {"checks_prev.jsonl": "the start (1.8a's end, update 190)", "checks_ref.jsonl": "1.7a's update 90"}
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
                got_ = {n2_: (ap_.get("file") or {}).get(n2_) for n2_ in befores()}
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
                u_ = seen_m[0]                               # (the run's update: the line of metrics.jsonl; the trainer's own number starts at 1 again
                #                                              after the restart at 150: found by tests.py smoke)
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
                fc_ = {k2_: v_ for k2_, v_ in pm_.items() if any(w_ in k2_ for w_ in ("shot", "fire", "blind")) and v_}
                tsw_ = {k2_: v_ for k2_, v_ in pm_.items() if "switch" in k2_ and v_}   # (the target-switch cost: not a firing cost; on a seat under no
                if tsw_:                                     # instruction only; 0 in 1.9a: a FLAG if it is there)
                    log("FLAG update {}: the target-switch cost a player-minute {} (INTENT_SWITCH is 0 in 1.9a)".format(u_, tsw_))
                log("update {}: big weapons owned {} | in hand in games rockets {} lightning {} rail {} | firing cost {} {}".format(
                    u_, bw_, ih_.get("rl"), ih_.get("lg"), ih_.get("rg"), sc_, fc_ or ""))
                if (sc_ or 0) > 0 or any(v_ < 0 for v_ in fc_.values()):
                    log("MAJOR PROBLEM FLAG update {}: A FIRING COST ABOVE ZERO: shot cost {} {}".format(u_, sc_, fc_))
                big_ = {k2_: wp_.get(k2_) for k2_ in ("hands", "head") if (wp_.get(k2_) or 0) > SIZE_FLAG}
                if big_:
                    log("FLAG update {}: a part of his weapon-key scores over {}: {}".format(u_, SIZE_FLAG, big_))
                for k2_ in ("ins", "ins_bind", "ins_norow", "pay_of", "follow", "judge_items", "fight"):     # (2.1) the instruction's records, as the trainer writes them
                    if m_.get(k2_) is not None:
                        log("update {}: {} {}".format(u_, k2_, json.dumps(m_[k2_], default=str)[:900]))
                tk_ = (m_.get("ins") or {}).get("tick") or {}     # (2.1a) the tick readouts: the head re-decides every 0.2 s; played and shadow seats
                for w_ in ("played", "shadow"):
                    if tk_.get(w_):
                        log("update {}: the head's choice, {} seats: {}".format(u_, w_, json.dumps(tk_[w_])))
                if ((tk_.get("played") or {}).get("ticks") or 0) > 0 and ((tk_.get("played") or {}).get("under_none") or 0) > 0:
                    log("FLAG update {}: played seats are under none on {} of their ticks (no valid real row: {})".format(u_, tk_["played"]["under_none"], m_.get("ins_norow")))
                if ((tk_.get("played") or {}).get("ticks") or 0) > 0 and ((tk_.get("played") or {}).get("changes_a_second") or 0) > CHG_MAX:
                    log("FLAG update {}: the played seats change order {} times a second (over {}: half of all ticks)".format(u_, tk_["played"]["changes_a_second"], CHG_MAX))
                ib_ = m_.get("ins_bind") or {}
                if (ib_.get("weapon_changes_min") or 0) > WPN_CHG:
                    log("FLAG update {}: weapon changes a player-minute {} (over {})".format(u_, ib_.get("weapon_changes_min"), WPN_CHG))
                bk_ = ((m_.get("ins") or {}).get("picks") or {}).get("blocks") or {}
                tot_ = sum(v_ for v_ in bk_.values() if isinstance(v_, (int, float))) if isinstance(bk_, dict) else 0
                big4_ = {k2_: round(v_ / tot_, 3) for k2_, v_ in bk_.items() if isinstance(v_, (int, float)) and v_ / tot_ > BLOCK_MAX} if tot_ else {}
                if big4_:
                    log("FLAG update {}: one block of rows takes over {} of the head's picks: {}".format(u_, BLOCK_MAX, big4_))
                h2_ = m_.get("head2") or {}
                if (h2_.get("credit") or 0) > 0:
                    log("MAJOR PROBLEM update {}: the old head's target credit is {} (H2_PG stays 0 in 1.9a)".format(u_, h2_.get("credit")))
                big2_ = {k2_: h2_.get(k2_) for k2_ in ("hands", "raw") if (h2_.get(k2_) or 0) > SIZE_FLAG}
                if big2_:
                    log("FLAG update {}: a part of his target scores over {}: {}".format(u_, SIZE_FLAG, big2_))
                log("update {}: his target scores: the hands' part {} the head's part {} their cosine {} | the head's credit {}".format(
                    u_, h2_.get("hands"), h2_.get("raw"), h2_.get("cos"), h2_.get("credit")))
                if (ih_.get("lg") or 0) > LG_SHARE:
                    log("FLAG update {}: the lightning is in his hand {} of his time in games (over {}; reported, nothing acted on)".format(u_, ih_.get("lg"), LG_SHARE))
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

    SAMPLE = os.path.join(DROOT, "data", "sim_runs", "inputs21", "sample_obs.npy")   # (raw rows of list 21's simulator; not there: no health report)

    def health(name):
        """(CLAUDE.md "Inputs") the input health report of a kept save (tools/run/input_health.py on the standing sample of real play): its
        summary and its FLAG lines into the log; each group's share at the hands', the brain's and the head's first layer in keep/"""
        try:
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "run", "input_health.py"), os.path.join(KEEP, name), SAMPLE, "--quiet", "--json",
                                os.path.join(KEEP, name.replace("policy_", "input_health_", 1).replace(".pt", ".json"))],
                               capture_output=True, text=True, timeout=900, env=dict(os.environ, CUDA_VISIBLE_DEVICES="-1", OPENBLAS_NUM_THREADS="1"),
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for ln in (r.stdout or "").splitlines()[-40:]:
                log("{} | {}".format(name, ln[:300]))
            if r.returncode not in (0, 1):
                log("input health of {} did not run: {}".format(name, (r.stderr or "")[-300:]))
        except Exception as e:                               # noqa: BLE001
            log("input health of {} did not run: {}".format(name, repr(e)[:200]))

    def keep(name):
        shutil.copy2(POL, os.path.join(KEEP, name))
        shutil.copy2(OPT, os.path.join(KEEP, name.replace("policy_", "opt_", 1)))
        if not a.dir and os.path.exists(SAMPLE):             # (not on the fake files of ramp_test.py)
            threading.Thread(target=health, args=(name,), daemon=True).start()

    def write(clock):
        d = json.load(open(LIVE, encoding="utf-8"))
        for n_, x_ in values(clock).items():
            d[n_] = round(x_, 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        v_ = {n_: d[n_] for n_ in befores()}
        with WLOCK:
            WRITES.append((clock, v_))
        return v_

    cur = json.load(open(LIVE, encoding="utf-8"))
    WRITES0.update({n_: cur.get(n_) for n_ in befores()})
    for n_, pre in ([] if a.resume else befores().items()):
        assert abs(float(cur.get(n_, -99)) - pre) < 1e-9, "{} is {} in live.json, not {}".format(n_, cur.get(n_), pre)
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_19a on for {}: {}; FREE: the clock never holds or steps back, a check under 40% is a MAJOR PROBLEM{}".format(
        a.run, ", ".join("{} {} -> {} over updates {} to {} ({} before)".format(n_, v0, v1, lo, hi, pre) for n_, lo, hi, v0, v1, pre in DIALS),
        " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = len(L0) if a.resume else 0                      # (the clock: the lines of metrics.jsonl, as the watcher counts)
    seen, marked = mtime(), set()
    if a.resume:
        marked = {k_ for k_ in MARKS if any(f_.startswith("policy_u") and f_.endswith("_19a.pt") and int(f_[8:-7]) >= k_
                                            for f_ in os.listdir(KEEP) if f_[8:-7].isdigit())}
    while True:
        time.sleep(a.poll)
        L = jl(MET)
        n = len(L)
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
                    keep("policy_u{}_19a.pt".format(n))
                    log("kept keep/policy_u{}_19a.pt with its optimizer (the mark {})".format(n, k_))


if __name__ == "__main__":
    main()
