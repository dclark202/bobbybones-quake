# Game-playing agents beyond AlphaStar: notes for Bobby (2026-11-13)

Research notes only. Nothing here is a decision or a design; every idea at the end is for the owner to accept or refuse.
Written after reading [PLAN.md](../PLAN.md), [HISTORY.md](../HISTORY.md), the 1.9a postmortem
([runs/1.9/1.9a/POSTMORTEM.md](../runs/1.9/1.9a/POSTMORTEM.md)) and the 2.0b postmortem
([runs/2.0/2.0b/POSTMORTEM.md](../runs/2.0/2.0b/POSTMORTEM.md)).

How to read it: each source gets what it is, its key techniques, what worked, what failed, its measured results and a
"Relevance to Bobby" paragraph that maps it onto our parts (the brain, the head, the hands, the league, the pay, the inputs) and
says where it does not fit one PC. The ranked list of ideas is at the end. The project's rules are respected throughout: pro data
measures game facts and human limits only (CLAUDE.md rule 12); a new part learns silently and is then blended in, never trained to
copy an unwanted rule or an old network (rule 13); a hand-built rule that is out stays out. Where a source's method breaks one of these,
it is said plainly, and the idea is either reshaped to fit or listed under "does not fit".

Unless marked otherwise, the facts below were read from the papers themselves on 2026-11-13 (arXiv full texts, the Quake III bot
thesis, the GT Sophy Nature paper, the F.E.A.R. GDC paper, the ioquake3 bot source). A few AlphaStar details come from the Nature
paper as known before today and are marked so.

## 0. Bobby's open problems, and which sources speak to them

| Bobby's problem (from the postmortems) | Sources that met the same problem | Section |
|---|---|---|
| A new chooser (the head) took his seats while untrained and he collapsed (1.9a: 2.5% at u90) | HIRO's relabelling, option-critic, FeUdal, behaviour priors, AlphaStar's KL kept through RL, DFP's per-action outcome prediction, Tencent's macro/micro split | 3, 9 |
| A chooser re-deciding every 0.2 s flickers (1.7a keep choice; 1.9a 4.8 changes a second) | FTW's slow prior over a fast posterior; the deliberation cost of options; FiGAR's learned repetition; the Quake III bot's long-term goal vs nearby goal split | 2, 8, 9 |
| New inputs destabilised his target (2.0b: 59 raw inputs) | Arnold: game features helped only as co-training targets, not as inputs; UNREAL; FTW's probes; OpenAI Five's surgery rules | 3, 4, 10 |
| Lightning only; self-play overvalues it because his copies are as easy to track as he is | GT Sophy: self-play alone left the agent unready for human imprecision, fixed by a mixed opponent population; AlphaStar exploiters; Gleave's adversarial policies | 6, 5, 12 |
| Pay shaping exploits (spawn camping), pay changes that change nothing (2.0a) | FTW's learned reward weights, OpenAI Five's fixed table + zero-sum, GT Sophy's collision penalties, Arnold's ammo penalty dilemma, JueWu's multi-head value | 2, 4, 6, 7, 12 |
| Space and holding ground have no price because nobody punishes a bad place (2.0b) | AlphaStar exploiters, Sophy's scripted scenario opponents (PID drivers on a chosen line), FTW's held-out-map exploit study | 5, 6, 2 |
| A noisy pay part dominating the head's pay (1.9a: items race 2-3x the judge part) | JueWu's multi-head value; OpenAI Five's team spirit and Rapier variance lesson | 4, 7 |
| Monitoring: alarms silent, a run judged late | FTW's probes and behaviour fingerprints; OpenAI Five's staleness and sample-reuse metrics | 2, 4 |

## 1. Scale for comparison

Every headline system below used far more compute than one PC. This matters when reading "it worked".

| System | Compute (as reported) | Bobby |
|---|---|---|
| FTW (Quake III CTF) | 30 agents, 1,920 arena processes, 2 billion steps an agent (about 450K five-minute games each) | one learner, one league, ~20 cores, one 16 GB card |
| OpenAI Five | 770 ± 50 PFLOPs/s-days over 10 months; batches of about 2 million frames every 2 s | |
| OpenAI Five Rerun | 150 ± 5 PFLOPs/s-days over 2 months | |
| GT Sophy | 10 PlayStations, 20 cars each; over 45,000 driving hours for the time trial alone | |
| Tencent Arena Breakout (NSRL) | 8 GPUs, 3,200 CPU cores, 6,000 clients a session | |
| CS:GO behavioural cloning | 4 Titan X GPUs; 95 hours of scraped play | |

The useful lessons for Bobby are the ones that are about structure and stability, not the ones that are paid for with scale.

## 2. DeepMind FTW: Quake III Arena Capture the Flag (Jaderberg et al., arXiv 2018 / Science 2019)

Source: https://arxiv.org/abs/1807.01281 (full text read), Science DOI 10.1126/science.aau6249.

**What it is.** Agents that play two-against-two Capture the Flag in DeepMind Lab (a modified Quake III Arena engine) from 84x84
pixels and the game's point events, on procedurally generated indoor and outdoor maps. Each player carries a railgun-like tagger.
No access to the map, other agents' policies or human data.

**Key techniques.**
- **Two-timescale recurrent core.** Two LSTMs: a fast one ticking every step and a slow one ticking every tau steps (tau evolved,
  sampled from 5 to 20). A stochastic latent z is sampled each step from a posterior made by the fast core; the slow core makes a
  prior over z. The loss includes the KL between posterior and prior, so the fast core must stay near what the slow core predicted.
  Both cores share a DNC-style external memory. The effect is a learned, soft commitment: fast reactions are allowed, but they pay
  a KL price for departing from the slow plan.
- **Learned internal reward.** The reward is a table over 13 game events (I captured, I was tagged with the flag, an opponent
  picked up our flag, ...). The table's weights are not hand-set: each agent's table is evolved by population based training (PBT)
  to maximise the win rate. The initial table was the default point values times a random factor between 0.1 and 10. Training on
  the win/loss only learned nothing; hand-tuned shaping (Quake's own point scheme) plateaued below strong humans.
- **Population based training.** 30 agents. Periodically each agent is compared with another by Elo; if its estimated win chance
  is under 70%, it copies the better agent's weights, reward table and hyperparameters, then perturbs them (±20% with 5% chance;
  tau re-sampled). 1,000 games of burn-in after each change. Evolved: learning rate, entropy cost, the KL weights, the auxiliary
  weights, the slow timescale and the reward table.
- **Matchmaking.** Co-players are sampled so the match outcome is uncertain: a normal distribution over Elo-predicted win chance,
  centred on 50% with a spread of 1/6.
- **Auxiliary losses (UNREAL).** Pixel control and reward prediction on every agent.
- **Action space.** 540 composite actions from 6 independent dimensions; 15 decisions a second with a 4-frame action repeat; only
  two yaw step sizes and one pitch step.

**What emerged.** Unsupervised clustering of two-second chunks of play (a VAE plus a 32-component mixture) found human-known
tactics: home base defence, waiting in the opponent's base for their flag to return (base camping), following a flag-carrying
teammate. Some behaviours appeared and were later dropped (teammate following peaked mid-training). Base camping appeared only
in agents with the temporal hierarchy. Linear probes on the recurrent state decoded about 200 game facts ("my flag is taken",
"teammate has the flag"); some were held by single neurons. The evolved reward weights shifted during training: early on picking
up the flag paid most; later, tagging an opponent and the penalty for an enemy capture doubled, and home defence rose with it.

**Results.** On unseen maps, a team of two FTW agents beat teams of two strong humans; a human-agent team was the only kind that
ever beat an agent-agent team (5% win probability). Two professional testers with full communication won only 25% (6.3% draws)
after 12 hours of practice on procedural maps. On a single fixed held-out map, after six hours, the testers found a winning
strategy: they studied the agents' preferred routes, drew maps and coordinated captures along routes the agents did not use.

**Fairness measurements.** Agents saw at 15 Hz with 66.7 ms delay and coarse controls; humans 60 Hz. Agents reacted faster: first
seeing an opponent to a tag attempt took 258 ms against 559 ms for humans; successful tag 233 ms against 627 ms. Agents' tagging
accuracy was 80% against 48% for humans. Discarding tags afterwards (no retraining) to bring accuracy to human levels lowered the
win rate but agents still beat humans; adding effective tag delay up to 375 ms did not change the win rate, at 448 ms it fell to
85%. Humans tagged more at long range (17% of tags above 5 map units, agents 0.5%).

**Failures and limits noted by the authors.** Keeping a population diverse is hard; PBT is greedy; the RL updates have high variance
in credit assignment. Agents could be beaten by a coordinated human strategy on a fixed map, i.e. by memorising their routes.

