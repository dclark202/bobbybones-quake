"""testkit: checks of a server's own routines (a game's end, the map vote, F3, the leaderboard's marks) on a PRIVATE
server with no person on it. Never on a server people play on. It does nothing unless it is named in QLX_PLUGINS AND
the environment has TESTKIT=1 (tools/duel_server.sh: PLUGINS_EXTRA=testkit DOCKER_EXTRA="-e TESTKIT=1").

What it does:
- A stand-in for a person: one of the game's own bots (not a Bobby: "addbot sarge 3") counts as a person in the other
  plugins (their is_bot() is replaced while this plugin is loaded), so it takes a seat, readies up, is counted by the
  leaderboard and written to the session logs as a person would be. It still plays by the game's own bot code.
- !tcmd <client number> <command ...>   the client "sends" that command (F3 is "readyup"), through the plugins' hooks
- !towner <client number>|off           that client is the server's owner for minqlx.owner() (in memory only)
- !tstate                               the game's state, the cvars that matter here, the players, the plugins' own state
- !tsay <text>                          a line into the event file (to mark a step of a test)
- !tloaded <client number>              the "player_loaded" event for that client (minqlx never sends it for a bot)
- !tframes [text]                       frames run and the longest gap between two frames since the last call
- every weapon of the map: when it is taken and when it is back, with the milliseconds between ("item" lines)
- testkit.jsonl in the data folder: every change of the game's state, of the map, of a watched cvar and of a
  configstring (the map vote lives in configstrings), with the time; game_start / game_end / vote events; what the
  server tells the players (print and chat lines), which is what a person would read.

Commands are the owner's (rcon: `python3 /tools/rcon.py "qlx !tstate"`).
"""
import json
import os
import sys
import time

import minqlx

ON = os.environ.get("TESTKIT") == "1"
D = "/tmp/practice"
BOBBY_NAMES = ("BobbyBones", "Mr Skeleton", "THE JUGGERNAUT", "Dr Evil")     # (duelbot.BOT_NAMES)
PATCHED = ("duelbot", "ffabot", "ladder", "botmode", "banter", "banlist")
CVARS = ("g_gameState", "mapname", "g_factory", "g_gametype", "timelimit", "fraglimit", "g_weaponRespawn", "sv_warmupReadyPercentage",
         "sv_mapPoolFile", "g_voteFlags", "g_allowVote", "g_spawnItemPowerup", "g_itemTimers", "sv_maxclients", "teamsize",
         "g_warmup", "g_doWarmup", "nextmap", "g_inactivity")
QUIET_CS = set(range(529, 593)) | {1, 12, 13, 21, 662, 663}   # per-player strings and clocks: too many changes to be of use


def real_bot(p):
    return str(p.steam_id).startswith("9007199")


def standin_is_bot(p):
    """a Bobby is a bot; one of the game's own bots is the stand-in for a person"""
    try:
        return real_bot(p) and any(n in p.clean_name for n in BOBBY_NAMES)
    except Exception:                                        # noqa: BLE001
        return real_bot(p)


