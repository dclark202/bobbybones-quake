# Go-live checklist (public server)

Not live yet. Work through this before opening the server to the public.

## Software (in repo)
- [ ] **Lock down admin chat commands.** `!drive`, `!range`, `!follow`, `!record`, `!items`, `!probe`, `!pr`, `!ir`, `!jl`, `!autospec` are currently usable by any player. Make them owner/console only (minqlx permission 5).
- [ ] **Recording notice.** Welcome message saying matches are recorded (movement, item timing, weapon use) to train the bot and to generate player reports.
- [ ] **Disk usage.** Rotate and cap `itemrun_frames.jsonl`, `trace_live.txt` and `server.log` (tens of MB per hour of play).
- [ ] **Server listing.** `sv_master 1`, a real hostname, tags.
- [ ] **Multiple humans.** Check queue/spectator behavior when a second human joins a 1v1-vs-bot server.
- [ ] **Per-player data.** Key recordings by Steam ID for player profiles and reports.
- [ ] **Crash watch.** Review `server.log` after the first public sessions. Auto-restart plus `tools/bootstrap.sh` recover in ~20 s.

## Hosting (outside the repo)
- [ ] Router: forward UDP 27970 to the host machine.
- [ ] Host firewall: allow inbound UDP 27970 for Docker.
- [ ] Host stays awake with Docker running, or move to a small VPS (~$5-10/month; avoids exposing a home IP).

## Already OK
- ZMQ remote console and stats feed are bound inside the container and not published.
- Auto-restart and self-setup after crashes.
- Duel bandwidth is negligible.
