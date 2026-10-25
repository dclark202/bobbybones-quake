"""The mind view's log (B-283; the owner, 2026-10-24: a live view of what Bobby thinks, on a second monitor, nothing in the
game itself). While the owner has it on (`!mind on` in plugins/duelbot.py), the 1v1 plugin writes one JSON line at every
tick of the brain (0.2 s) into the server's data folder (/tmp/practice/mind.jsonl); tools/mind_view.py serves a page that
draws it. Plain numpy and the standard library: nothing here touches the game, so it can be tested on recorded numbers.

A line ("k": "f"):
  t      wall time (s);  map;  fr  the plugin's frame count
  me     Bobby's place and view yaw [x, y, z, yaw] (map coordinates, yaw in degrees);  en  the opponent's, the truth
  seen   the opponent noticed in Bobby's view this frame (his own sense: the time since he noticed him under 0.1 s)
  bel    the brain's believed place of the opponent: ok (there is an answer), p [x, y, z], sxy / sz (one spread, units),
         unseen (s since he noticed him), zones (the three likeliest zones: [name, odds, [x, y, z]])
  ahead  the readout ahead (the export's "ahead"): [{h: seconds, p: [x, y, z], sxy}] for 1, 2 and 4 s; tgt: the opponent's
         target as the brain guesses it, the likeliest four [name, odds, [x, y, z] or null]; appear: the odds that he comes
         into view in under 1 s, 1-3 s, 3-6 s, over 6 s; race: mh / ra {lead (s of way, his minus Bobby's), sd, there}
         (null without the readout)
  score  [Bobby, opponent] as Bobby is shown it;  left  seconds of the game left as he is shown it
  win    Bobby's chance of winning from the pros' table (sim/win_chance.json, as WIN_PAY reads it) by lead and time left
  ctl    "in control" (v0.4.3's readout: his share of the next two mega / red armor spawns), null without it; with the
         readouts of v0.4.2b (sim/control.py layout 2) also ctl_src (the readout used: "both", the brain's state and the
         hands' memory, or "belief", the brain's state alone) and ctl4 {two, one, mh, ra}
A meta line ("k": "meta") at the start and at every map: the map's items and holding places, the version.
Writing never raises: a failure turns the log off for that session and is logged once."""
import json
import math
import os
import time

import numpy as np

INTENTS = ("none", "MH", "RA", "RL", "RG", "LG", "YA", "YA2", "EN", "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8")
HORIZ = (1.0, 2.0, 4.0)
LS_XY = (math.log(0.04), math.log(4.0))       # sim/ahead.py's spreads (thousands of units)
LS_Z = (math.log(0.03), math.log(1.5))
LS_L = (math.log(0.02), math.log(3.0))
LEAD_U = 10.0
ROTATE_BYTES = 64 * 1024 * 1024               # a full file is renamed mind.<date-time>.jsonl and kept (the owner: keep everything)


def _sim_dirs():
    here = os.path.dirname(os.path.abspath(__file__))
    return ["/sim", os.path.join(os.path.dirname(here), "sim")]


def _squash(x, lo, hi):
    mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
    return mid + half * np.tanh((x - mid) / half)


def _softmax(l):
    l = np.asarray(l, np.float64)
    e = np.exp(l - l.max())
    return e / e.sum()


def _mlp(W, s):
    w0, b0, w1, b1 = W
    return np.maximum(s @ w0.T + b0, 0.0) @ w1.T + b1


def _turn(yaw_deg, f, l):
    r = math.radians(float(yaw_deg))
    c, s = math.cos(r), math.sin(r)
    return c * f - s * l, s * f + c * l


def _r(v, n=1):
    return [round(float(x), n) for x in v]


