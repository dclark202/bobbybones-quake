"""physlab: measure Quake Live's player movement so the duel simulator can be checked against it (B-258).

One fully controlled bot (set_bot_input, human physics: three moves a frame, as the plugins play) runs scripted
movement cases on the test map: forward held in the air from 0 to 700 u/s; the wish direction held at a fixed angle to
the velocity in the air (forward + strafe, strafe alone, forward alone: the strafe curve); turning at a fixed rate in the
air; strafe-jump chains with the jump held (a fixed angle to the velocity, the angle that is best in Quake 3, a fixed
turn rate from each take-off); landings and the frame of the next jump (held through the landing, or pressed 1 to 6
frames after it); short hops with forward held; walking from a stand, friction, crouching, circle strafing on the
floor; the ramps-and-stairs course and the climb (step and chain jumps). Every frame's state and input is recorded so
that the simulator replays exactly the same commands from the same start (tools/phys_sim.py, tools/phys_compare.py).

At the start it writes the game's movement cvars (pmove_*, g_gravity, g_speed) to physlab_cvars.json.
PHYSLAB_REPS=<n> repetitions (default 2); PHYSLAB_ONLY=<a part of the case names>; PHYSLAB_FACTORY=ffa|duel.
Load with QLX_PLUGINS="botctl, physlab". Writes /tmp/practice/physlab.jsonl (one line a case) and physlab.log.
Private servers only.
"""
import json
import math
import os
import time

import minqlx

D = "/tmp/practice"
MAP = "testlab"
WEAPON = 2
SETTLE = 40                 # frames before a case: placed, still
PLACE_AT = (-40, -12)       # frames of the settle at which he is put on his start place again
CVARS = ["pmove_AirAccel", "pmove_AirControl", "pmove_AirStepFriction", "pmove_AirSteps", "pmove_AirStopAccel",
         "pmove_AutoHop", "pmove_BunnyHop", "pmove_ChainJump", "pmove_ChainJumpVelocity", "pmove_CircleStrafeFriction",
         "pmove_CrouchSlide", "pmove_CrouchSlideFriction", "pmove_CrouchSlideTime", "pmove_CrouchStepJump",
         "pmove_DoubleJump", "pmove_JumpTimeDeltaMin", "pmove_JumpVelocity", "pmove_JumpVelocityMax",
         "pmove_JumpVelocityScaleAdd", "pmove_JumpVelocityTimeThreshold", "pmove_JumpVelocityTimeThresholdOffset",
         "pmove_RampJump", "pmove_RampJumpScale", "pmove_StepHeight", "pmove_StepJump", "pmove_StepJumpVelocity",
         "pmove_StrafeAccel", "pmove_WalkAccel", "pmove_WalkFriction", "pmove_WaterSwimScale", "pmove_WaterWadeScale",
         "pmove_WeaponDropTime", "pmove_WeaponRaiseTime", "pmove_WishSpeed", "pmove_noPlayerClip", "pmove_velocity_gh",
         "g_gravity", "g_speed", "g_knockback", "sv_fps", "g_factory", "g_gametype", "pmove_fixed", "pmove_msec"]

# start places (resting origin) on testlab
AIM = (160.0, 820.0, 24.125)          # the aim box (1536 x 1024, 400 high): air cases, curving to the right (-y)
STRAIGHT = (200.0, 6256.0, 24.125)    # the speed straight (20480 x 512): hop chains along +x
RAMPS = (64.0, 14256.0, 24.125)       # the ramps and stairs course, along +x
CLIMB = (64.0, 36256.0, 24.125)       # the climb (eighteen ledges of 40), along +x
AIMC = (768.0, 512.0, 24.125)         # the middle of the aim box: circle strafing on the floor


