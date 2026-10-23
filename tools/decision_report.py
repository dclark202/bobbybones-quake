"""The decision report (docs/v0.3.12/BELIEF_LOOP.md, "How we measure whether the picture is used"): do his item and fight
choices follow the situation (the enemy's stack and place)? Plays the checks' games (tools/duel_eval.py's play(): two
networks, seats swapped, each seat's aim delays and clock) and reads the simulator's truth every frame beside them.

    python tools/decision_report.py --policy <a.pt> --opp policy:<b.pt> --map bloodrun,aerowalk --games 8 --minutes 10 \
        --procs 2 --swap --round 600 --opp-round 600 --opp-react-ms 100 --opp-acquire-ms 160 --set OVERTIME=1 --set ... \
        --json data/decision/<name>.json          (Anaconda Python; a .txt table is written beside the json)

Every row is counted for each side ("he" = --policy, "opponent" = the other network), per map and over all maps. "Stack" is
health + armor; "the gap" is his stack minus the enemy's (bands < -75, -75..-25, -25..25, 25..75, > 75).
 1 fight or avoid  a fresh sighting: his env.visible (the enemy in his sight cone with a clear line: the fact, not what he
                   noticed) opens after 1 s or more shut, both alive. Over the next 2 s (while both live): his closing speed,
                   the mean of his horizontal velocity along the horizontal line to the enemy (positive: toward); closes =
                   that mean > 50 u/s, backs off = < -50 u/s. Over the next 10 s: who loses stack first (a drop of 3 or more
                   on a frame, a death included; the decay above 100 is 1 a second) and who dies. By the gap at the sighting;
                   the slope of closing against the gap (u/s per 100 points, least squares).
 2 items vs enemy  each mega and red armor he takes (an item_up flip, given to the seat nearest the item): the enemy's distance
                   to it then and 3 s before, alive; "heading" = the enemy 150 u or more nearer than 3 s before; "near" = within
                   600 u. Lost contest: the enemy takes one while he is alive within 600 u of it. By his stack just before.
 3 timing          every respawn of a mega or red (item_up back on; the game's first spawns are not counted): per side, took
                   it "waiting" (within 200 u of it at the respawn), "on time" (otherwise taken within 2 s), "late" (later), or
                   missed: "enemy took" (within 10 s) or "unused 10 s+" (nobody took it in 10 s, and he not later either).
                   Split by the enemy's stack at the respawn (weak < 100).
 4 deaths weak     his deaths with his stack < 100 and the enemy's > 150 on the frame before; per game.
 5 lost sight      his env.visible shuts after 0.5 s or more open, both alive: over the next 5 s (while both live), the mean of
                   his horizontal velocity toward the enemy's TRUE place; toward > 50, away < -50 u/s; the change of distance.
                   By the gap at the moment it shut.
 6 belief          rows 1 and 5 again with the gap from his own hand-built belief (EN_STACK: es_h + es_a of the enemy's slot)
                   in place of the truth; zeros when EN_STACK is off.
Overtime frames are counted with the rest. Low cost: positions are kept 3 s back, everything else per event.
"""
import argparse
import json
import multiprocessing as mp_
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import duel_eval as DE  # noqa: E402
import pin  # noqa: E402

GAP_EDGES = (-75.0, -25.0, 25.0, 75.0)
GAP_NAMES = ("< -75", "-75..-25", "-25..25", "25..75", "> 75")
STACK_EDGES = (100.0, 150.0)
STACK_NAMES = ("< 100", "100..150", "> 150")
SIGHT_SHUT_S, LOST_OPEN_S = 1.0, 0.5
CLOSE_S, OUTCOME_S, LOST_S, HIST_S = 2.0, 10.0, 5.0, 3.0
MOVE_V = 50.0
NEAR, WAIT_R, HEADING = 600.0, 200.0, 150.0
ON_TIME_S, UNUSED_S = 2.0, 10.0


def band(x, edges):
    return int(np.searchsorted(edges, x, side="right"))


