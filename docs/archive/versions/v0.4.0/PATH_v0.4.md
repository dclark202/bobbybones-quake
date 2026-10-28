# The v0.4.x generation: goals and the path

*The owner, 2026-10-24: "There is only one goal: win games." Each generation has its own goals; every change is put in
terms of the equilibrium it leads to in self-play (short-term changes matter: they decide which behaviour emerges on the way),
but only winning matters in the long run. This page is the path, to adjust as results come in.*

## The generation's goals

1. **Fade out every hard-wired rule** (the fairness limits stay: human physics, senses, aim limits).
2. **The brain manages the game state and the strategy** (it predicts; the head plans; the hands do what is needed now).
3. **Pay by win chance only.** Every step on the way is scaffolded now and opened slowly, one at a time, check-tied.

**Open items beside the goals** (not the priority; raised at every plan): rocket jumps (the full-route copy `RJ_COPY`
passed its pupil test at 80%, off); failed movement jumps (Aerowalk's red armor: the two-hop route copy `ROUTE_COPY`, 62 to
66%, built); grenades, less so (as area denial: B-279).

## The rounds

| Round | The one new thing | What it retires | Equilibrium it aims at | Pass |
|---|---|---|---|---|
| v0.4.0 / 0.4.0b ✅ | the brain: the enemy's place now and ahead, his stack, who takes the next items, from the senses only | — | (labels in hindsight, no pay) | his errors under the rule's |
| v0.4.1 ✅ | the brain's token into the hands | — | the hands act on what the brain foresees | 64 to 71% against v0.4.0b |
| **v0.4.2** (running) | the old belief faded out of the hands (76 rule-made columns); the simulator's readers on the brain's answer; pre-fire free where the brain expects him | the rule belief in the hands and readers | his plays follow his own foresight, right or wrong; a wrong guess costs him, so the brain is pushed to be right | level or better than v0.4.1 at fade 1 in 3 checks |
| v0.4.3 | the strategy head: reads the brain's outputs (place 1/2/4 s ahead, "in control", the next items' takers) and picks the plan (which item, where to hold, when to push, a way to deny) | then, one after the other in the run: **the item rule** (the head takes it over), **the level pull** (0.95 -> 1.0) | plans pay through what they win: items, frags; a plan the enemy reads is beaten | level or better than v0.4.2's end; the decision report toward the pros |
| v0.4.4 | **win-chance pay, first step**: the overtime bug fixed, his own win table, the values' targets include it; cross-fade weight w from 0 slowly; the pays that do nothing for winning go first (big-weapon order, shot price, watching the doorways/pre-aim) | three shaping pays | the same as today's minus three pays that reward dying, firing less, looking: nearer "win" | level or better; WIN_PAY's share of his pay rising, the win rate not falling |
| v0.4.5 | the cross-fade goes on: the item flats, the stack difference, speed | the aligned shaping pays (the value already prices them) | items and stack worth what they win, no more | level or better |
| v0.4.6 | **the rules out of the brain** (its 76 rule columns, slowly: it relays the stack filter today) | the last rule belief | the brain's own senses only | the brain's errors not above ~5% worse |
| v0.4.7 | the last pays: damage, flat frags; **pay = win chance only** | every shaping pay | **zero-sum: win the game** | level or better than v0.4.6's end; the generation's end |

- One new thing per round; a round whose one thing opens shut, slowly and check-tied starts directly (no separate trial).
  Two things in a round open one after the other.
- Every pay change states its equilibrium. A dip lasts 20 to 30 updates at most (the guard: hold under 50%, back under 45%
  or two checks under 50%).
- The order can change with the results: the brain's rules could come before the pays if its errors allow; v0.4.4 to
  v0.4.7 may merge if each step passes fast.
- Before v0.4.4: who he trains against (only himself and his league under pure win pay; keep outside styles in the mix).
- The servers: each round that passes goes on them on the owner's word (the people data and the real-game checks come from there).