**Relevance to Bobby.**
- *Head flicker.* FTW's slow prior is the cleanest published answer to "a chooser that re-decides every step without a lock". Our
  head already has a slow memory. The FTW pattern would be: the head's choice distribution at each 0.2 s tick is regularised (by a
  KL) toward a prior produced by a slower part of the head that ticks every second or two. Switching is possible every tick but costs
  KL, so a near-uniform scorer stays near its prior instead of random-walking. The prior is learned, not a rule, so it respects rule
  13 and "no lock, ever". Its weight would be a live dial, opened slowly. One risk: a strong KL can freeze a bad prior; FTW evolved the
  weight by PBT, we would have to set it by checks.
- *Pay.* FTW is the strongest evidence that a reward table's weights can be set by the win rate rather than by hand. Our pay table
  plus the win-chance judge is the hand-set version of the same thing. A full PBT of 30 agents is out of reach; a cut-down version
  is discussed in the ideas (idea 9).
- *League.* FTW matched by skill (a bell over predicted win chance centred on 50%), not by "hardest first". Our PFSP leans toward
  opponents we lose to; FTW's centring is an alternative worth a look if the league gets lopsided.
- *Monitoring.* Linear probes for game facts and the behaviour fingerprint (clusters of two-second chunks, compared across training
  points and against humans) are cheap diagnostics we do not have. A probe for "enemy stack higher than mine", "mega up in N s",
  "enemy holds the rail" on the head's state would show what the head knows before it is given seats (1.9a's missing readiness
  measure). A fingerprint would have shown 1.9a's red-armour camping as a new cluster.
- *Fairness.* FTW measured its edge and showed that cutting accuracy to human levels still left a win: a model for how we report
  AIM3's effect. Its 15 Hz decisions with 4-frame repeats are coarser than our hands; it does not tell us anything new about aim.
- *The fixed-map exploit* (humans learning the agents' routes) is exactly the "people find his habits" risk on the public servers. FTW's
  answer was map variety; ours has ten fixed maps, so route predictability is a real risk to watch in play tests.
- *Does not fit:* the population of 30 and 2 billion steps an agent; pixels; the DNC memory (heavy for our learning step, which
  already spends 60% of an update stepping the GRU).

## 3. VizDoom agents and the Visual Doom AI Competitions (2016-2018)

Sources: DFP / IntelAct https://arxiv.org/abs/1611.01779; Arnold https://arxiv.org/abs/1609.05521; the competitions' paper
(Wydmuch, Kempka, Jaśkowski) https://arxiv.org/abs/1809.03470. Full texts read.

### 3.1 IntelAct: learning to act by predicting the future (Dosovitskiy and Koltun, ICLR 2017)

**What it is.** Instead of a scalar reward and a value, the agent predicts, for each possible action, how a small vector of
measurements (health, ammunition, frags) will change at several future offsets (1, 2, 4, 8, 16 and 32 steps). A goal is a weight
vector over those measurement changes; the agent picks the action whose predicted future scores best under the current goal. The
predictor is trained by plain supervised regression on the agent's own experience (the measurements that actually followed).

**What worked.** It beat DQN, A3C and DSR on the harder Doom tasks, generalised across maps and to goals not seen in training (the
goal vector can change at test time), and won the 2016 competition's Full Deathmatch track (unknown maps), well ahead of the rest.

**Relevance to Bobby.** This is the closest published match to what 1.9a's head lacked: a chooser whose lesson does not need it to
play. Each order (take the mega, chase, hold, break off...) could be scored by a head that predicts, from the brain's picture, the
change in a few measured quantities over the next 1, 2, 4, 8 s: his stack, the enemy's stack, item control, frags for and against,
and the judge's win chance. The lesson is a regression on what actually happened, so it learns on every tick, including the ticks
where the hands, not the head, chose. The choice is then the order whose predicted outcome the judge values most. Two cautions: (a)
the head only sees outcomes of orders that were actually carried out, so an order the hands never do (hold an angle) gets no data
and must stay shut until it does; (b) predicting "what followed" while the hands did their own thing is a value of the hands' own
behaviour, not a copy of an old rule, so it fits rule 13, but it is worth the owner's explicit read. Cost: small heads on the head's
memory; supervised targets from the rollout; no extra games.

### 3.2 Arnold (Lample and Chaplot, AAAI 2017)

**What it is.** A DRQN deathmatch agent split into two networks: a navigation network (explore, pick up items, find enemies) and an
action network (fight), switched by whether an enemy is visible or ammo is out. The key trick: during training only, the network is
also asked to predict "game features" (is an enemy / health pack / weapon on screen) from the engine's ground truth.

**What worked and what did not.**
- Co-training on the game features made the convolutional layers detect enemies (about 90% detection within hours) and sped
  learning a great deal. Feeding the same game features as *inputs* to the network did not help. Their help came only as
  prediction targets.
- Dropout lifted enemy detection from 70% to 90%; because detection accuracy tracked final performance, they could tune on it
  quickly instead of training full agents.
- A plain DRQN fired at will; a small ammo penalty did not stop it, a large one stopped it firing at all.
- Shaping: small rewards for pickups, small penalties for health lost and for shooting, and a reward for distance moved (to stop
  circling). Frame skip 4 was the best trade between speed and fine aim.
- Against humans in their tests: K/D 5.12 against 1.52 single player (vs bots), 1.33 against 0.49 in multiplayer.

**Relevance to Bobby.** The input lesson is directly 2.0b's lesson, reached independently: new information helps as something the
network must *predict*, not as raw columns poured into the decider. For Bobby this backs the 2.0b postmortem's step 3 (the space
readout reaches the hands through the brain's token, not as 59 raw inputs) and suggests a standing rule: a new kind of information
enters first as a brain readout (a lesson), is checked for skill, and reaches the head and hands only through the brain's token.
The "tune on a cheap proxy that tracks the final result" practice is also worth copying: the brain's readout skill is such a proxy.
The ammo penalty story is the same all-or-nothing behaviour our firing costs showed before they were removed (owner: no cost for
firing). The hard switch between navigation and action networks is a hand rule and does not fit; it is noted only as history.

### 3.3 The competitions' other winners and lessons

- **F1 (Wu and Tian, 2016 Track 1 winner):** A3C with a curriculum from weak opponents and small maps to strong opponents and big maps;
  some behaviour hard-coded (move faster when not firing). Fewest suicides.
- **Clyde (Ratcliffe, third 2016):** plain A3C rewarded for kills and items, penalised for suicides.
- **TUHO:** a navigation network rewarded for speed and a classical Haar detector for aiming.
- **Marvin (Bell, 2017 Track 1 winner):** A3C pre-trained on the authors' own recorded human games, then self-play against the
  built-in bots; separate move and aim outputs; a hand-written aim policy overrode the network when it was unsure. It did not aim
  best; it won by collecting medkits and armour. It was hit the most times and killed the fewest times.
- **Axon (third 2017):** a small human dataset, then skill drills (navigation, aiming), then play against F1.
- **The organisers' conclusion (2016 and 2017):** the bots were good at tactics (aim and shoot) but poor at strategy (defence,
  escape, navigation, exploration); on larger unknown maps they circled one place waiting for targets; no agent came close to
  human players, who exploited their weaknesses easily. Suicides with rockets stayed high for everybody.

**Relevance to Bobby.** Marvin's win is the single most striking result for us: in a deathmatch of competent aimers, the bot that
gathered health and armour won while being hit the most. That is the stack-decides-the-fight finding of 2.0b (88% of decided
fights by the stack) seen in another game. It supports keeping the items' value high in the pay and guarding the big items head to
head in every check. The human pretraining of Marvin and Axon and the hand-written aim override are out under rules 12 and 13.

## 4. OpenAI Five (Dota 2; Berner et al., 2019)

Source: https://arxiv.org/abs/1912.06680 (full text read, appendices B, C, G, N, Q).

**What it is.** Five agents (one shared network) playing 5v5 Dota 2 at a superhuman level, trained by PPO self-play for 10 months.
A single-layer 4,096-unit LSTM (about 159 million parameters) after a large observation encoder; acts every 4th frame (7.5 a second);
about 20,000 decisions a game.

**Key techniques.**
- **Surgery.** The code, the game version, the observations, the actions and even the network size changed about every two weeks.
  Instead of restarting, they transformed the trained model to a new shape that computes the same function (Net2Net-style): new
  inputs and new units with weights chosen so that the outputs are unchanged. Where exactness was impossible they did it
  approximately. Over twenty successful surgeries, plus unsuccessful attempts that were reverted. Lessons they wrote down:
  - Randomly initialised new weights let noise flow into the model, cause large gradients and destroy learned behaviour; zeroing
    the minimal set of weights avoids that, but zeroing too many creates symmetries that gradient never breaks. For the LSTM width
    doubling (2,048 to 4,096), new weights were set to small random values.
  - **The learning rate was set to 0 for the first several hours after a surgery**, so the optimiser's moment estimates could adapt
    and the rollout distribution could settle before training resumed.
  - Every stored past opponent in the league had to go through the same surgery; a surgery that does not exactly preserve behaviour
    leaves the past opponents permanently worse and spoils the league.
  - Surgery cannot easily remove parameters: a dropped "team spirit" embedding stayed as a vestigial 128-dimensional input. Setting
    those 128 learned parameters to zero later raised the win rate to about 55% against the unchanged model; the shaped reward did
    not change, so the optimiser had no signal to find it.