class Recorder:
    """reads the truth after every env.step(); sides: 0 he, 1 the opponent"""

    def __init__(self, E, env, swap):
        self.E, self.env = E, env
        n = env.n
        assert getattr(env, "G", 2) == 2 and n % 2 == 0, "duels only"
        self.n, self.dt = n, float(E.DT)
        self.side = (np.arange(n) + int(swap)) % 2
        self.big = [k for k, d in enumerate(env.item_def) if d[4] in ("MH", "RA")]
        self.big_lab = [env.item_def[k][4] for k in self.big]
        self.ipos = np.asarray(env.item_pos, np.float64)[self.big]
        self.nh = max(1, int(round(HIST_S / self.dt)))
        self.hist = None
        self.t = -1
        self.shut = np.full(n, 1e9)          # seconds his view of the enemy has been shut
        self.open_ = np.zeros(n)             # ... open
        self.vis0 = np.zeros(n, bool)
        self.alive0 = np.ones(n, bool)
        self.stack0 = None
        self.up0 = None
        self.win = []                        # open windows: dict(kind, seat, t0, ...)
        self.cyc = {}                        # (match, big index) -> the respawn cycle
        self.R = {s: dict(sight=[], lost=[], picks=[], lost_contest=[], timing=[], deaths=0, deaths_weak=0) for s in (0, 1)}

    def bel(self):
        env, i = self.env, np.arange(self.n)
        if not hasattr(env, "es_h"):
            return np.full(self.n, np.nan)
        k = (i ^ 1) % 2
        return np.asarray(env.es_h, np.float64)[i, k] + np.asarray(env.es_a, np.float64)[i, k]

    def step(self, info):
        env, n, dt = self.env, self.n, self.dt
        self.t += 1
        if self.t == 0:                                      # duel_eval's warm-up step
            return
        st = np.asarray(env.state, np.float64)
        pos, vel = st[:, :3], st[:, 3:6]
        hp, ar = np.asarray(env.hp, np.float64), np.asarray(env.armor, np.float64)
        alive = hp > 0
        stack = np.where(alive, hp + ar, 0.0)
        oth = np.arange(n) ^ 1
        vis = np.asarray(env.visible, bool)[:n] & alive & alive[oth]
        both = alive & alive[oth]
        if self.hist is None:
            self.hist = np.repeat(pos[None], self.nh, 0)
            self.stack0 = stack.copy()
            self.up0 = np.asarray(env.item_up, bool)[:, self.big].copy()
        died = np.zeros(n, bool)
        for e in info.get("events", ()):
            died[int(e["victim"])] = True
        # damage this frame: a drop of 3 or more (or a death)
        hurt = died | (self.alive0 & alive & (self.stack0 - stack >= 3.0))
        dvec = pos[oth, :2] - pos[:, :2]
        dist2 = np.linalg.norm(dvec, axis=1)
        u = dvec / np.maximum(dist2, 1e-6)[:, None]
        vtow = (vel[:, :2] * u).sum(1)                       # his horizontal speed toward the enemy's true place
        dist3 = np.linalg.norm(pos[oth] - pos, axis=1)
        gap = self.stack0 - self.stack0[oth]                 # (the frame before: what the moment started from)
        bel = self.bel()
        bgap = self.stack0 - bel
        # --- 4: deaths while weak
        for v in np.nonzero(died)[0]:
            s = self.side[v]
            self.R[s]["deaths"] += 1
            if self.stack0[v] < 100 and self.stack0[v ^ 1] > 150:
                self.R[s]["deaths_weak"] += 1
        # --- windows going on
        keep = []
        for w in self.win:
            i, j = w["seat"], w["seat"] ^ 1
            age = (self.t - w["t0"]) * dt
            if w["kind"] == "sight":
                if age <= CLOSE_S and w["both"] and both[i]:
                    w["v"] += vtow[i]
                    w["nv"] += 1
                elif w["both"] and not both[i]:
                    w["both"] = False
                if w["first_hurt"] is None and (hurt[i] or hurt[j]):
                    w["first_hurt"] = "both" if (hurt[i] and hurt[j]) else ("he" if hurt[i] else "enemy")
                if w["died"] is None and (died[i] or died[j]):
                    w["died"] = "both" if (died[i] and died[j]) else ("he" if died[i] else "enemy")
                if age >= OUTCOME_S:
                    self._close_sight(w)
                    continue
            elif w["kind"] == "lost":
                if age <= LOST_S and both[i] and not w["ended"]:
                    w["v"] += vtow[i]
                    w["nv"] += 1
                    w["d1"] = dist3[i]
                else:
                    w["ended"] = True
                if w["ended"]:
                    self._close_lost(w)
                    continue
            keep.append(w)
        self.win = keep
        # --- 1: fresh sightings; 5: sight lost
        fresh = vis & ~self.vis0 & (self.shut >= SIGHT_SHUT_S)
        lost = ~vis & self.vis0 & both & (self.open_ >= LOST_OPEN_S)
        for i in np.nonzero(fresh)[0]:
            self.win.append(dict(kind="sight", seat=int(i), t0=self.t, gap=float(gap[i]), bgap=float(bgap[i]), v=0.0, nv=0, both=True,
                                 first_hurt=None, died=None, dist=float(dist3[i])))
        for i in np.nonzero(lost)[0]:
            if not any(w["kind"] == "lost" and w["seat"] == i for w in self.win):
                self.win.append(dict(kind="lost", seat=int(i), t0=self.t, gap=float(gap[i]), bgap=float(bgap[i]), v=0.0, nv=0,
                                     d0=float(dist3[i]), d1=float(dist3[i]), ended=False))
        self.shut = np.where(vis, 0.0, self.shut + dt)
        self.open_ = np.where(vis, self.open_ + dt, 0.0)
        # --- 2, 3: the big items
        up = np.asarray(env.item_up, bool)[:, self.big]
        gone = self.up0 & ~up
        back = ~self.up0 & up
        for m, q in zip(*np.nonzero(back)):
            ip = self.ipos[q]
            dd = np.linalg.norm(pos[2 * m:2 * m + 2] - ip, axis=1)
            al = alive[2 * m:2 * m + 2]
            self.cyc[(m, q)] = dict(t0=self.t, wait=[bool(al[0] and dd[0] < WAIT_R), bool(al[1] and dd[1] < WAIT_R)],
                                    en_weak=[bool(stack[2 * m + 1] < 100), bool(stack[2 * m] < 100)], taker=None, tp=None)
        for m, q in zip(*np.nonzero(gone)):
            ip = self.ipos[q]
            seats = np.array([2 * m, 2 * m + 1])
            dd = np.linalg.norm(pos[seats] - ip, axis=1)
            i = int(seats[np.argmin(dd)])
            j = i ^ 1
            s = self.side[i]
            d_now = float(np.linalg.norm(pos[j] - ip))
            d_bef = float(np.linalg.norm(self.hist[self.t % self.nh][j] - ip))     # (the oldest kept: 3 s ago)
            self.R[s]["picks"].append(dict(item=self.big_lab[q], stack=float(self.stack0[i]), en_alive=bool(alive[j]), en_d=d_now, en_d3=d_bef,
                                           heading=bool(alive[j] and d_bef - d_now >= HEADING), near=bool(alive[j] and d_now < NEAR)))
            if alive[j] and np.linalg.norm(pos[j] - ip) < NEAR:          # the other side lost a contest
                self.R[self.side[j]]["lost_contest"].append(dict(item=self.big_lab[q], stack=float(self.stack0[j]), d=float(np.linalg.norm(pos[j] - ip))))
            c = self.cyc.pop((m, q), None)
            if c is not None:
                c["taker"], c["tp"] = int(i - 2 * m), self.t
                self._close_cycle(m, q, c)
        for key, c in list(self.cyc.items()):                # unused 10 s: counted as a miss for both, the cycle stays open for a late taker
            if not c.get("unused") and (self.t - c["t0"]) * dt > UNUSED_S:
                c["unused"] = True
        self.hist[self.t % self.nh] = pos
        self.vis0, self.alive0, self.stack0, self.up0 = vis, alive, stack, up.copy()

    def _close_sight(self, w):
        s = self.side[w["seat"]]
        self.R[s]["sight"].append(dict(gap=w["gap"], bgap=w["bgap"], close=(w["v"] / w["nv"]) if w["nv"] else None, hurt=w["first_hurt"] or "none",
                                       died=w["died"] or "none", dist=w["dist"]))

    def _close_lost(self, w):
        if w["nv"] < 4:                                      # (a death within 0.1 s: nothing to read)
            return
        s = self.side[w["seat"]]
        self.R[s]["lost"].append(dict(gap=w["gap"], bgap=w["bgap"], v=w["v"] / w["nv"], dd=w["d1"] - w["d0"], secs=w["nv"] * self.dt))

    def _close_cycle(self, m, q, c):
        lab = self.big_lab[q]
        for k in (0, 1):
            s = self.side[2 * m + k]
            if c["taker"] == k:
                dly = (c["tp"] - c["t0"]) * self.dt
                cat = "waiting" if c["wait"][k] else ("on_time" if dly <= ON_TIME_S else "late")
            else:
                cat = "unused_10s" if c.get("unused") else "enemy_took"
            self.R[s]["timing"].append(dict(item=lab, cat=cat, en_weak=c["en_weak"][k]))

    def finish(self):
        for w in self.win:
            if w["kind"] == "sight":
                self._close_sight(w)
            else:
                self._close_lost(w)
        for (m, q), c in self.cyc.items():                   # cycles open at the end: only those already unused count
            if c.get("unused"):
                for k in (0, 1):
                    self.R[self.side[2 * m + k]]["timing"].append(dict(item=self.big_lab[q], cat="unused_10s", en_weak=c["en_weak"][k]))
        return self.R


