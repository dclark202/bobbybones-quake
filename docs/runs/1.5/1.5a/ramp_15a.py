"""1.5a's dial (owner, 2026-11-04; CARD.md), on the clock of updates done:
  H2_WPG          0 -> 1      over updates 10 to 90  (part B: the weapon key's credit moves from the hands' term to the head's own;
                                                      owner, 11-04: "Make the ramp start at u10 and take 80 updates")
Written to live.json (read between rollouts) after each new update. The clock never holds or steps back (owner, 2026-11-04: "Don't hold
the ramps just go forward with them"; CLAUDE.md rule 6): every check is logged with its win rate, one under 40% as a MAJOR PROBLEM, and
the owner decides. Kept with their optimizers: the first saves at or past updates 10 (the dial's start), 50 and 90 (its end)
(keep/policy_u<update>_15a.pt). At the first kept save at or past update 50: the blanked check (blank_check.py: the head's weapon scores
switched off, against 1.3b's end, 200 games), started on this process's cores. Logged in watch.log each update: his weapon in hand in games
(rockets, lightning, rail) and the weapon part's record. Flagged: the head's weapon part over 40 (its centred size on the key's
frames) or the hands' over 40; the weapon key's step on the head's term (kl) over 0.05; a check under 40%; a habit kind with no league
frames once the league plays; his speed on trips or its share over 320 more than 10% under the run's first five updates; trips a minute
50% over them; targets reached 30% under them (1.4c's watch). Nothing here stops the run.
    python docs/runs/1.5/1.5a/ramp_15a.py <run> [--poll S] [--settle S] [--dir D] [--resume] [--blank-at 50]"""
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
DIALS = (("H2_WPG", 10, 90, 0.0, 1.0),)
END = max(d[2] for d in DIALS)
MARKS = (10, 50, 90)
SIZE_FLAG = 40.0
MAJOR = 0.40


