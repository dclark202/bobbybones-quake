# b1.2: the costs out, every item priced, free to re-decide in contact

**The goal (owner, 2026-11-01):** every health and armor item has a price; firing, changing weapon and moving the mouse cost nothing but what the game costs; he can re-decide his target when the enemy appears. It prepares [b1.3](../b1.3/README.md), the strategy layer's opening.

**Passes when:** at least level with b1.1 and v0.6.0's end; small items taken more often and his stack at fights up; no spam or weapon flicker that costs games; contact used without flicker that costs games; aim holds without the jerk cost; the owner's play test.

## The attempts

| Attempt | Started from | What | State | Result |
|---|---|---|---|---|
| [b1.2a](b1.2a/CARD.md) | b1.1 (b1.1a's save of update 140) | under the family's old goal: the head faded in, learning from combat plus win pay | **Crashed 11-01 15:18 at update 82, gate 0.7. UNUSABLE, saved only (`keep/policy_end_b12a_UNUSABLE.pt`, update 80)** | The head and the hands fought over his target choice: a design fault. See its card |
| [b1.2b](b1.2b/CARD.md) | b1.1 | the health and armor table, then the firing costs, then contact freedom, then the jerk cost | stopped 2026-11-01 17:40 at update 20 (owner): he must know where the small items are, and what they are | 53.1% against b1.1 at update 10 |
| [b1.2c](b1.2c/CARD.md) | b1.1, widened | b1.2b's plan, with every small health and armor item as an input | stopped 2026-11-02 12:52 at update 250 (owner); final check of u250: 55.6% against b1.1 (89-71) | level with b1.1 so far; reads the new inputs, barely acts on them (small items taken near his way 22% to 23%) |
| [b1.2d](b1.2d/CARD.md) | b1.2c's save of update 250 | five pay changes faded in together over updates 10 to 70: the table by the point (the line at 100, decay charged back), speed pay down, damage taken 0.8, the stack lead out, the long rail up; combat wins | ended 2026-11-02 19:41 at update 80 (owner): **a success** (owner, after his play test); on the public servers from 11-02 evening, release `b1.2d`; end `keep/policy_end_b12d.pt` with its optimizer | 56.2 / 57.5 / 51.2% against the start (u10 / 30 / 40), 59.4% against b1.1 (u60); final check of u80: 93-67, 58.1% against the start |
