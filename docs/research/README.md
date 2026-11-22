# Research notes: how Quake Live duel works, how the best play it, how bots learn it

Written 2026-11-13 on the owner's request: "a lot of the issues ... stem from a lack of understanding about how the game
works". These notes are the reference every training-round decision is checked against (CLAUDE.md hard rule 14).

| File | What | Size |
|---|---|---|
| [MECHANICS.md](MECHANICS.md) | Weapons, damage and armor, items and respawns, movement and strafe physics, aim, sound and senses; **section 7: our simulator against the real game** | ~9,400 words |
| [DUEL_STRATEGY.md](DUEL_STRATEGY.md) | Control, stack, timing, out-of-control play, spawns, information; each of the ten maps; skill levels; aim vs decisions | ~9,800 words |
| [PRO_INTERVIEWS.md](PRO_INTERVIEWS.md) | rapha, cypher, k1llsen, czm, Raisy, ZeRo4, Cooller, toxjq, Vo0, strenx, dkt, Evil... in their own words (from interview and lesson transcripts) | ~9,800 words |
| [BOTS.md](BOTS.md) | FTW (Quake III CTF), VizDoom, OpenAI Five, GT Sophy, CS:GO / Bleeding Edge / Battlefield / Tencent bots, the Quake III bot, hierarchical RL, belief, fairness, self-play pathologies; **section 13: ranked ideas** | ~12,400 words |

Every fact in the files carries a source link and a sure/likely/unsure mark. Gaps (Liquipedia blocked, some videos
without captions, thin map notes for Sinister and Battleforged) are listed in each file.

## The core, in one page

**What wins a duel** (agreed by the guides and every pro read):
1. **Die less than the opponent in the time limit** (rapha). Not "deal more damage", not "pick up more".
2. **The stack decides most fights before they start.** Effective stack = `min(H + A, 3H)` (armor takes 2/3 of each
   hit, so armor counts only up to twice the health). Order of needs: position, then weapon, then aim.
3. **Control = owning the next mega and red spawns** (mega +35 s, red +25 s from the pickup in QL; no in-game timers).
   It is a means to frags and to not dying, not a goal; paying it outright invites spawn camping.
4. **Out of control: don't die again**, restock on the weak side, damage him at his known pickup times and leave, steal
   the item he can't cover, wait for his items to sync, trap and double back.
5. **Information is the hidden stack**: sound (footsteps every 0.34 s with a move key, walking silent, pickups and jumps
   loud, nothing past ~1,330 units), seen pickups, item absence, the spawn rule (far half of the spawn points from the
   enemy), and his needs. Estimate his stack from what he took and what you dealt.
6. **Value a life by what follows a death**: where each respawns, whether control returns. Ahead: run the clock, don't
   force. Behind: don't gamble.
7. **Weapon by range and stack**: burst (rail, rocket) breaks a big stack, streams (LG, PG) finish; LG does nothing
   beyond 768; far rockets pay only as prediction at a place he must go (an item at its time, a door).
8. **Between equal aimers decisions win; the weaker aimer must make fights uneven.** At the top, decisions are the
   limit (ZeRo4, cypher, Raisy, dkt).
9. **No single style wins; adapt.** Practising against one partner builds habits that beat only him (rapha, dkt): a
   self-play warning.

**What the bot research says about our failures** (BOTS.md section 0 and 13):
- No system put an untrained strategy layer over trained hands (1.9a). They pre-trained it, scripted the macro actions,
  or trained jointly from scratch. Teaching the head from predicted outcomes of each order on every tick
  (IntelAct, HIRO-style relabelling, JueWu's value heads) is the strongest fit within rules 12-13.
- Game features help as **prediction targets**, not raw inputs (Arnold, UNREAL; matches 2.0b).
- Self-play alone leaves the agent unready for imprecise opponents (GT Sophy; matches the 11-13 lightning finding):
  varied opponents and small exploiters.
- One high-variance pay part can stop the value from being learned (OpenAI Five); FTW set its pay weights by win rate.
- After any change of the network's shape: a learning-rate-zero warm-up and the same surgery on league snapshots
  (OpenAI Five).

**Where our simulator is off the real game** (MECHANICS.md section 7; to measure on the server before any fix):
knockback of LG/MG/HMG/SG (sim lower; measured and fixed under `KNOCK_QL=1`, 2026-11-13), the shotgun's fixed ring pattern, the hit cylinder vs our box, players passing
through each other, the "weapon already held" pickup and ammo caps, the footstep rule (keys vs speed) and hearing
distances, fall-damage modifiers, plasma splash offset, the forced respawn time. The core numbers (damage, fire rates,
projectile speeds, splash, armor, respawns, switch time, 125/0 spawn) match.

## The decision checklist (hard rule 14)

Every run card, design proposal and pay change gets a **"Research check"** section that answers these, citing the
file and section for each answer. A "not covered by the notes" answer is allowed, and is said plainly.

1. **The game**: which mechanics does the change touch (MECHANICS.md)? Does the simulator model them as the real game
   does (section 7)? If not, the change is built on a sim artefact.
2. **What wins**: which principle of duel play does the change serve (DUEL_STRATEGY.md "Principles distilled",
   PRO_INTERVIEWS.md section 4)? Which does it work against? (E.g. a pay that rewards damage taken in a fight against a
   bigger stack works against principle 2.)
3. **The player's view**: what would a strong player be able to perceive and remember to make this decision (sound,
   timers from heard/seen pickups, his stack estimate, the spawn rule)? Does Bobby have it, as a human has it?
4. **In and out of control**: how does the change play for the controlling player and for the out-of-control
   player? Does it open an exploit (spawn camping, item hugging, never fighting)?
5. **Self-play equilibrium**: what do two copies of Bobby converge to under it, and is that how good duels look per
   the notes? Does a league opponent exist that punishes the bad version?
6. **Bot precedent**: has a system in BOTS.md met this problem? What did it do, what failed?
7. **Rule 12**: no pro outcome (hit rate, weapon share, position) is used as a target; pro numbers appear only as
   measured game facts or human limits, or as labelled readouts.

## Keeping the notes alive

- When a measurement, a run or the owner corrects a note, fix the note (with the date and source) in the same commit.
- New research goes into the matching file; a new topic gets its own file and a row above.
- The "what to measure next" lists (MECHANICS.md 8.6) feed the backlog when the owner takes them up.
