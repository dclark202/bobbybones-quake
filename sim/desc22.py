"""2.2a (docs/runs/2.2/DESIGN.md; the owner's brief of 2026-11-16): THE OUTLOOK THAT SCORES A DESCRIPTION OF A PLAY ("desc").

One small feed-forward network applied to each of the 17 targets. It reads, as numbers (never a gradient back into the head, the brain, the
hands, the tracker or the map sense):
  the head's state (256)                 as the built outlook (sim/outlook.py) reads it
  the target's own numbers               "the description": what the simulator's order_feat() gives for the 17 targets on this line (DESC_OX=1:
                                         the order's map numbers loaded without COMBAT; sim/duel_env.py), the columns TGT_COLS: valid, what it is
                                         (nothing, an item, the enemy, a holding place), the way's seconds from him and from where he believes the
                                         enemy (t_me, t_en), the place's height, range and direction from him, its sight of where the brain puts the
                                         enemy 1, 2, 4 s ahead (sees_1/2/4), whether it sees him now (seen_me), the item's state and time as he
                                         knows it (item_up, item_back), the holding place's pro weight; and the MAP SENSE at that place against
                                         where the brain believes the enemy (sim/mapsense.py): dealt and taken in 5 s for the weapon in his hand
                                         and for each weapon class he owns (MS_N numbers)
  the situation                          order_feat()'s situation (CTX_COLS: contact, seconds since seen, his health and armor exact, the brain's
                                         places ok, how far and high the enemy's coming place is, the weapon in his hand), his weapons owned, the
                                         enemy's as the brain believes them (its readout's "own" part), ALL the tracker's outputs (sim/tracker.py:
                                         in control, the fight's odds, deaths and contact within, the enemy's health and armor as a range), the map
                                         sense where he stands, whether the brain places the enemy at all
Not read (not on this line): the brain's odds that the enemy passes a place (the order's pass_1/2/4: this line has no pass-odds readout).

Each new number is standardised by its MEASURED mean and spread (the layout's "norm": tools/out22_init.py, a sample of 2.1d's end playing
in the simulator), the tracker's chances by the measured base rate of their labels (a learnt output's spread is set by design: sqrt(p (1-p))),
then rounded to half precision at this one source (inputs()/np_inputs()), played and learnt alike.

The network (per sibling): a = l1s([head state, situation]); per target relu(a + l1t(target)); the goal-blind row relu(a) (the same network
without any description: its yardstick, knowing the situation as well); l2, ReLU; l3 to the kinds (as the built outlook's, sim/outlook.py
KINDS22) and the facts (sim/outlook.py FACTS); l3 at zero. Three siblings side by side, each with its own Adam: "desc" (everything),
"desc_nomap" (the map-sense numbers held at their mean: 0), "desc_notrk" (the tracker's held at 0). Its lesson is the built outlook's (every
keep reading of his on a held trip, the goal he is on; smooth L1 of the standardised kinds, the facts' logistic and smooth L1; goal and
goal-blind), scored before it is learnt from.

The term (when OUT_SRC = 1 and OUT_G > 0): "desc"'s picked kind, as the built outlook's (sim/outlook.py term()); made at each keep reading from
that reading's inputs and held to the next. Rule 11: the decay of l3 at H2_L2 from the first update.

Numpy at the top level (the game server imports this file); torch inside the torch functions.
"""
import os

import numpy as np

VERSION = 1
SEED = 2202
SIBS = ("desc", "desc_nomap", "desc_notrk")
TGT_COLS = ("valid", "k_none", "k_item", "k_enemy", "k_hold", "t_me", "t_en", "height", "range", "fwd", "left", "up", "sees_1", "sees_2",
            "sees_4", "seen_me", "item_up", "item_back", "pro_hold")
CTX_COLS = ("contact", "seen_ago", "health", "armor", "ahead_ok", "belief_ok", "ahead_range", "ahead_height", "w_rl", "w_lg", "w_rg", "w_other")
WEAPONS = ("rocket launcher", "railgun", "lightning gun", "machine gun", "shotgun", "grenade launcher", "plasma gun", "heavy machine gun", "gauntlet")
EN_OWN = ("rl", "rg", "lg", "pg", "gl", "sg")                 # (sim/track.py OWN: the readout's "own" part, columns 21 .. 27)
TRK_OWN = slice(21, 27)
MS_NAMES = ("hand_dealt", "hand_taken", "rockets_dealt", "rockets_taken", "rail_dealt", "rail_taken", "lightning_dealt", "lightning_taken",
            "other_dealt", "other_taken")
