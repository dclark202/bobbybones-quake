"""practice: a bot practices movement skills on campgrounds by trial and error.

Each skill ("task") has a parameter space, a setup (teleport + loadout), a per-frame controller and a
score. A cross-entropy-method optimizer per task proposes parameters; a scheduler rotates through
tasks so every skill keeps improving over a long unattended session. Results go to /tmp/practice/.

Commands (console: qlx !pr ...):
  !pr start <bot> <idle_bot> [task,task,...]   rotate through tasks (default: all enabled)
  !pr stop | !pr status | !pr replay <task>
  !pr survey <x0> <x1> <y0> <y1> <step> <ztop>  drop-probe heightmap survey -> /tmp/practice/survey.txt
"""
import json
import math
import os
import random

import minqlx

FRAME = 0.025
WISHSPEED = 320.0
LOGDIR = "/tmp/practice"
PARK = (-768.0, 320.0, 40.0)
BUTTON_ATTACK = 1
WP_RL = 5

RAIL_LEDGE = [(497, -242), (497, -225), (470, -210), (488, -210), (466, -203), (481, -201), (463, -196),
              (456, -182), (468, -181), (448, -163), (458, -150), (447, -148), (458, -143), (447, -128),
              (447, -112), (447, -96), (447, -80), (448, -59), (448, -41), (448, -24), (449, -17),
              (450, -1), (450, 15), (450, 31), (449, 47), (439, 50), (448, 62), (447, 78), (449, 88),
              (450, 106), (441, 126), (435, 157), (427, 188), (417, 210), (403, 227), (385, 250)]


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def near(pts, x, y):
    return min(math.hypot(px - x, py - y) for px, py in pts)


def strafe_inputs(st, f, target, bias, lead):
    """Strafe-jump toward target (x, y). Returns (fwd, right, up, yaw)."""
    x, y = f["x"], f["y"]
    aim_yaw = math.degrees(math.atan2(target[1] - y, target[0] - x))
    speed = f["speed"]
    if speed < 250:
        up = 127 if f["ground"] and st["frame"] >= st.get("first_jump", 0) else 0
        return 127, 0, up, aim_yaw
    vel_yaw = math.degrees(math.atan2(f["vy"], f["vx"]))
    prev = st.get("prev_vel_yaw", vel_yaw)
    st["prev_vel_yaw"] = vel_yaw
    vel_yaw += wrap(vel_yaw - prev) * lead
    side = -1 if wrap(aim_yaw - vel_yaw) > 0 else 1
    theta = math.degrees(math.acos(max(-1.0, min(1.0, (WISHSPEED - WISHSPEED * FRAME) / speed))))
    theta = max(0.0, theta + bias)
    yaw = vel_yaw - side * theta + side * 45.0
    return 127, side * 127, 127 if f["ground"] else 0, yaw


# ----------------------------------------------------------------------------------------------
# Tasks
# ----------------------------------------------------------------------------------------------
class Task:
    name = "task"
    space = {}
    pop = 16
    n_elite = 4
    max_frames = 40 * 8
    enabled = True

    def setup(self, lab, p):
        raise NotImplementedError

    def step(self, lab, st, f):
        """Return None to continue, or (success, score, why)."""
        raise NotImplementedError


