"""movetest: does movement learned in the simulator carry over to the real Quake Live server?

Drives BobbyBones (alone on a private server) with a policy trained in sim/ and times item-to-item trips,
alternating human physics (3 moves per frame, what it trained under) and plain bot physics (1 move per frame).
The observation is built by the exact same code as in training (sim/movement_env.py, collision from the map
file), only position/velocity come from the real game.

Load with QLX_PLUGINS="botctl, movetest". Needs /tmp/practice/policy.npz (sim/export_policy.py) and the
map's nav graph /tmp/practice/nav_<map>.json. Writes /tmp/practice/movetest.jsonl (one line per trip) and
movetest_frames.jsonl (every frame, for comparing with the simulator).
"""
import json
import math
import os
import random
import sys
import time
import zipfile

import minqlx
import numpy as np

sys.path.insert(0, "/sim")
D = "/tmp/practice"
LABEL = {"item_armor_body": "RA", "item_armor_combat": "YA", "item_armor_jacket": "GA", "item_health_mega": "MH",
         "weapon_rocketlauncher": "RL", "weapon_lightning": "LG", "weapon_railgun": "RG", "weapon_plasmagun": "PG",
         "weapon_shotgun": "SG", "weapon_grenadelauncher": "GL", "item_health_large": "h50"}


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class movetest(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.ready = False
        self.next_check = 0.0
        self.trip = None
        self.k = 0

    def log(self, msg):
        minqlx.console_print("[movetest] " + msg + "\n")
        with open(os.path.join(D, "movetest.log"), "a") as f:
            f.write("{} {}\n".format(time.strftime("%H:%M:%S"), msg))

    def on_map(self, mapname, factory):
        self.ready, self.trip = False, None

    def setup(self):
        from movement_env import MoveEnv
        mapname = (minqlx.get_cvar("mapname") or "").lower()
        bsp = "/tmp/maps/{}.bsp".format(mapname)
        if not os.path.exists(bsp):
            os.makedirs("/tmp/maps", exist_ok=True)
            with open(bsp, "wb") as f:
                f.write(zipfile.ZipFile("/ql/baseq3/pak00.pk3").read("maps/{}.bsp".format(mapname)))
        P = np.load(os.path.join(D, "policy.npz"))
        self.P = {k: P[k] for k in P.files}
        self.dims = [int(x) for x in self.P["action_dims"]]
        self.env = MoveEnv(bsp, os.path.join(D, "nav_{}.json".format(mapname)), n=1, seed=1)
        from movement_env import TURN_BINS
        self.turn_bins = TURN_BINS
        ents = [e for e in self.env.w.entities if e.get("classname") in LABEL and "origin" in e]
        labels = [LABEL[e["classname"]] for e in ents]
        self.goals = {}
        for e, lab in zip(ents, labels):
            if labels.count(lab) == 1:
                d = np.linalg.norm(self.env.goal_pos - np.array(e["origin"], np.float32), axis=1)
                if d.min() < 1:
                    self.goals[lab] = int(d.argmin())
        self.pairs = [(x, y) for x in self.goals for y in self.goals if x != y]
        random.Random(7).shuffle(self.pairs)
        self.ready = True
        self.log("ready on {}: policy {}, {} trips, train substeps {}".format(
            mapname, self.P["run"], len(self.pairs), list(self.P["substeps"])))

    def bot(self):
        for p in self.players():
            if is_bot(p) and "Bones" in p.clean_name:
                return p
        return None

    def act(self, obs):
        P = self.P
        x = np.clip((obs - P["obs_mean"]) / np.sqrt(P["obs_var"] + 1e-8), -10, 10).astype(np.float32)
        h = np.tanh(x @ P["w0"].T + P["b0"])
        h = np.tanh(h @ P["w1"].T + P["b1"])
        logits = h @ P["wp"].T + P["bp"]
        out, i = [], 0
        for d in self.dims:
            l = logits[0, i:i + d]
            p = np.exp(l - l.max())
            p /= p.sum()
            out.append(int(np.random.choice(d, p=p)))      # sampled, as in the simulator evaluation
            i += d
        return out

    def start_trip(self, b):
        x, y = self.pairs[self.k % len(self.pairs)]
        mode = 3 if (self.k // len(self.pairs)) % 2 == 0 else 1     # all trips with human physics, then bot
        self.k += 1
        env, gi = self.env, self.goals[y]
        p = env.goal_pos[self.goals[x]]
        node, _ = env.field.locate(p[None])
        nx = env.field.next[gi, node[0]]
        q = env.field.nodes[nx] if nx >= 0 else env.goal_pos[gi]
        yaw = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))
        b.position(x=float(p[0]), y=float(p[1]), z=float(p[2]) + 2.0)
        b.velocity(reset=True)
        b.health = 200
        minqlx.set_bot_input(b.id, 0, 0, 0, 0, 0, 0.0, float(yaw))
        minqlx.set_bot_substeps(b.id, mode)
        self.trip = dict(key="{}>{}".format(x, y), goal=gi, yaw=yaw, frames=-3, mode=mode, vmax=0.0,
                         fast_air=0, moving=0)

    def on_frame(self):
        now = time.time()
        if not self.ready:
            if now > self.next_check:
                self.next_check = now + 2
                want = os.environ.get("LAB_MAP", "bloodrun").lower()
                if (minqlx.get_cvar("mapname") or "").lower() != want:
                    self.next_check = now + 10
                    minqlx.console_command("map {} duel".format(want))
                    return
                if minqlx.get_cvar("mapname"):
                    try:
                        self.setup()
                    except Exception as e:
                        self.log("setup failed: {!r}".format(e))
            return
        b = self.bot()
        if b is None:
            if now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("addbot bones 5 free 0 BobbyBones")
            return
        if self.trip is None:
            if b.state and b.state.health > 0:
                self.start_trip(b)
            return
        t = self.trip
        t["frames"] += 1
        if t["frames"] <= 0:                                  # let the teleport settle
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, 0, 0.0, float(t["yaw"]))
            return
        st = b.state
        t["yaw"] = float(minqlx.view_angles(b.id)[1])          # the real view (teleporters turn it, as in the sim)
        pos = np.array(st.position, np.float32)
        vel = np.array(st.velocity, np.float32)
        env = self.env
        floor = env.w.rays(pos[None], np.array([[0, 0, -1.0]], np.float32), 30.0)[0, 0] < 1
        ground = 1.0 if (abs(vel[2]) < 1 and floor) else 0.0
        env.state = np.array([[*pos, *vel, ground, t["yaw"]]], np.float32)
        env.yaw = np.array([t["yaw"]], np.float32)
        env.goal = np.array([t["goal"]], np.int32)
        env.phi, _ = env.field.potential(env.goal, pos[None])
        gp = env.goal_pos[t["goal"]]
        sp = float(math.hypot(vel[0], vel[1]))
        t["vmax"] = max(t["vmax"], sp)
        if sp > 50:
            t["moving"] += 1
            t["fast_air"] += int(sp > 330 and not ground)
        secs = t["frames"] * 0.025
        arrived = bool(math.hypot(gp[0] - pos[0], gp[1] - pos[1]) < 40 and abs(gp[2] - pos[2]) < 64)
        if arrived or secs > 20 or st.health <= 0:
            rec = dict(t=time.time(), trip=t["key"], mode="human" if t["mode"] == 3 else "bot", secs=round(secs, 3),
                       arrived=arrived, vmax=round(t["vmax"]), fast_air=round(t["fast_air"] / max(1, t["moving"]), 3))
            with open(os.path.join(D, "movetest.jsonl"), "a") as f:
                f.write(json.dumps(rec) + "\n")
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, 0, 0.0, float(t["yaw"]))
            self.trip = None
            return
        obs = env.observe()
        a = self.act(obs)
        fwd, side, jump = (a[0] - 1) * 127, (a[1] - 1) * 127, a[2] * 127
        t["yaw"] = (t["yaw"] + float(self.turn_bins[a[3]]) + 180.0) % 360.0 - 180.0
        minqlx.set_bot_input(b.id, fwd, side, jump, 0, 0, 0.0, float(t["yaw"]))
        with open(os.path.join(D, "movetest_frames.jsonl"), "a") as f:
            f.write(json.dumps([t["key"], t["mode"], t["frames"], *[round(float(v), 2) for v in pos],
                                *[round(float(v), 2) for v in vel], float(ground), fwd, side, jump, round(t["yaw"], 2)]) + "\n")
