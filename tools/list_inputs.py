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
OW = [E.WEAPONS[i] for i in E.OBS_W]      # the weapons the inputs cover since v8
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
        add("projectiles", "{} enemy projectile: position {}".format(n_, ax), "within 1,500 units, inside his view cone, the line from his eyes clear (v15, PROJ_SEE; before it: through walls inside the cone, and within 400 units in any direction)", "units / 1000")
    for ax in XYZ:
        add("projectiles", "{} enemy projectile: velocity {}".format(n_, ax), "", "units/s / 1000")
    for k_ in ("rocket", "grenade", "plasma"):
        add("projectiles", "{} enemy projectile: is a {}".format(n_, k_), "", "0 or 1")
# ---- weapons
for w in OW:
    add("weapons", "holding {}".format(WN[w]), "", "0 or 1")
for w in OW:
    add("weapons", "owns {}".format(WN[w]), "", "0 or 1")
for w in OW:
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
for per in (25, 35):
    add("clock and score", "clock: sin, {} s cycle".format(per), "armor comes back every 25 s, mega and health every 35 s", "sin", "v4")
    add("clock and score", "clock: cos, {} s cycle".format(per), "", "cos", "v4")
add("clock and score", "his frags this round", "", "/ 10, capped at 2", "v4")
add("clock and score", "enemy frags this round", "the best of the others with more than two players", "/ 10, capped at 2", "v4")
add("clock and score", "score difference", "", "/ 5, between -2 and 2", "v4")
for what in ("nearest health (25 or 50)", "second nearest health", "nearest health bubble or armor shard", "second nearest bubble or shard"):
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
for w in OW:
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
for w in OW:
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
for w in OW:
    add("memory", "enemy seen with {}".format(WN[w]), "in his hands at some point since his last death", "0 or 1", "v6")
add("memory", "time since his own respawn", "", "seconds / 30, capped at 2", "v6")
add("memory", "enemy's last death known", "he killed him, or heard him die", "0 or 1", "v6")
add("memory", "time since the enemy's last death", "", "seconds / 30, capped at 2", "v6")
add("self", "focus left", "sharp tracking for 2 s with an enemy in view, then slower until it has come back", "-0.25 to 1", "v6")
# ---- routes (2026-10-06): the way along the floor, as a player who knows the map has it
for it_ in ("mega health", "red armor", "rocket launcher", "railgun", "lightning gun"):
    add("routes", "{}: travel time".format(it_), "along the floor from where he stands (zero on maps without a walking map)", "seconds / 10, capped at 2", "v7")
for it_ in ("yellow armor", "second yellow armor"):
    add("routes", "{}: travel time".format(it_), "along the floor from where he stands (zero where the map has none)", "seconds / 10, capped at 2", "v13")
# ---- the mouse pad and hearing (2026-10-06)
N_BEFORE = len(rows)                                     # (in the group network the "more enemies" block sits here)
add("own hands", "hand on the mouse pad", "from the left edge to the right edge; 240 degrees of turning across", "-1 to 1", "v7")
add("own hands", "mouse in the air", "lifted to set it back in the middle: the view does not turn for 125 ms", "0 or 1", "v7")
add("hearing", "sound just heard", "an enemy's running steps, jump, landing or shot within 1000 units, no line of sight needed", "0 or 1", "v7")
add("hearing", "sound heard recently", "fades", "exp(-2 x seconds)", "v7")
add("hearing", "direction of the sound: sin", "against his view, about 10 degrees rough; kept for 3 s", "sin", "v7")
add("hearing", "direction of the sound: cos", "", "cos", "v7")
add("hearing", "above or below", "height of the sound against his own", "units / 200, between -1.5 and 1.5", "v7")
add("hearing", "loudness", "1 next to him, 0 at the edge of earshot", "0 to 1", "v7")
add("hearing", "coming or going", "positive: the gap is closing", "units/s / 400, between -1.5 and 1.5", "v7")
add("hearing", "railgun hum", "an enemy within 500 units holds a railgun (heard even when he stands still)", "0 or 1", "v7")
add("hearing", "lightning gun hum", "an enemy within 500 units holds a lightning gun", "0 or 1", "v7")
for dist_ in (96, 224):
    for what_, why_ in (("lava", "the floor there burns"), ("deadly drop", "nothing there but a fall that kills")):
        for k in range(8):
            add("hazards", "{} at {} deg, {} units".format(what_, k * 45, dist_), why_ + "; only inside his field of view", "0 or 1", "v7")