MS_N = len(MS_NAMES)
OTHER_W = 3                                                   # ("other": the weapon in his hand if it is one, else the machine gun)
N_T = 17
CMB_VALID = 8                                                 # (order_feat()'s column "valid": sim/duel_env.py CMB_FEAT)
IN_CLIP = 10.0                                                # (every standardised new input clipped to +- this before the half-precision rounding)


def sit_names():
    import tracker as tracker_
    return (["ctx " + c_ for c_ in CTX_COLS] + ["owns " + w_ for w_ in WEAPONS] + ["enemy owns " + w_ for w_ in EN_OWN]
            + ["trk " + o_ for o_ in tracker_.OUTS] + ["map sense here " + m_ for m_ in MS_NAMES] + ["brain places the enemy"])


def tgt_names():
    return list(TGT_COLS) + ["map sense " + m_ for m_ in MS_NAMES]


def groups():
    """the columns of the situation and of a target that are the map sense's and the tracker's"""
    sn, tn = sit_names(), tgt_names()
    return dict(sit_map=[i_ for i_, n_ in enumerate(sn) if n_.startswith("map sense")], tgt_map=[i_ for i_, n_ in enumerate(tn) if n_.startswith("map sense")],
                sit_trk=[i_ for i_, n_ in enumerate(sn) if n_.startswith("trk ")])


def layout(kinds, facts, head=256, n_target=N_T, hid=128, clip=5.0, norm=None, cmb_feat=None, cmb_ctx=None):
    sn, tn = sit_names(), tgt_names()
    g_ = groups()
    masks = dict(desc=dict(sit=[], tgt=[]), desc_nomap=dict(sit=g_["sit_map"], tgt=g_["tgt_map"]), desc_notrk=dict(sit=g_["sit_trk"], tgt=[]))
    L = dict(version=VERSION, head=int(head), n_target=int(n_target), kinds=list(kinds), facts=list(facts), hid=int(hid), clip=float(clip),
             sit=sn, tgt=tn, sibs=list(SIBS), masks=masks, plays="desc",
             tgt_idx=[list(cmb_feat).index(c_) for c_ in TGT_COLS] if cmb_feat is not None else None,
             ctx_idx=[list(cmb_ctx).index(c_) for c_ in CTX_COLS] if cmb_ctx is not None else None)
    L["norm"] = norm if norm is not None else dict(sit_mean=[0.0] * len(sn), sit_sd=[1.0] * len(sn), tgt_mean=[0.0] * len(tn), tgt_sd=[1.0] * len(tn),
                                                    measured=False)
    return L


def make_module(L):
    """the siblings as a ModuleDict by name (head2.dsc.<name>.*), each from a random stream of its own, l3 at zero"""
    import torch
    import torch.nn as nn
    assert int(L.get("version", 0)) == VERSION, "desc22: layout version {} expected".format(VERSION)
    S_, D_, H_, K_ = len(L["sit"]), len(L["tgt"]), int(L["hid"]), len(L["kinds"]) + len(L["facts"])

    class Desc(nn.Module):
        def __init__(self, seed):
            super().__init__()
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(int(seed))
                self.l1s = nn.Linear(int(L["head"]) + S_, H_)
                self.l1t = nn.Linear(D_, H_, bias=False)
                self.l2 = nn.Linear(H_, H_)
                self.l3 = nn.Linear(H_, K_)
            with torch.no_grad():
                self.l3.weight.zero_()
                self.l3.bias.zero_()
            self.nk = len(L["kinds"])

        def forward(self, s, sit, tgt):
            """s [B, head], sit [B, S], tgt [B, NT, D] (normalised, masked) -> (kinds [B, K, NT + 1], facts [B, F, NT + 1]); the last: goal-blind"""
            a = self.l1s(torch.cat([s.float(), sit.float()], 1))
            h = torch.relu(torch.cat([a[:, None, :] + self.l1t(tgt.float()), a[:, None, :]], 1))
            y = self.l3(torch.relu(self.l2(h))).transpose(1, 2)
            return y[:, :self.nk], y[:, self.nk:]
    return nn.ModuleDict({nm_: Desc(SEED + k_) for k_, nm_ in enumerate(L["sibs"])})


