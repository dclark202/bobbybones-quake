# Quake Live duel mechanics: a reference, checked against the simulator (2026-11-13)

What this is: a research pass on how Quake Live (QL) actually works, for the parts that matter to a 1v1 duel bot,
with numbers and a source for each. At the end, every value is set beside `sim/duel_env.py` (and `sim/q3`,
`sim/qsim.py`, `plugins/duel_items.json`), and a last section says what the facts mean for Bobby.

Nothing in the repo was changed except this file. No server, no training.

## How to read the sources

Quake Live's game code is closed. Its numbers come from four kinds of source, in order of trust:

1. **Our own measurements on a real QL server** (weaponlab, rjlab, physlab, itemlab, maplab; written up in
   [`docs/archive/versions/v0.4/FIDELITY_AUDIT.md`](../archive/versions/v0.4/FIDELITY_AUDIT.md) and
   [`REPORT_PLAYTEST_2026-10-19.md`](../archive/versions/v0.3.7/REPORT_PLAYTEST_2026-10-19.md)). Tagged **[ours]**.
2. **QL's server cvars.** QL exposes almost every weapon and rule constant as a server cvar. The best public copy of the
   defaults is a full `cvarlist` dump of a QL dedicated server, [pastebin zJ6XqCNq][cvarlist] (undated community paste;
   every value in it that I could cross-check agrees with the other sources). The **duel factory** (the preset our servers
   run) overrides only a few of them: [the default factories, formatted][factories]. Tagged **[cvar]**.
3. **The Quake 3 source** (ioquake3, GPL), which QL is built on: [`g_items.c`][g_items], [`g_combat.c`][g_combat],
   [`g_active.c`][g_active], [`snd_dma.c`][snd_dma], and our vendored `sim/q3/bg_pmove.c`. Where QL has no cvar and no
   known change, QL very likely keeps the Q3 behaviour, but that is an inference. Tagged **[q3src]**.
4. **Community pages**: ESReality, the Quake fandom wiki, Steam guides, Liquipedia-style guides. Good for history and
   strategy; the numbers are sometimes out of date (QL changed the lightning gun twice, for example). Tagged **[comm]**.

The Quake fandom wiki refused direct fetches (HTTP 402), so its facts here come from search-result extracts of its pages.
They are marked as such and are less sure.

Certainty marks used below: **sure** (cvar plus our measurement, or two independent sources), **likely** (one good source
or the Q3 source with no sign QL changed it), **unsure** (conflicting or single community source).

Watch out for Quake Champions (QC) pages: QC is a different game with different numbers (rocket damage, health, armor,
hitboxes). Nothing from QC is used here.

---

## 1. Weapons

### 1.1 The weapon table (QL defaults, the duel factory changes none of these)

All from the cvar dump [cvarlist] unless noted; the same values appear in the server-standards table [standards] (which
still shows the pre-2015 lightning gun, 7 damage and knockback 1.50). Fire interval = `weapon_reload_*` in ms.

| Weapon | Kind | Damage | Splash dmg / radius | Fire interval | Full-rate DPS | Projectile speed | Knockback factor (`g_knockback_*`) | Range |
|---|---|---|---|---|---|---|---|---|
| Gauntlet (G) | melee | 50 | - | 400 ms | 125 | - | 1 | melee (Q3: 32 units from the muzzle) |
| Machine gun (MG) | hitscan, spread 200 | 5 (4 in TDM: `g_damage_mg_tdm`) | - | 100 ms | 50 | - | 1 | 8192 |
| Heavy machine gun (HMG) | hitscan, spread 400 | 8 | - | 75 ms | 106.7 | - | 1 | 8192 |
| Shotgun (SG) | 20 pellets, fixed 3-ring pattern | 5 a pellet (100 all in) | - | 1000 ms | 100 | - | 1 | 1500 cap ([comm] fandom extract) |
| Grenade launcher (GL) | projectile, gravity, bounces | 100 | 100 / 150 | 800 ms | 125 | 700 | 1.10 | fuse 2.5 s ([q3src]) |
| Rocket launcher (RL) | projectile, straight | 100 | 84 / 120 | 800 ms | 125 | 1000 | 0.90 on others, 1.10 on self | - |
| Lightning gun (LG) | hitscan beam, ticks | 6 a tick | - | 50 ms | 120 | - | 1.75 | 768 |
| Railgun (RG) | hitscan | 80 | - | 1500 ms | 53.3 | - | 0.85 | 8192 |
| Plasma gun (PG) | projectile, straight | 20 | 15 / 20 | 100 ms | 200 | 2000 | 1.10 on others, 1.30 on self | - |

Not in duel on our ten maps: chaingun (8 dmg, 50 ms), nailgun (10 nails x 12, 1000 ms), proximity launcher, BFG
(all have cvars in the dump; the 2014 update removed prox from all maps and the chaingun and nailgun from several:
[holysh1t 2014 update][ql2014]).

Other weapon cvars in the dump whose exact effect is not documented anywhere I found: `g_knockback_z 24` and
`g_knockback_z_self 24` (very likely an upward kick added to knockback, which is why hits lift a player a little),
`g_splashdamageOffset 0.05`, `g_rocketsplashOffset -10` [standards], `g_accelFactor_rl 1` / `g_accelRate_rl 16` (an
optional accelerating rocket, off at factor 1), `g_damage_lg_falloff 0`, `g_damage_sg_falloff 0`. **unsure** what the
offsets do.

**QL against Q3 (vanilla, "VQ3")**, from [esr-balance] and the fandom extracts [fandom-ql]:

| Weapon | Q3 | QL | Notes |
|---|---|---|---|
| MG | 7 (5 in TDM) | 5 (4 in TDM) | QL's MG is a weak starter, 50 DPS |
| SG | 11 pellets x 10, spread 700 | 20 x 5, spread 1000, fixed pattern | wider, more forgiving close, weaker far |
| RL | 100 direct, 100 splash, 900 u/s | 100 direct, **84 splash**, **1000 u/s** | faster rockets, weaker splash |
| LG | 8 per tick (160 DPS) | **6 per tick (120 DPS)**, knockback 1.75 | pre-Steam QL was 7 (140 DPS); the 6 came with the Steam release ([esr-balance], [esr-callvote]) |
| RG | 100 | **80** | two rails no longer kill a 100/100 player |
| PG | 20, 15 splash | same | unchanged |
| GL | 100, 100 splash | same | grenades can no longer be set off by rocket blasts ([fandom-ql]) |
| HMG | - | new (2014) | 8 dmg, 75 ms, spread 400 |

### 1.2 Hitscan, projectiles, splash

