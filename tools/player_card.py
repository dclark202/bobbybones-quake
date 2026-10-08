"""One card for everybody: the same numbers for people, for the game's Nightmare bot and for BobbyBones, read from the
session logs of the play-test and public servers (docs/LOGS.md, schemas 1 to 4). What a player takes, holds, fires
and how he aims in real games, so that Bobby's numbers can be put beside a person's (owner, 2026-10-07: baselines
for tuning him to play like people, not only hitscan aim).

    python tools/player_card.py                               every session it can find (below)
    python tools/player_card.py <folder or .tar.gz> ...       those sessions (a sessions folder, one session, archives)
    python tools/player_card.py --games                       only real games (a scored duel or an F3 game), no warmup
    python tools/player_card.py --json docs/player_baselines.json

Looks by default in data/duellive/sessions, data/labtest/sessions, data/bench1/sessions, data/bench2/sessions and
T:/quake-sessions/public (the daily pull, tools/pull_sessions.sh). Groups: "people" (no names: a person is a seat of
a session), "Nightmare" (sparring sessions), and one group per trained network. In warmup everybody has every weapon,
so the weapon numbers of warmup show preference and those of games show what was fetched; --games separates them.
Aim: the angle between the crosshair and the opponent he attends to, while that one is in view. Hits are inferred
from health drops and exist for 1v1 only; the game's own table per weapon is in the "player_stats" events (schema 4).
"""
import argparse
import collections
import csv
import glob
import io
import json
import os
import sys
import tarfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WNAME = {1: "g", 2: "mg", 3: "sg", 4: "gl", 5: "rl", 6: "lg", 7: "rg", 8: "pg", 14: "hmg"}
BINS = (0, 150, 300, 450, 700, 1e9)
BIN_NAMES = ("0-150", "150-300", "300-450", "450-700", "700+")
RESPAWN = {"mega": 35.0, "red": 25.0}
ITEM = {"item_health_mega": "mega", "item_armor_body": "red", "item_armor_combat": "yellow", "weapon_rocketlauncher": "rl",
        "weapon_railgun": "rg", "weapon_lightning": "lg"}


def sessions_in(path):
    """yield (name, read(member) -> text or None) for every session under path"""
    if path.endswith(".tar.gz"):
        try:
            tf = tarfile.open(path)
        except (tarfile.TarError, OSError):
            return
        names = tf.getnames()
        top = sorted({n.split("/")[0] for n in names})
        for s in top:
            def rd(member, s=s, tf=tf, names=names):
                n = s + "/" + member
                return tf.extractfile(n).read().decode("utf-8", "replace") if n in names else None
            yield s, rd
    elif os.path.exists(os.path.join(path, "frames.csv")):
        def rd(member, path=path):
            p = os.path.join(path, member)
            return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None
        yield os.path.basename(path.rstrip("/\\")), rd
    elif os.path.isdir(path):
        for p in sorted(glob.glob(os.path.join(path, "*"))):
            if os.path.isdir(p) or p.endswith(".tar.gz"):
                yield from sessions_in(p)


