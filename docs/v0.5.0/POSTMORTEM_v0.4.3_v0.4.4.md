# Post-mortem: v0.4.3 and v0.4.4 (spawn camping), and what v0.5.0 changes

*2026-10-26. For review. Numbers are from the simulator unless marked "server". Scripts and raw outputs are in the session
scratchpad (`v044play/`, `v050/`, `aimcal/`, `ammolab/`, `lgcamp/`).*

## 1. What happened

On a local play server, v0.4.4 (save u211, strategy head at 0.9) played the owner like this:
- He looped one item and the weapon next to it and never went looking for the player.
- **Hektik, 4.9 minutes:** 7 megas, 6 yellow armors, **31 lightning-gun pickups**, 0 rocket-launcher pickups.
- **Blood Run, 1.9 minutes:** 13 lightning-gun pickups, 59% of his time within 300 u of the lightning gun's spawn.
- With the head switched off, he camped the rail and red-armor corner instead.

The run was stopped and saved (`duel_gru_v0_4_4/keep/stopped_20261026/`). The owner scrapped v0.4.3 and v0.4.4.

## 2. It was the network, not the server

The first suspicion was the new play-server build. It was ruled out three ways:
- **Same save, self-play in the simulator:**
  - Blood Run: lightning gun as his held target 82%, 47% of the time within 300 u of its spawn, 3.4–3.7 lightning pickups a minute.
  - Head shut: red armor 57%, rail in hand 75%.
  - Both matched the server.
- **Server against simulator inputs:** compared column by column (`v044play/compare_inputs.py`). The gaps came from the opponent being a person: the owner never died, so "enemy has mega / red armor" stayed on. None explained the looping.
- **The forward pass:** server and training compute the same answer from the same inputs (`tools/netpass_check.py`, every difference 0).

## 3. When it started (behaviour study: 12 saves × self-play on 4 maps + games against a scripted spot-holder)

| Save | Lightning gun as held target | Time near the LG spawn | Map coverage (cells/min) | Rockets in hand (mid range) | Frags/min vs the spot-holder |
|---|---|---|---|---|---|
| v0.4.1 end | 9% | 13% | 29.2 | 0.14 | 0.45 |
| v0.4.2 u100 | 8% | 11% | 28.0 | 0.13 | 0.49 |
| v0.4.2b end | 8% | 12% | 25.4 | 0.15 | 0.44 |
| v0.4.3 u40 | 9% | 12% | 28.6 | 0.13 | 0.38 |
| v0.4.3 u70 | 10% | 15% | 24.7 | 0.12 | 0.44 |
| v0.4.3 end (u80) | 14% | 16% | 24.5 | 0.11 | 0.43 |
| v0.4.4 u10 | 16% | 15% | 24.7 | 0.10 | 0.49 |
| v0.4.4 u141 (head shut) | 16% | 16% | 24.5 | 0.07 | 0.45 |
| v0.4.4 u181 (head 0.3) | 19% | 17% | 22.2 | 0.07 | 0.45 |
| v0.4.4 u221 (head 0.7) | **43%** | **25%** | 23.5 | **0.04** | 0.50 |

- **The drift began late in v0.4.3,** after the item rule (the teacher for which item to go for) had faded to 0. From then on nothing guided his choice of target.
- **The rockets fell steadily** through v0.4.4.
- **It exploded once the strategy head opened.** The head's bias was about half of his target choice, and it learned "lightning gun" because those fights paid most.

## 4. Root causes

1. **Instant-hit aim was too easy in the simulator.**
   - Hit rates at level 4, against v0.4.2b's end: LG 0.51 / rail 0.59 / rockets 0.49.
   - Pros' averages (4,166 demos): LG 32.7% / rail 43.5% / rockets 31.2%.
   - Bobby on the real servers: LG ~0.38 / rail ~0.43.

   So lightning fights paid far more than they should have: 82% of his frags were with the lightning gun.
2. **A loophole in how targets work.**
   - A weapon target stayed "done" after he picked it up, with his route and legs still pointing at its spawn.
   - Choosing the same target again started no new trip.
   - Weapons come back every 5 s and each pickup refills ammo.

   So a weapon target acted as a free "hold this spawn" order, and both seats in self-play learned to hold the best instant-hit weapon's spawn.
3. **No guide after the item rule faded,** and then the head, which optimised target choice on payoffs warped by 1 and 2.
4. **Shaping pay that bribed target choice.** The speed pay (0.85 a player-minute in games, against 1.34 for frags) paid for weapon-spawn circuits and for facing away from the enemy.

## 5. Why monitoring missed it

- **The checks played each save against the previous one** (v0.4.3's end, v0.4.2's end). A habit both share never loses: "75% against v0.4.3's end" said nothing about whether he plays sensibly.
- **Training's target shares averaged every kind of round,** including practice rounds where the target is given and league opponents with the head shut. The lightning gun showed as 0.20–0.32, not 82%.
- **Nothing measured roaming, camping or hunting.**

## 6. Other problems found and fixed today

| Problem | Fix | Verified |
|---|---|---|
| A play-server build for the owner was not compared with the simulator's behaviour before handoff | Every play build gets the server-against-simulator input check before the owner plays | tool in place |
| The first "LG 91%" figure read his target output on every frame, but it is only used every few frames | Measure the held target (and position) instead | corrected in the study |
| Mind-log "tgt" was misread as his own target; it is his guess of the enemy's target | corrected in the report | – |
| Starting the trainer as a child of a background helper risks it dying with the helper | Launch only via PowerShell `Start-Process` | v0.5.0 launched that way |

