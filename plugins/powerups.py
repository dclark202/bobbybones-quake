"""No powerups on a BobbyBones server, in any mode, on any map (owner, 2026-10-09: "FFA maps on the public server, testing,
etc. SHOULD NEVER HAVE QUAD ... Make sure it (and protection) are always off, and do not train bobby to do anything with it").
The simulator has never had any. Not a plugin: the helpers of plugins/duelbot.py, ffabot.py and botmode.py.

Two layers:
1. The game's own switch, g_spawnItemPowerup, is set before every map load the plugins ask for (load_map), and by
   entrypoint.sh for the first map: 0, so that no powerup is ever spawned (measured 2026-10-09 with plugins/maplab.py: on
   Blood Run the quad is gone, on Battleforged the quad and the invisibility).
2. The plugins remove every powerup they see all the same (strip, at a map's setup and every few seconds): a map the game
   loaded by itself (the map vote at the end of a match) has the switch as the last load left it.

One exception: Campgrounds in free-for-all. There the map has the quad in the mega's place and no mega (the mega is 1v1
only), and with the switch off it has neither. For that load the switch stays on and the quad is turned into the mega,
as since 2026-10-07; everywhere else the quad is simply removed (every other map has its mega beside it).
"""
import minqlx

POWERUPS = ("item_quad", "item_enviro", "item_haste", "item_invis", "item_regen", "item_flight", "holdable_invulnerability")
QUAD_IS_MEGA = (("campgrounds", "ffa"),)


def wanted(mapname, factory):
    """must the game spawn the quad on this map in this mode, so that it can be turned into the mega?"""
    return (str(mapname).lower(), str(factory).lower()) in QUAD_IS_MEGA


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
