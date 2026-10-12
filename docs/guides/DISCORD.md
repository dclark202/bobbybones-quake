# The Discord server's pinned messages (written 2026-10-12; update the status pin with every new network)

Three pins, each under Discord's 2,000-character limit. The invite: <https://discord.gg/dH2mfzbMa>. The commands
in full: [COMMANDS.md](COMMANDS.md); what is recorded: [LOGS.md](LOGS.md).

## Pin 1: what he is, and where he stands

```
**BobbyBones: a Quake Live bot that is learning the game from scratch**

Nobody told him how to aim, move or pick a weapon. A neural network plays millions of duels against copies of itself in a simulator of Quake Live, and what works stays. He never trains against the game's own bots.

He plays under human limits on purpose: the same 125 fps physics as you, he sees only what is in his view and hears roughly what you hear, and his aim goes through a "hand" with reaction time, a top flick speed and shake. If he ever hits or sees something a person could not, that is a bug: tell us.

**Where he stands (12 Oct 2026)**
- On the server: **v0.1**. He knows the ten duel maps, strafe jumps on his way to items, and is back at the mega within two seconds of its return about as often as a pro.
- Weak spots we know: he hardly uses rockets (2 a minute; our regulars fire 11), fights from low ground, takes fights when he is weak, and runs the same routes.
- Against people (measured on his last version): our regulars take 70 to 90% of the frags off him; newer players are about even with him.
- Trained last night: **v0.2**, which is shown more of the game (where he believes you are, the places pros hold). It beats v0.1 in the simulator and goes on the server after a review.
- **v1.0** is the day he beats the person who built him.

Code, the simulator and every result, including what did not work: https://github.com/dclark202/bobbybones-quake
```

## Pin 2: the server and its commands

```
**Playing him**

Find the server in Quake Live's browser: **doppz's bot arena | duel & FFA | chicago** (the connect line is in the README on GitHub). Nothing to install.

It starts in free-for-all on a duel map with two Bobbys and stays in warmup until people ready up.

**Type in the game chat**
`!help` what you can do here
`!map <name>` change the map: bloodrun, aerowalk, lostworld, sinister, furiousheights, battleforged, campgrounds, hektik, toxicity, cure
`!mode duel` / `!mode ffa` one against one, or everybody against everybody
`!bots <0-4>` how many Bobbys play in free-for-all
**F3** ready up: when more than half of the people are ready a real 10-minute game starts
`!duel [minutes]` in 1v1 mode: a timed, scored duel against him (10 minutes unless you say)
`!note <text>` tell us something at the moment it happens; the game's state is saved with it
`!top`, `!elo`, `!bobby` the leaderboard: your rating, his rating

Items are a map's duel items in every mode, and there are no powerups.
```

## Pin 3: how to help

```
**How you can help him most**

1. **Play real games.** Ready up (F3) and play the ten minutes, or duel him (`!mode duel`, then `!duel`). Warmup frags count for the leaderboard, but full games teach us far more.
2. **Play your normal game.** Do not go easy on him and do not farm one trick for an hour: we measure how he does against the way people really play.
3. **Use `!note` when something stands out**: "he never looks up", "walked into my rockets three times", "that rail felt unfair". A note saves where you both were, health, weapons and whether he could see you. What feels wrong is worth more to us than a score.
4. **Come back when a new version is up.** Your games against v0.1 and against the next one are the cleanest measure we have of whether he got better.
5. **Every level is welcome.** We have strong players; we need players he can beat just as much, to see where he stands.
6. **Tell us here** what he does that a person would not, good or bad, and which maps you want.

**What is recorded**
Every frame of a game with a person in it: positions, where you look, keys, weapon, health, and every hit and pickup. No names and no Steam IDs go into those recordings. The leaderboard knows you by a scrambled code, and anything we publish shows players only as random ids. The data is used to judge him and to set his human limits.
```
