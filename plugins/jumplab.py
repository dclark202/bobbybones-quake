"""jumplab: a bot teaches itself the campgrounds bridge -> rail strafe jump by trial and error.

Each trial: teleport the bot onto the bridge, run a strafe-jump controller whose behaviour is
set by a handful of parameters, and score how close it gets to landing on the rail ledge.
A cross-entropy-method optimizer proposes new parameters from the best trials so far.
"""
import json
import math
import random

import minqlx

FRAME = 0.025          # sv_fps 40
WISHSPEED = 320.0
AIR_ACCEL = 1.0
LOG = "/tmp/jumplab.jsonl"

# Geometry measured from bot traces (player origin z on the top floors is ~538).
LEDGE = dict(xmin=330, xmax=520, ymin=-320, ymax=345)
TOP_Z = 520
PARK = (-768.0, 320.0, 40.0)   # where the second (idle) bot is kept, ground floor near LG

# name: (low, high)
SPACE = {
    "start_x": (-250.0, 560.0),   # start point on the bridge
    "start_y": (-1010.0, -830.0),
    "way_x": (150.0, 640.0),      # waypoint on the bridge to run through before turning north
    "way_y": (-1010.0, -800.0),
    "way_r": (40.0, 220.0),       # switch to the final target once within this distance of the waypoint
    "aim_x": (380.0, 520.0),      # point on the ledge to steer toward
    "aim_y": (-300.0, 100.0),
    "bias": (-12.0, 12.0),        # degrees added to the optimal strafe angle (speed vs. turning)
    "first_jump": (0.0, 12.0),    # ground frames before the first jump
    "lead": (0.0, 3.0),           # frames of turn-rate prediction to cover input latency
}
DEFAULTS = {"lead": 0.0}
KEYS = list(SPACE)