- **Rerun.** A second run from scratch with the final code, model and environment took 2 months and about 20% of the compute, and
  reached over 98% win rate against the final OpenAI Five. Surgery saved project time but the surgically continued model plateaued
  lower than a clean run.
- **Reward.** A hand-built table fixed at the start and barely changed (win 5, hero death −1, gold, experience, health change with a
  quartic curve, towers, ...). Three extra pieces: every reward made zero-sum by subtracting the enemies' mean; non-win rewards scaled
  down over the game by 0.6 per 10 minutes so the late game (where everything pays more) does not dominate learning; team spirit (a
  blend between own and team reward) annealed from 0.3 to 1. The authors note the shaping signals were important for training.
- **Opponents.** 80% of games against the latest self, 20% against past versions sampled by a softmax over quality scores; a past
  version that loses to the current agent has its score lowered; new snapshots enter at the top score.
- **Horizon.** The discount horizon was raised during training (from about 180 s to 360 s game time); longer horizons kept helping
  up to the longest tried.
- **Data quality.** Staleness (data from older parameters) and sample reuse both hurt badly: reusing each sample 2-3 times cost about
  a factor of two in speed, 8 times could stop learning; they targeted reuse 1 and staleness 0-1.
- **Scripted parts kept.** Item and skill purchase order, the courier, which items to hold in reserve stayed hand-scripted; the
  authors expected learned versions would be better but reached superhuman play first.
- **The Rapier lesson.** In Rerun, one item (Divine Rapier, which drops on death and can be taken by the enemy) sent agents into a
  feedback loop that lowered skill; banning it fixed the run. They suspect it raised the variance of the reward so much that the
  value function could not be learned. In the original run it had entered only after team spirit reached 1.

**Results.** Beat the world champions (Team OG) 2-0 in April 2019; won 99.4% of 7,257 public games (42 losses to 29 teams). Average
reaction to a game event 217 ms, against roughly 250 ms for a typical human visual reaction.

