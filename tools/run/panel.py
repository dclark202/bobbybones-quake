"""v0.5.0's behaviour panel (owner, 2026-10-26: "What is all going into monitoring?"; the checks played each save against the
previous one and counted intentions over every kind of round, so v0.4.4's spawn camping went unseen). A save and the control
(v0.4.2b's end) are played the same way, side by side, in the v050 simulator with the run's play settings:
  self   each against itself on bloodrun, hektik, aerowalk, campgrounds (6 games of 3 minutes a map)
  watch  each against the scripted watcher (a player who holds a spot with the rail) on bloodrun and hektik
and compared. RED when (any one is enough):
  targets   on a map, his held target X: save share > 2 x the control's AND > the control's + 0.10
  camping   on a map, time within 300 u of an item's or weapon's spawn: save > 2 x the control's AND > the control's + 0.10
  roaming   map cells a seat-minute (256 x 256 x 128 u), mean over the self maps: save < 0.85 x the control's
  hunting   frags a minute against the watcher, mean over its maps: save < 0.75 x the control's
  items     mega and red armor share against the watcher, mean: save < 0.85 x the control's (each)
  rockets   (added 2026-10-26 after the review) rocket launcher in hand at mid range, mean over the self maps: save < 0.75 x the
            control's (the earliest sign in the study: 0.15 -> 0.04 before the lightning gun took over)
  passive   (added 2026-10-26) frags a seat-minute in self-play, mean over the self maps: save < 0.70 x the control's (the
            speed pay's end at 04:00 must not turn into peace; 18 minutes a map is noisy, hence 0.70)
Reported, not gated: weapons in hand by distance, hit rates, in view, distance to the enemy.
    python panel_v050.py <save.pt> <tag> [PERCEPT_SPEED]          (standalone: writes panel/<tag>/... and prints the verdict)
    import panel_v050 as P; P.run(save, tag, ps) -> dict(green, reasons, save=metrics, ctrl=metrics)"""
import collections, glob, json, os, subprocess, sys, time
ROOT_ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # (the repo root: tools/run/ is two down)
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.dirname(HERE)
CODE = os.environ.get("PANEL_CODE") or ROOT_   # (v0.6.1: branch v061 = aim2 + the shaping and the warm-up)
RUN_ = os.environ.get("PANEL_RUN") or "duel_gru_v0_6_0"
PY = (os.environ.get("BB_PY") or r"C:\Users\dacla\anaconda3\python.exe")
CTRL = os.environ.get("PANEL_CTRL") or os.path.join(ROOT_, "data", "sim_runs", "duel_gru_v0_4_2", "keep", "policy_end_v042.pt")   # (v0.6.1: v0.6.0's end)
PAR = int(os.environ.get("PANEL_PAR") or 6)              # (v0.6.1: games at once; the watcher passes 3 while a check plays beside it)
SELF_MAPS = ("bloodrun", "hektik", "aerowalk", "campgrounds")
WATCH_MAPS = ("bloodrun", "hektik")
INT = ["none", "MH", "RA", "RL", "RG", "LG", "YA", "YA2", "EN"] + ["H%d" % i for i in range(1, 9)]
SPAWNS = ("MH", "RA", "YA", "RL", "RG", "LG")
# the run's play settings (the checks' + v0.5.0's play switches and !aim default)
PLAY = dict(AIM_LEVEL="3", WEAPON_FREE="1", GONE_BELIEF="1", TELEFRAG="1", TRICKS="1")
PLAY.update(dict(x_.split("=", 1) for x_ in (os.environ.get("PANEL_SETS") or "AIM_LEVEL=3,PERCEPT_SPEED=0,AIM2=1,AIM2_SPLIT=1,AIM2_FOCUS=1,AIM2_FLINCH=1,PERCEPT_SIGMA=0.9,PERCEPT_TAU=0.15,SURPRISE_MS=0,MOTOR_NOISE=0.10,MOTOR_BASE=0.05,AIM2_W=1,AIM2_SPLIT_W=1,AIM2_FOCUS_GAIN=0,AIM2_FOCUS_SIG=1.0,AIM2_C_SLIP=0.023,AIM2_S0=5,AIM2_CAP_SLIP=2.1,AIM2_C_ECC=0.06,AIM2_E0=0,AIM2_CAP_ECC=2.8,FLINCH_PER_DMG=0.012,FLINCH_MAX=0.7,FLINCH_TAU=0.3,VEL_DELAY_MS=200,VEL_WEBER=0.2,RANGE_WEBER=0.19").split(",") if "=" in x_))   # (v0.6.1: v0.6.0's aim
#                                                         switches as its run has them, NAME=VALUE,NAME=VALUE)


