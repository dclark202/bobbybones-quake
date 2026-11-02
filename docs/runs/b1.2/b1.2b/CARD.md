# b1.2b: every health and armor item priced, the firing costs out, free to re-decide in contact, the jerk cost out

*2026-11-01 (owner): "We need to price ALL the health/armor on the map"; "it should be zero sum"; "remove fire toggle, jerk, weapon switch". The order: "hp/armor pay change; fire toggle/weapon switch/shot cost; contact freedom; jerk fade", "4-6hrs for most, hp/armor can be shorter, and saved between the steps"; "runs until noon Monday 11/2". The family: [README](../README.md). Why contact: [TARGET_LOCK.md](../../../design/TARGET_LOCK.md).*

**Marks:** ✅ built and tested · ⏳ to build · 🧪 to measure · ❓ owner's decision

## The owner's page

| | |
|---|---|
| Started from | **b1.1** (`duel_gru_b1_1a/keep/policy_b1.1.pt`), with `opt_b1.1.pt`, the optimizer of update 170: its own was not kept. No head. b1.2a is not used |
| Run | `duel_gru_b1_2b` |
| Stage 1: the table | at once, with no shut start (owner). `ITEM_RATE_HP` 0.0025 and `ITEM_RATE_AR` 0.002, for points actually gained, zero-sum; in `ITEM_FLAT`'s place on health and armor |
| Stage 2: firing costs | `COST_FIRE_W`, live, on the shot price, the fire-toggle cost and the weapon-switch cost together: 1 → 0.8 → 0.6 → 0.4 → 0.2 → 0 |
| Stage 3: contact freedom | `CONTACT_FREE`, live, the chance a contact is free: 0.25 → 0.5 → 0.75 → 1. A contact is the enemy noticed or heard in the last 2 s. It brings a reading at once, the lock does not hold, and the item rule is silent. Out of contact the 8 s lock stands |
| Stage 4: jerk | `COST_JERK_W`, live: 1 → 0.8 → 0.6 → 0.4 → 0.2 → 0 |
| Stays | `WIN_ADD` 0.33, the big weapons' pay, frags, deaths, damage at weight 1, speed pay, the item rule out of contact, the fairness limits, `!aim default`, 65% games / 35% pro starts. No head |
| Hold rule | goes on above 40%; a check under 50% flagged in the chat; 40% or less holds the next step |
| Length | `--minutes 1185`, to ~11:57 on 11-02 (owner: noon) |
| League, checks | b1.1 and v0.6.0's end as anchors; 160 games, about every 20 updates, against b1.1, each seat at its own contact dial; every fourth against v0.6.0's end; the panel. Never stopped |
| Kept | with its optimizer: each stage's end, to go back to: `keep/policy_table_b12b.pt`, `keep/policy_nofire_b12b.pt`, `keep/policy_contact_b12b.pt`, `keep/policy_end_b12b.pt`; and the save before each step |

## The pay table

Every item pays its rate times the points actually gained, and the enemy loses the same. A full pickup:

| Item | Points | Fills up to | Before | Full pickup |
|---|---|---|---|---|
| Mega | +100 health | 200 | 0.35 flat | **0.25** |
| 50 health | +50 health | 100 | 0 | **0.125** |
| 25 health | +25 health | 100 | 0 | **0.0625** |
| Bubble | +5 health | 200 | 0 | **0.0125** |
| Red armor | +100 armor | 200 | 0.30 flat | **0.20** |
| Yellow armor | +50 armor | 200 | 0.15 flat | **0.10** |
| Green armor | +25 armor | 200 | 0 | **0.05** |
| Shard | +5 armor | 200 | 0 | **0.01** |

## The schedule

Started 11-01 16:12. Clock times at ~4.6 minutes an update. A step comes right after a save. A hold adds to it.

| Update | Clock | What | Save |
|---|---|---|---|
| 0 to 30 | 16:12 to ~18:30 | **the table** in force; read | `policy_table_b12b.pt` at 30 |
| 30 / 40 / 50 / 60 / 70 | ~18:30 / 19:15 / 20:00 / 20:45 / 21:30 | **firing costs** 0.8 / 0.6 / 0.4 / 0.2 / 0 | one before each step |
| 70 to 90 | ~21:30 to 23:05 | held; read | `policy_nofire_b12b.pt` at 90 |
| 90 / 110 / 130 / 150 | ~23:05 / 00:35 / 02:10 / 03:40 | **contact** 25% / 50% / 75% / 100% | one before each step |
| 150 to 170 | ~03:40 to 05:10 | held; read | `policy_contact_b12b.pt` at 170 |
| 170 / 180 / 190 / 200 / 210 | ~05:10 / 06:00 / 06:45 / 07:30 / 08:15 | **jerk** 0.8 / 0.6 / 0.4 / 0.2 / 0 | one before each step |
| 210 to the end | ~08:15 to 11:57 | settles; the run ends itself (`--minutes 1185`) | `policy_end_b12b.pt` |

Stage lengths, with their holds: firing 4:35, contact 6:05, jerk about 4:40 with its settling beyond.

## Judged by

