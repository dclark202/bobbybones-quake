# 2.2: new plays, each tried for a whole trip, each with its weapon

**Rewritten 2026-11-16 (owner: "the old versions are no longer relevant, since it's not how 2.1 is ending. Take what we know about 2.1d
and what we hope to get from 2.1e, and start 2.2 from there").** The design of 11-14 is kept whole as
[README_2026-11-14.md](README_2026-11-14.md) (its inventory of built code is still the reference); the reasons for the changes are in
[REVIEW_2026-11-16.md](REVIEW_2026-11-16.md). **A proposal for the owner's design review. No run is carded; nothing here is built.**

## Where 2.2 starts from

| | |
|---|---|
| The network | **2.1e's end** if the slow half earns its place there; otherwise **2.1d's end** (`duel_gru_2_1d/keep/policy_end_21d.pt`, update 158) |
| How he chooses a goal now | every 0.2 s the head scores 17 targets (the hands' rows + the head's scores); **the held draw** picks one and keeps it until the trip ends (reached, gone, respawn) or something else scores higher; **the pull** adds the plan's forecast of his own goals, so a new idea has to beat a bar. No lock, no keep choice, no judge of forks |
| What 2.1d showed | lock out, level held: 52.0% against 2.1c's end, 55.0% against 2.0e's end; **31.5% with the pull at 0**. The pull steadies him in part: 40 mid-trip changes a seat-minute, 45% taken back within 2 s |
| What 2.1e is testing (running 11-16) | a slow half of the head: a memory of its own that holds the plan between ticks. If it works it is where a long play is held and where slow information enters. If it does not, 2.2 stands on the pull alone |
| The head's pay as it runs | the whole pay, the damage in it (`--head2-pay all`), credit over about 12 s. See "Open for the owner" 4 |

## The goal (the owner's, unchanged)

"His mechanical hands are reactionary, they see the enemy and fight when he's in sight. The head makes a decision saying 'you better shoot
a rocket there to deny him' and then he acts on it when the hands have no idea to do that." His list of goals grows from "go to one of 17
items" to the plays a duel player makes: **deny an item at its time, hold an angle, cut him off, break off.** He makes deliberate choices
and he fights. What must not happen with the lock out: walking around aimlessly, or camping one item as 1.7a did.

## What carries over from 11-14 (decided by the owner; kept)

| # | Decision |
|---|---|
| 1 | A new play is **a row added to the target choice** (the hands' row + the head's score). **No second chooser** |
| 2 | **The weapon and the trigger are sums**: the hands' scores plus the head's. Nothing binds; the hands can always disagree; no dial shrinks the hands' part |
| 3 | **Every sum is regularized from its first update** (`H2_L2` on both parts), each part's size recorded and flagged over 40 (rule 11) |
| 4 | **One new play a step.** Its weapon recommendation opens with it |
| 5 | **The hands stay reactive and stay paid by the pay table.** Timid (not firing with the enemy in view) is never right; playing to not die is |
| 6 | No table, no pro target, no weapon or shot share as a pass mark; no cost for firing, switching or holding (rule 12; owner 11-04) |

## What changes from 11-14, and why

| Was | Now | Why |
|---|---|---|
| Starts from "the keep choice holding", "the should-I-do-X method proven" | starts from the held draw, the plan and the pull | that is how 2.1 ended |
| A play's forecast learns from frozen moments where it is forced, then its row opens | **a play is learnt by playing it: trial trips.** On a small share of his trips (a live dial) the new row is his goal, held to the trip's end; the head's credit and the plan learn from those trips | the fork method showed no skill twice (2.1a, 2.1b: one fork's difference is noise many times the effect). The held draw makes a whole-trip trial possible, which nothing before 2.1 could (1.9a changed its order on 95% of ticks) |
| A new row is opened by a small bias | **it must be given trial trips**: the pull puts any row the plan does not yet forecast about 9 points down, so a bias alone would never be drawn | the pull's own arithmetic (2 x log of plan odds, floor 0.01) |
| Step order: hold a spot, deny, cut off, break off | **cover an item at its time first; break off; cut off; an angle away from items last (2.3)** | a scripted hold with perfect aim loses to free play (−20.4; his own aim −9.4; free about 0) and a free "hold here" became camping (v0.4.3, 1.9a). His copies take the mega 0.8 s after its spawn: a denial has a known time and place (DUEL_STRATEGY principles 5 and 13, section 5.4) |
| Hold and deny as two plays | **one play, "cover an item", with the weapon deciding**: a rail on the mega's approach before its spawn is a denial with a hitscan weapon | fewer new parts; every cover has an end |
| No word on what ends a play | **every play comes with what ends its trip** (the item's clock, contact made or lost) | the held draw ends a trip at an item; a play with no end is camping |
| Drills first, no pass mark | **the scripted play measured first, then drills with a pass mark** | the rule of 2.1's own design: "A verb whose perfect script loses to free play cannot be learnt by drills: that is then the finding, and it is fixed first" |
| The trigger taught from frozen moments (the head's score the main source) | ❓ **the hands are shown the point and learn the shot as any damage; the head's trigger score a small helper** | the head's fire push did nothing in 1.7a and had no lesson; the frozen-moment lesson is the method that failed. Open for the owner 3 |
| Step 0: the map sense as head inputs | **into the slow half if 2.1e supports it; otherwise after the first play** | 2.0b: per-place inputs into the fast chooser made his target unstable. It is not needed to cover an item, whose place and time he has |
| Step 1: the head paid by the win chance only | **not in 2.2's first steps; its own step in [2.3](../2.3/README.md)** | the judge cannot see items and would misprice the item plays; never run; 2.1's result came under the whole pay |

## The steps (one after the other; each ends on its measure, reported; nothing holds or steps back on its own)

Each step has the same five parts.

| Part | What happens | Read before the next part |
|---|---|---|
| a. The scripted play | a perfect script of the play against free play, on the current hands, his copies as opponents (recorded moments; no training) | does the perfect play beat free play, and by how much? If not: the play is not learnable as defined, and the step is redesigned |
| b. Drills | on drill trips the hands are given the place and the point and must carry the play out | the share of drill trips on which it is carried out (for a cover: at the spot with a line to the item, and the shot fired around its time) |
| c. Trial trips | the row is his goal on a small share of his trips, opened slowly; the head's credit and the plan learn what such a trip is worth | the play's result on trial trips against (a)'s mark; the guards |
| d. On its own | the trial share falls; the row lives or dies by the draw | how often he chooses it, when, and the checks |
| e. Blanked | at the step's end, 200 games with the row shut | no drop = it does not stay (the rule for every new part) |

| Step | The play | What ends its trip | The hands need | The head recommends |
|---|---|---|---|---|
| 1 | **Cover an item at its time** (mega and red first): be at a spot with a line to the item and fire as it spawns | the item's clock (a few seconds after the spawn), or the enemy in view | go to a spot that is not an item; look at a point with nobody in view; fire at it | the weapon to bring (rockets, or the rail); the trigger per "Open" 3 |
| 2 | **Break off**: leave a fight he is losing by a way out | out of contact | take the way | nothing |
| 3 | **Cut him off**: go where the brain forecasts him in 1, 2 and 4 s | contact, or the forecast gone | go there | the weapon to arrive with |

"Hold an angle away from the items" is not a step here: nothing in his world walks into one. It is 2.3's, with the opponent that makes it pay.

## Guards from update 1 of every step (reported; the owner decides)

| Guard | Line |
|---|---|
| **He fights**: frags and damage dealt a match-minute | no slide from the step's start |
| **He fires with the enemy in view** (timid) | must not fall from the step's start (training about 60%) |
| **Camping**: the share of his pickups on his single most-taken item; time near one item with the enemy out of view | no rise from the step's start (to be built from the checks' recorded games; owner 11-15) |
| **Wandering**: time on a goal he is not closing on | no rise (to be built) |
| The dithering measure of 2.1: mid-trip changes taken back within 2 s | no rise |
| The head's weapon and trigger scores with the enemy in view | stay small against the hands' |
| Weapon changes a minute | flag over 20 (1.9a: 107) |
| Shots with nobody in view: how many, what they hit | a readout (no cost is added) |
| Each part of each sum | flag over 40 (rule 11) |
| Every check against the step's start | one under 40% flagged at once |

Trips a minute is reported as a plain number and never read as progress or as a fault (owner, 11-15).

## Open for the owner (for the design review; my recommendation first)

1. **The first play**: cover an item at its time, hold folded into it by the weapon. (The alternative: the 11-14 order, hold first.)
2. **Trial trips** as the way a new row opens, replacing the forecasts from forced moments.
3. **Where the shot is learnt**: the hands shown the point (the seven "firing solution on the point" inputs exist) and paid as any
   damage, the head's trigger score added as a small part. The alternative, the head's trigger as the main source of a shot the hands
   "have no idea" about, is the 11-14 wording and needs a lesson nobody has made work.
4. **The head's pay.** The owner, 11-11: the head "should absolutely not be paid for doing damage". Every run since 2.0e pays the head
   its whole pay, the damage in it. My recommendation: leave it as it runs through 2.2's steps, and take win-chance-only up as its own
   step in 2.3 after a judge that sees items. To be decided knowingly either way.
5. **The map sense**: into the slow half if 2.1e supports it.
6. **Which spots** a cover uses: the candidate places built for 1.7 (`tools/order_maps.py`), re-checked for a line to the item.

## Weaknesses to carry into the first card

- It still starts from a play we chose, not one he found. The scripted measure and the trial share are the guards.
- His copies can answer a known cover spot by not coming on time; the measured gain may fade. That is a right answer (principle 7).
- A cover trip is time not spent taking items himself.
- The lightning habit (about 60% in hand) is untouched; a rocket denial asks for rockets in hand.
- The hands have never been shown to fire at a point with nobody in view (1.7a: "he goes to the spot and does not fire").
- The trial share is a hand-set dial; too large and it is the 1.9a failure (a part playing before it has learnt).
- The server: the plugins call `observe()` and never `step()`; a play's clock and trip end must be set by the plugin.
- If the slow half does not hold (2.1e's early reading: it ticks mostly on his changes of mind), plays longer than a few seconds lean
  on the pull alone.
- A Research check (rule 14) is owed on each step's card.

## My odds for step 1 (rule 15)

A perfect cover beats free play against his copies: about 60%. Given that, the hands learn the shot on drills and trial trips: about
55%. The row then survives on its own without costing checks: about 40%. It shows as a gain against the control within one run: about
25%; against people, who also walk to items on time, sooner.
