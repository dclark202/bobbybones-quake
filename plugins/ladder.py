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
    !qlstats off|on (only with QLSTATS=1) stop or allow the lookup of your public QLStats rating

Files in the server's data folder, outside the image and the repo: ratings.json (per player: an anonymous key, the name
he was last seen with, rating, RD, frags made and taken against Bobby) and frags.jsonl (every counted frag, keys only).
Bobby has one row per network (bobby:<run>); a new network starts at the last one's rating.

The owner (owner, 2026-10-12: "Mark me as the owner, I will likely have the most game time against him and may be running
tests which could corrupt the data"): the person whose Steam id is the server's QLX_OWNER (as plugins/banlist.py knows
him) gets "owner": true on his row of ratings.json and "owner": 1 on every frag line of his in frags.jsonl, so that the
PC's tools can set his games apart. Neither his id nor his name goes anywhere new; nothing else changes for him.

A person's key for the session logs: person_key() (duelbot.note_person writes it beside the seat he takes).

Finished duels: duels.jsonl, one line per finished duel between one person and Bobby in 1v1 mode, a real game (F3) or a
timed one (!duel): {t, map, net, key, owner, minutes, score: [person, bobby], forfeit, kind: game | timed}.

QLStats (docs/design/QLSTATS.md, section 4; owner, 2026-10-12: "Build the qlstats lookup"). OFF unless the server is
started with QLSTATS=1; QLSTATS_URL sets the service's address (default https://qlstats.net). At a person's first join of
a day a background thread asks <address>/glicko/<Steam id> and /elo/<Steam id> (3 s to connect, 5 s to answer, one try,
one person at a time) and the answer is written in the next frame: qlstats.json (the latest answer per anonymous key:
{t, status: ok | none | untracked | deactivated | error, duel: {r, rd, games}, ffa: {r, rd, games}, team}) and
qlstats.jsonl (every answer, appended). The Steam id is in the request and nowhere else: never in a file, never in a log
(an error is kept by its class name only: its text and the address hold the id). "!qlstats off" drops a person's stored
answers and stops the lookups for him (qlstats_off.json, by key).

One board for both public servers (owner, 2026-10-23; plugins/ratings.py has the scheme): a server that knows its name
(LADDER_SRV, or one word in srv.txt in the data folder, e.g. "us") tags its frag and duel lines with it ("srv") and plays
on board.json, the shared board that tools/board_merge.py writes into its data folder every few minutes, plus its own
lines after the board's "upto" mark for it. The plugin never writes board.json; it looks for a new one every 30 s and at
a map change. Without a name, or without a board that names this server, it is the local board it always was
(ratings.json). ratings.json is still written: this server's view (the board and its own frags since).

