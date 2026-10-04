"""itemlab: measure what every pickup on a map really gives (health, armor, weapon ammo, ammo boxes).

A controlled bot is stripped to the gauntlet with 50 health and no armor/ammo, placed on each item in turn,
and its state before and after is logged. Load with QLX_PLUGINS="botctl, itemlab", LAB_MAP=<map>.
Writes /tmp/practice/itemlab.jsonl (one line per item) and itemlab.log.
"""
import json
import os
import time

import minqlx

D = "/tmp/practice"
NAMES = ("g", "mg", "sg", "gl", "rl", "lg", "rg", "pg", "hmg")


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class itemlab(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.want = os.environ.get("LAB_MAP", "bloodrun").lower()
        self.next_check = 0.0
        self.todo = None
        self.cur = None
        self.done = False

    def log(self, msg):
        minqlx.console_print("[itemlab] " + msg + "\n")
        with open(os.path.join(D, "itemlab.log"), "a") as f:
            f.write("{} {}\n".format(time.strftime("%H:%M:%S"), msg))

    def snap(self, st):
        return dict(health=st.health, armor=st.armor,
                    weapons=[w for w in NAMES if getattr(st.weapons, w)],
                    ammo={w: getattr(st.ammo, w) for w in NAMES if w != "g"})

    def on_frame(self):
        now = time.time()
        if self.done:
            return
        if (minqlx.get_cvar("mapname") or "").lower() != self.want:
            if now > self.next_check:
                self.next_check = now + 10
                minqlx.console_command("map {} duel".format(self.want))
            return
        bots = [p for p in self.players() if is_bot(p) and p.team != "spectator"]
        if not bots:
            if now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("addbot bones 5")
            return
        b = bots[0]
        st = b.state
        if st is None or st.health <= 0:
            return
        minqlx.set_bot_input(b.id, 0, 0, 0, 0, 0, 0.0, 0.0)
        if self.todo is None:
            if now < self.next_check:
                return
            self.todo = [it for it in minqlx.item_states()[1]]
            self.log("{} items on {}".format(len(self.todo), self.want))
        c = self.cur
        if c is None:
            if not self.todo:
                self.done = True
                self.log("all items done")
                return
            num, cls, x, y, z, up, _ = self.todo.pop(0)
            b.weapons(reset=True, g=True)
            b.ammo(**{w: 0 for w in NAMES if w != "g"})
            b.health = 50
            b.armor = 0
            self.cur = dict(num=num, cls=cls, pos=(x, y, z), frame=0, up=bool(up))
            return
        c["frame"] += 1
        if c["frame"] == 3:
            c["before"] = self.snap(st)
            b.position(x=c["pos"][0], y=c["pos"][1], z=c["pos"][2] + 8.0)
            b.velocity(reset=True)
        elif c["frame"] == 20:
            rec = dict(map=self.want, item=c["cls"], was_up=c["up"], before=c["before"], after=self.snap(st))
            with open(os.path.join(D, "itemlab.jsonl"), "a") as f:
                f.write(json.dumps(rec) + "\n")
            self.cur = None
