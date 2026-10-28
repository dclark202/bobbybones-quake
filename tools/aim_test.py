"""!aim's test without a game: the 1v1 plugin's own aim code (plugins/duelbot.py cmd_aim, aim_reset, aim_frame, aim_busy)
driven through warmups, games, a game's end and map changes, the game stubbed out and the policy files replaced by small
files that carry only their aim level (env_vars AIM_LEVEL, as sim/export_duel.py writes it).

    python tools/aim_test.py

The owner's rule (2026-10-22): the default is 4 and every map starts at the default; a level asked for holds until the map
changes. A level asked for during a game (or after its gg, as the gg line suggests: "Try !aim 5 next game") is promised
"from the next game" and is that next game's: the next map's load must not wipe it (found 2026-10-25 on the public
servers: every such request was wiped and every game was played at 4). Exit 0 = every check held."""
import json
import os
import shutil
import sys
import tempfile
import time
import types

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np                                           # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "plugins"))
LEVELS = {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "max": 40}


def stub_minqlx():
    m = types.ModuleType("minqlx")

    class Plugin:
        def __init__(self, *a, **k):
            pass
    m.Plugin = Plugin
    m.get_cvar = lambda *a, **k: ""
    m.owner = lambda: 0
    m.console_print = lambda s: None
    sys.modules["minqlx"] = m


def write_policy(path, level):
    np.savez(path, env_vars=np.array(json.dumps({"AIM_LEVEL": LEVELS[level], "OTHER": 1})))


class Teller:
    def __init__(self, out):
        self.out = out

    def tell(self, s):
        self.out.append(("tell", s))


def main():
    stub_minqlx()
    import duelbot as DB
    d = tempfile.mkdtemp(prefix="aimtest_")
    DB.D = d
    for lv, f in DB.duelbot.AIM_FILES.items():
        write_policy(os.path.join(d, f), lv)
    shutil.copyfile(os.path.join(d, "policy_l5.npz"), os.path.join(d, "policy.npz"))    # left at 5 by the last run
    said, logs = [], []
    bot = object.__new__(DB.duelbot)
    bot.log = lambda s: logs.append(s)
    bot.msg = lambda s: said.append(("msg", s))
    bot.end_session = lambda: None
    bot.game = types.SimpleNamespace(state="warmup")
    bot.ready, bot.real_game, bot.go_f3, bot.game_over_t = False, False, 0.0, 0.0
    bot.room, bot.queue, bot.arena = None, [], None

    def setup():                                             # what setup() does for the aim: policy.npz loaded
        with np.load(os.path.join(d, "policy.npz")) as z:
            bot.P = {"env_vars": str(z["env_vars"])}
        bot.ready = True
    bot.setup = setup
    t = [1000.0]

    def frame(n=3):                                          # frames 2 s apart (aim_frame looks every 2 s)
        for _ in range(n):
            t[0] += 2.5
            if not bot.ready:
                setup()
            bot.aim_frame(t[0])

    def new_map():                                           # the map hook, then the load (setup once the map is up)
        bot.ready = False
        bot.game.state = "warmup"
        bot.game_over_t, bot.go_f3, bot.real_game = 0.0, 0.0, False
        bot.aim_reset()
        frame()

    def aim(*args):
        bot.cmd_aim(Teller(said), ["!aim"] + list(args), None)

    def on_disk():
        with np.load(os.path.join(d, "policy.npz")) as z:
            v = json.loads(str(z["env_vars"]))["AIM_LEVEL"]
        return "max" if v > 9 else str(v)

    fails = []

    def check(name, ok, extra=""):
        print(("ok   " if ok else "FAIL ") + name + (" " + extra if extra else ""))
        if not ok:
            fails.append(name)

    # the plugin's start: policy.npz was left at 5 by the last run; the start puts the default in
    bot.aim_want = None
    bot.aim_reset()
    frame()
    check("start: the default whatever policy.npz was left at", bot.aim_level() == "4" and on_disk() == "4",
          "level {} file {}".format(bot.aim_level(), on_disk()))

    # warmup: at once
    aim("5")
    check("warmup !aim 5: at once", bot.aim_level() == "5" and said[-1] == ("msg", "^3Aim level now^7 ^25^7."), str(said[-1:]))
    del said[:]
    aim()
    check("!aim with no level: says the level now", said and "^25^7" in said[-1][1], str(said[-1:]))

    # it holds through a game on the same map (a game thrown back to warmup, a second game)
    bot.game.state, bot.real_game = "in_progress", True
    frame()
    bot.game.state, bot.real_game = "warmup", False
    frame()
    check("holds through games on the same map", bot.aim_level() == "5")

    # a new map: the default
    new_map()
    check("new map: back to 4", bot.aim_level() == "4" and on_disk() == "4")

    # asked for during a game: from the next game, which is on the next map (the vote at a game's end loads one)
    bot.game.state, bot.real_game = "in_progress", True
    del said[:]
    aim("max")
    check("in a game: promised from the next game", bot.aim_level() == "4" and "from the next game" in said[-1][1], str(said[-1:]))
    frame()
    check("in a game: the game keeps its level", bot.aim_level() == "4")
    bot.game.state, bot.real_game, bot.game_over_t = "warmup", False, time.time()     # the game's end: scoreboard and vote
    frame()
    check("the game's end: still kept", bot.aim_level() == "4")
    del said[:]
    new_map()
    check("next map: the level asked for in the game (the bug of 2026-10-25)", bot.aim_level() == "max" and on_disk() == "max",
          "level {} file {}".format(bot.aim_level(), on_disk()))
    check("next map: it is said once the map is up", any("Aim level now" in s and "max" in s for _, s in said), str(said))
    n_said = len(said)
    frame()
    check("said once only", len(said) == n_said)
    new_map()
    check("the map after: back to 4", bot.aim_level() == "4" and on_disk() == "4")

    # asked for after the gg (the gg line's own suggestion), during the end sequence
    bot.game.state, bot.real_game = "in_progress", True
    frame()
    bot.game.state, bot.real_game, bot.game_over_t = "warmup", False, time.time()
    aim("5")
    frame()
    new_map()
    check("asked for after the gg: the next map's level", bot.aim_level() == "5")
    new_map()
    check("and the map after: 4", bot.aim_level() == "4")

    # asked for in a game that is thrown back to warmup on the same map (a person leaves): in at the warmup, as before
    bot.game.state, bot.real_game = "in_progress", True
    aim("3")
    frame()
    bot.game.state, bot.real_game = "warmup", False
    frame()
    check("a game thrown back to warmup: in at the warmup", bot.aim_level() == "3")
    new_map()
    check("then a new map: 4", bot.aim_level() == "4")

    # asked for the default during a game while at another level: the next map is at the default (nothing to say)
    aim("2")
    bot.game.state, bot.real_game = "in_progress", True
    aim("4")
    bot.game.state, bot.real_game, bot.game_over_t = "warmup", False, time.time()
    del said[:]
    new_map()
    check("asked for 4 in a game at 2: the next map at 4", bot.aim_level() == "4" and not any("Aim level now" in s for _, s in said))

    # a level whose file is not on the server: refused, nothing changes
    os.remove(os.path.join(d, "policy_l1.npz"))
    del said[:]
    aim("1")
    check("a missing file: refused", bot.aim_level() == "4" and "not on this server" in said[-1][1], str(said[-1:]))

    shutil.rmtree(d, ignore_errors=True)
    print("{} of the checks failed".format(len(fails)) if fails else "all checks held")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
