# The enemy in his head: a proposal (2026-10-12; for the owner's review)

The owner, 2026-10-12: "we should be pushing him hard to prioritize knowing where the enemy is and how that should
inform what he does next. He's demonstrated his ability to play with a static template, the next step is dynamically
changing actions based on the presumed state of where the enemy is. Please think about that for awhile, it's possible
that we may need a more cohesive model of 'the enemy' inside of his model? ... Pro players almost always know where
their opponent is, and that is probably the main thing which informs what they will do next." Backlog: B-240.

Words used here: his **movement network** is the separate small network that runs and strafe-jumps to a target when he
switches it on (elsewhere in the docs: "his legs"). His **intention** is his choice of what to go for next (an item, a
place, nothing).

## 1. What he has today

- **The evidence, all of it as a player has it**: the enemy in view; his last known place and movement; every sound
  with its direction (steps, jumps, shots, teleporters, pickups and which item it was); pain sounds by health band;
  when each item was last taken; what the enemy was seen holding.
- **One guess made for him by a rule** ("the enemy as he believes him", 21 inputs): the last place seen or heard,
  pushed on a second along his last movement, with how long ago and how far he can have got since. One point, no "he
  is at the red armor or at the mega", and it goes out after a few seconds.
- **A memory** (512 numbers) and the attention part over his inputs, both free to keep track of anything.
- **Nothing that makes him use it.** Section 2.

## 2. Why a template is what this setup makes

