"""How far he is from the pros: one scorecard (owner, 2026-10-11: "frame his progression as 'convergence on pros' in terms
of some metrics that capture the pro play: position, speed bursts, combos, aggressive play ... The real numbers will
likely have to come from him playing himself, using the nightmare bot as a validation holdout set").

    python tools/convergence.py v14 v15b v15c [--speed v15c=data/sim_runs/.../speed/x_game.json ...] [--json out.json]

Each tag is a network that tools/bobby_yardsticks.py has played against itself (docs/bobby_yardsticks_<tag>.json); the
pros are docs/pro_yardsticks.json (the six trained maps). Fourteen measures in five groups, the pros' value beside his,
and for each how near he is: 100% at the pros' value, 0% at a distance of the measure's scale or more (the scale is the
pros' own value, or for a difference the pros' difference). The index is the mean nearness, by group and in all.
These are measures, not rewards: nothing here is paid.

The speed measures come from tools/speed_profile.py (his games against the stand-in, travelling with no enemy in view):
give its file with --speed <tag>=<json>; without it they are left out of that tag's index."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRO_SPEED = dict(at_400=17.5, hop2=421.0, gained=70.0)      # the pros travelling: tools/speed_profile.py --demos (787 player-minutes)


def measures(a, routes=None, standing=None, speed=None):
    """the scorecard's numbers from one map-block of a yardstick file (the pros' or his)"""
    ag = a["aggression"]
    lf = ag["by_stack_and_last_frag"]
    out = {
        ("Position", "higher than the enemy in view, %"): a["predictability"]["height"]["higher_share"],
        ("Position", "time in the lowest third of the map, %"): a["predictability"]["lowest_third_share"],
        ("Position", "trips on the commonest way between two items, %"): routes["commonest"] if routes else None,
        ("Position", "distance he fights at (median, units)"): standing["distance_median"] if standing else None,
        ("Speed", "time at 400 or more while travelling, %"): speed["at_400"] if speed else None,
        ("Speed", "speed at the second hop of a chain"): speed["hop2"] if speed else None,
        ("Speed", "hops that gain speed, %"): speed["gained"] if speed else None,
        ("Weapons", "rockets a minute"): a["spam"]["rl"]["shots_a_minute"],
        ("Weapons", "rockets fired with no enemy in view, % of his rockets"): a["spam"]["rl"]["blind_share"],
        ("Weapons", "a rocket, then rail or lightning within 1.5 s, per ten minutes"): a["combinations"]["rocket then rail or lightning"]["per_ten_minutes"],
        ("Weapons", "rockets in hand with the enemy in view, %"): standing["weapon_shares"].get("rockets") if standing else None,
        ("Aggression", "closing when stacked: just after a frag less otherwise"):
            lf["over 125, fragged him under 10 s ago"]["closing_speed"] - lf["over 125, over 25 s ago or not yet"]["closing_speed"],
        ("Aggression", "closing when weak (under 60)"): ag["by_stack"]["under 60"]["closing_speed"],
        ("Control", "back at the mega within 2 s of its return, %"): a["items"]["mega"]["back_at_return_share"],
    }
    return out


def near(x, pro, scale):
    return None if x is None or pro is None else max(0.0, 1.0 - abs(x - pro) / scale)


def main():
    args = [x for x in sys.argv[1:]]
    speed, out_json, tags = {}, None, []
    i = 0
    while i < len(args):
        if args[i] == "--speed":
            t, f = args[i + 1].split("=", 1)
            j = json.load(open(f))
            speed[t] = dict(at_400=100.0 * j["at_400"]["time_share"], hop2=float(j["speed_at_hop"][1]["speed"]), gained=100.0 * j["gain_per_hop"]["gained"])
            i += 2
        elif args[i] == "--json":
            out_json = args[i + 1]
            i += 2
        else:
            tags.append(args[i])
            i += 1
    pro_all = json.load(open(os.path.join(ROOT, "docs", "pro_yardsticks.json")))["maps"]["all"]
    cols, pro_routes, pro_stand = {}, None, None
    for t in tags:
        b = json.load(open(os.path.join(ROOT, "docs", "bobby_yardsticks_{}.json".format(t))))
        r = b["routes"]["self"]
        cols[t] = measures(b["self"]["all"], dict(commonest=r["commonest_share"]), b["standing"]["self"], speed.get(t))
        pro_routes, pro_stand = dict(commonest=r["pros_commonest_share"]), b["standing"]["pros"]       # (the pros at the same number of trips of the same pairs)
    pro = measures(pro_all, pro_routes, pro_stand, PRO_SPEED)
    scale = {k: (abs(v) if v else 1.0) for k, v in pro.items()}
    print("| Group | Measure | The pros | " + " | ".join(tags) + " |")
    print("|---|---|---|" + "---|" * len(tags))
    idx = {t: {} for t in tags}
    for k in pro:
        row = []
        for t in tags:
            x = cols[t][k]
            n = near(x, pro[k], scale[k])
            if n is not None:
                idx[t].setdefault(k[0], []).append(n)
            row.append("-" if x is None else "{:.3g} ({:.0%})".format(x, n))
        print("| {} | {} | {:.3g} | {} |".format(k[0], k[1], pro[k] if pro[k] is not None else float("nan"), " | ".join(row)))
    groups = []
    for k in pro:
        if k[0] not in groups:
            groups.append(k[0])
    print()
    print("| How near the pros (100% = their value) | " + " | ".join(tags) + " |")
    print("|---|" + "---|" * len(tags))
    res = {t: {} for t in tags}
    for g in groups:
        for t in tags:
            v = idx[t].get(g)
            res[t][g] = None if not v else sum(v) / len(v)
        print("| {} | {} |".format(g, " | ".join("-" if res[t][g] is None else "{:.0%}".format(res[t][g]) for t in tags)))
    for t in tags:
        v = [x for g in groups for x in idx[t].get(g, [])]
        res[t]["all"] = sum(v) / max(1, len(v))
        res[t]["measures"] = len(v)
    print("| **All measures** | {} |".format(" | ".join("**{:.0%}** ({} measures)".format(res[t]["all"], res[t]["measures"]) for t in tags)))
    if out_json:
        json.dump(dict(pros={"{}: {}".format(*k): v for k, v in pro.items()}, tags={t: {"{}: {}".format(*k): v for k, v in cols[t].items()} for t in tags},
                       nearness=res), open(out_json, "w"), indent=1)


if __name__ == "__main__":
    main()