def grid():
    out = []

    def add(name, place, v=(0.0, 0.0, 0.0), frames=46, **ctrl):
        out.append(dict(name=name, place=place, v=list(v), frames=frames, **ctrl))

    # A. forward (or nothing, or back) held in the air, launched straight up at 400 with horizontal speed s along the view
    for s in (0, 100, 200, 280, 320, 360, 400, 450, 500, 600, 700):
        add("air_f_v{}".format(s), AIM, (s, 0, 400), keys=(127, 0, 0))
    for s in (320, 500, 700):
        add("air_none_v{}".format(s), AIM, (s, 0, 400), keys=(0, 0, 0))
    for s in (320, 600):
        add("air_back_v{}".format(s), AIM, (s, 0, 400), keys=(-127, 0, 0))
    # B. the wish direction at phi degrees to the right of the velocity, held so every frame (the strafe curve)
    for s in (320, 500, 700):
        for phi in (0, 20, 40, 50, 60, 70, 80, 90, 100, 120):
            add("air_fr_v{}_phi{}".format(s, phi), AIM, (s, 0, 400), keys=(127, 127, 0), phi=phi)
        for phi in (30, 60, 80, 90, 100, 120):
            add("air_r_v{}_phi{}".format(s, phi), AIM, (s, 0, 400), keys=(0, 127, 0), phi=phi)
    for phi in (20, 45, 70, 90):
        add("air_f_v500_phi{}".format(phi), AIM, (500, 0, 400), keys=(127, 0, 0), phi=phi)
    # C. turning right at a fixed rate in the air from a view along the velocity
    for w in (90, 180, 360):
        add("air_rturn_v400_w{}".format(w), AIM, (400, 0, 400), keys=(0, 127, 0), turn=-w)
        add("air_frturn_v400_w{}".format(w), AIM, (400, 0, 400), keys=(127, 127, 0), turn=-w, yaw_off=45)
    # D. strafe-jump chains on the straight, jump held, from 320 on the floor; sides swap at every take-off
    for phi in (20, 30, 40, 50, 60, 70, 80, 90):
        add("hop_phi{}".format(phi), STRAIGHT, (320, 0, 0), frames=160, keys=(127, 127, 127), phi=phi, flip=True)
    add("hop_opt", STRAIGHT, (320, 0, 0), frames=160, keys=(127, 127, 127), phi="opt", flip=True)
    add("hop_opt_v0", STRAIGHT, (0, 0, 0), frames=160, keys=(127, 127, 127), phi="opt", flip=True)
    for w in (60, 120, 180, 240, 360):
        add("hop_rate_w{}".format(w), STRAIGHT, (320, 0, 0), frames=160, keys=(127, 127, 127), rate=w, a0=20, flip=True)
    # E. a landing and the next jump: held through it (k0), or pressed k frames after the landing is seen (k1..k6)
    for s in (400, 600):
        for kk, keys in (("none", (0, 0)), ("f", (127, 0))):
            for k in (0, 1, 2, 3, 4, 6):
                add("land_{}_v{}_k{}".format(kk, s, k), STRAIGHT, (s, 0, 275), frames=64, keys=(keys[0], keys[1], 0), land_k=k)
    # F. on the floor
    add("hops_f_v0", STRAIGHT, (0, 0, 0), frames=120, keys=(127, 0, 127))
    add("hops_f_v320", STRAIGHT, (320, 0, 0), frames=120, keys=(127, 0, 127))
    add("hops_fr_v0", STRAIGHT, (0, 0, 0), frames=120, keys=(127, 127, 127))
    add("walk_f_v0", STRAIGHT, (0, 0, 0), frames=60, keys=(127, 0, 0))
    add("walk_fr_v0", STRAIGHT, (0, 0, 0), frames=60, keys=(127, 127, 0))
    for s in (320, 600):
        add("stop_v{}".format(s), STRAIGHT, (s, 0, 0), frames=48, keys=(0, 0, 0))
    add("crouch_f_v500", STRAIGHT, (500, 0, 0), frames=48, keys=(127, 0, -127))
    add("crouch_none_v500", STRAIGHT, (500, 0, 0), frames=48, keys=(0, 0, -127))
    for w in (90, 180):
        add("circle_w{}".format(w), AIMC, (320, 0, 0), frames=80, keys=(127, 127, 0), turn=-w, yaw_off=45)
    add("side_v0", AIMC, (0, 0, 0), frames=40, keys=(0, 127, 0))
    # G. the ramps and stairs course and the climb, forward held
    for s in (320, 500):
        add("ramps_hop_v{}".format(s), RAMPS, (s, 0, 0), frames=200, keys=(127, 0, 127))
    add("ramps_run_v320", RAMPS, (320, 0, 0), frames=200, keys=(127, 0, 0))
    add("climb_hop_v320", CLIMB, (320, 0, 0), frames=200, keys=(127, 0, 127))
    add("climb_hop_v0", CLIMB, (0, 0, 0), frames=200, keys=(127, 0, 127))
    # H. (2026-10-16) more: forward held on the floor above running speed, the walk key in the air, a jump a frame late
    add("run_f_v600", STRAIGHT, (600, 0, 0), frames=40, keys=(127, 0, 0))
    add("air_walk_v400", AIM, (400, 0, 400), keys=(64, 0, 0))
    add("air_walk_v200", AIM, (200, 0, 400), keys=(64, 0, 0))
    add("air_fl_v500_phi0", AIM, (500, 0, 400), keys=(127, -127, 0), phi=0)
    return out


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