class BridgeRail(Task):
    """Strafe-jump from the bridge across the gap onto the rail ledge."""
    name = "bridge_rail"
    space = {
        "start_x": (-250.0, 560.0), "start_y": (-1010.0, -830.0),
        "way_x": (150.0, 640.0), "way_y": (-1010.0, -800.0), "way_r": (40.0, 220.0),
        "aim_x": (420.0, 520.0), "aim_y": (-260.0, -100.0),
        "bias": (-12.0, 12.0), "first_jump": (0.0, 12.0), "lead": (0.0, 2.0),
    }

    def setup(self, lab, p):
        lab.teleport(p["start_x"], p["start_y"], 545)
        yaw = math.degrees(math.atan2(p["way_y"] - p["start_y"], p["way_x"] - p["start_x"]))
        return dict(stage=0, yaw=yaw, best=-1e9, first_jump=p["first_jump"])

    def step(self, lab, st, f):
        p = st["params"]
        if f["z"] >= 525:
            # progress: closeness to the ledge's walkable strip while still high enough to land on it
            st["best"] = max(st["best"], -near(RAIL_LEDGE, f["x"], f["y"]))
        if f["ground"] and f["z"] >= 520 and f["y"] > -260 and near(RAIL_LEDGE, f["x"], f["y"]) < 40:
            return True, 1000 + st["best"], "landed on rail ledge"
        if f["z"] < 400:
            return False, st["best"], "fell"
        if st["frame"] > self.max_frames:
            return False, st["best"], "timeout"
        if st["stage"] == 0 and math.hypot(p["way_x"] - f["x"], p["way_y"] - f["y"]) < p["way_r"]:
            st["stage"] = 1
        tgt = (p["way_x"], p["way_y"]) if st["stage"] == 0 else (p["aim_x"], p["aim_y"])
        lab.input(*strafe_inputs(st, f, tgt, p["bias"], p["lead"]))


class RocketJumpHigh(Task):
    """Rocket jump for maximum height on flat ground."""
    name = "rj_high"
    space = {
        "pitch": (45.0, 89.0),        # degrees looking down
        "jump_frame": (0.0, 6.0),     # frame (after ready) to press jump
        "fire_frame": (0.0, 6.0),     # frame (after ready) to press fire
        "fwd": (-127.0, 127.0),       # forward input during the jump
    }
    max_frames = 40 * 4
    START = (-576.0, -330.0, 40.0)    # open ground floor near quad

    def setup(self, lab, p):
        lab.teleport(*self.START)
        lab.loadout(rl=True)
        return dict(z0=None, zmax=-1e9, air=False, hp0=None)

    def step(self, lab, st, f):
        p = st["params"]
        if st["z0"] is None:
            st["z0"], st["hp0"], st["r0"] = f["z"], f["health"], f["rockets"]
        st["zmax"] = max(st["zmax"], f["z"])
        k = st["frame"]
        if not f["ground"]:
            st["air"] = True
        if st["air"] and f["ground"] and k > 10:
            gain = st["zmax"] - st["z0"]
            dist = math.hypot(f["x"] - self.START[0], f["y"] - self.START[1])
            return gain > 150, gain, "height {:.0f} dist {:.0f} hp_cost {} rockets {} wp {}".format(
                gain, dist, st["hp0"] - f["health"], st["r0"] - f["rockets"], f["weapon"])
        if k > self.max_frames:
            return False, st["zmax"] - st["z0"], "timeout"
        up = 127 if abs(k - p["jump_frame"]) < 1 else 0
        fire = BUTTON_ATTACK if 0 <= k - p["fire_frame"] < 3 else 0
        lab.input(int(p["fwd"]) if k >= min(p["jump_frame"], p["fire_frame"]) else 0, 0, up, fire, WP_RL,
                  p["pitch"], st["yaw"])


class RocketJumpFar(RocketJumpHigh):
    """Rocket jump for maximum horizontal distance (run-up, then jump + rocket behind you)."""
    name = "rj_far"
    space = {
        "pitch": (30.0, 89.0),
        "runup": (0.0, 30.0),         # frames of running before the jump
        "jump_frame": (0.0, 4.0),     # relative to end of run-up
        "fire_frame": (0.0, 4.0),
        "strafe": (-127.0, 127.0),
    }
    START = (-576.0, -330.0, 40.0)

    def setup(self, lab, p):
        st = RocketJumpHigh.setup(self, lab, p)
        st["dir"] = random.choice([0.0])  # run toward +x along the ground floor
        return st

    def step(self, lab, st, f):
        p = st["params"]
        if st["z0"] is None:
            st["z0"], st["x0"], st["y0"], st["hp0"], st["r0"] = f["z"], f["x"], f["y"], f["health"], f["rockets"]
        st["zmax"] = max(st["zmax"], f["z"])
        k = st["frame"] - p["runup"]
        if not f["ground"]:
            st["air"] = True
        if st["air"] and f["ground"] and k > 4:
            dist = math.hypot(f["x"] - st["x0"], f["y"] - st["y0"])
            return dist > 500, dist, "dist {:.0f} height {:.0f} speed {:.0f} rockets {}".format(
                dist, st["zmax"] - st["z0"], f["speed"], st["r0"] - f["rockets"])
        if st["frame"] > self.max_frames:
            return False, 0, "timeout"
        if k < 0:
            lab.input(127, 0, 0, 0, WP_RL, 0.0, st["dir"])
            return
        up = 127 if abs(k - p["jump_frame"]) < 1 else 0
        fire = BUTTON_ATTACK if 0 <= k - p["fire_frame"] < 3 else 0
        lab.input(127, int(p["strafe"]), up, fire, WP_RL, p["pitch"], st["dir"])


