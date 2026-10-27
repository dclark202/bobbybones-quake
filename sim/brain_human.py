"""(brainppl, 2026-10-24) the brain's lesson on people's games inside a run: the trainer's --brain-human <dir>.

A dataset dir (sim/brain_fit.py --save-pack): obs.npy [L, B, OBS_DIM] float16 (raw inputs, read memory-mapped), done.npy [L, B],
labels.pt (the trainer's truth at the belief's ticks: track [W, B, 13], its mask, its per-part mask, track_z [W, B, 5],
ahead's tuple), meta.json. People's sessions and pro demos (sim/brain_data.py), packed in B lanes.

Each learning step of the brain's lesson (a minibatch: the trainer's belief branch of --track) takes the next piece of
PIECE frames of every lane, runs the brain over it from the state the lanes carried (detached, as rollouts are), and adds
trk_w x w x (track + track_z x trz_w / trk_w + ahead x ah_w / trk_w) of it to the loss: the same lesson as self-play's,
on people's frames, times w (the live factor BRAIN_HUMAN_W times its opening). Its inputs are numbers from a file: nothing
of the hands is in its graph (the trainer's iso proof covers the self-play part; brain_fit.py proves this part).
Imported lazily by the trainer; off (no --brain-human): never imported, the trainer is as before.
"""
import json
import os

import numpy as np

K = 8


def track_loss(o, y, weights, mask, pm):
    """sim/track.py's loss with a mask per part (pm [..., 5]: a demo has no health, armor or weapons owned of the enemy)"""
    import track as track_
    m = mask.float()[..., None] * pm
    ll = track_.loglik(o, y, floor=False)
    parts = -(ll * m).sum(tuple(range(ll.dim() - 1))) / m.sum(tuple(range(m.dim() - 1))).clamp(min=1.0)
    return (parts * track_.wvec(weights, o)).sum(), parts.detach()


class HumanLesson:
    def __init__(self, path, obs_mean, obs_var, hid, dev, piece=384, lanes=0):
        import torch
        self.path = path
        self.meta = json.load(open(os.path.join(path, "meta.json")))
        self.obs = np.load(os.path.join(path, "obs.npy"), mmap_mode="r")
        self.done = np.load(os.path.join(path, "done.npy"))
        Y = torch.load(os.path.join(path, "labels.pt"), weights_only=False)
        self.trk_y, self.trk_m, self.pm, self.trz_y, self.ah_y = Y["trk_y"], Y["trk_m"], Y["pm"], Y["trz_y"], tuple(Y["ah_y"])
        L, B = self.done.shape
        self.NB = B                                          # (the pack's lanes; a piece takes self.B of them, the groups in turn)
        self.B = B if lanes <= 0 else min(B, int(lanes))
        self.G = self.NB // self.B
        assert piece % K == 0 and L >= piece
        self.L, self.P = L - L % piece, int(piece)
        self.dev = dev
        self.mean = torch.as_tensor(np.asarray(obs_mean, np.float32), device=dev)
        self.sd = torch.as_tensor(np.sqrt(np.asarray(obs_var, np.float64) + 1e-8).astype(np.float32), device=dev)
        self.s = torch.zeros(self.G * self.B, int(hid), device=dev)      # (every lane's own state, carried)
        self.p0s = [0] * self.G
        self.g = 0
        self.p0 = 0
        self.lane0 = 0
        self.n = 0
        self.acc = None

    def describe(self):
        return "brain-human: {} lanes x {} frames ({:.1f} h; {}), pieces of {} frames x {} lanes (the lanes' groups in turn)".format(
            self.NB, self.L, self.NB * self.L / 144000.0, self.meta.get("sources"), self.P, self.B)

    def next_loss(self, pol, trk_parts, trz_parts, ah_layout, ah_parts, trz_f, ah_f):
        """the lesson of the next piece -> (loss tensor, parts numpy [12])"""
        import torch
        import ahead as ahead_
        import belief as belief_
        import track_z as trz_
        g = self.g                                           # (this piece's group of lanes; the next piece takes the next group)
        self.g = (self.g + 1) % self.G
        ln = slice(g * self.B, (g + 1) * self.B)
        if self.p0s[g] + self.P > self.L:                    # (the lanes start again: their last frame was a reset)
            self.p0s[g] = 0
            s_ = self.s.clone()
            s_[ln] = 0.0
            self.s = s_
        p0, P, B = self.p0s[g], self.P, self.B
        self.p0 = p0
        x = torch.from_numpy(np.ascontiguousarray(self.obs[p0:p0 + P, ln])).to(self.dev)
        x = torch.clamp((x.float() - self.mean) / self.sd, -10, 10).half().float()
        d = torch.from_numpy(self.done[p0:p0 + P, ln].astype(np.float32)).to(self.dev)
        sl = slice(p0 // K, (p0 + P) // K)
        bs = belief_.seq(pol.belief, x, d, self.s[ln], K)
        tm = self.trk_m[sl, ln].to(self.dev).float()
        tl, tp = track_loss(pol.track(bs), self.trk_y[sl, ln].to(self.dev).float(), trk_parts, tm, self.pm[sl, ln].to(self.dev))
        loss = tl
        zp = torch.zeros(3, device=self.dev)
        if trz_f > 0:
            zl, zp = trz_.loss(pol.trackz(bs), self.trz_y[sl, ln].to(self.dev).float(), trz_parts, tm)
            loss = loss + trz_f * zl
        ap = torch.zeros(4, device=self.dev)
        if ah_f > 0:
            al, ap, _ = ahead_.loss(pol.ahead(bs), ah_layout, tuple(y[sl, ln].to(self.dev) for y in self.ah_y), ah_parts, torch.ones_like(tm))
            loss = loss + ah_f * al
        s_ = self.s.clone()                                  # (not in place: the piece's graph holds the old state)
        s_[ln] = bs[-1].detach()
        self.s = s_
        self.p0s[g] += P
        self.n += 1
        pr = torch.cat([tp, zp, ap]).detach().float().cpu().numpy()
        self.acc = pr if self.acc is None else self.acc + pr
        return loss, pr

    def take_counters(self):
        """the mean parts since the last call, and the pieces"""
        if not self.n or self.acc is None:
            return None
        out = dict(pieces=self.n, parts=[round(float(v), 4) for v in self.acc / self.n], at=int(self.p0))
        self.acc, self.n = None, 0
        return out


class HumanMix:
    """several datasets (pro demos, server sessions) in set shares: next_loss is the shares' weighted sum of each one's
    next piece"""

    def __init__(self, lessons, shares):
        tot = float(sum(shares))
        assert tot > 0
        self.L = lessons
        self.w = [float(x) / tot for x in shares]

    def describe(self):
        return "; ".join("{} (share {:.2f})".format(l_.describe(), w_) for l_, w_ in zip(self.L, self.w))

    def next_loss(self, pol, trk_parts, trz_parts, ah_layout, ah_parts, trz_f, ah_f):
        loss = 0.0
        for l_, w_ in zip(self.L, self.w):
            if w_ > 0:
                x_, _ = l_.next_loss(pol, trk_parts, trz_parts, ah_layout, ah_parts, trz_f, ah_f)
                loss = loss + w_ * x_
        return loss

    def take_counters(self):
        out = {}
        for k_, l_ in enumerate(self.L):
            c_ = l_.take_counters()
            if c_ is not None:
                out["set{}".format(k_)] = dict(c_, share=round(self.w[k_], 3), name=os.path.basename(os.path.normpath(l_.path)))
        return out
