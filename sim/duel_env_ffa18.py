"""The simulator that gives the cleaned input list 18 (owner, 2026-11-11; docs/design/INPUTS_CLEANUP.md; sim/input_list.py): the group
module (sim/duel_env_ffa.py) unchanged, its observe() giving only the list's columns, in the list's order. Everything else (the game, the
switches, the pay, the names the trainer reads) is the group module's own: this file has no simulator code.

    --env duel_env_ffa18                      the trainer; a network of this list (tools/inputs18.py convert)
    OBS_DIM, INPUT_LIST, INPUT_NAMES, INPUT_SRC, N_BRAIN, N_HANDS

The checks (tools/duel_eval.py) play in the full simulator and give each network its own columns by name, so a network of this list meets
an older one there with nothing changed for either."""
import numpy as np

import duel_env_ffa as _B
import input_list as _IL

INPUT_LIST = _IL.load(18)
assert INPUT_LIST["full"] <= _B.OBS_DIM, "the list was made for {} inputs, the simulator has {}".format(INPUT_LIST["full"], _B.OBS_DIM)   # (2.1: taken by name;
#                                                             the full list may have grown at its end since)
INPUT_NAMES = [tuple(x) for x in INPUT_LIST["names"]]
INPUT_SRC = np.asarray(INPUT_LIST["src"], np.int64)
N_BRAIN, N_HANDS = int(INPUT_LIST["n_brain"]), int(INPUT_LIST["n_hands"])
OBS_DIM = int(len(INPUT_SRC))
OBS_FULL = int(_B.OBS_DIM)


def col(group, name):
    """the list's column of an input by its name"""
    return INPUT_NAMES.index((group, name))


class DuelEnv(_B.DuelEnv):
    """the list is taken where the inputs leave the simulator: inside a step the simulator's own code (the moments, the scripted
    seats) sees its full list as always"""
    _in_step = False

    def observe(self):
        o = super().observe()
        return o if self._in_step else o[:, INPUT_SRC]

    def observe_full(self):
        return super().observe()

    def step(self, actions):
        self._in_step = True
        try:
            obs, rew, done, info = super().step(actions)
        finally:
            self._in_step = False
        return obs[:, INPUT_SRC], rew, done, info


def __getattr__(name):                                      # everything else is the group module's
    return getattr(_B, name)
