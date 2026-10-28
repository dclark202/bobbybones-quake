"""The mind view's test without a game (B-283): the 1v1 plugin's own mind code (plugins/duelbot.py cmd_mind and mind_frame,
plugins/mindlog.py) driven with a network and recorded inputs, the game stubbed out.

    python tools/mind_test.py --policy data/<folder>/policy.npz --obs data/<folder>/obs_dump.npy --out data/mindtest
           [--maps bloodrun,aerowalk] [--frames 2000]

For each map: two walkers on the map's walking graph (data/maps/nav_<map>_sim.json) stand in for Bobby and the owner;
the network steps on the recorded inputs (an OBSDUMP of a real server; the brain therefore believes what those frames
said, not what the walkers do: this checks the plumbing, not the brain); the plugin's mind_frame writes its lines into
<out>/mind.jsonl, which tools/mind_view.py can then show. Checks: a line at every tick of the brain (every eighth
frame), the map line first, every field there and finite, the readout ahead's places turned to the map as sim/ahead.py
labels them (a round trip), the win table as duel_env._win_p, a writer that cannot write turns itself off and play goes
on, !mind off stops the lines. Numpy only: OPENBLAS_NUM_THREADS=1 is set here."""
import argparse
import json
import math
import os
import sys
import types

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np                                           # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "plugins"))


def stub_minqlx():
    m = types.ModuleType("minqlx")

    class Plugin:
        def __init__(self, *a, **k):
            pass
    m.Plugin = Plugin
    m.get_cvar = lambda *a, **k: ""
    m.owner = lambda: 0
    sys.modules["minqlx"] = m


class Walker:
    """a player walking the map's graph at about 320 units a second, turning to where he goes"""

    def __init__(self, nodes, nbr, rng, start):
        self.N, self.nbr, self.rng = nodes, nbr, rng
        self.a = start
        self.b = self._next(start, None)
        self.f = 0.0
        self.prev = None

    def _next(self, a, prev):
        c = [j for j in self.nbr[a] if j != prev] or self.nbr[a] or [a]
        return int(self.rng.choice(c))

    def step(self, dt=0.025, speed=320.0):
        pa, pb = self.N[self.a], self.N[self.b]
        d = float(np.linalg.norm(pb[:2] - pa[:2])) or 1.0
        self.f += speed * dt / d
        while self.f >= 1.0:
            self.f -= 1.0
            self.a, self.b, self.prev = self.b, self._next(self.b, self.a), self.a
            pa, pb = self.N[self.a], self.N[self.b]
            d = float(np.linalg.norm(pb[:2] - pa[:2])) or 1.0
        p = pa + (pb - pa) * self.f
        yaw = math.degrees(math.atan2(pb[1] - pa[1], pb[0] - pa[0]))
        return p, yaw


def env_for(mapname):
    """the plugin's simulator, stubbed: the arrays mind_frame reads"""
    nav = json.load(open(os.path.join(ROOT, "data", "maps", "nav_{}_sim.json".format(mapname)), encoding="utf-8"))
    N = np.array([n[:3] for n in nav["nodes"]], np.float64)
    nbr = [[] for _ in range(len(N))]
    for e in nav["edges"]:
        if len(e) < 4 or e[3] == "walk":
            nbr[int(e[0])].append(int(e[1]))
    env = types.SimpleNamespace(n=2, state=np.zeros((2, 7), np.float32), yaw=np.zeros(2, np.float32), frags_r=np.zeros(2, np.float32),
                                clock_t=np.zeros(2, np.float32), round_t=np.zeros(2, np.float32), hp=np.array([125, 125]),
                                armor=np.array([50, 0]), has=np.zeros((2, 9), bool))     # (the referee's stacks: win_ref)
    env.has[0, 0] = True                                     # (Bobby holds a rocket launcher: weapon 0, RL)
    goal, item, pos = [], [], []
    at = os.path.join(ROOT, "maps", "atlas", mapname + ".json")
    if os.path.exists(at):
        for it in json.load(open(at, encoding="utf-8"))["items"]:
            lab = it["name"].rstrip("12") if it["name"][:2] in ("RL", "RG", "LG") else it["name"]
            if lab in ("MH", "RA", "RL", "RG", "LG", "YA") and lab not in goal:
                goal.append(lab)
                item.append(len(pos))
                pos.append(it["pos"])
    env.route_goal, env.route_item, env.item_pos = goal, item, np.array(pos, np.float32).reshape(-1, 3)
    hl = os.path.join(ROOT, "sim", "pro_holds", mapname + ".json")
    env.hold_pos = np.array([p["pos"] for p in json.load(open(hl, encoding="utf-8"))["places"]][:8], np.float32) if os.path.exists(hl) else np.zeros((0, 3))
    return env, N, nbr


