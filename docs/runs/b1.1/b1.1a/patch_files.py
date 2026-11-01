"""b1.1a's edits (owner, 2026-10-31, the card's plan: the brain, the pull, the lock), applied once: INTENT_HOLD a live name; the panel plays a save at its own lock; ramp_live's list of values; the ramp, smoke run, start and command.
    python docs/runs/b1.1/b1.1a/patch_files.py"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))


def rep(p, *pairs):
    p = os.path.join(ROOT, p)
    t = open(p, encoding="utf-8", newline="").read()
    for a, b in pairs:
        assert t.count(a) >= 1, (p, a[:70])
        t = t.replace(a, b)
    open(p, "w", encoding="utf-8", newline="").write(t)


rep("sim/duel_env.py",
    ('             "LEVEL_PULL",                                                                                          # (v0.4.3, B-275)\n',
     '             "LEVEL_PULL",                                                                                          # (v0.4.3, B-275)\n'
     '             "INTENT_HOLD",                                                                                         # (b1.1a, owner 2026-10-31: the target lock faded, a PLAY_VAR too)\n'),
    ('    bap_ = get("BLIND_AHEAD_P")',
     '    ih_ = get("INTENT_HOLD")                                 # (b1.1a) how long a target choice holds, seconds, live; unset: 3 (read each frame by intend())\n'
     '    v["INTENT_HOLD"] = float(ih_) if (ih_ or "").strip() else 3.0\n'
     '    if not 0.0 <= v["INTENT_HOLD"] <= 60.0:\n'
     '        raise ValueError("INTENT_HOLD must be within 0 .. 60")\n'
     '    bap_ = get("BLIND_AHEAD_P")'))
rep("tools/run/panel.py",
    ('    if lv_ is not None:\n        S_["LEVEL_PULL"] = lv_\n',
     '    if lv_ is not None:\n        S_["LEVEL_PULL"] = lv_\n'
     '    if pol:                                                  # (b1.1a, the target lock\'s fade: the save\'s own; both seats alike)\n'
     '        import torch\n'
     '        ih_ = (torch.load(pol, map_location="cpu", weights_only=False).get("env_vars") or {}).get("INTENT_HOLD")\n'
     '        if ih_ not in (None, ""):\n'
     '            S_["INTENT_HOLD"] = str(ih_)\n'))
rep("tools/run/ramp_live.py",
    ('    ap.add_argument("--hold-at", type=float',
     '    ap.add_argument("--values", default="", help="(b1.1) the steps\' values, comma-separated, in place of a fixed STEP (the last must be TO)")\n'
     '    ap.add_argument("--hold-at", type=float'),
    ('        v = round(v + sign * a.step, 6)\n        v = a.to if sign * (v - a.to) > 0 else v\n',
     '        if SEQ:\n            v = SEQ.pop(0)\n        else:\n            v = round(v + sign * a.step, 6)\n            v = a.to if sign * (v - a.to) > 0 else v\n'),
    ('    saves, t_last = 0, 0.0\n', '    saves, t_last = 0, 0.0\n    SEQ = [float(x) for x in a.values.split(",")] if a.values else []\n'))
rep("docs/runs/b1.1/b1.1a/ramp_b11.py",
    ('''"""b1.1a's schedule (owner, 2026-10-31): shut to update 10; the pull toward level out (LEVEL_PULL 0.95 -> 1, eight steps, one right after each save, ~5.3 h); held to update
110; the brain's old belief out (BRAIN_FADE 0 -> 1, eight steps, the same way).''',
     '''"""b1.1a's schedule (owner, 2026-10-31; the card): shut to update 10; the brain's old belief out (BRAIN_FADE 0 -> 1, seven steps, one right after each save, ~4.5 h); held to update 90; the pull toward level
out (LEVEL_PULL 0.95 -> 1, three steps, ~2 h); held to update 130; the target lock out (INTENT_HOLD 8 -> 4 -> 2 -> 1 s, ~2 h).'''),
    ('[--shut N] [--hold-to N] [--steps N]', '[--shut N] [--hold-pull N] [--hold-lock N] [--brain-steps N] [--pull-steps N]'),
    ('import json\nimport os\n', 'import json\nimport math\nimport os\n'),
    ('ap.add_argument("--hold-to", type=int, default=110)\n    ap.add_argument("--steps", type=int, default=8)',
     'ap.add_argument("--hold-pull", type=int, default=90)\n    ap.add_argument("--hold-lock", type=int, default=130)\n    ap.add_argument("--brain-steps", type=int, default=7)\n    ap.add_argument("--pull-steps", type=int, default=3)'),
    ('def fade(name, frm, to, keep):', 'def fade(name, frm, to, step, keep, *more):'),
    ('str(round((to - frm) / a.steps, 6)), "--keep-as", keep,', 'str(step), "--keep-as", keep,'),
    ('"--dir", D], cwd=ROOT)', '"--dir", D] + list(more), cwd=ROOT)'),
    ('''    fade("LEVEL_PULL", 0.95, 1.0, "policy_prepull_b11a.pt")
    log("the pull is out; held to update {}".format(a.hold_to))
    while updates() < a.hold_to:
        time.sleep(a.poll)
    fade("BRAIN_FADE", 0.0, 1.0, "policy_nopull_b11a.pt")
    log("the brain's old belief is out; both fades done; the checks are still flagged")''',
     '''    up = lambda x, n: math.ceil(x / n * 1e6) / 1e6             # (rounded up: the last step lands on TO)  # noqa: E731
    fade("BRAIN_FADE", 0.0, 1.0, up(1.0, a.brain_steps), "policy_prebrain_b11a.pt")
    log("the brain's old belief is out; held to update {}".format(a.hold_pull))
    while updates() < a.hold_pull:
        time.sleep(a.poll)
    fade("LEVEL_PULL", 0.95, 1.0, up(0.05, a.pull_steps), "policy_nobrain_b11a.pt")
    log("the pull is out; held to update {}".format(a.hold_lock))
    while updates() < a.hold_lock:
        time.sleep(a.poll)
    fade("INTENT_HOLD", 8.0, 1.0, 1.0, "policy_nopull_b11a.pt", "--values", "4,2,1")
    log("the lock is out; all three fades done; the checks are still flagged")'''))
