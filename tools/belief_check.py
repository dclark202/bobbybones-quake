"""v0.4.0 stage A: checks of the belief memory (sim/belief.py) on random numbers, CPU only (a few seconds).

    python tools/belief_check.py

1. online = sequence: the rollout's State stepped frame by frame (resets anywhere, on a tick's frame and on the frame
   before one too) gives the same states at the ticks as seq() over the whole rollout, by the loop and by the trainer's
   gru_seq (the library's GRU cut at the resets).
2. a one-frame spike: a single frame's input changed between two ticks changes that tick's input (the max part by the
   spike's full size), and nothing before it.
3. isolation: the readout's lesson (both parts: sim/track.py and sim/track_z.py) on the belief's state gives a gradient to the belief and the readout only (every
   other parameter of a stand-in policy that reads the same inputs: no gradient at all).
"""
import os
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "sim"))
import belief as B                                             # noqa: E402
import track as track_                                         # noqa: E402
import track_z as trz_                                         # noqa: E402
from train_duel_rnn import gru_seq, gru_layout                             # noqa: E402


def online(mod, L, x, done):
    T, n, _ = x.shape
    st = B.State(n, L, "cpu")
    out = []
    for t in range(T):
        if st.frame(mod, x[t], (t + 1) % L["every"] == 0):
            out.append(st.s.clone())
        st.reset(done[t])
    return torch.stack(out), st


