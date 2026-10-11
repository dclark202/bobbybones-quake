"""Read the fourth output of tools/demodump (out.events.json): a demo's events with their kind, the config strings as
they change, the server commands, and the exact server time of every snapshot. The format is described at the top of
tools/demodump/demodump.cpp; the snapshots themselves are in out.bin (sim/demo_reader.py).

    demodump.exe <demo> d.bin d.json d.events.json

    sys.path.insert(0, "tools/demodump"); import events_reader as R
    E = R.load("d.events.json")
    E["events"]                        (n, columns) float64, one row an event; E["c"]["snap"] is a column's number
    E["times"]                         (snapshots,) int64: the server time of every snapshot record of d.bin, exact
    R.rows(E, "Obituary", source=0)    the rows of one kind of event (a name of E["event_ids"] or a number)
    R.obituaries(E)                    (k, 5) int64: snap, server time, victim, killer (-1: the world), means of death
                                       (a number of E["means_of_death"]; the library has no name for 33, which the
                                       later versions of the game use: the demo site counts it as a rail kill)
    R.score_changes(E)                 (k, 3) int64: snap, client, +1 or -1 (the game's rule for a frag and an accident)
    R.config_string(E, "LevelStartTime")   [(at_snapshot, string), ...]: at every gamestate and every time it was set

No player names are read here; the players' config strings are in the file (as they are in d.json), under their
indices (E["config_string_ids"]["FirstPlayer"] + the client number).
"""
import json

import numpy as np

MAX_CLIENTS = 64


def load(path):
    E = json.load(open(path, encoding="ascii"))
    E["c"] = {n: i for i, n in enumerate(E["event_cols"])}
    E["events"] = np.array(E["events"], np.float64).reshape(-1, len(E["event_cols"]))    # (a null, never seen, would be NaN)
    E["times"] = np.array(E["times"], np.int64)
    return E


def rows(E, event, source=None, etype=None):
    """the rows of one kind of event: `event` a name of E["event_ids"] or this protocol's number; `source` 0 an event
    entity, 1 another entity's event field, 2 the followed player's own; `etype` a name of E["entity_types"]"""
    c, ev = E["c"], E["events"]
    m = ev[:, c["event"]] == (E["event_ids"][event] if isinstance(event, str) else event)
    if source is not None:
        m &= ev[:, c["source"]] == source
    if etype is not None:
        m &= ev[:, c["eType"]] == E["entity_types"][etype]
    return ev[m]


def obituaries(E):
    """(k, 5) int64: snap, server time, victim, killer (-1: the world or anything that is no client), means of death"""
    c, r = E["c"], rows(E, "Obituary", source=0)
    out = r[:, [c["snap"], c["serverTime"], c["otherEntityNum"], c["otherEntityNum2"], c["eventParm"]]].astype(np.int64)
    out = out[(out[:, 2] >= 0) & (out[:, 2] < MAX_CLIENTS)]                                # (the victim is always a client)
    out[(out[:, 3] < 0) | (out[:, 3] >= MAX_CLIENTS), 3] = -1
    return out


def score_changes(E):
    """(k, 3) int64: snap, client, change. The game's rule: a frag is a point for the killer; a death by his own hand or
    by the world takes a point off the victim, and so does leaving the game (he dies by his own hand, the means of death
    "TeamSwitch": the demo site does not count that one among his deaths). A forfeit shows as the game setting his score
    to -999, which is no event. Checked 2026-10-11 against the followed player's score on every snapshot of 189 games and
    against the two score config strings at every obituary."""
    out = []
    for snap, _, victim, killer, _ in obituaries(E):
        out.append((snap, killer, 1) if killer >= 0 and killer != victim else (snap, victim, -1))
    return np.array(out, np.int64).reshape(-1, 3)


def config_string(E, key):
    """[(at_snapshot, string), ...] for one config string (a name of E["config_string_ids"] or an index): its value at
    every gamestate ("" where it was empty) and every time the server set it, in the order of the demo"""
    idx = E["config_string_ids"][key] if isinstance(key, str) else int(key)
    out = [(g["at_snapshot"], 0, g["cs"].get(str(idx), "")) for g in E["gamestates"]]
    out += [(r[0], 1, r[5]) for r in E["commands"] if r[3] == "cs" and r[4] == idx]
    out.sort(key=lambda x: (x[0], x[1]))            # (stable: the commands stay in the order received, a gamestate first)
    return [(a, s) for a, _, s in out]
