"""The map command of a BobbyBones server, 1v1 only (owner, 2026-10-23: "I only really care about duel mode btw, we can
remove ffa entirely from the server, and remove the two custom maps that we had built. It should just have duel mode on
the 10 duel maps we've been training on.").

!map <name> brings one of the ten duel maps up in the duel factory; !mode answers that the server plays 1v1 only. Until
2026-10-23 this plugin switched a running server between 1v1 (plugins/duelbot.py) and free-for-all (plugins/ffabot.py);
ffabot stays in the repo but no server loads it. Load before duelbot: QLX_PLUGINS="botctl, botmode, duelbot".
"""
import importlib
import os
import sys
import time

import minqlx

try:                                                        # no powerups on any server: the shared helpers (plugins/powerups.py)
    _pu = importlib.import_module(__package__ + ".powerups")
except Exception:                                           # noqa: BLE001 - loaded outside the plugin package
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _pu = importlib.import_module("powerups")

MAPS = ("bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure")   # = duelbot.MAPS


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class botmode(minqlx.Plugin):
    def __init__(self):
        self.add_command("mode", self.cmd_mode, 0, priority=minqlx.PRI_HIGH)
        self.add_command("map", self.cmd_map, 0, usage="<{}>".format("|".join(MAPS)), priority=minqlx.PRI_HIGH)
        self.last_switch = 0.0

    def cmd_mode(self, player, msg, channel):
        player.tell("^3This server plays 1v1 only^7 (on the ten duel maps: ^2!maps^7 lists them).")
        return minqlx.RET_STOP_ALL

    def cmd_map(self, player, msg, channel):
        if len(msg) < 2 or msg[1].lower() not in MAPS:     # one usage line (RET_USAGE let duelbot's own !map print it again)
            player.tell("Usage: ^6!map <{}>".format("|".join(MAPS)))
            return minqlx.RET_STOP_ALL
        mapname = msg[1].lower()
        if time.time() - self.last_switch < 15:
            player.tell("^3wait a moment: a map change is in progress")
            return minqlx.RET_STOP_ALL
        self.last_switch = time.time()
        os.environ["LAB_MAP"] = mapname
        duel = minqlx.Plugin._loaded_plugins.get("duelbot")
        if duel is not None:                                 # the plugin stays loaded: left on its old map it pulled the server
            duel.want_map = mapname                          # straight back (2026-10-06)
        for p in self.players():                             # the game's own bots (a !spar opponent); Bobby comes back with the map
            if is_bot(p):
                minqlx.console_command("clientkick {}".format(p.id))
        _pu.load_map(mapname, "duel")
        self.msg("^3{} changed the map to {}.^7".format(player.clean_name, mapname))
        return minqlx.RET_STOP_ALL
