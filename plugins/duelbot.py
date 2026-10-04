"""duelbot: play a duel policy trained in the simulator (sim/train_duel_rnn.py) on the real Quake Live server,
and run the standard test rooms (sim/test_suite.py) with a human as the subject.

Policy play: BobbyBones is fully controlled by the network with human physics (3 moves per frame). His inputs
are built by the exact same code as in training (the simulator's observe()), fed from the real game: positions,
health, armor, weapons, ammo, the opponent's projectiles, item states. The same fairness rules apply as in
training: the opponent is only known when in view with line of sight (after the trained reaction delay) or
roughly when heard nearby. Both players spawn with the loadout the policy trained with.

Test rooms (!room ...): Bobby's body becomes the scripted target / fighter of the simulator's rooms and the
human is measured with the same metrics, giving a human baseline card (docs/LOGS.md).

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
import sys
import time
import zipfile

import minqlx
import numpy as np

sys.path.insert(0, "/sim")
D = "/tmp/practice"
MAPS = ("bloodrun", "aerowalk", "campgrounds", "bobbylab")
QLNUM = {"rl": 5, "rg": 7, "lg": 6, "mg": 2, "sg": 3, "gl": 4, "pg": 8, "hmg": 14, "g": 1}
QLNAME = {v: k for k, v in QLNUM.items()}
SCHEMA = 2
_P = ["x", "y", "z", "vx", "vy", "vz", "pitch", "yaw", "health", "armor", "weapon", "ammo_rl", "ammo_rg", "ammo_lg",
      "fwd", "right", "up", "fire"]
FRAME_COLS = ["t", "server_ms", "drill"] + ["b_" + c for c in _P] + ["o_" + c for c in _P] + \
    ["b_sees", "b_seen_ago", "los", "b_aim_err", "o_aim_err", "missiles"]
BANDS = {"close": (150.0, 300.0), "mid": (350.0, 650.0), "far": (800.0, 1200.0)}
STYLES = ("still", "slow", "fast", "jump")
ROOM_SECS = {"aim": 60, "choice": 40, "move": 90, "solo": 120, "ladder": 120}
REP_SECS = 10.0
GOAL_NAMES = {"MH": "Mega Health", "RA": "Red Armor", "YA": "Yellow Armor"}
# the test map "bobbylab" (tools/make_lab_map.py): fixed rooms, the suite never changes maps
LAB_WEAPONS = ("mg", "sg", "rl", "lg", "rg", "pg", "hmg")      # no grenade launcher: not an aim weapon
LAB_STYLES = ("walk", "jump", "env")       # target moves in all four directions; "jump" also jumps; "env" = environment box
LAB_SUITE = [["aim", w, t] for w in LAB_WEAPONS for t in LAB_STYLES] + \
    [["move", c_] for c_ in ("speed", "gaps", "ramps", "slalom")] + \
    [["fight", p_] for p_ in ("allround", "sniper", "rusher", "tracker")]
SUITE = [["aim", w, s, "mid"] for w in ("lg", "rg", "rl") for s in ("still", "fast")] + \
    [["aim", w, "fast", b] for w in ("lg", "rg", "rl") for b in ("close", "far")] + \
    [["choice", b] for b in ("close", "mid", "far")] + [["move"], ["solo"]] + \
    [["ladder", p] for p in ("allround", "sniper", "rusher", "tracker")]


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


class duelbot(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.add_command("map", self.cmd_map, 0, usage="<bloodrun|aerowalk|campgrounds|bobbylab>")
        self.lab = None
        self.add_command("note", self.cmd_note, 0, usage="<anything you noticed>")
        self.add_command("drill", self.cmd_drill, 0, usage="<weapon|off>")
        self.add_command("room", self.cmd_room, 0,
                         usage="aim <weapon> <still|slow|fast|jump> [close|mid|far] | choice <close|mid|far> | move | solo | ladder [style] | suite | off")
        self.add_command("rooms", self.cmd_rooms, 0)
        self.add_command("spar", self.cmd_spar, 0, usage="<on|off>")
        self.drill = None                                    # weapon drill: both players have only this weapon
        self.top_up = 0.0
        self.last = {}                                       # latest snapshot of both players, for notes
        self.ready = False
        self.next_check = 0.0
        self.want_map = os.environ.get("LAB_MAP", "bloodrun").lower()
        self.opp_bot = os.environ.get("DUEL_OPP", "") == "bot"
        self.room_test = os.environ.get("DUEL_ROOMTEST", "") == "1"
        self.alive = {}                                      # client id -> was alive last frame
        self.score = dict(bobby=0, opp=0)
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

    # ------------------------------------------------------------------ session logs (schema: docs/LOGS.md)
    def start_session(self, opp):
        self.end_session()
        kind = "spar" if is_bot(opp) else "human"
        mapname = (minqlx.get_cvar("mapname") or "").lower()
        self.sess = os.path.join(D, "sessions", "{}_{}_{}".format(time.strftime("%Y%m%d-%H%M%S"), mapname, kind))
        os.makedirs(self.sess, exist_ok=True)
        self.sess_opp = opp.id
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
        self.log("session {}".format(os.path.basename(self.sess)))

    def end_session(self):
        if self.sess:
            self.record(event="end", **self.score)
            self.frames_f.close()
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
               self.aim_err(env, bs_slot), self.aim_err(env, o_slot), len(minqlx.missiles())]
        self.frames_f.write(",".join(str(v) for v in row) + "\n")
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
        minqlx.console_command("map {} duel".format(self.want_map))

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
                if is_bot(p) and "Bones" not in p.clean_name:
                    minqlx.console_command("kick {}".format(p.id))
            self.msg("Spar off. Join the game to play him yourself.")

    def cmd_rooms(self, player, msg, channel):
        if self.lab:
            player.tell("!room aim <{}> <walk|jump|env>  (15 s)".format("|".join(LAB_WEAPONS)))
            player.tell("!room move <{}> (30 s or until the end)".format("|".join(self.lab.get("courses", {}))))
            player.tell("!room fight <{}> (30 s)".format("|".join(self.R.PERSONAS)))
            player.tell("!room suite = all 29 rooms, about 12 minutes | !room off")
            return
        player.tell("!room aim <lg|rg|rl|pg|sg|hmg|mg> <still|slow|fast|jump> [close|mid|far]  (60 s)")
        player.tell("!room choice <close|mid|far> (40 s) | move (90 s) | solo (120 s)")
        player.tell("!room ladder [{}] (120 s)".format("|".join(self.R.PERSONAS)))
        player.tell("!room suite = the standard set, about 20 minutes | !room off")

    def cmd_room(self, player, msg, channel):
        a = [m.lower() for m in msg[1:]]
        if not self.ready:
            player.tell("The server is still loading the map, try again in a few seconds.")
            return
        if not a:
            return self.cmd_rooms(player, msg, channel)
        if a[0] == "off":
            self.queue, self.room = [], None
            self.msg("Rooms off: back to the normal duel.")
            return
        specs = (LAB_SUITE if self.lab else SUITE) if a[0] == "suite" else [a]
        out = []
        for s in specs:
            r = self.room_spec(s)
            if r is None:
                player.tell("^1No such room:^7 !room {}".format(" ".join(a)))
                return self.cmd_rooms(player, msg, channel)
            out.append(r)
        if a[0] != "suite":                                  # a single room starts right away, replacing whatever runs
            self.queue, self.room = [], None
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
                            script=1, secs=15, where="env" if a[2] == "env" else "aim", jump=a[2] == "jump")
            if a[0] == "terrain" and len(a) >= 2 and a[1] in self.lab["stations"]:
                return dict(kind="terrain", lab=True, name="terrain/" + a[1], script=0, secs=60, key=a[1])
            if a[0] == "speed" or (a[0] == "move" and len(a) >= 2 and a[1] in self.lab.get("courses", {})):
                key = "speed" if a[0] == "speed" else a[1]
                return dict(kind="speed", lab=True, name="move/" + key, script=0, secs=30, key=key)
            if a[0] == "fight" and len(a) >= 2 and a[1] in R.PERSONAS:
                return dict(kind="ladder", lab=True, name="fight/" + a[1], style=0, script=2, secs=30,
                            persona=R.PERSONAS.index(a[1]))
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

    # ------------------------------------------------------------------ setup
    def setup(self):
        mapname = (minqlx.get_cvar("mapname") or "").lower()
        bsp = "/tmp/maps/{}.bsp".format(mapname)
        if not os.path.exists(bsp) or os.path.getsize(bsp) < 1000:
            os.makedirs("/tmp/maps", exist_ok=True)
            data = None
            for pak in ("/ql/baseq3/pak00.pk3", "/ql/baseq3/{}.pk3".format(mapname)):
                try:
                    data = zipfile.ZipFile(pak).read("maps/{}.bsp".format(mapname))
                    break
                except (KeyError, OSError):
                    pass
            if data is None:
                raise RuntimeError("no map file for " + mapname)
            with open(bsp, "wb") as f:
                f.write(data)
        P = np.load(os.path.join(D, "policy.npz"))
        self.P = {k: P[k] for k in P.files}
        self.policy_mtime = os.path.getmtime(os.path.join(D, "policy.npz"))
        self.dims = [int(x) for x in self.P["action_dims"]]
        self.E = E = importlib.import_module(str(self.P["env"]))
        self.env = E.DuelEnv(bsp, n_matches=1, seed=1)
        self.react_ms = float(self.P["react_ms"]) if "react_ms" in self.P else E.REACT_FRAMES * 25.0
        self.env.react_frames = round(self.react_ms / 25)    # same reaction delay as in training (newer simulators)
        self.h = np.zeros((1, self.P["whh"].shape[1]), np.float32)
        # the test rooms always use the current simulator's scripted players; slot 0 = human, slot 1 = Bobby
        self.R = R = importlib.import_module("duel_env")
        nav = "/maps/nav_{}_sim.json".format(mapname)
        self.renv = R.DuelEnv(bsp, n_matches=1, seed=2, nav=nav if os.path.exists(nav) else None)
        self.goal_labels = [d[4] for d in self.renv.item_def if d[4] in GOAL_NAMES]
        self.lab = None
        if mapname == "bobbylab":
            with open("/ql/maps-data/bobbylab/rooms.json") as f:
                self.lab = json.load(f)
        self.rng = np.random.default_rng(int(time.time()))
        self.item_ent = {}
        self.ready = True
        self.log("ready on {}: policy {} ({} min of training), {} inputs, reaction {} ms, rooms nav {}".format(
            mapname, self.P["run"], int(self.P["minutes"]), E.OBS_DIM, int(self.react_ms),
            "yes" if self.renv.field is not None else "no"))

    def act(self, obs):
        P = self.P
        x = np.clip((obs - P["obs_mean"]) / np.sqrt(P["obs_var"] + 1e-8), -10, 10).astype(np.float32)
        x = np.tanh(x @ P["w0"].T + P["b0"])
        x = np.tanh(x @ P["w1"].T + P["b1"])
        gi = x @ P["wih"].T + P["bih"]
        gh = self.h @ P["whh"].T + P["bhh"]
        H = self.h.shape[1]
        r = sig(gi[:, :H] + gh[:, :H])
        z = sig(gi[:, H:2 * H] + gh[:, H:2 * H])
        nn_ = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
        self.h = ((1 - z) * nn_ + z * self.h).astype(np.float32)
        logits = self.h @ P["wp"].T + P["bp"]
        out, i = [], 0
        for d in self.dims:
            l = logits[0, i:i + d]
            p = np.exp(l - l.max())
            p /= p.sum()
            out.append(int(np.random.choice(d, p=p)))        # sampled, as in training
            i += d
        return out

    # ------------------------------------------------------------------ players and world
    def cast(self):
        bobby, human, filler = None, None, None
        for p in self.players():
            if p.team == "spectator":
                continue
            if is_bot(p):
                if "Bones" in p.clean_name:
                    bobby = p
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
        nine = hasattr(E, "NW")
        try:
            if only:
                k = E.WEAPONS.index(only)
                p.weapons(reset=True, g=nine, **{only: True})
                p.ammo(**{only: int(E.DRILL_AMMO[k]) if nine else (150 if only == "lg" else 25)})
                p.weapon(QLNUM[only])
            elif nine:
                owned, ammo = E.LOADOUTS["all"]
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
        for slot, owner in enumerate(ids):
            k = 0
            for num, own, weapon, x, y, z, vx, vy, vz in ms:
                if own == owner and weapon in kinds and k < E.K:
                    env.rp[slot, k] = (x, y, z)
                    env.rv[slot, k] = (vx, vy, vz)
                    env.ra[slot, k] = True
                    if hasattr(env, "rw"):
                        env.rw[slot, k] = kinds[weapon]
                    k += 1
        taken = []
        if env.nI:
            for num, cls, x, y, z, up, _ in minqlx.item_states()[1]:
                key = (id(env), num)
                k = self.item_ent.get(key)
                if k is None:
                    d = np.linalg.norm(env.item_pos - np.array([x, y, z], np.float32), axis=1)
                    k = self.item_ent[key] = int(d.argmin()) if d.min() < 40 else -1
                if k >= 0:
                    env.item_up[0, k] = bool(up)
                if self.item_was.get(num, up) and not up:    # an item was just taken: by the nearer player
                    d = np.linalg.norm(env.state[:, :3] - np.array([x, y, z], np.float32), axis=1)
                    taken.append((cls, int(d.argmin()) if d.min() < 120 else -1))
                self.item_was[num] = up
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
        infov = (to * fdir).sum(1) / dist > E.FOV_COS
        alive = env.hp[opp] > 0
        cand = np.nonzero(infov & (dist < 4000) & alive)[0]
        vis = np.zeros(n, bool)
        if len(cand):
            vis[cand] = env._los(eye[cand], s[opp[cand], :3] + np.array([0, 0, 8.0], np.float32))
        env.visible = vis
        heard = (~vis) & alive & (dist < E.HEAR) & (np.hypot(s[opp, 3], s[opp, 4]) > 250)
        env.known[vis] = s[opp[vis], :3]
        if heard.any():
            env.known[heard] = s[opp[heard], :3] + env.rng.normal(0, 80, (int(heard.sum()), 3)).astype(np.float32) * \
                np.array([1, 1, 0], np.float32)
        env.seen_t = np.where(vis | heard, 0.0, env.seen_t + E.DT).astype(np.float32)
        return dist

    def drive(self, p, env, E, i, a, pitch, yaw, only=None):
        """turn one action row into keys and mouse for the controlled bot in slot i (same rules as the simulator)"""
        fwd, side, jump = (int(a[0]) - 1) * 127, (int(a[1]) - 1) * 127, int(a[2]) * 127
        cmd = np.array([E.TURN[a[3]], E.PITCH[a[4]]], np.float32)
        nine = hasattr(E, "NW")
        sm = np.where(np.abs(cmd) <= 1.0, E.MOUSE_SMOOTH_FINE, E.MOUSE_SMOOTH) if hasattr(E, "MOUSE_SMOOTH_FINE") \
            else E.MOUSE_SMOOTH
        env.mv[i] = sm * env.mv[i] + (1.0 - sm) * cmd
        yaw = (yaw + float(env.mv[i, 0]) + 180.0) % 360.0 - 180.0
        lev = 1.0 if (nine and env.seen_t[i] <= 0.5) else env.level     # newer simulators: no pull while an enemy is in view
        pitch = float(np.clip(pitch * lev + env.mv[i, 1], -89, 89))
        names = E.WEAPONS
        ncol = env.has.shape[1]
        w = int(env.weapon[i])
        if only:
            w = names.index(only)
        if a[6] > 0:                                         # switch only to weapons owned
            want = int(a[6]) - 1
            ok = bool(env.has[i, want]) if want < ncol else not only     # older simulator: machine gun always owned
            if ok and want != w and not (only and not nine):
                w = want
                env.cool[i] = max(env.cool[i], (float(env.fire_cd[i]) if nine else 0.0) + E.SWITCH)
        fire = bool(a[5] == 1)
        env.cool[i] = max(0.0, env.cool[i] - E.DT)
        if nine:
            env.fire_cd[i] = max(0.0, env.fire_cd[i] - E.DT)
        if fire and env.cool[i] <= 0:
            refire = E.W_REFIRE if nine else (E.REFIRE, E.RG_REFIRE, E.LG_TICK, E.MG_TICK)
            env.cool[i] = float(refire[w])
            if nine:
                env.fire_cd[i] = float(refire[w])
        minqlx.set_bot_input(p.id, fwd, side, jump, 1 if fire else 0, QLNUM[names[w]], pitch, yaw)
        return w, fire, pitch, yaw, [fwd, side, jump, int(fire)]

    # ------------------------------------------------------------------ frame
    def on_frame(self):
        try:
            self.frame()
        except Exception as e:
            if time.time() > self.err_t:
                self.err_t = time.time() + 5
                self.log("frame error: {!r}".format(e))

    def frame(self):
        now = time.time()
        if not self.ready:
            if now > self.next_check:
                self.next_check = now + 2
                if (minqlx.get_cvar("mapname") or "").lower() != self.want_map:
                    self.next_check = now + 10
                    minqlx.console_command("map {} duel".format(self.want_map))
                    return
                self.setup()
            return
        if (minqlx.get_cvar("mapname") or "").lower() not in MAPS:       # the game rotated to another map
            if now > self.next_check:
                self.next_check = now + 10
                minqlx.console_command("map {} duel".format(self.want_map))
            return
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
        bobby, human, filler = self.cast()
        real_human = human is not None and not is_bot(human)
        if real_human and self.game is not None and self.game.state not in ("warmup", None) \
                and now - self.last_abort > 30:
            self.last_abort = now                            # with a human: stay in warmup (never abort in a tight loop)
            self.log("game state {} - back to warmup".format(self.game.state))
            minqlx.console_command("abort")
        if bobby is None:
            if now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("addbot bones 5 free 0 BobbyBones")
            return
        if human is not None and filler is not None:
            if now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("kick {}".format(filler.id))
            return
        opp = human or filler
        if opp is None:
            if self.opp_bot and now > self.next_check:
                self.next_check = now + 5
                minqlx.console_command("addbot sarge 5")
            minqlx.set_bot_input(bobby.id, 0, 0, 0, 0, 0, 0.0, 0.0)
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
                    self.give_loadout(p)
                self.tot.pop(who, None)
                if who == "bobby":
                    self.h[:] = 0
                    for env in (self.env, self.renv):
                        env.mv[:] = 0
                        env.cool[:] = 0
                        env.seen_t[:] = 9.0
                        env.opp_hist = []
                    minqlx.set_bot_substeps(bobby.id, 3)
            if was and not up:
                other = "opp" if who == "bobby" else "bobby"
                self.score[other] += 1
                if self.room is not None and self.room.get("started"):
                    self.room["m"]["frags" if who == "bobby" else "deaths"] += 1
                self.record(event="death", who=who, drill=self.drill, room=self.room["name"] if self.room else None,
                            state=self.last, **self.score)
            self.alive[p.id] = up
        if in_room:
            return self.room_frame(now, bobby, opp, bs, os_)
        env, E = self.env, self.E
        if bs.health <= 0:                                   # tap fire to respawn
            minqlx.set_bot_input(bobby.id, 0, 0, 0, int(now * 4) % 2, 0, 0.0, 0.0)
            self.fill_player(env, E, 0, bobby, bs)
            self.fill_player(env, E, 1, opp, os_)
            env.visible[:] = False
            self.log_frame(now, env, 0, bobby, opp, bs, os_, [0, 0, 0, 0], self.drill)
            return
        if self.drill and not hasattr(E, "NW") and now > self.top_up:    # older simulator: drills had endless ammo
            self.top_up = now + 2
            for p in (bobby, opp):
                p.ammo(**{self.drill: 150 if self.drill == "lg" else 25})
        pos, vel, ground, pitch, yaw = self.fill_player(env, E, 0, bobby, bs)
        opos = self.fill_player(env, E, 1, opp, os_)[0]
        for cls, slot in self.sync_world(env, E, (bobby.id, opp.id)):
            self.record(event="pickup", item=cls, by=("bobby", "opp")[slot] if slot >= 0 else "?")
        self.senses(env, E)
        a = self.act(env.observe()[:1])
        w, fire, pitch, yaw, keys = self.drive(bobby, env, E, 0, a, pitch, yaw, only=self.drill)
        wname = E.WEAPONS[w]
        self.last = dict(bobby=[round(float(v)) for v in pos], opp=[round(float(v)) for v in opos],
                         bobby_hp=[bs.health, bs.armor], opp_hp=[os_.health, os_.armor], weapon=wname,
                         visible=bool(env.visible[0]), seen_ago=round(float(env.seen_t[0]), 1))
        self.log_frame(now, env, 0, bobby, opp, bs, os_, keys, self.drill)
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
        if k == "aim":
            return "{} only, endless ammo. Hit the target as much as you can.".format(r["weapon"].upper())
        if k == "choice":
            return "All weapons. Use whatever you think is right at this distance."
        if k == "speed":
            return "Gauntlet only. {}: reach the far end as fast as you can.".format(
                self.lab["courses"][r["key"]]["name"] if self.lab else "Course")
        if k == "move":
            return "Gauntlet only. Run to the item named on screen."
        if k == "solo":
            return "All weapons. Collect what you would in a real game."
        if k == "ladder":
            style = {"allround": "rockets close, LG mid, rail far", "sniper": "rail, keeps its distance",
                     "rusher": "rockets, always closing in", "tracker": "LG at mid range",
                     "dodger": "dodges, backs off when hurt", "stander": "stands still",
                     "jumper": "runs at you, always jumping", "spammer": "fires blind"}.get(r["name"].split("/")[-1], "")
            return "All weapons, your choice. Play to win. Opponent: {} ({}).".format(r["name"].split("/")[-1], style)
        return ""

    def room_loadout(self, bobby, human, only=None):
        r, R = self.room, self.R
        if only in (None, "opp"):
            if r["kind"] == "aim":
                self.give_loadout(human, R, only=r["weapon"])
            elif r["kind"] in ("move", "terrain", "speed"):
                human.weapons(reset=True, g=True)
            else:
                self.give_loadout(human, R, only="")
            r["ammo"] = None
        if only in (None, "bobby"):
            if r["kind"] == "ladder":
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
                    return True
        return False

    def put(self, p, pos, yaw=None, human=False):
        p.position(x=float(pos[0]), y=float(pos[1]), z=float(pos[2]) + 2.0)
        p.velocity(reset=True)
        if yaw is not None and human:
            minqlx.set_view(p.id, 0.0, float(yaw))
        elif yaw is not None:
            minqlx.set_bot_input(p.id, 0, 0, 0, 0, 0, 0.0, float(yaw))

    def lab_place(self, bobby, human):
        """fixed placement on the lab map: aim box (about 700 units apart) or the environment box"""
        r, L = self.room, self.lab
        if r.get("where") == "aim":
            a = L["aim"]
            self.put(human, a["subject"], a["yaw"], human=True)
            self.put(bobby, a["target"], float(self.rng.uniform(-180, 180)))
            r["home"], r["zone"], r["hard"] = a["target"], a["zone"], [-64, -64, 1600, 1088]
        else:
            e = L["env"]
            spots = [np.array([x, y, e["z"]], np.float32) for x, y in e["spots"]]
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

    def lab_keep(self, p, pos, human=False):
        """fights: a player who respawned elsewhere on the lab map is moved back into the environment box"""
        e = self.lab["env"]
        b = e["bounds"]
        if not (b[0] <= pos[0] <= b[2] and b[1] <= pos[1] <= b[3]):
            x, y = e["spots"][int(self.rng.integers(len(e["spots"])))]
            self.put(p, (x, y, e["z"]), 0.0, human=human)

    def lab_terrain(self, now, human, hpos, hvel, hground):
        """trick-jump stations and the speed straight: put the subject at the start, time each attempt"""
        r, m = self.room, self.room["m"]
        sp = math.hypot(hvel[0], hvel[1])
        if r["kind"] == "speed":
            st = self.lab["courses"][r.get("key", "speed")]
            if r.get("leg") is None:
                self.put(human, st["start"], st["yaw"], human=True)
                r["leg"], r["t_run"] = 0, None
                return
            r["top"] = max(r.get("top", 0.0), sp)
            m["dist"] = max(m.get("dist", 0.0), float(hpos[0] - st["start"][0]))
            if r["t_run"] is None and sp > 50:
                r["t_run"] = now
            if hpos[2] < st["fall_z"]:                      # fell into a pit: back to the start of that platform
                cps = [c for c in st["checkpoints"] if c <= hpos[0]] or st["checkpoints"][:1]
                self.put(human, [cps[-1], st["start"][1], st["start"][2]], st["yaw"], human=True)
                m["falls"] = m.get("falls", 0) + 1
            elif hpos[0] > st["end_x"]:                     # reached the end: the room is over
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
            human.weapons(reset=True)                         # no weapons during the countdown
            human.center_print("^3{}^7: {}".format(r["name"], self.room_hint(r)))
            self.record(event="room_start", room=r["name"])
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
            if r["kind"] == "move":
                self.new_goal(human, hpos)
            self.tot = {}
            human.center_print("^2GO: {}".format(r["name"]))
        keys = [0, 0, 0, 0]
        if bs.health <= 0:
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
                if r.get("lab"):
                    # lab targets: random walk in all four directions, with or without jumping (jump is tapped,
                    # the game wants a fresh press per jump); near the edge of its zone the target walks back
                    a[2] = int(r.get("jump", False) and m["frames"] % 2 == 0)
                    z = r["zone"]
                    if not (z[0] + 120 <= bpos[0] <= z[2] - 120 and z[1] + 120 <= bpos[1] <= z[3] - 120):
                        dx, dy = (z[0] + z[2]) / 2.0 - bpos[0], (z[1] + z[3]) / 2.0 - bpos[1]   # toward the middle
                        yr = math.radians(byaw)
                        f_, l_ = dx * math.cos(yr) + dy * math.sin(yr), -dx * math.sin(yr) + dy * math.cos(yr)
                        a[0] = (1 if f_ > 40 else -1 if f_ < -40 else 0) + 1
                        a[1] = (-1 if l_ > 40 else 1 if l_ < -40 else 0) + 1
                    h_ = r["hard"]                           # never moved at a wall; only if it somehow leaves the room
                    if not (h_[0] <= bpos[0] <= h_[2] and h_[1] <= bpos[1] <= h_[3]):
                        self.put(bobby, r["home"], byaw)     # far outside (knocked out): put it back
                keys = self.drive(bobby, env, R, 1, a, bpitch, byaw)[4]
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
            minqlx.set_bot_input(bobby.id, 0, 0, 0, 0, 0, 0.0, byaw)
            if hs.health > 0:
                self.lab_terrain(now, human, hpos, hvel, hground)
        else:
            minqlx.set_bot_input(bobby.id, 0, 0, 0, 0, 0, 0.0, byaw)
        dmg, los = self.log_frame(now, env, 1, bobby, human, bs, hs, keys, "room:" + r["name"])
        if r["kind"] in ("aim", "choice") and bs.health > 0 and (bs.health < 150 or bs.armor > 0):
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
        if r["kind"] != "ladder" and 0 < hs.health < 150:
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
                       falls=m.get("falls", 0))
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
        self.room = None
        if not self.queue:
            self.msg("Rooms done: back to the normal duel. Card saved.")
            self.give_loadout(human)
