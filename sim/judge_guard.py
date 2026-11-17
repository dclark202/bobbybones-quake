"""2.2b's guard (the owner, 11-17: "whatever you need to do to fix it so that this doesn't happen again"): no new run pays its win chance with the
judge that does not see the items. A command (its environment; and the run's live.json, whose WIN_ADD / WIN_W may switch the pay on) whose
win-chance pay is on (WIN_ADD or WIN_W above 0) must have the paid win part read the judge with the items:

    JUDGE_PAY=1                            the simulator pays the judge with the items (sim/duel_env.py; off: the item-blind judge, wb_raw)
    WIN_JUDGE=<the judge>                  the judge itself (it must exist)
    JUDGE_ITEMS=<items json>               its items' part, an ACCEPTED fit (tools/run/fit_items.py: "accepted": true)

Otherwise the command is refused (sim/train_duel_rnn.py at its start, tools/run/check_settings.py, tools/run/make_train_cmd.py), unless it
carries the trainer's --old-judge-replay 1 (a replay or an evaluation of an older run's command; the checks' players and duel_eval do not pay
and are not touched)."""
import json
import os

WIN_NAMES = ("WIN_ADD", "WIN_W")
FIX = ("set JUDGE_PAY=1, WIN_JUDGE=<the judge> and JUDGE_ITEMS=<an accepted fit of tools/run/fit_items.py> (the judge with the items), or give "
       "the trainer --old-judge-replay 1 to replay an older run's command")


def _f(x):
    try:
        return float(str(x).strip() or 0.0)
    except ValueError:
        return 0.0


def check(env, live=None, root=None):
    """env: the command's environment {name: value}; live: the run's live.json (its WIN_ADD, WIN_W override) or None; root: where relative
    paths are -> (ok, why)"""
    v = {k_: env.get(k_) for k_ in ("WIN_ADD", "WIN_W", "JUDGE_PAY", "WIN_JUDGE", "JUDGE_ITEMS")}
    for k_ in WIN_NAMES:
        if live and live.get(k_) not in (None, ""):
            v[k_] = live[k_]
    if not any(_f(v.get(k_)) > 0 for k_ in WIN_NAMES):
        return True, "no win-chance pay (WIN_ADD and WIN_W at 0)"
    prob = []
    if _f(v.get("JUDGE_PAY")) <= 0:
        prob.append("JUDGE_PAY is not 1: the paid win part would be the item-blind judge's")

    def path_(p_):
        p_ = str(p_).strip().strip('"')
        for pre_ in ("%ROOT%\\", "%ROOT%/"):
            if p_.upper().startswith(pre_.upper()):
                p_ = p_[len(pre_):]
        return p_ if os.path.isabs(p_) or root is None else os.path.join(root, p_)
    if not v.get("WIN_JUDGE"):
        prob.append("no WIN_JUDGE")
    elif not os.path.exists(path_(v["WIN_JUDGE"])):
        prob.append("WIN_JUDGE {} does not exist".format(v["WIN_JUDGE"]))
    if not v.get("JUDGE_ITEMS"):
        prob.append("no JUDGE_ITEMS")
    else:
        p_ = path_(v["JUDGE_ITEMS"])
        if not os.path.exists(p_):
            prob.append("JUDGE_ITEMS {} does not exist".format(v["JUDGE_ITEMS"]))
        else:
            try:
                acc_ = json.load(open(p_, encoding="utf-8")).get("accepted") is True
            except (OSError, ValueError):
                acc_ = False
            if not acc_:
                prob.append("JUDGE_ITEMS {} is not an accepted fit".format(v["JUDGE_ITEMS"]))
    if prob:
        return False, "the win-chance pay is on (WIN_ADD {}, WIN_W {}) but {}: {}".format(v.get("WIN_ADD"), v.get("WIN_W"), "; ".join(prob), FIX)
    return True, "the win-chance pay reads the judge with the items ({})".format(v["JUDGE_ITEMS"])
