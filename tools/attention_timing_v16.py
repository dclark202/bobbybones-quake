"""What the v16 model (docs/design/V16_ATTENTION.md) would cost at play time: random weights, numpy only, one thread, the
arithmetic a play plugin would do each frame, timed for 1 to 4 bots.

    python tools/attention_timing_v16.py [--frames 3000]
    ssh <server> 'docker exec -i qlduel python3 -' < tools/attention_timing_v16.py     (the rented server, inside the game's image;
                                                                                         only with nobody playing: it takes a core for a minute)

  flat   today's network: 577 inputs -> 256 -> 256 -> GRU 512 -> 77 logits
  v16    the same, and beside it T tokens of 24 numbers -> width D; block 1: self-attention among all tokens (4 heads,
         feed-forward 2 D); block 2: the same computed only for the two rows that are read (himself, the summary); the two
         rows -> Linear(2 D, 256) added to the encoder's output before the GRU
Variants: D 96 with 58 tokens (the proposal), D 64 with 58, D 96 with 48, D 64 with 48."""
import os
import sys
import time

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "1")                    # one thread, as inside the game server's frame
import numpy as np

FRAMES = int(sys.argv[sys.argv.index("--frames") + 1]) if "--frames" in sys.argv else 3000
F, HEADS, FLAT, HID, GRU, OUT = 24, 4, 577, 256, 512, 77
rng = np.random.default_rng(0)
W = lambda o, i: (rng.standard_normal((o, i)) / np.sqrt(i)).astype(np.float32)      # noqa: E731
Z = lambda n: np.zeros(n, np.float32)                                               # noqa: E731
sig = lambda x: 1.0 / (1.0 + np.exp(-x))                                            # noqa: E731


def norm(x):
    m = x.mean(-1, keepdims=True)
    return (x - m) / np.sqrt(((x - m) ** 2).mean(-1, keepdims=True) + 1e-5)


def make(D, T):
    blk = lambda: dict(q=W(D, D), k=W(D, D), v=W(D, D), o=W(D, D), f1=W(2 * D, D), f2=W(D, 2 * D))      # noqa: E731
    return dict(w0=W(HID, FLAT), b0=Z(HID), w1=W(HID, HID), b1=Z(HID), wih=W(3 * GRU, HID), whh=W(3 * GRU, GRU), bih=Z(3 * GRU), bhh=Z(3 * GRU),
                wp=W(OUT, GRU), bp=Z(OUT), emb=W(D, F), kind=(rng.standard_normal((T, D)) * 0.1).astype(np.float32), b1k=blk(), b2k=blk(),
                read=np.zeros((HID, 2 * D), np.float32) + 0.01, D=D, T=T)


def attend(B_, xq, xall, P):
    """rows xq [B, Q, D] attend over xall [B, T, D]: 4 heads, then the feed-forward part"""
    D = xall.shape[-1]
    hd = D // HEADS
    q = (norm(xq) @ B_["q"].T).reshape(xq.shape[0], -1, HEADS, hd).transpose(0, 2, 1, 3)
    na = norm(xall)
    k = (na @ B_["k"].T).reshape(xall.shape[0], -1, HEADS, hd).transpose(0, 2, 3, 1)
    v = (na @ B_["v"].T).reshape(xall.shape[0], -1, HEADS, hd).transpose(0, 2, 1, 3)
    a = (q @ k) / np.sqrt(hd)
    a = np.exp(a - a.max(-1, keepdims=True))
    a /= a.sum(-1, keepdims=True)
    y = xq + (a @ v).transpose(0, 2, 1, 3).reshape(xq.shape[0], -1, D) @ B_["o"].T
    return y + np.maximum(norm(y) @ B_["f1"].T, 0.0) @ B_["f2"].T


def step(P, x, tok, h, v16):
    e = np.tanh(np.tanh(x @ P["w0"].T + P["b0"]) @ P["w1"].T + P["b1"])
    if v16:
        t = tok @ P["emb"].T + P["kind"]
        t = attend(P["b1k"], t, t, P)                # block 1: every token over every token
        r = attend(P["b2k"], t[:, :2], t, P)         # block 2: only the two rows that are read
        e = e + r.reshape(len(x), -1) @ P["read"].T
    gi = e @ P["wih"].T + P["bih"]
    gh = h @ P["whh"].T + P["bhh"]
    r_ = sig(gi[:, :GRU] + gh[:, :GRU])
    z = sig(gi[:, GRU:2 * GRU] + gh[:, GRU:2 * GRU])
    n = np.tanh(gi[:, 2 * GRU:] + r_ * gh[:, 2 * GRU:])
    h = (1 - z) * n + z * h
    return h @ P["wp"].T + P["bp"], h


def time_it(P, B, v16):
    x = rng.standard_normal((FRAMES, B, FLAT)).astype(np.float32)
    tok = rng.standard_normal((FRAMES, B, P["T"], F)).astype(np.float32)
    h = np.zeros((B, GRU), np.float32)
    ts = np.zeros(FRAMES)
    for f in range(FRAMES):
        t0 = time.perf_counter()
        lg, h = step(P, x[f], tok[f], h, v16)
        for i in range(0, OUT, 7):                   # (sampling the outputs, roughly as the plugin does)
            p = np.exp(lg[:, i:i + 7] - lg[:, i:i + 7].max(1, keepdims=True))
            (p / p.sum(1, keepdims=True)).cumsum(1)
        ts[f] = time.perf_counter() - t0
    return 1000 * np.median(ts[100:]), 1000 * np.percentile(ts[100:], 99)


print("milliseconds a frame for all bots together: median (99th percentile); {} frames, one thread".format(FRAMES))
print("| Bots | today's network | D 96, 58 tokens | D 64, 58 tokens | D 96, 48 tokens | D 64, 48 tokens |")
print("|---|---|---|---|---|---|")
models = [(make(96, 58), False), (make(96, 58), True), (make(64, 58), True), (make(96, 48), True), (make(64, 48), True)]
for B in (1, 2, 3, 4):
    print("| {} | ".format(B) + " | ".join("{:.2f} ({:.2f})".format(*time_it(P, B, v)) for P, v in models) + " |", flush=True)
