"""2.1, the finish time's table (docs/runs/2.1/SIM_PARTS.md "Third pass"; the owner, 2026-11-11: "It needs to be based around the hit
rate he believes he will get, or perhaps simpler just an average dps of each weapon"): HIS OWN damage a second of trigger held, by
weapon and by the distance to the enemy, measured from his own recorded games. A fact about his hands, not a target: nothing here
reads a pro's game (CLAUDE.md rule 12). Measurement only: reads records, plays nothing.

    python tools/run/fin_rate.py measure <recdir> [<recdir> ...] [--side -1] [--min-secs 20] [--out <file.json>]
    python tools/run/fin_rate.py show <file.json>

<recdir>: tools/run/cypher_measure.py sim's records made with this build (rec_<map>_<k>.npz with fire, wfire, dealt_w, pos, alive,
side). --side: 0 = the network under test, -1 = every seat (self-play: both are it).

  the trigger   a shot = a frame in which the ammunition of the weapon in his hand fell; its trigger time = the weapon's refire time
                (sim/duel_env.py W_REFIRE), booked in the band of the distance to the enemy at the shot (under 400, 400 to 768, over
                768 units; the enemy's true place: this measures his hands, in play the band comes from his belief)
  the damage    as the simulator books each hit on another player, by the weapon that did it (splash in it), booked in the band of
                the distance when it lands (a rocket's flight is under a second: decided here)
  the rate      damage / trigger seconds, a cell. A cell with under --min-secs seconds of trigger keeps the PLACEHOLDER's number and
                is listed as not measured (the gauntlet always: it has no ammunition to count shots by).

Prints the table and the line for a run's command (FIN_RATE=...; the same string as a live.json value), and writes them as JSON.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "sim"))
NAMES = ("rockets", "rail", "lightning", "machine gun", "shotgun", "grenades", "plasma", "hmg", "gauntlet")
BANDS = ("under 400", "400 to 768", "over 768")


def table(secs, dmg, default, min_secs):
    """secs, dmg [weapons, 3] -> (rate [weapons, 3], measured [weapons, 3]): damage a second of trigger where there are min_secs
    seconds or more; elsewhere the default's cell"""
    secs, dmg = np.asarray(secs, np.float64), np.asarray(dmg, np.float64)
    ok = secs >= float(min_secs)
    return np.where(ok, dmg / np.maximum(secs, 1e-9), np.asarray(default, np.float64)), ok


def add(d, side, refire, bands, secs, dmg):
    """one record's seats of `side` into secs, dmg [weapons, 3] (in place) -> the seats counted"""
    for k in ("fire", "wfire", "dealt_w"):
        if k not in d.files:
            raise SystemExit("a record without `{}`: make the records with this build's tools/run/cypher_measure.py".format(k))
    pos, alive = d["pos"].astype(np.float32), d["alive"].astype(bool)
    n = alive.shape[1]
    sd = d["side"] if "side" in d.files else np.zeros(n, np.int8)
    k = 0
    for s in range(n):
        if side >= 0 and int(sd[s]) != side:
            continue
        o = s ^ 1
        band = np.digitize(np.linalg.norm(pos[:, s] - pos[:, o], axis=1), bands)
        f = d["fire"][:, s].astype(bool)
        w = d["wfire"][:, s].astype(int).clip(0, len(refire) - 1)
        np.add.at(secs, (w[f], band[f]), refire[w[f]])
        dw = d["dealt_w"][:, s].astype(np.float64)            # [frames, weapons]
        for b in range(3):
            dmg[:, b] += dw[band == b].sum(0)
        k += 1
    return k


def measure(a):
    import duel_env_ffa as E
    refire = np.asarray(E.W_REFIRE, np.float64)
    secs, dmg = np.zeros((E.NW, 3)), np.zeros((E.NW, 3))
    games = seats = 0
    for rd in a.rec:
        for f in sorted(glob.glob(os.path.join(rd, "rec_*.npz"))):
            seats += add(np.load(f, allow_pickle=True), a.side, refire, E.FIN_BANDS, secs, dmg)
            games += 1
    assert games, "no records in {}".format(a.rec)
    rate, ok = table(secs, dmg, E.FIN_RATE_DEFAULT, a.min_secs)
    out = dict(rate=np.round(rate, 2).tolist(), measured=ok.tolist(), secs=np.round(secs, 1).tolist(), dmg=np.round(dmg, 0).tolist(),
               weapons=list(E.WEAPONS), bands=list(E.FIN_BANDS), min_secs=a.min_secs, games=games, seats=seats, side=a.side, records=list(a.rec),
               env="FIN_RATE=" + E.fin_rate_str(rate))
    show(out)
    if a.out:
        json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1)
        print("wrote {}".format(a.out))
    return out


def show(o):
    print("his own damage a second of trigger held ({} games, {} seats; a cell under {} s of trigger keeps the placeholder, marked *)".format(
        o["games"], o["seats"], o["min_secs"]))
    print("  {:<12} {}".format("", "  ".join("{:>22}".format(b) for b in BANDS)))
    for w, nm in enumerate(NAMES):
        print("  {:<12} {}".format(nm, "  ".join("{:>7.1f}{} ({:>7.0f} s fired)".format(o["rate"][w][b], " " if o["measured"][w][b] else "*", o["secs"][w][b])
                                                 for b in range(3))))
    print("for the run's command (or a live.json value, without the name):\n  " + o["env"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("measure")
    p.add_argument("rec", nargs="+")
    p.add_argument("--side", type=int, default=-1)
    p.add_argument("--min-secs", type=float, default=20.0)
    p.add_argument("--out", default="")
    p = sp.add_parser("show")
    p.add_argument("file")
    a_ = ap.parse_args()
    if a_.cmd == "measure":
        measure(a_)
    else:
        show(json.load(open(a_.file, encoding="utf-8")))
