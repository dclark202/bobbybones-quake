"""poollab: what lava and water do in the real game: a controlled bot is put at a place and stands or walks, and his
health and speed are logged frame by frame.

Cases come from /tmp/practice/poollab_cases.json: a list of {"map", "name", "pos": [x, y, z], "yaw", "forward": 0 or 1,
"seconds"}. For each: the map is loaded (free-for-all, two bots, "allready"), the bot gets 100 health and no armor, is set
down at pos (8 units above it) with no speed, and holds forward (or nothing) facing yaw for that many seconds.

Load with QLX_PLUGINS="botctl, poollab". Writes /tmp/practice/poollab.jsonl (one line per case: the series of time,
place, speed, health) and poollab.log; "all done" marks the end.
"""
import json
import math
import os
import time

import minqlx

D = "/tmp/practice"


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class poollab(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.cases = json.load(open(os.path.join(D, "poollab_cases.json")))
        self.k = 0
        self.next_check = 0.0
        self.cur = None

    def log(self, msg):
        minqlx.console_print("[poollab] " + msg + "\n")
        with open(os.path.join(D, "poollab.log"), "a") as f:
            f.write("{} {}\n".format(time.strftime("%H:%M:%S"), msg))

    def on_frame(self):
        now = time.time()
        if self.k >= len(self.cases):
            return
        c = self.cases[self.k]
        if (minqlx.get_cvar("mapname") or "").lower() != c["map"]:
            if now > self.next_check:
                self.next_check = now + 20
                self.cur = None
                minqlx.console_command("map {} ffa".format(c["map"]))
            return
        bots = sorted([p for p in self.players() if is_bot(p) and p.team != "spectator"], key=lambda p: p.id)
        if len(bots) < 2:
            if now > self.next_check:
                self.next_check = now + 4
                minqlx.console_command("addbot bones 3")
            return
        b, o = bots[0], bots[1]
        so = o.state
        minqlx.set_bot_input(o.id, 0, 0, 0, 1 if (so is not None and so.health <= 0) else 0, 0, 0.0, 0.0)
        state = self.game.state if self.game is not None else None
        if state != "in_progress":
            if state == "warmup" and now > self.next_check:
                self.next_check = now + 12
                self.set_cvar("timelimit", "0")
                self.set_cvar("fraglimit", "0")
                minqlx.console_command("allready")
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, 0, 0.0, 0.0)
            return
        st = b.state
        if st is None:
            return
        if self.cur is None:
            if st.health <= 0:
                minqlx.set_bot_input(b.id, 0, 0, 0, int(now * 10) % 2, 0, 0.0, 0.0)      # tap fire until he is back
                return
            b.health = 100
            b.armor = 0
            b.position(x=c["pos"][0], y=c["pos"][1], z=c["pos"][2] + 8.0)
            b.velocity(reset=True)
            self.cur = dict(t0=now, rows=[], ms0=minqlx.item_states()[0])
            return
        fwd = 127 if c.get("forward") else 0
        minqlx.set_bot_input(b.id, fwd, 0, 0, 0, 0, 0.0, float(c.get("yaw", 0.0)))
        p, v = st.position, st.velocity
        self.cur["rows"].append([int(minqlx.item_states()[0] - self.cur["ms0"]), round(p.x, 1), round(p.y, 1), round(p.z, 1),
                                 round(math.hypot(v.x, v.y), 1), round(v.z, 1), int(st.health), int(st.armor)])
        if now - self.cur["t0"] >= float(c["seconds"]) or st.health <= 0:
            rows = self.cur["rows"]
            with open(os.path.join(D, "poollab.jsonl"), "a") as f:
                f.write(json.dumps(dict(case=c, rows=rows)) + "\n")
            self.log("{} {}: {} frames, health {} -> {}, top speed {}".format(c["map"], c["name"], len(rows), rows[0][6] if rows else None,
                                                                              rows[-1][6] if rows else None, max(r[4] for r in rows) if rows else None))
            self.cur = None
            self.k += 1
            self.next_check = 0.0
            if self.k >= len(self.cases):
                self.log("all done")
