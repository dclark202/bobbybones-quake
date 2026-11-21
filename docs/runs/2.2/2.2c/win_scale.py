"""2.2c (2.2b's, with 2.2c's pay split: FIGHT_SPLIT=22c; rule 14): the win scales and the pathology check on the start's games, with the judge
with the items as the paid win chance. Reads play22c.py pay files (the start file playing itself on every map, 2.2c's command and the start's
live.json: the contest pay, the rail chain, the near miss at 5, all at their start values), sums them, and writes win_scale_22c.json for start.ps1:
  k_items = max(1, sum|items| / sum|win|)    k_fight = max(1, sum|fight| / sum|win|)     (game frames of his seats; the win part as paid)
  the two judges' win part per frame (WIN_ADD x the change): mean and spread under the item-blind judge (2.2a's pay) and the judge with the items
  frags: the fragger's frag term <= 0, his whole pay <= 0, the win part <= 0 under either judge (sign flips); the victim's whole pay >= 0
  every pay term's sum, size, its minus and plus parts, and the learners that count it (sim/fight22.py's groups)
    python docs/runs/2.2/2.2c/win_scale.py <out json> <pay json> [<pay json> ...]"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "sim"))
os.environ["FIGHT_SPLIT"] = "22c"                             # (2.2c's groups: read at fight22's import)
import fight22 as F22  # noqa: E402

WHO = {"items": "the item picker (+ the hands)", "fight": "the fight network (the lever) (+ the hands)", "win": "the item picker x k_items, the fight network x k_fight (+ the hands)",
       "other": "the hands only"}


def main():
    out, files = sys.argv[1], sys.argv[2:]
    S = None
    for f_ in files:
        d = json.load(open(f_, encoding="utf-8"))
        if S is None:
            S = d
            S["margins"] = list(d["margins"])
            continue
        for k_, v_ in d.items():
            if k_ == "margins":
                S["margins"] += v_
            elif k_ == "terms":
                for t_, x_ in v_.items():
                    S["terms"][t_] = [a_ + b_ for a_, b_ in zip(S["terms"].get(t_, [0.0] * 4), x_)]
            elif k_ in ("contest", "rail_chain", "contest_burst", "odd"):
                if v_ is not None:
                    S[k_] = v_ if S.get(k_) is None else (__import__("numpy").asarray(S[k_]) + __import__("numpy").asarray(v_)).tolist()
            elif isinstance(v_, list):
                S[k_] = [a_ + b_ for a_, b_ in zip(S[k_], v_)]
            else:
                S[k_] += v_
    ki = max(1.0, S["abs_items"] / max(1e-12, S["abs_win"]))
    kf = max(1.0, S["abs_fight"] / max(1e-12, S["abs_win"]))

    def ms(t_):
        n_, s_, q_ = t_
        m_ = s_ / max(1, n_)
        return m_, math.sqrt(max(0.0, q_ / max(1, n_) - m_ * m_)), q_
    mb, sb, qb = ms(S["blind"])
    mh, sh, qh = ms(S["items_judge"])
    g_ = F22.groups(list(S["terms"]))
    grp = {t_: k_ for k_ in ("items", "fight", "win", "other") for t_ in [list(S["terms"])[i_] for i_ in g_[k_]]}
    ledger = [dict(term=t_, group=grp[t_], learners=WHO[grp[t_]], sum=x_[0], size=x_[1], minus=x_[2], plus=x_[3],
                   size_share=x_[1] / max(1e-12, sum(y_[1] for y_ in S["terms"].values())))
              for t_, x_ in sorted(S["terms"].items(), key=lambda kv: -kv[1][1])]
    mg = S["margins"]
    res = dict(k_items=round(ki, 4), k_fight=round(kf, 4), ratio_items_to_win=S["abs_items"] / max(1e-12, S["abs_win"]),
               ratio_fight_to_win=S["abs_fight"] / max(1e-12, S["abs_win"]), abs=dict(items=S["abs_items"], fight=S["abs_fight"], win=S["abs_win"],
               other=S["abs_other"]), frames=S["frames"],
               judges=dict(item_blind=dict(mean=mb, spread=sb, frames=S["blind"][0]), with_items=dict(mean=mh, spread=sh, frames=S["items_judge"][0]),
                           spread_ratio=sh / max(1e-12, sb)),
               frags=dict(n=S["frags"], frag_term_le0=S["frag_term_le0"], fragger_total_le0=S["frag_total_le0"], win_le0_items_judge=S["frag_win_le0"],
                          win_le0_blind_judge=S["frag_blind_le0"], victim_total_ge0=S["victim_total_ge0"]),
               margins=dict(n=len(mg), mean_abs=sum(abs(x_) for x_ in mg) / max(1, len(mg)), over_10=sum(1 for x_ in mg if abs(x_) >= 10),
                            note="the score of the games under way when the 4,000 frames (100 s) ended, not finished games"),
               ledger=ledger, files=files, contest=S.get("contest"), rail_chain=S.get("rail_chain"))
    json.dump(res, open(out, "w", encoding="utf-8"), indent=1)
    print(json.dumps({k_: v_ for k_, v_ in res.items() if k_ not in ("ledger", "files")}, indent=1))
    print("| term | group | counted by | sum | size | minus | plus | share of all pay's size |")
    print("|---|---|---|---|---|---|---|---|")
    for r_ in ledger:
        print("| {term} | {group} | {learners} | {sum:.4f} | {size:.4f} | {minus:.4f} | {plus:.4f} | {size_share:.4f} |".format(**r_))


if __name__ == "__main__":
    main()
