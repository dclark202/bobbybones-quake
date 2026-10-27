"""AIM2 item 5: the step responses of his mouse chain (the view inertia MOUSE_SMOOTH / _FINE, the flick cap, the hand's
bandwidth HAND_BAND), with and without the inertia (AIM2_SMOOTH_K), no hand noise. Pure arithmetic of duel_env.step()'s
lines (no simulator is built).

    python tools/aim2_hand_chain.py

(1) a held rate command: the frames until the view turns at 90% of it.
(2) a flick of X degrees, the fastest he can make with his discrete turn commands (TURN): every plan "a command c for k
    frames, then a command c2 for k2 frames, then nothing" is tried; reported: the plan that first comes within 10% of X
    and stays within max(1 deg, 5%) of X (settled) from then on, its time to 90% of X, its time to settle and its
    overshoot. With the inertia a held command has to be released early (the view coasts on), so the fastest plans
    brake with a command the other way.
"""
import itertools
import math

import numpy as np

DT = 0.025
_T = [0.03, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60]
TURN = np.array(_T)
MS, MS_FINE, CAP, FC, BETA = 0.75, 0.2, 30.0, 4.0, 0.5


def run(cmds, k_sm=1.0, band=True, frames=40):
    mv = hb = 0.0
    view = 0.0
    out = []
    for f in range(frames):
        c = cmds[f] if f < len(cmds) else 0.0
        sm = (MS_FINE if abs(c) <= 1.0 else MS) * k_sm
        mv = sm * mv + (1 - sm) * c
        mv = max(-CAP, min(CAP, mv))
        if band:
            k = 1 - math.exp(-2 * math.pi * (FC + BETA * abs(hb)) * DT)
            hb = hb + k * (mv - hb)
            v = hb
        else:
            v = mv
        view += v
        out.append(view)
    return np.array(out)


def held(rate, **kw):
    v = np.diff(np.concatenate([[0], run([rate] * 40, **kw)]))
    return int(np.argmax(v >= 0.9 * min(rate, CAP))) + 1


def flick(X, **kw):
    best = None
    cs = list(TURN) + [-x for x in TURN]
    for c in TURN:
        for k in range(1, 16):
            if c * k < 0.5 * X or c * k > 3 * X:
                continue
            for c2 in [0.0] + cs:
                for k2 in range(0, 6):
                    if (c2 == 0.0) != (k2 == 0):
                        continue
                    cmds = [c] * k + [c2] * k2
                    v = run(cmds, frames=60, **kw)
                    tol = max(1.0, 0.05 * X)
                    inside = np.abs(v - X) <= tol
                    # settled: inside from frame s on
                    s = None
                    for f in range(len(v)):
                        if inside[f:].all():
                            s = f
                            break
                    if s is None:
                        continue
                    t90 = int(np.argmax(v >= 0.9 * X)) + 1 if (v >= 0.9 * X).any() else 99
                    over = max(0.0, v.max() - X)
                    key = (s, t90)
                    if best is None or key < best[0]:
                        best = (key, dict(t90_ms=t90 * 25, settle_ms=(s + 1) * 25, overshoot=round(over, 2),
                                          plan="{}x{} then {}x{}".format(c, k, c2, k2)))
    return best[1] if best else None


def main():
    print("held rate command: frames to 90% of the rate")
    for r in (2, 8, 15, 30):
        print("  {:>4} deg/frame: chain {} | no inertia {} | inertia only (no band) {}".format(
            r, held(r), held(r, k_sm=0.0), held(r, band=False)))
    print("\nflick of X degrees: the fastest plan (90% of X, settled within max(1, 5%), overshoot deg)")
    for X in (10, 40, 80):
        for name, kw in (("today: inertia + band", {}), ("no inertia (AIM2_SMOOTH_K=0)", dict(k_sm=0.0)),
                         ("inertia, no band", dict(band=False)), ("half inertia (K=0.5)", dict(k_sm=0.5))):
            print("  {:>3} deg  {:<30} {}".format(X, name, flick(X, **kw)))


if __name__ == "__main__":
    main()
