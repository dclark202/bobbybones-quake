"""droplab: measure what a dying player's weapon leaves behind in the real game.

A controlled bot is given a weapon and some ammo, made to hold it, and slain. The new item on the floor is logged
(class, place, how long until the game removes it). After he has respawned he is stripped (or given the same weapon
with a little ammo: "own") and put on the dropped weapon; his state before and after is logged, and whether the item
is gone. One case holds the weapon back to see how long it really lies.

DROPLAB_KILL=rocket (the default): the second bot kills him with a rocket at their feet, a real kill by another
player; DROPLAB_KILL=slay: the game's own kill command, which drops nothing (2026-10-08).
A second bot stands idle so that a real game can run: DROPLAB_LIVE=1 (the default) starts one (free-for-all, "allready")
and measures in it; DROPLAB_LIVE=0 measures in the warmup, where nothing is dropped (2026-10-08).

Load with QLX_PLUGINS="botctl, droplab", LAB_MAP=<map>. Writes /tmp/practice/droplab.jsonl (one line per case) and
droplab.log. Cases: every weapon held with two amounts of ammo; held with none; the machine gun or the gauntlet held
while a rocket launcher is owned; picked up by a player who has the weapon already.
"""
import json
import os
import time

import minqlx

D = "/tmp/practice"
NAMES = ("g", "mg", "sg", "gl", "rl", "lg", "rg", "pg", "hmg")
QLNUM = dict(g=1, mg=2, sg=3, gl=4, rl=5, lg=6, rg=7, pg=8, hmg=13)
LIVE = os.environ.get("DROPLAB_LIVE", "1") != "0"
KILL = os.environ.get("DROPLAB_KILL", "rocket")
# (held, its ammo, what else he owns {weapon: ammo}, what the picker owns of it before or None, wait for it to vanish)
CASES_ALL = [("rl", 3, {}, None, False), ("rl", 17, {}, None, False), ("rl", 7, {}, 5, False), ("rl", 7, {}, 24, False),
         ("rg", 4, {}, None, False), ("rg", 14, {}, None, False), ("lg", 37, {}, None, False), ("lg", 130, {}, None, False),
         ("sg", 6, {}, None, False), ("gl", 4, {}, None, False), ("pg", 33, {}, None, False), ("hmg", 44, {}, None, False),
         ("rl", 0, {}, None, False), ("mg", 60, {"rl": 9}, None, False), ("g", 0, {"rl": 9}, None, False),
         ("mg", 60, {}, None, False), ("rl", 9, {"rg": 6, "lg": 80}, None, False), ("rl", 6, {}, None, True)]
