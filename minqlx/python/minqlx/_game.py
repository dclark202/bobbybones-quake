# minqlx - Extends Quake Live's dedicated server with extra functionality and scripting.
# Copyright (C) 2015 Mino <mino@minomino.org>

# This file is part of minqlx.

# minqlx is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# minqlx is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with minqlx. If not, see <http://www.gnu.org/licenses/>.


# Since this isn't the actual module, we define it here and export
# it later so that it can be accessed with minqlx.__doc__ by Sphinx.

import minqlx

class NonexistentGameError(Exception):
    """An exception raised when accessing properties on an invalid game."""
    pass

class Game():
    """A class representing the game. That is, stuff like what map is being played,
    if it's in warmup, and so on. It also has methods to call in timeins, aborts,
    pauses, and so on."""
    def __init__(self, cached=True):
        self.cached = cached
        self._valid = True
        cs = minqlx.get_configstring(0)
        if not cs:
            self._valid = False
            raise NonexistentGameError("Tried to instantiate a game while no game is active.")

    def __repr__(self):
        try:
            return "{}({}@{})".format(self.__class__.__name__, self.short_type, self.short_map)
        except NonexistentGameError:
            return "{}(N/A@N/A)".format(self.__class__.__name__)

    def __str__(self):
        try:
            return "{} on {}".format(self.type, self.map)
        except NonexistentGameError:
            return "Invalid game"

    def __contains__(self, key):
        cs = minqlx.get_configstring(0)
        if not cs:
            self._valid = False
            raise NonexistentGameError("Invalid game. Is the server loading a new map?")
            
        cvars = minqlx.parse_variables(cs)
        return key in cvars

    def __getitem__(self, key):
        cs = minqlx.get_configstring(0)
        if not cs:
            self._valid = False
            raise NonexistentGameError("Invalid game. Is the server loading a new map?")

        cvars = minqlx.parse_variables(cs)
        return cvars[key]

    @property
    def cvars(self):
        """A dictionary of unprocessed cvars. Use attributes whenever possible, but since some
        cvars might not have attributes on this class, this could be useful.

        """
        return minqlx.parse_variables(minqlx.get_configstring(0))

    @property
    def type(self):
        return minqlx.GAMETYPES[int(self["g_gametype"])]

    @property
    def type_short(self):
        return minqlx.GAMETYPES_SHORT[int(self["g_gametype"])]

    @property
    def map(self):
        """The short name of the map. Ex.: ``longestyard``."""
        return self["mapname"]

    @map.setter
    def map(self, value):
        minqlx.console_command("map {}".format(value))

    @property
    def map_title(self):
        """The full name of the map. Ex.: ``Longest Yard``."""
        return minqlx._map_title

    @property
    def map_subtitle1(self):
        """The map's subtitle. Usually either empty or has the author's name."""
        return minqlx._map_subtitle1

    @property
    def map_subtitle2(self):
        """The map's second subtitle. Usually either empty or has the author's name."""
        return minqlx._map_subtitle2

    @property
    def red_score(self):
        return int(minqlx.get_configstring(6))

    @property
    def blue_score(self):
        return int(minqlx.get_configstring(7))

    @property
    def state(self):
        """A string describing the state of the game.

        Possible values:
        - *warmup* -- The game has yet to start and is waiting for players to ready up.
        - *countdown* -- Players recently readied up, and it's counting down until the game starts.
        - *in_progress* -- The game is in progress.

        """
        s = self["g_gameState"]
        if s == "PRE_GAME":
            return "warmup"
        elif s == "COUNT_DOWN":
            return "countdown"
        elif s == "IN_PROGRESS":
            return "in_progress"
        else:
            logger = minqlx.get_logger()
            logger.warning("Got unknown game state: {}".format(s))
            return s

    @property
    def factory(self):
        return self["g_factory"]

    @factory.setter
    def factory(self, value):
        minqlx.console_command("map {} {}".format(self.map, value))

    @property
    def factory_title(self):
        return self["g_factoryTitle"]

    @property
    def hostname(self):
        return self["sv_hostname"]

    @hostname.setter
    def hostname(self, value):
        minqlx.set_cvar("sv_hostname", str(value))

    @property
    def instagib(self):
        return bool(int(self["g_instaGib"]))

    @instagib.setter
    def instagib(self, value):
        if isinstance(value, bool):
            minqlx.set_cvar("g_instaGib", str(int(value)))
        elif value == 0 or value == 1:
            minqlx.set_cvar("g_instaGib", str(value))
        else:
            raise ValueError("instagib needs to be 0, 1, or a bool.")

    @property
    def loadout(self):
        return bool(int(self["g_loadout"]))

    @loadout.setter
    def loadout(self, value):
        if isinstance(value, bool):
            minqlx.set_cvar("g_loadout", str(int(value)))
        elif value == 0 or value == 1:
            minqlx.set_cvar("g_loadout", str(value))
        else:
            raise ValueError("loadout needs to be 0, 1, or a bool.")

    @property
    def maxclients(self):
        return int(self["sv_maxclients"])

    @maxclients.setter
    def maxclients(self, new_limit):
        minqlx.set_cvar("sv_maxclients", str(new_limit))

    @property
    def timelimit(self):
        return int(self["timelimit"])

    @timelimit.setter
    def timelimit(self, new_limit):
        minqlx.set_cvar("timelimit", str(new_limit))

    @property
    def fraglimit(self):
        return int(self["fraglimit"])

    @fraglimit.setter
    def fraglimit(self, new_limit):
        minqlx.set_cvar("fraglimit", str(new_limit))

    @property
    def roundlimit(self):
        return int(self["roundlimit"])

    @roundlimit.setter
    def roundlimit(self, new_limit):
        minqlx.set_cvar("roundlimit", str(new_limit))

    @property
    def roundtimelimit(self):
        return int(self["roundtimelimit"])

    @roundtimelimit.setter
    def roundtimelimit(self, new_limit):
        minqlx.set_cvar("roundtimelimit", str(new_limit))

    @property
    def scorelimit(self):
        return int(self["scorelimit"])

    @scorelimit.setter
    def scorelimit(self, new_limit):
        minqlx.set_cvar("scorelimit", str(new_limit))

    @property
    def capturelimit(self):
        return int(self["capturelimit"])

    @capturelimit.setter
    def capturelimit(self, new_limit):
        minqlx.set_cvar("capturelimit", str(new_limit))

    @property
    def teamsize(self):
        return self["teamsize"]

    @teamsize.setter
    def teamsize(self, new_size):
        minqlx.set_cvar("teamsize", str(new_size))

    @property
    def tags(self):
        return minqlx.get_cvar("sv_tags").split(",")

    @tags.setter
    def tags(self, new_tags):
        if isinstance(new_tags, str):
            minqlx.set_cvar("sv_tags", new_tags)
        elif hasattr(new_tags, "__iter__"):
            minqlx.set_cvar("sv_tags", ",".join(new_tags))
        else:
            raise ValueError("tags need to be a string or an iterable returning strings.")

    @property
    def workshop_items(self):
        return [int(i) for i in minqlx.get_configstring(715).split()]

    @workshop_items.setter
    def workshop_items(self, new_items):
        if hasattr(new_items, "__iter__"):
            minqlx.set_configstring(715, " ".join([str(i) for i in new_items]) + " ")
        else:
            raise ValueError("The value needs to be an iterable.")

    @classmethod
    def shuffle(cls):
        minqlx.console_command("forceshuffle")

    # ====================================================================
    #                         ADMIN COMMANDS
    # ====================================================================

    @classmethod
    def timeout(cls):
        return minqlx.console_command("timeout")

    @classmethod
    def timein(cls):
        return minqlx.console_command("timein")

    @classmethod
    def allready(cls):
        return minqlx.console_command("allready")

    @classmethod
    def pause(cls):
        return minqlx.console_command("pause")

    @classmethod
    def unpause(cls):
        return minqlx.console_command("unpause")

    @classmethod
    def lock(cls, team=None):
        if team is None:
            return minqlx.console_command("lock")
        elif team.lower() not in minqlx.TEAMS.values():
            raise ValueError("Invalid team.")
        
        return minqlx.console_command("lock {}".format(team.lower()))

    @classmethod
    def unlock(cls, team=None):
        if team is None:
            return minqlx.console_command("unlock")
        elif team.lower() not in minqlx.TEAMS.values():
            raise ValueError("Invalid team.")

        return minqlx.console_command("unlock {}".format(team.lower()))

    @classmethod
    def put(cls, player, team):
        cid = minqlx.Plugin.client_id(player)
        if cid is None:
            raise ValueError("Invalid player.")
        elif team.lower() not in minqlx.TEAMS.values():
            raise ValueError("Invalid team.")

        return minqlx.console_command("put {} {}"
            .format(cid, team.lower()))

    @classmethod
    def mute(cls, player):
        cid = minqlx.Plugin.client_id(player)
        if cid is None:
            raise ValueError("Invalid player.")

        return minqlx.console_command("mute {}".format(cid))

    @classmethod
    def unmute(cls, player):
        cid = minqlx.Plugin.client_id(player)
        if cid is None:
            raise ValueError("Invalid player.")

        return minqlx.console_command("unmute {}".format(cid))

    @classmethod
    def tempban(cls, player):
        cid = minqlx.Plugin.client_id(player)
        if cid is None:
            raise ValueError("Invalid player.")

        return minqlx.console_command("tempban {}".format(cid))

    @classmethod
    def ban(cls, player):
        cid = minqlx.Plugin.client_id(player)
        if cid is None:
            raise ValueError("Invalid player.")

        return minqlx.console_command("ban {}".format(cid))

    @classmethod
    def unban(cls, player):
        cid = minqlx.Plugin.client_id(player)
        if cid is None:
            raise ValueError("Invalid player.")

        return minqlx.console_command("unban {}".format(cid))

    @classmethod
    def opsay(cls, msg):
        return minqlx.console_command("opsay {}".format(msg))

    @classmethod
    def addadmin(cls, player):
        cid = minqlx.Plugin.client_id(player)
        if cid is None:
            raise ValueError("Invalid player.")

        return minqlx.console_command("addadmin {}".format(cid))

    @classmethod
    def addmod(cls, player):
        cid = minqlx.Plugin.client_id(player)
        if cid is None:
            raise ValueError("Invalid player.")

        return minqlx.console_command("addmod {}".format(cid))

    @classmethod
    def demote(cls, player):
        cid = minqlx.Plugin.client_id(player)
        if cid is None:
            raise ValueError("Invalid player.")

        return minqlx.console_command("demote {}".format(cid))

    @classmethod
    def abort(cls):
        return minqlx.console_command("map_restart")

    @classmethod
    def addscore(cls, player, score):
        cid = minqlx.Plugin.client_id(player)
        if cid is None:
            raise ValueError("Invalid player.")

        return minqlx.console_command("addscore {} {}".format(cid, score))

    @classmethod
    def addteamscore(cls, team, score):
        if team.lower() not in minqlx.TEAMS.values():
            raise ValueError("Invalid team.")

        return minqlx.console_command("addteamscore {} {}".format(team.lower(), score))

    @classmethod
    def setmatchtime(cls, time):
        return minqlx.console_command("setmatchtime {}".format(time))
