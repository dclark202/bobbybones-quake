"""
botctl.py -- Python client for the Quake3e engine's botctl Unix-domain socket.

Protocol (little-endian, framed): [u32 total_len][u8 opcode][payload...]
where total_len = 1 + len(payload). Request/response is 1:1 except CMD,
which is fire-and-forget (the engine stages inputs and replays them on its
own clock; the sidecar never blocks on them).

  0x01 PING   : no payload              -> b"PONG"
  0x02 ADD    : name[32] team[16] u32   -> u32 client_num (-1 on failure)
  0x03 REMOVE : u32 client_num         -> u32 result (1 ok / 0 fail)
  0x04 CMD    : u32 client, i16 fwd/right/up, u32 buttons, u32 weapon,
                f32 pitch, f32 yaw      -> (no response)
  0x05 SNAP   : no payload              -> snapshot blob (empty on timeout)
  0x06 LIST   : no payload              -> u16 count + [u32 num, name[32], team[16]]*
  0x07 TEXT   : u32 client, text bytes  -> u32 result (1 ok / 0 fail)

Snapshot blob layout:
  u32 time
  u32 restart_id       # sv.restartedServerId: changes on every map (re)start
  u16 num_players  u16 num_ents
  per player (132 B):
    u32 client_num
    f32 origin[3]
    u32 health  u32 armor  u32 weapon  u32 weaponstate
    u32 team    u32 score
    f32 viewangles[3]
    u32 delta_angles[3]
    u32 pm_type
    u32 ammo[MAX_WEAPONS]   # ammo[0..15]; -1 = infinite
  per entity (52 B):
    u32 number  u32 eType  u32 eFlags
    f32 origin[3]
    u32 modelindex  u32 client_num  u32 weapon  u32 other_entity_num
    f32 pos_delta[3]

Stdlib only. x86 host (little-endian) -- the engine's writer is explicit
little-endian, so struct '<' formats match byte-for-byte.
"""

import socket
import struct

# ---------------------------------------------------------------- protocol
OP_PING = 0x01
OP_ADD = 0x02
OP_REMOVE = 0x03
OP_CMD = 0x04
OP_SNAP = 0x05
OP_LIST = 0x06
OP_TEXT = 0x07

MAX_NAME = 32
MAX_TEAM = 16


def sockpath_for_port(port: int) -> str:
    """Default engine socket path (mirrors Botctl_DeriveSockpath)."""
    return f"/tmp/q3e-botctl-{port}.sock"


def angle2short(deg: float) -> int:
    return int(deg * 65536.0 / 360.0) & 0xFFFF


# ----------------------------------------------------------------- framing
def _recv_exact(f, n: int) -> bytes:
    """Read exactly n bytes from the socket file (read() may return less)."""
    buf = b""
    while len(buf) < n:
        chunk = f.read(n - len(buf))
        if not chunk:
            raise ConnectionError("botctl socket closed")
        buf += chunk
    return buf


def _send_frame(sock: socket.socket, op: int, payload: bytes) -> None:
    total = 1 + len(payload)
    sock.sendall(struct.pack("<IB", total, op) + payload)


def _read_frame(f) -> tuple:
    total = struct.unpack("<I", _recv_exact(f, 4))[0]
    if total < 1 or total > (1 << 20):
        raise ValueError(f"botctl: bad frame length {total}")
    op = _recv_exact(f, 1)[0]
    payload = _recv_exact(f, total - 1) if total > 1 else b""
    return op, payload


