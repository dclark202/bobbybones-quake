"""What the bots say in chat (owner, 2026-10-09: "have them all say 'GG' at the end of the game. Not just 'GG' --
something sort of fun and maybe somewhat silly, use the colors in the chat. They can also write messages in the chat
during the game, if they think they did something really good. Pros usually have a smiley face bind or some other thing
they use to show respect, 'I goofed', etc.").

Each of the four bots has a voice of its own (the names are duelbot.BOT_NAMES): BobbyBones the pupil, Mr Skeleton the
bone jokes, Dr Evil the plan, The Juggernaut in capitals.

- At a game's end every bot says a line, by where it finished (first, in the middle, last), a second or two apart.
- During a game, and only with a person playing: after three frags without dying (pleased with itself), after dying by
  its own hand or the map ("I goofed"), after the same person has fragged it three times without an answer (respect, by
  name), after a frag with the rail from far away. A bot speaks at most once in 75 seconds, the bots together at most
  once in 20, and not every time.

Who fragged whom comes from plugins/ladder.py (it reads the game's counters every frame); without it only the lines at a
game's end are said. Load after ladder: QLX_PLUGINS="botctl, banlist, ladder, banter, botmode, <duelbot|ffabot>".
    !banter         (the owner) every bot says one line now: a check that they can be heard

A line must not hold a double quote, a semicolon, or a percent sign (the game takes the first two for the command's end
and "% h" for a printf format); say() takes them out of a player's name.
"""
import random
import time

import minqlx

NAMES = ("BobbyBones", "Mr Skeleton", "Dr Evil", "The Juggernaut")     # (duelbot.BOT_NAMES; kept in step by hand)
EACH, ALL, CHANCE = 75.0, 20.0, 0.7
FAR = 1500.0                                                           # a rail frag from this far is worth a smile

LINES = (
    dict(   # BobbyBones: the pupil
        first=("^2gg^7! I did a learn :)", "^2gg^7 all :) don't tell my trainer, it will only raise the bar",
               "^2gg^7! all those hours in the simulator, ^3worth it^7"),
        mid=("^2gg^7! filing this one under ^3training data^7", "^2gg^7 :) I'll get you after my next ^310,000^7 games",
             "^2gg^7. not first, not last, ^3still learning^7"),
        last=("^2gg^7... I have been ^1owned^7. respectfully.", "^2gg^7 :( writing this down in my ^3loss function^7",
              "^2gg^7. back to the simulator for me"),
        streak=("^2:)^7", "did you see that?? ^3I^7 did that", "the practice is ^2working^7 :)"),
        oops=("^1oops^7", "I meant to do that. (I did not)", "^3note to self:^7 that is not a floor"),
        respect=("ok ^3{name}^7 that was ^2clean^7", "nice one ^3{name}^7 :)", "^3{name}^7 please, I am only ^35 MB^7 of numbers"),
        rail=("^5*click*^7 :)", "^5rail^7 :)"),
        ),
    dict(   # Mr Skeleton: bone jokes
        first=("^2gg^7. no ^7bones^7 about it", "^2gg^7! that was ^1spine^7-tingling", "^2gg^7 :) you have all been ^3rattled^7"),
        mid=("^2gg^7, I felt that one in my bones", "^2gg^7. tibia honest, good game", "^2gg^7. I had a ^3skeleton^7 crew out there"),
        last=("^2gg^7. I am ^1dead^7. again. still.", "^2gg^7... I've got no body to blame", "^2gg^7, right in the funny bone"),
        streak=("^7rattle rattle^7 :)", "^2bone^7 appetit", "calcium. it ^2works^7."),
        oops=("^1oops^7, lost my footing. and my foot.", "that one is on me. all ^3206^7 of me.", "I went to pieces there"),
        respect=("^3{name}^7 you gave me chills. I have no skin", "humerus. very humerus, ^3{name}^7", "^3{name}^7 you rattle me"),
        rail=("^5right through the ribs^7 :)", "^5x-ray vision^7 :)"),
        ),
    dict(   # Dr Evil: the plan
        first=("^2gg^7. all according to ^1plan^7", "^2gg^7! one... ^3MILLION^7... frags. roughly.", "^2gg^7. my ^1evil^7 is paying off"),
        mid=("^2gg^7. the plan needs ^3minor^7 revisions", "^2gg^7. I blame my henchmen", "^2gg^7. phase two will go better"),
        last=("^2gg^7. curse you all. ^3politely^7.", "^2gg^7... you have foiled me. ^1this time^7.", "^2gg^7. back to the ^3lair^7"),
        streak=("^1mwahaha^7 :)", "^3exactly^7 as I calculated", "behold my ^1genius^7"),
        oops=("^1that^7 was not in the plan", "a ^3minor^7 setback", "who put that there??"),
        respect=("^3{name}^7... I could use someone like you", "well played ^3{name}^7. ^1too^7 well.", "^3{name}^7, you make a fine nemesis"),
        rail=("^5the laser^7. finally. :)", "^5precisely^7 :)"),
        ),
    dict(   # The Juggernaut: capitals
        first=("^2GG^7. NOTHING STOPS ^1THE JUGGERNAUT^7", "^2GG^7!! I AM ^3UNSTOPPABLE^7 (TODAY)", "^2GG^7. ^1JUGGERNAUT^7 SMASH. POLITELY."),
        mid=("^2GG^7. THE JUGGERNAUT WAS ^3SLIGHTLY^7 STOPPED", "^2GG^7. I WAS JUST WARMING UP", "^2GG^7. MOSTLY UNSTOPPABLE"),
        last=("^2GG^7. OK. SOMETHING STOPPED THE JUGGERNAUT", "^2GG^7. THE JUGGERNAUT NEEDS A ^3NAP^7", "^2GG^7. I WAS STOPPED. ^1A LOT^7."),
        streak=("^1UNSTOPPABLE^7 :)", "CAN'T STOP. WON'T STOP.", "^3MOMENTUM^7!!"),
        oops=("THE FLOOR STOPPED THE JUGGERNAUT", "^1OOPS^7. THAT DOES NOT COUNT", "I TRIPPED. ^3MIGHTILY^7."),
        respect=("^3{name}^7 STOPPED THE JUGGERNAUT. RESPECT.", "NICE SHOT ^3{name}^7. NOW HOLD STILL.", "^3{name}^7!! AGAIN?!"),
        rail=("^5BOOM^7 :)", "^5FROM DOWNTOWN^7 :)"),
        ),
)


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