for ax in XYZ:
    add("enemy", "last known speed: {}".format(ax), "his speed and heading when last seen, kept for 5 s", "units/s / 400", "v7")
for ax in XYZ:
    add("place", "where the nearest jump pad lands: {}".format(ax), "", "units / 1000", "v7")
for j in range(2):
    n_ = "nearest" if j == 0 else "second nearest"
    for ax in XYZ:
        add("projectiles", "his own {} projectile: position {}".format(n_, ax), "", "units / 1000", "v7")
    for ax in XYZ:
        add("projectiles", "his own {} projectile: velocity {}".format(n_, ax), "", "units/s / 1000", "v7")
    for k_ in ("rocket", "grenade", "plasma"):
        add("projectiles", "his own {} projectile: is a {}".format(n_, k_), "", "0 or 1", "v7")
# ---- v9 (2026-10-06): item respawns heard, the nearest spawn points
for k_ in ("the mega health", "the red armor", "a weapon", "a small health or armor"):
    add("sounds", "{} came back".format(k_), "the respawn sound, within 1200 units", "exp(-seconds)", "v9")
for j in range(4):
    for ax in XYZ:
        add("place", "spawn point {}: {}".format(j + 1, ax), "the four nearest places where players appear", "units / 1000", "v9")
# ---- the intention and the map cells (2026-10-06, v8)
add("intention", "chosen way: travel time", "seconds along the floor to the item he has chosen to go for (zero with none chosen)", "seconds / 10, capped at 2", "v8")
for ax in XYZ:
    add("intention", "chosen way: next step {}".format(ax), "where the way there leads next", "units / 200, between -1 and 1", "v8")
add("intention", "chosen item is up", "", "0 or 1", "v8")
add("intention", "chosen item comes back in", "", "seconds / 30, capped at 2", "v8")
for nm in ("none", "the mega health", "the red armor", "the rocket launcher", "the railgun", "the lightning gun"):
    add("intention", "going for {}".format(nm), "his own choice, read once a second and held", "0 or 1", "v8")
add("intention", "seconds since chosen", "", "seconds / 10, capped at 2", "v8")
for k in range(16):
    add("map reader", "his own cell: reading {}".format(k), "what the map reader (sim/map_reader.py) says about the 64-unit cell he stands in, learned from the game's maps", "about -2 to 2", "v9")
for k in range(16):
    add("map reader", "the enemy's last known cell: reading {}".format(k), "the same for where the enemy was last seen or heard (zero after 5 s)", "about -2 to 2", "v9")
for nm in ("general", "rockets", "rail", "lightning"):   # ---- playing styles (2026-10-08, v12)
    add("style", "playing style: {}".format(nm), "the state he is in this life: no preference, or a preferred weapon he is pushed to fetch, hold and fight at the distance of", "0 or 1", "v12")
for nm in ("the yellow armor", "the second yellow armor"):   # ---- v13
    add("intention", "going for {}".format(nm), "his own choice, read once a second and held", "0 or 1", "v13")
DROP_WHAT = "the nearest weapon a dead player left that he can see (it lies 30 seconds where it fell); zero without one"
for ax in XYZ:                                           # ---- weapons that dead players leave (2026-10-08, v13)
    add("dropped weapon", "nearest dropped weapon in view: {}".format(ax), DROP_WHAT, "units / 1000", "v13")
add("dropped weapon", "a dropped weapon is in view", DROP_WHAT, "0 or 1", "v13")
for nm in ("a rocket launcher", "a lightning gun", "a railgun"):
    add("dropped weapon", "the dropped weapon is {}".format(nm), "none of the three: another weapon", "0 or 1", "v13")
add("dropped weapon", "the dropped weapon's time left", "the share of its 30 seconds", "0 to 1", "v13")
MOVE_WHAT = "the angle from his view to the way he is moving; zero under 50 units a second"
for nm, what, sc in (("his speed over the ground", "", "units/s / 400, capped at 3"),      # ---- his own movement, read out for strafe jumping (2026-10-09, v14)
                     ("the way he moves against his view: sin", MOVE_WHAT, "sin"), ("the way he moves against his view: cos", MOVE_WHAT, "cos"),
                     ("speed gained in the last 100 ms", "", "units/s / 100, between -1 and 1")):
    add("his movement", nm, what, sc, "v14")
