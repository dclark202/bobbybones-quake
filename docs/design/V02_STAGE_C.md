# Stage C of the attention model: one way of moving. The build's specification (2026-10-11 night; built in copies while v0.2 trains)

The owner, 2026-10-11: "Make sure parts B and C are built along the way too." Stage A is training as v0.2
([../runs/MANIFEST_v0.2.md](../runs/MANIFEST_v0.2.md)); stage B is in [V02_STAGE_B.md](V02_STAGE_B.md). This page says
what stage C is in the simulator and the trainer. As in stage B every part is behind a switch that is off by default,
and with all of them off fixed runs must be bit for bit what they are today.

## Where he stands

His legs are a second network (`move_v15n`) that he switches on and off. On them he is as fast as the pros (at 400
units a second or more 20% of the time; the pros 17.5%). Over a whole game he is not (9.4%), for three reasons measured
on 2026-10-11:

| Cause | Measure | Where it is addressed |
|---|---|---|
| With no target his legs cannot carry him | the intention "nothing" 13 to 23% of his time, on his own feet at 270 | stage B part 2 (a target that is never "nothing") |
| His legs hold his view: he cannot run and look | three of four stretches on his legs end at a glimpse of the enemy | here, part 2 |
| On his own feet he does not strafe jump | his own movement outputs were last taught by the movement network of v14, which had not his hands | here, part 1 |

## Part 1. His own movement taught by his legs, then the switch weaned

Why: "blend the two styles". What his legs do in the stretches he chooses them is exactly what he should be able to do
himself: the same hands, the same inputs, the same moment. It is the one place where a movement label is never wrong
for the situation, because it is the movement that was made.

- Simulator, switch `LEGS_LABEL=1`: `info["legs_lab"]`, for every player a frame the movement network's four choices
  (forward and back, sideways, jump and crouch, the view's turn) on the frames his legs carried him, and "no label"
  elsewhere. Changes nothing he does.
- Trainer, `--legs-teach <weight>` (0 = off): on the frames with a label, his own four outputs are pulled toward it
  (cross-entropy, the keys only on the frames his hand reads them). `--legs-teach-trunk` (how much of it reaches the
  shared layers, as `--teach-trunk`), `--legs-teach-warm` (minutes from nothing to the weight: a teacher at full
  weight from the first update has cost him aim before). Written with every update: the loss, and how often his own
  choice is the label's, by output.
- Weaning, switch `LEGS_KEEP=<share>` (1 = as today): at the start of a stretch on his legs a draw; with the chance
  1 - share the stretch is **withheld**: he asked for his legs and moves himself. The label is still worked out and
  taught, and the input "his legs carried him" says truthfully that they do not. Counted apart: his speed (time at 400
  or more, units a second gained in the first two seconds) in withheld stretches beside carried ones.
- The plan for a run: `LEGS_KEEP` 1 with the teaching on until his own choice is the label's about as often as two
  runs of the movement network agree with each other; then the share falls in steps (0.75, 0.5, 0.25) while his speed
  in withheld stretches stays within a tenth of the carried ones; at 0 the switch has no work left and his movement is
  one network's, learnt from the game.
- Not paid. No label outside the stretches he chose: the movement network runs for an item, and in a fight that is
  the wrong lesson (v14 lost a map to exactly this within an hour).

## Part 2. Run and look

Why: his legs take his view's turn, because strafe jumping is made with the view. A pro keeps most of his speed with
his view off his way (sideways hops, half-beat, a look back in the air); the movement network was never asked to.

Two ways, the first built first:

1. **Through part 1.** Once he moves himself the game pays him for looking and for speed at once, and nothing holds his
   view. Measured: the share of his fast stretches that end at a glimpse of the enemy (today three of four), and his
   speed two seconds after a glimpse.
2. **Legs that take a look direction** (the movement trainer's `--look`): in a share of its tries a direction is given
   (up to 120 degrees off his way) and progress is paid only while his view is within 30 degrees of it; the direction is
   two more inputs of the movement network. In games, switch `LEGS_LOOK=1`: while his legs carry him and he believes
   the enemy somewhere (stage A's belief, under 20 s old), that direction is given to his legs; with no belief they run
   as today. The movement trainer and the switch are built; the network needs about three hours of training on the
   graphics card, which the run holds: after v0.2.

**For the owner to decide before the second is used in a run**: who chooses the direction. As specified it is his
belief of the enemy, always: simple, and what a pro mostly does, but a rule. The other form is an output of his own
(free, the believed enemy, the way ahead): his choice, at the price of one more thing to learn.

## Part 3. The judges (not built)

The owner on the judge of pro-like movement: "Yes, eventually. Don't build it now but remind me of it after tonight's
run". It belongs here: a guard while part 1 weans the switch (does his own movement stay inside what a person's looks
like), with a second one for movement in a fight. Raised again when v0.2 ends.

## The order

Part 1 is built first and can go into the run after v0.2 with the teaching on and `LEGS_KEEP` at 1: it changes no
behaviour at its start and its numbers say when weaning can begin. Part 2's second way is trained when the card is free.
Each part arrives as a patch script against the simulator and the trainer as they stand in v0.2, with its checks.