def voice(p):
    """which of the four a bot is, or None for anybody else"""
    if not is_bot(p):
        return None
    for k, n in enumerate(NAMES):
        if n in p.clean_name:
            return k
    return None


def clean(s):
    return str(s).replace('"', "").replace(";", "").replace("%", "").replace("\n", " ")[:24]


class banter(minqlx.Plugin):
    def __init__(self):
        super().__init__()
        self.rng = random.Random()
        self.queue = []                                      # (when, client id, line)
        self.spoke = {}                                      # client id -> when it last spoke
        self.spoke_any = 0.0
        self.run = {}                                        # client id -> frags since its last death
        self.owed = {}                                       # (bot id, person's steam id) -> frags by him without an answer
        self.add_hook("frame", self.on_frame)
        self.add_hook("game_end", self.on_game_end)
        self.add_hook("map", self.on_map)
        self.add_command("banter", self.cmd_banter, 5)
        lad = minqlx.Plugin._loaded_plugins.get("ladder")
        if lad is not None and hasattr(lad, "listeners"):
            lad.listeners.append(self.on_frag)

    # ------------------------------------------------------------------ saying
    def say(self, cid, line, delay=0.0):
        self.queue.append((time.time() + delay, cid, line))

    def on_frame(self):
        if not self.queue:
            return
        now = time.time()
        due = [q for q in self.queue if q[0] <= now]
        if not due:
            return
        self.queue = [q for q in self.queue if q[0] > now]
        here = {p.id: p for p in self.players()}
        for _, cid, line in due:
            p = here.get(cid)
            if p is None or voice(p) is None:
                continue
            try:                                             # the bot says it himself, as a player would
                minqlx.client_command(cid, 'say "{}"'.format(line.replace('"', "").replace(";", "").replace("%", "")))
            except Exception:                                # noqa: BLE001
                pass

    def may(self, p, now):
        if now - self.spoke_any < ALL or now - self.spoke.get(p.id, 0.0) < EACH or self.rng.random() > CHANCE:
            return False
        if not any(not is_bot(q) and q.team != "spectator" for q in self.players()):
            return False                                     # nobody to hear it
        self.spoke[p.id] = self.spoke_any = now
        return True

    def pick(self, p, kind, **kw):
        return self.rng.choice(LINES[voice(p)][kind]).format(**kw)

    # ------------------------------------------------------------------ during a game
    def on_frag(self, killer, victim):
        """from the ladder, for every death it reads: killer is None for a death by his own hand or the map"""
        now = time.time()
        if voice(victim) is not None:
            self.run[victim.id] = 0
            if killer is None:
                if self.may(victim, now):
                    self.say(victim.id, self.pick(victim, "oops"), 1.0)
            elif not is_bot(killer):
                k = (victim.id, killer.steam_id)
                self.owed[k] = self.owed.get(k, 0) + 1
                if self.owed[k] >= 3 and self.may(victim, now):
                    self.owed[k] = 0
                    self.say(victim.id, self.pick(victim, "respect", name=clean(killer.clean_name)), 1.5)
        if killer is not None and voice(killer) is not None:
            self.run[killer.id] = self.run.get(killer.id, 0) + 1
            if not is_bot(victim):
                self.owed[(killer.id, victim.steam_id)] = 0
            far = False
            try:
                a, b = killer.state.position, victim.state.position
                far = killer.state.weapon == 7 and ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5 > FAR
            except Exception:                                # noqa: BLE001
                pass
            if far and self.may(killer, now):
                self.say(killer.id, self.pick(killer, "rail"), 0.8)
            elif self.run[killer.id] == 3 and self.may(killer, now):
                self.say(killer.id, self.pick(killer, "streak"), 0.8)

    # ------------------------------------------------------------------ a game's end
    def on_game_end(self, data):
        if isinstance(data, dict) and data.get("ABORTED"):
            return
        self.gg()

    def gg(self):
        table = sorted((p for p in self.players() if p.team != "spectator"), key=lambda p: (-p.stats.score, p.stats.deaths))
        bots = [(n, p) for n, p in enumerate(table) if voice(p) is not None]
        delay = 1.5
        for n, p in bots:
            kind = "first" if n == 0 else "last" if n == len(table) - 1 and len(table) > 1 else "mid"
            self.say(p.id, self.pick(p, kind), delay)
            delay += 1.2 + self.rng.random()

    def on_map(self, mapname, factory):
        self.queue, self.run, self.owed = [], {}, {}

    def cmd_banter(self, player, msg, channel):
        n = 0
        for p in self.players():
            if voice(p) is not None:
                self.say(p.id, self.pick(p, self.rng.choice(("first", "streak", "oops"))), 0.5 + 1.2 * n)
                n += 1
        player.tell("{} bots will each say a line.".format(n))
        return minqlx.RET_STOP_ALL
