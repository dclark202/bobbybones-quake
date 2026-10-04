"""duelbot: play a duel policy trained in the simulator (sim/train_duel_rnn.py) on the real Quake Live server.

BobbyBones is fully controlled by the network with human physics (3 moves per frame). His inputs are built by
the exact same code as in training (the simulator's observe()), fed from the real game: positions, health,
armor, weapons, ammo, the opponent's rockets, item states. The same fairness rules apply as in training: the
opponent is only known when in view with line of sight (150 ms late) or roughly when heard nearby.

Opponent: the first human on the server; with DUEL_OPP=bot a plain Nightmare bot fills in while no human
is there. Both players spawn with the loadout the policy trained with (MG, RL, RG, LG and a little ammo).

Load with QLX_PLUGINS="botctl, duelbot". Needs /tmp/practice/policy.npz (sim/export_duel.py).
Writes /tmp/practice/duel_live.jsonl (frags and a summary line every minute) and duelbot.log.
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
MAPS = ("bloodrun", "aerowalk", "campgrounds")
QL_WEAPON = (5, 7, 6, 2)                                    # simulator weapon index (RL, RG, LG, MG) -> game number
SIM_WEAPON = {5: 0, 7: 1, 6: 2, 2: 3}
SCHEMA = 1
_P = ["x", "y", "z", "vx", "vy", "vz", "pitch", "yaw", "health", "armor", "weapon", "ammo_rl", "ammo_rg", "ammo_lg",
      "fwd", "right", "up", "fire"]
FRAME_COLS = ["t", "server_ms", "drill"] + ["b_" + c for c in _P] + ["o_" + c for c in _P] + \
    ["b_sees", "b_seen_ago", "los", "b_aim_err", "o_aim_err", "missiles"]


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


class duelbot(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.add_command("map", self.cmd_map, 0, usage="<bloodrun|aerowalk|campgrounds>")
        self.add_command("note", self.cmd_note, 0, usage="<anything you noticed>")
        self.add_command("drill", self.cmd_drill, 0, usage="<rl|rg|lg|off>")
        self.drill = None                                    # weapon drill: both players have only this weapon
        self.top_up = 0.0
        self.last = {}                                       # latest snapshot of both players, for notes
        self.ready = False
        self.next_check = 0.0
        self.want_map = os.environ.get("LAB_MAP", "bloodrun").lower()
        self.opp_bot = os.environ.get("DUEL_OPP", "") == "bot"
        self.alive = {}                                      # client id -> was alive last frame
        self.score = dict(bobby=0, opp=0)
        self.acc = dict(frames=0, visible=0, fire=0, fast_air=0, w=[0, 0, 0, 0])
        self.next_summary = time.time() + 60
        self.err_t = 0.0
        self.sess, self.frames_f, self.sess_opp = None, None, None
        self.tot, self.item_was = {}, {}

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

    def aim_err(self, i):
        """degrees between player i's crosshair and the true direction to the other player's body"""
        env = self.env
        to = env.state[i ^ 1, :3] + np.array([0, 0, 4.0], np.float32) - env._eye(env.state)[i]
        yr, pr = math.radians(float(env.yaw[i])), math.radians(float(env.pitch[i]))
        f = np.array([math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), -math.sin(pr)])
        c = float((to * f).sum() / (np.linalg.norm(to) + 1e-6))
        return round(math.degrees(math.acos(max(-1.0, min(1.0, c)))), 2)

    def log_frame(self, now, bobby, opp, bs, os_, bcmd):
        env = self.env
        oc = minqlx.ran_usercmd(opp.id)                       # the opponent's real keys and buttons this frame
        eye = env._eye(env.state)
        los = bool(env._los(eye[:1], env.state[1:2, :3] + np.array([0, 0, 8.0], np.float32))[0])
        row = [round(now, 3), minqlx.item_states()[0], self.drill or "-",
               *self.player_row(bobby, bs, bcmd), *self.player_row(opp, os_, [oc[3], oc[4], oc[5], oc[1] & 1]),
               int(env.visible[0]), round(float(env.seen_t[0]), 2), int(los), self.aim_err(0), self.aim_err(1),
               len(minqlx.missiles())]
        self.frames_f.write(",".join(str(v) for v in row) + "\n")
        # damage events from health + armor drops
        for who, st, other in (("bobby", bs, os_), ("opp", os_, bs)):
            tot = max(0, st.health) + st.armor
            prev = self.tot.get(who)
            if prev is not None and prev - tot >= 3 and prev > 0:
                self.record(event="hit", victim=who, dmg=int(prev - tot), killed=bool(st.health <= 0),
                            attacker_weapon=int(other.weapon), victim_weapon=int(st.weapon),
                            dist=round(float(np.linalg.norm(env.state[0, :3] - env.state[1, :3]))), los=los,
                            drill=self.drill)
            self.tot[who] = tot

    def cmd_map(self, player, msg, channel):
        if len(msg) < 2 or msg[1].lower() not in MAPS:
            return minqlx.RET_USAGE
        self.want_map = msg[1].lower()
        minqlx.console_command("map {} duel".format(self.want_map))

    def cmd_note(self, player, msg, channel):
        """the play-tester's feedback, stamped with the game state at that moment"""
        if len(msg) < 2:
            return minqlx.RET_USAGE
        self.record(event="note", text=" ".join(msg[1:]), drill=self.drill, state=self.last, **self.score)
        player.tell("noted")

    def cmd_drill(self, player, msg, channel):
        if len(msg) < 2 or msg[1].lower() not in ("rl", "rg", "lg", "off"):
            return minqlx.RET_USAGE
        self.drill = None if msg[1].lower() == "off" else msg[1].lower()
        self.record(event="drill", drill=self.drill, **self.score)
        for p in self.players():
            if p.team != "spectator" and p.state and p.state.health > 0:
                self.give_loadout(p)
        self.msg("Drill: {}".format(self.drill or "off (normal loadout)"))

    def on_map(self, mapname, factory):
        self.end_session()
        self.ready = False
        self.alive = {}

    # ------------------------------------------------------------------ setup
    def setup(self):
        mapname = (minqlx.get_cvar("mapname") or "").lower()
        bsp = "/tmp/maps/{}.bsp".format(mapname)
        if not os.path.exists(bsp):
            os.makedirs("/tmp/maps", exist_ok=True)
            with open(bsp, "wb") as f:
                f.write(zipfile.ZipFile("/ql/baseq3/pak00.pk3").read("maps/{}.bsp".format(mapname)))
        P = np.load(os.path.join(D, "policy.npz"))
        self.P = {k: P[k] for k in P.files}
        self.dims = [int(x) for x in self.P["action_dims"]]
        self.E = E = importlib.import_module(str(self.P["env"]))
        self.env = E.DuelEnv(bsp, n_matches=1, seed=1)
        self.react_ms = float(self.P["react_ms"]) if "react_ms" in self.P else E.REACT_FRAMES * 25.0
        self.env.react_frames = round(self.react_ms / 25)   # same reaction delay as in training (newer simulators)
        self.h = np.zeros((1, self.P["whh"].shape[1]), np.float32)
        self.refire = np.array([E.REFIRE, E.RG_REFIRE, E.LG_TICK, E.MG_TICK], np.float32)
        self.item_ent = {}                                   # game entity number -> simulator item index
        self.ready = True
        self.log("ready on {}: policy {} ({} min of training), {} inputs".format(
            mapname, self.P["run"], int(self.P["minutes"]), E.OBS_DIM))

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

    # ------------------------------------------------------------------ players
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
        return bobby, human, filler

    def give_loadout(self, p):
        try:
            if self.drill:                                   # as in training: one weapon, ammo never runs out
                p.weapons(reset=True, **{self.drill: True})
                p.ammo(**{self.drill: 150 if self.drill == "lg" else 25})
                p.weapon({"rl": 5, "rg": 7, "lg": 6}[self.drill])
                return
            has, ammo = self.E.LOADOUTS["full"]
            p.weapons(reset=True, g=True, mg=True, rl=bool(has[0]), rg=bool(has[1]), lg=bool(has[2]))
            p.ammo(mg=100, rl=int(ammo[0]), rg=int(ammo[1]), lg=int(ammo[2]))
        except Exception as e:
            self.log("loadout error: {!r}".format(e))

    def fill_player(self, i, p, st):
        """copy one real player's state into simulator slot i; returns (pos, vel, ground, pitch, yaw)"""
        env = self.env
        pos = np.array(st.position, np.float32)
        vel = np.array(st.velocity, np.float32)
        floor = env.w.rays(pos[None], np.array([[0, 0, -1.0]], np.float32), 30.0)[0, 0] < 1
        ground = 1.0 if (abs(vel[2]) < 1 and floor) else 0.0
        va = minqlx.view_angles(p.id)
        pitch, yaw = float(va[0]), float(va[1])
        env.state[i] = [*pos, *vel, ground, yaw]
        env.yaw[i], env.pitch[i] = yaw, pitch
        env.hp[i], env.armor[i] = st.health, st.armor
        env.weapon[i] = SIM_WEAPON.get(int(st.weapon), 3)
        env.has[i] = [bool(st.weapons.rl), bool(st.weapons.rg), bool(st.weapons.lg)]
        env.ammo[i] = [max(0, st.ammo.rl), max(0, st.ammo.rg), max(0, st.ammo.lg)]
        return pos, vel, ground, pitch, yaw

    def sync_world(self, bobby, opp):
        """rockets in flight and item states from the real game into the simulator"""
        env, E = self.env, self.E
        env.ra[:] = False
        for owner, slot in ((opp.id, 1), (bobby.id, 0)):
            k = 0
            for num, own, weapon, x, y, z, vx, vy, vz in minqlx.missiles():
                if own == owner and weapon == 5 and k < E.K:
                    env.rp[slot, k] = (x, y, z)
                    env.rv[slot, k] = (vx, vy, vz)
                    env.ra[slot, k] = True
                    k += 1
        if env.nI:
            for num, cls, x, y, z, up, _ in minqlx.item_states()[1]:
                k = self.item_ent.get(num)
                if k is None:
                    d = np.linalg.norm(env.item_pos - np.array([x, y, z], np.float32), axis=1)
                    k = self.item_ent[num] = int(d.argmin()) if d.min() < 40 else -1
                if k >= 0:
                    env.item_up[0, k] = bool(up)
                if self.item_was.get(num, up) and not up:    # an item was just taken: by the nearer player
                    d = np.linalg.norm(env.state[:, :3] - np.array([x, y, z], np.float32), axis=1)
                    self.record(event="pickup", item=cls, by=("bobby", "opp")[int(d.argmin())] if d.min() < 120 else "?")
                self.item_was[num] = up

    def senses(self):
        """sight (line of sight + field of view) and hearing, same rules as the simulator's step()"""
        env, E = self.env, self.E
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
        bobby, human, filler = self.cast()
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
            return
        env, E = self.env, self.E
        if self.sess is None or self.sess_opp != opp.id:
            self.start_session(opp)
        bs, os_ = bobby.state, opp.state
        if bs is None or os_ is None:
            return
        # deaths and respawns
        for p, st, who in ((bobby, bs, "bobby"), (opp, os_, "opp")):
            up = st.health > 0
            was = self.alive.get(p.id)
            if up and not was:
                self.give_loadout(p)
                self.tot.pop(who, None)
                if who == "bobby":
                    self.h[:] = 0
                    env.mv[0] = 0
                    env.cool[0] = 0
                    env.seen_t[0] = 9.0
                    env.opp_hist = []
                    minqlx.set_bot_substeps(bobby.id, 3)
            if was and not up:
                other = "opp" if who == "bobby" else "bobby"
                self.score[other] += 1
                self.record(event="death", who=who, drill=self.drill, state=self.last, **self.score)
            self.alive[p.id] = up
        if bs.health <= 0:                                   # tap fire to respawn
            minqlx.set_bot_input(bobby.id, 0, 0, 0, int(now * 4) % 2, 0, 0.0, 0.0)
            self.fill_player(0, bobby, bs)
            self.fill_player(1, opp, os_)
            env.visible[:] = False
            self.log_frame(now, bobby, opp, bs, os_, [0, 0, 0, 0])
            return
        if self.drill and now > self.top_up:
            self.top_up = now + 2
            for p in (bobby, opp):
                p.ammo(**{self.drill: 150 if self.drill == "lg" else 25})
        pos, vel, ground, pitch, yaw = self.fill_player(0, bobby, bs)
        opos = self.fill_player(1, opp, os_)[0]
        self.sync_world(bobby, opp)
        self.senses()
        a = self.act(env.observe()[:1])
        fwd, side, jump = (a[0] - 1) * 127, (a[1] - 1) * 127, a[2] * 127
        env.mv[0] = E.MOUSE_SMOOTH * env.mv[0] + (1.0 - E.MOUSE_SMOOTH) * np.array([E.TURN[a[3]], E.PITCH[a[4]]])
        yaw = (yaw + float(env.mv[0, 0]) + 180.0) % 360.0 - 180.0
        pitch = float(np.clip(pitch * env.level + env.mv[0, 1], -89, 89))
        w = int(env.weapon[0])
        if self.drill:                                       # drill rounds have no machine gun, as in training
            w = ("rl", "rg", "lg").index(self.drill)
        if a[6] > 0:                                         # switch only to weapons owned
            want = a[6] - 1
            if ((want == 3 and not self.drill) or (want < 3 and env.has[0, want])) and want != w:
                w = want
                env.cool[0] = max(env.cool[0], E.SWITCH)
        fire = a[5] == 1
        env.cool[0] = max(0.0, env.cool[0] - E.DT)
        if fire and env.cool[0] <= 0 and (w == 3 or env.ammo[0, w] > 0):
            env.cool[0] = self.refire[w]
        minqlx.set_bot_input(bobby.id, fwd, side, jump, 1 if fire else 0, QL_WEAPON[w], pitch, yaw)
        self.last = dict(bobby=[round(float(v)) for v in pos], opp=[round(float(v)) for v in opos],
                         bobby_hp=[bs.health, bs.armor], opp_hp=[os_.health, os_.armor], weapon=E.WEAPONS[w],
                         visible=bool(env.visible[0]), seen_ago=round(float(env.seen_t[0]), 1))
        self.log_frame(now, bobby, opp, bs, os_, [fwd, side, jump, int(fire)])
        c = self.acc
        c["frames"] += 1
        c["visible"] += int(env.visible[0])
        c["fire"] += int(fire)
        c["w"][w] += 1
        c["fast_air"] += int(math.hypot(vel[0], vel[1]) > 330 and not ground)
        if now > self.next_summary:
            self.next_summary = now + 60
            f = max(1, c["frames"])
            self.record(event="minute", visible=round(c["visible"] / f, 3),
                        fire=round(c["fire"] / f, 3), fast_air=round(c["fast_air"] / f, 3), weapon_share=[round(x / f, 2) for x in c["w"]],
                        dmg_dealt=bobby.stats.damage_dealt, dmg_taken=bobby.stats.damage_taken, **self.score)
            self.acc = dict(frames=0, visible=0, fire=0, fast_air=0, w=[0, 0, 0, 0])
