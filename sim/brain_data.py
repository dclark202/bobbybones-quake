"""(brainppl, 2026-10-24) data for the brain's lesson on how PEOPLE play: Bobby's senses frame by frame and the truth of the
enemy (a person), in the trainer's own layout, so that the brain (belief.*) and its readouts (track.*, trackz.*, ahead.*) can be
taught offline (sim/brain_fit.py) or in a run (the trainer's --brain-human).

    python sim/brain_data.py session <session folder or .tar.gz> ... --ck <policy.pt> --out <dir>      # people's games, replayed
    python sim/brain_data.py sim --map bloodrun --matches 4 --minutes 10 --ck <policy.pt> --out <dir> [--write-sessions <dir>]
    python sim/brain_data.py check <sim shard> <replayed shard>    # the replay of a simulator game against the simulator's own

A shard (npz): obs [T, S, OBS_DIM] float16 (the raw inputs of the seat whose senses they are: Bobby), done [T, S] (his memory and
the brain are cleared after this frame: his death, a cut), aux [T + 1, S, len(COLS)] float32 (info["aux"]'s columns of the
same names, as the trainer keeps them: row t comes with the inputs of frame t; the last row repeats the last frame), meta.
S streams side by side (a simulator shard: every seat; a session: one). As in the trainer's whole games, done is set at a
game's end (a session: a game's end or a cut), not at a death; a session's frames while Bobby is dead are left out (the
simulator's stream has them, with his inputs of the respawn wait). The trainer's labels are made from aux by the
modules' own code (track.COLS, track_z.COLS, ahead.labels).

Sessions (frames.csv, events.jsonl, missiles.csv): replayed with sim/head_data.py's Feeder (the 1v1 plugin's frame()
without the game), Bobby seat 0, the person seat 1; what the logs do not have is as head_data.py says (ammunition beyond RL /
RG / LG, item timers from the pickups). Changes here: the weapons owned are those picked up (events.jsonl) or seen in hand
since the spawn (the logged ammunition is not ownership: the game counts ammo for weapons not held); the person's life clock
starts at his spawn (the readout's 0.2 s velocity window is cleared there); the aux columns are env.aux() of the replayed
state after the frame's observe(); frag / fragged mark the person's and Bobby's deaths. The target ("what he goes for"): a
network seat's own intention in the simulator; for a person, unknown: the intention-list item (MH, RA, RL, RG, LG, YA, YA2)
he picks up next within TARGET_S seconds and before his death, -1 (no label) otherwise (column en_target; the simulator's
own is kept in en_target_sim of a simulator shard, beside the same proxy in en_target_ppl).
No names, Steam ids or addresses are read or written.
"""
import argparse
import csv
import glob
import importlib
import json
import math
import os
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

DT = 0.025
TARGET_S = 15.0
# the columns the brain's lessons read (track.COLS, track_z.COLS, ahead.COLS + COLS_RACE; asserted equal in brain_fit.py, which
# has torch: simulator workers must not import it), and the counters' extras
TRACK_COLS = ("en_fwd", "en_left", "en_up", "en_vfwd", "en_vleft", "en_band", "en_weapon", "en_own_rl", "en_own_rg", "en_own_lg",
              "en_own_pg", "en_own_gl", "en_own_sg")
TRZ_COLS = ("en_zone", "zone_n", "en_spd8", "en_mvf8", "en_mvl8")
AHEAD_COLS = ("en_fwd", "en_left", "en_up", "x", "y", "z", "yaw", "en_in_view", "en_target", "frag", "fragged", "trk_on",
              "mega_s", "red_s", "race_me_mh", "race_en_mh", "race_me_ra", "race_en_ra")
EXTRA = ("unseen_s", "zone_seen", "en_alive", "bel_ok", "bel_fwd", "bel_left", "bel_up", "zone_map", "hp_me", "en_hp")
COLS = tuple(dict.fromkeys(TRACK_COLS + TRZ_COLS + AHEAD_COLS + EXTRA + ("en_target_sim", "en_target_ppl", "src_demo", "trk_game")))
# src_demo (a demo's rows: 1): the enemy's truth only while the demo has him (trk_on is 0 elsewhere); his health and armor and
# his weapons owned are not in a demo (the lessons' band and own parts are silent on these rows), nor the item race
TRUTH_VARS = dict(TRACK_TRUTH="1", TRACK_Z="1", TRACK_RACE="1")
BIG_LABS = ("MH", "RA", "RL", "RG", "LG", "YA", "YA2")
QL_NUM = {"g": 1, "mg": 2, "sg": 3, "gl": 4, "rl": 5, "lg": 6, "rg": 7, "pg": 8, "hmg": 14}


LEGS_NET = os.path.join(ROOT, "data", "sim_runs", "move_v17_look", "policy.npz")     # (the run's LEGS_NET: the movement network, an input)


def env_vars_of(ck_path):
    import head_data as HD
    spec = HD.env_spec(ck_path)
    spec["env_vars"] = dict(spec["env_vars"], **TRUTH_VARS)
    if os.path.exists(LEGS_NET):
        spec["env_vars"].setdefault("LEGS_NET", os.environ.get("LEGS_NET") or LEGS_NET)
    return spec


def aux_row(env, E, C, a=None):
    """env.aux()'s columns of COLS (the extras by hand) for every seat: [n, len(COLS)] float32 (a: the step's info["aux"],
    which has the frame's events: frag, fragged)"""
    a = env.aux() if a is None else a
    AC = {k: i for i, k in enumerate(E.AUX_COLS)}
    out = np.zeros((env.n, len(COLS)), np.float32)
    for j, k in enumerate(COLS):
        if k in AC:
            out[:, j] = a[:, AC[k]]
    out[:, C["hp_me"]] = env.hp[:env.n]
    foe = env._others_arr()[:, 0]
    out[:, C["en_hp"]] = env.hp[foe]
    out[:, C["en_target_sim"]] = out[:, C["en_target"]]
    return out


