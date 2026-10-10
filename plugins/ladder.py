"""The leaderboard of a BobbyBones server (owner, 2026-10-09: "keep it local to this server, and base it on all
interactions with the bots from humans (meaning warmup is included)").

Every frag between a person and BobbyBones counts, in warmup and in games, in free-for-all and in 1v1; nothing else does
(plugins/ratings.py has the rules and the arithmetic: Glicko-1, one update per frag). Who made a frag is read from the
game's own counters each frame: the player whose deaths went up and the player whose kills went up in the same frame.
That works in warmup too, where the game sends no kill events. A frame in which that does not pair up (two frags by
different players at once) is left out.

    !bobby          BobbyBones' rating and rank
    !top            the board
    !elo [name]     your rating and rank (or somebody else's)
    !ladder         (the owner) what the plugin has read since it was loaded: deaths seen, paired with a killer, counted

Files in the server's data folder, outside the image and the repo: ratings.json (per player: an anonymous key, the name
he was last seen with, rating, RD, frags made and taken against Bobby) and frags.jsonl (every counted frag, keys only).
Bobby has one row per network (bobby:<run>); a new network starts at the last one's rating.

Load with QLX_PLUGINS="botctl, banlist, ladder, botmode, <duelbot|ffabot>". LADDER_TEST=1 (tests without a person) counts
the second Bobby of a free-for-all as a person.
"""
import hashlib
import importlib
import json
import os
import sys
import time

import minqlx

try:
    _ra = importlib.import_module(__package__ + ".ratings")
except Exception:                                           # noqa: BLE001 - loaded outside the plugin package
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _ra = importlib.import_module("ratings")

