"""Watch the server; whenever a human client joins, make them spectate the practicing bot (client 0)."""
import re
import subprocess
import time

seen = set()
while True:
    out = subprocess.run(["python3", "/tools/rcon.py", "status", "--wait", "1"], capture_output=True, text=True).stdout
    humans = set()
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+-?\d+\s+\d+\s+(.+?)\s+\d+\s+(\S+)", line)
        if m and m.group(3) != "bot":
            humans.add(int(m.group(1)))
    for cid in humans - seen:
        time.sleep(3)
        subprocess.run(["python3", "/tools/rcon.py", "qlx !follow {} 0".format(cid), "--wait", "1"])
        print("follow set for client", cid, flush=True)
    seen = humans
    time.sleep(4)
