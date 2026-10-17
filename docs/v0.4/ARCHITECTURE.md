# BobbyBones: model architecture (v0.3.1 now, v0.4 candidate)

*Written 2026-10-16 for cross-reference. Numbers from the running checkpoint `duel_gru_v0_3_1b` (update 50).*

## 1. Task and training

- **Environment:** a Quake Live duel simulator (`sim/`). ioquake3 movement and collision in C (`qsim.dll`), matched to
  Quake Live's measured physics (`QL_MOVE`, `QL_FLOAT`, `QL_FWD`, `QL_LAND`, `QL_JUMP`). 125 fps physics; the policy acts
  at 40 Hz, as the game server's `sv_fps` does. Ten duel maps.
- **Fairness limits on the actions:** human-like aim (reaction 100 ms, acquire 200 ms, flick speed, hand noise,
  `AIM_LEVEL=3`). Key changes are read 1 frame in 4 (`KEY_RATE=8`, about 8 a second).
- **Senses:** line-of-sight vision, sound, and enemy projectiles only as a player would see them. No privileged state
  in the inputs.
- **Algorithm:** PPO with self-play.
  - Rollouts: 30 CPU workers × 168 matches × 384 steps per update (about 3.9 M steps).
  - Hyperparameters: γ 0.999, λ 0.98, lr 1e-4, entropy coefficient 0.005 (per head), 360 minibatches.
  - Speed: about 4.1 min per update on one 16 GB GPU.
