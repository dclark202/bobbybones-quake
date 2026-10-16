"""rjlab: measure Quake Live's rocket jump so the duel simulator can be checked against it (B-252).

One fully controlled bot (set_bot_input, human physics: three moves a frame) does scripted rocket jumps on a grid:
look-down 45 to 90 degrees by 5; the shot on the jump's frame, 1 to 4 frames after, or standing (no jump); no key,
the forward key or a strafe key held from the jump on; on open flat floor and facing a wall close by; at 100 health
with no armor, and with armor. Every frame of the next 2 s is recorded: place, speed, health, armor, his view and his
rocket. The inputs of every frame are in the record, so that the simulator replays exactly them
(the scratch rj_sim.py of 2026-10-15; results entry of that day).

RJLAB_MAP=testlab (default) or bloodrun; RJLAB_REPS=<n> repetitions of the grid (default 2); RJLAB_ONLY=<a part of the case names>.
Load with QLX_PLUGINS="botctl, rjlab". Writes /tmp/practice/rjlab.jsonl (one line a jump) and rjlab.log.
Private servers only.
"""
import json
import math
import os
import time

import minqlx

D = "/tmp/practice"
RL = 5
SETTLE = 40                 # frames before a jump: weapon up, placed, still
PLACE_AT = -12              # the frame of the settle at which he is put on his place again, health and armor set
FRAMES = 80                 # frames recorded from the first input on (2 s)
PITCHES = [45, 50, 55, 60, 65, 70, 75, 80, 85, 90]
KEYS = {"none": (0, 0), "fwd": (127, 0), "right": (0, 127), "run": (127, 0)}
RUN_FROM = -24              # "run": the forward key from this frame of the settle on (a run-up of 0.6 s to full speed)
RUN_PLACE_AT = -30          # ... and he is placed this early

# start places (resting origin), facing; found with the simulator's traces (the scratch spots.py / scan.py)
#   testlab "open": the flat top of the long straight (no wall within 1500 units, nothing above for 2000)
#   testlab "wall": the aim room's west wall 45 units in front of him (ceiling 344 above his origin)
#   bloodrun "open": the pros' take-off by the rockets (673, -1048), ceiling 712, facing their landing (446, -1304)
#   bloodrun "wall": the pros' take-off below the red armor's ledge (203, -391), walls 30 to 42 units to the south
PLACES = {
    "testlab": {"open": ((10000.0, 6256.0, 312.6), 0.0), "wall": ((60.0, 3768.0, 24.6), 180.0)},
    "bloodrun": {"open": ((673.0, -1048.0, 88.6), math.degrees(math.atan2(-1304 + 1048, 446 - 673))),
                 "wall": ((203.0, -391.0, 88.6), math.degrees(math.atan2(-460 + 391, -304 - 203)))},
}


def grid(mapname):
    out = []

    def add(place, pitch, fire, keys, hp=100, armor=0, shot=True):
        out.append(dict(name="{}_p{}_{}_{}_h{}a{}{}".format(place, pitch, "st" if fire is None else "f{}".format(fire), keys, hp, armor,
                                                            "" if shot else "_noshot"),
                        place=place, pitch=float(pitch), fire=fire, keys=keys, hp=hp, armor=armor, shot=shot))
    # no shot at all: what health and armor do by themselves over the record (the game's rot, see on_frame)
    add("open", 90, None, "none", 100, 100, shot=False)
    add("open", 90, 0, "none", 60, 50, shot=False)
    if mapname == "testlab":
        for p in PITCHES:
            for f in (None, 0, 1, 2, 3, 4):
                for k in ("none", "fwd", "right"):
                    add("open", p, f, k)
        for p in PITCHES:
            for f in (None, 0, 2):
                add("wall", p, f, "none")
        for p in (50, 60, 70, 80, 90):            # a run-up (the pros jump running): the forward key from RUN_FROM
            for f in (None, 0, 2):
                add("open", p, f, "run")
        for hp, ar in ((100, 100), (50, 25)):
            for p in (50, 70, 90):
                for f in (None, 0, 2):
                    add("open", p, f, "none", hp, ar)
    else:
        for p in (45, 55, 65, 75, 85, 90):
            for f in (None, 0, 2):
                for k in ("none", "fwd"):
                    add("open", p, f, k)
        for p in (50, 70, 90):
            for f in (None, 0, 2):
                add("wall", p, f, "none")
    return out


