# v16: his pay, his rounds, his opponents (proposals of 2026-10-11 evening; nothing here is built)

The owner, 2026-10-11: "can you just take a second think about if there's any signal in the pro demos that we're
overlooking or not taking full advantage of? Or if there's better ways to reward his play in training to get us towards
these goals, changes to architecture, etc." The model itself is [V16_ATTENTION.md](V16_ATTENTION.md); the stages are
[../v0.2/MANIFEST_v16.md](MANIFEST_v16.md). Every change to his pay below is the owner's call.

## 1. Three reasons in the trainer why he plays moment to moment

| | As it is (read from the code) | What follows |
|---|---|---|
| **How far ahead he counts** | his discount is 0.999 a frame at 40 frames a second (`--gamma 0.999`): a reward 25 s ahead counts 37%, one a minute ahead 9% | a mega's cycle is 35 s, a red armor's 25 s; holding a lead, denying an item, a position for the next fight are nearly worthless to him. Pay for a game's result changes nothing while this stands |
| **How far back his memory is trained** | a training sequence is 384 frames, 9.6 s (`--steps 384`); what he remembered before it is carried along but nothing teaches him to keep it | he can learn "the enemy went left three seconds ago"; "he took the red armor twenty seconds ago" stays by chance only. The tokens that say such things outright (the enemy as believed, item clocks as he knows them, his own last pickups) are the right fix, more than a larger memory |
| **Who he plays** | his last eight selves, two older networks, scripted opponents | nobody waits for him on his usual way and nobody pushes him when he is weak, as the owner did on the server. Being predictable costs him nothing in training, so no variety is learned |

## 2. Proposals

| # | What | Why | Cost | Needs |
|---|---|---|---|---|
| 1 | **Two value estimates**: the fight's pay counted over 25 s as today, the game's pay (items, the result) over about two minutes (0.9998) | the first row above. His hands stay on the short count (aim needs it); his target and way get the long one | small: one more output, a second sum in the trainer. In stage B of the manifest already; I would bring it to stage A | nothing new |
| 2 | **Pay the change in his chance of winning the game**, in whole ten-minute games: a frag is worth what it moves that chance, by the score and the clock | one rule gives "defend a lead late", "take risks when behind", "a frag at 10 ahead is worth little" without a pay for any behaviour. The chance by score and clock is a table from the pros' games (after the parser's fix, B-218) or from his own | whole games are slower to learn from; the table is an hour's work | the owner's word (it replaces the flat pay for a frag in those games); he said "Yes" to pay for the result |
| 3 | **An exploiter in his league**: a second network trained only to beat the current Bobby, frozen and renewed every few hours, a standing opponent in a share of his games | the third row above. It finds his habits (the same stairs, the same way to the mega, closing when weak) and he must then answer them. Variety and counterplay get a price without our paying for variety | a fifth to a quarter of the simulators for the exploiter's own training; it will also find faults of the simulator (useful, but they must be read) | the owner's word on the share |
| 4 | **Rounds that begin from moments of pro games** (places, stacks, weapons, item clocks, score, time left), and from moments of his games against people on the server | today a round begins from a spawn and lasts two minutes: he hardly meets "ahead by two with ninety seconds left" or "stacked against a fresh spawn". The demos hold thousands of each | needs exact states: after the converter's and the parser's fixes (B-219, B-218) | decision 3 of the manifest ("drawn states or only whole games") |
| 5 | **A judge of pro-like travelling for his legs**: a small network learns to tell two-second clips of the pros travelling from his (speed, the angle of view to movement, air or ground, turn rate); his legs are paid a little for clips it cannot tell apart, beside the pay for getting there | "more speed per jump, maintaining speed for longer": it pays the whole shape of a pro's run, not one number. For movement only; never for aim (2026-10-04) | a day to build; the judge must not see anything the pros' demos and his runs record differently (a fault there is what it would learn) | approved in principle on 2026-10-10 beside a pay for speed gained from hop to hop (B-211: "the rule to be shown to him first"); decision 8 of the manifest |
| 6 | **The pros' choices as a standing prior, not a fading teacher**: a small network fitted to the pros' target and weapon by situation; his own choices are held near it by a small, constant weight | a teacher that fades is forgotten or, kept at full weight, obeyed blindly (the weapon teacher, the item rule). A light pull that stays lets the game's pay overrule it where it pays | small | decision 4 of the manifest |
| 7 | **Things he is asked to foretell, not paid for**: who wins the next exchange, where the unseen enemy is (the belief), when each big item returns | they shape what his memory keeps, at no risk to his play. Tried on the demos today: the next item and a just-lost enemy can be learned, the fight's outcome hardly | small | nothing new (the belief is in stage B) |
| 8 | **Promotion by the scorecard too** (`tools/convergence.py`): a network is promoted if it beats the control and does not fall back in any group | "convergence on the pros" as the owner framed it; the control stays the gate | none | the owner's word on the rule |

