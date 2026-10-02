# bobbybones-quake

A Quake Live duel bot, **BobbyBones**, that plays real people on a real Quake Live dedicated server, learns from how they play, and gives them a report on their game.

## Vision

1. **Bobby learns from opponents.** Every match is recorded: how players move, which weapons they pick in which situations, where they prefire, which areas they control, and how they time items. That feeds back into his routes, weapon choices and item timing.
2. **Players get a report.** After playing Bobby: a heatmap of where you spent your time, item timing (how long after spawn you took RA/YA/MH, what you gave away), movement stats (speed, strafe-jumping share), and weapon usage.
3. **Nightmare first, aim tiers later.** Get a very strong but fair bot public so it can learn from many players. Different aim and difficulty tiers come after.

## How it works

- **Server:** Quake Live dedicated server (Steam app 349090) in Docker, with [minqlx](https://github.com/MinoMino/minqlx) for Python plugins.
- **Bot control** (`minqlx/botctl.c`): a hook on the engine's `SV_ClientThink` lets Python override a bot's per-frame input (movement, view, buttons, weapon).
- **Hybrid combat:** the built-in bot AI decides *when* it can shoot (it traces line of sight). Our code chooses the weapon, aims with human-like error and reaction time, and steers movement. There's no wallhack: Bobby only knows your position from sight or sound.
- **Item control** (`plugins/itemrun.py`): routes on a navigation graph learned from recorded bot and player movement (`maps/campgrounds/nav.json`), strafe-jumping on straight stretches, arriving at RA/YA/MH on their spawn timers. Item timers are fair: he only knows what he saw or heard.
- **Skill practice** (`plugins/practice.py`, `plugins/jumplab.py`): trial-and-error optimization (cross-entropy method) of movement tricks such as rocket jumps, pillar hops and the bridge-to-rail jump.
- **Analysis** (`tools/`): session reports and heatmaps (`analyze_session.py`), nav graph builder (`navgraph.py`), video renderers.

## Running it

```bash
docker build -t qlbot .
docker run -d --name ql --restart unless-stopped -p 27970:27970/udp -v "$PWD/data/practice:/tmp/practice" qlbot +set net_port 27970 +set sv_serverType 2
```

The server sets itself up on start (`tools/bootstrap.sh`): campgrounds duel in permanent warmup with all weapons, BobbyBones added, recording on, item control and combat running. In the Quake Live console, run `connect 127.0.0.1:27970`.

Remote console: `docker exec ql python3 /tools/rcon.py "status"`.

## Status

| | |
|---|---|
| Bot input control, strafe jumping, rocket jumps | working |
| Item timing (RA 25 s, YA 25 s, MH 35 s) | working; routing still has rough spots |
| Hybrid combat with fair senses and aim error | first version; accuracy tuning in progress |
| Session report + heatmaps | working (offline script) |
| Learning weapon choice from players | recording in place, policy builder next |
| Public server, per-player profiles | not yet |

## Repo layout

```
Dockerfile, entrypoint.sh   server image
server/                     lab server config
minqlx/                     vendored minqlx + BobbyBones input hook (see minqlx/UPSTREAM.md)
plugins/                    botctl (control/recording), itemrun (item control + combat), practice, jumplab
tools/                      rcon, stats feed, bootstrap, nav graph, analysis, video renderers
maps/campgrounds/           learned map knowledge: nav graph, walk traces, item spots, pillar survey
docs/                       feasibility report
data/                       (git-ignored) local recordings, telemetry, videos
```

Optional: `-e QLX_OWNER=<your steam id64>` gives your Steam account minqlx owner permissions in game.

## License

GPL-3.0 (see `LICENSE`). The bundled minqlx is GPL-3.0, so the project follows it.
