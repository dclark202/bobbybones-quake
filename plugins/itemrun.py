"""itemrun: item control on campgrounds duel - RA, YA and Mega, picked up the moment they spawn.

The bot plans routes on a navigation graph built from recorded bot movement
(/tmp/practice/nav_campgrounds.json), follows them (strafe-jumping on straight level
stretches), and times its arrival to each item's exact spawn using the server's item timers.
Every pickup is logged with its timing error. Per-frame telemetry goes to
/tmp/practice/itemrun_frames.jsonl for rendering videos.

  !ir start <bot> <idle_bot> [lookahead] [hop_straight]   !ir stop   !ir status
"""
import heapq
import json
import math
import os
import random

import minqlx

LOGDIR = "/tmp/practice"
def nav_path(mapname):
    """nav graph for a map: freshly learned copy in the data dir wins, otherwise the one shipped in the image"""
    for f in (os.path.join(LOGDIR, "nav_{}.json".format(mapname)), "/ql/maps-data/{}/nav.json".format(mapname)):
        if os.path.exists(f):
            return f
    return None
PARK = (-768.0, 320.0, 40.0)
RUN = 320.0
FRAME = 0.025
# QL weapon ids (ammo field names from minqlx)
WEAPONS = {1: "g", 2: "mg", 3: "sg", 4: "gl", 5: "rl", 6: "lg", 7: "rg", 8: "pg", 11: "ng", 13: "cg", 14: "hmg"}
PROJECTILE_SPEED = {4: 700.0, 5: 1000.0, 8: 2000.0, 11: 1000.0}   # grenades, rockets, plasma, nails
GRAVITY = 800.0
# fighting: winning = frags. Items are a means. Engage when healthy, hold the weapon's best range.
PREF_RANGE = {6: 380.0, 5: 350.0, 7: 900.0, 3: 180.0, 8: 300.0, 2: 500.0, 14: 500.0, 13: 400.0, 4: 400.0, 11: 350.0}
ENGAGE_STACK = 80          # health + armor needed to choose a fight; below it, go get stuff
ARMED_WITH = ("rl", "lg", "rg", "pg", "sg")   # a real weapon is needed to choose a fight (not just the MG)
SPRAY = {2, 6, 13, 14}                          # held-trigger tracking weapons: MG, LG, CG, HMG
# accuracy targets (tunable live: e.g. "bobby_acc_lg 0.45" in the server console); aim self-tunes toward them
ACC_TARGET_CVARS = {6: ("bobby_acc_lg", 0.40), 7: ("bobby_acc_rg", 0.65), 5: ("bobby_acc_rl", 0.70),
                    8: ("bobby_acc_pg", 0.35), 3: ("bobby_acc_sg", 0.50), 14: ("bobby_acc_hmg", 0.40)}
# "flex": once we've measured the opponent's own accuracy with a weapon, aim for theirs + FLEX_MARGIN
FLEX_MARGIN = 0.05
FLEX_MIN_SHOTS = 40
ACC_CAP = {6: 0.60, 7: 0.80, 5: 0.85, 8: 0.50, 3: 0.65, 14: 0.55}
ACC_FLOOR = 0.15
POLICY = os.path.join(LOGDIR, "weapon_policy.json")
RESPAWN = {"RA": 25000, "YA": 25000, "MH": 35000, "RL": 5000, "LG": 5000, "RG": 5000}
TRAINING = os.environ.get("LAB_MODE") == "train"
# diagnostic split: full = our movement + our aim; aimonly = AI movement + our aim; moveonly = our movement + AI aim
VARIANT = os.environ.get("LAB_VARIANT", "full")
EXPLORE = 0.2 if TRAINING else 0.0        # chance per engagement to try a different weapon
MOVE_EXPLORE = 0.2 if TRAINING else 0.0   # chance per trip to try a different route/movement style
MOVE_POLICY = os.path.join(LOGDIR, "movement_policy.json")
STYLE_CHOICES = dict(lookahead=[80.0, 110.0, 150.0, 200.0], hop_straight=[200.0, 300.0, 350.0, 500.0, 99999.0],
                     noise=[0.0, 0.0, 0.3, 0.6])
DEFAULT_STYLE = dict(lookahead=110.0, hop_straight=350.0, noise=0.0, seed=0)
# fair mode: hearing radii (units) and aim error (1-sigma, units at the target)
HEAR_STEPS, HEAR_JUMP, HEAR_FIRE, HEAR_ITEM, SEE_ITEM = 700, 900, 1500, 1000, 600
# aim model: crosshair pursues the target like a hand on a mouse (gain per frame, max deg/s),
# plus a slow, small drift (units at the target). Misses come mostly from the target changing direction.
AIM_GAIN = {6: 0.7, 7: 0.55, 5: 0.45, 8: 0.45, 3: 0.5, 2: 0.5, 4: 0.4, 11: 0.45, 13: 0.5, 14: 0.5, 1: 0.6}
AIM_MAX_DPS = 720.0
AIM_DRIFT = {6: 2.5, 7: 9.0, 5: 14.0, 8: 12.0, 3: 12.0, 2: 6.0, 4: 20.0, 11: 12.0, 13: 6.0, 14: 6.0, 1: 4.0}
ITEMS = {"RA": "item_armor_body", "YA": "item_armor_combat", "MH": "item_health_mega",
         "RL": "weapon_rocketlauncher", "LG": "weapon_lightning", "RG": "weapon_railgun"}
VALUE = {"RA": 3, "MH": 2, "YA": 1, "RL": 5, "LG": 4, "RG": 4}   # weapons only count while he lacks them
WEAPON_ITEM = {"RL": "rl", "LG": "lg", "RG": "rg"}
# classname -> (label, kind, amount or weapon, respawn ms). Every health/armor/ammo/weapon item counts.
ITEM_KINDS = {
    "item_health_small": ("h5", "hp", 5, 35000), "item_health": ("h25", "hp", 25, 35000),
    "item_health_large": ("h50", "hp", 50, 35000), "item_health_mega": ("MH", "mega", 100, 35000),
    "item_armor_shard": ("sh", "ar", 5, 25000), "item_armor_jacket": ("GA", "ar", 25, 25000),
    "item_armor_combat": ("YA", "ar", 50, 25000), "item_armor_body": ("RA", "ar", 100, 25000),
    "weapon_shotgun": ("SG", "wp", "sg", 5000), "weapon_grenadelauncher": ("GL", "wp", "gl", 5000),
    "weapon_rocketlauncher": ("RL", "wp", "rl", 5000), "weapon_lightning": ("LG", "wp", "lg", 5000),
    "weapon_railgun": ("RG", "wp", "rg", 5000), "weapon_plasmagun": ("PG", "wp", "pg", 5000),
    "weapon_hmg": ("HMG", "wp", "hmg", 5000), "weapon_nailgun": ("NG", "wp", "ng", 5000),
    "weapon_chaingun": ("CG", "wp", "cg", 5000),
    "ammo_bullets": ("am", "ammo", "mg", 40000), "ammo_shells": ("am", "ammo", "sg", 40000),
    "ammo_grenades": ("am", "ammo", "gl", 40000), "ammo_rockets": ("am", "ammo", "rl", 40000),
    "ammo_lightning": ("am", "ammo", "lg", 40000), "ammo_slugs": ("am", "ammo", "rg", 40000),
    "ammo_cells": ("am", "ammo", "pg", 40000), "ammo_hmg": ("am", "ammo", "hmg", 40000),
    "ammo_nails": ("am", "ammo", "ng", 40000), "ammo_belt": ("am", "ammo", "cg", 40000),
}
MAJOR = {"RA", "YA", "GA", "MH", "RL", "LG", "RG", "PG", "SG", "GL"}
LOW_AMMO = {"rl": 5, "lg": 50, "rg": 5, "pg": 30, "sg": 5, "mg": 30, "gl": 4, "hmg": 30, "ng": 10, "cg": 30}
# fight / stack / push. aggr shifts how readily he fights (+) or stacks (-); varied per round in training
AGGR_CHOICES = [-50, -25, 0, 25, 50]
DECISION_POLICY = os.path.join(LOGDIR, "decision_policy.json")
# routing arm (Nightmare base): who drives out-of-combat trips between major items, the AI or our routes
ROUTE_POLICY = os.path.join(LOGDIR, "route_policy.json")
ROUTE_EXPLORE = 0.25 if TRAINING else 0.0