## 7. The loophole audit (v0.4.4's simulator; owner's decisions)

| # | Loophole | Owner | v0.5.0 |
|---|---|---|---|
| 0 | A weapon target is a free "hold this spawn" order | fix | `WEAPON_FREE`: taking the chosen weapon ends the choice; a weapon he holds with at least a pickup's ammo is no target. Server plugin alike. |
| 1 | Speed pay paid while facing away from the enemy, and for weapon circuits | fix; fade out | `SPEED_LOS` (line of sight, not view cone); speed pay phased out 04:00–06:05 Tue, before the head |
| 2 | Damage taken cost 0.75 of damage dealt, so even trades paid both | 1.0 | `--dmg-taken-w 1.0` |
| 3 | The 8-second target lock released early when an item was truly gone: a free probe of item clocks out of sight | fix | `GONE_BELIEF` (by what he knows; simulator and plugin) |
| 4 | Re-picking an owned weapon refills up to the cap | match QL | Measured in Quake Live (private server, live duel, 100 cases): a weapon pickup always adds a full load (LG +100, RL/RG +10), cap 150/25/25; boxes +50/+5, not taken at the cap; respawns 5 s / 40 s. **The simulator already matched.** |
| 5 | No telefrag | fix | `TELEFRAG` (games only; frag to the teleporter, victim's whole stack as damage) |
| 6 | A failed jump-practice try kept its speed pay | fix | `JRUN_SPEED_BACK` (reward only) |
| 7 | Grenade/plasma/blind rocket fire free | leave | – |
| 8 | The knowledge pay and big-weapon order pay paid both seats | zero-sum | `SMALL_ZERO` |

All switches are off by default. Tests:
- **Off:** play, pay, round ends and events are identical bit for bit to the code before, in both simulator modules.
- **On:** a unit test per switch (`v050/unit/`). They found two bugs, both fixed and re-tested:
  - telefrag fired in practice runs;
  - the jump give-back also hit the long-term value.
- **WEAPON_FREE on the camping save:**
  - Blood Run: time near the LG spawn 51% → 22%, map coverage 13.5 → 25.3 cells/min.
  - Hektik: it moved to the mega instead.
  - A trained-in habit finds the next anchor, which is why v0.5.0 retrains from v0.4.2b rather than patching v0.4.4.

## 8. Aim: one setting, `!aim`, calibrated to the pros

v0.4.2b's end against itself, 8 maps × 8 games:

| Setting | LG | Rail | Rockets |
|---|---|---|---|
| Pros (demos) | 32.7% | 43.5% | 31.2% |
| Level 4, no limit (v0.4.x) | 50.8% | 58.8% | 49.2% |
| Level 3, fast-target 0.075, cap 3° | 40.0% | 43.0% | 51.4% |
| **Level 3, 0.075, cap 5° (default)** | **37.4%** | **38.2%** | **52.4%** |
| Level 3, 0.1, cap 8° | 33.3% | 35.5% | 53.6% |

- The limit moves lightning and rail together. A rail-only lever is a later item.
- Rockets read high overall because he fires them close; by distance band they match the pros.
- `!aim worse / default / better / max` scale every limit from the default. He always trains on default.

## 9. v0.5.0 (running since 2026-10-26 16:14) and v0.5.1

- **Start:** v0.4.2b's end, with v0.4.3 and v0.4.4 scrapped. v0.4.2b against v0.4.1 over 160 games: 44.4% as trained, 47.5% with the aim fix. The owner chose it for the brain trained on people's games.
- **v0.5.0, one phase:**
  - every fix above;
  - `!aim default`, the fast-target limit ramped 0 → 0.075 over 1.5 h;
  - mix 60 games / 30 pro starts / 10 jump practice, with jump focus (Campgrounds b2r, Aerowalk red armor) 4×;
  - shadow readouts;
  - item rule on, no strategy head;
  - overnight; speed pay out from 04:00.
- **v0.5.1 (Tue 07:00 → Wed noon):**
  - head attached shut and trained shut;
  - phase 2 opens it with the item rule **still on**;
  - after a play test, phase 3 fades the item rule.

  Last time the order was reversed (rule out first, then the head), which left the target choice unguided.

## 10. Monitoring from now on

- **Checks:** every 20 updates, 160 games against **v0.4.2b's end (fixed)**; every 4th against v0.4.1's end. Both seats at `!aim default`.
- **The behaviour panel** (`v050/panel_v050.py`), after every check. The save and the control are played the same way: self-play on 4 maps and against the scripted spot-holder on 2. It goes **red** on any of:
  - targets: > 2× the control's share and > +0.10;
  - camping near any item or weapon spawn: same bar;
  - map coverage: < 0.85×;
  - frags against the spot-holder: < 0.75×;
  - mega or red armor share: < 0.85×.

  A red holds or steps back the open ramp. Its proof (v0.4.1 green, v0.4.4 u221 red) is running.
- **Before any play build reaches the owner:** the server-against-simulator input check, plus a short local game at the end of each phase.

## 11. Open items

- Amsterdam frame time: median 21–22 ms of the 25 ms budget, 10–18% of frames over. The profile and optimisation come after v0.5.0 settles.
- A rail-only aim lever (the pros' rail-lightning gap).
- `!aim worse/default/better/max` in the server plugin: ships with the first deploy, after measuring `better` and `worse`.
- New human data (both players' perspectives) for the brain's people lesson, as its own step.
