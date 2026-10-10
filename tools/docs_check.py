"""Check the docs before a commit (docs/README.md has the routine):

    python tools/docs_check.py

1. every relative link in README.md, CLAUDE.md and docs/**/*.md leads to a file;
2. every entry of the results log (a "## <date> ..." section in docs/results/<date>.md) has its line in the index
   (docs/RESULTS.md), and every line of the index has its entry;
3. every backlog ID (B-nn) is there once (docs/BACKLOG.md and docs/archive/BACKLOG_closed.md together), and the IDs
   named in the plan's "Now" section exist.
Exit code 1 if anything is wrong. Standard library only."""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"\]\(([^)#\s]+)(#[^)\s]*)?\)")
bad = []


def read(rel):
    return io.open(os.path.join(ROOT, rel), encoding="utf-8").read()


files = ["README.md", "CLAUDE.md"]
for dp, dn, fn in os.walk(os.path.join(ROOT, "docs")):
    files += [os.path.relpath(os.path.join(dp, f), ROOT).replace("\\", "/") for f in fn if f.endswith(".md")]
for rel in files:
    for m in LINK.finditer(read(rel)):
        t = m.group(1)
        if re.match(r"[a-z]+:", t):
            continue
        if not os.path.exists(os.path.normpath(os.path.join(ROOT, os.path.dirname(rel), t))):
            bad.append("link: {} -> {}".format(rel, t))

# the results log and its index
index = {}
day = None
for line in read("docs/RESULTS.md").splitlines():
    m = re.match(r"## \[([^\]]+)\]\(results/([^)]+)\.md\)", line)
    if m:
        day = m.group(2)
        index[day] = []
    elif day and line.startswith("- "):
        index[day].append(line[2:].strip())
rdir = os.path.join(ROOT, "docs", "results")
for f in sorted(os.listdir(rdir)):
    d = f[:-3]
    titles = []
    for line in read("docs/results/" + f).splitlines():
        if line.startswith("## "):
            t = line[3:].strip()
            titles.append(re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", t).strip() or t)
    if d not in index:
        bad.append("results: docs/results/{} is not in the index".format(f))
        continue
    for t in titles:
        if t not in index[d]:
            bad.append("results: no index line for {}: {}".format(d, t[:70]))
    for t in index[d]:
        if t not in titles:
            bad.append("results: the index has a line without an entry, {}: {}".format(d, t[:70]))
for d in index:
    if not os.path.exists(os.path.join(rdir, d + ".md")):
        bad.append("results: the index names docs/results/{}.md, which is not there".format(d))

# the backlog
ids = {}
for rel in ("docs/BACKLOG.md", "docs/archive/BACKLOG_closed.md"):
    if not os.path.exists(os.path.join(ROOT, rel)):
        continue
    for line in read(rel).splitlines():
        m = re.match(r"\|\s*(B-\d+[a-z]?)\s*\|", line)
        if m:
            ids.setdefault(m.group(1), []).append(rel)
for k, v in ids.items():
    if len(v) > 1:
        bad.append("backlog: {} is there {} times ({})".format(k, len(v), ", ".join(v)))
plan = read("docs/PLAN.md")
now = plan.split("\n## Now", 1)[1].split("\n## ", 1)[0] if "\n## Now" in plan else ""
for k in sorted(set(re.findall(r"B-\d+[a-z]?", now))):
    if k not in ids:
        bad.append("plan: the Now section names {}, which is not in the backlog".format(k))

for b in bad:
    print(b)
print("docs check: {} Markdown files, {} results entries on {} days, {} backlog items; {}".format(
    len(files), sum(len(v) for v in index.values()), len(index), len(ids), "{} problems".format(len(bad)) if bad else "all in order"))
sys.exit(1 if bad else 0)