LEAD_WHAT = ("where a rocket or a plasma ball fired now would meet the enemy he sees, from what he knows of the enemy's movement "
             "(a reaction time old); zero with another weapon in hand or no enemy in view")
for nm, sc in (("meeting point: crosshair error left-right, coarse", "degrees / 30, capped at 1"),      # ---- the lead of a shot (v14)
               ("meeting point: crosshair error left-right, fine", "degrees / 2, capped at 1"),
               ("meeting point: crosshair error up-down, coarse", "degrees / 15, capped at 1"),
               ("meeting point: crosshair error up-down, fine", "degrees / 2, capped at 1"),
               ("the shot's flight time", "seconds / 1.5, capped at 2"),
               ("the floor under the meeting point lies below it by", "degrees / 15, capped at 1 (1: no floor near)")):
    add("lead", nm, LEAD_WHAT, sc, "v14")
JUMP_WHAT = ("the first of the pros' jumps on his way (sim/jump_links.py): in a jump run, or a jump that is open in his games (JUMP_OPEN); "
             "zero without one within 1,500 units of way")
for nm, sc in (("a jump is ahead on his way", "0 or 1"), ("the speed the jump needs", "units/s / 600"),      # ---- a jump ahead (2026-10-10, v15)
               ("the way to the jump's take-off", "units / 1000, capped at 1.5"), ("the jump's length", "units / 600"),
               ("the jump's rise", "units / 100, between -3 and 1")):
    add("jump ahead", nm, JUMP_WHAT, sc, "v15")
ARC_WHAT = ("with the grenade launcher in his hand and the enemy seen in the last 3 seconds: his view against the one that lands a grenade "
            "at the enemy's feet (the low arc); zero otherwise")
for nm, sc in (("grenade arc: view error left-right, coarse", "degrees / 30, capped at 1"),                  # ---- a grenade's arc (v15)
               ("grenade arc: view error left-right, fine", "degrees / 2, capped at 1"),
               ("grenade arc: view error up-down, coarse", "degrees / 15, capped at 1"),
               ("grenade arc: view error up-down, fine", "degrees / 2, capped at 1"),
               ("the grenade's flight time", "seconds / 1.5, capped at 2"), ("the grenade reaches", "0 or 1")):
    add("grenade arc", nm, ARC_WHAT, sc, "v15")
PROJ_WHAT = ("an enemy projectile he sees (PROJ_SEE: inside his view cone, within 1,500 units, the line from his eyes clear), nearest "
             "first; the nearest two are the inputs of old")
for j in ("third", "fourth", "fifth", "sixth"):          # ---- the projectiles he sees beyond the nearest two (v15)
    for ax in XYZ:
        add("projectiles", "{} nearest enemy projectile: position {}".format(j, ax), PROJ_WHAT, "units / 1000", "v15")
    for ax in XYZ:
        add("projectiles", "{} nearest enemy projectile: velocity {}".format(j, ax), "", "units/s / 1000", "v15")
    for kd in ("a rocket", "a grenade", "a plasma"):
        add("projectiles", "{} nearest enemy projectile: is {}".format(j, kd), "", "0 or 1", "v15")
for j in ("nearest", "second nearest", "third nearest", "fourth nearest", "fifth nearest", "sixth nearest"):
    add("projectiles", "{} enemy projectile: a grenade's fuse left".format(j), "the share of its 2.5 seconds; zero for a rocket or plasma", "0 to 1", "v15")
    add("projectiles", "{} enemy projectile: seconds until it passes closest to him".format(j), "as if both kept their speed", "seconds / 2, capped at 1", "v15")
    add("projectiles", "{} enemy projectile: how close it passes".format(j), "in its splash radii (rocket 120 units, grenade 150, plasma 20)",
        "radii / 3, capped at 1 (under a third: inside its blast)", "v15")
add("his legs", "the switch to his legs is on", "the movement network moves him while it is on and he has a target it knows a way to (LEGS)",      # ---- his legs (2026-10-10, v15b)
    "0 or 1", "v15b")
