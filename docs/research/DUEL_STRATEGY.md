# Duel strategy: what the guides teach

*Research notes, 2026-11-13. Scope: Quake Live 1v1 duel strategy as written down in guides, tutorials, forum
lessons and analysis. The pros' own interviews are in `PRO_INTERVIEWS.md`, the raw mechanics in `MECHANICS.md`
(other agents). Nothing here is a design decision; the last two parts are proposals for the owner to weigh.*

**How to read this.** Every idea carries its source (a numbered reference, list at the end). Most of what exists
in writing about QL duel is in ESReality forum threads from 2010 to 2018: real players, often good ones, but
opinions, not tested facts. Where a claim is my reading, a game rule I checked in code, or a fact from this
repository's own data, it says so. **[?]** marks an uncertain point. Older games (QuakeWorld, Quake 2) and
Quake Champions are used only where the idea transfers; the difference is noted.

**What I could not read.** Liquipedia's Arena FPS wiki (the map pages) answers every automated fetch with a
human check, which I did not pass; the Wayback Machine is closed to the fetch tool. YouTube lessons (Strenx's
duel lesson, av3k's Blood Run tutorial, Fraze's tutorials, ShockeD's commentary series with its "Timing
Tutorial", "Quake Live Lesson #2" on rail angles) are known by title from the forums [R13, R19] but have no
transcripts I could reach. Memento_Mori's "Duel Guide for CA Players" pages and the ESReality duel wiki page
were not served. The per-map part is thinner than I wanted for that reason; the gaps are named.

---

## Part 1. Core concepts

### 1.1 Stack: what it is and why it decides fights

- **Stack = health + armor**, the amount of damage you can take. Chance's "Quake Bible" calls the opponent's
  health, armor, weapons, ammo and position his "status" and makes it the first thing to track; the maximum is
  200/200 [R4]. Every guide treats the fight as decided first by who has more stack, then by position and weapon,
  then by aim [R3, R4, R12].
- **Effective stack (my derivation from the game rule, the simulator's `duel_env.py` header: armor absorbs 2/3 of
  damage).** A player dies when health hits 0. With enough armor, health takes a third of each hit, so the damage
  needed to kill is `min(3H, H + A)`. 100/0 dies to 100; 100/100 to 200; 200/200 to 400; 100/200 to 300; 25/200
  to only 75. So armor is worth its full value only while health is at least half of it: low health with high
  armor is fragile. Guides talk in totals ("175/150", "200/160 vs 100/150") [R8, R14]; the real comparison is
  this effective number.
- **Stack income per minute (Memento_Mori [R3]).** The "big stack" (mega and red, each taken every time it spawns)
  is at most 411 points a minute; the "small stack" (two yellows) 240. These follow from the respawn times (mega
  100 every 35 s = 171/min; red 100 every 25 s = 240/min; a yellow 50 every 25 s = 120/min). His use of it:
  over a game, the player out of control must out-damage the stack difference to stay level. In his own Toxicity
  example he dealt 3,470 damage in ten minutes against an opponent on the big stack, and says he needed at least
  4,110 to have a chance. A rail is "almost a mega or a red" by this arithmetic [R10].
- **Stack decides when to fight.** "Don't fight unless you have a huge stack and are sure you'll win; otherwise deal
  damage and collect stack" [R12, h8m3]. One player's rule of thumb: no fight below 90 health and 75 armor
  [R12, Jamerio]. A QC guide: "You can't push it with a 25/25 stack" [R8]. With an advantage press; at a
  disadvantage wait for a mistake or go and stack [R4].
- **Small items are stack too.** Out-of-control players build 100 to 150 armor from the yellow, green and shards in
  about 25 to 30 s on Hektik and Cure [R21, R22]; "2 YA = 1 RA" [R14]; "do not underestimate the green armor"
  [R18]. Several maps have a "weak side" with a yellow and some health precisely so a beaten player can rebuild
  [R22 thread note: Campgrounds, Cure, Blood Run].
- **Taking the stack away is half of it.** Steal his small items to keep his stack and options low when you are in
  control [R6]; "starving your rival of ammo and health" [R5].

### 1.2 Control: in control and out of control

- **Definition.** Control means owning the big items (mega and red), so that over the cycles your stack income is
  the big stack and his is the small one [R3, R6]. In a neutral cycle each player takes one of the two; when one
  player collects both he "has control" [R17 summary of the QL Blood Run layout; same idea in R6, R8]. Control also
  means owning the weapons [R4]: holding LG, RL or rail when he does not, and fighting at your weapon's range.
- **Why it snowballs.** The player in control has more stack, so he wins more fights, so he frags more, so the
  other spawns with a machine gun and 125 health far from the items, so control continues. ChillOut: stack and map
  control give the better-stacked player more spawn frags and freedom to set up angles [R3 comments].
- **Control is a place as much as a set of items.** On Aerowalk the in-control player holds the lower RL room, "the
  most important position on the map", which watches the routes out of the other side, with the RA room behind it
  [R18]. On Furious Heights, standing in the doorway between the two main rooms and listening blocks the opponent
  from the key items without seeing him [R23]. On Blood Run the 50 health bubble "controls the whole map" [R14,
  hitsu]. Control positions sit between the enemy's likely spawns and the big items, with escape routes.
- **Control is not the goal.** "The goal of a duel is to score most frags, not to eat most pickups" [R11 comments,
  fau]. Several warn against playing the map instead of the player: one controller held the "best control" award
  and still lost most games [R12, gSTRUCTOR]. Control is the means; frags and the score are the end.

### 1.3 Item timing (the "timer" skill)

**The game rule (checked in code).** Quake 3's `g_items.c` (ioquake3): armor respawns 25 s after pickup, health 35,
**mega health 35 (from pickup, not after its extra health has decayed)**, ammo 40 [R30]. The repository's
simulator uses the same (armor 25, mega 35, weapons 5 in duel, ammo 40). QL players time **red +25, mega +35**
[R25 Oaki_Duke thread, Tox quoted: "the +25 on all the 60 combinations"]. The Dignitas article's "both on 30 s"
[R1] is Quake Champions; QuakeWorld's 20 s armor and decay-dependent mega are QuakeWorld's [R16]. **[?]** One 2010
thread summary has the two swapped; the posters' own examples there use +25 for red [R24].

**How players count.**
- Note the clock at the pickup (seen or heard), add the offset, and remember the result [R6]. The ESReality basic
  timing guide's three steps: catch the pickup; compute the next spawn (memorized pairs, not arithmetic); fit it
  into your plan so it sticks [R6].
- Memorization: flashcards of 00 to 59 against +25 (two weeks for the armor "language", then mega) [R25,
  Memento_Mori]; digit tricks (+2 or +3 on the tens digit mod 6, +5 on the units) [R24]; "+25 is the same as
  -35" on a 60-second clock, so one table serves both [R24, R25]. Rapha's advice as reported: "learn two new
  languages", the armor and mega times; he was said to time up to five items [R25].
- Say it aloud or repeat it in a rhythm [R1, R4, R8]. Recall under fire is the real difficulty, not the arithmetic
  ("The problem isn't calculating, it's remembering", FlashSoul [R25]); harassment makes people forget [R25].
- Time the next item to come first: confusing the order (mega before red) is the classic error [R4].
- Do not time items that respawn in a few seconds; prioritize mega and red; on some maps the yellow too [R4, R24].
- The out-of-control player mainly times armors, "because their order doesn't change": time one armor and the rest
  of the armors and shards follow a cycle [R6 page 2].
- A dead player can wait up to about 5 s before respawning to see or hear the pickup and catch its time [R6 page 1].
  (This repository measured the QL respawn wait: back at 2.1 s at the earliest, forced at 4.5 s [`sim/duel_env.py`,
  `RESPAWN_QL`].)
- Enemy timings come from his pickups seen or heard; if he is seen leaving an item, subtract 2 to 5 s [R24, zealot];
  item absence and his health tell you too [R26].

**What timing is for.** "The largest advantage of timing is not knowing the time but knowing which item comes up and
how your opponent can attack it" [R24, R27 Weird]. Exact seconds matter only in the fight at the item; the rest is
knowing the gaps and which routes are safe [R27]. "Timing for its own sake is useless": act on it [R27, maza].
Without it "you aren't ever in position to take RA/MH or do damage on it" [R27, grume].

**Rules of thumb from the timing guide (Memento_Mori, ESReality 2011 [R6 page 2]).**

| Rule | What it says |
|---|---|
| Five-second rule | about 5 s gets you from anywhere to anywhere on a duel map; subtract 5 from the time to the next big spawn to see what you can do. 15 s or more: room for a real action. 7 s or less: go and secure the item |
| Delay rule | taking red about 10 s after mega puts the two in sync (35 = 25 + 10) and lets the opponent take one while you take the other. Take red within 5 s of mega or 15+ s after; around 10 s is "really wrong" |
| Double red | red taken within 5 s after mega gives a second red before the next mega |
| Steal | in control, steal his minor items; out of control, steal a big one when he makes a mistake |

Other players: keep mega and red at least 5 s apart [R24]; "always delay RA so it never clashes with mega"
[R14 on Furious Heights]; round pickups to :x0 or :x5 to simplify (good players notice) [R24]; delay to confuse
or to set a trap [R24]; the 35 s grid repeats every 70 s for mega and resets at 7:00 [R24]; arrive at mega about
5 s before it spawns [R12, InDepther on Campgrounds; R22 ischju on Cure for the out-of-control player].

**Denying** = taking an item you do not need (so he cannot), or making its pickup cost him. Spam the item before it
spawns: grenades 2 to 3 s before mega [R18]; spam mega from red's side to shift its timing so you can steal one
while he takes the other [R14]. Damage "voids" an item: a red taken at 50/50 after 100 points of spam is worth less
[R31 Toxicity note].

### 1.4 Trading and giving up items

- **Give up an item when its price is too high.** Dignitas, for the controlling player: you do not have to take a
  powerup the instant it spawns; if the enemy's position is known, leaving an undisputed item can be right [R1].
  Weird's breakdown of a 2000-Elo hopeful's demo: trading damage with no item gain left him behind; a small LG hit
  on a healthy opponent on his way to red is a poor trade [R27].
- **Trade one for the other.** With the two big items desynced, the controlling player can lose one and keep the
  other; with them in sync he must choose, and the opponent takes the other [R6, R14].
- **Bait.** Big items are bait: "push a yellow at the right time and hit rails" while he goes for the big one [R14,
  hitsu]; leave a yellow up as bait and camp the RL to deny it [R14, jamalz]; leave red up, hide, and LG him as he
  jumps to it [R14, Deadlynoob, Blood Run].
- **On Aerowalk** do not kill the opponent on the YA side when red is about to be his: he may respawn near red
  [R18 comment, sTPHN; same idea in QW: "don't kill while the RA is open to you; take the armor first" R15].

### 1.5 The out-of-control player's playbook

Collected from [R6, R8, R12, R14, R18, R19, R21, R22, R23, R26, R27, R28]. The common core:

1. **Do not die again.** "Don't let your opponent frag you again. Ever." [R8]. "It's a lot easier to come back
   from 3-0 than 10-0" (myrm1don, quoted in [R8]). Survival training [R28]. Keep the frag count low [R26].
2. **Slow down and restock.** Get weapons and small items, by walking where it matters [R8]; "it's okay to give the
   items up for more equipment" [R8]; stack on the weak side's yellow, green and shards [R21, R23].
3. **Deal damage at his pickups, then leave.** The rich target is the item: he must come to it at a known time.
   "Get into position to deal damage as the opponent picks up items, then leave without taking damage" [R26,
   magadog]. Spam the item and its approaches with grenades and rockets [R14, R18, R31]; rail him at the mega from
   cover [R23]. Make his stack worth less than it reads: "don't let your opponent make use of the stack he gains"
   [R8].
4. **Steal at a timing.** When he commits to one big item, take the other [R6, R14]. On Furious Heights wait on
   grenades to guess his route, then go the other way to a free yellow [R29].
5. **Ambush and trap.** Traps at chokepoints, quiet movement, listening [R12]; doubling back ("go one way, return
   once he has reacted to the first movement", timed with items and covered by a sound cue) [R12]. Know when a trap
   is worth committing to; overcommitting throws games [R12, loveless].
6. **Avoid the obvious.** Do not rush the rail right after spawning: it is the known spawn kill on Furious Heights
   and Blood Run [R14, R23]. "Rail whoring" makes you predictable [R14, R23].
7. **Punish aggression.** If he comes in full speed, make space and land shots as he beelines [R8]; spam
   defensively when chased [R12]; against an over-offensive opponent avoid head-on fights and deny with splash
   and LG threats [R15].
8. **Take small fights with the small stack.** At 100/150 against 200/160 take small fights and heal on the 50s
   [R14, Deadlynoob]; trade a death for his frag only when killing him strips his weapons [R28].
9. **Know where he is.** Sound, item disappearance, his last frag place, spawn logic [R13, R26].

A dissent worth keeping: on small control maps (Hektik, Cure) the out-of-control side has little room and "cannot
set up any traps at all" [R21]; on Cure at 5:0 it is "hard to come back" [R22]. Maps differ in how much a lead
locks.

### 1.6 The in-control player's playbook

- **Time both big items, desynced; arrive early; hold the position between him and them** [R6, R14, R18].
- **Steal his small items**, so he cannot rebuild [R6, R29 EVOL: "deny the yellow armor"].
- **Mix up routes and delay timings** to stay unpredictable; take the high ground; listen [R8].
- **Defensive style**: traps, walking (quiet), spamming the entries to your area, reading his moves [R8].
- **Aggressive style**: spawn frags (by where you stand: see 1.7), rocket rushes, take everything fast so "there is
  nothing to play for" [R8].
- **Don't chase blindly; never give up the position for a frag that may not come.** "Dont give up your position EVER"
  (juM8o on the lower RL on Aerowalk [R19]). The QC guide: chasing a retreating enemy over-extends and misses the
  timing [R32].
- **Do damage, leave, make him "needy"** [R19, juM8o]: initiate, take a chunk, break off before the return damage.

### 1.7 Spawns in Quake Live

**The rule.**
- Quake 3 (ioquake3 `g_client.c`): spawn spots that would telefrag are skipped, the rest are sorted by distance from
  the dying player's own position, and one is drawn at random from the **far half** [R30].
- Quake Live changed it for duel. A 31 May 2011 update, quoted on ESReality: "Relaxed spawn system in Duel such that
  it now looks at 50% of the furthest away spawn choices with a minimum of 3 choices", read by players as **the far
  half from the opponent**, at random, never fewer than three candidates [R33]. In 2012 the developers offered a
  "Spawn Furthest" setting in Start-a-Match (above 0.5 = fewer candidates, 0.7 suggested) and said "add more
  randomness" [R34]. 2014's rulesets left classic duel as the default [R35] **[?] whether later patches changed
  the duel rule**.
- **This repository measured it.** On 14,937 pro respawns (twelve maps, spectator demos with the enemy's place known),
  "random among the far half of the spawn points from the enemy" fits best: 86.9% inside that half, against 70.2%
  for Quake 3's far half from the death place and 50% for uniform (`sim/duel_env.py`, `SPAWN_QL`). `info_player_start`
  counts as a spawn point on Furious Heights and Dismemberment (also noticed by players in 2012 [R23]).

**What players do with it.**
- **Force spawns by where you stand.** Because the candidates are the far half from you, your position decides
  which half he spawns in. On Furious Heights, standing at the top between LG and top RL forces him to the corner
  near the GL door ("the best position when you need frags") [R23]. On Blood Run under the 2012 spawns, holding
  the mega niche put the opponent into the rail or RL spawns, where a rail player killed him [R34]; one tester
  "can predict spawn from ANY position" [R34]. On Aerowalk, staying on the RA side makes him spawn at GL [R19].
- **Read the spawn.** If he did not show at the rail, listen at GL and aim at RL; if not there, he is in the PG room
  with its three exits, coverable from GL [R33, aeoL].
- **Spawn frags.** A player fragged at mega had roughly a 50% chance to respawn at the rail spawn: "5-6 frags in a
  row" [R33]. Controlling the upper YA exits on Blood Run meant the opponent "cant leave without taking damage"
  [R34].
- **The newly spawned player** (machine gun and gauntlet only, low stack; **[?]** the exact spawn health and armor are
  in `MECHANICS.md` and the simulator's `SPAWN_HP`, not from a guide) goes for the nearest good weapon or health [R28]; the controller waits there or covers the exits.
- **The first minute after a frag** is where the snowball happens (1.2). The guides frame it as a choice for the
  controller: hunt the spawn (frags) or let him run and take the items (stack). The QC guide lists spawn fragging
  under the aggressive style [R8]; ChillOut suggests fresh-spawn timing such as waiting before grabbing the LG when
  he is near [R3]; on Aerowalk, rush the yellow only "straight after picking up the red", or he respawns at red and
  takes control [R19].
- **Opening spawns** (the first spawn of the game) are their own lesson: baksteen's Lost World lesson #1 is entirely
  about the first route from each start [R36]; "learn the openings" [R27].

### 1.8 The frag-and-control loop, and the clock and score

- The loop: stack → fight won → frag → he respawns weak and far → controller takes the next items → stack. The
  out-of-control player breaks it by not dying, by damage at the items, and by steals at the timing (1.5).
- **Ahead**: keep control, run the items, protect the lead [R5]; "if you are unable to make frags then keep the score
  as even as possible"; "you have the decision and the dictation when to take engagements" [R8]. Against an
  over-offensive opponent, wait him out if you lead [R15].
- **Even**: watch for his mistakes and wait for an opening [R5].
- **Behind**: avoid unnecessary deaths, use surprise [R5]; do not "throw away frags in half-assed attacks or angry
  retorts" [R8]. Pressure late in a game makes players push too hard [R26, Brainie]. The guides I found say little
  about forcing fights in the last minute when behind; the general rule is "don't rush" [R8] **[?] a gap**.
- Sudden death: QL duel goes to overtime on a tie (my knowledge of the rules; not from a guide here **[?]**).

### 1.9 Positions: height, chokepoints, angles

- "Take the high ground at all times" [R8]; "maintain a height advantage" [R5]. Vertical fights in red rooms are a
  map feature (Sinister) [R37].
- **Right position, right weapon, right aim, in that order** [R3]. A spot good for LG can be bad for rail if there is
  no escape after a miss; angles are map-specific [R3].
- **Rail spots need a safe position and an exit** [R3]. Peek rail from mega or LG; don't rail while pushing [R14].
- **Escape routes**: "always leave yourself an escape" [R15]; learn positions with several exits [R12, qr]; don't get
  cornered: good opponents try to force it [R4]. On Aerowalk the red is on a ledge with only one way out forward,
  easy to be trapped on [R20].
- Choke points and doorways are where spam pays: spam the exits of his area [R15]; spam teleporter exits [R38].

### 1.10 Pre-firing and spam

- "Spam is one of the primary sources of damage" unless stealthy or low on ammo [R3]. Rockets and grenades at
  doorways, corners, teleporter exits and item spots [R14, R18, R19]; prediction shots where he wants to go [R15].
- Grenades to listen: drop grenades at mega to hear if he is there [R14, Deadlynoob]; "wait on nades to guess his
  route" [R29].
- Plasma is called the best trap weapon and a spawn-spam weapon ("insta 100 dmg") [R38].
- Projectiles also throw off the opponent's aim [R12, ika]; rockets beat LG close up for some players [R12].

### 1.11 Weapons by range and stack

- LG for mid-range tracking when you can "get in their face"; rockets against fast runners and up close; rail from
  safe angles at range [R14]. Out of control, rockets and grenades over aim duels; "dont rely on aim, biggest
  mistake ever" [R14, Daddy_].
- **Weapon control is control**: deny him the LG, RL or rail that wins at the range the map forces [R4]; on Lost World
  the RL and the LG each sit where the other has the advantage, and lopsided games come from one player holding
  both [R39]. Railgun denial near red or mega [R12].
- **Over-reliance on one weapon is named as a mistake** in several threads: "71% [LG] usage is not healthy" (HippY, to
  a player asking for advice [R14]); players who "rely only on the lightning gun or rocket launcher" (tnz [R40]);
  "avoid constant LG use" [R26, megaman3]. These are human coaching remarks about balance, given as advice, not
  measured outcomes; see Part 5 on how not to use them.

### 1.12 Sound discipline and information

- Listen: jumps, pickups, weapon switches and landings tell you where he is [R13, R15, R26]. Headphones; music off
  [R28, R41].
- Walk to be quiet: the walk bind, "walk frequently" when defending [R8, R12]; "if not in control, do not make sounds"
  [R8]. Pickups (shards, armor) make sounds that give you away; double-backs can be timed with such a sound so he
  does not expect you [R12, eburbeck].
- On Sinister the rail's respawn has a gong heard map-wide (with ambient sounds on) [R37].
- **Information = prediction.** The QuakeWorld strategy page and inertia's Aerowalk guide put the whole game on
  "prediction and counter-prediction": you gain when you guess his move right and when he guesses yours wrong, so
  predict and stay unpredictable [R5, R15]. Weird's three questions before every fight: what do I want, what does he
  want, what is the best counter to his likely plan [R27]. Assume a weakened opponent has picked up health since,
  and deduce what he has from the pickups you saw [R27]. Chance dissents: read and react, "you can not predict what a
  person will do" [R4].

### 1.13 Baiting and respect of damage

- Bait with items (1.4), with sound (a deliberate pickup or jump), with a visible retreat into a prepared spot (a
  chased player runs for items: pre-aim there [R42]).
- **Respect damage**: duel "is decided by avoiding hits more than dealing damage" [R26 tbone]; "survival is as
  important as fragging" [R8]; "it's very rare that the player with the least damage taken wins" is a garbled line in
  [R8] (it says the opposite of what is meant: the player who takes less damage usually wins). Cypher's edge as
  described by a forum player: he "takes little damage in return" [R26, qr]. Position so you end every fight on 20 to
  50 health at worst [R12, MailmanMel].
- "Committal: don't enter a fight you aren't sure to win" [R15].

---

## Part 2. The maps

**Repository facts first.** The duel item sets below are from `plugins/duel_items.json` (the game's own duel items);
the spawn counts and straight-line distances are from the maps' entity lumps in `data/maps/*.bsp` (my script, not
path lengths). "Spawns within 700u" counts spawn points near an item (a rough index of how often a fresh spawn is
near it). These are facts of the maps, safe to use.

| Map | Spawns | Big items | Weapons | Red to mega (straight, height) | Spawns near red / mega / a yellow (700u) |
|---|---|---|---|---|---|
| Aerowalk | 8 | RA, MH, YA, 2 GA | RL x2, RG, LG, GL, SG | 707u, red 288 higher | 3 / 3 / 2 |
| Battleforged | 9 | RA, MH, YA, GA | RL x2, RG, LG, PG, GL, SG | 1,581u, red 312 higher | 3 / 3 / 1 |
| Blood Run | 10 | RA, MH, YA x2 | RL, RG, LG, PG, GL, SG | 1,071u, red 447 higher | 2 / 3 / 2 and 4 |
| Campgrounds | 27 | RA, MH, YA | RL, RG, LG, PG, GL, SG x2 | 1,383u | 3 / 5 / 11 |
| Cure | 12 | RA, MH, YA, 2 GA | RL x2, RG, LG, PG, GL, SG | 1,293u, mega 255 higher | 3 / 1 / 3 |
| Furious Heights | 17 (16 + a start) | RA, MH, YA x2 | RL x2, RG, LG, PG, GL, SG | 1,901u, mega 473 higher | 6 / 3 / 4 and 6 |
| Hektik | 10 | RA, MH, YA, GA | RL x2, RG, LG, PG, GL, SG | 546u, red 463 higher | 1 / 3 / 5 |
| Lost World | 18 | RA, MH, YA x2 | RL, LG, PG, GL, SG; **no rail** | 781u, mega 237 higher | 7 / 8 / 8 and 6 |
| Sinister | 11 | RA, MH, YA x2 | RL x2, RG, LG, PG, GL, SG | 1,359u, red 535 higher | 2 / 3 / 4 and 2 |
| Toxicity | 8 | RA, MH, YA x2 | RL x2, RG, LG, PG, GL | 1,256u, mega 240 higher | 2 / 3 / 2 and 2 |

Notes on the table: Hektik and Aerowalk have the big items close together (one player can watch both); Furious
Heights and Battleforged have them far apart (a neutral cycle of one each is natural). Lost World's spawns cluster
near every item. Red sits high on Aerowalk, Blood Run, Hektik and Sinister (jumps and ledges to reach it, a fall or
a trap when leaving).

### Aerowalk (Quake Live; the Q3 remix of Preacher's map)
- **Two sides** [R18]: the RA side (red, lower RL, mega) is the control side; the YA side (GL, upper RL, rail, the
  teleporter) the out-of-control side. Pivot points: the lower RL room ("the most important position", it sees and
  interrupts his movement) and the RA room behind it. Never let him be in the RA room right before red spawns.
- **In control** [R18]: hold lower RL, cut him off as he leaves his basement; when he passes upper RL toward LG, move
  to LG; damage him before he takes mega; if red is up, damage and fall back to it. juM8o: control the lower RL / tele
  area and "dont give up your position EVER" [R19]. Strenx is reported to prefer the terrace instead [R18 comments].
- **Out of control** [R18, R19]: GL first (most players "hold their opponent there", and you usually spawn there);
  through the teleporter to the rail (beware the barred window); grenades on his teleporter and terrace; grenades
  down the doorway under upper RL before showing yourself; then adapt (he goes to the rail bridge → you go red; he
  takes red → you take the rail or set up for mega; he pushes → back to GL and "the escape game"). Spam grenades 2 to
  3 s before mega, then teleporter to high ground and rail [R19, ischju].
- **Timing**: mega matters more than red here for some [R19, ischju]; others say red [R20]. Rush the yellow only right
  after taking red [R19].
- **Spawns**: staying on the RA side makes him spawn at GL [R19]. Don't kill him on the YA side if red is about to be
  his [R18 comment].
- **Red's ledge** has one way out, forward: easy to be trapped [R20]. The circle jump to red from the stairs is the
  known movement trick (the repository's `design/TRICK_JUMPS.md`; inertia's QW guide lists rocket jumps to red from
  several places [R15], QW layout).
- Opinions: "advanced strategy and aerowalk doesnt really belong in the same sentence" [R19, Nukm]; fast map [R43].

### Blood Run (ztn3tourney1)
- **Items**: red high in the central three-story room, mega in a hall, two yellows (one by the PG high, one low near
  the RL), rail at the base of the central room [table; QC's remake has a similar central vault with the heavy armor
  on a ledge, rail at its base and LG near the mega hall, R44 **[?] layouts differ**].
- **Control**: the 50 health bubble controls the whole map; push a yellow at the right time and hit rails [R14,
  hitsu]. Take mega and red and the RL yellow, leave the PG yellow as bait, camp the RL [R14, jamalz]. Safe: take
  everything and steal at least one yellow and the shards [R14, Deadlynoob]. Risky: leave red up, hide behind the
  pillar, LG him as he jumps to red [R14].
- **Out of control**: steal the RL and PG yellows; steal mega or red when he commits to the other; spam rockets into
  corners; do not rely on aim [R14]. If he spawns at the lower LG, forget mega and take the yellow and the plasma
  [R12, ollir]. Delay him at mega from the bottom of the mega room behind pillars with rails [R31].
- **Spawns**: the rail rush after dying at mega is the known spawn-kill trap [R14, R31]. Under the 2012 spawns,
  holding the mega niche forced rail or RL spawns; controlling the upper YA exits meant he could not leave unhurt
  [R34]. The teleporter-exit spawn was disliked [R34].
- **Timing** example quoted for this map: lower YA 27, red 35, mega 39, top YA 33 (s, as an answer to "item timings")
  [R12, Lup1n] **[?] meaning unclear: likely travel or first-spawn times, not respawns**. Take the RL yellow first if
  red is about 3 s away [R24, lizahd].

### Furious Heights (t7)
- **Rail is the comeback weapon** [R14, R23]: always mind it. Don't rush the rail after respawning (a common spawn
  kill); listen with grenades first [R14].
- **Timing**: delay red so it never clashes with mega [R14]; delay mega to hit him and avoid a clash at red [R29].
- **Control**: stand near the 50 health bubble or in the doorway between the two main rooms and listen: he goes for
  the shaft or the rail [R14, R23]. Don't attack red without knowing where he is unless far ahead in stack [R29].
- **Out of control**: get a yellow, learn the timers, spam red with grenades and rockets, rail him when he goes to
  mega, retake a yellow, harass mega [R14]. Wait on grenades, guess his route, go the other way to a free yellow
  [R29]. Out of control, delay him at mega from behind the pillars at the bottom of the mega room [R31].
- **Spawns**: standing at the top between LG and top RL forces his spawn into the corner by the GL door; near the
  red marker he can spawn in the lower door between the red and mega rooms (spam it) [R23]. Mega is reachable from
  both sides here, unlike Cure [R22].

### Lost World (dm13)
- **Weapons decide**: RL and LG each sit where the other weapon has the advantage; lopsided games are one player
  holding both [R39]. **No railgun** in the duel set (table).
- **In control** [R29, EVOL]: deny the yellows (take the upper one before dropping for red, holding the outside and
  high ground); keep him on the LG side and away from mega as it comes. "Play the items, not the opponent" [R29].
- **Out of control** [R29]: yellows and shards; take the RL when he drops for red, damage him as he takes the GL or
  leaves red; don't go for the RL unless you know where he is (LG kills you); trap him in the LG area (from outside
  or upper you watch both exits).
- **Openings** [R36]: the first route depends on the spawn: from the shotgun spawn go straight to mega; plasma, then
  RL, then LG from the plasma spawn (or LG first to see whether the RL is taken).
- Corridors and rings suit retreating, chasing and trapping; the center is where damage is taken at pickups [R39].
  Lava edges [R45].

### Campgrounds (q3dm6)
- An "aim map", small, many spawn frags; the only area worth controlling may be red [R12, R31]. Control, keep it,
  avoid rail exposure in red, deny the rail if you can, reach mega at least 5 s before it spawns [R12, InDepther].
- Don't let mega and red spawn together [R31]. 27 spawn points, 11 near the yellow (table).
- Practice suggestion: a bot game on Campgrounds with the goal of not giving a single frag [R31].
- The repository's own note: Campgrounds' rail was never taken in Bobby's training (PLAN, HISTORY).

### Hektik
- Small; the big items mostly central; **the controller can hold everything** by standing between the mega teleporter
  and the RL; lower ground is weak for the out-of-control player [R21, B4ZE]. "Easy map control (hold RG/RA)", "lots
  of spawnkills", rail-heavy, often one-sided [R43].
- Typical game: one player on red and mega with the LG, the other on the yellow; it turns on clean spawn frags [R22
  summary]. A 25-0 in a final; Rapha dominated it [R21].
- **Out of control**: know the timers, stack on the bottom-level green, yellow and shards (up to 150 armor in 25 s),
  damage him after he takes the big items, die only after taking his stack: "have patience" [R21, Ziel, hitsu].
  Dissent: few ways to deal damage, no room for traps, his position easy to track [R21].
- Spawns: effectively two outcomes, the yellow or a bad spawn at upper RL; too many spawns in the YA room [R21].

### Cure
- Control is easy to keep: weapons in open areas (LG especially) [R22]. Rail, LG and RL on the same side as mega and
  red; mega to red is fast [R22].
- **Mega is reachable only from the mid level**: from the red side there are three ways (low by tele, mid jump, high
  jump, with a +25 armor on a short detour), but the out-of-control player can reach armor and not mega, so he can
  "only do dmg on the item" [R22, atomigo].
- Out of control is "really difficult": reach the big items about 5 s early to damage without showing yourself; the
  rail is often a waste of time because it takes you out of position; 100+ armor on the weak side in about 30 s
  [R22]. Choke points and fall-back spaces exist [R22, zoot].

### Toxicity
- Fast [R43]; "force spawns easy and spawn rape very hard" while the out-of-control player still has room [R22
  summary]. Red is the more important item here, most frags happen at red [R31]. Out of control: a yellow, learn
  the timers, spam red with grenades and rockets, take the rail when he goes to mega [R31]. QL has its own item
  layout, unlike Q3's [R46]. 8 spawn points, the fewest with Aerowalk (table).

### Sinister
- yellack and akm's QL map; vertical fights in the red room expected; the rail's respawn has a map-wide gong; doors
  low enough to break movement [R37]. No written strategy found **[gap]**. Red is 535 units above mega, the biggest
  height gap of the ten (table).

### Battleforged (phantq3dm1)
- Little written. One player proposed removing its red to make games less decided by control [R43, jamalz];
  "unpopular for some reason" [R43]. The two big items are 1,581u apart (table): a neutral one-each cycle is natural.
  **[gap]**

### Held out: House of Decay and Dismemberment
- House of Decay = qztourney9 (Dreamcast's "Blue Monday", Team Arena's mptourney1); Dismemberment = hub3tourney1;
  Dismemberment called "a good map as far as testing control and your brain-game" [R47]. Dismemberment has 6 spawn
  points and an `info_player_start` that takes 23.8% of the pros' respawns there (repository measurement,
  `SPAWN_QL`). No strategy text found **[gap]**.

---

## Part 3. Skill progression: what separates the levels

**Beginner → intermediate** (what threads tell new duelers) [R11, R26, R27, R40, R45, R48]:
- Die less first: "just try to die the least times possible"; then win [R45].
- Learn movement, binds and the maps outside duel (FFA, CA, TDM) or on empty maps; learn item places and routes
  [R45, R37 comment].
- Learn the openings and time the two big items [R27, R36].
- Stop playing "the ABC game" badly: deal unreturned damage, time without being killed, don't overexpose, keep an
  escape [R26, puritan].
- Typical mistakes: grabbing the nearest big item and then fighting anyhow ("I'm stacked, so I can do anything")
  [R26]; predictable routes [R26]; rushing [R8, R26]; constant LG [R26]; aim-focused play with timing and decisions "a
  mess" [R49]; learning one skill and over-using it [R40]; playing only other beginners [R45].

**Intermediate → good** [R12, R14, R26, R27]:
- Timing becomes automatic, then turns into **plans**: what item is next, how he can contest it, where to be [R27].
- Fights get a purpose: "what do I want to achieve with this fight" [R27]. Fights are made easy or skipped: good
  players set up easy finishes and favorable odds [R26, magadog]; they "force unfair fights" such as item traps and
  avoid pointless aim duels [R10, palatka].
- Taking less damage in return (the Cypher example) [R26].
- Using the enemy's state: assume he has healed, deduce his stack from pickups [R27].
- Fighting outstacked differently: position to damage at his pickups, leave [R26].

**Good → pro** [R10, R25]:
- Timing up to five items, to the second, by memorized "languages" [R25].
- Reading and manipulating spawns [R33, R34].
- Being unpredictable and exploiting predictability: prediction and counter-prediction [R5, R15].
- Control of the whole map with aim to back it: "hold down a map so tight it's unreal to see" [R50 summary].
- Players type pros: Rapha "the smartest player", Cypher the "combat-skills master" [R10].

**What coaches tell players to work on first.** The consistent answer: survival and timing before aim; review your
own demos for mistakes and pros' for inspiration [R3, R4]; play opponents slightly better than you [R45]; one map,
several games in a row [R29].

---

## Part 4. Strategy versus mechanics

No guide measures it; these are judgments of experienced players and analysts.

- **Decisions first, aim as a lever.** Chance: good decisions make aim easier; enemy status and item timing are the
  core of the game and aim supports them [R4]. QC wiki: aim is "only part of the battle"; you "will be crushed by
  anyone who is more experienced"; aim-dependent players win or lose by large margins [R8]. palatka: in QL duel aim
  is "very rarely a deciding factor"; good positioning inflates accuracy [R10]. "Good aim won't save you from being
  consistently outstacked" [R12, Retribution]. Order of needs: position, weapon, then aim [R3].
- **Aim as a floor and a decider between equals.** Heartlesss: "ql duel is pretty balanced", aim can offset weaker
  decisions; Tox's aim lets him beat Rapha [R10]. Weaker aim makes everything hard; positional play beats better aim
  but you must improve aim to go further [R50]. One 2014 adviser: "Better players have better aim" [R26].
- **QL and Q3 are "brain limited"** (p4r4), unlike QC with smaller stacks where "two rails in a row" undo control and
  aim matters more [R51]. A rail of 100 is "almost a mega or a red" in QL [R51, nex1].
- A real test case: a CS-trained friend out-aimed a player with the better stack; the advice (dodge, position, time,
  rockets over shotgun, trap, listen, don't fight outstacked) turned it into a 3:0 win on Blood Run [R12].
- **The repository's own measurement points the same way** (`design/LG_REAL_VS_SIM.md`, HISTORY 2026-11-13): Bobby's
  LG hit rate is close in real and simulated play, but people hit him far better than he hits them. The gap is not
  his hand; it is what his opponents do (dodging, positioning). That is the guides' claim made concrete.

**My synthesis.** At equal aim, decisions decide (stack, timing, position, spawns). At unequal aim the better aimer
wins the even fights, so the weaker aimer must make fights uneven (traps, damage at pickups, splash, quiet routes)
and avoid even ones. Both ends need the strategic layer; mechanics set how much a correct decision is worth.

---

## Principles distilled

1. **Stack is the currency.** A fight is won mostly before it starts, by effective stack (`min(3H, H + A)`),
   position and weapon, in that order; aim decides what is left.
2. **Control is owning the next big spawns**, not the last pickup: being where mega and red will appear, earlier and
   safer than him, with his routes covered.
3. **Timing is the map's clock made into plans**: which big item is next, how long until it, who is closer, how he can
   attack it. Red +25 s, mega +35 s from the pickup.
4. **Keep the big items apart in time**: take red within 5 s or more than 15 s after mega, never about 10 s; arrive
   ahead; the 5-second rule for what fits before the next spawn.
5. **Every pickup is a known time and place**, so it is the out-of-control player's best chance to deal damage; an item
   taken under fire is worth less.
6. **Out of control: don't die, restock on the weak side, damage at his pickups and leave, steal when he commits,
   trap and double back, avoid the obvious rush.** The score is easier to recover from 3-0 than 10-0.
7. **In control: desync, steal his small items, hold the position between him and the items, stay unpredictable,
   don't chase away from the timing.**
8. **Give up an item when its price is above its worth**; trade one big item for the other; use items as bait.
9. **The spawn is chosen from the far half of the spawn points from the enemy** (QL duel; measured here at 86.9%): where
   you stand chooses his spawn half. The fresh spawn is weak and predictable; the first seconds after a frag decide
   whether control continues.
10. **Information is the hidden stack**: sound (walk, avoid noisy pickups when hiding), seen pickups, item absence, the
    spawn rule and his needs (low health → health; no weapon → nearest weapon) give his position and state.
11. **Prediction and counter-prediction**: predict him, be unpredictable yourself (routes, delays, double-backs).
12. **Height, exits and angles**: a position is good for a weapon and only with a way out.
13. **Spam is damage**: projectiles at doorways, teleporter exits, items and his predicted path; they also spoil his aim.
14. **The score and clock change the price of risk**: ahead, choose the fights; behind, still don't throw frags.
15. **Avoid damage as much as you deal it**; the player who takes less damage usually wins.

---

## Part 5. Implications for Bobby

Framed for a self-play RL agent with a brain (belief), a head (orders every 0.2 s: go, contest, hold, spam, push, cut
off, break off, with a place, point and weapon), hands (execution), a win-chance judge and the 2.0 aim of paying stack
and control, not damage (PLAN, `runs/2.1/DESIGN.md`, `design/PLAN_2.md`). Rule 12 holds throughout: the guides and
the pros give **facts of the game and human limits**, and **readouts**; never a target for his choices.

### 5.1 What the strategy layer must perceive (brain and head inputs)

| Need | What the guides say | Where Bobby stands (from the docs) | Gap |
|---|---|---|---|
| Item timers as **he** knows them | the core skill; from own pickups, seen and heard pickups, item absence, a delayed respawn to watch the item | the head was given the item timers in list 18 (PLAN) | check they are **belief** timers (seen/heard/inferred), not truth, and include the yellows; "who takes the next mega, the next red" exists, the yellows are new (STRATEGY_2) |
| **Time to next spawn vs travel time** | the 5-second rule; "15 s or more: act; 7 s or less: secure" | not named | an input per big item: seconds to spawn minus his path time, and the same for the enemy at his believed place |
| Order of the next spawns, and their sync | the delay rule (10 s apart = sync), double red | not named | a readout of the next two big spawns and the gap between them |
| **Enemy stack estimate** | assume he healed; deduce from pickups seen | the brain predicts his stack | it should move with item **disappearances** and elapsed time, not only damage; effective stack `min(3H, H+A)` for both |
| His weapons | fresh spawn = MG; who holds LG/RL/rail | the brain predicts his weapon | his weapon set, not only weapon in hand; "seconds since his respawn" exists |
| **His spawn set** | far half from me (QL rule, measured) | `SPAWN_QL`, `RESPAWN_QL` built; `SPAWN_TRUTH` adds the truth (switch) | the head should see **where he can spawn given where I stand**, so "force a spawn" is a reachable plan |
| Sound | walking, pickups, jumps, weapon switches; Sinister's rail gong | `HEAR_QL`, heard item returns (`note_respawn`) | his own noise: does he know what his pickups and jumps tell the enemy? an input of "how loud have I been" |
| Score, clock | ahead/behind changes risk | the judge reads score and time | none |
| The place's worth by weapon | position, then weapon, then aim; angles are map-specific | the map sense (2.1 design) | as designed |

### 5.2 What it must decide (the order's verbs, matched to the guides' plays)

| Guide play | Order in 2.1's vocabulary | Comment |
|---|---|---|
| Contest at a timing; arrive ahead | go / contest (item, way) | the arrival time is the decision, not only the item |
| Steal when he commits to the other | go (item) chosen against his believed target | needs the enemy's next target as a brain readout |
| Delay or desync a pickup | hold near the item, take it later | not an explicit verb; "hold" with an item in reach covers it if the hands can wait |
| Give up an item | go elsewhere / hold | the appraisals must price the item **against** the risk at it |
| Damage at his pickup, then leave | spam / hold an angle on the item at its time, then break off | the out-of-control core; needs "his pickup time" from the timers |
| Ambush, trap, double back | hold (place, watched point); go by a chosen way | double-back = a deliberate route change after a sound |
| Force his spawn | hold a place chosen for the spawn half it leaves him | only possible if the head sees the spawn set |
| Spawn pressure vs let him run | push/cut off vs go (items) | the first seconds after a frag: a choice worth its own appraisal |
| Escape and reset | break off, go to the weak side's items | "don't die again" |
| Hold the control position (Aerowalk lower RL) | hold (place) | the 2.0b postmortem: a place has no price until someone punishes it |

### 5.3 What it should be paid for, and the self-play equilibrium

- **The guides agree control is instrumental**: "the goal is frags, not pickups" [R11]; a controller who plays the map
  instead of the player loses [R12]. So paying control outright risks the pathology PLAN_2 names (camping the spawn,
  ignoring the fight; B-280). The guides support 2.0's route: price stack and control **through winning** (the
  judge), not as their own pay.
- **The judge should know what the guides think wins**: effective stack both sides, who owns the next big spawns (the
  "in control" readout), the weapons each holds, the score and time. A frag's worth depends on what it does to the next
  spawns (he respawns far and weak). A damage trade's worth depends on the item it wins or loses (Weird's "a small LG
  hit on a healthy opponent heading to red is a poor trade" [R27]): damage that makes him pick up red at 50/50 is worth
  more than damage he heals before the next spawn.
- **Death priced above the frag** (the 2.0a proposal) fits "don't die again" and "avoid damage as much as dealing it".
- **In self-play, strategic moves only pay if the opponent punishes their absence.** Prediction and
  counter-prediction [R5, R15] need opponents that predict. A league of copies that never traps, never times and
  never steals makes timing and position worthless (the 2.0b lesson: "a place has no price in a game where nobody
  holds an angle"). The guides' strategic layer emerges against an opponent that uses it. The holder seat and the
  exploiters (parked, per AlphaStar) are the tools; the same logic gives: a **timer** seat (one that arrives at every
  big spawn on time) and a **thief** seat (one that steals when he commits) would make his timing pay. These would be
  league opponents with a habit (like the weapon leaners), not lessons he copies (rule 13).

### 5.4 The LG-only habit, read through the guides

- The guides call one-weapon play a known amateur mistake [R14, R26, R40]; that is human coaching, a readout at most.
  It must not become a weapon target (rule 12, 1.7c's failure).
- The guides' **mechanism** is what matters: weapons are picked by **position and range, then stack**; projectiles
  spoil the opponent's aim and deal damage at chokepoints and items without exposure; rail is a position weapon that
  needs an exit. In self-play the LG pays because his copies are as easy to track as he is (LG_REAL_VS_SIM) and because
  nobody punishes a tracking duel in the open. Projectiles pay where there are chokepoints and predictable arrivals:
  **item timings are the predictable arrivals**. If the timers make his enemy's arrival predictable, spam at the item
  pays by itself; if they don't, the LG stays the only weapon that pays. The weapon may follow from the strategy layer
  rather than need a fix of its own.

### 5.5 Facts the pros' demos may supply (rule 12: measured facts and readouts only)

Allowed as facts of the game or human limits: the spawn rule (done); travel times between items by the ways; how long
an item stays up when nobody contests it is **not** a fact (it is a choice outcome). Readouts only, beside his, never
targets: how early pros arrive at a spawn (the "5 s early" advice), how often the big items go to one player per cycle
(the control share), how often pros take an item under fire, weapon by range. A proposal never says "bring him to the
pros' X".

### 5.6 Things in the guides the project may not have yet (for the owner to weigh)

1. **Belief timers for the yellows and the order of the next spawns**, with the "time to spawn minus travel" number for
   him and for the believed enemy.
2. **The spawn set as an input** to the head (where he can respawn given where I stand), so spawn forcing and spawn
   reading are learnable.
3. **His own noise** as an input (sound discipline).
4. **League seats with a strategic habit** (timer, thief, trapper, holder) so that strategy is punished when absent.
5. **The judge's view of an item taken under damage** (the voided red) and of the next spawns' ownership.
6. **The first seconds after a frag** as a distinct moment for the frozen-moment lesson (spawn pressure or items).

---

## References

All fetched 2026-11-13 unless marked. ESR = esreality.com Quake Live forum unless stated.

| # | Source | URL |
|---|---|---|
| R1 | Pat Flannigan, "How to Master Quake Spawn Timers", Dignitas, 18 Sep 2017 (Quake Champions) | https://dignitas.gg/articles/blogs/Quake/11424/how-to-master-quake-spawn-timers-controlling-mega-and-armor |
| R3 | Memento_Mori, "Duel - Damage Output Guide", ESR, 13 Aug 2011, with comments | https://www.esreality.com/post/2133254/duel-damage-output-guide |
| R4 | Chance Lacina (Team EG), "Quake Bible" (2009), mirror; ESR news post | https://people.freebsd.org/~danfe/eg-chances-quake-bible.html ; https://esreality.com/post/1747280/team-eg-s-chance-releases-quake-bible |
| R5 | QuakeWorld wiki, "Strategy" (QuakeWorld) | https://www.quakeworld.nu/wiki/Strategy |
| R6 | Memento_Mori, "Basic Timing Guide", ESR, 17 Feb 2011 (pages 1 and 2) | https://www.esreality.com/?a=post&id=2028953 ; https://www.esreality.com/?a=longpost&id=2028953&page=1 ; https://www.esreality.com/?a=longpost&id=2028953&page=2 |
| R8 | Quake Champions wiki, "Time Limit Duel" (Item control, Reclaiming and Maintaining control) | https://quakechampions.fandom.com/wiki/Time_Limit_Duel |
| R10 | ESR, "Which (duel) pro had the best aim in QL?", Oct 2016 | https://www.esreality.com/post/2843268/which-duel-pro-had-the-best-aim-in-ql/ |
| R11 | Memento_Mori, "A Duel Guide for CA Players", ESR, 2 Jan 2014 (intro and comments only) | https://esreality.com/post/2538217/a-duel-guide-for-ca-players/ |
| R12 | ESR, "Strategy against aimbased playstyle", Aug-Sep 2016 | https://www.esreality.com/post/2837720/strategy-against-aimbased-playstyle/ |
| R13 | search summaries naming ShockeD's "Timing Tutorial" and "Quake Live Lesson #2" (videos, not read) | https://irc.pcper.com/quake-live-tutorial-the-very-basics-of-dueling-and-item-control.html (unreachable) |
| R14 | ESR, "Looking for duel advices [NO TROLL]", 3-6 Jan 2013 | https://esreality.com/post/2367975/re-looking-for-duel-advices-no-troll/ |
| R15 | inertia, "Advanced Aerowalk Strategy", quakeworld.nu forum, 2005 (QuakeWorld) | https://quakeworld.nu/forum/topic/2131 |
| R16 | QuakeWorld wiki, Ztndm3 (QW Blood Run) | https://www.quakeworld.nu/wiki/Ztndm3 |
| R17 | search summary of QL Blood Run control (neutral cycle) | via search; see R16 |
| R18 | garz, "Aerowalk guide for noobs", ESR, 7 Nov 2018 | https://www.esreality.com/post/2928073/re-aerowalk-guide-for-noobs/ |
| R19 | ESR, "Aerowalk tips", 22-24 Jun 2011 | https://esreality.com/post/2099637/aerowalk-tips |
| R20 | search summary of ESR Aerowalk threads (red's ledge, red vs mega timing) | https://www.esreality.com/index.php?a=post&id=1966308 (via search) |
| R21 | ESR, "So Hektik", Nov-Dec 2012 | https://esreality.com/post/2349876/re-so-hektik/ |
| R22 | ESR, "Cure", May 2013 | https://esreality.com/post/2420278/re-cure/ |
| R23 | Memento_Mori et al., "Spawn-System: Furiousheights", ESR, 4-5 Feb 2012; also search summary of FH threads | https://www.esreality.com/post/2218235/spawn-system-furiousheights/ |
| R24 | ESR, "[duel] How do you time?", Feb 2010 | https://www.esreality.com/post/1828703/re-duel-how-do-you-time/ |
| R25 | Oaki_Duke, "Timing to the second: A Method", ESR, Apr 2012 - Jul 2014 | https://www.esreality.com/post/2249289/timing-to-the-second-a-method/ |
| R26 | ESR, "Duel problems", Oct 2014 | https://www.esreality.com/?a=post&id=2668708 |
| R27 | ESR, "need some duel tips", Oct 2014 | https://www.esreality.com/post/2673628/re-need-some-duel-tips/ |
| R28 | Xonotic forums, "Who can offer 1vs1 advice?", Feb 2016 (Xonotic; transfers) | https://forums.xonotic.org/printthread.php?tid=6012 |
| R29 | ESR, "How do I play dm13 ztn and t7?", Oct 2012 | https://esreality.com/post/2326071/how-do-i-play-dm13-ztn-and-t7/ |
| R30 | ioquake3 source, `code/game/g_items.c` (RESPAWN_*), `code/game/g_client.c` (SelectRandomFurthestSpawnPoint) | https://raw.githubusercontent.com/ioquake/ioq3/main/code/game/g_items.c ; https://raw.githubusercontent.com/ioquake/ioq3/main/code/game/g_client.c |
| R31 | search summaries of ESR Campgrounds / Toxicity / Blood Run advice threads | https://esreality.com/post/2838132 ; https://www.esreality.com/post/2375352/re-regarding-dm6-ztn-in-the-duel-mapp/ (via search) |
| R32 | Magic Game World, "Quake Champions tips and tricks" (via search summary) | https://www.magicgameworld.com/quake-champions-tips-and-tricks/ |
| R33 | Memento_Mori et al., "Spawn-System: Bloodrun", ESR, Oct 2011 (quotes the 31 May 2011 QL update) | https://www.esreality.com/post/2161834/spawn-system-bloodrun/ |
| R34 | Teen Queen et al., "Bloodrun spawns opinion", ESR, May 2012 (SyncError's replies) | https://www.esreality.com/post/2257199/bloodrun-spawns-opinion |
| R35 | holysh1t.net on the 2014 rulesets (via search summary) | https://holysh1t.net/?p=5755 |
| R36 | baksteen, "Lost World duel lesson #1: Starting Spawns", ESR, 9 Nov 2015 (video; comments) | https://www.esreality.com/post/2783590/re-lost-world-duel-lesson-1-starting-sp/ |
| R37 | ESR, "QL Duel Map Sinister by yellack and akm" (via search summary) | https://esreality.com/post/2254509/ql-duel-map-sinister/ |
| R38 | ESR "Duel Basics Page" comments (plasma as trap weapon) | https://www.esreality.com/post/2216860/duel-basics-page/ |
| R39 | Memento_Mori comment in "quakelive duel maps and their stuff", ESR, Dec 2014 | https://esreality.com/post/2691214/quakelive-duel-maps-and-their-stuff/ |
| R40 | ESR "Duel Basics Page" comments (tnz on over-using one skill) | https://www.esreality.com/post/2216860/duel-basics-page/ |
| R41 | Xonotic thread (Beagle: music off) | see R28 |
| R42 | Theros, "The Tactics and Psychology of Quake 2" (Quake 2; dondeq2 repost 2017) | https://dondeq2.com/2017/05/27/the-tactics-and-psychology-of-quake-2-by-theros/ |
| R43 | ESR, "duel maps", May 2012 | https://esreality.com/post/2259933/duel-maps/ |
| R44 | Quake wiki, "Blood Run (QC map)" | https://quake.fandom.com/wiki/Blood_Run_(QC_map) |
| R45 | ESR, "New to Duel. This isn't fun at all", Dec 2013 - Jan 2014 | https://esreality.com/post/2533721/new-to-duel-this-isn-t-fun-at-all |
| R46 | QuakeWorld wiki, Toxicity (via search summary) | https://quakeworld.nu/wiki/Toxicity |
| R47 | ESR threads on House of Decay and Dismemberment (via search summary) | https://esreality.com/post/2148297/re-dismemberment/ |
| R48 | ESR, "HOW TO IMPROVE AT DUEL", Aug-Sep 2015 | https://www.esreality.com/post/2765112/how-to-improve-at-duel-tips-and-tricks/ |
| R49 | as R48 (bolus major) | see R48 |
| R50 | search summary of ESR aim-vs-decision threads | https://esreality.com/post/2336991/new-duel-idea/ (via search) |
| R51 | ESR (QC forum), "2GD opinions on Duel and Sacrifice modes", Jun 2017 | https://www.esreality.com/post/2875426/re-2gd-opinions-on-duel-and-sacrifice-m/ |

Repository sources: `sim/duel_env.py` (item respawns, `RESPAWN_QL`, `SPAWN_QL` and the 14,937-respawn spawn fit),
`plugins/duel_items.json`, `data/maps/*.bsp` (spawn points), `docs/PLAN.md`, `docs/HISTORY.md`,
`docs/runs/2.1/DESIGN.md`, `docs/design/STRATEGY_2.md`, `docs/design/PLAN_2.md`, `docs/design/LG_REAL_VS_SIM.md`.

Not reachable: Liquipedia Arena FPS map pages (human check), the Wayback Machine, Patreon (Robin Mendoza, "Loop
wrangling in Duel"), Steam guides (rate limit), YouTube transcripts.