class Pillars(Task):
    """Hop the pillars by yellow armor: YA platform -> pillar A -> pillar B -> back to the platform.
    Geometry from the drop-probe survey (top surfaces at player-origin z ~538, gaps ~100 units)."""
    name = "pillars"
    HOPS = [((-1356.0, 330.0), (-1450.0, 56.0)),    # platform -> pillar A (south-west, over the trench)
            ((-1450.0, 56.0), (-1228.0, 56.0)),     # pillar A -> pillar B (east, over the stairs)
            ((-1228.0, 56.0), (-1260.0, 320.0))]    # pillar B -> platform (north, over the trench)
    space = {}
    for i in range(3):
        space["back%d" % i] = (0.0, 70.0)        # run-up: back away from the edge this far first
        space["jump_at%d" % i] = (80.0, 230.0)   # jump when this far from the next pillar's centre
    space["air_strafe"] = (0.0, 1.0)             # >0.5: strafe-steer in the air, else hold forward
    space["air_brake"] = (0.0, 200.0)            # in the air, push against velocity once this close to target
    max_frames = 40 * 20

    def setup(self, lab, p):
        (fx, fy), _ = self.HOPS[0]
        lab.teleport(fx, fy, 545)
        return dict(hop=0, phase="position", landed=0, air=False,
                    yaw=math.degrees(math.atan2(self.HOPS[0][1][1] - fy, self.HOPS[0][1][0] - fx)))

    def step(self, lab, st, f):
        p = st["params"]
        h = st["hop"]
        (fx, fy), (tx, ty) = self.HOPS[h]
        if f["z"] >= 525 and st["phase"] == "air":
            st["closest"] = min(st.get("closest", 400.0), math.hypot(tx - f["x"], ty - f["y"]))
        partial = st["landed"] * 1000 + 400 - st.get("closest", 400.0)
        if f["z"] < 500:
            return False, partial, "fell on hop {}".format(h + 1)
        if st["frame"] > self.max_frames:
            return False, partial, "timeout on hop {}".format(h + 1)
        d = math.hypot(tx - fx, ty - fy)
        ux, uy = (tx - fx) / d, (ty - fy) / d
        yaw = math.degrees(math.atan2(uy, ux))
        to_target = math.hypot(tx - f["x"], ty - f["y"])
        if st["phase"] == "position":
            bx, by = fx - ux * p["back%d" % h], fy - uy * p["back%d" % h]
            db = math.hypot(bx - f["x"], by - f["y"])
            if f["speed"] > 60 and f["ground"]:
                # brake: face along our velocity and pull back
                lab.input(-127, 0, 0, 0, 0, 0.0, math.degrees(math.atan2(f["vy"], f["vx"])))
            elif db > 12:
                lab.input(127, 0, 0, 0, 0, 0.0, math.degrees(math.atan2(by - f["y"], bx - f["x"])))
            elif f["speed"] > 30:
                lab.input(0, 0, 0, 0, 0, 0.0, yaw)
            else:
                st["phase"] = "run"
            return
        if st["phase"] == "run":
            jump = f["ground"] and to_target <= p["jump_at%d" % h]
            lab.input(127, 0, 127 if jump else 0, 0, 0, 0.0, yaw)
            if jump:
                st["phase"] = "air"
            return
        # air
        if not f["ground"]:
            st["air"] = True
        if st["air"] and f["ground"]:
            if to_target < 90 and f["z"] > 520:
                st["landed"] += 1
                if st["landed"] == len(self.HOPS):
                    return True, 3000 + (self.max_frames - st["frame"]), "all 3 hops in {:.1f}s".format(st["frame"] * FRAME)
                st["hop"], st["phase"], st["air"], st["closest"] = h + 1, "position", False, 400.0
                return
            return False, partial, "landed short on hop {}".format(h + 1)
        aim = math.degrees(math.atan2(ty - f["y"], tx - f["x"]))
        if to_target < p.get("air_brake", 0.0):
            lab.input(-127, 0, 0, 0, 0, 0.0, math.degrees(math.atan2(f["vy"], f["vx"])))
        elif p["air_strafe"] > 0.5 and f["speed"] > 250:
            fwd, right, up, vyaw = strafe_inputs(st, f, (tx, ty), 0.0, 0.0)
            lab.input(fwd, right, 0, 0, 0, 0.0, vyaw)
        else:
            lab.input(127, 0, 0, 0, 0, 0.0, aim)