def live_caps():
    """PERCEPT_SPEED_MAX_RG / _LG as the run's live.json has them now (none before the restart of 2026-10-26)"""
    try:
        d = json.load(open(os.path.join(os.path.join(ROOT_, "data", "sim_runs"), RUN_, "live.json")))
    except Exception:                                        # noqa: BLE001
        return {}
    return {k: str(d[k]) for k in ("PERCEPT_SPEED_MAX_RG", "PERCEPT_SPEED_MAX_LG") if d.get(k)}


def settings(ps):
    S_ = json.load(open(os.path.join(HERE, "check_sets.json")))   # (the checks' play switches; from the scratchpad's v044w/, 2026-10-28)
    S_["LEGS_NET"] = os.path.join(ROOT_, "data", "sim_runs", "move_v17_look", "policy.npz")   # (the file carried the old checkout's path)
    S_.update(PLAY)
    S_["PERCEPT_SPEED"] = str(ps)
    S_.update(live_caps())                                   # (the cap by weapon, as the run has it now; both seats alike)
    return ["{}={}".format(k, v) for k, v in S_.items() if k != "OVERTIME"] + ["OVERTIME=1"]


def jobs(pol, out, ps):
    J = []
    for cond, maps, opp in (("self", SELF_MAPS, None), ("watch", WATCH_MAPS, "watcher")):
        d = os.path.join(out, cond)
        os.makedirs(d, exist_ok=True)
        env = dict(os.environ, DUMP_OUT=d, OPENBLAS_NUM_THREADS="1", PYTHONFAULTHANDLER="1", CUDA_VISIBLE_DEVICES="-1")
        for mp in maps:
            js = os.path.join(d, "eval_{}.json".format(mp))
            if os.path.exists(js):
                continue
            cmd = [PY, os.path.join(HERE, "dump_eval.py"), "--run", RUN_, "--policy", pol, "--map", mp, "--games", "6",
                   "--minutes", "3", "--procs", "2", "--json", js, "--round", "600", "--seed", "300",
                   "--react-ms", "125", "--acquire-ms", "225"]
            cmd += (["--opp", "policy:" + pol, "--opp-inputs", os.path.join(CODE, "docs", "INPUTS.csv"), "--opp-round", "600",
                     "--opp-react-ms", "125", "--opp-acquire-ms", "225"] if opp is None else ["--opp", opp])
            cmd += [x for s_ in settings(ps) for x in ("--set", s_)]
            J.append((cmd, env, js))
    return J


def play(J, par=None):
    par = par or PAR
    run_ = []
    while J or run_:
        while J and len(run_) < par:
            cmd, env, js = J.pop(0)
            run_.append(subprocess.Popen(cmd, cwd=CODE, env=env, creationflags=0x4000 | 0x08000000, stdout=open(js + ".log", "w"),
                                         stderr=subprocess.STDOUT))
        time.sleep(5)
        run_ = [p for p in run_ if p.poll() is None]