add("his legs", "his legs carried him on the last frame", "", "0 or 1", "v15b")
add("intention", "his intention is the enemy", "the ninth intention (FIGHT_TARGET; HUNT, v0.3.1: B-256): his way leads to where he believes the enemy is", "0 or 1", "v15f")     # ---- the enemy as a target (2026-10-11)
assert len(rows) == E.OBS_DIM - E.N_V02 - E.N_B2 - E.N_B3 - E.N_ES - E.N_RAIM - E.N_PREF - E.N_EMG - E.N_DRIFT, (len(rows), E.OBS_DIM - E.N_V02 - E.N_B2 - E.N_B3 - E.N_ES - E.N_RAIM - E.N_PREF - E.N_EMG - E.N_DRIFT)
# ---- v0.2 (2026-10-11): stage A of the attention model, five groups (N_V02 in sim/duel_env.py; the tokens are cut by these group names)
V02 = "v0.2"
add("v02 game", "time left in the round", "the share of the round's length still to play (on a game server: of the game's time limit)", "0 to 1", V02)
add("v02 game", "how loud he has been", "over the last 3 seconds: a frame of running steps counts one frame, a shot (not the gauntlet), a jump or a landing eight; "
    "1 = heard all the time. Walking and crouching are silent", "0 to 1", V02)
add("v02 game", "made a noise near a believed enemy", "in the last second he made such a noise while he believed an enemy within earshot (seen or heard in the "
    "last 3 s, within 1,000 units of where he was). From what he believes, not from where the enemy is", "0 or 1", V02)
BEL = "the place he believes the enemy is: his last known place and up to a second of his last known movement; believed for 20 s after he was last seen or heard, not across a round's start or a death of his that he knows of"
CELL = "from sim/pro_places/<map>_cells.json for the cell of 256 x 256 x 128 units he stands in (zero where the pros were seen under 30 times, or the map has no file)"
add("v02 position", "height above the believed enemy", BEL + "; zero with nothing believed", "units / 300, between -1 and 1", V02)
add("v02 position", "height among the map's standing places", "the share of the walking map's points that lie below him", "0 (lowest) to 1 (highest)", V02)
add("v02 position", "pros in this cell: outcome over expected", "frags less deaths in the 10 s after a sighting that begins with a pro standing here, less what his stack and "
    "the weapons would give anywhere; " + CELL, "/ 0.3, between -1 and 1", V02)
add("v02 position", "pros in this cell: sightings", CELL, "log(1 + n) / log(1 + the map's busiest cell)", V02)
for w_ in ("rockets", "rail", "lightning"):
    add("v02 position", "pros in this cell: {} in hand".format(w_), "the share of their time here with the enemy in view; " + CELL, "share (0 to 1)", V02)
add("v02 position", "pros in this cell: push share", "the share of their sightings here after which they close on the enemy at over 150 units a second; " + CELL, "share / 0.5, capped at 1", V02)
add("v02 position", "this cell has numbers", CELL, "0 or 1", V02)
add("v02 position", "places with a clear line", "how many of the eight place slots (v02 places) he has a clear line to from his eyes", "count / 8", V02)
add("v02 believed", "a place is believed", BEL, "0 or 1", V02)
for ax in XYZ:
    add("v02 believed", "believed place: {}".format(ax), BEL + "; from him, turned to his facing; as old as his reaction time and with his error of sight while in view; zero with nothing believed",
        "units / 1500, between -2 and 2", V02)
HEARD = "heard: running within 800 units out of view, or any sound the simulator delivers (steps, jumps, landings, shots, a weapon's hum, pickups, teleporters)"
add("v02 believed", "seconds since he last heard him", HEARD, "seconds / 20, capped at 1 (1: never in this round and life of his)", V02)
for ax in XYZ:
    add("v02 believed", "where he last heard him: {}".format(ax), "about where the sound came from, from where he stands now; zero if never", "units / 1500, between -2 and 2", V02)
add("v02 believed", "how far he can have got since", "400 units for every second since he was last seen or heard", "units / 3000, capped at 1 (1: nothing believed)", V02)
add("v02 believed", "way to the believed place", "seconds along the walking map from where he stands", "seconds / 15, capped at 1 (1: none, or nothing believed)", V02)
for it_ in ("mega health", "red armor"):
    add("v02 believed", "way from the believed place to the {}".format(it_), "seconds along the walking map", "seconds / 15, capped at 1 (1: the map has none, or nothing believed)", V02)
add("v02 believed", "damage dealt to him this life", "the same number as the older input: what he knows he has hit for", "/ 200, capped at 2", V02)
add("v02 believed", "seconds since his life began", "since the frag he made or heard; with none known, since the round began", "seconds / 60, capped at 1", V02)
add("v02 believed", "his last death is known", "he made the frag or heard it", "0 or 1", V02)
for it_ in ("the mega health", "the red armor", "a yellow or green armor"):
    add("v02 believed", "times he took {} this life".format(it_), "pickups heard within 1,200 units or made in his view, since that player's last spawn", "count / 2, capped at 1", V02)
