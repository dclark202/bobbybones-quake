"""BobbyBones in a free-for-all: up to four copies of him and people, six players at most, on one map.

Load with QLX_PLUGINS="botctl, ffabot" and the ffa factory (entrypoint: FACTORY=ffa). BOBBYS=<n> (1 to 4) sets how
many Bobbys start; !bots <n> changes it. People can only take the seats the bots do not: 6 - n. Nobody can push a
bot out; lowering !bots frees seats.

How it works: one simulator (the group one, sim/duel_env_ffa.py, six seats) is built once; every client gets a seat
on joining and keeps it until he leaves (empty seats are parked far away, dead). Each frame every real player's
state is copied into his seat, the simulator's own senses run for every seat (sight, hearing, attention), the
inputs are built for all Bobby seats in one batch, one network pass gives their actions, and each Bobby is driven
with the same hand and finger rules as in training (duelbot.drive). Everything per Bobby is logged.
"""
import importlib
import json
import math
import os
import sys
import time

import minqlx
import numpy as np

try:                                                        # the duel plugin: shared helpers (world sync, hands, logs)
    _duel = importlib.import_module(__package__ + ".duelbot")
except Exception:                                           # noqa: BLE001 - loaded outside the plugin package
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    _duel = importlib.import_module("duelbot")
duelbot, is_bot, sig, D, QLNUM = _duel.duelbot, _duel.is_bot, _duel.sig, _duel.D, _duel.QLNUM
_pu = _duel._pu                                              # no powerups on any server (plugins/powerups.py)

SEATS = 6
MAX_BOTS = 4
FFA_MAPS = _duel.MAPS                                       # the maps Bobby has trained on; a map outside this list makes frame() reload it (sinister, 2026-10-06)
ROUND_SECS = 180.0                                           # as the training rounds: the clock and the memory start over
FRAME_COLS = ["t", "server_ms", "bot", "seat"] + ["b_" + c for c in _duel._P] + ["foe_seat", "foe_bot", "b_sees", "b_seen_ago",
                                                               "b_aim_err", "intent", "people", "bots"]
PARK = np.array([-6000.0, -6000.0, -6000.0, 0, 0, 0, 1.0, 0.0], np.float32)


