"""Pretraining of v0.4's head on the sequences of sim/head_data.py (docs/v0.4/BUILD_v0.4.md section 4): the hands of a
v0.3.1 network are frozen and give e (the encoder with the attention part) and h (the fast memory) frame by frame; only
the head learns, from three lessons:
  target  which item or holding place the player reaches next (cross-entropy over the 17 intentions)
  enemy   where the enemy will be 3, 10 and 30 s on (cross-entropy over the same landmarks: the aux question "near")
  win     the band of the game's final score margin (cross-entropy over 5 bands)

    python sim/pretrain_head.py --ck <policy.pt> --data scratch/head_data --steps 300 [--small] [--test <names>]

The hands: the checkpoint's enc, attn and gru, in eval mode, never in the optimiser; their weights are hashed before and
after and must be bit-identical. The head's plan_in stays at zero (not trained here): the hands' memory does not depend on
the head, so e and h are worked out once per shard (cached in --cache) and the head is unrolled over its ticks alone
(head_ticks below: sim/head.py's tick() once a tick, the store read before the step, a slot written every write_every
ticks; its read entropy by tick()'s stats). The enemy lesson's
layer (pre.en, size -> 3 x 17) belongs to the pretraining only: the head's aux.* questions are the trainer's.

The gate numbers (on the held-out ticks):
  does the head's guess of the enemy's landmark at 10 and 30 s beat the belief inputs (the landmark of v0.2's believed
  place now, v02_bel; a tick with nothing believed counts as a miss, and also shown on the believed ticks alone);
  does its target agree with the pros (or the people) more often than the item rule (env.intent_rule() at the tick).

The held-out ticks are whole shards (--split shard, the default), a game's two seats together (a session's b and o): the
win band is one number a game, so a time split would hold out later minutes of games seen in training. --test names them
(parts of shard names); without it groups are drawn until --hold of the ticks are held out."""
import argparse
import glob
import hashlib
import importlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


