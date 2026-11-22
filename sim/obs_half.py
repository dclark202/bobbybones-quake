"""The inputs at half precision, as the trainer's norm() makes them (owner, 2026-11-15: "move everything to half precision ... it
just needs to be consistent").

The trainer (sim/train_duel_rnn.py norm()), the checks' player (sim/test_suite.py Policy.act) and the plugins' pass
(plugins/netpass.py step) all do, in numpy:

    np.clip((obs - mean) / np.sqrt(var + 1e-8), -10, 10).astype(np.float16).astype(np.float32)

with obs float32 and mean, var float64 (a checkpoint's obs_mean / obs_var): the sums in float64, then ONE rounding to half precision.
norm_t() is the same on a torch tensor (the brain's lessons on the card: sim/brain_fit.py, sim/brain_human.py), bit for bit. Torch's
own double -> half cast goes through single precision first (two roundings: a value next to a midpoint of half precision can go the
other way), so the one rounding is done here in double precision: x scaled by a power of two to a whole-number grid, rounded to
nearest-even by adding and taking away 2^52, scaled back. Numpy only at the top; torch is imported in norm_t."""
import numpy as np

EPS = 1e-8


def stats(mean, var):
    """a checkpoint's obs_mean, obs_var -> (mean, sd) in float64, as the trainer uses them"""
    m = np.asarray(mean, np.float64)
    return m, np.sqrt(np.asarray(var, np.float64) + EPS)


def norm_np(obs, mean, var):
    """the trainer's norm() without its map cells (no network since v9 has them): float32 [.., D]"""
    return np.clip((obs - np.asarray(mean, np.float64)) / np.sqrt(np.asarray(var, np.float64) + EPS), -10, 10).astype(np.float16).astype(np.float32)


def half_t(x):
    """a float64 tensor -> float32 holding x rounded once to half precision (nearest, ties to even), as numpy's float64 -> float16.
    Exact for |x| < 65504 (the normalised inputs are within +-10)."""
    import torch
    x = x.double()
    _, ex = torch.frexp(x)                                   # |x| = m 2^ex, m in [0.5, 1): the binade's exponent is ex - 1
    e = torch.clamp(ex.to(torch.int64) - 1, min=-14)         # (below 2^-14 the subnormals: a fixed step of 2^-24)
    step = ((e - 10 + 1023) << 52).view(torch.float64)       # 2^(e - 10) built from its bits (exact on any device): half keeps 10 bits
                                                             # after the leading one
    c = 4503599627370496.0                                   # 2^52: adding it rounds |x / step| < 2^11 to a whole number, ties to even
    r = ((x.abs() / step + c) - c) * step
    return torch.copysign(r, x).float()


def norm_t(o, mean_t, sd_t):
    """o (a tensor of raw inputs), mean_t, sd_t (float64 tensors from stats(), on o's device) -> float32 as the trainer's norm()"""
    import torch
    return half_t(torch.clamp((o.to(torch.float32).double() - mean_t) / sd_t, -10, 10))
