# BobbyBones: plan

Goal: a Quake Live duel bot that **learns** to play (movement, aim, tactics) and beats people fairly:
human physics, human-like limits, knowledge only from sight and sound. Judge everything by match win
rate against a control group of plain Nightmare bots, and by live tests on a real QL server.
Findings and numbers go in [FINDINGS.md](FINDINGS.md).

## Approach

1. **Learn in a fast simulator, verify in the real game.** Quake Live runs in real time; the simulator
   (`sim/`) runs ~18,000x faster with the same physics (validated). Every learned skill gets a live check
   (`plugins/movetest.py` style) before it is trusted.
2. **Learn from people.** Pro duel demos and our own server's recordings teach what good players do
   (imitation). Then reinforcement learning improves on it.
3. **Nightmare stays the fallback** for anything not yet learned better. Promote only what beats control.

## Status

| Stage | What | Status |
|---|---|---|
| 1 | Movement simulator (Q3 Pmove + collision, QL settings, jump pads, teleporters) | done, validated |
| 1 | Movement policy (PPO): strafe jumping emerged | done (Blood Run) |
| 1 | Live transfer test, human physics on the server (8 ms split) | done: live/sim time 1.01 |
| 2 | Nav graphs built by the simulator instead of recordings | done (3 maps, ~10 s each) |
| 2 | One movement policy on Blood Run + Aerowalk + Campgrounds | done: 96% sim, live 67-100% |
| 3 | Duel simulator: RL/RG/LG, damage, knockback, 150 ms reaction, self-play | first pass training |
| 3 | Robustness options (sensor noise, late commands) | in code, not trained yet |
| 4 | Pro-demo imitation (parser, inferred actions, model) | data downloaded (380 demos) |
| 5 | Reinforcement learning in real QL (cluster) on top of 3/4 | later |
| 6 | Opponent profiles, player reports | later |

## Priorities (owner decisions, 2026-10-03 noon), in order

1. DONE (FINDINGS.md): weapons checked against the real game; RL/RG/LG damage, timing and knockback in the
   simulator now match. Still to measure: weapon switch time, armor, the other weapons.
   Original item: **Check weapons against the real game first**: controlled tests on a real server (rocket direct/splash by
   distance, self-splash for rocket jumps, rail, LG damage and range, knockback, rocket speed), same setups in
   the simulator, fix the simulator until they match. Training in the simulator is only trusted after this.
2. IN CODE, training in `duel_v2`: mouse-like aim (21 turn speeds 0.1-60 deg/frame, view inertia, small jerk cost).
   Original item: **Smooth, human-like aim that can still flick**: continuous mouse-style turning (fine control for tracking,
   large fast moves allowed for flicks), a cost on jitter. Fixes the video jitter; needed for rail/LG.
3. IN CODE, training in `duel_v2`: all health/armor/weapon/ammo items with timers, armor absorption, decay,
   limited ammo, machine-gun fallback, spawn with the full set ("full" loadout; "mg" = pick everything up).
   Pickup amounts, ammo caps, MG damage and switch time still to be measured on the real server.
   Original item: **Items in the duel simulator**: every item on the 3 maps with QL rules and timers; items must be picked up.
   Option (curriculum): spawn with the full weapon set while learning to aim, ammo/pickups still matter.
4. **Combine skills + memory**: start duel training from the movement skills, switch to the recurrent model.
5. **Nav builder: running-start jumps** (Aerowalk Red Armor reachable).
6. **Pro-demo pipeline** (owner: start with Blood Run and Aerowalk only, 226 + 148 recent demos; fetch more
   or older demos later if needed): parser + inferring the pros' keys with the simulator.
7. **Public server stays off** until a model beats the Nightmare bots reliably.
Done: duel run reviewed (FINDINGS.md); everything committed and pushed (a04f9e2).

## Next steps (in order)

### A. Simulator-built nav graphs (all maps)
Flood-fill each map with simulated movement (walk, drops, jumps, jump pads, teleports) instead of old
recordings. Removes junk nodes, works on any map at once (Aerowalk, Campgrounds have little recorded data).
Done when movement policies train on all three maps with no falls and live tests pass.

### A2. Simulator gaps found by live tests
Nav builder: add running-start jumps (and later rocket jumps) so items like Aerowalk's Red Armor become
reachable. Find why ~17% of Aerowalk trips stall only in the live game (robustness training, D, may help).