def target_proxy(n_frames, picks, deaths, horizon=TARGET_S):
    """[n_frames] INTENTS index of the next big pickup (picks: [(frame, intent)] sorted) within horizon seconds and before the
    next death (deaths: sorted frames of his deaths), else -1"""
    out = np.full(n_frames, -1, np.int64)
    hf = int(round(horizon / DT))
    pf = np.array([p for p, _ in picks], np.int64)
    pk = np.array([k for _, k in picks], np.int64)
    dth = np.array(sorted(deaths), np.int64)
    if not len(pf):
        return out
    f = np.arange(n_frames)
    j = np.searchsorted(pf, f, side="right")                 # the first pickup after frame f
    ok = j < len(pf)
    jj = np.minimum(j, len(pf) - 1)
    nxt = pf[jj]
    dj = np.searchsorted(dth, f, side="left") if len(dth) else np.zeros(n_frames, np.int64)
    nd = np.where(dj < len(dth), dth[np.minimum(dj, max(0, len(dth) - 1))] if len(dth) else 1 << 40, 1 << 40)
    ok &= (nxt - f <= hf) & (nxt <= nd)
    out[ok] = pk[jj[ok]]
    return out


# ---------------------------------------------------------------------------------------------------------- sessions
def replay_session(spec, sess, seed=1, max_frames=0, games_only=False, record_xl=False):
    """a 1v1 session with a person, Bobby's seat -> dict(obs [F, D] f16, done [F], aux [F, C], t [F], row [F]) of his
    living frames, or (None, why)"""
    import head_data as HD
    meta_s = json.load(open(os.path.join(sess, "meta.json")))
    mp = meta_s["map"]
    if meta_s.get("opponent") not in ("human", "spar") or meta_s.get("kind") == "ffa":
        return None, "not 1v1"
    c, body = HD.read_frames(sess)
    if len(body) < 400:
        return None, "short"
    if max_frames:
        body = body[:max_frames]
    events = HD.read_events(sess)
    games = HD.session_games(events)
    E, env = HD.make_env(spec, mp, seed)
    C = {k: i for i, k in enumerate(COLS)}
    names = E.WEAPONS
    NW = len(names)
    qln = {5: "rl", 7: "rg", 6: "lg", 2: "mg", 3: "sg", 4: "gl", 8: "pg", 14: "hmg", 1: "g"}
    lt_, li_ = None, None                                    # (an input log: his own intention as the network chose it, held between
    fl_ = sorted(glob.glob(os.path.join(sess, "inputs_*.npz")))     # the logged frames; else the item rule's)
    if fl_:
        try:
            zs_ = [np.load(f_) for f_ in fl_]
            ac_ = np.concatenate([z_["acts"] for z_ in zs_])
            if ac_.shape[1] > 10:
                lt_ = np.concatenate([z_["t"] for z_ in zs_]).astype(np.float64)
                li_ = ac_[:, 10].astype(np.int64)
                o_ = np.argsort(lt_, kind="stable")
                lt_, li_ = lt_[o_], np.clip(li_[o_], 0, len(E.INTENTS) - 1)
        except (OSError, ValueError, KeyError):
            lt_ = li_ = None
    F = HD.Feeder(E, env, "rule" if lt_ is None else "log")
    it_intent, _ = HD.item_classes(env, E)
    pick = [(float(e["t"]), e["item"], e.get("by")) for e in events if e.get("event") == "pickup"]
    pi = 0
    miss_rows = {}
    mp_path = os.path.join(sess, "missiles.csv")
    if os.path.exists(mp_path):
        for r in csv.DictReader(open(mp_path)):
            miss_rows.setdefault(r["t"], []).append(r)
    born = {}
    me, en = HD.Player(NW), HD.Player(NW)
    owned = [set(), set()]
    tot = [None, None]
    score = [0, 0]
    clock0 = float(body[0][c["t"]])
    game_i = None
    alive_prev = [None, None]
    obs, aux, done, ts, rows, ingame, xls = [], [], [], [], [], [], []
    picks_en, deaths_en = [], []                              # (frames of the shard: the person's big pickups, his deaths)
    pending_frag = [0.0, 0.0]                                # (frag: the person died; fragged: Bobby died) on the next row kept

    def fill(p, pre, k, row):
        p.pos = np.array([float(row[c[pre + "_x"]]), float(row[c[pre + "_y"]]), float(row[c[pre + "_z"]])], np.float32)
        p.vel = np.array([float(row[c[pre + "_vx"]]), float(row[c[pre + "_vy"]]), float(row[c[pre + "_vz"]])], np.float32)
        p.pitch, p.yaw = float(row[c[pre + "_pitch"]]), float(row[c[pre + "_yaw"]])
        p.hp, p.armor = float(row[c[pre + "_health"]]), float(row[c[pre + "_armor"]])
        p.alive = p.hp > 0 and not (p.pos == 0).all()
        p.hp = max(0.0, p.hp)
        wn = qln.get(int(float(row[c[pre + "_weapon"]])), "mg")
        p.w = names.index(wn)
        if not p.alive:
            owned[k].clear()
        owned[k].update(("mg", "g", wn))
        p.has[:] = False
        p.ammo[:] = 0.0
        for nm in owned[k]:
            p.has[names.index(nm)] = True
            p.ammo[names.index(nm)] = HD.TYPICAL_AMMO.get(nm, 0.0)
        for nm in ("rl", "rg", "lg"):
            if nm in owned[k]:
                p.ammo[names.index(nm)] = max(0.0, float(row[c["{}_ammo_{}".format(pre, nm)]]))
        p.duck = float(row[c[pre + "_up"]]) < 0
        p.fire = float(row[c[pre + "_fire"]]) > 0
        p.present = True
        p.ground = None

    for fi, row in enumerate(body):
        t = float(row[c["t"]])
        # the frame's pickups first: a weapon picked up is owned from this frame on
        taken = []
        while pi < len(pick) and pick[pi][0] <= t:
            _, cls, by = pick[pi]
            pi += 1
            st_ = 0 if by == "bobby" else 1 if by == "opp" else -1
            if st_ < 0 or cls not in E.ITEM_DEFS:
                continue
            d_ = E.ITEM_DEFS[cls]
            if d_[0] == "wp":
                owned[st_].add(names[int(d_[1])])
            pre = "b" if st_ == 0 else "o"
            pp = np.array([float(row[c[pre + "_x"]]), float(row[c[pre + "_y"]]), float(row[c[pre + "_z"]])], np.float32)
            cand = [k for k in range(env.nI) if env.item_def[k] == d_]
            if not cand:
                continue
            k = min(cand, key=lambda k_: float(np.linalg.norm(env.item_pos[k_] - pp)))
            taken.append((st_, int(k)))
            if st_ == 1 and it_intent[k] >= 0 and E.INTENTS[int(it_intent[k])] in BIG_LABS:
                picks_en.append((len(obs), int(it_intent[k])))
        fill(me, "b", 0, row)
        fill(en, "o", 1, row)
        if en.alive and not alive_prev[1]:                   # (the person's life clock: his readout window starts again)
            env.life_t[1] = 0.0
        gi = next((j for j, g in enumerate(games) if g[0] <= t <= g[1]), None)
        game_new = False
        if gi != game_i:
            if gi is not None:
                game_new = True
                clock0 = games[gi][0]
            else:
                clock0 = t
            score = [0, 0]
            if done:
                done[-1] = True
            game_i = gi
        elif t - clock0 > 600.0 and gi is None:
            clock0 = t
            score = [0, 0]
            if done:
                done[-1] = True
        clock = t - clock0
        dmg = [0.0, 0.0]
        for i, p in enumerate((me, en)):
            tt = max(0.0, p.hp) + p.armor
            if p.alive and not alive_prev[i]:
                tot[i] = None
            if tot[i] is not None and tot[i] - tt >= 3 and tot[i] > 0:
                dmg[i] = tot[i] - tt
            tot[i] = tt
            if alive_prev[i] and not p.alive:
                score[1 - i] += 1
                if i == 0:                                   # Bobby died (in whole games the trainer's done is not set at a death:
                    pending_frag[1] = 1.0                    # his memory and the brain go on; only a game's end or a cut clears them)
                else:
                    deaths_en.append(len(obs))
                    pending_frag[0] = 1.0
            alive_prev[i] = p.alive
        miss = []
        kinds = {5: E.RL, 4: E.GL, 8: E.PG}
        live_ = set()
        for r in miss_rows.get(row[c["t"]], []):
            w_ = int(r["weapon"])
            who = int(r["owner"])
            if w_ not in kinds or who not in (0, 1):
                continue
            num = int(r["num"])
            live_.add(num)
            age = t - born.setdefault(num, t)
            miss.append((who, kinds[w_], np.array([float(r["x"]), float(r["y"]), float(r["z"])], np.float32),
                         np.array([float(r["vx"]), float(r["vy"]), float(r["vz"])], np.float32), age))
        for num in [n_ for n_ in born if n_ not in live_]:
            del born[num]
        if lt_ is not None:
            q_ = np.searchsorted(lt_, t, side="right") - 1
            F.intent_next = np.array([li_[q_] if q_ >= 0 else 0, 0], np.int64)
        ob = F.frame(me, en, clock, (score[0], score[1]), taken=taken, missiles=miss, dealt=dmg[1], took=dmg[0], items=None,
                     game_new=game_new)
        env._trk_step()                                      # (as step(): once a frame, after the senses)
        if ob is None:
            continue
        ar = aux_row(env, E, C)[0]
        ar[C["frag"]], ar[C["fragged"]] = pending_frag
        pending_frag = [0.0, 0.0]
        obs.append(ob.astype(np.float16))
        if record_xl:                                        # (the play effect: the legs' inputs as the plugin takes them, after observe and intend)
            xls.append(env.legs_prep()[0].astype(np.float16))
        aux.append(ar)
        done.append(False)
        ts.append(t)
        rows.append(fi)
        ingame.append(gi is not None)
    if len(obs) < 400:
        return None, "short"
    obs = np.stack(obs)
    aux = np.stack(aux)
    done = np.asarray(done, bool)
    done[-1] = True
    tp = target_proxy(len(obs), picks_en, deaths_en)
    aux[:, C["en_target"]] = tp
    aux[:, C["en_target_ppl"]] = tp
    aux[:, C["en_target_sim"]] = -1
    ingame = np.asarray(ingame, bool)
    if games_only:
        aux[~ingame, C["trk_on"]] = 0.0
    meta = dict(source="session", map=mp, name=os.path.basename(sess), policy=meta_s.get("policy"), env=spec["env"],
                games=len(games), frames=len(obs), intent="log" if lt_ is not None else "rule", frames_in_games=int(ingame.sum()), people=len(meta_s.get("people") or []))
    out = dict(obs=obs, done=done, aux=aux, t=np.asarray(ts), row=np.asarray(rows, np.int64), ingame=ingame, meta=meta)
    if record_xl:
        out["xl"] = np.stack(xls)
    return out, "ok"


