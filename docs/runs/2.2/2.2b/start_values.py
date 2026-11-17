"""2.2b: the command's start values against the start's live.json, name by name (the coordinator's audit of 11-17: a refused live file must not
bring back what an older command still had written). For every name of the live file: the value the trainer starts with from the command
alone (the simulator's names: the command's environment as the simulator's import works it out, sim/duel_env.py live_values; the trainer's:
its argument, or the factor's own start), and the live file's. Refuses (exit 1) on any name that differs, or that it cannot map.
    python docs/runs/2.2/2.2b/start_values.py <train.cmd> <live.json> [--table]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(ROOT, "tools", "run"))
import check_settings as CS  # noqa: E402

# the trainer's live names: (its argument, how the start is made): "arg" the argument's value; "eff" the argument x a factor starting at 1 (an
# argument of 0 makes the live factor play nothing); a number: the factor's own start (no argument); "off:<arg>" not read when the argument is 0
TRAINER = {"DMG_TAKEN_W": ("--dmg-taken-w", "arg"), "DMG_REWARD": ("--dmg-reward", "arg"), "HELD_G": ("--held-g", "arg"), "PULL_G": ("--pull-g", "arg"),
           "H2_GATE_CAP": ("--head2-cap", "arg"), "H2_GATE_OPEN": ("--head2-open", "arg"), "H2_PG": (None, 1.0), "H2_WPG": ("--head2-wpg", "arg"),
           "HABIT_P": ("--habit-p", "arg"), "BTOK_GATE_CAP": ("--btoken-cap", "arg"), "FADE_CAP": ("--rule-fade-cap", "arg"),
           "INTENT_TEACH_W": ("--intent-teach", "eff"), "RJ_TEACH_W": ("--rj-teach", "eff"), "H2_COPY": ("--head2-copy", "eff"),
           "BRAIN_FADE": ("--brain-fade", "off"), "VALUE_WARM": ("--value-warm", "arg"), "H2_MIX": (None, 0.0),
           "FGT_G": ("--fgt-g", "arg"), "FGT_W": ("--fgt-w", "arg"), "PRACTICE_P": ("--practice-p", "arg"), "H2_WADD": ("--h2-wadd", "arg"),
           "FGT_GATE": ("--fgt-gate", "arg")}
DEFAULTS = {"--head2-cap": 1.0, "--head2-open": 0.0, "--btoken-cap": 1.0, "--rule-fade-cap": 1.0, "--value-warm": 0.0, "--head2-copy": 0.0,
            "--rj-teach": 0.0, "--intent-teach": 0.0, "--brain-fade": 0.0}


def main():
    cmd, livep = sys.argv[1], sys.argv[2]
    env, args = CS.read_cmd(cmd)
    live = json.load(open(livep, encoding="utf-8"))
    os.environ.update({k_: v_.replace("%ROOT%", ROOT) for k_, v_ in env.items()})
    sys.path.insert(0, os.path.join(ROOT, "sim"))
    import duel_env as E
    sim_cmd = E.live_values(lambda k_: env.get(k_))
    rows, bad = [], 0
    for k_ in sorted(live):
        lv_ = live[k_]
        if k_ in E.LIVE_VARS:
            sim_live = E.live_values(lambda n_: (str(live[n_]) if n_ in live else env.get(n_)))
            c_, l_ = sim_cmd[k_], sim_live[k_]
            ok_ = (c_ == l_) if not isinstance(c_, float) else abs(float(c_) - float(l_)) < 1e-9
            rows.append((k_, "simulator", env.get(k_, "<unset: {}>".format(c_)), lv_, ok_))
        elif k_ in TRAINER:
            a_, how_ = TRAINER[k_]
            if a_ is None:
                c_ = float(how_)
                ok_ = abs(c_ - float(lv_)) < 1e-9
                rows.append((k_, "trainer (its own start)", c_, lv_, ok_))
            else:
                av_ = float(args[a_]) if a_ in args and args[a_] != "" else float(DEFAULTS.get(a_, float("nan")))
                if how_ == "arg":
                    ok_ = abs(av_ - float(lv_)) < 1e-9
                    rows.append((k_, "trainer " + a_, av_, lv_, ok_))
                elif how_ == "eff":
                    ok_ = abs(av_ * 1.0 - av_ * float(lv_)) < 1e-9
                    rows.append((k_, "trainer {} x the factor (the command's start: {} x 1)".format(a_, av_), av_ * 1.0, av_ * float(lv_), ok_))
                else:
                    ok_ = av_ == 0.0
                    rows.append((k_, "trainer: not read ({} 0)".format(a_), "not read", lv_, ok_))
        else:
            rows.append((k_, "NOT MAPPED", None, lv_, False))
        bad += not rows[-1][4]
    for r_ in rows:
        print("{:4s} {:18s} {:58s} command {!r:>34} | live {!r}".format("ok" if r_[4] else "DIFF", r_[0], r_[1], r_[2], r_[3]))
    print("start values:", "PASS: the command's start values are the live file's, name by name ({} names)".format(len(rows)) if not bad else
          "{} name(s) differ or are not mapped: FAIL".format(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
