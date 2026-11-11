"""(2.0a, 2026-11-08; docs/runs/2.0/2.0a/CARD.md) What the judge pays, in frags of win chance: the price table of the card, the chip table and the
losing fight, from any judge file (sim/win_judge.py's .npz) at any weight (WIN_ADD) and damage floor (DMG_REWARD, zero-sum). The card's sizing
and the refit's check: the two rules are printed with their verdict (the first 50 off a 200/200 not paid less than the flat 0.275 today; the red
armor at 100/0, table included, under a kill of a fresh spawn).
    python tools/run/judge_prices.py data/sim_runs/judge/judge_v060_wpn.npz [--weight 0.6] [--floor 0.001] [--flat 0.0055] [--left 600]"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "sim"))
import win_judge as wj                                       # noqa: E402

LG = (0.0, 1.0, 0.0)


def hit(hp, ar, dmg):
    """the game's armor rule: armor takes two thirds while it lasts"""
    a = min(ar, dmg * 2.0 / 3.0)
    return max(hp - (dmg - a), 0.0), ar - a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("judge")
    ap.add_argument("--weight", type=float, default=0.6)
    ap.add_argument("--floor", type=float, default=0.001, help="the damage pay a point, zero-sum (DMG_REWARD with DMG_TAKEN_W 1)")
    ap.add_argument("--flat", type=float, default=0.0055, help="today's flat damage pay a point, for the comparison column")
    ap.add_argument("--left", type=float, default=600.0)
    a = ap.parse_args()
    P, meta = wj.load(a.judge)
    L = a.left

    def p(d, left, hpa, ara, hpb, arb, wa=LG, wb=LG, deada=False, deadb=False):
        Sa = wj.parts([hpa], [ara], [deada]); Sb = wj.parts([hpb], [arb], [deadb])
        return float(wj.chance(P, np.array([d], float), np.array([left], float), Sa, np.array([wa], float), Sb, np.array([wb], float))[0])

    p1 = p(1, 600, 125, 0, 125, 0, (0, 0, 0), (0, 0, 0))
    scale = 1.0 / (p1 - 0.5)
    pay = lambda b, c: scale * (c - b)                       # noqa: E731
    w, fl = a.weight, a.floor
    print("judge {} (made {}, fit on {}); WIN_SCALE {:.2f} (a lead of 1 at 10:00 = {:.3f}); weight {}, floor {} a point".format(
        os.path.basename(a.judge), meta.get("made"), meta.get("run"), scale, p1, w, fl))
    R = [("100 damage on an enemy at 100/50 (he is at 50/0 after)", pay(p(0, L, 125, 0, 100, 50), p(0, L, 125, 0, 50, 0)), 100),
         ("100 damage on an enemy at 200/200", pay(p(0, L, 125, 0, 200, 200), p(0, L, 125, 0, 167, 133)), 100),
         ("50 chip on an enemy at 125/0", pay(p(0, L, 125, 0, 125, 0), p(0, L, 125, 0, 75, 0)), 50),
         ("50 chip on an enemy at 200/0 (the decaying part)", pay(p(0, L, 125, 0, 200, 0), p(0, L, 125, 0, 150, 0)), 50),
         ("his death at 125/0 (beside the flat -1)", pay(p(0, L, 125, 0, 125, 0), p(-1, L, 125, 0, 125, 0, deada=True)), 0),
         ("his death at 200/200 (beside the flat -1)", pay(p(0, L, 200, 200, 125, 0), p(-1, L, 125, 0, 125, 0, deada=True)), 0),
         ("his death at 60/0 to an enemy at 150/100", pay(p(0, L, 60, 0, 150, 100), p(-1, L, 125, 0, 150, 100, deada=True)), 0),
         ("he takes the red at 100/0 (beside the table's 0.40)", pay(p(0, L, 100, 0, 125, 0), p(0, L, 100, 100, 125, 0)), 0),
         ("he takes the mega at 100/0 (beside 0.28)", pay(p(0, L, 100, 0, 125, 0), p(0, L, 200, 0, 125, 0)), 0),
         ("he takes a yellow at 100/0 (beside 0.20)", pay(p(0, L, 100, 0, 125, 0), p(0, L, 100, 50, 125, 0)), 0),
         ("he takes a yellow at 100/100 (beside 0.15)", pay(p(0, L, 100, 100, 125, 0), p(0, L, 100, 150, 125, 0)), 0),
         ("he owns the rail (against not), both at 125/0", pay(p(0, L, 125, 0, 125, 0), p(0, L, 125, 0, 125, 0, (0, 1, 1), LG)), 0),
         ("he owns rockets (against not)", pay(p(0, L, 125, 0, 125, 0), p(0, L, 125, 0, 125, 0, (1, 1, 0), LG)), 0),
         ("a frag at 0:0 with 2:00 left (beside the flat 1)", pay(p(0, 120, 125, 0, 125, 0), p(1, 120, 125, 0, 125, 0, deadb=True)), 0),
         ("a frag when 3 behind with 2:00 left", pay(p(-3, 120, 125, 0, 125, 0), p(-2, 120, 125, 0, 125, 0, deadb=True)), 0),
         ("a frag when 3 ahead with 2:00 left", pay(p(3, 120, 125, 0, 125, 0), p(4, 120, 125, 0, 125, 0, deadb=True)), 0),
         ("the leader's trickle, one ahead, 5:00 to 4:00", pay(p(1, 300, 125, 0, 125, 0), p(1, 240, 125, 0, 125, 0)), 0)]
    print("\n%-56s %9s %9s %12s %9s" % ("scenario", "weight 1", "x0.33", "x%.2f+floor" % w, "flat"))
    for n, v, d in R:
        print("%-56s %9.2f %9.2f %12.2f %9s" % (n, v, 0.33 * v, w * v + fl * d, ("%.2f" % (a.flat * d)) if d else ""))
    C = [("50 chip, enemy 200/200 -> 183/167", pay(p(0, L, 125, 0, 200, 200), p(0, L, 125, 0, 183, 167)), 50),
         ("100 chip, enemy 200/200 -> 167/133", pay(p(0, L, 125, 0, 200, 200), p(0, L, 125, 0, 167, 133)), 100),
         ("the next 50, enemy 150/100 -> 133/67", pay(p(0, L, 125, 0, 150, 100), p(0, L, 125, 0, 133, 67)), 50),
         ("the next 50, enemy 133/67 -> 117/33", pay(p(0, L, 125, 0, 133, 67), p(0, L, 125, 0, 117, 33)), 50),
         ("50 chip, enemy 200/0 -> 150/0 (a mega holder)", pay(p(0, L, 125, 0, 200, 0), p(0, L, 125, 0, 150, 0)), 50),
         ("50 chip, enemy 100/100 -> 83/67", pay(p(0, L, 125, 0, 100, 100), p(0, L, 125, 0, 83, 67)), 50),
         ("50 chip, enemy 125/0 -> 75/0 (a fresh spawn)", pay(p(0, L, 125, 0, 125, 0), p(0, L, 125, 0, 75, 0)), 50),
         ("50 chip by a 60/0 Bobby on a 200/200 enemy", pay(p(0, L, 60, 0, 200, 200), p(0, L, 60, 0, 183, 167)), 50)]
    Ws = (0.33, 0.5, 0.6, 0.7, 1.0) if w in (0.33, 0.5, 0.6, 0.7, 1.0) else (0.33, 0.5, w, 1.0)
    print("\n%-48s %7s | %s" % ("chip (the floor included)", "today", " ".join("w %.2f" % x for x in Ws)))
    for n, v, d in C:
        print("%-48s %7.2f | %s" % (n, a.flat * d, " ".join("%6.2f" % (x * v + fl * d) for x in Ws)))
    red = pay(p(0, L, 100, 0, 125, 0), p(0, L, 100, 100, 125, 0))
    kill = pay(p(0, L, 125, 0, 125, 0), p(1, L, 125, 0, 125, 0, deadb=True))
    print("%-48s %7s | %s" % ("the red at 100/0, the table's 0.40 included", "0.40", " ".join("%6.2f" % (0.40 + x * red) for x in Ws)))
    print("%-48s %7s | %s" % ("a kill of a fresh spawn, the flat 1 included", "1.00", " ".join("%6.2f" % (1.0 + x * kill) for x in Ws)))
    r1 = w * C[0][1] + fl * 50
    r2 = 0.40 + w * red < 1.0 + w * kill
    print("\nrule 1: the first 50 off a 200/200 pays {:.3f} at weight {} (today {:.3f}): {}".format(r1, w, a.flat * 50, "OK" if r1 >= a.flat * 50 - 0.005 else "BROKEN"))
    print("rule 2: the red at 100/0 pays {:.2f} against a spawn kill's {:.2f}: {}".format(0.40 + w * red, 1.0 + w * kill, "OK" if r2 else "BROKEN"))

    # the losing fight: he fights to the death at equal aim (he deals about his own effective stack before dying) against chipping 50 and leaving
    def eff(h, ar):
        return h + min(ar, 2 * h)

    def fight(me, en, w_, fl_, dtw, flat):
        dealt = min(eff(*me), eff(*en)); eh, ea = hit(*en, dealt)
        return w_ * pay(p(0, L, *me, *en), p(-1, L, 125, 0, eh, ea, deada=True)) + flat * dealt - flat * dtw * eff(*me) - 1.0

    def leave(me, en, w_, flat):
        eh, ea = hit(*en, 50)
        return w_ * pay(p(0, L, *me, *en), p(0, L, *me, eh, ea)) + flat * 50

    print("\n%-26s | %9s %9s %7s | %9s %9s %7s" % ("the losing fight", "today:fi", "chip+go", "margin", "new:fight", "chip+go", "margin"))
    for me, en in (((100, 0), (200, 200)), ((125, 0), (200, 200)), ((150, 100), (200, 200)), ((200, 200), (200, 200)), ((200, 200), (125, 0)), ((60, 0), (150, 100))):
        ft, ct = fight(me, en, 0.33, 0.0, 0.8, a.flat), leave(me, en, 0.33, a.flat)
        fn, cn = fight(me, en, w, fl, 1.0, fl), leave(me, en, w, fl)
        print("%-26s | %9.2f %9.2f %7.2f | %9.2f %9.2f %7.2f" % ("%d/%d vs %d/%d" % (me + en), ft, ct, ct - ft, fn, cn, cn - fn))
    print("an even trade of 200 for 200, nobody dies: today %+.2f each, new %+.2f each" % (a.flat * 200 - 0.8 * a.flat * 200, fl * 200 - fl * 200))
    return 0


if __name__ == "__main__":
    sys.exit(main())
