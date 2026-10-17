# One movement network: the plan (B-259; written 2026-10-16 night)

The owner's direction, 2026-10-16 evening: "there should only be one actual movement network ultimately"; "a precursor to
doing the strategy layer. And getting there is our immediate goal"; and generally smaller steps do better.

## Where he is

He has two drivers. His own network (the hands) fights, aims and chooses targets. His legs are a small movement network,
inside him since v0.3.1 as a branch, and they strafe jump along his way. A switch (output 11) decides who drives. While
the legs drive (54% of his game time) they own his keys, his left-right turn, walk and zoom, and know nothing of the
enemy. That gives the owner's "moving mode" tunnel vision, and he never walks.

## The steps

Every step:
- sits behind a switch, off by default
- starts exactly where the last left off: the network plays the same on its first frame, proved by fixed-seed replays
- passes ten updates and the check against the control before it joins a run
- joins only at a save

| Step | Change | Switch | Built | Its gate |
|---|---|---|---|---|
| 1 | Legs that look: while they drive, his view stays within about 30 degrees of where he believes the enemy, from his own senses only. Plus the turn correction: his own network adds to the legs' turn, starting at zero. | `LEGS_LOOK`, `LEGS_TURN_ADD` | v0.3.2, 2026-10-16 night | legs speed and jumps cleared within 2 points of v0.3.1's; the share of moving time with the view on the believed enemy rises; the checks hold against v0.3.1's end |
| 2 | Corrections on all the legs' outputs: keys, walk, zoom, the same way as the turn | (with step 1's design) | after v0.3.2's report: it extends step 1's correction | the walking share rises; damage taken while on the legs falls; the checks hold |
| 3 | The legs' 256-number layer feeds his memory through a door that starts shut | `--legs-feat` | building 2026-10-16 night | his own speed and hop chains on the frames he moves himself rise; the checks hold |
| 4 | When his own network drives, the legs' choice is a guide: his logits + w × the legs' logits, w learnt from 0 | `--legs-guide` | building 2026-10-16 night | the agreement between his own choice and the legs' on switch-off frames rises (the convergence measure) |
| 5 | Retire the switch: first a bias toward the legs as the guide, then the switch output removed; one set of keys and one turn | to build | after 3 and 4 have run | the checks hold with the switch gone; speed within 2 points |
| 6 | Clean-up: the legs branch is a layer of his network at the full learning rate; the legs' inputs are a token or a group of the encoder | to build | after 5 | v0.4's head is built on top of this |

## How long each step trains before the next

A step is ready for the next when two things hold:
- its new part has moved and settled (the correction's size, the door's norm, the guide's w stop climbing from check to check)
- three checks in a row, about 30 updates or 2 to 3 hours, read level or better against the control

Steps 2 and 3 are tested while the run is paused, so they go in at the run's planned stops, not in the middle of a night.

| When | What |
|---|---|
| Fri night to Sat 19:00 | v0.3.2 = step 1 (about 280 updates) |
| Sat 19:00 | play test; the ten-update tests of step 2 and step 3, one after the other (about 3 hours of the card); the ones that hold go in as v0.3.3 overnight |
| Sun to the week | step 4 tested and folded in the same way; steps 5 and 6 built and tested; then v0.4's head on one movement network |

## What is watched at every step

In `metrics.jsonl` and the watcher's lines:
- the legs' share of his game time
- the view on the believed enemy while moving
- the walking share
- legs speed and hop chains, his own speed when he drives, jumps cleared
- damage taken while on the legs
- the switch-off agreement (step 4 on)
- the checks against the control, by map

Not done: no step grades his keys against the legs. The two times that was done (`--legs-teach`, 2026-10-13) cost him the
game within 20 updates.
