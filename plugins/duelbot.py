"""duelbot: play a duel policy trained in the simulator (sim/train_duel_rnn.py) on the real Quake Live server,
and run the standard test rooms (sim/test_suite.py) with a human as the subject.

Policy play: BobbyBones is fully controlled by the network with human physics (3 moves per frame). His inputs
are built by the exact same code as in training (the simulator's observe()), fed from the real game: positions,
health, armor, weapons, ammo, the opponent's projectiles, item states. The same fairness rules apply as in
training: the opponent is only known when in view with line of sight (after the trained reaction delay) or
roughly when heard nearby. Both players spawn with the loadout the policy trained with.

Test rooms (!room ...): Bobby's body becomes the scripted target / fighter of the simulator's rooms and the
human is measured with the same metrics, giving a human baseline card (docs/guides/LOGS.md).

Opponent: the first human on the server; with DUEL_OPP=bot a plain Nightmare bot fills in while no human is
there. The server is held in warmup on the three maps.

Chat commands: !note <text>, !drill <weapon|off>, !map <name>, !room <...> (see cmd_room), !rooms.
Load with QLX_PLUGINS="botctl, duelbot". Needs /tmp/practice/policy.npz (sim/export_duel.py); rooms need
/maps/nav_<map>_sim.json. Writes /tmp/practice/sessions/<session>/ and /tmp/practice/suite/.
"""
import importlib
import json
import math
import os
import re
import shutil
import sys
import time
import zipfile

import minqlx
import numpy as np

try:                                                        # no powerups on any server: the shared helpers (plugins/powerups.py)
    _pu = importlib.import_module(__package__ + ".powerups")
except Exception:                                           # noqa: BLE001 - loaded outside the plugin package
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _pu = importlib.import_module("powerups")
try:                                                        # the network's forward pass, with the attention part of v0.2 (plugins/netpass.py)
    _net = importlib.import_module(__package__ + ".netpass")
except Exception:                                           # noqa: BLE001 - loaded outside the plugin package
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _net = importlib.import_module("netpass")

sys.path.insert(0, "/sim")
TIMING = bool(os.environ.get("DUEL_TIMING"))                # DUEL_TIMING=1: the plugin's time a frame goes to timing.txt (see time_note)
# BOBBY_AUTOHOP=1 (B-258, off by default): the game re-jumps a held jump on landing (pmove_AutoHop 1) only for a player
# whose userinfo carries cg_autoHop 1, which a person's game sends (the owner's config has it) and a bot's has not: on
# the servers Bobby's held jump has never hopped again, while the simulator he learnt in always did (plugins/physlab.py,
# 2026-10-16: with it set in the bot's userinfo, the game's hop chains match the simulator's to 0.01 u/s).
AUTOHOP = os.environ.get("BOBBY_AUTOHOP", "0") not in ("", "0")
_autohop_next = {}


_autohop_said = set()


def autohop_want(P):
    """(v0.3.7) the auto-hop a network was trained with: its policy.npz's env_vars AUTO_HOP (sim/export_duel.py writes it
    into every file from v0.3.7 on) -> True / False; None for an older file that does not say (BOBBY_AUTOHOP decides)"""
    try:
        ev_ = json.loads(str(P["env_vars"])) if P is not None and "env_vars" in P else {}
    except Exception:  # noqa: BLE001
        return None
    if "AUTO_HOP" not in ev_:
        return None
    return str(ev_["AUTO_HOP"]).strip() not in ("0", "", "0.0")


def give_autohop(p, now, log=None, want=None):
    """put cg_autoHop in a Bobby's userinfo (at most every 10 s a player): want True / False, the network's own setting
    (autohop_want: a server cannot play him with another than he trained with; BOBBY_AUTOHOP is overruled, and said so
    once); want None (an older file), cg_autoHop 1 when BOBBY_AUTOHOP is on, as before"""
    if want is None and not AUTOHOP:
        return
    if p is None or now < _autohop_next.get(p.id, 0.0):
        return
    _autohop_next[p.id] = now + 10.0
    val = "1" if (AUTOHOP if want is None else want) else "0"
    if want is not None and "BOBBY_AUTOHOP" in os.environ and bool(want) != AUTOHOP and "said" not in _autohop_said:
        _autohop_said.add("said")
        if log:
            log("BOBBY_AUTOHOP={} overruled: the network was trained with AUTO_HOP={}".format(os.environ["BOBBY_AUTOHOP"], val))
    try:
        cv = p.cvars
        if str(cv.get("cg_autoHop", "")) != val:
            cv["cg_autoHop"] = val
            p.cvars = cv
            if log:
                log("cg_autoHop {} given to client {}".format(val, p.id))
    except Exception:  # noqa: BLE001
        pass
D = "/tmp/practice"
MAPS = ("testlab", "bloodrun", "aerowalk", "lostworld", "sinister", "furiousheights", "battleforged", "campgrounds", "hektik", "toxicity", "cure")      # the only maps a player can pick with !map (owner, 2026-10-09): the duel maps he trained on or is checked on (botmode.py keeps a copy)
QLNUM = {"rl": 5, "rg": 7, "lg": 6, "mg": 2, "sg": 3, "gl": 4, "pg": 8, "hmg": 14, "g": 1}
QLNAME = {v: k for k, v in QLNUM.items()}
SCHEMA = 3
_P = ["x", "y", "z", "vx", "vy", "vz", "pitch", "yaw", "health", "armor", "weapon", "ammo_rl", "ammo_rg", "ammo_lg",
      "fwd", "right", "up", "fire"]
FRAME_COLS = ["t", "server_ms", "drill"] + ["b_" + c for c in _P] + ["o_" + c for c in _P] + \
    ["b_sees", "b_seen_ago", "los", "b_aim_err", "o_aim_err", "missiles"] + \
    ["o_buttons", "o_k_fwd", "o_k_side", "o_k_up", "o_k_fire", "o_k_btn", "o_k_wpn"]    # schema 3: the opponent's button bits, and
# his key changes counted over every command he sent (125 a second), running totals: forward/back, strafe,
# jump/crouch, fire presses, other buttons, weapon
BANDS = {"close": (150.0, 300.0), "mid": (350.0, 650.0), "far": (800.0, 1200.0)}
STYLES = ("still", "slow", "fast", "jump")
ROOM_SECS = {"aim": 60, "choice": 40, "move": 90, "solo": 120, "ladder": 120}
REP_SECS = 10.0
GOAL_NAMES = {"MH": "Mega Health", "RA": "Red Armor", "YA": "Yellow Armor"}
# the test map "testlab" (tools/make_lab_map.py): fixed rooms, the suite never changes maps
LAB_WEAPONS = ("mg", "sg", "rl", "lg", "rg", "pg")      # no grenade launcher: not an aim weapon
LAB_STYLES = ("walk", "jump", "env")       # target moves in all four directions; "jump" also jumps; "env" = environment box
# the aim-reflex experiment: three short rooms in the aim box that measure a player's hands and eyes, not his game
# (tools/reflex_report.py reads the session and works out steadiness, tracking lag, reaction and flick speed)
REFLEX = [["reflex", "slow"], ["reflex", "track"], ["reflex", "flick"], ["reflex", "rocket"]]
LAB_SUITE = [["aim", w, t] for w in LAB_WEAPONS for t in LAB_STYLES] + \
    [["move", "*"]]                        # aim rooms and movement courses; items and the fight only on request
SUITE = [["aim", w, s, "mid"] for w in ("lg", "rg", "rl") for s in ("still", "fast")] + \
    [["aim", w, "fast", b] for w in ("lg", "rg", "rl") for b in ("close", "far")] + \
    [["choice", b] for b in ("close", "mid", "far")] + [["move"], ["solo"]] + \
    [["ladder", p] for p in ("allround", "sniper", "rusher", "tracker")]


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


# the bots' own names (owner, 2026-10-09), each with "(BOT)" after it, in the order they join: the one of a 1v1 server
# is the first. All four are the same network; plugins/ladder.py keeps one row for them and plugins/banter.py gives each
# a voice.
BOT_NAMES = ("BobbyBones", "Mr Skeleton", "THE JUGGERNAUT", "Dr Evil")
# ... and their looks (owner: "The juggernaut and dr evil can get different avatars from bones in game too ... Your choice"):
# the game's own bot whose body each one is added with (the plugin moves it either way; the game's box for a player is the
# same for every model). BobbyBones and Mr Skeleton are the skeleton, THE JUGGERNAUT the big one, Dr Evil the bald one.
BOT_BODY = {"BobbyBones": "bones", "Mr Skeleton": "bones", "THE JUGGERNAUT": "tankjr", "Dr Evil": "xaero"}
BOT_SKIN = {"Mr Skeleton": "bones/red"}                    # a skin of his own, where the game lets a bot's be set


def is_bobby(p):
    """one of ours, not a person and not one of the game's own bots (a spar)"""
    return is_bot(p) and any(n in p.clean_name for n in BOT_NAMES)


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


GAME_SECS = 600.0                                           # a whole game as he is trained on them (duel_env's GAME_LEN)


class GameClock:
    """The clock and the score of a whole-games network on a server (policy.npz round_secs >= 600; duelbot.clock_frame
    keeps one for all seats). Plain numbers in, plain numbers out: nothing of the game is read here.
    key     ("game", its start) a real game, ("arena", its end) a timed duel, ("free",) neither: warmup, a server
            that never plays a game
    t0      when it began (wall time); length: the game's or the duel's limit in seconds; real: a real game
    ot      seconds of one overtime period of a real game (0: none, or sudden death)"""

    def __init__(self, key, t0, length=GAME_SECS, real=False, ot=0.0):
        self.key, self.t0, self.length, self.real, self.ot = key, float(t0), float(length), bool(real), float(ot)
        self.src = None                                      # a real game: "level" (the game's own clock) or "wall", decided once
        self.prev, self.tally = {}, {}                       # outside a real game: the game's score counted from here

    def elapsed(self, now, level=None):
        """seconds since it began. level: a real game's own clock in seconds (level time minus the level's start time)
        or None. It is taken, for the rest of the game, if after the first second it stands within five seconds of the
        time since the game's start event (a timeout stops it, the wall clock goes on: the game's is the true one);
        if it does not (a start time that is not the game's), the wall clock stays."""
        wall = max(0.0, float(now) - self.t0)
        if not self.real:
            return wall
        if self.src is None and level is not None and wall >= 1.0:
            self.src = "level" if abs(float(level) - wall) <= 5.0 else "wall"
        if self.src == "level" and level is not None:
            return max(0.0, float(level))
        return wall

    def fed(self, el, extra=True):
        """the seconds of a ten-minute game he is shown at el seconds of this clock (0 to GAME_SECS: training shows
        nothing else). A game or a timed duel shorter than ten minutes ends at GAME_SECS: it is shown as the last
        minutes of a game, as a mid-game start is in training. Past the limit: a real game in overtime (extra: not the
        scoreboard) is shown its last ot seconds again, period after period (the score is level and that much is left:
        what those inputs say); with no overtime period, or a longer game, the clock holds at the end."""
        L = self.length
        if self.key[0] == "free" or L <= 0:
            return min(el, GAME_SECS)
        if el <= L:
            return min(max(0.0, GAME_SECS - L) + el, GAME_SECS)
        if self.real and self.ot > 0 and extra:
            w = min(self.ot, GAME_SECS)
            return GAME_SECS - w + (el - L) % w
        return GAME_SECS

    def score(self, pid, raw):
        """player pid's score as he is shown it. raw: the game's own score of him (frags, a point off for a death by
        his own hand or the map). A real game: that number. Otherwise it is counted from this clock's start; a fall of
        more than a point in a frame is the game setting its counters back (a restart), not a score."""
        raw = int(raw)
        if self.real:
            return float(raw)
        d = raw - self.prev.get(pid, raw)
        self.prev[pid] = raw
        self.tally[pid] = self.tally.get(pid, 0) + (d if d >= -1 else 0)
        return float(self.tally[pid])


