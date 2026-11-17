"""Writes a run's train.cmd into its folder docs/runs/<version>/ from a command file, with every path made relative to the repo
root (the command computes ROOT from its own place, so the repo can live anywhere) and the aim block called from beside it.
Prints any absolute path left. Usage: python tools/run/make_train_cmd.py <source .cmd> <version> [aim env .cmd]"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src, ver = sys.argv[1], sys.argv[2]
aim = sys.argv[3] if len(sys.argv) > 3 else None
out_dir = os.path.join(ROOT, "docs", "runs", ver)
s = open(src).read().replace("\r\n", "\n")
s, n = re.subn(r"^cd /d C:\\Users\\dacla\\ql-bot[^\n]*\n",
               "rem the repo root: this file lives in docs\\\\runs\\\\" + ver + "\\\\\nset ROOT=%~dp0..\\\\..\\\\..\ncd /d %ROOT%\n", s, count=1, flags=re.M)
assert n == 1, "no cd line"
s = re.sub(r"call C:\\Users\\dacla\\ql-bot[^\\]*\\scratch\\aim2_env\.cmd", lambda m: "call %~dp0aim2_env.cmd", s)
s = s.replace("C:\\Users\\dacla\\ql-bot\\data\\", "%ROOT%\\data\\")
left = re.findall(r"C:\\Users\\dacla\\ql-bot[^ \n]*", s)
print("absolute repo paths left:", left)
assert not left
sys.path.insert(0, os.path.join(ROOT, "sim"))                 # (2.2b's guard) a command whose win-chance pay does not read the judge with the items
import judge_guard as JG  # noqa: E402                         # is not written: it stops and says what to set (an older run's replay: --old-judge-replay 1)
_env = {m_.group(1): m_.group(2).strip() for m_ in re.finditer(r"(?im)^set ([A-Za-z0-9_]+)=(.*)$", s)}
_env.update({m_.group(1): m_.group(2).strip() for m_ in re.finditer(r"(?im)^set ([A-Za-z0-9_]+)=(.*)$", open(aim).read())} if aim else {})
_old = re.search(r"--old-judge-replay\s+1\b", s) is not None
_ok, _why = JG.check(_env, None, ROOT)
if not _ok and not _old:
    raise SystemExit("REFUSED, train.cmd not written (the judge's guard): " + _why)
print("judge's guard:", _why)
open(os.path.join(out_dir, "train.cmd"), "w", newline="\r\n").write(s)
if aim:
    open(os.path.join(out_dir, "aim2_env.cmd"), "w", newline="\r\n").write(open(aim).read().replace("\r\n", "\n"))
print("wrote", os.path.join(out_dir, "train.cmd"))
