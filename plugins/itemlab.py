"""itemlab: measure what every pickup on a map really gives (health, armor, weapon ammo, ammo boxes).

A controlled bot is stripped to the gauntlet with 50 health and no armor/ammo, placed on each item in turn,
and its state before and after is logged. Load with QLX_PLUGINS="botctl, itemlab", LAB_MAP=<map>.
Writes /tmp/practice/itemlab.jsonl (one line per item) and itemlab.log.

ITEMLAB_OWNED=1: the weapons and ammo boxes only, with every weapon owned, four times over: with 3/10 of a pickup's
ammo, with exactly one pickup's, with one and a half, and one short of the cap ("pre" in each line says which). Shows
what a weapon gives when already owned and where the caps are. An item that is not there yet is put back in the queue.
"""
import json
import os
import time

import minqlx

D = "/tmp/practice"
NAMES = ("g", "mg", "sg", "gl", "rl", "lg", "rg", "pg", "hmg")
OWNED = bool(os.environ.get("ITEMLAB_OWNED"))
PRE = {"low": dict(mg=30, sg=3, gl=3, rl=3, lg=30, rg=3, pg=15, hmg=15),
       "one": dict(mg=100, sg=10, gl=10, rl=10, lg=100, rg=10, pg=50, hmg=50),
       "more": dict(mg=120, sg=15, gl=15, rl=15, lg=120, rg=15, pg=75, hmg=75),
       "cap": dict(mg=149, sg=24, gl=24, rl=24, lg=149, rg=24, pg=149, hmg=149)}


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
            if OWNED:
                self.todo = [it + (pre,) for pre in PRE for it in self.todo if it[1].startswith(("weapon_", "ammo_"))]
            self.log("{} items on {}".format(len(self.todo), self.want))
        c = self.cur
        if c is None:
            if not self.todo:
                self.done = True
                self.log("all items done")
                return
            it = self.todo.pop(0)
            num, cls, x, y, z, up, _ = it[:7]
            pre = it[7] if len(it) > 7 else ""
            if pre:
                up = {e[0]: e[5] for e in minqlx.item_states()[1]}.get(num, 0)
                if not up:                                   # taken in the pass before: later
                    self.todo.append(it)
                    return
                b.weapons(**{w: True for w in NAMES})
                b.ammo(**PRE[pre])
            else:
                b.weapons(reset=True, g=True)
                b.ammo(**{w: 0 for w in NAMES if w != "g"})
            b.health = 50
            b.armor = 0
            self.cur = dict(num=num, cls=cls, pos=(x, y, z), frame=0, up=bool(up), pre=pre)
            return
        c["frame"] += 1
        if c["frame"] == 3:
            c["before"] = self.snap(st)
            b.position(x=c["pos"][0], y=c["pos"][1], z=c["pos"][2] + 8.0)
            b.velocity(reset=True)
        elif c["frame"] == 20:
            rec = dict(map=self.want, item=c["cls"], was_up=c["up"], before=c["before"], after=self.snap(st))
            if c.get("pre"):
                rec["pre"] = c["pre"]
            with open(os.path.join(D, "itemlab.jsonl"), "a") as f:
                f.write(json.dumps(rec) + "\n")
            self.cur = None