def work(job):
    """a pool worker: duel_eval.play() with the simulator's step watched"""
    envmod, envvars, swap = job[0], job[1], bool(job[12]) and job[9] is not None
    os.environ.update(envvars)
    import importlib
    E = importlib.import_module(envmod)
    rec = {}
    step0 = E.DuelEnv.step

    def step(self, a):
        out = step0(self, a)
        if "r" not in rec:
            rec["r"] = Recorder(E, self, swap)
        rec["r"].step(out[3])
        return out
    E.DuelEnv.step = step
    try:
        res = DE.play(job)
    finally:
        E.DuelEnv.step = step0
    R = rec["r"].finish()
    return dict(score=res["score"], games=int(res["games"]), R=R)       # (the score already he first)


# ---------------------------------------------------------------- summaries
def pct(a, b):
    return round(float(a) / b, 3) if b else None


def summ(R, games):
    """the rows of one side from its raw lists"""
    S = R["sight"]
    out = {}

    def sight_rows(key):
        rows = []
        for b, nm in enumerate(GAP_NAMES):
            L = [x for x in S if x[key] == x[key] and band(x[key], GAP_EDGES) == b]
            cl = [x["close"] for x in L if x["close"] is not None]
            rows.append(dict(band=nm, n=len(L), close_mean=round(float(np.mean(cl)), 1) if cl else None,
                             closes=pct(sum(c > MOVE_V for c in cl), len(cl)), backs_off=pct(sum(c < -MOVE_V for c in cl), len(cl)),
                             hurt_first_he=pct(sum(x["hurt"] == "he" for x in L), len(L)), hurt_first_enemy=pct(sum(x["hurt"] == "enemy" for x in L), len(L)),
                             he_died=pct(sum(x["died"] in ("he", "both") for x in L), len(L)), enemy_died=pct(sum(x["died"] in ("enemy", "both") for x in L), len(L))))
        xy = np.array([(x[key], x["close"]) for x in S if x["close"] is not None and x[key] == x[key]])
        slope = round(float(np.polyfit(xy[:, 0], xy[:, 1], 1)[0] * 100.0), 1) if len(xy) > 2 and np.ptp(xy[:, 0]) > 0 else None
        return rows, slope
    out["fight"], out["fight_slope_per_100"] = sight_rows("gap")
    out["fight_n"] = len(S)
    Lo = R["lost"]

    def lost_rows(key):
        rows = []
        for b, nm in enumerate(GAP_NAMES):
            L = [x for x in Lo if x[key] == x[key] and band(x[key], GAP_EDGES) == b]
            rows.append(dict(band=nm, n=len(L), v_mean=round(float(np.mean([x["v"] for x in L])), 1) if L else None,
                             toward=pct(sum(x["v"] > MOVE_V for x in L), len(L)), away=pct(sum(x["v"] < -MOVE_V for x in L), len(L)),
                             dist_change=round(float(np.mean([x["dd"] for x in L])), 0) if L else None))
        xy = np.array([(x[key], x["v"]) for x in Lo if x[key] == x[key]])
        slope = round(float(np.polyfit(xy[:, 0], xy[:, 1], 1)[0] * 100.0), 1) if len(xy) > 2 and np.ptp(xy[:, 0]) > 0 else None
        return rows, slope
    out["lost_sight"], out["lost_sight_slope_per_100"] = lost_rows("gap")
    has_bel = any(x["bgap"] == x["bgap"] for x in S)
    if has_bel:
        out["belief"] = dict()
        out["belief"]["fight"], out["belief"]["fight_slope_per_100"] = sight_rows("bgap")
        out["belief"]["lost_sight"], out["belief"]["lost_sight_slope_per_100"] = lost_rows("bgap")
        bg = np.array([(x["gap"], x["bgap"]) for x in S if x["bgap"] == x["bgap"]])
        out["belief"]["gap_error_mean_abs"] = round(float(np.mean(np.abs(bg[:, 0] - bg[:, 1]))), 1) if len(bg) else None
        out["belief"]["same_band"] = pct(sum(band(a, GAP_EDGES) == band(b, GAP_EDGES) for a, b in bg), len(bg))
    P, LC = R["picks"], R["lost_contest"]
    items = []
    for b, nm in enumerate(STACK_NAMES):
        L = [x for x in P if band(x["stack"], STACK_EDGES) == b]
        La = [x for x in L if x["en_alive"]]
        items.append(dict(his_stack=nm, picks=len(L), enemy_near=pct(sum(x["near"] for x in L), len(L)), enemy_heading=pct(sum(x["heading"] for x in L), len(L)),
                          enemy_dist_median=round(float(np.median([x["en_d"] for x in La])), 0) if La else None,
                          lost_contests=sum(1 for x in LC if band(x["stack"], STACK_EDGES) == b)))
    out["items"] = items
    out["items_per_game"] = dict(mega=round(sum(x["item"] == "MH" for x in P) / games, 2), red=round(sum(x["item"] == "RA" for x in P) / games, 2),
                                 lost_contests=round(len(LC) / games, 2))
    T = R["timing"]
    cats = ("waiting", "on_time", "late", "enemy_took", "unused_10s")
    tim = {}
    for nm, f in (("all", lambda x: True), ("enemy_weak", lambda x: x["en_weak"]), ("enemy_not_weak", lambda x: not x["en_weak"]),
                  ("mega", lambda x: x["item"] == "MH"), ("red", lambda x: x["item"] == "RA")):
        L = [x for x in T if f(x)]
        tim[nm] = dict(n=len(L), **{c: pct(sum(x["cat"] == c for x in L), len(L)) for c in cats})
    out["timing"] = tim
    out["deaths_per_game"] = round(R["deaths"] / games, 2)
    out["deaths_weak_per_game"] = round(R["deaths_weak"] / games, 2)
    out["deaths_weak_share"] = pct(R["deaths_weak"], R["deaths"])
    return out