- **Opponents:**
  - A league of the last 8 snapshots, one taken every 20 min.
  - An anchor (the previous model, v0.3's end) at 25%.
  - Promotion only if he beats the anchor head to head: 160 ten-minute games, ten maps, seats swapped.
- **Episodes (share of his time):**
  - whole 10-minute games with overtime: 75%
  - mid-game starts from saved game states: 15%
  - item runs (alone, sent to an item): 5%
  - jump runs (alone, at the pros' jumps): 5%
- **Pay:** a shaped mix.
  - Damage dealt and taken (taken × 0.82).
  - Frags and deaths.
  - A stack term (health + armour advantage), flat pickup pay for mega and armours, a knowledge pay, a small hop
    pay.
  - Whole-game win pay (`WIN_PAY`) is built but off.
- **Auxiliary lessons:**
  - Imitation priors at a fading weight: the item rule for the intention head (floor 0.1), the pros' opening and hand
    tables.
  - An auxiliary prediction loss ("guess the enemy": where he is, and the landmark he is near in 3 s).

## 2. v0.3.1 network: one recurrent policy, 1.86 M weights

```
797 inputs ──► encoder 797→256→256 (tanh) ──(+)──► GRUCell(256 → 512) ──► policy logits (87 over 13 heads)
     │                                       ▲                         ├──► value (1), long values (2)
     └─► 48 tokens ─► attention (D=96) ─► door                         └──► aux heads (place, appear, fight, items, near)
 61 movement inputs ─► legs MLP 61→256→256→17 ─► replaces the movement heads' choice while the legs switch is on
```

| Part | Shape | Weights |
|---|---|---|
| Encoder | Linear 797→256, tanh, Linear 256→256, tanh | 270 K |
| Attention | 48 entity tokens of 15 kinds (self, game, around, enemy, believed, way, sound, 8 projectiles, 13 items, 8 pro places, 8 holding places, enemy stack, …) plus 1 summary token. Each kind has its own embedding to D=96 and a learned mark. Block 1: full self-attention (4 heads, FFN 96→192→96). Block 2: computed for 2 query rows only (summary, self). Output 192 → **door** (a linear layer initialised at zero), added to the encoder output. Per-token additive gates (a buffer) let new tokens be opened gradually. | 249 K |
| Memory | `GRUCell(256, 512)` stepped every frame; reset at episode ends | 1.18 M |
| Policy | Linear 512→87 | 45 K |
| Values | 512→1 (main, γ 0.999); 512→2 (item/stack pay at the fight's horizon and at two minutes ahead, γ 0.9998) | 1.5 K |
| Aux heads | 512→3, 2, 4, 2, 34 (prediction only: labels from the simulator, never inputs) | 23 K |
| Legs | MLP 61→256→256→17, the movement network merged in as a branch, trained at 0.25× the learning rate | 86 K |

**The 13 action heads (`ACTION_DIMS`):**
- forward/back 3, strafe 3, jump/crouch 3
- yaw-turn bins 23, pitch bins 15
- fire 2, weapon 10, walk 2, zoom 2, mouse lift 2
- **intention** 17 (target: nothing, mega, red armour, RL, RG, LG, two yellow armours, *the enemy* = hunt, 8 holding
  places)
- **legs switch** 2
- **way** 3 (which of three routes)

Each head is a categorical distribution and they are sampled independently.

**Timing:**
- The intention is read every 8 frames and held (`INTENT_HOLD`), and it sets the route the inputs describe.
- The legs switch is read every 4 frames. While it is on, the legs branch's choices replace his keys, turn, walk and
  zoom.
- The losses are masked to the frames where an output was actually read.

**The inputs (797):** a flat vector.
- His own state, weapons and ammo.
- Map geometry probes and the map reader's cell embedding (32).
- The enemy, only when seen or heard; otherwise a belief (last seen and heard place, decaying).
- Item timers as he knows them.
- Routes and jumps ahead on his chosen way, projectiles, the clock and score, the pros' places and holding places.
- **The enemy's stack as he believes it** (6, `EN_STACK`): a filter over his senses, built from his own hits, pickups
  heard or seen, the pain sound, the over-100 tick-down and a drift while unseen.
- Inputs are normalised with frozen running statistics.

## 3. v0.4 candidate: hands and head (about 9.1 M weights; not built)

Two recurrent cores at different rates, as in FTW (DeepMind's Quake III CTF agent):

```
 HANDS (every frame, 40 Hz) = the v0.3.1 network, copied exactly (2.1 M)
   encoder + attention ─► fast GRU (input 256 + plan 256, state 512) ─► the 13 heads (target/way also from the head)
                                       ▲ plan (256, held 8 frames)
 HEAD (every 8th frame, 5 Hz, ~7 M)    │
   [encoder mean over 8 frames 256 ; fast state 512 ; store read 256 ; tick events 32] = 1056 ─► 768
     ─► slow GRU (768 → 1024) ─► plan 1024→256
                               ─► target and way logits (added to the hands' heads; init zero)
                               ─► value 25 s and 2 min ; win chance in bands ; aux "guess the enemy"
   STORE: every 0.8 s write [slow state ; encoder mean ; events] → 128-d slot; 224 slots (3 min);
          read by 4-head attention queried by the slow state, with each slot's age as a feature
```

- **Exact start:** the plan's input columns into the fast GRU and the head's output contributions start at zero, so
  the converted network answers exactly as v0.3.1 (proved with fixed-seed replays).
- **Training:**
  - 768-frame windows (96 head ticks); both GRUs run over whole sequences by the library routine.
  - The target loss is counted on head ticks only.
  - The head learns at 0.25× the hands' rate at first.
  - Head lessons: the win chance, and the auxiliary "guess the enemy" questions moved from the hands.
  - Offline pretraining of those lessons on recorded whole games before the head is connected.
- **Smaller changes in the package:**
  - The attention part's second block takes its query from the memory of the frame before, not from the inputs alone.
  - The strategic outputs are decided in order (target → way → legs switch → weapon), each conditioned on the one
    before.
- **Open, the owner's decisions:**
  - Pay from the change in win chance per frame (`WIN_PAY`).
  - Further pay-table variants, kept as an open line of exploration. The variant with damage taken at 0.2 and no flat
    death cost is not planned (owner, 2026-10-16).
- **Serving:** a numpy forward pass in the game server plugin (`plugins/netpass.py`). The hands cost about 2.1 M weights
  every frame; the head costs 7 M every 8th frame, about 3 ms at one thread. One or two bots fit in the 25 ms frame.
- **Test order:** one part at a time, each with ten updates and a 160-game check against the control.

## 4. Lineage

| Version | What changed |
|---|---|
| v0.2 | Attention stage A (tokens, door) |
| v0.2.1 | Holding places, whole games, multiple ways |
| v0.3 | Overtime, no style draws |
| v0.3.1 | Fast learning step, legs merged into the network and learning, enemy-stack belief and the hunt intention, measured Quake Live physics. About 62% of frags against v0.3's end at update 80 |