TASKS = {t.name: t for t in (BridgeRail(), RocketJumpHigh(), RocketJumpFar(), Pillars())}


# ----------------------------------------------------------------------------------------------
# Optimizer
# ----------------------------------------------------------------------------------------------
class CEM:
    def __init__(self, task):
        self.task = task
        self.mu = {k: (lo + hi) / 2 for k, (lo, hi) in task.space.items()}
        self.sigma = {k: (hi - lo) / 3 for k, (lo, hi) in task.space.items()}
        self.queue, self.results, self.gen, self.best = [], [], 0, None
        self.trials = 0
        self.load()

    @property
    def path(self):
        return os.path.join(LOGDIR, self.task.name + ".jsonl")

    def load(self):
        if not os.path.exists(self.path):
            return
        rs = [json.loads(l) for l in open(self.path)]
        rs = [r for r in rs if set(self.task.space) <= set(r["params"]) and not r.get("replay")]
        if not rs:
            return
        self.trials = len(rs)
        self.gen = max(r["gen"] for r in rs) + 1
        rs.sort(key=lambda r: -r["score"])
        self.best = rs[0]
        self.refit(rs[: self.task.n_elite * 2], floor=0.06)

    def refit(self, elite, floor=0.02):
        for k, (lo, hi) in self.task.space.items():
            vals = [e["params"][k] for e in elite]
            m = sum(vals) / len(vals)
            self.mu[k] = m
            self.sigma[k] = max(math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals)), (hi - lo) * floor)

    def next_params(self):
        if not self.queue:
            if self.results:
                elite = sorted(self.results, key=lambda r: -r["score"])[: self.task.n_elite]
                self.refit(elite)
                self.gen += 1
            self.results = []
            self.queue = [{k: min(hi, max(lo, random.gauss(self.mu[k], self.sigma[k])))
                           for k, (lo, hi) in self.task.space.items()} for _ in range(self.task.pop)]
            if self.best:
                self.queue[0] = dict(self.best["params"])
        return self.queue.pop()

    def record(self, res):
        self.trials += 1
        res["gen"] = self.gen
        self.results.append(res)
        new_best = self.best is None or res["score"] > self.best["score"]
        if new_best:
            self.best = res
        with open(self.path, "a") as f:
            f.write(json.dumps(res) + "\n")
        return new_best


