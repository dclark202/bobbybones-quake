# v16, the attention model: where we are, what I need from you, what I suggest (2026-10-11, 19:00)

The owner, 2026-10-11 17:50: "give me an approach doc for attention, including what you recommend for training tonight,
and all the discussions/points we've made so far. Make the report + this a clear 'here's where we are', 'here's what I
need from you (me)' and 'here's what I suggest we do'".

The working copy of this page, with the questions renumbered (24) and a column for the owner's answers, is a private doc he
edits; this file is the repo's record as of 19:00 and takes his answers when they are given.

**Which run is which.** v15c's end (his legs, the weapon rounds) is on the public server since 13:01 and is the control.
`duel_gru_v15f` was the afternoon's trial of the enemy as a target (stopped), `duel_gru_v15r` the trial of the three
rocket changes (ended 18:01). `duel_gru_v15e` is the run proposed for tonight with today's network
([../v0.2/MANIFEST_v15e.md](MANIFEST_v15e.md)). v16 is the attention model, not built yet. The details behind
this page: the model ([V16_ATTENTION.md](V16_ATTENTION.md)), its stages ([../v0.2/MANIFEST_v16.md](MANIFEST_v16.md)),
pay, rounds and opponents ([V16_TRAINING.md](V16_TRAINING.md)), the day's numbers
([the log of 2026-10-11](../results/2026-10-11.md)).

## 1. Where we are

**What plays today.** v15c's end beats the game's Nightmare bot 50 frags to 22 in six real ten-minute games and the
stand-in on ten maps (153 games won, 1 drawn, 6 lost). The owner after playing it: "much better than v14 was", "strong
LG, very strong", plasma "a little but it was really good", rockets "could use more"; "their main failure point is that
their routes are predictable"; "he doesn't know how to push an advantage".

**How near he is to the pros** (`tools/convergence.py`: fourteen measures from his games against himself, set beside
4,085 pro demos of the six maps; 100% is the pros' value; the Nightmare bot is the floor, the owner's play the judge):

| How near the pros (100% = their value) | v14's end | v15b's end | v15c's end | the rocket trial's end |
|---|---|---|---|---|
| Position | 62% | 66% | 65% | 64% |
| Speed | 42% | 79% | 82% | 79% |
| Weapons | 18% | 17% | 17% | 19% |
| Aggression | 0% | 0% | 3% | 12% |
| Control | 92% | 92% | 95% | 99% |
| **All measures** | **39%** (14 measures) | **47%** (14 measures) | **48%** (14 measures) | **50%** (14 measures) |

The measures one by one (his value, and how near):

| Group | Measure | The pros | v14's end | v15b's end | v15c's end | the rocket trial's end |
|---|---|---|---|---|---|---|
| Position | higher than the enemy in view, % | 26.4 | 18.1 (69%) | 17.5 (66%) | 17.5 (66%) | 18.4 (70%) |
| Position | time in the lowest third of the map, % | 27.8 | 41.1 (52%) | 39.9 (56%) | 40.4 (55%) | 40.8 (53%) |
| Position | trips on the commonest way between two items, % | 45.2 | 62.7 (61%) | 56.1 (76%) | 57.5 (73%) | 59.4 (69%) |
| Position | distance he fights at (median, units) | 508 | 341 (67%) | 331 (65%) | 327 (64%) | 328 (65%) |
| Speed | time at 400 or more while travelling, % | 17.5 | 1.3 (7%) | 9.2 (53%) | 9.4 (54%) | 9.3 (53%) |
| Speed | speed at the second hop of a chain | 421 | 229 (54%) | 377 (90%) | 389 (92%) | 375 (89%) |
| Speed | hops that gain speed, % | 70 | 45.1 (64%) | 67.1 (96%) | 70.9 (99%) | 66 (94%) |
| Weapons | rockets a minute | 10.8 | 2.17 (20%) | 2.04 (19%) | 2.14 (20%) | 2.4 (22%) |
| Weapons | rockets fired with no enemy in view, % of his rockets | 49.7 | 0.3 (1%) | 0.2 (0%) | 0.3 (1%) | 0.1 (0%) |
| Weapons | a rocket, then rail or lightning within 1.5 s, per ten minutes | 3.6 | 0.1 (3%) | 0.05 (1%) | 0.05 (1%) | 0.08 (2%) |
| Weapons | rockets in hand with the enemy in view, % | 39.5 | 19.5 (49%) | 18.1 (46%) | 18.7 (47%) | 20.8 (53%) |
| Aggression | closing when stacked: just after a frag less otherwise | 32.5 | -8.1 (0%) | -7.2 (0%) | 2 (6%) | 8.1 (25%) |
| Aggression | closing when weak (under 60) | -12.4 | 19.2 (0%) | 25.2 (0%) | 33.3 (0%) | 30.5 (0%) |
| Control | back at the mega within 2 s of its return, % | 47.2 | 43.4 (92%) | 51 (92%) | 49.4 (95%) | 46.6 (99%) |