ONLY = [w for w in os.environ.get("DROPLAB_ONLY", "").split(",") if w]      # e.g. "lg,sg": those weapons' cases, twice over
CASES = [c for c in CASES_ALL if c[0] in ONLY and not c[4]] * 2 if ONLY else CASES_ALL


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class droplab(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.want = os.environ.get("LAB_MAP", "bloodrun").lower()
        self.next_check = 0.0
        self.todo = list(CASES)
        self.cur = None
        self.done = False

    def log(self, msg):
        minqlx.console_print("[droplab] " + msg + "\n")
        with open(os.path.join(D, "droplab.log"), "a") as f:
            f.write("{} {}\n".format(time.strftime("%H:%M:%S"), msg))

    def snap(self, st):
        return dict(health=st.health, armor=st.armor, held=int(st.weapon),
                    weapons=[w for w in NAMES if getattr(st.weapons, w)],
                    ammo={w: getattr(st.ammo, w) for w in NAMES if w != "g"})

    def on_frame(self):
        now = time.time()
        if self.done:
            return
        if (minqlx.get_cvar("mapname") or "").lower() != self.want:
            if now > self.next_check:
                self.next_check = now + 10
                minqlx.console_command("map {} ffa".format(self.want))
            return
        bots = sorted([p for p in self.players() if is_bot(p) and p.team != "spectator"], key=lambda p: p.id)
        if len(bots) < 2:
            if now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("addbot bones 5")
            return
        b = bots[0]
        other = bots[1].state
        shooting = self.cur is not None and self.cur.get("phase") == "arm" and self.cur.get("frame", 0) >= 62 and KILL == "rocket"
        if other is not None and not shooting:               # the second bot: stands still, comes back when dead
            minqlx.set_bot_input(bots[1].id, 0, 0, 0, 1 if other.health <= 0 else 0, 0, 0.0, 0.0)
        state = self.game.state if self.game is not None else None
        if LIVE and state != "in_progress":
            if state == "warmup" and now > self.next_check:
                self.next_check = now + 15
                self.set_cvar("timelimit", "0")
                self.set_cvar("fraglimit", "0")
                minqlx.console_command("allready")
                self.log("allready (state {})".format(state))
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, 0, 0.0, 0.0)
            return
        st = b.state
        if st is None:
            return
        c = self.cur
        if c is None:
            if not self.todo:
                self.done = True
                self.log("all cases done")
                return
            if st.health <= 0:
                minqlx.set_bot_input(b.id, 0, 0, 0, 1, 0, 0.0, 0.0)          # fire: respawn
                return
            held, n, more, own, wait = self.todo.pop(0)
            self.cur = c = dict(held=held, n=n, more=more, own=own, wait=wait, frame=0, phase="arm")
            b.weapons(reset=True, **{w: True for w in set(["g", "mg", held]) | set(more)})
            am = {w: 0 for w in NAMES if w != "g"}
            am.update(more)
            if held not in ("g",):
                am[held] = n
            if held != "mg":
                am["mg"] = max(am.get("mg", 0), 50)
            b.ammo(**am)
            b.health = 100
            b.armor = 0
            return
        c["frame"] += 1
        f = c["frame"]
        if c["phase"] == "arm":                                               # make him hold it, then slay him
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, QLNUM[c["held"]], 0.0, 0.0)
            if f == 60 and KILL != "rocket":
                c["dying"] = self.snap(st)
                c["place"] = (st.position.x, st.position.y, st.position.z)
                c["items0"] = {e[0] for e in minqlx.item_states()[1]}
                b.slay()
                c["phase"], c["frame"] = "dead", 0
            elif f == 60 and other is not None and other.health > 0:          # beside the second bot, nearly dead
                o = bots[1]
                o.weapons(reset=True, g=True, rl=True)
                o.ammo(rl=20)
                o.health = 300
                o.armor = 200
                b.position(x=other.position.x + 40.0, y=other.position.y, z=other.position.z + 4.0)
                b.velocity(reset=True)
                b.health = 5
                b.armor = 0
                c["items0"] = {e[0] for e in minqlx.item_states()[1]}
            elif f == 60:
                c["frame"] = 40                                               # the second bot is not there yet: wait
            elif f > 60 and KILL == "rocket":
                o = bots[1]
                if st.health > 0:
                    if f == 61:
                        c["dying"] = self.snap(st)
                        c["place"] = (st.position.x, st.position.y, st.position.z)
                    o.health = 300
                    minqlx.set_bot_input(o.id, 0, 0, 0, 1 if f >= 75 else 0, QLNUM["rl"], 89.0, 0.0)    # a rocket at his own feet
                    if f > 400:
                        self.log("no kill after {} frames: giving the case up".format(f))
                        self.cur = None
                else:
                    minqlx.set_bot_input(o.id, 0, 0, 0, 0, 0, 0.0, 0.0)
                    far = max(minqlx.item_states()[1], key=lambda e: (e[2] - c["place"][0]) ** 2 + (e[3] - c["place"][1]) ** 2)
                    o.position(x=far[2], y=far[3], z=far[4] + 8.0)            # away, so that he does not take what fell
                    o.velocity(reset=True)
                    c["phase"], c["frame"] = "dead", 0
        elif c["phase"] == "dead":
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, 0, 0.0, 0.0)
            if f == 5:
                c["health_after_slay"] = st.health
            if f == 20:
                lt, items = minqlx.item_states()
                c["drop"] = [dict(num=e[0], cls=e[1], pos=[round(e[2], 1), round(e[3], 1), round(e[4], 1)], up=e[5],
                                  removed_in_ms=int(e[6] - lt)) for e in items if e[0] not in c["items0"]]
                c["t_drop"] = now
                c["phase"], c["frame"] = "respawn", 0
        elif c["phase"] == "respawn":
            if st.health <= 0:
                minqlx.set_bot_input(b.id, 0, 0, 0, f % 2, 0, 0.0, 0.0)      # tap fire until he is back
                c["frame_alive"] = None
                return
            minqlx.set_bot_input(b.id, 0, 0, 0, 0, 0, 0.0, 0.0)
            if c.get("frame_alive") is None:
                c["frame_alive"] = f
            g = f - c["frame_alive"]
            if not c["drop"]:                                                 # nothing fell: done
                self.write(c, None, None, None)
                return
            if c["wait"]:                                                     # how long does it really lie?
                nums = {e[0] for e in minqlx.item_states()[1]}
                if c["drop"][0]["num"] not in nums:
                    c["lay_s"] = round(now - c["t_drop"], 2)
                    self.write(c, None, None, None)
                return
            if g == 5:
                b.weapons(reset=True, g=True, **({self.short(c["drop"][0]["cls"]): True} if c["own"] is not None else {}))
                am = {w: 0 for w in NAMES if w != "g"}
                if c["own"] is not None:
                    am[self.short(c["drop"][0]["cls"])] = c["own"]
                b.ammo(**am)
                b.health = 100
            elif g == 10:
                c["before"] = self.snap(st)
                now_ = {e[0]: e for e in minqlx.item_states()[1]}.get(c["drop"][0]["num"])     # where it lies now (it was thrown)
                p = [now_[2], now_[3], now_[4]] if now_ is not None else c["drop"][0]["pos"]
                c["drop"][0]["rest"] = [round(x, 1) for x in p]
                c["drop"][0]["up_at_pickup"] = None if now_ is None else now_[5]
                b.position(x=p[0], y=p[1], z=p[2] + 8.0)
                b.velocity(reset=True)
            elif g == 30:
                nums = {e[0]: e[5] for e in minqlx.item_states()[1]}
                self.write(c, c["before"], self.snap(st), c["drop"][0]["num"] not in nums)

    @staticmethod
    def short(cls):
        return {"weapon_rocketlauncher": "rl", "weapon_railgun": "rg", "weapon_lightning": "lg", "weapon_shotgun": "sg",
                "weapon_grenadelauncher": "gl", "weapon_plasmagun": "pg", "weapon_hmg": "hmg", "weapon_machinegun": "mg"}.get(cls, "rl")

    def write(self, c, before, after, gone):
        rec = dict(map=self.want, live=LIVE, kill=KILL, state=self.game.state if self.game is not None else None, health_after_slay=c.get("health_after_slay"),
                   held=c["held"], ammo=c["n"], also_owned=c["more"], picker_owned=c["own"], dying=c.get("dying"),
                   died_at=[round(x, 1) for x in c.get("place", (0, 0, 0))], dropped=c.get("drop"), before=before, after=after,
                   item_gone_after_pickup=gone, lay_s=c.get("lay_s"))
        with open(os.path.join(D, "droplab.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        self.log("{} with {} (also {}; picker owns {}): dropped {} | lay {}".format(
            c["held"], c["n"], c["more"], c["own"], [(d_["cls"], d_["removed_in_ms"]) for d_ in (c.get("drop") or [])], c.get("lay_s")))
        self.cur = None