def save_shard(path, d, streams=False):
    """one stream ([F, ...]) or many ([T, S, ...]) -> the shard layout ([T, S, ...]; aux T + 1 rows)"""
    obs, done, aux = d["obs"], d["done"], d["aux"]
    if not streams:
        obs, done, aux = obs[:, None], done[:, None], aux[:, None]
    aux = np.concatenate([aux, aux[-1:]], 0)
    extra = {k: v for k, v in d.items() if k not in ("obs", "done", "aux", "meta")}
    np.savez(path, obs=obs, done=done, aux=aux.astype(np.float32), meta=json.dumps(dict(d["meta"], cols=list(COLS))), **extra)
    return path


# ---------------------------------------------------------------------------------------------------------- pro demos
RACE_CAP_ = 30.0


def replay_demo(spec, mp, path, seed=1, max_frames=0):
    """a pro demo, the recording (followed) player's senses: sim/head_data.py build_demo's feeding, the brain's columns.
    The enemy's truth only while the demo sends him (in the recorder's PVS): trk_on = sent, both alive, in a game. Labels
    that need the hidden path stay out by that mask (ahead's places need him sent at both ends). -> (dict, why)"""
    import hashlib
    import shutil
    import head_data as HD
    import demo_dataset as DS
    import demo_reader as D
    tmp = os.path.join(ROOT, "scratch", "dd_{}".format(os.getpid()))
    os.makedirs(tmp, exist_ok=True)
    try:
        d, Ev, R = HD.parse_demo(path, tmp)
    except Exception as e:                                   # noqa: BLE001
        return None, "parse " + repr(e)[:100]
    N = len(d["time"])
    if N < 800:
        return None, "short"
    t_ms = DS.exact_times(os.path.join(tmp, "d.bin"), d["time"])
    E, env = HD.make_env(spec, mp, seed)
    C = {k: i for i, k in enumerate(COLS)}
    names = E.WEAPONS
    NW = len(names)
    F = HD.Feeder(E, env, "rule")
    F.count_frags = False
    it_intent, _ = HD.item_classes(env, E)
    wslot, aslot = DS.stat_layout(d)
    normal = int(np.bincount(d["pm_type"].clip(0, 15)).argmax())
    games, lst, changes = HD.demo_games(Ev, R, N)
    picks = HD.demo_pickups(Ev, R)
    ps = d["ps"]
    me_cl = d["clientNum"]
    item_near = {}
    prev_cl, prev_t = None, None
    me, en = HD.Player(NW), HD.Player(NW)
    en_cl = -1
    score = {}
    ci = 0
    mi = d.get("missiles")
    g_cur = None
    obs, aux, done, ts = [], [], [], []
    picks_en, deaths_en = [], []
    pk_stat = {}
    pend = [0.0, 0.0]
    en_was = False
    dts = np.diff(np.asarray(t_ms, np.float64))
    for k in range(min(N, max_frames) if max_frames else N):
        tm = int(t_ms[k])
        cl = int(me_cl[k])
        playing = d["pm_type"][k] == normal
        gi = next((j for j, (s0, e) in enumerate(games) if s0 <= k and (e is None or k <= e)), None)
        game_new = gi is not None and gi != g_cur
        if gi != g_cur:
            score = {}
            if prev_cl is not None and done:
                done[-1] = True
            g_cur = gi
        if prev_cl is not None and (cl != prev_cl or tm - prev_t > 1000):
            if done:
                done[-1] = True
            F.alive = [None, None]
            F.ground_was = None
        prev_cl, prev_t = cl, tm
        while ci < len(changes) and changes[ci][0] <= k:
            if gi is not None:
                score[changes[ci][1]] = score.get(changes[ci][1], 0) + changes[ci][2]
            if changes[ci][1] == cl and changes[ci][2] > 0:
                F.frag_next += 1.0
                pend[0] = 1.0                                # (he fragged: the enemy died)
                deaths_en.append(len(obs))
            ci += 1
        s_ = d["stats"][k]
        alive_was = me.alive
        me.alive = bool(playing and s_[0] > 0)
        me.pos, me.vel = d["origin"][k].astype(np.float32), d["velocity"][k].astype(np.float32)
        me.pitch, me.yaw = float(d["angles"][k][0]), float(d["angles"][k][1])
        hp_was = me.hp + me.armor
        me.hp, me.armor = float(max(s_[0], 0)), float(s_[aslot])
        bits = int(s_[wslot])
        for q, nm in HD.QLW.items():
            me.has[names.index(nm)] = bool(bits & (1 << q))
            me.ammo[names.index(nm)] = 0 if nm == "g" else max(0.0, float(d["ammo"][k][q]))
        me.w = names.index(HD.QLW.get(int(d["weapon"][k]), "mg"))
        me.duck = bool(ps[k, D.PS["viewheight"]] < 20)
        me.fire = bool((int(ps[k, D.PS["eFlags"]]) & 0x100) or d["weaponstate"][k] == 3)
        me.ground = float(d["groundEntityNum"][k] != 1023)
        took = max(0.0, hp_was - (me.hp + me.armor)) if (me.alive and F.alive[0]) else 0.0
        if alive_was and not me.alive:
            pend[1] = 1.0
        en.present = False
        for row in d["players"][k]:
            if DS.is_enemy(row, cl):
                en.pos = np.array(row[2:5], np.float32)
                en.vel = np.array(row[5:8], np.float32)
                en.pitch, en.yaw = float(row[8]), float(row[9])
                en.w = names.index(HD.QLW.get(int(row[11]), "mg"))
                en.fire = bool(int(row[12]) & 0x100)
                en.present = True
                en_cl = int(row[1])
                break
        if en.present and not en_was:                        # (sent again: his 0.2 s velocity window starts again)
            env.life_t[1] = 0.0
        en_was = en.present
        en.hp, en.armor = 100.0, 0.0
        en.has[:] = False
        en.has[[names.index("mg"), names.index("g"), en.w]] = True
        en.ammo[:] = 50.0
        en.alive = True
        seen_ = np.zeros(env.nI, bool)
        for it in d["items"][k]:
            key = (round(float(it[2])), round(float(it[3])), round(float(it[4])))
            idx = item_near.get(key)
            if idx is None:
                dd = np.linalg.norm(env.item_pos - np.array(key, np.float32), axis=1) if env.nI else np.array([1e9])
                idx = item_near[key] = int(dd.argmin()) if dd.min() < 48 else -1
            if idx >= 0 and (int(it[5]) & 0x80) == 0:
                seen_[idx] = True
        taken = []
        for c_, cls, p_ in picks.get(k, ()):
            idx = HD.nearest_item(env, E, cls, p_)
            if idx < 0:
                continue
            seat = 0 if c_ == cl else 1 if (c_ == en_cl or en_cl < 0) else -1
            taken.append((seat, idx))
            if it_intent[idx] >= 0 and E.INTENTS[int(it_intent[idx])] in BIG_LABS and gi is not None:
                pk_stat[seat] = pk_stat.get(seat, 0) + 1
                if seat == 1:
                    pk_stat["en_unseen"] = pk_stat.get("en_unseen", 0) + int(not bool(env.visible[0]))
                    pk_stat["en_not_sent"] = pk_stat.get("en_not_sent", 0) + int(not en.present)
            if seat == 1 and it_intent[idx] >= 0 and E.INTENTS[int(it_intent[idx])] in BIG_LABS:
                picks_en.append((len(obs), int(it_intent[idx])))
        for seat, idx in taken:
            seen_[idx] = False
        miss = []
        if mi is not None:
            kinds = {5: E.RL, 4: E.GL, 8: E.PG}
            for r in mi[k]:
                w_ = int(r[1])
                if w_ not in kinds:
                    continue
                age = max(0.0, (tm - float(r[3])) / 1000.0)
                p_ = np.array(r[4:7], np.float32) + np.array(r[7:10], np.float32) * age
                v_ = np.array(r[7:10], np.float32)
                if int(r[2]) == 5:
                    p_[2] -= 0.5 * 800.0 * age * age
                    v_[2] -= 800.0 * age
                miss.append((0 if int(r[11]) == cl else 1, kinds[w_], p_, v_, age))
        if gi is not None and lst[k] > 0:
            clock = max(0.0, (tm - int(lst[k])) / 1000.0)
        else:
            clock = ((tm - int(t_ms[0])) / 1000.0) % 600.0
        sc = (score.get(cl, 0), sum(v for c_, v in score.items() if c_ != cl))
        ob = F.frame(me, en, clock, sc, taken=taken, missiles=miss, dealt=0.0, took=took, items=(np.ones(env.nI, bool), seen_),
                     game_new=game_new)
        env._trk_step()
        if ob is None:
            continue
        ar = aux_row(env, E, C)[0]
        ar[C["trk_game"]] = float(ar[C["trk_on"]] > 0.5 and gi is not None)        # (a game, both in play: whether or not he is sent)
        ar[C["trk_on"]] = float(ar[C["trk_on"]] > 0.5 and en.present and gi is not None)
        ar[C["frag"]], ar[C["fragged"]] = pend
        pend = [0.0, 0.0]
        ar[C["src_demo"]] = 1.0
        for c_ in ("race_me_mh", "race_en_mh", "race_me_ra", "race_en_ra"):
            ar[C[c_]] = RACE_CAP_
        ar[C["mega_s"]] = ar[C["red_s"]] = 40.0
        obs.append(ob.astype(np.float16))
        aux.append(ar)
        done.append(False)
        ts.append(tm / 1000.0)
    shutil.rmtree(tmp, ignore_errors=True)
    if len(obs) < 400:
        return None, "short"
    obs = np.stack(obs)
    aux = np.stack(aux)
    done = np.asarray(done, bool)
    done[-1] = True
    tp = target_proxy(len(obs), picks_en, deaths_en)
    aux[:, C["en_target"]] = tp
    aux[:, C["en_target_ppl"]] = tp
    aux[:, C["en_target_sim"]] = -1
    stem = os.path.splitext(os.path.basename(path))[0]      # (the file's name has the players' names: only a hash of it is kept)
    meta = dict(source="demo", map=mp, name="demo_" + hashlib.sha1(stem.encode("utf-8", "replace")).hexdigest()[:12], env=spec["env"],
                games=len(games), frames=len(obs), lesson_frames=int((aux[:, C["trk_on"]] > 0.5).sum()),
                snap_ms_median=float(np.median(dts)) if len(dts) else None,
                big_pickups=dict(me=pk_stat.get(0, 0), enemy=pk_stat.get(1, 0), enemy_not_in_view=pk_stat.get("en_unseen", 0),
                                 enemy_not_sent=pk_stat.get("en_not_sent", 0), unknown_seat=pk_stat.get(-1, 0)))
    return dict(obs=obs, done=done, aux=aux, t=np.asarray(ts), meta=meta), "ok"


