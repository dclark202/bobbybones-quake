"""2.1, the instruction in the simulator (INSTRUCTION.md): its tests. Nothing here trains; one simulator a process, a few thousand
frames of random play each, one core. NOT RUN YET (written while 1.8a trained; the worktree has no data folder).

    python docs/runs/2.1/tests_instr.py [--map bloodrun] [--frames 2000] [--base c99cc02]         (Anaconda Python; ALL PASSED at the end)

  1  off = the simulator before: the group module of commit --base (the last before this build) and today's with INSTR=0, the same
     seed and actions: the inputs both have, the pay and the rounds' ends equal to the bit; the 39 new columns all zero
  2  on, no instruction given = off: INSTR=1 against INSTR=0, everything equal to the bit
  3  on, instructions given every head tick to half the seats (a driver with its own random stream; the places and points are the
     opponent's TRUE place: a test of the machinery, not of fair play): a seat under none reads zeros; a seat under one has exactly
     one verb and every number within its stated range; the states each verb reached are printed; a moment taken from one match and
     set into another carries the instruction
  7  (second pass) the labels KNOWN_TRUTH and SPAWN_TRUTH, the check rows, the spawn rows after a death, the quiet field
  4  tools/ffa_check.py: the two-player module against the group module
  5  the candidates (docs/runs/2.1/SIM_PARTS.md): instr_feat() called at every head tick and nothing picked = off, to the bit (a
     read); its shapes, every number finite and within 3, an invalid row its verb alone, the spare row never valid, "none" valid
     for the living; a row picked with instr_pick() lands (the verb, the row, the weapon, the kept place and point); a forced seat
     (force_instr) takes the forced row whatever is passed, and is free again when the force is lifted; instr_state() in range
  6  the drills: DRILL_INS_P=0 is case 2 (nothing changes); with DRILL_INS_P=1 and INS_DRILL_SECS=2 a game's start is followed by
     a drill: the seat is forced to a valid row of a verb, flagged (ins_drill), for no longer than the window, then under none
  8  (third pass) the finish time, the wake, the pattern's moments, with EN_STACK=1 (his stack belief) and instructions given: the
     hands' seven finish columns and the rows' 27 within 0 .. 2, the same in every valid row of a seat, the weapon-in-hand columns
     equal to _fin() for the weapon in his hand and zero for the dead; instr_state() has 8 numbers; wakes and pattern moments
     occur; a moment carries the wake's books; the label HEAD_PAY_TRUTH changes nothing of the game
  9  (2.1a) the binding weapon (INS_BIND=1): on with no instruction given = off, to the bit; under instructions the action the
     step sets is ins_bind_act() of the state before it, only for a weapon he owns with ammunition; a seat bound to one weapon for
     2 s has it in his hand (the finger limits and the game's switch time allow no less); with it off under the same instructions
     nothing is bound
(From the third pass on, "as off, to the bit" in cases 2 and 5 leaves out the last four inputs: the finish time of the weapon in
his hand and "he has a belief", which are live for every living seat with INSTR on, under an instruction or not.)
"""
import argparse
import os
import subprocess
import sys
import tempfile
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SIM = os.path.join(ROOT, "sim")
MAPS = os.path.join(os.environ.get("QLBOT_ROOT") or ROOT, "data", "maps")