# ------------------------------------------------------------------------------------------------------------------ the inputs (numpy: every reader)
def ms_numbers(fwd, msL, tables, seat_map, places, pok, bel, bok, wme, wen, has):
    """the map sense at places [n, m, 3] (pok [n, m]: which are there) against where the brain believes the enemy (bel [n, 3], bok [n]):
    dealt and taken (hundreds) for the weapon in his hand (wme [n]) and for each class he owns (has [n, 9]: rockets, rail, lightning; "other":
    his weapon in hand if it is one, else the machine gun; a class not owned: 0); the enemy's weapon as the brain believes it (wen [n]); "standing
    there" (the seed "moved" 0). fwd(x [K, inp], row [K] or None) -> [K, 8] (sim/mapsense.py np_forward or torch_fwd). -> [n, m, MS_N]
    float32 (0 without a belief, a place or a table)"""
    import mapsense as ms_
    places = np.asarray(places, np.float32)
    n, m = places.shape[:2]
    out = np.zeros((n, m, MS_N), np.float32)
    ok = np.asarray(pok, bool) & np.asarray(bok, bool)[:, None]
    if not ok.any() or msL is None:
        return out
    wme = np.asarray(wme, np.int64)
    has = np.asarray(has, bool)
    sm = np.asarray(seat_map)
    oth = np.where(ms_.cls_of(wme) == 3, wme, OTHER_W)
    for mp, S in tables.items():
        r, c = np.nonzero(ok & (sm == mp)[:, None])
        if not len(r) or mp not in msL["maps"]:
            continue
        pos, e = places[r, c], np.asarray(bel, np.float32)[r]
        i, j = S.at(pos), S.at(e)
        F = ms_.feats(S, i, j, pos, e, wme[r], np.asarray(wen, np.int64)[r], np.zeros(len(r), np.float32))
        row = int(msL["maps"][mp]["off"]) + i.astype(np.int64)
        ws = [wme[r], np.zeros(len(r), np.int64), np.ones(len(r), np.int64), np.full(len(r), 2, np.int64), oth[r]]
        X = np.concatenate([ms_.encode(np.concatenate([F[:, :13], w_[:, None].astype(np.float32), F[:, 14:15]], 1)) for w_ in ws])
        Y = np.asarray(fwd(X, np.concatenate([row] * len(ws))), np.float32).reshape(len(ws), len(r), 2, 4)
        cl = [ms_.cls_of(w_) for w_ in ws]
        ar = np.arange(len(r))
        own = [np.ones(len(r), bool), has[r, 0], has[r, 1], has[r, 2], np.ones(len(r), bool)]
        for v_ in range(len(ws)):
            out[r, c, 2 * v_] = Y[v_, ar, 0, cl[v_]] * own[v_]
            out[r, c, 2 * v_ + 1] = Y[v_, ar, 1, cl[v_]] * own[v_]
    return out