**Relevance to Bobby.**
- *Widening and new inputs.* Our widening already keeps answers identical with zero weights (`tools/b17b_init.py`, `add_attention.py
  --same`). OpenAI Five adds three practices we do not write down: (1) a learning-rate-zero warm-up after any shape change (a few
  updates where the rollouts run and Adam's moments adapt, but no step is taken), which could have softened 2.0b's input opening;
  (2) every league snapshot goes through the identical surgery and is checked identical; (3) a vestigial or shut part can carry a
  hidden cost, so measure "with it zeroed" now and then. Their Rerun finding also says a long chain of surgeries ends lower than a
  clean run: once the design settles (after 2.1), a clean run from scratch on the final list may be worth its cost.
- *Sample reuse.* Worth one check of our PPO settings: how many epochs and minibatches each rollout is reused for, against their
  finding that reuse above 1 slowed learning sharply at their scale. (At our small batch size the trade-off differs; it is a
  measurement, not a recommendation.)
- *Pay.* Zero-sum shaping is already ours (the damage pay is zero-sum). The Rapier story is the 1.9a items-race story: a pay part with
  high variance can stop the value from being learned. That supports measuring each pay part's noise before it reaches the head.
- *The scripted parts.* OpenAI Five kept rules where learning was not needed for the goal. For us the owner's rule is the opposite
  (rules are retired and never return), so this part does not transfer.
- *Does not fit:* scale, and the 80/20 latest-self split (our league is PFSP over anchors, which is closer to AlphaStar).

## 5. AlphaStar (StarCraft II) in brief, and what we have not used

Sources: DeepMind blog https://deepmind.google/discover/blog/alphastar-grandmaster-level-in-starcraft-ii-using-multi-agent-reinforcement-learning/
(read); Nature 2019, DOI 10.1038/s41586-019-1724-z (details marked * are from the paper as known, not re-read today); AlphaStar
Unplugged https://arxiv.org/abs/2308.03526 (skimmed).

**What we already use:** the league of snapshots and anchors, PFSP-style matchmaking*, the control in every check, handing a choice
to a learner on its own states. The blog confirms: training began from imitation of human games (the starting policy beat 84% of
active players), a latent conditioned the policy on human opening statistics, the agent was capped at 22 agent actions per 5 s and
used a camera interface, it reached Grandmaster for all three races (above 99.8% of ranked players), and plain self-play and even
fictitious self-play failed through forgetting and cycles.

**What we have not used:**
- **Exploiters.** *Main exploiters train only against the current main agents and are reset to the supervised start when they
  succeed; league exploiters train against the whole league to find global weaknesses. Their job is to make the main agent's
  weaknesses expensive. We have frozen snapshots and anchors but no learner whose pay is "beat the current Bobby". The 2.0b postmortem's
  holder seat is a hand-built stand-in for one.
- **A KL to a prior kept through RL.** *AlphaStar kept a KL penalty toward its supervised (human) policy throughout RL, not only at the
  start. The HISTORY row on 1.7a already names this. Under rule 12 the prior cannot be human; under rule 13 it cannot be an old rule.
  What remains possible is a KL toward a *learned* prior of the agent itself (FTW's slow prior, behaviour priors in section 9).
- **The statistic z.** *A conditioning vector (build order and unit counts) let one network play many strategies and kept diversity.
  Taken from human games, so out under rule 12 as a target; a self-generated z (e.g. a code for the agent's own style, sampled per
  game) is a different, permitted idea, but nothing here shows it works without the human data.
- **UPGO and V-trace*:** off-policy corrections suited to a large asynchronous system; PPO on fresh data is fine at our size.

**Relevance to Bobby.** The exploiter is the one AlphaStar part that most directly answers 2.0b ("his world has no one in it who
punishes a bad place") and the lightning question (his copies are easy to track). On one PC a second learner halves the main
learner's time. A cheaper form: a learned exploiter trained in short bursts from Bobby's current save, paid only to beat him, frozen
into the league when it wins, and reset. That is AlphaStar's main exploiter at small scale.

## 6. Sony GT Sophy (Gran Turismo; Wurman et al., Nature 2022)

Source: Nature 602, 223-228, https://www.nature.com/articles/s41586-021-04357-7 (full text via the authors' copy
https://www.cs.utexas.edu/~pstone/Papers/bib2html-links/nature22.pdf, read).

**What it is.** A racing agent trained by a quantile-regression variant of soft actor-critic (QR-SAC) on PlayStations, racing
four of the best human drivers in teams of four.

**Key techniques.**
- **Reward.** A weighted sum of: course progress (the main term), off-course penalty, wall penalty, tyre-slip penalty, a passing
  bonus, an any-collision penalty, a rear-end penalty (scaled by the speed difference) and an unsporting-collision penalty, weighted
  per track. Without the off-course penalty, lap times got slower and laps within bounds fell from 98% to 90%. With fewer collision
  penalties the agent became much more aggressive; stewards and test drivers judged it unsporting. They chose a conservative
  penalty for any collision regardless of fault, plus extra for collisions likely to be penalised.
- **Why self-play alone was not enough.** Racing only against copies of itself, the agent did not expect a human to brake a fraction
  earlier; a small bump at the wrong moment then caused a penalty. They trained against a mixed population: curated agents from earlier
  experiments and the game's slower built-in AI. Training only against the built-in AI made it too aggressive; training against
  aggressive opponents made it lose its competitive edge.
- **Mixed-scenario training.** With a retired professional driver, they picked a small number of race situations likely to decide a
  race on each track (slipstream passes, grid starts, specific corners) and trained on noisy variations of them, with simple PID
  controllers driving opponents along chosen lines (e.g. always on the left) so the agent met the situations it otherwise rarely saw.
  All scenarios were present all the time (no sequential curriculum).
- **Stratified sampling.** Even with balanced scenarios, random sampling from the replay buffer made skills be unlearned between epochs.
  Separate buffers per scenario with fixed proportions in every mini-batch stabilised skill retention.
- **Policy selection.** Performance kept wandering after convergence; they selected the policy to race from many saves by tests.

**Results.** The human team won the first event (2 July 2021) 86 to 70. After improving the training (bigger network, better opponent
population, some feature and reward changes, a 7-step return instead of 5) GT Sophy won the rematch on 21 October 2021 by 104 to 52.
Inference took 23-30 ms; retrained with 100, 200 and 250 ms of artificial perception delay it still lapped faster than the best human.

**Relevance to Bobby.**
- *The lightning.* Sophy's "self-play leaves it unready for human imprecision" is our 2026-11-13 lightning finding from the other side:
  his copies move like him, so the lightning tracks them easily, and self-play overvalues it against a person who dodges. Sophy's fix
  was opponent variety chosen to cover what people do. For Bobby that means league seats that move in ways people move (measured human
  limits and movement statistics from the pro demos are allowed under rule 12 as facts about human movement, if they are used for an
  *opponent's* behaviour and never as a target for Bobby's). Whether a measured-human-movement opponent is a "hand-built opponent" the
  owner accepts is his call; a trained exploiter (section 5) is the learned alternative.
- *Scenarios.* We already have mid-game starts sampled from real moments (v0.4.4). Sophy adds two things: pick the pivotal moments
  deliberately (a mega contest with both players arriving, a fight entered outstacked, a rail holder on a corridor) and keep each
  scenario's share fixed in every training batch so skills are not unlearned. The pivotal moments can be picked from measured game
  facts (where and when the pros' games are decided), which is measurement, not a behaviour target.
- *Opponent mix size.* Their e/f ablations (only built-in AI → too aggressive; only aggressive opponents → lost its edge) are a
  warning for any holder or exploiter seat: its share must be set and checked, not maximised.
- *Selecting the save.* Their per-save selection by tests matches our checks; it supports judging the end of a run by its best save,
  not its last (as 1.7a's u90 was kept).
- *Reaction-time retraining.* They retrained with human-size delays rather than adding delay at play time. Our AIM3 and human limits
  are in training from the start; this confirms that is the right place.

## 7. Shooter bots in industry and applied research

### 7.1 Microsoft Research and Ninja Theory (Bleeding Edge)

Sources: Navigation Turing Test https://arxiv.org/abs/2105.09637 (read); WHAM / Muse, Nature 638 (2025),
https://www.microsoft.com/en-us/research/blog/introducing-muse-our-first-generative-ai-model-designed-for-ga (search summary only).

- **Navigation Turing Test.** People judged whether recorded navigation in Bleeding Edge was a human's or an agent's; the team then
  trained classifiers to predict those judgements (the automated test). The best classifiers told humans from agents well, but did not
  track finer judgements of how human an agent was becoming. The authors explicitly advise against using such a classifier as a reward:
  agents exploit static classifiers.
- **WHAM (Muse).** A generative model of the game's frames and players' actions, trained on about seven years of recorded Bleeding Edge
  play, used for gameplay ideation, not for playing.

**Relevance.** Human-likeness should be measured, never paid. If the owner wants a "does he look like a person" measure for play tests,
a judged test on recorded clips is the trustworthy form; a learned judge may be used as a readout beside the checks, never as a pay or
a pass mark. Imitation of human play (their "agents that play like humans" work) is out under rule 12.

### 7.2 EA SEED (Battlefield 1; automated testing)

Sources: https://www.ea.com/seed/news/self-learning-agents-play-bf1 (read: a short announcement; detail in a video);
https://www.ea.com/en-gb/news/teaching-ai-agents-battlefield-1 and press coverage (search summaries); "Augmenting automated game testing
with deep RL" https://arxiv.org/abs/2103.15819 (read).

- Agents trained with imitation of about 30 minutes of human play followed by RL; press reports put imitation at roughly 2% of what
  they learned and total experience around 300 days of play. The team described them as capable but clearly weaker than humans and
  poor at planning ahead.
- The testing paper uses RL agents to find exploits and stuck spots in FPS maps (e.g. a wall without collision), and to measure map
  difficulty.

**Relevance.** The testing use is directly useful: an RL agent paid to reach places or to survive finds simulator holes. For Bobby, the
simulator-vs-game fidelity work could use short "explorer" runs to find spots where the simulator lets him do what the game does not.

### 7.3 Ubisoft La Forge: deep RL for navigation in AAA games (Alonso et al., 2020)

Source: https://arxiv.org/abs/2011.04764 (read).

- Point-to-point navigation with jump pads, double jumps, jetpacks on maps 300 m across; soft actor-critic with an LSTM; inputs: relative
  goal, speed, a local 3D occupancy grid from box casts, a depth map from ray casts. A curriculum widened the spawn radius until it
  covered the map. Over 90% success on all scenarios, where a navigation mesh cannot express such movement.

**Relevance.** Supports the 1.8 movement plan (rocket jumps, trick jumps) being learnable by RL with a goal and a widening curriculum,
rather than by a navigation graph. The spawn-radius curriculum is a cheap pattern for teaching a single jump (start near its take-off
point, widen).

### 7.4 CS:GO deathmatch by large-scale behavioural cloning (Pearce and Zhu, 2021)

Source: https://arxiv.org/abs/2104.04258 (read).

- A pixel-input agent cloned from 95 hours (5.5 million frames) of scraped public-server play, then fine-tuned on clean expert
  demonstrations. It reached the level of the game's medium bot, about a casual player. Weak navigation in areas people rarely visit,
  no audio, rarely reacted to damage indicators. Chosen because the game cannot be simulated cheaply at scale.

**Relevance.** Shows what imitation alone buys: a casual human level with a human style. Out for Bobby under rule 12, and unnecessary
because our simulator is fast. Its observation that missing audio limited the agent supports our sound inputs.

### 7.5 Unity ML-Agents DodgeBall

Source: https://blog.unity.com/technology/ml-agents-plays-dodgeball (search summary).

- Team shooter (Elimination, Capture the Flag); MA-POCA with self-play against older snapshots; Elo watched for its trend. In CTF the
  agents first learned to hit each other and only later to take and return the flag; coordination around 80 million steps.

**Relevance.** The same order of learning we see (fighting first, objectives later) in a small public environment. Nothing new to take.

### 7.6 Tencent: Arena Breakout FPS (NSRL, 2024)

Source: https://arxiv.org/abs/2410.04936 (read in part).

- A deployed FPS opponent on a large map: a navigation mesh for global movement, rule-based shooting for control, and an RL model that
  decides when to switch the navigation mesh on; rewards shaped toward human-like behaviour.

**Relevance.** An industry design that keeps rules for what must be controlled and learns the switching. Out for Bobby (rules stay out);
noted because it shows the commercial pressure is toward controllability, the opposite of our "genuine learned behaviour" goal.

### 7.7 Tencent JueWu / Honor of Kings (MOBA) and other macro/micro systems

Sources: "Mastering complex control in MOBA games" https://arxiv.org/abs/1912.09729; "Towards playing full MOBA games"
https://arxiv.org/abs/2011.12692; "Hierarchical macro strategy model" https://arxiv.org/abs/1812.07887; vivo's "Hierarchical RL for
multi-agent MOBA" https://arxiv.org/abs/1901.08004; TStarBots (StarCraft II) https://arxiv.org/abs/1809.07193. Read in part.

- **Tencent Solo (1v1):** an actor-critic with control-dependency decoupling (the parts of an action, e.g. which skill and which target,
  are separate output heads trained as independent labels), action masks from game rules for legality, a target-attention head for
  choosing a unit, an LSTM for skill combos, and **dual-clip PPO** (an extra clip bound on the ratio when the advantage is negative, to
  stop huge updates from stale, very off-policy samples). Beat top professionals in 1v1.
- **Full 5v5 (JueWu):** curriculum self-play (fixed lineups first, then multi-teacher distillation into one student, then random picks);
  **multi-head value:** the reward is split into five groups (farming, kills-deaths-assists, damage, pushing, win/loss) with a value head
  each, the total value being their weighted sum, so each head's target is less noisy. 40 wins of 42 against professionals.
- **Hierarchical Macro Strategy (HMS):** a "phase" head (which stage of the game) as an auxiliary task and an "attention" head that predicts
  the region of the map to go to; its output is passed to the micro model as an embedding. Trained by supervised learning on human
  replays. 48% against top-1% human teams.
- **vivo HRL MOBA:** macro by imitation, micro by RL.
- **TStarBot1 / 2:** RL over a set of hand-designed macro actions (each a scripted sequence); TStarBot2 was hand-coded rules over a
  hierarchy. Both beat the built-in AI up to its cheating levels.

**How they trained a high level without breaking the low level.** In every published MOBA and StarCraft system read here, the high level
was either (a) trained by supervised learning on human data, (b) a set of scripted macro actions under a learned selector, or (c) not
separated at all (one network with factorised output heads, trained jointly by RL from the start). None opened an untrained learned high
level on top of a trained low level and let it take over by the clock. That is what 1.9a did.

**Relevance to Bobby.**
- *Multi-head value* fits 1.9a's finding that the items race in the head's pay was two to three times the judge's part and noisy: a value
  head per pay part (items, damage, frags, the judge) gives a cleaner baseline for each, lets us see each part's explained variance, and
  lets a pay weight change live without the whole value relearning (2.0a changed the damage pay and saw nothing but lost points). Cost:
  a few linear heads on the existing value trunk.
- *Factorised heads with masks* is what our head and hands already do (order kind, pointer, weapon). Their dual-clip is a cheap guard
  worth knowing if a new head's ratios ever explode.
- *Macro supervised on human replays* is out under rule 12. The architecture idea (a "where to go" head whose output is an embedding for
  the low level, plus a "phase" auxiliary) is close to our head and order; the training signal must come from our own pay and our own
  outcomes.
- *Distillation from teachers* (CSPL) is a copy lesson; under rule 13 it is out when the teachers are old rules or old networks. Distilling
  specialists trained by RL into one student is a different case and would need the owner's ruling.

### 7.8 Riot / Valve / Valorant, NetEase, FPS surveys, VPT / MineRL

- No public research on Riot (Valorant) or Valve (CS) learned bots was found beyond the academic CS:GO cloning work above. The Valorant
  and CS bots that ship are scripted. NetEase has published game-AI work (mostly MOBA, racing, card games); nothing found that is specific
  to a duel FPS and adds to the above.
- VPT (Minecraft, OpenAI 2022) learns from 70,000 hours of unlabelled video via an inverse dynamics model and then fine-tunes by RL with a
  KL to the pretrained policy. Imitation-based, out under rule 12; its "KL to the pretrained policy during RL fine-tuning" is the same
  device as AlphaStar's and only usable with a non-human prior.

## 8. Classic hand-built bots

### 8.1 The Quake III Arena bot (J.M.P. van Waveren, "The Quake III Arena Bot", MSc thesis, TU Delft 2001)

Sources: the thesis http://fd.fabiensanglard.net/quake3/The-Quake-III-Arena-Bot.pdf (read: sections 8, 9, 11, 15); the bot's goal code
in ioquake3 https://github.com/ioquake/ioq3/blob/main/code/botlib/be_ai_goal.c (read); Fabien Sanglard's review
https://fabiensanglard.net/quake3/a.i.php.

**Structure.**
- **Area Awareness System (AAS):** the map compiled into convex areas with "reachabilities" (walk, jump, jump pad, rocket jump, teleport,
  ladder, swim) and travel times; a hierarchical router caches, per goal area, the travel time from every area and the first reachability
  to take. Fully automatic from the map; no hand-placed waypoints. The first commercial bot to do so.
- **The AI network** (a state machine): Respawn, Stand, Seek Long Term Goal, Seek Nearby Goal, Seek Activate Entity, Battle Fight,
  Battle Chase, Battle Retreat, Battle Nearby Goal. Each think frame the bot moves through the network until it finds the one node that
  fits the situation; each node is if-then rules.
- **Goals.** A long-term goal (an item to get, the enemy to fight or chase, a place to camp, retreating to an item away from the enemy)
  plus nearby goals picked up on the way when they cost little detour. When the enemy goes out of sight, the bot runs to his last seen
  position.
- **Item choice.** Each item has a fuzzy weight from a tree of conditions on the bot's inventory (health, armour, weapons, ammunition).
  In code, an item's score is its weight divided by the travel time to it; the best score is the long-term goal. A nearby goal must be
  within a maximum travel time and no farther from the long-term goal than the bot already is.
- **Item timing.** The bot does not track when the enemy took an item. When it chooses an item as a goal, the item goes on an "avoid"
  list for that item's respawn time (default 30 s, at least 10 s), and an item whose avoid time will not have run out by the arrival
  time is skipped. Dropped items are kept 30 s.
- **Weapon choice.** Fuzzy weights per weapon by distance and ammunition (the thesis's own example: the lightning gun is wanted only
  within its 768-unit range, more with more ammunition).
- **Characters.** Each bot has a character file: reaction time, aim accuracy and aim skill per weapon (with explicit levels: affected by
  enemy movement, linear lead, exact lead, splash at nearby geometry, shooting where the enemy is predicted when unseen), maximum view
  change a second, attack skill (from standing still to circle-strafing with random direction changes), aggression, self-preservation,
  camper, alertness, fire throttle, and the fuzzy item and weapon weights. The thesis stresses that what players perceive matters more
  than what the bot really does.
- **Tuning by evolution.** The thesis describes balancing the fuzzy weights by a genetic process: bots with the same logic fight duels,
  are ranked by wins, parents are averaged into a child and mutated, repeat.

**What it did well that learned bots struggle with.** Long-horizon goal choice at low cost: an explicit long-term goal (one item or the
enemy) that persists, with small detours handled underneath; routes by computed travel time on every map without training; item
availability by respawn timers; a single, readable place to change a preference. It does not flicker, because the long-term goal is only
re-chosen when it is reached, lost or overridden by battle.

**What it did badly.** No model of the opponent's item timing (it times its own pickups only), fixed preferences that do not adapt to the
opponent, strategy limited to what the rules name.

**Relevance to Bobby.**
- The long-term goal / nearby goal split is a useful *shape* for our head and hands: the head holds one order (the long-term goal) and the
  hands take small detours (nearby goals) on their own. 1.9a's head changed its order on 95% of ticks; the Q3 bot shows that a strategy
  layer only needs to re-choose when something changes. Taken as a shape it is not a rule (the order is still learned and the re-choice is
  still the head's own); a fixed re-choice schedule would be a lock and is out.
- "Score = want / travel time" is a sensible inductive bias for a learned item scorer: the brain can predict the travel time (the ways
  exist), and the head learns the want. It is a factorisation inside a learned head, not a rule; whether it counts as "hand-built" is the
  owner's call.
- Item timing: a learned bot can do better than the Q3 bot by also timing the *enemy's* pickups (our brain's item timers already do this).
- The genetic tuning of preference weights by duel wins is the same idea as FTW's PBT of reward weights, 17 years earlier, at tiny cost:
  evolve a handful of numbers by win rate.
- Its character parameters (reaction time, view change limit, aim skill levels) are an early, explicit form of our AIM3: limits set as
  parameters, not tuned to a hit rate.

### 8.2 Reaper bot (Quake, 1996) and the Unreal Tournament bots (Steven Polge)

Sources: the Reaper readme https://discmaster.textfiles.com/view/11997/IMG%2051%20Vol%205-8.iso/Goodies/More%20For%20Your%20Games/Quake/MODs/Reaper%20Bots/Reaprb80.txt
and Polge's UT AI notes https://www.unrealarchive.org/unreal-tournament/documents/reference/unrealed/unreal-tournament-ai/index.html (search
summaries).

- Reaper: roaming on bot paths it placed itself while playing; combat and local goals by heuristics with fuzzy logic. Remembered for
  play that felt human.
- UT bots: hand-placed waypoint networks (designers place path nodes; automatic generators were judged worse by the community), with
  per-bot skill and personality settings.

**Relevance.** Historical. The point that carries: early bots felt human mostly through movement and imperfect, personality-shaped
choices, not through strong strategy.

### 8.3 F.E.A.R.: goal-oriented action planning (Orkin, GDC 2006)

Source: https://www.gamedevs.org/uploads/three-states-plan-ai-of-fear.pdf (read).

- Three states (go to, animate, use a smart object) under a STRIPS-like planner: each character has goals and actions with preconditions,
  effects and costs; the planner chains actions to reach the active goal and re-plans when a step fails. Squad behaviour was simple; the
  appearance of flanking often came from individual re-planning around obstacles.

**Relevance.** Two lessons: the illusion of tactics often comes from simple local re-planning, and a cost per action is how hand-built
planners stop flicker. Neither is a rule we would add. GOAP's "goal persists, plan re-made" split again matches the long-term goal idea.

### 8.4 Behaviour trees and utility AI

- Behaviour trees (popularised by Halo 2, Isla GDC 2005, cited by Orkin) give priority-ordered, interruptible behaviours; utility AI scores
  each option by curves over the situation and picks the best (the Q3 bot's fuzzy weights are an early form).
- Both solve the "commitment" problem with hand-set hysteresis: a running behaviour gets a bonus, or a new option must beat the current one
  by a margin. For a learned head, the learned equivalents are an option's termination function and a deliberation cost (section 9).

## 9. Hierarchical RL: training a strategy layer without breaking the layer below

Sources (full texts read in part): FeUdal Networks https://arxiv.org/abs/1703.01161; Option-Critic https://arxiv.org/abs/1609.05140;
Options with a deliberation cost https://arxiv.org/abs/1709.04571; FiGAR (learned action repetition) https://arxiv.org/abs/1702.06054;
HIRO https://arxiv.org/abs/1805.08296; Behaviour priors https://arxiv.org/abs/2010.14274; Kickstarting https://arxiv.org/abs/1803.03835;
plus the MOBA and StarCraft systems of section 7.7.

### 9.1 The methods

- **FeUdal Networks (Vezhnevets et al., 2017).** A Manager at a slow rate sets a direction in a learned latent space; a Worker acts every
  step and is paid an intrinsic reward for moving its state in that direction. No gradient flows from Worker to Manager; the Manager learns
  from the environment's reward alone, with a "transition policy gradient" that treats its goals as directions of state change. The Manager
  uses a dilated LSTM to remember over long spans. Ablations showed the transition gradient and directional goals mattered most.
- **Option-Critic (Bacon et al., 2017).** Learns, end to end, the options' internal policies, their *termination functions* and the policy
  over options. Known failure: options collapse to one step (terminate every step) or one option takes over, because nothing rewards
  holding an option.
- **Deliberation cost (Harb et al., 2017).** Adds a cost each time an option terminates (a margin that switching must beat), derived from
  bounded rationality. Options became longer and more interpretable and Atari scores rose. This is the learned form of "a running
  behaviour gets a bonus".
- **FiGAR (Sharma et al., 2017).** The policy outputs an action *and* how many steps to repeat it; repetition becomes a learned choice.
- **HIRO (Nachum et al., 2018).** A high level sets goals every c steps, a low level is paid to reach them. Because the low level keeps
  changing, an old high-level choice no longer means what it did. HIRO relabels each stored high-level choice with the goal that best
  explains what the low level actually did, so past data stays valid for training the high level.
- **Behaviour priors (Tirumala et al., 2020; also Distral).** The policy is regularised by a KL toward a learned "default" policy that sees
  less information (e.g. not the task). The prior is learned jointly; it captures common behaviour and makes the KL a soft, learned anchor.
- **Kickstarting (Schmitt et al., 2018).** A student is trained with an extra distillation loss toward a teacher, its weight annealed (by
  PBT); students can surpass teachers. A copy lesson, so out under rule 13 when the teacher is an old rule or old network.
- **MOBA / StarCraft practice (7.7).** High levels trained by imitation, or scripted macro actions with a learned selector, or one joint
  network trained by RL from the start.

### 9.2 How each guards against "the high level takes over untrained" (1.9a)

| Guard | Who | Fits Bobby's rules? |
|---|---|---|
| Train the high level by imitation first | HMS, vivo, AlphaStar, Marvin | No (rule 12 for human data; rule 13 for old rules) |
| Scripted macro actions, learned selector | TStarBot1 | No (hand-built rules out) |
| One network, all heads trained together from the start | Tencent Solo, OpenAI Five | Only for a fresh start; not for adding a head to a trained Bobby |
| The high level learns from the environment's return only, the low level from an intrinsic goal reward | FeUdal | Partly: the head paid by the judge only is already the owner's rule; the hands are paid by the table |
| Relabel the high level's past choices with what the low level actually did | HIRO | Yes, as a *value* lesson on shadow ticks (see idea 1); it is not imitation of an old rule, but the owner should rule on it |
| Predict each high-level choice's outcome from own experience, choose by the prediction | DFP (IntelAct) | Yes; a lesson that needs no played seats |
| A KL toward a learned prior | FTW, behaviour priors | Yes if the prior is learned by the head itself, not an old network |
| A cost on switching, learned termination | Deliberation cost, option-critic | Needs the owner: a deliberation cost is a hand-set margin in the head's objective, though not a lock |
| Learned repetition length | FiGAR | Yes; a "keep for k ticks" output is a learned commitment, not the lock |
| Open on a readiness measure, not the clock | (none published as such; our 1.9a postmortem) | Yes, with rule 6: the ramp reports the mark, the owner opens |

**Relevance to Bobby.** The published systems avoided our 1.9a failure mostly by means our rules exclude (imitation, scripts, joint training
from scratch). The ones that remain compatible are: outcome prediction per order on every tick (DFP, HIRO's relabelling read as a value
lesson), a learned prior with a KL (FTW, behaviour priors), learned commitment (FiGAR, option termination), and the readiness gate. These
are ideas 1 and 2 below.

## 10. Opponent modelling and belief

Sources: UNREAL https://arxiv.org/abs/1611.05397; FTW probes (section 2); Arnold (section 3.2); DFP (section 3.1); Machine Theory of
Mind https://arxiv.org/abs/1802.07740. Read in part.

- **UNREAL (Jaderberg et al., 2016).** A3C plus auxiliary tasks: pixel control (learn to change parts of the image), reward prediction
  (predict the next reward from a short history, sampled half from rewarding frames), value replay. About 10x faster learning on 3D
  Labyrinth tasks, 87% of expert human there, 880% of expert human on Atari. Auxiliary tasks shape the shared representation without
  biasing the policy.
- **FTW's probes.** Linear readouts of the recurrent state decoded past, present and near-future game facts; FTW's representation encoded
  the past especially well; knowledge appeared in a fixed order (own base, enemy base, flag pick-up, then tagging and the teammate).
- **Arnold.** Ground-truth game features as training-only prediction targets made the network see enemies; as inputs they did nothing.
- **Machine Theory of Mind (Rabinowitz et al., 2018).** A "character net" summarises past episodes of a particular agent into an
  embedding; a "mental state net" summarises the current episode; a prediction net forecasts that agent's next actions, goals and what it
  will believe. It passed a false-belief test in gridworlds.

**Relevance to Bobby.**
- Our brain is already a belief network trained on human-fair senses, with readouts (the space readout of 2.0b reached skill 0.66-0.77).
  The literature says this is the right place for new information, and that its readouts should be checked like FTW's probes.
- A reward-prediction auxiliary (predict the next pay part from a short history) is cheap and could help the head's value learn the pay's
  structure, which 1.9a's head did not.
- ToMnet's character net is the shape of the owner's "adapt to this opponent, remember past games" idea (parked until 2.1 works, per
  memory). Nothing to do now; when it comes, a per-opponent embedding from past games fed to the brain is the published form.
- The brain predicting the enemy's *next order* (what he is about to do: go for the mega, hold, chase) is a ToM-style readout that the head
  could use; it is measured on our own league games, not on pros.

## 11. Fairness and human-likeness

| Source | Limit or measure | Finding |
|---|---|---|
| FTW | 15 Hz, 66.7 ms observation delay, coarse turning; measured reaction and accuracy | Agents 258 ms to a tag attempt vs humans 559; accuracy 80 vs 48%; cutting accuracy to human level still won; tag delay up to 375 ms did not matter |
| OpenAI Five | measured reaction | 217 ms average to a game event |
| AlphaStar | 22 agent actions per 5 s, camera interface | Grandmaster with the caps |
| GT Sophy | retrained with 100, 200, 250 ms perception delay | still faster than the best human |
| Q3 bot | per-character reaction time, view change limit, aim skill levels | limits as parameters, perceived behaviour first |
| BotPrize 2012 (UT2004) | judges tag players as human or bot in play | MirrorBot 52.2% and UT^2 51.9% judged human; the human players averaged 40% |
| UT^2 (Schrum, Miikkulainen) | neuroevolution under human-like constraints (aim worse at speed and range), replay of human movement when stuck, grudges | "optimised within human limitations" |
| NTT (Microsoft) | human judgement of navigation clips, learned judge | a learned judge must not be a reward (it gets exploited) |

Sources: BotPrize poster https://people.southwestern.edu/~schrum2/AAAI-BotPrizePoster.pdf and UT Austin news
https://news.utexas.edu/2012/09/26/artificially-intelligent-game-bots-pass-the-turing-test-on-turings-centenary/ (read via summary).

**Relevance to Bobby.** Our approach (limits measured from the pros' own parameters, trained in from the start, never missing on purpose)
matches the best practice found: FTW and Sophy both show that limits applied in training, not bolted on at play, are what keep a fair agent
strong. UT^2 is the closest precedent to AIM3: aim error growing with speed and range as a constraint, then optimise inside it. Two notes:
(1) the BotPrize result shows people are poor judges of humanness (humans scored 40%), so a "looks human" test needs many judgements and a
human baseline; (2) a human-likeness score is a readout only, never a pay or a pass mark (NTT's warning agrees with rule 12).

## 12. Reward hacking, curriculum and self-play pathologies

Sources: Bansal et al. "Emergent complexity via multi-agent competition" https://arxiv.org/abs/1710.03748; Baker et al. "Emergent tool
use" https://arxiv.org/abs/1909.07528; Czarnecki et al. "Real world games look like spinning tops" https://arxiv.org/abs/2004.09468;
Gleave et al. "Adversarial policies" https://arxiv.org/abs/1905.10615; PBT https://arxiv.org/abs/1711.09846; plus OpenAI Five, FTW,
GT Sophy and Arnold above.

- **Dense-to-sparse annealing (Bansal).** A dense "exploration" reward (move, stand, touch) annealed linearly to zero in favour of the
  sparse competition reward, so most training is on the real goal. Opponents sampled uniformly from a window of past snapshots worked
  better than always the latest. Policies overfit to their opponent; training against an ensemble helped.
- **Auto-curricula (hide and seek).** Six phases of strategy emerged, each a response to the other side's last; agents also found physics
  exploits (box surfing, launching through walls). Self-play finds whatever the simulator allows.
- **Spinning tops.** Real games have a transitive axis (strength) and, at each strength, a set of strategies that beat each other in cycles.
  The cycles are widest in the middle of the strength range. Climbing through that middle needs a population large enough to cover the
  cycles; a single self-play line can get stuck going around one.
- **Adversarial policies (Gleave).** In simulated humanoid games, an adversary trained against a fixed self-play victim won 86% (a normal
  opponent 47%) by behaving strangely (collapsing on the ground), which pushed the victim's observations off-distribution. A victim that
  could not see the adversary was immune. Fine-tuning the victim against it fixed that adversary, but a new one could be found.
- **Reward lessons from the systems above.** Arnold's ammo penalty: too small did nothing, too big stopped firing. OpenAI Five: a fixed,
  hand-made table worked, but one high-variance item (Rapier) wrecked the value; a zero vector the shaped reward could not see was worth 5
  points of win rate. FTW: hand shaping plateaued below the learned weights; the weights that win shift during training. GT Sophy: each
  collision penalty removed made it more aggressive; opponents' mix decided aggression.

**Relevance to Bobby.**
- Spawn camping (v0.4.3), the red-armour camping of 1.9a, the lightning equilibrium: each is self-play finding what the pay and simulator
  allow. Gleave and hide-and-seek say this never stops; the remedy is a league that contains its own punishers (exploiters), not more pay
  terms.
- Spinning tops supports keeping the league diverse at Bobby's own level: weapon styles (lightning, rail holder, rocket spammer) are the
  kind of cycle that a single line of self-play can lock into one side of. The parked "weapon leaners" (1.5) are the cheap form.
- Gleave's "masked victim was immune" is an argument for the brain's role: the hands react to the brain's belief token, not to raw
  enemy-driven inputs, which also limits how far an odd opponent can push them off-distribution.
- Dense-to-sparse annealing is what the owner's design already does in spirit (the pay table as baseline, the judge as correction, rules
  faded). Bansal's window of past opponents is close to our snapshots.

## 13. Ideas worth considering for Bobby (ranked)

Ranked by how directly each attacks a current blocker (the 2.1 strategy layer, the lightning, the items) times how cheap it is on one PC.
Each is a proposal for the owner; none is started. "Cost" is in the project's own terms (extra network parts, extra games, extra
learners), not in hours.

### 1. Teach the head on every tick by predicting each order's outcome, and open its seats on a readiness mark
- **Source:** DFP / IntelAct (per-action prediction of future measurements), HIRO (relabel past high-level choices with what the low level
  did), JueWu's multi-head value, our own 1.9a postmortem.
- **What:** a head part that, on every 0.2 s tick (played or shadow), predicts for each offered order the change over the next 1, 2, 4 and 8 s
  in a few measured quantities: his stack, the enemy's stack, item control, frags for and against, and the judge's win chance. Trained by
  regression on what followed. On shadow ticks the target belongs to the order that best matches what the hands did (HIRO's relabel), so
  every tick teaches something. The head's choice is the order whose predicted change the judge values most (with its usual sampling).
  Seats open only when the owner-set marks are met (entropy, changes a second, prediction skill on held-out games), reported by the ramp.
- **Why it wins games:** 1.9a's scorer learned nothing until it played and played near-uniformly; this one is trained before it plays, by its
  own pay's facts, and can be checked before it takes a seat.
- **Cost:** small heads on the head's memory; targets computed from the rollout; no extra games.
- **Risks:** orders the hands never carry out get no data (keep them shut); the relabel makes the head's values reflect the hands' current
  habits (the lightning) until the head plays; it must be shown not to be a copy of an old rule (it is a value of the current network's
  outcomes, a point for the owner's ruling under rule 13).

### 2. Learned commitment for the head: a slow learned prior with a KL, and/or a learned "keep for k ticks"
- **Source:** FTW's two-timescale prior; behaviour priors; FiGAR; option termination with a deliberation cost; the Q3 bot's long-term goal.
- **What:** the head's order distribution each tick is pulled (KL, a live dial opened slowly) toward a prior made by a slower part of the head
  that updates every one or two seconds; or the head outputs how many ticks to keep its order. A switch remains possible every tick; it just
  costs. The deliberation-cost variant (a fixed margin a switch must beat) is listed for completeness but is a hand-set number, so it is the
  owner's call.
- **Why it wins games:** flicker lost 1.7a's keep choice its gains and made 1.9a's head a random walk; the Q3 bot shows one persistent goal is
  enough for good item play. A learned commitment is the owner's standing ask ("re-choosing every tick needs a learned commitment, never the
  lock").
- **Cost:** a second small recurrent cell or one extra output; a KL term.
- **Risks:** a strong KL can freeze a bad prior (FTW evolved its weight; we must set it by checks); a prior is itself learned, so it can
  learn to flicker too unless it ticks slower.

### 3. New information enters as a brain readout first, never as raw inputs to the deciders
- **Source:** Arnold (features helped as co-training targets, not inputs), UNREAL, FTW's probes; 2.0b's postmortem step 3.
- **What:** a standing rule for every future input: first a brain lesson (predict it from the senses), its skill measured; then the hands and
  head see it only through the brain's token; raw columns into the head or the keep choice only on the owner's word with a check-tied ramp.
- **Why it wins games:** 2.0b lost its items when 59 fast-moving inputs fed the head; Arnold found the same direction independently.
- **Cost:** none beyond what the brain already does; it changes the order of opening.
- **Risks:** a readout can be skilful and still unused by the hands; the input health report and the end-of-run blank test stay required.

### 4. Opponents that punish: a small exploiter and a varied league
- **Source:** AlphaStar's main exploiters; GT Sophy's mixed opponent population; Gleave; spinning tops; 2.0b's holder idea.
- **What:** in bursts, train a copy of Bobby's current save paid only to beat the current Bobby (no table, the frags and the win); freeze it into
  the league when it wins more than an owner-set share; reset it from the newest save. Its share in the league fixed and checked (Sophy: too
  much of one opponent type changes the main agent's style). The rule-made holder seat of 2.0b is the cheap first version if the owner prefers
  it; the exploiter is the learned one.
- **Why it wins games:** the lightning equilibrium and the unpriced space both come from a league where nobody plays differently from him. An
  exploiter finds and prices his habits; people will find them anyway (FTW's testers memorised routes in six hours).
- **Cost:** a second learner's time (time-sliced on the one card), or the holder seat at rollout cost only.
- **Risks:** an exploiter may find simulator holes rather than play (useful to know, but it must be read); a strong exploiter seat can make the
  main agent passive (Sophy's aggressive-opponent result).

### 5. A value head per pay part
- **Source:** JueWu's multi-head value; OpenAI Five's Rapier variance lesson; 1.9a's noisy items race.
- **What:** split the value into heads for the items, damage, frags and the judge (and the head's own pay parts), summed with the live weights.
  Report each head's explained variance in `metrics.jsonl` and flag a part whose noise exceeds the judge's.
- **Why it wins games:** a noisy part cannot then drown the others' baseline; pay weights can change live without the value relearning;
  the owner gets each part's signal-to-noise before it is paid to the head (the 1.9a lesson asks for exactly this).
- **Cost:** a few linear heads; a small change to the value loss.
- **Risks:** a widening of the value output; to be done with the identity check and a learning-rate-zero warm-up (idea 8).

### 6. Pivotal-moment scenarios with fixed shares in every batch
- **Source:** GT Sophy's mixed-scenario training and stratified sampling; FTW's map variety; Ubisoft's widening spawn radius.
- **What:** add to the mid-game starts a short list of pivotal duel moments chosen from measured game facts (both players converging on the mega;
  a fight entered outstacked; a rail on a long corridor against an approach; the opening seconds), each with noisy variations, and keep each
  scenario's share fixed in every minibatch so a skill is not unlearned between updates.
- **Why it wins games:** the 2.0b postmortem says self-play never shows him a lost mega's cost; these situations decide duels and are rare in
  free play.
- **Cost:** start-state sampling (exists); a per-scenario share in the batch builder.
- **Risks:** a scenario chosen from the pros' games must be a game fact (a place, a time, a stack), never the pros' choice in it (rule 12);
  too much scenario time can bias him toward those moments.

### 7. Probes and behaviour fingerprints in every check
- **Source:** FTW (linear probes, VAE-plus-mixture clusters of two-second chunks).
- **What:** (a) linear probes on the head's and the hands' states for 20-40 game facts (who is ahead in stack, mega up in N s, enemy holding the
  rail, enemy last heard), as a readiness measure for any new chooser; (b) an unsupervised clustering of two-second chunks of check games, with
  each check's cluster histogram compared with the control's (a new cluster = a new habit such as red-armour camping).
- **Why it wins games:** earlier warnings: 1.9a's camping and 2.0b's item loss were found in postmortems, not by the watcher.
- **Cost:** offline, on recorded check games; no training cost.
- **Risks:** clusters need a human read; a probe that decodes a fact does not prove the network uses it.

### 8. Surgery hygiene for every widening and new head
- **Source:** OpenAI Five's surgery appendix and data-quality study.
- **What:** (a) a learning-rate-zero warm-up of a few updates after any shape change, so Adam's moments and the rollout mix settle; (b) apply
  the same surgery to every league snapshot and check them identical; (c) now and then, measure a shut or vestigial part zeroed; (d) one check
  of our sample reuse (PPO epochs over each rollout) against their finding; (e) once the design settles after 2.1, consider one clean run from
  scratch on the final list (their Rerun beat the surgically continued model).
- **Why it wins games:** the widenings that hurt (2.0b's inputs) and the hidden-cost parts would be caught or softened.
- **Cost:** small, except (e), which is a long run.
- **Risks:** (a) delays learning slightly; (e) costs days of the PC.

### 9. A tiny population over the pay weights, selected by wins against the control
- **Source:** FTW (PBT of the reward table by win rate); the Q3 bot thesis (genetic tuning of preference weights by duel wins); PBT.
- **What:** two or three short arms from the same save with different pay weights (e.g. items vs damage vs the judge), compared by games against
  the control, the best continued; repeated at intervals. The table's numbers are then chosen by winning games, the one goal, instead of by hand.
- **Why it wins games:** every pay change so far was argued in advance and judged after a whole run; FTW shows the winning weights also drift over
  training.
- **Cost:** high on one PC (each arm is a short run); the run window allows little of it.
- **Risks:** greedy selection on noisy checks (a 200-game check has about 3.5 points of noise); two changes at once break "one new thing a round"
  unless each arm changes one weight.

### 10. The long-term order / nearby detour split as the head-hands contract
- **Source:** the Quake III bot (long-term goal, nearby goals within a time budget, want divided by travel time), F.E.A.R.'s persistent goals.
- **What:** the head's order names one long-term target; the hands are free to take nearby pickups whose detour is small; the head's item scorer
  is factored as a learned want over a brain-predicted travel time.
- **Why it wins games:** keeps the head's job small and persistent, which is what hand-built bots did well and what learned heads have struggled with.
- **Cost:** mostly a design choice for 2.1's order; a travel-time readout in the brain (the ways exist).
- **Risks:** a factorised scorer may be read as a hand-built structure (owner's call); "nearby" budgets must be learned or measured, not set.

### 11. Human-likeness as an evaluation, never a pay
- **Source:** BotPrize, UT^2, NTT.
- **What:** in play tests, a blind judgement of clips (Bobby vs people, with a human baseline) as a readout beside the win-loss record.
- **Why it matters:** the owner's fairness goal and the public servers; it does not win games by itself.
- **Cost:** people's time.
- **Risks:** judges are poor (humans scored 40% at BotPrize); never to be trained against.

### 12. A simulator-exploit explorer
- **Source:** EA SEED's testing agents; hide-and-seek's physics exploits.
- **What:** short runs of a small agent paid to reach odd places or to survive, on each map, to find where the simulator allows what the game does not.
- **Why it matters:** anything the simulator allows, self-play will eventually use, and it will not transfer to the server.
- **Cost:** daytime light job, cores only, on the owner's word.
- **Risks:** finds holes, not fixes; each hole is a code change behind a switch.

## 14. What does not fit, and why

| Method | Source | Why not for Bobby |
|---|---|---|
| Imitation of human play as a start, a prior or a macro teacher | AlphaStar, CS:GO BC, HMS, vivo, Marvin, Axon, EA BF1, VPT | Rule 12: pro and human data measure, never set behaviour |
| Copy or distillation lessons from old rules or old networks | b1.3a's history, Kickstarting, CSPL distillation | Rule 13; specialist RL teachers would need the owner's ruling |
| Hand-written rules kept beside the learner (shooting rules, aim overrides, scripted purchases, navigation-mesh switches) | NSRL, Marvin, OpenAI Five's scripts, TStarBot2, Arnold's phase switch | The owner retires rules and never brings one back |
| Populations of 30, thousands of arenas, months of training | FTW, OpenAI Five, JueWu | One PC; cut-down forms only (ideas 4 and 9) |
| A learned human-likeness judge as a reward | NTT warns against it | Gets exploited; rule 12 |
| Pixels as input, DNC memory | FTW, VizDoom | Our inputs are structured and fair by construction; a DNC would slow the learning step |

## 15. Sources read

Papers (full text unless noted):
- Jaderberg et al., Human-level performance in first-person multiplayer games with population-based deep RL (FTW), https://arxiv.org/abs/1807.01281
- Berner et al. (OpenAI), Dota 2 with Large Scale Deep Reinforcement Learning, https://arxiv.org/abs/1912.06680
- Dosovitskiy and Koltun, Learning to Act by Predicting the Future, https://arxiv.org/abs/1611.01779
- Lample and Chaplot, Playing FPS Games with Deep Reinforcement Learning, https://arxiv.org/abs/1609.05521
- Wydmuch, Kempka, Jaśkowski, ViZDoom Competitions: Playing Doom from Pixels, https://arxiv.org/abs/1809.03470
- Wurman et al., Outracing champion Gran Turismo drivers with deep RL, Nature 602 (2022), https://www.nature.com/articles/s41586-021-04357-7 (authors' copy https://www.cs.utexas.edu/~pstone/Papers/bib2html-links/nature22.pdf)
- Pearce and Zhu, Counter-Strike Deathmatch with Large-Scale Behavioural Cloning, https://arxiv.org/abs/2104.04258
- Devlin et al., Navigation Turing Test, https://arxiv.org/abs/2105.09637
- Alonso et al., Deep RL for Navigation in AAA Video Games, https://arxiv.org/abs/2011.04764
- Bergdahl et al., Augmenting Automated Game Testing with Deep RL, https://arxiv.org/abs/2103.15819
- Zhang et al., Training Interactive Agent in Large FPS Game Map with Rule-enhanced RL (Tencent, Arena Breakout), https://arxiv.org/abs/2410.04936 (in part)
- Ye et al., Mastering Complex Control in MOBA Games with Deep RL, https://arxiv.org/abs/1912.09729 (in part)
- Ye et al., Towards Playing Full MOBA Games with Deep RL, https://arxiv.org/abs/2011.12692 (in part)
- Wu et al., Hierarchical Macro Strategy Model for MOBA Game AI, https://arxiv.org/abs/1812.07887 (in part)
- Zhang et al., Hierarchical RL for Multi-agent MOBA Game, https://arxiv.org/abs/1901.08004 (abstract)
- Sun et al., TStarBots, https://arxiv.org/abs/1809.07193 (in part)
- Vezhnevets et al., FeUdal Networks, https://arxiv.org/abs/1703.01161 (in part)
- Bacon, Harb, Precup, The Option-Critic Architecture, https://arxiv.org/abs/1609.05140 (in part)
- Harb et al., When Waiting is not an Option: Learning Options with a Deliberation Cost, https://arxiv.org/abs/1709.04571 (in part)
- Sharma et al., Learning to Repeat: Fine Grained Action Repetition (FiGAR), https://arxiv.org/abs/1702.06054 (in part)
- Nachum et al., Data-Efficient Hierarchical RL (HIRO), https://arxiv.org/abs/1805.08296 (in part)
- Tirumala et al., Behavior Priors for Efficient RL, https://arxiv.org/abs/2010.14274 (in part)
- Schmitt et al., Kickstarting Deep RL, https://arxiv.org/abs/1803.03835 (in part)
- Jaderberg et al., RL with Unsupervised Auxiliary Tasks (UNREAL), https://arxiv.org/abs/1611.05397 (in part)
- Rabinowitz et al., Machine Theory of Mind, https://arxiv.org/abs/1802.07740 (in part)
- Czarnecki et al., Real World Games Look Like Spinning Tops, https://arxiv.org/abs/2004.09468 (in part)
- Bansal et al., Emergent Complexity via Multi-Agent Competition, https://arxiv.org/abs/1710.03748 (in part)
- Baker et al., Emergent Tool Use from Multi-Agent Autocurricula, https://arxiv.org/abs/1909.07528 (in part)
- Gleave et al., Adversarial Policies, https://arxiv.org/abs/1905.10615 (in part)
- Jaderberg et al., Population Based Training, https://arxiv.org/abs/1711.09846 (downloaded; used via FTW)
- Mathieu et al., AlphaStar Unplugged, https://arxiv.org/abs/2308.03526 (skimmed)
- van Waveren, The Quake III Arena Bot (MSc thesis, 2001), http://fd.fabiensanglard.net/quake3/The-Quake-III-Arena-Bot.pdf (sections 8, 9, 11, 15)
- ioquake3 bot goal code, https://github.com/ioquake/ioq3/blob/main/code/botlib/be_ai_goal.c
- Orkin, Three States and a Plan: The A.I. of F.E.A.R. (GDC 2006), https://www.gamedevs.org/uploads/three-states-plan-ai-of-fear.pdf

Blogs and news (read or via search summaries):
- DeepMind, AlphaStar: Grandmaster level in StarCraft II, https://deepmind.google/discover/blog/alphastar-grandmaster-level-in-starcraft-ii-using-multi-agent-reinforcement-learning/ ; Vinyals et al., Nature 575 (2019), DOI 10.1038/s41586-019-1724-z (details marked * from prior knowledge)
- EA SEED, https://www.ea.com/seed/news/self-learning-agents-play-bf1 and https://www.ea.com/en-gb/news/teaching-ai-agents-battlefield-1
- Unity, ML-Agents plays DodgeBall, https://blog.unity.com/technology/ml-agents-plays-dodgeball
- Microsoft Research, Muse / WHAM, https://www.microsoft.com/en-us/research/blog/introducing-muse-our-first-generative-ai-model-designed-for-ga
- BotPrize 2012: https://people.southwestern.edu/~schrum2/AAAI-BotPrizePoster.pdf ; https://news.utexas.edu/2012/09/26/artificially-intelligent-game-bots-pass-the-turing-test-on-turings-centenary/
- Fabien Sanglard, Quake 3 source code review (AI), https://fabiensanglard.net/quake3/a.i.php
- Steven Polge: Reaper bot readme and UT AI notes (search summaries), https://www.unrealarchive.org/unreal-tournament/documents/reference/unrealed/unreal-tournament-ai/index.html
