"""What the bots say in chat (owner, 2026-10-09: "have them all say 'GG' at the end of the game. Not just 'GG' --
something sort of fun and maybe somewhat silly, use the colors in the chat. They can also write messages in the chat
during the game, if they think they did something really good. Pros usually have a smiley face bind or some other thing
they use to show respect, 'I goofed', etc.").

Each of the four bots has a voice of its own (the names are duelbot.BOT_NAMES, in the order they join): BobbyBones the
pupil, Mr Skeleton the bone jokes, THE JUGGERNAUT in capitals, Dr Evil the plan.

- In the countdown before a game (only with a person playing) every bot says a short "glhf" line, once per countdown
  (owner, 2026-10-18: "a few 'glhf' type messages that he will choose from during the countdown").
- At a game's end every bot says a line, by where it finished (first, in the middle, last), a second or two apart. No
  line there gives the game up (owner, 2026-10-24: the "wp <name> you are too good" line "looks like he's giving up").
- During a game, and only with a person playing, a bot speaks only when a fight surprised it (owner, 2026-10-24: "reserve
  them for moments where he's 'surprised' (i.e., thought he would lose a fight but won, or vice versa)"): a fight
  between a bot and a person that ends in a frag, judged by what each had when the fight began (the highest of the last
  FIGHT_S seconds, sampled every SAMPLE s: health and armor as effective health, times a factor for the weapon in hand,
  WEAPON_F). The bot won with less than UPSET_RATIO of the person's strength and at least UPSET_GAP below it:
  "upset_win"; the bot lost with UPSET_RATIO more and the gap the other way: "upset_loss". The truth of both stacks, not
  his belief: this is chat only and nothing of it reaches the network or training.
  Limits: at most GAME_MAX lines a bot a game, a bot at most once in EACH seconds, the bots together at most once in
  ALL, and with chance CHANCE. No line twice in a game, and the last RECENT lines of a bot are avoided across games.

Who fragged whom comes from plugins/ladder.py (it reads the game's counters every frame); without it only the lines at a
game's end are said. Load after ladder: QLX_PLUGINS="botctl, banlist, ladder, banter, botmode, <duelbot|ffabot>".
    !banter         (the owner) every bot says one line now: a check that they can be heard

A line must not hold a double quote, a semicolon, or a percent sign (the game takes the first two for the command's end
and "% h" for a printf format); say() takes them out of a player's name. tools/banter_check.py tests the rules offline.
"""
import collections
import random
import time

import minqlx

NAMES = ("BobbyBones", "Mr Skeleton", "THE JUGGERNAUT", "Dr Evil")     # (duelbot.BOT_NAMES; kept in step by hand)
EACH, ALL, CHANCE, GAME_MAX, RECENT = 90.0, 20.0, 0.85, 3, 12
SAMPLE, FIGHT_S = 0.25, 5.0                                            # stacks sampled every SAMPLE s, a fight's start: FIGHT_S back
UPSET_RATIO, UPSET_GAP = 0.6, 50.0
# what a weapon in hand is worth in a fight (cosmetic; QL weapon numbers: 1 gauntlet, 2 MG, 3 SG, 4 GL, 5 RL, 6 LG, 7 RG,
# 8 PG, 9 BFG, 11 nailgun, 12 prox, 13 chaingun, 14 HMG)
WEAPON_F = {1: 0.5, 2: 0.7, 3: 0.85, 4: 0.8, 5: 1.0, 6: 1.0, 7: 1.0, 8: 0.95, 9: 1.0, 11: 0.85, 12: 0.8, 13: 0.85, 14: 0.85}
GLHF = ("glhf", "gl hf", "good luck, have fun", "glhf ^3:)^7", "gl", "hf", "^2glhf^7", "gl hf ^3:)^7")   # the countdown's lines, any bot
IN_GAME = ("upset_win", "upset_loss")