# ----------------------------------------------------------------------------------------------
# Plugin
# ----------------------------------------------------------------------------------------------
class practice(minqlx.Plugin):
    def __init__(self):
        os.makedirs(LOGDIR, exist_ok=True)
        self.add_command("pr", self.cmd_pr, usage="start <bot> <idle> [tasks] | stop | status | replay <task> | survey ...")
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.bot = self.idle = None
        self.mode = None            # "train" | "replay" | "survey"
        self.order, self.idx, self.gens_per_turn, self.turn_gens = [], 0, 3, 0
        self.cems = {}
        self.trial = None
        self.survey = None

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
        line = "[practice] " + msg
        minqlx.console_print(line + "\n")
        with open(os.path.join(LOGDIR, "events.log"), "a") as f:
            f.write(line + "\n")

    # ---- helpers used by tasks ----
    def teleport(self, x, y, z):
        p = self.player(self.bot)
        p.position(x=x, y=y, z=z)
        p.velocity(reset=True)

    def loadout(self, rl=False):
        p = self.player(self.bot)
        if rl:
            p.weapons(reset=True, g=True, rl=True)
            p.ammo(rl=50)
            p.weapon("rl")
        p.health = 400
        p.armor = 0

    def input(self, fwd, right, up, buttons=0, weapon=0, pitch=0.0, yaw=0.0):
        minqlx.set_bot_input(self.bot, int(fwd), int(right), int(up), int(buttons), int(weapon), float(pitch), float(yaw))

    # ---- commands ----
    def cmd_pr(self, player, msg, channel):
        sub = msg[1] if len(msg) > 1 else "status"
        if sub == "start":
            self.bot, self.idle = int(msg[2]), int(msg[3])
            names = msg[4].split(",") if len(msg) > 4 else [n for n, t in TASKS.items() if t.enabled]
            self.order = [n for n in names if n in TASKS]
            for n in self.order:
                self.cems.setdefault(n, CEM(TASKS[n]))
            self.idx, self.turn_gens, self.mode, self.trial = 0, 0, "train", None
            self.log("practicing {} with bot {}".format(self.order, self.bot))
        elif sub == "stop":
            self.mode = None
            if self.bot is not None:
                minqlx.clear_bot_input(self.bot)
            self.log("stopped")
        elif sub == "replay":
            n = msg[2]
            self.cems.setdefault(n, CEM(TASKS[n]))
            if len(msg) > 4:
                self.bot, self.idle = int(msg[3]), int(msg[4])
            self.order, self.idx, self.mode, self.trial = [n], 0, "replay", None
            self.log("replaying best {}".format(n))
        elif sub == "survey":
            x0, x1, y0, y1, step, ztop = (float(v) for v in msg[2:8])
            if len(msg) > 9:
                self.bot, self.idle = int(msg[8]), int(msg[9])
            pts = [(x, y) for x in frange(x0, x1, step) for y in frange(y0, y1, step)]
            self.survey = dict(pts=pts, i=0, ztop=ztop, frame=0, last_z=None, still=0)
            self.mode, self.trial = "survey", None
            self.log("survey of {} points".format(len(pts)))
        else:
            for n, c in self.cems.items():
                b = c.best
                self.log("{}: trials={} gen={} best={}".format(
                    n, c.trials, c.gen, "{:.0f} ({})".format(b["score"], b["why"]) if b else "-"))

    # ---- per frame ----
    def on_frame(self):
        if self.mode is None or self.bot is None:
            return
        try:
            self.park_idle()
            if self.mode == "survey":
                return self.step_survey()
            if self.trial is None:
                return self.start_trial()
            self.step_trial()
        except Exception as e:  # keep the session alive no matter what
            self.log("error: {!r}".format(e))
            self.trial = None

    def park_idle(self):
        if self.idle is None:
            return
        minqlx.set_bot_input(self.idle, 0, 0, 0, 0, 0, 0.0, 0.0)
        ip = self.player(self.idle)
        if ip and ip.state and math.hypot(ip.state.position[0] - PARK[0], ip.state.position[1] - PARK[1]) > 50:
            ip.position(x=PARK[0], y=PARK[1], z=PARK[2])
            ip.velocity(reset=True)

    def features(self, st):
        s = minqlx.player_state(self.bot)
        x, y, z = s.position
        vx, vy, vz = s.velocity
        ground = abs(vz) < 1 and st.get("last_z") is not None and abs(z - st["last_z"]) < 1
        st["last_z"] = z
        return dict(x=x, y=y, z=z, vx=vx, vy=vy, vz=vz, speed=math.hypot(vx, vy), ground=ground,
                    health=s.health, alive=s.is_alive or s.health > 0, rockets=s.ammo.rl, weapon=s.weapon)

    def start_trial(self):
        name = self.order[self.idx]
        task, cem = TASKS[name], self.cems[name]
        if self.mode == "replay":
            params = dict(cem.best["params"]) if cem.best else cem.next_params()
        else:
            params = cem.next_params()
        st = task.setup(self, params)
        st.update(params=params, task=name, frame=0, settle=0, path=[], peak=0.0,
                  yaw=st.get("yaw", 0.0), gen=cem.gen)
        self.trial = st

    def step_trial(self):
        st = self.trial
        task, cem = TASKS[st["task"]], self.cems[st["task"]]
        f = self.features(st)
        if st["settle"] < 12:  # let the teleport land and the weapon come up
            st["settle"] += 1
            self.input(0, 0, 0, 0, 0, 0.0, st["yaw"])
            return
        st["frame"] += 1
        st["peak"] = max(st["peak"], f["speed"])
        st["path"].append((round(f["x"]), round(f["y"]), round(f["z"]), round(f["speed"]), int(f["ground"])))
        res = task.step(self, st, f) if f["alive"] else (False, -1e6, "died")
        if res is None:
            return
        success, score, why = res
        out = dict(params=st["params"], score=score, success=success, why=why, peak_speed=round(st["peak"]),
                   path=st["path"], replay=self.mode == "replay")
        if self.mode == "replay":
            self.log("replay {}: {} score={:.0f} ({})".format(st["task"], "SUCCESS" if success else "miss", score, why))
            with open(os.path.join(LOGDIR, st["task"] + "_replays.jsonl"), "a") as fh:
                fh.write(json.dumps(out) + "\n")
        else:
            gen_before = cem.gen
            if cem.record(out):
                self.log("{} new best (trial {}, gen {}): score={:.0f} success={} ({})".format(
                    st["task"], cem.trials, cem.gen, score, success, why))
            if not cem.queue:  # generation finished -> maybe rotate to the next task
                self.turn_gens += 1
                if self.turn_gens >= self.gens_per_turn and len(self.order) > 1:
                    self.turn_gens = 0
                    self.idx = (self.idx + 1) % len(self.order)
        self.trial = None

    def step_survey(self):
        sv = self.survey
        if sv["i"] >= len(sv["pts"]):
            self.log("survey done")
            self.mode = None
            return
        s = minqlx.player_state(self.bot)
        if not (s.is_alive or s.health > 0):
            sv["frame"] = 0  # dead (fell into the void): wait for respawn, then redo this point
            return
        x, y = sv["pts"][sv["i"]]
        if sv["frame"] == 0:
            self.teleport(x, y, sv["ztop"])
            self.player(self.bot).health = 400
            sv["last_z"], sv["still"] = None, 0
            sv["frame"] = 1
            return
        self.input(0, 0, 0, 0, 0, 0.0, 0.0)
        sv["frame"] += 1
        px, py, pz = s.position
        if sv["last_z"] is not None and abs(pz - sv["last_z"]) < 0.5 and abs(s.velocity[2]) < 1:
            sv["still"] += 1
        else:
            sv["still"] = 0
        sv["last_z"] = pz
        void = pz < -250
        if sv["still"] >= 3 or void or sv["frame"] > 90:
            with open(os.path.join(LOGDIR, "survey.txt"), "a") as fh:
                fh.write("{:.0f} {:.0f} {:.1f} {:.1f} {:.1f} {} {}\n".format(
                    x, y, px, py, pz, sv["frame"], "void" if void else "ok"))
            sv["i"] += 1
            sv["frame"] = 0
            if void:
                self.teleport(-768.0, 320.0, 60.0)


def frange(a, b, step):
    v = a
    while v <= b + 1e-6:
        yield v
        v += step
