"""maplab: what the real game puts on a map, mode by mode, to set beside the simulator's own list.

For every map of MAPLAB_MAPS (comma-separated) and every factory of MAPLAB_FACTORIES (default "duel,ffa") the map is
loaded, two bots are added so that the game runs, the warmup is left ("allready") and after MAPLAB_WAIT seconds
(default 6) every item entity is written down: class, where it rests (items are dropped to the floor when they spawn),
whether it is there now and when it comes back; then again MAPLAB_LATE seconds later (default 0 = not), for things that
only appear after a while. Also the cvars that set the rules the simulator copies.

Load with QLX_PLUGINS="botctl, maplab". Writes /tmp/practice/maplab.jsonl (one line per map, factory and reading) and
maplab.log; "all done" in the log marks the end.
"""
import json
import os
import time

import minqlx

D = "/tmp/practice"
MAPS = [m.strip().lower() for m in os.environ.get("MAPLAB_MAPS", "bloodrun").split(",") if m.strip()]
FACTORIES = [f.strip() for f in os.environ.get("MAPLAB_FACTORIES", "duel,ffa").split(",") if f.strip()]
WAIT = float(os.environ.get("MAPLAB_WAIT", "6"))
LATE = float(os.environ.get("MAPLAB_LATE", "0"))
CVARS = ("g_gametype", "g_factory", "sv_fps", "g_gravity", "g_speed", "g_knockback", "g_weaponrespawn", "g_startingWeapons",
         "g_startingHealth", "g_startingArmor", "g_spawnItemPowerup", "g_spawnItemHoldable", "g_spawnItemAmmo",
         "g_ammoPack", "g_ammoRespawn", "g_itemTimers", "pmove_WaterSwimScale", "pmove_WaterWadeScale", "pmove_AutoHop",
         "pmove_JumpVelocity", "pmove_AirControl", "pmove_StepHeight", "g_quadDamageFactor", "g_dropPowerups",
         "g_infiniteAmmo", "dmflags", "g_lavaDamage", "g_slimeDamage", "g_fallDamage")


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class maplab(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.jobs = [(m, f) for m in MAPS for f in FACTORIES]
        self.k = 0
        self.asked = None                                    # the job the map command was last given for
        self.next_check = 0.0
        self.t_live = None
        self.read = 0

    def log(self, msg):
        minqlx.console_print("[maplab] " + msg + "\n")
        with open(os.path.join(D, "maplab.log"), "a") as f:
            f.write("{} {}\n".format(time.strftime("%H:%M:%S"), msg))

    def on_frame(self):
        now = time.time()
        if self.k >= len(self.jobs):
            return
        mp, fac = self.jobs[self.k]
        if self.asked != self.k or (minqlx.get_cvar("mapname") or "").lower() != mp:
            if now > self.next_check:
                self.next_check = now + 20
                self.asked = self.k
                self.t_live, self.read = None, 0
                minqlx.console_command("map {} {}".format(mp, fac))
            return
        bots = [p for p in self.players() if is_bot(p) and p.team != "spectator"]
        if len(bots) < 2:
            if now > self.next_check:
                self.next_check = now + 4
                minqlx.console_command("addbot bones 3")
            return
        state = self.game.state if self.game is not None else None
        if state != "in_progress":
            if state == "warmup" and now > self.next_check:
                self.next_check = now + 12
                self.set_cvar("timelimit", "0")
                self.set_cvar("fraglimit", "0")
                minqlx.console_command("allready")
            return
        if self.t_live is None:
            self.t_live = now
        due = WAIT if self.read == 0 else WAIT + LATE
        if now - self.t_live < due:
            return
        t_ms, items = minqlx.item_states()
        row = dict(map=mp, factory=fac, reading=self.read, seconds_live=round(now - self.t_live, 1), level_ms=int(t_ms),
                   cvars={c: minqlx.get_cvar(c) for c in CVARS},
                   items=[dict(num=int(n), cls=c, at=[round(float(x), 1), round(float(y), 1), round(float(z), 1)], up=bool(up),
                               back_ms=int(b)) for n, c, x, y, z, up, b in items])
        with open(os.path.join(D, "maplab.jsonl"), "a") as f:
            f.write(json.dumps(row) + "\n")
        self.log("{} {}: {} item entities ({} there now), reading {}".format(mp, fac, len(items), sum(1 for i in items if i[5]), self.read))
        self.read += 1
        if self.read >= (2 if LATE > 0 else 1):
            self.k += 1
            self.next_check = 0.0
            if self.k >= len(self.jobs):
                self.log("all done")
