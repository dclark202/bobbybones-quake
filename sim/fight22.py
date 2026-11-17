"""2.2b, the simulators' side of the trainer's fight network (sim/train_duel_rnn.py --fight22; the workers import this, no torch here).

THE PAY SPLIT (docs/runs/2.2/2.2b/CARD.md change 8; the owner's word of 11-17 on the rest): each frame's pay (PAY_SPLIT=1: info["pay_terms"],
they sum to the frame's pay) in the parts each learner counts:
  ITEMS   the item picker (with the win part): the item flats and points, the big weapons' order, an item's loss, the decay, the stack terms
  FIGHT   the fight network (with the win part): damage dealt and taken, the far rails, frags and deaths, the near misses, the high ground
  WIN     both, each times its own scale (--win-scale-items, --win-scale-fight): the paid win chance (WIN_ADD x the judge with the items)
  OTHER   the hands only: every shaping pay (knowing where he is, watching the right spot, pre-aim, speed, jumps, the way to an item, ...)
The hands are paid the whole as ever. The groups are by the pay term's name; a term in none of the three named lists is OTHER."""
import numpy as np

ITEMS = ("item_MH", "item_RA", "item_YA", "item_flat_other", "big_order", "item_points", "item_loss", "items_other", "item_decay",
         "stack_diff", "stack_keep")
FIGHT = ("dmg_dealt", "dmg_taken", "rail", "frag", "death", "deaths_other", "near_miss", "high")
WIN = ("win_part", "win_pay")
COLS = ("items", "fight", "win", "other", "dealt", "taken", "near")


def groups(terms):
    """the pay terms' indices of each group -> dict"""
    t_ = list(terms)
    g_ = {k_: [t_.index(x_) for x_ in L_ if x_ in t_] for k_, L_ in (("items", ITEMS), ("fight", FIGHT), ("win", WIN))}
    named_ = set(sum(g_.values(), []))
    g_["other"] = [i_ for i_ in range(len(t_)) if i_ not in named_]
    for k_ in ("dmg_dealt", "dmg_taken", "near_miss"):
        g_[k_] = [t_.index(k_)] if k_ in t_ else []
    return g_


_G = {}


def pay_parts(E, info):
    """[n, 7] float32 of a frame: items, fight, win, other, then (readouts) damage dealt's pay, damage taken's, the near misses'"""
    pt_ = info.get("pay_terms")
    if pt_ is None:
        raise RuntimeError("--fight22: the simulator gives no pay terms (PAY_SPLIT=1)")
    key_ = tuple(E.PAY_TERMS)
    if key_ not in _G:
        _G[key_] = groups(key_)
    g_ = _G[key_]
    pt_ = np.asarray(pt_, np.float64)
    out_ = np.zeros((len(pt_), len(COLS)), np.float32)
    for j_, k_ in enumerate(("items", "fight", "win", "other", "dmg_dealt", "dmg_taken", "near_miss")):
        if g_[k_]:
            out_[:, j_] = pt_[:, g_[k_]].sum(1)
    return out_


PACK_F = ("Xh", "Xc", "Xs", "Xa")
PACK_B = ("vh", "vc", "vs", "va", "ia")


def pack(env):
    """the fight options' numbers of every seat after this step (env.fight_feat(): kept by the simulator for the coming readings), half
    precision, and the weapons he owns"""
    F = env.fight_feat()
    out = {k_: np.asarray(F[k_], np.float16) for k_ in PACK_F}
    out.update({k_: np.asarray(F[k_], bool) for k_ in PACK_B})
    out["Pc"] = np.asarray(F["Pc"], np.float16)
    out["has"] = np.asarray(env.has[:env.n], bool).copy()
    return out


def cat(packs):
    """the workers' packs of a step, one after the other (the trainer's seat order)"""
    return {k_: np.concatenate([p_[k_] for p_ in packs]) for k_ in packs[0]}


def reader_fx(env):
    """(the readers: sim/test_suite.py act(fx=), tools/duel_eval.py) the fight options' numbers of every seat after the frame before, as the
    trainer's rollout reads them (half precision, as they travel from its workers), and the fight option each seat is on"""
    F = env.fight_feat()
    out = {k_: np.asarray(np.asarray(F[k_], np.float16), np.float32) for k_ in PACK_F}
    out.update({k_: np.asarray(F[k_], bool) for k_ in PACK_B})
    out["fk"] = np.asarray(env.fgt_k[:env.n], np.int64).copy()
    return out