# ---------------------------------------------------------------- the readouts in the export (sim/export_duel.py)
def readouts(P):
    """the readouts the mind view shows, from a policy.npz dict: {"ahead": (layout, weights), "control": (layout, weights)}
    (each missing when the file lacks it); kept in P["_mind"]"""
    if "_mind" in P:
        return P["_mind"]
    R = {}
    for name in ("ahead", "control"):
        ks = ["{}.{}.{}".format(name, i, w) for i in (0, 2) for w in ("weight", "bias")]
        if name in P and all(k in P for k in ks):
            try:
                R[name] = (json.loads(str(P[name])), tuple(np.asarray(P[k], np.float32) for k in ks))
            except (ValueError, TypeError):
                pass
    if "control" not in R and "control" in P:                # (v0.4.2b, sim/control.py layout version 2) readouts side by side:
        try:                                                 # weights {name: (w0, b0, w1, b1)} of "control.<name>.{0,2}.*"
            L = json.loads(str(P["control"]))
            if int(L.get("version", 1)) == 2:
                W = {}
                for r_ in L.get("readouts", []):
                    ks = ["control.{}.{}.{}".format(r_["name"], i, w) for i in (0, 2) for w in ("weight", "bias")]
                    if all(k in P for k in ks):
                        W[r_["name"]] = tuple(np.asarray(P[k], np.float32) for k in ks)
                if W:
                    R["control"] = (L, W)
        except (ValueError, TypeError, KeyError):
            pass
    P["_mind"] = R
    return R


def ahead_of(L, W, s, pose):
    """the readout ahead on the brain's state s [256] at his pose [x, y, z, yaw] -> (ahead list, targets (all 17 odds),
    appear odds, race dict or None)"""
    o = _mlp(W, np.asarray(s, np.float32)[None])[0].astype(np.float64)
    nh = len(L.get("horiz", HORIZ))
    out = []
    for k in range(nh):
        f, l, u, lxy, lz = o[5 * k:5 * k + 5]
        x_, y_ = _turn(pose[3], f * 1000.0, l * 1000.0)
        out.append(dict(h=float(L.get("horiz", HORIZ)[k]), p=_r([pose[0] + x_, pose[1] + y_, pose[2] + u * 1000.0]),
                        sxy=round(1000.0 * math.exp(float(_squash(lxy, *LS_XY))), 1),
                        sz=round(1000.0 * math.exp(float(_squash(lz, *LS_Z))), 1)))
    nt = int(L["n_target"])
    tg = _softmax(o[5 * nh:5 * nh + nt])
    na = len(L.get("appear", (1, 3, 6))) + 1
    ap = _softmax(o[5 * nh + nt:5 * nh + nt + na])
    race = None
    if L.get("race"):
        r0 = 5 * nh + nt + na
        race = {}
        for k, nm in enumerate(("mh", "ra")):
            le, ls, th = o[r0 + 3 * k:r0 + 3 * k + 3]
            race[nm] = dict(lead=round(float(le) * LEAD_U, 1), sd=round(LEAD_U * math.exp(float(_squash(ls, *LS_L))), 1),
                            there=round(1.0 / (1.0 + math.exp(-float(th))), 3))
    return out, tg, ap, race


def control_src(L, W, mem=None):
    """the readout used (layout version 2): "both" when the hands' memory is given and the file has it, else "belief"
    (None for a layout of version 1: one readout on the brain's state)"""
    if not isinstance(W, dict):
        return None
    if mem is not None and "both" in W:
        return "both"
    return "belief" if "belief" in W else None


