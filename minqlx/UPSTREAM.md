# Vendored minqlx

Upstream: https://github.com/MinoMino/minqlx at commit `fbdd915185337791d8e209dc4b686a1ee60d3721` (2023-08-13), GPL-3.0.

Local changes (BobbyBones):
- `botctl.c` / `botctl.h` (new): hooks the engine's `SV_ClientThink` so a bot's per-frame input can be
  overridden from Python. Python API: `set_bot_input`, `clear_bot_input`, `set_bot_move` (hybrid: AI aims,
  we steer), `set_bot_aim` (aim/weapon override + fire suppression), `ai_wants_fire`, `view_angles`,
  `last_usercmd`, `item_states`.
- `dllmain.c`: pattern-search `SV_ClientThink`. `hooks.c`: install the hook. `python_embed.c`: register the
  new functions. `Makefile`: build `botctl.c`.