1. **His intention's teacher never looks at the enemy.** Through every run, at a weight his own results cannot
   outvote (`--intent-teach 2.0` to the run's end), his choice of the next item is pulled toward a hand-written rule
   (`intent_rule()`): the nearest item he can use that is there or about to be, by his own health, armor, weapons and
   the items' clocks. The rule was the cure for collapsing pickups (2026-10-08) and it worked; it is also a template
   by construction.
2. **He is paid for items, not for the enemy.** Of the 6.1 he earns a player-minute, 5.5 is for items and stack; the
   damage he deals is 1.7 and the damage he takes the same again off; a frag 1.2 (RESULTS 2026-10-12 15:00).
3. **His opponent is himself**: the same template, where it is due, when it is due. Nothing punishes being
   predictable and nothing rewards knowing where the other one is beyond the fight itself.
4. **While his movement network carries him it holds his view** (half of every game): he cannot look where the enemy
   will appear.
5. **Rounds of two minutes**: control of the map over a game is never paid.

## 3. How much the enemy weighs with him today (the yardsticks)

| Yardstick | The pros | He (v0.2's end) |
|---|---|---|
| Fights he commits to with a stack under 60 | 1.2% | 5.0% |
| His speed toward an enemy in view when his own stack is under 60 | -12 units a second (they back off) | +30, and +30 when he is stacked: the same |
| Closes in just after his own frag, more than otherwise | +32 units a second | 0 (31.5 against 31.6) |
| Commits more against an enemy spawned under 10 s ago than against one alive over 25 s | +2.4 points | -5.6 (v0.1) |
| **The blindfold, all of him**: his share of the frags against himself with everything about an unseen enemy hidden from all his outputs | | 14.9% (64 games on four maps: 3 won, 60 lost); he is seen without seeing 9% of the time against 2% |
| **The blindfold, his intention only**: the same, hidden only from his choice of what to go for next | | **51.0% (160 games on the ten maps: 79 won, 74 lost): it costs him nothing.** He uses where the enemy is to turn, face and track, and not at all to choose what he does next |
| **Contest sense, who takes it**: the mega or the red armor, 3 s before its return, his way under 5 s: taken when he is clearly nearer, and when the enemy is | 67% and 16% | 70% and 21%: the same (it is the race) |
| **Contest sense, who comes**: he is at the item within 10 s, at equal own distance: when he is nearer, and when the enemy is | 57% and 28% | 72% and 61% |
| ... at the mega alone | 72% and 30% | 73% and 71% |
| **Contest sense, the stack**: a contest or the enemy nearer; he comes when he is 50 or more of stack ahead, and when 50 or more behind | 64% and 26% | 69% and 55% |
| ... the enemy clearly nearer and he 50 or more behind | 10% | 37% |
| His intention names that item, at equal own distance: he nearer, the enemy nearer | | 45% and 39% (at the mega 39% and 44%) |

The contest numbers: 999 pro games (both players' own recordings laid over each other, so the enemy's place and stack
are exact) beside 192 games of v0.2's end against himself; Blood Run, Aerowalk and Lost World carry the tables. Two
things stand out. The pros stay away from an item the enemy sits on, and he walks in. And **the stack matters more than
the distance**: the pros go when they are the stronger and stay away when the weaker; he comes either way. Who takes
the item in the end is no different: that is the race. The scripts are kept as a yardstick (to go into `tools/`).

## 4. What I propose

The owner, of the guessing game (tonight's "things he foretells"): "Yes this is the way. Think more about this
particular implementation." So part A is the centre and the rest hangs on it.

### A. The guessing game, in three steps

**What it is today (step 1, in tonight's run).** Every frame he is asked four things and corrected by what truly
happened; nothing is paid: where the unseen enemy is (one point); where he next comes into view (two angles); how the
next fight ends (a frag, fragged, neither; and the damage); when the mega and the red armor are back. In four updates
of a dry run the first went from 640 to 548 units off (a blind guess: 800); the fight's end was not learnt. Its
limits: a single point cannot say "at the red armor or at the mega" (it lands between the two); it asks nothing about
what the enemy WANTS or how strong he is; and his answers go nowhere: they shape his memory and that is all. The
blindfold of section 3 shows what that is worth to his next move: nothing yet.

**Step 2: the questions a pro asks himself** (built as an option for tonight; no new inputs, the checks and the
servers untouched):

| The question | The answer's form | Where the truth comes from | What a pro does with it |
|---|---|---|---|
| What is he going for? | odds over the items and places (the same list his own intention chooses from) | the other seat's own intention, which the simulator holds; free in self-play | goes somewhere else, or gets there first, or waits for him there |
| How strong is he, and what does he hold? | his stack in four bands; the weapon in his hand | the simulator | fights or does not; picks the range |
| Who gets there first? | for the mega and for the red armor: I, he, nobody in the next ten seconds | what then happened | goes or lets it go |

**Step 3: his answers feed his choices.** The map's landmarks are the things his intention already chooses among
(the mega, the armors, the three big weapons, the eight holding places: about fifteen a map). His picture is drawn on
them: for each landmark how likely the enemy is nearest to it now, in three seconds, and that it is what the enemy is
going for; beside it the enemy's strength and weapon and who gets each big item first. Two ways to let him use it,
the first much the cheaper:

- **3a, a short way from the picture to the choice (the same frame).** His answers, as they come out of the guessing
  game's outputs, are handed straight to the outputs that decide what he does next: his intention, the switch to his
  movement network, his weapon. A small table of weights, all nothing at the start (he answers exactly as before, so
  no level is lost), learnt by what it pays him. Then "the enemy is probably at the red armor" to "not the red armor
  now" is a handful of weights to learn, not a rebuilding of his memory; and the table can be printed and read: by how
  much his wish for each item falls or rises with where he thinks the enemy is. No new inputs; the checks and the
  plugins need only the network's own new part.
- **3b, the picture among his inputs (the next frame)**, on each landmark's own token, so that the attention part and
  his memory can use it too. His answers must then be carried from frame to frame wherever the network is run (the
  trainer, the checks, the plugins) and there are about seventy new inputs. Only if 3a is not enough.

With either, we can read the picture (draw it in a video; count how often it is right by the seconds since he last
saw him, and whether "70%" from him is right 70% of the time), and the teacher can be tied to it: the item rule silent
where HE says the enemy gets there first (section 5 does this tonight with the rule-made guess he has already). The
truth is a label only, never an input: a player learns the same from watching both sides of a demo. The blindfold of
section 3 becomes the proof: hiding the picture from his choice must begin to cost him.

### B. His intention taught by what the pros chose in the same situation, not by the item rule

From the 5,000 demos: a player's situation as his own inputs describe it and what he went for next. A small network
learns that; its answer on Bobby's own situation is the teacher's label, the rule the fallback where the demos are
thin. The pros' choices contain the enemy; the rule does not. With step 3 in, the same network can be asked the same
question of the enemy's side: a learnt guess of what a good player in his place would go for.

### C. Opponents who punish a template

Two more among the scripted players of training: a hunter (goes where it last heard him, pushes when it has hurt him)
and an ambusher (waits out of sight at the item he is due at). Against them knowing where the other one is wins
fights, which is the only thing that teaches it by itself.

### D. Whole games, paid by the game, begun in their middle

Built but for the last part (the owner: "games can and should start mid way with a different variety of states
(up/down/tied/stacked/not/etc.)"). Then denying an item, holding a lead and pushing a fresh spawn are paid for what
they do to the game.

### E. His view while the movement network carries him

Where it does not need the turn (a straight, a landing), his own aim holds the view, toward where his picture says the
enemy will come from. A design question of its own, after step 3.

**The order**: step 2 tonight if it passes its tests; step 3a and C next (a day or two of building and checks); B
beside them as a data job; 3b if 3a is not enough; D when games can begin in their middle; E last.

## 5. A first step that is ready tonight, if the owner wants it

`RULE_CONTEST` (built 2026-10-12, off by default, with it off the simulator is unchanged bit for bit): **the item
rule's lesson falls silent on the frames he believes the enemy nearer to the item it names than he is himself** (by
two seconds of way or more; his own inputs' belief, not the truth). There the template says nothing and what he does
is his own to find, by what it pays him: go anyway, wait, take another item, go to a place. It silences 4 to 6% of the
rule's frames. It adds no pay and no new lesson, so it cannot buy a habit; what it risks is fewer pickups in those
moments, which is the point of the trial and is counted (the take rate by who is nearer, section 3).

## 6. What would show it works

The blindfold costs him more than it does today; his take rate of a contested item moves toward the pros'; the three
scorecard measures of section 3 move; and, when part A is in, his picture of an unseen enemy is right more often than
"the last place seen" at 5 and at 10 seconds.