def control_all(L, W, s, mem=None):
    """the readout "in control" -> (its four outputs as odds 0..1 in L["outs"] order, the readout's name).
    Version 2 (sim/control.py, v0.4.2b): each readout is Linear(inp -> hid) + ReLU + Linear(hid -> 4), sigmoid, on the
    ring's row as the trainer keeps it: the brain's state s [256] at its tick, then (for "both") the hands' GRU memory
    [512] after that frame's step, both rounded to half precision (the ring is float16); a readout reads the row's first
    inp numbers. Version 1: one readout on s."""
    if isinstance(W, dict):
        nm = control_src(L, W, mem)
        if nm is None:
            raise KeyError("control: no readout to use")
        x = np.asarray(s, np.float32).reshape(-1)
        if nm == "both":
            x = np.concatenate([x, np.asarray(mem, np.float32).reshape(-1)])
        inp = int(W[nm][0].shape[1])
        x = x[:inp].astype(np.float16).astype(np.float32)
        o = _mlp(W[nm], x[None])[0].astype(np.float64)
    else:
        nm = None
        o = _mlp(W, np.asarray(s, np.float32)[None])[0].astype(np.float64)
    return 1.0 / (1.0 + np.exp(-o)), nm


def control_of(L, W, s, mem=None):
    """"in control": the output "two" (his share of the next two big spawns), 0..1"""
    p, _ = control_all(L, W, s, mem)
    outs = list(L.get("outs") or ["two"])
    i = outs.index("two") if "two" in outs else 0
    return float(p[i])


# ---------------------------------------------------------------- the win table (sim/win_chance.json)
_WIN = {}


def win_table(path=None):
    """(p [time steps, leads], step s, D) or None"""
    if "t" not in _WIN:
        _WIN["t"] = None
        for p_ in ([path] if path else []) + [os.path.join(d, "win_chance.json") for d in _sim_dirs()]:
            if p_ and os.path.exists(p_):
                with open(p_, encoding="utf-8") as fh:
                    wc = json.load(fh)
                p = np.array(wc["p"], np.float64)
                left = np.array(wc["left_s"], np.float64)
                _WIN["t"] = (p, float(left[1]), int(wc["diffs"][-1]))
                break
    return _WIN["t"]


def win_p(d, left, tab):
    """duel_env._win_p: the chance of winning for a player d frags ahead with `left` seconds to play"""
    p, step, D = tab
    x = min(max(float(left) / step, 0.0), p.shape[0] - 1.0)
    i0 = min(int(x), p.shape[0] - 2)
    f = x - i0
    j = int(np.clip(np.rint(d), -D, D)) + D
    return float(p[i0, j] * (1.0 - f) + p[i0 + 1, j] * f)


# ---------------------------------------------------------------- the line
def target_names(n):
    return list(INTENTS[:n]) + ["?{}".format(i) for i in range(len(INTENTS), n)]


