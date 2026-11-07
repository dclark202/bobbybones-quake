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

**The replace form, "pros" (2026-11-07 evening, after the play test of the push: "didnt do fucking anything").** The push
moved a key he almost never presses, and at close range (50/50) it added nothing: he fought with the lightning gun as he
trained. In the replace form the table *chooses* his weapon: among rockets, the rail and the lightning gun that he owns with
ammunition, one is drawn from the table's row for his situation, and the weapon key's action is set to it (a press of it
until it is in his hand, then keep) in place of the network's; the network's own weapon key is not read at all while he
owns one of the three. The choice is held: it is drawn again only when his situation's row changes (and the weapon held
has been held HOLD_FRAMES frames: no flapping at a distance band's edge), at once when the row gives the weapon in hand
nothing (the lightning gun with the enemy at long range), or when the weapon is no longer owned with ammunition (a new
life, the ammunition out). Fire, aim and movement stay his. Where the row allows none of the three he owns (the machine gun
of a spawn; the lightning gun alone with the enemy at long range) the network's key stands. The same function runs in the checks (WeaponPush form "replace", tools/duel_eval.py --wpush-form
replace) and on the servers (!weapons pros): choose().

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
LEVELS = {"off": 0.0, "light": 2.0, "strong": 4.0}         # p of each push setting (measured in the checks: docs/runs/1.7/1.7c/DIAL.md)
REPLACE = "pros"                                           # the replace form's setting: the table chooses (choose() below; LEVELS has no p for it)
SETTINGS = ("off", "light", "strong", REPLACE)             # !weapons' settings, in the order they are offered
HOLD_FRAMES = 60                                           # 1.5 s at 40 frames a second: the least a chosen weapon is held before a change of
                                                           # situation draws again (a band's edge crossed and recrossed does not flap him)
KEY_IDX = (1, 2, 3)                                        # the weapon key's actions for rockets, rail, lightning gun: 0 keep, 1 + WEAPONS index

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


def new_state(n):
    """the replace form's memory of n players: the row the choice was drawn for (-1 none), the weapon chosen (0 rockets, 1 rail,
    2 lightning gun; -1 none), frames since the choice"""
    return {"row": np.full(n, -1, np.int64), "pick": np.full(n, -1, np.int64), "age": np.zeros(n, np.int64)}


def choose(obs, state, rng):
    """the replace form: [players] the weapon key's action this frame (0 keep, 1 + the weapon's index: KEY_IDX), -1 where the
    network's own key stands (none of rockets, rail, lightning gun owned with ammunition). state: new_state(n), kept by the
    caller from frame to frame (made or resized here when it does not fit); rng: the dial's own stream (one uniform number a player
    on a frame with a new choice; its own, so that the network's other outputs are drawn exactly as with the dial off)"""
    obs = np.asarray(obs)
    n_ = len(obs)
    if state.get("pick") is None or len(state["pick"]) != n_:
        state.update(new_state(n_))
    row_ = situation(obs)
    own_ = (obs[:, list(OWN)] > 0.5) & (obs[:, list(AMMO)] > 0.0)      # [n, 3] the three he may choose from
    hd_ = obs[:, list(HOLD)] > 0.5
    held_ = np.where(hd_.any(1), hd_.argmax(1), -1)                     # the one of the three in hand, else -1
    t_ = np.where(TABLE[row_] >= FLOOR, TABLE[row_], 0.0) * own_        # the row's shares over what he owns (true zeros stay zero)
    any_ = t_.sum(1) > 0                                                # the row allows one he owns; else the network's own key stands
    pick_, prow_, age_ = state["pick"], state["row"], state["age"]
    ar_ = np.arange(n_)
    pick_ok_ = (pick_ >= 0) & own_[ar_, np.maximum(pick_, 0)]           # the choice still one he owns with ammunition
    pick_t_ = np.where(pick_ok_, t_[ar_, np.maximum(pick_, 0)], 0.0)    # its share in this frame's row
    redo_ = any_ & (~pick_ok_ | (pick_t_ <= 0) | ((row_ != prow_) & (age_ >= HOLD_FRAMES)))
    if redo_.any():
        u_ = rng.random(n_)
        c_ = t_.cumsum(1)
        new_ = np.minimum((c_ < (u_ * np.maximum(c_[:, -1], 1e-12))[:, None]).sum(1), 2)
        pick_[redo_] = new_[redo_]
        prow_[redo_] = row_[redo_]
        age_[redo_] = 0
    pick_[~any_] = -1
    prow_[~any_] = -1
    age_ += 1
    act_ = np.where(pick_ == held_, 0, np.asarray(KEY_IDX)[np.maximum(pick_, 0)])
    out_ = np.where(any_, act_, -1).astype(np.int64)
    if _LOG is not None:                                                # (WDIAL_LOG=<file>: a diagnostic, one line a player a frame)
        d_ = 1000.0 * np.sqrt((obs[:, list(POS)].astype(np.float64) ** 2).sum(1))
        for i_ in range(n_):
            _LOG.write("{} {} {} {} {} {:.0f} {}\n".format(i_, row_[i_], held_[i_], pick_[i_], out_[i_], d_[i_], int(obs[i_, INVIEW] > 0.5)))
    return out_


import os as _os
_LOG = open(_os.environ["WDIAL_LOG"], "a") if _os.environ.get("WDIAL_LOG") else None


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
    # the replace form on the same rows: what it chooses over many draws (the choice held from one frame to the next, so one
    # draw a row here: a fresh state and a fresh random number a trial)
    print("replace form (\"{}\"): the share of the first choice over 2000 draws, rockets / rail / lightning (-1: his own key)".format(REPLACE))
    for i_ in range(len(x)):
        cnt = np.zeros(4, int)
        for s_ in range(2000):
            a_ = int(choose(x[i_:i_ + 1], new_state(1), np.random.default_rng(s_))[0])
            cnt[int(np.argmax(x[i_, list(HOLD)])) if a_ == 0 else (a_ - 1 if a_ > 0 else 3)] += 1
        print("  {:16s} holding {:9s} rail owned {}: {:.0%} / {:.0%} / {:.0%}".format(
            ROWS[situation(x[i_:i_ + 1])[0]], "rockets" if x[i_, HOLD[0]] else "lightning", int(x[i_, OWN[1]]), *(cnt[:3] / cnt.sum())))
    # the hold: the row changes at a band's edge and back; the choice stays until HOLD_FRAMES, and at once when the row gives it nothing
    st_, rng_ = new_state(1), np.random.default_rng(0)
    y = x[1:2].copy()                                      # in view, medium, lightning in hand: rockets 70 / lightning 30
    a0 = choose(y, st_, rng_)[0]
    y2 = y.copy()
    y2[0, POS[0]] = 0.25                                   # close now: 50 / 50; held, not drawn again before HOLD_FRAMES
    same = all(int(choose(y2, st_, rng_)[0]) == int(a0) for _ in range(HOLD_FRAMES - 2))
    y3 = y.copy()
    y3[0, POS[0]] = 0.9                                    # long: the lightning gun gets nothing there -> at once rockets or the rail
    a3 = int(choose(y3, new_state(1), np.random.default_rng(1))[0])
    print("hold: a band's edge crossed keeps the choice for {} frames: {}; the lightning gun at long range changed at once: {}".format(
        HOLD_FRAMES, "yes" if same else "NO", "yes" if a3 in (1, 2) else "NO"))
    return 1 if bad or not same or a3 not in (1, 2) else 0


if __name__ == "__main__":
    raise SystemExit(main())
