# v0.3.1: the mechanical side

*Written 2026-10-15 on the owner's word: "before v0.4 starts (perhaps concurrently with pretraining the strategy layer) we
should work on rocket jumping and merging the two movement networks into one ... along with better rocket/projectile
aim". v0.3.x is the hands: aim, movement, the weapons, with a little strategy. v0.4 bolts the strategy layer (the head)
onto its end ([../v0.4/CANDIDATE_v0.4.md](../v0.4/CANDIDATE_v0.4.md)). Not built; it starts from the network the owner
picks after v0.3's evaluation and play test.*

## The priorities

| # | What | Why | Done when |
|---|---|---|---|
| 0 | **The learning step rebuilt** (B-237): his memory by the library's GRU, not frame by frame in Python | every run after it about twice as fast; moved here from v0.4 because all of v0.3.1 gains from it | the same loss and gradients as today on a saved update, to rounding |
| 1 | **His legs inside the network** (B-253): the movement network as a branch of the main network, then learning from games, then seeing the enemy and his memory | two networks cannot learn from each other; his legs know nothing of the enemy and never learn from games | each step level or better against the control |
| 2 | **Rocket jumps** (B-252): the game's rocket jump measured and the simulator checked against it; the pros' and the free-for-all players' rocket jumps found in the demos; rocket jump runs with a ladder of starts and a fading nudge on the look-down and the timing; the links in each map's walking graph | he never rocket jumps; some routes, items and escapes need it | he reaches the landings in the runs, then uses them in games where they pay |
| 3 | **Better rocket and projectile aim** (B-254) | rockets are the owner's second priority; his rockets hit less and he fires far fewer than the pros | his damage per rocket and plasma shot moves toward the pros' |

## Rocket and projectile aim (item 3), the first steps

- **Measure first**, his and the pros' and the free-for-all players' (B-251): rockets a minute, direct hits, splash damage
  per rocket, shots at the enemy's feet or the floor beside him, plasma hits, by distance and by whether the enemy is in
  the air.
- **What he is told.** He has six inputs for a rocket's and a plasma ball's lead (since v14). Check they give what a
  player aims at: the floor under the enemy's predicted place for splash, the time the rocket takes, an enemy in the air.
- **His limits.** The reaction, flick and hand limits from the free-for-all games (B-251) apply to projectile aim too.
- **Not proposed without the owner**: rocket drills (the rule of 2026-10-13 is whole games and mid-game starts only) and
  any pay for a near miss (a reward for a single behaviour).

## Beside it: the head's pre-training

The strategy layer of v0.4 learns from the pros' demos offline while v0.3.1 trains (the candidate, "The pros' demos and
the head"): the demo sets rebuilt with the mended converter first (B-218, B-219). It shares the PC's one graphics card
with the trainer: it runs on the processor, in the trainer's gaps, or on rented time.

## The order

0 first (a day). 1 and the measurements of 2 and 3 next; 2's runs after 1 (they train the legs branch). Each part
alone: ten updates and a check against the control before it joins the run, as every new part since 2026-10-13.

## After v0.3 (the owner, 2026-10-15): three plans

The order: v0.3 stops at 18:00, its evaluation (an hour), the owner's play test (19:00 to 20:00); these three start after,
with the PC free of training. The public free-for-all demos (`hza`: 6,192 games, 99.5% recorded by one player, mostly
other maps) are put off (B-251).

### 1. Does the simulator rocket jump as the game does? (B-252, first)

- **The game.** A measuring plugin beside `plugins/weaponlab.py` on a private server, the test map and Blood Run: a bot
  (through `set_bot_input`) does scripted rocket jumps on a grid: look-down 45 to 90 degrees by 5; fire on the jump's
  frame, one to four frames after, or standing; with and without a forward or strafe key; on flat floor and beside a
  wall; at 100 health with no armor and with armor. About 200 jumps, every frame of the next 1.5 s recorded: place,
  speed, health, armor.
- **The simulator.** The same inputs on the same maps in `duel_env.py`. Set side by side: the rise, the distance, the
  top upward speed, the self-damage (armor's share), the landing.
- **Passes** when the rise and distance agree within 5% and the damage exactly, and the game's grid covers the pros' range
  (rise about 200 to 320, self-damage 33 to 38). A difference is fixed behind a switch (with it off the simulator is
  v0.3's, by fixed runs), as every simulator fix since v14. Also checked: his hands allow the jump and the click within
  his limits.
- About a day. Written down as a results entry.

### 2. The pros' rocket jumps as runs (B-252)

- **The links.** Per map, the take-off and landing pairs the pros used five times or more (5 to 22 a map;
  `docs/pro_rocket_jumps.json`), drawn on the maps' pictures for the owner to keep or drop (a `use` flag, as the jumps'
  lists have), each marked: to an item, a route, an escape.
- **A run** per link, as the jump runs today: he starts at the take-off with the rocket launcher and the pros' health
  (about 220 with armor) and must reach the landing; paid for arriving, the health it costs is the game's own.
- **A ladder of starts**, per link, the next when he arrives in half of the tries: in the air at the pros' moment and
  already looking down (only the shot); on the floor looking down (the jump and the shot); a normal stance (the whole).
- **A nudge that fades**: in these runs only, a lesson on his look-down and the shot's moment toward the pros' (their
  medians per link); never his aim elsewhere.
- **A share** inside today's movement practice (about 5% of his time): rocket jump runs about 2%.
- **Into games only after he can do them**: a link goes into the map's walking graph (priced: health, a rocket, the
  launcher in hand) once he arrives on it in the runs, never before (Aerowalk's red armor in v14: a rule that named what
  he could not reach cost him the map).
- **Read by**: arrivals per link; rocket jumps a game in self-play beside the pros' table; none at low health.

### 3. Drills for rocket aim (B-254)

The owner's rule since 2026-10-13 is whole games and mid-game starts only: drills come back only on his word, as a small
share that fades.

- **Measure first**, his and the pros': rockets a minute (2.1 against 10.8), direct hits, splash damage a rocket, shots at
  the feet or the floor beside the enemy, by distance and with the enemy in the air or below him. These say which drill
  is needed.
- **The drills** (the trainer's one-weapon round, `--drill-p`, exists), on the real maps, not in a box: short rounds,
  rockets only, against his league and the scripted movers (the strafer, the holder, the lobber), four kinds:
  splash at the feet at middle range; an enemy in the air (the direct hit); an enemy coming round a corner (the shot
  before he is seen: the pros' places for blind rockets are in `sim/pro_places/`); an enemy below him.
- **Pay**: the game's own, damage and frags; no pay for a near miss (a reward for one behaviour: the owner's call).
- **His inputs** checked first: the lead inputs must give the floor under the enemy's predicted place and the rocket's
  time to get there.
- **A share** of 5 to 10% of his time, fading over the run; kept only if his rockets in whole games improve (damage a
  rocket, rockets a minute, the share of frags) and the check against the control holds.
