# b1.4a: the old rules fade out, the head decides his target

*2026-11-02 evening (owner): "B1.3 - fade head IN. It starts overnight and is ready sometime tomorrow. B1.4 - fade OLD rules out"; "we bring it in in b1.3 to learn how to copy the rules that exist, and then once we know it can, we remove those rules and let the head train"; "Your proposed schedule here is too timid, I want most of those to be in 1.4, possibly 1.5 at most"; "I'm fine leaving combat, item and win pay in him. I view the win pay as the correction factor on top of those"; "have B1.4 ready to go tomorrow ~9am". The family: [README](../README.md). The earlier plan in this folder (the damage weight; its `ident.py`, `smoke.py`, `ramp_b13.py`, `ramp_test.*`) went into b1.2d and is history.*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Started from | **b1.3a's end** with its optimizer (`keep/policy_end_b13a.pt`), if its copy passes (below); the head shut (gate 0), mix 0 |
| Run | `duel_gru_b1_4a` |
| What | his target choice moves from the hands' (the old rules' imprint) to the strategy head's own, then the target lock and the way pay come out. Combat, item and win pay stay |
| How his target is chosen | (1 - mix) x the hands' choice + mix x the head's own choice (`H2_MIX`, a new buffer in the network, `sim/head2.py`). Where the head has no state yet (from a respawn to its next tick, up to 0.2 s) the hands' choice stands; counted (`head2.copy.no_state`) |
| One learner (b1.2a's blowup) | the hands' target outputs are frozen (`--head2-sole 1`): no gradient, no entropy, no rule's label reach them; only the head learns his target choice, from his whole pay (`--head2-pg 1`, `--head2-pay all`) |
| The copy lesson | stays at the start and fades behind the mix (`H2_COPY`), holding the head near the old choice while it takes over |
| Length | **12 hours** (`--minutes 720`) unless the owner says otherwise ❓ |
| League, checks | b1.3a's end, b1.2d's end, b1.1 and v0.6.0's end as anchors; 200 games (20 a map) every 20 updates against the start (b1.3a's end), every fourth against b1.1; the panel. Never stopped |
| Cores | the trainer on the 8 performance cores; the checks, panel, ramp and logger on 8 efficiency cores; 4 left for the owner |
| Kept | every save during the fades with its optimizer (`keep/policy_fade<update>_b14a.pt`), the first save past each fade (`policy_Adone_b14a.pt`, `Bdone`, `Cdone`), the end |

## The fades (`ramp_b14a.py`, on one clock of updates that stops while a hold is on)

| Fade | Dial | From → to | Updates | About |
|---|---|---|---|---|
| A | `H2_MIX`: his target choice, the hands' → the head's | 0 → 1 | **10 to 50** | 40 updates, 3 h |
| A | `H2_COPY`: the copy lesson's factor | 1 → 0 | 10 to 70 | |
| B | `INTENT_HOLD`: the target lock, seconds | 8 → 0 | **50 to 80** | 30 updates, 2.2 h |
| C | `INTENT_SEEK_W`: the way pay's factor (pay for progress toward his chosen target) | 1 → 0 | **80 to 110** | 30 updates, 2.2 h |
| | settle | | 110 to the end | about 3.5 h |

**Hold:** a check of 40% or less against the start holds the clock until a later check is above it; under 50% flagged. With checks every 20 updates, a hold can act on a check up to 20 updates old.

**Tripwire (flagged in the chat at once; the run never stopped):** the head's own target logits' centred length over 60 (`--raw-lim`; the copy trial's start was about 20, the hands' about 22), a non-finite number, a skipped piece.

