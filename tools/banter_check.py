"""Offline check of plugins/banter.py (no game server): the lines' rules and the surprise rule, with a stand-in minqlx
and fake players and frags.  python tools/banter_check.py   (exit 0: all passed)"""
import os
import random
import re
import sys
import types

fake = types.ModuleType("minqlx")


class _Plugin:
    _loaded_plugins = {}

    def __init__(self):
        self._players = []

    def add_hook(self, *a, **k):
        pass

    def add_command(self, *a, **k):
        pass

    def players(self):
        return list(self._players)


fake.Plugin, fake.RET_STOP_ALL = _Plugin, 2
fake.client_command = lambda cid, cmd: None
sys.modules["minqlx"] = fake
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugins"))
import banter as B                                            # noqa: E402

BOT_SID, PERSON_SID = 90071992547409920, 1000000000000001    # (a bot's id form; a made-up person's id, no real one)


class St:
    def __init__(self, health, armor, weapon):
        self.health, self.armor, self.weapon = health, armor, weapon


class P:
    def __init__(self, cid, name, sid, health=125, armor=0, weapon=5, team="free"):
        self.id, self.clean_name, self.steam_id, self.team = cid, name, sid, team
        self.state = St(health, armor, weapon)


fails = []


def check(cond, what):
    if not cond:
        fails.append(what)
        print("FAIL", what)


# 1. the lines themselves
for v, d in enumerate(B.LINES):
    for kind, pool in d.items():
        check(len(set(pool)) == len(pool), "voice {} {}: a line twice".format(v, kind))
        for s in pool:
            check(not re.search(r'[";%]', s), "bad character: " + s)
            check("too good" not in s.lower(), "a giving-up line is back: " + s)
            s.format(name="x")                               # every {} is {name}
    check(set(d) == {"first", "mid", "last", "upset_win", "upset_loss"}, "voice {} kinds {}".format(v, sorted(d)))
check(len(B.LINES[0]["upset_win"]) >= 15 and len(B.LINES[0]["upset_loss"]) >= 12, "BobbyBones: enough in-game lines")

# 2. the surprise rule
full_rl = B.strength(125, 100, 5)
weak_mg = B.strength(40, 0, 2)
check(B.upset(weak_mg, full_rl, True) == "upset_win", "won from far behind: a surprise")
check(B.upset(full_rl, weak_mg, False) == "upset_loss", "lost from far ahead: a surprise")
check(B.upset(full_rl, weak_mg, True) is None, "won from ahead: expected, no line")
check(B.upset(weak_mg, full_rl, False) is None, "lost from behind: expected, no line")
check(B.upset(B.strength(100, 50, 5), B.strength(125, 50, 5), True) is None, "a near-even fight: no line")
check(B.strength(100, 300, 5) == 300.0, "armor counts up to twice the health")

# 3. the plugin: fights, limits, repeats
def plugin(seed=1):
    pl = B.banter()
    pl.rng.seed(seed)
    pl.lines.rng = pl.rng
    bob, me = P(0, "BobbyBones (BOT)", BOT_SID), P(1, "tester", PERSON_SID)
    pl._players = [bob, me]
    return pl, bob, me


def fight(pl, bob, me, t, bob_stack, me_stack, bob_wins):
    """five seconds of samples at the given stacks, then a frag"""
    for k in range(20):
        bob.state, me.state = St(*bob_stack), St(*me_stack)
        pl.sample(t + 0.25 * k)
    if bob_wins:
        pl.on_frag(bob, me, now=t + 5.0)
    else:
        pl.on_frag(me, bob, now=t + 5.0)


B.CHANCE = 1.0
pl, bob, me = plugin()
fight(pl, bob, me, 1000.0, (125, 100, 5), (125, 100, 5), True)
check(not pl.queue, "an even fight says nothing")
fight(pl, bob, me, 1010.0, (30, 0, 2), (150, 100, 7), True)
check(len(pl.queue) == 1 and pl.queue[0][2] in [s.format(name="tester") for s in B.LINES[0]["upset_win"]],
      "a won upset says an upset_win line")
fight(pl, bob, me, 1030.0, (30, 0, 2), (150, 100, 7), True)
check(len(pl.queue) == 1, "the cooldown holds the next one back")
fight(pl, bob, me, 1030.0 + B.EACH, (150, 100, 7), (30, 0, 2), False)
check(len(pl.queue) == 2 and pl.queue[1][2] in [s.format(name="tester") for s in B.LINES[0]["upset_loss"]],
      "a lost upset after the cooldown says an upset_loss line")
for k in range(10):
    fight(pl, bob, me, 2000.0 + k * (B.EACH + 1), (30, 0, 2), (150, 100, 7), True)
check(len(pl.queue) == B.GAME_MAX, "at most GAME_MAX lines a game ({} said)".format(len(pl.queue)))
pl.new_game()
fight(pl, bob, me, 9000.0, (30, 0, 2), (150, 100, 7), True)
check(len(pl.queue) == B.GAME_MAX + 1, "a new game may speak again")

# bot against bot (free-for-all) and a death by the map say nothing
pl, bob, me = plugin()
sk = P(2, "Mr Skeleton (BOT)", BOT_SID + 1)
pl._players.append(sk)
for k in range(20):
    bob.state, sk.state = St(30, 0, 2), St(150, 100, 7)
    pl.sample(100 + 0.25 * k)
pl.on_frag(bob, sk, now=105.0)
pl.on_frag(None, bob, now=105.0)
check(not pl.queue, "bot against bot, or the map, says nothing")

# nobody to hear it
pl, bob, me = plugin()
me.team = "spectator"
pl._players = [bob, me, P(3, "tester2", PERSON_SID + 1, team="spectator")]
fight(pl, bob, P(4, "x", PERSON_SID + 2), 100.0, (30, 0, 2), (150, 100, 7), True)
check(not pl.queue, "no person playing: no line")

# no line twice in a game; an exhausted pool goes quiet; across games the recent ones are avoided
pk = B.Picker(random.Random(3))
said = [pk.pick(0, "upset_win", name="n") for _ in range(len(B.LINES[0]["upset_win"]) + 3)]
real = [s for s in said if s is not None]
check(len(real) == len(set(real)) == len(B.LINES[0]["upset_win"]), "every in-game line once, then quiet")
pk = B.Picker(random.Random(4))
g1 = [pk.pick(0, "last") for _ in range(3)]
pk.new_game()
g2 = [pk.pick(0, "last") for _ in range(3)]
check(not set(g1) & set(g2), "the next game avoids the last game's lines")
pk = B.Picker(random.Random(5))
seen = []
for g in range(40):
    pk.new_game()
    seen.append(pk.pick(0, "first"))
check(all(seen[i] not in seen[max(0, i - B.RECENT):i] for i in range(len(seen))),
      "a game-end line does not come back within RECENT games")

print("banter_check: {} failed".format(len(fails)) if fails else "banter_check: all passed")
sys.exit(1 if fails else 0)