D = os.environ.get("LADDER_DIR", "/tmp/practice")
TEST = bool(os.environ.get("LADDER_TEST"))
TOP = 8


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class ladder(minqlx.Plugin):
    WELCOME = ("^3See how I rank on the leaderboard:^7 ^2!bobby^7 shows my rating and rank, ^2!top^7 the board, ^2!elo^7 yours. "
               "Every frag between you and me counts.")
    HELP = ("^3Leaderboard:^7 every frag between a person and me counts, in warmup and in games. ^2!bobby^7 my rating and rank, "
            "^2!top^7 the board, ^2!elo^7 yours (ranked from {} frags with me; the board shows the name you play under).".format(_ra.MIN_FRAGS))

    def __init__(self):
        super().__init__()
        self.table = _ra.Table(os.path.join(D, "ratings.json"))
        self.prev = {}                                       # client id -> (steam id, kills, deaths) last frame
        self.next_save = 0.0
        self.seen = dict(deaths=0, own=0, paired=0, counted=0, unsure=0)   # since the plugin was loaded (see cmd_ladder)
        self.salt = None
        self.listeners = []                                  # called with (killer or None, victim) for every death read (plugins/banter.py)
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.add_hook("unload", self.on_unload)
        self.add_command("bobby", self.cmd_bobby, 0)
        self.add_command("top", self.cmd_top, 0)
        self.add_command("elo", self.cmd_elo, 0, usage="[name]")
        self.add_command("ladder", self.cmd_ladder, 5)

    # ------------------------------------------------------------------ who is who
    def bot_plugin(self):
        """the plugin that plays Bobby now (duelbot or ffabot), once its network is loaded"""
        for name in ("ffabot", "duelbot"):
            pl = minqlx.Plugin._loaded_plugins.get(name)
            if pl is not None and getattr(pl, "ready", False) and getattr(pl, "P", None) is not None:
                return pl
        return None

    def bobby_key(self):
        pl = self.bot_plugin()
        return None if pl is None else _ra.BOT + str(pl.P["run"])

    def key(self, p):
        """an anonymous key for a person: the same on this server every time, no Steam ID kept (the salt is the one of the
        session logs' subject ids)"""
        if self.salt is None:
            path = os.path.join(D, "salt.txt")
            if not os.path.exists(path):
                with open(path, "w") as f:
                    f.write(hashlib.sha1(os.urandom(32)).hexdigest())
            self.salt = open(path).read().strip()
        return hashlib.sha1((self.salt + str(p.steam_id)).encode()).hexdigest()[:10]

    def who(self, p, bobby, names=("BobbyBones",)):
        """(key, name) of a player who counts, or None: a person, or Bobby himself. All of the server's bots (their names:
        duelbot.BOT_NAMES) are the one network and share his row."""
        if is_bot(p):
            if not any(n in p.clean_name for n in names):
                return None                                  # one of the game's own bots (a spar)
            if TEST and len(names) > 1 and names[1] in p.clean_name:
                return "test000002", "test player"
            return bobby, "BobbyBones ({})".format(_ra.label(bobby[len(_ra.BOT):]))
        return self.key(p), p.clean_name[:24]

    # ------------------------------------------------------------------ frags
    def on_frame(self):
        pl = self.bot_plugin()
        if pl is None or getattr(pl, "room", None) is not None:      # no network playing, or a test room (Bobby's body is a scripted target there)
            self.prev = {}
            return
        cur, died, scored = {}, [], []
        try:
            for p in self.players():
                if p.team == "spectator":
                    continue
                st = p.stats
                cur[p.id] = (p.steam_id, st.kills, st.deaths)
                old = self.prev.get(p.id)
                if old is not None and old[0] == p.steam_id:
                    if st.deaths == old[2] + 1:
                        died.append(p)
                    if st.kills == old[1] + 1:
                        scored.append(p)
        except Exception:                                    # noqa: BLE001 - a player left in the middle of the frame
            self.prev = {}
            return
        self.prev = cur
        self.seen["deaths"] += len(died)
        if not died or not scored:                           # nobody died, or by his own hand or the map
            self.seen["own"] += len(died)
            for p in died:
                self.tell_listeners(None, p)
            return
        if len(died) == 1 and len(scored) == 1 and died[0].id != scored[0].id:
            pairs = [(scored[0], died[0])]
        elif len(died) == 2 and len(scored) == 2 and {p.id for p in died} == {p.id for p in scored}:
            pairs = [(died[1], died[0]), (died[0], died[1])]         # the two killed each other
        else:
            self.seen["unsure"] += len(died)
            return
        self.seen["paired"] += len(pairs)
        bobby = _ra.BOT + str(pl.P["run"])
        names = getattr(pl, "BOT_NAMES", ("BobbyBones",))
        for killer, victim in pairs:
            self.tell_listeners(killer, victim)
            a, b = self.who(killer, bobby, names), self.who(victim, bobby, names)
            if a is None or b is None or (a[0] == bobby) == (b[0] == bobby):
                continue                                     # a frag between two people, or between two Bobbys
            now = time.time()
            self.seen["counted"] += 1
            ra, rb = self.table.frag(a[0], a[1], b[0], b[1], now)
            try:
                with open(os.path.join(D, "frags.jsonl"), "a") as f:
                    f.write(json.dumps(dict(t=round(now, 2), map=(minqlx.get_cvar("mapname") or "").lower(),
                                            state=self.game.state if self.game is not None else None,
                                            mode=getattr(pl, "FACTORY", "duel"), net=str(pl.P["run"]), killer=a[0], victim=b[0],
                                            r=[round(ra["r"], 1), round(rb["r"], 1)])) + "\n")
            except OSError:
                pass
        if time.time() > self.next_save:
            self.next_save = time.time() + 20
            self.table.save()

    def tell_listeners(self, killer, victim):
        for fn in self.listeners:
            try:
                fn(killer, victim)
            except Exception:                                # noqa: BLE001 - a listener's fault is not the ladder's
                pass

    def on_map(self, mapname, factory):
        self.prev = {}
        self.table.save()

    def on_unload(self, plugin):
        self.table.save()

    # ------------------------------------------------------------------ commands
    @staticmethod
    def line(n, p, mark=""):
        return "{:>2}. {:24s} {:4.0f}{}".format(n if n else "-", p["name"], p["r"], mark)

    # (a percent sign must be followed by ")" in these lines: the game takes "% h" and the like for a printf format)
    def cmd_bobby(self, player, msg, channel):
        bobby = self.bobby_key()
        p = self.table.players.get(bobby) if bobby else None
        if p is None:
            player.tell("^3BobbyBones has no rating yet:^7 it starts with the first frag between him and a person.")
            return minqlx.RET_STOP_ALL
        n, of = self.table.rank(bobby, bobby)
        tot = p["won"] + p["lost"]
        player.tell("^3{}^7: rating ^2{:.0f}^7 (+-{:.0f}), rank ^2{}^7 of {} on the board. Frags with people: {} made, {} taken (his share {:.0%}).".format(
            p["name"], p["r"], 2 * p["rd"], n, of, p["won"], p["lost"], p["won"] / max(1, tot)))
        old = self.table.earlier(bobby)[:3]
        if old:
            player.tell("Earlier networks: " + ", ".join("{} {:.0f}".format(_ra.label(k[len(_ra.BOT):]), q["r"]) for k, q in old))
        return minqlx.RET_STOP_ALL

    def cmd_top(self, player, msg, channel):
        bobby = self.bobby_key()
        rows = self.table.board(bobby)
        if not rows:
            player.tell("^3The board is empty:^7 a person is ranked from {} frags with BobbyBones.".format(_ra.MIN_FRAGS))
            return minqlx.RET_STOP_ALL
        me = None if is_bot(player) else self.key(player)
        player.tell("^3Leaderboard^7 ({} ranked; every frag between a person and BobbyBones counts):".format(len(rows)))
        for n, (k, p) in enumerate(rows, 1):
            if n <= TOP or k in (bobby, me):
                player.tell(("^2" if k == bobby else "^5" if k == me else "") + self.line(n, p) + "^7")
        return minqlx.RET_STOP_ALL

    def cmd_elo(self, player, msg, channel):
        bobby = self.bobby_key()
        if len(msg) > 1:
            want = " ".join(msg[1:]).lower()
            hits = [(k, p) for k, p in self.table.players.items() if want in p["name"].lower()]
            if len(hits) != 1:
                player.tell("^3{} players on the board match '{}'.".format(len(hits), want))
                return minqlx.RET_STOP_ALL
            k, p = hits[0]
        else:
            k = self.key(player)
            p = self.table.players.get(k)
            if p is None:
                player.tell("^3You have no rating yet:^7 it starts with your first frag with BobbyBones, either way.")
                return minqlx.RET_STOP_ALL
        n, of = self.table.rank(k, bobby)
        tot = p["won"] + p["lost"]
        where = "rank ^2{}^7 of {}".format(n, of) if n else "ranked after {} more frags with BobbyBones".format(max(0, _ra.MIN_FRAGS - tot))
        player.tell("^3{}^7: rating ^2{:.0f}^7 (+-{:.0f}), {}. Frags with BobbyBones: {} made, {} taken (a share of {:.0%}).".format(
            p["name"], p["r"], 2 * p["rd"], where, p["won"], p["lost"], p["won"] / max(1, tot)))
        return minqlx.RET_STOP_ALL

    def cmd_ladder(self, player, msg, channel):
        s = self.seen
        player.tell("ladder since its load: {} deaths seen, {} by his own hand or the map, {} paired with a killer ({} of them counted: "
                    "a person and Bobby), {} left out (more than one frag in a frame); {} rows in the table.".format(
                        s["deaths"], s["own"], s["paired"], s["counted"], s["unsure"], len(self.table.players)))
        return minqlx.RET_STOP_ALL
