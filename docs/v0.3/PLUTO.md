# What Pluto does, and what Bobby takes from it

*Written 2026-10-14 18:15 on the owner's word: "we should try to design around the pluto bot as much as possible, it obviously
works really well". Pluto: a StarCraft: Brood War bot by Vegard Mella (tscmoo), one network trained by self-play, winner of
the 2026 Computer Olympiad / CoG StarCraft competition (the final 4-1; reportedly 98% of its games).*

## What is known

The author has published no paper and no training code: what is known comes from the released program
([github.com/tscmoo/pluto](https://github.com/tscmoo/pluto)) and a third party's reading of its weights
([pluto-re](https://github.com/hwkim3330/pluto-re/blob/master/docs/model.md)).

| | Pluto | Bobby (v0.3) |
|---|---|---|
| Size | 315 million weights | 2 million |
| What he sees | every visible unit as a token, a transformer of 6 layers over them, the map as pictures | about 800 numbers, a small attention part over groups of them |
| Short memory | a GRU 4096 wide that, every step, looks back at the units, the map and the long memory (attention added into its gates) | a GRU 512 wide fed by the encoder |
| **Long memory** | **every 8 steps (about 2 s) his state is written into a store of 128 slots (about 4.3 minutes); a transformer of 4 layers reads the store** | none (the slow GRU of test S is left out) |
| Decisions | one every 6 game frames (4 a second); action, then its target, one after the other | every frame (40 a second; keys every fourth) |
| **The judge** | **training only, removed from the released network: several value outputs, a win-probability output in 53 bands paired across both players, a guess of the opponent** | **v0.3: a judge that sees the truth (training only)** |
| Win chance | an output of its own, read from the long memory; he resigns on it | a table made by hand (`win_chance.json`) |
| Fog of war | respected; what is unseen is left to the memories | respected; the same |
| Openings | a bandit over openings per opponent, from his record against them | the pros' openings by spawn point |
| Teachers, styles, scripted parts | none: self-play only | several teachers and rules, faded over a run |

Unknown: the learning method (the author co-wrote moolib, FAIR's library for IMPALA-style training), the pay, the league,
the computers used, how long it trained.

## What Bobby takes from it, in order

1. **The judge that sees the truth** (v0.3, tonight if its test passes). Pluto's paired win output reads both players: our
   next step is the same (the judge also reads the enemy's own memory where the enemy is the same network).
2. **The long memory, Pluto's way** (v0.3.x, the first test arm after v0.3 starts). Not a second, slower GRU but a store: his
   state written every 0.6 to 1.2 s into about 160 slots (2 to 3 minutes, the owner's window), read by attention every frame
   and fed into his GRU's input (Pluto adds it into the gates). The store we already keep for test S is the hard part of it.
   Taught by the guessing game (where the enemy is, what he goes for) and the judge; the win-chance output reads it.
3. **A learned win chance**: an output that foretells the game's result in bands, taught by the results of whole games, in
   place of the hand-made table; the pay can then lean more on winning and less on the hand-made parts (the owner's call:
   the pay is his).
4. **Fewer hand-made parts over time**: Pluto has no teachers at all. Each teacher still on in v0.3 gets its own test: off,
   ten updates, a check.
5. **Size**, last: Pluto is 150 times bigger, on more computers than this PC. A GRU of 1024 and a larger attention part are
   possible here (an update would take about twice as long); worth it only after 1 to 3 work.
6. **On the servers**: openings chosen per person by a bandit over his record against them (the random ids), Pluto's way.
