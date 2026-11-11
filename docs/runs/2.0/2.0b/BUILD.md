# 2.0b: the build (branch `b20b`, 2026-11-09)

*The card: [CARD.md](CARD.md); the measurements: [MEASURED.md](MEASURED.md). Every part of the card is built as written (rule 10); a
detail the card leaves open is decided from its intent and recorded here. The owner's go, 11-09 evening: "continue the build and start it
when it's ready"; the length: to 16:00 on 11-10 ("sure 16:00 is fine").*

**Marks:** ✅ built and tested · 🔨 in work · ⏳ to build

| | Part | Where | State |
|---|---|---|---|
| 1 | The table a map: sight between the walking points, the reach (1.5 s, teleporters as one-way links), by the line's length; the grid (the nearest point of a 32-unit cell: the zones' grid), the tables by zone, the points' neighbours | `tools/run/space_score.py score` → `data/maps/space_<map>.npz` (the run's ten maps; 1.3 to 5 MB) | ✅ |
| 2 | The weapon table (tracked: the servers need it) | `sim/space_weapon.json` (from `space_score.py edge`) | ✅ |
| 3 | The lookup, plain numpy: `at`, `threat`, `edge`, `zone_cover` (24 zones and the aggregate), `safer`, the same against a spread of places | `sim/space.py` | ✅ the same numbers as the measurement tool's on 300,000 recorded places; the edge and the cover zero-sum between the seats; 9.3 ms for 10,000 players, all of it. The grid's point is the tree's nearest in 74% of places (else a neighbour, a cell away) |
| 4 | The truth columns `SPACE_TRUTH=1`: `sp_ok`, `sp_thr`, `sp_put`, `sp_edge`, `sp_agg`, `sp_z0..23` | `sim/duel_env.py` (`_space_true`, `aux`); `sim/duel_env_ffa.py` regenerated | ✅ `tests_env.py`: 18 checks; off, the simulator is 2.0a's frame by frame (`sim/duel_env_20a.py`, the frozen copy); the group module the same as the duel module at two players with every switch on (2,000 frames on Blood Run: `testlab.bsp` is not in `data/maps`, so `tools/ffa_check.py` as written cannot run) |
| 5 | Part 1, the readout: `--space-read`, its own layers (768 → 128 → 27) and Adam, live `SPACE_W`, the record `space` in `metrics.jsonl` (the skill by group) | `sim/spaceread.py`, `sim/train_duel_rnn.py` (beside every site of `--fight-odds`) | 🔨 built; tested by `tests.py` |
| 6 | Part 2, the inputs `SPACE_IN=1` (a `PLAY_VAR`): group "b20b space" (8) and "b20b targets" (3 an intention: 51), times the live `SPACE_GATE` (a `PLAY_VAR` too: a save plays at its gate) | `sim/duel_env.py` (`_sp`, `_sp_bel`), `docs/INPUTS.csv` (1053 in the group module), `sim/attn.py` (tokens "space", "targets"), the trainer's offsets, `sim/head_data.py`, the checks' `fit_list`; `tools/b20b_init.py` (`add`, `widen-league`, `same`) | 🔨 built; `tests_env.py` ✅, `tests.py start` ✅ (0 actions differ on 400 frames x 8 seats; at 64 seats 1 action of 358,400 differs, the float's last place) |
| 7 | Part 3, the pay: `EDGE_PAY`, `COVER_PAY`, live, their ledger terms "edge" and "cover" | `sim/duel_env.py` (`_space_pay`, after the blend: not faded) | ✅ `tests_env.py`: zero-sum every frame, the dial's arithmetic, the ledger sums to the pay; 🔨 in the trainer: `tests.py ident`, `live` |
| 8 | The recorder: the brain's place readout beside the truth (measurement 4: belief against truth) | `tools/run/cypher_measure.py` | ⏳ **not built**: the gate opens at update 30 without it having been read |
| 9 | The checks' space measures | the readout's record carries, every update, his share of frames under a threat over 20 and with the edge under −10 (the training's own frames) 🔨; the same of every check's games (`space_score.py` on a check's records) | ⏳ the per-check part **not built**: the checks carry Cypher's measures only |
| 10 | The run's files: `make_files.py`, `start_live.py`, `ramp_20b.py`, `start.ps1`, `tests.py`, `tests_env.py` | `docs/runs/2.0/2.0b/` | 🔨 the settings check against 2.0a's command passes (only `--run`, `--minutes`, `--space-read` and the five set lines differ); `live_accept.py`: the start's file and the ramp's 102 files accepted |
| 11 | The plugins and the export | `plugins/`, `sim/export_duel.py` | ⏳ after the run; **no deploy of a 2.0b network before it** |

## Decided in the build

| Detail | Decision | Why |
|---|---|---|
| The nearest point of a place in the simulator | the 32-unit cell's nearest walking point (a grid), not a tree | no scipy in the simulator's workers or on the servers; the zones do the same |
| The cover of a zone | from the zone's mean threat (a table by zone), not point by point | 24 lookups a player; the truth and the inputs use the same |
| The scale of the cover | 10 damage a second more than the enemy = the zone is his (`COVER_SCALE`) | the 95th percentile of the edge is 17.9 |
| **His belief of the enemy's place is one place, not a spread** | the simulator has the brain's answer as a point (`brain_bel`, as every reader of `BRAIN_READ`); the table spreads it over the ground the enemy can walk to in 1.5 s. Seen: the place he sees. No belief: the inputs are zeros and the first says so | the card says "a spread of places"; the brain's zone odds live in the trainer, not in the simulator. A wider bubble for an older belief is a next step, not in this run |
| The enemy's weapon in the inputs | the one last seen in his hand; the machine gun before any sighting and after the enemy's death | his own senses; the truth columns and the pay use the weapon truly in hand |
| "Along the way" to a target | the most threat on the next six points of the walking map's way to it (an item's); a holding place: its own place | the walking map's own next-point table; cheap |
| The inputs' gate | `SPACE_GATE` multiplies the 59 columns in the simulator; the network's weights on them start at zero | at gate 0 the inputs are exactly zeros; opening is slow twice (the gate, then the weights) |
| The gates on the clock | `SPACE_GATE` over updates 30 to 60, `EDGE_PAY` over 60 to 100, whatever the readout reads; a readout not above its base rate at update 30 is a MAJOR line | rule 6: a ramp never holds on its own; the card's "when the readout beats its base rate" becomes a report |
| The item ground's weights (`COVER_PAY`, at 0) | the mega, the red and the yellows 1 while there or back within 10 s, else 0.3; rockets, rail, lightning gun 0.3 | "by their clocks", the card; not opened in this run |
| The pay after the blend | not faded by `FADE_V` / `WIN_W` (both 0 here), as `WIN_SHAPE_K` | a term of its own in the ledger |
| The readout's ring | every second tick of the brain (0.4 s), one rollout long | half the fight odds' memory; the truth changes slowly |
| The held-out maps (House of Decay, Dismemberment) | no table: their columns, inputs and pay are zeros there | no walking map under `data/maps/nav_<map>_sim.json` (measurement 7); the ten maps of the run have theirs (Campgrounds built 11-09 evening) |