def module(base, name="duel_env_ffa"):
    """today's group module (or the two-player one: name), or (base: a commit) that commit's source run as a module that sits where today's does"""
    sys.path.insert(0, SIM)
    if not base:
        import importlib
        return importlib.import_module(name)
    src = subprocess.run(["git", "-C", ROOT, "show", base + ":sim/duel_env_ffa.py"], check=True, capture_output=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.decode("utf-8")
    E = types.ModuleType("duel_env_ffa_base")
    E.__file__ = os.path.join(SIM, "duel_env_ffa.py")
    sys.modules["duel_env_ffa_base"] = E
    exec(compile(src, E.__file__, "exec"), E.__dict__)
    return E


def actions(E, env, rng):
    a = np.stack([rng.integers(0, d, env.n) for d in E.ACTION_DIMS], 1)
    a[:, 5] = rng.random(env.n) < 0.8
    foe = env._others_arr()[:, 0]
    s = env.state
    to = s[foe, :3] - s[:, :3]
    ey = (np.degrees(np.arctan2(to[:, 1], to[:, 0])) - env.yaw + 180.0) % 360.0 - 180.0
    ep = -np.degrees(np.arctan2(to[:, 2], np.hypot(to[:, 0], to[:, 1]) + 1e-6)) - env.pitch
    aim = rng.random(env.n) < 0.7
    a[:, 3] = np.where(aim, np.abs(E.TURN[None, :] - np.clip(ey, -20, 20)[:, None]).argmin(1), a[:, 3])
    a[:, 4] = np.where(aim, np.abs(E.PITCH[None, :] - np.clip(ep, -10, 10)[:, None]).argmin(1), a[:, 4])
    return a


def drive(E, env, drng, t):
    """instructions for half the seats, another one every 2 s; the same one given again at the ticks between"""
    n = env.n
    if t % 80 == 0 or not hasattr(drive, "cur"):
        v = drng.integers(1, len(E.INS_VERBS), n)
        v[drng.random(n) < 0.5] = 0
        tg = np.full(n, -1, np.int64)
        it = np.isin(v, (E.INS_GO, E.INS_CONTEST))
        tg[it] = drng.integers(1, E.EN_INTENT, int(it.sum()))
        hd = (v == E.INS_HOLD) & (getattr(env, "hold_n", 0) > 0)
        tg[hd] = E.HOLD_INTENT + drng.integers(0, max(1, getattr(env, "hold_n", 1)), int(hd.sum()))
        w = np.where(drng.random(n) < 0.8, drng.choice([E.RL, E.RG, E.GL, E.PG, E.LG], n), -1)
        drive.cur = (v, tg, w, drng.random(n) * 4.0 - 0.5, drng.random(n) < 0.5)
    v, tg, w, when, self_place = drive.cur
    foe = env._others_arr()[:, 0]
    pos = env.state[:, :3].astype(np.float32)
    place = np.where(self_place[:, None], pos, pos[foe])
    place[np.isin(v, (E.INS_GO, E.INS_CONTEST)) & (tg >= 0)] = np.nan       # an item: the target alone
    point = pos[foe] + np.array([0, 0, 20.0], np.float32)
    point[v == E.INS_GO] = np.nan
    env.instr_in(v, tg, place, point, w, np.maximum(when - (t % 80) * E.DT, -1.0))
    return v


def cand(E, env, crng, t, st):
    """case 5: the candidates' checks at a head tick, then rows picked for half the seats; a force on seat 0 for a while"""
    n = env.n
    ar = np.arange(n)
    X, ok, wok = env.instr_feat()
    bad = st.setdefault("bad", [])
    if X.shape != (n, E.INS_C, E.INS_F) or ok.shape != (n, E.INS_C) or wok.shape != (n, E.NW) or X.dtype != np.float32:
        bad.append((t, "shapes"))
        return
    nv = len(E.INS_VERBS)
    alive = env.hp[:n] > 0
    if getattr(E, "INS_WAY", False):                         # (case 10) the receiver's side: its three numbers over the valid rows
        j_ = E.INS_FEAT.index("way_seen")
        w_ = st.setdefault("way", [0, 0, 0, 0.0, 0.0])       # valid rows, watched on the way, at a teleporter's end, sum and sum of squares of way_seen_t
        v_ = ok & (E.INS_ROW_VERB[None, :] > 0)
        w_[0] += int(v_.sum()); w_[1] += int(X[..., j_][v_].sum()); w_[2] += int(X[..., j_ + 2][v_].sum())
        w_[3] += float(X[..., j_ + 1][v_].sum()); w_[4] += float((X[..., j_ + 1][v_] ** 2).sum())
        if ((X[..., j_ + 2] > X[..., j_]).any() or (X[..., j_ + 1][v_ & (X[..., j_] == 0)] != 2.0).any() or (X[..., j_ + 1][v_ & (X[..., j_] > 0)] >= 2.0 + 1e-6).any()
                or X[..., j_:j_ + 3][~ok].any()):
            bad.append((t, "the way numbers: a teleporter with no watched point, a time without one, or an invalid row not zero"))
    if not np.isfinite(X).all() or np.abs(X).max() > 3.0 + 1e-6:
        bad.append((t, "a number outside 3: {:.3f}".format(float(np.abs(X).max()))))
    on_col = E.INS_FEAT.index("on_now")
    Z = X[..., nv:].copy()
    Z[..., on_col - nv] = 0.0
    if np.abs(Z[~ok]).sum() != 0:
        bad.append((t, "an invalid row carries numbers"))
    if not wok[alive].any(1).all() or not wok[alive, E.G].all() or wok[~alive].any():     # (2.1a, G) a weapon to name always: the gauntlet at the least
        bad.append((t, "a living seat has no weapon to name (the gauntlet), or a dead one has one"))
    if ok[:, E.INS_ROW0["spare"]].any() or not np.array_equal(ok[:, E.INS_NONE_ROW], alive & (not getattr(E, "INS_NO_NONE", False))) or ok[~alive].any():
        bad.append((t, "the spare row, the row none, or a dead seat's rows"))
    if not np.array_equal(X[..., E.INS_FEAT.index("valid")] > 0, ok):
        bad.append((t, "valid is not ok"))
    st["rows_ok"] = st.get("rows_ok", np.zeros(E.INS_C, np.int64)) + ok.sum(0)
    stt = env.instr_state()
    if stt.shape != (n, E.INS_SIG) or not np.isfinite(stt).all() or stt.min() < 0 or stt.max() > 2.0 + 1e-6 or np.abs(stt[env.ins_v[:n] == 0]).sum() != 0:
        bad.append((t, "instr_state"))
    forced = 600 <= t < 900
    row = E.INS_ROW0["push"]
    env.force_instr[:] = -1
    if forced:
        env.force_instr[0] = (row, -1)
    c = np.full(n, -1, np.int64)
    w = np.full(n, -1, np.int64)
    who = crng.random(n) < 0.5
    for i in np.nonzero(who)[0]:
        rows = np.nonzero(ok[i])[0]
        if len(rows):
            c[i] = int(crng.choice(rows))
        ws = np.nonzero(wok[i])[0]
        if len(ws) and crng.random() < 0.8:
            w[i] = int(crng.choice(ws))
    kept = (env.ins_cp.copy(), env.ins_cpk.copy(), env.ins_co.copy(), env.ins_cog.copy())
    env.instr_pick(c, w, who)
    cc = np.clip(c, 0, E.INS_C - 1)
    good = who & (c >= 0) & ok[ar, cc] & (E.INS_ROW_VERB[cc] > 0)
    if forced:
        good[0], cc[0], c[0], w[0] = bool(ok[0, row]), row, row, -1
        who = who | (ar == 0)
        st["forced"] = st.get("forced", 0) + 1
        if int(env.ins_cur[0]) != (row if ok[0, row] else -1):
            bad.append((t, "the forced seat is on row {}".format(int(env.ins_cur[0]))))
    if not np.array_equal(env.ins_v[who], np.where(good, E.INS_ROW_VERB[cc], 0)[who]) or not np.array_equal(env.ins_cur[who], np.where(good, c, -1)[who]):
        bad.append((t, "a picked row did not land (verb, row)"))
    gw = good & (w >= 0)
    if not np.array_equal(env.ins_w[gw], w[gw]):
        bad.append((t, "the weapon did not land"))
    gp = good & kept[1][ar, cc]
    go_ = good & kept[3][ar, cc]
    if not np.allclose(env.ins_p[gp], kept[0][ar, cc][gp]) or not np.allclose(env.ins_o[go_], kept[2][ar, cc][go_]) \
            or not np.array_equal(env.ins_pok[good], kept[1][ar, cc][good]) or not np.array_equal(env.ins_ook[good], kept[3][ar, cc][good]):
        bad.append((t, "the place or the point did not land"))
    if t == 904 and (env.force_instr >= 0).any():
        bad.append((t, "the force was not lifted"))


def drill_watch(E, env, st):
    """case 6: every frame of a run with drills on"""
    n = env.n
    d = env.ins_drill[:n]
    bad = st.setdefault("bad", [])
    st["drill_frames"] = st.get("drill_frames", 0) + int(d.sum())
    run_ = st.setdefault("run", np.zeros(n, np.int64))
    run_[:] = np.where(d, run_ + 1, 0)
    st["longest"] = max(st.get("longest", 0), int(run_.max()))
    st["begun"] = st.get("begun", 0) + int((run_ == 1).sum())
    if d.any():
        rows = env.force_instr[:n][d, 0]
        if (rows < 0).any() or (E.INS_ROW_VERB[np.clip(rows, 0, E.INS_C - 1)] == 0).any():
            bad.append("a drill's seat is not forced to a verb's row")
        v = env.ins_v[:n][d]
        if not np.all((v == 0) | (v == E.INS_ROW_VERB[np.clip(rows, 0, E.INS_C - 1)])):
            bad.append("a drill's seat is under another verb")
        for vv in v[v > 0]:
            st.setdefault("verbs", {}).setdefault(E.INS_VERBS[int(vv)], 0)
            st["verbs"][E.INS_VERBS[int(vv)]] += 1
    if (env.force_instr[:n][~d] >= 0).any():
        bad.append("a seat out of a drill is forced")
    was = st.get("was", np.zeros(n, bool))
    ended = was & ~d
    if (env.ins_v[:n][ended] != 0).any():
        bad.append("a drill ended and its instruction stayed")
    st["was"] = d.copy()


def truth(E, env, crng, t, st, o):
    """case 7 (KNOWN_TRUTH, SPAWN_TRUTH, RESPAWN_QL on), every frame after the step: the labels; at a head tick: the check and
    the spawn rows, and rows picked with quiet asked; a quiet force on seat 0 for a while"""
    n = env.n
    ar = np.arange(n)
    bad = st.setdefault("bad", [])
    C = {k_: i_ for i_, k_ in enumerate(E.AUX_COLS)}
    A = env.aux()
    foe = env._others_arr()[:n, 0]
    pos = env.state[:n, :3]
    ek, eh = A[:, C["en_knows"]] > 0, A[:, C["en_heard"]] > 0
    st["knows"], st["heard"] = st.get("knows", 0) + int(ek.sum()), st.get("heard", 0) + int(eh.sum())
    bel, bok = env._ins_bel()
    near = (np.linalg.norm(env.known[foe] - pos, axis=1) < E.KNOWN_R) | (bok[foe] & (np.linalg.norm(bel[foe] - pos, axis=1) < E.KNOWN_R))
    if (ek & ~(np.asarray(env.acquired, bool)[foe] | ((env.seen_t[foe] <= E.KNOWN_T) & near))).any():
        bad.append((t, "en_knows without the enemy's sight or a fresh picture within KNOWN_R"))
    sp = A[:, C["en_spawn"]].astype(np.int64)
    b = sp >= 0
    st["born"] = st.get("born", 0) + int(b.sum())
    if b.any():
        if (sp[b] >= len(env.spawns)).any() or (np.linalg.norm((env.spawns[np.minimum(sp[b], len(env.spawns) - 1)] - pos[foe[b]])[:, :2], axis=1) > 64.0).any():
            bad.append((t, "en_spawn is not where the enemy stands"))
    dt_ = A[:, C["en_dead_t"]]
    if not np.isfinite(dt_).all() or dt_.min() < 0 or dt_.max() > 99.0 + 1e-6:
        bad.append((t, "en_dead_t"))
    nq = E.OBS_DIM - 1 - getattr(E, "N_FIN", 0)               # "quiet asked": the last input before the finish time's
    if not np.array_equal(o[:, nq] > 0, (env.ins_q[:n] > 0) & (env.ins_v[:n] > 0)):
        bad.append((t, "the input 'quiet asked' is not the instruction's"))
    if t % 8:
        return
    X, ok, wok = env.instr_feat()
    pok = env._cmb_ahead()[5]
    r0 = E.INS_ROW0["check"]
    if ok[~pok, r0:r0 + 3].any():
        bad.append((t, "a check row without a belief"))
    st["check_ok"] = st.get("check_ok", 0) + int(ok[:, r0:r0 + 3].sum())
    rows = np.concatenate([np.arange(E.INS_ROW0[b_], E.INS_ROW0[b_] + E.SPAWN_K) for b_ in ("spush", "sspam")])
    oks = ok[:, rows]
    st["spawn_ok"] = st.get("spawn_ok", 0) + int(oks.sum())
    if oks[env.ins_dead_t[:n] >= E.INS_SPAWN_SECS].any():
        bad.append((t, "a spawn row outside its seconds"))
    cs = env.ins_cspawn[:n]
    other = np.ones(E.INS_C, bool)
    other[rows] = False
    if (cs[:, other] >= 0).any() or (cs[:, rows][oks] < 0).any() or (cs >= len(env.spawns)).any() or (cs[:, rows][~oks] >= 0).any():
        bad.append((t, "ins_cspawn"))
    if not np.array_equal(X[..., E.INS_FEAT.index("spawn_row")] > 0, cs >= 0) or any(np.abs(X[..., c_]).sum() != 0 for c_ in E.INS_FILL.values()):
        bad.append((t, "spawn_row, or a column the trainer fills is not zero"))
    forced = 600 <= t < 900
    env.force_quiet[:] = -1
    if forced:
        env.force_quiet[0] = 1
    c, w, q = np.full(n, -1, np.int64), np.full(n, -1, np.int64), (crng.random(n) < 0.5).astype(np.int64)
    who = crng.random(n) < 0.5
    for i in np.nonzero(who)[0]:
        rr = np.nonzero(ok[i])[0]
        if len(rr):
            c[i] = int(crng.choice(rr))
    env.instr_pick(c, w, who, q=q)
    cc = np.clip(c, 0, E.INS_C - 1)
    good = who & (c >= 0) & ok[ar, cc] & (E.INS_ROW_VERB[cc] > 0)
    want = q.copy()
    if forced:
        want[0] = 1
        st["forced"] = st.get("forced", 0) + 1
    if not np.array_equal(env.ins_q[:n][good], want[good]) or (env.ins_q[:n][who & ~good] != 0).any():
        bad.append((t, "quiet did not land"))
    if not np.array_equal(env.ins_spk[:n][good], cs[ar, cc][good]):
        bad.append((t, "the row's spawn point did not land"))
    st["verbs"] = st.get("verbs", np.zeros(len(E.INS_VERBS), np.int64)) + np.bincount(env.ins_v[:n], minlength=len(E.INS_VERBS))
    if t == 1000:                                            # a moment: match 0 into match 1: quiet with it, the force not
        env.force_quiet[0] = 1
        mo = env._moment_take(0, o)
        env._moment_set(1, mo, o)
        st["moment_ok"] = bool(np.array_equal(env.ins_q[0:2], env.ins_q[2:4]) and np.array_equal(env.ins_spk[0:2], env.ins_spk[2:4])
                               and env.force_quiet[2] == -1 and env.force_quiet[0] == 1)
        env.force_quiet[:] = -1


def fin_watch(E, env, t, st, o):
    """case 8, every frame after the step (EN_STACK=1, instructions given by drive())"""
    n = env.n
    ar = np.arange(n)
    bad = st.setdefault("bad", [])
    c1 = E.OBS_DIM - E.N_FIN
    x = o[:, c1:]
    if not np.isfinite(x).all() or x.min() < 0 or x.max() > 2.0 + 1e-6:
        bad.append((t, "a finish column outside 0 .. 2"))
    fin, fhi, fire, fok = env._fin()
    hw = np.clip(env.weapon[:n], 0, E.NW - 1)
    alive = env.hp[:n] > 0
    if not (np.allclose(x[:, 3], fin[ar, hw]) and np.allclose(x[:, 4], fhi[ar, hw]) and np.allclose(x[:, 5], fire[ar, hw]) and np.array_equal(x[:, 6] > 0, fok)):
        bad.append((t, "the weapon-in-hand columns are not _fin()'s"))
    if np.abs(x[~alive]).sum() != 0:
        bad.append((t, "a dead seat reads a finish time"))
    on = env.ins_v[:n] > 0
    w = env.ins_w[:n]
    asked = on & (w >= 0)
    if np.abs(x[~asked, :3]).sum() != 0:
        bad.append((t, "the asked-weapon columns without a weapon asked"))
    wc = np.clip(w, 0, E.NW - 1)
    if asked.any() and not np.allclose(x[asked, 0], fin[ar, wc][asked]):
        bad.append((t, "the asked-weapon finish time is not _fin()'s"))
    if (fhi + 1e-6 < fin).any():
        bad.append((t, "a cautious time under the plain one"))
    st["belief"] = st.get("belief", 0) + int(fok.sum())
    st["short"] = st.get("short", 0) + int(((fin[ar, hw] < 0.4) & fok).sum())      # (under 2 s to finish with the weapon in hand)
    pat = env.instr_pattern()
    if pat.shape != (n,) or not np.isin(pat, (0, 1, 2)).all() or pat[~alive].any():
        bad.append((t, "instr_pattern"))
    st["pat1"], st["pat2"] = st.get("pat1", 0) + int((pat == 1).sum()), st.get("pat2", 0) + int((pat == 2).sum())
    st["chunk"] = st.get("chunk", 0) + int((env.ins_chunk_t[:n] <= 0).sum())
    if t % 8 == 0:
        X, ok, wok = env.instr_feat()
        f0 = E.INS_FIN0
        Z = X[..., f0:f0 + E.FIN_F * E.NW]
        if Z.min() < 0 or Z.max() > 2.0 + 1e-6 or np.abs(Z[~ok]).sum() != 0:
            bad.append((t, "the rows' finish numbers"))
        want = np.stack([fin, fhi, fire], 2).reshape(n, 1, -1)
        if not np.allclose(np.where(ok[..., None], Z, 0.0), np.where(ok[..., None], want, 0.0)):
            bad.append((t, "the rows' finish numbers are not _fin()'s, or differ between a seat's rows"))
        sg = env.instr_state()
        if sg.shape != (n, E.INS_SIG) or sg.min() < 0 or sg.max() > 2.0 + 1e-6 or np.abs(sg[~on]).sum() != 0:
            bad.append((t, "instr_state"))
        st["wake"] = st.get("wake", 0) + int((sg[:, E.INS_SIG_WAKE] > 0).sum())
        st["fell"] = st.get("fell", 0) + int((sg[:, E.INS_SIG_WAKE + 1] > 0).sum())
        st["ticks_on"] = st.get("ticks_on", 0) + int(on.sum())
    if t == 1000 and alive[0] and alive[1]:                   # a chunk hit booked by hand (random play seldom lands one): the mark of seat 0
        env.note_dealt(0, 1, E.INS_CHUNK + 10.0)             # alone, and the pattern's moment where the enemy is near
        st["chunk_ok"] = bool(env.ins_chunk_t[0] == 0.0 and env.ins_chunk_t[1] > 0.0 and int(env.instr_pattern()[0]) == int(
            bool(env.visible[0]) or (env._ins_bel()[1][0] and np.linalg.norm(env.state[0, :3] - env._ins_bel()[0][0]) < E.INS_PAT_NEAR)))
    if t == 1200:                                             # a moment: match 0 into match 1: the wake's books with it
        mo = env._moment_take(0, o)
        env._moment_set(1, mo, o)
        st["moment_ok"] = all(np.array_equal(getattr(env, k)[0:2], getattr(env, k)[2:4]) for k in
                              ("ins_s0", "ins_s00", "ins_sok", "ins_wake_f", "ins_pain_p", "ins_chunk_t", "ins_vis_t", "ins_gap", "ins_unseen"))


def bind_watch(E, env, st, pre):
    """case 9, every frame after the step: pre = (the expected action, the weapon asked for) from the state before it"""
    exp, w = pre
    got = env.ins_bind_a[:env.n]
    st.setdefault("bad", [])
    if not np.array_equal(got, exp):
        st["bad"].append("the action set is not ins_bind_act() of the state before the step")
    run_ = st.get("run", np.zeros(env.n, np.int64))
    lw_ = st.get("lw", np.full(env.n, -1, np.int64))
    b = got >= 0
    run_ = np.where(b & (w == lw_), run_ + 1, np.where(b, 1, 0))
    st["run"], st["lw"] = run_, np.where(b, w, -1)
    late = b & (run_ >= 80) & (env.weapon[:env.n] != w) & (env.hp[:env.n] > 0)
    if late.any():
        st["bad"].append("bound to a weapon for 2 s and it is not in his hand")
    st["bound"] = st.get("bound", 0) + int(b.sum())
    st["held"] = st.get("held", 0) + int((b & (env.weapon[:env.n] == w)).sum())
    st["sw"] = st.get("sw", 0) + int((got > 0).sum())


def cmd_env(path, skip=("LEGS", "OPENBLAS", "OMP_", "CUDA", "PYTHON", "ROOT", "PATH")):
    """a run's train.cmd -> its `set NAME=VALUE` lines as a dict (%ROOT% = the repo the file is in; the trainer's own and the
    movement network's names left out: a test's simulator is stepped without the trainer)"""
    root = os.path.abspath(path)
    for _ in range(5):
        root = os.path.dirname(root)
    root = os.environ.get("QLBOT_ROOT") or root            # (a worktree without data: the repo that has it)
    out = {}
    for ln in open(path, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if ln.lower().startswith("set ") and "=" in ln:
            k, v = ln[4:].split("=", 1)
            k = k.strip()
            if k and not k.upper().startswith(skip):
                out[k] = v.strip().replace("%ROOT%", root)
    return out


def run(a):
    if a.cmd:
        os.environ.update(cmd_env(a.cmd))
    for s in a.set:
        k, v = s.split("=", 1)
        os.environ[k] = v
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1")
    E = module(a.base, a.module)
    env = E.DuelEnv(os.path.join(MAPS, a.map + ".bsp"), n_matches=8, seed=5, nav=os.path.join(MAPS, "nav_{}_sim.json".format(a.map)),   # (the walking map: without it there is no way and no candidate row but "none")
                    **({"group": 2} if a.module.endswith("ffa") else {}))
    env.react_frames, env.acquire_frames = 3, 8
    rng, drng = np.random.default_rng(11), np.random.default_rng(77)
    obs, rew, don = [], [], []
    o = env.observe()
    notes = dict(route=env.route is not None, om=getattr(env, "om", None) is not None, obs_dim=int(o.shape[1]))
    bad, states, moment_ok = [], {}, None
    crng, cst, dst, tst, fst = np.random.default_rng(78), {}, {}, {}, {}
    bst = {}
    nf_ = getattr(E, "N_FIN", 0) - 3 if getattr(E, "N_FIN", 0) else 0     # (the columns live under none: the weapon in hand's and the belief's mark)
    for t in range(a.frames):
        act = actions(E, env, rng)
        if a.drive and t % 8 == 0:
            drive(E, env, drng, t)
        if a.feat and t % 8 == 0:
            env.instr_feat()
            env.instr_state()
        if a.cand and t % 8 == 0:
            cand(E, env, crng, t, cst)
        if a.bind:                                           # (case 9) the binding the step must set, from the state before it
            pre_ = (np.where(env.script[:env.n] == 0, E.ins_bind_act(env.ins_v[:env.n], env.ins_w[:env.n], env.has[:env.n], env.ammo[:env.n],
                                                                 env.weapon[:env.n], env.hp[:env.n] > 0), -1), env.ins_w[:env.n].copy())
        o, r, d, info = env.step(act)
        if a.bind:
            bind_watch(E, env, bst, pre_)
        obs.append(o.copy()), rew.append(r.copy()), don.append(d.copy())
        if a.drill:
            drill_watch(E, env, dst)
        if a.truth:
            truth(E, env, crng, t, tst, o)
        if a.fin:
            fin_watch(E, env, t, fst, o)
        if a.drive:
            n0 = E.OBS_DIM - E.N_INS
            x, v = o[:, n0:], env.ins_v
            nv = len(E.INS_VERBS)
            if np.abs(x[v == 0][:, :x.shape[1] - nf_]).sum() != 0:
                bad.append((t, "a seat under none reads something"))
            on = v > 0
            if on.any():
                if not np.all(x[on, :nv].sum(1) == 1) or not np.all(x[on, 0] == 0) or not np.all(x[on][np.arange(int(on.sum())), v[on]] == 1):
                    bad.append((t, "the verb's one-hot"))
                if not np.isfinite(x).all() or np.abs(x).max() > 3.0 + 1e-6:
                    bad.append((t, "a number outside its range: {:.3f}".format(float(np.abs(x).max()))))
                for vv, st in zip(v[on], env.ins_st[on]):
                    states.setdefault(E.INS_VERBS[int(vv)], np.zeros(4, np.int64))[int(st)] += 1
            if t == a.frames // 2:                           # a moment: match 0 into match 1, the instruction with it
                mo = env._moment_take(0, o)
                env._moment_set(1, mo, o)
                moment_ok = all(np.array_equal(getattr(env, k)[0:2], getattr(env, k)[2:4]) for k in
                                ("ins_v", "ins_tg", "ins_p", "ins_pok", "ins_o", "ins_ook", "ins_w", "ins_when", "ins_when0", "ins_t", "ins_st", "ins_in", "ins_q", "ins_spk"))
    np.savez(a.out, obs=np.array(obs), rew=np.array(rew), don=np.array(don), n_ins=getattr(E, "N_INS", 0),
             cut=E.OBS_BASE + E.N_EXTRA + E.N_FIGHT + E.N_MEM + E.N_ROUTE, n_ffa=getattr(E, "N_FFA", 0),
             notes=np.array(repr(dict(notes, bad=bad[:5], n_bad=len(bad), moment_ok=moment_ok,
                                      states={k: v.tolist() for k, v in states.items()},
                                      norow=np.asarray(getattr(env, "ins_norow", np.zeros(3))).tolist(),
                                      cand=dict(way=cst.get("way"), bad=cst.get("bad", [])[:5], n_bad=len(cst.get("bad", [])), forced=cst.get("forced", 0),
                                                rows_ok=np.asarray(cst.get("rows_ok", np.zeros(1))).tolist()),
                                      truth=dict(bad=tst.get("bad", [])[:5], n_bad=len(tst.get("bad", [])), knows=tst.get("knows", 0), heard=tst.get("heard", 0),
                                                 born=tst.get("born", 0), check_ok=tst.get("check_ok", 0), spawn_ok=tst.get("spawn_ok", 0),
                                                 forced=tst.get("forced", 0), moment_ok=tst.get("moment_ok"),
                                                 verbs=np.asarray(tst.get("verbs", np.zeros(1))).tolist()),
                                      fin=dict(bad=fst.get("bad", [])[:5], n_bad=len(fst.get("bad", [])), moment_ok=fst.get("moment_ok"), chunk_ok=fst.get("chunk_ok"),
                                               **{k_: int(fst.get(k_, 0)) for k_ in ("belief", "short", "pat1", "pat2", "chunk", "wake", "fell", "ticks_on")}),
                                      bind=dict(bad=sorted(set(bst.get("bad", [])))[:5], bound=bst.get("bound", 0), held=bst.get("held", 0), sw=bst.get("sw", 0),
                                                stat=np.asarray(env.stats.get("ins_bind", np.zeros(4))).tolist()),
                                      drill=dict(bad=sorted(set(dst.get("bad", [])))[:5], frames=dst.get("drill_frames", 0),
                                                 begun=dst.get("begun", 0), longest=dst.get("longest", 0), verbs=dst.get("verbs", {}))))))


def child(out, base="", sets=(), drive_=False, a=None, extra=(), frames=0):
    cmd = [sys.executable, os.path.abspath(__file__), "--child", "--out", out, "--map", a.map, "--frames", str(frames or a.frames)]
    cmd += ["--base", base] if base else []
    cmd += [x for s in sets for x in ("--set", s)] + (["--drive"] if drive_ else []) + list(extra) + (["--cmd", a.cmd] if a.cmd else [])
    subprocess.run(cmd, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    z = np.load(out)
    return z, eval(str(z["notes"]))


def main(a):
    tmp = tempfile.mkdtemp()
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("PASS  " if good else "FAIL  ") + line, flush=True)

    zb, nb = child(os.path.join(tmp, "base.npz"), base=a.base, sets=("INSTR=0",), a=a)
    z0, n0 = child(os.path.join(tmp, "off.npz"), sets=("INSTR=0",), a=a)
    z1, n1 = child(os.path.join(tmp, "on.npz"), sets=("INSTR=1",), a=a)
    zd, nd = child(os.path.join(tmp, "drive.npz"), sets=("INSTR=1",), drive_=True, a=a)
    k = int(z0["n_ins"])
    w = zb["obs"].shape[2]
    say(z0["obs"].shape[2] == w + k and k > 0, "1  the list: {} inputs at {}, {} today ({} new); route {}, the order's map numbers {}".format(
        w, a.base, z0["obs"].shape[2], k, n0["route"], n1["om"]))
    say(np.array_equal(zb["obs"], z0["obs"][:, :, :w]) and np.array_equal(zb["rew"], z0["rew"]) and np.array_equal(zb["don"], z0["don"]),
        "1  off: the inputs, the pay and the rounds' ends as at {} over {} frames".format(a.base, a.frames))
    say(not z0["obs"][:, :, w:].any(), "1  off: the new columns are zeros")
    same = lambda za, zb: np.array_equal(za["obs"][:, :, :-4], zb["obs"][:, :, :-4]) and np.array_equal(za["rew"], zb["rew"]) and np.array_equal(za["don"], zb["don"])  # noqa: E731
    say(same(z0, z1), "2  on with no instruction given: as off, to the bit (but the four finish inputs of the weapon in hand, live for every seat)")
    say(not z1["obs"][:, :, w:-4].any() and z1["obs"][:, :, -4:].any(), "2  ... every other new column zero; those four live")
    say(nd["n_bad"] == 0, "3  given: zeros under none, one verb, every number in range ({} bad frames{})".format(
        nd["n_bad"], "" if not nd["bad"] else ": " + repr(nd["bad"])))
    say(bool(nd["moment_ok"]), "3  a moment carries the instruction")
    say(zd["obs"][:, :, w:].any(), "3  the columns are live under an instruction")
    print("      the states reached, frames by verb (on the way, doing, done, failed):")
    for v_, c in sorted(nd["states"].items()):
        print("        {:<8} {}".format(v_, c))
    zf, nf = child(os.path.join(tmp, "feat.npz"), sets=("INSTR=1",), a=a, extra=("--feat",))
    say(same(z0, zf), "5  instr_feat() and instr_state() at every tick, nothing picked: as off, to the bit (but those four)")
    say(np.array_equal(z1["obs"], zf["obs"]), "5  ... and exactly as on with nothing read (a read changes nothing)")
    zc, nc = child(os.path.join(tmp, "cand.npz"), sets=("INSTR=1",), a=a, extra=("--cand",))
    cd = nc["cand"]
    say(cd["n_bad"] == 0 and cd["forced"] > 0, "5  the candidates: shapes, ranges, invalid rows, picks land, the force holds and lifts ({} bad ticks{}; {} forced ticks)".format(
        cd["n_bad"], "" if not cd["bad"] else ": " + repr(cd["bad"]), cd["forced"]))
    print("      valid seat-ticks by row (go 7, contest 4, hold 8, spam 4, push, cut 3, out 3, none, spare, check 3, spawn push 3, spawn spam 3): {}".format(cd["rows_ok"]))
    say(zc["obs"][:, :, w:].any(), "5  a picked row reaches the hands' inputs")
    zr, nr = child(os.path.join(tmp, "drill.npz"), sets=("INSTR=1", "DRILL_INS_P=1", "INS_DRILL_SECS=2"), a=a, extra=("--drill",), frames=max(a.frames, 6000))
    dr = nr["drill"]
    say(dr["begun"] > 0 and not dr["bad"] and dr["longest"] <= int(2.0 / 0.025) + 8,
        "6  the drills: {} begun, {} seat-frames, the longest {} frames (the window 80), verbs {}{}".format(
            dr["begun"], dr["frames"], dr["longest"], dr["verbs"], "" if not dr["bad"] else "; " + repr(dr["bad"])))
    zm, nm = child(os.path.join(tmp, "drillm.npz"), sets=("INSTR=1", "DRILL_INS_RATE=0.05", "INS_DRILL_SECS=2"), a=a, extra=("--drill",), frames=max(a.frames, 6000))
    dm = nm["drill"]
    share_ = dm["frames"] / float(max(a.frames, 6000) * zm["obs"].shape[1])
    say(dm["begun"] > 20 and not dm["bad"] and dm["longest"] <= int(2.0 / 0.025) + 8 and 0.03 < share_ < 0.15,
        "6  (2.1a) drills begun in the middle of a game (DRILL_INS_RATE=0.05 a second, 2 s each): {} begun, {:.1%} of the seats' frames in one (0.05 x 2 / 1.1 = 9% less the "
        "dead and the waiting), the longest {} frames, verbs {}{}".format(dm["begun"], share_, dm["longest"], dm["verbs"], "" if not dm["bad"] else "; " + repr(dm["bad"])))
    zt0, _ = child(os.path.join(tmp, "truth0.npz"), sets=("INSTR=1", "RESPAWN_QL=1"), a=a, frames=max(a.frames, 6000))
    zt1, _ = child(os.path.join(tmp, "truth1.npz"), sets=("INSTR=1", "RESPAWN_QL=1", "KNOWN_TRUTH=1", "SPAWN_TRUTH=1"), a=a, frames=max(a.frames, 6000))
    say(all(np.array_equal(zt0[q], zt1[q]) for q in ("obs", "rew", "don")), "7  the labels on (KNOWN_TRUTH, SPAWN_TRUTH), nothing picked: the game as with them off, to the bit")
    zt, nt = child(os.path.join(tmp, "truth.npz"), sets=("INSTR=1", "RESPAWN_QL=1", "KNOWN_TRUTH=1", "SPAWN_TRUTH=1"), a=a, extra=("--truth",), frames=max(a.frames, 6000))
    tr = nt["truth"]
    say(tr["n_bad"] == 0, "7  the labels and the new rows: en_knows only with the enemy's sight or a fresh picture within reach, en_spawn where he stands, "
        "check rows only with a belief, spawn rows only in their seconds and about a real spawn point, quiet lands ({} bad frames{})".format(
            tr["n_bad"], "" if not tr["bad"] else ": " + repr(tr["bad"])))
    say(tr["knows"] > 0 and tr["born"] > 0 and tr["check_ok"] > 0 and tr["spawn_ok"] > 0 and tr["forced"] > 0,
        "7  they occur: en_knows {} seat-frames, heard {}, respawns labelled {}, check rows valid {}, spawn rows valid {}, quiet forced {} ticks; under each verb {}".format(
            tr["knows"], tr["heard"], tr["born"], tr["check_ok"], tr["spawn_ok"], tr["forced"], tr["verbs"]))
    say(bool(tr["moment_ok"]), "7  a moment carries quiet and the row's spawn point, not the quiet force")
    es0, _ = child(os.path.join(tmp, "es0.npz"), sets=("INSTR=0", "EN_STACK=1"), a=a)
    es1, _ = child(os.path.join(tmp, "es1.npz"), sets=("INSTR=1", "EN_STACK=1"), a=a)
    say(same(es0, es1), "8  with his stack belief on (EN_STACK=1): on with nothing given as off, to the bit (but those four)")
    zl, _ = child(os.path.join(tmp, "label.npz"), sets=("INSTR=1", "EN_STACK=1", "HEAD_PAY_TRUTH=1"), a=a)
    say(all(np.array_equal(es1[q], zl[q]) for q in ("obs", "rew", "don")), "8  the head's pay label on (HEAD_PAY_TRUTH=1): the game as with it off, to the bit")
    zq, nq_ = child(os.path.join(tmp, "fin.npz"), sets=("INSTR=1", "EN_STACK=1"), drive_=True, a=a, extra=("--fin",), frames=max(a.frames, 6000))
    fn = nq_["fin"]
    say(fn["n_bad"] == 0, "8  the finish time: the hands' columns and the rows' numbers within 0 .. 2 and equal to _fin(), zero for the dead, the cautious time "
        "never under the plain one, instr_state() of 8 numbers, instr_pattern() in 0, 1, 2 ({} bad frames{})".format(fn["n_bad"], "" if not fn["bad"] else ": " + repr(fn["bad"])))
    say(fn["belief"] > 0 and fn["wake"] > 0 and fn["pat1"] > 0, "8  they occur: seat-frames with a belief {}, under 2 s to finish with the weapon in hand {}, chunk hits {}, "
        "seat-ticks under an instruction {}, with a wake {}, with the believed stack fallen since it was given {}; pattern moments: after a hit {} seat-frames, "
        "a fight's start with both stacks high {}".format(fn["belief"], fn["short"], fn["chunk"], fn["ticks_on"], fn["wake"], fn["fell"], fn["pat1"], fn["pat2"]))
    say(bool(fn["moment_ok"]), "8  a moment carries the wake's and the pattern's books")
    say(fn["chunk_ok"] is not False, "8  a chunk hit booked (note_dealt) marks the attacker alone and makes a pattern's moment where the enemy is near{}".format(
        "" if fn["chunk_ok"] else " (NOT CHECKED: a seat was dead at the frame)"))
    two = ("INSTR=1", "EN_STACK=1", "RESPAWN_QL=1", "KNOWN_TRUTH=1", "SPAWN_TRUTH=1", "HEAD_PAY_TRUTH=1")
    zg, ng = child(os.path.join(tmp, "grp.npz"), sets=two, drive_=True, a=a)
    z2, n2 = child(os.path.join(tmp, "two.npz"), sets=two, drive_=True, a=a, extra=("--module", "duel_env"))
    cut, nf = int(zg["cut"]), int(zg["n_ffa"])
    og = np.concatenate([zg["obs"][:, :, :cut], zg["obs"][:, :, cut + nf:]], 2)
    say(nf > 0 and og.shape == z2["obs"].shape and np.array_equal(og, z2["obs"]) and np.array_equal(zg["rew"], z2["rew"]) and np.array_equal(zg["don"], z2["don"])
        and ng["states"] == n2["states"],
        "4b the two-player module (sim/duel_env.py) and the generated group module at two players, on {} under instructions with every 2.1 switch on: "
        "the inputs (but the group block's {}), the pay and the rounds' ends alike to the bit".format(a.map, nf))
    b1, _ = child(os.path.join(tmp, "bind1.npz"), sets=("INSTR=1", "INS_BIND=1"), a=a)
    say(all(np.array_equal(z1[q], b1[q]) for q in ("obs", "rew", "don")), "9  the binding on (INS_BIND=1), no instruction given: as with it off, to the bit")
    zb9, nb9 = child(os.path.join(tmp, "bind.npz"), sets=("INSTR=1", "INS_BIND=1"), drive_=True, a=a, extra=("--bind",), frames=max(a.frames, 6000))
    bd = nb9["bind"]
    say(not bd["bad"] and bd["bound"] > 0 and bd["sw"] > 0, "9  under instructions: the action set is the one definition's, a seat bound for 2 s holds the weapon "
        "({} seat-frames bound, the asked weapon in hand on {:.0%} of them, a switch asked on {}; stats[ins_bind] readings, bound, not his own pick, weapon changes {}{})".format(
            bd["bound"], bd["held"] / max(bd["bound"], 1), bd["sw"], bd["stat"], "" if not bd["bad"] else "; " + repr(bd["bad"])))
    zo9, no9 = child(os.path.join(tmp, "bind0.npz"), sets=("INSTR=1", "INS_BIND=0"), drive_=True, a=a, extra=("--bind",), frames=max(a.frames, 6000))
    say(no9["bind"]["bound"] == 0 and not np.array_equal(zo9["obs"], zb9["obs"]), "9  with it off under the same instructions: nothing bound, and the games differ")
    f1, nf1 = child(os.path.join(tmp, "nonone.npz"), sets=("INSTR=1", "INS_NO_NONE=1"), a=a, extra=("--feat",), frames=max(a.frames, 6000))
    f0, _ = child(os.path.join(tmp, "nonone0.npz"), sets=("INSTR=1",), a=a, extra=("--feat",), frames=max(a.frames, 6000))
    nr = nf1["norow"]
    say(all(np.array_equal(f0[q], f1[q]) for q in ("obs", "rew", "don")), "11 (2.1a) the row 'none' never offered (INS_NO_NONE=1), nothing picked: the game as with it off, to the bit")
    say(nr[0] > 0, "11 a real row to pick: of {:.0f} readings of a living network seat, {:.0f} had no valid real row ({:.4%}; {:.0f} of them on a map without tables)".format(
        nr[0], nr[1], nr[1] / max(nr[0], 1), nr[2]))
    fc, nfc = child(os.path.join(tmp, "nononec.npz"), sets=("INSTR=1", "INS_NO_NONE=1"), a=a, extra=("--cand",), frames=max(a.frames, 6000))
    say(nfc["cand"]["n_bad"] == 0, "11 the candidates with it on: the row 'none' never valid, the rest as before ({} bad ticks{})".format(
        nfc["cand"]["n_bad"], "" if not nfc["cand"]["bad"] else ": " + repr(nfc["cand"]["bad"])))
    w1, _ = child(os.path.join(tmp, "way1.npz"), sets=("INSTR=1", "INS_WAY=1"), a=a, extra=("--feat",))
    say(np.array_equal(z1["obs"], w1["obs"]) and np.array_equal(z1["rew"], w1["rew"]) and np.array_equal(z1["don"], w1["don"]),
        "10 (2.1a) the receiver's side on (INS_WAY=1), the rows read at every tick: the game as with it off, to the bit (the rows are the head's, not the hands')")
    wc, nw_ = child(os.path.join(tmp, "wayc.npz"), sets=("INSTR=1", "INS_WAY=1"), a=a, extra=("--cand",), frames=max(a.frames, 6000))
    wy = nw_["cand"]["way"] or [0, 0, 0, 0.0, 0.0]
    m_ = wy[3] / max(wy[0], 1)
    say(nw_["cand"]["n_bad"] == 0 and wy[1] > 0, "10 the rows are 3 wider, every number in range, an invalid row zero ({} bad ticks{}); of {} valid rows {:.1%} have a watched "
        "spam point on the way, {:.1%} at a teleporter's end; way_seen_t mean {:.3f} spread {:.3f}".format(
            nw_["cand"]["n_bad"], "" if not nw_["cand"]["bad"] else ": " + repr(nw_["cand"]["bad"]), wy[0], wy[1] / max(wy[0], 1), wy[2] / max(wy[0], 1),
            m_, max(wy[4] / max(wy[0], 1) - m_ * m_, 0.0) ** 0.5))
    if os.path.exists(os.path.join(MAPS, "testlab.bsp")):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ffa_check.py")], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        say(r.returncode == 0 and "TWO PLAYERS: identical" in r.stdout, "4  tools/ffa_check.py: the two-player module and the group module alike")
    else:
        print("NOT RUN  4  tools/ffa_check.py: it plays on the test map and there is no testlab.bsp under {} (4b above is its comparison on {})".format(MAPS, a.map), flush=True)
    print("ALL PASSED" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--map", default="bloodrun")
    ap.add_argument("--frames", type=int, default=2000)
    ap.add_argument("--base", default="")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--drive", action="store_true")
    ap.add_argument("--feat", action="store_true")
    ap.add_argument("--cand", action="store_true")
    ap.add_argument("--drill", action="store_true")
    ap.add_argument("--truth", action="store_true")
    ap.add_argument("--fin", action="store_true")
    ap.add_argument("--bind", action="store_true")
    ap.add_argument("--module", default="duel_env_ffa")
    ap.add_argument("--cmd", default="", help="a run's train.cmd: every case plays under its simulator settings (set lines), with the case's own laid over")
    a_ = ap.parse_args()
    if a_.child:
        run(a_)
    else:
        a_.base = a_.base or "c99cc02"
        main(a_)
