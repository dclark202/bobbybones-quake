"""lab: supervisor that keeps the BobbyBones server in its intended state, no matter what.

- always LAB_MAP (default bloodrun) in duel; anything else is corrected within seconds
- permanent warmup: any match countdown/start is aborted
- map/kick votes blocked (nobody votes Bobby off or changes the map)
- BobbyBones present and named, item run + combat running, recording on
- tells every joining player that matches are recorded and why
"""
import os
import time

import minqlx

LAB_MAP = os.environ.get("LAB_MAP", "bloodrun")
LAB_FACTORY = "duel"
CHECK_EVERY = 5.0
NOTICE = ("^7Welcome to the ^1B^3o^2b^5b^4y^6B^1o^3n^2e^5s ^7lab. Matches here are recorded (movement, item timing, "
          "weapon use) to train the bot and to make player reports.")


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class lab(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.add_hook("game_countdown", self.on_countdown)
        self.add_hook("game_start", self.on_countdown)
        self.add_hook("vote_called", self.on_vote)
        self.add_hook("player_loaded", self.on_loaded)
        self.next_check = 0.0
        self.fixing_map_until = 0.0

    def log(self, msg):
        minqlx.console_print("[lab] " + msg + "\n")
        try:
            with open("/tmp/practice/lab.log", "a") as f:
                f.write("{} {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), msg))
        except OSError:
            pass

    # ---- events ----
    def on_map(self, mapname, factory):
        if mapname.lower() != LAB_MAP or factory != LAB_FACTORY:
            self.fix_map()

    def on_countdown(self, *args):
        self.log("match tried to start - back to warmup")
        self.abort_later()

    @minqlx.delay(0.5)
    def abort_later(self):
        minqlx.console_command("abort")

    def on_vote(self, caller, vote, args):
        if vote.lower() in ("map", "kick", "clientkick", "map_restart", "nextmap", "g_gametype", "teamsize"):
            caller.tell("^3That vote is disabled on the BobbyBones lab.")
            return minqlx.RET_STOP_ALL

    def on_loaded(self, player):
        if not is_bot(player):
            self.welcome(player)

    @minqlx.delay(3)
    def welcome(self, player):
        try:
            player.tell(NOTICE)
            player.center_print("^7Recorded server - see chat")
        except Exception:
            pass

    # ---- periodic enforcement ----
    def fix_map(self):
        now = time.time()
        if now < self.fixing_map_until:
            return
        self.fixing_map_until = now + 20
        self.log("wrong map/mode -> {} {}".format(LAB_MAP, LAB_FACTORY))
        minqlx.console_command("map {} {}".format(LAB_MAP, LAB_FACTORY))

    def on_frame(self):
        now = time.time()
        if now < self.next_check:
            return
        self.next_check = now + CHECK_EVERY
        try:
            self.enforce(now)
        except Exception as e:
            self.log("enforce error: {!r}".format(e))

    def enforce(self, now):
        if (minqlx.get_cvar("mapname") or "").lower() != LAB_MAP or minqlx.get_cvar("g_factory") not in (None, "", LAB_FACTORY):
            return self.fix_map()
        if now < self.fixing_map_until - 12:          # give a fresh map a few seconds to settle
            return
        for name, value in (("timelimit", "0"), ("fraglimit", "0"), ("g_doWarmup", "1")):
            if minqlx.get_cvar(name) != value:
                minqlx.set_cvar(name, value)
        if self.game is not None and self.game.state not in ("warmup", None):
            self.log("game state {} - aborting to warmup".format(self.game.state))
            minqlx.console_command("abort")
        bots = [p for p in self.players() if is_bot(p)]
        if not bots:
            self.log("BobbyBones missing - adding him")
            minqlx.console_command("addbot bones 5 free 0 BobbyBones")
            return
        plugins = minqlx.Plugin._loaded_plugins
        bobby = plugins.get("bobby")
        if bobby is not None:
            bobby.rename()
        botctl = plugins.get("botctl")
        if botctl is not None and not getattr(botctl, "recording", False):
            botctl.recording = True
            self.log("recording was off - on again")
        itemrun = plugins.get("itemrun")
        if itemrun is not None and not getattr(itemrun, "running", False):
            self.log("item run not running - starting")
            minqlx.console_command("qlx !ir start auto -1")
