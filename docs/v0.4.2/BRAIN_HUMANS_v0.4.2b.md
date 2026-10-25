# v0.4.2b: the brain models every opponent as Bobby (for review)

*2026-10-24 ~21:00. Written for an outside reviewer: the problem, the context, what we are doing about it tonight, and what
we would like suggestions on. Status: v0.4.2 paused at update 160; the fix is being built; it resumes overnight as v0.4.2b
and runs to noon on 2026-10-25, when the owner decides.*

## 1. Context

**BobbyBones** is a Quake Live duel bot (1v1, ten maps) trained from scratch by self-play PPO in a fast simulator built on
ioquake3's movement and collision code, then played on real Quake Live servers through a minqlx plugin. Human limits are
built in (reaction time, flick speed, hand noise; sight with line of sight; hearing). About 3 M weights; about 100,000
player-hours of self-play on the current line.

**The network (v0.4.x), in three parts:**

| Part | What | Trained by |
|---|---|---|
| **The brain** (GRU 256, ticks every 0.2 s) | reads all 868 inputs (his senses: what he sees and hears, his stack, items, clock); answers questions about the enemy: where he is now (place, spread, map zone), where he will be in 1/2/4 s, what he is going for, when he will appear, who wins the race to the next mega / red armor, his stack band and weapon | **hindsight labels only**: after each self-play game, the enemy's true place and actions grade the brain's guesses; no reward gradient |
| **The token** | the brain's answer, fed to the hands as one more token of their attention (v0.4.1) | – |
| **The hands** (encoder 868→256→256, attention over 55 tokens, GRU 512, 13 action heads, values) | moves, aims, fires, chooses an intention (an item, a weapon, a holding place, "the enemy") | PPO on the game's pay (frags, damage, item flats, shaping pays) |

**The run that showed the problem: v0.4.2** ("the old belief faded out of the hands"). Until v0.4.1 the hands also read
about 76 rule-made input columns: a hand-built belief of the unseen enemy (an extrapolated place, the way to it, his stack
filter, pre-fire spots, the emergence point). v0.4.2 multiplied those columns by (1 − g) in the hands only, with g opened
0 → 1 over the day, and moved the simulator's own readers of that belief (the legs' look point, the hunt, the item rule's
contest test, the openings pay) to the brain's answer on the same draw. **At g = 1 (reached 18:40) the hands know where the
enemy is only through the brain.**

**The checks said it worked.** Every 20 updates, 160 ten-minute games (ten maps, seats swapped, aim level 4) against the
previous version and, every fourth check, a long-term control:

| Update | Fade g at the save | Against | Games | Frag share |
|---|---|---|---|---|
| 70 | ~0.5 | v0.4.1's end | 81-79 (50.6%) | 49.8% |
| 90 | ~0.65 | v0.4.1's end | 92-68 (57.5%) | 51.5% |
| 110 | 0.80 | v0.4.1's end | 88-72 (55.0%) | 52.1% |
| 130 | ~0.95 | v0.3.10's end | 109-51 (68.1%) | 58.5% |

## 2. The problem

**The owner played v0.4.2 at full fade (save 140) on a local server, 2026-10-24 evening, and the play was bad.**

