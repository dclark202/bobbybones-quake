"""weaponlab: measure Quake Live's real weapon numbers so the duel simulator can be checked against them.

Two fully controlled bots on a long flat stretch of Campgrounds. For each test the shooter fires one setup and
both bots' health, armor, position and velocity are logged every frame. Test names: <weapon>_<what>:
  *_body / *_<dist>   shot(s) at the target's body from that distance (default 400)
  *_floor_<d>         one shot at the floor d units in front of the target's feet (splash falloff + knockback)
  *_self              one shot straight down at the shooter's own feet
  lg/mg/hmg/pg/g      held for 1 s with the target pinned in place (damage rate, range, projectile speed)
WEAPONLAB_SET=1 (default): rockets, rail, lightning. =2: machine gun, heavy machine gun, shotgun, plasma,
grenades, gauntlet. Load with QLX_PLUGINS="botctl, weaponlab". Writes /tmp/practice/weaponlab.jsonl.
"""
import json
import math
import os
import time

import minqlx

D = "/tmp/practice"
LINE_START = (-1377.0, -817.0, 538.1)       # longest flat, clear floor run on Campgrounds (1408 units, simulator search)
LINE_YAW = 0.0
LINE2 = (447.0, 255.0, 538.1, 270.0)       # (set 7) open air ahead: shooter here, target along -y (2026-11-13)
WEAPON = {"g": 1, "mg": 2, "sg": 3, "gl": 4, "rl": 5, "lg": 6, "rg": 7, "pg": 8, "hmg": 14}
REPEATS = 4


def spec(weapon, dist=400.0, aim="body", hold=1, frames=48, pin=False, off=0.0, pre=None, pf=0, thp=200, air=0.0, line=None):
    return dict(weapon=weapon, dist=dist, aim=aim, hold=hold, frames=frames, pin=pin, off=off, pre=pre, pf=pf, thp=thp, air=air, line=line)


