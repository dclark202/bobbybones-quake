"""The generated starts' bias, from what he does not do in games (owner, 2026-10-25: "if the report shows he's not using the rail
on campgrounds say then it puts him more and more with rail or near its spawn so he learns to use it"; "specifically aimed
towards getting him to do stuff he is not doing in games (e.g. going for certain weapons)").

Reads his numbers per map from the weapon watch (one line a save: pick_per_min, held_in_view, items_det_per_min; short whole
games of the save) and the pros' from data/behaviour/pros_baseline.json, and writes GEN_BIAS (sim/duel_env.py's
GEN_START_SHARE) for the next starts:
  a gap        = 1 - his / the pros' (0 when he does it as much as they do or more; maps where the pros barely do it: none)
  near[w]      = NEAR_W x the pickup gap of weapon w (RL, RG) or big item (RA, MH): the chance the first seat starts within
                 GEN_NEAR of its spawn (a weapon: half the time not owned, so he takes it; half owned, so he uses it there)
  own[w]       = OWN_W x the in-hand gap: added to the chance he owns it at the start
  hand[w]      = 1 + HAND_W x the in-hand gap: its weight as the weapon in hand at the start
Each value moves STEP of the way from the last file's toward the new target (a slow, smooth bias: one watch line is a few
games a map), and is capped (the simulator caps the near chances at 0.6 a start in all). A line in gen_bias.log per write.
Run after every weapon-watch line:  python tools/gen_bias.py --watch <weapon_watch.jsonl> --out <run>/gen_bias.json"""
import argparse, json, os, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEAR_W, OWN_W, HAND_W, STEP = 0.20, 0.25, 2.0, 0.5
NEAR_CAP = 0.25


def gap(his, pro, floor):
    if pro is None or pro < floor or his is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(his) / float(pro)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", required=True)
    ap.add_argument("--baseline", default=os.path.join(r"C:\Users\dacla\ql-bot", "data", "behaviour", "pros_baseline.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--update", type=int, default=None, help="the watch line of this save (default: the newest)")
    ap.add_argument("--step", type=float, default=STEP)
    ap.add_argument("--fresh", action="store_true", help="ignore the last file: the targets at once")
    a = ap.parse_args()
    L = [json.loads(l) for l in open(a.watch, encoding="utf-8") if l.strip()]
    rec = [r for r in L if a.update is None or int(r["update"]) == a.update][-1]
    base = json.load(open(a.baseline, encoding="utf-8"))["maps"]
    old = {}
    if os.path.exists(a.out) and not a.fresh:
        old = json.load(open(a.out, encoding="utf-8"))
    out = dict(heat=old.get("heat", 1.0), uniform=old.get("uniform", 0.1), own=old.get("own", 0.5), maps={},
               made=time.strftime("%Y-%m-%d %H:%M"), from_update=int(rec["update"]), step=a.step)
    st = 1.0 if (a.fresh or not old) else a.step
    notes = []
    for mp, his in rec["maps"].items():
        pro = {k: v["pooled"] for k, v in (base.get(mp) or {}).get("measures", {}).items()}
        om = (old.get("maps") or {}).get(mp) or {}
        tg = dict(near={}, own={}, hand={})
        for w in ("rl", "rg"):
            g_pick = gap((his.get("pick_per_min") or {}).get(w), pro.get("pick_" + w), 0.1)
            g_hold = gap((his.get("held_in_view") or {}).get(w), pro.get("held_" + w), 0.05)
            tg["near"][w.upper()] = NEAR_W * g_pick
            tg["own"][w.upper()] = OWN_W * g_hold
            tg["hand"][w.upper()] = 1.0 + HAND_W * g_hold
        for it in ("ra", "mh"):
            tg["near"][it.upper()] = 0.5 * NEAR_W * gap((his.get("items_det_per_min") or {}).get(it), pro.get("pick_" + it), 0.3)
        m_ = {}
        for part, t_ in tg.items():
            o_ = om.get(part) or {}
            m_[part] = {}
            for k, v in t_.items():
                prev = float(o_.get(k, 1.0 if part == "hand" else 0.0))
                x = prev + st * (v - prev)
                x = min(NEAR_CAP, x) if part == "near" else x
                m_[part][k] = round(x, 4)
        out["maps"][mp] = m_
        top = sorted(((v, "near " + k) for k, v in m_["near"].items()), reverse=True)[:2] + \
            sorted(((v, "own " + k) for k, v in m_["own"].items()), reverse=True)[:1]
        notes.append("{} {}".format(mp, ",".join("{} {:.2f}".format(n, v) for v, n in top if v >= 0.01) or "-"))
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    for _ in range(20):
        try:
            os.replace(tmp, a.out)
            break
        except PermissionError:
            time.sleep(0.5)
    line = "{} u{}: {}".format(time.strftime("%m-%d %H:%M"), rec["update"], " | ".join(notes))
    with open(os.path.join(os.path.dirname(os.path.abspath(a.out)), "gen_bias.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


if __name__ == "__main__":
    main()