class jumplab(minqlx.Plugin):
    def __init__(self):
        self.add_command("jl", self.cmd_jl, usage="start <bot> <idle_bot> [gens] | stop | best | replay")
        self.add_hook("frame", self.on_frame)
        self.bot = None
        self.idle = None
        self.running = False
        self.trial = None
        self.best = None
        self.replay = False
        self.reset_cem()

    def log(self, msg):
        minqlx.console_print("[jumplab] " + msg + "\n")

    # ---------------- optimizer (cross-entropy method) ----------------
    def reset_cem(self):
        self.mu = {k: (lo + hi) / 2 for k, (lo, hi) in SPACE.items()}
        self.sigma = {k: (hi - lo) / 3 for k, (lo, hi) in SPACE.items()}
        self.gen, self.max_gens, self.pop, self.n_elite = 0, 25, 20, 5
        self.queue, self.results = [], []
        self.trials_done = 0

    def sample(self):
        p = {}
        for k, (lo, hi) in SPACE.items():
            p[k] = min(hi, max(lo, random.gauss(self.mu[k], self.sigma[k])))
        return p

    def next_params(self):
        if self.replay and self.best:
            return dict(self.best["params"])
        if not self.queue:
            if self.results:
                self.update_cem()
            if self.gen >= self.max_gens:
                return None
            self.queue = [self.sample() for _ in range(self.pop)]
            if self.best:  # keep the champion in every generation
                self.queue[0] = dict(self.best["params"])
            self.results = []
        return self.queue.pop()

    def update_cem(self):
        elite = sorted(self.results, key=lambda r: -r["score"])[:self.n_elite]
        for k, (lo, hi) in SPACE.items():
            vals = [e["params"][k] for e in elite]
            m = sum(vals) / len(vals)
            sd = math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))
            self.mu[k] = m
            self.sigma[k] = max(sd, (hi - lo) * 0.02)
        self.gen += 1
        succ = sum(1 for r in self.results if r["success"])
        self.log("gen {} done: best={:.0f} elite_mean={:.0f} successes_this_gen={}/{}".format(
            self.gen, elite[0]["score"], sum(e["score"] for e in elite) / len(elite), succ, len(self.results)))

    # ---------------- commands ----------------
    def cmd_jl(self, player, msg, channel):
        sub = msg[1] if len(msg) > 1 else ""
        if sub == "start":
            self.bot, self.idle = int(msg[2]), int(msg[3])
            if not (len(msg) > 5 and msg[5] == "keep"):
                self.reset_cem()
            else:
                self.gen, self.queue, self.results = 0, [], []
            if len(msg) > 4:
                self.max_gens = int(msg[4])
            self.replay, self.running, self.trial = False, True, None
            self.log("training bot {} ({} generations x {} trials)".format(self.bot, self.max_gens, self.pop))
        elif sub == "stop":
            self.running = False
            minqlx.clear_bot_input(self.bot)
            self.log("stopped")
        elif sub == "best":
            self.log("best: " + json.dumps(self.best))
        elif sub == "load":
            # load the best trials from previous runs and centre the optimizer on them
            rs = [json.loads(l) for l in open(LOG)]
            rs = [r for r in rs if set(r["params"]) <= set(KEYS)]
            for r in rs:
                for k, v in DEFAULTS.items():
                    r["params"].setdefault(k, v)
            rs.sort(key=lambda r: -r["score"])
            self.best = rs[0]
            elite = rs[:8]
            for k, (lo, hi) in SPACE.items():
                vals = [e["params"][k] for e in elite]
                m = sum(vals) / len(vals)
                self.mu[k] = m
                self.sigma[k] = max(math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals)), (hi - lo) * 0.08)
            self.log("loaded {} past trials, best score {:.0f}".format(len(rs), self.best["score"]))
        elif sub == "replay":
            if len(msg) > 3:
                self.bot, self.idle = int(msg[2]), int(msg[3])
            self.replay, self.running, self.trial = True, True, None
            self.log("replaying best trial on a loop")

    # ---------------- per-frame trial runner ----------------
    def on_frame(self):
        if not self.running or self.bot is None:
            return
        if self.idle is not None:
            minqlx.set_bot_input(self.idle, 0, 0, 0, 0, 0, 0.0, 0.0)
            ip = self.player(self.idle)
            if ip and ip.state and math.hypot(ip.state.position[0] - PARK[0], ip.state.position[1] - PARK[1]) > 50:
                ip.position(x=PARK[0], y=PARK[1], z=PARK[2])
                ip.velocity(reset=True)
        if self.trial is None:
            params = self.next_params()
            if params is None:
                self.running = False
                minqlx.clear_bot_input(self.bot)
                self.log("training finished. best: " + json.dumps(self.best))
                return
            self.start_trial(params)
            return
        self.step_trial()

    def start_trial(self, params):
        p = self.player(self.bot)
        p.position(x=params["start_x"], y=params["start_y"], z=545)
        p.velocity(reset=True)
        p.health = 200
        yaw = math.degrees(math.atan2(params["way_y"] - params["start_y"], params["way_x"] - params["start_x"]))
        self.trial = dict(params=params, frame=0, phase="settle", stage=0, side=1, yaw=yaw,
                          max_score=-1e9, path=[], airborne=False, last_z=None, jumps=0, peak_speed=0)

    def step_trial(self):
        tr = self.trial
        prm = tr["params"]
        tr["frame"] += 1
        s = minqlx.player_state(self.bot)
        x, y, z = s.position
        vx, vy, vz = s.velocity
        speed = math.hypot(vx, vy)
        tr["peak_speed"] = max(tr["peak_speed"], speed)
        on_ground = abs(vz) < 1 and tr["last_z"] is not None and abs(z - tr["last_z"]) < 1
        tr["last_z"] = z
        tr["path"].append((round(x), round(y), round(z), round(speed), int(on_ground), round(vz)))

        # settle for a few frames after the teleport so the bot is standing on the bridge
        if tr["phase"] == "settle":
            minqlx.set_bot_input(self.bot, 0, 0, 0, 0, 0, 0.0, tr["yaw"])
            if tr["frame"] >= 6:
                tr["phase"], tr["frame"] = "run", 0
            return

        # --- scoring ---
        on_ledge = LEDGE["xmin"] <= x <= LEDGE["xmax"] and LEDGE["ymin"] <= y <= LEDGE["ymax"]
        if z >= TOP_Z - 6:
            # progress = how far north (toward/along the ledge) we got while still high enough
            tr["max_score"] = max(tr["max_score"], y - abs(x - 450) * 0.3)
        if on_ground and on_ledge and z >= TOP_Z:
            return self.finish(True, "landed on rail ledge")
        if z < TOP_Z - 120:
            return self.finish(False, "fell")
        if tr["frame"] > 40 * 7:
            return self.finish(False, "timeout")

        # --- controller ---
        if tr["stage"] == 0 and math.hypot(prm["way_x"] - x, prm["way_y"] - y) < prm["way_r"]:
            tr["stage"] = 1
        tx, ty = (prm["way_x"], prm["way_y"]) if tr["stage"] == 0 else (prm["aim_x"], prm["aim_y"])
        aim_yaw = math.degrees(math.atan2(ty - y, tx - x))
        if speed < 250:
            # run-up: run straight at the current target, jump after first_jump frames
            up = 127 if (on_ground and tr["frame"] >= prm["first_jump"]) else 0
            minqlx.set_bot_input(self.bot, 127, 0, up, 0, 0, 0.0, aim_yaw)
            return
        vel_yaw = math.degrees(math.atan2(vy, vx))
        prev = tr.get("prev_vel_yaw", vel_yaw)
        tr["prev_vel_yaw"] = vel_yaw
        vel_yaw += ((vel_yaw - prev + 180) % 360 - 180) * prm["lead"]
        # strafe toward the side that turns the velocity onto the target direction
        err = (aim_yaw - vel_yaw + 180) % 360 - 180
        side = -1 if err > 0 else 1   # side=-1 strafes left (turns velocity counter-clockwise)
        theta = math.degrees(math.acos(max(-1.0, min(1.0, (WISHSPEED - AIR_ACCEL * WISHSPEED * FRAME) / speed))))
        theta = max(0.0, theta + prm["bias"])
        # (wish = view - 45*side); want wish = vel_yaw - side*theta
        view_yaw = vel_yaw - side * theta + side * 45.0
        up = 127 if on_ground else 0
        if on_ground and not tr["airborne"]:
            pass
        if not on_ground and not tr["airborne"]:
            tr["jumps"] += 1
        tr["airborne"] = not on_ground
        minqlx.set_bot_input(self.bot, 127, side * 127, up, 0, 0, 0.0, view_yaw)

    def finish(self, success, why):
        tr = self.trial
        score = tr["max_score"] + (2000 if success else 0)
        res = dict(params=tr["params"], score=score, success=success, why=why,
                   peak_speed=round(tr["peak_speed"]), jumps=tr["jumps"], gen=self.gen)
        self.trials_done += 1
        if not self.replay:
            self.results.append(res)
            if self.best is None or score > self.best["score"]:
                self.best = dict(res)
                self.best["path"] = tr["path"]
                self.log("new best #{}: score={:.0f} success={} peak_speed={} ({})".format(
                    self.trials_done, score, success, res["peak_speed"], why))
        else:
            self.log("replay: {} peak_speed={} ({})".format("SUCCESS" if success else "miss", res["peak_speed"], why))
        with open(LOG, "a") as f:
            res["path"] = tr["path"]
            f.write(json.dumps(res) + "\n")
        self.trial = None