def raw_inputs(L, oxX, oxC, oxP, has, wpn, en_own, trk_read, tok_P, tok_ok, tok_hand, ms_fwd, msL, tables, seat_map):
    """the raw (unscaled) inputs of every seat at a keep reading -> (sit [n, S], tgt [n, NT, D]). oxX, oxC, oxP: order_feat()'s target rows
    [n, >= NT, CMB_F], situation [n, CMB_CTX], places [n, >= NT, 3]; has [n, 9] his weapons, wpn [n] the weapon in his hand; en_own [n, 6] the
    brain's chances of the enemy's weapons; trk_read [n, 18] the tracker's readable outputs; tok_P [n, 3], tok_ok [n], tok_hand [n] the brain's
    place of the enemy and his weapon in hand (sim/btoken.py Token: P, valid, hand.argmax)"""
    NT = int(L["n_target"])
    X = np.asarray(oxX, np.float32)[:, :NT][..., np.asarray(L["tgt_idx"], np.int64)]
    C = np.asarray(oxC, np.float32)[:, np.asarray(L["ctx_idx"], np.int64)]
    Pl = np.asarray(oxP, np.float32)[:, :NT]
    valid = X[..., TGT_COLS.index("valid")] > 0.5
    n = len(X)
    ms_t = ms_numbers(ms_fwd, msL, tables, seat_map, Pl, valid, tok_P, tok_ok, wpn, tok_hand, has)
    ms_h = ms_numbers(ms_fwd, msL, tables, seat_map, Pl[:, :1], np.ones((n, 1), bool), tok_P, tok_ok, wpn, tok_hand, has)[:, 0]
    sit = np.concatenate([C, np.asarray(has, np.float32)[:, :len(WEAPONS)], np.asarray(en_own, np.float32), np.asarray(trk_read, np.float32), ms_h,
                          np.asarray(tok_ok, np.float32)[:, None]], 1)
    tgt = np.concatenate([X, ms_t], 2)
    return sit.astype(np.float32), tgt.astype(np.float32)


def np_inputs(L, sit_raw, tgt_raw):
    """standardised by the layout's measured norm, clipped to +- IN_CLIP, rounded to half precision (the one source; the masks are the
    siblings')"""
    N_ = L["norm"]
    sit = (np.asarray(sit_raw, np.float32) - np.asarray(N_["sit_mean"], np.float32)) / np.asarray(N_["sit_sd"], np.float32)
    tgt = (np.asarray(tgt_raw, np.float32) - np.asarray(N_["tgt_mean"], np.float32)) / np.asarray(N_["tgt_sd"], np.float32)
    c_ = np.float32(IN_CLIP)
    return np.clip(sit, -c_, c_).astype(np.float16).astype(np.float32), np.clip(tgt, -c_, c_).astype(np.float16).astype(np.float32)


def inputs(L, sit_raw, tgt_raw):
    """np_inputs in torch (the same arithmetic in float32, the same rounding)"""
    import torch
    N_ = L["norm"]
    d_ = sit_raw.device
    sit = (sit_raw.float() - torch.as_tensor(N_["sit_mean"], dtype=torch.float32, device=d_)) / torch.as_tensor(N_["sit_sd"], dtype=torch.float32, device=d_)
    tgt = (tgt_raw.float() - torch.as_tensor(N_["tgt_mean"], dtype=torch.float32, device=d_)) / torch.as_tensor(N_["tgt_sd"], dtype=torch.float32, device=d_)
    return sit.clamp(-IN_CLIP, IN_CLIP).half().float(), tgt.clamp(-IN_CLIP, IN_CLIP).half().float()


def masked(L, sib, sit, tgt):
    """a sibling's view: its group of columns held at 0 (their mean)"""
    m_ = L["masks"][sib]
    if not m_["sit"] and not m_["tgt"]:
        return sit, tgt
    sit, tgt = sit.clone() if hasattr(sit, "clone") else sit.copy(), tgt.clone() if hasattr(tgt, "clone") else tgt.copy()
    if m_["sit"]:
        sit[:, m_["sit"]] = 0.0
    if m_["tgt"]:
        tgt[..., m_["tgt"]] = 0.0
    return sit, tgt


def forward(mods, L, sib, s, sit, tgt):
    """a sibling's (kinds, facts) on torch rows (no gradient handling here: the caller's)"""
    si_, tg_ = masked(L, sib, sit, tgt)
    return mods[sib](s, si_, tg_)


def np_params(W, sib="desc", prefix="dsc."):
    ks = ("l1s.weight", "l1s.bias", "l1t.weight", "l2.weight", "l2.bias", "l3.weight", "l3.bias")
    if not all(prefix + sib + "." + k_ in W for k_ in ks):
        return None
    return tuple(np.asarray(W[prefix + sib + "." + k_], np.float32) for k_ in ks)