# ---------------------------------------------------------------- client
class Botctl:
    """One connected sidecar session. Request ops block for their reply;
    cmd() is fire-and-forget."""

    def __init__(self, sockpath: str):
        self.sockpath = sockpath
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(sockpath)
        self.f = self.sock.makefile("rb")

    def close(self):
        try:
            self.sock.close()
        finally:
            self.f = None

    # -- request/response ops
    def ping(self) -> str:
        _send_frame(self.sock, OP_PING, b"")
        op, payload = _read_frame(self.f)
        if op != OP_PING:
            raise ValueError(f"botctl: expected PING reply, got 0x{op:02x}")
        return payload.decode("ascii", "replace")

    def add(self, name: str, team: str = "", substeps: int = 1) -> int:
        payload = (
            name.encode("ascii", "replace").ljust(MAX_NAME, b"\0")[:MAX_NAME]
            + team.encode("ascii", "replace").ljust(MAX_TEAM, b"\0")[:MAX_TEAM]
            + struct.pack("<i", substeps)
        )
        _send_frame(self.sock, OP_ADD, payload)
        op, resp = _read_frame(self.f)
        if op != OP_ADD:
            raise ValueError(f"botctl: expected ADD reply, got 0x{op:02x}")
        return struct.unpack("<i", resp)[0]

    def remove(self, client_num: int) -> int:
        _send_frame(self.sock, OP_REMOVE, struct.pack("<i", client_num))
        op, resp = _read_frame(self.f)
        if op != OP_REMOVE:
            raise ValueError(f"botctl: expected REMOVE reply, got 0x{op:02x}")
        return struct.unpack("<i", resp)[0]

    def text(self, client_num: int, cmd: str) -> int:
        """Send a game text command as the client ('ready', 'say hi', ...)."""
        _send_frame(self.sock, OP_TEXT, struct.pack("<i", client_num) + cmd.encode("ascii", "replace"))
        op, resp = _read_frame(self.f)
        if op != OP_TEXT:
            raise ValueError(f"botctl: expected TEXT reply, got 0x{op:02x}")
        return struct.unpack("<i", resp)[0]

    def list(self) -> list:
        _send_frame(self.sock, OP_LIST, b"")
        op, payload = _read_frame(self.f)
        if op != OP_LIST:
            raise ValueError(f"botctl: expected LIST reply, got 0x{op:02x}")
        if len(payload) < 2:
            return []
        count = struct.unpack("<H", payload[:2])[0]
        out = []
        off = 2
        for _ in range(count):
            num = struct.unpack_from("<I", payload, off)[0]
            name = payload[off + 4: off + 4 + MAX_NAME].split(b"\0")[0].decode("ascii", "replace")
            team = payload[off + 4 + MAX_NAME: off + 4 + MAX_NAME + MAX_TEAM].split(b"\0")[0].decode("ascii", "replace")
            off += 4 + MAX_NAME + MAX_TEAM
            out.append((num, name, team))
        return out

    def snap(self) -> "Snapshot":
        _send_frame(self.sock, OP_SNAP, b"")
        op, payload = _read_frame(self.f)
        if op != OP_SNAP:
            raise ValueError(f"botctl: expected SNAP reply, got 0x{op:02x}")
        return Snapshot(payload) if payload else Snapshot(b"")

    # -- fire-and-forget input
    def cmd(self, client_num: int, fwd: int, right: int, up: int,
            buttons: int = 0, weapon: int = 0,
            pitch: float = 0.0, yaw: float = 0.0) -> None:
        """Stage one usercmd (absolute view angles in degrees)."""
        payload = struct.pack(
            "<i h h h I I f f",
            client_num,
            int(fwd), int(right), int(up),
            buttons & 0xFFFFFFFF, weapon & 0xFFFFFFFF,
            pitch, yaw,
        )
        _send_frame(self.sock, OP_CMD, payload)


