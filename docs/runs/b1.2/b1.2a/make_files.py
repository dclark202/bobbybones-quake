"""b1.2a's code edits and train.cmd (owner, 2026-10-31). Edits, applied once (--patch): the trainer's --head2-pay (the head's value and advantage on combat plus win pay; "all" as before),
ramp_head.py's names and hold (RAMP_OPEN_NAME, RAMP_HOLD_AT). train.cmd from b1.1a's: --run duel_gru_b1_2a, --minutes 1440, the head's arguments.
    python docs/runs/b1.2/b1.2a/make_files.py [--patch]"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
BS = "\\"


def rep(p, *pairs):
    p = os.path.join(ROOT, p)
    t = open(p, encoding="utf-8", newline="").read()
    for a, b in pairs:
        assert t.count(a) == 1, (p, a[:70], t.count(a))
        t = t.replace(a, b)
    open(p, "w", encoding="utf-8", newline="").write(t)


if "--patch" in sys.argv:
    rep("sim/train_duel_rnn.py",
        ('                         (wv_pack(env, wv_pre, info, G) if wv_pre is not None else None)))',
         '                         (wv_pack(env, wv_pre, info, G) if wv_pre is not None else None),\n'
         '                         (((1.0 - float(E_.WIN_W)) * info["win_blend"][:, 1] + info["win_blend"][:, 2]).astype(np.float32)   # (--head2-pay combat_win) combat plus the win part\n'
         '                          if "win_blend" in info else None)))'),
        ('    ap.add_argument("--head2-v", type=float, default=0.5,',
         '    ap.add_argument("--head2-pay", default="all", choices=("all", "combat_win"), help="(--head2, b1.2a) what its value and advantage count: his whole pay, or combat (frags, deaths, damage) plus the win part, not the item pay")\n'
         '    ap.add_argument("--head2-v", type=float, default=0.5,'),
        ('        b_rew = torch.zeros(T, N, device=dev)\n',
         '        b_rew = torch.zeros(T, N, device=dev)\n'
         '        b_hr = torch.zeros(T, N, device=dev) if a.head2_pay != "all" else None   # (--head2-pay) the head\'s own pay\n'),
        ('            b_rew[t] = torch.from_numpy(np.concatenate([r[1] for r in res])).to(dev)\n',
         '            b_rew[t] = torch.from_numpy(np.concatenate([r[1] for r in res])).to(dev)\n'
         '            if b_hr is not None:                                         # (a frame with no blend: his pay as it is)\n'
         '                b_hr[t] = torch.from_numpy(np.concatenate([r[21] if r[21] is not None else r[1] for r in res])).to(dev)\n'),
        ('        return dict(b_obs=b_obs, b_hq=b_hq, b_rl=b_rl, b_val2=b_val2, b_act=b_act, b_logp=b_logp, b_val=b_val, b_rew=b_rew,',
         '        return dict(b_hr=b_hr, b_obs=b_obs, b_hq=b_hq, b_rl=b_rl, b_val2=b_val2, b_act=b_act, b_logp=b_logp, b_val=b_val, b_rew=b_rew,'),
        ('            ADV_H, RET_H = head2_.gae(b_rew, B_VH, b_done, float(H2L["gamma"]), lam)\n',
         '            B_HR = R.get("b_hr") if R.get("b_hr") is not None else b_rew\n'
         '            H2_PAYS = [float(B_HR.abs().mean()), float(b_rew.abs().mean())]   # (a frame\'s |pay|: the head\'s, his)\n'
         '            ADV_H, RET_H = head2_.gae(B_HR, B_VH, b_done, float(H2L["gamma"]), lam)\n'),
        ('                v=round(float(B_VH[:T].mean()), 4), ret=round(float(RET_H.mean()), 4),',
         '                pay=a.head2_pay, pay_abs=[round(x_, 6) for x_ in H2_PAYS], v=round(float(B_VH[:T].mean()), 4), ret=round(float(RET_H.mean()), 4),'))
    rep("tools/run/ramp_head.py",
        ('HEAD_ONLY = float(os.environ.get("RAMP_HEAD_ONLY") or 0) > 0\n',
         'HEAD_ONLY = float(os.environ.get("RAMP_HEAD_ONLY") or 0) > 0\n'
         'OPEN_NAME = os.environ.get("RAMP_OPEN_NAME") or "policy_head_open_v062.pt"   # (b1.2a) the head-open save\'s name\n'
         'HOLD_AT = float(os.environ.get("RAMP_HOLD_AT") or 0)          # (b1.2a) no step while the last check is at or under this win rate; 0: on the clock\n'),
        ('kept = os.path.exists(os.path.join(KEEP, "policy_head_open_v062.pt"))', 'kept = os.path.exists(os.path.join(KEEP, OPEN_NAME))\nFLAGGED = [len(jl(CHK))]'),
        ('            shutil.copy2(src, os.path.join(KEEP, "policy_head_open_v062.pt"))\n', '            shutil.copy2(src, os.path.join(KEEP, OPEN_NAME))\n'),
        ('as keep/policy_head_open_v062.pt (the owner\'s play test; training goes on)".format(tag))', 'as keep/{} (the owner\'s play test; training goes on)".format(tag, OPEN_NAME))'),
        ('    if n < n_last + EVERY_N or time.time() - t_last < EVERY_S:\n        continue\n',
         '    if HOLD_AT > 0:                                          # (b1.2a) a check under 50% is flagged; at or under HOLD_AT it holds the next step\n'
         '        c_ = jl(CHK)\n'
         '        for d_ in c_[FLAGGED[0]:]:\n'
         '            if d_["won"] / max(1, d_["won"] + d_["lost"]) < 0.5:\n'
         '                log("FLAG check update {} against the start: {}-{}".format(d_.get("update"), d_["won"], d_["lost"]))\n'
         '        FLAGGED[0] = len(c_)\n'
         '        if c_ and c_[-1]["won"] / max(1, c_[-1]["won"] + c_[-1]["lost"]) <= HOLD_AT:\n'
         '            continue\n'
         '    if n < n_last + EVERY_N or time.time() - t_last < EVERY_S:\n        continue\n'))
    print("patched")

t = open(os.path.join(HERE, "..", "..", "b1.1", "b1.1a", "train.cmd"), encoding="ascii").read().replace("\r\n", "\n")


def sub(a, b):
    global t
    assert t.count(a) == 1, (a, t.count(a))
    t = t.replace(a, b)


t = t.replace("duel_gru_b1_1a", "duel_gru_b1_2a")
sub("--minutes 885 --gamma", "--minutes 1440 --gamma")
sub(" %LEARN% >> ", " --head2 1 --head2-ctrl-src belief --head2-open 1 --head2-cap 0 --head2-gate 0 --head2-start %H2_START% --head2-pay combat_win %LEARN% >> ")
sub('if "%RF_START%"=="" set RF_START=18411.038983547685',
    'if "%H2_START%"=="" set H2_START=-1\nif "%RF_START%"=="" set RF_START=18411.038983547685')
sub("rem the repo root: this file lives in docs\\runs\\b1.1\\b1.1a\\",
    "rem ==== b1.2a (owner, 2026-10-31; docs/runs/b1.2/b1.2a/CARD.md): the strategy head faded in, learning from combat plus win pay (--head2-pay combat_win); the item rule stays on. b1.1a's command with: run duel_gru_b1_2a;\n"
    "rem  --minutes 1440; the head's arguments. The start save given the head shut by tools/head2_init.py add --gate 0 --ctrl-src belief. H2_START: -1 = this process's start. The live dials come from the start save. Made by make_files.py.\n"
    "rem the repo root: this file lives in docs\\runs\\b1.2\\b1.2a\\")
open(os.path.join(HERE, "train.cmd"), "w", encoding="ascii", newline="").write(t.replace("\n", "\r\n"))
shutil.copy2(os.path.join(HERE, "..", "..", "b1.1", "b1.1a", "aim2_env.cmd"), os.path.join(HERE, "aim2_env.cmd"))
print("written")