class testkit(minqlx.Plugin):
    def __init__(self):
        super().__init__()
        if not ON:
            minqlx.console_print("[testkit] loaded without TESTKIT=1: it does nothing\n")
            return
        self.last = {}
        self.cs = {}
        self.items = {}                                      # entity number -> (there, the level's clock at the last change)
        self.next_cs = 0.0
        self.owner_was = None
        self.add_hook("frame", self.on_frame)
        for ev in ("map", "new_game", "game_countdown", "game_start", "game_end", "vote_called", "vote_started", "vote_ended",
                   "player_loaded", "player_disconnect", "team_switch"):
            self.add_hook(ev, (lambda name: (lambda *a: self.note(event=name, args=[str(x)[:300] for x in a])))(ev),
                          priority=minqlx.PRI_LOWEST)
        self.add_hook("client_command", self.on_client_command, priority=minqlx.PRI_HIGHEST)
        self.add_hook("console_print", self.on_console_print)
        self.add_hook("server_command", self.on_server_command, priority=minqlx.PRI_LOWEST)
        self.fr_n, self.fr_max, self.fr_last, self.fr_t0 = 0, 0.0, 0.0, time.time()
        self.add_command("tframes", self.cmd_tframes, 5)
        self.add_command("tloaded", self.cmd_tloaded, 5, usage="<client number>")
        self.add_command("tcmd", self.cmd_tcmd, 5, usage="<client number> <command ...>")
        self.add_command("towner", self.cmd_towner, 5, usage="<client number>|off")
        self.add_command("tstate", self.cmd_tstate, 5)
        self.add_command("tsay", self.cmd_tsay, 5)
        self.note(event="testkit", on=True)

    @staticmethod
    def note(**rec):
        rec["t"] = round(time.time(), 2)
        rec["clock"] = time.strftime("%H:%M:%S")
        try:
            with open(os.path.join(D, "testkit.jsonl"), "a") as f:
                f.write(json.dumps(rec) + "\n")
        except OSError:
            pass

    def patch(self):
        for name, mod in list(sys.modules.items()):
            if name.rsplit(".", 1)[-1] in PATCHED and getattr(mod, "is_bot", None) not in (None, standin_is_bot):
                mod.is_bot = standin_is_bot
                self.note(event="standin", module=name)

    def on_client_command(self, player, cmd):
        c = cmd.strip()
        if c.split(" ")[0].lower() not in ("score", "userinfo"):
            self.note(event="client_command", client=player.id, bot=real_bot(player), cmd=c[:200])

    def on_console_print(self, text):
        low = text.lower()
        if any(k in low for k in ("vote", "map pool", "mappool", "warmup", "ready", "intermission", "timelimit hit", "exception",
                                  "traceback", "error", "game_end", "abort", "restart")):
            self.note(event="console", text=text.strip()[:300])

    def on_server_command(self, player, cmd):
        """what the server tells one player or all (print, chat, the vote's commands): the lines a person would read"""
        c = cmd.split(" ", 1)[0]
        if c in ("print", "chat", "cp", "enable_vote_ui", "disable_vote_ui", "nextmaps", "bcs0", "pcp") or "vote" in c:
            self.note(event="told", to=(player.id if player is not None else "all"), cmd=cmd[:420])

    def cmd_tloaded(self, player, msg, channel):
        """the "player_loaded" event for a client, as minqlx sends it when a person has finished loading (it never
        comes for a bot): the plugins' welcome and whatever else they do at a person's arrival"""
        p = next((q for q in self.players() if msg[1:] and msg[1].isdigit() and q.id == int(msg[1])), None)
        if p is None:
            return minqlx.RET_USAGE
        self.note(event="loaded", client=p.id)
        minqlx.EVENT_DISPATCHERS["player_loaded"].dispatch(p)
        return minqlx.RET_STOP_ALL

    def cmd_tframes(self, player, msg, channel):
        """frames run and the longest gap between two since the last call: is the game held up by anything?"""
        now = time.time()
        secs = max(1e-6, now - self.fr_t0)
        out = dict(frames=self.fr_n, seconds=round(secs, 2), per_second=round(self.fr_n / secs, 1), longest_gap_ms=round(self.fr_max * 1000, 1))
        self.note(event="frames", text=" ".join(msg[1:]), **out)
        player.tell("frames: " + json.dumps(out))
        self.fr_n, self.fr_max, self.fr_t0 = 0, 0.0, now
        return minqlx.RET_STOP_ALL

    def on_frame(self):
        self.patch()
        now = time.time()
        if self.fr_last:
            self.fr_max = max(self.fr_max, now - self.fr_last)
        self.fr_last = now
        self.fr_n += 1
        try:                                                 # the map's weapons: when one is taken and when it is back
            t_ms, items = minqlx.item_states()
            if t_ms < getattr(self, "items_ms", 0):
                self.items = {}                              # the level's clock started over (a new map, a game's start)
            self.items_ms = t_ms
            for num, cls, x, y, z, up, back in items:
                if not cls.startswith("weapon_"):
                    continue
                was = self.items.get(num)
                if was is not None and was[0] != bool(up):
                    self.note(event="item", num=int(num), cls=cls, up=int(bool(up)), level_ms=int(t_ms), back_in_ms=int(back - t_ms),
                              pos=[round(x), round(y), round(z)], away_ms=(int(t_ms) - was[1]) if up else None)
                if was is None or was[0] != bool(up):
                    self.items[num] = (bool(up), int(t_ms))
        except Exception:                                    # noqa: BLE001
            pass
        cur = {}
        for c in CVARS:
            cur[c] = minqlx.get_cvar(c)
        try:
            cur["state"] = self.game.state if self.game is not None else None
        except Exception:                                    # noqa: BLE001 - between two maps
            cur["state"] = None
        ch = {k: [self.last.get(k), v] for k, v in cur.items() if self.last.get(k) != v}
        if ch:
            self.note(event="change", **{k: v for k, v in ch.items()})
        self.last = cur
        if now > self.next_cs:
            self.next_cs = now + 0.5
            diff = {}
            for i in range(0, 1024):
                if i in QUIET_CS:
                    continue
                try:
                    v = minqlx.get_configstring(i)
                except Exception:                            # noqa: BLE001
                    continue
                if self.cs.get(i) != v:
                    if i in self.cs or v:
                        diff[i] = v[:400]
                    self.cs[i] = v
            if diff and len(diff) < 60:
                self.note(event="configstrings", cs=diff)
            elif diff:
                self.note(event="configstrings", n=len(diff), cs={k: v for k, v in list(diff.items())[:12]})

    def cmd_tcmd(self, player, msg, channel):
        if len(msg) < 3 or not msg[1].isdigit():
            return minqlx.RET_USAGE
        cid, cmd = int(msg[1]), " ".join(msg[2:])
        self.note(event="inject", client=cid, cmd=cmd)
        minqlx.client_command(cid, cmd)
        player.tell("client {} sent: {}".format(cid, cmd))
        return minqlx.RET_STOP_ALL

    def cmd_towner(self, player, msg, channel):
        if len(msg) < 2:
            return minqlx.RET_USAGE
        if msg[1] == "off":
            if self.owner_was is not None:
                minqlx.owner = self.owner_was
                self.owner_was = None
            player.tell("the owner is the server's own again")
            return minqlx.RET_STOP_ALL
        p = next((q for q in self.players() if q.id == int(msg[1])), None) if msg[1].isdigit() else None
        if p is None:
            player.tell("no such client")
            return minqlx.RET_STOP_ALL
        sid = int(p.steam_id)
        if self.owner_was is None:
            self.owner_was = minqlx.owner
        minqlx.owner = lambda: sid
        self.note(event="owner", client=p.id)
        player.tell("client {} ({}) is the owner for this test".format(p.id, p.clean_name))
        return minqlx.RET_STOP_ALL

    def cmd_tsay(self, player, msg, channel):
        self.note(event="mark", text=" ".join(msg[1:]))
        return minqlx.RET_STOP_ALL

    def cmd_tstate(self, player, msg, channel):
        out = {"cvars": {c: minqlx.get_cvar(c) for c in CVARS}, "plugins": sorted(minqlx.Plugin._loaded_plugins)}
        try:
            out["state"] = self.game.state
        except Exception as e:                               # noqa: BLE001
            out["state"] = repr(e)
        rows = []
        for p in self.players():
            try:
                st = p.state
                rows.append(dict(id=p.id, name=p.clean_name, team=p.team, game_bot=real_bot(p), person=not standin_is_bot(p),
                                 health=st.health if st else None, kills=p.stats.kills, deaths=p.stats.deaths,
                                 weapon=int(st.weapon) if st else None))
            except Exception as e:                           # noqa: BLE001
                rows.append(dict(id=p.id, err=repr(e)))
        out["players"] = rows
        for name in ("ffabot", "duelbot"):
            pl = minqlx.Plugin._loaded_plugins.get(name)
            if pl is not None:
                d = {}
                for k in ("ready", "want_map", "n_bots", "ready_ids", "real_game", "go_t", "last_abort", "seat", "sess", "game_over_t", "go_f3", "vote_map_ok"):
                    if hasattr(pl, k):
                        v = getattr(pl, k)
                        d[k] = sorted(v) if isinstance(v, set) else (v if isinstance(v, (int, float, str, bool, type(None))) else str(v))
                m = getattr(pl, "match", None)
                d["match"] = None if m is None else {k: v for k, v in m.items() if k != "base"}
                a = getattr(pl, "arena", None)
                d["arena"] = None if a is None else {k: v for k, v in a.items() if k in ("where", "mins", "t_end")}
                out[name] = d
        self.note(event="state", **out)
        for k, v in out.items():
            if k == "players":
                for r in v:
                    player.tell("  " + json.dumps(r))
            else:
                player.tell("{}: {}".format(k, json.dumps(v)))
        return minqlx.RET_STOP_ALL