Not proposed: paying any yardstick directly (rockets a minute, time on high ground). The fight target's first trial
today is the lesson: placed by a broad rule it cost him his items and he dropped it within forty minutes.

## 3. The demos: what is not used yet

Pulled on 2026-10-11 evening for the pros (`docs/pro_yardsticks.json`: `looking`, `holds`, `hands`, `fight_movement`);
his own numbers come beside them when his games are replayed through `tools/bobby_yardsticks.py`:

1. Where a pro looks with nobody in view. Half a second before the enemy appears his view is within 20 degrees of the
   spot half the time (at the sighting: 74%); a sound of the enemy in the last second makes no difference. They are
   aimed at where he will come from, not turning to him.
2. Holds and traps. 21 holds per ten minutes (two seconds or more in one spot with a big weapon and nobody in view), 11%
   of their time, rockets in hand three times in four; the enemy comes into view within 3 s of half of them. A blind
   rocket or grenade from a hold that hits: 1.7 per ten minutes.
3. Their hands as measured. After a sighting the first shot comes at 0.33 s and the first hit at 0.53 s (medians); the
   view turns at 130 degrees a second at its peak (570 at the 90th percentile). Lightning hits 45% of its cells under 250
   units, 37% at 250 to 500, 32% at 500 to 750; rail 43% overall; a rocket hits (splash counted) 28%. This is the measure
   for his aim limits: in the simulator his lightning hits about 45% at a median distance of 327.
4. Movement in a fight. Against lightning or rail they stay on the ground and change direction 1.9 times a second
   (5 jumps a minute); against rockets they jump (18 a minute, 39% of the time in the air). After a hit of 50 or more
   they break the line of sight within 2 s four times in five and change weapon half the time.

Not started:

5. The enemy's side of every demo: the other player is in the recording whenever in view. Twice the fights, seen from outside.
6. Which fights they take: of the sightings, which they close on and which they leave, with the outcome of each.
7. The first ten seconds after a spawn and after a frag: the sequence, not the averages.
8. What the pro could hear at each moment (the demo has the sound events), set beside what he then did.

## 4. How the two movement networks become one

Stage C of the manifest makes his legs a branch of the one network: same inputs, trained by the game's pay, the switch
kept. Beyond it:

- His own movement outputs are taught by the branch in every frame the branch is carrying him (a lesson with his own
  hands, at a small constant weight). What the branch knows moves into the shared layers; the switch is used less as
  his own movement gets as fast, and can be measured going to zero.
- His legs need a target at every moment. Measured on v15c's end (the log of 2026-10-11 19:00): carried by his legs
  he is at 400 or more 20% of the time (the pros 17.5%) and past 500 after six seconds; on his own feet with nobody in
  view he mostly has no target (the intention "nothing") or has just lost sight of the enemy. A target that is never
  "nothing" (a place worth holding when no item is due) is a gain in speed as much as in position.
- The same form fits the next skills as they come: quiet movement, rocket jumps, dodging. Each is learned alone where
  it is easy to pay for, joins as a branch, and is absorbed.

## 5. The order I would take

1 (with stage A), then 3, then 2 and 4 together when the parser is right, then 5 on his word. 6 and 8 are decisions,
not work. 7 comes with the belief.