# ----------------------------------------------------------------- snapshot
class Snapshot:
    """Parsed state dump from the engine (see module docstring for layout)."""

    PLAYER_F = "<I 3f I I I I I I 3f 3i I 16i"
    PLAYER_SZ = struct.calcsize(PLAYER_F)   # 132
    ENT_F = "<I I I 3f I I I I 3f"
    ENT_SZ = struct.calcsize(ENT_F)         # 52

    def __init__(self, blob: bytes):
        self.blob = blob
        self.time = 0
        self.restart_id = 0
        self.players = {}     # client_num -> dict
        self.ents = []        # list of dicts

        if len(blob) < 12:
            return
        self.time, self.restart_id, np, ne = struct.unpack_from("<I I H H", blob, 0)
        off = 12
        for _ in range(np):
            p = struct.unpack_from(self.PLAYER_F, blob, off)
            off += self.PLAYER_SZ
            self.players[p[0]] = {
                "num": p[0],
                "origin": (p[1], p[2], p[3]),
                "health": p[4], "armor": p[5],
                "weapon": p[6], "weaponstate": p[7],
                "team": p[8], "score": p[9],
                "viewangles": (p[10], p[11], p[12]),
                "delta_angles": (p[13], p[14], p[15]),
                "pm_type": p[16],
                "ammo": list(p[17:17 + 16]),
            }
        for _ in range(ne):
            e = struct.unpack_from(self.ENT_F, blob, off)
            off += self.ENT_SZ
            self.ents.append({
                "number": e[0], "eType": e[1], "eFlags": e[2],
                "origin": (e[3], e[4], e[5]),
                "modelindex": e[6], "clientNum": e[7],
                "weapon": e[8], "otherEntityNum": e[9],
                "posDelta": (e[10], e[11], e[12]),
            })

    def player(self, num: int):
        return self.players.get(num)

    def items(self, modelindex: int = None):
        return [e for e in self.ents if e["eType"] == 2
                and (modelindex is None or e["modelindex"] == modelindex)]

    def missiles(self):
        return [e for e in self.ents if e["eType"] == 3]


# ------------------------------------------------------------ q3 constants
# buttons (q_shared.h)
BUTTON_ATTACK = 1
BUTTON_TALK = 2
BUTTON_USE_HOLDABLE = 4
BUTTON_GESTURE = 8
BUTTON_WALKING = 16
BUTTON_AFFIRMATIVE = 32
BUTTON_NEGATIVE = 64

# weapons — THIS OSP BUILD's weapon_t (bg_public.h), NOT vanilla Q3!
# There is no blaster here: slot 1 is the GAUNTLET (fires only on a physical
# trace hit), and the spawn weapon in TDM mode is the MACHINEGUN (2).
WP_NONE = 0
WP_GAUNTLET = 1
WP_MACHINEGUN = 2
WP_SHOTGUN = 3
WP_GRENADE_LAUNCHER = 4
WP_ROCKET_LAUNCHER = 5
WP_LIGHTNING = 6
WP_RAILGUN = 7
WP_PLASMAGUN = 8
WP_BFG = 9
WP_GRAPPLING_HOOK = 10
# MISSIONPACK-only (not defined in the clan QVM build, listed for reference):
WP_NAILGUN = 11
WP_PROX_LAUNCHER = 12
WP_CHAINGUN = 13
WP_NUM_WEAPONS = 14

# weaponstate_t (bg_public.h) — note: FIRING is 3, not 1 (vanilla has the same
# order; earlier probes wrongly checked state==1)
WEAPON_READY = 0
WEAPON_RAISING = 1
WEAPON_DROPPING = 2
WEAPON_FIRING = 3

# pmove types
PM_NORMAL = 0
PM_NOCLIP = 1
PM_SPECTATOR = 2
PM_DEAD = 3
PM_FREEZE = 4
PM_INTERMISSION = 5
PM_SPINTERMISSION = 6

# teams
# OSP's team_t (bg_public.h) is NOT vanilla Q3's ordering!
TEAM_NONE = 0        # TEAM_FREE
TEAM_RED = 1
TEAM_BLUE = 2
TEAM_SPECTATOR = 3

# entity types (bg_public.h)
ET_GENERAL = 0
ET_PLAYER = 1
ET_ITEM = 2
ET_MISSILE = 3
ET_MOVER = 4
ET_BEAM = 5
ET_PORTAL = 6
ET_SPEAKER = 7
ET_PUSH_TRIGGER = 8
ET_TELEPORT_TRIGGER = 9
ET_INVISIBLE = 10
ET_GRAPPLE = 11
ET_TEAM = 12
ET_EVENTS = 13