def dial_at(clock, lo, hi, v0, v1):
    f = min(1.0, max(0.0, (clock - lo) / float(hi - lo)))
    return v0 + (v1 - v0) * f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--poll", type=float, default=30)
    ap.add_argument("--settle", type=float, default=20)
    ap.add_argument("--dir", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--blank-at", type=int, default=50, help="the blanked check at the first kept save at or past this update (0: none)")
    a = ap.parse_args()
    D = a.dir or os.path.join(ROOT, "data", "sim_runs", a.run)
    WD, LIVE, POL, OPT, KEEP, MET = (os.path.join(D, "watch"), os.path.join(D, "live.json"), os.path.join(D, "policy.pt"), os.path.join(D, "opt.pt"),
                                     os.path.join(D, "keep"), os.path.join(D, "metrics.jsonl"))
    os.makedirs(WD, exist_ok=True)
    os.makedirs(KEEP, exist_ok=True)

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
        seen = {"checks_prev.jsonl": 0, "checks_ref.jsonl": 0, "checks_blank.jsonl": 0}
        names = {"checks_prev.jsonl": "the start (1.3b's end)", "checks_ref.jsonl": "b1.2d's end",
                 "checks_blank.jsonl": "1.3b's end, the head's weapon scores switched off (add 0)"}
        if a.resume:
            seen = {f_: len(jl(os.path.join(WD, f_))) for f_ in seen}
        seen_m, base = [len(jl(MET)) if a.resume else 0], []
        while True:
            for f_, n_ in seen.items():
                R = jl(os.path.join(WD, f_))
                for d in R[n_:]:
                    log(("MAJOR PROBLEM " if wr(d) < MAJOR else "") + "check update {} against {}: {}-{} = {:.1%}{}".format(
                        d["update"], names[f_], d["won"], d["lost"], wr(d), " (under 40%)" if wr(d) < MAJOR else ""))
                seen[f_] = len(R)
            for m_ in jl(MET)[seen_m[0]:]:
                seen_m[0] += 1
                u_ = m_.get("update")
                ih_ = (m_.get("v15") or {}).get("in_hand_games") or {}
                wp_ = m_.get("weapon") or {}
                hb_ = m_.get("habit") or {}
                log("update {}: in hand in games rockets {} lightning {} rail {} | weapon credit {} head part {} hands {} cos {} kl {} | "
                    "habits {}".format(u_, ih_.get("rl"), ih_.get("lg"), ih_.get("rg"), wp_.get("credit"), wp_.get("head"), wp_.get("hands"),
                                       wp_.get("cos"), wp_.get("kl"), hb_.get("share")))
                big_ = {k_: wp_.get(k_) for k_ in ("hands", "head") if (wp_.get(k_) or 0) > SIZE_FLAG}
                if big_:
                    log("FLAG update {}: a part of his weapon-key scores over {}: {}".format(u_, SIZE_FLAG, big_))
                if (wp_.get("kl") or 0) > 0.05:
                    log("FLAG update {}: the weapon key's step on the head's term {} (over 0.05)".format(u_, wp_.get("kl")))
                fr_ = hb_.get("frames") or {}
                if fr_ and sum(fr_.values()) > 0 and any(fr_.get(k_, 0) == 0 for k_ in ("pro", "rg", "rl")) and (hb_.get("p") or 0) > 0:
                    log("FLAG update {}: a habit with no league frames: {}".format(u_, fr_))
                h2_ = m_.get("head2") or {}
                big2_ = {k_: h2_.get(k_) for k_ in ("hands", "raw") if (h2_.get(k_) or 0) > SIZE_FLAG}
                if big2_:
                    log("FLAG update {}: a part of his target scores over {}: {}".format(u_, SIZE_FLAG, big2_))
                pc_, it_ = m_.get("pace") or {}, m_.get("intent") or {}
                now_ = (pc_.get("trip_speed"), pc_.get("over_320"), it_.get("trips_per_player_min"), it_.get("reached"))
                if None in now_:
                    continue
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
        for n_, lo, hi, v0, v1 in DIALS:
            d[n_] = round(dial_at(clock, lo, hi, v0, v1), 6)
        with open(LIVE + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(d))
        os.replace(LIVE + ".tmp", LIVE)
        return {n_: d[n_] for n_, *_ in DIALS}

    cur = json.load(open(LIVE, encoding="utf-8"))
    for n_, lo, hi, v0, v1 in ([] if a.resume else DIALS):
        assert abs(float(cur.get(n_, -1)) - v0) < 1e-9, "{} is {} in live.json, not {}".format(n_, cur.get(n_), v0)
    threading.Thread(target=flags, daemon=True).start()
    log("ramp_15a on for {}: {}; FREE: the clock never holds or steps back, a check under 40% is a MAJOR PROBLEM{}".format(
        a.run, ", ".join("{} {} -> {} over updates {} to {}".format(n_, v0, v1, lo, hi) for n_, lo, hi, v0, v1 in DIALS), " (resumed)" if a.resume else ""))
    L0 = jl(MET)
    done_n = int(L0[-1]["update"]) if (a.resume and L0) else 0
    seen, marked, blanked = mtime(), set(), os.path.exists(os.path.join(WD, "blank_started"))
    if a.resume:
        marked = {k_ for k_ in MARKS if any(f_.startswith("policy_u") and f_.endswith("_15a.pt") and int(f_[8:-7]) >= k_
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
                    keep("policy_u{}_15a.pt".format(n))
                    log("kept keep/policy_u{}_15a.pt with its optimizer (the mark {})".format(n, k_))
                    if a.blank_at and k_ == a.blank_at and not blanked:
                        blanked = True
                        open(os.path.join(WD, "blank_started"), "w").write(str(n))
                        subprocess.Popen([sys.executable, os.path.join(HERE, "blank_check.py"), a.run, os.path.join(KEEP, "policy_u{}_15a.pt".format(n)),
                                          str(n)], cwd=ROOT, stdout=open(os.path.join(WD, "blank_stdout.log"), "a"), stderr=subprocess.STDOUT,
                                         creationflags=0x4000 | 0x08000000)
                        log("the blanked check started on the save of update {} (the head's weapon scores switched off, against 1.3b's end)".format(n))


if __name__ == "__main__":
    main()
