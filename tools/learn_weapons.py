"""Learn a weapon-choice table from how humans fire at BobbyBones.

For every frame where the human holds fire, record the situation from the shooter's point of view
(distance band, target above/level/below, target airborne) and the weapon used. The policy is the
most-used weapon per situation, given enough frames. Bands match itemrun.choose_weapon.

usage: python tools/learn_weapons.py <trace files...>   ->   data/practice/weapon_policy.json
"""
import json
import math
import sys
from collections import Counter, defaultdict

NAMES = {1: "G", 2: "MG", 3: "SG", 4: "GL", 5: "RL", 6: "LG", 7: "RG", 8: "PG", 11: "NG", 13: "CG", 14: "HMG"}
MIN_FRAMES = 40   # ~1 s of firing before a situation counts
MIN_DPS = 10.0    # the winning weapon must have done real damage in this situation


def band(dist, dz, air):
    return "{}|{}|{}".format(min(int(dist // 250), 6), "above" if dz > 64 else ("below" if dz < -64 else "level"),
                             "air" if air else "ground")


policy_counts = defaultdict(Counter)   # frames fired per (situation, weapon)
damage = defaultdict(Counter)          # damage dealt per (situation, weapon)
for fn in sys.argv[1:]:
    frames = defaultdict(dict)
    humans = set()
    for line in open(fn):
        f = line.split()
        if len(f) != 11:
            continue                                   # older recordings without weapon/buttons
        fr, cid = int(f[0]), int(f[1])
        x, y, z, vx, vy, vz = map(float, f[2:8])
        buttons = int(f[9])
        if buttons > 1:
            humans.add(cid)                            # real clients send extra button flags; bots only 0/1
        frames[fr][cid] = dict(pos=(x, y, z), vz=vz, weapon=int(f[8]), buttons=buttons, hp=int(f[10]))
    last_fire = {}                                     # shooter -> (frame, weapon, situation)
    prev_hp = {}
    for fr in sorted(frames):
        players = frames[fr]
        if len(players) != 2:
            prev_hp = {}
            continue
        for sid, s in players.items():
            t_id = next(k for k in players if k != sid)
            t = players[t_id]
            # damage the target just took -> credit the shooter's recent shot
            if sid in humans and t_id in prev_hp and 0 < t["hp"] < prev_hp[t_id] and sid in last_fire:
                ffr, w, key = last_fire[sid]
                if fr - ffr <= 40:
                    damage[key][w] += prev_hp[t_id] - t["hp"]
            if sid not in humans or not (s["buttons"] & 1) or s["hp"] <= 0 or t["hp"] <= 0 or s["weapon"] not in NAMES:
                continue
            key = band(math.dist(s["pos"], t["pos"]), t["pos"][2] - s["pos"][2], abs(t["vz"]) > 1)
            policy_counts[key][s["weapon"]] += 1
            last_fire[sid] = (fr, s["weapon"], key)
        prev_hp = {k: v["hp"] for k, v in players.items()}

policy = {}
for key in sorted(policy_counts):
    used = policy_counts[key]
    if sum(used.values()) < MIN_FRAMES:
        continue
    dmg = damage[key]
    # effectiveness: damage per second of firing, only for weapons used at least 0.5 s here
    eff = {w: dmg[w] / (used[w] / 40.0) for w in used if used[w] >= 20}
    if not eff or max(eff.values()) < MIN_DPS:
        continue                                       # not enough evidence: keep the bot's defaults here
    w = max(eff, key=eff.get)
    policy[key] = w
    print("{:<20} {:<3} dps by weapon: {}".format(key, NAMES[w], ", ".join(
        "{} {:.0f} ({:.1f}s)".format(NAMES[k], v, used[k] / 40.0) for k, v in sorted(eff.items(), key=lambda kv: -kv[1]))))
json.dump(policy, open("data/practice/weapon_policy.json", "w"), indent=1)
print("situations learned:", len(policy))
