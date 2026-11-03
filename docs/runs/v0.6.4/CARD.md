# v0.6.4: the advanced movement mechanics back in, from v0.6.3's end (DRAFT, not final)

*2026-10-29 (owner): "The goal of that version is reintroduce advanced movement mechanics"; first written as v0.6.3,
renumbered the same day ("this should be v0.6.3 and movement should be v0.6.4": the hand-built rules go first,
[v0.6.3](../v0.6.3/CARD.md)). To be finalised with the owner once v0.6.2 is training. The design and its reasons:
[TRICK_JUMPS.md](../../design/TRICK_JUMPS.md). The view's pull toward level is faded in v0.6.1 (owner, 2026-10-29), so it
is at 1.0 by this run. Nothing is built.*

**Marks:** ✅ built and tested · ⏳ building · 🧪 to measure · ❓ owner's decision · ⏸ later

## The owner's page

| | |
|---|---|
| Goal | Three movement mechanics he does not have. Bobby's record so far: **rocket jumps** (0 rockets in about 420 tries on Aerowalk's red armor), **two-hop strafe jumps** (Campgrounds' bridge to rail: 0 of about 2,700), **Aerowalk's red armor circle jump** (13-16%, taking off at about 340 u/s against the 425 needed). All three are makeable in the simulator: the pros' keys land the bridge to rail 84 of 89 times, and the scripted routes clear the other two. The failure is exploration: he never lands one, so there is nothing to learn from |
| Way | Scaffolding outside him: a library of makes, then three teacher networks, then a copy into his legs branch before the run. The run itself has no teacher, and the teachers are gone at the end: **one movement network** |
| Network | v0.6.3's end with its optimizer (`keep/policy_end_v063.pt`), its legs branch refitted (step 3 below) and checked to play as before |
| Pay | win chance only, as v0.6.3. Practice pays only for landing (`JUMP_OVER_PAY`, `RJ_ARRIVE`), as before |
| Practice | jump runs and rocket-jump runs back in, shut at the start, opened slowly and tied to the checks (hold under 50%, back under 45% or two checks under 50%), up to ❓ % of **all** training (the 10% of advanced movement of 2026-10-20 as a starting point), taken out of the 35% of mid-game starts or the 65% of whole games ❓ |
| Routes | a jump enters his routes (`JUMP_OPEN`, the rocket-jump links, Aerowalk's red armor in the walking graph: B-114) at 50% or more in practice, and comes back out under 25% (the jump-flow rule) |
| New things | (1) the refitted legs branch + practice: the strafe and circle jumps; (2) the legs branch widened to pitch and fire: the rocket jumps. Two new things, so they open **one after the other** ❓ |
| The jumps | the owner's B-204 list. The first three: Aerowalk's red armor, Campgrounds' bridge to rail, the rocket jumps the pros use most (Blood Run's and Aerowalk's red armor; `docs/pro_rocket_jumps.json`) ❓ |
| Aim, mix, maps, league | as v0.6.3 (`!aim default`; the ten maps; v0.6.3's end and v0.6.2's end as anchors ❓) |
| Checks | every 10 updates, 160 games against v0.6.3's end, every fourth against the long-term control; the behaviour panel; the jump checks per jump (`tools/jump_check.py`) |
| Play tests | the owner plays the end; Aerowalk and Campgrounds first |

## Before the run: the scaffolding (simulator only; each step on the owner's go)

| Step | What | Passes when |
|---|---|---|
| 1. A library of makes | For each jump, thousands of runs that land, under his hands (finger and mouse limits, aim2, `LEVEL_PULL` 1.0). Seeded from the pros' run-ups (`sim/pro_jump_starts/`), their inferred keys, the 104 cleared rocket-jump links (`sim/rj_clear.json`) and the full-route copies (`ROUTE_COPY`, `RJ_COPY`). Widened by a random search over keys and mouse that keeps only landings, varied in run-up, take-off and timing ⏸ | at least 500 varied makes a jump |
| 2. Three teachers | One each for the rocket jump, the multi-hop strafe and the circle jump. Each starts as a copy of his own legs branch (the same 61 inputs, 17 outputs). Trained with `sim/train_move.py`, paid for arriving and time only. It begins by copying the library, faded to zero, and starts first near the landing (mid-air on a made run), its start moved back toward the run-up and 2-3 s before it as it succeeds at 70% or more ⏸ | `tools/label_check.py` with his hands: at least 60% from varied run-ups; rocket jumps also on the game's own physics (`plugins/rjlab.py`, a private server) |
| 3. The copy into his branch | Off-line, only the branch's weights change: fitted to its own answers on frames from his games (it keeps what it does) and the teachers' answers at the jumps, with a few rounds of the branch playing the jumps and the teacher labelling what it reaches (DAgger). His gate (`--legs-gate`) decides how much he listens ⏸ | his game play unchanged: the same-answer check, then 160 games against v0.6.3's end at about 50%; the branch alone passes the jump runs |
| 4. The rocket-jump channel | The branch gives no pitch and no fire today (17 outputs: forward 3, sideways 3, jump 2, turn 9), and `--legs-gate` takes no pitch or fire (`LEGS_TAKES` 0, 1, 2, 3, 7, 8). The rocket jump needs both, and maybe more inputs (launcher in hand, rockets, health) 🧪. New outputs and gate links at zero ⏸ | the identity check with them shut: no difference in his answers |

## The checklist

| | |
|---|---|
| Settings check | `train.cmd` against v0.6.3's: only `--run`, the practice shares and the jump switches differ ❓ |
| Identity | the refitted network with practice shut plays as v0.6.3's end (step 3's check); the widened branch with the new links shut answers exactly as before (step 4) |
| Not tested | everything: nothing is built |
| Hand-built / assumed parts | which jumps are taught (B-204; measured alternative: the pros' frequencies in `pro_gaps`); the library's seeds (inferred keys, scripted routes: gone after step 2, where the copying fades to zero); the step-back threshold (70%), the pass bars (60%, 50% / 25%); the share of practice; the copy's mix between his games and the jumps (tuned on the same-answer check) |
| Weaknesses | he may learn the jumps in practice and never use them in games: then it is the head that does not value them, a strategy question (watched: how often he takes the jump while the item is up); the copy into the branch may move his game play slightly, which the 160-game check catches only on average; the rocket jump needs a new channel (step 4), so it comes later than the other two; the bridge to rail and the circle jump have not been checked against the real game's physics |
| Pay pathologies (ledger) | rocket jumps cost health: rocket-jumping too often or in fights (watched: rocket jumps per game, the health lost to them, jump tries with the enemy in view against "no jumping in fights"); as always negative frags, sign flips, lopsided games |
| Watched | success per jump in practice and in games; how often each jump is taken with its item up; items per player-minute (Aerowalk's red armor above all); the lightning gun and rocket launcher shares |

## The reasons for the design

The rest of [TRICK_JUMPS.md](../../design/TRICK_JUMPS.md):
- **Why the teachers stay outside his network:** `--legs-teach` cost 51% → 36% (2026-10-13).
- **Why not practice alone:** that was v0.3.x-v0.5.0, and it stalled.
- **Why not the full-route copies as labels:** that is a hard-wired path.