**What is missing, by the owner's priorities** (v15c's end beside the pros; all measured today):

| Priority | What the numbers say | The cause as I read it |
|---|---|---|
| 1. Speed | on his legs he is at 400 or more 20% of the time (the pros 17.5%) and past 500 after six seconds; over a whole game 9.4%. His legs carry him 58% of his time on Blood Run, 27% on Aerowalk | on his own feet he has no target (the intention "nothing": 13 to 23% of his time), and three of four stretches on his legs end at a glimpse of the enemy: his legs hold his view, so he cannot run and look |
| 2. Rockets | 2.1 a minute (10.8); none with nobody in view (the pros: half of theirs; 56% of those within 5 s of losing the enemy, half near a big item); a rocket hit then a beam hit 0.02 per ten minutes (2.0) | he has never fired a rocket with nobody in view, so no price teaches it; in hand he prefers lightning (42% against 29%) |
| 3. Plasma, grenades | in hand 1.7% and 0.9%; grenades 0.03 a minute (2.2) | as rockets: they are weapons for places, and he has no places |
| 4. Game awareness | closes on the enemy at +33 whether weak or stacked (the pros: -12 weak, +37 just after a frag, +5 otherwise); the commonest way between two items 57% of his trips (43%); the lowest third of the map 40% of his time (28%); higher than the enemy in view 17.5% (26%) | he is shown the enemy only while in view; one way to each item; nothing in training punishes a habit; he counts 25 s ahead |
| Aim and hands | first shot 0.33 s and first hit 0.53 s after a sighting: the pros' own times. As the enemy appears he is 19.5 degrees off (7.5). Lightning under 250 units 60% (45%); rail and rockets at or under the pros' by distance | his hand makes up for where he looks; his opponents dodge less than pros (1.1 changes of direction a second against 1.6) |
| Holding and noise | holds a spot 13% of his time (11%) with lightning in hand 59% of it (the pros: rockets 76%, a silent weapon); traps from a hold 0.007 per ten minutes (1.7); walks 0.08% of his time (3.1%) | nothing tells him what he gives away |

**What was tried today.**