# ---------------------------------------------------------------------------------------------------------- simulator
class SessionWriter:
    """a simulator match written as the 1v1 plugin writes a session (frames.csv, events.jsonl, missiles.csv, meta.json):
    seat a is "bobby", a + 1 the person. Only what the plugin logs and the replay reads."""

    def __init__(self, folder, E, env, mp, a=0, t0=1.8e9, swap=False):
        self.E, self.env, self.a, self.t = E, env, a, t0
        self.seats = (a + 1, a) if swap else (a, a + 1)          # (swap: the second seat of the match is "bobby")
        os.makedirs(folder, exist_ok=True)
        self.dir = folder
        cols = ["t", "server_ms", "drill"]
        for p in ("b", "o"):
            cols += [p + "_" + k for k in ("x", "y", "z", "vx", "vy", "vz", "pitch", "yaw", "health", "armor", "weapon", "ammo_rl",
                                           "ammo_rg", "ammo_lg", "fwd", "right", "up", "fire")]
        self.cols = cols
        self.ff = open(os.path.join(folder, "frames.csv"), "w")
        self.ff.write(",".join(cols) + "\n")
        self.ef = open(os.path.join(folder, "events.jsonl"), "w")
        self.mf = open(os.path.join(folder, "missiles.csv"), "w")
        self.mf.write("t,num,owner,weapon,x,y,z,vx,vy,vz\n")
        json.dump(dict(schema=3, map=mp, opponent="human", policy="sim", frame_columns=cols, people=[]), open(os.path.join(folder, "meta.json"), "w"))
        self.up = env.item_up[0].copy() if env.nI else None
        self.gen = np.zeros((2, E.K), np.int64)
        self.was = np.zeros((2, E.K), bool)
        self.score = [0, 0]
        self.t_start = None
        self.names = {v: k for k, v in E.ITEM_DEFS.items()}

    def frame(self, events):
        E, env, a = self.E, self.env, self.a
        self.t += DT
        t = round(self.t, 3)
        if self.t_start is None:
            self.t_start = t
        seats = self.seats
        for e in events:                                     # deaths first (the score as the plugin writes it)
            v, k = int(e["victim"]), int(e["killer"])
            if v in seats:
                if k in seats and k != v:
                    self.score[seats.index(k)] += 1
                who = "bobby" if v == seats[0] else "opp"
                self.ef.write(json.dumps(dict(event="death", who=who, bobby=self.score[0], opp=self.score[1], t=t)) + "\n")
        if env.nI:
            m = a // 2
            up = env.item_up[m]
            gone = np.nonzero(self.up & ~up)[0]
            for k in gone:
                d_ = env.item_pos[k]
                dist = [float(np.linalg.norm(env.state[s, :3] - d_)) for s in seats]
                j = int(np.argmin(dist))
                nm = self.names.get(tuple(env.item_def[k]))
                if nm is not None and dist[j] < 120:
                    self.ef.write(json.dumps(dict(event="pickup", item=nm, by="bobby" if j == 0 else "opp", t=t)) + "\n")
            self.up = up.copy()
        row = [t, 0, "-"]
        for s in self.seats:
            st = env.state[s]
            am = env.ammo[s]
            has = env.has[s]
            alive = env.hp[s] > 0
            pos = st[:3] if alive else np.zeros(3)
            row += [round(float(pos[0]), 1), round(float(pos[1]), 1), round(float(pos[2]), 1), round(float(st[3]), 1), round(float(st[4]), 1),
                    round(float(st[5]), 1), round(float(env.pitch[s]), 2), round(float(env.yaw[s]), 2), int(round(float(env.hp[s]))),
                    int(round(float(env.armor[s]))), QL_NUM[E.WEAPONS[int(env.weapon[s])]]]
            for w_ in ("rl", "rg", "lg"):
                wi = E.WEAPONS.index(w_)
                row.append(int(am[wi]) if has[wi] else -1)
            row += [0, 0, -127 if env.duck[s] else 0, int(bool(env.fire_last[s]))]
        self.ff.write(",".join(str(v) for v in row) + "\n")
        ql = {E.RL: 5, E.GL: 4, E.PG: 8}
        for j, s in enumerate(self.seats):
            for k in range(E.K):
                on = bool(env.ra[s, k])
                if on and not self.was[j, k]:
                    self.gen[j, k] += 1
                self.was[j, k] = on
                if not on:
                    continue
                w_ = int(env.rw[s, k]) if hasattr(env, "rw") else E.RL
                if w_ not in ql:
                    continue
                p_, v_ = env.rp[s, k], env.rv[s, k]
                self.mf.write("{},{},{},{},{:.1f},{:.1f},{:.1f},{:.0f},{:.0f},{:.0f}\n".format(
                    t, 100000 * int(self.gen[j, k]) + 100 * j + k, j, ql[w_], p_[0], p_[1], p_[2], v_[0], v_[1], v_[2]))

    def close(self, play_time):
        for who in ("person", "bobby"):
            self.ef.write(json.dumps(dict(event="player_stats", who=who, warmup=False, aborted=False, play_time=int(play_time),
                                          t=round(self.t, 3) + 0.001)) + "\n")
        self.ef.write(json.dumps(dict(event="end", bobby=self.score[0], opp=self.score[1], t=round(self.t, 3) + 0.002)) + "\n")
        for f in (self.ff, self.ef, self.mf):
            f.close()


