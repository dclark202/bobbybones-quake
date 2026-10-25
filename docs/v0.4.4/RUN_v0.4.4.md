# v0.4.4 on one page: pay by win chance, first step (DRAFT)

*2026-10-25 (draft for the owner's review): the generation's goal (the owner, 2026-10-23: pay by win chance as the only game
pay; [../v0.4.0/PATH_v0.4.md](../v0.4.0/PATH_v0.4.md)). From v0.4.3's last save (the strategy head in, the "will be"
exemption and the level pull through Monday). Start: Tuesday morning on the owner's go. Before it: [../v0.4.3/RUN_v0.4.3.md](../v0.4.3/RUN_v0.4.3.md).*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## What it is

| | |
|---|---|
| The one new thing | **Win-chance pay** cross-faded in: a frame's pay = the change in his chance of winning (from the score and the clock), at weight w; w rises 0 -> target slowly, live, tied to the checks |
| What goes out with it | three shaping pays that do nothing for winning (below), faded as w rises |
| Second thing (after the first is in) | ❓ mid-game starts from people's games and moments before pickups (built 2026-10-25, off) |
| Equilibrium it aims at | the same play as v0.4.3 minus what the three pays bought (firing less, looking at doorways, pre-aiming for pay); everything else priced by what it wins. In self-play: zero-sum, "win the game" |
| Pass | level or better against v0.4.3's end; the win pay's share of his pay rising, the win rate not falling; the behaviour check (per map, against the pros) not worse |

## The parts

| Part | Detail | State |
|---|---|---|
| Win-chance pay | `WIN_PAY` in the simulator (frame pay = change in win chance, `sim/win_chance.json`) | ✅ built (on/off only) |
| Overtime | the last overtime frame reads 0 s left, not 120 (commit 4e52053) | ✅ fixed |
| The cross-fade weight | live `WIN_PAY_W` 0 -> target: win pay times w added, the retired pays times (1 - w); identity at w 0 proven | ⏳ to build |
| The critic's start | the value outputs learn the win pay from the shadow win value v0.4.3 trained all along (`--win-value`), not cold | ⏳ to build |
| His own win table | `tools/win_table.py` on his own games (whole games, checks), set beside the pros' table; the one used is the owner's call | ⏳ to build, 🧪 |
| The guard | as every round: a check under 50% holds w; under 45% (frag share under 48.5%) or two checks under 50% steps it back | ✅ (the watcher) |
| Measures | per check: games, frag share, the behaviour check per map, the pay ledger (each pay's share of the total), the decision report at the end | ✅ / ⏳ the ledger in the check line |

## The pays that go out first (the path's list)

| Pay | What it pays now | Why it goes | Equilibrium without it | State |
|---|---|---|---|---|
| Shot price (`SHOT_W`, `RG_FAR_PRICE`) | a cost per shot by weapon | firing well is priced by what it wins; the price makes him fire less | fires when the shot's expected damage pays for the exposure | ❓ |
| Watching the right spot before a sighting (`WATCH_PAY`) | pay for having the doorway in view when the enemy appears | the win value prices a good read itself | watches where the enemy is likely, when it helps win | ❓ |
| Pre-aim pay (`PREAIM_PAY`) | pay for the crosshair near where he appears | as above | pre-aims when it wins fights | ❓ |
| The big-weapon pay (`BIG_PICK_SEQ`, equal 0.10 since 2026-10-25) | 0.10 for each of RL, RG, LG once a life | today it is the weapon-variety scaffold (B-286) | recommended: keep it in v0.4.4, retire it in v0.4.5 once the weapon numbers hold | ❓ |

## Decisions for the owner

| # | Question | Recommendation |
|---|---|---|
| 1 | The win table: the pros' or his own | his own if it agrees with the pros' within noise; else the pros' (fewer games, but not his habits) |
| 2 | The target w for v0.4.4 | 0.5 (half the game pay by win chance) by the end of the day; 1.0 in v0.4.5 to v0.4.7 with the rest of the cross-fade |
| 3 | How fast w opens | +0.05 every 25 min on passing checks (about 4 h to 0.5) |
| 4 | Who he trains against under win pay (the path: "keep outside styles in the mix") | keep the long-term control in the league, the mid-game starts at 40%, and the people's moments as the second thing |
| 5 | The big-weapon pay | keep in v0.4.4 (above) |
| 6 | The people's mid-game starts | as v0.4.4's second thing, opened after w is at its target |

## Reminders for this round's planning
- The pros' jump-pad landings (`PAD_PRO`, branch `pads`, B-287): built and off; a later round's one new thing.
- The brain widened 256 -> 512: on the table, the test not yet run.
- Rocket jumps and the tricky movement jumps (B-284, B-212): important, not this round.
- The hindsight review of games against people before any network goes on the public servers.

## Schedule (draft)

| When | What |
|---|---|
| Mon daytime | the cross-fade weight, the critic's start, his own win table built and tested on the CPU beside v0.4.3 |
| Mon 19:30 | play test of v0.4.3; the owner's go on this card |
| Tue morning | v0.4.4 starts from v0.4.3's last save, w 0; opens on passing checks |
| Tue afternoon | w at its target; two checks; then the second thing if decided |