def vdir(vx, vy):
    return math.degrees(math.atan2(vy, vx))


def wish_off(keys):
    """the wish direction's angle to the view for these keys (degrees, positive to the left)"""
    fw, sd = keys[0], keys[1]
    if fw == 0 and sd == 0:
        return 0.0
    return math.degrees(math.atan2(-sd, fw))


def opt_phi(speed):
    """Quake 3's best angle between the wish direction and the velocity at this speed (320 wish, accel 1, 8 ms)"""
    a = 320.0 - 320.0 * 1.0 * 0.008
    if speed <= a:
        return 0.0
    return math.degrees(math.acos(a / speed))


class physlab(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        reps = int(os.environ.get("PHYSLAB_REPS", "2"))
        only = os.environ.get("PHYSLAB_ONLY", "")
        self.factory = os.environ.get("PHYSLAB_FACTORY", "ffa")
        cases = [c for c in grid() if only in c["name"]]
        self.queue = [(dict(cases[0], name="warmup"), -1)] + [(c, r) for r in range(reps) for c in cases]
        self.cur = None
        self.next_check = 0.0
        self.done_said = False
        self.cvars_done = False
        self.log("{} cases ({} reps)".format(len(cases), reps))

    def log(self, msg):
        minqlx.console_print("[physlab] " + msg + "\n")
        os.makedirs(D, exist_ok=True)
        with open(os.path.join(D, "physlab.log"), "a") as f:
            f.write("{} {}\n".format(time.strftime("%H:%M:%S"), msg))

    def bot(self):
        for p in self.players():
            if is_bot(p) and p.team != "spectator":
                return p
        return None

    def dump_cvars(self):
        vals = {k: minqlx.get_cvar(k) for k in CVARS}
        with open(os.path.join(D, "physlab_cvars.json"), "a") as f:
            f.write(json.dumps(dict(factory=self.factory, time=time.strftime("%H:%M:%S"), cvars=vals)) + "\n")
        self.log("cvars: " + " ".join("{}={}".format(k, v) for k, v in vals.items()))

    def control(self, c, st, f):
        """this frame's [forward, right, up] and view yaw, from the state read now (closed loop where the case asks)"""
        case = c["case"]
        fw, sd, up = case["keys"]
        vx, vy, vz = (float(v) for v in st.velocity)
        sp = math.hypot(vx, vy)
        ground = abs(vz) < 1e-3 and c["prev_vz"] is not None and c["prev_vz"] <= 1e-3
        takeoff = vz > 100.0 and c["prev_vz"] is not None and c["prev_vz"] <= 1e-3
        c["prev_vz"] = vz
        if takeoff:
            c["hops"] += 1
            if case.get("flip"):
                c["side"] = -c["side"]
        side = c["side"]
        sd = sd * side
        yaw = c["yaw"]
        if "phi" in case and sp > 1.0:
            phi = opt_phi(sp) if case["phi"] == "opt" else float(case["phi"])
            # the wish direction phi to the strafe side of the velocity: view = velocity dir - side*phi - the keys' angle
            yaw = vdir(vx, vy) - side * phi - wish_off((fw, sd))
        elif "rate" in case:
            if takeoff or f == 0:
                c["yaw_base"] = (vdir(vx, vy) if sp > 1.0 else c["yaw"]) - side * case["a0"] - wish_off((fw, sd))
                c["t_hop"] = 0
            yaw = c["yaw_base"] - side * case["rate"] * c["t_hop"] * 0.025
            c["t_hop"] += 1
        elif "turn" in case:
            yaw = c["yaw0"] + case["turn"] * f * 0.025
        if "land_k" in case:
            k = case["land_k"]
            if c["land_f"] is None and f > 2 and ground:
                c["land_f"] = f
            up = 0
            if k == 0:
                up = 127
            elif c["land_f"] is not None and c["land_f"] + k - 1 <= f < c["land_f"] + k + 1:
                up = 127                                     # pressed for two frames
        c["yaw"] = yaw
        return int(fw), int(sd), int(up), yaw

    def on_frame(self):
        now = time.time()
        if (minqlx.get_cvar("mapname") or "").lower() != MAP:
            if now > self.next_check:
                self.next_check = now + 15
                minqlx.console_command("map {} {}".format(MAP, self.factory))
            return
        if not self.cvars_done:
            self.cvars_done = True
            self.dump_cvars()
        b = self.bot()
        if b is None:
            if now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("addbot sarge 1")
            return
        try:
            hc = str(b["handicap"])
        except Exception:  # noqa: BLE001
            hc = "?"
        if hc != "100":
            if now > self.next_check:
                self.next_check = now + 3
                self.log("bot handicap {}: set to 100".format(hc))
                b.handicap = 100
            return
        # PHYSLAB_AUTOHOP=1: the client setting a person's game sends (cg_autoHop, in the userinfo) put in the bot's:
        # without it the server's pmove_AutoHop does not re-jump a held jump for him
        ah = os.environ.get("PHYSLAB_AUTOHOP", "")
        if ah and str(b.cvars.get("cg_autoHop", "")) != ah:
            if now > self.next_check:
                self.next_check = now + 3
                cv = b.cvars
                cv["cg_autoHop"] = ah
                b.cvars = cv
                self.log("bot userinfo cg_autoHop set to {} (keys: {})".format(ah, ",".join(sorted(cv))))
            return
        c = self.cur
        if c is None:
            if not self.queue:
                if not self.done_said:
                    self.done_said = True
                    self.log("all cases done")
                return
            if not (b.state and b.state.health > 0):
                return
            case, rep = self.queue.pop(0)
            sx, sy, sz = case["v"]
            sp = math.hypot(sx, sy)
            yaw0 = 0.0
            if "phi" in case and sp > 1.0:
                phi = opt_phi(sp) if case["phi"] == "opt" else float(case["phi"])
                yaw0 = -phi - wish_off(case["keys"])
            elif "rate" in case:
                yaw0 = -case["a0"] - wish_off(case["keys"])
            yaw0 += case.get("yaw_off", 0.0)
            # the start velocity is along +x (yaw 0), the view at yaw0
            self.cur = c = dict(case=case, rep=rep, frame=-SETTLE, rows=[], ins=[], yaw0=yaw0, yaw=yaw0, prev_vz=None,
                                side=1, hops=0, land_f=None, t_hop=0, yaw_base=yaw0)
            minqlx.set_bot_substeps(b.id, 3)
            self.place(b, case)
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, WEAPON, 0.0, yaw0)
            return
        case = c["case"]
        f = c["frame"]
        st = minqlx.player_state(b.id)
        if f in PLACE_AT:
            self.place(b, case)
        if f < 0:
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, WEAPON, 0.0, c["yaw0"])
            c["frame"] += 1
            return
        if f == 0:                                           # the start: his resting place, the case's velocity
            pos = [float(v) for v in st.position]
            c["start"] = pos
            c["start_vel"] = [float(v) for v in case["v"]]
            c["rest_vel"] = [round(float(v), 3) for v in st.velocity]
            b.velocity(x=float(case["v"][0]), y=float(case["v"][1]), z=float(case["v"][2]))
            st = minqlx.player_state(b.id)
            c["prev_vz"] = 0.0
        uc = minqlx.ran_usercmd(b.id)
        va = minqlx.view_angles(b.id)
        c["rows"].append([f, *[round(float(v), 4) for v in st.position], *[round(float(v), 4) for v in st.velocity],
                          round(float(va[1]), 4), int(uc[0])])
        if f >= case["frames"]:
            rec = dict(map=MAP, rep=c["rep"], **{k: v for k, v in case.items()},
                       cols="rows: hook x y z vx vy vz view_yaw cmd_time (the state at hook f is after the input of frame "
                            "f-1; row 0 is after the start velocity was set); ins: frame fwd right up yaw (the yaw asked)",
                       start=c["start"], start_vel=c["start_vel"], rest_vel=c["rest_vel"], yaw0=c["yaw0"],
                       hops=c["hops"], land_f=c["land_f"], rows=c["rows"], ins=c["ins"])
            rec["autohop"] = os.environ.get("PHYSLAB_AUTOHOP", "")
            with open(os.path.join(D, "physlab{}.jsonl".format(os.environ.get("PHYSLAB_TAG", ""))), "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            r0, r1 = c["rows"][0], c["rows"][-1]
            self.log("{} rep {} ({} left): speed {:.1f} -> {:.1f}, moved {:.0f}, hops {}".format(
                case["name"], c["rep"], len(self.queue), math.hypot(r0[4], r0[5]), math.hypot(r1[4], r1[5]),
                math.hypot(r1[1] - r0[1], r1[2] - r0[2]), c["hops"]))
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, WEAPON, 0.0, c["yaw"])
            self.cur = None
            return
        fw, sd, up, yaw = self.control(c, st, f)
        c["ins"].append([f, fw, sd, up, round(yaw, 4)])
        minqlx.set_bot_input(b.id, fw, sd, up, 0, WEAPON, 0.0, yaw)
        c["frame"] += 1

    def place(self, b, case):
        x, y, z = case["place"]
        b.position(x=x, y=y, z=z)
        b.velocity(reset=True)
        b.health = 100
        b.armor = 0