for w_ in ("rockets", "rail", "lightning"):
    add("v02 believed", "seen with {} this life".format(w_), "in his hands at some point since his last death (the same flag as the older memory input)", "0 or 1", V02)
for lab in E.SLOTS:
    add("v02 items", "since he took: nearest {}".format(NAMES[lab]), "seconds since HE last took the item the slot's own inputs describe", "seconds / 40, capped at 1 (1: not in this round, or the map has none)", V02)
for what in ("nearest health (25 or 50)", "second nearest health", "nearest health bubble or armor shard", "second nearest bubble or shard"):
    add("v02 items", "since he took: {}".format(what), "seconds since HE last took the item the slot's own inputs describe", "seconds / 40, capped at 1 (1: not in this round, or the map has none)", V02)
PLACE = "one of the eight places of sim/pro_places/<map>.json (where the pros' shots land with nobody in view) nearest to him, nearest first; zeros on a map without a list"
for j in range(1, E.V02_SLOTS + 1):
    for ax in XYZ:
        add("v02 places", "place {}: {}".format(j, ax), PLACE, "units / 1500, between -2 and 2", V02)
    add("v02 places", "place {}: distance".format(j), PLACE, "units / 2000, capped at 1.5", V02)
    add("v02 places", "place {}: clear line".format(j), "the line from his eyes to it is clear (looked at every eighth frame, whichever way he faces)", "0 or 1", V02)
    add("v02 places", "place {}: distance from the believed enemy".format(j), BEL, "units / 1500, capped at 1 (1: nothing believed)", V02)
    add("v02 places", "place {}: share of the pros' blind shots".format(j), "of the map's rockets, grenades and plasma fired with nobody in view", "per cent / 15, capped at 1", V02)
    add("v02 places", "place {}: pros meet the enemy there".format(j), "the share of their shots at it after which the enemy came into view near it within 2 s", "share (0 to 1)", V02)
    add("v02 places", "place {}: pros hit the enemy there".format(j), "the share of their shots at it at whose landing a hit was counted; zero where it is not known", "share (0 to 1)", V02)
    add("v02 places", "place {}: outcome over expected standing there".format(j), "as for his cell, for a pro seen standing within 128 units of it; zero where it is not known", "/ 0.3, between -1 and 1", V02)
    add("v02 places", "place {}: nearest to the believed enemy".format(j), "of all the map's places this one is nearest to " + BEL.split(":")[0], "0 or 1", V02)
    add("v02 places", "place {}: slot holds a place".format(j), "", "0 or 1", V02)
assert len(rows) == E.OBS_DIM - E.N_B2 - E.N_B3 - E.N_ES - E.N_RAIM - E.N_PREF - E.N_EMG - E.N_DRIFT, (len(rows), E.OBS_DIM - E.N_B2 - E.N_B3 - E.N_ES - E.N_RAIM - E.N_PREF - E.N_EMG - E.N_DRIFT)
# ---- stage B part 2 (TARGETS; N_B2 in sim/duel_env.py): the map's holding places, slot by slot (a token each: the text before the colon)
B2 = "stage B2"
HOLD = ("one of the map's eight holding places (sim/pro_holds/<map>.json: where the pros hold longest and fare best), in the file's order: "
        "slot j is the intention 'place j'; zeros on a map without a list")
for j in range(1, E.HOLD_SLOTS + 1):
    for ax in XYZ:
        add("b2 holds", "hold {}: {}".format(j, ax), HOLD, "units / 1500, between -2 and 2", B2)
    add("b2 holds", "hold {}: way".format(j), "seconds along the walking map from where he stands to it", "seconds / 15, capped at 1 (1: none)", B2)
    add("b2 holds", "hold {}: share of the pros' holds".format(j), "of the map's holds (2 s or more within 150 units, a big weapon in hand, no enemy in view) those in its cell; "
        "where the demos give no holds, put from the pros' sightings there", "per cent / 10, capped at 1", B2)
    add("b2 holds", "hold {}: outcome over expected standing there".format(j), "as for his cell (v02 position): frags less deaths in the 10 s after a sighting that begins with a pro "
        "standing in its cell, less what his stack and the weapons would give anywhere", "/ 0.3, between -1 and 1", B2)
    add("b2 holds", "hold {}: his target".format(j), "his intention is this place (TARGETS)", "0 or 1", B2)
    add("b2 holds", "hold {}: slot holds a place".format(j), "", "0 or 1", B2)
