"""Switch a BobbyBones server between 1v1 (plugins/duelbot.py, the duel factory) and free-for-all (plugins/ffabot.py,
the ffa factory) while it runs: !mode ffa|duel [bots], and !map <name>, which picks the map's own mode (arena1 is a
free-for-all map by design; testlab and the duel maps are 1v1, the duel factory keeps two players active).

Load first: QLX_PLUGINS="botctl, botmode, duelbot" (or ffabot). The switch unloads the one plugin, kicks the bots,
changes the map with the other factory and loads the other plugin, which adds its own bots.
"""
import os
import time

import minqlx

FFA_MAPS = ("arena1",)
DUEL_MAPS = ("testlab", "bloodrun", "aerowalk", "lostworld", "campgrounds")
PLUGIN = {"ffa": "ffabot", "duel": "duelbot"}


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class botmode(minqlx.Plugin):
    def __init__(self):
        self.add_command("mode", self.cmd_mode, 0, usage="<ffa|duel> [bots 1-4]", priority=minqlx.PRI_HIGH)
        self.add_command("map", self.cmd_map, 0, usage="<{}>".format("|".join(FFA_MAPS + DUEL_MAPS)), priority=minqlx.PRI_HIGH)
        self.add_hook("map", self.on_map, priority=minqlx.PRI_LOW)
        self.last_switch = 0.0
        self.pending = None                                  # the plugin to load once the new map is up

    def on_map(self, mapname, factory):
        """the other plugin is loaded only once the new map is in: a plugin adding bots while the map still loads
        hung the server (2026-10-06, the switch to bloodrun)"""
        if self.pending:
            name, self.pending = self.pending, None
            minqlx.load_plugin(name)

    def current(self):
        loaded = minqlx.Plugin._loaded_plugins
        return "ffa" if "ffabot" in loaded else "duel" if "duelbot" in loaded else None

    def switch(self, mode, mapname, bots=None, who="the server"):
        if time.time() - self.last_switch < 15:
            return "wait a moment: a switch is in progress"
        self.last_switch = time.time()
        cur = self.current()
        if bots is not None:
            os.environ["BOBBYS"] = str(bots)
        os.environ["LAB_MAP"] = mapname
        if cur and cur != mode:
            plugin = minqlx.Plugin._loaded_plugins.get(PLUGIN[cur])
            try:
                plugin.end_session()
            except Exception:                               # noqa: BLE001
                pass
            minqlx.unload_plugin(PLUGIN[cur])
        for p in self.players():
            if is_bot(p):
                minqlx.console_command("clientkick {}".format(p.id))
        if cur != mode:
            self.pending = PLUGIN[mode]
        minqlx.console_command("map {} {}".format(mapname, "ffa" if mode == "ffa" else "duel"))
        self.msg("^3{} switched the server to {} on {}.^7".format(who, "free-for-all" if mode == "ffa" else "1v1", mapname))
        return None

    def cmd_mode(self, player, msg, channel):
        if len(msg) < 2 or msg[1].lower() not in PLUGIN:
            return minqlx.RET_USAGE
        mode = msg[1].lower()
        bots = None
        if len(msg) > 2:
            if not msg[2].isdigit() or not 1 <= int(msg[2]) <= 4:
                return minqlx.RET_USAGE
            bots = int(msg[2])
        mapname = (minqlx.get_cvar("mapname") or "arena1").lower()
        if mode == self.current() and bots is None:
            player.tell("The server is already in {} mode.".format("free-for-all" if mode == "ffa" else "1v1"))
            return minqlx.RET_STOP_ALL
        err = self.switch(mode, mapname, bots, player.clean_name)
        if err:
            player.tell("^3" + err)
        return minqlx.RET_STOP_ALL

    def cmd_map(self, player, msg, channel):
        if len(msg) < 2 or msg[1].lower() not in FFA_MAPS + DUEL_MAPS:
            return minqlx.RET_USAGE
        mapname = msg[1].lower()
        mode = "ffa" if mapname in FFA_MAPS else "duel"
        err = self.switch(mode, mapname, None, player.clean_name)
        if err:
            player.tell("^3" + err)
        return minqlx.RET_STOP_ALL
