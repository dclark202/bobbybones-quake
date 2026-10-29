"""v0.6.1b: the brain's fade, checked on a saved network (read-only; CPU, one thread). Exit 0 = all passed."""
import os
import sys
ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, "sim"))
import numpy as np
import torch
torch.set_num_threads(1)
import belief as belief_
import btoken as btoken_

ck = torch.load(sys.argv[2], map_location="cpu", weights_only=False)
L = ck["belief"]
cols = ck["rule_fade"]["cols"]
sd = {k[len("belief."):]: v for k, v in ck["model"].items() if k.startswith("belief.")}
ok = True


def check(name, cond):
    global ok
    ok = ok and bool(cond)
    print(("PASS " if cond else "FAIL ") + name, flush=True)


m0 = belief_.make_module(L)
m0.load_state_dict(sd)
m1 = belief_.make_module(dict(L, fade=belief_.fade_layout(cols, 0.0)))
m1.load_state_dict(sd)
check("state dict keys unchanged", sorted(m0.state_dict()) == sorted(m1.state_dict()))
g = torch.Generator().manual_seed(1)
x = torch.randn(64, int(L["obs_dim"]), generator=g)
with torch.no_grad():
    ref = torch.tanh(m0.inp(x))
    check("g 0: the same as without the entry, bit for bit", torch.equal(m1.enc(x), ref))
    m1.fade_g = 0.3
    xm = x.clone()
    xm[:, cols] *= 0.7
    d = float((m1.enc(x) - torch.tanh(m0.inp(xm))).abs().max())
    check("g 0.3: the same as the inputs times 0.7 (max diff {:.2e})".format(d), d < 1e-5)
    m1.fade_g = 1.0
    x2 = x.clone()
    x2[:, cols] = torch.randn(64, len(cols), generator=g) * 5
    check("g 1: the faded columns change nothing", torch.equal(m1.enc(x), m1.enc(x2)))
    others = [c for c in range(x.shape[1]) if c not in set(cols)][:5]
    x3 = x.clone()
    x3[:, others] += 1.0
    check("g 1: the other columns still count", not torch.equal(m1.enc(x), m1.enc(x3)))
# the numpy brain (checks, servers): the same weights as the trainer's at g
sdn = {k: v.numpy() for k, v in ck["model"].items() if k.startswith("belief.")}
B0 = btoken_.numpy_brain(sdn, L, None, None)
check("numpy brain, no entry: weights as saved", np.array_equal(B0["inp_w"], sdn["belief.inp.weight"]))
B05 = btoken_.numpy_brain(sdn, dict(L, fade=belief_.fade_layout(cols, 0.5)), None, None)
m1.fade_g = 0.5
with torch.no_grad():
    ut = m1.enc(x).numpy()
un = np.tanh(x.numpy() @ B05["inp_w"].T + B05["inp_b"])
d = float(np.abs(ut - un).max())
m0n = np.tanh(x.numpy() @ B0["inp_w"].T + B0["inp_b"])                 # numpy against torch with no fade at all: the float noise
with torch.no_grad():
    d0 = float(np.abs(torch.tanh(m0.inp(x)).numpy() - m0n).max())
check("numpy brain at g 0.5 = the trainer's (max diff {:.2e}; numpy against torch without the fade {:.2e})".format(d, d0), d < 2 * d0 + 1e-6)
check("numpy brain did not change the saved weights", np.array_equal(sdn["belief.inp.weight"], ck["model"]["belief.inp.weight"].numpy()))
print("ALL PASSED" if ok else "FAILED", flush=True)
sys.exit(0 if ok else 1)