assert len(rows) == E.OBS_DIM - E.N_B3 - E.N_ES - E.N_RAIM - E.N_PREF - E.N_EMG - E.N_DRIFT, (len(rows), E.OBS_DIM - E.N_B3 - E.N_ES - E.N_RAIM - E.N_PREF - E.N_EMG - E.N_DRIFT)
# ---- stage B part 3 (WAYS; N_B3 in sim/duel_env.py): his way to his target, and what the other ways are from where he stands (one token)
B3 = "stage B3"
WAYN = ("the shortest", "the second", "the third")
for j in range(E.N_WAYS):
    add("b3 ways", "his way: {}".format(WAYN[j]), "the set of ways he is on to his target (his thirteenth output, read with his intention; "
        "zeros with WAYS off)", "0 or 1", B3)
for j in range(1, E.N_WAYS):
    add("b3 ways", "{} way: longer".format(WAYN[j]), "how much longer that way to his target is than the shortest from where he stands (0: it is "
        "the shortest way here, or he has no target, or he is in an item run)", "seconds / 5, capped at 1", B3)
for j in range(1, E.N_WAYS):
    add("b3 ways", "{} way: differs".format(WAYN[j]), "from where he stands more than a quarter of that way's seconds lie farther than 128 units "
        "from the shortest way", "0 or 1", B3)
assert len(rows) == E.OBS_DIM - E.N_ES - E.N_RAIM - E.N_PREF - E.N_EMG - E.N_DRIFT, (len(rows), E.OBS_DIM - E.N_ES - E.N_RAIM - E.N_PREF - E.N_EMG - E.N_DRIFT)
# ---- v0.3.1, B-257 (EN_STACK; N_ES in sim/duel_env.py): the enemy's stack as he believes it, from his senses only (one token)
ES_ = "v0.3.1"
ESW = "(EN_STACK; zeros with it off, and in movement rounds) "
add("v031 enemy stack", "believed stack: health", ESW + "the enemy's expected health: 125 at a spawn he knows of, his own hits off, pickups heard or seen on, "
    "over 100 ticking down, a pain sound's band, drifting to an unseen enemy's average while unseen", "/ 200", ES_)
add("v031 enemy stack", "believed stack: armor", ESW + "the enemy's expected armor, by the same rules (his hits take the armor's share off first)", "/ 200", ES_)
add("v031 enemy stack", "believed stack: health and armor", ESW + "the two together", "/ 300", ES_)
add("v031 enemy stack", "believed stack: spread", ESW + "how unsure he is: the standard deviation of the two together (0 at a spawn he knows of; grows "
    "while the enemy is out of view, toward an unseen enemy's)", "/ 150", ES_)