- **Hitscan** (MG, HMG, SG, LG, RG): the hit is decided at the server frame the shot is fired, with **server-side lag
  compensation** for people ("unlagged": the server rewinds the target to where the shooter saw him). Only hitscan is
  compensated; projectiles are not ([esr-unlagged], users' reports, 2009, **likely**). So rockets and plasma must be led
  by the shooter's own ping too.
- **Splash** ([q3src] `G_RadiusDamage`): damage = splash x (1 - d / radius), where d is the distance from the blast to the
  **nearest point of the target's box**, not its centre. A target is hit only if a trace from the blast reaches the box's
  centre or one of eight points 15 units off it (`CanDamage`), so **splash does not go through walls or floors**, but it
  does reach round a corner by up to about 15 units. QL keeps this (`thrufloors off` is the default in the callvote
  plugin's list [esr-callvote]; **likely**).
- **Direct hit**: a projectile touching a player does its full damage to him and no splash to him (Q3 `G_MissileImpact`
  skips the direct target in the radius damage); other players near still take splash.
- **Own damage**: own splash is halved (`damage *= 0.5` when target = attacker, [g_combat]); the knockback is computed
  from the **full** damage before halving, so a rocket jump pushes as hard as a rocket at an enemy's feet would, at half
  the cost. [ours] confirms the halving for rockets, plasma, grenades.
- **Knockback** ([g_combat]): velocity added = direction x `g_knockback` (1000) x knockback / 200, i.e. **5 u/s per
  point of knockback**, with knockback = damage x the weapon's factor, capped at 200 points (1,000 u/s). While knocked
  back the player gets 50 to 200 ms of no ground friction (`pm_time = 2 x knockback`, clamped).
  Examples: a direct rocket on an enemy, 100 x 0.9 x 5 = 450 u/s; a rail 80 x 0.85 x 5 = 340 u/s [ours: 340];
  an LG tick 6 x 1.75 = 10.5, cut to 10 points = 50 u/s (measured 2026-11-13; 20 ticks a second: an LG stream pushes a target
  hard in the air).

### 1.3 Weapon by weapon

**Gauntlet.** 50 per hit every 400 ms, melee reach. [ours]: hits at 40 units, not at 70. Mostly used by players spawned
with only MG and gauntlet, or to finish.

**Machine gun.** Starting weapon, 100 rounds at spawn (`g_startingAmmo_mg 100` [cvarlist]). 5 per bullet, 10 a second,
spread "200" (Q3 meaning: the bullet leaves inside a cone whose radius is 200 units at 8,192 units, about 1.4 degrees).
Fandom calls it very accurate [fandom-mg]. 50 DPS at best: a 125-health spawn needs 25 bullets (2.5 s of perfect aim).

**Heavy machine gun.** Added in the 2014 update [ql2014]. 8 per bullet every 75 ms, spread 400 (about 2.8 degrees),
max ammo 150 [fandom-hmg]. Present on some maps only.

**Shotgun.** 20 pellets x 5 damage, 1 s refire. QL fires a **fixed pattern**, not a random one: an outer ring of 10
pellets and a middle and an inner ring of 5 each, with **no pellet in the centre**; spread radius 1000 (about 7 degrees
for the outer ring) against Q3's random 700; range limited to 1500 units ([fandom-sg] extract; [esr-sg] on
`cg_trueShotgun`: 1 shows the true fixed pattern, 2 a jittered picture of it). `g_damage_sg_outer 5` [cvarlist] is the
outer ring's damage (same as inner by default). **likely** (two community sources agree).
Consequence: point blank everything hits (100); at mid range only the inner rings land; a target dead centre at long
range can be missed entirely.

**Grenade launcher.** 100 direct, 100 splash within 150, 700 u/s launch, gravity 800, bounces (Q3 keeps 65% of speed at
a bounce), explodes after 2.5 s or on touching a player. 800 ms refire. Uses: spam into a doorway or onto an item,
blocking, grenade jumps.

**Rocket launcher.** 100 direct, 84 splash within 120, 1000 u/s, 800 ms refire, knockback 0.9 (others) / 1.1 (self).
The workhorse of duel: splash means a rocket at the feet of a grounded player hurts even when it misses the body.
At 1000 u/s a rocket needs 0.3 s to cross 300 units and 0.6 s for 600; a target running at 320 u/s moves 96 to 192 units
in that time, more than the 120 splash radius at long range, so far rockets are prediction or spam (see section 5).

**Lightning gun.** A hitscan "beam" that does 6 damage every 50 ms (120 DPS) out to 768 units, nothing beyond.
[ours]: hits at 700, misses at 800. The beam is drawn client-side; the damage is ticks of hitscan along the crosshair, so
LG damage is exactly (fraction of ticks on target) x 120. Knockback 1.75 per point: a target in the air is pushed about
50 u/s a tick. Ammo is burned at 20 cells a second, so a 100-cell pickup is 5 s of beam. History: 8 (Q3) -> 7 (QL web)
-> 6 (QL Steam, 2015) [esr-balance]; knockback 1.50 -> 1.75 with the last change [esr-callvote].

**Railgun.** 80 damage, instant, unlimited range, 1.5 s between shots. Zoom is client-side (`cg_zoomfov`): it changes the
view and mouse scale, not the weapon. The rail's hum (a loop sound while it is held) and its trail tell the enemy where
the shooter is. QL lowered it from 100 to 80 [fandom-rg]: two rails (160) kill a 125 spawn or a 150 stack but not
100/100 (200).

**Plasma gun.** 20 per bolt, 10 a second (200 DPS: the highest), 2000 u/s, 15 splash within 20 units, self knockback
1.3. Short splash means it must hit the body or the floor right under the feet. Plasma climbing (firing at a wall while
jumping) works because of the self push; [ours] measured own-feet plasma at 8 damage and 95 u/s of push.

### 1.4 Weapon switching and refire

- **Switch time**: drop 200 ms + raise 200 ms in QL (`pmove_WeaponDropTime 200`, `pmove_WeaponRaiseTime 200` [cvarlist];
  Q3 is 200 + 250). Some community configs show 10 ms: those are the PQL/Turbo and race factories [cvar-race], not
  duel. [ours]: 17 server frames (425 ms) from the switch command to the first shot.
- **You cannot switch while the weapon is still reloading** ([q3src] `PM_Weapon`: a change starts only when
  `weaponTime <= 0` or the weapon is not firing). So after a rail shot, the earliest next shot from another weapon is
  1.5 + 0.4 = 1.9 s later. After a rocket, 0.8 + 0.4 = 1.2 s.
- **Out of ammo**: a dry click costs 500 ms ([q3src]), then the client's auto-switch (`cg_switchOnEmpty`) picks another
  weapon.
- The first shot of any weapon fires as soon as the trigger is pressed if the weapon is ready (no wind-up).

### 1.5 Ammo

| Weapon | Weapon pickup gives | Ammo box gives | Max carried | Sources |
|---|---|---|---|---|
| MG | (always held) 100 at spawn | 50 | unsure: 150 in our sim; Q3 200 | [ours] itemlab, [cvarlist] |
| SG | 10 | 5 | 25 ([fandom-sg]: 25 in duel/FFA, 50 in CA) | [ours] |
| GL | 10 | 5 | **conflict**: 25 in our sim; fandom 50 | [ours], [fandom-gl] |
| RL | 10 | 5 | **conflict**: 25 in our sim; fandom 50 | [ours], [fandom-rl] |
| LG | 100 | 50 | 150 | [ours], [fandom-lg] |
| RG | 10 | 5 | 25 | [ours], [fandom-rg] |
| PG | 50 | 50 | 150 | [ours], [fandom-pg] |
| HMG | 50 | 50 | 150 | [ours], [fandom-hmg] |

- QL's own `g_startingAmmo_*` defaults (rl 5, rg 5, lg 100, pg 50, sg 10, gl 10, hmg 50 [cvarlist]) are what a weapon
  gives in modes that start with it; the CA/AD/RR factories start with sg 50, mg 100, lg 150, hmg 150, rl 50, pg 100,
  rg 25, gl 25 [factories] (which suggests the caps are at least that, at least in those modes: **unsure**).
- **Picking up a weapon you already hold** ([q3src] `Pickup_Weapon`): you are topped up to the pickup amount if you have
  less than it; if you have as much or more you get **one** round. (Dropped weapons give their own count.) QL has no
  cvar for it; **likely** the same. Our sim instead adds a full pickup up to the cap (see section 7).
- Ammo boxes respawn after 40 s in duel (`g_ammoRespawn 40` [cvarlist]; the CTF-type factories set 10 [factories]; the
  2014 "Default" ruleset's 10 s [ql2014] does not apply to the classic duel preset).
- No universal ammo packs in duel (`g_ammoPack` is a team-mode feature [ql2014]; [ours] itemlab found none on duel maps).

### 1.6 Accuracy: what good players hit (a readout, not a target)

Per project rule 12 these are facts about people, to read beside Bobby's numbers, never to aim him at.

| Weapon | Pros in duels (our measure of the pro demos) | Community self-reports |
|---|---|---|
| LG | 31 to 32% of cells (`docs/archive/versions/v0.5.1/AIM_LIMITS.md`; `docs/runs/2.1/DESIGN.md`: 32% over 1,255 games) | 30 to 40% in duel, more in FFA ([esr-lg]) |
| RG | 42 to 45% of shots (same sources) | 40 to 60% ([esr-lg] thread); the owner's yardstick for people 50 to 60% |
| RL | about 28% "hit share" in our older measure (`RUN_v0.3.8.md`); rocket splash makes "accuracy" ill-defined | none found |

Duel accuracies are lower than FFA because the opponent is dodging one known enemy. Our own pro measures also give
first-hit times after an enemy appears: about 0.32, 0.44, 0.55, 0.76 s when he appears 0-5, 5-10, 10-20, 20-40 degrees
off the crosshair (`MANIFEST_v0.2.md`).

---

## 2. The damage model: health, armor, stacks

### 2.1 Rules

| Rule | Value | Source | Certainty |
|---|---|---|---|
| Spawn | 100 health + 25 bonus (decays) = **125**, no armor, MG (100 rounds) + gauntlet | `g_startingHealth 100`, `g_startingHealthBonus 25` [cvarlist]; [lutro] | sure |
| Max health | 200 (only the +5 bubble and the mega go above 100) | [g_items] `Pickup_Health`: cap 2 x max for 5 and 100, else max | sure |
| Max armor | 200 (any armor item) | [g_items] `Pickup_Armor`: cap 2 x max health; [lutro] | sure (tiers off) |
| Decay | health above 100 and armor above 100 each lose 1 a second | [g_active] `ClientTimerActions`; [lutro] | sure |
| Armor absorption | armor takes `ceil(0.66 x damage)` while it lasts, health the rest | [g_combat] `CheckArmor`; [ours] exact to the point | sure |
| Fall damage | 5 ("medium", impact delta > 40) or 10 ("far", delta > 60); delta = (impact speed)^2 x 0.0001, x2 if crouched, x0.5 in ankle water, x0.25 waist, none fully under water or on `SURF_NODAMAGE` (pads) | [g_active] `ClientEvents`, `bg_pmove.c` `PM_CrashLand` | likely (no QL cvar found) |
| Respawn after death | allowed after 2.1 s, forced by 2.4 s | `g_respawn_delay_min 2100`, `_max 2400` [cvarlist] (Q3: 1.7 s, press to respawn) | sure on the minimum; [ours] from demos: forced near 4.5 s (unsure which) |
| Telefrag | a teleport or spawn onto a player kills him (Q3 `G_KillBox`) | [q3src] | likely |
| Self-kill | allowed, costs a frag (-1), plus 1 s extra respawn wait in the 2014 rules | [ql2014], [holysh1t-duel] | likely |
| Lava | [ours] 30 a tick at the feet, every 0.7 to 0.8 s; 60 at the waist | poollab | sure |
| Spawn protection | none found in duel | - | unsure |

The fall thresholds as speeds: "medium" (5 damage) above about 632 u/s of downward speed, "far" (10) above about 775 u/s;
crouched, above 447 and 548. A plain 275 jump lands at 275 u/s, harmless.

**Armor tiers** exist in QL as a **server option**, off in the standard duel preset ([steam-tiers], 2020, "assuming you
have Armor Tiers enabled"). With tiers on: green 50 (to 100), yellow 100 (to 150), red 150 (to 200), a higher tier blocks
lower pickups and different protection per tier. Our servers run the classic rules: [ours] measured 2/3 absorption on
red and yellow alike. **Ignore tiers unless a server turns them on.**

Q1/QW numbers (red 80%, yellow 60%, green 30%) seen on many pages are Quake 1 rules: not QL.

### 2.2 Effective health: the stack formula

Because armor soaks 2/3 of each hit until it runs out:

- armor runs out after 1.5 x A damage, during which health loses 0.5 x A;
- if H > A / 2, the rest comes off health at full rate: total = **H + A**;
- if H <= A / 2, health runs out first: total = **3 x H**.

So **effective health = min(H + A, 3H)**: armor counts only up to twice the health. Worked examples:

| Stack (health / armor) | Damage to kill | Note |
|---|---|---|
| 125 / 0 (spawn) | 125 | two rails (160) kill; one direct rocket + 25 more |
| 100 / 50 | 150 | |
| 100 / 100 | 200 | three rails |
| 100 / 200 | 300 | (3H = H + A = 300: the armor just fits) |
| 50 / 150 | 150 | 3H = 150: 50 of the armor is wasted |
| 200 / 100 | 300 | |
| 200 / 200 | 400 | the maximum stack; decays 2 a second |

(Rounding with `ceil` moves these by a point or two.) The ceiling also means a heavily armored player at low health is
fragile: what kills him is the health.

### 2.3 What an item is worth in damage (from the formula)

| Item | Gives | Effective health gained |
|---|---|---|
| Red armor (RA) | +100 armor (to 200) | up to +100, but only while H >= (A + 100) / 2; at 125 / 0: +100 (to 225 effective, 3H = 375) |
| Yellow armor (YA) | +50 armor | up to +50 |
| Green armor (GA) | +25 armor | up to +25 |
| Shard | +5 armor (to 200) | up to +5 |
| Mega health (MH) | +100 health (to 200) | +100, and raises the armor ceiling by 200 |
| +50 / +25 health | to 100 only | +50 / +25 below 100, nothing above |
| +5 bubble | to 200 | +5 |

---

## 3. Items and timing

### 3.1 Respawn times in QL duel

| Item | Respawn | Counted from | Source | Certainty |
|---|---|---|---|---|
| Mega health | 35 s | the pickup | [g_items] `RESPAWN_MEGAHEALTH 35`; [lutro], [esr-timing], [holysh1t-duel] | sure |
| Red / yellow / green armor, shards | 25 s | the pickup | [g_items] `RESPAWN_ARMOR 25`; [lutro], [esr-timing] | sure |
| Health +5 / +25 / +50 | 35 s | the pickup | [g_items] `RESPAWN_HEALTH 35` | likely |
| Weapons | 5 s | the pickup | `g_weaponRespawn 5` [cvarlist]; "unified at 5 s in all modes" [ql2014]; [ours] cvar | sure |
| Ammo | 40 s | the pickup | `g_ammoRespawn 40` [cvarlist]; [ours] cvar | sure |
| Dropped weapon (on death) | lies 30 s | the death | [ours] droplab | sure |

Notes:

- **The mega's clock starts at the pickup in Q3 and QL**, not when the holder's health falls back to 100. The "wears
  off" rule (respawn 20 s after the holder drops to 100) is QuakeWorld's, and CPMA's is different again ([qw-mh] for the
  QW rule). Old Q3 tourney maps used 120 s for the mega ([fandom-mh] extract: `35//120` in the source shows the old
  value). QL also had maps with a 2-minute mega (qztourney4, qztourney6 [holysh1t-duel]); none of our ten.
- Some guides (the Dignitas article [dignitas]) say 30 s for both mega and armor: that is not QL duel (it matches Quake
  Champions-style timers). **Ignore.**
- QL has in-world item timers (`g_itemTimers`), but the **duel factory turns them off** (`g_itemTimers 0` [factories]).
  In duel the player times items himself.
- All items are present at the start of a game in Q3 rules (only powerups wait); our servers run no powerups.

### 3.2 How people time items

- They read the game clock (`cg_drawTimer 1`) at the pickup and add 25 or 35 s by a digit trick: for armor
  (+25) round the seconds and swap the last digit 0<->5, 1<->6, ... ; for the mega (+35) swap the tens 0<->3, 1<->4,
  2<->5 and add 5 ([esr-timing]; [lutro] gives "round to the nearest 5 s": an armor taken at 1:15 is back at 1:40).
- They track three items at once in a fixed order (MH, RA, YA) [esr-timing]; some top players deliberately play
  without the clock to keep their eyes on the opponent [esr-timing].
- **Enemy pickups they did not see are timed by sound**: the pickup sound of the mega and of the armors is distinct and
  heard within earshot ([holysh1t-duel]: footsteps, jumps and pickups give away place and item state).
- When an item is about to come up, the player in control is there a second or two early; the other side shoots the spot
  (a rocket or grenade on the respawn) to deny it or to catch the taker ([holysh1t-duel] comments).
- Behind on stack: slow down, gather yellow armor, shards and bubbles, and retake control later ([holysh1t-duel]).

### 3.3 Items on our ten maps (the real duel item lists, measured on our servers: `plugins/duel_items.json`)

| Map | MH | RA | YA | GA | Shards | +5 / +25 / +50 | Weapons |
|---|---|---|---|---|---|---|---|
| Blood Run | 1 | 1 | 2 | 0 | 11 | 7 / 4 / 1 | RL, RG, LG, SG, GL, PG |
| Aerowalk | 1 | 1 | 1 | 2 | 0 | 4 / 6 / 0 | RL x2, RG, LG, SG, GL |
| Lost World | 1 | 1 | 2 | 0 | 8 | 4 / 6 / 3 | RL, LG, SG, GL, PG (**no rail**) |
| Sinister | 1 | 1 | 2 | 0 | 5 | 8 / 5 / 1 | RL x2, RG, LG, SG, GL, PG |
| Furious Heights | 1 | 1 | 2 | 0 | 5 | 3 / 6 / 1 | RL x2, RG, LG, SG, GL, PG |
| Battleforged | 1 | 1 | 1 | 1 | 5 | 9 / 3 / 1 | RL x2, RG, LG, SG, GL, PG |
| Campgrounds | 1 | 1 | 1 | 0 | 5 | 0 / 6 / 0 | RL, RG, LG, SG x2, GL, PG |
| Hektik | 1 | 1 | 1 | 1 | 6 | 4 / 5 / 1 | RL x2, RG, LG, SG, GL, PG |
| Toxicity | 1 | 1 | 2 | 0 | 3 | 3 / 4 / 1 | RL x2, RG, LG, GL, PG (no SG) |
| Cure | 1 | 1 | 1 | 2 | 11 | 5 / 5 / 1 | RL x2, RG, LG, SG, GL, PG |

Every map has exactly one mega and one red armor: the two items a duel is built around. No map has the HMG.
Per minute a map's big items can deliver at most: MH 100 x 60/35 = 171 health, RA 100 x 60/25 = 240 armor, each YA 120
armor; against 2 a second of decay above 100 for a full stack (120 a minute of health and 120 of armor).

---

## 4. Movement

### 4.1 QL's movement constants (duel)

QL's physics are Quake 3's (VQ3) with QL's own additions, all set by `pmove_*` cvars. Default list from [cvarlist];
the duel factory overrides from [factories].

| Setting | QL default | **Duel factory** | Q3 (VQ3) | Meaning |
|---|---|---|---|---|
| `g_speed` | 320 | 320 | 320 | run speed |
| `g_gravity` | 800 | 800 | 800 | |
| `pmove_JumpVelocity` | 275 | 275 | 270 | jump speed (QL jumps a little higher: 47.3 units [ours]) |
| `pmove_WalkAccel` / `WalkFriction` | 10 / 6 | same | 10 / 6 | ground accel and friction |
| `pmove_AirAccel` | 1 | 1 | 1 | air accel |
| `pmove_AirControl` | 0 | 0 | none | CPMA-style air control: **off** |
| `pmove_StrafeAccel`, `WishSpeed`, `AirStopAccel` | 1, 400, 1 | same | - | only matter with air control on |
| `pmove_ChainJump` / `ChainJumpVelocity` | 1 / 110 | same | none | a jump soon after the last is faster: [ours] +110 x (1 - t/500 ms) |
| `pmove_JumpTimeDeltaMin` | 100 | **50** | none | no jump within this many ms of the last |
| `pmove_BunnyHop` | 1 | **0** | none | QL's "forward key alone" push toward 640 u/s: **off in duel** |
| `pmove_AutoHop` | 1 | 1 | none | holding jump re-jumps on landing (also needs the client's `cg_autoHop 1`) |
| `pmove_StepJump` / `StepJumpVelocity` | 1 / 48 | same | none | a small jump boost when stepping up |
| `pmove_CrouchStepJump` | 1 | **0** | none | |
| `pmove_AirSteps` / `AirStepFriction` | 1 / 0.03 | same | none | stepping onto a ledge while rising |
| `pmove_StepHeight` | 22 | 22 | 18 | |
| `pmove_RampJump` | 0 | 0 | none | ramp jump boost off |
| `pmove_DoubleJump` | 0 | 0 | none | CPMA-style double jump off |
| `pmove_CrouchSlide` | 0 | 0 | none | crouch slide off (exists for other factories) |
| `pmove_WaterSwimScale` / `WadeScale` | 0.6 / 0.8 | **0.5 / 0.75** | 0.5 / - | |
| `pmove_noPlayerClip` | 0 | 0 | 0 | **players are solid to each other** |
| `sv_fps` | 40 | 40 | 20 | server frames a second (25 ms) |

No velocity snapping in QL: the physics do not depend on the client's frame rate the way Q3's did (Q3 at 125 fps rounded
velocity to whole numbers each frame, which let a player jump higher at 125 or 333 fps: [fandom-hwj], [q3w-fps]).
[ours] rjlab: QL's gravity is exactly 20 u/s a 25 ms frame and a plain jump peaks at 47.25 units.

### 4.2 Why strafe jumping works (from the code)

Air movement is `PM_Accelerate` with accel 1 ([q3src] `bg_pmove.c`):

```
currentspeed = dot(velocity, wishdir)
addspeed     = wishspeed - currentspeed           (nothing added if <= 0)
accelspeed   = min(accel * frametime * wishspeed, addspeed)
velocity    += accelspeed * wishdir
```

The cap is on the **projection** of the velocity on the wish direction, not on the speed. If the player keeps the wish
direction at a large angle to his velocity, the projection stays under 320 and every frame adds up to
a = 1 x 0.008 x 320 = 2.56 u/s (at 125 fps), partly sideways, so the total speed grows.

- **Best angle** between velocity and wish direction: cos(theta) = (320 - a) / v. With a = 2.56: theta = 7 degrees at
  320 u/s, 37 at 400, 50 at 500, 58 at 600, 63 at 700. Holding forward + a strafe key, the wish direction is 45 degrees
  off the view, so the view points 38 degrees to the other side of the velocity at 320, about level with it near 450,
  and to the strafe side above that. Turning the mouse smoothly toward the strafe side keeps the angle right.
- **Gain at the best angle**: v^2 grows by 640a - a^2 = 1,632 a frame, so dv/dt = 1632 x 125 / (2v) = about
  **320 u/s^2 at 320 u/s, 255 at 400, 170 at 600**. The gain is nearly independent of frame rate (a is proportional to
  the frame time). This is the ideal; people get a fraction of it.
- **Landing** costs: on the ground, friction (6) acts for the frames before the next jump (one frame with auto-hop or a
  well-timed press), and ground acceleration pulls the speed toward 320 in the wish direction. QL's chain jump makes a
  jump within 500 ms of the last one faster upward (+110 at 0 ms, fading to 0 at 500 ms [ours]), so a quick re-jump is
  also a longer one.
- **Circle jump**: on the ground, accel 10 adds 25.6 u/s a frame; turning the view while running forward+strafe swings
  the wish direction across the velocity so that the ground move ends above 320 at the jump. The usual start of a
  run; community pages cite "past 500" for Q3 [strafe-wiki] but that number is unsourced. **unsure** of a typical figure.
- **Without a strafe key** (forward only) in the air: no gain in duel (BunnyHop 0). With the strafe key alone and no
  forward key, Q3/QL gain too (the "half beat" / side strafe), at a different angle.
- **Typical speeds**: a running player 320 u/s; strafe jumping a corridor 400 to 500; long runs to 600+. I found no
  measured pro distribution online; the pro demos could give one (not done here).

### 4.3 Rocket, grenade and plasma jumps

- **Rocket jump**: a rocket at the feet. The push is from the full splash (84 x falloff x 1.1 x 5 = up to about 460 u/s
  plus the `g_knockback_z` kick), the damage is half: up to about 42, two-thirds of it from armor. [ours]: the sim's
  fit gives about 549 u/s of push from a rocket at one's own feet (450 at an enemy's); rjlab found a rocket fired on the
  jump's own frame gives a rise of 319 against 264 when it leaves one 25 ms frame later (timing matters by a sixth), and
  the sim's rocket-jump damage within a point of the game in 486 cases. Running rocket jumps carry the run speed.
- **Grenade jump**: [ours] one case: 43 damage and 277 u/s up with the blast 42 units away (not re-measured since the
  grenade fix).
- **Plasma climb**: each bolt at the feet pushes about 95 u/s and costs about 8 [ours]; at 10 a second, holding jump
  against a wall climbs it. Plasma's self knockback is 1.3 [cvarlist].
- **Jump pads** throw a player to a fixed target; **teleporters** set his speed to 400 u/s along the exit direction,
  turn his view to the exit's angle, and kill anyone standing on the exit [ours, q3src].

### 4.4 Noise: what makes a sound

From the Q3 movement code ([q3src] `PM_Footsteps`, `PM_CrashLand`):

- **Footsteps**: only on the ground, only with a move key held (forward, back or strafe), **not with the walk key, not
  crouched**. With 125 fps the step cycle adds 3 a frame (`(int)(0.4 x 8)`) and a step sounds every 128: **one step
  every 0.34 s** whatever the speed. The walk key also forces the walk flag automatically when the move command is 64 or
  less (half speed). A player sliding without keys makes no steps. QL can turn footsteps off per server
  (`footsteps on/off` callvote [esr-callvote]); our duel servers leave them on.
- **Jumps**: a jump grunt every jump (`EV_JUMP`). Strafe jumping is loud.
- **Landings**: from a small drop a footstep; a short fall (delta > 7) a landing thud; medium and far falls a pain grunt.
- **Weapons**: every shot has a firing sound; the LG and the rail have a "hum" loop while held (and the gauntlet), which
  says which weapon the enemy holds ([holysh1t-duel]).
- **Pickups**: each item has its pickup sound, played at the player; item respawn sounds play at the item.
- **Pain**: four pain sounds by the victim's health: under 25, under 50, under 75, 75 and up ([q3src] `CG_PainEvent`).
  A hit therefore tells both sides a health band.
- **Water**: splashes when wading, a swim sound at the surface, silence under water.

**How far sounds carry** ([snd_dma]): full volume within 80 units, then the volume falls by 0.0008 a unit to nothing at
**about 1,330 units**; left/right panning from the direction. On top of that, a server sends a client an entity (and its
sounds) only when it is in the client's **potentially visible set** (PVS), so a sound behind thick map geometry two rooms
away is not heard at all, however near ([ours] confirmed on the pro demos: 99.3% of frames the enemy was sent, he was in
the PVS). QL's client is closed; the 1,330 is Q3's and **likely** QL's.

---

## 5. Aiming

### 5.1 The game's timing and netcode

- The server runs at **40 frames a second** (25 ms; `sv_fps 40`, locked in QL). The client moves at its own rate
  (125 fps is the old standard; QL allows up to 250 [comm]) and sends a command each frame.
- Hitscan shots are **lag compensated** on the server (the target is rewound to what the shooter saw); projectiles are
  not ([esr-unlagged], 2009, users; **likely**). Users report it works best under about 80 ms of ping.
- A person sees the enemy as of the last snapshot (every 25 ms) plus the client's interpolation and his ping.

### 5.2 Hitboxes

- **Movement** uses Q3's box: 30 x 30 x 56 units (mins -15,-15,-24; maxs 15,15,32), crouched top 16.
- **Shots**: since December 2009 QL hits a **cylinder**, not the box ([q3w-hitbox], [quakehaus-hitbox]). The change cut
  the hittable area by roughly 30 to 40%; March 2011 grew it by 10% "to more closely mimic the area of the old cuboid";
  a hemisphere on top lets hitscan hit the head; a 2012 fix corrected cylinder misses at some angles
  ([quakehaus-hitbox]). Same size for every model. **No headshot damage** in QL.
  Exact radius and height: **not found**. **likely** (two community sources).
- Crouching in the air raises the body's centre a little; small effect ([quakehaus-hitbox]).

### 5.3 Human aim and perception (facts about people)

- **Sensitivity**: Quake players use roughly 20 to 45 cm per 360 degrees; the community settings list shows
  e.g. 34.6 cm (Cypher, 400 dpi, sens 3, fov 106) and others 35 to 72 cm ([stripyq]). A few top players are reported as
  low as 10 cm (anecdotal, [mouse-sens]).
- **Field of view**: typical `cg_fov` 96 to 110 among listed players ([stripyq]); QL's range is up to 130.
- **Visibility**: most competitive players force a bright enemy model (`cg_forceEnemyModel`, bright skins) and lower
  detail, so an enemy in view is very easy to see; QL's own option set allows this, so it is fair for Bobby to see any
  enemy in his view.
- **Reaction**: simple visual reaction time is about 200 ms for anyone and does not differ much between pro and amateur
  gamers in a controlled test ([bickmann]). In real duels the delay to a first hit is much longer: our pro measure gives
  0.32 to 0.76 s by how far off the crosshair the enemy appears (section 1.6); people fire about 0.5 s after an enemy
  appears (`duel_env.py`'s `surprise_ms` note).
- **Tracking (LG)**: the beam needs the crosshair on a 30-unit-wide target 20 times a second; at 300 units that is a
  5.7-degree window, at 700 units 2.5 degrees. People lose the most against direction changes (strafe reversals).
- **Leading projectiles**: lead = target speed x flight time. Rockets at a grounded target are aimed at the feet (splash
  reaches within 120 units of the box even on a miss); at an airborne target, at the landing point or direct. A player
  in the air follows a parabola he cannot change much (no air control), which is why jumping in a fight is risky.
- **Rail flicks**: the shot is instant, so the skill is landing the crosshair at the right moment; the 1.5 s reload
  makes each miss costly.
- **Damage feedback**: QL shows damage numbers above the target (`g_damagePlums 2` [cvarlist]) and plays hit sounds
  whose pitch depends on the damage ([qc-hitbeep] notes QL's damage-based hit beep). They tell the shooter how much he
  hit, not the target's remaining health ([esr-sept22]).

---

## 6. Senses and information: what a duel player knows

| Source | What it tells | Limits |
|---|---|---|
| Sight | place, direction, weapon held (model), whether he is in the air | needs a clear line and the enemy in the field of view; a bright forced model makes him easy to see |
| Footsteps | place and direction of a running enemy, every 0.34 s | not when he walks, crouches, or is in the air; PVS and 1,330 units |
| Jump grunts, landings | a moving enemy, often strafe jumping | same |
| Weapon fire sound | his weapon and place | same |
| LG / rail / gauntlet hum | which weapon he holds right now | same, quieter |
| Pickup sounds | which item he took (mega, armor, weapon) and when: starts a timer | same; an unseen pickup must be heard |
| Item respawn sound | an item came back | at the item |
| Pain sounds | his health band (under 25/50/75/above) after each hit | only when he is hit |
| Damage numbers, hit sounds | how much each of my hits did | not his remaining stack |
| Obituary (kill message) | who died, by what weapon | broadcast to all |
| Scoreboard / score | the frag score and the clock | no health or armor of the enemy |
| Item timers | in-world timers | **off in duel** (`g_itemTimers 0`) |
| The respawn | an enemy who just died is out for 2.1 to 2.4 s and spawns at a spawn point | which point: our fit on the pros' demos says the far half from the enemy (86.9%) |

**Sound tracking** (how pros use it, [holysh1t-duel] and general practice): keep a running guess of the enemy's place and
stack from sounds alone; the guess narrows with every step, jump or pickup; a silent enemy is either walking (holding a
place), crouching, or out of earshot. Walking costs speed (about half), so silence itself is information: the enemy
is probably holding, not travelling.

---

## 7. Cross-check: the simulator against Quake Live

Read from `sim/duel_env.py` (constants at lines 49 to 63, 110 to 126, 415 to 427, 3440 to 3456), `sim/qsim.py`,
`sim/q3/bg_pmove.c`, `plugins/duel_items.json`, and the run file of the last run (`docs/runs/1.9/1.9a/train.cmd`)
for the switches that are on.

### 7.1 Values that differ (or may differ)

| Thing | Real QL | Our sim | Source | How sure the difference is real |
|---|---|---|---|---|
| **Knockback factor, LG** | 1.75 (6 x 1.75 = 10.5, cut to 10 points: 50 u/s a tick) | `W_KNOCK` 1.167 (35 u/s); **`KNOCK_QL=1` (2026-11-13): 50 u/s, as measured** | [cvarlist], [esr-callvote]; **[ours] weaponlab set 6 (2026-11-13, `data/weaponlab6`)** | **measured, fixed under `KNOCK_QL`**: a tick in the air pushes 47.5 u/s horizontal at an 18-degree aim = 50 u/s; on the ground friction takes 15 u/s a frame from the hit frame on (34.9, 19.9, 4.9), which is what the old 1.167 had been fitted to |
| **Knockback factor, MG** | 1 (25 u/s a bullet) | 0.4; **`KNOCK_QL=1`: 1, as measured** | [cvarlist]; [ours] weaponlab set 6 | **measured, fixed under `KNOCK_QL`** (air 23.8 at 18 degrees; ground 9.9 = 25 - 15) |
| **Knockback factor, HMG** | 1 (40 u/s a bullet) | 0.625; **`KNOCK_QL=1`: 1, as measured** | [cvarlist]; [ours] weaponlab set 6 | **measured, fixed under `KNOCK_QL`** (air 38.0; ground 24.9) |
| **Knockback factor, SG** | 1 per pellet (500 u/s for 20 pellets) | 0.85; **`KNOCK_QL=1`: 1 a pellet** | [cvarlist]; [ours] weaponlab set 6 | **measured, fixed under `KNOCK_QL`** (air 357 at 44 degrees = 500; ground 415 after the hit frame's friction) |
| **HMG spread** | 400 (about 2.8 degrees) | `MG_SPREAD` 1.4 degrees, shared with the MG | [esr-balance], [fandom-hmg] | high (no HMG on our ten maps, so it matters little) |
| **Shotgun pattern** | fixed 3 rings (10 + 5 + 5), outer ring about 7 degrees, no centre pellet | gaussian, sigma 3 degrees, random (expected hits) | [fandom-sg], [esr-sg] | high on the shape; the sim's **mean** damage at 100/300/600 units was fitted to the game [ours] |
| **Shotgun range** | 1500 units | 8192 | [fandom-sg] | medium (single source); little effect (beyond 1000 the sim's damage is already tiny) |
| **Hitbox for shots** | a cylinder (smaller than the box, +10% in 2011) with a head hemisphere for hitscan | the 30 x 30 x 56 box | [q3w-hitbox], [quakehaus-hitbox] | medium: sizes unknown; the sim may make every weapon slightly easier to hit with, most of all on diagonal shots (box corners) |
| **Players collide** | solid to each other (`pmove_noPlayerClip 0`) | pass through each other | [cvarlist]; audit gap 12 | high (known) |
| **Weapon picked up when already held** | topped up to the pickup amount, else +1 round (Q3 code) | a full pickup added, to the cap | [g_items] | medium (QL not checked; B-14) |
| **Ammo caps, RL and GL** | fandom says 50 | 25 | [fandom-rl], [fandom-gl] | low (conflicting; fandom also says 25 for SG and RG, which the sim has); measure (B-14) |
| **Ammo cap, MG** | unknown in QL (Q3 200) | 150 | [g_items] | low |
| **Footsteps** | every 0.34 s with a move key held on the ground, not walking, not crouched, **whatever the speed** | with `HEAR_FIX`: every `HF_STEP_DT` (0.3 in 1.9a; code default 0.55) while faster than 150 u/s, not crouched | [q3src] `PM_Footsteps` | medium: the sim makes a slow runner (under 150) silent and a sliding player (no keys, over 150) noisy; the game does the opposite. The walk key's 64 limit makes walking about half speed (about 160 u/s), close to the sim's threshold |
| **Hearing distance** | volume to nothing at about 1,330 units (Q3 client), inside the PVS | spheres: steps 1,000 (`EAR_RANGE`), events 1,200 (`HEAR_EVT`), "heard moving" 800 (`HEAR`), hum 500 (`HUM_RANGE`); `HEAR_QL_RANGE` unset in 1.9a | [snd_dma] | medium (QL client closed; what a person notices is less than the full 1,330) |
| **Fall damage** | from the exact impact speed; crouched x2; water x0.5 / x0.25; none on pad surfaces | from the frame before landing (up to 20 u/s low); none of the modifiers | [q3src]; audit gap 8 | high (known) |
| **Grenade self push** | `g_knockback_gl` 1.10 (no separate self value in the dump) | `SPLASH_KNOCK_SELF` 1.3 on the old splash path | [cvarlist] | low (depends on what `GL_QL` uses; check) |
| **Splash shift for GL/PG** | splash measured from the box's nearest point (no shift) | `SPLASH_NEAR` 20 units closer, still on plasma (audit gap 6) | [g_combat] | medium (rockets fixed by `RL_QL`; plasma's 20-unit radius is doubled by the shift) |
| **Upward kick on knockback** | `g_knockback_z 24` (meaning undocumented) | splash pushes upward; hitscan pushes along the shot | [cvarlist] | low (unknown meaning) |
| **Respawn wait** | allowed from 2.1 s, forced at 2.4 s (cvar) | `RESPAWN_QL=1`: 2.1 s (Bobby taps fire); sim note says forced 4.5 s from demos | [cvarlist] | low (only matters for people) |
| **Shot timing on a flick** | fires in the first 8 ms move of the frame | `FIRE_QL=1` handles it (audit gap 1) | [ours] | resolved if `FIRE_QL` is right |

**The small kicks' friction (measured 2026-11-13, weaponlab set 6):** for the lightning, the machine guns and shotgun pellets the game sets no no-friction time (Q3 would floor it at 50 ms); a rail (136 ms) and a rocket (180 ms) keep their speed. The simulator's `KNOCK_QL=1` does the same (`sim/sim_api.c` `qsim_knockback_t`). One difference stays: the game applies the target's move after the hit within the hit frame, the simulator a frame later (the same for every weapon).

### 7.2 Values that match (checked)

| Thing | Real QL | Our sim |
|---|---|---|
| Damage per hit (RL 100, RG 80, LG 6, MG 5, SG 5 x 20, GL 100, PG 20, HMG 8, G 50) | [cvarlist] | `W_DMG` same |
| Fire intervals (0.8, 1.5, 0.05, 0.1, 1.0, 0.8, 0.1, 0.075, 0.4 s) | [cvarlist] `weapon_reload_*` | `W_REFIRE` same |
| Projectile speeds RL 1000, GL 700, PG 2000 | [cvarlist] | `P_SPEED` same |
| Splash RL 84/120, GL 100/150, PG 15/20 | [cvarlist] | `P_SPLASH`, `P_RADIUS` same |
| Knockback RL 0.9 (self 1.1), RG 0.85, GL 1.1, PG 1.1 (self 1.3), G 1 | [cvarlist] | `W_KNOCK` and `RL_QL` same |
| LG range 768 | [cvarlist]/[ours] | `W_RANGE` 768 |
| MG spread 200 (1.4 degrees) | [fandom-mg], Q3 `MG_SPREAD 200` | `MG_SPREAD` 1.4 |
| Own splash halved | [g_combat] | `SELF_FACTOR` 0.5 |
| Switch time 200 + 200 ms (+ a frame) | [cvarlist] | `SWITCH` 0.425 |
| No switch during a reload; 0.5 s dry click | [q3src] | as the code |
| Armor 2/3, `ceil` | [g_combat] | `ARMOR_ABSORB` 0.66, `ceil` |
| Armor and health caps (200; +25/+50 to 100) | [g_items] | `ITEM_DEFS` |
| Decay 1/s above 100 for both | [g_active] | same |
| Spawn 125 / 0, MG 100 | [cvarlist] | `SPAWN_HP` 125, loadout "mg" |
| Respawns: MH 35, armor 25, health 35, weapon 5, ammo 40 | [g_items], [cvarlist] | `ITEM_DEFS` |
| No ammo packs in duel | [ours] itemlab | `AMMO_PACKS=0` in 1.9a |
| Pickup amounts (weapons and boxes) | [ours] itemlab | `ITEM_DEFS` |
| Movement: speed 320, gravity 800, accel 10/1, friction 6, no air control, jump 275, step 22 | [cvarlist] | `bg_pmove.c` + `QL_PARAMS` + `QL_MOVE` |
| Duel factory: BunnyHop off, jump delta 50 ms, swim 0.5, wade 0.75 | [factories] | `QL_FWD=0`, `DQ_JUMP_MS=50`, `pm_swimScale` 0.5, `DQ_WADE=0.75` in 1.9a |
| Chain jump +110 within 500 ms; air steps; auto-hop | [cvarlist], [ours] | `QL_JUMP=1`, `AUTO_HOP=1` |
| No velocity snapping | [ours] rjlab | `QL_FLOAT=1` |
| Server frame 25 ms | `sv_fps 40` | `DT` 0.025 |
| Pain sounds in four bands of 25 | [q3src] | four bands |
| Telefrag | [q3src] | `TELEFRAG=1` |
| Items per map | [ours] maplab | `plugins/duel_items.json` |

---

## 8. Implications for Bobby

These are facts of the game, stated for a learning duel bot. **Project rule 12 applies**: the pro numbers above
(accuracies, reaction times, sensitivity) may be used to measure the game and set human limits, never as a target for
his behaviour; nothing here says "bring his X to the pros' Y".

### 8.1 The stack decides fights, and the formula is min(H + A, 3H)

- Armor is worth its points only up to twice his health. A player at 50/150 dies to 150, not 200. So health and armor
  are not interchangeable: low health with high armor is a trap, and the **mega raises the value of all armor he holds**.
- The **red armor every 25 s** gives more effective health per minute (240) than the **mega every 35 s** (171), but the
  mega is what lets a big armor count. The two together make the 300+ stacks that win trades.
- Everything above 100 decays at 1 a second each: a full stack loses 2 points a second. A stack is a wasting asset; it
  should be used (pushed into a fight) while it lasts.
- A frag resets the loser to 125/0 and takes him out for 2.1 s; the winner keeps his stack and the clock on the items.
  The seconds right after a frag are the cheapest time to take the mega or armor, and the respawn rule (far half from
  the enemy) says roughly where the loser comes back.

### 8.2 Which weapon at which range (full-rate numbers; real numbers scale with hits)

| Range | Strong | Why |
|---|---|---|
| Point blank (under 150) | PG (200 DPS), SG (100 in one shot), RL (direct 100 + splash), G (if nothing else) | fast damage; rockets and grenades at this range splash the shooter too (half) |
| Close to mid (150 to 500) | RL, LG, PG | rockets can still be led and splash the feet; LG's 120 DPS needs only tracking |
| Mid (500 to 768) | LG, RG | LG still in range; rockets take 0.5 to 0.8 s to arrive and can be dodged |
| Long (over 768) | RG (80 instant, unlimited range); MG to finish | LG does nothing beyond 768 |

- **Burst against stream**: the rail does 80 at once but 53 DPS over time, and locks the shooter for 1.5 s (1.9 s to
  fire anything else). LG and PG do more over time but need the enemy in view and in range the whole time. Against a
  bigger stack, the burst weapons (rail, rocket) are what break it down; the stream finishes.
- **Kill thresholds**: a rail + a rail (160) kills a spawn (125) and nothing more; a direct rocket + a rail (180) kills
  up to 180; 100/100 needs 200.
- His own measured damage rate (the `FIN_RATE` of 1.9a, a fact about his hands, not a target) is highest with LG
  (52 per second under 400 units) and PG (46), then RL (39) and rail (20); everything falls off with range. That is his
  current hands; the table above is the game's ceiling.

### 8.3 Projectiles, splash and dodging

- A rocket at 1000 u/s needs 0.3 s per 300 units. A runner at 320 u/s moves 96 units in that time, a strafe jumper at
  450 moves 135: beyond the 120 splash radius at mid range. Close rockets at the feet always pay (splash measured to the
  box); far rockets pay only as prediction (where he must go: a doorway, an item, a landing).
- A player in the air cannot steer (no air control, accel 1): his landing point is predictable for the whole jump.
  Jumping in view of an enemy with rockets or a rail is costly; jumping out of view is free speed.
- Splash does not go through walls or floors, but it reaches about 15 units round an edge.
- Knockback is large: a direct rocket pushes the victim 450 u/s, an LG stream about 50 u/s a tick. Being hit moves him,
  which spoils his aim and his path.

### 8.4 Movement

- Strafe jumping gains up to about 250 to 320 u/s each second of air at the ideal angle; the angle that works changes
  with speed (7 degrees from the velocity at 320, 37 at 400, 50 at 500). It is the way to cross a map faster than 320 and
  to arrive at an item first.
- In duel there is **no gain from forward alone** (BunnyHop off): speed comes only from strafing.
- QL's chain jump makes quick re-jumps higher; the auto-hop removes the timing of the press.
- Rocket jumps cost up to about 42 (two-thirds from armor when he has it) for a large height gain: worth it to reach the
  red armor or the mega first, ruinous at 125/0 against an enemy waiting with a rail.

### 8.5 Information

- Running makes footsteps every 0.34 s; walking and crouching are silent; jumps and pickups are loud. Sounds stop at
  about 1,330 units and at the PVS. A silent enemy is likely holding a place.
- Pain sounds give the enemy's health band after each hit; damage numbers give his own hits; nothing gives the enemy's
  armor. The enemy's stack must be estimated from items heard or seen and damage dealt.
- No item timers in duel: knowing when the mega and the red armor come back is a skill (35 s and 25 s from the pickup,
  which may itself have been heard, not seen).

### 8.6 What to measure next (from the gaps in section 7)

1. Knockback of LG, MG, HMG, SG in the air on the real server (does 1.75 / 1 hold, and why the sim's fit is lower).
2. The ammo caps and the "weapon already held" pickup (B-14): it sets how many rockets a held launcher spot is worth.
3. The hit cylinder's size, if the game's cvars or a hit test on the server can show it (it changes every weapon's value
   a little, the rail's and LG's most).
4. Footstep rule (keys, not speed) and the hearing distance: they set what he can know of the enemy.
5. The shotgun's real pattern (the fixed rings).

---

## Sources

- [cvarlist]: Quake Live dedicated server `cvarlist` (community paste, undated): https://pastebin.com/zJ6XqCNq
- [cvar-race]: a race/PQL-style pmove config (10 ms weapon switch, air control on): https://pastebin.com/NY8D4QfT
- [factories]: Default Quake Live factories, formatted (duel factory overrides): https://gist.github.com/cstewart90/a1163bad196977e351eb
- [standards]: quakelive-server-standards, factory cvars: https://github.com/quakelive-server-standards/quakelive-server-standards/blob/master/factories/cvars.md
- [esr-balance]: ESReality, "QL vs VQ3 weapon balance" (Therapist, 2016-10-10): https://esreality.com/post/2843260/ql-vs-vq3-weapon-balance
- [esr-callvote]: ESReality, "Custom callvote plugin (LG damage, etc.)" (x0rnn, 2016-01-05): https://esreality.com/post/2791943/custom-callvote-plugin-lg-damage-etc/
- [ql2014]: holysh1t, Quake Live gameplay update (August 2014): https://holysh1t.net/?p=5755
- [g_items], [g_combat], [g_active]: ioquake3 game code: https://github.com/ioquake/ioq3/tree/main/code/game
- [snd_dma]: ioquake3 client sound: https://github.com/ioquake/ioq3/blob/main/code/client/snd_dma.c
- [q3src]: the above plus our vendored `sim/q3/bg_pmove.c` (ioquake3)
- [lutro]: Beginner's guide to Quake Live: https://www.lutro.me/quake-live-beginner-guide
- [holysh1t-duel]: Quake Live duel strategy, the basics: https://www.holysh1t.net/introduction-quake-live-duels/
- [esr-timing]: ESReality, "The novice's Quake3 timing guide": https://www.esreality.com/post/869752/the-novices-quake3-timing-guide
- [dignitas]: Dignitas, "How to master Quake spawn timers" (30 s timers: not QL duel): https://dignitas.gg/articles/blogs/Quake/11424/how-to-master-quake-spawn-timers-controlling-mega-and-armor
- [qw-mh]: QuakeWorld wiki, Mega Health (the QW wear-off rule): https://quakeworld.nu/wiki/MH
- [steam-tiers]: Steam discussion, "Did you guys know this about armor?" (2020-11-24): https://steamcommunity.com/app/282440/discussions/0/2963893984930878949/
- [fandom-ql], [fandom-sg], [fandom-gl], [fandom-rl], [fandom-lg], [fandom-rg], [fandom-pg], [fandom-mg], [fandom-hmg], [fandom-mh], [fandom-hwj]: Quake fandom wiki pages (read through search extracts only; direct fetch refused): https://quake.fandom.com/wiki/Quake_Live, .../Shotgun_(Q3), .../Grenade_Launcher_(Q3), .../Rocket_Launcher_(Q3), .../Lightning_Gun_(Q3), .../Railgun_(Q3), .../Plasma_Gun, .../Machine_Gun_(Q3), .../Heavy_Machine_Gun_(QL), .../Megahealth_(Q3), .../High_Wall_Jump
- [esr-sg]: ESReality, "sg question" (`cg_trueShotgun`): https://www.esreality.com/post/2799387/sg-question/
- [q3w-hitbox]: Quake3World, "Quakelive receives new hitboxes/hit detection" (2009): https://www.quake3world.com/forum/viewtopic.php?f=6&t=42210
- [quakehaus-hitbox]: quakehaus, Hitzylinder (QL hit cylinders, 2009-2012 changes): https://www.quakehaus.com/archiv/quakelive/quake3_quakelive_waffenguide_hitzylinder.html
- [esr-unlagged]: ESReality, "QL 'unlagged' netcode" (2009): https://www.esreality.com/post/1768002/ql-unlagged-netcode/
- [esr-lg]: ESReality, "Your average LG accuracy": https://esreality.com/post/2727116/yor-average-lg-accuracy-with-60hz-in-ql/
- [esr-sept22]: ESReality, Quake Live Sept 22nd update (hit beep does not reveal health): https://esreality.com/post/1756026/quakelive-sept-22nd-update
- [qc-hitbeep]: Quake Champions changelog noting QL's damage-based hit beep: https://games.softpedia.com/progChangelog/Quake-Champions-Changelog-149341.html
- [q3w-fps]: Quake3World, frame-rate physics: https://quake3world.com/forum/viewtopic.php?p=46497
- [strafe-wiki]: strafejumping article mirror (unsourced speed claims): https://bafybeiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq.ipfs.4everland.io/wiki/Strafejumping.html
- [stripyq]: Quake players' settings list: https://stripyq.github.io/quakesettings/players/cypher/
- [mouse-sens]: mouse-sensitivity.com Quake Live forum: https://www.mouse-sensitivity.com/forums/topic/43-quake-live/
- [bickmann]: Bickmann and Wechsler, reaction times of esports players and athletes: https://irma-international.org/article/comparison-of-reaction-time-between-esports-players-of-different-genres-and-sportsmen/274054/
- [ours]: `docs/archive/versions/v0.4/FIDELITY_AUDIT.md`, `docs/archive/versions/v0.3.7/REPORT_PLAYTEST_2026-10-19.md`, the comments in `sim/duel_env.py` and `sim/qsim.py`, `docs/archive/versions/v0.5.1/AIM_LIMITS.md`, `docs/runs/2.1/DESIGN.md`.

Not reached: Liquipedia's arena FPS pages (not found by search), YouTube tutorials (no transcripts retrieved), the
Quake fandom wiki directly (refused). Things still unknown after this pass: the hit cylinder's size, QL's ammo caps for
RL/GL/MG, whether QL changed Q3's "weapon already held" pickup rule, the exact meaning of `g_knockback_z` and the splash
offsets, and a measured distribution of pro movement speeds.