| Measure | Before (b1.1 or b1.2a's start) | Wanted |
|---|---|---|
| Win rate against b1.1, against v0.6.0's end | | at least 50% |
| Pickups by item (`pick_by`) | not split before | small items up; pros' rates from the demos 🧪 |
| Stack at the start of a fight | 139-160 against the owner's 198-254 (b1.0a's games) | up |
| Mega and red armor | 0.8 and 1.0 a minute | hold |
| Firing in view, hit rates | 0.6; rocket 0.46, rail 0.38, lightning 0.38 | firing up, hit rates hold |
| Ammunition, weapon switches | to read | no spam or flicker that costs games |
| Contact (`contact`): free, readings, changes, to the enemy | none | used; the enemy's share up from 1.2% |
| Trips a minute, targets reached | 12.5, 40% | no collapse as in b1.1a (20, 21%) |
| Aim error, on target | 14 degrees or so, 0.22 | hold through stage 4 |
| Fires within 1 s of a sighting, closing (`tools/bobby_yardsticks.py`) | to measure | pros: 79%, +5 u/s |
| The owner's play test | "tunnel vision" | smooth aim, picks up what's near, takes shots |

## The equilibrium

**The table:** both keep their stack up and contest what is near, and a top-up is worth most when hurt. Denial is left to the win part. **Firing costs:** shots cost only ammunition, so both fire whenever a hit is worth more than the ammunition may be later. An even exchange goes from -0.42 to about -0.08 a player-minute at today's volume. **Contact:** both re-decide at contact, so a commitment holds only while nobody is about. **Jerk:** only human limits hold his mouse, so he turns as far as it helps. Frags, damage and winning say whether any of it is good.

## Red team

| | |
|---|---|
| The table may add to tunnel vision | more items carry pay, the big ones about a third less: item pay falls about 25% at today's rates (estimated). Small items are no targets, so they take no lock |
| Denial pays less | a mega at full stack pays little; the pros take it again within 5 s of its return 55% of the time. Measured alternative: the big ones flat |
| A sudden pay change | no shut start (owner). Item pay is ~12% of his pay |
| Spam | the shot price was added on 10-08 because "ammo is a scarce resource". Only the game's ammunition limits him afterwards. `BLIND_RULE`'s cost stays |
| Weapon flicker | `SWITCH_COST` was raised to 0.02 because entropy drowned 0.002. Measured alternative: stop that dial at 0.2 |
| Contact | the only change here with a record of losing games, though b1.1a's was the lock off everywhere, with no way of telling seats apart. He re-samples every second in contact; the reviewer suspects this disturbs the hands. Without a head the hands choose alone. Item pay still pulls at readings, and the rule is silent |
| Pay's level | the costs sum to about -0.88 a player-minute, none zero-sum: his mean pay rises as they go, and values must follow |
| Shaky aim | the jerk cost has kept his mouse smooth. Fairness limits stay. Last for this reason (owner), the saves are the way back |
| Steps against checks | firing and jerk step every 10 updates, a check every 20 or so; b1.1a's harm took about 40 updates to show. A cost may show in the next stage |
| Hold at 40% | below b1.1a's failure (41-42%): a slow loss goes through, flagged only |
| The optimizer | from update 170, with the lock then at 1 s, on a network of update 140, as b1.2a |
| Hand-built / assumed | the rates (owner), points rather than flat, one dial for three costs, the 2 s window, what counts as contact, the schedule |
| Pay pathologies (ledger) | watched in self-play games: negative scores, sign flips, lopsided games. Own splash at full cost against a refill at 0.0025 a point: no pump |
| Rocket jumps, movement jumps, Aerowalk's red armor | important, not in this run (owner) |

## Before the start

| Step | Where it stands |
|---|---|
| The pay, the dials, contact, counters | in `sim/duel_env.py`, regenerated `duel_env_ffa.py`; identity `ident.log` ⏳ |
| Command, ramp, start script | `make_files.py`, `ramp_b12b.py`, `start.ps1`; ramp on a fake run folder ⏳ |
| Smoke run | every dial at its end value, no head, a check with each seat's contact ⏳ |
| Contact on a server | to reach the plugin by `env_vars`; before a play test of stage 3 on ⏳ |
| b1.2a's leftovers | stopped; `keep/policy_end_b12a_UNUSABLE.pt` ✅ |
| A run not approved | a command the owner rejected still ran: `duel_gru_b1_3a`, from b1.1 on an old plan, 15:44 to 16:08 on 11-01, a few updates. Stopped on his word; its folder is `duel_gru_b1_3a_UNAPPROVED_DO_NOT_USE`, its log here `start_unapproved_1544.log`. Not used ✅ |
| The owner's go ✅ | 11-01: "The run we will start is B1.2b, it runs until noon Monday 11/2". Started 16:12 |

Identity, ramp and smoke all ALL PASSED, 11-01 (`ident.log`, `ramp_test.log`, `smoke.log`).

## Changes on the fly

| Time | Change | Why |
|---|---|---|
| 11-01, not done | owner: if the mega's behaviour turns concerning, raise its pay "maybe to .3"; "this doesn't need to happen yet". `ITEM_RATE_HP` 0.003 is live and does it, but raises every health item by a fifth. The mega alone needs a code change and a restart | mega 0.42 to 0.49 a minute in updates 4 to 7, about 0.8 before: too early to read |
