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


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


class duelbot(minqlx.Plugin):
    def __init__(self):
        self.add_hook("frame", self.on_frame)
        self.add_hook("map", self.on_map)
        self.add_command("map", self.cmd_map, 0, usage="<bloodrun|aerowalk|campgrounds>")
        self.ready = False
        self.next_check = 0.0
        self.want_map = os.environ.get("LAB_MAP", "bloodrun").lower()
        self.opp_bot = os.environ.get("DUEL_OPP", "") == "bot"
        self.alive = {}                                      # client id -> was alive last frame
        self.score = dict(bobby=0, opp=0)
        self.acc = dict(frames=0, visible=0, fire=0, fast_air=0, w=[0, 0, 0, 0])
        self.next_summary = time.time() + 60
        self.err_t = 0.0

    def log(self, msg):
        minqlx.console_print("[duelbot] " + msg + "\n")
        with open(os.path.join(D, "duelbot.log"), "a") as f:
            f.write("{} {}\n".format(time.strftime("%H:%M:%S"), msg))

    def record(self, **rec):
        rec["t"] = round(time.time(), 2)
        rec["map"] = (minqlx.get_cvar("mapname") or "").lower()
        with open(os.path.join(D, "duel_live.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")

    def cmd_map(self, player, msg, channel):
        if len(msg) < 2 or msg[1].lower() not in MAPS:
            return minqlx.RET_USAGE
        self.want_map = msg[1].lower()
        minqlx.console_command("map {} duel".format(self.want_map))

    def on_map(self, mapname, factory):
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
            return
        env, E = self.env, self.E
        bs, os_ = bobby.state, opp.state
        if bs is None or os_ is None:
            return
        # deaths and respawns
        for p, st, who in ((bobby, bs, "bobby"), (opp, os_, "opp")):
            up = st.health > 0
            was = self.alive.get(p.id)
            if up and not was:
                self.give_loadout(p)
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
                self.record(event="death", who=who, vs=opp.clean_name, human=not is_bot(opp), **self.score)
            self.alive[p.id] = up
        if bs.health <= 0:                                   # tap fire to respawn
            minqlx.set_bot_input(bobby.id, 0, 0, 0, int(now * 4) % 2, 0, 0.0, 0.0)
            return
        _, vel, ground, pitch, yaw = self.fill_player(0, bobby, bs)
        self.fill_player(1, opp, os_)
        self.sync_world(bobby, opp)
        self.senses()
        a = self.act(env.observe()[:1])
        fwd, side, jump = (a[0] - 1) * 127, (a[1] - 1) * 127, a[2] * 127
        env.mv[0] = E.MOUSE_SMOOTH * env.mv[0] + (1.0 - E.MOUSE_SMOOTH) * np.array([E.TURN[a[3]], E.PITCH[a[4]]])
        yaw = (yaw + float(env.mv[0, 0]) + 180.0) % 360.0 - 180.0
        pitch = float(np.clip(pitch * env.level + env.mv[0, 1], -89, 89))
        w = int(env.weapon[0])
        if a[6] > 0:                                         # switch only to weapons owned
            want = a[6] - 1
            if (want == 3 or env.has[0, want]) and want != w:
                w = want
                env.cool[0] = max(env.cool[0], E.SWITCH)
        fire = a[5] == 1
        env.cool[0] = max(0.0, env.cool[0] - E.DT)
        if fire and env.cool[0] <= 0 and (w == 3 or env.ammo[0, w] > 0):
            env.cool[0] = self.refire[w]
        minqlx.set_bot_input(bobby.id, fwd, side, jump, 1 if fire else 0, QL_WEAPON[w], pitch, yaw)
        c = self.acc
        c["frames"] += 1
        c["visible"] += int(env.visible[0])
        c["fire"] += int(fire)
        c["w"][w] += 1
        c["fast_air"] += int(math.hypot(vel[0], vel[1]) > 330 and not ground)
        if now > self.next_summary:
            self.next_summary = now + 60
            f = max(1, c["frames"])
            self.record(event="minute", vs=opp.clean_name, human=not is_bot(opp), visible=round(c["visible"] / f, 3),
                        fire=round(c["fire"] / f, 3), fast_air=round(c["fast_air"] / f, 3), weapon_share=[round(x / f, 2) for x in c["w"]],
                        dmg_dealt=bobby.stats.damage_dealt, dmg_taken=bobby.stats.damage_taken, **self.score)
            self.acc = dict(frames=0, visible=0, fire=0, fast_air=0, w=[0, 0, 0, 0])