add("v031 enemy stack", "believed stack: since pinned", ESW + "seconds since a spawn he knows of or a pain sound of the three low bands", "seconds / 30, capped at 1", ES_)
add("v031 enemy stack", "believed stack: weak", ESW + "the expected health and armor together are under 80 (ES_WEAK)", "0 or 1", ES_)
assert len(rows) == E.OBS_DIM - E.N_RAIM - E.N_PREF - E.N_EMG - E.N_DRIFT, (len(rows), E.OBS_DIM - E.N_RAIM - E.N_PREF - E.N_EMG - E.N_DRIFT)
# ---- v0.3.6 (RL_AIM, PREFIRE; N_RAIM, N_PREF in sim/duel_env.py): what a rocket is aimed at (docs/v0.4/ROCKETS_v0.3.6.md items 1 to 4)
V36 = "v0.3.6"
RA_ = "(RL_AIM; zeros with it off) with the rocket launcher in his hand: "
RV_ = "(RL_AIM; zeros with it off) with the rocket launcher in his hand and the enemy in view (noticed, his reaction time late): "
add("v036 rocket aim", "backstop: on", RA_ + "these inputs are live", "0 or 1", V36)
add("v036 rocket aim", "backstop: distance", RA_ + "where a rocket fired now along his view would burst (a trace from his eyes, the shots' mask)", "units / 2000, capped at 2 (nothing within 4096)", V36)
add("v036 rocket aim", "backstop: height", RA_ + "that burst's height against his eyes", "units / 300, -1 to 1", V36)
add("v036 rocket aim", "backstop: against the enemy", RV_ + "the burst's distance less the enemy's (below 0: it bursts before him)", "units / 500, -1 to 1", V36)
add("v036 rocket aim", "backstop: splash on him", RV_ + "1 - the distance from that burst to him / the rocket's splash radius (120)", "0 to 1", V36)
add("v036 rocket aim", "floor point: on", RV_ + "the floor aim point is live", "0 or 1", V36)
add("v036 rocket aim", "floor point: yaw coarse", RV_ + "from his crosshair to the floor under where the enemy will be when a rocket fired now gets there (the lead's flight time, his fall in the air)", "degrees / 30, -1 to 1", V36)
add("v036 rocket aim", "floor point: yaw fine", RV_ + "the same", "degrees / 2, -1 to 1", V36)
add("v036 rocket aim", "floor point: pitch coarse", RV_ + "the same, up and down", "degrees / 15, -1 to 1", V36)
add("v036 rocket aim", "floor point: pitch fine", RV_ + "the same", "degrees / 2, -1 to 1", V36)
add("v036 rocket aim", "floor point: floor found", RV_ + "a floor within 1024 units under that place", "0 or 1", V36)
add("v036 rocket aim", "floor point: his height over it", RV_ + "the enemy's feet above that floor by then (jumping, knocked up)", "units / 200, 0 to 2", V36)
add("v036 rocket aim", "floor point: flight", RV_ + "the rocket's flight time to it", "seconds / 1.5, 0 to 2", V36)
add("v036 rocket aim", "floor point: clear", RV_ + "a clear line from his eyes to it", "0 or 1", V36)
add("v036 rocket aim", "wall by him: found", RV_ + "a wall within 192 units of the predicted place (8 level traces at the height of his middle)", "0 or 1", V36)
add("v036 rocket aim", "wall by him: direction sin", RV_ + "the way from that place to the nearest wall, in his own frame", "sin", V36)
add("v036 rocket aim", "wall by him: direction cos", RV_ + "the same", "cos", V36)
add("v036 rocket aim", "wall by him: distance", RV_ + "from that place to the nearest wall (1: none)", "units / 192", V36)
add("v036 rocket aim", "wall by him: yaw", RV_ + "from his crosshair to the point the trace hit", "degrees / 30, -1 to 1", V36)
add("v036 rocket aim", "wall by him: pitch", RV_ + "the same, up and down", "degrees / 15, -1 to 1", V36)
assert len(rows) == E.OBS_DIM - E.N_PREF - E.N_EMG - E.N_DRIFT, (len(rows), E.OBS_DIM - E.N_PREF - E.N_EMG - E.N_DRIFT)
PF_ = ("(PREFIRE; zeros with it off, with the enemy in view, with nothing believed of him, without rockets, grenades or plasma) "
       "of the pros' blind-shot places of one weapon (sim/pro_places/<map>_rl/_gl/_pg.json: the weapon in his hand, else the first "
       "of rockets, grenades, plasma he has) the nearest to the enemy's believed way to him (least off the way first; none within "
       "160 units of him): ")
for j in range(E.PF_SLOTS):
    nm_ = "pre-fire place {}".format(j + 1)
    add("v036 prefire", nm_ + ": yaw", PF_ + "from his crosshair to it", "degrees / 30, -1 to 1", V36)
    add("v036 prefire", nm_ + ": pitch", PF_ + "the same, up and down", "degrees / 15, -1 to 1", V36)
    add("v036 prefire", nm_ + ": distance", PF_ + "from his eyes", "units / 2000, to 1.5", V36)
    add("v036 prefire", nm_ + ": enemy could be there", PF_ + "the seconds of way from the believed place to it less the time since that belief (below 0: he could have passed it)", "seconds / 5, -1 to 1", V36)
    add("v036 prefire", nm_ + ": flight", PF_ + "the list's weapon's flight time there (a rocket 1000 u/s, a plasma cell 2000 u/s, a grenade along its low arc; 0 where none reaches)", "seconds / 1.5, 0 to 2", V36)
    add("v036 prefire", nm_ + ": clear", PF_ + "a clear line from his eyes to it", "0 or 1", V36)
    add("v036 prefire", nm_ + ": off the way", PF_ + "how many seconds longer the way from the believed place to him is through it", "seconds / 5, 0 to 1", V36)
    add("v036 prefire", nm_ + ": pros' share", PF_ + "the share of that weapon's pros' blind shots that land there", "per cent / 15", V36)
    add("v036 prefire", nm_ + ": grenade pitch", PF_ + "the grenade list only: from his crosshair to the low arc that lands a grenade there (0: none reaches)", "degrees / 15, -1 to 1", V36)
    add("v036 prefire", nm_ + ": there", PF_ + "the slot holds a place", "0 or 1", V36)
    for k_, w_ in zip(E.PF_KINDS, ("rockets", "grenades", "plasma")):
        add("v036 prefire", nm_ + ": list {}".format(k_), PF_ + "the list is the {} places".format(w_), "0 or 1", V36)
