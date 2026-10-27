"""v0.4.2a: the old hand-built belief faded out of the hands (docs/v0.4.0/RUN_v0.4.2a.md).

The rule-made input columns (the believed place of the unseen enemy and everything made from it, the stack filter, the
pre-fire spots and the emergence point) are multiplied by (1 - g) AFTER the input scaling, so a faded column reads its
average (raw "nothing" codes are not zero). Only the hands read the faded inputs: the encoder and the attention part.
The brain (sim/belief.py) keeps reading the unfaded inputs. g = 0 is exactly the network without the fade (nothing is
multiplied). The raw sensed facts stay: time since seen or heard, where heard, damage, life clock, death known, pickups
and weapons seen, the drift.

The columns are chosen by NAME from docs/INPUTS.csv (select()); the checkpoint's "rule_fade" entry carries the names and
their indices in the network's own input list, and the gate g. Plain numpy at the top (the plugins import it)."""
import csv
import re

VERSION = 1

# (group, input) pairs, or (group, a regular expression over the input's name), or (group, None) for the whole group;
# EXCEPT: names kept raw inside a faded group
FADE = (
    ("v02 position", "height above the believed enemy"),
    ("v02 believed", "a place is believed"),
    ("v02 believed", "believed place: forward"),
    ("v02 believed", "believed place: left"),
    ("v02 believed", "believed place: up"),
    ("v02 believed", "way to the believed place"),
    ("v02 believed", "way from the believed place to the mega health"),
    ("v02 believed", "way from the believed place to the red armor"),
    ("v02 places", re.compile(r"place \d+: distance from the believed enemy$")),
    ("v02 places", re.compile(r"place \d+: nearest to the believed enemy$")),
    ("v031 enemy stack", None),
    ("v036 prefire", None),
    ("v036 emergence", None),
)
EXCEPT = (("v031 enemy stack", "believed stack: since pinned"),)


def names_of(inputs_csv):
    return [(r["group"], r["input"]) for r in csv.DictReader(open(inputs_csv, encoding="utf-8"))]


def select(inputs_csv):
    """-> (cols [int], names [[group, input]]) of the faded columns in that input list, in its order"""
    nm = names_of(inputs_csv)
    cols, out = [], []
    for i, (g, n) in enumerate(nm):
        if (g, n) in EXCEPT:
            continue
        for fg, fn in FADE:
            if g != fg:
                continue
            if fn is None or (isinstance(fn, str) and fn == n) or (not isinstance(fn, str) and fn.match(n)):
                cols.append(i)
                out.append([g, n])
                break
    for fg, fn in FADE:                                       # every name asked for must be there (a renamed input is an error)
        if isinstance(fn, str):
            assert (fg, fn) in nm, "rule_fade: no input {} in {}".format((fg, fn), inputs_csv)
    return cols, out


def layout(inputs_csv, readers=False, blind=False):
    """the checkpoint's "rule_fade" entry: the names, their columns, the gate (shut)"""
    cols, nm = select(inputs_csv)
    return dict(version=VERSION, cols=cols, names=nm, n=len(cols), g=0.0, readers=bool(readers), blind=bool(blind))


def cols_for(L, inputs_csv=None, names=None):
    """the entry's columns in another input list (by name): the checks' tools play a network through its own list"""
    if names is None:
        names = names_of(inputs_csv)
    ix = {tuple(x): i for i, x in enumerate(names)}
    return [ix[tuple(x)] for x in L["names"]]


def apply_np(x, cols, g):
    """x [B, inputs] normalised -> the hands' copy with the columns times (1 - g); x itself when g is 0"""
    if not g > 0 or not len(cols):
        return x
    import numpy as np
    y = np.array(x, copy=True)
    y[:, cols] = y[:, cols] * np.float32(1.0 - float(g))
    return y


def describe(L):
    return "rule fade (v0.4.2a): {} columns at gate {:.4f}; the simulator's readers {}, blind-fire exemption {}".format(
        int(L.get("n", len(L["cols"]))), float(L.get("g", 0.0)), "on the brain's answer by the same gate" if L.get("readers") else "on the rule",
        "on the brain" if L.get("blind") else "on the rule")