### B. Duel simulator, first pass (the big one)
Add to the simulator: rockets (projectile, splash, knockback incl. self-knockback so rocket jumps are
possible), health/armor, damage, death/respawn. Two players controlled by the same policy (self-play),
each seeing the other only with line of sight. Reward = frags. Later: rail, LG, items and respawn timers,
armor, all weapons. Watch for emergent aiming, dodging, prefire, rocket jumps, item control.

### C. More maps (generalization)
Train on Blood Run, Aerowalk, Campgrounds together, then more of QL's ~27 duel maps. Skills should stop
being memorized routes.

### D. Robustness for transfer
Small random noise in position, velocity and timing, an occasional one-frame delay, during training.

### E. More human-like control and memory
Finer turning (smoother "mouse"), a short memory of the last moment (hop timing, tracking a target).

### F. Richer goals
Arrive with speed for the next leg, arrive exactly at an item spawn, pay for health (fall damage,
rocket-jump self-damage).

### G. Pro-demo imitation
Parse the 380 demos (UberDemoTools), infer movement keys with the simulator (demos have no inputs),
train a model on fair information only, then fine-tune with B's reinforcement learning.

## Scope and priorities (owner decisions, 2026-10-03)

- Maps: Blood Run (ZTN), Aerowalk, Campgrounds only, until told otherwise.
- The simulator's maps must have every item (health incl. 5 hp bubbles, armor incl. shards, mega, weapons,
  ammo) with Quake Live's respawn timers and rules, plus correct teleporters and jump pads.
- Weapons: the "main 3" first (rockets, lightning gun, railgun), then the rest (shotgun, grenades, plasma,
  machine gun, HMG, gauntlet).
- Memory is required for a good duel bot: switch to a recurrent model (GRU) when the duel simulator gets items
  and timers (next phase), and use it from the start for pro-demo imitation.

## Getting the main 3 weapons used (not just rockets)
Self-play first drifted to rockets only (100% of frags): rail and LG need fine, steady aim and were never
rewarded early. Planned, in order of expected effect:
1. Mouse-like aim: continuous (or much finer) yaw/pitch control instead of coarse turn steps.
2. Realistic loadout: spawn with gauntlet + machine gun, pick weapons up on the map, limited ammo. Rockets
   stop being the only answer when they run out and rails are lying around.
3. Short weapon drills as a curriculum (rail at range, LG tracking a strafing target), then full duels.
4. Pro-demo imitation: pros' weapon choices are the strongest prior.
5. Report per-weapon accuracy and frag share every run; no permanent reward for "using weapon X".

## Simulator accuracy: what still needs adding or checking
- Items: all pickups, QL respawn timers, armor rules (protection share, tiers, max 200), health/armor decay
  above 100, mega rules, spawn 125 hp, starting weapons, ammo counts and limits, weapon pickup ammo.
- Weapons: all of them with QL values (refire, damage, splash, knockback, projectile speed, LG range, shotgun
  spread, bouncing grenades, plasma), weapon switch times (`pmove_WeaponRaiseTime/DropTime`), self-damage
  and rocket-jump knockback checked against recordings.
- Players: real hitbox, crouching, fall damage, spawn-point selection rules, death/respawn delay.
- Senses: sound ranges for footsteps, jumps, landings, item pickups, weapon fire (now only "moving fast within
  800 units").
- Validation: record Nightmare-vs-Nightmare duels on a real server and compare damage per shot, splash, knockback
  and item timings with the simulator, as done for movement.

## Fairness rules (owner decisions)

- Human physics only (125 fps); no bot-only frame-rate tricks.
- Human-like reaction and aim limits; never miss on purpose to hit a number; no wallhacks.
- Promote to the public server only what beats the control group's win rate.

## How to run (short)

```bash
sim\build.bat                                             # Windows: build sim\qsim.dll (MSVC)
python sim/validate.py <inputs_map.txt> data/maps/<map>.bsp   # simulator vs recorded QL frames
python sim/train_move.py --run <name> --minutes 60        # movement PPO (human physics by default)
python sim/eval_move.py --run <name>                      # trips vs Nightmare, strafe-jump detector, picture
python sim/export_policy.py --run <name> --out data/movetest/policy.npz
docker run -d --name qlmove -e QLX_PLUGINS="botctl, movetest" -e LAB_MAP=bloodrun \
  -v "<repo>/data/movetest:/tmp/practice" qlbot +set sv_master 0 +set sv_serverType 0
python sim/compare_live.py                                # live vs simulator vs Nightmare
```
Maps are extracted from the game's pak into `data/maps/` (never committed).
