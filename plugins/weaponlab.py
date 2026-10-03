"""weaponlab: measure Quake Live's real weapon numbers so the duel simulator can be checked against them.

Two fully controlled bots on a long flat stretch of Campgrounds. For each test the shooter fires one setup and
both bots' health, armor, position and velocity are logged every frame for 1.2 s. Tests (each repeated):
  rl_body       rocket at the target's body from 400 units
  rl_floor_<d>  rocket at the floor d units in front of the target's feet (splash falloff + knockback)
  rl_self       rocket straight down at the shooter's own feet (rocket jump)
  rl_speed      rocket at the body from 800 units (travel time)
  rg_body       railgun at the body from 1000 units
  lg_<d>        lightning gun held 1 s at the target from d units (damage per frame, range)
Load with QLX_PLUGINS="botctl, weaponlab" and LAB_MAP=campgrounds. Writes /tmp/practice/weaponlab.jsonl.
"""
import json
import math
import os
import time

import minqlx

D = "/tmp/practice"
LINE_START = (-1377.0, -817.0, 538.1)       # longest flat, clear floor run on Campgrounds (1408 units, simulator search)
LINE_YAW = 0.0
TESTS = (["rl_body", "rl_self", "rl_speed", "rg_body"] + ["rl_floor_{}".format(d) for d in (0, 20, 40, 60, 80, 100, 120, 140)] +
         ["lg_300", "lg_700", "lg_800", "lg_850", "lg_875", "lg_900", "lg_925", "lgkick_300"])
REPEATS = 4
WEAPON = {"rl": 5, "lg": 6, "rg": 7}


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class weaponlab(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.queue = [(t, r) for r in range(REPEATS) for t in TESTS]
        self.cur = None
        self.next_check = 0.0

    def log(self, msg):
        minqlx.console_print("[weaponlab] " + msg + "\n")
        with open(os.path.join(D, "weaponlab.log"), "a") as f:
            f.write("{} {}\n".format(time.strftime("%H:%M:%S"), msg))

    def bots(self):
        return [p for p in self.players() if is_bot(p) and p.team != "spectator"]

    def setup_test(self, shooter, target, name):
        dirx, diry = math.cos(math.radians(LINE_YAW)), math.sin(math.radians(LINE_YAW))
        dist = {"rl_speed": 800.0, "rg_body": 1000.0}.get(name, 400.0)
        if name.startswith("lg_"):
            dist = float(name[3:])
        if name.startswith("lgkick_"):
            dist = float(name[7:])
        sx, sy, sz = LINE_START
        sp = (sx + dirx * 64, sy + diry * 64, sz + 2)
        tp = (sp[0] + dirx * dist, sp[1] + diry * dist, sz + 2)
        for p, pos in ((shooter, sp), (target, tp)):
            p.position(x=pos[0], y=pos[1], z=pos[2])
            p.velocity(reset=True)
            p.health = 200
            p.armor = 0
            p.weapons(g=True, mg=True, rl=True, lg=True, rg=True)
            p.ammo(rl=50, lg=200, rg=50, mg=100)
        wname = name.split("_")[0].replace("lgkick", "lg")
        # aim point
        eye = (sp[0], sp[1], sp[2] + 26.0)
        if name == "rl_self":
            pitch, yaw = 89.0, LINE_YAW
        else:
            if name.startswith("rl_floor_"):
                off = float(name.split("_")[2])
                aim = (tp[0] - dirx * (15 + off), tp[1] - diry * (15 + off), tp[2] - 24.0)   # floor, in front of the box
            else:
                aim = (tp[0], tp[1], tp[2] + 4.0)                                            # body centre
            dx, dy, dz = aim[0] - eye[0], aim[1] - eye[1], aim[2] - eye[2]
            pitch = -math.degrees(math.atan2(dz, math.hypot(dx, dy)))
            yaw = math.degrees(math.atan2(dy, dx))
        self.cur = dict(name=name, tpos=tp, shooter=shooter.id, target=target.id, weapon=WEAPON[wname], pitch=pitch, yaw=yaw,
                        frame=-30, dist=dist, rows=[])
        minqlx.set_bot_input(shooter.id, 0, 0, 0, 0, WEAPON[wname], pitch, yaw)
        minqlx.set_bot_input(target.id, 0, 0, 0, 0, 2, 0.0, LINE_YAW + 180.0)

    def on_frame(self):
        now = time.time()
        if (minqlx.get_cvar("mapname") or "").lower() != "campgrounds":
            if now > self.next_check:
                self.next_check = now + 10
                minqlx.console_command("map campgrounds duel")
            return
        bots = self.bots()
        if len(bots) < 2:
            if now > self.next_check:
                self.next_check = now + 4
                minqlx.console_command("addbot {} 5".format("bones" if not bots else "sarge"))
            return
        shooter, target = bots[0], bots[1]
        c = self.cur
        if c is None:
            if not self.queue:
                if now > self.next_check:
                    self.next_check = now + 60
                    self.log("all tests done")
                return
            name, rep = self.queue.pop(0)
            if not (shooter.state and target.state and shooter.state.health > 0 and target.state.health > 0):
                self.queue.insert(0, (name, rep))
                return
            self.setup_test(shooter, target, name)
            self.cur["rep"] = rep
            return
        c["frame"] += 1
        f = c["frame"]
        if f < 0:                                               # settle, weapon up, keep both still
            if f == -10:
                for p in (shooter, target):
                    p.health = 200
                    p.armor = 0
                    p.velocity(reset=True)
            minqlx.set_bot_input(c["shooter"], 0, 0, 0, 0, c["weapon"], c["pitch"], c["yaw"])
            return
        firing = (f == 0) or (c["name"].startswith("lg_") and f < 40) or (c["name"].startswith("lgkick_") and f < 2)
        minqlx.set_bot_input(c["shooter"], 0, 0, 0, 1 if firing else 0, c["weapon"], c["pitch"], c["yaw"])
        row = [f]
        for pid in (c["shooter"], c["target"]):
            st = minqlx.player_state(pid)
            row += [st.health, st.armor, *[round(v, 2) for v in st.position], *[round(v, 2) for v in st.velocity]]
        c["rows"].append(row)
        if c["name"].startswith("lg_"):                       # pin the target so the beam stays on it (damage rate, range)
            tgt = self.player(c["target"])
            if tgt is not None:
                tgt.position(x=c["tpos"][0], y=c["tpos"][1], z=c["tpos"][2])
                tgt.velocity(reset=True)
        if f >= 48:
            rec = dict(test=c["name"], rep=c["rep"], dist=c["dist"], pitch=round(c["pitch"], 3), yaw=round(c["yaw"], 3),
                       cols="frame s_hp s_armor s_x s_y s_z s_vx s_vy s_vz t_hp t_armor t_x t_y t_z t_vx t_vy t_vz",
                       rows=c["rows"])
            with open(os.path.join(D, "weaponlab.jsonl"), "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            self.log("{} rep {}: target hp {} -> {}, shooter hp {} -> {}".format(
                c["name"], c["rep"], c["rows"][0][9], min(r[9] for r in c["rows"]), c["rows"][0][1],
                min(r[1] for r in c["rows"])))
            minqlx.set_bot_input(c["shooter"], 0, 0, 0, 0, c["weapon"], c["pitch"], c["yaw"])
            self.cur = None