def np_forward(PW, L, s, sit, tgt, sib="desc"):
    """forward() in numpy -> (kinds [B, K, NT + 1], facts [B, F, NT + 1])"""
    sit, tgt = masked(L, sib, np.asarray(sit, np.float32), np.asarray(tgt, np.float32))
    a = np.concatenate([np.asarray(s, np.float32)[:, :int(L["head"])], sit], 1) @ PW[0].T + PW[1]
    h = np.maximum(np.concatenate([a[:, None, :] + tgt @ PW[2].T, a[:, None, :]], 1), 0.0)
    y = (np.maximum(h @ PW[3].T + PW[4], 0.0) @ PW[5].T + PW[6]).transpose(0, 2, 1)
    nk = len(L["kinds"])
    return y[:, :nk].astype(np.float32), y[:, nk:].astype(np.float32)


def np_term(PW, L, s, sit, tgt, g, pick):
    """the term on the target's logits [B, NT] (float32 holding half-precision numbers): g x clip(the picked kind's outlook - its mean over the
    targets) (sim/outlook.py np_term)"""
    import outlook as outlook_
    o_, _ = np_forward(PW, L, s, sit, tgt)
    return outlook_.np_term(o_[:, int(pick)], g, float(L["clip"]))


def term(mods, L, s, sit, tgt, g, pick, nonfinite=None):
    """(nonfinite: a list whose first number counts the seats whose outlook is not finite: their term is 0)"""
    import torch
    import outlook as outlook_
    with torch.no_grad():
        o_, _ = forward(mods, L, "desc", s, sit, tgt)
        if nonfinite is not None:
            nonfinite[0] += outlook_.nonfinite_rows(o_[:, int(pick)])
        return outlook_.term(o_[:, int(pick)], g, float(L["clip"]))


def need_om(env):
    """(the review of 2026-11-16) the description needs the order's map numbers in the simulator: raise when they are missing"""
    if getattr(env, "om", None) is None:
        raise RuntimeError("2.2a: the description of the targets is asked of a simulator without the order's map numbers (DESC_OX=1 not set when "
                           "the module was imported, or no sim/order_maps/<map>.npz): it would read all zeros; refused")


def check_blank(X):
    """(the readers and the trainer) a description whose target 'nothing' is not valid on some seat is blank (order_feat() without the map's
    numbers gives zeros): raise"""
    v_ = np.asarray(X)[:, 0, CMB_VALID]
    if not bool((np.asarray(v_, np.float32) > 0.5).all()):
        raise RuntimeError("2.2a: a blank description (the target 'nothing' not valid on {} of {} seats): the simulator gives no map numbers "
                           "(DESC_OX?); refused".format(int((np.asarray(v_, np.float32) <= 0.5).sum()), len(v_)))


# ------------------------------------------------------------------------------------------------------------------ the readers' tick
class NpState:
    """a reader's per-seat numbers between keep readings: the desc term made at the last keep reading (held, as the trainer holds it)"""

    def __init__(self, n, nt=N_T):
        self.term = np.zeros((n, nt), np.float32)

    def grow(self, n):
        if len(self.term) < n:
            self.term = np.concatenate([self.term, np.zeros((n - len(self.term), self.term.shape[1]), np.float32)])


def env_ox(env, rows=N_T):
    """the simulator's numbers the description reads at a keep reading, for these seats (after the frame before): order_feat()'s targets'
    rows, situation and places (the first `rows` rows), the weapons he owns, the weapon in his hand. -> a tuple (X, C, P, has, weapon).
    A simulator without the order's map numbers (DESC_OX unset, or no sim/order_maps/<map>.npz) cannot give it: RAISES (never zeros)"""
    need_om(env)
    X, C, P = env.order_feat()
    n = env.n
    return (np.asarray(X)[:, :rows].astype(np.float16), np.asarray(C).astype(np.float16), np.asarray(P)[:, :rows].astype(np.float16),
            np.asarray(env.has[:n, :len(WEAPONS)], bool).copy(), np.asarray(env.weapon[:n], np.int64).copy())


