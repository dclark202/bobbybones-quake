# v0.6.1, b, c, d: what was tried and how it failed

*Written 2026-10-30 evening for an outside review. v0.6.1d is still running (about update 23 at the time of writing; no check result
yet). Numbers come from each run's `metrics.jsonl` and `watch/watch.log` in `data/sim_runs/<run>/`. Conclusions are the author's and may
be wrong; the author ran these runs, so read them sceptically.*

> **Correction after the review (2026-10-30):** H3 below is misstated. The rocket +4.7 against lightning +2.1 came from a trial on the first 150 games, in other units. The judge actually used in b, c and d (`judge_v061_wpn`, computed with `win_judge._mlp`, in frags at 10, 5 and 1 min left): rocket 0.31, 0.22, 0.16; lightning and rail, set equal by hand, 0.57, 0.31, 0.17. v0.6.1's `judge_v060_wpn` has all three at 0.26. So the judge does not pay rockets above rail. Fitted, rail is at its floor (-0.05).

## Background

BobbyBones is a Quake Live duel bot: a recurrent network (about 3 M weights, GRU 512, PPO, self-play league) trained in a fast simulator
of the game. The goal of this generation is that he wins games, paid **by win chance only**, with hand-built rules faded out.

**The pay formula.** In a game frame, with live dials `WIN_W` (w), `FADE_V` (v) and `WIN_GAIN` (G):

`paid = (1 - v) x other + (1 - w) x combat + w x G x win`

- `other`: hand-built pays (item pickups, speed, rail range, watching, shot price, ...). Size about 3.9 a player-minute.
- `combat`: flat pay for frags, deaths and damage. Size about 4.2.
- `win`: `scale x` the change in his chance of winning, from "the judge", a model fitted to how his own games ended and frozen for a run.
  Zero-sum and cannot be pumped. Size at G = 1: about 13 with the first judge, about 10 with the refit.

"Size" (`win_blend.*_size`) is the sum of |pay| a player-minute in games. It measures the reward, not the advantage.

**Other terms.**
- **Level pull** (`LEVEL_PULL`, 0.95 → 1 means off): a hand-built pull of his view toward level.
- **Brain fade** (`BRAIN_FADE`, 0 → 1): removes 76 rule-made input columns (the old hand-written belief about the unseen enemy) from
  "the brain", the part that predicts the enemy's place and stack. They were already faded out of the hands.
- **The item rule**: a remaining hand-built label on his target choice. On in all these runs.
- **PPO details:** no advantage normalization; loss is `pg + 0.5 vl - 0.005 x entropy`.
- **Adv-pay rescale** (added in v0.6.1c): advantages only, after GAE, times `ADV_PAY_REF / running mean of paid size` (cap 4; value targets stay in pay units).

**How strength is measured.** A check is 160 ten-minute games on ten maps, seats swapped, against a fixed network. Noise is about ±4 points
(the same network against itself once read 48.8%). A behaviour panel flags changes from a control. v0.6.0's end is the shared yardstick: it
is the last flat-pay network and the owner likes how it plays.

## What was tried

| Run | Start | Changed | Dates, length | Outcome |
|---|---|---|---|---|
| v0.6.0 | v0.4.2b line | flat pay; the baseline | 10-28, 80 updates | good play; paid size ~8.6, entropy 1.73 → 1.76 |
| v0.6.1 | v0.6.0's end | win pay faded in over u30-150 with judge v060 (`G` 0.33); then level pull faded u250-290 | 10-28 to 10-29, 340 updates | level with v0.6.0 on win only; end lost to its own u250, 144-176 (45.0%) and felt weaker to the owner |
| v0.6.1b | v0.6.1's end | brain fade over u10-100; **also** refit judge and game-end pay fix (`WIN_END`) | 10-29 to 10-30, stopped at u181 | no-go: 43.8% against its start, 40.6% against v0.6.0's end |
| arm B | v0.6.1b's end | `--ent-coef 0.002` | 10-30, stopped at ~u17 | abandoned for v0.6.1c; no conclusion (entropy flat at 1.987, too short) |
| v0.6.1c | v0.6.1's u250 | rescale to 10; level pull and brain fade **together** over u10-80; refit judge and `WIN_END` as b | 10-30, stopped at u130 | 43.1% against its start and against v0.6.0's end |
| v0.6.1d | v0.6.1's u110 (w 0.8, v 0.5) | as c, but pay **held as a blend** with old and win pay about equal; `G` 0.35, adjusted live to stay equal | 10-30 17:41, to ~08:56 10-31 | running |

## Numbers

Win rate in each run's checks (won-lost in the logs):