def main():
    torch.manual_seed(0)
    torch.set_default_dtype(torch.float32)
    L = B.layout(obs_dim=37, hid=16, every=8)
    mod = B.make_module(L)
    T, n, K = 64, 7, 8
    x = torch.randn(T, n, 37) * 2
    done = torch.zeros(T, n)
    done[3, 0] = 1                         # inside a window
    done[7, 1] = 1                         # on a tick's frame (after the tick)
    done[6, 2] = 1                         # on the frame before a tick (the tick has only its own frame)
    done[8, 3] = 1                         # the first frame after a tick
    done[15, 4] = done[16, 4] = done[40, 4] = 1
    done[:, 5] = (torch.rand(T) < 0.2).float()
    s0 = torch.randn(n, 16) * 0.5
    with torch.no_grad():
        st = B.State(n, L, "cpu")
        st.s = s0.clone()
        out = []
        for t in range(T):
            if st.frame(mod, x[t], (t + 1) % K == 0):
                out.append(st.s.clone())
            st.reset(done[t])
        on = torch.stack(out)
        sq = B.seq(mod, x, done, s0, K)
        sg = B.seq(mod, x, done, s0, K, gru_fn=gru_seq)
        lay = gru_layout(B.tick_resets(done, K)[1], torch.device("cpu"))       # (--learn-nosync: the cut made on the host)
        sl = B.seq(mod, x, done, s0, K, gru_fn=lambda c_, e_, h_, d_: gru_seq(c_, e_, h_, d_, lay=lay))
    e1, e2, e3 = float((on - sq).abs().max()), float((on - sg).abs().max()), float((on - sl).abs().max())
    print("1. online against seq: largest difference {:.2e} (loop), {:.2e} (gru_seq), {:.2e} (gru_seq, host cut); end state carried: cnt {}".format(
        e1, e2, e3, st.cnt.tolist()))
    assert e1 < 1e-5 and e2 < 1e-5 and e3 < 1e-5, "online and sequence differ"
    assert float(st.cnt.abs().max()) == 0.0, "a rollout of whole ticks must end with nothing gathered"

    # 2. a one-frame spike between two ticks (frame 19, inside the window of tick 2: frames 16..23)
    x = x.clone()
    x[:, 6] = 0.0                          # a quiet seat: the same inputs on every frame (a constant inp output)
    x2 = x.clone()
    j = 5
    with torch.no_grad():
        u = mod.enc(x)
        i_ = int(torch.argmax(mod.inp.weight[j]))
        x2[19, 6, i_] += 40.0 * torch.sign(mod.inp.weight[j, i_])        # one input pushed hard on one frame
        u2 = mod.enc(x2)
        a1, _ = B.summaries(u, torch.zeros(T, n), K)
        a2, _ = B.summaries(u2, torch.zeros(T, n), K)
    dm = (a2 - a1)[:, 6]
    H = L["hid"]
    print("2. spike on frame 19, input unit {}: unit {} of frame 19 {:.3f} -> {:.3f}; tick 2's input: mean part +{:.3f}, max part "
          "+{:.3f}; the other ticks' change {:.1e}".format(i_, j, float(u[19, 6, j]), float(u2[19, 6, j]), float(dm[2, j]),
                                                          float(dm[2, H + j]), float(torch.cat([dm[:2], dm[3:]]).abs().max())))
    assert float(dm[2, H + j]) > 0.0 and float(torch.cat([dm[:2], dm[3:]]).abs().max()) == 0.0
    assert abs(float(dm[2, H + j]) - K * float(dm[2, j])) < 1e-4, "the max part carries the spike at full size, the mean at 1/K"

    # 3. isolation: a stand-in policy (encoder, GRU, output) reads the same x; the lesson reads the belief only
    pol = torch.nn.Module()
    pol.enc = torch.nn.Linear(37, 32)
    pol.gru = torch.nn.GRUCell(32, 24)
    pol.pi = torch.nn.Linear(24, 5)
    pol.belief = mod
    TL = track_.layout()
    pol.track = track_.make_module(H, TL)
    pol.trackz = trz_.make_module(H, trz_.layout(inp=H))     # (2026-10-23: the readout's second part, its lesson beside)
    with torch.no_grad():
        pol.track[2].weight.normal_(0, 0.1)                     # (at zero, the first layer would get no gradient)
        pol.trackz[2].weight.normal_(0, 0.1)
    xs = x.clone()
    h, hs = torch.zeros(n, 24), []
    for t in range(T):                                          # the policy's forward pass, in the same graph
        h = pol.gru(torch.tanh(pol.enc(xs[t])), h)
        hs.append(h)
    _ = pol.pi(torch.stack(hs))
    bs = B.seq(pol.belief, xs, done, s0, K)
    y = torch.zeros(T // K, n, len(track_.COLS))
    y[..., 0:3] = torch.randn(T // K, n, 3) * 500
    lo, _ = track_.loss(pol.track(bs), y, track_.DEFAULT_W, torch.ones(T // K, n))
    yz = torch.zeros(T // K, n, len(trz_.COLS))
    yz[..., 0] = torch.randint(0, 16, (T // K, n))
    yz[..., 1] = 16
    yz[..., 2] = 300 + 100 * torch.randn(T // K, n)
    yz[..., 3:5] = 300 * torch.randn(T // K, n, 2)
    lz, _ = trz_.loss(pol.trackz(bs), yz, trz_.DEFAULT_W, torch.ones(T // K, n))
    lo = lo + lz
    names = [nm for nm, _ in pol.named_parameters()]
    gr = torch.autograd.grad(lo, [p for _, p in pol.named_parameters()], allow_unused=True)
    bad = [nm for nm, g in zip(names, gr) if not nm.startswith(("belief.", "track.", "trackz.")) and g is not None and float(g.abs().sum()) != 0.0]
    got = [nm for nm, g in zip(names, gr) if nm.startswith(("belief.", "track.", "trackz.")) and g is not None and float(g.abs().sum()) > 0.0]
    print("3. the lesson's gradient: {} of {} policy parameters reached ({}); belief and readout parameters reached: {} of {}".format(
        len(bad), sum(not nm.startswith(("belief.", "track.", "trackz.")) for nm in names), bad or "none",
        len(got), sum(nm.startswith(("belief.", "track.", "trackz.")) for nm in names)))
    assert not bad
    print("belief_check: all passed")


if __name__ == "__main__":
    main()
