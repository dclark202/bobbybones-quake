# v0.3.1 at 06:30 Friday (run `duel_gru_v0_3_1`)

*v0.3 resumed from its 18:00 stop with the owner's pay table and the faster learning step, started 20:53 Thursday, to 16:00
Friday ([RUN_v0.3.1.md](RUN_v0.3.1.md)). 137 updates at 06:30. Nothing was stopped or changed during the night.*

## How the numbers moved overnight

**Against the control, v0.3's end** (160 ten-minute whole games a check, ten maps, seats swapped, aim level 3; a check's noise is
about ±4 points):

| Update | Frag share | Won-drawn-lost | His frags a game | v0.3's | In view him / v0.3 | His damage a minute | Mega share him / v0.3 | Speed him / v0.3 |
|---|---|---|---|---|---|---|---|---|
| 10 | 49.0% | 74-5-81 | 12.2 | 12.3 | 0.156 / 0.154 | 43 | 0.47 / 0.44 | 309 / 309 |
| 30 | 51.7% | 72-16-72 | 12.5 | 11.8 | 0.159 / 0.156 | 43 | 0.45 / 0.45 | 308 / 309 |
| 50 | 53.4% | 88-12-60 | 13.3 | 11.4 | 0.159 / 0.154 | 43 | 0.45 / 0.46 | 308 / 309 |
| 70 | 57.2% | 101-7-52 | 14.1 | 10.8 | 0.158 / 0.152 | 43 | 0.46 / 0.43 | 308 / 308 |
| 90 | 55.3% | 100-6-54 | 13.7 | 11.1 | 0.161 / 0.151 | 43 | 0.45 / 0.45 | 307 / 309 |
| 100 | 60.5% | 118-5-37 | 15.0 | 9.8 | 0.164 / 0.151 | 43 | 0.47 / 0.43 | 306 / 309 |
| 110 | 59.4% | 111-4-45 | 14.3 | 10.0 | 0.162 / 0.149 | 42 | 0.45 / 0.45 | 305 / 309 |
| 120 | **60.0%** | **110-5-45** | 14.4 | 9.9 | 0.164 / 0.149 | 42 | 0.45 / 0.44 | 304 / 308 |

By map (frag share %), first check and the last three: Blood Run 46 → 71 / 62 / 59; Aerowalk 55 → 58 / 53 / 49; Lost World
46 → 52 / 54 / 54; Sinister 51 → 64 / 57 / 58; Furious Heights 48 → 59 / 66 / 60; Battleforged 47 → 59 / 71 / 68; Campgrounds
47 → 53 / 61 / 62; Hektik 48 → 63 / 61 / 61; Toxicity 57 → 57 / 55 / 66; Cure 44 → 69 / 55 / 63. Nine maps of ten above
v0.3; Aerowalk is level.

