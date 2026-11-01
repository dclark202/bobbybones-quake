---
name: local-server
description: Put a BobbyBones model checkpoint on a private local Quake Live server for the owner to play. Use when asked for a local playtest, a local server, or to play a run, version or save locally. Never for the public servers.
---

# Local server from a checkpoint

1. **Pick the save.** Find the run's folder and exact save: usually `data/sim_runs/<run>/keep/policy_end_<ver>.pt`, or the save the owner names. Say which one if it's unclear from the request. Find its `train.cmd` under `docs/runs/`.
2. **Check first.** Run `docker ps`, and check whether a trainer is running. If `docker ps` shows a server on the port, don't stop it: someone may be on it. Ask, or use another `PORT`. Never restart a server the owner may be on.
3. **Start it** (Git Bash):

   ```bash
   CARD_CMD=docs/runs/<ver>/train.cmd bash tools/run/local_server.sh <run> <save> <version> [map]
   ```

   It exports the save, makes the `!aim` files, starts the unlisted server with the mind log on, and starts the mind viewer and the local games site.
4. **Read the output.** It must show `duelbot] ready` naming the right run, and 200 from both pages.
   - **Settings check (hard rule):** read every difference. A dial changed live during the run, such as `LEVEL_PULL`, is expected if the run's card says so. Anything else: tell the owner before they play.
   - **Older networks:** a network with another input count needs its own `ENVMOD` (`--env`, see `CLAUDE.md`). Networks from before the aim2 model (v0.6.0) may not fit `aim2_levels.py`; stop and say so.
5. **Tell the owner:** the connect line, the two page addresses, the data folder, and what the network plays with (the aim, the pull, the belief).
   - **Training at the same time is fine for play tests:** the owner has never noticed a slowdown from it (2026-10-31), so don't warn about stutter. Measurements on a real server (sparring, timing) still need nothing else running.
   - **The image:** `qlbot:playaim2` is the default, built 10-27. It's older than the public servers' build. Standing rule: local servers use the public build plus only the change under test, so say so, or pass a newer `IMAGE`. Check the server and viewmodel behaviour after changing image.
6. **Afterwards.** When the owner is done, `docker stop <name>` (never `docker rm`). Then analyse `mind.jsonl` and the session together. Local games never go on the public site. Log the play test's outcome on the run's card.
