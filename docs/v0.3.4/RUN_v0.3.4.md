# v0.3.4: one page (prepared 2026-10-17; starts on the coordinator's go)

**Start**: v0.3.2's save at update 140 (`keep/policy_switch.pt`), converted with every new part at zero: at the start he plays
exactly as v0.3.2 did. League: v0.3.2's last eight snapshots; control: v0.3.1's end. Until Sunday 12:00.

- **His own hands get the legs' help** (A): where he drives himself, his movement keys and turn may lean on what his legs
  would do, by an amount his memory sets (starts at zero).
- **He can correct his legs while they drive** (B): the legs' choices become a blend of theirs and his, starting as theirs alone.
- **He drives himself in item and jump runs** (C): the legs are off there; once his own speed in those runs reaches 325, the
  switch to his legs is made a little less likely in games after each such update (up to a limit).
- **Walking lets go of jump** (D), as the game needs. **Hop pay is silent near the enemy** (E): heard in 4 s, believed within
  700 units, or holding a place.
- Kept: his turn correction on his legs (v0.3.2), his legs' features in his memory (step 3).
- **Solo runs at 20% of his time at first** (item runs 10%, jump runs 10%); the second .cmd puts them back to 5% + 5% at a save,
  once his run speed reaches 325.

**Watch**: `solo` (his run speed, the fade, the switch in games), `gate`, `legs.share`, `turn_add`, `hop`, the checks against
the control.