class ffabot(duelbot):
    FACTORY = "ffa"

    def __init__(self):                                      # not duelbot's: no duel rooms, no 1v1 commands
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.add_hook("player_loaded", self.on_player_loaded)
        self.add_hook("player_disconnect", self.on_disconnect)
        self.add_hook("vote_called", self.on_vote_called)
        self.add_hook("team_switch_attempt", self.on_team_switch)
        self.add_hook("game_start", self.on_game_start)
        self.add_hook("game_end", self.on_game_end)
        self.add_hook("stats", self.on_stats)                # the game's own per-weapon table (duelbot.on_stats)
        self.add_command("help", self.cmd_help, 0)
        self.add_command("bots", self.cmd_bots, 0, usage="<0-4>")
        self.add_command("map", self.cmd_map, 0, usage="<{}>".format("|".join(FFA_MAPS)))
        self.add_command("maps", self.cmd_maps, 0)
        self.add_command("note", self.cmd_note, 0, usage="<anything you noticed>")
        self.add_hook("client_command", self.on_client_command)
        self.match = None                                    # the running game (see on_game_start)
        self.ready_ids = set()                               # people who pressed F3 in this warmup
        self.go_t = 0.0
        self.n_bots = max(0, min(MAX_BOTS, int(os.environ.get("BOBBYS") or 2)))   # 0 allowed: people only (owner, 2026-10-06)
        self.want_map = os.environ.get("LAB_MAP", "aerowalk").lower()
        self.lab, self.arena, self.drill, self.room, self.queue = None, None, None, None, []
        self.no_sg = self.no_walk = False
        self.ready = False
        self.next_check = self.err_t = self.last_abort = 0.0
        self.reload_check, self.policy_mtime = 0.0, 0.0
        self.sess, self.frames_f, self.sess_opp = None, None, None
        self.want_w, self.item_was, self.item_ent, self.last = {}, {}, {}, {}
        self.seat = {}                                       # client id -> seat
        self.alive = {}                                      # client id -> was alive last frame
        self.fired = np.zeros(SEATS, bool)                   # Bobby seats: the trigger was pressed last frame
        self.prev = {}                                       # seat -> (position, on ground) last frame
        self.ammo_prev = {}                                  # seat -> ammo of the weapon held, last frame (people: shots)
        self.tot = {}                                        # seat -> health + armor last frame
        self.dealt_prev = {}                                 # client id -> damage dealt (the game's count) last frame
        self.kills0 = {}                                     # client id -> kills at the start of the round
        self.acc = {}                                        # seat -> per-minute counters
        self.next_summary = time.time() + 60
        self.score = {}

    WELCOME = "^2!bots <0-4>^7 sets how many of me play. ^2!map <name>^7 changes the map (^2!maps^7 lists them), ^2!mode duel^7 is one against one."
    HELP = ["^3What I can do:^7 I learned to play from scratch in a simulator: movement, aim, picking up items, choosing weapons. I play with human limits.",
            "^3Play me:^7 join the game. ^2!bots <0-4>^7 sets how many of me play; people get the other seats (six play, the rest spectate).",
            "^3Commands:^7 ^2F3^7 readies you up: when more than half of the people are ready a real game starts (10 min, machine gun at spawn). ^2!map <name>^7 changes the map (^2!maps^7 lists them), ^2!map testlab^7 is 1v1 with ^2!reflex^7 and ^2!movement^7. ^2!mode ffa|duel^7 switches the mode.",
            "^3Give feedback:^7 ^2!note <text>^7 tells me what you noticed. Every match I play is recorded, without names."]

    def log(self, msg):
        minqlx.console_print("[ffabot] " + msg + "\n")
        with open(os.path.join(D, "duelbot.log"), "a") as f:
            f.write("{} ffa {}\n".format(time.strftime("%H:%M:%S"), msg))

    # ------------------------------------------------------------------ a timed, scored match
    def on_client_command(self, player, cmd):
        """F3 toggles a person's ready state (the game's "readyup" command). The game starts when more than half of the
        people in the game are ready (owner, 2026-10-06); the engine's own rule would count the bots, who never are."""
        if cmd.strip().lower() == "readyup" and not is_bot(player) and self.game is not None and self.game.state == "warmup":
            if player.id in self.ready_ids:
                self.ready_ids.discard(player.id)
            else:
                self.ready_ids.add(player.id)
            people = self.people()
            n = len([q for q in people if q.id in self.ready_ids])
            self.msg("^3{} of {} people ready.^7 More than half starts a real game (machine gun at spawn, 10 minutes).".format(n, len(people)))

    def on_game_start(self, data):
        """a real game: the stats start from zero here; the table at the end is the game's own score"""
        self.ready_ids = set()
        if not self.people():
            return
        try:
            mins = int(float(minqlx.get_cvar("timelimit") or 0)) or 10
        except ValueError:
            mins = 10
        self.match = dict(mins=mins, base={}, started=True, t_end=time.time() + mins * 60 + 15)
        for p in self.bobbys() + self.people():
            self.match["base"][p.id] = (p.stats.kills, p.stats.deaths, p.stats.damage_dealt, p.stats.damage_taken)
        self.record(event="match_start", minutes=mins, people=len(self.people()), bots=len(self.bobbys()))
        self.msg("^3Game on: {} minutes, everybody against everybody, machine gun at spawn.^7".format(mins))

    def on_game_end(self, data):
        if self.match:
            self.match_end("time")

    def match_end(self, why="time"):
        M = self.match
        self.match = None
        rows = []
        for p in self.bobbys() + self.people():
            b = M["base"].get(p.id, (0, 0, 0, 0) if M.get("started") else (p.stats.kills, p.stats.deaths, p.stats.damage_dealt, p.stats.damage_taken))
            rows.append(dict(name=p.clean_name if is_bot(p) else "person {}".format(self.seat.get(p.id, "?")), bot=is_bot(p),
                             seat=self.seat.get(p.id), kills=p.stats.kills - b[0], deaths=p.stats.deaths - b[1],
                             dmg_dealt=p.stats.damage_dealt - b[2], dmg_taken=p.stats.damage_taken - b[3]))
        rows.sort(key=lambda r: (-r["kills"], r["deaths"]))
        self.record(event="match_result", minutes=M["mins"], why=why, table=rows)
        self.msg("^3Match over ({})^7:".format(why))
        for i, r in enumerate(rows, 1):
            self.msg("  {}. {} ^2{}^7 kills, {} deaths, damage {} : {}".format(i, r["name"], r["kills"], r["deaths"], r["dmg_dealt"], r["dmg_taken"]))

    # ------------------------------------------------------------------ seats and commands
    def people(self):
        return [p for p in self.players() if not is_bot(p) and p.team != "spectator"]

    def bobbys(self):
        return sorted([p for p in self.players() if is_bot(p) and "Bones" in p.clean_name], key=lambda p: p.id)

    def cmd_bots(self, player, msg, channel):
        if len(msg) < 2 or not msg[1].isdigit() or not 0 <= int(msg[1]) <= MAX_BOTS:
            return minqlx.RET_USAGE
        n = int(msg[1])
        if len(self.people()) > SEATS - n:
            player.tell("^3{} people are playing:^7 with ^2!bots {}^7 only {} could. Wait for a seat to free up.".format(
                len(self.people()), n, SEATS - n))
            return
        self.n_bots = n
        self.msg("^3{} set the number of Bobbys to {}.^7 {} seats for people.".format(player.clean_name, n, SEATS - n))
        self.record(event="bots", n=n)

    def cmd_map(self, player, msg, channel):
        if len(msg) < 2 or msg[1].lower() not in FFA_MAPS:
            return minqlx.RET_USAGE
        self.want_map = msg[1].lower()
        _pu.load_map(self.want_map, "ffa")

    def on_team_switch(self, player, old, new):
        """people take the seats the bots leave: SEATS - n_bots; a bot is never pushed out"""
        if is_bot(player) or new == "spectator":
            self.ready_ids.discard(player.id)
            return
        others = [p for p in self.people() if p.id != player.id]
        if len(others) >= SEATS - self.n_bots:
            player.tell("^3All {} seats for people are taken^7 ({} Bobbys play). ^2!bots <n>^7 with a smaller number frees seats.".format(
                SEATS - self.n_bots, self.n_bots))
            return minqlx.RET_STOP_ALL

    def on_disconnect(self, player, reason):
        self.free_seat(player.id)
        self.ready_ids.discard(player.id)

    def on_map(self, mapname, factory):
        self.end_session()
        self.ready = False
        self.ready_ids = set()
        self.seat, self.alive, self.prev, self.ammo_prev, self.tot, self.acc = {}, {}, {}, {}, {}, {}

    # ------------------------------------------------------------------ setup
    def setup(self):
        """the map file, the policy and one six-seat simulator (the only world of this process: the simulator's
        worlds share buffers sized by player count, so duelbot's two-seat ones are never built here)"""
        mapname = (minqlx.get_cvar("mapname") or "").lower()
        self.set_cvar("g_itemTimers", "0")                   # owner (2026-10-06): no spawn timers on the armors and the mega
        self.set_cvar("g_weaponRespawn", "2")                # weapons back in 2 s (duelbot.setup puts the 5 s of 1v1 back)
        self.set_cvar("timelimit", "10")                     # a real game (started by the people readying up) lasts this long
        self.set_cvar("fraglimit", "0")
        if _pu.reload_needed(mapname, "ffa"):                # the game loaded Campgrounds by itself with no quad to turn into the mega
            self.log("{}: loaded again with its quad, for the mega".format(mapname))
            _pu.load_map(mapname, "ffa")
            return
        self.no_powerups(say=True)
        bsp = "/tmp/maps/{}.bsp".format(mapname)
        if not os.path.exists(bsp) or os.path.getsize(bsp) < 1000:
            os.makedirs("/tmp/maps", exist_ok=True)
            data = None
            for pak in ["/ql/baseq3/pak00.pk3", "/ql/baseq3/{}.pk3".format(mapname)] + sorted(
                    __import__("glob").glob("/ql/steamapps/workshop/content/282440/*/{}.pk3".format(mapname))):   # the Workshop item (public server)
                try:
                    data = __import__("zipfile").ZipFile(pak).read("maps/{}.bsp".format(mapname))
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
        envmod = str(self.P["env"]) if "ffa" in str(self.P["env"]) else "duel_env_ffa"     # the group simulator the policy was trained in
        self.E = E = self.env_module(envmod)                   # with the switches he was trained with (policy.npz env_vars)
        self.round_secs = float(self.P["round_secs"]) if "round_secs" in self.P else ROUND_SECS
        self.react_ms = float(self.P["react_ms"]) if "react_ms" in self.P else E.REACT_FRAMES * 25.0
        self.no_walk = bool(self.P["no_walk"]) if "no_walk" in self.P else False
        self.rules2 = hasattr(E, "ACQUIRE_FRAMES")
        self.lab = None
        rooms_json = "/ql/maps-data/{}/rooms.json".format(mapname)
        if os.path.exists(rooms_json):
            with open(rooms_json) as f:
                self.lab = json.load(f)
        os.environ["ROUTE_CACHE"] = D                          # the route grid is cached here (/maps is read-only)
        self.rng = np.random.default_rng(int(time.time()))
        self.item_ent, self.item_was, self.want_w = {}, {}, {}
        nav = "/maps/nav_{}_sim.json".format(mapname)
        self.env = env = E.DuelEnv(bsp, n_matches=1, seed=3, nav=nav if os.path.exists(nav) else None, group=SEATS)
        env.react_frames = round(self.react_ms / 25)
        if hasattr(env, "_ffa"):
            # "players beyond two": the simulator here has six seats, so the input read 1.0 whoever was present; in training
            # it was 0, 0.25 or 0.5 (groups of 2, 3 and 4). It follows the players in the game now.
            ffa_ = env._ffa
            self.n_present = 2

            def ffa_present(*a_, **k_):
                out = ffa_(*a_, **k_)
                out[:, 17] = min(0.5, max(0.0, (self.n_present - 2) / 4.0))
                return out
            env._ffa = ffa_present
        if self.rules2:
            env.acquire_frames = round(float(self.P["acquire_ms"]) / 25) if "acquire_ms" in self.P else E.ACQUIRE_FRAMES
            env.lab = None
            env.kind[:] = E.NORMAL
        self.h = np.zeros((SEATS, self.P["whh"].shape[1]), np.float32)
        for k in range(SEATS):
            self.park(k)
        self.sess_t0 = time.time()
        self.ready = True
        self.start_session()
        self.log("free-for-all on {}: {} Bobbys, {} seats, policy {} ({} min), {} inputs".format(
            mapname, self.n_bots, SEATS, self.P["run"], int(self.P["minutes"]), E.OBS_DIM))

    def park(self, k):
        env = self.env
        env.state[k] = PARK
        env.hp[k], env.armor[k] = 0.0, 0.0
        env.yaw[k], env.pitch[k] = 0.0, 0.0
        env.mv[k], env.cool[k] = 0.0, 0.0
        self.h[k] = 0.0
        self.want_w.pop((id(env), k), None)
        self.prev.pop(k, None), self.ammo_prev.pop(k, None), self.tot.pop(k, None)

    def free_seat(self, cid):
        k = self.seat.pop(cid, None)
        if k is not None and self.ready:
            self.park(k)
            self.record(event="leave", seat=k)

    def take_seat(self, p):
        used = set(self.seat.values())
        for k in range(SEATS):
            if k not in used:
                self.seat[p.id] = k
                self.record(event="join", seat=k, bot=is_bot(p))
                return k
        return None

    # ------------------------------------------------------------------ session logs
    def record(self, **rec):
        """what happens in the game is written only while a person is playing (owner, 2026-10-07: "it should only log when
        humans are actively playing": the bots alone filled the event log with their own deaths and pickups), and not
        when the disk is nearly full. Joins, leaves, notes and the end of a session are always written."""
        if rec.get("event") in ("death", "pickup", "minute", "bots", "style") and not (getattr(self, "people_now", False) and getattr(self, "disk_ok", True)):
            return
        duelbot.record(self, **rec)

    def no_quad(self):
        """no quad in free-for-all (owner; the simulator has none). Where the map puts the quad in the mega's place
        (campgrounds), the mega comes back, as in 1v1 and in training. The game puts every item back when a real game
        starts (the restart after the countdown), so this is done at setup, at the start of a game and every few
        seconds after: it was only done at setup, and the quad was back in every real game (owner, 2026-10-07)."""
        self.no_powerups()                                   # (every powerup since 2026-10-09: plugins/powerups.py)

    def start_session(self):
        self.end_session()
        mapname = (minqlx.get_cvar("mapname") or "").lower()
        self.sess = os.path.join(D, "sessions", "{}_{}_ffa".format(time.strftime("%Y%m%d-%H%M%S"), mapname))
        os.makedirs(self.sess, exist_ok=True)
        meta = dict(schema=4, kind="ffa", started=round(time.time(), 2), map=mapname, seats=SEATS, policy=str(self.P["run"]),
                    train_minutes=int(self.P["minutes"]), env=str(self.P["env"]), react_ms=int(self.react_ms), frame_ms=25,
                    frame_columns=FRAME_COLS)
        with open(os.path.join(self.sess, "meta.json"), "w") as f:
            json.dump(meta, f, indent=1)
        self.frames_f = open(os.path.join(self.sess, "frames.csv"), "a")
        self.frames_f.write(",".join(FRAME_COLS) + "\n")
        self.log("session {}".format(os.path.basename(self.sess)))

    def end_session(self):
        if self.sess:
            self.record(event="end")
            self.frames_f.close()
        self.sess, self.frames_f = None, None

    # ------------------------------------------------------------------ the network for several seats at once
    def act_batch(self, obs, seats):
        P = self.P
        x = np.clip((obs - P["obs_mean"]) / np.sqrt(P["obs_var"] + 1e-8), -10, 10).astype(np.float32)
        if "cell" in P:
            ids = np.clip(obs[:, -2:].astype(np.int64), 0, len(P["cell"]) - 1)
            x = np.concatenate([x[:, :-2], P["cell"][ids[:, 0]], P["cell"][ids[:, 1]]], 1)
        x = np.tanh(x @ P["w0"].T + P["b0"])
        x = np.tanh(x @ P["w1"].T + P["b1"])
        h = self.h[seats]
        gi = x @ P["wih"].T + P["bih"]
        gh = h @ P["whh"].T + P["bhh"]
        H = h.shape[1]
        r = sig(gi[:, :H] + gh[:, :H])
        z = sig(gi[:, H:2 * H] + gh[:, H:2 * H])
        nn_ = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
        h = ((1 - z) * nn_ + z * h).astype(np.float32)
        self.h[seats] = h
        logits = h @ P["wp"].T + P["bp"]
        out = np.zeros((len(seats), len(self.dims)), np.int64)
        i = 0
        for j, d in enumerate(self.dims):
            l = logits[:, i:i + d]
            p = np.exp(l - l.max(1, keepdims=True))
            p /= p.sum(1, keepdims=True)
            out[:, j] = (p.cumsum(1) > self.rng.random((len(seats), 1))).argmax(1)     # sampled, as in training
            i += d
        return out

    # ------------------------------------------------------------------ the simulator's senses for every seat
    def senses_all(self, env, E, present):
        """sight, hearing and attention for every seat, as the group simulator's step() does it (nothing is seen or
        heard of an empty or dead seat)"""
        s, n, G = env.state, env.n, env.G
        ar = np.arange(n)
        eye = env._eye(s)
        yr, pr = np.radians(env.yaw), np.radians(env.pitch)
        fdir = np.stack([np.cos(pr) * np.cos(yr), np.cos(pr) * np.sin(yr), -np.sin(pr)], 1)
        live = present & (env.hp > 0)
        off = np.zeros((n, G - 1), np.float32)
        for k_ in range(G - 1):
            opp = env.others[:, k_]
            to = s[opp, :3] - eye
            dist = np.linalg.norm(to, axis=1) + 1e-6
            cosang = (to * fdir).sum(1) / dist
            off[:, k_] = 1.0 - cosang
            cand = np.nonzero((cosang > env.fov()[2]) & (dist < 4000) & live[opp] & live)[0]
            vis = np.zeros(n, bool)
            if len(cand):
                vis[cand] = env._los(eye[cand], s[opp[cand], :3] + np.array([0, 0, 8.0], np.float32))
            heard = (~vis) & live[opp] & live & (dist < E.HEAR) & (np.hypot(s[opp, 3], s[opp, 4]) > 250)
            env.vis2[:, k_] = vis
            need_ = max(1, env.acquire_frames - env.react_frames)
            if getattr(E, "SURPRISE_MS", 0) > 0 and hasattr(env, "acq_extra2"):   # off the crosshair and unexpected: noticed later (as in training)
                ecc_ = np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))
                env.acq_extra2[:, k_] = np.where(vis & (env.vis_run2[:, k_] == 0), E.surprise_frames(ecc_, env.seen2[:, k_]),
                                                 np.where(vis, env.acq_extra2[:, k_], 0))
                need_ = need_ + env.acq_extra2[:, k_]
            env.vis_run2[:, k_] = np.where(vis, env.vis_run2[:, k_] + 1, 0)
            acq = vis & (env.vis_run2[:, k_] >= need_)
            env.acq2[:, k_] = acq
            env.known2[acq, k_] = s[opp[acq], :3]
            if heard.any():
                env.known2[heard, k_] = s[opp[heard], :3] + env.rng.normal(0, 80, (int(heard.sum()), 3)).astype(np.float32) * \
                    np.array([1, 1, 0], np.float32)
            env.seen2[:, k_] = np.where(acq | heard, 0.0, env.seen2[:, k_] + E.DT)
        cur = np.zeros((n, G - 1), bool)
        cur[ar, env.fidx] = True
        sc_ = np.where(env.acq2, off * np.where(cur, 0.6, 1.0), np.where(env.vis2, 2.0 + off, 4.0 + env.seen2))
        env.fidx = sc_.argmin(1)
        env.foe = env.others[ar, env.fidx]
        env.visible = env.vis2[ar, env.fidx]
        env.vis_run = env.vis_run2[ar, env.fidx]
        env.acquired = env.acq2[ar, env.fidx]
        env.known = env.known2[ar, env.fidx]
        env.seen_t = env.seen2[ar, env.fidx]

    # ------------------------------------------------------------------ frame
    def frame(self):
        now = time.time()
        mapname = (minqlx.get_cvar("mapname") or "").lower()
        if not self.ready:
            if now > self.next_check:
                self.next_check = now + 2
                if mapname in FFA_MAPS:
                    self.want_map = mapname                  # the end-of-game map vote (sv_mapPoolFile) picked it: stay
                elif mapname != self.want_map:
                    self.next_check = now + 10
                    _pu.load_map(self.want_map, "ffa")
                    return
                self.setup()
            return
        if mapname not in FFA_MAPS:
            if now > self.next_check:
                self.next_check = now + 10
                _pu.load_map(self.want_map, "ffa")
            return
        if now > self.reload_check:
            self.reload_check = now + 5                      # a newer policy.npz is picked up without a restart
            try:
                if os.path.getmtime(os.path.join(D, "policy.npz")) != self.policy_mtime:
                    self.end_session()
                    self.on_map(mapname, "ffa")
                    self.setup()
                    self.msg("^3New BobbyBones loaded^7: {} at {} minutes of training.".format(self.P["run"], int(self.P["minutes"])))
            except OSError:
                pass
        bobbys, people = self.bobbys(), self.people()
        self.people_now = bool(people)                       # (record() writes game events only then)
        if now > getattr(self, "quad_check", 0.0):
            self.quad_check = now + 3.0
            self.no_quad()
        # Warmup for ever, as on the 1v1 server: with bots only the game starts a match by itself (harmless); once a person
        # is in the game and loaded, one "abort" brings it back to warmup, and an unready person keeps it there. Never
        # while someone is still loading: a restart then looks like a hanging connection (2026-10-06).
        loaded = [p for p in people if p.state is not None and p.state.health > 0]
        # Not in the 30 s after the people's own start ("allready"): this frame can run before on_game_start has marked the
        # game as theirs, and the abort then threw the game they had just started back to warmup, with the "Game on" line
        # on the screen and everybody still carrying every weapon (owner, 2026-10-07).
        if (loaded and not self.match and self.game is not None and self.game.state == "in_progress"
                and now - self.last_abort > 60 and now - self.go_t > 30):
            self.last_abort = now
            minqlx.console_command("abort")
        if len(bobbys) < self.n_bots and now > self.next_check:
            self.next_check = now + 4
            k = len(bobbys) + 1
            minqlx.console_command("addbot bones 5 free 0 \"BobbyBones {} (BOT)\"".format(k))
        elif len(bobbys) > self.n_bots and now > self.next_check:
            self.next_check = now + 4
            minqlx.console_command("clientkick {}".format(bobbys[-1].id))
        env, E = self.env, self.E
        here = {p.id: p for p in bobbys + people}
        for cid in [c for c in self.seat if c not in here]:
            self.free_seat(cid)
        for p in bobbys + people:
            if p.id not in self.seat and self.take_seat(p) is None:
                continue
        present = np.zeros(SEATS, bool)
        seated = []                                          # (seat, player, state)
        for p in bobbys + people:
            k = self.seat.get(p.id)
            st = p.state
            if k is None or st is None:
                continue
            present[k] = True
            seated.append((k, p, st))
            self.fill_player(env, E, k, p, st)
        if self.match:
            if now >= self.match["t_end"]:                                     # the game's own end was missed
                self.match_end("time")
                minqlx.console_command("abort")
        elif people and self.game is not None and self.game.state == "warmup" and now - self.go_t > 20:
            n = len([p for p in people if p.id in self.ready_ids])
            if n * 2 > len(people):                                            # more than half of the people are ready
                self.go_t = now
                self.ready_ids = set()
                minqlx.console_command("allready")                             # the game's countdown starts
        if not seated:
            return
        # the round clock (as in training: the clock, the score and the memory start over every ROUND_SECS)
        if now - self.sess_t0 > self.round_secs:
            self.sess_t0 = now
            self.h[:] = 0
            self.kills0 = {p.id: p.stats.kills for k, p, st in seated}
        env.round_t[0] = now - self.sess_t0
        for k, p, st in seated:
            env.frags_r[k] = p.stats.kills - self.kills0.get(p.id, p.stats.kills)
        # deaths and respawns
        noisy = np.zeros(SEATS, bool)
        hurt = {}
        for k, p, st in seated:
            bot = is_bot(p)
            up = st.health > 0
            was = self.alive.get(p.id)
            if up and not was:
                if bot:
                    if mapname == "testlab":                 # the test map has no weapons lying about; everywhere else the
                        self.give_loadout(p)                 # game's own spawn stands (he was handed every weapon on the duel
                                                             # maps, in real games too: owner, 2026-10-07)
                    env.life_t[k], env.flinch[k], env.focus[k] = 0.0, 0.0, E.FOCUS_SECS
                    env.mv[k], env.cool[k] = 0.0, 0.0
                    self.want_w.pop((id(env), k), None)
                    minqlx.set_bot_substeps(p.id, 3)
                    # his playing style for this life: one of the map's at random (owner, 2026-10-08: "for now spawn at
                    # random with each style"; choosing it himself comes with a later network); intention and hands anew
                    st_ = self.fresh_life(env, E, k)
                    if st_:
                        self.record(event="style", seat=k, style=st_)
                self.tot.pop(k, None)
                self.prev.pop(k, None)                       # (a respawn is not a teleport: no such sound)
                if hasattr(env, "dmg_on"):
                    env.dmg_on[:, k] = 0.0                   # what the others had done to him is gone with his old life
            if was and not up:
                env.note_death(k, -1)                        # those in earshot know; the killer is not known here
                self.record(event="death", seat=k, bot=bot, kills=p.stats.kills, deaths=p.stats.deaths)
            self.alive[p.id] = up
            # sounds: running steps, shots, jumps, teleports; what people fire is read from their commands
            pos, ground = env.state[k, :3].copy(), float(env.state[k, 6])
            fire = bool(self.fired[k]) if bot else bool(minqlx.ran_usercmd(p.id)[1] & 1) and int(st.weapon) != QLNUM["g"]
            noisy[k] = up and ((ground > 0.5 and math.hypot(env.state[k, 3], env.state[k, 4]) > 200.0) or fire)
            po = self.prev.get(k)
            if po is not None and up and self.rules2:
                if fire:
                    env._hear(1, np.array([k]))
                if po[1] > 0.5 and ground < 0.5 and env.state[k, 5] > 100:
                    env._hear(2, np.array([k]))
                if np.linalg.norm(pos - po[0]) > 200:
                    env._hear(3, np.array([k]))
                if hasattr(env, "note_shots"):               # his weapon lost ammo: he fired (Bobbys too: until 2026-10-08 only people's shots were noted)
                    wn_ = E.WEAPONS[int(env.weapon[k])] if int(env.weapon[k]) < len(E.WEAPONS) else "mg"
                    am_ = getattr(st.ammo, wn_, 0) if wn_ != "g" else 0
                    pa_ = self.ammo_prev.get(k)
                    if pa_ is not None and pa_[0] == wn_ and am_ < pa_[1]:
                        env.note_shots(np.array([k]))
                    self.ammo_prev[k] = (wn_, am_)
            self.prev[k] = (pos, ground)
            if not bot:
                env.duck[k] = minqlx.ran_usercmd(p.id)[5] < 0
            # damage taken (health + armor drops) -> flinch, pain sounds for those near, hit feedback
            tot = max(0, st.health) + st.armor
            prev = self.tot.get(k)
            if prev is not None and prev - tot >= 3 and prev > 0 and up:
                hurt[k] = int(prev - tot)
            self.tot[k] = tot
        self.n_present = int(present.sum())
        if hasattr(env, "hear"):
            env.hear(noisy & present)
        ids = [-1] * SEATS
        for k, p, st in seated:
            ids[k] = p.id
        for cls, slot in self.sync_world(env, E, ids):
            self.record(event="pickup", item=cls, seat=slot, bot=bool(slot >= 0 and ids[slot] >= 0 and is_bot(here[ids[slot]])))
            if slot >= 0 and self.rules2:
                self.took_chosen(env, E, slot, cls)
                if hasattr(env, "note_pickup") and cls in ("item_health_mega", "item_armor_body"):
                    env.note_pickup(slot, 0 if cls == "item_health_mega" else 1)
                big = 0 if cls == "item_health_mega" else 1 if cls == "item_armor_body" else \
                    2 if cls in ("item_armor_combat", "item_armor_jacket") else 3 if cls.startswith("weapon_") else None
                if big is not None:
                    env._hear(0, np.array([slot]), big)
        if self.rules2:
            env.snd_t += E.DT
            if hasattr(env, "resp_t"):
                env.resp_t += E.DT
            if hasattr(env, "shot_t"):
                env.shot_t += E.DT
                env.trail_t += E.DT
            if hasattr(env, "pain_t"):
                env.pain_t += E.DT
        bot_seats = [k for k, p, st in seated if is_bot(p)]
        for k, p, st in seated:                              # hit feedback and pain sounds
            bot = is_bot(p)
            took = hurt.get(k, 0)
            if bot and self.rules2:
                dealt_now = p.stats.damage_dealt
                dealt = max(0, dealt_now - self.dealt_prev.get(p.id, dealt_now))
                self.dealt_prev[p.id] = dealt_now
                foe = int(env.foe[k])
                ang = math.atan2(env.state[foe, 1] - env.state[k, 1], env.state[foe, 0] - env.state[k, 0]) - math.radians(float(env.yaw[k]))
                env.fb[k] = (min(dealt / 100.0, 2.0), min(took / 100.0, 2.0), math.sin(ang) * (took > 0), math.cos(ang) * (took > 0))
                env.dmg_life[k] += dealt
                if hasattr(env, "dmg_on"):                   # (the group simulator reads this one; it was never written: the game
                    env.dmg_on[k, foe] += dealt              # does not say whom he hit, so the enemy he attends to is charged)
                if took > 0 and hasattr(env, "note_hit") and getattr(env, "flinch_on", False):
                    env.note_hit(k, took)
            if took > 0 and hasattr(env, "pain_t"):
                for b in bot_seats:
                    if b != k and float(np.linalg.norm(env.state[b, :3] - env.state[k, :3])) < E.HEAR_EVT:
                        env.pain_t[b], env.pain_b[b] = 0.0, min(3, int(max(0, st.health)) // 25)
        self.senses_all(env, E, present)
        for k in bot_seats:
            env.weapon[k] = self.held(env, k)
        live_bots = [k for k, p, st in seated if is_bot(p) and st.health > 0]
        for k, p, st in seated:
            if is_bot(p) and st.health <= 0:                 # tap fire to respawn
                minqlx.set_bot_input(p.id, 0, 0, 0, int(now * 4) % 2, 0, 0.0, 0.0)
                self.fired[k] = False
        if people:                                           # the people's own frames too (owner, 2026-10-07: to learn aim habits
            for k, p, st in seated:                          # from): the same columns, bot = 0, the keys as the engine ran them
                if not is_bot(p) and st.health > 0:
                    c_ = minqlx.ran_usercmd(p.id)
                    keys_ = (int(np.sign(c_[3])), int(np.sign(c_[4])), int(np.sign(c_[5])), int(c_[1] & 1))
                    self.log_row(now, env, E, k, p, st, keys_, present, bot_seats, len(people), len(bobbys), bot=0)
        if not live_bots:
            return
        obs = env.observe()
        acts = self.act_batch(obs[live_bots], live_bots)
        if acts.shape[1] > 10 and hasattr(env, "intend"):
            choice = np.zeros(SEATS, np.int64)
            choice[live_bots] = acts[:, 10]
            env.intend(choice, np.isin(np.arange(SEATS), live_bots))
        self.intent_release(env, E, live_bots)
        by_seat = {k: (p, st) for k, p, st in seated}
        # The finger rules for all Bobbys in ONE call, as the simulator does. Until 2026-10-08 drive() called them once per
        # Bobby with his own row copied to every seat: with two or more Bobbys alive each one moved on the keys of the
        # Bobby handled before him, and the fire finger's clock ran once per Bobby (10.9 key changes a second in the
        # logs against 1.5 in 1v1).
        limited = hasattr(E, "ACQUIRE_FRAMES") and acts.shape[1] > 7 and hasattr(env, "limit_keys") and getattr(env, "key_limits", False)
        if limited:
            A = np.zeros((SEATS, acts.shape[1]), np.int64)
            A[:, 0] = A[:, 1] = 1
            A[live_bots] = acts
            env.limit_keys(A, who=np.isin(np.arange(SEATS), live_bots))
            acts = A[live_bots]
        for a, k in zip(acts, live_bots):
            p, st = by_seat[k]
            w, fire, pitch, yaw, keys = self.drive(p, env, E, k, a, float(env.pitch[k]), float(env.yaw[k]), limited=limited)
            self.fired[k] = bool(fire)
            if people or os.environ.get("FFA_LOG_ALWAYS"):       # frames are logged only while a person is in the game (FFA_LOG_ALWAYS=1: tests with bots alone)
                self.log_row(now, env, E, k, p, st, keys, present, bot_seats, len(people), len(bobbys))
            c = self.acc.setdefault(k, dict(frames=0, visible=0, fire=0, w={}))
            c["frames"] += 1
            c["visible"] += int(env.visible[k])
            c["fire"] += int(fire)
            c["w"][E.WEAPONS[w]] = c["w"].get(E.WEAPONS[w], 0) + 1
        self.last = {k: dict(bot=is_bot(p), hp=[st.health, st.armor], pos=[round(float(v)) for v in st.position],
                             intent=E.INTENTS[int(env.intent[k])] if hasattr(E, "INTENTS") and is_bot(p) else "")
                     for k, p, st in seated}
        if now > self.next_summary:
            self.next_summary = now + 60
            try:                                             # a floor: no frames or events with under 5 GB free on the disk
                self.disk_ok = __import__("shutil").disk_usage(D).free > 5e9
            except OSError:
                self.disk_ok = True
            for k, p, st in seated:
                if not is_bot(p) or not people:              # per-minute numbers only while a person is in the game
                    continue
                c = self.acc.get(k, dict(frames=0, visible=0, fire=0, w={}))
                f = max(1, c["frames"])
                self.record(event="minute", seat=k, visible=round(c["visible"] / f, 3), fire=round(c["fire"] / f, 3),
                            weapon_share={w_: round(v / f, 2) for w_, v in c["w"].items()}, kills=p.stats.kills, deaths=p.stats.deaths,
                            dmg_dealt=p.stats.damage_dealt, dmg_taken=p.stats.damage_taken, people=len(people), bots=len(bobbys))
                self.acc[k] = dict(frames=0, visible=0, fire=0, w={})

    @staticmethod
    def aim_to(env, i, j):
        """degrees between seat i's crosshair and the body of seat j"""
        to = env.state[j, :3] + np.array([0, 0, 4.0], np.float32) - env._eye(env.state)[i]
        yr, pr = math.radians(float(env.yaw[i])), math.radians(float(env.pitch[i]))
        f = np.array([math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), -math.sin(pr)])
        c = float((to * f).sum() / (np.linalg.norm(to) + 1e-6))
        return round(math.degrees(math.acos(max(-1.0, min(1.0, c)))), 2)

    def log_row(self, now, env, E, k, p, st, keys, present, bot_seats, n_people, n_bots, bot=1):
        if not getattr(self, "disk_ok", True):
            return
        foe = int(env.foe[k])
        row = [round(now, 3), minqlx.item_states()[0], bot, k, *self.player_row(p, st, keys), foe, int(foe in bot_seats),
               int(env.visible[k]), round(float(env.seen_t[k]), 2), self.aim_to(env, k, foe) if present[foe] else -1,
               E.INTENTS[int(env.intent[k])] if hasattr(E, "INTENTS") else "", n_people, n_bots]
        self.frames_f.write(",".join(str(v) for v in row) + "\n")