def merge(Rs):
    out = {s: dict(sight=[], lost=[], picks=[], lost_contest=[], timing=[], deaths=0, deaths_weak=0) for s in (0, 1)}
    for R in Rs:
        for s in (0, 1):
            r = R[s] if s in R else R[str(s)]
            for k, v in r.items():
                out[s][k] = out[s][k] + v
    return out


def table(name, d):
    """a short plain-text table of one block (a map or all)"""
    L = ["== {} ({} games) ==".format(name, d["games"])]
    for who in ("he", "opponent"):
        x = d[who]
        L.append("-- {} --".format(who))
        L.append("  fight or avoid (n {}; slope of closing {} u/s per 100 of gap)".format(x["fight_n"], x["fight_slope_per_100"]))
        L.append("    {:10s} {:>5s} {:>7s} {:>7s} {:>7s} {:>8s} {:>8s} {:>7s} {:>7s}".format("gap", "n", "close", "closes", "backs", "hit1st:he", "enemy", "he dies", "en dies"))
        for r in x["fight"]:
            f = lambda v, p=True: "-" if v is None else ("{:.0%}".format(v) if p else "{:.0f}".format(v))   # noqa: E731
            L.append("    {:10s} {:5d} {:>7s} {:>7s} {:>7s} {:>8s} {:>8s} {:>7s} {:>7s}".format(r["band"], r["n"], f(r["close_mean"], False), f(r["closes"]), f(r["backs_off"]),
                                                                                       f(r["hurt_first_he"]), f(r["hurt_first_enemy"]), f(r["he_died"]), f(r["enemy_died"])))
        L.append("  after losing sight (slope {} u/s per 100)".format(x["lost_sight_slope_per_100"]))
        for r in x["lost_sight"]:
            f = lambda v, p=True: "-" if v is None else ("{:.0%}".format(v) if p else "{:.0f}".format(v))   # noqa: E731
            L.append("    {:10s} n {:5d} v {:>5s} toward {:>4s} away {:>4s} dist change {:>5s}".format(r["band"], r["n"], f(r["v_mean"], False), f(r["toward"]), f(r["away"]), f(r["dist_change"], False)))
        if "belief" in x:
            b = x["belief"]
            L.append("  by his belief of the gap (|truth - belief| {} on average; same band {}): closing slope {}, after losing sight slope {}".format(
                b["gap_error_mean_abs"], b["same_band"], b["fight_slope_per_100"], b["lost_sight_slope_per_100"]))
            L.append("    closes by band: " + " | ".join("{} {}".format(r["band"], "-" if r["closes"] is None else "{:.0%} (n {})".format(r["closes"], r["n"])) for r in b["fight"]))
        ip = x["items_per_game"]
        L.append("  items: mega {}/game, red {}/game, lost contests {}/game".format(ip["mega"], ip["red"], ip["lost_contests"]))
        for r in x["items"]:
            L.append("    his stack {:9s} picks {:4d} enemy within 600 {} heading to it {} median enemy dist {} | lost contests {}".format(
                r["his_stack"], r["picks"], "-" if r["enemy_near"] is None else "{:.0%}".format(r["enemy_near"]),
                "-" if r["enemy_heading"] is None else "{:.0%}".format(r["enemy_heading"]), r["enemy_dist_median"], r["lost_contests"]))
        for k, t in x["timing"].items():
            L.append("  timing {:15s} n {:4d} ".format(k, t["n"]) + " ".join("{} {}".format(c, "-" if t[c] is None else "{:.0%}".format(t[c]))
                                                                        for c in ("waiting", "on_time", "late", "enemy_took", "unused_10s")))
        L.append("  deaths {}/game, while weak {}/game ({} of deaths)".format(x["deaths_per_game"], x["deaths_weak_per_game"],
                                                                         "-" if x["deaths_weak_share"] is None else "{:.0%}".format(x["deaths_weak_share"])))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="")
    ap.add_argument("--policy", required=True)
    ap.add_argument("--inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--opp", required=True, help="policy:<file>")
    ap.add_argument("--opp-inputs", default=os.path.join(ROOT, "docs", "INPUTS.csv"))
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--games", type=int, default=8)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--round", type=float, default=600.0)
    ap.add_argument("--opp-round", type=float, default=600.0)
    ap.add_argument("--env", default="duel_env_ffa")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--react-ms", type=float, default=None)
    ap.add_argument("--acquire-ms", type=float, default=None)
    ap.add_argument("--opp-react-ms", type=float, default=None)
    ap.add_argument("--opp-acquire-ms", type=float, default=None)
    ap.add_argument("--swap", action="store_true")
    ap.add_argument("--json", required=True)
    a = ap.parse_args()
    assert a.opp.startswith("policy:"), "two networks only"
    import test_suite as T
    pol = T.Policy(a.policy, seed=1)
    now = DE.names(os.path.join(ROOT, "docs", "INPUTS.csv"))
    old = DE.names(a.inputs)
    assert len(old) == len(pol.mean)
    idx = np.array([now.index(x) for x in old])
    opp_pol = T.Policy(a.opp[7:], seed=2)
    oo = DE.names(a.opp_inputs)
    assert len(oo) == len(opp_pol.mean)
    opp_idx = np.array([now.index(x) for x in oo])
    envvars = dict(x.split("=", 1) for x in a.set)
    delays = (pol.react_ms if a.react_ms is None else a.react_ms, pol.acquire_ms if a.acquire_ms is None else a.acquire_ms,
              opp_pol.react_ms if a.opp_react_ms is None else a.opp_react_ms, opp_pol.acquire_ms if a.opp_acquire_ms is None else a.opp_acquire_ms)
    rounds = (DE.round_of(a.round, pol), DE.round_of(a.opp_round, opp_pol), False)
    out = dict(policy=a.policy, opp=a.opp, env=a.env, set=envvars, delays_ms=list(delays), rounds=list(rounds[:2]), minutes=a.minutes, maps={})
    allR, allG, allsc = [], 0, []
    for mp in a.map.split(","):
        per = [a.games // a.procs + (1 if k < a.games % a.procs else 0) for k in range(a.procs)]
        jobs = [(a.env, envvars, mp, g, a.minutes, a.seed + 17 * k, pol, idx, "policy", opp_pol, opp_idx, rounds, a.swap and k % 2 == 1, delays)
                for k, g in enumerate(per) if g > 0]
        with mp_.Pool(len(jobs), initializer=pin.pin_pool_worker) as pool:
            res = pool.map(work, jobs)
        R = merge([r["R"] for r in res])
        G = sum(r["games"] for r in res)
        sc = np.concatenate([np.array(r["score"]) for r in res])
        allR.append(R)
        allG += G
        allsc.append(sc)
        out["maps"][mp] = dict(games=G, won=int((sc[:, 0] > sc[:, 1]).sum()), drawn=int((sc[:, 0] == sc[:, 1]).sum()), lost=int((sc[:, 0] < sc[:, 1]).sum()),
                               score=[round(float(sc[:, 0].mean()), 2), round(float(sc[:, 1].mean()), 2)], he=summ(R[0], G), opponent=summ(R[1], G))
        print(table(mp, out["maps"][mp]), flush=True)
        with open(a.json, "w", encoding="utf-8") as f:       # (written after every map)
            json.dump(out, f, indent=1)
    R = merge(allR)
    sc = np.concatenate(allsc)
    out["all"] = dict(games=allG, won=int((sc[:, 0] > sc[:, 1]).sum()), drawn=int((sc[:, 0] == sc[:, 1]).sum()), lost=int((sc[:, 0] < sc[:, 1]).sum()),
                      he=summ(R[0], allG), opponent=summ(R[1], allG))
    with open(a.json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    txt = table("all maps", out["all"])
    print(txt, flush=True)
    with open(os.path.splitext(a.json)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join([txt] + [table(mp, v) for mp, v in out["maps"].items()]) + "\n")


if __name__ == "__main__":
    main()
