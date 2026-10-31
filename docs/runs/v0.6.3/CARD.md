# v0.6.3: no more hand-built rules telling him what to do, from v0.6.2a's end (DRAFT, not final)

> **Changed 2026-10-30 (owner): "v0.6.2 fades in v0.6.3 fades out. That's it".** The item rule's fade moves here from v0.6.2: it is the
> first thing out, so the groups run item rule → A → C. Where this draft says v0.6.2's end had the rule at 0, that no longer holds.

*2026-10-29 (owner): "I would like them all out before moving to more movement and punishers"; "this should be v0.6.3
and movement should be v0.6.4" ([v0.6.4](../v0.6.4/CARD.md)). From the read-only audit of v0.6.2's end state (2026-10-29).
To be finalised with the owner once v0.6.2 is training. Nothing is built.*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## What v0.6.2 leaves, in plain terms

At v0.6.2a's end the strategy head is fully open beside the item rule (weight 1, see the group below), every other teacher is off and the pay is
win chance only (with the game-end fix of [WINPAY_END.md](../v0.6.1/WINPAY_END.md)). What still decides for him:

| Group | The rule | What it does to him |
|---|---|---|
| **Item rule** | `INTENT_TEACH_W` 1 and its floor | the rule's label on his target choice; faded first, −0.1 a step to 0, `tools/run/ramp_head.py`'s phase 2 (built). Spawn camping came here in v0.4.4; the panel flags it |
| **A. The target lock** | `INTENT_HOLD` 8 s | a target, once chosen, is kept for 8 s unless it is taken, gone or he dies (`sim/duel_env.py:6708`) |
| | `TARGETS_FREE=2` | a holding place can be left only for an item (`:6710-6713`) |
| | `WEAPON_FREE` | choosing a weapon he already holds with ammo is thrown away and read as "nothing" (`:6702-6705`) |
| | `GONE_BELIEF` | his item clock ends the lock early; it disappears with the lock |
| **B. The old belief in the brain** | the 76 rule-made input columns of `sim/rule_fade.py` | **moved ahead of v0.6.2 as [v0.6.1b](../v0.6.1b/CARD.md)** (owner, 2026-10-29): done before this run, not in it |
| | `ITEM_BELIEF`, the item-clock inputs ❓ | a hand-written count from what he saw, heard or took: fair, but counted for him. Out here (with C's fade), or kept? |
| **C. The pros' tables** | the pro-place inputs (80 of 96 unfaded), the 64 holding-place inputs, "pros in this cell" (7) | where the pros stand, hold and pass, as permanent inputs that never fade |

**Not in this run:**
- **Movement** (v0.6.4): the hand-picked jump list (`JUMP_OPEN`, `JUMP_SKIP`), and his movement branch's origin in the old
  movement network.
- **Kept on purpose:**
  - the fairness limits;
  - the game's own behaviour (`AUTO_SWITCH`, `AUTO_HOP`);
  - the owner's walk-means-no-jump rule (`WALK_NO_JUMP`, 2026-10-17);
  - the walking graph that draws the way to a chosen target: his satnav, which people have from knowing the maps.
    Removing it is learned navigation, a project of its own.
- **`HUNT`'s snap** ("the enemy" as a target walks to the route goal nearest where the brain places him) is that same
  satnav and stays.

## The owner's page

| | |
|---|---|
| Goal | the item rule, then groups A and C out (B is done by v0.6.1b), each by a dial from 0 (the rule as today) to 1 (the rule gone), one after the other |
| Network | v0.6.2's end with its optimizer (`keep/policy_end_v062.pt`) |
| Pay | win chance only, as v0.6.2 (the game-end fix in) |
| How a dial moves | as the item rule's in v0.6.2: shut for 10 updates, then +0.1 a step, a step every 10 updates and at least 25 min; held under 50%, back a step under 45% or after two checks under 50%; the next group opens only when the one before reached 1 and held for 10 updates |
| A. The lock | the lock's length shrinks from 8 s to one reading (`INTENT_EVERY`, 1 s); the holding-place and owned-weapon blocks apply on a share (1 - g) of readings. Live dials to build ⏸ |
| C. The tables | first a measure: 160 games against v0.6.2's end with the tables blanked 🧪. A small drop: fade them by (1 - g) as the hands' rule fade does; the item clock with them if the owner says so ❓. A large drop: the owner decides (the fade longer, or kept for later) ❓ |
| Order | item rule → A → C ❓ (the rule first: the head is its direct replacement; A next: the head's own commitment) |
| Timing | about 10 steps a group at ~4 min an update: ~7 h a group, ~21 h with the holds not counted; past the 12 h default, so the owner sets the length before the start (or a group a run) ❓ |
| Aim, mix, maps, league | as v0.6.2 (`!aim default`; 65% whole games / 35% the pros' mid-game starts; the ten maps); v0.6.2's end and v0.6.1's end as anchors ❓ |
| Checks | every 10 updates, 160 games against v0.6.2's end, every fourth against the long-term control; the behaviour panel. Under 40% flagged, under 30% posted. Never stopped |
| Saves kept | group A's end (`keep/policy_noA_v063.pt`), so C can be gone back from alone |
| Play tests | the owner plays each group's end ❓ |

## Before the run

| Step | Passes when |
|---|---|
| The dials for A: `INTENT_HOLD`, `TARGETS_FREE`, `WEAPON_FREE` as live numbers ⏸ | identity: at g = 0 a fixed-seed run is the same as today's, bit for bit |
| The tables' blank for C, then their fade (and the item clock's, if chosen) ⏸ | identity at g = 0; the 160-game measure read before C opens |
| The ramp tool (`tools/run/ramp_head.py`'s pattern, the dials in a row) ⏸ | tested on a fake run folder, as v0.6.2's |
| The settings check | `train.cmd` against v0.6.2's: only `--run` and the new dials differ |

## The checklist

| | |
|---|---|
| Hand-built / assumed parts | the dials' schedule (ten steps, on the clock, held by the checks); the order A → C; the lock's floor of one reading; that the walking graph, `HUNT`'s snap and walk-means-no-jump stay |
| Weaknesses | the dips can add up across the two groups, and the run may end weaker than v0.6.2's end (the checks against it show this). After A his targets may flicker, as before the lock. Removing C may cost positions he took from the pros |
| Pay pathologies (ledger) | as v0.6.2: negative scores, sign flips, lopsided games in the self-play games |
| Watched | **A:** target changes a minute; time on a target; walking off half-way. **C:** time at the pros' places, positions per map. **Both:** items a player-minute, the lightning gun's share |