class Acc:
    """running sums for one group"""
    def __init__(self):
        self.n = collections.Counter()
        self.hand = collections.Counter()
        self.fire_w = collections.Counter()
        self.by_dist = [collections.Counter() for _ in BIN_NAMES]
        self.items = collections.Counter()
        self.dmg_w = collections.Counter()
        self.shots, self.hits = collections.Counter(), collections.Counter()      # the game's own table (player_stats events)
        self.aim, self.aim_fire, self.settle, self.first_wp = [], [], [], []
        self.spawn_share = {"mega": [0.0, 0.0], "red": [0.0, 0.0]}
        self.sessions = set()

    def frames(self, t, pos, vel, weapon, fire, up, sees, aim, foe_pos, alive):
        a = alive
        self.n["frames"] += int(a.sum())
        sp = np.hypot(vel[a, 0], vel[a, 1])
        self.n["speed"] += float(sp.sum())
        self.n["fast"] += int((sp > 330).sum())
        self.n["jump"] += int((up[a] > 0).sum())
        self.n["fire"] += int(fire[a].sum())
        for w, c in zip(*np.unique(weapon[a], return_counts=True)):
            self.hand[WNAME.get(int(w), str(int(w)))] += int(c)
        v = a & sees & (aim >= 0)
        self.n["see"] += int(v.sum())
        self.n["on_target"] += int((aim[v] < 3.0).sum())
        if v.any():
            self.aim.append(aim[v])
        f = v & fire
        if f.any():
            self.aim_fire.append(aim[f])
            d = np.linalg.norm(foe_pos[f] - pos[f], axis=1)
            b = np.digitize(d, BINS) - 1
            for bi, w in zip(b, weapon[f]):
                self.by_dist[min(int(bi), len(BIN_NAMES) - 1)][WNAME.get(int(w), "?")] += 1
            for w, c in zip(*np.unique(weapon[f], return_counts=True)):
                self.fire_w[WNAME.get(int(w), "?")] += int(c)
        s = (a & sees).astype(np.int8)                         # he comes into view: how long until the crosshair is within 5 degrees
        on = np.nonzero((s[1:] == 1) & (s[:-1] == 0))[0] + 1
        for i in on:
            if i >= 40 and not s[i - 40:i].any():
                seg = aim[i:i + 80]
                ok = np.nonzero((seg >= 0) & (seg < 5.0))[0]
                if len(ok):
                    self.settle.append(float(t[i + ok[0]] - t[i]))


def card(a):
    f = max(1, a.n["frames"])
    mins = f / 40.0 / 60.0
    aim = np.concatenate(a.aim) if a.aim else np.zeros(0)
    aimf = np.concatenate(a.aim_fire) if a.aim_fire else np.zeros(0)
    sh = lambda c: {k: round(v / max(1, sum(c.values())), 2) for k, v in c.most_common(6)}      # noqa: E731
    out = dict(sessions=len(a.sessions), minutes=round(mins, 1),
               frags_per_min=round(a.n["kills"] / mins, 2), deaths_per_min=round(a.n["deaths"] / mins, 2),
               damage_per_kill=round(a.n["dmg_dealt"] / a.n["kills"], 0) if a.n["kills"] and a.n["dmg_dealt"] else None,
               mega_per_min=round(a.items["mega"] / mins, 2), red_per_min=round(a.items["red"] / mins, 2),
               mega_share_of_spawns=round(a.spawn_share["mega"][0] / a.spawn_share["mega"][1], 2) if a.spawn_share["mega"][1] else None,
               red_share_of_spawns=round(a.spawn_share["red"][0] / a.spawn_share["red"][1], 2) if a.spawn_share["red"][1] else None,
               weapons_per_min=round((a.items["rl"] + a.items["rg"] + a.items["lg"]) / mins, 2),
               first_weapon_s=round(float(np.median(a.first_wp)), 1) if a.first_wp else None,
               lives_with_a_weapon=round(len(a.first_wp) / max(1, a.n["lives"]), 2) if a.n["lives"] else None,
               in_hand=sh(a.hand), fired=sh(a.fire_w),
               fired_by_distance={n: sh(c) for n, c in zip(BIN_NAMES, a.by_dist) if sum(c.values()) > 40},
               damage_by_weapon=sh(a.dmg_w) if a.dmg_w else None,
               speed=round(a.n["speed"] / f), fast_share=round(a.n["fast"] / f, 2), jump_share=round(a.n["jump"] / f, 2),
               firing_share=round(a.n["fire"] / f, 2), enemy_in_view=round(a.n["see"] / f, 2),
               aim_error_in_view=round(float(np.median(aim)), 1) if len(aim) else None,
               aim_error_firing=round(float(np.median(aimf)), 1) if len(aimf) else None,
               on_target_share=round(a.n["on_target"] / max(1, a.n["see"]), 2),
               settle_s=round(float(np.median(a.settle)), 2) if len(a.settle) >= 5 else None,
               accuracy={w: round(a.hits[w] / n_, 2) for w, n_ in a.shots.most_common(6) if n_ >= 20} or None)
    return {k: v for k, v in out.items() if v is not None}