SETS = {
    "1": dict(
        [("rl_body", spec("rl")), ("rl_self", spec("rl", aim="self")), ("rl_speed", spec("rl", dist=800)),
         ("rg_body", spec("rg", dist=1000))] +
        [("rl_floor_{}".format(d), spec("rl", aim="floor", off=d)) for d in (0, 20, 40, 60, 80, 100, 120, 140)] +
        [("lg_{}".format(d), spec("lg", dist=d, hold=40, pin=True)) for d in (300, 700, 750, 800)] +
        [("lgkick_300", spec("lg", dist=300, hold=2))]),
    "2": dict(
        [("mg_400", spec("mg", hold=40, pin=True)), ("mgkick_400", spec("mg", hold=2)),
         ("hmg_400", spec("hmg", hold=40, pin=True)), ("hmgkick_400", spec("hmg", hold=2)),
         ("sg_100", spec("sg", dist=100)), ("sg_300", spec("sg", dist=300)), ("sg_600", spec("sg", dist=600)),
         ("pg_400", spec("pg", hold=40, pin=True)), ("pg_800", spec("pg", dist=800, hold=40, pin=True)),
         ("pgkick_400", spec("pg", hold=1)), ("pg_self", spec("pg", aim="self"))] +
        [("pg_floor_{}".format(d), spec("pg", aim="floor", off=d)) for d in (0, 10, 20, 30)] +
        [("gl_150", spec("gl", dist=150, frames=140)), ("gl_self", spec("gl", aim="self", frames=140)),
         ("g_40", spec("g", dist=40, hold=40, pin=True)), ("g_70", spec("g", dist=70, hold=40, pin=True))]),
    # weapon switch time: hold `pre` during the settle, then select `weapon` and hold fire from frame 0
    "3": dict(
        [("sw_{}_{}".format(a, b), spec(b, hold=70, frames=80, pin=True, pre=a))
         for a, b in (("mg", "rg"), ("rl", "rg"), ("rg", "lg"), ("lg", "rl"), ("rg", "mg"), ("mg", "rl"))] +
        [("base_{}".format(b), spec(b, hold=70, frames=80, pin=True)) for b in ("rg", "lg", "rl", "mg")]),
    # grenades: the missile's own path (speed, arc, bounce, fuse), at fixed pitches along the flat stretch; the target far away
    "4": dict(
        [("glp_{}".format(p_), spec("gl", dist=1300, aim="pitch", off=p_, frames=130)) for p_ in (0, -20, -45, 20, 45, 70)] +
        [("gl_self", spec("gl", aim="self", frames=130)), ("gl_150", spec("gl", dist=150, frames=130))]),
    # (B-302, 2026-11-06) a switch started during the reload: fire `pre` once (frame 0), select `weapon` from frame 1 and hold fire;
    # when does `weapon` first fire? The simulator waits for the reload: cool = max(cool, fire_cd + SWITCH). The target at 999 health
    "5": dict(
        [("rl_{}_{}".format(a, b), spec(b, hold=100, frames=110, pin=True, pre=a, pf=1, thp=999))
         for a, b in (("rg", "lg"), ("rl", "lg"), ("rl", "rg"), ("rg", "rl"), ("sg", "lg"), ("gl", "lg"), ("mg", "lg"))]),
    # (2026-11-13, docs/research/MECHANICS.md section 7.1: the cvars say LG 1.75, MG/HMG/SG 1; the simulator has 1.167, 0.4, 0.625, 0.85)
    # knockback alone: one trigger frame at a target at 999 health, on the ground and in the air (lifted `air` units and let go two
    # frames before the shot: no ground friction in the hit frame), every frame's velocity recorded
    "6": dict(
        [("{}kick_{}".format(w, where), spec(w, dist=d, hold=1, frames=24, thp=999, air=a))
         for w, d in (("lg", 300), ("mg", 300), ("hmg", 300), ("sg", 100), ("rg", 400), ("rl", 300))
         for where, a in (("ground", 0.0), ("air", 120.0))] +
        [("lgkick2_air", spec("lg", dist=300, hold=3, frames=24, thp=999, air=120.0))]),
    # (2026-11-13) set 6's lifted targets at 300 units sat inside the geometry over the first line (they never moved); this line
    # (Campgrounds, found by a simulator search) has 900 units of open air ahead of a target lifted 100: streams in the air, the
    # vertical kick, and where the target is in the hit frame (the game moves it in that frame)
    "7": dict(
        [("lgstream_air_{}".format(d), spec("lg", dist=d, hold=h, frames=48, thp=999, air=100.0, line=LINE2))
         for d in (150, 300) for h in (1, 16)] +
        [("lgstream_ground_150", spec("lg", dist=150, hold=16, frames=40, thp=999, line=LINE2)),
         ("mgstream_air_150", spec("mg", dist=150, hold=16, frames=40, thp=999, air=100.0, line=LINE2)),
         ("rlkick_air_200", spec("rl", dist=200, hold=1, frames=40, thp=999, air=100.0, line=LINE2)),
         ("rgkick_air_300", spec("rg", dist=300, hold=1, frames=40, thp=999, air=100.0, line=LINE2)),
         ("sgkick_air_150", spec("sg", dist=150, hold=1, frames=40, thp=999, air=100.0, line=LINE2))]),
}
TESTS = SETS[os.environ.get("WEAPONLAB_SET", "1")]


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
        sp_ = TESTS[name]
        lx, ly, lz, lyaw = sp_.get("line") or (LINE_START[0], LINE_START[1], LINE_START[2], LINE_YAW)
        dirx, diry = math.cos(math.radians(lyaw)), math.sin(math.radians(lyaw))
        dist = float(sp_["dist"])
        sx, sy, sz = lx, ly, lz
        sp = (sx + dirx * 64, sy + diry * 64, sz + 2)
        tp = (sp[0] + dirx * dist, sp[1] + diry * dist, sz + 2)
        for p, pos in ((shooter, sp), (target, tp)):
            p.position(x=pos[0], y=pos[1], z=pos[2])
            p.velocity(reset=True)
            p.health = 200
            p.armor = 0
            p.weapons(g=True, mg=True, sg=True, gl=True, rl=True, lg=True, rg=True, pg=True, hmg=True)
            p.ammo(mg=150, sg=25, gl=25, rl=50, lg=200, rg=50, pg=200, hmg=200)
        eye = (sp[0], sp[1], sp[2] + 26.0)
        if sp_["aim"] == "self":
            pitch, yaw = 89.0, lyaw
        elif sp_["aim"] == "pitch":                             # a fixed pitch along the line (negative: up)
            pitch, yaw = float(sp_["off"]), lyaw
        else:
            if sp_["aim"] == "floor":
                off = float(sp_["off"])
                aim = (tp[0] - dirx * (15 + off), tp[1] - diry * (15 + off), tp[2] - 24.0)   # floor, in front of the box
            else:
                aim = (tp[0], tp[1], tp[2] + 4.0 + float(sp_.get("air", 0.0)))              # body centre (set 6: where it is lifted to)
            dx, dy, dz = aim[0] - eye[0], aim[1] - eye[1], aim[2] - eye[2]
            pitch = -math.degrees(math.atan2(dz, math.hypot(dx, dy)))
            yaw = math.degrees(math.atan2(dy, dx))
        self.cur = dict(name=name, spec=sp_, tpos=tp, shooter=shooter.id, target=target.id, weapon=WEAPON[sp_["weapon"]], pre=WEAPON[sp_["pre"] or sp_["weapon"]],
                        pitch=pitch, yaw=yaw, frame=-30, dist=dist, rows=[])
        minqlx.set_bot_input(shooter.id, 0, 0, 0, 0, self.cur["pre"], pitch, yaw)
        minqlx.set_bot_input(target.id, 0, 0, 0, 0, 2, 0.0, lyaw + 180.0)

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
        sp_ = c["spec"]
        if f < 0:                                               # settle, weapon up, keep both still
            if f == -10:
                for p in (shooter, target):
                    p.health = 200 if p is shooter else int(sp_.get("thp", 200))
                    p.armor = 0
                    p.velocity(reset=True)
                tgt = self.player(c["target"])
                if tgt is not None:
                    tgt.position(x=c["tpos"][0], y=c["tpos"][1], z=c["tpos"][2])
            if f == -2 and float(sp_.get("air", 0.0)) > 0:    # (set 6) the target lifted and let go: in the air at the shot
                tgt = self.player(c["target"])
                if tgt is not None:
                    tgt.position(x=c["tpos"][0], y=c["tpos"][1], z=c["tpos"][2] + float(sp_["air"]))
                    tgt.velocity(reset=True)
            minqlx.set_bot_input(c["shooter"], 0, 0, 0, 0, c["pre"], c["pitch"], c["yaw"])
            return
        firing = f < sp_["hold"]
        wsel = c["pre"] if f < sp_.get("pf", 0) else c["weapon"]     # (set 5) the first pf frames fire the pre weapon, then the switch
        minqlx.set_bot_input(c["shooter"], 0, 0, 0, 1 if firing else 0, wsel, c["pitch"], c["yaw"])
        row = [f]
        for pid in (c["shooter"], c["target"]):
            st = minqlx.player_state(pid)
            row += [st.health, st.armor, *[round(v, 2) for v in st.position], *[round(v, 2) for v in st.velocity]]
        c["rows"].append(row)
        row.append(int(minqlx.player_state(c["shooter"]).weapon))
        c.setdefault("missiles", []).append([[int(m_[0]), int(m_[2])] + [round(float(v_), 1) for v_ in m_[3:9]] for m_ in minqlx.missiles()])
        if sp_["pin"]:                                          # keep the target in the line of fire
            tgt = self.player(c["target"])
            if tgt is not None:
                tgt.position(x=c["tpos"][0], y=c["tpos"][1], z=c["tpos"][2])
                tgt.velocity(reset=True)
        if f >= sp_["frames"]:
            rec = dict(test=c["name"], rep=c["rep"], dist=c["dist"], pitch=round(c["pitch"], 3), yaw=round(c["yaw"], 3),
                       spec=sp_,
                       cols="frame s_hp s_armor s_x s_y s_z s_vx s_vy s_vz t_hp t_armor t_x t_y t_z t_vx t_vy t_vz s_weapon",
                       rows=c["rows"], missile_cols="entity weapon x y z vx vy vz (a list a frame)", missiles=c.get("missiles", []))
            with open(os.path.join(D, "weaponlab.jsonl"), "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            self.log("{} rep {}: target hp {} -> {}, shooter hp {} -> {}".format(
                c["name"], c["rep"], c["rows"][0][9], min(r[9] for r in c["rows"]), c["rows"][0][1],
                min(r[1] for r in c["rows"])))
            minqlx.set_bot_input(c["shooter"], 0, 0, 0, 0, c["weapon"], c["pitch"], c["yaw"])
            self.cur = None