def build(t, mapname, me, en, seen, tok, s, P, places, score, left, zones=None, frame=0, mem=None):
    """one line of the log as a dict.
    me, en   [x, y, z, yaw] (Bobby, the opponent: the truth);  seen  the opponent noticed in view this frame
    tok      the brain's answer: dict(ok, P [3], ls [2] (log spreads, thousands of units), unseen, zone [24] odds) or None
    s        the brain's state [256] (the readouts read it) or None
    P        the policy dict (its readouts: readouts(P))
    mem      the hands' GRU memory [512] after this frame's step (the readout "both" reads it beside s) or None
    places   {target name: [x, y, z]} (the map's items and holding places) for the targets' places
    score    (Bobby, opponent);  left  seconds left;  zones  a sim/zonemap.Zones of the map (or None) for the zones' names"""
    rec = dict(k="f", t=round(float(t), 3), fr=int(frame), map=mapname, me=_r(me[:3]) + [round(float(me[3]), 1)],
               en=_r(en[:3]) + [round(float(en[3]), 1)], seen=bool(seen))
    if tok is not None:
        b = dict(ok=bool(tok["ok"]), p=_r(tok["P"]), sxy=round(1000.0 * math.exp(float(tok["ls"][0])), 1),
                 sz=round(1000.0 * math.exp(float(tok["ls"][1])), 1), unseen=round(float(tok["unseen"]), 2))
        z = np.asarray(tok.get("zone") if tok.get("zone") is not None else [], np.float64)
        if zones is not None and z.size and z.sum() > 0:
            top = np.argsort(-z, kind="stable")[:3]
            b["zones"] = [[(zones.names[i] if i < len(zones.names) else "") or "zone {}".format(int(i) + 1), round(float(z[i]), 3),
                           _r(zones.centres[i]) if i < len(zones.centres) else None] for i in top if z[i] > 0]
        rec["bel"] = b
    else:
        rec["bel"] = None
    R = readouts(P)
    places = dict(places, EN=_r(me[:3]))                     # (the target "EN": Bobby himself)
    rec["ahead"] = rec["tgt"] = rec["appear"] = rec["race"] = rec["ctl"] = None
    if s is not None and "ahead" in R:
        L, W = R["ahead"]
        ah, tg, ap, race = ahead_of(L, W, s, me)
        rec["ahead"] = ah
        names = target_names(len(tg))
        top = np.argsort(-tg, kind="stable")[:4]
        rec["tgt"] = [[names[i], round(float(tg[i]), 3), _r(places[names[i]]) if names[i] in places else None] for i in top]
        rec["appear"] = _r(ap, 3)
        rec["race"] = race
    if s is not None and "control" in R:
        Lc, Wc = R["control"]
        pc, nm = control_all(Lc, Wc, s, mem)
        outs = list(Lc.get("outs") or ["two"])
        rec["ctl"] = round(float(pc[outs.index("two") if "two" in outs else 0]), 3)
        if nm is not None:                                   # (v0.4.2b) which readout, and its four outputs
            rec["ctl_src"] = nm
            rec["ctl4"] = {o_: round(float(pc[i]), 3) for i, o_ in enumerate(outs[:len(pc)])}
    rec["score"] = [int(score[0]), int(score[1])]
    rec["left"] = round(float(left), 1)
    tab = win_table()
    rec["win"] = round(win_p(score[0] - score[1], left, tab), 4) if tab is not None else None
    return rec


def meta(mapname, items, holds, version="", note=""):
    """the map's line: items {label: [x, y, z]}, holds [[x, y, z], ...] (H1 .. H8)"""
    return dict(k="meta", t=round(time.time(), 3), map=mapname, version=str(version), note=note,
                items={k: _r(v) for k, v in items.items()}, holds=[_r(h) for h in holds])


class Writer:
    """appends lines to path; rotates a full file into mind.<date-time>.jsonl; never raises (a failure: off, logged once)"""

    def __init__(self, path, log=None, rotate=ROTATE_BYTES):
        self.path, self.log, self.rotate = path, log, int(rotate)
        self.fh, self.dead = None, False
        self.n = 0

    def write(self, rec):
        if self.dead:
            return False
        try:
            if self.fh is None:
                self.fh = open(self.path, "a", encoding="utf-8")
            self.fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
            self.fh.flush()
            self.n += 1
            if self.fh.tell() > self.rotate:
                self.fh.close()
                self.fh = None
                base, ext = os.path.splitext(self.path)
                to, i = "{}.{}{}".format(base, time.strftime("%Y%m%d-%H%M%S"), ext), 1
                while os.path.exists(to):
                    to, i = "{}.{}-{}{}".format(base, time.strftime("%Y%m%d-%H%M%S"), i, ext), i + 1
                try:
                    os.replace(self.path, to)
                except OSError as e:                         # (a reader holding it open on Windows): go on in the same file
                    self.rotate *= 2
                    if self.log:
                        self.log("mind view: could not rotate {} ({!r}); writing on in it".format(self.path, e))
            return True
        except Exception as e:                               # noqa: BLE001 - the game goes on whatever happens here
            self.dead = True
            if self.log:
                try:
                    self.log("mind view: writing {} failed ({!r}); the mind log is off".format(self.path, e))
                except Exception:                            # noqa: BLE001
                    pass
            return False

    def close(self):
        try:
            if self.fh is not None:
                self.fh.close()
        except Exception:                                    # noqa: BLE001
            pass
        self.fh = None