**Collapse watch** (the last ten updates at each save; v0.3's last ten in the first row): no flag all night.

| Update | Rockets / rail / lightning in hand | Mega+red a minute | Frags a match-minute | Mega / red / yellow intentions |
|---|---|---|---|---|
| v0.3 | 0.21 / 0.10 / 0.49 | 1.82 | 1.99 | 0.16 / 0.21 / 0.22 |
| 10 | 0.27 / 0.12 / 0.42 | 1.99 | 1.28 | 0.14 / 0.18 / 0.20 |
| 40 | 0.20 / 0.09 / 0.50 | 1.76 | 2.45 | 0.17 / 0.22 / 0.23 |
| 80 | 0.24 / 0.10 / 0.48 | 1.84 | 1.96 | 0.15 / 0.20 / 0.21 |
| 130 | 0.21 / 0.10 / 0.50 | 1.76 | 2.22 | 0.16 / 0.22 / 0.23 |

**The trainer's own numbers** (means over twenty updates):

| Updates | Minutes an update | kl | Frags a match-minute | In view | Item lesson weight | Hop chains a minute | Pros' jumps cleared | Legs carry him |
|---|---|---|---|---|---|---|---|---|
| v0.3's last 10 | 6.3 | 0.019 | 1.99 | 0.140 | 2.0 | 10.7 | 54% | 63% |
| 1-20 | 4.3 | 0.020 | 1.71 | 0.112 | 1.77 | 12.0 | 57% | 70% |
| 41-60 | 4.2 | 0.018 | 2.54 | 0.157 | 0.83 | 9.8 | 50% | 57% |
| 81-100 | 4.2 | 0.018 | 2.20 | 0.139 | 0.10 | 10.3 | 56% | 59% |
| 121-137 | 4.1 | 0.020 | 2.12 | 0.145 | 0.10 | 9.2 | 59% | 49% |

**Aggression signs** (the checks, ten maps): his speed toward an enemy in view, by his own health plus armor (under 60 /
60 to 125 / over 125): update 10: −7 / 56 / 93 u/s; update 120: −14 / 46 / 81. Time exposed: 3.0% → 1.9%.

**Is it healthy? Yes.** No stall, no crash, no collapse; learning steady (kl 0.018 to 0.020). The faster learning step
holds: 4.1 minutes an update against v0.3's 6.3. The item lesson faded to 0.1 by update 85 and his mega and red armor
stayed exactly where they were: he holds the items without the lesson. He beats v0.3's end 60% of frags and 110 games to
45. The new pay does not count its own parts per minute in the trainer (stack differential and flat item pay are not
logged separately): read here by what they make him do.

## The pay as an equilibrium

What the night shows: **he wins the fights he gets, he does not seek more of them.** His damage a minute (43), the share
of time the enemy is in view (0.15 to 0.16) and the total frags of a game (about 24) are where v0.3's were; the frags
moved from v0.3 to him (12.2 → 14.4 a game against 12.3 → 9.9). He closes in about 10 u/s less at every strength and is
exposed a third less. That is what the zero-sum core pays: a frag, a hit and a stack lead are worth exactly what they cost
the other seat, so in self-play the copies trade evenly and the edge goes to better trading, not to more of it. The only
shared pumps are small: damage at 1.2:1 (about +0.1 for a 100-point trade each way) and knowing pay (0.38 of his time
known, about 0.1 a minute). Neither shows a sign of being farmed.

Against the five goals: weapon use (rockets, lightning, rail in hand unchanged) and positioning (less exposed, more won)
moved closer; beating humans should too, for the owner's complaint was paid-for fleeing, and that pay is gone. Two to
watch: **speed and movement** (hop chains 10.7 → 9.2 a minute, speed in the checks 309 → 304: the speed pay in games was
dropped by agreement; a small slide, not a fall), and **counterplay**: he cannot push a weak enemy he does not know is
weak (proposal 3), and no pay can fix that. **I propose no weight change now.** If speed keeps sliding by noon, the
equilibrium-safe lever is the hop bonus (paid on a running best, no pump), not the old speed pay.

## Physics, jumping and air control (the night's other work; RESULTS 2026-10-16 01:25, B-258)

Quake Live's movement measured case by case on a private server. Measures within 5% of the game: v0.3's simulator 1,088 of
1,892 on the test map and 266 of 520 on Blood Run; with five switches (`QL_FLOAT`, `QL_FWD`, `QL_LAND`, `QL_JUMP`, `QL_MOVE`)
**1,892 of 1,892 and 520 of 520**. Fixed: speed cut to whole units (every jump about 5% too high and long), the forward
key alone pushes in Quake Live and not in Quake 3 (why running rocket jumps landed short: now 30 of 30), landings,
Quake Live's chain jump and stair and ledge jumps. Off = today, proven; merged in main (11be809). Found: **Bobby has never
auto-hopped on the real servers** (the game needs a setting a bot never sends; `BOBBY_AUTOHOP=1` in the plugins, off).
Still off: a rocket's push on a standing player (5 to 15 units short), the jump pad's frame. His legs under the new
physics: item runs unchanged, the pros' jumps cleared 61% → 56%: **they need a short fine-tune first.** My start of it
at 01:30 failed in 90 seconds (a worker died) and reading its error was refused by the permission check; it is not
running. **Ready to add into v0.3.1? Not yet**: the physics is, the legs are not.

## Three proposals (each joins only at a restart from a save, after its ten-update test, on your word)

A ten-update test needs the graphics card, which the run is using: each test means stopping the run at a save for about
an hour (ten updates, then 4 maps of 16 games against the control and beside the run's own save) and resuming it.

1. **His legs learning from games (B-253 stage b)**: built, merged (27670f1), off = today proven (weight difference 0.0),
   on at a quarter rate proven to count only what it should. **Wait**: it would learn the old physics' jumps. Test it
   after the physics joins.
2. **Rocket jumps (B-252)**: the check against the game is done and the physics fix covers it; the rocket jump runs
   themselves (from the pros' take-offs and landings) are not built yet, and need the corrected physics underneath.
   **Not ready.** Next: build the runs on the corrected physics.
3. **The enemy's stack believed (B-257) with the hunt (B-256)**: built, merged (058ba62), off = today proven, the
   converted network answers as v0.3 (1.3e-6), the belief's error 18 points of health plus armor (a fixed guess: 64), a
   private-server game ran clean. Changes no pay. **I recommend it first**: it answers your play test directly (he
   should know you are weak) and runs on today's physics. One choice is yours: the hunt has to be opened out of an
   existing choice, for v0.3 never picks "nothing"; I suggest a share of the yellow armor (the tested copy: 30%, he
   hunted 7% of his time and closed on an unseen enemy at 58 u/s against 26).

**Suggested order**: (3) now, at a save; then the physics with the legs' fine-tune (a library rebuild, so a restart);
then (1) on the corrected physics; then (2).

## Questions

- Extend the run past 16:00? It is healthy and still rising (60% at update 120).
- Go for proposal 3's ten-update test (and the hunt out of the yellow armor at what share)?
- Go to retry the legs' fine-tune under the new physics (and to read the failed start's error)?
