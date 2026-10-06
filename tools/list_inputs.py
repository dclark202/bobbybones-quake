"""Write docs/INPUTS.csv: every input of the network, in order, with what it means. The list is checked against the
simulator's own count, so it cannot silently fall behind: when inputs are added, add them here too.

    python tools/list_inputs.py            (Anaconda Python)
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import duel_env as E          # noqa: E402
import duel_env_ffa as F      # noqa: E402

rows = []


def add(group, name, meaning, scale="", since="v3"):
    rows.append([len(rows), group, name, meaning, scale, since])


XYZ = ("forward", "left", "up")
W = E.WEAPONS
WN = dict(rl="rocket launcher", rg="railgun", lg="lightning gun", mg="machine gun", sg="shotgun", gl="grenade launcher",
          pg="plasma gun", hmg="heavy machine gun", g="gauntlet")


def item(group, what, since="v3"):
    for ax in XYZ:
        add(group, "{}: {}".format(what, ax), "where it is from him, turned to his facing (known from the map, not from sight)", "units / 1000", since)
    add(group, "{}: exists".format(what), "the map has one", "0 or 1", since)
    add(group, "{}: seen up".format(what), "he is looking at it within 1500 units and it is there", "0 or 1", since)
    add(group, "{}: seen gone".format(what), "he is looking at its place within 1500 units and it is taken", "0 or 1", since)


# ---- himself
for ax in XYZ:
    add("self", "velocity: {}".format(ax), "his own speed, turned to his facing", "units/s / 400")
add("self", "on the ground", "standing on something", "0 or 1")
add("self", "health", "", "/ 200")
add("self", "armor", "", "/ 200")
add("self", "weapon not ready", "time until he can fire (reload or weapon change)", "seconds / 1.5, capped at 1")
add("self", "view pitch", "looking up or down", "degrees / 90")
add("self", "dead", "", "0 or 1")
add("self", "mouse speed: turn", "how fast his view is turning", "degrees per frame / 30")
add("self", "mouse speed: pitch", "", "degrees per frame / 30")
# ---- surroundings
for k in range(E.N_WALL):
    add("walls", "wall distance at {:.1f} deg".format(k * 360.0 / E.N_WALL),
        "distance to the wall in that direction (0 = straight ahead, counted to the left), at body height; -1 when outside his field of view",
        "units / 512, capped at 1")
for k in range(E.N_FLOOR):
    add("floor", "drop at {} deg".format(k * 45), "how far down the floor is, 96 units away in that direction; -1 when outside his field of view",
        "units / 256, capped at 1")
# ---- the enemy
add("enemy", "noticed in view", "in his field of view with a clear line, for long enough to be noticed (as it was one reaction time ago)", "0 or 1")
add("enemy", "seen or heard recently", "fades after he was last seen or heard", "exp(-seconds)")
for ax in XYZ:
    add("enemy", "last known position: {}".format(ax), "from him, turned to his facing; exact while in view, rough when only heard", "units / 1000")
for ax in XYZ:
    add("enemy", "velocity: {}".format(ax), "only while in view; read 200 ms late", "units/s / 400")
add("enemy", "direction: sin", "angle from his crosshair to the enemy, left-right", "sin")
add("enemy", "direction: cos", "", "cos")
add("enemy", "direction up-down: cos", "", "cos")
add("enemy", "direction up-down: sin", "", "sin")
add("enemy", "crosshair error left-right, coarse", "", "degrees / 15, capped at 1")
add("enemy", "crosshair error left-right, fine", "", "degrees / 2, capped at 1")
add("enemy", "crosshair error up-down, coarse", "", "degrees / 15, capped at 1")
add("enemy", "crosshair error up-down, fine", "", "degrees / 2, capped at 1")
add("enemy", "crosshair on him", "a shot along the view would hit", "0 or 1")
add("enemy", "apparent size", "how big he looks (nearer = bigger)", "degrees / 10, capped at 1")
for j in range(E.N_PROJ):
    n_ = "nearest" if j == 0 else "second nearest"
    for ax in XYZ:
        add("projectiles", "{} enemy projectile: position {}".format(n_, ax), "within 1500 units and in view (or within 400)", "units / 1000")
    for ax in XYZ:
        add("projectiles", "{} enemy projectile: velocity {}".format(n_, ax), "", "units/s / 1000")
    for k_ in ("rocket", "grenade", "plasma"):
        add("projectiles", "{} enemy projectile: is a {}".format(n_, k_), "", "0 or 1")
# ---- weapons
for w in W:
    add("weapons", "holding {}".format(WN[w]), "", "0 or 1")
for w in W:
    add("weapons", "owns {}".format(WN[w]), "", "0 or 1")
for w in W:
    add("weapons", "ammo: {}".format(WN[w]), "", "share of the maximum")
# ---- items
NAMES = dict(MH="mega health", RA="red armor", YA="yellow armor", GA="green armor", RL="rocket launcher", RG="railgun",
             LG="lightning gun", SG="shotgun", GL="grenade launcher", PG="plasma gun", HMG="heavy machine gun")
for lab in E.SLOTS:
    item("items", "nearest {}".format(NAMES[lab]))
add("movement goal", "goal set", "movement rounds and courses only (zero in fights)", "0 or 1")
for ax in XYZ:
    add("movement goal", "goal: {}".format(ax), "where the goal or the far end of the course is", "units / 2000")
for ax in XYZ:
    add("movement goal", "next waypoint: {}".format(ax), "movement rounds on real maps only", "units / 500")
assert len(rows) == E.OBS_BASE, (len(rows), E.OBS_BASE)

# ---- added for duel_gru_v4
add("clock and score", "round time", "", "seconds / 120, capped at 2", "v4")
for per in (25, 35, 60):
    add("clock and score", "clock: sin, {} s cycle".format(per), "armor comes back every 25 s, mega and health every 35 s", "sin", "v4")
    add("clock and score", "clock: cos, {} s cycle".format(per), "", "cos", "v4")
add("clock and score", "his frags this round", "", "/ 10, capped at 2", "v4")
add("clock and score", "enemy frags this round", "the best of the others with more than two players", "/ 10, capped at 2", "v4")
add("clock and score", "score difference", "", "/ 5, between -2 and 2", "v4")
for what in ("second yellow armor", "nearest health (25 or 50)", "second nearest health", "third nearest health",
             "nearest health bubble or armor shard", "second nearest bubble or shard", "nearest ammo box", "second nearest ammo box"):
    item("more items", what, "v4")
SND = ("item pickup", "weapon fire", "jump", "teleport")
for c_ in SND:
    add("sounds", "heard: {}".format(c_), "fades after the enemy made that sound within 1200 units", "exp(-seconds)", "v4")
for c_ in SND:
    for ax in XYZ:
        add("sounds", "{} sound: position {}".format(c_, ax), "roughly where it came from, for 5 seconds", "units / 1000", "v4")
for k_ in ("mega health", "red armor", "other armor", "a weapon"):
    add("sounds", "pickup heard was {}".format(k_), "for 5 seconds", "0 or 1", "v4")
for ax in ("x", "y", "z"):
    add("place", "position on the map: {}".format(ax), "", "-1 to 1 across the map", "v4")
for m in E.MAP_IDS:
    add("place", "map is {}".format(m), "all zero on the test maps", "0 or 1", "v4")
for q in (-25, 0, 25):
    for y in (-40, -20, 0, 20, 40):
        add("sight", "view distance: {} deg {}, {} deg {}".format(abs(y), "left" if y > 0 else "right" if y < 0 else "ahead",
                                                               abs(q), "down" if q > 0 else "up" if q < 0 else "level"),
            "how far he sees along that line of his view (angles shrink when zoomed)", "units / 2000, capped at 1", "v4")
for n_ in ("straight up", "up and ahead", "up and left", "up and behind", "up and right"):
    add("sight", "ceiling: {}".format(n_), "distance to what is above; -1 when outside his field of view", "units / 512, capped at 1", "v4")
for k in range(E.N_LONG):
    add("sight", "long distance at {} deg".format(k * 45), "far wall distance in that direction; -1 when outside his field of view",
        "units / 2000, capped at 1", "v4")
for w in W:
    add("enemy", "enemy holds {}".format(WN[w]), "only while in view", "0 or 1", "v4")
add("enemy", "enemy facing: sin", "whether the enemy is turned toward him; only while in view", "sin", "v4")
add("enemy", "enemy facing: cos", "", "cos", "v4")
add("enemy", "damage dealt to the enemy this life", "what he knows he has hit for; no readout of the enemy's health", "/ 200, capped at 2", "v4")
add("hits", "damage dealt this frame", "", "/ 100, capped at 2", "v4")
add("hits", "damage taken this frame", "", "/ 100, capped at 2", "v4")
add("hits", "hit came from: sin", "direction of the attacker", "sin", "v4")
add("hits", "hit came from: cos", "", "cos", "v4")
for ax in XYZ:
    add("place", "nearest teleporter entrance: {}".format(ax), "", "units / 1000", "v4")
for ax in XYZ:
    add("place", "its exit: {}".format(ax), "", "units / 1000", "v4")
add("place", "map has a teleporter", "", "0 or 1", "v4")
for ax in XYZ:
    add("place", "nearest jump pad: {}".format(ax), "", "units / 1000", "v4")
add("place", "map has a jump pad", "", "0 or 1", "v4")
add("self", "crouched", "", "0 or 1", "v4")
assert len(rows) == E.OBS_BASE + E.N_EXTRA, (len(rows), E.OBS_BASE + E.N_EXTRA)

# ---- added for duel_gru_v5 (2026-10-05)
add("enemy shots", "enemy firing now", "a shot he saw (enemy noticed in view) or heard (within 1200 units) in the last frames", "0 or 1", "v5")
add("enemy shots", "enemy shot recently", "fades after the last shot", "exp(-2 x seconds)", "v5")
add("enemy shots", "time since the enemy's last shot", "", "seconds / 3, capped at 1", "v5")
for w in W:
    add("enemy shots", "last shot was a {}".format(WN[w]), "every weapon has its own sound; for 5 seconds", "0 or 1", "v5")
add("enemy shots", "enemy reloading", "time until that weapon can fire again", "seconds / 1.5", "v5")
add("enemy shots", "the shot was seen", "seen, not only heard", "0 or 1", "v5")
for ax in XYZ:
    add("enemy shots", "bullet, rail or lightning line: nearest point {}".format(ax), "the line of the enemy's last such shot while it is on screen (one second)",
        "units / 500, between -4 and 4", "v5")
add("enemy shots", "line just appeared", "fades", "exp(-4 x seconds)", "v5")
add("enemy", "enemy crouched", "only while in view", "0 or 1", "v5")
add("enemy", "enemy in the air", "only while in view", "0 or 1", "v5")
add("own hands", "forward / back key held", "what his fingers are actually holding", "-1, 0 or 1", "v5")
add("own hands", "strafe key held", "", "-1, 0 or 1", "v5")
add("own hands", "jump / crouch held", "", "1 jump, -1 crouch", "v5")
add("own hands", "left-hand stamina", "budget of key changes left (10 quick ones, refilling at 4 a second)", "0 to 1", "v5")
for f_ in ("ring finger (strafe left)", "middle finger (forward / back)", "index finger (strafe right, weapon keys)", "thumb (jump)",
           "little finger (crouch)"):
    add("own hands", "{} free".format(f_), "that finger can act again", "0 or 1", "v5")
add("own hands", "zoomed in", "", "0 or 1", "v5")
add("own hands", "fire finger free", "at most five clicks a second", "0 or 1", "v5")
add("own hands", "zoom finger free", "", "0 or 1", "v5")
for b_ in ("under 25", "25 to 49", "50 to 74", "75 or more"):
    add("enemy pain", "pain sound: enemy health {}".format(b_), "the sound an enemy makes when hit, heard within 1200 units; for 1.5 s", "0 or 1", "v5")
add("enemy pain", "pain sound just heard", "fades", "exp(-3 x seconds)", "v5")
# ---- memory aids (2026-10-05): things a player keeps in his head
for it_, tm in (("mega health", 35), ("red armor", 25)):
    add("memory", "{}: known to be taken".format(it_), "he took it, or heard it taken", "0 or 1", "v6")
    add("memory", "{}: how long ago".format(it_), "against its {} s timer".format(tm), "seconds / {}, capped at 2".format(tm), "v6")
add("memory", "enemy has the mega health", "heard or seen taken since his last death", "0 or 1", "v6")
add("memory", "enemy has the red armor", "heard or seen taken since his last death", "0 or 1", "v6")
for w in W:
    add("memory", "enemy seen with {}".format(WN[w]), "in his hands at some point since his last death", "0 or 1", "v6")
add("memory", "time since his own respawn", "", "seconds / 30, capped at 2", "v6")
add("memory", "enemy's last death known", "he killed him, or heard him die", "0 or 1", "v6")
add("memory", "time since the enemy's last death", "", "seconds / 30, capped at 2", "v6")
add("self", "focus left", "sharp tracking for 2 s with an enemy in view, then slower until it has come back", "-0.25 to 1", "v6")
assert len(rows) == E.OBS_DIM, (len(rows), E.OBS_DIM)

# ---- groups of more than two players (sim/duel_env_ffa.py): not in the network that is training now
for j in ("second", "third"):
    add("more enemies", "{} enemy in view".format(j), "another noticed enemy besides the one he attends to, nearest his crosshair first", "0 or 1", "ffa (not trained yet)")
    for ax in XYZ:
        add("more enemies", "{} enemy: position {}".format(j, ax), "as old as his reaction time", "units / 1000", "ffa (not trained yet)")
    add("more enemies", "{} enemy: direction sin".format(j), "", "sin", "ffa (not trained yet)")
    add("more enemies", "{} enemy: direction cos".format(j), "", "cos", "ffa (not trained yet)")
    add("more enemies", "{} enemy: direction up-down".format(j), "", "sin", "ffa (not trained yet)")
    add("more enemies", "{} enemy faces him".format(j), "", "cos", "ffa (not trained yet)")
add("more enemies", "enemies in view", "", "count / 5", "ffa (not trained yet)")
add("more enemies", "players beyond two", "", "(players - 2) / 4", "ffa (not trained yet)")
assert len(rows) == F.OBS_DIM, (len(rows), F.OBS_DIM)

out = os.path.join(ROOT, "docs", "INPUTS.csv")
with open(out, "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["index", "group", "input", "meaning", "scale", "added in"])
    wr.writerows(rows)
groups = {}
for r in rows:
    groups[r[1]] = groups.get(r[1], 0) + 1
print("{} inputs ({} in the network training now) -> docs/INPUTS.csv".format(len(rows), E.OBS_DIM))
print(", ".join("{} {}".format(v, k) for k, v in groups.items()))
ACT = ("forward / back", "strafe", "jump / crouch", "turn speed", "pitch speed", "fire", "weapon key", "walk (does nothing)", "zoom")
print("outputs: " + ", ".join("{} ({} choices)".format(n, d) for n, d in zip(ACT, E.ACTION_DIMS)))