def metrics(out):
    M = {"self": {}, "watch": {}}
    for cond, maps in (("self", SELF_MAPS), ("watch", WATCH_MAPS)):
        for mp in maps:
            d = os.path.join(out, cond)
            js = os.path.join(d, "eval_{}.json".format(mp))
            zs = [np.load(f) for f in glob.glob(os.path.join(d, "dump_{}_*.npz".format(mp)))]
            if not os.path.exists(js) or not zs:
                continue
            v = json.load(open(js))["maps"][mp]; he = v["he"]
            P = np.concatenate([z["pos"] for z in zs]); H = np.concatenate([z["held"] for z in zs])
            S = np.concatenate([z["seat"] + 1000 * i for i, z in enumerate(zs)])
            cells = []
            for s in np.unique(S):
                q = P[S == s]; m_ = len(q) / 600.0
                if m_ > 0.5:
                    cells.append(len({(int(x // 256), int(y // 256), int(z // 128)) for x, y, z in q}) / m_)
            c = collections.Counter(H.tolist())
            near = {}
            ip, il = zs[0]["items_pos"], zs[0]["items_lab"]
            for lab in SPAWNS:
                pts = ip[[i for i, l_ in enumerate(il) if l_ == lab]]
                if len(pts):
                    dmin = np.min(np.linalg.norm(P[:, None, :] - pts[None, :, :], axis=2), axis=1)
                    near[lab] = float((dmin < 300).mean())
            kills = sum(he["kills"]) if isinstance(he.get("kills"), list) else float(he.get("kills") or 0)
            M[cond][mp] = dict(held={INT[k]: n / len(H) for k, n in c.items()}, near=near, cells=float(np.mean(cells)) if cells else 0.0,
                               fpm=kills / (int(v.get("games") or 6) * float(v.get("minutes") or 3)), view=he.get("in_view", 0),
                               mega=he.get("mega_share", 0), red=he.get("red_share", 0),
                               hand=(he.get("in_hand_by_distance") or {}), hit=he.get("hit_rate", {}), won=v["won"], lost=v["lost"],
                               inview=(he.get("in_hand_in_view") or {}), switches=he.get("switches_per_min"))
    return M


def judge(S, C):
    red = []
    for mp in SELF_MAPS:
        s, c = S["self"].get(mp), C["self"].get(mp)
        if not s or not c:
            red.append("{}: missing".format(mp)); continue
        for k, x in s["held"].items():
            y = c["held"].get(k, 0.0)
            if x > 2 * y and x > y + 0.10:
                red.append("targets {} {} {:.0%} (control {:.0%})".format(mp, k, x, y))
        for k, x in s["near"].items():
            y = c["near"].get(k, 0.0)
            if x > 2 * y and x > y + 0.10:
                red.append("camping {} near {} {:.0%} (control {:.0%})".format(mp, k, x, y))
    mean = lambda D, key, maps: float(np.mean([D[m][key] for m in maps if m in D]))   # noqa: E731
    cs, cc = mean(S["self"], "cells", SELF_MAPS), mean(C["self"], "cells", SELF_MAPS)
    if cs < 0.85 * cc:
        red.append("roaming {:.1f} cells/min (control {:.1f})".format(cs, cc))
    fs, fc = mean(S["watch"], "fpm", WATCH_MAPS), mean(C["watch"], "fpm", WATCH_MAPS)
    if fs < 0.75 * fc:
        red.append("hunting {:.2f} frags/min vs the watcher (control {:.2f})".format(fs, fc))
    for key in ("mega", "red"):
        a, b = mean(S["watch"], key, WATCH_MAPS), mean(C["watch"], key, WATCH_MAPS)
        if a < 0.85 * b:
            red.append("items {} share {:.2f} (control {:.2f})".format(key, a, b))
    rs = float(np.mean([S["self"][m]["hand"].get("mid", {}).get("rl", 0.0) for m in SELF_MAPS if m in S["self"]]))
    rc = float(np.mean([C["self"][m]["hand"].get("mid", {}).get("rl", 0.0) for m in SELF_MAPS if m in C["self"]]))
    if rs < 0.75 * rc:
        red.append("rockets in hand at mid range {:.2f} (control {:.2f})".format(rs, rc))
    ps_, pc_ = mean(S["self"], "fpm", SELF_MAPS), mean(C["self"], "fpm", SELF_MAPS)
    if ps_ < 0.70 * pc_:
        red.append("passive: {:.2f} frags a seat-minute in self-play (control {:.2f})".format(ps_, pc_))
    return red


PRO_FIGHT_HAND = {"rl": 0.41, "lg": 0.32, "rg": 0.14, "other": 0.12}   # the pros' weapon in hand in fights (docs/pro_yardsticks.json,
#                                                       all ten maps, fight_movement by weapon: minutes 2,158 / 1,693 / 729 / 634 of 5,268)


def report(S, C):
    """(v0.5.1, reported, not gated) weapons in hand with the enemy in view against the pros, switches a minute, the two jumps'
    proxies (Aerowalk's red armor share in self-play: only a jump reaches it; Campgrounds' rail in hand: only the b2r jump does)"""
    def hand(D):
        acc, n = {}, 0
        for mp in SELF_MAPS:
            iv = (D["self"].get(mp) or {}).get("inview") or {}
            if not iv:
                continue
            n += 1
            for w, x in iv.items():
                k = w if w in ("rl", "lg", "rg") else "other"
                acc[k] = acc.get(k, 0.0) + x
        return {k: round(v / max(1, n), 3) for k, v in acc.items()}
    sw = lambda D: round(float(np.mean([D["self"][m]["switches"] for m in SELF_MAPS if m in D["self"] and D["self"][m].get("switches") is not None] or [float("nan")])), 2)  # noqa: E731
    cg = lambda D: (D["self"].get("campgrounds") or {}).get("hand", {})  # noqa: E731
    cgr = lambda D: round(float(np.mean([b.get("rg", 0.0) for b in cg(D).values()] or [0.0])), 3)  # noqa: E731
    aw = lambda D: (D["self"].get("aerowalk") or {}).get("red")  # noqa: E731
    return dict(hand_in_view=hand(S), hand_ctrl=hand(C), hand_pros=PRO_FIGHT_HAND, switches_per_min=sw(S), switches_ctrl=sw(C),
                aerowalk_red_share=aw(S), aerowalk_red_ctrl=aw(C), campgrounds_rail_in_hand=cgr(S), campgrounds_rail_ctrl=cgr(C))


def summary(M):
    sm, wm = M["self"], M["watch"]
    out = {}
    for mp, s in sm.items():
        top = sorted(s["held"].items(), key=lambda kv: -kv[1])[:3]
        nr = sorted(s["near"].items(), key=lambda kv: -kv[1])[:2]
        out[mp] = "held {} | near {} | cells {:.1f}".format(" ".join("{} {:.0%}".format(k, v) for k, v in top),
                                                              " ".join("{} {:.0%}".format(k, v) for k, v in nr), s["cells"])
    for mp, w in wm.items():
        out["watch " + mp] = "fpm {:.2f} mega {:.2f} red {:.2f}".format(w["fpm"], w["mega"], w["red"])
    return out


def run(save, tag, ps, root=None):
    root = root or os.path.join(ROOT_, "data", "sim_runs", RUN_, "panel")
    out_s = os.path.join(root, tag, "save")
    out_c = os.path.join(root, "ctrl_{}_ps{}".format(os.path.splitext(os.path.basename(CTRL))[0], ps))   # (v0.6.1: the fixed control's
    #                                                         panel once for every save, by its live PERCEPT_SPEED: half the cost)
    play(jobs(save, out_s, ps) + jobs(CTRL, out_c, ps))
    S, C = metrics(out_s), metrics(out_c)
    red = judge(S, C)
    res = dict(tag=tag, percept_speed=ps, green=not red, reasons=red, save=summary(S), ctrl=summary(C), report=report(S, C))
    json.dump(dict(res, save_full=S, ctrl_full=C), open(os.path.join(root, tag, "panel.json"), "w"), default=float)
    return res


if __name__ == "__main__":
    r = run(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.075)
    print(json.dumps(r, indent=1))