rep("docs/runs/b1.1/b1.1a/smoke.py",
    ('scratch_b11a_smoke', 'scratch_b11a_smoke3'),
    ('"--hold-to", "1", "--steps", "2", ', '"--hold-pull", "1", "--hold-lock", "1", "--brain-steps", "2", "--pull-steps", "2", '),
    ('the pull out first, the brain after it, both at 1', 'the brain out first, then the pull, then the lock, all at their ends'),
    ('lv.update(LEVEL_PULL=0.95, BRAIN_FADE=0.0)', 'lv.update(LEVEL_PULL=0.95, BRAIN_FADE=0.0, INTENT_HOLD=8.0)'),
    ('''check("LEVEL_PULL 1, BRAIN_FADE 1 at the end ({}, {})".format(lv2.get("LEVEL_PULL"), lv2.get("BRAIN_FADE")), lv2.get("LEVEL_PULL") == 1.0 and lv2.get("BRAIN_FADE") == 1.0)''',
     '''check("LEVEL_PULL 1, BRAIN_FADE 1, INTENT_HOLD 1 at the end ({}, {}, {})".format(lv2.get("LEVEL_PULL"), lv2.get("BRAIN_FADE"), lv2.get("INTENT_HOLD")), lv2.get("LEVEL_PULL") == 1.0 and lv2.get("BRAIN_FADE") == 1.0 and lv2.get("INTENT_HOLD") == 1.0)'''),
    ('''check("the pull done before the brain began", 0 < R.find("ramp_live done: LEVEL_PULL") < R.find("RAMP BRAIN_FADE"))''',
     '''check("the brain, then the pull, then the lock", 0 < R.find("ramp_live done: BRAIN_FADE") < R.find("RAMP LEVEL_PULL") and R.find("ramp_live done: LEVEL_PULL") < R.find("RAMP INTENT_HOLD") and "ramp_live done: INTENT_HOLD at 1.0" in R)
    check("the lock's steps 4, 2, 1", all("RAMP INTENT_HOLD " + x in R for x in ("4.0", "2.0", "1.0")))
    check("the lock taken live", "'INTENT_HOLD': '1.0'" in log)
    import torch
    ev_ = torch.load(os.path.join(D, "policy.pt"), map_location="cpu", weights_only=False).get("env_vars") or {}
    check("the last save carries the lock ({})".format(ev_.get("INTENT_HOLD")), float(ev_.get("INTENT_HOLD", -1)) == 1.0)'''),
    ('("policy_prepull_b11a.pt", "policy_nopull_b11a.pt")', '("policy_prebrain_b11a.pt", "policy_nobrain_b11a.pt", "policy_nopull_b11a.pt")'),
    ('("--minutes 885 --gamma", "--minutes 12 --gamma")', '("--minutes 855 --gamma", "--minutes 12 --gamma")'))
rep("docs/runs/b1.1/b1.1a/start.ps1",
    ("the pull toward level faded out, then the brain's old belief.", "the brain's old belief, the pull toward level and the target lock faded out."),
    ('d.update(LEVEL_PULL=0.95, BRAIN_FADE=0.0)', 'd.update(LEVEL_PULL=0.95, BRAIN_FADE=0.0, INTENT_HOLD=8.0)'),
    ('(the pull, then the brain; held', '(the brain, the pull, the lock; held'),
    ('''$f = Join-Path $HERE "smoke.log"
if (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 1) -like "*ALL PASSED*")) { Log "smoke.log has not passed: not started"; exit 1 }''',
     '''foreach ($n in "ident.log", "smoke.log") {
    $f = Join-Path $HERE $n
    if (-not (Test-Path $f) -or -not ((Get-Content $f -Tail 1) -like "*ALL PASSED*")) { Log "$n has not passed: not started"; exit 1 }
}
if (-not (Select-String -Path (Join-Path $HERE "smoke.log") -Pattern "the lock's steps" -SimpleMatch -Quiet)) { Log "smoke.log is from the old plan: not started"; exit 1 }
if (-not (Select-String -Path (Join-Path $HERE "ramp_b11.py") -Pattern '"INTENT_HOLD", 8.0' -SimpleMatch -Quiet)) { Log "the ramp has no lock fade: not started"; exit 1 }'''))
rep("docs/runs/b1.1/b1.1a/make_files.py",
    ("the pull toward level faded out, then the brain's old belief (live LEVEL_PULL, BRAIN_FADE:", "the brain's old belief, the pull toward level and the target lock faded out (live BRAIN_FADE, LEVEL_PULL, INTENT_HOLD:"),
    ("--minutes 885 --gamma", "--minutes 855 --gamma"),
    ("--minutes 885; --brain-fade 1", "--minutes 855; --brain-fade 1"),
    ("--minutes 885, --brain-fade 1", "--minutes 855, --brain-fade 1"))
print("patched")
