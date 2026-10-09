# Vendored minqlx

Upstream: https://github.com/MinoMino/minqlx at commit `fbdd915185337791d8e209dc4b686a1ee60d3721` (2023-08-13), GPL-3.0.

Local changes (BobbyBones):
- `botctl.c` / `botctl.h` (new): hooks the engine's `SV_ClientThink` so a bot's per-frame input can be
  overridden from Python. Python API: `set_bot_input`, `clear_bot_input`, `set_bot_move` (hybrid: AI aims,
  we steer), `set_bot_aim` (aim/weapon override + fire suppression), `ai_wants_fire`, `view_angles`,
  `last_usercmd`, `item_states`.
- `dllmain.c`: pattern-search `SV_ClientThink`. `hooks.c`: install the hook. `python_embed.c`: register the
  new functions. `Makefile`: build `botctl.c`.
- 2026-10-08: `botctl.c` / `hooks.c`: bots under full control (`set_bot_input` with `set_bot_substeps`) are commanded once per game frame from `Botctl_BeforeFrame` (called in `My_G_RunFrame` after the frame dispatcher); the game AI's own command for such a bot is dropped. Before, the input rode on that command and was lost in a server's catch-up frames.
- 2026-10-09: `botctl.c` / `botctl.h` / `python_embed.c`: `spawn_map_item(classname, x, y, z)`: an item put on the map that comes back after it is taken, like a map's own (`LaunchItem` with the dropped flag and its 30 s timer cleared). `plugins/powerups.py` uses it to give a free-for-all game the item layout of a duel.
