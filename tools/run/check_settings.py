"""The settings check (a hard rule: CLAUDE.md). Compares a run's command with a reference command, and the command with a
checkpoint, and prints every difference; exits 1 on any difference not listed with --allow.

    python tools/run/check_settings.py docs/runs/v0.6.0/train.cmd --ref <the reference .cmd> [--allow --minutes,--brain-human]
    python tools/run/check_settings.py docs/runs/v0.6.0/train.cmd --ck data/sim_runs/duel_gru_v0_6_0/policy.pt

What is compared: every `set NAME=VALUE` (the environment the trainer starts with, files called with `call` included) and every
trainer argument (`--name value`). Paths are compared after the repo root (%ROOT% or an absolute checkout path) is taken out.
Against a checkpoint: each simulator setting it carries (env_vars) against the command's, and its aim delays (react_ms,
acquire_ms) against --react-ms / --acquire-ms. A setting the checkpoint carries that the command does not set is reported too."""
import argparse
import os
import re
import sys


def norm(v):
    v = v.strip().strip('"')
    v = re.sub(r"(?i)^%ROOT%\\", "", v)
    v = re.sub(r"(?i)C:\\Users\\[^\\]+\\ql-bot[^\\]*\\", "", v)
    return v


def read_cmd(path, seen=None):
    seen = seen or set()
    path = os.path.abspath(path)
    if path in seen:
        return {}, {}
    seen.add(path)
    txt = open(path).read().replace("\r\n", "\n")
    env, args = {}, {}
    here = os.path.dirname(path)
    for line in txt.split("\n"):
        line = line.strip()
        m = re.match(r"(?i)^call\s+(\S+\.cmd)", line)
        if m:
            p = m.group(1).replace("%~dp0", here + os.sep)
            if os.path.exists(p):
                e2, _ = read_cmd(p, seen)
                env.update(e2)
            continue
        m = re.match(r"(?i)^set ([A-Za-z0-9_]+)=(.*)$", line)
        if m:
            if m.group(1).upper() != "ROOT":                 # (the repo root itself: where the repo lives, not a setting)
                env[m.group(1)] = norm(m.group(2))
            continue
        if "train_duel_rnn.py" in line:
            toks = line.split()
            i = 0
            while i < len(toks):
                t = toks[i]
                if t.startswith("--"):
                    if i + 1 < len(toks) and not toks[i + 1].startswith("--") and not toks[i + 1].startswith(">"):
                        args[t] = norm(toks[i + 1])
                        i += 2
                        continue
                    args[t] = ""
                i += 1
    return env, args


def same(a, b):
    try:
        return float(a) == float(b)
    except ValueError:
        return a == b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--ref", default="")
    ap.add_argument("--ck", default="")
    ap.add_argument("--allow", default="", help="comma list of setting / argument names allowed to differ")
    a = ap.parse_args()
    allow = set(x for x in a.allow.split(",") if x)
    env, args = read_cmd(a.cmd)
    bad = 0
    if a.ref:
        e0, a0 = read_cmd(a.ref)
        for kind, x, y in (("set", env, e0), ("arg", args, a0)):
            for k in sorted(set(x) | set(y)):
                if k in y and k in x and same(x[k], y[k]):
                    continue
                tag = "allowed" if k in allow else "DIFF"
                bad += tag == "DIFF"
                print("{:7s} {} {}: run {!r} | reference {!r}".format(tag, kind, k, x.get(k, "<unset>"), y.get(k, "<unset>")))
    if a.ck:
        import torch
        ck = torch.load(a.ck, map_location="cpu", weights_only=False)
        for k, v in sorted((ck.get("env_vars") or {}).items()):
            if k in env and same(env[k], str(v)):
                continue
            tag = "allowed" if k in allow else "DIFF"
            bad += tag == "DIFF"
            print("{:7s} checkpoint {}: checkpoint {!r} | command {!r}".format(tag, k, str(v), env.get(k, "<unset>")))
        for k, arg in (("react_ms", "--react-ms"), ("acquire_ms", "--acquire-ms")):
            if ck.get(k) is not None and not same(str(ck[k]), args.get(arg, "nan")):
                bad += 1
                print("DIFF    checkpoint {}: {} | command {} {}".format(k, ck[k], arg, args.get(arg)))
    print("settings check:", "PASS" if bad == 0 else "{} difference(s) not allowed: FAIL".format(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