LINES = (
    dict(   # BobbyBones: the pupil (owner, 2026-10-16: more of them, with colour; 2026-10-24: more, and only when surprised)
        first=("^2gg^7! I did a learn ^3:)^7", "^2gg^7 all ^3:)^7 don't tell my trainer, it will only raise the bar",
               "^2gg^7! all those hours in the simulator, ^3worth it^7",
               "^2gg^7! ^5gradient descent^7 goes brrr",
               "^2gg wp^7! that one goes on the ^3fridge^7",
               "^2gg^7 ^1<3^7 my reward function is so happy right now",
               "^2gg^7! I won?? ^6quick, somebody save a checkpoint^7",
               "^2gg^7. I would like to thank my ^5GPU^7 and the ^5ten maps^7",
               "^2gg^7! ^3v1.0^7 is closer than you think ^3:)^7",
               "^2gg^7 ^3:)^7 that was ^5in distribution^7",
               "^2gg^7! the ^5value head^7 called it",
               "^2gg^7 ^3:)^7 same time tomorrow?",
               "^2gg wp^7! that one is going in my ^3highlight reel^7",
               "^2gg^7! ^5one more epoch^7 and I am unstoppable",
               "^2gg^7 ^3:)^7 my legs and my aim showed up ^2together^7 for once"),
        mid=("^2gg^7! filing this one under ^3training data^7", "^2gg^7 ^3:)^7 I'll get you after my next ^310,000^7 games",
             "^2gg^7. not first, not last, ^3still learning^7",
             "^2gg^7! ^5mid table^7, mid learning curve",
             "^2gg^7. my loss went down a bit, so ^2a win^7 really",
             "^2gg^7 ^3:)^7 saving the highlights for the ^5replay buffer^7",
             "^2gg^7. ^6average^7 is just ^3above bad^7 with extra steps",
             "^2gg^7. good data, good game ^3:)^7"),
        last=("^2gg wp^7! you got this one, ^3I want the next^7", "^2gg^7 ^1:(^7 writing this down in my ^3loss function^7",
              "^2gg^7. back to the simulator for me",
              "^2gg^7. that was a ^1very large^7 learning signal",
              "^2gg wp^7. I will be ^3back^7, and ^5slightly^7 better",
              "^2gg^7. ^1overnight training^7 it is",
              "^2gg^7 ^1T_T^7 at least I am a ^3fast^7 learner",
              "^2gg^7. please do not show this one to my ^5trainer^7",
              "^2gg^7. new personal goal: ^3one more frag^7 than that",
              "^2gg wp^7. ^3rematch?^7",
              "^2gg^7. noted, learned, ^3coming back^7",
              "^2gg^7 ^3:)^7 that was a ^5lesson^7, not a ^1result^7"),
        upset_win=("^3wait^7, I won that? ^2:D^7", "that was ^1not^7 supposed to work ^3:)^7",
                   "^3{name}^7 had the stack, ^3I^7 had the ^2plan^7", "my value head said ^1no^7. my hands said ^2yes^7",
                   "^3low hp^7, high ^2confidence^7", "the odds were ^1bad^7. the odds were also ^3wrong^7",
                   "^3{name}^7 you had me, and then you ^1didn't^7 ^3:)^7", "surprised myself there ^2:D^7",
                   "underdog ^2wins^7 ^3:)^7", "that one is going straight into the ^5replay buffer^7",
                   "^3plot twist^7 ^2:)^7", "who needs armor anyway ^3:)^7", "^2clutch^7. I think. is this clutch?",
                   "^3{name}^7, I am as surprised as you are", "the simulator ^5never^7 let me win those ^3:)^7",
                   "^2:O^7 doing that again, on purpose next time", "did you see that?? ^3I^7 did that",
                   "the practice is ^2working^7 ^3:)^7"),
        upset_loss=("ok ^3{name}^7, ^2that^7 was clean", "I had the stack and ^3{name}^7 had the ^2aim^7. noted",
                    "^3{name}^7 how?? I am taking ^5notes^7", "^1huh^7. my value head did not see that coming",
                    "^3{name}^7 that one goes in my ^5training data^7", "nice one ^3{name}^7, ^1rematch^7 at the next spawn",
                    "^3{name}^7 outplayed the ^5math^7 there", "I had the ^3stack^7 and ^1a plan^7. one of them failed",
                    "^1that^7 was a large gradient", "well played ^3{name}^7. ^2the next one is mine^7",
                    "note to self: ^3stack^7 is not ^1skill^7", "^3{name}^7 ^2wp^7. I will remember that ^5angle^7",
                    "^1ouch^7. recalculating", "^3{name}^7 ok, you get ^2one^7 ^3:)^7"),
        ),
    dict(   # Mr Skeleton: bone jokes
        first=("^2gg^7. no ^7bones^7 about it", "^2gg^7! that was ^1spine^7-tingling", "^2gg^7 :) you have all been ^3rattled^7"),
        mid=("^2gg^7, I felt that one in my bones", "^2gg^7. tibia honest, good game", "^2gg^7. I had a ^3skeleton^7 crew out there"),
        last=("^2gg^7. I am ^1dead^7. again. still.", "^2gg^7... I've got no body to blame", "^2gg^7, right in the funny bone"),
        upset_win=("^7rattle rattle^7 :)", "^2bone^7 appetit", "calcium. it ^2works^7.", "^5right through the ribs^7 :)",
                   "^5x-ray vision^7 :)", "not bad for a ^3bag of bones^7"),
        upset_loss=("^3{name}^7 you gave me chills. I have no skin", "humerus. very humerus, ^3{name}^7",
                    "^3{name}^7 you rattle me", "I will pull myself ^3back together^7"),
        ),
    dict(   # THE JUGGERNAUT: capitals
        first=("^2GG^7. NOTHING STOPS ^1THE JUGGERNAUT^7", "^2GG^7!! I AM ^3UNSTOPPABLE^7 (TODAY)", "^2GG^7. ^1JUGGERNAUT^7 SMASH. POLITELY."),
        mid=("^2GG^7. THE JUGGERNAUT WAS ^3SLIGHTLY^7 STOPPED", "^2GG^7. I WAS JUST WARMING UP", "^2GG^7. MOSTLY UNSTOPPABLE"),
        last=("^2GG^7. OK. SOMETHING STOPPED THE JUGGERNAUT", "^2GG^7. THE JUGGERNAUT NEEDS A ^3NAP^7", "^2GG^7. NEXT TIME, ^1FULL SPEED^7."),
        upset_win=("^1UNSTOPPABLE^7 :)", "CAN'T STOP. WON'T STOP.", "^3MOMENTUM^7!!", "^5BOOM^7 :)", "^5FROM DOWNTOWN^7 :)"),
        upset_loss=("^3{name}^7 STOPPED THE JUGGERNAUT. RESPECT.", "NICE SHOT ^3{name}^7. NOW HOLD STILL.", "^3{name}^7!! AGAIN?!"),
        ),
    dict(   # Dr Evil: the plan
        first=("^2gg^7. all according to ^1plan^7", "^2gg^7! one... ^3MILLION^7... frags. roughly.", "^2gg^7. my ^1evil^7 is paying off"),
        mid=("^2gg^7. the plan needs ^3minor^7 revisions", "^2gg^7. I blame my henchmen", "^2gg^7. phase two will go better"),
        last=("^2gg^7. curse you all. ^3politely^7.", "^2gg^7... foiled. ^1this time^7.", "^2gg^7. back to the ^3lair^7"),
        upset_win=("^1mwahaha^7 :)", "^3exactly^7 as I calculated", "behold my ^1genius^7", "^5the laser^7. finally. :)",
                   "^5precisely^7 :)"),
        upset_loss=("^3{name}^7... I could use someone like you", "well played ^3{name}^7. ^1too^7 well.",
                    "^3{name}^7, you make a fine nemesis", "^1that^7 was not in the plan"),
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


def strength(health, armor, weapon):
    """what a player brings to a fight (cosmetic): effective health (armor takes two thirds of a hit, so it counts up to
    twice the health behind it) times the weapon in hand"""
    h = max(0.0, float(health))
    return (h + min(max(0.0, float(armor)), 2.0 * h)) * WEAPON_F.get(int(weapon or 0), 0.8)


def upset(own, other, won):
    """the bot's strength and the person's at the fight's start, and whether the bot won it: "upset_win", "upset_loss" or
    None (the fight went as expected, or was even)"""
    if won and own < UPSET_RATIO * other and other - own >= UPSET_GAP:
        return "upset_win"
    if not won and other < UPSET_RATIO * own and own - other >= UPSET_GAP:
        return "upset_loss"
    return None


class Picker:
    """lines without repeats: none twice in a game (in-game lines run out instead), the last RECENT of a bot avoided"""
    def __init__(self, rng):
        self.rng = rng
        self.used = set()                                    # (voice, line) said this game
        self.recent = collections.defaultdict(lambda: collections.deque(maxlen=RECENT))   # voice -> lines, oldest first

    def new_game(self):
        self.used = set()

    def pick(self, v, kind, **kw):
        pool = LINES[v][kind]
        fresh = [s for s in pool if (v, s) not in self.used]
        if not fresh:
            if kind in IN_GAME:
                return None
            rec = list(self.recent[v])                       # the line said longest ago (or never)
            fresh = [min(pool, key=lambda s: rec.index(s) if s in rec else -1)]
        best = [s for s in fresh if s not in self.recent[v]] or fresh
        s = self.rng.choice(best)
        self.used.add((v, s))
        if s in self.recent[v]:
            self.recent[v].remove(s)
        self.recent[v].append(s)
        return s.format(**kw)


def aim_level():
    """BobbyBones's aim setting on a 1v1 server ("worse", "default", "better", "max"), None elsewhere (plugins/duelbot.py, !aim)"""
    pl = minqlx.Plugin._loaded_plugins.get("duelbot")
    try:
        lv = pl.aim_level() if pl is not None and hasattr(pl, "aim_level") else None
    except Exception:                                        # noqa: BLE001
        lv = None
    return lv if lv in AIM_ORDER else None


AIM_ORDER = ("worse", "default", "better", "max")         # (owner, 2026-10-27: the labels replace 1-5|max)


def aim_gg_line(level, person, bobby):
    """after a full duel: what BobbyBones says about his aim, by the result (owner's wording, 2026-10-21); None on a draw"""
    if level is None or person == bobby:
        return None
    i = AIM_ORDER.index(level)
    if person > bobby:
        if level != "max":
            return "Too easy at aim {}? Try ^2!aim {}^7 next game".format(level, AIM_ORDER[i + 1])
        return "You beat me at max aim. Respect."
    if level == "worse":
        return "That's my easiest aim. Rematch?"
    return "Want a closer game? Try ^2!aim {}^7".format(AIM_ORDER[i - 1])


def clean(s):
    return str(s).replace('"', "").replace(";", "").replace("%", "").replace("\n", " ")[:24]


class banter(minqlx.Plugin):
    def __init__(self):
        super().__init__()
        self.rng = random.Random()
        self.lines = Picker(self.rng)
        self.queue = []                                      # (when, client id, line)
        self.spoke = {}                                      # client id -> when it last spoke
        self.spoke_any = 0.0
        self.said = {}                                       # client id -> in-game lines this game
        self.hist = {}                                       # client id -> deque of (when, strength) samples
        self.sample_t = 0.0
        self.add_hook("frame", self.on_frame)
        self.add_hook("game_start", self.on_game_start)
        self.add_hook("game_end", self.on_game_end)
        self.add_hook("game_countdown", self.on_countdown)
        self.glhf_t = 0.0                                    # when the bots last wished luck (once per countdown)
        self.add_hook("map", self.on_map)
        self.add_command("banter", self.cmd_banter, 5)
        lad = minqlx.Plugin._loaded_plugins.get("ladder")
        if lad is not None and hasattr(lad, "listeners"):
            lad.listeners.append(self.on_frag)

    # ------------------------------------------------------------------ saying
    def say(self, cid, line, delay=0.0):
        if line:
            self.queue.append((time.time() + delay, cid, line))

    def on_frame(self):
        now = time.time()
        if now - self.sample_t >= SAMPLE:
            self.sample_t = now
            self.sample(now)
        if not self.queue:
            return
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

    def sample(self, now):
        """every player's strength, a few times a second, for the fights' starts"""
        n = int(FIGHT_S / SAMPLE) + 2
        live = set()
        for p in self.players():
            try:
                st = p.state
                if p.team == "spectator" or st is None:
                    continue
                live.add(p.id)
                self.hist.setdefault(p.id, collections.deque(maxlen=n)).append(
                    (now, strength(st.health, st.armor, st.weapon) if st.health > 0 else 0.0))
            except Exception:                                # noqa: BLE001
                pass
        for cid in [c for c in self.hist if c not in live]:
            del self.hist[cid]

    def at_start(self, cid, now):
        """a player's strength when the fight began: the most of the last FIGHT_S seconds (a fight only takes away)"""
        xs = [s for t, s in self.hist.get(cid, ()) if now - t <= FIGHT_S]
        return max(xs) if xs else None

    def may(self, p, now):
        if self.said.get(p.id, 0) >= GAME_MAX or now - self.spoke_any < ALL or now - self.spoke.get(p.id, -1e9) < EACH:
            return False
        if self.rng.random() > CHANCE:
            return False
        if not any(not is_bot(q) and q.team != "spectator" for q in self.players()):
            return False                                     # nobody to hear it
        return True

    # ------------------------------------------------------------------ during a game
    def on_frag(self, killer, victim, now=None):
        """from the ladder, for every death it reads: killer is None for a death by his own hand or the map. Only a fight
        between a bot and a person that ended against what both brought to it is worth a line."""
        now = time.time() if now is None else now
        if killer is None:
            return
        kb, vb = voice(killer) is not None, voice(victim) is not None
        if kb == vb or (not kb and is_bot(killer)) or (not vb and is_bot(victim)):
            return                                           # bot against bot, person against person, or the game's own bots
        bot, person, won = (killer, victim, True) if kb else (victim, killer, False)
        own, other = self.at_start(bot.id, now), self.at_start(person.id, now)
        if own is None or other is None:
            return
        kind = upset(own, other, won)
        if kind is None or not self.may(bot, now):
            return
        line = self.lines.pick(voice(bot), kind, name=clean(person.clean_name))
        if line is None:
            return
        self.spoke[bot.id] = self.spoke_any = now
        self.said[bot.id] = self.said.get(bot.id, 0) + 1
        self.say(bot.id, line, 1.0 + self.rng.random())

    # ------------------------------------------------------------------ the countdown
    def on_countdown(self):
        now = time.time()
        if now - self.glhf_t < 30.0:                         # once per countdown
            return
        if not any(not is_bot(q) and q.team != "spectator" for q in self.players()):
            return                                           # nobody to hear it
        self.glhf_t = now
        delay = 1.0 + self.rng.random()
        for p in self.players():
            if voice(p) is not None and p.team != "spectator":
                self.say(p.id, self.rng.choice(GLHF), delay)
                delay += 0.8 + self.rng.random()
                lv = aim_level() if voice(p) == 0 else None  # (!aim, owner, 2026-10-21) BobbyBones says his aim level
                if lv:
                    self.say(p.id, "Aim ^2{}^7 (^2!aim worse|default|better|max^7 to change)".format(lv), delay)
                    delay += 0.8 + self.rng.random()

    # ------------------------------------------------------------------ a game's start and end
    def new_game(self):
        self.said = {}
        self.lines.new_game()

    def on_game_start(self, data):
        self.new_game()

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
            self.say(p.id, self.lines.pick(voice(p), kind), delay)
            delay += 1.2 + self.rng.random()
            lad = minqlx.Plugin._loaded_plugins.get("ladder")      # (owner, 2026-10-16) after a full duel BobbyBones says his
            if voice(p) == 0 and lad is not None and time.time() - getattr(lad, "full_duel_t", 0.0) < 10.0:   # rating and record
                try:
                    for line_ in lad.end_lines():            # (one chat line each: a long one is cut off)
                        self.say(p.id, line_, delay)
                        delay += 1.2 + self.rng.random()
                except Exception:                            # noqa: BLE001
                    pass
                try:                                         # (!aim, owner, 2026-10-21) a line by the result and his aim
                    people = [q for q in table if not is_bot(q)]
                    line_ = aim_gg_line(aim_level(), people[0].stats.score, p.stats.score) if len(people) == 1 else None
                    if line_:
                        self.say(p.id, line_, delay)
                        delay += 1.2 + self.rng.random()
                except Exception:                            # noqa: BLE001
                    pass
            if voice(p) == 0 and lad is not None and hasattr(lad, "report_lines"):   # (owner, 2026-10-25) the game history,
                try:                                         # after any recorded game (a quit too), with the shared board on
                    for line_ in lad.report_lines():
                        self.say(p.id, line_, delay)
                        delay += 1.2 + self.rng.random()
                except Exception:                            # noqa: BLE001
                    pass
        self.new_game()

    def on_map(self, mapname, factory):
        self.queue, self.hist = [], {}
        self.new_game()

    def cmd_banter(self, player, msg, channel):
        n = 0
        for p in self.players():
            if voice(p) is not None:
                kind = self.rng.choice(("first", "upset_win"))
                self.say(p.id, self.lines.pick(voice(p), kind, name=clean(player.clean_name)), 0.5 + 1.2 * n)
                n += 1
        player.tell("{} bots will each say a line.".format(n))
        return minqlx.RET_STOP_ALL
