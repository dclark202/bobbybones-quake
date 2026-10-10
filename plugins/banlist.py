"""Kicks and bans for the play-test servers, owner only (minqlx permission 5: the Steam ID in QLX_OWNER).

The bans are kept by Steam ID in a file in the server's data folder (bans.txt), outside the image: they survive a
redeploy, and the ids never get into the repo. The game's own ban list (access.txt) lives inside the container and is
lost when it is rebuilt.

    !players                    everyone connected: number and name
    !kick <number|name>         off the server now (he can come back)
    !ban <number|name> [why]    off the server and not back in
    !bans                       the list: a number per ban, when and why (the Steam IDs stay in the file)
    !unban <number from !bans>  lift a ban
"""
import os
import time

import minqlx

FILE = os.path.join(os.environ.get("BAN_DIR", "/tmp/practice"), "bans.txt")


def is_bot(p):
    return str(p.steam_id).startswith("9007199")


class banlist(minqlx.Plugin):
    def __init__(self):
        super().__init__()
        self.bans = self.load()
        self.add_hook("player_connect", self.on_connect, priority=minqlx.PRI_HIGHEST)
        self.add_command("players", self.cmd_players, 5)
        self.add_command("kick", self.cmd_kick, 5, usage="<number|name>")
        self.add_command("ban", self.cmd_ban, 5, usage="<number|name> [why]")
        self.add_command("bans", self.cmd_bans, 5)
        self.add_command("unban", self.cmd_unban, 5, usage="<number from !bans>")

    @staticmethod
    def load():
        """steam id -> (unix time, reason), in the file's order"""
        out = {}
        try:
            with open(FILE, encoding="utf-8") as f:
                for line in f:
                    p = line.rstrip("\n").split("|", 2)
                    if len(p) >= 1 and p[0].strip().isdigit():
                        out[p[0].strip()] = (float(p[1]) if len(p) > 1 and p[1] else 0.0, p[2] if len(p) > 2 else "")
        except OSError:
            pass
        return out

    def save(self):
        with open(FILE, "w", encoding="utf-8") as f:
            for sid, (t, why) in self.bans.items():
                f.write("{}|{:.0f}|{}\n".format(sid, t, why.replace("\n", " ")))

    def on_connect(self, player):
        if str(player.steam_id) in self.bans:
            return "You are banned from this server."

    def pick(self, caller, who):
        """the player meant by a client number or a part of a name; tells the caller when there is none or more than one"""
        people = [p for p in self.players() if not is_bot(p)]
        if who.isdigit():
            hit = [p for p in people if p.id == int(who)]
        else:
            hit = [p for p in people if who.lower() in p.clean_name.lower()]
        if len(hit) != 1:
            caller.tell("^3{} players match '{}'.^7 ^2!players^7 lists the numbers.".format(len(hit), who))
            return None
        return hit[0]

    def cmd_players(self, player, msg, channel):
        for p in self.players():
            look = ""
            if is_bot(p):
                try:
                    look = "  (bot, {})".format(p.model)
                except Exception:                            # noqa: BLE001
                    look = "  (bot)"
            player.tell("{:2d}  {}{}".format(p.id, p.clean_name, look))
        return minqlx.RET_STOP_ALL

    def cmd_kick(self, player, msg, channel):
        if len(msg) < 2:
            return minqlx.RET_USAGE
        p = self.pick(player, msg[1])
        if p is not None:
            name = p.clean_name
            p.kick("Kicked by the server's owner.")
            player.tell("^3Kicked {}.".format(name))
        return minqlx.RET_STOP_ALL

    def cmd_ban(self, player, msg, channel):
        if len(msg) < 2:
            return minqlx.RET_USAGE
        p = self.pick(player, msg[1])
        if p is not None:
            if str(p.steam_id) == str(minqlx.owner()):
                player.tell("^3That is you.")
                return minqlx.RET_STOP_ALL
            name, why = p.clean_name, " ".join(msg[2:])
            self.bans[str(p.steam_id)] = (time.time(), why)
            self.save()
            p.kick("You are banned from this server.")
            player.tell("^3Banned {}.^7 ^2!bans^7 lists the bans, ^2!unban <number>^7 lifts one.".format(name))
        return minqlx.RET_STOP_ALL

    def cmd_bans(self, player, msg, channel):
        if not self.bans:
            player.tell("No bans.")
        for k, (sid, (t, why)) in enumerate(self.bans.items(), 1):
            player.tell("{:2d}  {}  {}".format(k, time.strftime("%Y-%m-%d %H:%M", time.gmtime(t)) if t else "-", why or "(no reason given)"))
        return minqlx.RET_STOP_ALL

    def cmd_unban(self, player, msg, channel):
        if len(msg) < 2 or not msg[1].isdigit() or not 1 <= int(msg[1]) <= len(self.bans):
            return minqlx.RET_USAGE
        sid = list(self.bans)[int(msg[1]) - 1]
        del self.bans[sid]
        self.save()
        player.tell("^3Ban {} lifted.".format(msg[1]))
        return minqlx.RET_STOP_ALL
