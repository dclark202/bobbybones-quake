"""The mind view (B-283): a live picture of what Bobby thinks, for the owner's second monitor during a play test.

The 1v1 plugin writes plugins/mindlog.py's lines into the server's data folder while the owner has it on (`!mind on` in
the game). This serves a page that draws them, from above, on the map's walking floor (data/maps/nav_<map>_sim.json,
coloured by sim/zones/<map>.json): where the owner really is and where Bobby believes him, the brain's guess of where he
will be in 1, 2 and 4 s and what he is going for, the win table's chance and "in control".

    python tools/mind_view.py --data data/<server's data folder> [--port 8765]
    then open http://localhost:8765 in a browser on the second screen

Standard library only (any Python). It only reads: the data folder's mind.jsonl, the map files. Endpoints: /  the page,
/map/<name>  the floor (JSON), /events  the lines as server-sent events (the latest map line and the last lines first,
then each new line as it is written; a rotated or truncated file is followed), /last?n=[&bytes=]  the last lines (JSON; from at most `bytes` of the file's end, 400 kB by default)."""
import argparse
import base64
import json
import os
import re
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "tools", "mind_view.html")
_MAPS = {}
_LOCK = threading.Lock()


def floor(name, root=ROOT):
    """the map's walking floor for the page: nodes [[x, y, z, zone]], the zones' names and centres, the bounds"""
    with _LOCK:
        if name in _MAPS:
            return _MAPS[name]
    nav = os.path.join(root, "data", "maps", "nav_{}_sim.json".format(name))
    zf = os.path.join(root, "sim", "zones", "{}.json".format(name))
    nodes = []
    if os.path.exists(nav):
        with open(nav, encoding="utf-8") as fh:
            nodes = [list(map(float, n[:3])) for n in json.load(fh)["nodes"]]
    zones = None
    if os.path.exists(zf):
        with open(zf, encoding="utf-8") as fh:
            zones = json.load(fh)
    zid = [-1] * len(nodes)
    if zones is not None:
        g = zlib.decompress(base64.b64decode(zones["grid"]))
        dx, dy, dz = (int(v) for v in zones["dims"])
        lo, cell = zones["lo"], float(zones["cell"])
        for i, (x, y, z) in enumerate(nodes):
            ix = min(max(int((x - lo[0]) // cell), 0), dx - 1)
            iy = min(max(int((y - lo[1]) // cell), 0), dy - 1)
            iz = min(max(int((z - lo[2]) // cell), 0), dz - 1)
            v = g[(ix * dy + iy) * dz + iz]
            zid[i] = v - 256 if v > 127 else v
    out = dict(map=name, nodes=[[round(x), round(y), round(z), zid[i]] for i, (x, y, z) in enumerate(nodes)],
               spacing=48, zones=None)
    if nodes:
        xs, ys, zs = [n[0] for n in nodes], [n[1] for n in nodes], [n[2] for n in nodes]
        out["bounds"] = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]
    if zones is not None:
        out["zones"] = dict(names=zones.get("names") or [], centres=zones.get("centres") or [], k=int(zones["k"]))
        if not nodes:
            c = zones["centres"]
            out["bounds"] = [min(p[0] for p in c) - 300, min(p[1] for p in c) - 300, min(p[2] for p in c),
                             max(p[0] for p in c) + 300, max(p[1] for p in c) + 300, max(p[2] for p in c)]
    with _LOCK:
        _MAPS[name] = out
    return out


def tail_lines(path, max_bytes=400000):
    """the file's last lines (at most max_bytes of it)"""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            n = fh.tell()
            fh.seek(max(0, n - max_bytes))
            data = fh.read()
    except OSError:
        return []
    lines = data.decode("utf-8", "replace").splitlines()
    if n > max_bytes and lines:
        lines = lines[1:]                                    # (the first may be cut)
    return [l for l in lines if l.strip()]


def start_lines(path, keep=25):
    """what a new viewer gets first: the latest map line and the last `keep` lines after it"""
    ls = tail_lines(path)
    meta_i = None
    for i in range(len(ls) - 1, -1, -1):
        if '"k":"meta"' in ls[i]:
            meta_i = i
            break
    out = [ls[meta_i]] if meta_i is not None else []
    rest = ls[meta_i + 1:] if meta_i is not None else ls
    return out + rest[-keep:]


class Follow:
    """new lines of a file as it grows; a file that shrinks or is replaced (rotated) is read again from its start. The file
    is opened only for each read and closed at once: on Windows an open handle stops the plugin's rotation (a rename)."""

    def __init__(self, path):
        self.path, self.off, self.ino, self.buf = path, None, None, b""

    def poll(self, first=False):
        try:
            st = os.stat(self.path)
        except OSError:
            return []
        if self.off is None:                                 # the first look: from its end (start_lines sent the rest)
            self.off, self.ino = (st.st_size if first else 0), st.st_ino
        if st.st_ino != self.ino or st.st_size < self.off:
            self.off, self.ino, self.buf = 0, st.st_ino, b""     # rotated or cut: the new file from its start
        if st.st_size <= self.off:
            return []
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.off)
                data = fh.read(st.st_size - self.off)
        except OSError:
            return []
        self.off += len(data)
        self.buf += data
        *lines, self.buf = self.buf.split(b"\n")
        return [l.decode("utf-8", "replace") for l in lines if l.strip()]


def handler(path_jsonl, root):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):                           # (quiet)
            pass

        def _send(self, code, body, ctype):
            b = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            p = self.path.split("?")[0]
            if p in ("/", "/index.html"):
                with open(PAGE, "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            m = re.match(r"^/map/([a-z0-9_]+)$", p)
            if m:
                return self._send(200, json.dumps(floor(m.group(1), root)), "application/json")
            if p == "/last":
                q = dict(x.split("=", 1) for x in self.path.split("?", 1)[1].split("&")) if "?" in self.path else {}
                n = int(q.get("n", "50"))
                mb = min(16000000, max(1000, int(q.get("bytes", "400000"))))     # (the win chart's start: a whole game's lines)
                return self._send(200, "[" + ",".join(tail_lines(path_jsonl, mb)[-n:]) + "]", "application/json")
            if p == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                fol = Follow(path_jsonl)
                try:
                    for l in start_lines(path_jsonl):
                        self.wfile.write(("data: " + l + "\n\n").encode("utf-8"))
                    fol.poll(first=True)
                    self.wfile.flush()
                    quiet = 0.0
                    while True:
                        ls = fol.poll()
                        for l in ls:
                            self.wfile.write(("data: " + l + "\n\n").encode("utf-8"))
                        if ls:
                            self.wfile.flush()
                            quiet = 0.0
                        else:
                            quiet += 0.1
                            if quiet >= 10.0:                # a comment now and then: the page knows the server is there
                                self.wfile.write(b": idle\n\n")
                                self.wfile.flush()
                                quiet = 0.0
                        time.sleep(0.1)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                    return
            return self._send(404, "not found", "text/plain")
    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=os.path.join("data", "duellive"), help="the server's data folder (mounted at /tmp/practice), or a .jsonl file")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1", help="127.0.0.1: this PC only")
    ap.add_argument("--root", default=ROOT, help="the repo (data/maps, sim/zones)")
    a = ap.parse_args()
    f = a.data if a.data.endswith(".jsonl") else os.path.join(a.data, "mind.jsonl")
    f = os.path.abspath(f)
    print("mind view: http://localhost:{}/  (reading {}{})".format(a.port, f, "" if os.path.exists(f) else ", not there yet: type !mind on in the game"),
          flush=True)
    srv = ThreadingHTTPServer((a.host, a.port), handler(f, a.root))
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
