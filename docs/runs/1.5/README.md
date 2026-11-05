# 1.5: the strategy layer's next steps (planned)

**When:** after 1.4b, once the strategy layer has been shown to work (owner, 2026-11-03: "It would be after 1.4/5 at the earliest, once the strategy layer has been shown to work"). Each item below is one new thing: its own attempt or a step of its own, as the owner's rule for a start (one new thing per round; two open one after the other).

**Watch: speed** (owner, 2026-11-03: "speed is the thing to watch"). 1.4b fades the speed pay out (0.125 → 0 over updates 70 to 90); from then on fast movement is paid only by what it wins. Every 1.5 report carries his speed on trips (1.3b at update 37: 339, 52% of trip time over 320), air time and who takes the contested items first, beside 1.3b's end, with a flag if they slide.

**To address in 1.5: the lightning gun habit** (owner, 2026-11-04: "The LG habit is concerning, but I will address it in 1.5. My hope is that we can get through b and c before having to address it"). In 1.4b the lightning gun's share of his time in hand rose from 0.54 at update 10 to 0.62 at update 30, and rockets fell from 0.25 to 0.21 (the pros: rockets 0.41, lightning 0.32). 1.5's weapon leaners (does he answer the enemy's weapon?) are the first place to take it on.

## The items

| Item | What | Where it came from |
|---|---|---|
| **Weapon leaners in the league** | Some of the frozen league opponents fight with a habit: a push (about +2) on one weapon's score whenever they hold it with ammunition (the railgun, the lightning gun or rockets), drawn per life. Only frozen league seats (a snapshot of himself or an anchor), never a learning seat. His own seat, pay, lessons and inputs unchanged. The question: does he learn to read the enemy's weapon and answer it? | owner, 2026-11-03: "I don't think bobby changes weapons currently based on what the other person is fighting him with"; "yeah add this to 1.5" ([BACKLOG B-299](../../BACKLOG.md)) |
| The hunt as the head's choice among the brain's zones | new outputs: the head picks the zone he goes to when he hunts | the b1.4 plan of 11-02 ([b1.4](../b1.4/README.md)) |
| The movement network's look point out of his inputs | | the b1.4 plan of 11-02 |
| ~~Exploiters~~ | parked (owner, 11-03: "I'm skeptical on the ability to generate exploiters currently") | AlphaStar's league, discussed 11-03 |

Matchmaking by difficulty (AlphaStar's) goes earlier, as soon as possible ([BACKLOG B-300](../../BACKLOG.md)).

## Weapon leaners: the plan

| | |
|---|---|
| Who leans | about 30% of the frozen league seats' lives (about 10% of all his games: half his games are against the league), 10% each rail, lightning, rockets; the rest of the league and all self-play as today |
| The push | +2 on the leaning weapon's logit while the seat holds it with ammunition; it still switches when it has to; drawn per life, so he cannot know in advance |
| Why it should work | in self-play both copies fight alike, so the enemy's weapon rarely changes his best answer; against a mix of habits the only way to tell which he faces is what the enemy holds (`enemy holds ...`, `enemy seen with ...`, inputs he has), so reading it pays. The pay is unchanged and zero-sum |
| Measured by | his weapon in hand against the enemy's weapon and the distance, beside the pros' (the demos have both players' weapons); switches a minute with the enemy in view, beside the pros' and people's; the checks against unchanged opponents must hold (beating only the leaners means they are too easy or too many) |
| Risks | caricatures (a leaner changes weapons less than a person: keep the push moderate and the share small); exploiting a leaner's other habits instead of reading the weapon; a little less normal self-play |
| Build | small: a per-seat bonus on the league network's weapon logits in the trainer's rollout, drawn per life; a live dial for the share; the measures above in the panel |
| First, with no run | (B-299 1, 2) the measures on today's network and the pros, and the simulator's weapon-switch time against the game's (`plugins/weaponlab.py`) |

## The attempts

| Attempt | Started from | What | State | Result |
|---|---|---|---|---|
| [1.5a](1.5a/CARD.md) | 1.3b's end | (owner, 11-04 evening) the head contributes to his weapon choice before anything is faded: its weapon scores added to the hands' (at zero at the start), the weapon key's credit on the head's clock over updates 10 to 90, weapon habits on 30% of the league seats' lives; the switch cost, the weapon override and the blind-fire cost out at update 0; the item teacher and the lock as 1.3b (their fades: [1.6](../1.6/README.md)) | ended 2026-11-05 07:18 at update 133 | 56.5% against 1.3b's end at u110, 88% against b1.2d's end; rail owned and in hand down, lightning up 5 points; big weapons owned 1.80 → 1.70 |
