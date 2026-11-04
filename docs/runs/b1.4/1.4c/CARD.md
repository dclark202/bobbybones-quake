# 1.4c: the learned commitment (the target lock outside contact), from 1.4b's end

*2026-11-03 (owner): first merged into 1.4b ("Can we combine 1.4b & c into 'one run'"), then split out again the same evening: "We can make the lock into a separate run 1.4c, it needs more working". 1.4b keeps the matchmaking, the item rule's lesson out, the switch cost out, the weapon rule's change and the speed pay out; the lock is this run's one new thing. The design options (A: a hold length chosen with the target, AlphaStar's "delay"; B: keep or re-decide at every head tick; C: fade the lock 8 s → 0) are on [1.4b's card](../1.4b/CARD.md#step-5-the-learned-commitment-to-design) until this card is written. The family: [README](../README.md).*

**Watch: speed** (owner, 2026-11-03: "speed is the thing to watch"). 1.4b fades the speed pay out (0.125 → 0 over updates 70 to 90); from then on fast movement is paid only by what it wins (items first, escapes, finding the enemy). Every report of this run carries his speed on trips (1.3b at update 37: 339, 52% of trip time over 320), air time and who takes the contested items first, beside 1.3b's end, with a flag if they slide.

**A candidate to fade, not decided: the pre-aim pays** (`PREAIM_PAY` 0.05, `WATCH_PAY` 0.03). The owner's concern (2026-11-04): he keeps facing the enemy when he backs off. Measured on 1.3b (the 1.4b card, "Before the start"), these pays are not what keeps him facing: backing off costs him 0.014 a player-minute out of about 10. Like the other hand-built pays, they can go once win pay is shown to carry pre-aiming.

## The result

Not started.
