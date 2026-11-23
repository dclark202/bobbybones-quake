"""!version's test without a game (owner, 2026-11-22): the 1v1 plugin's own version code (plugins/duelbot.py cmd_version, ver_reset,
ver_frame, ver_tick) and the aim beside it, driven through warmups, games, people coming and going and map changes, the game
stubbed out and the networks replaced by small files that carry only what the version and aim code read (run, minutes,
version, env_vars with AIM_NAME, legs). The leaderboard's game records (plugins/ladder.py) are driven too.

    python tools/version_test.py <new empty folder>

The folder is the plugin's data folder for the test (nothing is removed from it afterwards). Exit 0 = every check held."""
import hashlib
import json
import os
import shutil
import sys
import time
import types

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np                                           # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "plugins"))
NETS = {"2.2e": ("duel_gru_2_2e", 27088, "2026-11-20"), "1.6a": ("duel_gru_1_6a", 24388, "2026-11-05")}
PERSON, OTHER, OWNER = "76561190000000001", "76561190000000002", "76561190000000009"


def stub_minqlx():
    m = types.ModuleType("minqlx")

    class Plugin:
        _loaded_plugins = {}

        def __init__(self, *a, **k):
            pass
    m.Plugin = Plugin
    m.get_cvar = lambda name, *a, **k: {"mapname": "bloodrun", "qlx_owner": OWNER, "timelimit": "10"}.get(name, "")
    m.owner = lambda: int(OWNER)
    m.console_print = lambda s: None
    m.RET_STOP_ALL = 3
    m.RET_USAGE = 2
    m.thread = lambda f: f
    m.next_frame = lambda f: f
    m.delay = lambda s: (lambda f: f)

    class RconDummyPlayer:
        steam_id = OWNER
        team = "spectator"
        clean_name = "rcon"

        def __init__(self, out):
            self.out = out

        def tell(self, s):
            self.out.append(("tell", s))
    m.RconDummyPlayer = RconDummyPlayer
    sys.modules["minqlx"] = m
    return m


def write_net(folder, name, legs=True, levels=("default", "max"), flat=False):
    run, mins, upd = NETS[name]
    os.makedirs(folder, exist_ok=True)
    for lv in levels:
        ev = {"AIM_NAME": lv, "NET": name}
        np.savez(os.path.join(folder, "policy_{}.npz".format(lv)), run=np.array(run), minutes=np.array(float(mins)),
                 version=np.array(name), updated=np.array(upd), env=np.array("duel_env_ffa"), env_vars=np.array(json.dumps(ev)),
                 **({"legs": np.array("legs.npz")} if legs else {}))
    if legs:
        np.savez(os.path.join(folder, "legs.npz"), who=np.array("legs of " + name))
    if flat:
        shutil.copyfile(os.path.join(folder, "policy_default.npz"), os.path.join(folder, "policy.npz"))


def md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