class NpDesc:
    """(the readers: sim/test_suite.py, plugins/netpass.py) the desc term in numpy, as the trainer makes it at a keep reading: the tracker on the
    brain's state and his inputs of the frame, the brain's chances of the enemy's weapons, the map sense (the file's own, its tables from
    <root>/data/maps/space_<map>.npz) at each target's place and his own, the description, the term. W: the head's weights (prefix "head2."
    stripped), L: the head's layout, ms: the checkpoint's "map_sense" (layout, weights as arrays) or None"""

    def __init__(self, W, L, ms=None, root=None):
        import os
        import tracker as tracker_
        self.L, self.TL, self.DL = L, L["trk22"], L["desc22"]
        self.trkW = tracker_.np_params(W)
        self.dscW = np_params(W, "desc")
        assert self.trkW is not None and self.dscW is not None, "the layout names 2.2a's parts and the weights are not there"
        self.src = int(round(float(np.asarray(W.get("out_src", 0.0)))))
        self.msL = ms["layout"] if ms else None
        self.msP = {k_: np.asarray(v_, np.float32) for k_, v_ in ms["model"].items()} if ms else None
        self.root = root or os.environ.get("QLBOT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.tabs = {}
        self.st = NpState(0)

    def tables(self, maps):
        import mapsense as ms_
        for mp_ in set(str(m_) for m_ in maps):
            if mp_ not in self.tabs:
                self.tabs[mp_] = ms_.load_tables(self.root, [mp_])[0].get(mp_)
        return {m_: t_ for m_, t_ in self.tabs.items() if t_ is not None}

    def inputs_rows(self, brain_s, xa, tokP, tokok, tokhand, trk_brain, ox, maps):
        """the normalised inputs of these rows (sit [r, S], tgt [r, NT, D]) and the tracker's readable outputs"""
        import tracker as tracker_
        import mapsense as ms_
        trr_ = tracker_.np_readable(tracker_.np_forward(self.trkW, tracker_.np_inp(self.TL, brain_s, xa)))
        eo_ = 1.0 / (1.0 + np.exp(-np.asarray(trk_brain, np.float32)[:, TRK_OWN]))
        fwd_ = (lambda x_, row_: ms_.np_forward(self.msP, x_, row_)) if self.msP is not None else None
        sr_, tr_ = raw_inputs(self.DL, ox[0], ox[1], ox[2], ox[3], ox[4], eo_, trr_, tokP, tokok, tokhand, fwd_, self.msL,
                              self.tables(maps) if self.msL is not None else {}, np.asarray(maps))
        si_, tg_ = np_inputs(self.DL, sr_, tr_)
        self.last_raw = (sr_, tr_)
        return si_, tg_, trr_

    def reading(self, rows, h2s_rows, brain_s, xa, tokP, tokok, tokhand, trk_brain, ox, maps, g, pick, n):
        """at a keep reading of rows (indices of n seats): the held term of those rows made anew"""
        self.st.grow(n)
        check_blank(ox[0])
        si_, tg_, _ = self.inputs_rows(brain_s, xa, tokP, tokok, tokhand, trk_brain, ox, maps)
        t_ = np_term(self.dscW, self.DL, h2s_rows, si_, tg_, g, pick)
        bad_ = ~np.isfinite(t_).all(1)                       # (a non-finite outlook: no term for that seat, counted, loud)
        if bad_.any():
            self.nonfinite = getattr(self, "nonfinite", 0) + int(bad_.sum())
            print("MAJOR PROBLEM: the desc term is not finite on {} seats (counted {}): 0 for them".format(int(bad_.sum()), self.nonfinite), flush=True)
            t_[bad_] = 0.0
        self.st.term[rows] = t_
        tp_ = os.environ.get("DESC22_TRACE")                 # (a test's trace: the first readings' raw inputs, head states and terms, by process)
        if tp_ and getattr(self, "n_trace", 0) < 20:
            self.n_trace = getattr(self, "n_trace", 0) + 1
            self.trace = getattr(self, "trace", []) + [(np.asarray(h2s_rows, np.float32), self.last_raw[0], self.last_raw[1], t_.copy(), float(g),
                                                        int(pick), np.asarray(ox[0], np.float32)[:, :, CMB_VALID])]
            np.savez(tp_ + "_{}.npz".format(os.getpid()), **{"{}_{}".format(k_, i_): v_ for i_, r_ in enumerate(self.trace)
                                                             for k_, v_ in zip(("h", "sit", "tgt", "term", "g", "pick", "valid"), r_)})

    def term(self, n):
        self.st.grow(n)
        return self.st.term[:n]