assert len(rows) == E.OBS_DIM - E.N_EMG - E.N_DRIFT, (len(rows), E.OBS_DIM - E.N_EMG - E.N_DRIFT)
EM_ = ("(EMERGE_IN; zeros with it off, with the enemy in view, with no belief of him in the last 5 s) where the enemy he believes "
       "in would come into his view: the walking map's way from the believed place to him, walked back from him to the last point "
       "his eyes see (worked out every 4 frames, held between): ")
add("v036 emergence", "emergence: live", EM_ + "these inputs are live", "0 or 1", V36)
add("v036 emergence", "emergence: yaw sin", EM_ + "the yaw from his facing to the point", "sin", V36)
add("v036 emergence", "emergence: yaw cos", EM_ + "the same", "cos", V36)
add("v036 emergence", "emergence: yaw", EM_ + "the same", "degrees / 30, -1 to 1", V36)
add("v036 emergence", "emergence: pitch", EM_ + "from his view up and down to the point", "degrees / 15, -1 to 1", V36)
add("v036 emergence", "emergence: distance", EM_ + "from his eyes", "units / 1500, to 2", V36)
add("v036 emergence", "emergence: at the belief", EM_ + "the point is the believed place itself (he sees the whole way)", "0 or 1", V36)
add("v036 emergence", "emergence: a way", EM_ + "a way from the believed place to him exists (0: the point inputs are zeros)", "0 or 1", V36)
assert len(rows) == E.OBS_DIM - E.N_DRIFT, (len(rows), E.OBS_DIM - E.N_DRIFT)
DR_ = ("(DRIFT_IN; zeros with it off, with the enemy not in view, while dead, on a sighting's first frame) how fast the enemy "
       "slides across his screen: the frame-to-frame change of the perceived crosshair-to-enemy angle (the enemy inputs' own: "
       "his delays and sight error; his own view turn included), with the motion sense's errors (DRIFT_WEBER, DRIFT_SIGMA), "
       "a slower slide than DRIFT_MIN read as 0, read DRIFT_DELAY late: ")
add("v038 drift", "drift: yaw rate", DR_ + "left and right (+: the enemy moves left of the crosshair)", "degrees/s / 180, -1 to 1", "v0.3.8")
add("v038 drift", "drift: pitch rate", DR_ + "up and down (+: the enemy moves below the crosshair)", "degrees/s / 90, -1 to 1", "v0.3.8")
add("v038 drift", "drift: yaw rate smoothed", DR_ + "the same, smoothed over DRIFT_SMOOTH (0.1 s)", "degrees/s / 180, -1 to 1", "v0.3.8")
add("v038 drift", "drift: pitch rate smoothed", DR_ + "the same, smoothed", "degrees/s / 90, -1 to 1", "v0.3.8")
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
    for w_ in ("rockets", "rail", "lightning"):
        add("more enemies", "{} enemy holds {}".format(j, w_), "only while in view", "0 or 1", "v9")
add("more enemies", "enemies in view", "", "count / 5", "ffa (not trained yet)")
add("more enemies", "players beyond two", "", "(players - 2) / 4", "ffa (not trained yet)")
assert len(rows) == F.OBS_DIM, (len(rows), F.OBS_DIM)
tail = rows[N_BEFORE:E.OBS_DIM]                           # the group block goes before the pad and hearing inputs
rows[:] = rows[:N_BEFORE] + rows[E.OBS_DIM:] + tail
for i_, r_ in enumerate(rows):
    r_[0] = i_

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
ACT = ("forward / back", "strafe", "jump / crouch", "turn speed", "pitch speed", "fire", "weapon key", "walk", "zoom", "lift the mouse",
       "intention", "his legs", "his way")
print("outputs: " + ", ".join("{} ({} choices)".format(n, d) for n, d in zip(ACT, E.ACTION_DIMS)))
