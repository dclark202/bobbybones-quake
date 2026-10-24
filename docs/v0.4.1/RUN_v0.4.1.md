# v0.4.1 on one page: the brain connected to the hands

*2026-10-23 12:15: **running** (`duel_gru_v0_4_1`, from v0.4.0b's end; gate shut 1 h, then capped at 10% until a check; to Sat noon). Update 10 (gate shut): 92-68 against v0.4.0b's end. Built 10:15 (branch `v041`, `f9fefcf`, on v0.4.0b's `49a105c`); start 12:00–14:00 from
v0.4.0b's latest save on the owner's go, after the zones' readiness review ([RUN_v0.4.0.md](../v0.4.0/RUN_v0.4.0.md)). Next: [RUN_v0.4.2.md](../v0.4.2/RUN_v0.4.2.md) (the old belief faded out), then [RUN_v0.4.3.md](../v0.4.3/RUN_v0.4.3.md) (the strategy head).
Design: [BELIEF_LOOP.md](../v0.4.0/BELIEF_LOOP.md).*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## The step

The hands start reading the brain. The brain's answers come in as **one new input** (a token in the hands' attention), behind a
gate that is shut at the start and opens over hours. **The old rule-made belief stays in for now** (it fades out in v0.4.2): one
change at a time. This is the first time the brain can change how he plays.

## What changes

| Part | Detail | State |
|---|---|---|
| The brain's answers as an input | a new token (`belief`) in the hands' attention: the readout's place (± spread), velocity, stack band, weapon in hand, weapons owned | ❓ |
| **Turned with him every frame** | the readout gives the enemy's place relative to his view at its 0.2 s tick; between ticks he turns and moves. The answer is kept in map coordinates and re-turned into his current view every frame | ❓ |
| **The gate** | shut for the first hour (play exactly v0.4.0's), then opening over ~4 h; live (pause, slow down, close). Gate 0 must mean the token is not there at all: the old gate (-30 on the scores) was not exact; the new one multiplies the token's weight by g, and at 0 leaves it out (bit-identical, tested) | ✅ |
| What the hands learnt from | the answers they actually saw in play are recorded with the games and used in learning (the brain keeps learning, so recomputing them would train the hands on inputs they never saw) | ✅ |
| The brain stays honest | no game reward flows back into it: it learns from the truth only (asserted every update: 0 of 18 brain weights reached, at gates 0, 0.05, 1) | ✅ |
| The brain learns more slowly once connected | so the hands are not chasing a moving input; its learning rate live | ❓ |
| **The zones in place of the long-gap point** (owner, 2026-10-23: "let's replace the 10+s range with the distribution over locations") | the odds over ~16–24 map zones, built now and pretrained in v0.4.0 from a save (nothing reads them there), then part of the token: the point ± spread for short gaps, the zones for long ones | ⏳ |
| **New readout outputs, added untrained** (not inputs yet) | the zones (odds over ~16–24 map zones + the top two places: a split belief can't be one point); where the enemy will be in 1, 2, 4 s; what he is going for; when he appears; the item race for mega and red (his walking-time lead, the chance the enemy is there at the spawn). Lesson only, **no pay on the future** | ❓ |
| **The velocity as speed + direction** (owner, 2026-10-22: "speed+direction separately makes sense. Probably both can be averaged over a short window") | the enemy nearly always moves ~340 u/s in an unknown direction: a Gaussian on zero can't say that (v0.4.0's flat ~13.8 nats, not a bug). Speed (± spread) and direction (a circular distribution) as two outputs, their truth averaged over a short window (~0.2 s, the brain's tick), a fresh last layer; lesson only | ❓ |
| The check tools run the brain too | the checks, the decision report and the drift check must play the same network as training once the gate opens, or every number is wrong | ❓ |

## Build results (CPU, 2026-10-23)

| Test | Result |
|---|---|
| Identity at gate 0 | trainer: 3 updates bit-identical to v0.4.0b's code (actions, log p, values, rewards), the full run settings; duel_eval: byte-identical |
| Gate 1 | 19% of actions change; the token moves the attention's output 17% (3% at gate 0.05) |
| No gradient into the brain from the game | 0 of 18 weights at every gate |
| Token contents (69 numbers) | the point ± spread, the zone odds and the three likeliest zones (as seen from him), speed and direction, stack band, weapon in hand, weapons owned, time since seen, the answer's age; re-turned with his facing every frame (within 0.5 u) |
| Checks run the brain | duel_eval, the drift check, the decision report (one Policy on two sides keeps two brains apart: a bug found and fixed) |
| `tools/btoken_check.py` | 37 of 37 |
| Cost (estimated) | +2–4% an update; 82k weights; 0.5 GB of host memory |
| Not done | the GPU run (time, memory measured), the plugins and export (a token network plays with the gate shut on a server) |

## Red team (before the go)

| Risk | Answer |
|---|---|
| The rule's "ten updates and a check against the control" needs the GPU, which the run holds | the first hour is gate 0: v0.4.0b exactly. Then the gate is **capped at 0.1** (`BTOK_GATE_CAP`) until a check against v0.4.0b's end at that gate is level or better; only then is the cap lifted. Way back: cap 0 |
| The new lessons ahead (1/2/4 s, target, appear, race) pull on the brain's memory and could blur the answers the hands now read | they rise over 60 min (`AHEAD_W` live); watch the brain's place and zone errors: any rise of more than ~5% → `AHEAD_W` down |
| The hands chase a moving input | the brain's rate halved (2.5×, live `BELIEF_LR`) |
| A check that doesn't run the brain reads the wrong network | duel_eval runs it whenever the gate is above 0 (tested); the watcher for v0.4.1 uses the `v041` code |
| One player's brain state leaking into the other's in checks | found and fixed (each seat's state in its own memory) |
| A server can't run it | plugins not updated: v0.4.1 does not go public until they are |

## Tests before the start

| Test | Pass |
|---|---|
| Identity at gate 0 | his actions bit-identical to v0.4.0's end, in the trainer's play and in the check tools |
| Gate at 1, short trial | runs; the token reaches his outputs |
| The brain's gradient from the game | exactly zero |
| Speed and the card's memory | – |
| Ten updates and a check against the control | the rule since 2026-10-13 |

## Targets: the decision report (the owner: "whatever we start doing in v0.4.x needs to target these findings")

Baseline (v0.3.10's end against v0.3.9's end, 80 whole games): presses in far behind 36% (then dies 61%); mega and red respawns
the enemy took 42%, on time 8%, no better when the enemy is weak; the enemy within 600 u at 32% of his pickups when he is weak;
deaths while weak 4.4 a game (38% of his deaths). v0.4.1 should move:

| Row | Why | Direction |
|---|---|---|
| Presses in when far behind; deaths while weak | the brain's stack of the enemy, sharper than the old filter | down |
| After losing sight, by the stack gap | the brain's place of the enemy | toward when ahead, away when behind, more clearly |
| Pre-aim at 0–2 s unseen | the brain's place | up |

The item rows are v0.4.3's (the strategy head); here measured.

## Watch, and the way back

| Every ~1.5 h | – |
|---|---|
| Record, win rate, frag share against v0.3.10's end and v0.4.0's end | the headline |
| The decision report; the drift check; the hands' attention on the new token; aim and hit rates | is he reading it, does he play better, is anything breaking |
| **Way back** | close the gate live: he is v0.4.0's hands again, no restart |
