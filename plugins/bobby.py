"""bobby: BobbyBones' personality - an obnoxious rainbow name and trash talk after frags."""
import random
import time

import minqlx

NAME = "^1B^3o^2b^5b^4y^6B^1o^3n^2e^5s"

TAUNTS = [
    "ez",
    "^3sit.",
    "BobbyBones ^1>^7 you",
    "did you even time that armor?",
    "gg no re",
    "^5*yawn*",
    "that was my warmup",
    "imagine losing to a bot named BobbyBones",
    "nice try ^6:)",
    "you should practice against me more. oh wait",
    "^2free frag",
    "lag? :)",
    "I could hear you coming from across the map",
    "try strafing next time",
    "BobbyBones: 1, you: 0 ^3(and counting)",
    "skill issue",
    "^1BOBBY^3BONES ^2STRIKES ^5AGAIN",
    "are you even holding mouse1?",
    "that's going in the highlight reel",
    "brb, timing your mega",
]

WEAPON_TAUNTS = {
    "RAILGUN": ["^1*ding*", "rail goes brrr", "should've stopped moving in a straight line"],
    "LIGHTNING": ["shocking.", "zap zap", "40% lg btw"],
    "ROCKET": ["direct hit. on purpose. obviously.", "splash damage is still damage"],
    "SHOTGUN": ["point blank, my favorite range"],
    "GAUNTLET": ["^1HUMILIATION", "imagine getting gauntleted by a bot"],
}


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class bobby(minqlx.Plugin):
    def __init__(self):
        self.add_hook("death", self.on_death)
        self.add_hook("frame", self.on_frame)       # warmup emits no death stats: watch health instead
        self.hp = {}
        self.bobby_fired = 0.0
        self.add_hook("player_loaded", self.on_loaded)
        self.add_command("bobbyname", self.cmd_name, permission=5)
        self.last_taunt = 0.0

    def bobby_player(self):
        for p in self.players():
            if is_bot(p) and "Bobby" in p.clean_name.replace(" ", ""):
                return p
        return None

    def cmd_name(self, player, msg, channel):
        self.rename()

    def on_loaded(self, player):
        self.rename_later()

    @minqlx.delay(1)
    def rename_later(self):
        self.rename()

    def rename(self):
        b = self.bobby_player()
        if b is not None and b.name != NAME:
            b.name = NAME

    def on_frame(self):
        b = self.bobby_player()
        if b is None:
            return
        now = time.time()
        if minqlx.last_usercmd(b.id)[1] & 1:
            self.bobby_fired = now
        for p in self.players():
            if is_bot(p):
                continue
            st = p.state
            hp = st.health if st else 0
            if self.hp.get(p.id, 1) > 0 and hp <= 0 and now - self.bobby_fired < 1.5:
                self.taunt(b, "")
            self.hp[p.id] = hp

    def taunt(self, killer, weapon):
        now = time.time()
        if now - self.last_taunt < 4:          # don't flood the chat
            return
        self.last_taunt = now
        pool = list(TAUNTS)
        for key, extra in WEAPON_TAUNTS.items():
            if key in weapon:
                pool += extra * 2
        self.say_later(killer.id, random.choice(pool))

    def on_death(self, victim, killer, data):
        if killer is None or victim is None or not is_bot(killer) or is_bot(victim):
            return
        if "Bobby" not in killer.clean_name.replace(" ", ""):
            return
        self.taunt(killer, str(data.get("MOD", "")) if isinstance(data, dict) else "")

    @minqlx.delay(0.8)
    def say_later(self, cid, text):
        minqlx.client_command(cid, 'say "{}"'.format(text.replace('"', "'")))