def time_now():
    import time
    return round(time.time(), 1)


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


class Nav:
    def __init__(self, path):
        g = json.load(open(path))
        self.nodes = [tuple(n) for n in g["nodes"]]
        self.cells = g.get("cells")
        self.adj = [[] for _ in self.nodes]
        have = set()
        for a, b, t, kind in g["edges"]:
            d = math.dist(self.nodes[a], self.nodes[b])
            if kind == "tele":
                cost = 0.1                                 # walk into the teleporter
            else:
                cost = d / RUN if kind == "walk" else max(t, d / 900.0)
            self.adj[a].append((b, cost, kind))
            have.add((a, b))
        # walking on (nearly) flat ground works both ways
        for a, b, t, kind in g["edges"]:
            if kind == "walk" and (b, a) not in have and abs(self.nodes[a][2] - self.nodes[b][2]) < 18:
                self.adj[b].append((a, math.dist(self.nodes[a], self.nodes[b]) / RUN, "walk"))
                have.add((b, a))

    def nearest_k(self, x, y, z, k=8, maxdz=48):
        c = []
        for i, (nx, ny, nz) in enumerate(self.nodes):
            if abs(nz - z) <= maxdz:
                c.append((math.hypot(nx - x, ny - y), i))
        c.sort()
        return c[:k]

    def nearest(self, x, y, z, maxdz=48):
        best, bd = None, 1e9
        for i, (nx, ny, nz) in enumerate(self.nodes):
            if abs(nz - z) > maxdz:
                continue
            d = math.hypot(nx - x, ny - y)
            if d < bd:
                best, bd = i, d
        return best, bd

    def dists(self, a, banned=()):
        """single-source shortest times from node a to every node (one search for all items)"""
        dist, prev = {a: 0.0}, {}
        pq = [(0.0, a)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, 1e18):
                continue
            for v, c, kind in self.adj[u]:
                if (u, v) in banned:
                    continue
                nd = d + c
                if nd < dist.get(v, 1e18):
                    dist[v], prev[v] = nd, (u, kind)
                    heapq.heappush(pq, (nd, v))
        return dist, prev

    @staticmethod
    def path_to(prev, a, b):
        path, kinds, u = [b], [], b
        while u != a:
            u, kind = prev[u]
            path.append(u)
            kinds.append(kind)
        path.reverse()
        kinds.reverse()
        return list(zip(path, ["start"] + kinds))

    def route(self, a, b, banned=(), noise=0.0, seed=0):
        dist, prev = {a: 0.0}, {}
        pq = [(0.0, a)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == b:
                break
            if d > dist.get(u, 1e18):
                continue
            for v, c, kind in self.adj[u]:
                if (u, v) in banned:
                    continue
                if noise:
                    c *= 1.0 + noise * (((u * 73856093 ^ v * 19349663 ^ seed * 83492791) % 1000) / 500.0 - 1.0)
                nd = d + c
                if nd < dist.get(v, 1e18):
                    dist[v], prev[v] = nd, (u, kind)
                    heapq.heappush(pq, (nd, v))
        if b not in dist:
            return None, 1e9
        path, kinds, u = [b], [], b
        while u != a:
            u, kind = prev[u]
            path.append(u)
            kinds.append(kind)
        path.reverse()
        kinds.reverse()
        return list(zip(path, ["start"] + kinds)), dist[b]


class itemrun(minqlx.Plugin):
    def __init__(self):
        self.add_command("ir", self.cmd_ir, usage="start <bot> <idle> [lookahead] [hop_straight] | stop | status", permission=5)
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.running = False
        self.nav = None

    def on_map(self, mapname, factory):
        # map change: drop every input override so nothing touches stale game state
        for cid in range(64):
            try:
                minqlx.clear_bot_input(cid)
            except Exception:
                break
        self.trial = None if hasattr(self, "trial") else None
        if hasattr(self, "mode"):
            self.mode = None
        if hasattr(self, "running"):
            self.running = False

    def log(self, msg):
        line = "[itemrun] " + msg
        minqlx.console_print(line + "\n")
        with open(os.path.join(LOGDIR, "itemrun_events.log"), "a") as f:
            f.write(line + "\n")

    def cmd_ir(self, player, msg, channel):
        sub = msg[1] if len(msg) > 1 else "status"
        if sub == "start":
            # "auto" = first bot on the server; never drive a human client
            if msg[2] == "auto":
                bots = [p.id for p in self.players() if is_bot(p) and "Bobby" in p.clean_name.replace(" ", "")] or                        [p.id for p in self.players() if is_bot(p)]
                if not bots:
                    self.log("no bot on the server")
                    return
                self.bot = bots[0]
            else:
                self.bot = int(msg[2])
            self.idle = int(msg[3]) if len(msg) > 3 else -1
            if self.idle < 0:
                self.idle = None
            target = self.player(self.bot)
            if target is None or not is_bot(target):
                self.log("refusing: client {} is not a bot".format(self.bot))
                self.bot = None
                return
            self.lookahead = float(msg[4]) if len(msg) > 4 else 110.0
            self.hop_straight = float(msg[5]) if len(msg) > 5 else 350.0
            mapname = minqlx.get_cvar("mapname")
            nav = nav_path(mapname)
            if nav is None:
                self.log("no nav graph for {} yet - record bots on it first".format(mapname))
                self.bot = None
                return
            self.nav = Nav(nav)
            self.running = True
            self.hybrid = False
            self.aim_scale = getattr(self, "aim_scale", {})
            self.static_items, self.item_nodes, self.belief = None, None, None
            self.enemy_stack, self.mode, self.goal_score = 125, "fight", 0.0
            try:
                self.aggr = int(json.load(open(DECISION_POLICY)).get("aggr", 0))
            except Exception:
                self.aggr = 0
            if TRAINING:
                self.aggr = random.choice(AGGR_CHOICES)
            self.opp_acc = getattr(self, "opp_acc", {})       # steam id -> {weapon: [shots, hits]}
            self.opp_mem = {}
            self.load_policy()
            self.goal = None
            self.path = None
            self.pickups = []
            self.frame = 0
            self.speed_factor = 1.15   # learned: real travel time / planned time
            self.leg = None
            self.stuck = 0
            self.prev_avail = {}
            self.prev_vel_yaw = None
            self.last_z = None
            minqlx.set_cvar("timelimit", "0")
            minqlx.set_cvar("fraglimit", "0")
            self.log("item run started bot={} lookahead={} hop_straight={} nodes={}".format(
                self.bot, self.lookahead, self.hop_straight, len(self.nav.nodes)))
        elif sub == "policy":
            self.load_policy()                     # hot-reload the learned weapon table
        elif sub == "nav":
            nav = nav_path(minqlx.get_cvar("mapname"))
            if nav and getattr(self, "running", False):   # hot-reload the (re)learned route graph
                self.nav, self.path, self.banned = Nav(nav), None, set()
                self.log("nav reloaded: {} nodes".format(len(self.nav.nodes)))
        elif sub == "stop":
            self.running = False
            minqlx.clear_bot_input(self.bot)
            self.log("stopped")
        else:
            errs = [abs(p["error_ms"]) for p in getattr(self, "pickups", []) if p["error_ms"] is not None]
            self.log("pickups={} median_abs_error_ms={} speed_factor={:.2f}".format(
                len(self.pickups), sorted(errs)[len(errs) // 2] if errs else "-", getattr(self, "speed_factor", 0)))

    # ------------------------------------------------------------------
    def on_frame(self):
        if not self.running:
            return
        try:
            self.tick()
        except Exception as e:
            self.log("error: {!r}".format(e))
            self.path = None

    def item_table(self):
        level_time, items = minqlx.item_states()
        static = getattr(self, "static_items", None)
        tab = {}
        for num, cls, x, y, z, avail, nextthink in sorted(items):
            k = ITEM_KINDS.get(cls)
            if k is None:
                continue
            key = "{}@{}".format(k[0], num)
            if static is not None and key not in static:
                continue                                       # dropped weapons etc.: not map items
            tab[key] = dict(pos=(x, y, z), avail=bool(avail), spawn=level_time if avail else nextthink,
                            label=k[0], kind=k[1], amount=k[2], respawn=k[3])
        if static is None:
            self.static_items = set(tab)
        return level_time, tab

    def believe(self, now, truth, x, y, z):
        """Fair item timers: BobbyBones only learns an item's state by seeing it, or by hearing it
        get picked up / respawn. Everything else is his last belief."""
        bel = getattr(self, "belief", None)
        if bel is None:
            bel = self.belief = {k: dict(pos=v["pos"], spawn=now, avail=True) for k, v in truth.items()}
        for k, v in truth.items():
            bel.setdefault(k, dict(pos=v["pos"], spawn=now, avail=True))
        prev = getattr(self, "truth_prev", {})
        for k, v in truth.items():
            d = math.dist((x, y, z), v["pos"])
            was = prev.get(k)
            if d < SEE_ITEM:                                   # looking right at it
                if v["avail"]:
                    bel[k].update(avail=True, spawn=now)
                elif bel[k]["avail"]:
                    bel[k].update(avail=False, spawn=now + v["respawn"] // 2)   # gone, unknown when: guess
            if was is not None and was != v["avail"] and d < HEAR_ITEM:      # heard pickup / respawn
                bel[k].update(avail=v["avail"], spawn=v["spawn"])
            if not bel[k]["avail"] and now >= bel[k]["spawn"]:
                bel[k]["avail"] = True                         # by his own count it should be up
        self.truth_prev = {k: v["avail"] for k, v in truth.items()}
        out = {}
        for k, b in bel.items():
            if k in truth:
                out[k] = dict(truth[k], avail=b["avail"], spawn=now if b["avail"] else b["spawn"])
        return out

    def tick(self):
        self.frame += 1
        if self.frame % 40 == 1:
            p = self.player(self.bot)
            if p is None or not is_bot(p):   # the slot now belongs to someone else: let go
                minqlx.clear_bot_input(self.bot)
                self.running = False
                self.log("client {} is no longer our bot - stopping".format(self.bot))
                return
            self.update_hybrid()
        self.park_idle()
        s = minqlx.player_state(self.bot)
        x, y, z = s.position
        vx, vy, vz = s.velocity
        speed = math.hypot(vx, vy)
        ground = abs(vz) < 1 and self.last_z is not None and abs(z - self.last_z) < 1
        self.last_z = z
        now, truth = self.item_table()
        self.now = now
        if s.health <= 0 and getattr(self, "trip_from", None) != "spawn":
            self.trip_from, self.trip_start, self.trip_fight = "spawn", now, 0     # died: new trip from spawn
        if getattr(self, "in_combat", False):
            self.trip_fight = getattr(self, "trip_fight", 0) + 25
        items = self.believe(now, truth, x, y, z) if getattr(self, "fair", True) else truth
        if self.hybrid:
            self.combat(x, y, z, now)

        # pickups: an item we were heading to just went from up -> taken while we're next to it
        if not hasattr(self, "spawned_at"):
            self.spawned_at = {}
        for key, it in truth.items():
            was = self.prev_avail.get(key)
            if it["avail"] and was is False:
                self.spawned_at[key] = now
            if was and not it["avail"] and math.dist((x, y, z), it["pos"]) >= 90 and \
                    math.dist((x, y, z), it["pos"]) < HEAR_ITEM and it["kind"] in ("hp", "mega", "ar"):
                self.enemy_stack = min(300, self.enemy_stack + it["amount"])   # heard them take it
            if was and not it["avail"] and math.dist((x, y, z), it["pos"]) < 90 and it["label"] in MAJOR:
                self.end_trip(now, key)
            if was and not it["avail"] and math.dist((x, y, z), it["pos"]) < 90:
                err = now - self.spawned_at[key] if key in self.spawned_at else None
                self.pickups.append(dict(item=key, t=now, error_ms=err, leg_s=self.leg_time(now)))
                if it["label"] in MAJOR:
                    self.log("picked {} at {:.1f}s, {} after spawn (leg {:.1f}s)".format(
                        key, now / 1000.0, "{} ms".format(err) if err is not None else "?", self.leg_time(now)))
                self.learn_speed(now)
                self.log_leg(now, key)
                self.last_item = key
                if not self.hybrid:
                    # solo item practice only: reset so he can keep collecting; never in a real fight
                    p = self.player(self.bot)
                    p.health = 100
                    p.armor = 0
                self.goal, self.path = None, None
            self.prev_avail[key] = it["avail"]

        # fight / stack / push decision, and the opponent as a "goal" when pushing
        if self.hybrid:
            self.decide(now)
            k = getattr(self, "known", None)
            if self.mode == "push" and k is not None:
                items["ENEMY"] = dict(pos=k["pos"], avail=True, spawn=now, label="ENEMY", kind="enemy", amount=0, respawn=0)

        # choose / re-evaluate the goal: what each item is worth to us right now, per second to get it
        if self.goal is None or self.goal not in items or now >= getattr(self, "reeval_at", 0):
            self.reeval_at = now + 1500
            best = self.best_goal(x, y, z, now, items)
            if best is None:
                self.input(0, 0, 0, 0.0)
                return
            score, key, route, cost = best
            cur = getattr(self, "goal_score", 0.0) if self.goal in items else 0.0
            if self.goal is None or self.goal not in items or (key != self.goal and score > cur * 1.4) or key == "ENEMY":
                if key != self.goal:
                    leg_key = "{}>{}".format(getattr(self, "last_item", "spawn"), key)
                    self.style = self.pick_style(leg_key)
                    self.lookahead, self.hop_straight = self.style["lookahead"], self.style["hop_straight"]
                    self.leg = dict(start=now, planned=cost, key=leg_key, stucks=0, fight_ms=0, arrive=None)
                    if items[key]["label"] in MAJOR or key == "ENEMY":
                        self.log("-> {} [{}] (planned {:.1f}s, spawns in {:.1f}s)".format(
                            key, self.mode, cost, (items[key]["spawn"] - now) / 1000.0))
                if key != self.goal:
                    self.pick_driver(key)
                self.goal, self.path, self.goal_score = key, route, score
                self.path_i = 0
                if self.style.get("noise") and key != "ENEMY":
                    styled, styled_cost = self.plan(x, y, z, items[key]["pos"], self.style)
                    if styled is not None:
                        self.path = styled

        it = items[self.goal]
        dist_item = math.hypot(it["pos"][0] - x, it["pos"][1] - y)
        if self.leg is not None:
            if self.leg["arrive"] is None and dist_item < 120 and abs(it["pos"][2] - z) < 80:
                self.leg["arrive"] = now
            if getattr(self, "in_combat", False):
                self.leg["fight_ms"] += 25
        time_to_spawn = (it["spawn"] - now) / 1000.0

        # replan if we left the path (fell off, got bumped)
        if self.path is None or self.off_path(x, y, z):
            self.path, _ = self.plan(x, y, z, it["pos"], getattr(self, "style", None))
            self.path_i = 0
            if self.path is None:
                self.input(0, 0, 0, 0.0)
                return

        # fight first: if we can see them and we're healthy enough, take the fight instead of the route
        if self.hybrid and self.engage(x, y, z, now):
            self.telemetry(now, x, y, z, speed, items, "fight")
            return

        # timing: if we'd arrive early, hold position short of the item
        remaining = self.remaining_cost(x, y, z) * self.speed_factor
        hold = time_to_spawn - remaining > 0.15 and dist_item < 260
        target, straight, next_air_up = self.lookahead_target(x, y, z)

        if hold:
            # wait about 70 units from the item, facing it; step on just in time
            yaw = math.degrees(math.atan2(it["pos"][1] - y, it["pos"][0] - x))
            if dist_item > 75 + 30:
                self.input(127, 0, 0, yaw)
            else:
                self.input(0, 0, 0, yaw)
            self.telemetry(now, x, y, z, speed, items, "wait")
            return

        aim_yaw = math.degrees(math.atan2(target[1] - y, target[0] - x))
        if next_air_up and ground:
            self.input(127, 0, 127, aim_yaw)
        elif straight and speed > 280:
            self.strafe(vx, vy, speed, aim_yaw, ground)
        else:
            self.input(127, 0, 0, aim_yaw)

        # progress watchdog: remaining route cost must keep dropping
        if not hasattr(self, "banned"):
            self.banned = set()
        if self.leg is not None:
            best = self.leg.get("best_remaining")
            if best is None or remaining < best - 0.3:
                self.leg["best_remaining"], self.leg["best_t"] = remaining, now
            elif now - self.leg["best_t"] > 3000 and self.path and self.path_i + 1 < len(self.path) and \
                    (VARIANT != "aimonly" or getattr(self, "driver", "ai") == "ours"):   # only judge our own driving
                e = (self.path[self.path_i][0], self.path[self.path_i + 1][0])
                self.banned.add(e)
                if self.leg is not None:
                    self.leg["stucks"] = self.leg.get("stucks", 0) + 1
                cells = getattr(self.nav, "cells", None)
                if cells:
                    with open(os.path.join(LOGDIR, "banned_moves.txt"), "a") as f:
                        f.write("{}>{}\n".format(",".join(map(str, cells[e[0]])), ",".join(map(str, cells[e[1]]))))
                self.log("stuck near {} -> banning edge {} and rerouting".format((round(x), round(y), round(z)), e))
                self.path, self.leg["best_remaining"] = None, None
                return
        # stuck detection
        self.stuck = self.stuck + 1 if speed < 40 else 0
        if self.stuck > 30:
            self.stuck = 0
            self.path = None
            self.input(127, 127, 127, aim_yaw + 90)
        self.telemetry(now, x, y, z, speed, items, self.goal)

    # ------------------------------------------------------------------
    def item_value(self, it, me):
        """what picking this up is worth to us right now (health/armor points, with meta bonuses)"""
        kind, amt = it["kind"], it["amount"]
        hp, ar = me.health, me.armor
        stack_w = 1.8 if getattr(self, "mode", "") == "stack" else 1.0
        if kind == "hp":
            return max(0, min(amt, (200 if amt <= 5 else 100) - hp)) * stack_w
        if kind == "mega":
            return max(0, min(100, 200 - hp)) * 1.2 * stack_w + 25          # +deny
        if kind == "ar":
            deny = 35 if amt >= 100 else (15 if amt >= 50 else 0)
            return max(0, min(amt, 200 - ar)) * 1.3 * stack_w + deny
        if kind == "wp":
            return 0 if getattr(me.weapons, amt, False) else 60
        if kind == "ammo":
            if not getattr(me.weapons, amt, False):
                return 0
            return 20 if getattr(me.ammo, amt, 0) < LOW_AMMO.get(amt, 10) else 1
        if kind == "enemy":
            return 300 if getattr(self, "mode", "") == "push" else 0
        return 0

    def best_goal(self, x, y, z, now, items):
        me = minqlx.player_state(self.bot)
        node_of = getattr(self, "item_nodes", None)
        if node_of is None:
            node_of = self.item_nodes = {}
        for banned in (getattr(self, "banned", set()), set()):
            for da, a in self.nav.nearest_k(x, y, z):
                if da > 250:
                    break
                dist, prev = self.nav.dists(a, banned)
                if len(dist) < 20:
                    continue                                   # dead-end start cell, try the next
                best = None
                for key, it in items.items():
                    v = self.item_value(it, me)
                    if v <= 0:
                        continue
                    if key == "ENEMY":
                        b, db = self.nav.nearest(*it["pos"], maxdz=64)
                    else:
                        if key not in node_of:
                            node_of[key] = self.nav.nearest(*it["pos"], maxdz=64)
                        b, db = node_of[key]
                    if b is None or b not in dist:
                        continue
                    eta = (dist[b] + (da + db) / RUN) * self.speed_factor
                    wait = max(0.0, (it["spawn"] - now) / 1000.0 - eta)
                    score = v / (eta + wait + 0.5)
                    if best is None or score > best[0]:
                        best = (score, key, b, eta)
                if best is not None:
                    score, key, b, eta = best
                    return score, key, self.nav.path_to(prev, a, b), eta
        return None

    def decide(self, now):
        """fight when armed and not behind, stack when behind, push when clearly ahead.
        The opponent's stack is estimated only from fair info: what we heard/saw them pick up,
        damage we dealt, and their deaths (kill feed)."""
        me = minqlx.player_state(self.bot)
        my = me.health + me.armor
        dt = (now - getattr(self, "est_t", now)) / 1000.0
        self.est_t = now
        if self.enemy_stack > 100:
            self.enemy_stack = max(100, self.enemy_stack - dt)  # stack above 100 decays like the game does
        p, st = self.human()
        if p is not None and st is not None and st.health <= 0:
            self.enemy_stack = 125                            # they died (kill feed): fresh spawn
        armed = any(getattr(me.weapons, n, False) and getattr(me.ammo, n, 0) > 0 for n in ARMED_WITH)
        k = getattr(self, "known", None)
        fresh = k is not None and now - k["t"] < 6000
        a = getattr(self, "aggr", 0)
        if armed and fresh and my - self.enemy_stack > 75 - a:
            mode = "push"
        elif armed and my >= max(70, self.enemy_stack - 25 - a):
            mode = "fight"
        else:
            mode = "stack"
        if mode != getattr(self, "mode", None):
            self.reeval_at = 0                                 # re-plan right away on a mode change
        self.mode = mode

    def new_round(self):
        """training: try a different aggression level each scored round"""
        if TRAINING:
            self.aggr = random.choice(AGGR_CHOICES)

    def plan(self, x, y, z, item_pos, style=None):
        b, db = self.nav.nearest(*item_pos, maxdz=64)
        if b is None:
            return None, 1e9
        tail = math.hypot(item_pos[0] - self.nav.nodes[b][0], item_pos[1] - self.nav.nodes[b][1]) / RUN
        for banned in (getattr(self, "banned", set()), set()):
            # try the nearest few start nodes: some cells are dead ends in the recorded graph
            for da, a in self.nav.nearest_k(x, y, z):
                if da > 250:
                    break
                st_ = style or {}
                route, cost = self.nav.route(a, b, banned, st_.get("noise", 0.0), st_.get("seed", 0))
                if route is not None:
                    if banned is not getattr(self, "banned", None):
                        self.banned = set()   # had to forgive bans to find a way
                    return route, cost + da / RUN + tail
        return None, 1e9

    def advance(self, x, y, z):
        # move path_i to the closest node ahead of us
        best_i, best_d = self.path_i, 1e9
        for i in range(self.path_i, min(len(self.path), self.path_i + 12)):
            nx, ny, nz = self.nav.nodes[self.path[i][0]]
            d = math.hypot(nx - x, ny - y) + abs(nz - z) * 0.5
            if d < best_d:
                best_i, best_d = i, d
        self.path_i = best_i
        return best_d

    def off_path(self, x, y, z):
        d = self.advance(x, y, z)
        nz = self.nav.nodes[self.path[self.path_i][0]][2]
        return d > 160 or z < nz - 70

    def remaining_cost(self, x, y, z):
        c, px, py = 0.0, x, y
        for node, kind in self.path[self.path_i:]:
            nx, ny, nz = self.nav.nodes[node]
            c += 0.1 if kind == "tele" else math.hypot(nx - px, ny - py) / RUN
            px, py = nx, ny
        it_pos = None
        return c

    def lookahead_target(self, x, y, z):
        pts = [self.nav.nodes[n] for n, _ in self.path[self.path_i:]]
        kinds = [k for _, k in self.path[self.path_i:]]
        target = pts[-1]
        acc, px, py = 0.0, x, y
        next_air_up = False
        for i, (nx, ny, nz) in enumerate(pts):
            if kinds[i] == "tele" and i > 0:
                target = pts[i - 1]                        # run into the teleporter; we re-plan on arrival
                break
            if kinds[i] == "air" and i > 0:
                px0, py0, pz0 = pts[i - 1]
                gap = math.hypot(nx - px0, ny - py0)
                takeoff_dist = math.hypot(px0 - x, py0 - y) if i > 1 else 0.0
                is_jump = nz > pz0 + 20 or (gap > 70 and nz > pz0 - 40)
                if is_jump and acc + 0 < 70 and takeoff_dist < 40:
                    next_air_up = True
                    target = (nx, ny, nz)
                    break
            acc += math.hypot(nx - px, ny - py)
            px, py = nx, ny
            if acc >= self.lookahead or (kinds[i] == "air" and acc > 48):
                target = (nx, ny, nz)
                break
        # straight & level for hop_straight units ahead?
        straight = True
        acc, px, py = 0.0, x, y
        for i, (nx, ny, nz) in enumerate(pts):
            if abs(nz - z) > 12 or kinds[i] in ("air", "tele"):
                straight = False
                break
            acc += math.hypot(nx - px, ny - py)
            px, py = nx, ny
            if acc >= self.hop_straight:
                break
        if straight and acc >= self.hop_straight * 0.9:
            # deviation of the stretch from the straight line to its end
            ex, ey = px, py
            for nx, ny, nz in pts[:i + 1]:
                if seg_dev((nx, ny), (x, y), (ex, ey)) > 28:
                    straight = False
                    break
        else:
            straight = False
        return target, straight, next_air_up

    def strafe(self, vx, vy, speed, aim_yaw, ground):
        if self.hybrid:  # AI owns the view, so no air-strafing: hop toward the target, but not mid-fight
            self.input(127, 0, 127 if ground and not getattr(self, "in_combat", False) else 0, aim_yaw)
            return
        vel_yaw = math.degrees(math.atan2(vy, vx))
        side = -1 if wrap(aim_yaw - vel_yaw) > 0 else 1
        theta = math.degrees(math.acos(max(-1.0, min(1.0, (RUN - RUN * FRAME) / speed))))
        yaw = vel_yaw - side * theta + side * 45.0
        minqlx.set_bot_input(self.bot, 127, side * 127, 127 if ground else 0, 0, 0, 0.0, yaw)

    def input(self, fwd, right, up, yaw):
        if self.hybrid and VARIANT == "aimonly" and (getattr(self, "driver", "ai") != "ours" or getattr(self, "in_combat", False)):
            minqlx.set_bot_move(self.bot, 0.0, 0, -1.0)   # Nightmare drives; our aim still applies
            return
        if self.hybrid:
            now = getattr(self, "now", 0)
            if fwd == 0 and right == 0 and not getattr(self, "in_combat", False):
                # waiting for a spawn: shuffle side to side instead of standing still
                minqlx.set_bot_move(self.bot, float(yaw + (90 if (now // 500) % 2 else -90)), 0)
                return
            dyaw, hop = self.dodge_yaw(yaw, now)
            if dyaw is None:                               # planted: stand still, aim keeps running
                minqlx.set_bot_move(self.bot, float(yaw), 0, 0.0)
                return
            fighting = getattr(self, "in_combat", False)
            jump = hop or (up and not fighting)            # no route bunny-hops mid-fight
            minqlx.set_bot_move(self.bot, float(dyaw), 127 if jump else 0)
            return
        minqlx.set_bot_input(self.bot, int(fwd), int(right), int(up), 0, 0, 0.0, float(yaw))

    # ---------------- combat ----------------
    def pick_style(self, leg_key):
        """best known route/movement style for this trip; in training, sometimes try something new"""
        best = getattr(self, "move_policy", {}).get(leg_key)
        self.style_explored = False
        if best is not None and random.random() >= MOVE_EXPLORE:
            return dict(best)
        if MOVE_EXPLORE:
            self.style_explored = True
            st = {k: random.choice(v) for k, v in STYLE_CHOICES.items()}
            st["seed"] = random.randint(1, 10 ** 6)
            return st
        return dict(DEFAULT_STYLE)

    def pick_driver(self, goal):
        """Nightmare drives by default; our route takes the trip if it has proven faster for it (or to explore)"""
        trip = "{}>{}".format(getattr(self, "trip_from", "spawn"), goal)
        learned = getattr(self, "route_policy", {}).get(trip) == "ours"
        self.driver = "ours" if (learned or random.random() < ROUTE_EXPLORE) else "ai"
        self.driver_trip = trip

    def end_trip(self, now, picked):
        start = getattr(self, "trip_start", None)
        if start is not None:
            rec = dict(t=time_now(), key="{}>{}".format(getattr(self, "trip_from", "spawn"), picked),
                       secs=(now - start) / 1000.0, fight=getattr(self, "trip_fight", 0) / 1000.0,
                       driver=getattr(self, "driver", "ai") if getattr(self, "driver_trip", "").endswith(">" + picked) else "ai",
                       stucks=(self.leg or {}).get("stucks", 0))
            with open(os.path.join(LOGDIR, "trips.jsonl"), "a") as f:
                f.write(json.dumps(rec) + "\n")
        self.trip_from, self.trip_start, self.trip_fight = picked, now, 0
        self.driver = "ai"

    def log_leg(self, now, picked):
        leg = self.leg
        if leg is None:
            return
        rec = dict(t=time_now(), key=leg["key"], picked=picked, style=getattr(self, "style", DEFAULT_STYLE),
                   travel=((leg["arrive"] or now) - leg["start"]) / 1000.0, total=(now - leg["start"]) / 1000.0,
                   planned=round(leg["planned"], 2), stucks=leg.get("stucks", 0), fight=leg["fight_ms"] / 1000.0,
                   ok=picked == self.goal and leg.get("stucks", 0) == 0,
                   explored=getattr(self, "style_explored", False))
        with open(os.path.join(LOGDIR, "legs.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")

    def load_policy(self):
        try:
            self.route_policy = json.load(open(ROUTE_POLICY))   # {"RA@119>YA@96": "ours", ...}
        except Exception:
            self.route_policy = {}
        try:
            self.move_policy = json.load(open(MOVE_POLICY))   # {"RA>MH": style, ...} learned in training
            self.log("movement policy loaded: {} trips".format(len(self.move_policy)))
        except Exception:
            self.move_policy = {}
        try:
            self.policy = json.load(open(POLICY))   # {"<band>": weapon, ...} learned from the human
            self.log("weapon policy loaded: {} situations".format(len(self.policy)))
        except Exception:
            self.policy = None

    @staticmethod
    def band(dist, dz, enemy_air):
        return "{}|{}|{}".format(min(int(dist // 250), 6), "above" if dz > 64 else ("below" if dz < -64 else "level"),
                                 "air" if enemy_air else "ground")

    def choose_weapon(self, dist, dz, enemy_air, ammo):
        prefs = []
        b = self.band(dist, dz, enemy_air)
        self.cur_band = b
        if EXPLORE:
            ex = getattr(self, "explore", None)
            if ex is None or ex[0] != b or self.now - ex[2] > 4000:
                usable = [w for w, n in ammo.items() if n > 0 and w != 1]
                pick = random.choice(usable) if usable and random.random() < EXPLORE else None
                self.explore = ex = (b, pick, self.now)
            if ex[1] is not None and ammo.get(ex[1], 0) > 0:
                return ex[1]
        if self.policy and b in self.policy:
            prefs.append(int(self.policy[b]))
        # defaults until the learned table covers a situation
        if dist < 120:
            prefs += [3, 5, 6, 8, 13, 14]                  # point blank: shotgun
        elif dist < 700:
            prefs += [6, 5, 8, 3, 13, 14, 2]
        elif dz < -64 or (not enemy_air and dist < 1000):
            prefs += [5, 4, 7, 6, 14, 2]                   # they're below / grounded: rockets, grenades
        else:
            prefs += [7, 5, 14, 2]
        for w in prefs:
            if ammo.get(w, 0) > 0:
                return w
        return 2

    def human(self):
        """the opponent: whoever else is playing (a human on the public server, a bot in training)"""
        for p in self.players():
            if p.id != self.bot and p.team != "spectator":
                st = p.state
                if st and (st.is_alive or st.health > 0):
                    return p, st
        return None, None

    def senses(self, x, y, z, now, p, st):
        """What BobbyBones legitimately knows about the human: sight (the AI's own line-of-sight
        attack decision) or sound (steps, jumps, shots) within realistic ranges."""
        ex, ey, ez = st.position
        evx, evy, evz = st.velocity
        d = math.dist((x, y, z), (ex, ey, ez))
        if minqlx.ai_wants_fire(self.bot):
            self.last_seen = now
        visible = now - getattr(self, "last_seen", -1e9) < 150
        cmd = minqlx.last_usercmd(p.id)
        heard = False
        if math.hypot(evx, evy) > 250 and abs(evz) < 1 and d < HEAR_STEPS:
            heard = True                                   # footsteps
        if evz > 200 and getattr(self, "prev_evz", 0) < 50 and d < HEAR_JUMP:
            heard = True                                   # jump grunt
        if cmd[1] & 1 and d < HEAR_FIRE:
            heard = True                                   # weapon fire
        self.prev_evz = evz
        if visible:
            self.known = dict(pos=(ex, ey, ez), vel=(evx, evy, evz), t=now, exact=True)
        elif heard:
            self.known = dict(pos=(ex + random.gauss(0, 80), ey + random.gauss(0, 80), ez), vel=(0.0, 0.0, 0.0),
                              t=now, exact=False)
        return visible

    def combat(self, x, y, z, now):
        p, st = self.human()
        if p is None:
            minqlx.set_bot_aim(self.bot, 0.0, 0.0, -1)
            self.in_combat = False
            return
        visible = self.senses(x, y, z, now, p, st)
        k = getattr(self, "known", None)
        if k is None or now - k["t"] > 4000:
            minqlx.set_bot_aim(self.bot, 0.0, 0.0, -1)     # no idea where they are: AI does its own thing
            self.in_combat = False
            return
        self.tracking = now - getattr(self, "last_seen", -1e9) < 350
        # a new engagement (= reaction time again) only after losing sight for a full second; the AI
        # letting go of the trigger between shots (rocket refire etc.) is not losing sight
        if visible and now - getattr(self, "prev_seen", -1e9) > 1000:
            self.engage_start = now
            self.reaction = random.uniform(170, 260)       # ms before the first shot
        if visible:
            self.prev_seen = now
        self.was_visible = visible
        ex, ey, ez = k["pos"]
        evx, evy, evz = k["vel"]
        a = minqlx.player_state(self.bot).ammo
        ammo = {i: getattr(a, n, 0) for i, n in WEAPONS.items()}
        ammo[1] = 1                                        # gauntlet never runs out
        dist = math.dist((x, y, z), (ex, ey, ez))
        enemy_air = abs(evz) > 1
        w = self.choose_weapon(dist, ez - z, enemy_air, ammo)
        t = 0.05
        if w in PROJECTILE_SPEED:
            for _ in range(3):
                px, py, pz = ex + evx * t, ey + evy * t, ez + evz * t
                t = 0.05 + math.dist((x, y, z + 26), (px, py, pz)) / PROJECTILE_SPEED[w]
        tx, ty, tz = ex + evx * t, ey + evy * t, ez + evz * t
        if w == 5 and not enemy_air:
            tz -= 20                                       # rockets at the feet for splash
        if w == 4:
            tz += 0.5 * GRAVITY * (t - 0.05) ** 2          # grenades: aim above for the lob
        # human-like aim: small slow drift around the target point...
        scale = self.aim_scale.get(w, 1.0)                 # <1 tighter, >1 looser (self-tuned)
        drift = AIM_DRIFT.get(w, 10.0) * scale * (3.0 if not k["exact"] else 1.0)
        rho = 0.97                                         # ~0.8 s correlation at 40 Hz
        self.err_h = getattr(self, "err_h", 0.0) * rho + random.gauss(0, drift * math.sqrt(1 - rho * rho))
        self.err_v = getattr(self, "err_v", 0.0) * rho + random.gauss(0, drift * math.sqrt(1 - rho * rho))
        dx, dy, dz = tx - x, ty - y, tz - (z + 26)
        hd = math.hypot(dx, dy) or 1.0
        dx, dy = dx - dy / hd * self.err_h, dy + dx / hd * self.err_h
        dz += self.err_v
        want_yaw = math.degrees(math.atan2(dy, dx))
        want_pitch = -math.degrees(math.atan2(dz, math.hypot(dx, dy)))
        # ...and a crosshair that chases that point instead of snapping to it
        cy, cp = getattr(self, "cross_yaw", None), getattr(self, "cross_pitch", None)
        if cy is None or now - getattr(self, "cross_t", 0) > 1000:
            v = minqlx.view_angles(self.bot)
            cy, cp = v[1], v[0]                            # start from where the AI was looking
        gain = min(0.9, AIM_GAIN.get(w, 0.45) / math.sqrt(scale))
        step = AIM_MAX_DPS * 0.025
        dyaw, dpit = wrap(want_yaw - cy), want_pitch - cp
        cy += max(-step, min(step, dyaw * gain))
        cp += max(-step, min(step, dpit * gain))
        self.cross_yaw, self.cross_pitch, self.cross_t = cy, cp, now
        yaw, pitch = cy, cp
        settled = abs(wrap(want_yaw - cy)) < 2.5 and abs(want_pitch - cp) < 2.5
        allow = visible and now - getattr(self, "engage_start", now) >= getattr(self, "reaction", 200)
        if w in (3, 4, 5, 7, 8, 11):
            allow = allow and settled                      # aimed shots: fire once the flick lands
        fire_mode = 1 if allow else 0
        if w in SPRAY and allow and self.tracking:
            fire_mode = 2                                  # LG/MG/CG/HMG: track continuously, trigger held
        if VARIANT == "moveonly":
            minqlx.set_bot_aim(self.bot, 0.0, 0.0, -1)    # the built-in AI aims and picks weapons
        else:
            minqlx.set_bot_aim(self.bot, pitch, yaw, w, fire_mode)
        if visible:
            self.combat_until = now + 1200
        self.in_combat = now < getattr(self, "combat_until", 0)
        self.track_accuracy(now, w, p, st)

    def track_accuracy(self, now, w, p, st):
        """log BobbyBones' real accuracy per weapon: shots = ammo used, hits = damage taken by the human"""
        acc = getattr(self, "acc", None)
        if acc is None:
            acc = self.acc = {}
            self.prev_ammo, self.prev_hp, self.acc_log, self.last_shot = {}, None, now + 30000, {}
        me = minqlx.player_state(self.bot)
        cur = {i: getattr(me.ammo, n, 0) for i, n in WEAPONS.items() if i != 1}
        firing = bool(minqlx.last_usercmd(self.bot)[1] & 1) and me.health > 0
        for wp, n in cur.items():
            used = self.prev_ammo.get(wp, n) - n
            if 0 < used < 20 and firing and wp == me.weapon:
                a = acc.setdefault(wp, [0, 0])
                a[0] += used
                self.last_shot[wp] = now
                self.experience("shot", wp, used)
            self.prev_ammo[wp] = n
        self.track_opponent(now, p, st, me)
        hp = st.health + st.armor
        if self.prev_hp is not None and hp < self.prev_hp and st.health > 0:
            window = {4: 2500, 5: 1500, 8: 800, 11: 1500}.get(me.weapon, 100)
            if now - self.last_shot.get(me.weapon, -1e9) <= window:
                acc.setdefault(me.weapon, [0, 0])[1] += 1
                self.enemy_stack = max(0, self.enemy_stack - (self.prev_hp - hp))
                self.experience("dmg", me.weapon, self.prev_hp - hp)
        self.prev_hp = hp
        if now >= self.acc_log:
            self.acc_log = now + 30000
            self.tune_aim()
            names = {1: "G", 2: "MG", 3: "SG", 4: "GL", 5: "RL", 6: "LG", 7: "RG", 8: "PG", 11: "NG", 13: "CG", 14: "HMG"}
            parts = ["{} {:.0f}% ({}/{})".format(names.get(wp, wp), 100.0 * min(h, s_) / s_, min(h, s_), s_)
                     for wp, (s_, h) in sorted(acc.items()) if s_ > 0]
            if parts:
                self.log("accuracy: " + ", ".join(parts))

    def experience(self, kind, wp, n):
        """Bobby's own combat results per situation: shots fired and damage dealt (self-play learning)"""
        with open(os.path.join(LOGDIR, "experience.jsonl"), "a") as f:
            f.write(json.dumps(dict(t=time_now(), k=kind, band=getattr(self, "cur_band", "?"), w=wp, n=n)) + "\n")

    def track_opponent(self, now, p, st, me):
        """the opponent's own accuracy per weapon (keyed by steam id), used to set Bobby's targets"""
        opp = self.opp_acc.setdefault(str(p.steam_id), {})
        mem = self.opp_mem
        if mem.get("sid") != str(p.steam_id):
            mem.clear()
            mem["sid"] = str(p.steam_id)
        cur = {i: getattr(st.ammo, n, 0) for i, n in WEAPONS.items() if i != 1}
        prev = mem.get("ammo", cur)
        firing = bool(minqlx.last_usercmd(p.id)[1] & 1) and st.health > 0
        for wp, n in cur.items():
            used = prev.get(wp, n) - n
            if 0 < used < 20 and firing and wp == st.weapon:
                opp.setdefault(wp, [0, 0])[0] += used
                mem.setdefault("last_shot", {})[wp] = now
        mem["ammo"] = cur
        my_hp = me.health + me.armor
        if mem.get("my_hp") is not None and my_hp < mem["my_hp"] and me.health > 0:
            window = {4: 2500, 5: 1500, 8: 800, 11: 1500}.get(st.weapon, 100)
            if now - mem.get("last_shot", {}).get(st.weapon, -1e9) <= window:
                opp.setdefault(st.weapon, [0, 0])[1] += 1
        mem["my_hp"] = my_hp

    def target_for(self, wp):
        name, default = ACC_TARGET_CVARS[wp]
        try:
            target = float(minqlx.get_cvar(name) or default)
        except ValueError:
            target = default
        p, st = self.human()
        if p is not None:
            shots, hits = self.opp_acc.get(str(p.steam_id), {}).get(wp, (0, 0))
            if shots >= FLEX_MIN_SHOTS:
                theirs = min(hits, shots) / float(shots)
                target = max(ACC_FLOOR, min(ACC_CAP.get(wp, 0.6), theirs + FLEX_MARGIN))
        return target

    def tune_aim(self):
        """nudge each weapon's aim toward its accuracy target using the shots since the last step"""
        last = getattr(self, "acc_prev", {})
        for wp, (shots, hits) in self.acc.items():
            ps, ph = last.get(wp, (0, 0))
            ds, dh = shots - ps, hits - ph
            if wp not in ACC_TARGET_CVARS or ds < 30:
                continue
            target = self.target_for(wp)
            acc = min(dh, ds) / float(ds)
            old = self.aim_scale.get(wp, 1.0)
            self.aim_scale[wp] = max(0.2, min(3.0, old * math.exp(-2.0 * (target - acc))))
            self.log("aim tune w{}: {:.0f}% vs target {:.0f}% -> scale {:.2f}".format(wp, acc * 100, target * 100, self.aim_scale[wp]))
        self.acc_prev = {wp: tuple(v) for wp, v in self.acc.items()}

    def engage(self, x, y, z, now):
        """Fight movement: hold the current weapon's preferred range, circle-strafe, dodge.
        Returns False (keep running the item plan) when it's not a fight worth taking."""
        k = getattr(self, "known", None)
        if k is None or not k["exact"] or now - getattr(self, "last_seen", -1e9) > 1500:
            return False                                   # no fresh sight of them: items
        me = minqlx.player_state(self.bot)
        stack = me.health + me.armor
        ex, ey, ez = k["pos"]
        dist = math.hypot(ex - x, ey - y)
        armed = any(getattr(me.weapons, n, False) and getattr(me.ammo, n, 0) > 0 for n in ARMED_WITH)
        if dist > 250 and (stack < ENGAGE_STACK or not armed or getattr(self, "mode", "fight") == "stack"):
            return False                                   # behind, weak or only a machine gun: go stack up
        to_yaw = math.degrees(math.atan2(ey - y, ex - x))
        pref = PREF_RANGE.get(me.weapon, 400.0)
        if now >= getattr(self, "circle_next", 0):
            self.circle_side = random.choice((-1, 1))
            self.circle_next = now + random.uniform(600, 1600)
        if dist > pref * 1.3:
            base = to_yaw + self.circle_side * 25.0        # close in, slightly angled
        elif dist < pref * 0.7:
            base = to_yaw + 180.0 - self.circle_side * 25.0  # back off
        else:
            base = to_yaw + self.circle_side * 90.0        # circle-strafe at range
        self.in_combat = True
        self.input(127, 0, 0, base)                        # input() adds the unpredictable dodge on top
        self.engaged_ms = getattr(self, "engaged_ms", 0) + 25
        return True

    def dodge_yaw(self, yaw, now):
        """Fight movement: unpredictable ground strafing around the intended direction.
        Random strafe lengths, sometimes holding, stopping or reversing early; jumps are rare."""
        if not getattr(self, "in_combat", False):
            return yaw, False
        if now >= getattr(self, "dodge_next", 0):
            r = random.random()
            if r < 0.15:
                self.dodge_mode = "stop"                  # plant feet briefly (breaks rhythm, good for rail)
                dur = random.uniform(120, 250)
            elif r < 0.30:
                self.dodge_mode = "hold"                  # keep the same strafe longer than expected
                dur = random.uniform(400, 800)
            else:
                self.dodge_mode = "switch"
                self.dodge_side = -getattr(self, "dodge_side", 1)
                dur = random.uniform(150, 600)
            self.dodge_next = now + dur
            self.dodge_hop = random.random() < 0.06       # the odd jump, never a pattern
            self.dodge_angle = random.uniform(55, 95)
        if getattr(self, "dodge_mode", "") == "stop":
            return None, False
        hop, self.dodge_hop = self.dodge_hop, False
        return yaw + getattr(self, "dodge_side", 1) * self.dodge_angle, hop

    def update_hybrid(self):
        humans = [p for p in self.players() if p.id != self.bot and p.team != "spectator"]
        h = bool(humans)
        if h != getattr(self, "hybrid", None):
            self.log("hybrid combat mode {} ({} opponent(s))".format("ON" if h else "OFF", len(humans)))
        self.hybrid = h

    def leg_time(self, now):
        return (now - self.leg["start"]) / 1000.0 if self.leg else 0.0

    def learn_speed(self, now):
        if not self.leg or self.leg["planned"] <= 0.5:
            return
        # only learn from legs where we didn't wait
        actual = self.leg_time(now)
        ratio = actual / self.leg["planned"]
        if 0.7 < ratio < 1.6:
            self.speed_factor = 0.8 * self.speed_factor + 0.2 * ratio

    def park_idle(self):
        if self.idle is None:
            return
        minqlx.set_bot_input(self.idle, 0, 0, 0, 0, 0, 0.0, 0.0)
        ip = self.player(self.idle)
        if ip and ip.state and math.hypot(ip.state.position[0] - PARK[0], ip.state.position[1] - PARK[1]) > 50:
            ip.position(x=PARK[0], y=PARK[1], z=PARK[2])
            ip.velocity(reset=True)

    def telemetry(self, now, x, y, z, speed, items, state):
        if TRAINING:
            return                                         # trainers don't need per-frame video telemetry
        rec = dict(t=now, x=round(x), y=round(y), z=round(z), v=round(speed), s=state,
                   it={k: (v["avail"], round((v["spawn"] - now) / 1000.0, 2)) for k, v in items.items()})
        with open(os.path.join(LOGDIR, "itemrun_frames.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")


def seg_dev(p, a, b):
    ax, ay, bx, by, px, py = a[0], a[1], b[0], b[1], p[0], p[1]
    l2 = (bx - ax) ** 2 + (by - ay) ** 2
    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l2)) if l2 else 0.0
    return math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay)))
