"""The weapon dial for play against people (owner, 2026-11-07: "What I want to see is him use rockets both in close and medium
range, and for zoning. Use LG at close range, and rail at long range. He's not learning it in training, but perhaps there's a
way to nudge toward that for play against people?" ... "Build the dial for play against people and I'll play test it").

A push on his weapon key at play time, no training: a press of weapon j (rockets, rail, lightning gun; owned with ammunition)
gets  p x (log t_j - log t_held)  added to its score, where t is the owner's table below for the situation and t_held the
table's value for the weapon in his hand (with none of the three in hand: the mean over the ones he owns). Shares under
FLOOR count as FLOOR. Keep and the other weapons' presses are untouched, so between two weapons the table rates alike
(rockets and the lightning gun close) he keeps what he has.

The situation is read from his own inputs (what he perceives): the enemy noticed in view, and the distance to where he last
knew the enemy. The same code runs in the checks (sim/test_suite.py WeaponPush, form "dial") and on the servers
(plugins/netpass.py step(), plugins/duelbot.py !weapons).

    python sim/weapon_dial.py            the input columns checked against docs/INPUTS.csv, the push on a few rows printed
"""
import numpy as np

# the owner's table (2026-11-07; the draft he did not correct): the weapon in hand he wants, rockets / rail / lightning gun
NEAR, FAR = 300.0, 700.0                                   # units: close below NEAR, long from FAR (the lightning gun reaches 768)
TABLE = np.array([[0.50, 0.00, 0.50],                      # in view, close: rockets or the lightning gun
                  [0.70, 0.00, 0.30],                      # in view, medium: mostly rockets
                  [0.30, 0.70, 0.00],                      # in view, long: the rail where he has it, else rockets
                  [0.70, 0.15, 0.15]], np.float64)         # out of view (travelling, zoning): mostly rockets
ROWS = ("in view, close", "in view, medium", "in view, long", "out of view")
FLOOR = 0.03
LEVELS = {"off": 0.0, "light": 2.0, "strong": 4.0}         # p of each setting (measured in the checks: docs/runs/1.7/1.7c/DIAL.md)

# his input columns (docs/INPUTS.csv; all from v3, the same in every simulator module since): checked by main() below
HOLD = (71, 72, 73)                                        # holding rocket launcher, railgun, lightning gun
INVIEW = 35                                                # the enemy noticed in view
POS = (37, 38, 39)                                         # the enemy's last known position: forward, left, up (units / 1000)
OWN = (80, 81, 82)                                         # owns rocket launcher, railgun, lightning gun
AMMO = (89, 90, 91)                                        # ammunition of the three (share of the maximum)
NAMES = dict(zip(HOLD, ("holding rocket launcher", "holding railgun", "holding lightning gun")))
NAMES.update({INVIEW: "noticed in view", POS[0]: "last known position: forward", POS[1]: "last known position: left",
              POS[2]: "last known position: up"})
NAMES.update(dict(zip(OWN, ("owns rocket launcher", "owns railgun", "owns lightning gun"))))
NAMES.update(dict(zip(AMMO, ("ammo: rocket launcher", "ammo: railgun", "ammo: lightning gun"))))


def situation(obs):
    """the table's row of each player: 0 to 2 in view by distance, 3 out of view"""
    obs = np.asarray(obs)
    d_ = 1000.0 * np.sqrt((obs[:, list(POS)].astype(np.float64) ** 2).sum(1))
    row_ = np.where(d_ < NEAR, 0, np.where(d_ < FAR, 1, 2))
    return np.where(obs[:, INVIEW] > 0.5, row_, 3)


def push(obs, p):
    """[players, 3]: what is added to the scores of the presses of rockets, the rail and the lightning gun (the weapon key's
    choices 1 + RL, 1 + RG, 1 + LG); zeros at p = 0"""
    obs = np.asarray(obs)
    n_ = len(obs)
    if not p:
        return np.zeros((n_, 3), np.float32)
    own_ = (obs[:, list(OWN)] > 0.5) & (obs[:, list(AMMO)] > 0.0)
    lt_ = np.log(np.maximum(TABLE, FLOOR))[situation(obs)]
    hd_ = obs[:, list(HOLD)] > 0.5
    ref_ = np.where(hd_.any(1), (lt_ * hd_).sum(1), (lt_ * own_).sum(1) / np.maximum(own_.sum(1), 1))
    return (float(p) * (lt_ - ref_[:, None]) * own_).astype(np.float32)


def main():
    import csv
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "INPUTS.csv")
    rows = {int(r["index"]): r["input"] for r in csv.DictReader(open(path, encoding="utf-8"))}
    bad = {c: (n, rows.get(c)) for c, n in NAMES.items() if rows.get(c) != n}
    print("input columns:", "all as docs/INPUTS.csv" if not bad else "WRONG {}".format(bad))
    x = np.zeros((6, max(rows) + 1), np.float32)
    x[:, list(OWN)] = 1.0
    x[:, list(AMMO)] = 0.5
    x[:, HOLD[2]] = 1.0                                    # the lightning gun in hand
    x[0:3, INVIEW] = 1.0
    x[0, POS[0]], x[1, POS[0]], x[2, POS[0]] = 0.2, 0.5, 0.9
    x[4, HOLD[2]], x[4, HOLD[0]] = 0.0, 1.0                # rockets in hand, out of view
    x[5, OWN[1]] = 0.0                                     # no rail, out of view
    for i_, r_ in enumerate(push(x, 1.0)):
        print("  {:16s} holding {:9s} rail owned {}: push at p 1 rockets {:+.2f} rail {:+.2f} lightning {:+.2f}".format(
            ROWS[situation(x[i_:i_ + 1])[0]], "rockets" if x[i_, HOLD[0]] else "lightning", int(x[i_, OWN[1]]), *r_))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
