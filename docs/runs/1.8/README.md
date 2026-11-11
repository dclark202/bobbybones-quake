# 1.8: the 1.n series redone from b1.2d's end, under AIM3

*Owner, 2026-11-11, after 2.0c: "this run makes me think we need to go further back than 1.7 to start. The trend away from range weapons
was already beginning before then"; "Call this model 1.8".*

*The name 1.8 was first given on 2026-11-05 to a movement family (the jumps he cannot make, the ways, rocket jumps) that was designed
and never built or run; those pages are kept as [README_movement_2026-11-05.md](README_movement_2026-11-05.md) and
[1.8a/CARD_movement_2026-11-05.md](1.8a/CARD_movement_2026-11-05.md). ❓ the owner's: where the movement work is numbered now.*

**The goal:** one network at roughly 1.7a's update 90 (the strategy head on his target, the keep choice, no hand-written rule on his
target, no firing cost, no speed pay in games) whose hands and head learnt under the aim model AIM3
([design/AIM3.md](../../design/AIM3.md)), as the start of 2.1 ([../2.1/DESIGN.md](../2.1/DESIGN.md)).

**Why b1.2d:** the weapon in his hand in training games, at each run's end (rockets / rail / lightning): v0.6.0 16 / 22 / 45%, b1.0a
19 / 15 / 45%, b1.2d 37 / 5 / 38%, 1.3b 26 / 2 / 56%, 1.7a's update 90 19 / 1 / 67%. The lightning took over inside 1.3b, in step with
the head's credit; b1.2d's end is the last network before it.

| Attempt | What | Result |
|---|---|---|
| [1.8a](1.8a/CARD.md) | on the cleaned input list 18 and the tuned AIM3: AIM3 (updates 0 to 30), 1.3b's head opening (50 to 130), the rules on his target out (the restart at 150), the item teacher and speed pay out (160 to 190), the keep choice (210 to 250), the strategy inputs out of the hands (270 to 310): one run of 330 updates from b1.2d's end, the damage pay 0.005 and zero-sum from the start | **built and tested 2026-11-11 evening; not started: the owner's review and go, from a new session** |

**The order of work (owner, 2026-11-11):** (1) the input clean-up ([design/INPUTS_CLEANUP.md](../../design/INPUTS_CLEANUP.md): its "Final"
table and "How it is done"; the measurements: [1.8a/INPUT_AUDIT.md](1.8a/INPUT_AUDIT.md)) and AIM3's open points
([design/AIM3.md](../../design/AIM3.md); the clean-up doc's "AIM3: what tune covers"); (2) this run, on the cleaned start; (3) 2.1.
