# The remaining v0.3.x mechanics, before the strategy layer

*The owner, 2026-10-18: "we should make sure this guy is 'really good' before adding the strategy layer". The strategy layer
(the v0.4 head, [PROPOSAL_v0.4.md](PROPOSAL_v0.4.md)) waits until these are tried. Order is a suggestion; the owner decides.*

## Now (v0.3.6, from 2026-10-18 night)
- **Rockets:** aim at the wall behind the enemy and at the floor, pre-fire at the pros' places (rocket, grenade, plasma), blind rockets free ([ROCKETS_v0.3.6.md](ROCKETS_v0.3.6.md)).
- **Rail at range:** the long-range rail pay (600 to 900 units). The pros rail 78% of their fire at 900 units; v0.3.5 has 8% of his frags by rail.
- **Speed in games:** strafe jumping at pro speed while the enemy is unseen. v0.3.5 moves about 300 u/s in games and 333 alone (speed pay 0.25, 0.35 if needed).

## Next (v0.3.x)
1. **Rocket jumps** (B-252, B-212): the rocket-jump runs built for v0.3.6, held back at its start (owner, 2026-10-18). Then the plasma climb.
2. **The jumps he lost:** in the v0.3.5 play test he missed jumps he used to make; 59% of tries make it in jump runs. Circle jumps (Aerowalk's red armor) included (B-204, B-209).
3. **Fighting while moving:** he slows to about 288 u/s with the enemy in view. Strafing and dodging rockets in a fight, air control.
4. **Weapon switching and combos:** rail then lightning, rocket then rail; how fast he switches and when.
5. **The gauntlet, rarely:** only where it is right (out of ammunition at close range, a humiliation finish). A small item, not a style.

## Later (the owner: "those come later")
- **Ledge grabbing**: catching a ledge at the top of a jump.
- **Stair "sliding"**: holding jump to go up stairs without losing speed.
- **Ledge jumps**: jumping off an edge to keep or gain speed.
- Each needs the game's movement measured first (`plugins/movetest.py`) and checked in the simulator (`sim/q3`) before any lesson: what the game does that the simulator may not.

## Not here (strategy, v0.4)
Predictable paths, falling for spam out of a teleporter, the same routes every time (owner's v0.3.4 play test), item timing, reading the enemy: the head's work.