def sim_record(ck, mp, matches, minutes, seed, write_sessions=None, record_seats=True, record_xl=False):
    """self-play of the checkpoint against itself in whole games (as the checks play: tools/duel_eval.py), every seat a
    stream -> dict(obs [T, S, D], done [T, S], aux [T, S, C], meta); write_sessions: the first match as a session folder"""
    import duel_eval as DE
    import test_suite as T_
    spec = env_vars_of(ck)
    os.environ.update(spec["env_vars"])
    os.environ["HEAD_EVENTS"] = "1"
    os.environ.setdefault("ROUTE_CACHE", os.path.join(ROOT, "scratch", "route_cache"))
    E = importlib.import_module(spec["env"])
    nav_ = os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mp))
    env = E.DuelEnv(os.path.join(ROOT, "data", "maps", mp + ".bsp"), n_matches=matches, seed=seed, loadout="all",
                    nav=nav_ if os.path.exists(nav_) else None, group=2)
    pol = T_.Policy(ck, seed=seed)
    opp = T_.Policy(ck, seed=seed + 1)
    n = env.n
    T_.set_delays(E, env, [(np.arange(0, n), pol.react_ms, pol.acquire_ms)])
    env.arena_stack = False
    env.arena_sets = [(E.MG,)]
    env.loadout_p = (0.0, 1.0, 0.0, 0.0)
    env.stack_p = env.near_item_p = 0.0
    env.close_p = 0.0
    env.item_run_p = 0.0
    env.jump_run_p = 0.0
    env.kind_p = (1.0, 0.0, 0.0, 0.0)
    env.bot_p = 0.0
    env.runner_p = 0.0
    env.round_t[:] = 1e9
    BR_ = bool(getattr(E, "BRAIN_READ", False))
    if BR_:
        env.set_brain_g(np.full(n, pol.rfg if getattr(pol, "rf_read", False) else 0.0, np.float32))
    obs, _, _, info = env.step(np.zeros((n, len(E.ACTION_DIMS)), np.int64))
    env.round_len = env.arena_len = 1e9
    env.round_t[:] = 0.0
    env.script[:] = 0
    ev, od = np.arange(0, n, 2), np.arange(1, n, 2)
    h, h2 = pol.zeros(len(ev)), opp.zeros(len(od))
    sc_ = DE.SeatClock(E, env, ev, od, (600.0, 600.0), left_full=False)
    C = {k: i for i, k in enumerate(COLS)}
    frames = int(minutes * 60 / DT)
    W = [SessionWriter(write_sessions, E, env, mp), SessionWriter(write_sessions + "_seat1", E, env, mp, swap=True)] if write_sessions else None
    O, A, D, X = [], [], [], []
    aux = aux_row(env, E, C)
    picks = [[] for _ in range(n)]
    deaths = [[] for _ in range(n)]
    up0 = env.item_up.copy() if env.nI else None
    it_intent = None
    import head_data as HD
    it_intent, _ = HD.item_classes(env, E)
    t = -1
    while t + 1 < frames:
        t += 1
        a = np.zeros((n, len(E.ACTION_DIMS)), np.int64)
        hev_ = env.head_events() if hasattr(env, "head_events") and (pol.head_due(h).any() or opp.head_due(h2).any()) else None
        xlu_ = env.legs_prep() if getattr(E, "LEGS_IN", False) and (pol.needs_xl or opp.needs_xl) else None
        pz_ = zz_ = None
        if pol.needs_pose:
            import btoken as btoken_
            pz_, zz_ = btoken_.pose_from_env(env, mp)
        if record_seats:
            O.append(obs.astype(np.float16))
            A.append(aux)
            if record_xl:
                X.append((xlu_ if xlu_ is not None else env.legs_prep()).astype(np.float16))
        al, h = pol.act(obs[ev], h, None if hev_ is None else hev_[ev], xl=None if xlu_ is None else xlu_[ev],
                        **({"pose": pz_[ev], "zmap": zz_[ev]} if pol.needs_pose else {}))
        a[ev, :min(al.shape[1], a.shape[1])] = al[:, :a.shape[1]]
        ao, h2 = opp.act(obs[od], h2, None if hev_ is None else hev_[od], xl=None if xlu_ is None else xlu_[od],
                         **({"pose": pz_[od], "zmap": zz_[od]} if opp.needs_pose else {}))
        a[od, :min(ao.shape[1], a.shape[1])] = ao[:, :a.shape[1]]
        if BR_:
            ans_ = dict(bel=np.zeros((n, 3), np.float32), ok=np.zeros(n, bool), band=np.zeros((n, 4), np.float32), ztop=np.full(n, -1, np.int16))
            for m_, p_, hs_ in ((ev, pol, h), (od, opp, h2)):
                an_ = p_.brain_answer(hs_)
                if an_ is not None:
                    for k_ in ans_:
                        ans_[k_][m_] = an_[k_]
            env.brain_in(ans_)
        sc_.before()
        if getattr(E, "LEGS_IN", False) and pol.legsP is not None:
            xl_ = env.legs_prep()
            lg_ = np.zeros((n, 17), np.float32)
            lg_[ev] = pol.legs_logits(xl_[ev])
            lg_[od] = opp.legs_logits(xl_[od])
            env.legs_lg = lg_
        obs, r, done, info = env.step(a)
        aux = aux_row(env, E, C, info["aux"])
        if record_seats:
            D.append(np.asarray(done, bool).copy())
        for e in info["events"]:
            v_ = int(e["victim"])
            deaths[v_ ^ 1].append(t + 1)                     # (seat v ^ 1's enemy died: from the frame after, as the session's)
        if env.nI:                                           # the big pickups of each seat (the person's target proxy, beside the simulator's own)
            for m in range(env.n // 2):
                gone = np.nonzero(up0[m] & ~env.item_up[m])[0]
                for k in gone:
                    if it_intent[k] < 0 or E.INTENTS[int(it_intent[k])] not in BIG_LABS:
                        continue
                    ss = (2 * m, 2 * m + 1)
                    j = min(ss, key=lambda s_: float(np.linalg.norm(env.state[s_, :3] - env.item_pos[k])))
                    picks[j ^ 1].append((t + 1, int(it_intent[k])))     # (stream j ^ 1's enemy took it)
            up0 = env.item_up.copy()
        if W is not None:
            for w_ in W:
                w_.frame(info["events"])
        # memories cleared on the trainer's done (his death), each Policy's own clear
        for m_, p_, hs_ in ((ev, pol, h), (od, opp, h2)):
            dd = np.nonzero(np.asarray(done, bool)[m_])[0]
            if len(dd):
                p_.clear(hs_, dd)
        sc_.after(t, info["events"], (h, h2), (pol, opp))
    if W is not None:
        for w_ in W:
            w_.close(minutes * 60)
    out = dict(meta=dict(source="sim", map=mp, matches=matches, minutes=minutes, seed=seed, ck=os.path.basename(ck), env=spec["env"]))
    if record_seats:
        A.append(aux)
        aux_ = np.stack(A)                                   # [T + 1, S, C]
        Tn = len(O)
        for s in range(n):
            tp = target_proxy(Tn + 1, sorted(picks[s]), deaths[s])
            aux_[:, s, C["en_target_ppl"]] = tp
        out.update(obs=np.stack(O), done=np.stack(D), aux=aux_)
        if record_xl:
            out["xl"] = np.stack(X)
    return out


def save_sim(path, d):
    ex = {"xl": d["xl"]} if "xl" in d else {}
    np.savez(path, obs=d["obs"], done=d["done"], aux=d["aux"].astype(np.float32), meta=json.dumps(dict(d["meta"], cols=list(COLS))), **ex)
    return path


# ---------------------------------------------------------------------------------------------------------- the check
def check(sim_path, rep_path, seat=0):
    """the replayed session of a simulator match beside the simulator's own record of the same frames (seat 0 = bobby)"""
    zs, zr = np.load(sim_path), np.load(rep_path)
    cols = json.loads(str(zs["meta"]))["cols"]
    C = {k: i for i, k in enumerate(cols)}
    os_, ds_, as_ = zs["obs"][:, seat].astype(np.float32), zs["done"][:, seat], zs["aux"][:-1, seat]
    alive = as_[:, C["hp_me"]] > 0
    # the session writes a row per step after the first; the replay keeps his living rows: line them up by frame
    rows = zr["row"]
    orr, arr = zr["obs"][:, 0].astype(np.float32), zr["aux"][:-1, 0]
    fs = rows + 1                                            # (the session's row r is the state after step r: the simulator's frame r + 1)
    ok = fs < len(os_)
    fs, orr, arr = fs[ok], orr[ok], arr[ok]
    return dict(C=C, sim_obs=os_[fs], rep_obs=orr, sim_aux=as_[fs], rep_aux=arr, alive=alive[fs], frames=fs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("session", "sim", "check", "demo"))
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--ck", required=False)
    ap.add_argument("--out", default=os.path.join(ROOT, "scratch", "brain_data"))
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--matches", type=int, default=4)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--write-sessions", default=None)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--games-only", action="store_true")
    ap.add_argument("--xl", action="store_true", help="also the legs' inputs of every frame (the play effect of sim/brain_fit.py)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    if a.what == "session":
        import head_data as HD
        spec = env_vars_of(a.ck)
        paths = []
        for p in a.paths:                                    # (a .txt: one session folder or archive a line)
            paths += [q.strip() for q in open(p) if q.strip()] if p.endswith(".txt") else [p]
        for i, p in enumerate(paths):
            name = os.path.basename(os.path.normpath(p)).replace(".tar.gz", "")
            out = os.path.join(a.out, "ppl_{}.npz".format(name))
            if os.path.exists(out):
                print("have", out, flush=True)
                continue
            tmp = None
            sess = p
            if p.endswith(".tar.gz"):
                tmp = tempfile.mkdtemp(dir=os.path.join(ROOT, "scratch"))
                sess = HD.unpack(p, tmp)
            try:
                d, why = replay_session(spec, sess, seed=a.seed + i, max_frames=a.max_frames, games_only=a.games_only, record_xl=a.xl)
            except Exception as e:                           # noqa: BLE001 - a broken session must not stop the batch
                d, why = None, repr(e)[:300]
            if d is not None:
                save_shard(out, d)
            print("session {} -> {} ({}) {:.0f} s".format(name, out if d is not None else None, why, time.time() - t0), flush=True)
            if tmp:
                import shutil
                shutil.rmtree(tmp, ignore_errors=True)
    elif a.what == "demo":
        import hashlib
        spec = env_vars_of(a.ck)
        paths = []
        for p in a.paths:
            paths += [q.strip() for q in open(p) if q.strip()] if p.endswith(".txt") else [p]
        for i, p in enumerate(paths):
            mp = os.path.basename(os.path.dirname(p))
            stem = os.path.splitext(os.path.basename(p))[0]
            out = os.path.join(a.out, "demo_{}_{}.npz".format(mp, hashlib.sha1(stem.encode("utf-8", "replace")).hexdigest()[:12]))
            if os.path.exists(out):
                continue
            try:                                             # (several workers on one list: the first to claim a demo does it)
                os.close(os.open(out + ".claim", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            except FileExistsError:
                continue
            try:
                d, why = replay_demo(spec, mp, p, seed=a.seed + i, max_frames=a.max_frames)
            except Exception as e:                           # noqa: BLE001
                d, why = None, repr(e)[:300]
            if d is not None:
                save_shard(out, d)
            print("demo {} {} -> {} ({}) {:.0f} s".format(i, mp, os.path.basename(out) if d is not None else None, why, time.time() - t0), flush=True)
    elif a.what == "sim":
        out = os.path.join(a.out, "sim_{}_s{}.npz".format(a.map, a.seed))
        d = sim_record(a.ck, a.map, a.matches, a.minutes, a.seed, write_sessions=a.write_sessions, record_xl=a.xl)
        save_sim(out, d)
        print("sim {} -> {} {:.0f} s".format(a.map, out, time.time() - t0), flush=True)
    elif a.what == "check":
        r = check(a.paths[0], a.paths[1])
        print({k: v.shape for k, v in r.items() if hasattr(v, "shape")})


if __name__ == "__main__":
    main()