- **Campgrounds: the owner won 17-3.** Items were roughly even (red armor Bobby 13, owner 9; mega 7 / 9; yellow 7 / 11).
  The gap was fights and weapons: Bobby held the lightning gun 65% of the game and never held the railgun; the owner held
  the rocket launcher 62% (took it 23 times to Bobby's 7) and the rail 16% (21 of 29 hits, 7 kills). Most of Bobby's deaths
  came with the owner in view, low on stack, lightning in hand at 230-700 units.
- **Hektik: camping armor spots.** In the first 5.5 minutes Bobby spent ~100 s within 200 units of an armor or the mega,
  mostly while the item was not up (yellow armor: 37 of 53 s waiting for its spawn), and engaged little.
- The owner's read: **"he's using as reference WHAT HE WOULD DO not what I am doing, so he's often in weird spots relative
  to my play."** And: "He may play better against himself but it's worse overall."

**What the live mind log showed** (the brain's answers recorded 5 times a second beside the owner's true place, Campgrounds):

| Measure | Result |
|---|---|
| Place error while the owner was unseen 3-6 s / 6-15 s | 400 / 560 units (last-seen place as the guess: 850 / 1,060): **tracking is good** |
| Truth in the brain's three likeliest zones | 60-90% |
| Sightings that were a real surprise (P(appear < 1 s) < 0.15 a tick before) | 11 of 94 |
| The 1 s / 2 s / 4 s predictions | 466 / 557 / 621 units, against "he stays where I believe him now": 460 / 578 / 717: **no better at 1-2 s** |
| The owner's target (his next big item or weapon within 15 s), top guess | **24% right**; most common miss: armor guessed while he went for the **rocket launcher** |
| The item race (mega / red armor), sign right | 61%; six times on the mega the brain thought Bobby was 1-2 s ahead and the owner took it |
| P(appear < 1 s) | predicted 0.23 on average, happened 0.12 (ordered right, too high) |

## 3. Diagnosis

**The brain has only ever been taught by self-play, so its opponent is always a Bobby.** "Where will the enemy be" has
been learnt as "where would a Bobby be". In training Bobby chooses mega/red/yellow armor about 63% of the time and the
rocket launcher 8%; his item choices are shaped by the hand-made item rule (an intention teacher with a 10% floor) and by
flat item pays (mega 0.35, red 0.30, yellow 0.15 on pickup; nothing charges waiting at a spawn). So the brain predicts
armor, the hands position against a Bobby who would come for it, and waiting at the spawn looks right. Against himself this
is accurate, hence the checks; against a person who controls the rocket launcher and comes to him, it is wrong.

The fade did not create this; it removed the hand-built belief that partly masked it (that belief extrapolated the enemy's
last motion and did not model his intentions). v0.4.3's planned strategy head would plan from the same biased picture.

## 4. What we are doing (tonight, owner's go)

1. **Paused v0.4.2 at update 160** (20:31, with its optimizer). Fallbacks kept: v0.4.1's end (update 320) and v0.4.2
   update 160, each with optimizer and league (`data/fallbacks/`, untracked).
2. **A brain lesson on real human games**, supervised, with the same hindsight targets the brain already learns:
   - **Pro duel demos (~7,650 on the ten maps; the owner: "the highest quality data we have")**: inputs rebuilt in today's
     868 layout through the simulator's own `observe()` from the demo's game state, from the recording player's seat; labels
     **masked** to what the demo holds (the enemy only while the server sent him, roughly while in view; his pickups;
     reappearance times and places; the 1/2/4 s places at moments he is present then).
   - **Play-test and public-server sessions** (Bobby against people): the server's 40 Hz record of both players' true
     state, the hidden times included (full labels), and Bobby's own recorded inputs (directly usable for the v0.4.x
     sessions; older layouts mapped or left out).
   - Labels reproduced from the recorded truth exactly as the trainer makes them, checked against the simulator's own labels
     on simulator games first.
3. **An offline fit** of the brain and its readouts only (never the hands), from a copy of save 160, on human data mixed with
   fresh self-play data so it still reads a Bobby. Held out by file: some demos and the owner's play-test sessions of today.
   Before / after on held-out human games and on self-play: place error by seconds unseen, top-3 zones, 1/2/4 s errors
   against "stays put", target top-1, appearance calibration, the readouts' losses; and **the effect on play** (how far the
   hands' action distribution moves with the tuned brain, KL per frame and argmax changes).
4. **v0.4.2b**: the run resumes from save 160 with the human lesson **inside** the run (each update the brain's lesson
   mixes a batch of human moments with self-play; the human share a live setting), so self-play does not pull the brain
   back. Faded in over 2-6 h (length, human share, and whether to start from the old brain or blend toward the offline fit
   chosen from the measured play effect), with the "in control" shadow readouts on (no effect on play).
5. **Guard for this run:** checks every 20 updates as usual and reported, but **no automatic hold or rollback on games**
   (the owner: "it's fine if the games dip. He's unusable in his form so either we do this and the fix works or we go back
   to v0.4.1"); only a breakage floor (games under ~35% or the training step jumping: the human share held, a message
   sent). Judged by the held-out human numbers and the owner's next play test with the mind view.
6. **Then** the strategy head (built and tested, bit-identical at gate 0) as the next round; pay by win chance after that.

Equilibrium (the project states every change by it): a supervised prediction lesson with no pay; in self-play the brain's
best answer is still Bobby's true behaviour, and with human games mixed in it becomes "the opponent's behaviour, read from
how this opponent plays". The hands' equilibrium is unchanged (the same pay); only what they believe about the enemy moves.

## 5. Risks we see

- **Demo labels are partial**: a demo has no truth for the enemy's hidden path, so tracking-while-unseen learns only from the
  sessions (fewer hours, and people playing Bobby, who adapt to him). Masking must be right or the brain learns "hidden = gone".