class Player:
    def __init__(self, sid, team="free", name="person"):
        self.steam_id, self.team, self.clean_name, self.id = sid, team, name, int(str(sid)[-2:])
        self.out = []

    def tell(self, s):
        self.out.append(("tell", s))


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    d = os.path.abspath(sys.argv[1])
    if os.path.exists(d) and os.listdir(d):
        raise SystemExit("REFUSED: {} is not empty".format(d))
    os.makedirs(d, exist_ok=True)
    os.environ["LADDER_DIR"] = d
    m = stub_minqlx()
    import duelbot as DB
    import ladder as LA
    import ratings as RA
    DB.D = d
    LA.D = d
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import version_set as VS

    fails, n_checks = [], [0]

    def check(name, ok, extra=""):
        n_checks[0] += 1
        print(("ok   " if ok else "FAIL ") + name + (" " + extra if extra else ""))
        if not ok:
            fails.append(name)

    said, logs, recs = [], [], []
    people = []                                              # the players on the server (besides Bobby)
    bobby = types.SimpleNamespace(steam_id="90071990000000001", team="free", clean_name="BobbyBones", id=1)
    loads = []

    def make_bot():
        bot = object.__new__(DB.duelbot)
        bot.log = lambda s: logs.append(s)
        bot.msg = lambda s: said.append(("msg", s))
        bot.end_session = lambda: None
        bot.players = lambda: [bobby] + people
        bot.game = types.SimpleNamespace(state="warmup")
        bot.ready, bot.real_game, bot.go_f3, bot.game_over_t = False, False, 0.0, 0.0
        bot.room, bot.queue, bot.arena = None, [], None
        bot.env, bot.aim_prof, bot.aim_bad = None, {}, {}
        bot.wdial_reset = lambda why: None

        def setup():                                         # what setup() does for !version and !aim: policy.npz loaded
            with np.load(os.path.join(d, "policy.npz")) as z:
                bot.P = {k: z[k] for k in z.files}
            bot.policy_mtime = os.path.getmtime(os.path.join(d, "policy.npz"))
            bot.ready = True
            bot.ver_identify()
            bot.env = object()                               # (a network loaded: the aim switches live)
            bot.aim_prof = {lv: {} for lv, f in DB.duelbot.AIM_FILES.items() if os.path.exists(os.path.join(d, f))}
            loads.append(str(bot.P["version"]))
        bot.setup = setup

        def aim_live(level):                                 # the live switch: the loaded network's env_vars become the level's
            with np.load(os.path.join(d, DB.duelbot.AIM_FILES[level])) as z:
                bot.P["env_vars"] = z["env_vars"]
            return 0.1
        bot.aim_live = aim_live
        orig_record = DB.duelbot.record

        def record(**rec):
            recs.append(dict(rec))
            orig_record(bot, **rec)
        bot.record = record
        bot.sess = None
        return bot

    t = [1000.0]

    def frame(bot, n=4):                                     # frames 0.6 s apart (ver_frame and aim_frame look twice a second)
        for _ in range(n):
            t[0] += 0.6
            if not bot.ready:
                bot.setup()
            job = bot.__dict__.get("ver_job")
            if job is not None:
                job["th"].join()                             # (the copy's thread: done before the next frame here)
            bot.ver_frame(t[0])
            bot.aim_frame(t[0])

    def new_map(bot):                                        # the map hook, then the load (setup once the map is up)
        bot.ready = False
        bot.game.state = "warmup"
        bot.game_over_t, bot.go_f3, bot.real_game = 0.0, 0.0, False
        bot.ver_reset()
        bot.aim_reset()
        frame(bot)

    def flat_is(name):
        src = os.path.join(d, "versions", name)
        return all(md5(os.path.join(d, f)) == md5(os.path.join(src, s)) for s, f in
                   (("legs.npz", "legs.npz"), ("policy_default.npz", "policy_default.npz"), ("policy_max.npz", "policy_max.npz"),
                    ("policy_default.npz", "policy.npz")))

    def ver_cmd(bot, who, *args):
        bot.cmd_version(who, ["!version"] + list(args), None)

    def aim_cmd(bot, who, *args):
        bot.cmd_aim(who, ["!aim"] + list(args), None)

    # ---- 1. no versions folder: the old behaviour exactly (flat files, no !version)
    write_net(d, "2.2e", flat=True)
    mt0 = os.path.getmtime(os.path.join(d, "policy.npz"))
    bot = make_bot()
    bot.ver_name, bot.ver_job, bot.ver_pending, bot.ver_for = None, None, None, None
    bot.ver_reset()
    bot.aim_reset()
    frame(bot)
    p_ = Player(PERSON)
    people[:] = [p_]
    frame(bot)
    ver_cmd(bot, p_)
    ver_cmd(bot, p_, "1.6a")
    check("no versions: !version says nothing", p_.out == [] and not said, str(p_.out + said))
    check("no versions: policy.npz untouched", os.path.getmtime(os.path.join(d, "policy.npz")) == mt0)
    check("no versions: no welcome line, no version name", bot.ver_welcome() is None and bot.ver_name is None)
    check("no versions: the version line from the network", bot.bot_version() == "2.2e", bot.bot_version())
    check("no versions: one load only", loads == ["2.2e"], str(loads))
    help_out = Player(OTHER)
    bot.cmd_help(help_out, ["!help"], None)
    check("no versions: !help has no !version line", not any("!version" in s for _, s in help_out.out))

    # ---- 2. two versions served; policy.npz left at 1.6a by the last run: the start puts the default (the newest, 2.2e) in
    write_net(os.path.join(d, "versions", "2.2e"), "2.2e")
    write_net(os.path.join(d, "versions", "1.6a"), "1.6a")
    for v_ in ("2.2e", "1.6a"):
        json.dump(VS.build(os.path.join(d, "versions", v_)), open(os.path.join(d, "versions", v_, "version.json"), "w"))
    for f_ in ("legs.npz", "policy_default.npz", "policy_max.npz"):
        shutil.copyfile(os.path.join(d, "versions", "1.6a", f_), os.path.join(d, f_))
    shutil.copyfile(os.path.join(d, "versions", "1.6a", "policy_default.npz"), os.path.join(d, "policy.npz"))
    people[:] = []
    del said[:], loads[:]
    bot = make_bot()
    bot.ver_name, bot.ver_job, bot.ver_pending, bot.ver_for = None, None, None, None
    bot.ver_reset()
    bot.aim_reset()
    frame(bot)
    check("start: the default version (newest: 2.2e) whatever was left", bot.ver_name == "2.2e" and flat_is("2.2e") and loads == ["2.2e"],
          "{} {}".format(bot.ver_name, loads))
    check("start: the version line names it", bot.bot_version() == "2.2e")
    check("welcome line: default first", bot.ver_welcome() is not None and bot.ver_welcome().startswith("^3My versions:^7 ^2!version 2.2e^7 ^6(default)^7, ^2!version 1.6a^7"),
          str(bot.ver_welcome()))
    help_out = Player(OTHER)
    bot.cmd_help(help_out, ["!help"], None)
    check("!help lists !version", any("!version 2.2e|1.6a" in s for _, s in help_out.out), str(help_out.out[-1:]))

    # ---- 3. the command
    p_ = Player(PERSON)
    people[:] = [p_]
    frame(bot)
    ver_cmd(bot, p_)
    check("!version: the version now and the list", p_.out and p_.out[-1][1] == "^3Version^7 ^22.2e^7 (^2!version 2.2e|1.6a^7 to change, in warmup)", str(p_.out[-1:]))
    ver_cmd(bot, p_, "9.9z")
    check("!version unknown: the list, nothing changes", "^2!version 1.6a^7" in p_.out[-1][1] and bot.ver_name == "2.2e" and not bot.ver_busy(), str(p_.out[-1:]))
    spec = Player(OTHER, team="spectator")
    people[:] = [p_, spec]
    ver_cmd(bot, spec, "1.6a")
    check("permission: a spectator may not", spec.out[-1][1] == "^3Only the player in the duel can change the version.^7" and not bot.ver_busy())
    del said[:]
    ver_cmd(bot, p_, "2.2e")
    check("!version <the one playing>: stays", said[-1] == ("msg", "^3Version^7 ^22.2e^7 stays.") and not bot.ver_busy(), str(said[-1:]))

    # ---- 4. switch in warmup; the aim after it
    aim_cmd(bot, p_, "max")                                  # (the person's aim: max, remembered)
    check("aim max on 2.2e", bot.aim_level() == "max")
    del said[:], loads[:]
    ver_cmd(bot, p_, "1.6A")
    check("warmup switch: loading said, the copy started", said and said[0] == ("msg", "^3Loading version^7 ^21.6a^7 ...") and bot.ver_busy(), str(said))
    f3 = Player(PERSON)
    bot.ready_ids = set()
    bot.on_client_command(p_, "readyup")
    check("F3 while loading: refused", p_.out[-1][1] == "^3A version is loading:^7 F3 in a moment." and not bot.go_f3, str(p_.out[-1:]))
    frame(bot)
    check("switch: 1.6a loaded, its files in the flat names", bot.ver_name == "1.6a" and flat_is("1.6a") and loads == ["1.6a"], "{} {}".format(bot.ver_name, loads))
    check("switch: said with its minutes", ("msg", "^5BobbyBones^7 ^21.6a^7 loaded (^524,388^7 min of training).") in said, str(said))
    if hasattr(DB.duelbot, "aim_saved"):                    # (pub-perf: !aim remembers a person's setting; main does not)
        check("switch: the aim is the person's remembered max on 1.6a", bot.aim_level() == "max" and json.loads(str(bot.P["env_vars"]))["NET"] == "1.6a")
    else:
        check("switch: the aim is 1.6a's default (no remembered aim on this branch)", bot.aim_level() == "default" and json.loads(str(bot.P["env_vars"]))["NET"] == "1.6a")
    check("switch: remembered", json.load(open(os.path.join(d, "version_choices.json"))) == {bot.aim_key(PERSON): "1.6a"})
    ev_ = [r for r in recs if r.get("event") == "version"]
    check("switch: a version event with its times", ev_ and ev_[-1]["version"] == "1.6a" and ev_[-1]["was"] == "2.2e" and "copy_ms" in ev_[-1], str(ev_[-1:]))
    check("the version line names 1.6a", bot.bot_version() == "1.6a")
    aim_cmd(bot, p_, "default")
    del said[:], loads[:]
    ver_cmd(bot, p_, "2.2e")
    frame(bot)
    check("switch back to 2.2e: the aim is the default (none remembered)", bot.ver_name == "2.2e" and bot.aim_level() == "default" and flat_is("2.2e"), bot.aim_level())
    check("the default removes the remembered line", json.load(open(os.path.join(d, "version_choices.json"))) == {})
    ver_cmd(bot, p_, "1.6a")
    frame(bot)

    # ---- 5. the owner from the spectators (rcon): allowed, not remembered as anyone's
    people[:] = [p_]
    rc = m.RconDummyPlayer([])
    del said[:]
    ver_cmd(bot, rc, "2.2e")
    frame(bot)
    check("owner (rcon): allowed", bot.ver_name == "2.2e")
    check("owner (rcon): not remembered", json.load(open(os.path.join(d, "version_choices.json"))) == {bot.aim_key(PERSON): "1.6a"})
    ver_cmd(bot, p_, "1.6a")
    frame(bot)

    # ---- 6. during a game: promised for the next warmup
    bot.game.state, bot.real_game = "in_progress", True
    del said[:], loads[:]
    ver_cmd(bot, p_, "2.2e")
    check("in a game: promised, nothing loaded", said[-1] == ("msg", "^3Version^7 ^22.2e^7 from the next warmup (it changes between games).") and bot.ver_name == "1.6a" and not bot.ver_busy(), str(said[-1:]))
    frame(bot)
    check("in a game: the game keeps its version", bot.ver_name == "1.6a" and loads == [])
    bot.game.state, bot.real_game, bot.game_over_t = "warmup", False, time.time()     # the game's end: scoreboard and vote
    frame(bot)
    check("the game's end sequence: still kept", bot.ver_name == "1.6a" and loads == [])
    bot.game_over_t = 0.0                                    # (thrown back to warmup on the same map)
    frame(bot)
    check("the next warmup: the promised version", bot.ver_name == "2.2e" and loads == ["2.2e"], str(loads))
    bot.game.state = "in_progress"
    ver_cmd(bot, p_, "1.6a")
    del loads[:]
    bot.game.state, bot.game_over_t = "warmup", time.time()
    frame(bot)
    new_map(bot)
    check("asked for in a game, then the vote's new map: the person's choice, loaded once", bot.ver_name == "1.6a" and loads == ["1.6a"], str(loads))

    # ---- 7. the person leaves: back to the default; comes back: their choice again
    del said[:], loads[:]
    people[:] = []
    frame(bot, 8)
    check("the person leaves: back to the default", bot.ver_name == "2.2e" and flat_is("2.2e") and loads == ["2.2e"], "{} {}".format(bot.ver_name, loads))
    check("the person leaves: said", ("msg", "^3Version reset to^7 ^22.2e^7: loading ...") in said, str(said))
    del said[:], loads[:]
    people[:] = [p_]
    frame(bot)
    check("the person seated again: the remembered version", bot.ver_name == "1.6a" and loads == ["1.6a"], str(loads))
    check("the person seated again: said", any(s.startswith("^3Version back to your last choice:^7 ^21.6a^7") for _, s in said), str(said))
    p2 = Player(OTHER)
    people[:] = []
    frame(bot, 8)
    people[:] = [p2]                                         # another person, no choice of theirs
    frame(bot)
    check("another person: the default", bot.ver_name == "2.2e")

    # ---- 8. a new map: nobody's choice -> the default; with the seated person's choice -> theirs in one load
    ver_cmd(bot, p2, "1.6a")
    frame(bot)
    people[:] = [Player("76561190000000003")]               # (p2 gone, a third person seated, no choice)
    del said[:], loads[:]
    new_map(bot)
    frame(bot, 8)
    check("new map, nobody's choice: the default, one load", bot.ver_name == "2.2e" and flat_is("2.2e") and loads == ["2.2e"], str(loads))
    check("new map: the reset said", ("msg", "^3Version reset to^7 ^22.2e^7.") in said, str(said))
    people[:] = [p_]
    frame(bot, 8)
    check("p seated: 1.6a", bot.ver_name == "1.6a")
    del said[:], loads[:]
    new_map(bot)
    frame(bot, 8)
    check("new map with the seated person's choice: theirs, one load", bot.ver_name == "1.6a" and loads == ["1.6a"] and flat_is("1.6a"), str(loads))

    # ---- 9. a version folder whose files are missing is not offered
    os.replace(os.path.join(d, "versions", "1.6a", "policy_max.npz"), os.path.join(d, "versions", "1.6a", "policy_max.npz.aside"))
    vs = bot.ver_here(fresh=True)
    check("a folder with a file missing: not offered", list(vs) == ["2.2e"] and any("not offered" in l_ for l_ in logs), str(list(vs)))
    check("one version left: no welcome line", bot.ver_welcome() is None)
    ver_cmd(bot, p_, "1.6a")
    check("!version 1.6a while not offered: the list", "^2!version 2.2e^7" in p_.out[-1][1] and "1.6a" not in p_.out[-1][1], str(p_.out[-1:]))
    new_map(bot)
    check("its remembered choice: no longer offered, the default", bot.ver_name == "2.2e", str(bot.ver_name))
    os.replace(os.path.join(d, "versions", "1.6a", "policy_max.npz.aside"), os.path.join(d, "versions", "1.6a", "policy_max.npz"))
    os.makedirs(os.path.join(d, "versions", "bad name!"), exist_ok=True)
    check("a folder with a bad name: not offered", sorted(bot.ver_here(fresh=True)) == ["1.6a", "2.2e"])
    os.environ["BOBBY_VERSION_DEFAULT"] = "1.6a"
    check("BOBBY_VERSION_DEFAULT names the default", bot.ver_default(bot.ver_here(fresh=True)) == "1.6a" and bot.ver_order()[0] == "1.6a")
    del os.environ["BOBBY_VERSION_DEFAULT"]

    # ---- 10. the game's records carry the version: the session's meta and stats, the leaderboard's duel and frag lines
    ver_cmd(bot, p_, "1.6a")
    frame(bot)
    bot.sess = None
    bot.end_session = lambda: None
    bot.head_clear = lambda: None
    bot.note_person = lambda p, seat: None
    bot.react_ms = 125.0
    bot.P["action_dims"] = np.array([3])
    opp = Player(PERSON)
    opp.clean_name = "person"
    bot.start_session(opp)
    meta = json.load(open(os.path.join(bot.sess, "meta.json")))
    check("session meta: version and run", meta.get("version") == "1.6a" and meta.get("policy") == "duel_gru_1_6a", str({k: meta.get(k) for k in ("version", "policy")}))
    bot.seat = {}
    bot.on_stats({"TYPE": "PLAYER_STATS", "DATA": {"STEAM_ID": "0", "NAME": "BobbyBones", "KILLS": 3, "DEATHS": 1, "WEAPONS": {}, "PICKUPS": {}}})
    ps = [r for r in recs if r.get("event") == "player_stats"]
    check("session player_stats: version", ps and ps[-1].get("version") == "1.6a", str(ps[-1:]))
    DB.duelbot.end_session(bot)
    ends = [r for r in recs if r.get("event") == "end"]
    check("session end: version", ends and ends[-1].get("version") == "1.6a", str(ends[-1:]))

    lad = object.__new__(LA.ladder)
    lad.table = RA.Table(os.path.join(d, "ratings.json"))
    lad.board, lad.board_mt, lad.board_up, lad.salt, lad.duel, lad.report_t = None, None, {}, None, None, 0.0
    lad.game = types.SimpleNamespace(state="in_progress")
    lad.bot_plugin = lambda: bot
    m.Plugin._loaded_plugins["duelbot"] = bot
    lad.on_game_start({})
    lad.duel_track(bot, [(bobby, 0), (p_, 0)])
    bot.ver_name = "2.2e"                                    # (a switch after the start cannot happen; the record keeps the start's)
    lad.duel_track(bot, [(bobby, 5), (p_, 2)])
    bot.ver_name = "1.6a"
    lad.on_game_end({"EXIT_MSG": "Timelimit hit.", "GAME_LENGTH": 600})
    with open(os.path.join(d, "duels.jsonl")) as f:
        line = json.loads(f.read().splitlines()[-1])
    check("duels.jsonl: the version at the game's start", line.get("version") == "1.6a" and line.get("net") == "duel_gru_1_6a" and line.get("score") == [2, 5],
          str({k: line.get(k) for k in ("version", "net", "score", "aim")}))
    rec = lad.duel_record()
    check("the duel record by version", rec.get("1.6a") == [1, 0, 0] and rec.get("all") == [1, 0, 0], str(rec))
    check("the welcome's record line names the version playing", "^21.6a^7 ^51-0^7" in lad.record_line(), lad.record_line())
    lad.note_duel("k", 0, 3.0, 1, 2, True, "timed")
    with open(os.path.join(d, "duels.jsonl")) as f:
        line = json.loads(f.read().splitlines()[-1])
    check("duels.jsonl (timed): the version playing", line.get("version") == "1.6a", str(line))
    # a frag line: the frame loop pairs a death with a kill
    lad.prev, lad.seen, lad.next_save, lad.listeners, lad.next_board = {}, dict(deaths=0, own=0, paired=0, counted=0, unsure=0), 1e18, [], 1e18
    st = {1: [0, 0, 0], 99: [0, 0, 0]}
    bobby.stats = types.SimpleNamespace(kills=0, deaths=0, score=0)
    p_.stats = types.SimpleNamespace(kills=0, deaths=0, score=0)
    p_.id = 99
    lad.players = lambda: [bobby, p_]
    lad.on_frame()
    bobby.stats = types.SimpleNamespace(kills=1, deaths=0, score=1)
    p_.stats = types.SimpleNamespace(kills=0, deaths=1, score=0)
    lad.on_frame()
    with open(os.path.join(d, "frags.jsonl")) as f:
        fl = json.loads(f.read().splitlines()[-1])
    check("frags.jsonl: the version", fl.get("version") == "1.6a" and fl.get("net") == "duel_gru_1_6a", str(fl))
    check("ratings.version_of: the families' runs", RA.version_of("duel_gru_2_2e") == "2.2e" and RA.version_of("duel_gru_v0_3_1b") == "v0.3.1"
          and RA.version_of("duel_gru_v15c") == "v0.1" and RA.version_of("duel_gru_b1_1a") == "duel_gru_b1_1a")
    check("ratings.line_version: the field first, else the run", RA.line_version({"version": "1.6a", "net": "x"}) == "1.6a"
          and RA.line_version({"net": "duel_gru_2_2e"}) == "2.2e")

    print("{} of {} checks failed".format(len(fails), n_checks[0]) if fails else "all {} checks held".format(n_checks[0]))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