class Hands:
    """the frozen hands of a checkpoint (encoder, attention part, fast GRU) in torch on the CPU"""

    def __init__(self, ck_path):
        import torch
        import torch.nn as nn
        import attn as attn_
        ck = torch.load(ck_path, weights_only=False, map_location="cpu")
        sd = ck["model"]
        self.mean = torch.tensor(np.asarray(ck["obs_mean"], np.float32))
        self.std = torch.tensor(np.sqrt(np.asarray(ck["obs_var"], np.float64) + 1e-8).astype(np.float32))
        D = int(self.mean.shape[0])
        H = int(sd["gru.weight_hh"].shape[1])
        assert "cell.weight" not in sd, "a network with map cells (v8) is not handled here"
        self.enc = nn.Sequential(nn.Linear(D, 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh())
        self.enc.load_state_dict({k[4:]: v for k, v in sd.items() if k.startswith("enc.")})
        self.attn = None
        if ck.get("attn") is not None:
            self.attn = attn_.make_module(ck["attn"], 256)
            self.attn.load_state_dict({k[5:]: v for k, v in sd.items() if k.startswith("attn.")})
        self.gru = nn.GRU(256, H)
        g = {"weight_ih_l0": sd["gru.weight_ih"], "weight_hh_l0": sd["gru.weight_hh"], "bias_ih_l0": sd["gru.bias_ih"],
             "bias_hh_l0": sd["gru.bias_hh"]}
        self.gru.load_state_dict(g)
        self.mods = [m for m in (self.enc, self.attn, self.gru) if m is not None]
        for m in self.mods:
            m.eval()
            m.requires_grad_(False)
        self.D, self.H = D, H
        self.ck = ck

    def digest(self):
        """a hash of every weight of the hands (bit-identical before and after)"""
        h = hashlib.sha256()
        for m in self.mods:
            for k, v in sorted(m.state_dict().items()):
                h.update(k.encode())
                h.update(v.detach().cpu().numpy().tobytes())
        return h.hexdigest()

    def encode(self, obs, chunk=4096):
        """obs [F, D] (raw inputs) -> e [F, 256] (what the fast GRU is given)"""
        import torch
        out = []
        with torch.no_grad():
            for i in range(0, len(obs), chunk):
                x = torch.as_tensor(np.asarray(obs[i:i + chunk], np.float32))
                x = ((x - self.mean) / self.std).clamp(-10, 10)
                e = self.enc(x)
                if self.attn is not None:
                    e = e + self.attn(x)
                out.append(e)
        return torch.cat(out).numpy()

    def run(self, obs, done, h0=None):
        """obs [F, D], done [F] (the memory is cleared after these frames) -> e [F, 256], h [F, H] (after each frame)"""
        import torch
        e = self.encode(obs)
        F = len(e)
        h = np.zeros((F, self.H), np.float32)
        st = [0] + [i + 1 for i in np.nonzero(done)[0] if i + 1 < F]
        en = st[1:] + [F]
        with torch.no_grad():
            for k, (a, b) in enumerate(zip(st, en)):
                hi = torch.zeros(1, 1, self.H) if (k > 0 or h0 is None) else torch.as_tensor(h0, dtype=torch.float32).view(1, 1, -1)
                o, _ = self.gru(torch.as_tensor(e[a:b])[:, None], hi)
                h[a:b] = o[:, 0].numpy()
        return e, h

    def step(self, obs, h_in):
        """one frame from a stored memory: obs [T, D], h_in [T, H] -> e [T, 256], h after [T, H]"""
        import torch
        e = self.encode(obs)
        with torch.no_grad():
            g = self.gru
            h = torch.gru_cell(torch.as_tensor(e), torch.as_tensor(np.asarray(h_in, np.float32)), g.weight_ih_l0, g.weight_hh_l0,
                               g.bias_ih_l0, g.bias_hh_l0)
        return e, h.numpy()


def numpy_check(hands, ck_path, obs, n=40):
    """the hands here against sim/test_suite.py's numpy Policy (the checks' and the servers' sums) on n frames"""
    import test_suite as T
    P = T.Policy(ck_path)
    hh = np.zeros((1, P.W), np.float32)
    ref = []
    for k in range(n):
        _, hh = P.act(np.asarray(obs[k:k + 1], np.float32), hh)
        ref.append(hh[0, :P.H].copy())
    _, h = hands.run(obs[:n], np.zeros(n, bool))
    return float(np.abs(np.stack(ref) - h).max())


# ------------------------------------------------------------------------------------------------------------- the cache
def tick_inputs(hands, z):
    """one shard -> per tick: hf (the fast memory after the tick's frame), em (the mean of e over the tick's frames since
    the last clearing), rs (the memory was cleared since the last tick)"""
    obs, tick = z["obs"], z["tick"]
    if "h_in" in z.files:                                    # an input log: one row a tick, the memory he answered from
        e, h = hands.step(obs, z["h_in"])
        rs = np.zeros(len(tick), bool)
        return h.astype(np.float16), e.astype(np.float16), rs
    done = z["done"]
    e, h = hands.run(obs, done)
    J = len(tick)
    em = np.zeros((J, e.shape[1]), np.float32)
    rs = np.zeros(J, bool)
    prev = -1
    for j, f in enumerate(tick):
        a = prev + 1
        cut = np.nonzero(done[max(0, prev):f])[0]            # (a clearing after frame prev .. f - 1)
        if len(cut):
            rs[j] = True
            a = max(0, prev) + int(cut[-1]) + 1
        if prev < 0:
            rs[j] = True
        em[j] = e[a:f + 1].mean(0)
        prev = f
    return h[tick].astype(np.float16), em.astype(np.float16), rs


def load_shards(hands, files, cache_dir, ck_tag):
    os.makedirs(cache_dir, exist_ok=True)
    out = []
    for f in files:
        cf = os.path.join(cache_dir, "{}_{}.npz".format(os.path.splitext(os.path.basename(f))[0], ck_tag))
        z = np.load(f)
        if os.path.exists(cf) and os.path.getmtime(cf) >= os.path.getmtime(f):
            c = np.load(cf)
            hf, em, rs = c["hf"], c["em"], c["rs"]
        else:
            hf, em, rs = tick_inputs(hands, z)
            np.savez(cf, hf=hf, em=em, rs=rs)
        m = json.loads(str(z["meta"]))
        out.append(dict(name=os.path.basename(f), meta=m, hf=hf, em=em, rs=rs, ev=z["ev"].astype(np.float32),
                        target=z["target"].astype(np.int64), en=z["en_cls"].astype(np.int64), win=z["win"].astype(np.int64),
                        rule=z["rule"].astype(np.int64), bel=z["bel_cls"].astype(np.int64)))
    return out


# ------------------------------------------------------------------------------------------------------------ the head
def head_ticks(head, mod, lay, hf, em, ev, rs):
    """the head over J ticks of B sequences, under the gradient, by sim/head.py's tick() (the same function as its live()
    and seq()): hf [J, B, fast] the fast memory after each tick's frame, em [J, B, enc] the mean of e over the tick's frames,
    ev [J, B, ev] the tick's events, rs [J, B] bool: the memory was cleared before this tick (State.reset: s, the store and
    its tick count; the plan is not used here: plan_in stays at zero). -> s [J, B, size], the read's entropy a tick (nats,
    mean over the heads of the sequences with a slot)"""
    import torch
    J, B = rs.shape
    st = head.State(B, lay, hf.device)
    out, ent = [], []
    for j in range(J):
        st.reset(rs[j].float())
        stats = []
        st.s, st.plan, st.slots, st.age1, st.ticks, _ = head.tick(mod, lay, st.s, st.slots, st.age1, st.ticks, hf[j], em[j], ev[j], stats)
        out.append(st.s)
        e_ = stats[0] if stats else None
        ent.append(float(e_[0] / e_[1]) if e_ is not None and float(e_[1]) > 0 else 0.0)
    return torch.stack(out), torch.tensor(ent)


# ------------------------------------------------------------------------------------------------------------ training
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ck", required=True, help="the hands' checkpoint (read only: give a copy)")
    ap.add_argument("--data", default=os.path.join(ROOT, "scratch", "head_data"))
    ap.add_argument("--cache", default=os.path.join(ROOT, "scratch", "head_cache"))
    ap.add_argument("--small", action="store_true", help="a small head for the CPU (size 256, store 64 slots of 64)")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--seq", type=int, default=128, help="ticks a window (128: 26 s)")
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--w-target", type=float, default=1.0)
    ap.add_argument("--w-enemy", type=float, default=1.0)
    ap.add_argument("--w-win", type=float, default=0.5)
    ap.add_argument("--hold", type=float, default=0.2, help="the share held out: whole games (--split shard) or the last part of every shard (time)")
    ap.add_argument("--split", default="shard", choices=("shard", "time"))
    ap.add_argument("--test", default="", help="--split shard: the held-out shards, comma-separated parts of their names")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "scratch", "pretrain_head"))
    ap.add_argument("--check-numpy", action="store_true", help="the hands against test_suite's numpy Policy on 40 frames")
    a = ap.parse_args()
    import torch
    import torch.nn as nn
    torch.manual_seed(a.seed)
    dev = torch.device("cpu")
    print("device", dev, "cuda visible:", torch.cuda.is_available(), "threads", torch.get_num_threads(), flush=True)
    head = importlib.import_module("head")
    print("head module:", head.__file__, "version", getattr(head, "VERSION", "?"), flush=True)
    hands = Hands(a.ck)
    d0 = hands.digest()
    ck_tag = hashlib.sha1(d0.encode()).hexdigest()[:8]
    files = sorted(glob.glob(os.path.join(a.data, "*.npz")))
    t0 = time.time()
    if a.check_numpy and files:
        z0 = np.load(files[0])
        print("hands vs the numpy Policy (40 frames): largest difference in h {:.2e}".format(numpy_check(hands, a.ck, z0["obs"])), flush=True)
    shards = load_shards(hands, files, a.cache, ck_tag)
    print("{} shards, {} ticks, e and h in {:.0f} s".format(len(shards), sum(len(s["target"]) for s in shards), time.time() - t0), flush=True)
    kw = dict(size=256, inp=192, plan=64, slots=64, slot=64, read=64) if a.small else {}
    lay = head.layout(**kw)
    nT = lay["n_target"]
    mod = head.make_module(lay, seed=a.seed)
    pre = nn.Module()
    pre.en = nn.Linear(lay["size"], 3 * nT)
    pin0 = [p.detach().clone() for p in mod.plan_in.parameters()]
    train_p = [p for n_, p in mod.named_parameters() if not n_.startswith("plan_in.")]
    for p in mod.plan_in.parameters():
        p.requires_grad_(False)
    opt = torch.optim.Adam(train_p + list(pre.parameters()), lr=a.lr)
    print("head: {} parameters learning (plan_in held at zero); layout {}".format(sum(p.numel() for p in train_p) + sum(p.numel() for p in pre.parameters()),
                                                                                  {k: lay[k] for k in ("size", "inp", "slots", "slot", "read")}), flush=True)
    # the split: the held-out ticks of each shard (time) or whole shards
    rng = np.random.default_rng(a.seed)
    for s in shards:
        s["test"] = np.zeros(len(s["target"]), bool)
        s["group"] = s["meta"]["source"] + ":" + s["meta"]["name"]          # (a session's two seats are one game)
        if a.split == "time":
            s["test"][int(len(s["target"]) * (1.0 - a.hold)):] = True
    if a.split == "shard":
        groups = sorted({s["group"] for s in shards})
        if a.test:
            pick = {s["group"] for s in shards if any(t_ and t_ in s["name"] for t_ in a.test.split(","))}
        else:
            pick, tot = set(), sum(len(s["target"]) for s in shards)
            for g in rng.permutation(groups):
                if sum(len(s["target"]) for s in shards if s["group"] in pick) >= a.hold * tot:
                    break
                pick.add(g)
        for s in shards:
            s["test"][:] = s["group"] in pick
        print("held out:", sorted(pick), flush=True)
    pool = [(k, s) for k, s in enumerate(shards) if (~s["test"]).sum() > a.seq]
    assert pool, "no shard with enough training ticks"
    wts = np.array([(~s["test"]).sum() for _, s in pool], np.float64)
    wts /= wts.sum()
    ce = nn.CrossEntropyLoss(reduction="none")

    def outputs(s_):
        return dict(target=mod.target(s_), win=mod.win(s_))

    def batch():
        hf, em, ev, rs, tg, en, wn = [], [], [], [], [], [], []
        for _ in range(a.batch):
            k, s = pool[rng.choice(len(pool), p=wts)]
            ntr = int((~s["test"]).sum()) if a.split == "time" else len(s["target"])
            i0 = int(rng.integers(0, ntr - a.seq))
            sl = slice(i0, i0 + a.seq)
            hf.append(s["hf"][sl]); em.append(s["em"][sl]); ev.append(s["ev"][sl])
            r_ = s["rs"][sl].copy(); r_[0] = True
            rs.append(r_); tg.append(s["target"][sl]); en.append(s["en"][sl]); wn.append(s["win"][sl])
        f = lambda x, dt=torch.float32: torch.as_tensor(np.stack(x, 1).astype(np.float32 if dt == torch.float32 else np.int64))
        return (f(hf), f(em), f(ev), torch.as_tensor(np.stack(rs, 1)), f(tg, 0), f(en, 0), f(wn, 0))

    def losses(s_, tg, en, wn):
        o = outputs(s_)
        lt = o["target"]
        le = pre.en(s_).view(*s_.shape[:2], 3, nT)
        out = {}
        m = tg >= 0
        out["target"] = (ce(lt.reshape(-1, nT), tg.clamp(min=0).reshape(-1)) * m.reshape(-1)).sum() / m.sum().clamp(min=1)
        me = en >= 0
        out["enemy"] = (ce(le.reshape(-1, nT), en.clamp(min=0).reshape(-1)) * me.reshape(-1)).sum() / me.sum().clamp(min=1)
        mw = wn >= 0
        out["win"] = (ce(o["win"].reshape(-1, lay["win_bands"]), wn.clamp(min=0).reshape(-1)) * mw.reshape(-1)).sum() / mw.sum().clamp(min=1)
        return out, lt, le, o["win"]

    def evaluate(test=True):
        """every shard run whole from its start (no gradient); the numbers on its held-out (or training) ticks"""
        mod.eval()
        acc = dict(n_t=0, t_head=0, t_rule=0, t_rule_any=0, n_rule_any=0, t_prior=0, n_w=0, w_head=0, w_prior=0, ce_t=0.0, ce_w=0.0, ce_e=0.0, n_e=0)
        for j in range(3):
            acc.update({"n_e%d" % j: 0, "e_head%d" % j: 0, "e_bel%d" % j: 0, "n_eb%d" % j: 0, "e_headb%d" % j: 0, "e_belb%d" % j: 0})
        with torch.no_grad():
            for s in shards:
                sel = s["test"] if test else ~s["test"]
                if not sel.any():
                    continue
                t_ = lambda x: torch.as_tensor(np.asarray(x, np.float32))[:, None]
                rs = torch.as_tensor(s["rs"])[:, None].clone()
                rs[0] = True
                s_, _ = head_ticks(head, mod, lay, t_(s["hf"]), t_(s["em"]), t_(s["ev"]), rs)
                o = outputs(s_)
                pt = o["target"][:, 0].argmax(-1).numpy()
                pe = pre.en(s_[:, 0]).view(-1, 3, nT).argmax(-1).numpy()
                pw = o["win"][:, 0].argmax(-1).numpy()
                lt = torch.log_softmax(o["target"][:, 0], -1).numpy()
                lw = torch.log_softmax(o["win"][:, 0], -1).numpy()
                le = torch.log_softmax(pre.en(s_[:, 0]).view(-1, 3, nT), -1).numpy()
                tg, en, wn, rule, bel = s["target"], s["en"], s["win"], s["rule"], s["bel"]
                m = sel & (tg >= 0)
                acc["n_t"] += int(m.sum())
                acc["t_head"] += int((pt[m] == tg[m]).sum())
                acc["t_rule"] += int((rule[m] == tg[m]).sum())
                acc["t_prior"] += int((prior_t == tg[m]).sum())
                mr = m & (rule > 0)
                acc["n_rule_any"] += int(mr.sum())
                acc["t_rule_any"] += int((rule[mr] == tg[mr]).sum())
                acc["ce_t"] += float(-lt[m, tg[m]].sum())
                mw = sel & (wn >= 0)
                acc["n_w"] += int(mw.sum())
                acc["w_head"] += int((pw[mw] == wn[mw]).sum())
                acc["w_prior"] += int((prior_w == wn[mw]).sum())
                acc["ce_w"] += float(-lw[mw, wn[mw]].sum())
                for j in range(3):
                    me = sel & (en[:, j] >= 0)
                    acc["n_e%d" % j] += int(me.sum())
                    acc["e_head%d" % j] += int((pe[me, j] == en[me, j]).sum())
                    acc["e_bel%d" % j] += int((bel[me] == en[me, j]).sum())
                    mb = me & (bel >= 0)
                    acc["n_eb%d" % j] += int(mb.sum())
                    acc["e_headb%d" % j] += int((pe[mb, j] == en[mb, j]).sum())
                    acc["e_belb%d" % j] += int((bel[mb] == en[mb, j]).sum())
                    acc["ce_e"] += float(-le[me, j, en[me, j]].sum())
                    acc["n_e"] += int(me.sum())
        mod.train()
        q = lambda x, n: round(x / n, 3) if n else None
        r = dict(ticks_target=acc["n_t"], target_head=q(acc["t_head"], acc["n_t"]), target_rule=q(acc["t_rule"], acc["n_t"]),
                 target_rule_named=q(acc["t_rule_any"], acc["n_rule_any"]), target_prior=q(acc["t_prior"], acc["n_t"]),
                 target_ce=q(acc["ce_t"], acc["n_t"]), ticks_win=acc["n_w"], win_head=q(acc["w_head"], acc["n_w"]),
                 win_prior=q(acc["w_prior"], acc["n_w"]), win_ce=q(acc["ce_w"], acc["n_w"]), enemy_ce=q(acc["ce_e"], acc["n_e"]))
        for j, sec in enumerate((3, 10, 30)):
            r["enemy%d" % sec] = dict(ticks=acc["n_e%d" % j], head=q(acc["e_head%d" % j], acc["n_e%d" % j]), belief=q(acc["e_bel%d" % j], acc["n_e%d" % j]),
                                      believed_ticks=acc["n_eb%d" % j], head_on_believed=q(acc["e_headb%d" % j], acc["n_eb%d" % j]),
                                      belief_on_believed=q(acc["e_belb%d" % j], acc["n_eb%d" % j]))
        return r

    # the priors (most common label on the training ticks): what a head that learnt nothing from the inputs gets
    tr_t = np.concatenate([s["target"][~s["test"]] for s in shards])
    tr_w = np.concatenate([s["win"][~s["test"]] for s in shards])
    prior_t = int(np.bincount(tr_t[tr_t >= 0], minlength=nT).argmax()) if (tr_t >= 0).any() else 0
    prior_w = int(np.bincount(tr_w[tr_w >= 0], minlength=5).argmax()) if (tr_w >= 0).any() else 2
    rates = {k: round(float(np.mean(np.concatenate([(s[k] if s[k].ndim == 1 else s[k][:, 1]) >= 0 for s in shards]))), 3) for k in ("target", "en", "win", "bel")}
    print("label rates over all ticks (known): target {target}, enemy at 10 s {en}, win {win}, belief {bel}".format(**rates), flush=True)
    ev0 = evaluate(True)
    print("held out before:", json.dumps(ev0), flush=True)
    hist = []
    t1 = time.time()
    for step in range(1, a.steps + 1):
        hf, em, ev, rs, tg, en, wn = batch()
        s_, ent = head_ticks(head, mod, lay, hf, em, ev, rs)
        L, _, _, _ = losses(s_, tg, en, wn)
        loss = a.w_target * L["target"] + a.w_enemy * L["enemy"] + a.w_win * L["win"]
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(train_p + list(pre.parameters()), 1.0)
        opt.step()
        hist.append([float(L[k]) for k in ("target", "enemy", "win")] + [float(ent.mean())])
        if step % 25 == 0 or step == 1:
            h_ = np.mean(hist[-25:], 0)
            print("step {:4d}  loss target {:.3f} enemy {:.3f} win {:.3f}  read entropy {:.2f}  {:.2f} s/step".format(
                step, *h_, (time.time() - t1) / step), flush=True)
    ev1 = evaluate(True)
    evt = evaluate(False)
    print("held out after:", json.dumps(ev1), flush=True)
    print("training ticks after:", json.dumps(evt), flush=True)
    d1 = hands.digest()
    pin_same = all(torch.equal(p, q) for p, q in zip(mod.plan_in.parameters(), pin0))
    print("hands bit-identical before and after: {} ({}...)".format(d0 == d1, d0[:16]), flush=True)
    print("plan_in still zero: {}".format(pin_same and all(float(p.abs().max()) == 0.0 for p in mod.plan_in.parameters())), flush=True)
    assert d0 == d1, "the hands changed"
    os.makedirs(a.out, exist_ok=True)
    first = np.mean(hist[:25], 0).tolist()
    last = np.mean(hist[-25:], 0).tolist()
    rep = dict(ck=os.path.basename(a.ck), head_module=head.__file__, layout=lay, steps=a.steps, shards=[s["name"] for s in shards],
               label_rates=rates, loss_first25=first, loss_last25=last, held_out_before=ev0, held_out_after=ev1, train_after=evt,
               hands_identical=d0 == d1, plan_in_zero=pin_same)
    json.dump(rep, open(os.path.join(a.out, "report.json"), "w"), indent=1)
    torch.save(dict(head=lay, model={"head." + k: v for k, v in mod.state_dict().items()},
                    pre={k: v for k, v in pre.state_dict().items()}, report=rep), os.path.join(a.out, "head_pre.pt"))
    print("losses, first 25 steps -> last 25: target {:.3f} -> {:.3f}, enemy {:.3f} -> {:.3f}, win {:.3f} -> {:.3f}".format(
        first[0], last[0], first[1], last[1], first[2], last[2]), flush=True)
    print("written:", os.path.join(a.out, "head_pre.pt"), flush=True)


if __name__ == "__main__":
    main()
