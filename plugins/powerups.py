"""No powerups on a BobbyBones server, in any mode, on any map (owner, 2026-10-09: "FFA maps on the public server, testing,
etc. SHOULD NEVER HAVE QUAD ... Make sure it (and protection) are always off, and do not train bobby to do anything with it").
The simulator has never had any. Not a plugin: the helpers of plugins/duelbot.py, ffabot.py and botmode.py.

Two layers:
1. The game's own switch, g_spawnItemPowerup, is set before every map load the plugins ask for (load_map), and by
   entrypoint.sh for the first map: 0, so that no powerup is ever spawned (measured 2026-10-09 with plugins/maplab.py: on
   Blood Run the quad is gone, on Battleforged the quad and the invisibility).
2. The plugins remove every powerup they see all the same (strip, at a map's setup and every few seconds): a map the game
   loaded by itself (the map vote at the end of a match) has the switch as the last load left it.

The items of a duel, in every mode (owner, 2026-10-09: "use the 'duel weapon locations' for all of the maps ... Even for
the public FFA matches and training FFA matches ... Those should be the 'only ones that exist' in our world"). The
simulator has always used a map's duel items for every group size. In the game a free-for-all has other items on six of
the eight maps listed (Hektik: 18 of its 37; Battleforged: no grenade launcher; Furious Heights: a rocket launcher and
an ammo box elsewhere; Blood Run, Lost World: the quad; Campgrounds: the quad where the mega is). duel_layout() sets
that right: plugins/duel_items.json holds the real game's duel items per map (tools/duel_items.py, from the listing of
plugins/maplab.py); what a duel lacks is removed, what it has is put there with minqlx.spawn_map_item (an item that
comes back after it is taken, as a map's own). So Campgrounds gets its mega in free-for-all too.

On a server image without spawn_map_item (before 2026-10-09) the old way stays for Campgrounds in free-for-all: the
switch is left on for that load and the quad is turned into the mega; everywhere else the quad is simply removed.
"""
import json
import math
import os

import minqlx

POWERUPS = ("item_quad", "item_enviro", "item_haste", "item_invis", "item_regen", "item_flight", "holdable_invulnerability")
QUAD_IS_MEGA = (("campgrounds", "ffa"),)


_DUEL = None


def duel_items(mapname):
    """the items of a duel on this map: [classname, x, y, z] as they rest in the game, or None for a map not listed"""
    global _DUEL
    if _DUEL is None:
        try:
            _DUEL = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "duel_items.json")))
        except Exception:                                    # noqa: BLE001
            _DUEL = {}
    return _DUEL.get(str(mapname).lower())


def can_place(mapname):
    return hasattr(minqlx, "spawn_map_item") and bool(duel_items(mapname))


def wanted(mapname, factory):
    """must the game spawn the quad on this map in this mode, so that it can be turned into the mega? Only where the
    mega cannot be put there directly (an older server image)"""
    return (str(mapname).lower(), str(factory).lower()) in QUAD_IS_MEGA and not can_place(mapname)


def duel_layout(mapname):
    """give the map the items of a duel: remove what a duel does not have, put what it has. Returns (removed, added), or
    None where it cannot be done (a map without a list, an older server image). Weapons dead players left are not items
    of the map and are left alone."""
    want = duel_items(mapname)
    if not want or not hasattr(minqlx, "spawn_map_item"):
        return None
    now_ms, items = minqlx.item_states()
    have = []
    for num, cls, x, y, z, up, back_ms in items:
        if cls in POWERUPS:
            continue                                         # (strip() deals with those)
        if up and cls.startswith("weapon_") and 0 < back_ms - now_ms <= 30500:
            continue                                         # a weapon a dead player left: gone by itself in 30 s
        have.append((num, cls, x, y, z))
    used, missing = set(), []
    for cls, wx, wy, wz in want:
        best, bd = None, 1e9
        for k, (num, c2, x, y, z) in enumerate(have):
            if c2 == cls and k not in used:
                d = math.hypot(x - wx, y - wy)
                if d < bd and abs(z - wz) < 96:
                    best, bd = k, d
        if best is not None and bd < 40:
            used.add(best)
        else:
            missing.append((cls, wx, wy, wz))
    extra = [h for k, h in enumerate(have) if k not in used]
    for num, cls, x, y, z in extra:
        minqlx.replace_items(int(num), 0)
    for cls, x, y, z in missing:
        minqlx.spawn_map_item(cls, float(x), float(y), float(z) + 2.0)
    return len(extra), len(missing)


def load_map(mapname, factory):
    """every map change of the plugins goes through here"""
    minqlx.console_command('set g_spawnItemPowerup "{}"'.format(1 if wanted(mapname, factory) else 0))
    minqlx.console_command("map {} {}".format(mapname, factory))


def reload_needed(mapname, factory):
    """the map is up without the quad it needs for its mega (the game loaded it by itself with the switch off)"""
    return wanted(mapname, factory) and (minqlx.get_cvar("g_spawnItemPowerup") or "1").strip().strip('"') == "0"


def strip():
    """remove the powerups lying on the map; where the map has no mega the quad becomes it. Returns what was done."""
    done = []
    cls = [c for _, c, *_ in minqlx.item_states()[1]]
    if "item_quad" in cls:
        mega = "item_health_mega" in cls
        minqlx.replace_items("item_quad", 0 if mega else "item_health_mega")
        done.append("the quad removed" if mega else "the quad turned into the mega")
    for c in POWERUPS[1:]:
        if c in cls:
            minqlx.replace_items(c, 0)
            done.append(c.split("_", 1)[1] + " removed")
    return done
