"""Minimal Quake Live ZMQ rcon client: rcon.py "cmd1" "cmd2" ... [--wait SECONDS]"""
import sys
import time
import uuid

import zmq

HOST = "tcp://127.0.0.1:28960"
PASSWORD = "lab"

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
while time.time() < end:
    if s.poll(100):
        msg = s.recv().decode("utf-8", "replace")
        sys.stdout.write(msg)
s.close()
ctx.term()
