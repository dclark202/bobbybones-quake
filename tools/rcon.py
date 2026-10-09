"""Minimal Quake Live ZMQ rcon client: rcon.py "cmd1" "cmd2" ... [--wait SECONDS]

The server sends its whole console to every rcon client and its send blocks: a client that leaves while the server is
printing (a map load prints a few hundred lines) can freeze the server's main thread for good (2026-10-09: "!map cure"
with --wait 2, the client left in the middle of the load). So this client leaves only in a quiet moment: after the wait
it keeps reading until nothing has come for QUIET seconds (at most MAX_EXTRA more). Give a command that loads a map a
wait that covers the load (--wait 30).
"""
import sys
import time
import uuid

import zmq

HOST = "tcp://127.0.0.1:28960"
PASSWORD = "lab"
QUIET = 1.0
MAX_EXTRA = 30.0

args = sys.argv[1:]
wait = 1.5
if "--wait" in args:
    i = args.index("--wait")
    wait = float(args[i + 1])
    del args[i:i + 2]

ctx = zmq.Context()
s = ctx.socket(zmq.DEALER)
s.plain_username = b"rcon"
s.plain_password = PASSWORD.encode()
s.zap_domain = b"rcon"
s.setsockopt(zmq.IDENTITY, uuid.uuid1().hex.encode())
s.connect(HOST)
s.send(b"register")
time.sleep(0.3)
for cmd in args:
    s.send(cmd.encode())
    time.sleep(0.2)

end = time.time() + wait
last = time.time()
while time.time() < end or (time.time() - last < QUIET and time.time() < end + MAX_EXTRA):
    if s.poll(100):
        msg = s.recv().decode("utf-8", "replace")
        last = time.time()
        if time.time() < end:                            # what comes after the wait is read, not shown
            sys.stdout.write(msg)
s.close()
ctx.term()