class Teller:
    def __init__(self):
        self.said = []

    def tell(self, s):
        assert "%" not in s, "a percent sign in a line to a player"
        self.said.append(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--obs", required=True, help="an OBSDUMP of a real server (obs_dump.npy) for the same inputs")
    ap.add_argument("--out", required=True)
    ap.add_argument("--maps", default="bloodrun,aerowalk")
    ap.add_argument("--frames", type=int, default=2000)
    a = ap.parse_args()
    stub_minqlx()
    import duelbot as DB
    import mindlog as ML
    import netpass as NP
    os.makedirs(a.out, exist_ok=True)
    out = os.path.join(a.out, "mind.jsonl")
    if os.path.exists(out):
        os.remove(out)
    DB.D = a.out
    obs_all = np.load(a.obs).astype(np.float32)
    rng = np.random.default_rng(7)
    bot = object.__new__(DB.duelbot)
    bot.log = lambda s: print("  [plugin]", s)
    bot.P, bot.attn = NP.load(a.policy)
    assert NP.brain_on(bot.P), "this network's brain is not stepped: nothing to show"
    R = ML.readouts(bot.P)
    print("network:", str(bot.P.get("run", "")), "readouts:", sorted(R))
    bot.mind_w = None
    bot.game_seat, bot.round_secs = True, 600.0
    bot.E = types.SimpleNamespace(RL=0, RG=1, LG=2)          # (the simulator's weapon numbers; WIN_* from mindlog's defaults)
    tel = Teller()
    bot.cmd_mind(tel, ["!mind", "on"], None)
    print("  [to the owner]", tel.said[-1])
    n_lines = 0
    for mi, mapname in enumerate(a.maps.split(",")):
        env, N, nbr = env_for(mapname)
        bot.mapname = mapname
        bot.h = np.zeros((1, NP.width(bot.P)), np.float32)
        wb, wo = Walker(N, nbr, rng, int(rng.integers(len(N)))), Walker(N, nbr, rng, int(rng.integers(len(N))))
        xl = np.zeros((1, bot.P["legs_w0"].shape[1]), np.float32) if NP.needs_xl(bot.P) else None
        t0 = 1.0e9 + 1000.0 * mi
        for f in range(a.frames):
            pb, yb = wb.step()
            po, yo = wo.step()
            env.state[0, :3], env.state[1, :3], env.yaw[:] = pb, po, (yb, yo)
            env.clock_t[:] = min(600.0, 300.0 + f * 0.025)
            env.frags_r[:] = (f // 600, f // 900)
            p_, z_ = NP.pose(bot.P, env, mapname)
            ob = obs_all[f % len(obs_all)][None]
            _, bot.h = NP.step(bot.P, bot.attn, ob, bot.h, rng, None, xl=xl, pose=p_[:1], zmap=z_[:1])
            bot.mind_frame(env, t0 + f * 0.025)
            assert bot.mind_w is not None, "the mind log turned itself off"
        lines = [json.loads(l) for l in open(out, encoding="utf-8")][n_lines:]
        n_lines += len(lines)
        assert lines[0]["k"] == "meta" and lines[0]["map"] == mapname, "the map line first"
        fr = [l for l in lines if l["k"] == "f"]
        assert abs(len(fr) - a.frames / 8) <= 1, "{} lines for {} frames: not one a tick".format(len(fr), a.frames)
        for l in fr:
            for k in ("me", "en", "bel", "ahead", "tgt", "appear", "race", "score", "left", "win"):
                assert k in l, k
            vals = l["me"] + l["en"] + l["bel"]["p"] + [x for h in l["ahead"] for x in h["p"]] + [l["win"]]
            assert all(math.isfinite(v) for v in vals), "a number that is not finite"
            assert abs(sum(t[1] for t in l["tgt"])) <= 1.0001 and abs(sum(l["appear"]) - 1) < 1e-2
            assert len(l["ahead"]) == 3 and [h["h"] for h in l["ahead"]] == [1.0, 2.0, 4.0]
            for k in ("win_his", "wv", "win_ref"):           # (2026-10-27) his win sense and the referee: null only without the head
                assert k in l, k
            assert ("win_value" in R) == (l["win_his"] is not None), "win_his: there exactly when the file has the win value"
            for k in ("win_his", "win_ref"):
                assert l[k] is None or 0.0 <= l[k] <= 1.0, k
        # the readout ahead's place, turned back into his facing, is the raw output (sim/ahead.py's labels: fwd = c dx + s dy)
        B_, bl_, bt_, at_, _ = bot.P["_brain"]
        br_, _tk = bt_.unpack(B_, bl_, bot.h[:1, at_:])
        Lh, Wh = R["ahead"]
        me = [float(v) for v in env.state[0, :3]] + [float(env.yaw[0])]
        ah, _, _, _ = ML.ahead_of(Lh, Wh, br_.s[0], me)
        o = ML._mlp(Wh, br_.s[:1])[0]
        c, s = math.cos(math.radians(me[3])), math.sin(math.radians(me[3]))
        for k in range(3):
            dx, dy = ah[k]["p"][0] - me[0], ah[k]["p"][1] - me[1]
            assert abs((c * dx + s * dy) / 1000.0 - o[5 * k]) < 2e-4 and abs((-s * dx + c * dy) / 1000.0 - o[5 * k + 1]) < 2e-4, "ahead: the turn"
        L = fr[-1]
        print("{}: {} lines; last: Bobby {} owner {} | belief {} (spread {:.0f}) | ahead 1/2/4 s {} | target {} | score {} left {:.0f} s win {}".format(
            mapname, len(lines), L["me"][:2], L["en"][:2], L["bel"]["p"][:2], L["bel"]["sxy"], [h["p"][:2] for h in L["ahead"]],
            L["tgt"][0][:2], L["score"], L["left"], L["win"]))
    # the win table as the simulator reads it
    tab = ML.win_table()
    wc = json.load(open(os.path.join(ROOT, "sim", "win_chance.json"), encoding="utf-8"))
    p = np.array(wc["p"])
    D = int(wc["diffs"][-1])
    assert ML.win_p(0, 600, tab) == 0.5 and ML.win_p(1, 600, tab) == p[-1, D + 1] and ML.win_p(-3, 0, tab) == 0.0
    assert abs(ML.win_p(2, 45, tab) - (0.5 * p[1, D + 2] + 0.5 * p[2, D + 2])) < 1e-12 and ML.win_p(25, 300, tab) == ML.win_p(D, 300, tab)
    # off
    bot.cmd_mind(tel, ["!mind", "off"], None)
    assert bot.mind_w is None
    # a writer that cannot write: off, never raises
    w = ML.Writer(os.path.join(a.out, "no_such_folder", "mind.jsonl"), log=lambda s: print("  [plugin]", s))
    assert w.write({"k": "f"}) is False and w.dead
    # rotation keeps the full file
    rp = os.path.join(a.out, "rot.jsonl")
    w = ML.Writer(rp, rotate=200)
    for i in range(10):
        w.write({"k": "f", "i": i, "pad": "x" * 40})
    w.close()
    import glob
    kept = glob.glob(os.path.join(a.out, "rot.*.jsonl"))
    assert kept, "no rotated file"
    for f_ in kept + [rp]:
        if os.path.exists(f_):
            os.remove(f_)
    print("all checks passed;", n_lines, "lines in", out)


if __name__ == "__main__":
    main()
