"""Subscribe to Quake Live's ZMQ stats feed and print one line per event."""
import json
import sys

import zmq

ctx = zmq.Context()
s = ctx.socket(zmq.SUB)
s.plain_username = b"stats"
s.plain_password = b"lab"
s.zap_domain = b"stats"
s.connect("tcp://127.0.0.1:27960")
s.setsockopt(zmq.SUBSCRIBE, b"")
while True:
    msg = json.loads(s.recv().decode("utf-8", "replace"))
    if "-v" in sys.argv:
        print(json.dumps(msg), flush=True)
    else:
        print(msg.get("TYPE"), json.dumps(msg.get("DATA"))[:400], flush=True)
