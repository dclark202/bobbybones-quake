# 2.0: pay the stack and the control, not the damage (a mock-up)

*2026-11-08 (owner, after watching pro games and playing 1.7a's u90): "we are paying damage far too much. The LG only behavior is likely
because he gets the most pay for using it directly"; "He doesn't value his own life or the positions he holds"; "stop trying to change the
weapon choice and instead change the incentive"; "Whatever comes next, 1.n is done; the next round starts with 2.0 and will address the idea of
control"; "paying for damage that only improves his win chance, or improves his control ... Or dropping pay by damage entirely. Making deaths
count for more, based on how much stack you're giving up, or what item control you give up"; "let's really push the boundaries of what we did
before". A mock-up for discussion: nothing here is built or decided. The start would be 1.7a's update 90 (`keep/policy_end_17a.pt`).*

**Marks:** ✅ measured or already built · 🧪 to measure before a go · ⏳ to build · ❓ owner's decision

## 1. What the pay says today (1.7a's end, the ledger of `PAY_SPLIT`, a player-minute)

| Term | Net | Size | What it is |
|---|---|---|---|
| damage dealt | **+1.84** | 1.84 | 0.0055 a point, flat, whatever it does to the fight |
| damage taken | **−1.55** | 1.55 | 0.8 of it (`DMG_TAKEN_W`; 1.0 in 1.7b) |
| frags | +1.18 | 1.18 | +1 flat |
| deaths | −1.06 | 1.06 | −1 flat, the same at 125/0 as at 200/200 |
| the win part (`WIN_ADD` 0.33 × the judge's change in his win chance) | +0.01 | **4.35** | the one term that prices the stack and the clock; it moves every frame and nets nothing |
| mega, red, yellows, points, decay (the table by the point) | +0.00 | 1.8 | zero-sum between the two copies |
| everything else (watch, pre-aim, order, know) | 0.00 | 0.3 | |

So **damage is the largest flow he is paid, 1.6 times the frags**, and it is paid as it happens, where a death is one lump at the end of
the fight and a game's result reaches the hands only in the last 25 s (`--gamma 0.999`; the head's own value sees two minutes).

**The owner's example, in numbers** (he takes the lightning gun, does 100, dies):

| | Raw pay | Discounted at 0.999 a frame (the death 5 s after the damage) |
|---|---|---|
| 100 damage dealt | +0.55 | +0.55 |
| 125 taken (a fresh spawn) | −0.55 | −0.50 |
| the death | −1.00 | −0.82 |
| **sum** | **−1.00** | **−0.77** |
| the same with 200/200 given up (400 damage absorbed) | −2.76 | about −2.4 |

He does not come out ahead on the sum; three things make him act as if he did:

1. **The trade pays both copies.** 100 for 100 with nobody dead pays each +0.11 (✅ measured: 0.37 a player-minute at u90, a third of
   his frags' pay). The weapon with the steadiest stream in contact earns it best whether or not the fight is won: the lightning gun at
   his hits (46 damage a second against the rail's 23). The strong aimer's trap, in the pay.
2. **Nothing pays out of a fight.** Items net nothing between two copies that both take them (zero-sum by design); the win part's trickle
   is tiny between frags. From the hands' seat the only place pay comes from is a fight, and in a fight it comes first from damage.
3. **Death is flat.** A death at 200/200 after a red armor and a mega costs −1, the same as one at the spawn, plus whatever the judge's
   stack term adds at a third of its weight. The stack he gives up is priced at 0.33 of what the judge thinks it is worth.

What this is not: his aim (✅ hits 52% rockets, 39% lightning, 43% rail at u90, level with the pros' lightning) and his pickups (mega
within 1 s 57%, a median 0.8 s). The fight data say the rest ([CYPHER.md](CYPHER.md)): out-stacked under 0.67 he dies in **56%** of his
fights where the pros get away from two in three (they die in 30%); the pros' fights mostly end with nobody dead (64 to 71%, his 38 to
49%); behind, the pros hit first 47% of the time, he 22%.

## 2. The principle for 2.0

**The stack is the score.** Combat pay is what a fight does to his chance of winning the game: the frags, the stack both sides are left
with, the items each will reach first, the clock. Damage has no price of its own: 50 points off a 200/200 that is about to decay are worth
almost nothing, 50 points off a 60/0 are a frag's worth. A death costs the frag **and** the stack and the item control it gives up. A fight
nobody wins pays nobody. Behind in stack, the pay says: chip from a spot he can leave, take the yellows, and do not die; ahead, it says:
hold the spawns, fight when the stacks say so.

We already have the instrument for this and have been running it at a third: **the judge** (`sim/win_judge.py`; `WIN_JUDGE` names its file,
`data/sim_runs/judge/judge_v060_wpn.npz`: fitted 2026-10-28 on 300 of v0.6.0's self-play games and frozen since; `--win-value 1` is a different
thing, a critic that predicts the result from the brain's state, never paid). Its shape carries the owner's four axioms (frag good, death bad, damage dealt
good, taken bad), prices the stack in a lasting part (up to 100 each) and a decaying part (above 100), the big three weapons owned, the
lead and the clock. Its pay is the change in his win chance a frame: **telescoping**, so a game's sum is its result less the chance at its
start and nothing on the way can be pumped (a setback and its recovery nets zero), and **zero-sum** between the two seats by construction.
Pay is allowed to know the truth (both stacks, both places); his inputs are not. This is the "damage that only improves his win chance":
the judge pays a hit exactly by how much it moves the odds, and nothing for the rest.

From AlphaStar: the reward is the game's result; everything else that shaped play came as human priors (the KL to human play) and the
league, not as pay for events. We cannot pay the result alone on one PC (v0.5.1, v0.6.1: level, then passive), so the judge brings the
result forward to the frame where the stack changes: a learned potential, which does not change what the best play is, only how soon it is
seen. The flat frag and death and the table by the point stay as the floor (the owner's b1 decision), but damage by the point goes.

## 3. The arms (one new thing a round; each a short run from u90 with 1.7a's checks and Cypher's measures)

| Arm | The one change | How | Code | What it pays that today's pay does not |
|---|---|---|---|---|
| **2.0a: damage out, the judge in** | damage by the point to zero, the judge's weight up so combat still outweighs items (the b1.2d rule: combat at least twice items, by size) | live dials, faded over updates 10 to 70 as b1.2d: `--dmg-reward` 0.0055 → **0** (the trainer's flag: make it live ⏳), `WIN_ADD` 0.33 → **1.0** 🧪 (sized so a 100-damage hit on a 100/0 enemy pays about what 0.55 paid, and the same hit on a 200/200 near nothing) | ⏳ small: `DMG_REWARD` live | a death at 200/200 costs the frag plus up to about 2 frags of stack (the judge's shape; the learned number read before the go 🧪); a trade nobody wins pays nobody; finishing damage pays, decaying damage does not |
| **2.0b: the death counts more than the frag** (the owner's "making deaths count for more") | the death's flat −1 → −1.5, the frag's +1 unchanged: negative-sum, so in self-play every fight is bad on average unless won cleanly (Cypher's "the goal is not to lose") | a new live `DEATH_W` (the ±1 are written into `sim/duel_env.py` today) | ⏳ one line | **the one lever measured to reach the weak side's losing fight** (the 2.0a card: at 100/0 against 200/200 the margin for leaving 1.17 → 1.67), where the judge rightly prices a 100/0 death cheaply. Risk: passivity (v0.5.1's shape); not telescoping. Alone in its round |
| **2.0b′: the death priced by what it gives up** (as a flat term beside the judge) | the death's flat −1 becomes −(1 + k × the stack he had, in frags by the judge's h) and the frag's +1 becomes +(1 + k × the enemy's stack) | a new live `DEATH_STACK_K` ⏳; zero-sum (the killer gets what the dead loses) | ⏳ small | the same thing as 2.0a's stack term paid at the death instead of frame by frame: easier to read in the ledger, but it pays the stack only if he dies, where the judge pays it as it bleeds. **I would not run both**: it double-prices the stack. 2.0a first; 2.0b if the per-frame judge proves too noisy (its size is already 4.35 a player-minute at 0.33) |
| **2.0c: position in the judge** ("places to control") | the judge learns from the race too: for each of the mega, the red and the yellows, the seconds until it is up and who is nearer by walking time (`sim/ahead.py`'s race truth, `TRACK_RACE`; the yellows ⏳) | the judge's h gets a positional part fitted on game outcomes with the stack part; then being first to the next spawn is priced by what it predicts, nothing by hand | ⏳ a day's build: judge inputs, the fit, the ledger | **dying gives up item control** (the enemy is first to everything for the respawn and the walk); standing where the next spawn is reachable first is worth something; leaving a spawn to the enemy who is nearer costs; the owner's "above: cycles and denial; behind: the yellows you can manage" without a rule for either |
| **2.0d: control paid outright** (the boundary) | a zero-sum pay for his share of the next big spawns, per frame (the control readout's truth, `CONTROL_TRUTH`, as a potential) | the change in P(he takes the next two of mega and red) a frame, truth from hindsight | ⏳ | the explicit "in control" the owner names. B-280 ruled it out as shaping; the pathology is camping the spawn and ignoring the fight. 2.0c prices the same thing through winning instead. Listed so the boundary is on the table ❓ |
| **2.0e: the hands see an item cycle** | `--gamma` 0.999 → 0.9995 (25 s → 50 s, one armor cycle) | a flag; variance up | none | the hands' own value sees the next spawn, not only the head's two-minute value |
| **2.0f: the frag flat out too** (win chance only, again) | frags and deaths through the judge only | dials | none | v0.5.1 and v0.6.1 did this and went passive and slower; the judge is better now (online, the stack in two parts) but the table was the owner's answer. **Not recommended first**; the floor stays until 2.0a to 2.0c have shown their equilibrium |

**Recommended order:** 2.0a (dials and one small change, the extra check at update 10, faded over 10 to 70) → 2.0c (built after 2.0a ends; nothing
beside a run without the owner's word) → the order and break off again on top of the new pay (1.7b's parts: the
fight odds learned well, Brier 0.12 against 0.21; the kinds never moved because the pay gave break off nothing to win). The weapon is **not**
touched (owner): it is read as an outcome.

**Measured on 11-08 (the 2.0a card, "The losing fight"):** on the judge the weak side's losing fight (100/0 against 200/200) is priced
about as today (the margin for leaving 1.23 → 1.17): a 100/0 who dies loses the frag and respawns better off, and the judge, by game outcomes,
is right to say so. 2.0a takes away the even trade's pay (+0.22 each → 0) and makes the stacked side's death 1.5 times dearer; the weak side's
fight needs 2.0b (the death at −1.5) or the fight odds in the head.

## 4. The equilibrium (the owner's standing rule: every pay change by its self-play equilibrium)

| | Today's pay | 2.0a + 2.0c |
|---|---|---|
| A fight at level stacks, in the open, lightning against lightning | both stand and trade: +0.05 a second each, the loser −1 later | nobody is paid for the trade; the odds are 50/50; the pay says take it only with the stack edge, else move to a spot or an item that changes the odds |
| Out-stacked (under 0.67) | engaging still pays the damage stream now; the death is discounted | engaging pays near nothing (his hits barely move a 200/200's chance), the death costs the frag and his stack: leave, chip from a way out, take the yellow |
| Stacked (over 1.5), the enemy in a corridor | the same as any fight | pushing is paid by the odds (his hits on a thin enemy move p a lot); his own stack is at risk only to the chip |
| After a red and a mega, nobody in sight | nothing pays (items zero-sum, decay charged) | the same, plus: his death now costs about 3; the judge's clock trickle pays the leader for time; so the stack is held, not spent |
| The next spawn, the enemy nearer | the item's points if he gets there first | 2.0c: the race itself is priced; a spawn he cannot win is worth leaving; one he can win by position is worth holding |
| The weapon | lightning: the steadiest stream for a flat per-point pay | an open question. Cause 1 of [TRAIN_UNDER_TABLE.md](../runs/1.7/1.7c/TRAIN_UNDER_TABLE.md) stands: against his own copy at equal aim lightning is the best weapon inside 768 units whatever the pay. What may move: the chip at range before a fight (rail, rockets) now has a price (it changes the odds of the fight to come) and a break off that lives is worth a frag, so fights at range and fights nobody finishes pay where they did not. 1.7b's 100 updates with zero-sum damage alone showed no move (✅); but that run kept the per-point pay |

The behaviour on the way: fewer frags a match-minute at first (the alarm of v0.5.1 is 1.42 against 1.65; 1.7a's u90 is 2.32), more fights
with nobody dead (wanted: toward the pros' 64 to 71% from 38 to 49%), fewer deaths out-stacked (wanted: toward 30% from 56%), more first hits
when weaker (toward 47% from 22%), stack at the start of his fights up, the mega and red timing held (0.8 s and 1.2 s), the yellows taken
more by the player behind. Win rate against u90 may fall before it rises: a copy that plays for the stack beats one that plays for damage
only once it can also escape, and escaping a lightning gun is a skill it has never had to learn.

## 5. Judged by (every check, from update 10)

| Measure | u90 | Wanted | Alarm |
|---|---|---|---|
| Win rate against 1.7a's u90 (200 games) | 50% | over 50% by the fade's end | under 40%: flagged at once (rule 6) |
| Fights with nobody dead | 38 to 49% | toward 64 to 71% | over 75% with frags under 1.4 a match-minute: passivity (v0.5.1) |
| Out-stacked (under 0.67): dies / gets away | 56 / 38% | toward 30 / 64% | |
| Weaker side hits first | 22% | toward 47% | |
| Stack at the start of his fights (effective, his / the enemy's) | 🧪 | up | |
| Deaths a minute while behind in stack | 🧪 | down | |
| Frags a match-minute | 2.32 | held above 1.8 | under 1.5 |
| The ledger | | damage 0; the win part the largest combat term; no term with a sign flip; no negative frags | the judge's size over 15 a player-minute (noise) |
| His weapon in view (rockets / lightning / rail) | 20 / 67 / 1% | read, not steered | |
| "In control" (the readout's truth: his share of the next spawns, by map) | 🧪 | up when ahead in stack | |
| The critic (`--win-value`): EV, calibration slope | 0.88, 0.60 | held | a fall: his play has moved where the frozen judge's prices no longer predict the result |

## 6. Red team

| Part | Hand-built or assumed | The measured alternative | Watch |
|---|---|---|---|
| The judge's weight (`WIN_ADD` 1.0) | a guess until sized: today the judge's part is 4.35 a player-minute of size at 0.33 | size it so a hit on a 100/0 pays what 0.55 paid (the judge's numbers from its current fit, before the go 🧪) | the ledger's sizes; the KL and the entropy (a noisier pay raises both) |
| The judge is v0.6.0's fit, frozen | it prices the stack as v0.6.0's lightning equilibrium valued it (a stack above 100 very highly: chipping 50 off a 200/0 pays 0.96 at G = 1, 50 off a 100/0 0.42); a judge that has never seen a rail-held angle win cannot price it | a refit on 1.7a u90's games with the pros' rows in the fit (`tools/run/fit_b.py`; the demos price the stack as people do) 🧪 | held-out log loss, the axioms; the stack term's prices (the card's table) |
| The pay knows the truth | by design (the pay is the owner's view). His inputs do not: the enemy's stack as he believes it (`EN_STACK`) | none needed | the brain's stack band Brier (he must *estimate* what the pay knows) |
| Passivity | v0.5.1 and v0.6.1d went slower on win-weighted pay; the flat frag and death stay here as the floor | a small positive-sum damage pay kept (0.001 a point) as a floor against standing off ❓ | frags a match-minute; nobody-dead share |
| The late-game table | the win table makes a leader's frag worth little late (v0.5.1's lesson); the judge's s(t) narrows with the time left | the flat frag stays (worth 1 whatever the clock) | checks by game phase |
| The lightning equilibrium is the self-play optimum, not a pay artefact | partly true (cause 1) | the weapon is an outcome here, not a target; B-305 later if the pay alone does not move it | his weapon by distance and phase |
| 2.0c's race truth | walking time by the simulator's graph, both players' true places | the pros' own races (who got there) | its weight in the judge after the fit |
| Variance | a per-frame pay that moves 13 a player-minute of size at `WIN_ADD` 1.0 | 2.0b (the stack priced at the death only) | the advantage's spread; updates' step |
| Pay pathologies (the ledger) | | | negative frags, sign flips, lopsided games |

## 7. What is already there (nothing to build for these)

✅ the judge (v0.6.0's fit, the stack in two parts and the weapons; `WIN_JUDGE`); ✅ `WIN_ADD` live; ✅ `DMG_TAKEN_W` live; ✅ the control
readouts with their hindsight truth (`CONTROL_TRUTH=1`, the mega and the red; the head reads them, `--head2-ctrl-src belief`); ✅ the race
readout (`TRACK_RACE`); ✅ the fight odds (1.7b, `FIGHT_TRUTH`); ✅ the yellow timers (1.7b's inputs); ✅ the ledger (`PAY_SPLIT`) and Cypher's
measures (`tools/run/cypher_measure.py`); ✅ whole games 65%, pro starts 35%, overtime. ⏳ `--dmg-reward` as a live dial; ⏳ the yellows in
the race and the control truth (B-307's second half); ⏳ 2.0c's judge inputs and fit; ⏳ 2.0b's `DEATH_STACK_K` if wanted.
