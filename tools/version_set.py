"""A version's folder for !version (plugins/duelbot.py; owner, 2026-11-22): checks a folder's files and writes its version.json.

    python tools/version_set.py <folder> [--name <name>]       check, then write <folder>/version.json
    python tools/version_set.py <folder> --check               check only (the folder's version.json must agree with its files)

The folder holds one network's !aim files, as tools/aim2_levels.py writes them (policy_default.npz, policy_max.npz; other levels'
files are left alone and never served) and legs.npz when the network has legs (its policy files name "legs.npz"). The checks:
both files there, each names its own level (env_vars AIM_NAME), the same network in both (every array but env_vars, react_ms
and acquire_ms equal: what the plugin's aim_build demands), legs.npz there when the network names it. version.json:
{"name", "run", "minutes", "updated", "env", "legs", "md5": {file: hash}}; the plugin matches a loaded network to its version by
run and minutes, and offers only a folder whose files are all there. --name defaults to the folder's own name, which is also
what a player types (!version <folder name>). Exit 1 on any failed check, with nothing written.
"""
import hashlib
import json
import os
import sys

import numpy as np

AIM_FILES = {"default": "policy_default.npz", "max": "policy_max.npz"}    # (plugins/duelbot.py AIM_FILES)
AIM_KEEP = ("env_vars", "react_ms", "acquire_ms")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def build(folder, name=None):
    """the folder's version.json as it should be; raises SystemExit on a failed check"""
    def fail(msg):
        raise SystemExit("REFUSED {}: {}".format(folder, msg))
    for f_ in AIM_FILES.values():
        if not os.path.isfile(os.path.join(folder, f_)):
            fail("no " + f_)
    Z = {lv: np.load(os.path.join(folder, f_), allow_pickle=False) for lv, f_ in AIM_FILES.items()}
    for lv, z in Z.items():
        ev = json.loads(str(z["env_vars"]))
        if ev.get("AIM_NAME") != lv:
            fail("{} names itself {}".format(AIM_FILES[lv], ev.get("AIM_NAME")))
    a, b = Z["default"], Z["max"]
    ka, kb = sorted(k for k in a.files if k not in AIM_KEEP), sorted(k for k in b.files if k not in AIM_KEEP)
    if ka != kb:
        fail("policy_default and policy_max hold other arrays")
    for k in ka:
        if not np.array_equal(a[k], b[k]):
            fail("policy_default and policy_max differ in {} (not one network)".format(k))
    legs = "legs" in a.files
    if legs and str(a["legs"]) != "legs.npz":
        fail("the network names its legs {} (the plugin's flat name is legs.npz)".format(a["legs"]))
    if legs and not os.path.isfile(os.path.join(folder, "legs.npz")):
        fail("the network has legs and legs.npz is not there")
    files = list(AIM_FILES.values()) + (["legs.npz"] if legs else [])
    out = dict(name=name or os.path.basename(os.path.normpath(folder)), run=str(a["run"]), minutes=int(a["minutes"]),
               updated=str(a["updated"]) if "updated" in a.files else "", env=str(a["env"]), legs=bool(legs),
               md5={f_: md5(os.path.join(folder, f_)) for f_ in files})
    return out


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    folder = args[0]
    name = args[args.index("--name") + 1] if "--name" in args else None
    want = build(folder, name)
    path = os.path.join(folder, "version.json")
    if "--check" in args:
        with open(path, encoding="utf-8") as f:
            have = json.load(f)
        bad = [k for k in want if have.get(k) != want[k]]
        if bad:
            raise SystemExit("REFUSED {}: version.json disagrees with the files in {}".format(folder, ", ".join(bad)))
        print("ok {}: {} ({} min, {}), {} files".format(folder, have["name"], have["minutes"], have["run"], len(have["md5"])))
        return
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(want, f, indent=1)
    os.replace(path + ".tmp", path)
    print("wrote {}: {} ({} min, {}, updated {}), legs {}".format(path, want["name"], want["minutes"], want["run"], want["updated"], want["legs"]))


if __name__ == "__main__":
    main()