- **Distribution shift in the senses**: demo inputs are rebuilt from a pro's seat (his view, his weapons, his aim), not
  Bobby's; some inputs the demo cannot supply (the enemy's health, exact sounds) are filled in.
- **The hands were trained on the old brain's answers**: a changed token shifts play; the fade limits it, but the checks
  against Bobby may dip and say little about the human-facing gain.
- **Self-play keeps teaching "the enemy is a Bobby"**: the human share has to be large enough to hold, small enough not to
  wreck the self-play predictions the hands also need.
- **The real issue may be wider than the brain**: the hands' habits (lightning everywhere, no rail, waiting at spawns) come
  from self-play and the shaping pays too. A better picture of the opponent may not change them without the head and
  pay by win chance.
- **Opponent diversity**: training opponents are all Bobby (his league of older selves, anchors, a few scripted styles); the
  hands never meet a rocket-launcher controller in training.

## 6. Questions for the reviewer

1. Is the diagnosis right, or is something else more likely (e.g. the fade itself, the hands' reliance on the token)?
2. Is "train the brain on human games" the best first fix, before the strategy head? What would you do instead or as well?
3. How to use partial-truth demos best: masking only; or also a learned model of the hidden path; or weighting by how much
   of the enemy the demo holds?
4. The mix: what share of human vs self-play in the brain's lesson, and should it change over time?
5. The fade: swap in the offline-fitted brain, blend weights, or only let the in-run lesson move it? How long?
6. How to judge success overnight without a person playing (which measures on held-out human data predict a better play test)?
7. Should opponent diversity in training (scripted "pushers" that take weapons, or league opponents conditioned on human
   styles) come with this or next?
8. Anything in the plan that could make him worse in ways the checks would not show?

Related: [RUN_v0.4.2.md](RUN_v0.4.2.md), [DIP_v0.4.2_try1.md](DIP_v0.4.2_try1.md),
[../v0.4.3/RUN_v0.4.3.md](../v0.4.3/RUN_v0.4.3.md), [../v0.4.3/ARCHITECTURE_v0.4.3.md](../v0.4.3/ARCHITECTURE_v0.4.3.md),
[../v0.4.0/PATH_v0.4.md](../v0.4.0/PATH_v0.4.md).

## 7. The review (2026-10-24 ~21:15) and what was adopted (the owner: "adopt anything you think is useful")

**Adopted for v0.4.2b:**

| # | What | Why |
|---|---|---|
| 1 | A domain-leak check before the fit: each of the 868 inputs tested alone for telling demo (and server-session) frames from simulator frames; a giveaway column is matched or neutralised for the brain | otherwise the brain learns "this is a demo" and keeps Bobby priors in live play while the held-out demo numbers look good |
| 2 | No hidden-time position labels from demos (masking on "present later" keeps only the times he walked into the recorder's view: "hidden enemies come toward me"); demos grade the target, the race where observable, appearance timing, and positions while present; hidden-time positions come from the sessions (full truth) | the visibility selection bias |
| 3 | Check that the brain's memory is not reset at Bobby's deaths | reading this opponent's style within a game needs it |
| 4 | The start set by the measured play effect: KL < 0.015 and intention changes < 8% → warm start from the offline fit (anchored to save 160), human share 0.20 → 0.35 over ~90 min; else save 160's brain, 0 → 0.35 over ~3 h | – |
| 5 | Human share ~30-35% of the brain's lesson (~20% demos, 10-15% sessions), constant once reached | self-play would pull it back |
| 6 | The overnight scoreboard on held-out human data: weapon-target recall, the 1-2 s gain over "stays put", appearance calibration, race false leads, a counterfactual replay of the hands on the owner's sessions (old vs new brain); the hands' attention on the brain's token logged every update | measures that predict a better play test |
| 7 | Label checks on both seats, two asymmetric maps | frame / seat bugs |

**To verify first (doubted):** whether demos hold the enemy's pickups while he is out of view; whether any simulator reader uses the brain's P(appear) (the readers read its believed place); whether the 0.23 vs 0.12 appearance figure uses the label's own definition. The 1-2 s predictions are not read by the hands in v0.4.2 (only by v0.4.3's head), so they did not break pre-fire; the hands lost the old pre-fire columns to the fade.

**Not now:** keeping the simple motion columns unfaded (a rule back in); weapon pickup pays (the fix is pay by win chance; for the pay review). **Next, as its own change (v0.4.2c):** opponents who push and take weapons in a share of training games (the opponent seat's intention steered to the rocket launcher / rail / the enemy), so the hands practise against a weapon controller.