| | Result |
|---|---|
| The enemy as a target (`FIGHT_TARGET`, built on "Build this first") | by a broad rule it lost (39% against the control; it cost him his items) and he dropped it in 40 minutes; by a narrow rule (strong, the enemy just spawned and just seen) it is level. Without knowing the enemy is weak the target has little to offer |
| The three rocket changes (half price, free at the pros' places, half the cost of a wasted one) | no change in his rocket use over 165 minutes (in hand 21% at the start and at the end, 0.003 blind rockets a player-minute); no harm (76 games won, 7 drawn, 61 lost against the control mid-trial). A price cannot teach what he never tries |
| A seed for rockets with nobody in view, as a probe (the owner: "just as a POC for now") | a rule that presses fire is level in games when it keeps its distance (20 games won, 6 drawn, 22 lost against 17, 6, 25 with no rule; 0.5 to 1.7 blind rockets a minute) and loses when it fires at close range (8, 5, 35); but its rockets do not hit: the other side's losses to hits while he has nobody in view do not rise. The rule fires wherever his view points; the pros aim at where the enemy comes out. Blind rockets and crosshair placement are one skill |
| A record of events, on the demos | helps the next item and a just-lost enemy, nothing else: out of the first build, its two useful parts go into the enemy token and the item tokens |
| The model's cost on the rented server | four bots 7.0 ms a frame (8.4 at the 99th percentile; today 1.1): passes |
| The demo parser and converter (B-218, B-219) | mended and checked: every event with its kind, both scores, exact times; no corpses taken for the enemy. The stored sets are to be rebuilt (two hours) |
| The duel check | the same network on both sides got 47% on the first-named seat; the checks now swap seats in half of the games |

**Three facts of the trainer** behind his playing from moment to moment: his discount makes a reward 25 s ahead worth
37% and one a minute ahead 9%; a training sequence is 9.6 s, so nothing teaches his memory to keep what is older; his
opponents are himself and scripts, so a habit costs nothing.

## 2. What I need from you

Already answered today, and built into section 3: v16 is judged by "game awareness primarily. Also how much his movement
begins to blend together the two styles fighting/moving"; whole ten-minute games with pay for the result ("Yes");
training speed ("completely neutral"; three bots a server are enough); the position token holds the weapon for the spot
("Absolutely it should"); places from the demos (yes); several ways to a target, his to choose ("Yes"); a target that is
never "nothing" ("Yes"); rounds from real moments ("Hold this for v16"); the judge of pro-like movement ("Yes,
eventually. Don't build it now but remind me of it after tonight's run"); an exploiter in his league ("I'm skeptical
how possible this would be": left out of the plan, see 3.4); the parser first ("do this right not rush it").

**Tonight** (my recommendation in the last column):

| # | Question | Recommendation |
|---|---|---|
| 1 | `duel_gru_v15e` through the night: games on all ten maps, the rocket changes, the enemy as a target by the narrow rule? | yes: its value is the four maps he has never fought on (he dies in Toxicity's slime) |
| 2 | Campgrounds in training, or held out? | in: 212 usable older demos exist, so its demo count is no reason to hold it out |
| 3 | House of Decay as the held-out map for checks? | yes; Dismemberment needs your word and two mends |
| 4 | The enemy as a target in tonight's run? | in, by the narrow rule: level in probes, his to drop |
| 5 | The rocket changes and the seed | keep the three changes (harmless); no trial of the seed tonight: a seed that only presses fire would be dropped in training as the broad fight target was |
| 6 | Fetch Campgrounds' 212 older demos (a download of about half an hour)? | yes |
| 7 | His lightning is above the pros' in the simulator (60% against 45% under 250 units). Tighten it now, or measure him against people on the server first? | measure first: his targets dodge less than people |
| 8 | Toxicity off the public server's map list until he has played games there? | yes, until tonight's run has been checked on it |

**For v16** (the open points of every discussion so far):

| # | Question | Recommendation |
|---|---|---|
| 9 | A second value estimate that counts about two minutes ahead, for his target and way; his hands keep the short one. (You: "He needs a much longer horizon, this is part of attention I believe": attention gives him what to know; how far ahead pay counts is this setting.) | yes, with the first stage |
| 10 | The list of events left out of the first build (the afternoon's trial)? | yes |
| 11 | In whole games, a frag paid by what it moves his chance of winning (by score and clock), in place of a flat pay for the result at the end? | yes: it is what makes "ahead, behind, time left" matter at every frag. The table comes from the pros' games, now that the parser gives both scores |
| 12 | Late-game rounds that begin from drawn states (ahead or behind by one to three at 7:00), beside whole games? Real moments wait for later, as you said | yes, 10% of his time |
| 13 | The pros' choices of target and weapon by situation as a small standing pull, not a fading teacher? | yes, small, after stage B's first night shows the gap |
| 14 | High ground: the position token alone, or also a hit from above paid more (`HIGH_PAY`, built, never used)? | the token alone first |
| 15 | A pay for speed gained from hop to hop (approved in principle on the 10th)? | no longer: his legs alone are as fast as the pros; what he lacks is using them |
| 16 | Crosshair placement: if his hand proves faster than the pros' at large angles (being measured), set it to their curve? | yes: your own method, and it makes looking in the right place pay |
| 17 | Fights taken and refused ("needs to be tuned"): the pros' table as a measure and as something he is asked to foretell (how this fight ends), not as a pay? | yes; a pay only if the measure does not move |
| 18 | What he hears: the four sound tokens as designed, calibrated by what the pros do after each kind of sound (being pulled)? | yes |
| 19 | The noise he makes: his own loudness in the game token, and the weapon in hand (humming or silent) measured beside the pros'? | yes; no pay |
| 20 | The gauntlet: should he learn it at all? | not now |
| 21 | Promotion: beats the control and does not fall back in any group of the scorecard? | yes |
| 22 | v16 starts from tonight's end if it beats v15c's end, else from v15c's end? | yes |

### The owner's answers (2026-10-11 evening, typed into the working copy; the numbers are that copy's)

New names: v15c's end on the server is v0.1; the next model is v0.2, trials on the way v0.2.1 and so on; v1.0 when he
beats the owner. "Add stage A from attention to your proposed v15e for tonight and call it v0.2": the manifest is
[../v0.2/MANIFEST_v0.2.md](MANIFEST_v0.2.md).

| Question | His answer |
|---|---|
| Campgrounds in training or held out | "in" |
| House of Decay as the held-out map | "held out" |
| The enemy as a target tonight | "in" |
| The three rocket changes | "in" |
| A trial of the rocket seed | not answered (my recommendation was no) |
| Fetch Campgrounds' older demos | "yes" |
| His lightning: tighten now or measure against people first | "measure first, I think he just sucks at doding" |
| Toxicity off the public server's list | "no" |
| A value estimate that counts two minutes ahead, with the first stage | "yes" |
| The list of events out of the first build | "yes" |
| A frag paid by what it moves his chance of winning | "yes" |
| Late-game rounds from drawn states | "yes, up to 25%" |
| The pros' choices as a small standing pull | "yes" |
| High ground: the token alone or also a pay | "token first" |
| A pay for speed gained from hop to hop | "I don't think they're quite there yet, pay him a tiny amount for it. but the key is getting him to use them and maintain speed" |
| His hand set to the pros' flick curve | "yes, it seems his aim is overtuned at possibly the reason why he has become so reliant on lg/rail rather than rockets. let's slowly tune it down, using pros as a goal" |
| Fights taken and refused as a measure and something to foretell | "yes. his choice of picking fight is terrible currently" |
| The sound tokens, calibrated on the pros | "yes" |
| The noise he makes, measured, no pay | "yes, make sure it involves footsteps and stairs as well (you make sound on stairs even when walking)" |
| The gauntlet | "ideally he should, but i won't hold up the run for it" |
| Promotion: beats the control and falls back in no group | "yes within an amount of noise" |
| v16 from tonight's end | "I'm tempted to just start v16 now, why not?" |
| The exploiter left out | "leave it out -- I think this is harder to build than you're anticipating. Isn't HE the exploiter? He should be?" |

## 3. What I suggest we do

### 3.1 Tonight

Nothing starts without the owner's go.

1. `duel_gru_v15e` at full size until 07:00 ([../v0.2/MANIFEST_v15e.md](MANIFEST_v15e.md)): games on all ten maps (thirty
   simulators, three a map, 10,080 players as before), the three rocket changes, the enemy as a target seeded by the narrow
   rule; v15c's end in his league and as the control in every check, seats swapped in half of the games; the stand-in on
   the ten maps and on House of Decay every third check. Stopped under 45% against the control at two checks in a row, or
   ten points under on a map at two checks.
2. Beside it at low load: the stored demo sets rebuilt with the converter's fix, and the six demo pulls.
3. At 07:00: the night's report with the scorecard for its end, real games against the game's Nightmare bot on the quiet
   PC, and the reminder about the judge.

What tonight's run does not do: nothing in it is new for speed or for rockets. Both need what stages B and C bring: a
target that is never "nothing", legs that can run and look, and a view that is on the place the enemy comes from.

### 3.2 The attention model, in three stages

What it is, in one paragraph: what he sees is cut into tokens (himself, the game, his position, the enemy as seen, the
enemy as he believes him to be, six projectiles, twelve items, eight places, his way, four sounds: 54 in a duel), each
96 numbers wide; two attention blocks let every token look at the others; the result goes into his memory through a
door that starts closed, so the first network is exactly the old one. About 1.7 million weights (today 1.4). The enemy
as believed is your "enemy position + uncertainty": where he was last seen or heard, how long ago, how he was moving,
how far he can have got, and his strength as far as it can be known. The position token is your "strength of
position": his height against the enemy's believed place, what he overlooks, and how the pros fare there with which
weapon.

| Stage | What is new | Addresses | Build, then train |
|---|---|---|---|
| **A. He is shown more** | the tokens; the enemy as believed with his strength; places; his position; the time left and his own noise; the second value estimate (question 9) | game awareness: the difference between situations he cannot see today | two days; one night. It passes if it is level with the control at the first check and ahead after a night, and the door has opened |
| **B. He chooses more** | a target that is never "nothing": an item, the enemy's believed place, a place worth holding (from the pros' holds and cells); up to three ways to it (the pros' ways are extracted: 58 to 92 a map); the belief as something he is asked to foretell, with where the enemy next appears and how a fight ends; whole ten-minute games, a frag paid by what it does to the game (question 11); late-game rounds (question 12) | predictable routes and odd places; rockets and grenades at places; pushing and backing off; offense or defense by score and time; and speed, because his legs then always have somewhere to go | three days; two nights. It passes by the scorecard: blind rockets, the commonest way, closing by the enemy's state, time at 400 or more |
| **C. One way of moving** | his legs become a part of the one network that learns from the game and can run and look at once; his own movement is taught by it until the switch is no longer needed; the judge of pro-like movement as a guard while it blends (to be raised again after tonight's run, as you asked), with a second one for movement in a fight | "blend the two styles"; speed kept through a glimpse of the enemy; dodging; crosshair placement on the move | three days; two nights |

Measured at every check, beside the pros: the scorecard's five groups, and from today's pulls where he looks before the
enemy appears, his holds and what he holds in them, his hands, his movement in a fight, the fights he takes and refuses.
Nothing of it is paid unless you say so.

### 3.3 The demos

Done: the measures of play, the places, the ways, walking, when they fire blind, combinations by hits, where they look,
holds and traps, their hands, movement in a fight (ten maps, 4,449 demos). Running, in your order: fights taken and
refused, the flick curve, plans after a spawn and after a frag, what they do with each sound, the weapon in hand (quiet
or loud), teleporters and the jumps through them (your Aerowalk example). To do: the stored sets rebuilt with the
converter's fix; Campgrounds' older demos (question 6).

### 3.4 What I would leave out or hold

- The exploiter (a network trained only to beat him). You are skeptical; it is also the most expensive idea (a fifth of
  the simulators) and it finds the simulator's faults as readily as his. Several ways and a target that is never
  "nothing" remove the built-in cause of his habits first; the scripted watcher stays. If the commonest-way number does
  not move after stage B, it comes back as a question.
- Rounds from real moments: held for later in v16, as you said. When it comes: his own server games against people
  first (both players' state is exact there), then pro games.
- The judge: with stage C.
- Any pay for a single behaviour (rockets a minute, high ground, walking): none proposed.

### 3.5 What could go wrong

- The door stays closed: the old network ignores the tokens. The first night shows it (the adapter's size is logged);
  the fallback is a short lesson that makes him foretell from the tokens.
- Training is three to four times slower a step than today. You are neutral on speed; a stage needs a night, not hours.
- More changes at once than the one-change rule likes: each stage is a batch, checked against the control and the
  scorecard before the next.
