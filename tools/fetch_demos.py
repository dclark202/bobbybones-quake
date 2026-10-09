"""Download recent Quake Live duel demos (.dm_91, 2024+) for imitation learning, politely.

    python tools/fetch_demos.py                      # bloodrun, aerowalk, campgrounds
    python tools/fetch_demos.py --gap 8 --maps 6,1,9
    python tools/fetch_demos.py --maps 22,2 --limit 150     # the newest 150 of each (Sinister, Furious Heights)

Source: demos.quakelive.ru (public JSON API; files on files.quakelive.ru). One request at a time with a
pause between downloads; already-downloaded files are skipped, so it can be stopped and resumed.
Writes <demo root>/demos/<map>/<file> and <demo root>/demos/index.jsonl (demo root: data/, or the folder named in
data/demo_root.txt) (the API's metadata incl. per-player stats).
"""
import argparse
import json
import os
import random
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://demos.quakelive.ru/api/demos?type=Duel&map_id={}&per_page=100&page={}"
FILES = "https://files.quakelive.ru/{}"
MAPS = {6: "bloodrun", 1: "aerowalk", 20: "lostworld", 9: "campgrounds", 22: "sinister", 2: "furiousheights",
        5: "battleforged", 17: "hektik", 11: "cure", 23: "toxicity"}      # the site's map ids (its /api/maps)
def demo_root():
    """where demos and the training data made from them live: the folder named in data/demo_root.txt (one line,
    for a big separate drive), else data/"""
    f = os.path.join(ROOT, "data", "demo_root.txt")
    if os.path.exists(f):
        p = open(f).read().strip()
        if p:
            return p
    return os.path.join(ROOT, "data")


UA = {"User-Agent": "bobbybones-quake research bot (one file at a time; github.com/dclark202/bobbybones-quake)"}


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default="6,1,9")
    ap.add_argument("--gap", type=float, default=8.0, help="seconds between downloads (plus jitter)")
    ap.add_argument("--ext", default=".dm_91")
    ap.add_argument("--limit", type=int, default=0, help="at most this many demos a map, the newest first (0 = all)")
    a = ap.parse_args()
    out = os.path.join(demo_root(), "demos")
    os.makedirs(out, exist_ok=True)
    index_f = os.path.join(out, "index.jsonl")
    known = set()
    if os.path.exists(index_f):
        known = {json.loads(l)["file"] for l in open(index_f)}
    todo = []
    for mid in (int(x) for x in a.maps.split(",")):
        page, last, n_map = 1, 1, 0
        while page <= last and not (a.limit and n_map >= a.limit):
            d = json.loads(get(API.format(mid, page)))
            last = d["last_page"]
            for demo in d["data"]:
                if demo["file"].endswith(a.ext) and not (a.limit and n_map >= a.limit):
                    n_map += 1
                    todo.append((MAPS.get(mid, str(mid)), demo))
                    if demo["file"] not in known:
                        with open(index_f, "a") as f:
                            f.write(json.dumps(demo) + "\n")
                        known.add(demo["file"])
            page += 1
            time.sleep(2.0)
    print("{} demos listed".format(len(todo)), flush=True)
    got = skipped = failed = 0
    for mapname, demo in todo:
        d = os.path.join(out, mapname)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, demo["file"])
        if os.path.exists(path) and os.path.getsize(path) > 0:
            skipped += 1
            continue
        try:
            data = get(FILES.format(urllib.parse.quote(demo["file"])), timeout=120)
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
            got += 1
        except Exception as e:
            failed += 1
            print("failed {}: {!r}".format(demo["file"], e), flush=True)
        if (got + failed) % 20 == 0:
            print("{} downloaded, {} skipped, {} failed of {}".format(got, skipped, failed, len(todo)), flush=True)
        time.sleep(a.gap + random.uniform(0, a.gap / 2))
    print("done: {} downloaded, {} already had, {} failed".format(got, skipped, failed), flush=True)


if __name__ == "__main__":
    main()