def windows(ev, kinds):
    """[(t0, t1)] of the real games in a session"""
    w, t0 = [], None
    for e in ev:
        if e.get("event") in kinds[0]:
            t0 = e["t"]
        elif e.get("event") in kinds[1] and t0 is not None:
            w.append((t0, e["t"]))
            t0 = None
    return w


def in_windows(t, w):
    m = np.zeros(len(t), bool)
    for a, b in w:
        m |= (t >= a) & (t <= b)
    return m


def run(paths, games_only):
    G = collections.defaultdict(Acc)
    for path in paths:
        for name, rd in sessions_in(path):
            fr, evt, meta = rd("frames.csv"), rd("events.jsonl"), rd("meta.json")
            if not fr or fr.count("\n") < 200:
                continue
            ev = []
            for l in (evt or "").split("\n"):
                try:
                    ev.append(json.loads(l))
                except ValueError:
                    pass
            try:
                meta = json.loads(meta or "{}")
            except ValueError:
                meta = {}
            pol = "Bobby " + str(meta.get("policy", "?")).replace("duel_gru_", "")
            for e in ev:                                       # the game's own per-weapon table, real games only
                if e.get("event") == "player_stats" and not e.get("warmup"):
                    A_ = G["people" if not e.get("bot") else ("Bobby " + str(meta.get("policy", "?")).replace("duel_gru_", "")
                                                               if "Bobby" in str(e.get("who")) else "Nightmare")]
                    for w, v in (e.get("weapons") or {}).items():
                        A_.shots[w] += v.get("S", 0)
                        A_.hits[w] += v.get("H", 0)
            rows = [r for r in csv.DictReader(io.StringIO(fr)) if r.get("t") not in (None, "", "t")]   # (a header can repeat)
            if not rows:
                continue

            def g(k, R=rows):
                out = np.zeros(len(R))
                for i_, r in enumerate(R):
                    try:
                        out[i_] = float(r.get(k) or 0)
                    except ValueError:
                        pass
                return out
            if "seat" in rows[0]:                              # free-for-all (schema 4): a row per player and frame
                t, seat, bot = g("t"), g("seat").astype(int), g("bot").astype(int)
                win = windows(ev, (("match_start",), ("match_result",)))
                pos = np.stack([g("b_x"), g("b_y"), g("b_z")], 1)
                where = {(round(tt, 3), s): p for tt, s, p in zip(t, seat, pos)}
                foe = g("foe_seat").astype(int)
                foe_pos = np.array([where.get((round(tt, 3), fs), p) for tt, fs, p in zip(t, foe, pos)])
                allv = dict(vel=np.stack([g("b_vx"), g("b_vy"), g("b_vz")], 1), weapon=g("b_weapon").astype(int), fire=g("b_fire") > 0,
                            up=g("b_up"), sees=g("b_sees") > 0, aim=g("b_aim_err"), hp=g("b_health"))
                keep = in_windows(t, win) if games_only else np.ones(len(t), bool)
                dur = sum(b - a for a, b in win) if games_only else (t.max() - t.min())
                for s, isbot in sorted(set(zip(seat.tolist(), bot.tolist()))):   # a seat can change hands (a bot in warmup, then a person)
                    m = (seat == s) & (bot == isbot) & keep
                    if m.sum() < 400:
                        continue
                    grp = pol if isbot else "people"
                    A = G[grp]
                    A.sessions.add(name)
                    A.frames(t[m], pos[m], allv["vel"][m], allv["weapon"][m], allv["fire"][m], allv["up"][m], allv["sees"][m],
                             allv["aim"][m], foe_pos[m], allv["hp"][m] > 0)
                    t0, t1 = t[m].min(), t[m].max()
                    mine = [e for e in ev if e.get("seat") == s and bool(e.get("bot")) == bool(isbot) and t0 <= e.get("t", 0) <= t1 and (not games_only or any(a <= e["t"] <= b for a, b in win))]
                    life0 = t0
                    got = False
                    for e in mine:
                        if e.get("event") == "pickup" and e.get("item") in ITEM:
                            A.items[ITEM[e["item"]]] += 1
                            if ITEM[e["item"]] in ("rl", "rg", "lg") and not got:
                                got = True
                                A.first_wp.append(e["t"] - life0)
                        elif e.get("event") == "death":
                            A.n["deaths"] += 1
                            A.n["lives"] += 1
                            life0, got = e["t"], False
                    for k in ("mega", "red"):
                        n_k = sum(1 for e in mine if e.get("event") == "pickup" and ITEM.get(e.get("item")) == k)
                        A.spawn_share[k][0] += n_k
                        A.spawn_share[k][1] += max(1.0, (t1 - t0) / RESPAWN[k])
                for e in ev:                                   # the game's own table at the end of a game
                    if e.get("event") == "match_result":
                        for r in e.get("table", []):
                            A = G[pol if r.get("bot") else "people"]
                            A.n["kills"] += r.get("kills", 0)
                            A.n["dmg_dealt"] += r.get("dmg_dealt", 0)
            else:                                              # 1v1 (schemas 1 to 3): Bobby = b_, the other one = o_
                other = "Nightmare" if name.endswith("_spar") else "people"
                t = g("t")
                win = windows(ev, (("arena_start",), ("arena_result",)))
                keep = in_windows(t, win) if games_only else np.ones(len(t), bool)
                if keep.sum() < 400:
                    continue
                P = {}
                for pre in ("b_", "o_"):
                    P[pre] = dict(pos=np.stack([g(pre + "x"), g(pre + "y"), g(pre + "z")], 1), vel=np.stack([g(pre + "vx"), g(pre + "vy"), g(pre + "vz")], 1),
                                  weapon=g(pre + "weapon").astype(int), fire=g(pre + "fire") > 0, up=g(pre + "up"), hp=g(pre + "health"),
                                  aim=g(pre + "aim_err"), sees=(g("b_sees") > 0) if pre == "b_" else (g("los") > 0))
                for pre, grp, who in (("b_", pol, "bobby"), ("o_", other, "opp")):
                    A, p, q = G[grp], P[pre], P["o_" if pre == "b_" else "b_"]
                    A.sessions.add(name)
                    A.frames(t[keep], p["pos"][keep], p["vel"][keep], p["weapon"][keep], p["fire"][keep], p["up"][keep], p["sees"][keep],
                             p["aim"][keep], q["pos"][keep], p["hp"][keep] > 0)
                    t0, t1 = t[keep].min(), t[keep].max()
                    mine = [e for e in ev if t0 <= e.get("t", 0) <= t1 and (not games_only or any(a <= e["t"] <= b for a, b in win))]
                    life0, got = t0, False
                    for e in mine:
                        k = e.get("event")
                        if k == "pickup" and e.get("by") == who and e.get("item") in ITEM:
                            A.items[ITEM[e["item"]]] += 1
                            if ITEM[e["item"]] in ("rl", "rg", "lg") and not got:
                                got = True
                                A.first_wp.append(e["t"] - life0)
                        elif k == "death":
                            if e.get("who") == who:
                                A.n["deaths"] += 1
                                A.n["lives"] += 1
                                life0, got = e["t"], False
                            else:
                                A.n["kills"] += 1
                        elif k == "hit" and e.get("victim") != who:
                            A.n["dmg_dealt"] += e.get("dmg", 0)
                            A.dmg_w[WNAME.get(int(e.get("attacker_weapon", 0)), "?")] += e.get("dmg", 0)
                    for k_ in ("mega", "red"):
                        n_k = sum(1 for e in mine if e.get("event") == "pickup" and e.get("by") == who and ITEM.get(e.get("item")) == k_)
                        A.spawn_share[k_][0] += n_k
                        A.spawn_share[k_][1] += max(1.0, (t1 - t0) / RESPAWN[k_])
    return {k: card(a) for k, a in G.items() if a.n["frames"] > 2400}       # (ten minutes of frames at least)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--games", action="store_true", help="only real games (a scored duel or an F3 game), no warmup")
    ap.add_argument("--json", default="")
    ap.add_argument("--only", default="", help="groups to print, by a part of their name: people,Nightmare,v10")
    a = ap.parse_args()
    paths = a.paths or [p for p in (os.path.join(ROOT, "data", d, "sessions") for d in ("duellive", "labtest", "bench1", "bench2")) if os.path.isdir(p)] + \
        (["T:/quake-sessions/public"] if os.path.isdir("T:/quake-sessions/public") else [])
    C = run(paths, a.games)
    order = sorted(C, key=lambda k: (k != "people", k != "Nightmare", k))
    if a.only:
        order = [k for k in order if any(k == "Bobby " + o or k == o or (o in k and not k.startswith("Bobby")) for o in a.only.split(","))]
    rows = [("sessions, minutes", lambda c: "{}, {}".format(c.get("sessions"), c.get("minutes"))),
            ("frags : deaths a minute", lambda c: "{} : {}".format(c.get("frags_per_min"), c.get("deaths_per_min"))),
            ("damage for a kill", lambda c: c.get("damage_per_kill", "-")),
            ("mega, red a minute", lambda c: "{}, {}".format(c.get("mega_per_min"), c.get("red_per_min"))),
            ("share of mega, red spawns taken", lambda c: "{}, {}".format(c.get("mega_share_of_spawns", "-"), c.get("red_share_of_spawns", "-"))),
            ("big weapons a minute", lambda c: c.get("weapons_per_min")),
            ("first weapon after (s), lives with one", lambda c: "{}, {}".format(c.get("first_weapon_s", "-"), c.get("lives_with_a_weapon", "-"))),
            ("in hand", lambda c: " ".join("{} {:.0%}".format(k, v) for k, v in c.get("in_hand", {}).items())),
            ("fired", lambda c: " ".join("{} {:.0%}".format(k, v) for k, v in c.get("fired", {}).items())),
            ("damage by weapon (1v1)", lambda c: " ".join("{} {:.0%}".format(k, v) for k, v in (c.get("damage_by_weapon") or {}).items()) or "-"),
            ("accuracy, the game's own count", lambda c: " ".join("{} {:.0%}".format(k[:6], v) for k, v in (c.get("accuracy") or {}).items()) or "-"),
            ("speed, share above 330, jumping", lambda c: "{}, {}, {}".format(c.get("speed"), c.get("fast_share"), c.get("jump_share"))),
            ("enemy in view, firing", lambda c: "{}, {}".format(c.get("enemy_in_view"), c.get("firing_share"))),
            ("aim error in view / firing (deg)", lambda c: "{} / {}".format(c.get("aim_error_in_view", "-"), c.get("aim_error_firing", "-"))),
            ("on target (within 3 deg)", lambda c: c.get("on_target_share")),
            ("on him after (s)", lambda c: c.get("settle_s", "-"))]
    print("player cards{}: {}".format(" (real games only)" if a.games else " (all play, warmup included)", ", ".join(order)))
    for label, fn in rows:
        print("  {:38s} | ".format(label) + " | ".join("{:>34s}".format(str(fn(C[k]))[:34]) for k in order))
    print("  fired, by distance to the enemy:")
    for b in BIN_NAMES:
        print("    {:36s} | ".format(b) + " | ".join("{:>34s}".format(" ".join("{} {:.0%}".format(k, v) for k, v in list(C[g].get("fired_by_distance", {}).get(b, {}).items())[:4])[:34] or "-") for g in order))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(dict(games_only=a.games, groups=C), f, indent=1)
        print("->", a.json)


if __name__ == "__main__":
    main()
