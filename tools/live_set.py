"""The safe restart's file: set settings of a running trainer for the games that begin next.

    python tools/live_set.py <run> NAME=VALUE [NAME=VALUE ...]   set or change these lines
    python tools/live_set.py <run> NAME=                          take a line out (its start value again)
    python tools/live_set.py <run> --clear                        an empty file: every setting at its start value
    python tools/live_set.py <run>                                show the file

Writes data/sim_runs/<run>/live_settings.env (or <run> as a folder path) in one step (a temporary file, then a rename),
keeps its other lines and comments, and prints what changed. The trainer (sim/train_duel_rnn.py, LS_SPEC) reads it between
two updates, checks the names and values and refuses the whole file on anything it can not take: see its log
("live_settings: ...") and <run>/live_settings.history.jsonl. Names read when a round or game begins (GAME_P, PRO_START_P,
JUMP_RUN_P, JUMP_W_*, ...) reach only the games that begin after that; the pays read every frame change for every game at
the next update, and no game is cut off.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    run, args = argv[0], argv[1:]
    d_ = run if os.path.isdir(run) else os.path.join(ROOT, "data", "sim_runs", run)
    if not os.path.isdir(d_):
        print("no run folder {}".format(d_))
        return 2
    path = os.path.join(d_, "live_settings.env")
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    if not args:
        print("{}:".format(path))
        print("\n".join(lines) if lines else "(no file: the run's start settings)")
        return 0
    clear = "--clear" in args
    sets = {}
    for x_ in args:
        if x_ == "--clear":
            continue
        if "=" not in x_:
            print("not NAME=VALUE: {!r}".format(x_))
            return 2
        k_, v_ = (t_.strip() for t_ in x_.split("=", 1))
        if not k_ or not all(c_.isupper() or c_.isdigit() or c_ == "_" for c_ in k_):
            print("not a setting's name: {!r}".format(k_))
            return 2
        sets[k_] = v_
    old = {}
    for l_ in lines:
        s_ = l_.strip()
        if s_ and not s_.startswith("#") and "=" in s_:
            k_, v_ = (t_.strip() for t_ in s_.split("=", 1))
            old[k_] = v_
    out, done = [], set()
    if not clear:
        for l_ in lines:
            s_ = l_.strip()
            k_ = s_.split("=", 1)[0].strip() if s_ and not s_.startswith("#") and "=" in s_ else None
            if k_ in sets:
                done.add(k_)
                if sets[k_]:
                    out.append("{}={}".format(k_, sets[k_]))
                continue                                     # (NAME= : the line goes)
            out.append(l_)
    else:
        out = [l_ for l_ in lines if l_.strip().startswith("#")]
    for k_, v_ in sets.items():
        if k_ not in done and v_:
            out.append("{}={}".format(k_, v_))
    new = {}
    for l_ in out:
        s_ = l_.strip()
        if s_ and not s_.startswith("#") and "=" in s_:
            k_, v_ = (t_.strip() for t_ in s_.split("=", 1))
            new[k_] = v_
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f_:
        f_.write("\n".join(out) + ("\n" if out else ""))
    os.replace(tmp, path)
    ch_ = sorted(set(old) | set(new))
    diff = ["  {}: {} -> {}".format(k_, old.get(k_, "(not in the file: the start value)"), new.get(k_, "(not in the file: the start value)"))
            for k_ in ch_ if old.get(k_) != new.get(k_)]
    print("{}: {}".format(path, "changed" if diff else "nothing changed"))
    for l_ in diff:
        print(l_)
    print("the trainer reads it before its next rollout (its log: 'live_settings: ...')")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
