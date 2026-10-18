# v0.3.3: one page (prepared 2026-10-16 night; not started)

**What**: v0.3.2 goes on from its noon save, with two more steps toward one movement network. Starts on the owner's go.

- **Step 3, his legs' features into his memory** (`--legs-feat 1`): what his legs' network "sees" (its last layer before
  its choices) reaches his memory on every frame through a new layer that starts at zero and learns at a quarter of the
  rate. At the start he plays exactly as v0.3.2.
- **Step 2, his own keys on his legs** (`LEGS_KEYS_ADD=1`): while his legs drive he may take over forward/back, sideways,
  jump/crouch, walk and zoom himself, key by key (as the turn correction of v0.3.2 for his view). Shut at the start; opened
  over two hours to about 5% of his frames on his legs; then his own. Same hand limits as any key of his.
- Kept from v0.3.2: everything, the turn correction too (its opening ended at 23:00 the night before; at the first update
  its bias is held at or under 4.68, as v0.3.2 left it).
- **Not on**: the guide (step 4, `--legs-guide`): ready for the 19:00 stop.

**Run**: `duel_gru_v0_3_3`, 12:00 to 19:00 (`--minutes 415`), the same league (v0.3.2's last eight snapshots, v0.3.1's end
as the control). Before the start: `tools/prep_v033.py` from the noon save (writes the run folder and the .cmd).
**Watch**: `keys_add` (share by key, biases), `unify.door_share`, `turn_add`, the checks against the control.
