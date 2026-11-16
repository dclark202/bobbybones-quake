"""rcon_probe.py -- minimal Q3e RCON client (UDP): rcon_probe.py <port> <cmd...>

q3e handles rcon CONNECTIONLESS: the request is '\xff\xffrcon <pass> <cmd>\0'
and the reply is one or more '\xff\xffprint\n<text>' packets
(sv_main.c SVC_RemoteCommand + SV_FlushRedirect). The legacy '\n\1\0'
clC_SYSTEM form only works for already-connected clients and is silently
dropped by SV_PacketEvent otherwise (verified 2026-11-16 with the spike).
"""
import socket
import sys

port = int(sys.argv[1])
cmds = sys.argv[2:]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(3.0)
s.bind(("127.0.0.1", 0))
for cmd in cmds:
    payload = b"\xff\xffrcon testrcon123 " + cmd.encode() + b"\x00"
    s.sendto(payload, ("127.0.0.1", port))
    chunks = []
    try:
        while True:
            data, _ = s.recvfrom(4096)
            if data.startswith(b"\xff\xffprint"):
                chunks.append(data[len(b"\xff\xffprint"):].decode(errors="replace").lstrip("\n"))
            else:
                break
    except socket.timeout:
        pass
    print(f"> {cmd}\n{''.join(chunks) or '(no reply)'}", flush=True)
s.close()
