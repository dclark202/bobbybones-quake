"""lab: supervisor that keeps the BobbyBones server in its intended state, no matter what.

- always LAB_MAP (default bloodrun) in duel; anything else is corrected within seconds
- permanent warmup: any match countdown/start is aborted
- map/kick votes blocked (nobody votes Bobby off or changes the map)
- BobbyBones present and named, item run + combat running, recording on
- tells every joining player that matches are recorded and why
"""
import json
import os
import time

import minqlx

LAB_MAP = os.environ.get("LAB_MAP", "bloodrun")
TRAIN = os.environ.get("LAB_MODE") == "train"
# training: real 10-minute matches vs rotating Nightmare (skill 5) bots
OPPONENTS = os.environ.get("LAB_OPPONENTS", "sarge,anarki,visor,xaero,klesk,doom,keel,major,orbb,ranger,slash,uriel,hunter,mynx,razor,sorlag").split(",")
RESULTS = "/tmp/practice/results.jsonl"
DEADLINE = float(os.environ.get("TRAIN_DEADLINE", "0") or 0)   # unix time; trainers go idle after it
SPAR = os.environ.get("LAB_SPAR") == "1"         # training in permanent warmup: all weapons, endless fighting
SPAR_ROUND = 600.0                                 # seconds per scored round (kills vs deaths)
CONTROL = os.environ.get("LAB_CONTROL") == "1"   # control group: plain built-in Nightmare bot as "BobbyBones"
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
        if not TRAIN:
            self.add_hook("game_countdown", self.on_countdown)
            self.add_hook("game_start", self.on_countdown)
        if TRAIN and SPAR:
            self.add_hook("player_spawn", self.on_spawn)
        self.spar = dict(start=time.time(), kills=0, deaths=0, hp={}, fired=0.0)
        self.add_hook("game_end", self.on_game_end)
        self.opp_i = int(os.environ.get("LAB_OPPONENT_START", "0"))
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
        if TRAIN and DEADLINE and now > DEADLINE:
            bots = [p for p in self.players() if is_bot(p)]
            if bots:
                self.log("training deadline reached - going idle")
                for p in bots:
                    minqlx.console_command("kick {}".format(p.id))
            return
        if (minqlx.get_cvar("mapname") or "").lower() != LAB_MAP or minqlx.get_cvar("g_factory") not in (None, "", LAB_FACTORY):
            return self.fix_map()
        if now < self.fixing_map_until - 12:          # give a fresh map a few seconds to settle
            return
        if TRAIN:
            wanted = (("timelimit", "10"), ("fraglimit", "0"), ("g_doWarmup", "0"))
        else:
            wanted = (("timelimit", "0"), ("fraglimit", "0"), ("g_doWarmup", "1"))
        for name, value in wanted:
            if minqlx.get_cvar(name) != value:
                minqlx.set_cvar(name, value)
        if not TRAIN and self.game is not None and self.game.state not in ("warmup", None)                 and now - getattr(self, "last_abort", 0) > 30:
            # should not happen (ready threshold is unreachable); aborting in a loop can hang the server
            self.last_abort = now
            self.log("game state {} - aborting to warmup".format(self.game.state))
            minqlx.console_command("abort")
        bots = [p for p in self.players() if is_bot(p)]
        bobby = [p for p in bots if "Bobby" in p.clean_name.replace(" ", "")]
        if not bobby:
            self.log("BobbyBones missing - adding him")
            minqlx.console_command("addbot bones 5 free 0 BobbyBones")
            return
        if TRAIN and len(bots) < 2:
            opp = OPPONENTS[self.opp_i % len(OPPONENTS)].strip()
            self.log("adding Nightmare opponent {}".format(opp))
            minqlx.console_command("addbot {} 5".format(opp))
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
        if CONTROL:
            return                                     # control group: leave the built-in AI alone
        if itemrun is not None and not getattr(itemrun, "running", False):
            self.log("item run not running - starting")
            minqlx.console_command("qlx !ir start auto -1")

    def on_spawn(self, player):
        self.give_loadout(player)

    @minqlx.delay(0.2)
    def give_loadout(self, player):
        """sparring: every weapon at spawn, moderate ammo (ammo boxes still matter)"""
        try:
            player.weapons(g=True, mg=True, sg=True, gl=True, rl=True, lg=True, rg=True, pg=True, hmg=True)
            player.ammo(mg=100, sg=10, gl=5, rl=10, lg=100, rg=5, pg=50, hmg=50)
        except Exception as e:
            self.log("loadout error: {!r}".format(e))

    def spar_frame(self, now):
        """warmup keeps no score: count kills/deaths ourselves and log a result every SPAR_ROUND seconds"""
        sp = self.spar
        players = [p for p in self.players() if p.team != "spectator"]
        bobby = [p for p in players if "Bobby" in p.clean_name.replace(" ", "")]
        opp = [p for p in players if p not in bobby]
        if not bobby or not opp:
            sp["start"] = now                              # no fight going on: don't run the clock
            return
        b, o = bobby[0], opp[0]
        if minqlx.last_usercmd(b.id)[1] & 1:
            sp["fired"] = now
        for p, side in ((b, "b"), (o, "o")):
            st = p.state
            hp = st.health if st else 0
            was = sp["hp"].get(side, 1)
            if was > 0 >= hp:
                if side == "b":
                    sp["deaths"] += 1                      # Bobby died (to the opponent or himself)
                elif now - sp["fired"] < 2.0:
                    sp["kills"] += 1                       # opponent died while Bobby was shooting
            sp["hp"][side] = hp
        if now - sp["start"] >= SPAR_ROUND:
            ir = minqlx.Plugin._loaded_plugins.get("itemrun")
            res = dict(t=now, map=LAB_MAP, variant="control" if CONTROL else "bobby", mode="spar",
                       bobby_score=sp["kills"], opp=o.clean_name, opp_score=sp["deaths"],
                       aggr=getattr(ir, "aggr", None) if not CONTROL else None,
                       container=os.environ.get("HOSTNAME", "?"))
            if ir is not None and not CONTROL:
                ir.new_round()
            with open(RESULTS, "a") as f:
                f.write(json.dumps(res) + "\n")
            self.log("spar round: BobbyBones {} - {} {}".format(sp["kills"], sp["deaths"], o.clean_name))
            self.spar = dict(start=now, kills=0, deaths=0, hp={}, fired=0.0)
            self.opp_i += 1
            self.kick_later(o.id)                          # next round, next opponent

    def on_game_end(self, data):
        """training: log the match result (for the Elo rating) and rotate to the next opponent"""
        if not TRAIN:
            return
        players = [p for p in self.players() if p.team != "spectator"]
        bobby = [p for p in players if "Bobby" in p.clean_name.replace(" ", "")]
        opp = [p for p in players if p not in bobby]
        if not bobby or not opp:
            return
        ir = minqlx.Plugin._loaded_plugins.get("itemrun")
        res = dict(t=time.time(), map=LAB_MAP, variant="control" if CONTROL else "bobby",
                   mode="spar" if SPAR else "match", aggr=getattr(ir, "aggr", None) if not CONTROL else None,
                   bobby_score=bobby[0].score, opp=opp[0].clean_name,
                   opp_score=opp[0].score, container=os.environ.get("HOSTNAME", "?"))
        with open(RESULTS, "a") as f:
            f.write(json.dumps(res) + "\n")
        self.log("match over: BobbyBones {} - {} {}".format(res["bobby_score"], res["opp_score"], res["opp"]))
        if ir is not None and not CONTROL:
            ir.new_round()
        self.opp_i += 1
        self.kick_later(opp[0].id)

    @minqlx.delay(5)
    def kick_later(self, cid):
        minqlx.console_command("kick {}".format(cid))
