"""Step 0 of docs/design/ATTENTION_POC.md: what would attention over the scene cost at play time? Random weights, numpy only,
the same arithmetic the play plugin does for today's network (plugins/ffabot.py act_batch), timed for 1 to 6 bots.

    python tools/attention_timing.py [--frames 3000]
    ssh <server> 'docker exec -i qlduel python3 -' < tools/attention_timing.py        (the rented server, inside the game's image)

Three networks:
  flat     today's: 449 inputs -> 256 -> 256 -> GRU 512 -> 71 logits
  cross    120 own numbers + 40 tokens of 24 numbers; token MLP to 64, ONE cross-attention read (himself as the only
           query, 4 heads); 120 + 64 -> 256 -> 256 -> GRU 512 -> 71
  self     as cross, with one self-attention layer among the 40 tokens first (4 heads, feed-forward 128)
"""
import os
import sys
import time

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "1")                    # one thread, as inside the game server's frame
import numpy as np

FRAMES = int(sys.argv[sys.argv.index("--frames") + 1]) if "--frames" in sys.argv else 3000
OWN, K, F, D, HEADS, FLAT, HID, GRU, OUT = 120, 40, 24, 64, 4, 449, 256, 512, 71
rng = np.random.default_rng(0)
W = lambda o, i: (rng.standard_normal((o, i)) / np.sqrt(i)).astype(np.float32)      # noqa: E731
Z = lambda n: np.zeros(n, np.float32)                                               # noqa: E731
sig = lambda x: 1.0 / (1.0 + np.exp(-x))                                            # noqa: E731


def body(n_in):
    return dict(w0=W(HID, n_in), b0=Z(HID), w1=W(HID, HID), b1=Z(HID), wih=W(3 * GRU, HID), whh=W(3 * GRU, GRU),
                bih=Z(3 * GRU), bhh=Z(3 * GRU), wp=W(OUT, GRU), bp=Z(OUT))


def run_body(P, x, h):
    x = np.tanh(x @ P["w0"].T + P["b0"])
    x = np.tanh(x @ P["w1"].T + P["b1"])
    gi = x @ P["wih"].T + P["bih"]
    gh = h @ P["whh"].T + P["bhh"]
    r = sig(gi[:, :GRU] + gh[:, :GRU])
    z = sig(gi[:, GRU:2 * GRU] + gh[:, GRU:2 * GRU])
    n = np.tanh(gi[:, 2 * GRU:] + r * gh[:, 2 * GRU:])
    h = ((1 - z) * n + z * h).astype(np.float32)
    return h @ P["wp"].T + P["bp"], h


A = dict(t0=W(D, F), tb0=Z(D), t1=W(D, D), tb1=Z(D), q=W(D, OWN), k=W(D, D), v=W(D, D), o=W(D, D),
         sq=W(D, D), sk=W(D, D), sv=W(D, D), so=W(D, D), f0=W(2 * D, D), fb0=Z(2 * D), f1=W(D, 2 * D), fb1=Z(D))
P_FLAT, P_ATT = body(FLAT), body(OWN + D)


def heads(x):                                        # [B, T, D] -> [B, HEADS, T, D / HEADS]
    b, t, _ = x.shape
    return x.reshape(b, t, HEADS, D // HEADS).transpose(0, 2, 1, 3)


def tokens_in(tok):
    return np.tanh(np.tanh(tok @ A["t0"].T + A["tb0"]) @ A["t1"].T + A["tb1"])


def self_attention(e, mask):
    q, k, v = heads(e @ A["sq"].T), heads(e @ A["sk"].T), heads(e @ A["sv"].T)
    s = q @ k.transpose(0, 1, 3, 2) / np.sqrt(D // HEADS) + mask[:, None, None, :]
    s = np.exp(s - s.max(-1, keepdims=True))
    s /= s.sum(-1, keepdims=True)
    e = e + (s @ v).transpose(0, 2, 1, 3).reshape(e.shape) @ A["so"].T
    return e + np.maximum(e @ A["f0"].T + A["fb0"], 0) @ A["f1"].T + A["fb1"]


def cross_read(own, e, mask):
    q = (own @ A["q"].T).reshape(len(own), HEADS, 1, D // HEADS)
    k, v = heads(e @ A["k"].T), heads(e @ A["v"].T)
    s = q @ k.transpose(0, 1, 3, 2) / np.sqrt(D // HEADS) + mask[:, None, None, :]
    s = np.exp(s - s.max(-1, keepdims=True))
    s /= s.sum(-1, keepdims=True)
    return (s @ v).reshape(len(own), D) @ A["o"].T


def time_it(kind, B):
    h = np.zeros((B, GRU), np.float32)
    flat = rng.standard_normal((B, FLAT)).astype(np.float32)
    own = rng.standard_normal((B, OWN)).astype(np.float32)
    tok = rng.standard_normal((B, K, F)).astype(np.float32)
    mask = np.where(rng.random((B, K)) < 0.8, 0.0, -1e9).astype(np.float32)        # a fifth of the token slots empty
    mask[:, 0] = 0.0
    ts = []
    for _ in range(FRAMES):
        t = time.perf_counter()
        if kind == "flat":
            _, h = run_body(P_FLAT, flat, h)
        else:
            e = tokens_in(tok)
            if kind == "self":
                e = self_attention(e, mask)
            _, h = run_body(P_ATT, np.concatenate([own, cross_read(own, e, mask)], 1), h)
        ts.append(time.perf_counter() - t)
    ts = np.array(ts[FRAMES // 10:]) * 1000.0
    return float(np.median(ts)), float(np.percentile(ts, 99))


print("numpy {}, {} frames, one thread; milliseconds a frame for all bots together: median (99th percentile)".format(np.__version__, FRAMES))
print("{:>6s} | {:>16s} | {:>16s} | {:>16s}".format("bots", "flat (today)", "cross-attention", "+ self-attention"))
for B in (1, 2, 3, 4, 6):
    r = [time_it(kd, B) for kd in ("flat", "cross", "self")]
    print("{:>6d} | {:>7.2f} ({:>5.2f}) | {:>7.2f} ({:>5.2f}) | {:>7.2f} ({:>5.2f})".format(B, *[x for p in r for x in p]))