| Run | Against v0.6.0's end | Against its own start |
|---|---|---|
| v0.6.1 | u10 59.4, u30 51.2, u50 57.5, u70 49.4, u90 59.4, u100 51.9, u120 60.0, u130 58.1, u140 52.5, u160 48.8, u170 53.8, u180 52.5, u210 48.8, u230 46.2, u250 53.8, u270 56.9, u290 51.9, u320 51.2, u340 48.1 | (start = v0.6.0's end) |
| v0.6.1b | u70 55.0, u150 **40.6** | u10 53.8, u30 50.6, u50 45.0, u90 46.9, u110 45.0, u130 43.8 |
| v0.6.1c | u50 51.2, u110 **43.1** | u10 50.6, u30 49.4, u40 52.5, u60 41.9, u70 46.9, u90 43.1 |

v0.6.1 grouped against v0.6.0's end (stretches picked after seeing the numbers):

| Updates | Pay | Average | Note |
|---|---|---|---|
| 10-70 | old, win arriving | 54.4 | u10 read 59.4 before any win pay: a guide to the noise |
| 90-140 | blend | 56.4 | |
| 160-250 | win only | 50.6 | HISTORY's figure for win only over 800 games is 50.0 |
| 270-340 | win only, pull fading/off | 52.0 | but its end lost 45.0% to its u250 head to head |

Metrics (entropy = mean over the last 10 updates; rail, lightning and rocket = share in hand in games):

| Run, update | Paid size | Effective (× k) | Entropy | Rail | Lightning | Rocket | Rule agreement |
|---|---|---|---|---|---|---|---|
| v0.6.0 u10 / u80 | 9.0 / 8.4 | same | 1.73 / 1.76 | .24 / .22 | .44 / .45 | .16 / .16 | .66 / .69 |
| v0.6.1 u110 (blend) | 6.4 | same | 1.81 | .19 | .45 | .17 | .71 |
| v0.6.1 u170 (win only) | 4.3 | same | 1.85 | .21 | .44 | .16 | .71 |
| v0.6.1 u250 | 4.2 | same | 1.86 | .15 | .46 | .18 | .71 |
| v0.6.1 u340 | 4.3 | same | 1.92 | .11 | .47 | .22 | .71 |
| v0.6.1b u30 | 3.3 | same | 1.94 | .09 | .45 | .24 | .70 |
| v0.6.1b u181 | 3.4 | same | 1.99 | .06 | .44 | .31 | .67 |
| v0.6.1c u30 | 3.3 | 10 | 1.87 | .16 | .46 | .17 | .68 |
| v0.6.1c u130 | 3.3 | 10 | 1.97 | .11 | .45 | .23 | .68 |
| v0.6.1d u23 | 5.2 | ~10 | 1.80 | .18 | .46 | .17 | .71 |

KL (~0.031) and clip share (0.32-0.34) barely move anywhere. The critic explains 0.84-0.86 of variance (v0.6.1b). In v0.6.1b the brain's own
scores held or improved through its fade.

## Failure modes seen

1. **Slow loss of strength once pay is win only.** Against v0.6.0's end: about 56 in the blend, about 50 once win only, then 40-43 in b and c.
   The owner also judged v0.6.1's end to play worse. The slide continues after the dials stop moving.
2. **Entropy creep.** Flat under flat pay and through most of the blend, then up steadily from v0.6.1's ~u150: 1.78 → 1.92, then 1.99 in b.
   **In c it rose about as fast with the effective pay held at 10** (1.87 → 1.97 in 100 updates), so the shrinking pay is not a sufficient explanation.
3. **The rail goes to the rocket launcher.** Rail .22 → .06 and rocket .16 → .31 from v0.6.0 to b's end, with lightning flat at about .45. Rail
   shots 2.3 → 0.5 a minute. c repeated it from .16/.17 to .11/.23. This is a **directed shift**, which more randomness alone would not obviously
   produce. Timing is uneven: in v0.6.1 most of the fall comes after u190.
4. **Softer map play in the panel.** Red-armor share of item control down (b 0.43-0.50 against control 0.60; c 0.45-0.49 against 0.58), roaming
   down (c 20.9 against 25.1 cells a minute; v0.6.1 20.1 against 27.1), "passive" flags (c 0.11 against 0.17 frags a seat-minute), Aerowalk yellow-armor
   camping in v0.6.1 (24% against 12%). Frags a match-minute 1.87 → 1.37 across v0.6.0 to v0.6.1. Pickups of megas and red armors per minute hold.
5. **A dip around the fades that did not recover.** c: 49-52 up to u40, 41.9 at u60, then 43-47. Dials reached 1 at u80, and the last reading is 30
   updates later. b fell likewise during its brain fade.
6. **Beats his recent selves, loses to fixed anchors.** b held about 0.52 kill share against its snapshots while falling against the anchors. The
   league alone hides the slide.

**Fixed or found on the way:**
- **Pay size shrink, unnoticed:** `G` was sized to match combat alone while `other` was removed, so the total halved; the refit judge cut it 22% more
  without a resize. The rescale addresses the size, not necessarily what it was thought to cause (mode 2).
- **Game-end pay error:** the judge's chance on the last frame was not the result (4.8% of games off by over 0.1). Fixed by `WIN_END` from b on.
- **Earlier, same generation:** v0.4.3/v0.4.4 faded the item rule before any head existed and he spawn camped. An earlier win-pay design could pay a frag negative.

## Hypotheses

| # | Hypothesis | For | Against, or unsettled |
|---|---|---|---|
| H1 | Entropy bonus too strong as pay shrank (DRIFT.md) | timing in v0.6.1; rail needs fine credit | c held pay at 10 and entropy still rose. Size is of the reward, not the advantage, so the real advantage-to-bonus ratio was never measured |
| H2 | The win signal is too weak or too delayed per action to hold fine skills; old pays were carrying them | blend stretch best; shaped skills go first; entropy could rise because actions stop mattering to the advantage | a blend held steady is untested until d. High critic R² does not show advantages carry action-level signal |
| H3 | The judge misprices weapons: rail hand-set, near 0 when fitted; rocket fitted at +4.7 against lightning's +2.1 | explains a directed shift to rockets; b and c with the refit judge shifted harder | v0.6.1's judge had both hand-set and shifted too, later and slower. Could be fitted on games that already favour rockets: a feedback loop across refits |
| H4 | The refit judge or `WIN_END` hurts | **b and c both carry them and are the two worst; no run isolates them.** Win size at G = 1 fell 22% | d carries them too. Not tested |
| H5 | The level pull's fade costs real strength | v0.6.1's end lost 45.0% (144-176) to u250; rail fell faster over u250-340 | the slide and the fade are confounded. The author previously called this "a little": too generous |
| H6 | The brain fade costs real strength | b and c fell during it | brain scores held. They measure prediction, not play. The author previously said it "cost nothing": **unsupported, b's checks fell 54 → 44 with it** |
| H7 | Self-play drift: the league chases itself | mode 6 | v0.6.0 did not drift on the same league design, though it was short (80 updates) |
| H8 | Run length: everything slides given enough updates | v0.6.0 has only 80 updates; its entropy and rail were already edging the wrong way (1.73 → 1.76, .24 → .22) | **no flat-pay control of comparable length exists**, so this cannot be excluded |

## What the evidence cannot separate

- **Confounded starts:** b and c changed the judge, `WIN_END` and the fades at once; c added the rescale. The owner chose to run the fades together
  in c and d and to isolate only if d fails.
- **Moving yardsticks:** each run's "own start" differs, so a percentage against it is not comparable across runs. Only v0.6.0's end is shared, and
  it was checked rarely in b and c (two readings each).
- **Selection:** the blend advantage (about 6 points, about 2.4 × noise) uses stretches chosen afterward, during a moving mix.
- **Panel noise:** "hunting" was RED in v0.6.1 from u20, before any win pay, so it is weak evidence. The red-share control reads 0.51, 0.60 or 0.58 by
  run, so the measure itself moves a lot.
- **Borrowed optimizers:** c and d start from mid-run saves using v0.6.1's end's optimizer (130-230 updates later).
- **No people:** none of this is checked against human play; the owner's sense of v0.6.1's end is the only such signal.

## What v0.6.1d tests, and its decision rule

It asks whether keeping about half the pay rule-based carries him through both fades. Its start already has the old and win pays about equal by size (2.82 against 3.30 at u110). Rule proposed to the owner:

- **Works:** 50%+ against its start and v0.6.0's end in the last checks, entropy flat, panel clean, beats c's end.
- **Fails:** under about 45% against either after 30 settling updates. Then isolate the fades one at a time.
- **Between:** head-to-head among the ends of b, c, d and v0.6.1's u250.

A success would not show that win-only pay works: the rest of the old pay still has to come out, and that may bring back modes 1-3.

## Plan after this

v0.6.2a fades in a strategy head only (item rule stays on). v0.6.3 fades out the item rule, target lock and pros' tables. v0.6.4 is movement. All are on hold on picking a sound base.

## Questions for the reviewer

1. Is the pay-size or entropy explanation worth keeping after c? What would measure the action-level advantage against the entropy bonus directly?
2. Would normalizing advantages per batch, or per-output target entropy, be a better fix than the running pay rescale?
3. What is the cheapest experiment to separate H2, H3 and H4? Candidates: u250 continued with judge v060 and no fades; a rail/rocket-neutral judge.
4. Is a long flat-pay control (H8) worth a night?
5. Is holding a blend sound, or does it only postpone the same fall? Is a slower cross-fade, or one tied to measured skill, better?
6. Are the checks the right ones: enough games, the right opponents, and should v0.6.0's end be checked at every save?
7. What has the author got wrong or left out?

## Where to look

- Cards: `docs/runs/v0.6.1/CARD.md`, `v0.6.1b/CARD.md`, `v0.6.1c/CARD.md`, `v0.6.1d/CARD.md`.
- Reports: `docs/runs/v0.6.1/REPORT_0630.md`, `v0.6.1b/REPORT_0630.md`, `v0.6.1b/DRIFT.md`, `v0.6.1/WINPAY_END.md`, `v0.6.1/B_FIT.md`.
- Pay: `sim/duel_env.py`, comment at `WIN_W=w`; judge: `sim/win_judge.py`; rescale: `sim/train_duel_rnn.py`, `adv_pay_ref`.
- Saves: `data/sim_runs/duel_gru_v0_6_*/keep/` (every 10 updates and the ends). Older history: `docs/HISTORY.md`.
