# Good design principles: what has worked

Started 2026-11-17 on the owner's word ("create a 'good design principles' doc ... based on what has worked recently. The design for
removing the lock is a good first entry"). One entry per principle: what it says, the case it comes from, and **how sure we are**.
What failed and why is in [HISTORY.md](../HISTORY.md); the rules are in [CLAUDE.md](../../CLAUDE.md). An entry is added when a design
has worked in a run, and its mark is changed when a later run confirms or breaks it.

| Mark | Meaning |
|---|---|
| ✅ proven | It worked in a run and held in the checks or a play test |
| 🟡 believed | It follows from a failure or from the owner's reading of one; not yet shown by a run of its own |
| ❌ broken | A run built on it failed; kept as the record, not to be followed |

## 1. Describe how a player does it, then build exactly that ✅

**Case: removing the 8-second lock (2.1c, 2.1d).** Six attempts had all kept one assumption: something decides *when* he may choose
again (a timer, a keep-or-switch choice, a margin). The owner described what a player does: "I'm going to go get mega ... every 200 ms
I ask myself what else should I be doing"; "he makes a decision, sticks to that decision, unless something appears that really calls
for a change". That was built as it was said:

- He re-chooses every 0.2 s by one comparison of totals. Nothing decides "should I switch".
- Each goal's total is its fresh score, plus dice rolled once when the trip starts and kept until it ends, plus a boost for the goal
  his slower plan expects him to be on in 2 seconds.
- A rival goal has to beat the kept dice and the plan's boost, so it needs real news to win. No timer, no margin set by hand.

It worked: the lock was taken out fully, the checks held, and in the owner's play test he "feels more human".

**The principle:** when a part keeps failing, find the assumption every attempt shared and remove it; then take the owner's
plain-words description of the player's thinking as the specification, and map each phrase onto a mechanism.

## 2. Let a part be what it turned out to be; give a new job a new part 🟡

**Case: the decider and the fight (1.7a, 1.9a, 2.2a → 2.2b).** The network that chooses his goal was offered fighting orders three
times and never took them up. Looked at plainly, it had become an item picker: 16 of its 17 options were "go to this item or place",
and the one fight option ("the enemy") was 6% of his time.

The owner's reading (11-17): "when we make a network that chooses, the number of 'things' to choose from cannot be that large. Or, put
differently, the failure of the original decision network to expand into different fight orders is a reflection that that network was
'saturated' by its choosing of items. So if we want to get the fight info into it, it has to go somewhere else." And: let things
dictate their use.

So in 2.2b the item picker stays an item picker, and whether and how to fight goes to a new network with the information a fight
needs and its own pay.

**The principle:** do not force a second job into a part that has settled into one. Read what the part actually does from its
behaviour, keep it at that, and build the new job beside it. A chooser works on a small set of options of one kind.

