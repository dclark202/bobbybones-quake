"""Probe plugin: read game state and drive a bot's inputs from Python."""
import math
import time

import minqlx

BUTTON_ATTACK = 1


class botctl(minqlx.Plugin):
    def __init__(self):
        self.add_command("probe", self.cmd_probe, permission=5)
        self.add_command("drive", self.cmd_drive, usage="<client_id> <test|aim|strafe>", permission=5)
        self.add_command("release", self.cmd_release, usage="<client_id>", permission=5)
        self.add_command("range", self.cmd_range, usage="<shooter_id> <target_id>", permission=5)
        self.add_command("items", self.cmd_items, permission=5)
        self.add_command("follow", self.cmd_follow, usage="<spectator_id> <target_id>", permission=5)
        self.add_hook("player_loaded", self.on_player_loaded)
        self.add_command("autospec", self.cmd_autospec, usage="<on|off>", permission=5)
        self.add_command("record", self.cmd_record, usage="<on|off>", permission=5)
        self.add_hook("frame", self.on_frame)
        self.recording = False
        self.hits = []
        self.hist = {}
        self.driving = {}  # client_id -> (mode, start_time)
        self.log_next = 0

    def log(self, msg):
        minqlx.console_print(msg + "\n")

    def cmd_probe(self, player, msg, channel):
        for p in self.players():
            s = p.state
            self.log("probe id={} name={} pos={} vel={} hp={} ar={} wp={} rg_ammo={} angles={} cmd={}".format(
                p.id, p.clean_name, fmt(s.position), fmt(s.velocity), s.health, s.armor, s.weapon, s.ammo.rg,
                fmt(minqlx.view_angles(p.id)), minqlx.last_usercmd(p.id)))

    def cmd_items(self, player, msg, channel):
        level_time, items = minqlx.item_states()
        with open("/tmp/items.txt", "w") as f:
            for num, cls, x, y, z, avail, nextthink in items:
                eta = "" if avail else " respawn_in={:.1f}s".format((nextthink - level_time) / 1000)
                line = "item {} {} at ({:.0f},{:.0f},{:.0f}) {}{}".format(
                    num, cls, x, y, z, "UP" if avail else "taken", eta)
                f.write(line + "\n")
                self.log(line)

    def cmd_autospec(self, player, msg, channel):
        self.autospec = len(msg) > 1 and msg[1] == "on"
        self.log("autospec={}".format(self.autospec))

    def on_player_loaded(self, player):
        # humans who join become spectators locked onto the practicing bot (client 0)
        if str(player.steam_id).startswith("9007199") or not getattr(self, "autospec", True):
            return
        self.spectate_bot(player.id)

    @minqlx.delay(2)
    def spectate_bot(self, cid):
        p = self.player(cid)
        if p is None:
            return
        if p.team != "spectator":
            p.put("spectator")
        minqlx.client_command(cid, "follow 0")

    def cmd_follow(self, player, msg, channel):
        # !follow <spectator_id> <target_id>: make a human client spectate a bot in first person
        sid, tid = int(msg[1]), int(msg[2])
        p = self.player(sid)
        if p.team != "spectator":
            p.put("spectator")
        minqlx.client_command(sid, "follow {}".format(tid))
        self.log("client {} now following {}".format(sid, tid))

    def cmd_record(self, player, msg, channel):
        # Record every player's position each frame to /tmp/trace.txt (builds a walkable-space map).
        self.recording = msg[1] == "on" if len(msg) > 1 else True
        self.log("recording={}".format(self.recording))

    def cmd_drive(self, player, msg, channel):
        cid, mode = int(msg[1]), msg[2] if len(msg) > 2 else "test"
        self.driving[cid] = (mode, time.time())
        self.log("driving {} mode={}".format(cid, mode))

    def cmd_range(self, player, msg, channel):
        # Shooting range: pick two points on a straight stretch of the shooter's recent path
        # (guaranteed open space with line of sight), freeze the target, give the shooter a railgun.
        shooter, target = int(msg[1]), int(msg[2])
        pts = [p for _, p in self.hist.get(shooter, [])]
        cur = pts[-1] if pts else None
        far = None
        for i in range(len(pts) - 1, -1, -1):
            d = dist(pts[i], cur)
            if d < 250 or abs(pts[i][2] - cur[2]) > 40:
                continue
            if all(line_dev(pts[j], pts[i], cur) < 24 for j in range(i, len(pts))):
                far = pts[i]
                break
        if far is None:
            self.log("range: no straight stretch in recent path yet, try again")
            return
        ps, pt = self.player(shooter), self.player(target)
        ps.position(x=far[0], y=far[1], z=far[2] + 4)
        pt.position(x=cur[0], y=cur[1], z=cur[2] + 4)
        ps.velocity(reset=True)
        pt.velocity(reset=True)
        ps.weapons(reset=True, g=True, rg=True)
        ps.ammo(rg=100)
        ps.weapon("rg")
        pt.health = 5000
        self.range_target, self.range_hp, self.hits = target, 5000, []
        self.driving[target] = ("idle", time.time())
        self.driving[shooter] = ("aim", time.time())
        self.log("range set up shooter={} target={} distance={:.0f}".format(shooter, target, dist(far, cur)))

    def cmd_release(self, player, msg, channel):
        cid = int(msg[1])
        self.driving.pop(cid, None)
        minqlx.clear_bot_input(cid)
        self.log("released {}".format(cid))

    def on_frame(self):
        now = time.time()
        if self.recording:
            self.rec_frame = getattr(self, "rec_frame", 0) + 1
            # one recording per map; last column = steam id (per-player profiles)
            path = "/tmp/practice/trace_live_{}.txt".format((minqlx.get_cvar("mapname") or "unknown").lower())
            with open(path, "a") as f:
                for p in self.players():
                    s = p.state
                    if s.is_alive or s.health > 0:
                        cmd = minqlx.last_usercmd(p.id)
                        f.write("{} {} {:.1f} {:.1f} {:.1f} {:.1f} {:.1f} {:.1f} {} {} {} {}\n".format(
                            self.rec_frame, p.id, *s.position, *s.velocity, s.weapon, cmd[1], s.health, p.steam_id))
        for p in self.players():
            h = self.hist.setdefault(p.id, [])
            h.append((now, tuple(p.state.position)))
            while h and now - h[0][0] > 3:
                h.pop(0)
        rt = getattr(self, "range_target", None)
        if rt is not None:
            hp = minqlx.player_state(rt).health
            if hp < self.range_hp - 5:
                self.hits.append(self.range_hp - hp)
                self.log("hit #{} dmg={} target_hp={}".format(len(self.hits), self.range_hp - hp, hp))
            self.range_hp = hp
        for cid, (mode, t0) in list(self.driving.items()):
            t = now - t0
            if mode == "test":
                self.drive_test(cid, t)
            elif mode == "aim":
                self.drive_aim(cid)
            elif mode == "idle":
                minqlx.set_bot_input(cid, 0, 0, 0, 0, 0, 0.0, 0.0)
            elif mode == "strafe":
                self.drive_strafe(cid, t)
            elif mode.startswith("air"):
                self.drive_airtest(cid, t, mode)
            if now >= self.log_next:
                s = minqlx.player_state(cid)
                self.log("drive t={:.1f} pos={} vel={} speed={:.0f} peak={:.0f} angles={} wp={}".format(
                    t, fmt(s.position), fmt(s.velocity), math.hypot(s.velocity[0], s.velocity[1]), getattr(self, "peak", 0),
                    fmt(minqlx.view_angles(cid)), s.weapon))
        if now >= self.log_next:
            self.log_next = now + 0.5

    def drive_test(self, cid, t):
        # 0-2s: stand still, yaw 0 | 2-4s: run forward, yaw 90 | 4-6s: jump while running
        # 6-8s: strafe right, yaw 180 | 8-10s: fire, pitch -30 | then stop
        if t < 2:
            minqlx.set_bot_input(cid, 0, 0, 0, 0, 0, 0.0, 0.0)
        elif t < 4:
            minqlx.set_bot_input(cid, 127, 0, 0, 0, 0, 0.0, 90.0)
        elif t < 6:
            minqlx.set_bot_input(cid, 127, 0, 127, 0, 0, 0.0, 90.0)
        elif t < 8:
            minqlx.set_bot_input(cid, 0, 127, 0, 0, 0, 0.0, 180.0)
        elif t < 10:
            minqlx.set_bot_input(cid, 0, 0, 0, BUTTON_ATTACK, 0, -30.0, 180.0)
        else:
            minqlx.set_bot_input(cid, 0, 0, 0, 0, 0, 0.0, 0.0)

    def drive_strafe(self, cid, t):
        # Textbook VQ3-style strafe jump: hold jump, alternate strafe direction each
        # jump, and keep the wish direction at the angle that maximizes air acceleration.
        s = minqlx.player_state(cid)
        vx, vy, vz = s.velocity
        speed = math.hypot(vx, vy)
        self.peak = max(getattr(self, "peak", 0), speed)
        if t < 0.5 or speed < 200:
            # build up ground speed; if blocked by a wall, pick a new direction
            if speed < 50 and t - getattr(self, "last_turn", 0) > 0.4:
                self.yaw0 = self.strafe_yaw0(cid) + 137.0
                self.last_turn = t
            minqlx.set_bot_input(cid, 127, 0, 0, 0, 0, 0.0, self.strafe_yaw0(cid))
            return
        vel_yaw = math.degrees(math.atan2(vy, vx))
        z = s.position[2]
        on_ground = vz == 0 and abs(z - getattr(self, "last_z", z + 1)) < 0.01
        self.last_z = z
        if on_ground and not getattr(self, "was_ground", False):
            self.side = -getattr(self, "side", 1)  # switch strafe side every landing
            self.landings = getattr(self, "landings", []) + [round(speed)]
            self.log("landing #{} speed={:.0f}".format(len(self.landings), speed))
        self.was_ground = on_ground
        # Only press jump on the ground: upmove counts toward PM_CmdScale, so holding it
        # in the air shrinks wishspeed to ~261 and kills air acceleration.
        up = 127 if on_ground else 0
        dt, accel, wishspeed = 0.025, 1.0, 320.0
        theta = math.degrees(math.acos(max(-1.0, min(1.0, (wishspeed - accel * wishspeed * dt) / speed))))
        side = getattr(self, "side", 1)
        # side=1: strafe right (wishdir = view - 45), side=-1: strafe left (wishdir = view + 45)
        view_yaw = vel_yaw - side * theta + side * 45.0
        minqlx.set_bot_input(cid, 127, side * 127, up, 0, 0, 0.0, view_yaw)
        n = getattr(self, "air_logs", 0)
        if n < 60:
            self.air_logs = n + 1
            self.log("air t={:.3f} ground={} speed={:.1f} vz={:.0f} vel_yaw={:.1f} view_yaw={:.1f} actual_yaw={:.1f} side={} up={} cmd={}".format(
                t, on_ground, speed, vz, vel_yaw, view_yaw, minqlx.view_angles(cid)[1], side, up, minqlx.last_usercmd(cid)))

    def drive_airtest(self, cid, t, mode):
        # run 0.5s, jump once, then in the air look 90 degrees left of travel holding forward
        s = minqlx.player_state(cid)
        vx, vy, vz = s.velocity
        yaw0 = self.strafe_yaw0(cid)
        if t < 0.5:
            minqlx.set_bot_input(cid, 127, 0, 0, 0, 0, 0.0, yaw0)
        elif t < 0.55:
            minqlx.set_bot_input(cid, 127, 0, 127, 0, 0, 0.0, yaw0)
        else:
            fwd = 127 if mode == "airfwd" else 0
            right = 127 if mode == "airright" else 0
            minqlx.set_bot_input(cid, fwd, right, 0, 0, 0, 0.0, yaw0 + 90.0)
        if t < 1.4:
            self.log("air t={:.3f} speed={:.1f} vel=({:.1f},{:.1f},{:.0f}) yaw={:.1f} cmd={}".format(
                t, math.hypot(vx, vy), vx, vy, vz, minqlx.view_angles(cid)[1], minqlx.last_usercmd(cid)))

    def strafe_yaw0(self, cid):
        if not hasattr(self, "yaw0"):
            self.yaw0 = minqlx.view_angles(cid)[1]
        return self.yaw0

    def drive_aim(self, cid):
        # Look at the nearest other living player and fire.
        me = minqlx.player_state(cid)
        best = None
        for p in self.players():
            if p.id == cid:
                continue
            s = p.state
            if not s or s.health <= 0:
                continue
            d = [s.position[i] - me.position[i] for i in range(3)]
            d[2] -= 26  # shots leave from eye height
            dist = math.sqrt(sum(x * x for x in d))
            if best is None or dist < best[0]:
                best = (dist, d)
        if best is None:
            minqlx.set_bot_input(cid, 0, 0, 0, 0, 0, 0.0, 0.0)
            return
        dist, d = best
        yaw = math.degrees(math.atan2(d[1], d[0]))
        pitch = -math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
        minqlx.set_bot_input(cid, 0, 0, 0, BUTTON_ATTACK, 0, pitch, yaw)


def fmt(v):
    return "(" + ", ".join("{:.0f}".format(x) for x in v) + ")" if v else str(v)


def dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def line_dev(p, a, b):
    # distance of p from segment a-b in the horizontal plane
    ax, ay, bx, by, px, py = a[0], a[1], b[0], b[1], p[0], p[1]
    l2 = (bx - ax) ** 2 + (by - ay) ** 2
    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l2)) if l2 else 0.0
    return math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay)))
