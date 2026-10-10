"""Add an entry to the results log (docs/README.md has the routine):

    python tools/add_result.py entry.md

entry.md is the entry as Markdown, its first line the heading "## 2026-10-10 12:00 — what happened" (date, time, a
dash, a title that says the finding). Links in it are written as from docs/results/ (for example ../BACKLOG.md,
../runs/MANIFEST_v14.md). The entry goes to the top of docs/results/<date>.md (made if the day is new) and its line to
the top of that day in the index, docs/RESULTS.md. Then run tools/docs_check.py and commit. Standard library only."""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
entry = io.open(sys.argv[1], encoding="utf-8").read().replace("\r\n", "\n").strip("\n") + "\n"
m = re.match(r"## (\d{4}-\d{2}-\d{2})\s*(.*)", entry)
assert m, "the entry must begin with '## YYYY-MM-DD HH:MM — title'"
day, title = m.group(1), m.group(2).strip()
assert title, "the heading has no title"


def read(path):
    s = io.open(path, encoding="utf-8", newline="").read()
    return s.replace("\r\n", "\n"), "\r\n" in s


def write(path, s, crlf):
    io.open(path, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)


ipath = os.path.join(ROOT, "docs", "RESULTS.md")
index, icrlf = read(ipath)
dpath = os.path.join(ROOT, "docs", "results", day + ".md")
if os.path.exists(dpath):
    s, crlf = read(dpath)
    assert ("\n## " + day + " " + title + "\n") not in s, "this entry is in the log already"
    head, sep, rest = s.partition("\n## ")
    s = head.rstrip("\n") + "\n\n" + entry + ("\n## " + rest if sep else "")
else:
    crlf = icrlf
    s = "# Results, {}\n\nNewest first. The index of all days: [RESULTS.md](../RESULTS.md).\n\n{}".format(day, entry)
write(dpath, s, crlf)
mark = "## [{0}](results/{0}.md)".format(day)
line = "- " + title
if mark in index:
    index = index.replace(mark + "\n\n", mark + "\n\n" + line + "\n", 1)
else:
    first = re.search(r"\n## \[", index)
    assert first, "the index has no day yet"
    index = index[:first.start() + 1] + mark + "\n\n" + line + "\n\n" + index[first.start() + 1:]
write(ipath, index, icrlf)
print("added to docs/results/{}.md and to the index: {}".format(day, title[:90]))