**Not yet proven.** 2.2b (RUNS.md #60) tested it with four fight options and failed, but by how the options were taught (principle 3),
not by the split itself. 2.2c keeps the split in a smaller form: the item picker keeps its whole list, "the enemy" in it, and the
fight network adds one number to that option's score. That the old decider was "saturated" is a reading, not a measurement.

## 3. The hands practise a play before whatever chooses it is judged on it ❌ (as dealt practice)

**Broken by 2.2b (RUNS.md #60).** Practice trips dealt at random moments, with a dealt weapon, were worth less than his own choice at
every update for all four options (the trips' damage trade 0.84 against 1.00 on his own choices, all run), and the chooser learnt
that the plays were bad. The owner (11-18): "Anything which forces him to use a specific method will not work ... dictating that he
play a certain way makes him worse. Full stop." **What replaces it:** nothing is dealt to him. A new behaviour is brought out by a pay
on what leads up to it, on events that already happen in his games (the pre-aim pay is the model: zero-sum, at every fresh sighting,
graded), and by the inputs it needs; his own network chooses. The text below is the record of 11-17.

**Case: 1.7a.** His choice of the fighting orders fell from 2% to 0.02% because, when they were first chosen, his hands did not know
what to do with them; they did not pay, and the chooser learnt that they were worthless. 1.9a and 2.2a repeated the shape: each
changed who chooses and none taught the doing.

**The principle:** anything that changes who chooses comes after the hands can carry the choice out. Deal the new play to him as
practice, at random moments, to both players, and only then let a chooser's opinion of it count.

**Not yet proven** as a cure: 2.2b's first 60 updates are the test. What is measured already: dealt a fight option, the start network
reaches the place or meets the enemy on 78 to 95 of 100 trips.

## 4. Knowledge reaches a decision as a prediction that was first shown to be right ✅ (the first half)

**Case: the predictions on the belief (2.2a).** The one part of 2.2a that worked: small readouts that predict the odds of a fight,
either player dying soon, the enemy's health and armor as a range, and where he will be in 1 to 4 seconds. Each learns from what
then happened, by itself, and its accuracy is known before anything depends on it (the enemy's armor off by 22 points against 42 for
the old hand-written rule). The opposite was 2.0b: 59 raw, fast-moving inputs fed straight into the decider made his goal unstable.

**The principle:** new knowledge is first a prediction with its own lesson and a measured accuracy; a decider reads the prediction,
never the raw numbers. **Proven:** that such predictions learn well. **Not yet proven:** that a decider uses them well (2.2b's fight
network was the first to read them, and its failure had other causes; 2.2c's lever reads them again).

## 5. A new part plays a little from the start; it is not kept fully silent ❌ (as built in 2.2b)

**Broken by 2.2b.** Half the practice was picked by the fight network itself, and it fed on its own ranking: at update 60 it picked
back off 3,281 times and go at him 18. A share picked by the part did not correct the part; it starved what the part ranked low.
2.2c does the opposite: the lever is at zero through update 10 while the new pays work on the hands, then it is added in full, with
the decay on it from the start. The text below is the record of 11-17.

**Case: the fight network's start (2.2b's design).** Kept fully silent, a chooser's scores have nothing to correct them: a score can
climb every update because the choice is never played. The first fix was a tie to hand-set starting shares; the owner did not trust
the amounts, and the tie would have held down the very options the run was for. The design now: half of the practice trips are picked
by the new network itself, so a score that climbs too high gets played more, shows its results and comes back down.

**The principle:** "learn silently, then blend in" means a small playing share from the start, not zero. Prefer a mechanism that
corrects itself over a number set by hand.

## 6. Every new thing starts as a no-op, proven identical, and opens on a live dial ✅

**Case: every run since b1.** A new part is added with zero effect; the network is shown to answer exactly as before (2.2b: 0 of
1,075,200 actions differ); then one dial opens it over tens of updates, settable while the run trains. A fall can then be pinned on
what was opening. Where several things opened together (1.7a's order, pointer and fire push; 2.2b's updates 60 to 100) the cause of
a fall could not be told, and that is said on the card.

**Changed by the owner, 2026-11-18:** the no-op proof and the live dial stay; "one thing at a time, opened slowly" does not. Changes
that only work together open together, at a size meant to change his behaviour ("these small subtle changes absolutely will not
work"; 2.2b's near-miss pay alone moved nothing). 2.2c opens three pays and the lever as one unit, each at full size from its start.

## 7. One list, no modes ✅ for the items, 🟡 for the fight

**Case: the item choice since 2.1d; the fight options in 2.2b.** Every option gets a score and he heads for the highest, re-scored
every tick. A new decider adds its options to that list; it does not switch him into a state where the others are off. The owner:
"what I do not want to happen is to have any type of blinders ... where they would force him into an action"; "'fight while going to
this item' is a total possibility".

**After 2.2b:** the principle stands; the four fight options as rows of the list failed (principle 3) and are out. In 2.2c the fight
side is one number on the list's own "the enemy" row.

## 8. Each decider is paid for its own job, and winning is the currency they share 🟡

**Case: 2.2b's pay split.** The item picker is paid for items and the chance of winning; the fight network for damage, frags and the
chance of winning; the chance of winning is at least as large as each one's own pay, and it comes from a judge that reads the whole
state (stacks and items). **Not yet proven:** in 2.2b's first 60 updates it cost nothing and showed no gain (checks level with the
start). Kept in 2.2c on the owner's word.

## 9. How we build ✅

- A worker builds and tests; the planning session reads its record, checks the deciding numbers itself, and sends it back when
  something works against the run's aim (2.2b: practice was mostly "back off"; an angle trip never held).
- A run's command carries the values that actually play, and the start refuses when they differ.
- No stage hangs on a test that has not been shown to pass for a part that works. Stages open on the clock; numbers are reported.
- Every report says, first and in plain words, what is playing and whether the run is on its plan.