def inputs(case):
    """per frame from 0: [forward, right, up, buttons]"""
    fw, sd = KEYS[case["keys"]]
    f = case["fire"]
    rows = []
    for k in range(FRAMES):
        jump = 127 if (f is not None and k == 0) else 0
        fire = 1 if (case.get("shot", True) and k == (0 if f is None else f)) else 0
        rows.append([fw, sd, jump, fire])
    return rows


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class rjlab(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.map = os.environ.get("RJLAB_MAP", "testlab").lower()
        reps = int(os.environ.get("RJLAB_REPS", "2"))
        only = os.environ.get("RJLAB_ONLY", "")
        cases = [c for c in grid(self.map) if only in c["name"]]
        # a first throw-away jump (the first case of a lab tends to carry setup glitches), then the grid rep by rep
        self.queue = [(dict(cases[0], name="warmup"), -1)] + [(c, r) for r in range(reps) for c in cases]
        self.total = len(self.queue)
        self.cur = None
        self.next_check = 0.0
        self.done_said = False
        self.log("{} cases on {} ({} reps)".format(len(cases), self.map, reps))

    def log(self, msg):
        minqlx.console_print("[rjlab] " + msg + "\n")
        os.makedirs(D, exist_ok=True)
        with open(os.path.join(D, "rjlab.log"), "a") as f:
            f.write("{} {}\n".format(time.strftime("%H:%M:%S"), msg))

    def bot(self):
        for p in self.players():
            if is_bot(p) and p.team != "spectator":
                return p
        return None

    def arm(self, b):
        b.weapons(g=True, mg=True, rl=True)
        b.ammo(mg=100, rl=50)

    def place(self, b, c):
        pos, yaw = PLACES[self.map][c["place"]]
        b.position(x=pos[0], y=pos[1], z=pos[2])
        b.velocity(reset=True)
        b.health = int(c["hp"])
        b.armor = int(c["armor"])

    def on_frame(self):
        now = time.time()
        if (minqlx.get_cvar("mapname") or "").lower() != self.map:
            if now > self.next_check:
                self.next_check = now + 15
                minqlx.console_command("map {} ffa".format(self.map))
            return
        b = self.bot()
        if b is None:
            if now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("addbot sarge 1")
            return
        # the game's bots join with a handicap (sarge at skill 1: 50), which is their most health: health and armor
        # above it fall by one a second (the rot) and the jumps' numbers with them. Set to 100 as a person's.
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
        c = self.cur
        if c is None:
            if not self.queue:
                if not self.done_said:
                    self.done_said = True
                    self.log("all jumps done")
                return
            if not (b.state and b.state.health > 0):
                return
            case, rep = self.queue.pop(0)
            pos, yaw = PLACES[self.map][case["place"]]
            self.cur = c = dict(case=case, rep=rep, yaw=yaw, frame=-SETTLE, rows=[], inputs=inputs(case))
            minqlx.set_bot_substeps(b.id, 3)
            self.arm(b)
            self.place(b, case)
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, RL, case["pitch"], yaw)
            return
        case = c["case"]
        f = c["frame"]
        st = minqlx.player_state(b.id)
        if f == (RUN_PLACE_AT if case["keys"] == "run" else PLACE_AT):
            self.arm(b)
            self.place(b, case)
        if f < 0:
            inp = [127, 0, 0, 0] if (case["keys"] == "run" and f >= RUN_FROM) else [0, 0, 0, 0]
        elif f < FRAMES:
            inp = c["inputs"][f]
        else:
            inp = [0, 0, 0, 0]
        if f >= -3:                                  # the state as read now: after the previous frame's move
            va = minqlx.view_angles(b.id)
            rk = [[round(float(v), 1) for v in m[3:9]] for m in minqlx.missiles() if int(m[1]) == b.id]
            c["rows"].append([f, st.health, st.armor, *[round(float(v), 2) for v in st.position],
                              *[round(float(v), 2) for v in st.velocity], round(float(va[0]), 2), round(float(va[1]), 2),
                              int(st.weapon), rk[0] if rk else None])
        if f >= FRAMES:
            rec = dict(map=self.map, rep=c["rep"], yaw=round(c["yaw"], 3), **case,
                       cols="hook hp armor x y z vx vy vz view_pitch view_yaw weapon rocket[x y z vx vy vz]; the state at hook f "
                            "is after the input of frame f-1",
                       start=list(PLACES[self.map][case["place"]][0]), inputs=c["inputs"], rows=c["rows"])
            with open(os.path.join(D, "rjlab.jsonl"), "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            r0 = c["rows"][3] if len(c["rows"]) > 3 else c["rows"][0]
            zmax = max(r[5] for r in c["rows"])
            self.log("{} rep {} ({} left): hp {} -> {}, armor {} -> {}, rise {:.0f}".format(
                case["name"], c["rep"], len(self.queue), r0[1], min(r[1] for r in c["rows"]), r0[2],
                min(r[2] for r in c["rows"]), zmax - r0[5]))
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, RL, case["pitch"], c["yaw"])
            self.cur = None
            return
        minqlx.set_bot_input(b.id, int(inp[0]), int(inp[1]), int(inp[2]), int(inp[3]), RL, case["pitch"], c["yaw"])
        c["frame"] += 1