class duelbot(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.add_hook("player_loaded", self.on_player_loaded)
        self.add_hook("vote_called", self.on_vote_called)
        self.add_hook("team_switch_attempt", self.on_team_switch)
        self.add_hook("client_command", self.on_client_command)
        self.add_hook("game_start", self.on_game_start)
        self.add_hook("game_end", self.on_game_end)
        self.add_hook("stats", self.on_stats)
        self.add_command("help", self.cmd_help, 0)
        self.add_command("maps", self.cmd_maps, 0)
        self.add_command("map", self.cmd_map, 0, usage="<{}>".format("|".join(MAPS)))
        self.lab = None
        self.add_command("note", self.cmd_note, 0, usage="<anything you noticed>")
        self.add_command("drill", self.cmd_drill, 5, usage="<weapon|off>")
        self.add_command("room", self.cmd_room, 5,
                         usage="aim <weapon> <still|slow|fast|jump> [close|mid|far] | choice <close|mid|far> | move | solo | ladder [style] | suite | off")
        self.add_command("rooms", self.cmd_rooms, 5)
        self.add_command("reflex", self.cmd_reflex, 0)
        self.add_command("movement", self.cmd_movement, 0)
        self.add_command("duel", self.cmd_duel, 0, usage="[minutes|off]")
        self.add_command("match", self.cmd_duel, 0, usage="[minutes|off]")
        self.add_command("spar", self.cmd_spar, 5, usage="<on|off>")
        self.add_command("nosg", self.cmd_nosg, 5, usage="<on|off>")
        self.add_command("arena", self.cmd_arena, 5, usage="<box|env|yard|off> [minutes]")
        self.add_command("aim", self.cmd_aim, 0, usage="[1|2|3|4|5|max]")
        self.aim_want = None                                 # (!aim) the level asked for, put in at the next warmup
        self.arena = None                                    # a fight in one room of the test map (see cmd_arena)
        self.no_sg = False
        self.no_walk = False
        self.drill = None                                    # weapon drill: both players have only this weapon
        self.top_up = 0.0
        self.last = {}                                       # latest snapshot of both players, for notes
        self.ready = False
        self.real_game = False                               # a game the person started with F3 (the warmup abort below leaves it alone)
        self.ready_ids = set()
        self.next_check = 0.0
        self.want_map = os.environ.get("LAB_MAP", "campgrounds").lower()
        self.opp_bot = os.environ.get("DUEL_OPP", "") == "bot"
        self.room_test = os.environ.get("DUEL_ROOMTEST", "") == "1"
        self.alive = {}                                      # client id -> was alive last frame
        self.score = dict(bobby=0, opp=0)
        self.want_w = {}
        self.acc = dict(frames=0, visible=0, fire=0, fast_air=0, w={})
        self.next_summary = time.time() + 60
        self.err_t = 0.0
        self.last_abort = 0.0
        self.reload_check, self.policy_mtime = 0.0, 0.0
        self.sess, self.frames_f, self.sess_opp = None, None, None
        self.tot, self.item_was, self.item_ent = {}, {}, {}
        self.room, self.queue, self.card, self.card_path = None, [], {}, None

    def log(self, msg):
        minqlx.console_print("[duelbot] " + msg + "\n")
        with open(os.path.join(D, "duelbot.log"), "a") as f:
            f.write("{} {}\n".format(time.strftime("%H:%M:%S"), msg))

    def record(self, **rec):
        rec["t"] = round(time.time(), 2)
        rec["map"] = (minqlx.get_cvar("mapname") or "").lower()
        path = os.path.join(self.sess, "events.jsonl") if self.sess else os.path.join(D, "duel_live.jsonl")
        with open(path, "a") as f:
            f.write(json.dumps(rec) + "\n")

    def note_person(self, p, seat):
        """a seat of this session tied to the leaderboard's anonymous key of the person in it (plugins/ladder.py; owner,
        2026-10-12: "give each person a unique random id that can be used to tie their performance together"): a line
        {"event": "person", "seat", "key", "owner"} in the session's events and the same in meta.json's "people" list.
        "owner": 1 for the server's owner, whose games may be tests. Nothing without a session, for a bot, or when the
        ladder plugin is not loaded. No name and no Steam id are written."""
        if not self.sess or p is None or is_bot(p):
            return
        try:
            lad = minqlx.Plugin._loaded_plugins.get("ladder")
            key = lad.person_key(p) if lad is not None and hasattr(lad, "person_key") else None
            if not key:
                return
            owner = int(bool(lad.is_owner(p))) if hasattr(lad, "is_owner") else 0
            self.record(event="person", seat=seat, key=key, owner=owner)
            path = os.path.join(self.sess, "meta.json")
            with open(path) as f:
                meta = json.load(f)
            meta.setdefault("people", []).append(dict(seat=seat, key=key, owner=owner, t=round(time.time(), 2)))
            with open(path + ".tmp", "w") as f:
                json.dump(meta, f, indent=1)
            os.replace(path + ".tmp", path)
        except Exception as e:                               # noqa: BLE001 - a log line is never worth a frame
            minqlx.console_print("[duelbot] person: {}\n".format(type(e).__name__))

    # ------------------------------------------------------------------ session logs (schema: docs/guides/LOGS.md)
    def start_session(self, opp):
        self.end_session()
        kind = "spar" if is_bot(opp) else "human"
        mapname = (minqlx.get_cvar("mapname") or "").lower()
        self.sess = os.path.join(D, "sessions", "{}_{}_{}".format(time.strftime("%Y%m%d-%H%M%S"), mapname, kind))
        os.makedirs(self.sess, exist_ok=True)
        self.sess_opp = opp.id
        self.sess_person = not is_bot(opp)
        self.sess_t0 = time.time()
        self.head_clear()                                    # a new opponent: fresh memory
        self.gclock = None                                   # (a whole-games network: and a new clock, clock_frame)
        self.score = dict(bobby=0, opp=0)
        self.tot = {}
        self.item_was = {}
        meta = dict(schema=SCHEMA, started=round(time.time(), 2), map=mapname, opponent=kind,
                    opponent_name=opp.clean_name if is_bot(opp) else "human", policy=str(self.P["run"]),
                    train_minutes=int(self.P["minutes"]), env=str(self.P["env"]),
                    react_ms=int(self.react_ms), frame_ms=25, frame_columns=FRAME_COLS)
        with open(os.path.join(self.sess, "meta.json"), "w") as f:
            json.dump(meta, f, indent=1)
        self.frames_f = open(os.path.join(self.sess, "frames.csv"), "a")
        self.frames_f.write(",".join(FRAME_COLS) + "\n")
        self.missiles_f = open(os.path.join(self.sess, "missiles.csv"), "a")      # projectiles in flight, per frame (for replays)
        self.missiles_f.write("t,num,owner,weapon,x,y,z,vx,vy,vz\n")
        self.note_person(opp, 1)                             # (the person of a 1v1 session is seat 1: the o_ columns)
        self.log("session {}".format(os.path.basename(self.sess)))

    INLOG_EVERY, INLOG_FLUSH = 8, 600                        # every 8th frame (5 a second: v0.4's head tick); a file every 2 min

    def inputs_log(self, now, ob, h, a):
        """(owner, 2026-10-16: "log the exact inputs Bobby was given, and his memory state, every head tick") the inputs the
        network was given, the memory it answered from and its choices, every INLOG_EVERY frames of a session with a
        person: training and calibration data for v0.4's head with nothing rebuilt. Half precision; inputs_<n>.npz files
        in the session's folder (t, frame, obs, h, acts), written every INLOG_FLUSH ticks and at the session's end."""
        self.inlog_frame = getattr(self, "inlog_frame", -1) + 1
        if self.inlog_frame % self.INLOG_EVERY:
            return
        buf = self.__dict__.setdefault("inlog", [])
        buf.append((now, self.inlog_frame, np.asarray(ob, np.float16), np.asarray(h, np.float16), np.asarray(a, np.int16)))
        if len(buf) >= self.INLOG_FLUSH:
            self.inputs_flush()

    def inputs_flush(self):
        buf, self.inlog = getattr(self, "inlog", []), []
        if not buf or not self.sess:
            return
        try:
            n = len([f for f in os.listdir(self.sess) if f.startswith("inputs_")])
            np.savez_compressed(os.path.join(self.sess, "inputs_{:04d}.npz".format(n)), t=np.array([b[0] for b in buf]),
                                frame=np.array([b[1] for b in buf], np.int64), obs=np.stack([b[2] for b in buf]),
                                h=np.stack([b[3] for b in buf]), acts=np.stack([b[4] for b in buf]))
        except Exception as e:                               # noqa: BLE001 - a full disk must not stop the game
            self.log("inputs log: {}".format(type(e).__name__))

    def end_session(self):
        if self.sess:
            self.inputs_flush()
            self.record(event="end", **self.score)
            self.frames_f.close()
            if getattr(self, "missiles_f", None):
                self.missiles_f.close()
                self.missiles_f = None
        self.sess, self.frames_f, self.sess_opp = None, None, None

    def player_row(self, p, st, cmd):
        va = minqlx.view_angles(p.id)
        own, am = st.weapons, st.ammo
        return [*[round(float(v), 1) for v in st.position], *[round(float(v), 1) for v in st.velocity],
                round(float(va[0]), 2), round(float(va[1]), 2), st.health, st.armor, int(st.weapon),
                am.rl if own.rl else -1, am.rg if own.rg else -1, am.lg if own.lg else -1, *cmd]

    @staticmethod
    def aim_err(env, i):
        """degrees between player i's crosshair and the true direction to the other player's body"""
        to = env.state[i ^ 1, :3] + np.array([0, 0, 4.0], np.float32) - env._eye(env.state)[i]
        yr, pr = math.radians(float(env.yaw[i])), math.radians(float(env.pitch[i]))
        f = np.array([math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), -math.sin(pr)])
        c = float((to * f).sum() / (np.linalg.norm(to) + 1e-6))
        return round(math.degrees(math.acos(max(-1.0, min(1.0, c)))), 2)

    def log_frame(self, now, env, bs_slot, bobby, opp, bs, os_, bcmd, tag):
        """one frames.csv row; env slot bs_slot is Bobby, the other slot is the opponent"""
        o_slot = bs_slot ^ 1
        oc = minqlx.ran_usercmd(opp.id)                       # the opponent's real keys and buttons this frame
        eye = env._eye(env.state)
        los = bool(env._los(eye[:1], env.state[1:2, :3] + np.array([0, 0, 8.0], np.float32))[0])
        row = [round(now, 3), minqlx.item_states()[0], tag or "-",
               *self.player_row(bobby, bs, bcmd), *self.player_row(opp, os_, [oc[3], oc[4], oc[5], oc[1] & 1]),
               int(env.visible[bs_slot]), round(float(env.seen_t[bs_slot]), 2), int(los),
               self.aim_err(env, bs_slot), self.aim_err(env, o_slot), len(minqlx.missiles()), oc[1],
               *(minqlx.key_counts(opp.id) if hasattr(minqlx, "key_counts") else (0, 0, 0, 0, 0, 0))]
        self.frames_f.write(",".join(str(v) for v in row) + "\n")
        if getattr(self, "missiles_f", None):
            for num, own, weapon, x, y, z, vx, vy, vz in minqlx.missiles():
                who = 0 if own == bobby.id else 1 if own == opp.id else -1
                self.missiles_f.write("{},{},{},{},{:.1f},{:.1f},{:.1f},{:.0f},{:.0f},{:.0f}\n".format(round(now, 3), num, who, weapon, x, y, z, vx, vy, vz))
        dmg = {}
        for who, st, other in (("bobby", bs, os_), ("opp", os_, bs)):   # damage events from health + armor drops
            tot = max(0, st.health) + st.armor
            prev = self.tot.get(who)
            if prev is not None and prev - tot >= 3 and prev > 0:
                dmg[who] = int(prev - tot)
                self.record(event="hit", victim=who, dmg=dmg[who], killed=bool(st.health <= 0),
                            attacker_weapon=int(other.weapon), victim_weapon=int(st.weapon),
                            dist=round(float(np.linalg.norm(env.state[0, :3] - env.state[1, :3]))), los=los, drill=tag)
            self.tot[who] = tot
        return dmg, los

    # ------------------------------------------------------------------ commands
    def cmd_map(self, player, msg, channel):
        if len(msg) < 2 or msg[1].lower() not in MAPS:
            return minqlx.RET_USAGE
        self.want_map = msg[1].lower()
        _pu.load_map(self.want_map, "duel")

    HELP = ["^3What I can do:^7 I learned to play from scratch in a simulator: movement, aim, picking up items, choosing weapons. I play with human limits.",
            "^3Play me:^7 join the game, I'm already in it. ^2F3^7 starts a real 10-minute game (the scoreboard and a vote for the next map at its end); ^2!duel [minutes]^7 a timed duel in warmup.",
            "^3Help me learn:^7 ^2!map testlab^7, then ^2!reflex^7 or ^2!movement^7. ^2!match [minutes]^7 scores a game on any map.",
            "^3Maps and modes:^7 ^2!maps^7 lists the maps, ^2!map <name>^7 changes it. ^2!mode ffa^7: up to four of me and people, six seats; ^2!bots <0-4>^7 sets how many of me play. ^2!mode duel^7: one against one.",
            "^3Give feedback:^7 ^2!note <text>^7 tells me what you noticed. Every match I play is recorded, without names."]

    def cmd_help(self, player, msg, channel):
        for line in self.HELP:
            player.tell(line)
        lad = minqlx.Plugin._loaded_plugins.get("ladder")    # the leaderboard, where it is loaded (plugins/ladder.py)
        if lad is not None:
            player.tell(lad.HELP)

    def cmd_maps(self, player, msg, channel):
        player.tell("^3Maps:^7 {}. Change with ^2!map <name>^7. ^3testlab^7 has the aim and movement tests; the others are the game's duel maps.".format(", ".join(MAPS)))

    BOT_NAMES = BOT_NAMES                                 # (read by plugins/ladder.py)

    # the second line a person reads on joining (owner, 2026-10-09: a word about !bots; 2026-10-16: one line for both modes)
    WELCOME = "^2!map <map>^7 to change maps (^2!maps^7 lists them), ^2!mode <ffa|duel>^7, ^2!bots <0,1,2,3>^7 ^6(FFA only)^7"

    AIM_WELCOME = ("^3My aim:^7 ^2!aim 1^7 or ^22^7 relaxed, ^2!aim 3^7 easier, ^2!aim 4^7 normal ^6(default)^7, "
                   "^2!aim 5^7 sharp, ^2!aim max^7 no human limits")

    def on_player_loaded(self, player):
        if not is_bot(player):
            player.tell("^3I'm ^5BobbyBones^3, the learning Quake bot.^7 Here's some commands")
            player.tell(self.WELCOME)
            if self.FACTORY == "duel":                       # (!aim, owner, 2026-10-21: the 1v1 plugin's command)
                player.tell(self.AIM_WELCOME)
            lad = minqlx.Plugin._loaded_plugins.get("ladder")
            if lad is not None:                              # owner, 2026-10-09: "see how I rank on the leaderboard"
                for line in (lad.welcome_lines(player) if hasattr(lad, "welcome_lines") else [lad.WELCOME]):
                    player.tell(line)
            player.tell("^3See more about the project:^7 ^5github.com/dclark202/bobbybones-quake")
            player.tell(self.DISCORD)
            up_ = self.bot_updated()
            player.tell("^3Current bot version:^7 ^2{}^7{}".format(self.bot_version(), " (last updated ^5{}^7)".format(up_) if up_ else ""))

    # owner, 2026-10-12: the project's Discord server, in the welcome of both modes (ffabot inherits on_player_loaded);
    # the wording and the version line: owner, 2026-10-15
    DISCORD = "^3Join the discord:^7 ^5discord.gg/dH2mfzbMa^7 ^6(feedback appreciated!)^7"

    def bot_version(self):
        """the network's version name (docs: v0.1, v0.2, v0.3, ...): BOBBY_VERSION if the server sets it, else from the run's
        name (duel_gru_v0_3 -> v0.3, duel_gru_v0_2_1 -> v0.2.1; v0.1 is the run duel_gru_v15c)"""
        v = os.environ.get("BOBBY_VERSION", "").strip()
        if v:
            return v
        P = getattr(self, "P", None)
        if P is not None and "version" in P and str(P["version"]).strip():     # (sim/export_duel.py writes it, 2026-10-16)
            return str(P["version"]).strip()
        run = str(P["run"]) if P is not None and "run" in P else ""
        m = re.match(r"duel_gru_v(\d+(?:_\d+)+)[a-z]?$", run)
        if m:
            return "v" + m.group(1).replace("_", ".")
        return "v0.1" if run == "duel_gru_v15c" else (run or "unknown")

    MONTHS = ("Jan.", "Feb.", "Mar.", "Apr.", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec.")

    def bot_updated(self):
        """the day the network was put on this server, as "16 Oct. 2026" (owner, 2026-10-16): BOBBY_UPDATED (YYYY-MM-DD) if the
        server sets it, else the date sim/export_duel.py stamped in policy.npz, else the policy file's own date"""
        try:
            d = os.environ.get("BOBBY_UPDATED", "").strip()
            P = getattr(self, "P", None)
            if not d and P is not None and "updated" in P:
                d = str(P["updated"]).strip()
            if d:
                y, mo, da = (int(x) for x in d[:10].split("-"))
            else:
                t = time.localtime(getattr(self, "policy_mtime", 0.0) or os.path.getmtime(os.path.join(D, "policy.npz")))
                y, mo, da = t.tm_year, t.tm_mon, t.tm_mday
            return "{} {} {}".format(da, self.MONTHS[mo - 1], y)
        except Exception:                                    # noqa: BLE001 - no date: the line goes without it
            return ""

    def on_vote_called(self, player, vote, args):
        """no votes called by players: no kicking Bobby, no config or map changes (the map has !map, limited to MAPS).
        The game's own vote for the next map at a game's end is not such a vote and is left alone."""
        player.tell("Voting is off on this server. ^2!map <{}>^7 changes the map.".format("|".join(MAPS)))
        return minqlx.RET_STOP_ALL

    AFTER_GAME = 90.0                                        # after a real game's end the game's own end is left alone for
                                                             # this long: the scoreboard, the vote for the next map (20 s), the
                                                             # map's load. A map load ends it; a server left without one goes
                                                             # back to warmup when it is over.

    def after_game(self, now=None):
        """is the game's own end sequence running (a real game has just ended and the next map is not up yet)"""
        return (time.time() if now is None else now) - getattr(self, "game_over_t", 0.0) < self.AFTER_GAME

    def on_client_command(self, player, cmd):
        """F3 (the game's "readyup") in 1v1: a real ten-minute game starts when the person in the game is ready. The
        engine would wait for the bot, who never readies up (owner, 2026-10-07), so the plugin says "allready" for
        him: in the NEXT frame (frame(), go_f3). Said here, before the game has run the person's own "readyup", it made
        everybody ready and the game then toggled the person back to not ready: nothing started, ever (found
        2026-10-12 after "f3 on duel mode wasn't working")."""
        if cmd.strip().lower() != "readyup" or is_bot(player) or self.game is None or self.game.state != "warmup":
            return
        people = [p for p in self.players() if not is_bot(p) and p.team != "spectator"]
        now = time.time()
        if player.id not in [p.id for p in people]:          # somebody watching: his F3 starts nothing, and he is told why
            tells = self.__dict__.setdefault("f3_told", {})
            if now - tells.get(player.id, 0.0) > 10:
                tells[player.id] = now
                player.tell("^3You are watching.^7 F3 starts a game for the one who plays; join when the seat is free.")
            return
        if self.room is not None or self.queue or self.arena:
            player.tell("^3A test room or a timed duel is running:^7 ^2!room off^7 or ^2!duel off^7 first, then F3.")
            return
        if getattr(self, "go_f3", 0.0):                      # the start is already on its way
            return
        if player.id in self.ready_ids:
            self.ready_ids.discard(player.id)
        else:
            self.ready_ids.add(player.id)
        n = len([q for q in people if q.id in self.ready_ids])
        if people and n * 2 > len(people):
            self.ready_ids = set()
            self.real_game = True
            self.go_f3 = now                                 # frame() says "allready" once the game has run his "readyup"
            self.set_cvar("timelimit", "10")

    def on_stats(self, stats):
        """the game's own table for a player at the end of a game (or when he leaves): shots, hits, damage, kills and time
        per weapon, items taken. Exact, where the plugin's hit counts are inferred from health drops. Written without
        the name and the Steam id: a person is "person" with his seat, a bot keeps its name (owner, 2026-10-07)."""
        try:
            if stats.get("TYPE") != "PLAYER_STATS":
                return
            d = stats.get("DATA", {})
            sid = str(d.get("STEAM_ID", "0"))
            pl = next((p for p in self.players() if str(p.steam_id) == sid), None) if sid not in ("0", "") else None
            bot = pl is None or is_bot(pl)
            weapons = {k.lower(): {q: v.get(q, 0) for q in ("S", "H", "DG", "DR", "K", "D", "T", "P")}
                       for k, v in (d.get("WEAPONS") or {}).items() if v.get("S") or v.get("T") or v.get("P")}
            seat = getattr(self, "seat", {}).get(pl.id) if pl is not None and isinstance(getattr(self, "seat", None), dict) else None
            self.record(event="player_stats", bot=bool(bot), who=(d.get("NAME") if bot else "person"), seat=seat,
                        warmup=bool(d.get("WARMUP")), aborted=bool(d.get("ABORTED")), play_time=d.get("PLAY_TIME"),
                        kills=d.get("KILLS"), deaths=d.get("DEATHS"), damage=d.get("DAMAGE"), weapons=weapons,
                        pickups={k.lower(): v for k, v in (d.get("PICKUPS") or {}).items() if v})
        except Exception as e:                                  # noqa: BLE001
            minqlx.console_print("[duelbot] stats: {}\n".format(e))

    def on_game_start(self, data):
        self.ready_ids = set()
        self.game_new = True                                 # (v0.2: frame() starts his round with the game)
        self.game_t0 = time.time()                           # (a whole-games network: the game's clock starts here, clock_frame)
        self.game_over_t = 0.0

    def on_game_end(self, data):
        """a real game's own end (not one thrown back to warmup): the scoreboard and the vote for the next map follow,
        and the plugin keeps its hands off until the next map is up (owner, 2026-10-12; until then frame() said
        "abort" in the very frame of the end, because the game was no longer a person's: no scoreboard, no vote)"""
        if self.real_game and not (isinstance(data, dict) and data.get("ABORTED")):
            self.game_over_t = time.time()
            self.vote_map_ok = True                          # the map the vote picks is kept (frame, not ready)
        self.real_game = False

    def on_team_switch(self, player, old, new):
        """one person plays against Bobby at a time; everyone else spectates and is queued by the game"""
        if is_bot(player) or new == "spectator":
            return
        for p in self.players():
            if p.id != player.id and not is_bot(p) and p.team in ("free", "red", "blue"):
                player.tell("^3BobbyBones is playing {}.^7 Spectate: you play when they leave.".format(p.clean_name))
                return minqlx.RET_STOP_ALL

    def cmd_note(self, player, msg, channel):
        """the play-tester's feedback, stamped with the game state at that moment"""
        if len(msg) < 2:
            return minqlx.RET_USAGE
        self.record(event="note", text=" ".join(msg[1:]), drill=self.drill, room=self.room["name"] if self.room else None,
                    state=self.last, **self.score)
        player.tell("noted")

    def cmd_drill(self, player, msg, channel):
        names = [w for w in self.E.WEAPONS if w != "g"] if self.ready else []
        if len(msg) < 2 or msg[1].lower() not in names + ["off"]:
            player.tell("usage: !drill <{}|off>".format("|".join(names)))
            return
        self.drill = None if msg[1].lower() == "off" else msg[1].lower()
        self.record(event="drill", drill=self.drill, **self.score)
        for p in self.players():
            if p.team != "spectator" and p.state and p.state.health > 0:
                self.give_loadout(p)
        self.msg("Drill: {}".format(self.drill or "off (normal loadout)"))

    def cmd_nosg(self, player, msg, channel):
        """!nosg: nobody spawns with a shotgun (it can still be picked up on the map). !nosg off: back to normal."""
        self.no_sg = len(msg) < 2 or msg[1].lower() != "off"
        self.record(event="nosg", on=self.no_sg, **self.score)
        for p in self.players():
            if p.team != "spectator" and p.state and p.state.health > 0:
                self.give_loadout(p)
        self.msg("Spawn weapons: {}".format("everything except the shotgun" if self.no_sg else "everything"))

    def cmd_arena(self, player, msg, channel):
        """!arena box | env [minutes]: fight BobbyBones in the aim box or the environment box under the rules he
        trains with there: full weapon set at spawn, 125 health, nobody leaves the room, five minutes. !arena off ends."""
        a = [m.lower() for m in msg[1:]]
        if a and a[0] == "off":
            if self.arena:
                self.arena_end("stopped")
            return
        if not self.lab:
            player.tell("The arena is on the test map: !map testlab first.")
            return
        here = {k: v for k, v in (("box", "aim"), ("env", "env"), ("yard", "yard")) if v in self.lab}
        if not a or a[0] not in here:
            player.tell("usage: !arena <{}|off> [minutes]".format("|".join(here)))
            return
        mins = float(a[1]) if len(a) > 1 and a[1].replace(".", "", 1).isdigit() else 5.0
        self.arena_start(a[0], mins)

    def arena_start(self, where, mins=5.0):
        self.queue, self.room, self.drill = [], None, None
        self.arena = dict(where=where, t_end=time.time() + mins * 60, mins=mins, base=dict(self.score), place=True, dmg=[0, 0])
        self.record(event="arena_start", where=where, minutes=mins)
        own = bool(self.lab.get("yard", {}).get("items")) and where == "yard"
        self.msg("^3Arena: the {}^7, {:g} minutes. {} !arena off stops.".format(
            {"box": "aim box", "env": "environment box", "yard": "yard"}[where], mins,
            "Duel spawn: the weapons, mega health and red armor are on the map." if own else "Full weapons at spawn, nobody leaves the room."))

    def arena_end(self, why="time"):
        A = self.arena
        self.arena = None
        b, o = self.score["bobby"] - A["base"]["bobby"], self.score["opp"] - A["base"]["opp"]
        self.record(event="arena_result", where=A["where"], minutes=A["mins"], why=why, bobby=b, opp=o,
                    dmg_dealt=A["dmg"][0], dmg_taken=A["dmg"][1])
        if A["where"] == "map" and A.get("key"):             # a timed duel on a duel map against a person: a line in the
            try:                                             # leaderboard's duels.jsonl, by his key (plugins/ladder.py)
                lad = minqlx.Plugin._loaded_plugins.get("ladder")
                if lad is not None and hasattr(lad, "note_duel"):
                    played = A["mins"] if why == "time" else max(0.0, A["mins"] - (A["t_end"] - time.time()) / 60.0)
                    lad.note_duel(A["key"], A.get("owner", 0), played, o, b, why != "time", "timed")
            except Exception as e:                           # noqa: BLE001
                self.log("duel line: {}".format(type(e).__name__))
        self.msg("^3Arena over ({})^7: BobbyBones ^2{}^7 : ^2{}^7 opponent. Damage {} : {}.".format(why, b, o, A["dmg"][0], A["dmg"][1]))

    def arena_spot(self, other):
        """a place in the arena at least 500 units from the other player"""
        L = self.lab
        if self.arena["where"] == "box":
            z = float(L["aim"]["subject"][2])
            cand = [np.array([self.rng.uniform(96, 1440), self.rng.uniform(96, 928), z], np.float32) for _ in range(12)]
        else:
            e = L["yard" if self.arena["where"] == "yard" else "env"]
            cand = [np.array([q[0], q[1], q[2] if len(q) > 2 else e["z"]], np.float32) for q in e["spots"]]
        d = np.array([float(np.linalg.norm(q - np.asarray(other, np.float32))) for q in cand])
        ok = np.nonzero(d > 500)[0]
        return cand[int(self.rng.choice(ok))] if len(ok) else cand[int(d.argmax())]

    def arena_inside(self, pos):
        b = [-32, -32, 1568, 1056] if self.arena["where"] == "box" else \
            self.lab["yard" if self.arena["where"] == "yard" else "env"]["bounds"]
        return b[0] - 48 <= pos[0] <= b[2] + 48 and b[1] - 48 <= pos[1] <= b[3] + 48

    def cmd_spar(self, player, msg, channel):
        """!spar on: you become a spectator and Bobby plays a Nightmare bot (a real match). !spar off: back to you."""
        on = len(msg) < 2 or msg[1].lower() != "off"
        self.opp_bot = on
        self.room, self.queue = None, []
        if on:
            player.put("spectator")
            self.msg("Spar: BobbyBones against a Nightmare bot. Join the game or type !spar off to stop.")
        else:
            for p in self.players():
                if is_bot(p) and not is_bobby(p):
                    minqlx.console_command("clientkick {}".format(p.id))
            self.msg("Spar off. Join the game to play him yourself.")

    def cmd_rooms(self, player, msg, channel):
        if self.lab and "aim" not in self.lab:
            player.tell("The training arena: play BobbyBones freely, or ^3!duel^7 for a timed five minutes. ^3!map testlab^7 has the test rooms.")
            return
        if self.lab:
            player.tell("!room aim <{}> <walk|jump|env>  (25 s, env 45 s)".format("|".join(LAB_WEAPONS)))
            player.tell("!room move <{}> (30 s or until the end)".format("|".join(self.lab.get("courses", {}))))
            player.tell("!arena box | env | yard = fight BobbyBones in that room for 5 minutes, full weapons (yard: the new two-level arena)")
            player.tell("!room moves = every movement course in a row, with a table of times at the end")
            player.tell("!room items (120 s): time the mega and the red armor | !room fight (60 s): the game's Nightmare bot")
            player.tell("!room suite = every room, about 20 minutes | !room off")
            player.tell("^3!movement^7 = every movement course, timed | ^3!duel^7 = five minutes against BobbyBones in the environment room")
            player.tell("^3!reflex^7 = the aim reflex test: four short aim rooms, three minutes (lightning, rail, rockets)")
            return
        player.tell("!room aim <lg|rg|rl|pg|sg|hmg|mg> <still|slow|fast|jump> [close|mid|far]  (60 s)")
        player.tell("!room choice <close|mid|far> (40 s) | move (90 s) | solo (120 s)")
        player.tell("!room ladder [{}] (120 s)".format("|".join(self.R.PERSONAS)))
        player.tell("!room suite = the standard set, about 20 minutes | !room off")

    def cmd_reflex(self, player, msg, channel):
        """!reflex = !room reflex"""
        if not (self.lab and "aim" in self.lab):
            player.tell("The reflex test is on the test lab: ^3!map testlab^7, then ^3!reflex")
            return
        return self.cmd_room(player, ["!room", "reflex"], channel)

    def cmd_movement(self, player, msg, channel):
        """!movement = every movement course in a row, timed (the test lab)"""
        if not (self.lab and self.lab.get("courses")):
            player.tell("The movement courses are on the test lab: ^3!map testlab^7, then ^3!movement")
            return
        return self.cmd_room(player, ["!room", "moves"], channel)

    def cmd_duel(self, player, msg, channel):
        """!duel [minutes] = a timed duel against BobbyBones: in the environment room on the test lab (full weapons),
        on the training arena across the whole map (duel spawn, items on the map)"""
        a = [m.lower() for m in msg[1:]]
        if a and a[0] == "off":
            if self.arena:
                self.arena_end("stopped")
            return
        if not self.lab:                                     # a duel map: the whole map as it is, scored and timed
            mins = float(a[0]) if a and a[0].replace(".", "", 1).isdigit() else 10.0
            self.queue, self.room, self.drill = [], None, None
            self.arena = dict(where="map", t_end=time.time() + mins * 60, mins=mins, base=dict(self.score), place=False, dmg=[0, 0])
            self.record(event="arena_start", where="map", minutes=mins)
            self.msg("^3Duel: {:g} minutes on this map.^7 Normal spawn, the items are on the map. !duel off stops.".format(mins))
            return
        where = "env" if "env" in self.lab else "yard"
        return self.cmd_arena(player, ["!arena", where] + [m for m in msg[1:2]], channel)

    def subject_id(self, p):
        """an anonymous id for a player: the same person gets the same id on this server, nothing personal is stored"""
        import hashlib
        path = os.path.join(D, "salt.txt")
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(hashlib.sha1(os.urandom(32)).hexdigest())
        return hashlib.sha1((open(path).read().strip() + str(getattr(p, "steam_id", p.id))).encode()).hexdigest()[:10]

    def cmd_room(self, player, msg, channel):
        a = [m.lower() for m in msg[1:]]
        if not self.ready:
            player.tell("The server is still loading the map, try again in a few seconds.")
            return
        if not a:
            return self.cmd_rooms(player, msg, channel)
        if self.lab and "aim" not in self.lab and a[0] != "off":      # the training arena has no test rooms
            return self.cmd_rooms(player, msg, channel)
        if a[0] == "off":
            self.queue, self.room = [], None
            self.msg("Rooms off: back to the normal duel.")
            return
        specs = (LAB_SUITE if self.lab else SUITE) if a[0] == "suite" else [a]
        if a[0] == "reflex" and len(a) == 1:
            if not (self.lab and "aim" in self.lab):
                player.tell("The reflex test runs on the test map: ^3!map testlab^7, then ^3!reflex")
                return
            specs = REFLEX
        if self.lab and a[0] == "moves":                     # every movement course in a row, timed
            specs = [["move", "*"]]
        if self.lab:                                         # "move *" = every movement course on the map
            specs = [x for sp_ in specs for x in ([["move", k] for k in self.lab.get("courses", {})]
                                                   if sp_ == ["move", "*"] else [sp_])]
        out = []
        for s in specs:
            r = self.room_spec(s)
            if r is None:
                player.tell("^1No such room:^7 !room {}".format(" ".join(a)))
                return self.cmd_rooms(player, msg, channel)
            out.append(r)
        if a[0] == "reflex" and len(a) == 1:
            self.queue, self.room, self.batch = list(out), None, None
            self.msg("^3Aim reflex test:^7 four short rooms, about three and a half minutes. In three of them the target shoots back for the second half. Aim as well as you can and move as you normally would. "
                     "!room off stops it.")
            return
        if a[0] != "suite":                                  # a single room starts right away, replacing whatever runs
            self.queue, self.room = [], None
        self.batch = None
        if self.lab and a[0] == "moves":
            self.batch = dict(names=[r["name"] for r in out], results={})
            self.queue += out
            self.msg("All {} movement courses in a row. A table of your times follows the last one. !room off stops.".format(len(out)))
            return
        if a[0] == "suite" and self.lab:
            self.queue += out
            self.msg("Test suite on the lab map: {} rooms, about {} minutes. !room off stops it.".format(
                len(out), round(sum(r["secs"] + 5 for r in out) / 60)))
            return
        if self.renv.field is None and any(r["kind"] == "move" for r in out):
            player.tell("The movement room needs this map's nav file.")
            out = [r for r in out if r["kind"] != "move"]
        self.queue += out
        if a[0] == "suite":
            self.msg("Test suite: {} rooms, about {} minutes. !room off stops it.".format(
                len(out), round(sum(r["secs"] + 6 for r in out) / 60)))

    def room_spec(self, a):
        R = self.R
        if self.lab:
            if a[0] == "aim" and len(a) >= 3 and a[1] in LAB_WEAPONS and a[2] in LAB_STYLES:
                return dict(kind="aim", lab=True, name="aim/{}/{}".format(a[1], a[2]), weapon=a[1], style=0,
                            script=1, secs=45 if a[2] == "env" else 25, where="env" if a[2] == "env" else "aim",
                            jump=a[2] == "jump")
            if a[0] == "reflex" and len(a) >= 2 and a[1] in ("slow", "track", "flick", "rocket") and "aim" in self.lab:
                # slow: the target walks slowly from side to side, turning every 2.5 s (steadiness on an easy target;
                # a standing one would be hit every time by anyone). track: it strafes left and right and turns round at
                # random moments (tracking lag, reaction to a change of direction). flick: it stands, and jumps to a
                # new place every two to three seconds (time to react, flick speed, time to the shot)
                return dict(kind="aim", lab=True, reflex=a[1], name="reflex/" + a[1], script=1, where="aim", jump=False,
                            weapon={"flick": "rg", "rocket": "rl"}.get(a[1], "lg"), near=a[1] != "flick",
                            style=1 if a[1] == "flick" else 0,
                            secs={"slow": 20, "track": 40, "flick": 40, "rocket": 40}[a[1]],
                            under_fire=a[1] != "slow")    # second half of the room: the target shoots back
            if a[0] == "terrain" and len(a) >= 2 and a[1] in self.lab["stations"]:
                return dict(kind="terrain", lab=True, name="terrain/" + a[1], script=0, secs=60, key=a[1])
            if a[0] == "speed" or (a[0] == "move" and len(a) >= 2 and a[1] in self.lab.get("courses", {})):
                key = "speed" if a[0] == "speed" else a[1]
                return dict(kind="speed", lab=True, name="move/" + key, script=0, secs=30, key=key)
            if a[0] == "items" and "items" in self.lab:
                return dict(kind="solo", lab=True, name="items", script=0, secs=int(self.lab["items"].get("secs", 120)),
                            where="items")
            if a[0] == "fight":
                # the game's own Nightmare bot: our control of Bobby's body is released for the room
                return dict(kind="ladder", lab=True, name="fight/nightmare", style=0, script=0, secs=60, ai=True)
            return None
        if a[0] == "aim" and len(a) >= 3 and a[1] in R.WEAPONS and a[1] != "g" and a[2] in STYLES:
            band = a[3] if len(a) > 3 and a[3] in BANDS else "mid"
            name = "aim/{}/{}".format(a[1], a[2]) + ("" if band == "mid" else "@" + band)
            return dict(kind="aim", name=name, weapon=a[1], style=R.STYLES.index(a[2]), band=BANDS[band], script=1,
                        secs=ROOM_SECS["aim"])
        if a[0] == "choice" and len(a) >= 2 and a[1] in BANDS:
            return dict(kind="choice", name="choice/" + a[1], style=3, band=BANDS[a[1]], script=1, secs=ROOM_SECS["choice"])
        if a[0] == "move":
            return dict(kind="move", name="move", script=0, secs=ROOM_SECS["move"])
        if a[0] == "solo":
            return dict(kind="solo", name="solo", script=0, secs=ROOM_SECS["solo"])
        if a[0] == "ladder":
            per = a[1] if len(a) > 1 and a[1] in R.PERSONAS else "allround"
            return dict(kind="ladder", name="ladder/" + per, style=0, script=2, secs=ROOM_SECS["ladder"],
                        persona=R.PERSONAS.index(per))
        return None

    def on_map(self, mapname, factory):
        self.end_session()
        self.ready = False
        self.alive = {}
        self.room, self.queue = None, []
        self.game_over_t, self.go_f3 = 0.0, 0.0              # a new map: a game's end sequence is over with it
        self.aim_reset()

    # ------------------------------------------------------------------ setup
    FACTORY = "duel"                                         # (ffabot: "ffa")

    def no_powerups(self, say=False):
        """no quad, no battle suit, no other powerup on any map, and the items of a duel in every mode (see
        plugins/powerups.py)"""
        try:
            done = _pu.strip()
            if self.FACTORY != "duel":
                lay = _pu.duel_layout((minqlx.get_cvar("mapname") or "").lower())
                if lay and (lay[0] or lay[1]):
                    done.append("the items of a duel: {} removed, {} put there".format(*lay))
                    self.item_ent, self.item_was = {}, {}   # entity numbers changed hands: match them to his items afresh
            if done or say:
                cls = [c for _, c, *_ in minqlx.item_states()[1]]
                self.log("powerups on {}: {} (the game's switch {}, {} items, mega {}, powerups left {})".format(
                    (minqlx.get_cvar("mapname") or "").lower(), ", ".join(done) if done else "none found",
                    minqlx.get_cvar("g_spawnItemPowerup"), len(cls), "there" if "item_health_mega" in cls else "NOT there",
                    sum(1 for c in cls if c in _pu.POWERUPS)))
        except Exception as e:                               # noqa: BLE001
            self.log("powerups: {!r}".format(e))

    def setup(self):
        mapname = (minqlx.get_cvar("mapname") or "").lower()
        self.set_cvar("g_weaponRespawn", "5")                # weapons back in 5 s, as in the simulator (ITEM_DEFS: every weapon
                                                             # 5); the free-for-all plugin sets the same (a runtime cvar outlives the map)
        if _pu.map_pool(self.FACTORY):                       # the maps of the vote at a game's end: the ten, in 1v1
            self.log("the vote's map pool: {}".format(minqlx.get_cvar("sv_mapPoolFile")))
        self.no_powerups(say=True)
        bsp = "/tmp/maps/{}.bsp".format(mapname)
        if not os.path.exists(bsp) or os.path.getsize(bsp) < 1000:
            os.makedirs("/tmp/maps", exist_ok=True)
            data = None
            for pak in ["/ql/baseq3/pak00.pk3", "/ql/baseq3/{}.pk3".format(mapname)] + sorted(
                    __import__("glob").glob("/ql/steamapps/workshop/content/282440/*/{}.pk3".format(mapname))):   # the Workshop item (public server)
                try:
                    data = zipfile.ZipFile(pak).read("maps/{}.bsp".format(mapname))
                    break
                except (KeyError, OSError):
                    pass
            if data is None:
                raise RuntimeError("no map file for " + mapname)
            with open(bsp, "wb") as f:
                f.write(data)
        self.P, self.attn = _net.load(os.path.join(D, "policy.npz"))     # (v0.2: with the attention part, if it has one)
        self.policy_mtime = os.path.getmtime(os.path.join(D, "policy.npz"))
        self.dims = [int(x) for x in self.P["action_dims"]]
        if "legs" in self.P:                                 # his legs' network (duel_env's LEGS), exported beside the policy file
            os.environ["LEGS_NET"] = os.path.join(D, str(self.P["legs"]))
        self.E = E = self.env_module(str(self.P["env"]))
        # the round after which his clock, score and memory start over, as in training
        self.round_secs = float(self.P["round_secs"]) if "round_secs" in self.P else (180.0 if mapname == "arena1" else 120.0)
        # with the map's walking graph: without it the inputs about the way to the items, about his chosen item and the
        # map reader's numbers are all zero. It was missing here until 2026-10-08 (the free-for-all plugin had it), so
        # in every 1v1 game on a real server he played without them (he never went near the red armor on arena1).
        nav = "/maps/nav_{}_sim.json".format(mapname)
        os.environ["ROUTE_CACHE"] = D                          # the route grid is cached here (/maps is read-only)
        self.env = E.DuelEnv(bsp, n_matches=1, seed=1, nav=nav if os.path.exists(nav) else None)
        self.clock_setup(self.env)                           # (a whole-games network: the game's clock, see clock_frame)
        self.react_ms = float(self.P["react_ms"]) if "react_ms" in self.P else E.REACT_FRAMES * 25.0
        self.env.react_frames = round(self.react_ms / 25)    # same reaction delay as in training (newer simulators)
        self.no_walk = bool(self.P["no_walk"]) if "no_walk" in self.P else False    # trained without the walk key
        self.rules2 = hasattr(E, "ACQUIRE_FRAMES")           # simulators with sounds, clock, crouch, human aim limits
        if self.rules2:
            self.env.acquire_frames = round(float(self.P["acquire_ms"]) / 25) if "acquire_ms" in self.P else E.ACQUIRE_FRAMES
            self.env.lab = None
        self.prev_opp, self.fb_next, self.sess_t0 = None, np.zeros(4, np.float32), time.time()
        self.round_base = (0, 0)
        self.h = np.zeros((1, _net.width(self.P)), np.float32)            # (--slow-mem: wider with the slow memory)
        # the test rooms always use the current simulator's scripted players; slot 0 = human, slot 1 = Bobby
        self.R = R = importlib.import_module("duel_env")
        self.renv = R.DuelEnv(bsp, n_matches=1, seed=2, nav=nav if os.path.exists(nav) else None)
        self.renv.lab = None                                 # the plugin runs the lab rooms itself (placement, zones, jumping)
        self.goal_labels = [d[4] for d in self.renv.item_def if d[4] in GOAL_NAMES]
        self.lab = None
        rooms_json = "/ql/maps-data/{}/rooms.json".format(mapname)       # our own maps: the test lab, the training arena
        if os.path.exists(rooms_json):
            with open(rooms_json) as f:
                self.lab = json.load(f)
        self.rng = np.random.default_rng(int(time.time()))
        self.item_ent = {}
        self.game_new, self.ground_was, self.shot_made = False, None, {}
        self.obs_dump, self.aim_dump = [], []                # (the debugging dumps start over with a network: another one has other inputs)
        self.ready = True
        self.log("rules on {}: weapons back in {} s, the vote's map pool {}, factory {}".format(
            mapname, minqlx.get_cvar("g_weaponRespawn"), minqlx.get_cvar("sv_mapPoolFile"), minqlx.get_cvar("g_factory")))
        self.log("ready on {}: policy {} ({} min of training), {} inputs, reaction {} ms, rooms nav {}, {}{}".format(
            mapname, self.P["run"], int(self.P["minutes"]), E.OBS_DIM, int(self.react_ms),
            "yes" if self.renv.field is not None else "no", _net.describe(self.P, self.attn), self.v02_note(self.env, E)))

    def act(self, obs):
        """one frame of the network for the one Bobby of a 1v1 server (plugins/netpass.py: the same sums as the
        simulator's checks, the attention part of v0.2 included; one sampled choice per output, as in training). (v0.4) A
        network with a head is told the tick's events on the frames its head ticks (head_events)."""
        ev = self.head_events(self.env) if _net.head_due(self.P, self.h)[0] else None
        xl = self.env.legs_prep()[:1] if _net.needs_xl(self.P) else None    # (--legs-feat, --legs-guide) the legs' inputs of this frame
        acts, self.h = _net.step(self.P, self.attn, obs, self.h, self.rng, ev, xl=xl)
        return [int(v) for v in acts[0]]

    # ------------------------------------------------------------------ v0.4: the head's events (sim/duel_env.py HEAD_EVENTS)
    # The head (sim/head.py) is told on each of its ticks what happened to him since the last one: the simulator's
    # head_events(), [players, 32] (HEAD_EVENT_COLS). step() fills its books; a plugin feeds the same books through the
    # simulator's own hooks: hear(), _hear(), note_take() and note_respawn() (called above as before: they count the sounds,
    # pickups and returns), and once a frame note_combat() (the damage he dealt and took, his frags, his deaths: from the
    # game's counts) and note_frame() (the frame, the enemy noticed, the pain sound, his weapon, take-offs and landings),
    # in head_note(). With a simulator without HEAD_EVENTS (or the switch off: the network was trained without it) the
    # events are zeros, as the trainer's are then.
    def head_events(self, env):
        """the tick's events for seat 0 [1, 32] (zeros without HEAD_EVENTS)"""
        if getattr(self.E, "HEAD_EVENTS", False) and hasattr(env, "head_events"):
            return np.asarray(env.head_events(), np.float32)[:1]
        return np.zeros((1, int(getattr(self.E, "N_HEAD_EVENTS", 32))), np.float32)

    def head_note(self, env, dealt=0.0, taken=0.0):
        """once a frame, at its end (as step() does at its end): the frame's fighting and the frame itself in the head's books.
        dealt, taken: points (health and armor) Bobby dealt to the opponent and took from anything; his frags and deaths since
        the last call are counted at the deaths (hd_frag, hd_died)"""
        if not (getattr(self.E, "HEAD_EVENTS", False) and hasattr(env, "note_combat")):
            return
        fr_, di_ = self.__dict__.pop("hd_frag", 0), self.__dict__.pop("hd_died", 0)
        env.note_combat(np.array([dealt, 0.0], np.float32), np.array([taken, 0.0], np.float32),
                        np.array([fr_, 0.0], np.float32), np.array([di_, 0.0], np.float32))
        env.note_frame()

    def head_clear(self):
        """a fresh memory (a new opponent, a new game, a new life of an older run): netpass.clear (the head's tick clock kept,
        as in training); the head's books start over"""
        _net.clear(self.P, self.h)
        if getattr(self.E, "HEAD_EVENTS", False) and hasattr(self.env, "head_events"):
            self.env.head_events()

    # ------------------------------------------------------------------ v0.2: what step() keeps for the last 143 inputs
    # The simulator's observe() builds them (N_V02) and keeps their clocks, but a plugin never calls step(): the noise he
    # makes (note_noise, beside hear), every pickup (note_take), the share of the round left (v02_left), a new life (what
    # _fresh forgets) and a game's start (what a round's start resets) are told to the simulator here. Both plugins use
    # these; with a simulator from before v0.2 each of them does nothing.
    def v02_note(self, env, E):
        """for the log: what the new inputs found on this map"""
        if not hasattr(env, "v02_pp"):
            return ""
        aim = getattr(E, "AIM_SET", {})                      # (as the module read it when it was loaded: the proof that the switch arrived)
        return "; v0.2 inputs: {} places, {} cells with numbers, ways {}; aim level {} (sight off by {:.3f} deg, hand noise {:.4f}, surprise {:.0f} ms), legs {} (a stretch ends after {} readings of no)".format(
            len(env.v02_pp), 0 if env.v02_cell is None else len(env.v02_cell[4]) - 1,
            "none" if env.v02_ways is None else "{} points".format(len(env.v02_ways)), aim.get("level", "?"),
            float(getattr(E, "PERCEPT_SIGMA", 0.0)), float(getattr(E, "MOTOR_NOISE", 0.0)), float(getattr(E, "SURPRISE_MS", 0.0)),
            "on" if getattr(E, "LEGS", False) and getattr(env, "teacher", None) is not None else "off", getattr(E, "LEGS_OFF", "?"))

    # ------------------------------------------------------------------ the game's clock for a whole-games network
    # A network trained on whole ten-minute games (policy.npz round_secs >= 600) has one clock, one score and one memory
    # for a game. Both plugins give it those through the simulator's seat clocks (clock_t, clock_game: observe() reads
    # them): clock_setup() after the simulator is built, clock_frame() once a frame for ALL seats in place of the round
    # lines. A network of two-minute rounds never comes here.
    def clock_setup(self, env):
        self.gclock = None                                   # (begun in the first frame: clock_frame)
        whole = self.round_secs >= GAME_SECS
        self.game_seat = whole and hasattr(env, "clock_t")
        if whole and not self.game_seat:
            self.log("policy.npz says whole games ({:.0f} s) and this simulator has no seat clocks: the round lines, every {:.0f} s".format(
                self.round_secs, self.round_secs))
        elif whole:
            self.log("a whole-games network: the game's clock, score and memory (a real game's own; outside one a clock of {:.0f} s)".format(GAME_SECS))

    def game_state(self):
        try:
            return self.game.state if self.game is not None else None
        except Exception:                                    # noqa: BLE001 - no game yet (a map is loading)
            return None

    @staticmethod
    def cvar_secs(name, scale=1.0):
        try:
            return max(0.0, float(minqlx.get_cvar(name) or 0) * scale)
        except (TypeError, ValueError):
            return 0.0

    def clock_frame(self, now, env, rows):
        """one frame of the game's clock for every seat. rows: (seat, player) for everybody seated, people too (their
        scores are in his inputs). Starts a new clock where one begins (his memory is empty there), then writes the
        time, the share left and the scores into the simulator for observe()."""
        state = self.game_state()
        t0g = getattr(self, "game_t0", None)                 # a real game's start (on_game_start)
        if t0g is not None and state != "in_progress" and now - t0g > 3.0:
            t0g = self.game_t0 = None                        # it is over (thrown back to warmup, or a new map)
        A = getattr(self, "arena", None)                     # a timed duel (the 1v1 plugin)
        key = ("game", t0g) if t0g is not None else ("arena", A["t_end"]) if A else ("free",)
        c = self.gclock
        why = None
        if c is None:
            why = "a new session"
        elif c.key != key:
            why = {"game": "a game began", "arena": "a timed duel began"}.get(key[0], "the {} is over".format(
                "game" if c.key[0] == "game" else "timed duel"))
        elif key[0] == "free" and now - c.t0 > GAME_SECS:
            why = "{:.0f} s outside a game".format(GAME_SECS)
        if why:
            if key[0] == "game":
                c = GameClock(key, t0g, self.cvar_secs("timelimit", 60.0) or GAME_SECS, True,
                              self.cvar_secs("g_overtime") if self.FACTORY == "duel" else 0.0)
            elif key[0] == "arena":
                c = GameClock(key, A["t_end"] - A["mins"] * 60.0, A["mins"] * 60.0)
            else:
                c = GameClock(key, now)
            self.gclock = c
            self.head_clear()                                # a new game, a new memory
            self.log("clock: {} ({}, limit {:.0f} s, overtime {:.0f} s): clock, score and memory start".format(why, key[0], c.length, c.ot))
        level, extra = None, True
        if c.real:
            if c.src != "wall":
                try:                                         # the game's own clock: level time minus the level's start time
                    level = (int(minqlx.item_states()[0]) - int(minqlx.get_configstring(13))) / 1000.0
                except Exception:                            # noqa: BLE001 - no such number: the time since the start event
                    level = None
            was = c.src
            el = c.elapsed(now, level)
            if c.src != was:
                self.log("clock: the game's time by {} ({} s against {:.1f} s since its start event)".format(
                    "the game's own clock" if c.src == "level" else "the wall clock", level, now - c.t0))
            if el > c.length:
                extra = (minqlx.get_configstring(14) or "") != "1"       # (configstring 14: the scoreboard is up, the game is over)
        else:
            el = c.elapsed(now)
        t = c.fed(el, extra)
        env.clock_t = np.full(env.n, t, np.float32)          # every seat: the same game
        env.clock_game = np.ones(env.n, bool)
        env.round_t[0] = t
        if hasattr(env, "v02_left"):                         # the share of the game left
            env.v02_left = min(1.0, max(0.0, 1.0 - t / GAME_SECS))
        env.frags_r[:] = 0                                   # (an empty seat has no score)
        ids = set()
        for k, p in rows:
            env.frags_r[k] = c.score(p.id, p.stats.score)
            ids.add(p.id)
        for pid in [q for q in c.prev if q not in ids]:      # he left: his count goes with him
            c.prev.pop(pid, None)
            c.tally.pop(pid, None)
        if os.environ.get("CLOCK_LOG") and now > getattr(self, "clock_log_t", 0.0):
            self.clock_log_t = now + 60.0                    # CLOCK_LOG=1: a line a minute, to set beside the game's own clock and scoreboard
            self.log("clock: {} at {:.1f} s of its {:.0f}, shown {:.1f} s (clock {:.3f}, left {:.3f}), by {}, level {}; scores by seat {}; kills and deaths {}".format(
                key[0], el, c.length, t, t / GAME_SECS, 1.0 - t / GAME_SECS, c.src or "the wall clock", level,
                {k: int(env.frags_r[k]) for k, p in rows}, {k: (p.stats.kills, p.stats.deaths) for k, p in rows}))

    @staticmethod
    def new_life_of(env, i):
        """player i has a new life: what the others knew him to have, and his big pickups as they counted them, went
        with the old one (the simulator's _fresh)"""
        if hasattr(env, "v02_pk"):
            m_ = env._mates(i)
            env.e_got[m_, env._slot(i)] = 0.0
            env.v02_pk[m_, env._slot(i)] = 0.0

    @staticmethod
    def new_game_in(env):
        """a real game has begun (everybody spawns anew, every item lies there again): what the simulator resets at a
        round's start. Nothing is known, nothing is believed, nothing was taken."""
        if hasattr(env, "_v02_round"):
            env.it_t[:], env.e_got[:], env.e_life[:] = 99.0, 0.0, 99.0
            if hasattr(env, "bel_t"):
                env.bel_t[:] = 99.0
            env._v02_round(np.ones(env.n, bool))

    @staticmethod
    def v02_tick(env, E):
        """a frame on which observe() is not called (none of ours alive): the new inputs' clocks, kept in observe(), go on"""
        if hasattr(env, "v02_took"):
            for name in ("v02_bt", "v02_ht", "v02_took", "v02_by"):
                setattr(env, name, np.minimum(getattr(env, name) + E.DT, 99.0).astype(np.float32))
            env.v02_loud = (env.v02_loud * (1.0 - E.DT / E.V02_LOUD_T)).astype(np.float32)
        if getattr(E, "EN_STACK", False) and hasattr(env, "_es_update"):
            env._es_update()                                 # (B-257) the belief of the enemy's stack goes on too
        if getattr(E, "DRIFT_IN", False) and hasattr(env, "drift_clear"):
            env.drift_clear()                                # (DRIFT_IN) a frame with no picture: no rate across it

    def time_note(self, total):
        """DUEL_TIMING=1: the plugin's time for a frame on which the network ran: the whole frame hook, of it building
        the inputs (observe) and the network. A line per number of Bobbys alive goes to timing.txt every 2,400 such
        frames (a minute for one Bobby): the median and the 99th percentile in milliseconds."""
        tn = self.__dict__.pop("t_net", None)
        if tn is None:
            return
        T = self.__dict__.setdefault("t_rows", [])
        T.append((int(self.__dict__.pop("t_live", 1)), total, self.__dict__.pop("t_obs", 0.0), tn))
        if len(T) >= 2400:
            a = np.array(T)
            self.t_rows = []
            with open(os.path.join(D, "timing.txt"), "a") as f:
                for nb in np.unique(a[:, 0]):
                    r = a[a[:, 0] == nb] * 1000.0
                    f.write("{} {} bobbys {} frames | frame median {:.2f} p90 {:.2f} p99 {:.2f} max {:.2f}, over 15 ms {:.1%}, over 25 ms {:.1%} | inputs median {:.2f} p99 {:.2f} | network median {:.2f} p99 {:.2f}\n".format(
                        time.strftime("%H:%M:%S"), int(nb), len(r), np.median(r[:, 1]), np.percentile(r[:, 1], 90), np.percentile(r[:, 1], 99), r[:, 1].max(),
                        float((r[:, 1] > 15.0).mean()), float((r[:, 1] > 25.0).mean()),
                        np.median(r[:, 2]), np.percentile(r[:, 2], 99), np.median(r[:, 3]), np.percentile(r[:, 3], 99)))

    # ------------------------------------------------------------------ players and world
    def cast(self):
        bobby, human, filler = None, None, None
        for p in sorted(self.players(), key=lambda q: q.id):
            if p.team == "spectator":
                continue
            if is_bot(p):
                if is_bobby(p):
                    if bobby is None:
                        bobby = p
                    elif time.time() > self.next_check:      # more than one Bobby (left over from free-for-all): one stays
                        self.next_check = time.time() + 3
                        minqlx.console_command("clientkick {}".format(p.id))
                else:
                    filler = p
            elif human is None:
                human = p
        if self.room_test and human is None:                 # dry run of the rooms with a bot as the subject
            human, filler = filler, None
        return bobby, human, filler

    def give_loadout(self, p, E=None, only=None, boost=1):
        """spawn weapons as in training. only = one weapon (drill / aim room); boost multiplies the ammo"""
        E = E or self.E
        if only is None:
            only = self.drill
        if not only and self.lab and self.lab.get("yard", {}).get("items"):
            return                                           # a map with its own weapons: the game's duel spawn stands
        nine = hasattr(E, "NW")
        try:
            if only:
                k = E.WEAPONS.index(only)
                p.weapons(reset=True, g=nine, **{only: True})
                p.ammo(**{only: int(E.DRILL_AMMO[k]) if nine else (150 if only == "lg" else 25)})
                p.weapon(QLNUM[only])
            elif nine:
                owned, ammo = E.LOADOUTS["all"]
                mw = getattr(self.env, "map_weapons", None)      # only weapons that lie on this map
                if mw is not None:
                    owned = tuple(k for k in owned if k in mw)
                    ammo = {k: v for k, v in ammo.items() if k in owned or E.WEAPONS[k] == "mg"}
                if getattr(self, "no_sg", False):
                    owned = tuple(k for k in owned if E.WEAPONS[k] != "sg")
                    ammo = {k: v for k, v in ammo.items() if E.WEAPONS[k] != "sg"}
                kw = {E.WEAPONS[k]: True for k in owned}
                kw.update(mg=True, g=True)
                p.weapons(reset=True, **kw)
                p.ammo(**{E.WEAPONS[k]: int(min(E.AMMO_MAX[k], v * boost)) for k, v in ammo.items()})
                p.weapon(QLNUM[E.WEAPONS[owned[0]]])          # the simulator spawns holding the first weapon (rockets)
            else:
                has, ammo = E.LOADOUTS["full"]
                p.weapons(reset=True, g=True, mg=True, rl=bool(has[0]), rg=bool(has[1]), lg=bool(has[2]))
                p.ammo(mg=100, rl=int(ammo[0]), rg=int(ammo[1]), lg=int(ammo[2]))
        except Exception as e:
            self.log("loadout error: {!r}".format(e))

    @staticmethod
    def fill_player(env, E, i, p, st):
        """copy one real player's state into simulator slot i; returns (pos, vel, ground, pitch, yaw)"""
        pos = np.array(st.position, np.float32)
        vel = np.array(st.velocity, np.float32)
        floor = env.w.rays(pos[None], np.array([[0, 0, -1.0]], np.float32), 30.0)[0, 0] < 1
        ground = 1.0 if (abs(vel[2]) < 1 and floor) else 0.0
        va = minqlx.view_angles(p.id)
        pitch, yaw = float(va[0]), float(va[1])
        if hasattr(env, "sp_hist"):                          # (v14) his speed over the ground one to four frames ago:
            env.sp_hist[i, 1:] = env.sp_hist[i, :-1].copy()  # the simulator's step() keeps it, a plugin has to
            env.sp_hist[i, 0] = float(np.hypot(env.state[i, 3], env.state[i, 4]))
        env.state[i] = [*pos, *vel, ground, yaw]
        env.yaw[i], env.pitch[i] = yaw, pitch
        env.hp[i], env.armor[i] = st.health, st.armor
        names = E.WEAPONS
        num = {QLNUM[w]: k for k, w in enumerate(names)}
        env.weapon[i] = num.get(int(st.weapon), names.index("mg"))
        for k in range(env.has.shape[1]):
            env.has[i, k] = bool(getattr(st.weapons, names[k]))
            env.ammo[i, k] = 0 if names[k] == "g" else max(0, getattr(st.ammo, names[k]))
        return pos, vel, ground, pitch, yaw

    def sync_world(self, env, E, ids):
        """projectiles in flight and item states from the real game into the simulator. ids = client id per slot.
        Returns the items taken this frame as (class name, slot or -1)."""
        env.ra[:] = False
        kinds = {5: 0}
        if hasattr(E, "NW"):
            kinds = {5: E.RL, 4: E.GL, 8: E.PG}
        ms = minqlx.missiles()
        born = getattr(self, "missile_born", None)           # entity number -> when it was first seen (a grenade's age: the game's
        if born is None:                                     # list has no fuse; the simulator's inputs want it, see PROJ_SEE)
            born = self.missile_born = {}
        now_ = time.time()
        live_ = {m_[0] for m_ in ms}
        for num_ in [n_ for n_ in born if n_ not in live_]:
            del born[num_]
        pf_ = getattr(E, "PROJ_FIX", False)
        if pf_ and not hasattr(self, "pf_slots"):
            self.pf_slots = {}
        for slot, owner in enumerate(ids):
            k = 0
            if pf_:                                          # (PROJ_FIX) a projectile keeps its slot while it flies, as in the simulator
                prev_ = self.pf_slots.get((id(env), slot), {})
                mine_ = [m_ for m_ in ms if m_[1] == owner and m_[2] in kinds]
                cur_ = {m_[0]: prev_[m_[0]] for m_ in mine_ if m_[0] in prev_}
                free_ = [q_ for q_ in range(E.K) if q_ not in cur_.values()]
                for m_ in mine_:
                    if m_[0] not in cur_ and free_:
                        cur_[m_[0]] = free_.pop(0)
                self.pf_slots[(id(env), slot)] = cur_
                for num, own, weapon, x, y, z, vx, vy, vz in mine_:
                    if num in cur_:
                        k_ = cur_[num]
                        env.rp[slot, k_], env.rv[slot, k_], env.ra[slot, k_] = (x, y, z), (vx, vy, vz), True
                        if hasattr(env, "rw"):
                            env.rw[slot, k_] = kinds[weapon]
                        if hasattr(env, "rage"):
                            env.rage[slot, k_] = now_ - born.setdefault(num, now_)
                continue
            for num, own, weapon, x, y, z, vx, vy, vz in ms:
                if own == owner and weapon in kinds and k < E.K:
                    env.rp[slot, k] = (x, y, z)
                    env.rv[slot, k] = (vx, vy, vz)
                    env.ra[slot, k] = True
                    if hasattr(env, "rw"):
                        env.rw[slot, k] = kinds[weapon]
                    if hasattr(env, "rage"):
                        env.rage[slot, k] = now_ - born.setdefault(num, now_)
                    k += 1
        taken = []
        self.took_k = []                                     # ... and which of the simulator's items each was (-1: none of his), in the same order
        drops = []
        dropped = {}
        if hasattr(E, "DROP_MAX"):
            dropped = {"weapon_rocketlauncher": E.RL, "weapon_railgun": E.RG, "weapon_lightning": E.LG, "weapon_shotgun": E.SG,
                       "weapon_grenadelauncher": E.GL, "weapon_plasmagun": E.PG, "weapon_hmg": E.HMG}
        if env.nI:
            now_ms, items = minqlx.item_states()
            for num, cls, x, y, z, up, back_ms in items:
                if up and cls.startswith("weapon_") and 0 < back_ms - now_ms <= 30500:
                    # A weapon a dead player left: the game removes it 30 s after it fell (a map item that is there has no
                    # such time). Until 2026-10-08 one lying within 40 units of a map item was taken for that item.
                    if cls in dropped:
                        drops.append((dropped[cls], (x, y, z), (back_ms - now_ms) / 1000.0))
                    continue
                key = (id(env), num)
                k = self.item_ent.get(key)
                if k is None:
                    d = np.linalg.norm(env.item_pos - np.array([x, y, z], np.float32), axis=1)
                    k = self.item_ent[key] = int(d.argmin()) if d.min() < 40 else -1
                if k >= 0:
                    if up and not env.item_up[0, k] and hasattr(env, "note_respawn") and self.item_was.get(num) is not None:
                        env.note_respawn(k)                  # it came back: those in earshot hear it
                    env.item_up[0, k] = bool(up)             # and the seconds until it is back, as the simulator counts them
                    env.item_t[0, k] = 0.0 if up else min(60.0, max(0.0, (back_ms - now_ms) / 1000.0))   # (never set until 2026-10-08)
                if self.item_was.get(num, up) and not up:    # an item was just taken: by the nearer player
                    d = np.linalg.norm(env.state[:, :3] - np.array([x, y, z], np.float32), axis=1)
                    taken.append((cls, int(d.argmin()) if d.min() < 120 else -1))
                    self.took_k.append(int(k))
                self.item_was[num] = up
        if hasattr(env, "drop_w"):                           # what he is shown of them (the simulator's N_DROP inputs)
            env.drop_w[0] = -1
            for j, (w_, p_, t_) in enumerate(drops[:env.drop_w.shape[1]]):
                env.drop_pos[0, j] = p_
                env.drop_w[0, j] = w_
                env.drop_t[0, j] = t_
                if hasattr(env, "drop_kn"):                  # (SENSE_MINOR) in a duel both know of the death that left it
                    env.drop_kn[:, j] = True
        return taken

    @staticmethod
    def senses(env, E):
        """sight (line of sight + field of view) and hearing, same rules as the simulator's step()"""
        s, n = env.state, 2
        eye = env._eye(s)
        opp = np.arange(n) ^ 1
        to = s[opp, :3] - eye
        dist = np.linalg.norm(to, axis=1) + 1e-6
        yr, pr = np.radians(env.yaw), np.radians(env.pitch)
        fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
        infov = (to * fdir).sum(1) / dist > (env.fov()[2] if hasattr(env, "fov") else E.FOV_COS)
        alive = env.hp[opp] > 0
        cand = np.nonzero(infov & (dist < 4000) & alive)[0]
        vis = np.zeros(n, bool)
        if len(cand):
            vis[cand] = env._los(eye[cand], s[opp[cand], :3] + np.array([0, 0, 8.0], np.float32))
        env.visible = vis
        heard = (~vis) & alive & (dist < E.HEAR) & (np.hypot(s[opp, 3], s[opp, 4]) > 250)
        hf_ = getattr(E, "HEAR_FIX", False)
        if hf_:                                              # (HEAR_FIX) a footstep or a jump of his on this frame, where the
            heard = (~vis) & alive & (dist < E.HEAR) & env.hf_ev[opp]     # game sends it (as step())
            if getattr(E, "HEAR_QL", False):
                heard &= env._hear_ok(np.arange(n), opp)
        if getattr(E, "LG_DEAF", False):                     # (LG_DEAF) his own lightning gun muffles the footsteps (as step())
            heard &= dist < env._lgd_hear_reach(np.arange(n), opp)
        if hasattr(env, "vis_run"):                          # newer rules: an enemy is noticed only after a moment in view
            need_ = max(1, env.acquire_frames - env.react_frames)
            if getattr(E, "SURPRISE_MS", 0) > 0 and hasattr(env, "acq_extra"):    # off the crosshair and unexpected: noticed later (as in training)
                ecc_ = np.degrees(np.arccos(np.clip((to * fdir).sum(1) / dist, -1.0, 1.0)))
                env.acq_extra = np.where(vis & (env.vis_run == 0), E.surprise_frames(ecc_, env.seen_t), np.where(vis, env.acq_extra, 0))
                need_ = need_ + env.acq_extra
            env.vis_run = np.where(vis, env.vis_run + 1, 0)
            vis = vis & (env.vis_run >= need_)
            env.acquired = vis
        env.known[vis] = s[opp[vis], :3]
        if heard.any() and hf_:                              # (HEAR_FIX) placed by the sound, as step() places him
            if getattr(E, "LG_DEAF", False):                 # (LG_DEAF) a muffled footstep is placed with more error
                env.known[heard] = env._hf_place(np.nonzero(heard)[0], opp[heard], muff=env._lgd_muff(np.nonzero(heard)[0], opp[heard]))
            else:
                env.known[heard] = env._hf_place(np.nonzero(heard)[0], opp[heard])
        elif heard.any():
            env.known[heard] = s[opp[heard], :3] + env.rng.normal(0, 80, (int(heard.sum()), 3)).astype(np.float32) * \
                np.array([1, 1, 0], np.float32)
        env.seen_t = np.where(vis | heard, 0.0, env.seen_t + E.DT).astype(np.float32)
        if hasattr(env, "seen2") and env.seen2.shape[1] == 1:
            # The group simulator with two players (a 1v1 server playing a network trained in it): it keeps these per
            # other player as well, and the inputs of v0.2 read them there (_v02_others); its step() fills both.
            env.vis2[:, 0], env.vis_run2[:, 0], env.acq2[:, 0] = env.visible, env.vis_run, env.acquired
            env.known2[:, 0], env.seen2[:, 0] = env.known, env.seen_t
        return dist

    def held(self, env, i):
        """the weapon slot i has chosen (as in the simulator, where a switch is immediate); the game's own weapon
        when nothing was chosen, the chosen one is not owned, or the game has disagreed for over a second"""
        real = int(env.weapon[i])
        k = (id(env), i)
        want, since = self.want_w.get(k, (real, 0))
        if want == real:
            since = 0
        else:
            since += 1
        if want >= env.has.shape[1] or not env.has[i, want] or since > 80:
            want, since = real, 0
        self.want_w[k] = (want, since)
        return want

    def drive(self, p, env, E, i, a, pitch, yaw, only=None, limited=False):
        """turn one action row into keys and mouse for the controlled bot in slot i (same rules as the simulator).
        limited: the finger rules were already applied to this row (the free-for-all plugin: one call for all seats)"""
        rules2 = hasattr(E, "ACQUIRE_FRAMES") and len(a) > 7 and env.script[i] == 0
        hand = rules2 and hasattr(env, "limit_keys") and getattr(env, "key_limits", False)
        if rules2 and not limited and getattr(E, "LEGS", False) and len(a) > getattr(E, "LEGS_HEAD", 99):
            # his legs (duel_env's LEGS): the switch is read as in the simulator and, while it is on, the movement
            # network's choices of this frame take the place of his movement keys and view turn, before the finger limits
            A = np.tile(np.asarray(a, np.int64), (env.n, 1))
            A[np.arange(env.n) != i, E.LEGS_HEAD] = 0
            _net.legs_feed(self.P, env, E, rows=[i])         # (LEGS_IN, B-253) his legs' choices from the branch of his network
            env._legs_step(A)
            a = A[i]
            self.legs_n = getattr(self, "legs_n", np.zeros(3))
            on_ = float(env.legs_on[i])
            self.legs_n += (1.0, on_, on_ * float(np.hypot(env.state[i, 3], env.state[i, 4])))
            if int(self.legs_n[0]) % 2400 == 0:              # a line a minute: how much his legs carried him, and how fast
                with open(os.path.join(D, "legs_status.txt"), "a") as f_:
                    f_.write("{} frames {} on his legs {:.3f} speed there {:.0f}\n".format(
                        time.strftime("%H:%M:%S"), int(self.legs_n[0]), self.legs_n[1] / self.legs_n[0], self.legs_n[2] / max(1.0, self.legs_n[1])))
        if rules2 and not limited and getattr(E, "WALK_NO_JUMP", False):     # (WALK_NO_JUMP) walking: the jump let go, before the finger limits
            A1_ = np.asarray(a, np.int64)[None].copy()
            E.walk_no_jump(A1_)
            a = A1_[0]
        if hand and not limited:                             # finger limits, as in training
            A = np.tile(np.asarray(a, np.int64), (env.n, 1))
            env.limit_keys(A, who=np.arange(env.n) == i)
            a = A[i]
        self.row_used = a                                    # (for DUEL_AIMDUMP: his choices as his hands and legs left them)
        key = E.WALK if (rules2 and a[7] == 1 and not self.no_walk) else 127
        fwd, side = (int(a[0]) - 1) * key, (int(a[1]) - 1) * key
        jump = (127 if a[2] == 1 else -127 if a[2] == 2 else 0) if len(a) > 7 else int(a[2]) * 127
        if rules2:
            env.duck[i] = a[2] == 2
        cmd = np.array([E.TURN[a[3]], E.PITCH[a[4]]], np.float32)
        if getattr(E, "LEGS_TURN_ADD", False) and len(a) > E.TA_HEAD and getattr(env, "ta_add", None) is not None:
            cmd[0] = float(E.turn_sum(cmd[:1], env.ta_add[i:i + 1])[0])     # (LEGS_TURN_ADD) on his legs: their turn plus his correction
        zs = float(E.ZOOM) if (rules2 and hasattr(env, "zoom") and env.zoom[i]) else 1.0     # zoomed: the hand turns the view less
        cmd = cmd * zs
        if hasattr(env, "turn_dir"):                         # (the simulator's step keeps these: the movement network is shown
            sg_ = float(np.sign(cmd[0]))                     # which way his view turns and when it may turn back)
            flip_ = sg_ != 0 and env.turn_dir[i] != 0 and sg_ != float(env.turn_dir[i])
            env.rev_wait[i] = float(env.t_rev) if flip_ else max(0.0, float(env.rev_wait[i]) - 1.0)
            if sg_ != 0:
                env.turn_dir[i] = sg_
        nine = hasattr(E, "NW")
        sm = np.where(np.abs(cmd) <= 1.0, E.MOUSE_SMOOTH_FINE, E.MOUSE_SMOOTH) if hasattr(E, "MOUSE_SMOOTH_FINE") \
            else E.MOUSE_SMOOTH
        if getattr(E, "ZOOM_PERCEPT", False):               # (ZOOM_PERCEPT) small in hand terms: 1 degree unzoomed, as in training
            sm = np.where(np.abs(cmd) <= zs + 1e-6, E.MOUSE_SMOOTH_FINE, E.MOUSE_SMOOTH)
        env.mv[i] = sm * env.mv[i] + (1.0 - sm) * cmd
        turn, dpit = float(env.mv[i, 0]), float(env.mv[i, 1])
        if rules2 and env.human_aim:                         # flick cap and hand noise, as in training
            env.mv[i, 0] = np.clip(env.mv[i, 0], -E.TURN_CAP * zs, E.TURN_CAP * zs)
            v_ = env._hand_band(np.arange(env.n) == i)[i] if getattr(E, "HAND_BAND", False) else env.mv[i]   # (HAND_BAND) as in training
            jit = self.rng.normal(0, 1, 2) * (E.MOTOR_NOISE * np.abs(v_) + E.MOTOR_BASE * zs)
            turn, dpit = float(v_[0] + jit[0]), float(v_[1] + jit[1])
        if rules2 and hasattr(env, "pad_turn"):               # the mouse pad: an edge, and lifting the mouse, as in training
            full = lambda v, t=np.float32: np.full(env.n, v, t)      # noqa: E731
            t_, p_ = env.pad_turn(full(turn), full(dpit), full(len(a) > 9 and a[9] == 1, bool), full(zs),
                                  np.arange(env.n) == i)
            turn, dpit = float(t_[i]), float(p_[i])
        yaw = (yaw + turn + 180.0) % 360.0 - 180.0
        lev = 1.0 if (nine and env.seen_t[i] <= 0.5) else env.level     # newer simulators: no pull while an enemy is in view
        pitch = float(np.clip(pitch * lev + dpit, -89, 89))
        names = E.WEAPONS
        ncol = env.has.shape[1]
        w = self.want_w.get((id(env), i), (int(env.weapon[i]), 0))[0] if nine else int(env.weapon[i])
        if only:
            w = names.index(only)
        if a[6] > 0:                                         # switch only to weapons owned
            want = int(a[6]) - 1
            ok = bool(env.has[i, want]) if want < ncol else not only     # older simulator: machine gun always owned
            if ok and want != w and not (only and not nine):
                w = want
                env.cool[i] = max(env.cool[i], (float(env.fire_cd[i]) if nine else 0.0) + E.SWITCH)
        fire = bool(a[5] == 1)
        if rules2 and hasattr(env, "mouse_hold") and hasattr(E, "MOUSE_HOLD") and not hand:
            # the fire finger as in training: the button changes state at most every 100 ms (MOUSE_HOLD). Without this
            # the network's frame-by-frame requests reached the game raw and the lightning gun stuttered (2026-10-06).
            # (Simulators with limit_keys do this there; until 2026-10-08 it was done here as well, so the finger's clock
            # ran double and the hold was half of the trained one.)
            env.mouse_hold[i, 0] += 1
            if fire != bool(env.fire_last[i]) and env.mouse_hold[i, 0] >= int(E.MOUSE_HOLD[0]):
                env.mouse_hold[i, 0] = 0
                env.fire_last[i] = fire
            fire = bool(env.fire_last[i])
        env.cool[i] = max(0.0, env.cool[i] - E.DT)
        if nine:
            env.fire_cd[i] = max(0.0, env.fire_cd[i] - E.DT)
        if rules2 and nine and getattr(E, "AUTO_SWITCH", False) and fire and env.cool[i] <= 1e-4 and w != E.G and w < ncol and env.ammo[i, w] <= 0:
            can_ = env.has[i] & (env.ammo[i] > 0)            # the game's weapon change on an empty weapon is the client's: a
            can_[E.G] = True                                 # server does not do it for a bot, so it is done here (AUTO_SWITCH)
            w = int(E.AUTO_ORDER[int(np.argmax(can_[E.AUTO_ORDER]))])
            env.cool[i] = max(float(env.cool[i]), E.NOAMMO_WAIT + E.SWITCH)
        refire = E.W_REFIRE if nine else (E.REFIRE, E.RG_REFIRE, E.LG_TICK, E.MG_TICK)
        ready = env.cool[i] <= 0
        if nine:                                             # a shot leaves on this frame, as the simulator counts one (v0.2: the
            self.__dict__.setdefault("shot_made", {})[(id(env), i)] = bool(     # noise he makes, told to it on the next frame)
                fire and ready and w != E.G and w < ncol and env.ammo[i, w] > 0)
        if fire and ready:
            env.cool[i] = float(refire[w])
            if nine:
                env.fire_cd[i] = float(refire[w])
            if rules2 and env.human_aim and refire[w] >= 0.4:    # nobody fires on the exact frame the reload ends
                env.cool[i] += min(float(self.rng.exponential(E.RELOAD_JITTER)), E.RELOAD_JITTER_MAX)
        # slow weapons under the newer rules: the button is only pressed when our own reload timer allows it
        if nine:
            self.want_w[(id(env), i)] = (w, self.want_w.get((id(env), i), (w, 0))[1])
        press = fire and (ready or not (rules2 and refire[w] >= 0.4))
        if hasattr(env, "fire_q"):                           # the simulator's shot leaves one frame after the command
            self.press_q = getattr(self, "press_q", {})
            rl_ = w == getattr(E, "RL", -1)
            if (getattr(E, "RL_QL", False) and rl_) or (getattr(E, "FIRE_QL", False) and not rl_):
                # (FIRE_QL) the same for every other weapon (rail, lightning, machine guns, shotgun, gauntlet, plasma,
                # grenades): the game fires on the command's frame, as the simulator does with the switch on.
                # (RL_QL, B-268) a rocket leaves on the command's frame, as in the simulator since v0.3.1: pressed now, no
                # hold. A press held from the frame before was for another weapon (the simulator fires it with that one);
                # here it would go out with the rocket launcher, so it is dropped (on a switch frame the game would only
                # begin the weapon change with it anyway).
                self.press_q[(id(env), i)] = False
            else:
                press, self.press_q[(id(env), i)] = self.press_q.get((id(env), i), False), press
        minqlx.set_bot_input(p.id, fwd, side, jump, 1 if press else 0, QLNUM[names[w]], pitch, yaw)
        return w, fire, pitch, yaw, [fwd, side, jump, int(fire)]

    # ------------------------------------------------------------------ !aim (owner, 2026-10-21)
    # !aim 1|2|3|4|5|max sets his aim for the next game (1 and 2: owner, 2026-10-22): one export per level (policy_l1.npz to l5,
    # policy_l4.npz, policy_l5.npz, policy_max.npz: the same network, AIM_LEVEL and the aim delays in env_vars changed),
    # and the chosen one is copied over policy.npz and loaded at once when no game runs (warmup), else at the next
    # warmup (a game in progress, its countdown, its end and the next map's load keep the aim they started with).
    AIM_FILES = {"1": "policy_l1.npz", "2": "policy_l2.npz", "3": "policy_l3.npz", "4": "policy_l4.npz", "5": "policy_l5.npz",
                 "max": "policy_max.npz"}

    def aim_level(self):
        """the aim level of the network loaded: "1" to "5", "max" (AIM_LEVEL in its env_vars; 40 is max)"""
        try:
            v = float(json.loads(str(self.P["env_vars"])).get("AIM_LEVEL", 3))
        except Exception:                                    # noqa: BLE001 - no network loaded yet
            return "?"
        return "max" if v > 9 else "{:g}".format(v)

    AIM_DEFAULT = "4"

    def aim_reset(self):
        """a new map: back to the default aim (owner, 2026-10-22); policy.npz is loaded by setup() once the map is up"""
        self.aim_want = None
        src, dst = os.path.join(D, self.AIM_FILES[self.AIM_DEFAULT]), os.path.join(D, "policy.npz")
        if self.aim_level() in (self.AIM_DEFAULT, "?") or not os.path.exists(src):
            return
        try:
            tmp = dst + ".aim.tmp"
            shutil.copyfile(src, tmp)
            os.replace(tmp, dst)
            self.log("new map: aim level back to {}".format(self.AIM_DEFAULT))
        except Exception as e:                           # noqa: BLE001
            self.log("aim reset: {!r}".format(e))

    def aim_busy(self):
        """a game (or its countdown or end), a test room, a timed duel or a map load: the aim stays as it is for now"""
        try:
            st = self.game.state if self.game is not None else None
        except Exception:                                    # noqa: BLE001
            st = None
        return (not self.ready or st != "warmup" or self.real_game or bool(getattr(self, "go_f3", 0.0)) or self.after_game()
                or self.room is not None or bool(self.queue) or bool(self.arena))

    def aim_apply(self, level):
        """copy the level's export over policy.npz and load it (setup(), as the hot reload does)"""
        src, dst = os.path.join(D, self.AIM_FILES[level]), os.path.join(D, "policy.npz")
        tmp = dst + ".aim.tmp"
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
        self.aim_want = None
        self.end_session()
        self.setup()
        self.log("aim level {} loaded ({})".format(level, self.AIM_FILES[level]))

    def cmd_aim(self, player, msg, channel):
        """!aim: the aim level now (and the one asked for the next game). !aim 1|2|3|4|5|max: that level from the next game
        (at once when no game runs)"""
        cur = self.aim_level()
        if len(msg) < 2:
            want = self.aim_want if self.aim_want and self.aim_want != cur else None
            player.tell("^3Aim level^7 ^2{}^7{} (^2!aim 1-5|max^7 to change)".format(
                cur, ", ^2{}^7 from the next game".format(want) if want else ""))
            return
        lv = msg[1].lower().strip()
        if lv not in self.AIM_FILES:
            player.tell("^3Aim levels:^7 ^2!aim 1^7 or ^22^7 relaxed, ^2!aim 3^7 easier, ^2!aim 4^7 normal, ^2!aim 5^7 sharp, "
                        "^2!aim max^7 no human limits")
            return
        if not os.path.exists(os.path.join(D, self.AIM_FILES[lv])):
            player.tell("^3Aim {} is not on this server.^7".format(lv))
            return
        if lv == cur:
            self.aim_want = None
            self.msg("^3Aim level^7 ^2{}^7 stays.".format(lv))
            return
        if self.aim_busy():
            self.aim_want = lv
            self.msg("^3Aim level^7 ^2{}^7 from the next game (this one stays at ^2{}^7).".format(lv, cur))
            return
        try:
            self.aim_apply(lv)
            self.msg("^3Aim level now^7 ^2{}^7.".format(self.aim_level()))
        except Exception as e:                               # noqa: BLE001
            self.log("aim {}: {!r}".format(lv, e))
            player.tell("^3Aim could not be changed.^7")

    def aim_frame(self, now):
        """a level asked for during a game goes in at the next warmup"""
        if not self.aim_want or now < getattr(self, "aim_check", 0.0):
            return
        self.aim_check = now + 2.0
        if self.aim_want == self.aim_level():
            self.aim_want = None
        elif not self.aim_busy():
            lv = self.aim_want
            try:
                self.aim_apply(lv)
                self.msg("^3Aim level now^7 ^2{}^7.".format(self.aim_level()))
            except Exception as e:                           # noqa: BLE001
                self.aim_want = None
                self.log("aim {}: {!r}".format(lv, e))

    # ------------------------------------------------------------------ frame
    def on_frame(self):
        t0_ = time.perf_counter() if TIMING else 0.0
        try:
            self.frame()
        except Exception as e:
            if time.time() > self.err_t:
                self.err_t = time.time() + 5
                self.log("frame error: {!r}".format(e))
                try:                                         # where it happened: the last lines of the trace, into the same log
                    import traceback
                    self.log("  " + " | ".join(l_.strip().replace("\n", " ") for l_ in traceback.format_exc().splitlines()[-7:-1]))
                except Exception:                            # noqa: BLE001
                    pass
        if TIMING:
            self.time_note(time.perf_counter() - t0_)

    def frame(self):
        now = time.time()
        if not self.ready:
            if now > self.next_check:
                self.next_check = now + 2
                mapname = (minqlx.get_cvar("mapname") or "").lower()
                if getattr(self, "vote_map_ok", False) and mapname in MAPS and mapname != "testlab":
                    self.want_map = mapname                  # the vote at the end of a person's game picked it: stay
                self.vote_map_ok = False                     # (a sparring server's games end with no person: it stays on its map)
                if mapname != self.want_map or (minqlx.get_cvar("g_factory") or "").lower() == "ffa":
                    self.next_check = now + 10               # another map, or this one in the free-for-all factory (a pool
                    _pu.load_map(self.want_map, "duel")      # of the other mode): the 1v1 plugin needs the duel factory
                    return
                self.setup()
            return
        if (minqlx.get_cvar("mapname") or "").lower() not in MAPS:       # the game rotated to another map
            if now > self.next_check:
                self.next_check = now + 10
                _pu.load_map(self.want_map, "duel")
            return
        if now > getattr(self, "powerup_check", 0.0):          # the game puts every item back when a real game starts
            self.powerup_check = now + 3.0
            self.no_powerups()
        if now > self.reload_check and self.room is None and not self.queue:
            self.reload_check = now + 5                      # a newer policy.npz is picked up without a restart
            try:
                if os.path.getmtime(os.path.join(D, "policy.npz")) != self.policy_mtime:
                    self.end_session()
                    self.setup()
                    self.msg("^3New BobbyBones loaded^7: {} at {} minutes of training.".format(
                        self.P["run"], int(self.P["minutes"])))
            except OSError:
                pass
        self.aim_frame(now)
        bobby, human, filler = self.cast()
        real_human = human is not None and not is_bot(human)
        if real_human:
            self.human_t = now
        elif now - getattr(self, "human_t", 0.0) > 3.0:      # the person gone for three seconds, not for one frame
            self.real_game = False
        if getattr(self, "go_f3", 0.0):                      # the person pressed F3 (on_client_command): the game has run his
            state_ = self.game.state if self.game is not None else None      # "readyup" by now, and "allready" readies Bobby
            if state_ in ("countdown", "in_progress"):
                self.go_f3 = 0.0                             # the countdown runs
            elif not getattr(self, "go_sent", 0.0) or self.go_sent < self.go_f3:
                self.go_sent = now
                minqlx.console_command("allready")
            elif now - self.go_f3 > 5.0:                     # the game would not start (its reason is on the console)
                self.go_f3, self.real_game = 0.0, False
                self.msg("^3The game did not start.^7 Press F3 again, or ^2!duel^7 for a timed duel.")
        if getattr(self, "vote_map_ok", False) and not self.after_game(now):
            self.vote_map_ok = False                         # no map came out of the vote: back to the usual rules
        # (not in the game's own end sequence: the scoreboard and the vote for the next map: see on_game_end)
        if real_human and not self.real_game and self.game is not None and self.game.state not in ("warmup", None) \
                and now - self.last_abort > 30 and not self.after_game(now):
            self.last_abort = now                            # with a human: stay in warmup (never abort in a tight loop)
            self.log("game state {} - back to warmup".format(self.game.state))
            minqlx.console_command("abort")
        if bobby is None:
            if now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("addbot bones 5 free 0 \"BobbyBones (BOT)\"")
            return
        give_autohop(bobby, now, self.log, want=autohop_want(getattr(self, "P", None)))
        if human is not None and filler is not None:
            if now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("clientkick {}".format(filler.id))
            return
        opp = human or filler
        if opp is None:
            if self.opp_bot and now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("addbot sarge {}".format(os.environ.get("DUEL_BOT_SKILL") or 5))   # 5 Nightmare, 4 Hardcore
            minqlx.set_bot_input(bobby.id, 0, 0, 0, 0, 0, 0.0, 0.0)
            if self.arena and self.sess and getattr(self, "sess_person", False):
                self.arena_end("left")                       # the person left in the middle of a timed duel: it ends here (it
                                                             # went on against whoever came next and ended on his first frame)
            if self.sess:
                self.end_session()
            self.room, self.queue = None, []
            return
        bs, os_ = bobby.state, opp.state
        if bs is None or os_ is None:
            return
        if self.sess is None or self.sess_opp != opp.id:
            self.start_session(opp)
        in_room = (self.room is not None or bool(self.queue)) and human is not None
        # deaths and respawns
        for p, st, who in ((bobby, bs, "bobby"), (opp, os_, "opp")):
            up = st.health > 0
            was = self.alive.get(p.id)
            if up and not was:
                if in_room and self.room is not None and self.room.get("started"):
                    self.room_loadout(bobby, opp, only=who)
                else:
                    if not ((self.arena and self.arena["where"] == "map") or (self.real_game and not self.lab)):
                        self.give_loadout(p)                 # not in a scored duel or an F3 game on a duel map: the game's own spawn stands there
                    if self.arena and self.lab:              # arena: come back inside the room, away from the other one
                        o_ = (opp if who == "bobby" else bobby).state
                        q = self.arena_spot(o_.position if o_ else (0, 0, 0))
                        face = math.degrees(math.atan2(o_.position[1] - q[1], o_.position[0] - q[0])) if o_ else 0.0
                        self.put(p, q, face, human=(who == "opp" and not is_bot(p)))
                self.tot.pop(who, None)
                self.new_life_of(self.env, 0 if who == "bobby" else 1)     # (v0.2: what the other knew him to have went with his old life)
                if was is None and hasattr(self.env, "_es_set") and getattr(self.E, "EN_STACK", False):
                    self.env._es_set(0 if who == "opp" else 1, 1 if who == "opp" else 0, spawn=True)   # (B-257) a newcomer: a fresh spawn
                self.ground_was = None                       # (a spawn is neither a jump nor a landing)
                if who == "opp" and getattr(self, "rules2", False):
                    self.env.dmg_life[0] = 0.0               # what Bobby knows about this opponent's damage resets
                    self.opp_ammo = None
                    if hasattr(self.env, "shot_t"):
                        self.env.shot_t[0] = self.env.trail_t[0] = 99.0
                self.want_w.clear()
                self.prev_opp = None                         # (a respawn is not a teleport: no such sound)
                if who == "bobby" and hasattr(self.env, "life_t"):      # a new life: time since the spawn, flinch, focus
                    self.env.life_t[0], self.env.flinch[0], self.env.focus[0] = 0.0, 0.0, self.E.FOCUS_SECS
                    st_ = self.fresh_life(self.env, self.E, 0)
                    if st_:
                        self.record(event="style", style=st_)
                if who == "bobby":
                    if not getattr(self, "rules2", False):
                        self.head_clear()                    # older runs: memory per life. Newer: kept for the session
                    for env in (self.env, self.renv):
                        env.mv[:] = 0
                        if hasattr(env, "hb"):
                            env.hb[:] = 0                    # (HAND_BAND) the view's velocity too
                        env.cool[:] = 0
                        env.seen_t[:] = 9.0
                        env.opp_hist = []
                        if hasattr(env, "drift_clear"):
                            env.drift_clear()                # (DRIFT_IN) no rate from the life before
                        if hasattr(env, "proj_clear"):
                            env.proj_clear()                 # (PROJ_FIX) nothing followed from the life before
                    minqlx.set_bot_substeps(bobby.id, 3)
            if was and not up:
                other = "opp" if who == "bobby" else "bobby"
                self.score[other] += 1
                k_ = "hd_died" if who == "bobby" else "hd_frag"         # (v0.4) for the head's events (head_note)
                self.__dict__[k_] = self.__dict__.get(k_, 0) + 1
                if hasattr(self.env, "note_death"):          # who knows of this death, and what he then forgets
                    self.env.note_death(0 if who == "bobby" else 1, 1 if who == "bobby" else 0)
                if self.room is not None and self.room.get("started"):
                    self.room["m"]["frags" if who == "bobby" else "deaths"] += 1
                self.record(event="death", who=who, drill=self.drill, room=self.room["name"] if self.room else None,
                            state=self.last, **self.score)
            self.alive[p.id] = up
        if in_room:
            return self.room_frame(now, bobby, opp, bs, os_)
        if self.arena and not self.lab and self.arena["where"] != "map":
            self.arena = None
        if self.arena is None and self.lab and os.environ.get("DUEL_ARENA") in ("box", "env", "yard") and is_bot(opp) \
                and not getattr(self, "arena_auto_done", False):
            self.arena_auto_done = True                      # benchmark servers: one arena fight against the game's bot
            self.arena_start(os.environ["DUEL_ARENA"], float(os.environ.get("DUEL_ARENA_MIN") or 5))
        if self.arena is None and not self.lab and os.environ.get("DUEL_ARENA") and is_bot(opp) \
                and not getattr(self, "arena_auto_done", False):
            self.arena_auto_done = True                      # the same on a duel map: the whole map as it is, the game's spawn
            mins = float(os.environ.get("DUEL_ARENA_MIN") or 5)
            self.arena = dict(where="map", t_end=now + mins * 60, mins=mins, base=dict(self.score), place=False, dmg=[0, 0])
            self.record(event="arena_start", where="map", minutes=mins)    # (the first life still has the handed-out weapons)
        if self.arena and self.arena["where"] == "map":       # a timed, scored duel on a map as it is
            if "key" not in self.arena:                      # who it is against, by the leaderboard's key (arena_end)
                lad_ = minqlx.Plugin._loaded_plugins.get("ladder")
                ok_ = lad_ is not None and hasattr(lad_, "person_key") and not is_bot(opp)
                self.arena["key"] = lad_.person_key(opp) if ok_ else None
                self.arena["owner"] = int(bool(lad_.is_owner(opp))) if ok_ else 0
            if now >= self.arena["t_end"]:
                self.arena_end("time")
        elif self.arena:
            A = self.arena
            for p_, st_, other_, who_ in ((bobby, bs, os_, "bobby"), (opp, os_, bs, "opp")):
                if st_.health > 0 and (A["place"] or not self.arena_inside(st_.position)):
                    q = self.arena_spot(other_.position)
                    self.put(p_, q, math.degrees(math.atan2(other_.position[1] - q[1], other_.position[0] - q[0])),
                             human=(who_ == "opp" and not is_bot(p_)))
                    if A["place"]:
                        self.give_loadout(p_)
            A["place"] = False
            for p_, st_ in ((bobby, bs), (opp, os_)):        # a match start hands out the default weapons again: re-arm
                if st_.health > 0 and not st_.weapons.rl and not self.lab.get("yard", {}).get("items"):
                    self.give_loadout(p_)
            if now >= A["t_end"]:
                self.arena_end("time")
        env, E = self.env, self.E
        if self.game_new:                                    # a real game has begun (the countdown is over, everybody spawns anew):
            self.game_new = False                            # with a simulator of v0.2 his round begins with it, as a round does
            if hasattr(env, "_v02_round"):                   # in training: clock, score and memory start over and nothing is
                self.sess_t0 = now                           # believed. (Ten minutes are five of his rounds: the share of the
                self.round_base = (self.score["bobby"], self.score["opp"])     # round left runs out with the game.)
                self.head_clear()
                self.new_game_in(env)
                self.log("a game began: his round starts with it")
        if bs.health <= 0:                                   # tap fire to respawn
            minqlx.set_bot_input(bobby.id, 0, 0, 0, int(now * 4) % 2, 0, 0.0, 0.0)
            self.fill_player(env, E, 0, bobby, bs)
            self.fill_player(env, E, 1, opp, os_)
            env.visible[:] = False
            self.shot_made = {}
            self.v02_tick(env, E)                            # (v0.2: the new inputs' clocks go on while he is dead)
            self.log_frame(now, env, 0, bobby, opp, bs, os_, [0, 0, 0, 0], self.drill)
            self.head_note(env)                              # (v0.4: the head's books count the frames he is dead too, as step())
            return
        if self.drill and not hasattr(E, "NW") and now > self.top_up:    # older simulator: drills had endless ammo
            self.top_up = now + 2
            for p in (bobby, opp):
                p.ammo(**{self.drill: 150 if self.drill == "lg" else 25})
        pos, vel, ground, pitch, yaw = self.fill_player(env, E, 0, bobby, bs)
        opos = self.fill_player(env, E, 1, opp, os_)[0]
        if hasattr(env, "hear"):                             # what he hears of the opponent: running steps and shots
            st_ = env.state
            gr_ = st_[:, 6] > 0.5
            noisy = gr_ & (np.hypot(st_[:, 3], st_[:, 4]) > 200.0)
            ofire_ = bool(minqlx.ran_usercmd(opp.id)[1] & 1) and int(os_.weapon) != QLNUM["g"]
            lgd_ = getattr(E, "LG_DEAF", False)
            if lgd_:                                         # (LG_DEAF) the trigger held on the LG (the game's weapon in hand, the command
                env.lgd_fire[0] = bool(minqlx.ran_usercmd(bobby.id)[1] & 1) and int(bs.weapon) == QLNUM["lg"]    # that ran), before
                env.lgd_fire[1] = ofire_ and int(os_.weapon) == QLNUM["lg"]                                    # anything is heard
            if hasattr(env, "note_noise"):
                # (v0.2) The noise of this frame as the simulator's step() has it, for both players in one call each:
                # a shot with anything but the gauntlet, a jump or a landing, a frame of running steps (not crouched).
                # hear() is given all three, as there (jumps and landings were missing here), and note_noise() the same
                # for the one who makes them: how loud he has been, and that he made a noise near a believed enemy.
                was_ = self.ground_was
                hop_ = (gr_ != was_) if was_ is not None else np.zeros(len(gr_), bool)
                self.ground_was = gr_.copy()
                steps_ = noisy & ~env.duck
                shot_ = np.array([bool(self.shot_made.get((id(env), 0), False)), ofire_], bool)
                heard_ = shot_ | hop_ | steps_
                foot_ = None
                if getattr(E, "HEAR_FIX", False):            # (HEAR_FIX) footsteps as events, as step() makes them
                    foot_ = env._hf_steps(gr_, gr_ if was_ is None else was_, st_[:, 3:6], env.duck, env.hp > 0)
                    heard_ = shot_ | hop_ | foot_
                heard_[0] = False
                if lgd_ and foot_ is not None:               # (LG_DEAF) the footsteps alone, for the muffling (as step())
                    env.hear(heard_, foot=foot_ & ~(shot_ | hop_))
                else:
                    env.hear(heard_)
                env.note_noise(shot_, hop_, steps_)
            else:
                noisy[1] |= ofire_
                noisy[0] = False
                env.hear(noisy)
        took_ = self.sync_world(env, E, (bobby.id, opp.id))
        for (cls, slot), k_ in zip(took_, self.took_k):
            self.record(event="pickup", item=cls, by=("bobby", "opp")[slot] if slot >= 0 else "?")
            if hasattr(env, "note_take") and slot in (0, 1) and k_ >= 0:
                env.note_take(slot, k_)                      # (v0.2) when he last took it; a big one the other heard or saw taken
            if hasattr(env, "note_pickup") and slot in (0, 1) and cls in ("item_health_mega", "item_armor_body"):
                env.note_pickup(slot, 0 if cls == "item_health_mega" else 1)     # he took it, or heard it taken
            if slot == 0:
                self.took_chosen(env, E, 0, cls)
            if getattr(self, "rules2", False) and slot == 1:
                big = 0 if cls == "item_health_mega" else 1 if cls == "item_armor_body" else \
                    2 if cls in ("item_armor_combat", "item_armor_jacket") else 3 if cls.startswith("weapon_") else None
                if big is not None:
                    env._hear(0, np.array([1]), big)
        taken_items = []
        if self.rules2:
            env.kind[0] = E.NORMAL
            if getattr(self, "game_seat", False):                    # a whole-games network: the game's clock, score and memory
                self.clock_frame(now, env, [(0, bobby), (1, opp)])
            else:
                if now - self.sess_t0 > self.round_secs:                  # the round as in training (see setup)
                    self.sess_t0 = now                                   # clock, score and memory start over
                    self.round_base = (self.score["bobby"], self.score["opp"])
                    self.head_clear()
                env.round_t[0] = now - self.sess_t0
                if hasattr(env, "v02_left"):                             # (v0.2) the share of his round left, by the same clock
                    env.v02_left = min(1.0, max(0.0, 1.0 - (now - self.sess_t0) / max(1.0, self.round_secs)))
                env.frags_r[:] = (self.score["bobby"] - self.round_base[0], self.score["opp"] - self.round_base[1])
            oc_ = minqlx.ran_usercmd(opp.id)
            env.duck[1] = oc_[5] < 0
            env.snd_t += E.DT
            if hasattr(env, "resp_t"):
                env.resp_t += E.DT
            self.intent_release(env, E, [0])
            if hasattr(env, "note_shots"):                           # enemy shots seen or heard, and their trails
                env.shot_t += E.DT
                env.trail_t += E.DT
                am_ = {w_: getattr(os_.ammo, w_) for w_ in E.WEAPONS if w_ != "g"}
                wn_ = E.WEAPONS[int(env.weapon[1])] if int(env.weapon[1]) < len(E.WEAPONS) else "mg"
                pa_ = getattr(self, "opp_ammo", None)
                if pa_ is not None and os_.health > 0 and wn_ in am_ and am_[wn_] < pa_.get(wn_, am_[wn_]):
                    env.note_shots(np.array([1]))                    # the weapon in his hand lost ammo: he fired
                self.opp_ammo = am_
            po = self.prev_opp
            if po is not None and os_.health > 0:
                if oc_[1] & 1:                                       # the opponent is firing
                    env._hear(1, np.array([1]))
                if po[1] > 0.5 and env.state[1, 6] < 0.5 and env.state[1, 5] > 100:
                    env._hear(2, np.array([1]))                      # jumped
                if np.linalg.norm(env.state[1, :3] - po[0]) > 200:
                    env._hear(3, np.array([1]))                      # teleported
            self.prev_opp = (env.state[1, :3].copy(), float(env.state[1, 6]))
            env.fb[0] = self.fb_next
        self.senses(env, E)
        if hasattr(E, "NW"):
            env.weapon[0] = self.held(env, 0)                # the chosen weapon, as the simulator shows it
        t_ = time.perf_counter()
        ob = env.observe()[:1]                               # (once a frame: the new inputs' clocks are kept in it)
        self.t_obs = time.perf_counter() - t_
        if os.environ.get("DUEL_OBSDUMP"):                   # debugging: keep the inputs to compare with the simulator's
            self.obs_dump = getattr(self, "obs_dump", [])
            self.obs_dump.append(ob[0].copy())
            if len(self.obs_dump) % 2000 == 0:
                np.save("/tmp/practice/obs_dump.npy", np.array(self.obs_dump[-12000:]))
        t_ = time.perf_counter()
        h_in_ = self.h[0].copy() if self.sess else None      # (the memory the network answers from, for the input log)
        a = self.act(ob)
        self.t_net, self.t_live = time.perf_counter() - t_, 1
        if h_in_ is not None:
            self.inputs_log(now, ob[0], h_in_, a)
        if len(a) > 10 and hasattr(env, "intend"):           # the intention head (v8), as in training
            env.intend(np.full(env.n, int(a[10]), np.int64), np.arange(env.n) == 0)
        yaw_in_, pitch_in_ = float(yaw), float(pitch)
        w, fire, pitch, yaw, keys = self.drive(bobby, env, E, 0, a, pitch, yaw, only=self.drill)
        if os.environ.get("DUEL_AIMDUMP"):                   # debugging: what became of the mouse output, frame by frame
            self.aim_dump = getattr(self, "aim_dump", [])
            ru_ = minqlx.ran_usercmd(bobby.id)
            self.aim_dump.append([now, float(a[3]), float(a[4]), float(a[9]) if len(a) > 9 else -1.0, float(env.mv[0, 0]), float(env.mv[0, 1]),
                                  float(env.pad[0]) if hasattr(env, "pad") else 0.0, float(env.pad_lift[0]) if hasattr(env, "pad_lift") else 0.0,
                                  float(env.zoom[0]) if hasattr(env, "zoom") else 0.0, float(env.script[0]), float(getattr(env, "human_aim", False)),
                                  yaw_in_, float(yaw), pitch_in_, float(pitch), float(ru_[0]), float(ru_[7]), float(ru_[6]), float(bs.health),
                                  float(self.h.std()) if hasattr(self, "h") else 0.0, float(env.seen_t[0]), float(env.intent[0]) if hasattr(env, "intent") else -1.0,
                                  # (columns 22 to 30, for the weapon change on an empty weapon: the trigger and the weapon key the network
                                  # asked for and as his hand left them, the weapon the plugin holds, the game's, his reload clock, the
                                  # ammunition of the plugin's weapon, his style)
                                  float(a[5]), float(a[6]), float(self.row_used[5]), float(self.row_used[6]), float(w), float(bs.weapon),
                                  float(env.cool[0]), float(env.ammo[0, w]) if w < env.ammo.shape[1] else -1.0,
                                  float(env.style[0]) if hasattr(env, "style") else -1.0])
            if len(self.aim_dump) % 1000 == 0:
                np.save("/tmp/practice/aim_dump.npy", np.array(self.aim_dump[-12000:]))
        wname = E.WEAPONS[w]
        self.last = dict(bobby=[round(float(v)) for v in pos], opp=[round(float(v)) for v in opos],
                         bobby_hp=[bs.health, bs.armor], opp_hp=[os_.health, os_.armor], weapon=wname,
                         visible=bool(env.visible[0]), seen_ago=round(float(env.seen_t[0]), 1),
                         intent=E.INTENTS[int(env.intent[0])] if hasattr(E, "INTENTS") else "")
        dmg, _ = self.log_frame(now, env, 0, bobby, opp, bs, os_, keys, self.drill)
        if self.rules2:                                      # hit feedback for the next frame, and damage dealt this life
            dealt, took = dmg.get("opp", 0), dmg.get("bobby", 0)
            ang = math.atan2(opos[1] - pos[1], opos[0] - pos[0]) - math.radians(yaw)
            self.fb_next = np.array([min(dealt / 100.0, 2.0), min(took / 100.0, 2.0),
                                     math.sin(ang) * (took > 0), math.cos(ang) * (took > 0)], np.float32)
            env.dmg_life[0] += dealt
            es_ = getattr(E, "EN_STACK", False) and hasattr(env, "note_dealt")
            if es_:                                          # (B-257) his own hits on the living opponent, by the game's count of
                dn_ = int(bobby.stats.damage_dealt)          # the damage he dealt (never the opponent's own splash or falls)
                hit_ = max(0, dn_ - self.__dict__.get("es_dealt0", dn_))
                self.es_dealt0 = dn_
                if hit_ > 0 and os_.health > 0:
                    env.note_dealt(0, 1, hit_)
            if took > 0 and hasattr(env, "note_hit") and getattr(env, "flinch_on", False):
                env.note_hit(0, took)                        # being shot at throws his aim off for a moment
            if hasattr(env, "pain_t"):                       # the opponent's pain sound, by his health after the hit
                env.pain_t += E.DT                           # (EN_STACK: after any hurt the game plays it for, his own splash and falls too, as step())
                near_ = float(np.linalg.norm(np.asarray(opos) - np.asarray(pos))) < \
                    (float(env._evt_reach(0)) if getattr(E, "LG_DEAF", False) else E.HEAR_EVT)     # (LG_DEAF: firing the LG, 1,000 at most)
                if (dealt > 0 or (es_ and dmg.get("opp", 0) > 0)) and os_.health > 0 and near_:
                    env.pain_t[0], env.pain_b[0] = 0.0, min(3, int(os_.health) // 25)
        if getattr(E, "HEAD_EVENTS", False):                 # (v0.4) the frame in the head's books: what he dealt by the game's count of his
            dd_ = int(bobby.stats.damage_dealt)              # damage (never the opponent's own splash or falls), what he took from anything
            hdl_ = max(0, dd_ - self.__dict__.get("hd_dealt0", dd_))
            self.hd_dealt0 = dd_
            self.head_note(env, float(hdl_), float(dmg.get("bobby", 0)))
        if self.arena:
            self.arena["dmg"][0] += dmg.get("opp", 0)
            self.arena["dmg"][1] += dmg.get("bobby", 0)
        c = self.acc
        c["frames"] += 1
        c["visible"] += int(env.visible[0])
        c["fire"] += int(fire)
        c["w"][wname] = c["w"].get(wname, 0) + 1
        c["fast_air"] += int(math.hypot(vel[0], vel[1]) > 330 and not ground)
        if now > self.next_summary:
            self.next_summary = now + 60
            f = max(1, c["frames"])
            self.record(event="minute", visible=round(c["visible"] / f, 3), fire=round(c["fire"] / f, 3),
                        fast_air=round(c["fast_air"] / f, 3), weapon_share={k: round(v / f, 2) for k, v in c["w"].items()},
                        dmg_dealt=bobby.stats.damage_dealt, dmg_taken=bobby.stats.damage_taken, **self.score)
            self.acc = dict(frames=0, visible=0, fire=0, fast_air=0, w={})

    # ------------------------------------------------------------------ test rooms (human = subject, slot 0)
    def room_hint(self, r):
        """one line that tells the player what to do and with which weapons"""
        k = r["kind"]
        if k == "aim" and r.get("reflex"):
            return {"slow": "Lightning gun. The target walks slowly from side to side: hold your crosshair on it and keep firing.",
                    "track": "Lightning gun. The target strafes and turns round without warning: stay on it.",
                    "flick": "Railgun. The target jumps to a new place every few seconds: hit it as fast as you can.",
                    "rocket": "Rockets. The target strafes and turns round without warning: hit it."}[r["reflex"]] + \
                " Move as you normally would when you aim." + \
                (" After 20 seconds the target shoots back (you cannot die): keep aiming." if r.get("under_fire") else "")
        if k == "aim":
            return "{} only, endless ammo. Hit the target as much as you can.".format(r["weapon"].upper())
        if k == "choice":
            return "All weapons. Use whatever you think is right at this distance."
        if k == "speed":
            c_ = self.lab["courses"][r["key"]]
            return ("Rocket launcher. " if c_.get("weapon") == "rl" else "Gauntlet only. ") + c_.get("hint", c_["name"])
        if k == "move":
            return "Gauntlet only. Run to the item named on screen."
        if k == "solo" and r.get("where") == "items":
            return "Gauntlet only. Mega health (35 s) and red armor (25 s) in opposite corners: be there each time one comes back."
        if k == "solo":
            return "All weapons. Collect what you would in a real game."
        if k == "ladder":
            style = {"allround": "rockets close, LG mid, rail far", "sniper": "rail, keeps its distance",
                     "rusher": "rockets, always closing in", "tracker": "LG at mid range",
                     "dodger": "dodges, backs off when hurt", "stander": "stands still",
                     "jumper": "runs at you, always jumping", "spammer": "fires blind"}.get(r["name"].split("/")[-1], "")
            if r.get("where") == "peek":
                return "Railgun only. He stands in the open and shoots back: deal damage through the gaps, take as little as you can."
            if r.get("ai"):
                return "All weapons, your choice. Play to win. Opponent: the game's Nightmare bot."
            return "All weapons, your choice. Play to win. Opponent: {} ({}).".format(r["name"].split("/")[-1], style)
        return ""

    @staticmethod
    def gauntlet_only(p):
        """take every gun away. The weapon in hand and its ammo must go too: the game fires whatever is held."""
        p.weapons(reset=True, g=True)
        p.ammo(**{w: 0 for w in QLNUM if w != "g"})
        p.weapon(QLNUM["g"])

    def room_loadout(self, bobby, human, only=None):
        r, R = self.room, self.R
        if only in (None, "opp"):
            if r["kind"] == "aim":
                self.give_loadout(human, R, only=r["weapon"])
            elif r["kind"] == "speed" and self.lab and self.lab["courses"][r["key"]].get("weapon") == "rl":
                human.weapons(reset=True, g=True, rl=True)   # rocket-jump course
                human.ammo(rl=25)
                human.weapon(QLNUM["rl"])
            elif r["kind"] in ("move", "terrain", "speed") or r.get("where") == "items":
                self.gauntlet_only(human)
            elif r.get("where") == "peek":
                self.give_loadout(human, R, only="rg")
            else:
                self.give_loadout(human, R, only="")
            r["ammo"] = None
        if only in (None, "bobby"):
            if r.get("where") == "peek":
                self.give_loadout(bobby, R, only="rg", boost=3)
            elif r["kind"] == "speed" and self.lab and "turret" in self.lab["courses"][r["key"]]:
                bobby.weapons(reset=True, g=True, rl=True)   # the rocket turret of the dodge room
                bobby.ammo(rl=50)
                bobby.weapon(QLNUM["rl"])
            elif r["kind"] == "ladder":
                self.give_loadout(bobby, R, only="", boost=3)
            else:
                bobby.weapons(reset=True, g=True)

    def place_pair(self, bobby, human):
        """target at a map spawn point, the subject 'band' units away with a clear line, facing it within 60 degrees"""
        env, r = self.renv, self.room
        eye = np.array([0, 0, self.R.VIEW_H], np.float32)
        if env.spots is None:
            return False
        for _ in range(30):
            k = int(self.rng.integers(len(env.spawns)))
            t = env.spawns[k] + np.array([0, 0, 9.0], np.float32)
            d = np.linalg.norm(env.spots - t, axis=1)
            cand = np.nonzero((d > r["band"][0]) & (d < r["band"][1]))[0]
            for j in self.rng.permutation(cand)[:24]:
                q = env.spots[j]
                if env.w.trace(q + eye, t + np.array([0, 0, 8.0], np.float32))["fraction"] >= 0.999:
                    face = math.degrees(math.atan2(t[1] - q[1], t[0] - q[0])) + float(self.rng.uniform(-60, 60))
                    bobby.position(x=float(t[0]), y=float(t[1]), z=float(t[2]))
                    bobby.velocity(reset=True)
                    human.position(x=float(q[0]), y=float(q[1]), z=float(q[2]) + 2.0)
                    human.velocity(reset=True)
                    minqlx.set_view(human.id, 0.0, face)
                    minqlx.set_bot_input(bobby.id, 0, 0, 0, 0, 0, 0.0, float(self.rng.uniform(-180, 180)))
                    env.mv[:] = 0
                    if hasattr(env, "hb"):
                        env.hb[:] = 0                        # (HAND_BAND) the view's velocity too
                    return True
        return False

    def env_module(self, name):
        """the simulator module a policy was trained in, with the switches it was trained with (policy.npz env_vars:
        INTENT_HOLD, ITEM_BELIEF, ...). None of them reached a server until 2026-10-08. They are read when the module is
        loaded, so they are set first; a module loaded before with other values is loaded again."""
        ev_ = json.loads(str(self.P["env_vars"])) if "env_vars" in self.P else {}
        for k_ in set(getattr(duelbot, "_env_set", ())) - set(ev_):     # a switch of the network served before that this one
            os.environ.pop(k_, None)                                    # does not name goes back to the simulator's own value
        duelbot._env_set = set(ev_)
        os.environ.update({k_: str(v_) for k_, v_ in ev_.items()})
        E = importlib.import_module(name)
        if hasattr(E, "_plugin_env") and E._plugin_env != ev_:
            E = importlib.reload(E)
        E._plugin_env = ev_
        return E

    def fresh_life(self, env, E, k, style=True):
        """what the simulator resets at a spawn (_fresh, _spawn) and the plugins did not: his intention (read anew at
        once), his hands and mouse pad, and his playing style for this life (one of the map's, at random)"""
        if hasattr(env, "intent_new"):
            env.intent[k], env.intent_t[k], env.intent_new[k], env.intent_done[k] = 0, 0.0, True, False
        if hasattr(env, "key_tok"):
            env.key_last[k], env.key_hold[k], env.key_tok[k] = (1, 1, 0), 99, E.KEY_BURST
            env.key_req[k] = (1, 1, 0, 0)
        for name, v in (("zoom", False), ("fire_last", False), ("mouse_hold", 99), ("pad", 0.0), ("pad_lift", 0), ("walk_last", False),
                        ("resp_t", 99.0)):
            if hasattr(env, name):
                getattr(env, name)[k] = v
        getattr(self, "press_q", {}).pop((id(env), k), None)
        no_styles = str(getattr(E, "_plugin_env", {}).get("STYLE_P", "")) in ("0", "0.0")   # (v0.3 on) trained with no styles
        if style and not no_styles and hasattr(E, "STYLES") and hasattr(env, "style"):
            ok_ = [j for j, w_ in enumerate(E.STYLE_W) if w_ < 0 or int(w_) in env.map_weapons]
            env.style[k] = int(ok_[np.random.randint(len(ok_))])
            return E.STYLES[int(env.style[k])]
        return None

    def intent_release(self, env, E, seats):
        """what step() does for the intention besides reading it: the chosen item is gone and will not be back before he
        can be there (the hold ends), as in the simulator"""
        R_ = getattr(env, "route", None)
        if R_ is None or not hasattr(env, "intent_gone"):
            return
        s = env.state
        node = R_.locate(s[:, :3])
        gi_ = env._trip_goal(env.intent, node) if hasattr(env, "_trip_goal") else np.array(env.intent_gi)[env.intent]
        valid = gi_ >= 0
        g_ = np.maximum(gi_, 0)
        phi = np.where(valid, R_.T[g_, node] + np.linalg.norm(R_.nodes[node] - s[:, :3], axis=1) / 320.0, 0.0)
        it_ = np.array(env.route_item)[np.minimum(g_, len(env.route_item) - 1)]     # (a holding place's row is no item's: "soon" below)
        soon = env.item_up[0, it_] | (env.item_t[0, it_] < phi + 5.0) | (env.intent >= getattr(E, "EN_INTENT", 1 << 30))
        gone = valid & ~soon & (env.intent > 0)
        if getattr(env, "hold_n", 0):                        # (TARGETS, as step() does: a place is reached where he stands at it,
            hd_ = env.intent >= E.HOLD_INTENT                # given up where no way leads to it; 2026-10-14, the first real games)
            env.note_holds()
            gone = gone | (hd_ & (~valid | (R_.T[g_, node] >= 1e8)))
        mine_ = np.isin(np.arange(env.n), seats)
        if getattr(E, "EN_ON", False):                       # (HUNT, B-256; FIGHT_TARGET) the enemy as his target, as step() does:
            en_ = env.intent == E.EN_INTENT                  # reached when he is in view, given up when nothing is believed of him
            env.intent_done = env.intent_done | (en_ & np.asarray(env.visible, bool)[:len(en_)] & mine_)
            gone = gone | (en_ & ~valid)
        env.intent_gone = np.where(mine_, gone, False)

    def took_chosen(self, env, E, k, cls):
        """player k took an item: was it the one he was going for (then the choice is done, as in the simulator)"""
        d = getattr(E, "ITEM_DEFS", {}).get(cls)
        if d is None or not hasattr(env, "intent_done"):
            return
        lab = d[4] if d[4] else (E.WEAPONS[int(d[1])].upper() if d[0] == "wp" else None)
        want = E.INTENTS[int(env.intent[k])]
        if lab is not None and (lab == want or (lab == "YA" and want == "YA2")):
            env.intent_done[k] = True

    def put(self, p, pos, yaw=None, human=False):
        p.position(x=float(pos[0]), y=float(pos[1]), z=float(pos[2]) + 2.0)
        p.velocity(reset=True)
        if yaw is not None:
            minqlx.set_view(p.id, 0.0, float(yaw))           # turn the view (Bobby too: his command of this frame starts from it)

    def lab_place(self, bobby, human):
        """fixed placement on the lab map: aim box (about 700 units apart) or the environment box"""
        r, L = self.room, self.lab
        if r.get("where") == "aim":
            a = L["aim"]
            self.put(human, a["subject"], a["yaw"], human=True)
            lg = (r.get("weapon") == "lg" or r.get("near")) and "zone_lg" in a   # lightning range; reflex rockets too
            tg_ = a["target_lg"] if lg else a["target"]
            self.put(bobby, tg_, float(self.rng.uniform(-180, 180)) if not r.get("reflex") else   # reflex: facing the subject,
                     math.degrees(math.atan2(a["subject"][1] - tg_[1], a["subject"][0] - tg_[0])))     # so its strafe is sideways to him
            r["home"], r["zone"], r["hard"] = (a["target_lg"] if lg else a["target"]), \
                (a["zone_lg"] if lg else a["zone"]), [-64, -64, 1600, 1088]
        else:
            e = L["env"]
            spots = [np.array([q[0], q[1], q[2] if len(q) > 2 else e["z"]], np.float32) for q in e["spots"]]
            i = int(self.rng.integers(len(spots)))
            d = [float(np.linalg.norm(q - spots[i])) for q in spots]
            cand = [k for k, v in enumerate(d) if 400 <= v <= 1300] or [int(np.argmax(d))]
            j = int(self.rng.choice(cand))
            face = math.degrees(math.atan2(spots[i][1] - spots[j][1], spots[i][0] - spots[j][0]))
            self.put(bobby, spots[i], float(self.rng.uniform(-180, 180)))
            self.put(human, spots[j], face, human=True)
            b = e["bounds"]
            r["home"], r["zone"] = [float(v) for v in spots[i]], [b[0] + 48, b[1] + 48, b[2] - 48, b[3] - 48]
            r["hard"] = [b[0] - 64, b[1] - 64, b[2] + 64, b[3] + 64]
        self.renv.mv[:] = 0
        if hasattr(self.renv, "hb"):
            self.renv.hb[:] = 0

    def lab_keep(self, p, pos, human=False):
        """fights: a player who respawned elsewhere on the lab map is moved back into the environment box"""
        e = self.lab["env"]
        b = e["bounds"]
        if not (b[0] <= pos[0] <= b[2] and b[1] <= pos[1] <= b[3]):
            q = e["spots"][int(self.rng.integers(len(e["spots"])))]
            self.put(p, (q[0], q[1], q[2] if len(q) > 2 else e["z"]), 0.0, human=human)

    def lab_terrain(self, now, human, hpos, hvel, hground):
        """trick-jump stations and the speed straight: put the subject at the start, time each attempt"""
        r, m = self.room, self.room["m"]
        sp = math.hypot(hvel[0], hvel[1])
        if r["kind"] == "speed":
            st = self.lab["courses"][r.get("key", "speed")]
            path = st["path"]
            if r.get("leg") is None:
                self.put(human, st["start"], st["yaw"], human=True)
                r["leg"], r["t_run"], r["seg"], r["prog"] = 0, None, 0, 0.0
                return
            r["top"] = max(r.get("top", 0.0), sp)
            if st.get("weapon") == "rl" and getattr(human.state.ammo, "rl") < 10:
                human.ammo(rl=25)
            # progress = distance along the path at the nearest point, searched near the current segment only
            best = None
            for k in range(max(0, r["seg"] - 1), min(len(path) - 1, r["seg"] + 2)):
                ax, ay = path[k]
                bx, by = path[k + 1]
                L = math.hypot(bx - ax, by - ay) or 1.0
                t_ = max(0.0, min(1.0, ((hpos[0] - ax) * (bx - ax) + (hpos[1] - ay) * (by - ay)) / (L * L)))
                d = math.hypot(hpos[0] - (ax + (bx - ax) * t_), hpos[1] - (ay + (by - ay) * t_))
                if best is None or d < best[0]:
                    best = (d, k, t_ * L)
            r["seg"] = best[1]
            done_len = sum(math.hypot(path[k + 1][0] - path[k][0], path[k + 1][1] - path[k][1]) for k in range(best[1]))
            r["prog"] = max(r["prog"], done_len + best[2])
            m["dist"] = r["prog"]
            m["height"] = max(m.get("height", 0.0), float(hpos[2] - st["start"][2]))
            if r["t_run"] is None and sp > 50:
                r["t_run"] = now
            ex, ey_ = path[-1]
            at_end = math.hypot(hpos[0] - ex, hpos[1] - ey_) < st.get("end_r", 120) and \
                (st.get("end_z") is None or hpos[2] >= st["end_z"])
            if hpos[2] < st["fall_z"]:                      # fell: back to the last checkpoint reached
                cp, cl = st["checkpoints"][0], -1.0
                for c in st["checkpoints"]:
                    # how far along the path this checkpoint is (nearest path point)
                    acc, bestc = 0.0, None
                    for k in range(len(path) - 1):
                        ax, ay = path[k]
                        bx, by = path[k + 1]
                        L = math.hypot(bx - ax, by - ay) or 1.0
                        t_ = max(0.0, min(1.0, ((c[0] - ax) * (bx - ax) + (c[1] - ay) * (by - ay)) / (L * L)))
                        d = math.hypot(c[0] - (ax + (bx - ax) * t_), c[1] - (ay + (by - ay) * t_))
                        if bestc is None or d < bestc[0]:
                            bestc = (d, acc + t_ * L)
                        acc += L
                    if bestc[1] <= r["prog"] + 32 and bestc[1] > cl:
                        cp, cl = c, bestc[1]
                self.put(human, cp[:3], cp[3] if len(cp) > 3 else st["yaw"], human=True)
                m["falls"] = m.get("falls", 0) + 1
            elif at_end:                                    # reached the end: the room is over
                t = now - (r["t_run"] or now)
                m["best"] = t
                human.tell("^2{:.2f} s^7 for {} units, top speed {:.0f}".format(t, int(st["length"]), r.get("top", 0.0)))
                r["t_end"] = now
            return
        st = self.lab["stations"][r["key"]]
        via = st.get("via") or [st["goal"]]
        if r.get("leg") is None or r.get("reset"):
            self.put(human, st["start"], st["yaw"], human=True)
            r["leg"], r["t_run"], r["reset"] = 0, None, False
            return
        if r["t_run"] is None:
            if math.hypot(hpos[0] - st["start"][0], hpos[1] - st["start"][1]) > 48:
                r["t_run"] = now
                m["attempts"] = m.get("attempts", 0) + 1
            return
        g = via[r["leg"]]
        gz = g[2] if len(g) > 2 else st["goal"][2]
        if hground and math.hypot(hpos[0] - g[0], hpos[1] - g[1]) < st["goal_r"] and abs(hpos[2] - gz) < st["goal_dz"] + 24:
            r["leg"] += 1
            if r["leg"] >= len(via):
                t = now - r["t_run"]
                m["successes"] = m.get("successes", 0) + 1
                m["best"] = min(m.get("best", 1e9), t)
                m["speed_at_goal"] = max(m.get("speed_at_goal", 0.0), sp)
                human.tell("^2made it^7 in {:.2f} s".format(t))
                r["reset"] = True
        elif hpos[2] < min(st["start"][2], st["goal"][2]) - 150 or now - r["t_run"] > 15:
            r["reset"] = True

    def new_goal(self, human, pos):
        env, r = self.renv, self.room
        f = env.field
        node, _ = f.locate(pos[None])
        T = f.T[:, node[0]]
        ok = np.nonzero((T > 1.5) & (T < 12.0))[0]
        if not len(ok):
            ok = np.nonzero(T < 1e8)[0]
        if not len(ok):
            r["goal"] = None
            return
        g = int(self.rng.choice(ok))
        r["goal"] = g
        human.center_print("Go to: ^3{}".format(GOAL_NAMES[self.goal_labels[g]]))
        human.tell("Go to: ^3{}".format(GOAL_NAMES[self.goal_labels[g]]))

    def room_frame(self, now, bobby, human, bs, hs):
        R, env = self.R, self.renv
        if self.room is None:                                # next room from the queue, after a short countdown
            r = self.room = self.queue.pop(0)
            r.update(t0=now + 5, started=False, rep_end=0.0, ammo=None, goal=None, prev_w=None, said=0,
                     m=dict(frames=0, shots=0, dmg=0, hit_events=0, aim_err=0.0, aim_frames=0, on_target=0, held={},
                            switches=0, fire=0, blind=0, arrive=0, speed=0.0, fast=0, frags=0, deaths=0, dmg_taken=0,
                            picks={}))
            self.msg("^3Next: {}^7 ({} s). Starts in 5 s; the countdown is not scored.".format(r["name"], r["secs"]))
            self.msg("^5" + self.room_hint(r))
            self.gauntlet_only(human)                         # no guns during the countdown
            human.center_print("^3Next: {}".format(r["name"]))        # the instructions are in the chat (long lines clip here)
            self.record(event="room_start", room=r["name"], subject=self.subject_id(human), subject_is_bot=is_bot(human))
        r = self.room
        m = r["m"]
        hpos, hvel, hground, hpitch, hyaw = self.fill_player(env, R, 0, human, hs)
        bpos, bvel, bground, bpitch, byaw = self.fill_player(env, R, 1, bobby, bs)
        taken = self.sync_world(env, R, (human.id, bobby.id))
        env.script[:] = (0, r["script"])
        env.sc_style = r.get("style", 0)
        env.sc_persona[1] = r.get("persona", 0)
        self.senses(env, R)
        self.last = dict(bobby=[round(float(v)) for v in bpos], opp=[round(float(v)) for v in hpos],
                         bobby_hp=[bs.health, bs.armor], opp_hp=[hs.health, hs.armor], room=r["name"])
        if not r["started"]:
            if 0 < hs.health < 150:
                human.health = 200
            if bs.health <= 0:
                minqlx.set_bot_input(bobby.id, 0, 0, 0, int(now * 4) % 2, 0, 0.0, 0.0)
            else:
                minqlx.set_bot_input(bobby.id, 0, 0, 0, 0, 0, 0.0, byaw)
                if bs.health < 150 and r["kind"] in ("aim", "choice", "move", "solo", "terrain", "speed"):
                    bobby.health = 200                       # nobody kills the target between rooms
            if now < r["t0"]:
                return
            r["started"], r["t_end"] = True, now + r["secs"]
            self.room_loadout(bobby, human)
            r["mortal"] = r["kind"] == "speed" and bool(self.lab) and bool(self.lab["courses"][r["key"]].get("mortal"))
            if r["mortal"]:
                human.health = 1                             # any fall damage at all ends the run
                human.armor = 0
            if r["kind"] == "move":
                self.new_goal(human, hpos)
            self.tot = {}
            human.center_print("^2GO")
        keys = [0, 0, 0, 0]
        if r.get("ai"):                                      # bot fight: the game's AI drives the body
            if not r.get("placed"):
                r["placed"] = True
                self.lab_place(bobby, human)
                minqlx.clear_bot_input(bobby.id)
            else:
                if bs.health > 0:
                    self.lab_keep(bobby, bpos)
                if hs.health > 0:
                    self.lab_keep(human, hpos, human=True)
        elif bs.health <= 0:
            minqlx.set_bot_input(bobby.id, 0, 0, 0, int(now * 4) % 2, 0, 0.0, 0.0)
        elif r["kind"] in ("aim", "choice"):
            if now >= r["rep_end"]:                          # new placement every REP_SECS, fresh ammo
                r["rep_end"] = now + (1e9 if r.get("lab") else REP_SECS)
                if r.get("lab"):
                    self.lab_place(bobby, human)             # lab rooms: one fixed placement for the whole room
                else:
                    self.place_pair(bobby, human)
                self.room_loadout(bobby, human, only="opp")
                env.round_t[0] = 0.0
                self.tot = {}
            else:
                env.round_t[0] += R.DT
                a = env._script_actions(np.array([1]))[0].copy()
                if r.get("reflex") == "slow":                # a slow walk from side to side: one frame in three, turning every 2.5 s
                    a[0], a[1], a[2] = 1, 1, 0
                    if m["frames"] % 3 == 0:
                        a[1] = 2 if int((now - r["t_end"] + r["secs"]) / 2.5) % 2 else 0
                if r.get("reflex") in ("track", "rocket"):   # sideways only: left or right, turning round at random moments
                    a[0] = 1
                    if a[1] == 1:
                        a[1] = 0 if int(now * 1000) % 2 else 2
                        env.sc_dir[1] = a[1] - 1
                if r.get("reflex") == "flick" and now >= r.get("hop_t", r["t_end"] - r["secs"] + 1.5):
                    z = r["zone"]                            # the target jumps to a new place, at least 150 units away
                    for _ in range(20):
                        hp_ = [float(self.rng.uniform(z[0] + 140, z[2] - 140)), float(self.rng.uniform(z[1] + 140, z[3] - 140)),
                               float(r["home"][2])]
                        if math.hypot(hp_[0] - bpos[0], hp_[1] - bpos[1]) > 150:
                            break
                    self.put(bobby, hp_, math.degrees(math.atan2(hpos[1] - hp_[1], hpos[0] - hp_[0])))
                    r["home"] = hp_
                    r["hop_t"] = now + float(self.rng.uniform(1.8, 3.2))
                    self.record(event="hop", room=r["name"], pos=[round(v, 1) for v in hp_], frame_t=round(now, 3))
                if r.get("reflex") == "flick" and math.hypot(bpos[0] - r["home"][0], bpos[1] - r["home"][1]) > 12:
                    self.put(bobby, r["home"], byaw)         # a standing target is not pushed around by the hits
                if r.get("lab"):
                    # lab targets: random walk in all four directions, with or without jumping (jump is tapped,
                    # the game wants a fresh press per jump); near the edge of its zone the target walks back
                    a[2] = int(r.get("jump", False) and m["frames"] % 2 == 0)
                    z = r["zone"]
                    if not (z[0] + 120 <= bpos[0] <= z[2] - 120 and z[1] + 120 <= bpos[1] <= z[3] - 120):
                        a[2] = 0                             # near the edge: stop jumping so it can walk back in
                        dx, dy = (z[0] + z[2]) / 2.0 - bpos[0], (z[1] + z[3]) / 2.0 - bpos[1]   # toward the middle
                        yr = math.radians(byaw)
                        f_, l_ = dx * math.cos(yr) + dy * math.sin(yr), -dx * math.sin(yr) + dy * math.cos(yr)
                        a[0] = (1 if f_ > 40 else -1 if f_ < -40 else 0) + 1
                        a[1] = (-1 if l_ > 40 else 1 if l_ < -40 else 0) + 1
                    h_ = r["hard"]                           # never moved at a wall; only if it somehow leaves the room
                    if not (h_[0] <= bpos[0] <= h_[2] and h_[1] <= bpos[1] <= h_[3]):
                        self.put(bobby, r["home"], byaw)     # far outside (knocked out): put it back
                under = bool(r.get("under_fire")) and now >= r["t_end"] - r["secs"] / 2.0
                if under and not r.get("fire_on"):           # second half: the target shoots back with the machine gun
                    r["fire_on"] = True
                    bobby.weapons(reset=True, g=True, mg=True)
                    bobby.ammo(mg=150)
                    self.record(event="fire_phase", room=r["name"], frame_t=round(now, 3))
                    human.center_print("^1He shoots back")
                if under:
                    if bs.ammo.mg < 50:
                        bobby.ammo(mg=150)
                    dv = np.array([hpos[0] - bpos[0], hpos[1] - bpos[1], hpos[2] - bpos[2]], np.float32)
                    wob = self.rng.normal(0, 1.2, 2)         # not every bullet lands: about as steady as a decent player
                    tyaw = math.degrees(math.atan2(dv[1], dv[0])) + float(wob[0])
                    tpit = -math.degrees(math.atan2(dv[2], math.hypot(dv[0], dv[1]))) + float(wob[1])
                    mvk = [(int(a[0]) - 1) * 127, (int(a[1]) - 1) * 127, 127 if int(a[2]) == 1 else 0]
                    minqlx.set_bot_input(bobby.id, mvk[0], mvk[1], mvk[2], 1, QLNUM["mg"], tpit, tyaw)
                    keys = mvk + [1]
                else:
                    keys = self.drive(bobby, env, R, 1, a, bpitch, byaw)[4]
        elif r["kind"] == "ladder" and r.get("where") == "peek":
            pk = self.lab["peek"]
            if not r.get("placed"):
                r["placed"] = True
                self.put(human, pk["subject"], pk["yaw"], human=True)
                self.put(bobby, pk["target"], pk["target_yaw"])
                env.mv[:] = 0
                if hasattr(env, "hb"):
                    env.hb[:] = 0                            # (HAND_BAND) the view's velocity too
            b_ = pk["bounds"]
            if not (b_[0] <= hpos[0] <= b_[2] and b_[1] <= hpos[1] <= b_[3]) and hs.health > 0:
                self.put(human, pk["subject"], pk["yaw"], human=True)
            if math.hypot(bpos[0] - pk["target"][0], bpos[1] - pk["target"][1]) > 200:
                self.put(bobby, pk["target"], pk["target_yaw"])
            a = env._script_actions(np.array([1]))[0].copy()
            a[0], a[1], a[2] = 1, 1, 0                       # he aims and shoots but does not move
            if len(a) > 6:
                a[6] = 0
            keys = self.drive(bobby, env, R, 1, a, bpitch, byaw, only="rg")[4]
            if bs.ammo.rg < 10:
                bobby.ammo(rg=40)
            if hs.ammo.rg < 10:
                human.ammo(rg=40)
                r["ammo"] = None
        elif r["kind"] == "ladder":
            if r.get("lab"):
                if not r.get("placed"):
                    r["placed"] = True
                    self.lab_place(bobby, human)
                else:
                    self.lab_keep(bobby, bpos)
                    if hs.health > 0:
                        self.lab_keep(human, hpos, human=True)
            a = env._script_actions(np.array([1]))[0]
            keys = self.drive(bobby, env, R, 1, a, bpitch, byaw)[4]
        elif r["kind"] in ("terrain", "speed"):
            tur = self.lab["courses"][r["key"]].get("turret") if r["kind"] == "speed" else None
            if tur:                                          # the rocket turret: stands still, leads its target
                if not r.get("turret_on") or math.hypot(bpos[0] - tur[0], bpos[1] - tur[1]) > 64:
                    r["turret_on"] = True
                    self.put(bobby, tur[:3], tur[3])
                if bs.ammo.rl < 10:
                    bobby.ammo(rl=50)
                eye_ = np.array([bpos[0], bpos[1], bpos[2] + R.VIEW_H], np.float32)
                aim = np.array([hpos[0], hpos[1], hpos[2] - 16.0], np.float32)      # at the feet, for splash
                for _ in range(2):                           # where he will be when the rocket gets there
                    t_fly = float(np.linalg.norm(aim - eye_)) / 1000.0
                    aim = np.array([hpos[0] + hvel[0] * t_fly, hpos[1] + hvel[1] * t_fly, hpos[2] - 16.0], np.float32)
                dv = aim - eye_
                tyaw = math.degrees(math.atan2(dv[1], dv[0]))
                tpit = -math.degrees(math.atan2(dv[2], math.hypot(dv[0], dv[1])))
                minqlx.set_bot_input(bobby.id, 0, 0, 0, 1 if hs.health > 0 else 0, QLNUM["rl"], tpit, tyaw)
            else:
                minqlx.set_bot_input(bobby.id, 0, 0, 0, 0, 0, 0.0, byaw)
            if hs.health > 0:
                self.lab_terrain(now, human, hpos, hvel, hground)
        elif r.get("where") == "items":
            it = self.lab["items"]
            minqlx.set_bot_input(bobby.id, 0, 0, 0, 0, 0, 0.0, byaw)
            b_ = it["bounds"]
            if not r.get("placed") or not (b_[0] <= hpos[0] <= b_[2] and b_[1] <= hpos[1] <= b_[3]):
                r["placed"] = True
                self.put(human, it["start"], it["yaw"], human=True)
            if hs.health > 0 and (hs.health != 100 or hs.armor != 0):
                human.health = 100                           # always able to pick both items up
                human.armor = 0
                self.tot.pop("opp", None)
        else:
            minqlx.set_bot_input(bobby.id, 0, 0, 0, 0, 0, 0.0, byaw)
        dmg, los = self.log_frame(now, env, 1, bobby, human, bs, hs, keys, "room:" + r["name"])
        if (r["kind"] in ("aim", "choice") or r.get("where") == "peek") and bs.health > 0 and (bs.health < 150 or bs.armor > 0):
            bobby.health = 200                               # the target never dies; its damage was counted above
            bobby.armor = 0
            self.tot["bobby"] = 200
        # ---- the subject's numbers
        oc = minqlx.ran_usercmd(human.id)
        fire = bool(oc[1] & 1)
        m["frames"] += 1
        m["fire"] += int(fire)
        m["blind"] += int(fire and env.seen_t[0] > 1.0)
        m["dmg"] += dmg.get("bobby", 0)
        m["hit_events"] += int("bobby" in dmg)
        m["dmg_taken"] += dmg.get("opp", 0)
        wnow = int(hs.weapon)
        if r["prev_w"] is not None and wnow != r["prev_w"]:
            m["switches"] += 1
        r["prev_w"] = wnow
        ammo = {w: getattr(hs.ammo, w) for w in R.WEAPONS if w != "g"}
        if r["ammo"] is not None:
            m["shots"] += sum(max(0, r["ammo"][w] - ammo[w]) for w in ammo)
        r["ammo"] = ammo
        if r["kind"] == "aim" and ammo.get(r["weapon"], 0) < 0.5 * float(R.AMMO_MAX[R.WEAPONS.index(r["weapon"])]):
            human.ammo(**{r["weapon"]: int(R.AMMO_MAX[R.WEAPONS.index(r["weapon"])])})   # aim rooms: ammo never runs out
            r["ammo"] = None
        if env.visible[0]:
            m["aim_frames"] += 1
            m["aim_err"] += self.aim_err(env, 0)
            eye = env._eye(env.state)
            yr, pr = math.radians(hyaw), math.radians(hpitch)
            fd = np.array([math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), -math.sin(pr)], np.float32)
            m["on_target"] += int(env._seg_box(eye[:1], (eye[0] + fd * 4000.0)[None], env.state[1:2, :3])[0])
            name = QLNAME.get(wnow, "?")
            m["held"][name] = m["held"].get(name, 0) + 1
        sp = math.hypot(hvel[0], hvel[1])
        m["speed"] += sp
        m["fast"] += int(sp > 330 and not hground)
        for cls, slot in taken:
            self.record(event="pickup", item=cls, by=("opp", "bobby")[slot] if slot >= 0 else "?")
            if slot == 0:
                key = "mega" if cls == "item_health_mega" else "red_armor" if cls == "item_armor_body" else \
                    "armor" if cls.startswith("item_armor") else "health" if cls.startswith("item_health") else None
                if key:
                    m["picks"][key] = m["picks"].get(key, 0) + 1
        if r["kind"] == "move" and r["goal"] is not None:
            gp = env.field.goals[r["goal"]]
            if math.hypot(gp[0] - hpos[0], gp[1] - hpos[1]) < 40 and abs(gp[2] - hpos[2]) < 64:
                m["arrive"] += 1
                self.new_goal(human, hpos)
            elif now > r["said"]:
                r["said"] = now + 2
                human.center_print("Go to: ^3{}".format(GOAL_NAMES[self.goal_labels[r["goal"]]]))
        if r.get("mortal") and hs.health <= 0 and "died" not in m:
            m["died"] = 1                                    # this room is over when you die
            human.tell("^1You died:^7 the run ends here.")
            r["t_end"] = now
        if r["kind"] != "ladder" and r.get("where") != "items" and not r.get("mortal") and 0 < hs.health < 150:
            human.health = 200                               # the subject cannot die in a test room (fights excepted)
            self.tot.pop("opp", None)
        if now >= r["t_end"]:
            self.finish_room(human)

    def finish_room(self, human):
        r, R = self.room, self.R
        m = r["m"]
        f = max(1, m["frames"])
        mins = f * R.DT / 60.0
        if r["kind"] == "aim":
            k = R.WEAPONS.index(r["weapon"])
            kind = R.W_KIND[k]
            hits = m["hit_events"] if kind == "proj" else m["dmg"] / float(R.W_DMG[k])
            shots = m["shots"] * (R.SG_PELLETS if kind == "pellet" else 1)
            res = dict(hit_rate=hits / max(1, shots), damage_per_s=m["dmg"] / (mins * 60),
                       kills_per_min=m["dmg"] / 125.0 / mins, aim_err_deg=m["aim_err"] / max(1, m["aim_frames"]),
                       on_target=m["on_target"] / max(1, m["aim_frames"]), sees_target=m["aim_frames"] / f)
        elif r["kind"] == "choice":
            tot = max(1, sum(m["held"].values()))
            held = dict(sorted(((k, round(v / tot, 2)) for k, v in m["held"].items()), key=lambda kv: -kv[1])[:3])
            res = dict(held=held, switches_per_min=m["switches"] / mins, damage_per_s=m["dmg"] / (mins * 60),
                       kills_per_min=m["dmg"] / 125.0 / mins)
        elif r["kind"] == "move":
            res = dict(arrivals_per_min=m["arrive"] / mins, speed=m["speed"] / f, fast_air=m["fast"] / f)
        elif r["kind"] == "terrain":
            att = max(m.get("attempts", 0), m.get("successes", 0))
            res = dict(successes=m.get("successes", 0), attempts=att,
                       success_rate=m.get("successes", 0) / max(1, att),
                       best_time=m["best"] if "best" in m else -1.0, speed_at_goal=m.get("speed_at_goal", 0.0))
        elif r["kind"] == "speed":
            res = dict(finished=1.0 if "best" in m else 0.0, time=m["best"] if "best" in m else -1.0,
                       distance=m.get("dist", 0.0), top_speed=r.get("top", 0.0), mean_speed=m["speed"] / f,
                       falls=m.get("falls", 0), height=m.get("height", 0.0), damage_taken=m["dmg_taken"])
            if r.get("mortal"):
                res["died"] = m.get("died", 0)
                if res["died"]:
                    res["finished"], res["time"] = 0.0, -1.0
        elif r["kind"] == "solo" and r.get("where") == "items":
            p = m["picks"]
            res = dict(mega=p.get("mega", 0), mega_possible=1 + int(r["secs"] // 35), red_armor=p.get("red_armor", 0),
                       red_armor_possible=1 + int(r["secs"] // 25), mean_speed=m["speed"] / f)
        elif r["kind"] == "solo":
            p = m["picks"]
            res = dict(mega_per_min=p.get("mega", 0) / mins, red_armor_per_min=p.get("red_armor", 0) / mins,
                       armor_per_min=p.get("armor", 0) / mins, health_per_min=p.get("health", 0) / mins,
                       fire=m["fire"] / f, blind_fire=m["fire"] / f, switches_per_min=m["switches"] / mins)
        else:
            res = dict(frags_per_min=m["frags"] / mins, deaths_per_min=m["deaths"] / mins,
                       damage_dealt_per_min=m["dmg"] / mins, damage_taken_per_min=m["dmg_taken"] / mins,
                       switches_per_min=m["switches"] / mins, blind_fire=m["blind"] / f)
        res = {k: (v if isinstance(v, dict) else round(float(v), 3)) for k, v in res.items()}
        self.record(event="room_result", room=r["name"], result=res)
        b = getattr(self, "batch", None)
        if b and r["name"] in b["names"]:
            b["results"][r["name"]] = res
            if len(b["results"]) == len(b["names"]):
                tot, done_ = 0.0, 0
                self.msg("^3Movement courses:")
                for nm in b["names"]:
                    x = b["results"][nm]
                    ok_ = x.get("finished", 0) >= 1 and x.get("time", -1) > 0
                    tot += x["time"] if ok_ else 30.0
                    done_ += int(ok_)
                    self.msg("  {:<14} {}  top {:.0f}  mean {:.0f}{}".format(
                        nm.split("/")[-1], "^2{:.2f} s^7".format(x["time"]) if ok_ else "^1not finished^7",
                        x.get("top_speed", 0), x.get("mean_speed", 0),
                        "  falls {:.0f}".format(x["falls"]) if x.get("falls") else ""))
                self.msg("^3Finished {} of {}. Total {:.1f} s^7 (30 s counted for each one not finished).".format(
                    done_, len(b["names"]), tot))
                self.record(event="moves_result", total=round(tot, 2), finished=done_, courses=b["results"])
                self.batch = None
        self.msg("^3{}^7: {}".format(r["name"], "  ".join("{} {}".format(k, v) for k, v in res.items())))
        # human baseline card, same shape as sim/test_suite.py cards (repeats of a room are averaged)
        if self.card_path is None:
            os.makedirs(os.path.join(D, "suite"), exist_ok=True)
            self.card_path = os.path.join(D, "suite", "human_{}.json".format(time.strftime("%Y%m%d-%H%M%S")))
        self.card.setdefault(r["name"], []).append(res)
        rooms = {}
        for name, runs in self.card.items():
            out = {}
            for k in runs[0]:
                out[k] = runs[-1][k] if isinstance(runs[0][k], dict) else round(float(np.mean([x[k] for x in runs])), 3)
            out["runs"] = len(runs)
            rooms[name] = out
        with open(self.card_path, "w") as fh:
            json.dump(dict(suite=1, run="human", subject="human", minutes=0, rooms=rooms), fh, indent=1)
        if r.get("ai"):
            minqlx.set_bot_substeps(self.cast()[0].id, 3)    # our control of the body resumes
        self.room = None
        if not self.queue and r.get("reflex"):
            self.msg("^2Reflex test done, thank you.^7 Your numbers are saved without your name. ^3!reflex^7 runs it again "
                     "(two or three runs give a steadier result).")
        elif not self.queue:
            self.msg("Rooms done: back to the normal duel. Card saved.")
            self.give_loadout(human)