Load with QLX_PLUGINS="botctl, banlist, ladder, botmode, <duelbot|ffabot>". LADDER_TEST=1 (tests without a person) counts
the second Bobby of a free-for-all as a person.
"""
import copy
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
PAGE = "dclark202.github.io/bobbybones-leaderboard"          # the public page of the shared board (published twice a day)
BOARD_EVERY = 30.0                                           # seconds between looks for a new board.json


def server_name():
    """this server's name on the shared board: LADDER_SRV, else the first word of srv.txt in the data folder; None if
    neither (a local board)"""
    import re
    v = (os.environ.get("LADDER_SRV") or "").strip()
    if not v:
        try:
            with open(os.path.join(D, "srv.txt")) as f:
                v = (f.read().split() or [""])[0]
        except OSError:
            v = ""
    v = v.lower()
    return v if re.match(r"^[a-z0-9]{1,8}$", v) else None


SRV = server_name()

# ---------------------------------------------------------------------- QLStats (off unless QLSTATS=1)
QL_ON = os.environ.get("QLSTATS") == "1"
QL_URL = (os.environ.get("QLSTATS_URL") or "https://qlstats.net").rstrip("/")
QL_AGENT = "BobbyBones-quake ladder plugin (github.com/dclark202/bobbybones-quake)"
QL_TIMEOUT = (3, 5)                                          # seconds to connect, seconds to answer; one try
QL_FRESH = dict(ok=86400.0, none=86400.0, deactivated=86400.0, error=3600.0, untracked=30 * 86400.0)   # no new request before
QL_TEAM = ("ca", "tdm", "ctf", "ft", "ad")                   # "team": 20 games or more in one of these
QL_TEAM_GAMES = 20


def ql_ask(base, sid, timeout=QL_TIMEOUT):
    """One person's answer from QLStats as plain values: {status, duel, ffa, team, err}. It runs in a background thread
    and touches nothing of minqlx. It never raises, and nothing it returns holds an error's text or the address asked
    (both contain the Steam id, and the raw logs are taken off the server every day): an error is its class name, a bad
    answer "http503" or "notjson". /elo carries the lists of untracked and deactivated players and is the fallback for
    the numbers; /glicko has r, rd and games. A rating with 0 games is no rating (the service answers 900 with 0 games
    for a player it does not know)."""
    out = dict(status="error", duel=None, ffa=None, team=False, err=None)
    try:
        import requests
        sid = str(sid)

        def get(path):
            try:
                r = requests.get("{}/{}/{}".format(base, path, sid), headers={"User-Agent": QL_AGENT}, timeout=timeout)
            except Exception as e:                           # noqa: BLE001 - its text holds the address: the class only
                return None, type(e).__name__, True
            if r.status_code != 200:
                return None, "http{}".format(int(r.status_code)), False
            try:
                d = r.json()
            except Exception:                                # noqa: BLE001
                return None, "notjson", False
            return (d, None, False) if isinstance(d, dict) else (None, "notjson", False)

        gl, gerr, down = get("glicko")
        if down:                                             # no answer at all: the second request would only wait again
            out["err"] = gerr
            return out
        el, eerr, down = get("elo")
        if el is None:                                       # who is untracked or deactivated is known from /elo alone
            out["err"] = eerr
            return out

        def listed(d, name):
            return any(str(x) == sid for x in ((d or {}).get(name) or []))

        def mine(d):
            return next((p for p in ((d or {}).get("players") or []) if isinstance(p, dict) and str(p.get("steamid")) == sid), {})

        if listed(el, "untracked"):
            out["status"] = "untracked"
            return out
        pg, pe = mine(gl), mine(el)

        def games(p, gt):
            v = p.get(gt)
            try:
                return int(v.get("games") or 0) if isinstance(v, dict) else 0
            except (TypeError, ValueError):
                return 0

        def rating(gt):
            if games(pg, gt) > 0:
                return dict(r=int(round(float(pg[gt]["r"]))), rd=int(round(float(pg[gt]["rd"]))), games=games(pg, gt))
            if games(pe, gt) > 0:
                return dict(r=int(round(float(pe[gt]["elo"]))), rd=None, games=games(pe, gt))
            return None

        out["duel"], out["ffa"] = rating("duel"), rating("ffa")
        out["team"] = any(max(games(pg, gt), games(pe, gt)) >= QL_TEAM_GAMES for gt in QL_TEAM)
        info = (el.get("playerinfo") or {}).get(sid) if isinstance(el.get("playerinfo"), dict) else None
        dead = listed(el, "deactivated") or listed(gl, "deactivated") or bool(isinstance(info, dict) and info.get("deactivated"))
        out["status"] = "deactivated" if dead else "ok" if (out["duel"] or out["ffa"]) else "none"
        if gl is None:
            out["err"] = gerr                                # /glicko closed or broken: the numbers are /elo's, without rd
        return out
    except Exception as e:                                   # noqa: BLE001 - never the text
        return dict(status="error", duel=None, ffa=None, team=False, err=type(e).__name__)


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class ladder(minqlx.Plugin):
    WELCOME = ("^3This server has a local leaderboard:^7 see my rank ^2!bobby^7 (^2!top^7 for the whole board). "
               "Every frag between you and me counts ^6(including warmup)^7")
    HELP = ("^3Leaderboard:^7 every frag between a person and me counts, in warmup and in games. ^2!bobby^7 my rating and rank, "
            "^2!top^7 the board, ^2!elo^7 yours (ranked from {} frags with me; the board shows the name you play under).".format(_ra.MIN_FRAGS))

    def __init__(self):
        super().__init__()
        self.table = _ra.Table(os.path.join(D, "ratings.json"))
        self.board, self.board_mt, self.board_up, self.next_board = None, None, {}, 0.0   # the shared board (see the top)
        self.board_n = dict(loads=0, tail=0)
        self.board_check()
        minqlx.console_print("[ladder] board: {}\n".format(self.board_state()))
        self.prev = {}                                       # client id -> (steam id, kills, deaths) last frame
        self.next_save = 0.0
        self.seen = dict(deaths=0, own=0, paired=0, counted=0, unsure=0)   # since the plugin was loaded (see cmd_ladder)
        self.salt = None
        self.listeners = []                                  # called with (killer or None, victim) for every death read (plugins/banter.py)
        self.duel = None                                     # a real 1v1 game between one person and Bobby (see on_game_start)
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.add_hook("unload", self.on_unload)
        self.add_hook("game_start", self.on_game_start)
        self.add_hook("game_end", self.on_game_end)
        self.add_command("bobby", self.cmd_bobby, 0)
        self.add_command("top", self.cmd_top, 0)
        self.add_command("elo", self.cmd_elo, 0, usage="[name]")
        self.add_command("ladder", self.cmd_ladder, 5)
        # QLStats: nothing of it exists unless the server was started with QLSTATS=1 (no hook, no command, no thread)
        self.ql, self.ql_off = {}, set()                     # key -> the latest answer; the keys of those who switched it off
        self.ql_queue, self.ql_busy, self.ql_tell = [], 0.0, {}   # (key, Steam id) waiting; when the one in flight left; key -> client to tell
        self.ql_cur = None                                   # the key of the request in flight
        self.ql_n = dict(asked=0, answered=0)
        if QL_ON:
            self.ql = self.ql_load("qlstats.json", {})
            self.ql_off = set(self.ql_load("qlstats_off.json", []))
            self.add_hook("player_loaded", self.on_player_loaded)
            self.add_command("qlstats", self.cmd_qlstats, 0, usage="<off|on>")
        minqlx.console_print("[ladder] qlstats: {}\n".format(
            "on ({} answers stored, {} people switched it off)".format(len(self.ql), len(self.ql_off)) if QL_ON else "off"))

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

    def person_key(self, p):
        """a person's key for the session logs (duelbot.note_person writes it beside the seat he takes, so that a
        session's frames can be tied to the leaderboard); None for a bot. No name and no Steam id leave here."""
        try:
            return None if is_bot(p) else self.key(p)
        except Exception:                                    # noqa: BLE001 - a log line is never worth a frame
            return None

    def is_owner(self, p):
        """is this person the server's owner (QLX_OWNER, as plugins/banlist.py knows him)? His games are marked, so that
        they can be set apart; the id itself is compared here and written nowhere."""
        try:
            if is_bot(p) or not (minqlx.get_cvar("qlx_owner") or "").strip().isdigit():
                return False
            return str(p.steam_id) == str(minqlx.owner())
        except Exception:                                    # noqa: BLE001
            return False

    def who(self, p, bobby, names=("BobbyBones",)):
        """(key, name) of a player who counts, or None: a person, or Bobby himself. All of the server's bots (their names:
        duelbot.BOT_NAMES) are the one network and share his row."""
        if is_bot(p):
            if not any(n in p.clean_name for n in names):
                return None                                  # one of the game's own bots (a spar)
            if TEST and len(names) > 1 and names[1] in p.clean_name:
                return "test000002", "test player"
            return bobby, "^5B^7o^5bbyB^7o^5nes^7 ({})".format(_ra.label(bobby[len(_ra.BOT):]))
        return self.key(p), p.clean_name[:24]

    # ------------------------------------------------------------------ the shared board (several servers; see the top)
    def board_check(self):
        """take a new board.json if there is one: the board, then this server's own frags after its mark, in their order.
        Only a stat of the file when nothing changed; a missing or broken board leaves the table as it is."""
        if not SRV:
            return
        path = os.path.join(D, "board.json")
        try:
            mt = os.stat(path).st_mtime_ns
        except OSError:
            return
        if mt == self.board_mt:
            return
        self.board_mt = mt
        b = _ra.load_board(path)
        up = ((b or {}).get("upto") or {}).get(SRV)
        if b is None or not isinstance(up, dict):
            minqlx.console_print("[ladder] board.json {}: the table stays as it is\n".format("broken" if b is None else "does not name this server"))
            return
        names = {k: p.get("name") for k, p in self.table.players.items()}     # (names of people new since the board)
        t = _ra.Table()
        t.path = self.table.path
        t.players = copy.deepcopy(b["players"])
        tail, _ = _ra.read_tail(os.path.join(D, "frags.jsonl"), int(up.get("frags") or 0))
        _ra.replay(t, tail, names)
        t.dirty = True
        self.table, self.board, self.board_up = t, b, up
        self.board_n["loads"] += 1
        self.board_n["tail"] = len(tail)
        self._rec = None

    def board_state(self):
        if not SRV:
            return "local (no server name)"
        if self.board is None:
            return "server {}, no shared board yet: local".format(SRV)
        return "server {}, shared board of {} UTC ({} rows, {} frags), {} of this server's frags on top; {} loads".format(
            SRV, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(float(self.board.get("saved") or 0))),
            len(self.board["players"]), self.board.get("n_frags", "?"), self.board_n["tail"], self.board_n["loads"])

    # ------------------------------------------------------------------ frags
    def on_frame(self):
        if time.time() > self.next_board:
            self.next_board = time.time() + BOARD_EVERY
            try:
                self.board_check()
            except Exception as e:                           # noqa: BLE001 - the board is never worth a frame
                minqlx.console_print("[ladder] board: {}\n".format(type(e).__name__))
        pl = self.bot_plugin()
        if pl is None or getattr(pl, "room", None) is not None:      # no network playing, or a test room (Bobby's body is a scripted target there)
            self.prev = {}
            return
        cur, died, scored, playing = {}, [], [], []
        try:
            for p in self.players():
                if p.team == "spectator":
                    continue
                st = p.stats
                cur[p.id] = (p.steam_id, st.kills, st.deaths)
                playing.append((p, st.score))
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
        if self.duel is not None:
            self.duel_track(pl, playing)
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
            line = dict(t=round(now, 2), map=(minqlx.get_cvar("mapname") or "").lower(),
                        state=self.game.state if self.game is not None else None,
                        mode=getattr(pl, "FACTORY", "duel"), net=str(pl.P["run"]), killer=a[0], victim=b[0],
                        r=[round(ra["r"], 1), round(rb["r"], 1)])
            if SRV:
                line["srv"] = SRV
            person, row = (killer, ra) if b[0] == bobby else (victim, rb)
            if self.is_owner(person):                        # the owner's frags and his row are marked (see the top)
                line["owner"] = 1
                if not row.get("owner"):
                    row["owner"] = True
                    self.table.dirty = True
            try:
                with open(os.path.join(D, "frags.jsonl"), "a") as f:
                    f.write(json.dumps(line) + "\n")
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
        self.duel = None
        self.table.save()
        try:
            self.board_check()
        except Exception as e:                               # noqa: BLE001
            minqlx.console_print("[ladder] board: {}\n".format(type(e).__name__))

    def on_unload(self, plugin):
        self.table.save()

    # ------------------------------------------------------------------ finished duels (duels.jsonl)
    @staticmethod
    def version_of(net):
        """the docs' version name of a run (as sim/export_duel.py: duel_gru_v0_3_1b -> v0.3.1, duel_gru_v15c -> v0.1)"""
        return _ra.version_of(net)

    FORFEIT_WIN_MIN = 5.0                                  # (owner, 2026-10-24) minutes after which a quit while behind is his win

    def duel_record(self):
        """(owner, 2026-10-16) Bobby's record in full duel games against people: real games (kind "game"), the owner's games
        included (owner, 2026-10-16). A forfeit (the person left before the end) counts as Bobby's win when it came after more than
        FORFEIT_WIN_MIN minutes with Bobby ahead (owner, 2026-10-24); any other forfeit is left out (ratings.duel_result).
        Returns {version: [won, lost, drawn]} with "all" for every version together.
        With the shared board: the board's record of every server, and this server's own duels after its mark."""
        path = os.path.join(D, "duels.jsonl")
        try:
            mt = os.path.getmtime(path)
        except OSError:
            mt = None
        if mt is None and self.board is None:
            return {"all": [0, 0, 0]}
        if getattr(self, "_rec", None) and self._rec[0] == (mt, self.board_mt):
            return self._rec[1]
        if self.board is not None:
            out = {k: list(v) for k, v in (self.board.get("duels") or {}).items()}
            out.setdefault("all", [0, 0, 0])
            lines, _ = _ra.read_tail(path, int(self.board_up.get("duels") or 0))
        else:
            out = {"all": [0, 0, 0]}
            lines, _ = _ra.read_tail(path, 0)
        for d in lines:
            k_ = _ra.duel_result(d)
            if k_ is None:
                continue
            for v_ in ("all", self.version_of(d.get("net", ""))):
                out.setdefault(v_, [0, 0, 0])[k_] += 1
        self._rec = ((mt, self.board_mt), out)
        return out

    @staticmethod
    def wld(r):
        """won-lost, and -drawn only if there was a draw"""
        return "{}-{}".format(r[0], r[1]) + ("-{}".format(r[2]) if r[2] else "")

    def record_line(self):
        """the welcome's line: "Duel record (full games): v0.3.1 0-0 | all versions 0-37" (the network playing now first)"""
        rec = self.duel_record()
        pl = self.bot_plugin()
        ver = pl.bot_version() if pl is not None and hasattr(pl, "bot_version") else None
        cur = "^2{}^7 ^5{}^7 | ".format(ver, self.wld(rec.get(ver, [0, 0, 0]))) if ver else ""
        return "^3Duel record^7 (full games): {}all versions ^5{}^7".format(cur, self.wld(rec["all"]))

    def end_lines(self):
        """what Bobby says after a finished duel (owner, 2026-10-16: "he should also tell his elo and overall record at the
        end of a duel match"; on two lines, the chat box cut one off): the board's rating of the network playing now, then
        the record, this game included"""
        rec = self.duel_record()
        bobby = self.bobby_key()
        p = self.table.players.get(bobby) if bobby else None
        out = []
        if p is not None:
            n, of = self.table.rank(bobby, bobby)
            out.append("my rating ^2{:.0f}^7 (rank ^3{}^7 of {})".format(p["r"], n, of))
        out.append("my duel record ^5{}^7".format(self.wld(rec["all"])))
        return out

    def on_game_start(self, data):
        """a real game began: in 1v1 mode it is a duel between the person and Bobby, written down at its end. Who plays
        is read in the frames after (at the start the game's bots are between teams for a moment)."""
        pl = self.bot_plugin()
        self.duel = dict(t0=time.time(), score=[0, 0]) if pl is not None and getattr(pl, "FACTORY", "duel") == "duel" else None

    def duel_track(self, pl, playing):
        """the two of a running duel and their score, kept every frame: at the end the person may be gone"""
        d = self.duel
        try:
            names = getattr(pl, "BOT_NAMES", ("BobbyBones",))
            people = [(p, sc) for p, sc in playing if not is_bot(p)]
            bots = [(p, sc) for p, sc in playing if is_bot(p) and any(n in p.clean_name for n in names)]
            if "key" not in d:
                if len(people) == 1 and len(bots) == 1 and len(playing) == 2:
                    d.update(key=self.key(people[0][0]), owner=int(self.is_owner(people[0][0])), net=str(pl.P["run"]), left=False)
                return
            mine = [(p, sc) for p, sc in people if self.key(p) == d["key"]]
            d["left"] = not mine
            if mine and bots:
                d["score"] = [int(mine[0][1]), int(bots[0][1])]
        except Exception:                                    # noqa: BLE001 - a player left in the middle of the frame
            pass

    def on_game_end(self, data):
        d, self.duel = self.duel, None
        try:
            if not d or "key" not in d or not isinstance(data, dict) or data.get("ABORTED"):
                return                                       # no duel, or thrown back to warmup: not a finished one
            msg = str(data.get("EXIT_MSG") or "").lower()
            secs = float(data.get("GAME_LENGTH") or (time.time() - d["t0"]))
            limit = float(minqlx.get_cvar("timelimit") or 0) * 60.0
            forfeit = d.get("left") or "forfeit" in msg or ("limit hit" not in msg and limit > 0 and secs < limit - 5)
            self.note_duel(d["key"], d["owner"], secs / 60.0, d["score"][0], d["score"][1], forfeit, "game", net=d["net"])
            if not forfeit:
                self.full_duel_t = time.time()               # (plugins/banter.py: Bobby says his rating and record after his gg)
        except Exception as e:                               # noqa: BLE001
            minqlx.console_print("[ladder] duel: {}\n".format(type(e).__name__))

    def note_duel(self, key, owner, minutes, person, bobby, forfeit, kind, net=None):
        """one finished duel between a person and Bobby: a real game of the 1v1 mode ("game", from on_game_end) or a
        timed one in warmup ("timed": !duel, from duelbot.arena_end). Keys only, no name."""
        try:
            pl = self.bot_plugin()
            if net is None:
                net = str(pl.P["run"]) if pl is not None else ""
            try:                                             # (owner, 2026-10-23) the aim level the duel was played at
                aim = pl.aim_level() if pl is not None and hasattr(pl, "aim_level") else ""
            except Exception:                                # noqa: BLE001
                aim = ""
            line = dict(t=round(time.time(), 2), map=(minqlx.get_cvar("mapname") or "").lower(), net=net, key=key,
                        owner=int(bool(owner)), minutes=round(float(minutes), 2), score=[int(person), int(bobby)],
                        forfeit=int(bool(forfeit)), kind=kind, aim=str(aim))
            if SRV:
                line["srv"] = SRV
            with open(os.path.join(D, "duels.jsonl"), "a") as f:
                f.write(json.dumps(line) + "\n")
        except Exception as e:                               # noqa: BLE001
            minqlx.console_print("[ladder] duel: {}\n".format(type(e).__name__))

    # ------------------------------------------------------------------ QLStats (docs/design/QLSTATS.md); all of it behind QL_ON
    QL_WELCOME = ("I look up your public ^5QLStats^7 rating (your Steam id goes to qlstats.net) to see how strong my "
                  "opponents are. ^2!qlstats off^7 stops it.")

    SHARED_WELCOME = ("^3Both BobbyBones servers (US and EU) share one leaderboard:^7 see my rank ^2!bobby^7 (^2!top^7 for the "
                      "whole board). Every frag between you and me counts ^6(including warmup)^7")
    PAGE_LINE = "^3The leaderboard on the web^7 (updated twice a day): ^5" + PAGE

    def welcome_lines(self, player):
        """what a person is told about the leaderboard on joining (duelbot.on_player_loaded)"""
        out = [self.SHARED_WELCOME, self.PAGE_LINE] if self.board is not None else [self.WELCOME]
        try:
            rec_ = self.record_line()
            if rec_:
                out.append(rec_)
        except Exception:                                    # noqa: BLE001
            pass
        try:
            if QL_ON and not is_bot(player) and self.key(player) not in self.ql_off:
                out.append(self.QL_WELCOME)
        except Exception:                                    # noqa: BLE001
            pass
        return out

    @staticmethod
    def ql_load(name, default):
        try:
            with open(os.path.join(D, name), encoding="utf-8") as f:
                d = json.load(f)
            return d.get("players" if name == "qlstats.json" else "keys", default)
        except Exception:                                    # noqa: BLE001 - no file yet, or a broken one: start empty
            return default

    @staticmethod
    def ql_write(name, obj):
        try:
            path = os.path.join(D, name)
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=1)
            os.replace(path + ".tmp", path)
        except OSError:
            pass

    def ql_save(self):
        self.ql_write("qlstats.json", dict(schema=1, saved=round(time.time(), 1), players=self.ql))

    def ql_fresh(self, key, now):
        """is there an answer for this key that is not to be asked for again yet (a day; an hour after a failure; thirty
        days for a player QLStats does not track)"""
        row = self.ql.get(key)
        if row is None:
            return False
        if now - row.get("tried", 0.0) < QL_FRESH["error"]:
            return True
        return now - row.get("t", 0.0) < QL_FRESH.get(row.get("status"), QL_FRESH["error"])

    def ql_want(self, p):
        """a lookup for this person, unless he switched it off or his answer is fresh"""
        if not QL_ON or is_bot(p) or isinstance(p, minqlx.AbstractDummyPlayer):
            return
        key = self.key(p)
        if key in self.ql_off or self.ql_fresh(key, time.time()):
            return
        if key != getattr(self, "ql_cur", None) and all(k != key for k, _ in self.ql_queue):
            self.ql_queue.append((key, str(p.steam_id)))     # (the id waits here in memory and goes into the request: nowhere else)
        self.ql_pump()

    def ql_pump(self):
        """start the next request if none is in flight (one at a time; a thread not heard of for a minute is given up)"""
        now = time.time()
        if self.ql_busy and now - self.ql_busy < 60.0:
            return
        self.ql_busy, self.ql_cur = 0.0, None
        if not self.ql_queue:
            return
        key, sid = self.ql_queue.pop(0)
        self.ql_busy, self.ql_cur = now, key
        self.ql_n["asked"] += 1
        self.ql_fetch(key, sid, QL_URL)

    @minqlx.thread
    def ql_fetch(self, key, sid, base):
        """the background thread: plain values in, a plain answer out (ql_ask), handed to the next frame"""
        self.ql_done(key, ql_ask(base, sid))

    @minqlx.next_frame
    def ql_done(self, key, res):
        """the main thread, a frame later: the only place the answers are written"""
        if minqlx.Plugin._loaded_plugins.get("ladder") is not self:
            return                                           # the plugin was loaded anew while the thread ran
        now = time.time()
        if getattr(self, "ql_cur", None) == key:
            self.ql_busy, self.ql_cur = 0.0, None
        self.ql_n["answered"] += 1
        status = str(res.get("status") or "error")
        minqlx.console_print("[ladder] qlstats: an answer ({}{})\n".format(status, ", " + str(res["err"])[:40] if res.get("err") else ""))
        if key not in self.ql_off:                           # (switched off while the request was out: nothing is kept)
            row = dict(t=round(now, 1), status=status, duel=res.get("duel"), ffa=res.get("ffa"), team=bool(res.get("team")))
            if res.get("err"):
                row["err"] = str(res["err"])[:40]
            try:
                with open(os.path.join(D, "qlstats.jsonl"), "a") as f:
                    f.write(json.dumps(dict(key=key, **row)) + "\n")
            except OSError:
                pass
            old = self.ql.get(key)
            if status == "error" and old is not None and old.get("status") != "error":
                old["tried"] = round(now, 1)                 # the last real answer stays; the next try in an hour
            else:
                self.ql[key] = row
            self.ql_save()
            cid = self.ql_tell.pop(key, None)
            if cid is not None:                              # he asked with !elo: tell him, if he still sits there
                try:
                    p = next((q for q in self.players() if q.id == cid and not is_bot(q)), None)
                    if p is not None and self.key(p) == key:
                        p.tell(self.ql_line(self.ql.get(key)))
                except Exception:                            # noqa: BLE001
                    pass
        self.ql_pump()

    @staticmethod
    def ql_line(row):
        """the line of !elo about QLStats (no percent sign: see cmd_bobby)"""
        if row is None or row.get("status") == "error":
            return "^3QLStats^7 did not answer just now."

        def part(gt):
            r = row.get(gt)
            if not r:
                return None
            return "{} ^2{}^7 ({}{} games)".format(gt, r["r"], "+-{}, ".format(r["rd"]) if r.get("rd") is not None else "", r["games"])
        duel, ffa = part("duel"), part("ffa")
        if duel:
            return "^3QLStats (global):^7 " + duel + (", " + ffa if ffa else "")
        return "^3QLStats^7 has no duel rating for you" + ("; global ffa: " + ffa[4:] if ffa else "") + "."

    def ql_say(self, player, key):
        """the second line of a person's own !elo: from the stored answer, or from the thread's when it comes"""
        if key in self.ql_off:
            player.tell("^3QLStats:^7 off for you (^2!qlstats on^7 allows the lookup).")
        elif self.ql_fresh(key, time.time()):
            player.tell(self.ql_line(self.ql.get(key)))
        else:
            self.ql_tell[key] = player.id
            self.ql_want(player)

    def on_player_loaded(self, player):
        try:
            self.ql_want(player)
        except Exception as e:                               # noqa: BLE001 - never the text
            minqlx.console_print("[ladder] qlstats: {}\n".format(type(e).__name__))

    def cmd_qlstats(self, player, msg, channel):
        if is_bot(player) or isinstance(player, minqlx.AbstractDummyPlayer):
            return minqlx.RET_STOP_ALL
        if len(msg) < 2 or msg[1].lower() not in ("off", "on"):
            return minqlx.RET_USAGE
        key = self.key(player)
        if msg[1].lower() == "off":
            self.ql_off.add(key)
            self.ql.pop(key, None)
            self.ql_tell.pop(key, None)
            self.ql_queue = [q for q in self.ql_queue if q[0] != key]
            self.ql_save()
            self.ql_write("qlstats_off.json", dict(schema=1, keys=sorted(self.ql_off)))
            try:                                             # his lines leave the history too
                path = os.path.join(D, "qlstats.jsonl")
                if os.path.exists(path):
                    with open(path) as f:
                        keep = [ln for ln in f if '"key": "{}"'.format(key) not in ln]
                    with open(path + ".tmp", "w") as f:
                        f.writelines(keep)
                    os.replace(path + ".tmp", path)
            except OSError:
                pass
            player.tell("^3QLStats:^7 off for you. What I had stored is deleted and I will not look you up again. ^2!qlstats on^7 allows it again.")
        else:
            self.ql_off.discard(key)
            self.ql_write("qlstats_off.json", dict(schema=1, keys=sorted(self.ql_off)))
            player.tell("^3QLStats:^7 on for you. ^2!elo^7 shows your global rating beside the one you have here.")
            self.ql_want(player)
        return minqlx.RET_STOP_ALL

    # ------------------------------------------------------------------ commands
    @staticmethod
    def line(n, p, mark=""):
        return "{:>2}. {:24s} {:4.0f}{}".format(n if n else "-", p["name"], p["r"], mark)

    # (a percent sign must be followed by ")" in these lines: the game takes "% h" and the like for a printf format)
    def cmd_bobby(self, player, msg, channel):
        bobby = self.bobby_key()
        p = self.table.players.get(bobby) if bobby else None
        if p is None:
            player.tell("^5B^7o^5bbyB^7o^5nes^3 has no rating yet:^7 it starts with the first frag between him and a person.")
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
            player.tell("^3The board is empty:^7 a person is ranked from {} frags with ^5B^7o^5bbyB^7o^5nes^7.".format(_ra.MIN_FRAGS))
            return minqlx.RET_STOP_ALL
        me = None if is_bot(player) else self.key(player)
        player.tell("^3Leaderboard^7 ({} ranked; every frag between a person and ^5B^7o^5bbyB^7o^5nes^7 counts{}):".format(
            len(rows), ", both servers" if self.board is not None else ""))
        for n, (k, p) in enumerate(rows, 1):
            if n <= TOP or k in (bobby, me):
                player.tell(("^2" if k == bobby else "^5" if k == me else "") + self.line(n, p) + "^7")
        if self.board is not None:
            player.tell(self.PAGE_LINE)
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
            ql = False                                       # (somebody else's line stays local: his QLStats answer is his)
        else:
            k = self.key(player)
            p = self.table.players.get(k)
            ql = QL_ON and not is_bot(player) and not isinstance(player, minqlx.AbstractDummyPlayer)
            if p is None:
                player.tell("^3You have no rating {}yet:^7 it starts with your first frag with ^5B^7o^5bbyB^7o^5nes^7, either way.".format("here " if ql else ""))
                if ql:
                    self.ql_say(player, k)
                return minqlx.RET_STOP_ALL
        n, of = self.table.rank(k, bobby)
        tot = p["won"] + p["lost"]
        where = "rank ^2{}^7 of {}".format(n, of) if n else "ranked after {} more frags with ^5B^7o^5bbyB^7o^5nes^7".format(max(0, _ra.MIN_FRAGS - tot))
        # (with the QLStats line under it the two numbers are named apart: this one starts at 1500 and knows only frags with Bobby)
        player.tell("^3{}^7{}: rating ^2{:.0f}^7 (+-{:.0f}), {}. Frags with ^5B^7o^5bbyB^7o^5nes^7: {} made, {} taken (a share of {:.0%}).".format(
            p["name"], " here, against me" if ql else "", p["r"], 2 * p["rd"], where, p["won"], p["lost"], p["won"] / max(1, tot)))
        if ql:
            self.ql_say(player, k)
        return minqlx.RET_STOP_ALL

    def cmd_ladder(self, player, msg, channel):
        s = self.seen
        player.tell("ladder since its load: {} deaths seen, {} by his own hand or the map, {} paired with a killer ({} of them counted: "
                    "a person and Bobby), {} left out (more than one frag in a frame); {} rows in the table.".format(
                        s["deaths"], s["own"], s["paired"], s["counted"], s["unsure"], len(self.table.players)))
        player.tell("board: " + self.board_state())
        return minqlx.RET_STOP_ALL
