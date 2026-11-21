"""1.7's servers (BUILD.md part 10): the plugins' forward pass (plugins/netpass.py, on sim/export_duel.py's file) against the checks'
(sim/test_suite.py Policy) with every part of 1.7 open, on the same random inputs and candidates: the start given random weights on the
order's parts on the head's state (ok_s, op_s) and on the fire push (fsc), every share and add 1, the order's token open. Checks: the
logits the same every frame (both draw from them), the order's held numbers the same, the keep column's order fields asked on the keep
readings in both, the brain's places ahead the same; and the file's attention part leaves the token out while it is shut.
    run17b.cmd docs/runs/1.7/1.7a/plugin_parity.py <a start of 1.7: tools/order_init.py add's out>"""
import os
import subprocess
import sys
import tempfile

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(ROOT, "sim"))
sys.path.insert(0, os.path.join(ROOT, "plugins"))
import attn as A  # noqa: E402
import head2 as head2_  # noqa: E402
import netpass as NP  # noqa: E402
import test_suite as T  # noqa: E402

OK = [True]


def check(name, c):
    OK[0] = OK[0] and bool(c)
    print(("PASS " if c else "FAIL ") + name, flush=True)


src = sys.argv[1]
ck = torch.load(src, map_location="cpu", weights_only=False)
sd = ck["model"]
g = torch.Generator().manual_seed(11)
for k_ in ("head2.ok_s.weight", "head2.op_s.weight", "head2.fsc.weight", "head2.fsc.bias", "head2.op_v.weight"):
    sd[k_] = torch.randn(sd[k_].shape, generator=g) * 0.3
for k_ in ("head2.keep_g", "head2.cmb_g", "head2.padd", "head2.fadd"):
    sd[k_] = torch.ones(())
rows = A.drop_rows(ck["attn"])
gate = sd["attn.gate"].clone()
gate[rows] = 0.0
sd["attn.gate"] = gate
D = tempfile.mkdtemp(prefix="parity17_")
rd = os.path.join(D, "data", "sim_runs", "parity")
os.makedirs(rd)
torch.save(ck, os.path.join(rd, "policy.pt"))
os.makedirs(os.path.join(ROOT, "data", "sim_runs"), exist_ok=True)
npz = os.path.join(D, "policy.npz")
r = subprocess.run([sys.executable, os.path.join(ROOT, "sim", "export_duel.py"), "--run", "parity", "--out", npz, "--env", "duel_env_ffa",
                    "--policy", os.path.join(rd, "policy.pt"), "--legs", "move_v17_look"], cwd=ROOT, capture_output=True, text=True)
print((r.stdout + r.stderr)[-600:])
check("the export wrote the file", r.returncode == 0 and os.path.exists(npz))
P, Aa = NP.load(npz)
check("the file has the pass readout and the order", P.get("_pass") is not None and P.get("_ord") is not None)
pol = T.Policy(os.path.join(rd, "policy.pt"), seed=7)
B, F = 6, 240
rng = np.random.default_rng(3)
h_t, h_n = pol.zeros(B), np.zeros((B, NP.width(P)), np.float32)
check("the same array width ({} and {})".format(h_t.shape[1], h_n.shape[1]), h_t.shape[1] == h_n.shape[1])
pose = np.zeros((B, 4), np.float32)
zmap = np.zeros(B, np.int64)
dl, dh, rd_t, rd_n, q_t, q_n, dfut = 0.0, 0.0, 0, 0, 0, 0, 0.0
nrng = np.random.default_rng(9)
ox = None
for t in range(F):
    raw = rng.normal(pol.mean, np.sqrt(pol.var) + 1e-3, size=(B, len(pol.mean))).astype(np.float32)
    pose[:, :3] += rng.normal(0, 10, (B, 3)).astype(np.float32)
    pose[:, 3] = rng.uniform(-180, 180, B)
    kf = np.stack([rng.uniform(0, 16, B), (rng.random(B) < 0.3), rng.integers(0, pol.dims[10], B), np.zeros(B), np.zeros(B),
                   np.full(B, 20.0), np.full(B, 20.0)], 1).astype(np.float32)
    xl = rng.normal(0, 1, (B, pol.legsP[0].shape[1])).astype(np.float32) if pol.needs_xl else None
    due_t, due_n = pol.order_due, NP.order_due(P)
    if t > 0:
        check_due = due_t == due_n
        if not check_due:
            check("frame {}: both see the same keep readings".format(t), False)
    if due_t or due_n:
        X = rng.normal(0, 0.5, (B, head2_.CMB_ROWS, head2_.CMB_F)).astype(np.float32)
        X[..., head2_.CMB_VALID] = (rng.random((B, head2_.CMB_ROWS)) < 0.8)
        ox = (X, rng.normal(0, 0.5, (B, head2_.CMB_NCTX)).astype(np.float32))
    else:
        ox = None
    kw = {"xl": xl} if xl is not None else {}
    at, h_t = pol.act(raw, h_t, pose=pose, zmap=zmap, kf=kf, ox=ox if due_t else None, **kw)
    an, h_n = NP.step(P, Aa, raw, h_n, nrng, xl=xl, pose=pose, zmap=zmap, kf=kf, ox=ox if due_n else None)
    dl = max(dl, float(np.abs(pol.last_logits - P["_logits"]).max()))
    dh = max(dh, float(np.abs(h_t - h_n).max()))
    ct, cn = at[:, -1], P["_keep"]
    rd_t += int(((ct >> 2) & 1).sum())
    rd_n += int(((cn >> 2) & 1).sum())
    q_t += int(((ct & 256) > 0).sum())
    q_n += int(((cn & 256) > 0).sum())
    if pol.fut is not None and P.get("_fut") is not None:
        dfut = max(dfut, float(np.abs(pol.fut - P["_fut"]).max()))
check("the logits the same every frame (largest difference {:.3g})".format(dl), dl < 1e-3)
check("the arrays the same: hands, head, the order's held numbers, the brain (largest difference {:.3g})".format(dh), dh < 1e-3)
check("keep readings in both ({}, {}) and the order asked at them ({}, {})".format(rd_t, rd_n, q_t, q_n), rd_t == rd_n and rd_t > 0 and q_t > 0 and q_n > 0)
check("the brain's places ahead the same (largest difference {:.3g})".format(dfut), dfut < 1e-2)
print("ALL PASSED" if OK[0] else "FAILED")
sys.exit(0 if OK[0] else 1)