**What goes with A:** everything the old rules taught through his target choice: the item rule's order (`PRO_ITEMS`), the pros' openings from each spawn, the stack and spawn routines, the silences (`RULE_CONTEST`, `RULE_HUNT`, `OPEN_SILENT`). From the start their labels reach nothing (the hands' target outputs are frozen); at mix 1 their imprint no longer chooses.

**Not in b1.4a:** the dead switches' removal from the command (no effect on play once the target outputs are frozen; its own commit with an identity check, later); the hunt as the head's choice among the brain's zones and the movement network's look point (b1.5).

## Before the start

| Step | Where it stands |
|---|---|
| The mix in the network (`sim/head2.py`: the buffer, `State.adds`, `seq`'s raw and k, `mix_in`, `np_mix_in`, `np_open`; an old save loads with mix 0) | ✅ built; ✅ unit test (`mix_unit.py`, scratchpad): torch = numpy to 4e-9 at mix 0, 0.3, 1; mix 0 = the old numbers exactly; a seat with no state keeps the hands' choice; `seq` = the live state |
| The trainer (`--head2-mix`, live `H2_MIX`, `H2_COPY`, `INTENT_SEEK_W`; the rollout played and learnt at its mix; the head's lesson through the mix; the league counts a head with a mix; the record: `head2.mix`, `seek_w`, `copy.raw`, `copy.no_state`) | ✅ built, compiles; 🧪 the trial |
| The checks (`test_suite.Policy.set_head2_mix`, `duel_eval --head2-mix`), the plugin (`plugins/netpass.py`), the export (carries `head2.mix`) | ✅ built; the image rebuild before a play test ⏳ |
| `make_files.py` (b1.3a's command with `--head2-pg 1 --head2-mix 0 --head2-sole 1`), settings check against b1.3a's | ✅ PASS |
| `ramp_b14a.py` (the fades, the hold, the tripwire, the kept saves) | ✅ written; 🧪 the trial runs it at a quarter scale |
| `start.ps1` (refuses unless b1.3a's end is there with its head shut and mix 0, the settings check passes, the trial passed or `-NoTrial`) | ✅ written, not run |
| The trial (`trial_b14a.py`, `trial_b14a.log`): from the copy trial's last save, the whole schedule at a quarter scale, 60 min on the CPU | ✅ **ALL PASSED** (11-02 20:32 to 21:38, 136 updates): the mix reached 1, the lock 0 in the simulators, the way pay's factor 0; no NaN, nothing skipped, no tripwire; the hands' target rows the same to the bit, the rest moved; the head's own logits' length 7 at the start, 10 to 13 after (bounded); the three fade saves kept; a check at the save's mix finished. **The respawn reading: `no_state` 0 after the first rollout** (the head resets at a death and ticks through the 2.1 s respawn wait, so it has a state when he spawns) |
| **b1.3a's copy passes** (agreement, and the head playing alone about level: `duel_eval --head2-mix 1` against b1.2d's end, 200 games) | 🧪 11-03 morning |
| The owner's go | ❓ |

## Judged by

| Measure | Wanted |
|---|---|
| Win rate against the start (b1.3a's end) and v0.6.0's end | at least 50% once the fades are done; dips back within 20 to 30 updates |
| The enemy's share of his targets | up ("he needs to fight more") |
| Items a minute, stack at fights, time at spawns | hold (floors from b1.3a's end) |
| No spawn camping (v0.4.4), no holding a spot all game | the panel |
| The head's own logits' length | bounded, no runaway |
| His target switches a minute (after B) | no dithering |
| The share of targets he reaches (after C) | holds: the hands still follow the head |
| The owner's play test | "he picks fights" |

## The equilibrium

The head plans for his whole pay: combat, the item table and the win correction. In self-play the combat and item parts are zero-sum and the win part is the correction both copies gain from getting right. With the lock gone he can change his mind as the game changes; with the way pay gone, getting to an item pays only through the item and what it wins. Expected on the way: more fights when level or ahead with the stack, items when behind or when the enemy is far; the risk is a head that undervalues the items' timing (it learnt them from the rules' imprint) and drifts toward fighting everywhere.

## Red team

| | |
|---|---|
| A hand-over too fast | 40 updates from the rules to the head. If b1.3a's copy is weak (agreement low), the head takes over choices it cannot make yet: the copy lesson stays until update 70 to hold it near; a check of 40% or less holds the clock |
| The head is a slow memory | (b1.3a's card) if its copy stays near the average choice, A is a hand-over to a head that cannot track the situation: b1.3a's verdict decides whether b1.4a starts |
| The respawn reading | feared: the hands' frozen choice deciding his first target after a spawn. Measured in the trial: `no_state` 0 (the head ticks through the respawn wait); watched in the run |
| Lock out → dithering | the 0.02 switch cost stays as a brake; switches a minute watched |
| Way pay out → the hands stop following | the share of targets reached watched; C holds if it falls |
| Item value | the head learns it from the item pay (whole pay); the risk is the timing the rules carried (mega, red armor) |
| Pay pathologies (ledger) | negative frags, sign flips, lopsided games: watched |

## Changes on the fly

| Time | Change | Why |
|---|---|---|
