"""Rocket jumps: the real game (plugins/rjlab.py records) against the simulator (rj_sim.replay, RL_QL from the
environment). python tools/rj_compare.py <out.json> <rjlab.jsonl of ONE map> [...]; tables: tools/rj_report.py

Per jump: the blast hook, the self-damage at the blast (health, armor), the top upward speed after it, the rise (highest
point above the start before the landing), the landing hook (standing again), the horizontal distance at the landing or
at 1.5 s (hook 60) if he is still in the air, and the fall damage at the landing.
"""
import json
import math
import sys

import rj_sim

H15 = 60


def metrics(rows, ground=None):
    rows = [r for r in rows if r[0] >= 0]
    r0 = rows[0]
    blast = next((i for i in range(1, len(rows)) if rows[i][1] < rows[i - 1][1] - 0.01 or rows[i][2] < rows[i - 1][2] - 0.01), None)
    if blast is None:
        return None
    dmg = rows[blast - 1][1] - rows[blast][1]
    arm = rows[blast - 1][2] - rows[blast][2]
    land = None
    for i in range(blast + 1, len(rows)):
        if ground is not None:
            on = ground[i] > 0.5
        else:                                # the game: standing = no vertical speed after a frame with some
            on = abs(rows[i][8]) < 1e-3 and abs(rows[i - 1][8]) > 1e-3
        if on:
            land = i
            break
    seg = rows[:land + 1] if land is not None else rows
    zmax = max(r[5] for r in seg)
    end = land if land is not None and land <= H15 else min(H15, len(rows) - 1)
    dist = math.hypot(rows[end][3] - r0[3], rows[end][4] - r0[4])
    fall = 0.0
    if land is not None:
        fall = (rows[land - 1][1] - rows[min(land + 2, len(rows) - 1)][1]) + (rows[land - 1][2] - rows[min(land + 2, len(rows) - 1)][2])
    top_vz = max(r[8] for r in rows[blast:blast + 3])
    return dict(blast=rows[blast][0], dmg=round(dmg, 2), armor=round(arm, 2), total=round(dmg + arm, 2), top_vz=top_vz,
                rise=zmax - r0[5], land=rows[land][0] if land is not None else None, dist=dist, end=rows[end][0], fall=round(fall, 2))


def main():
    out_path = sys.argv[1]
    recs = [json.loads(l) for f in sys.argv[2:] for l in open(f)]
    recs = [r for r in recs if r["rep"] >= 0 and r.get("shot", True)]
    out = []
    for r in recs:
        g = metrics(r["rows"])
        srows = rj_sim.replay(r)
        h0 = [x for x in r["rows"] if x[0] == 0][0]
        srows = [[0, float(h0[1]), float(h0[2]), *h0[3:9], 1.0, None]] + srows
        s = metrics(srows, [x[9] for x in srows])
        out.append(dict(name=r["name"], map=r["map"], rep=r["rep"], place=r["place"], pitch=r["pitch"], view_pitch=h0[9],
                        fire=r["fire"], keys=r["keys"], hp=r["hp"], armor=r["armor"], game=g, sim=s))
    json.dump(out, open(out_path, "w"))
    print(len(out), "jumps written to", out_path)


if __name__ == "__main__":
    main()
