# QLStats and BobbyBones: can the server use the global duel ratings?

Research of 2026-10-12. Nothing was built, registered or changed; no Steam id was sent anywhere.

## The answer in three lines

- **Possible: partly.** Looking people up works (QLStats is alive and its rating lookup by Steam id is open to game servers); a global rating for Bobby himself is not possible (a match with a bot in it is never rated).
- **What it takes:** one HTTPS request per person per day from the ladder plugin, in a background thread, with the Steam id in the URL; a private file of ratings beside the anonymous keys; one line in the welcome and an off switch.
- **What it gives:** the strength of the people he meets, at once and without a model; and an estimate of his own level ("he takes half the frags off a 1,350 player") that is coarse: a few hundred frags place him within about 150 to 300 points, and only duel games against rated people make it a duel rating.

## 1. Is QLStats alive, and what does the lookup return

**Alive.** Evidence of today and this year:
- The front page lists games of the last minutes; of the 20 latest, 13 were duels. A notice of 2026-01-20 says servers without a match in 90 days were purged. https://qlstats.net/
- The node API answered with live JSON today (no id involved): https://qlstats.net/api/a_rated_factories
- The source repository had commits on 2026-02-19 ("backported changes from production deployment") and 2025-10-23 (a check against a DDoS attack). https://github.com/PredatH0r/XonStat/commits/master
- A Steam thread of 25 to 27 February (no year shown, so this year) has an owner connecting a new server through the panel. https://steamcommunity.com/app/282440/discussions/0/766311764553974824/

**Base URL:** `https://qlstats.net/`. Plain `http://qlstats.net/elo/...` is still let through for old plugins (balance.py builds exactly that); the old `qlstats.net:8080` was closed in November 2016; `api.qlstats.net/*` is a legacy name for `/api/*`. Sources: the nginx file and README of the repository, https://github.com/PredatH0r/XonStat/blob/master/nginx/qlstats.net/qlstats.net , https://github.com/PredatH0r/XonStat ; port 8080: https://www.esreality.com/post/2810808/re-qlstats-net-changes/ (comments of November 2016)

**The endpoints** (routes in `xonstat/__init__.py`, bodies in `xonstat/views/player.py`; no login check in any of them):

| Endpoint | Returns |
|---|---|
| `/elo/<id>+<id>+...` | `{"players": [{"steamid": "...", "duel": {"elo": n, "games": n}, "ffa": {...}, "ca", "tdm", "ctf", "ft", "ad"}], "untracked": [ids], "deactivated": [ids], "playerinfo": {id: {"privacy", "allowRating", "deactivated", "ratings"}}}` |
| `/elo_b/<ids>` | the same shape with the B ratings (games on non-standard factories, instagib and the like) |
| `/glicko/<ids>` | `{"players": [{"steamid", "active", "<game type>": {"r", "rd", "r_rd", "games"}}], "deactivated": [...]}`; only game types the player has a row for; a player with no rating is left out |

- Ids are joined with a plus sign; the code sets no maximum.
- "elo" is not Elo: it is the Glicko-1 rating `r`, rounded. "games" is the number of rated games in that game type. "rd" is the rating deviation (how unsure: 350 for a new player, never under 30, growing back to 350 over 720 days without games). "r_rd" is `r - rd`.
- **An unknown player and a player with no games both come back from `/elo` as `{"elo": 900, "games": 0}`**: 900 is the starting value, not a rating. Read `games == 0` as "no rating".
- Scale: Glicko-1 on the usual 400-point curve (`q = ln 10 / 400`), start 900 with RD 350, floor 300, at most 150 points a step, one rating period a day. It is the same arithmetic as `plugins/ratings.py`, with another starting number (ours 1500).
- Rate limit in the repository's nginx file: 3 requests a second per address with a burst of 10 on HTTPS; none written for the plain-HTTP exception. No cache on their side.
- `balance.py` (the standard consumer): `http://qlstats.net/elo/` + ids joined by "+", `requests.get` in a `@minqlx.thread`, three attempts, **no timeout**, the result handed back with `@minqlx.next_frame`, a 10-minute cache; an untracked player gets 9999. https://github.com/MinoMino/minqlx-plugins/blob/master/balance.py

Sources for the code facts: https://github.com/PredatH0r/XonStat/blob/master/xonstat/__init__.py , https://github.com/PredatH0r/XonStat/blob/master/xonstat/views/player.py , https://github.com/PredatH0r/XonStat/blob/master/feeder/modules/gamerating.js , https://github.com/PredatH0r/XonStat/blob/master/feeder/modules/glicko1.js

**What a duel rating means there:** only matches won and lost count, not frags (`p.win ? 1 : 0`, a quit is a loss). A rated duel: factory `duel` or `qcon_duel`, two players, at least 595 seconds or a forfeit, not aborted. A rated free-for-all: factory `ffa` or `mg_ffa_classic`, four players or more, frag limit 50 or more, compared pairwise by score per time. (gamerating.js)

## 2. Having our games counted, and a rating for Bobby

**What a server must do:** `zmq_stats_enable 1`, a `zmq_stats_password` (letters and digits: a symbol in it failed this February), the stats port (the game port's number, TCP) open to the internet, then the address and that password entered in one of the panels (`https://qlstats.net/panel1/servers.html` to `panel4`, 340 servers each). QLStats then connects to the server as a listener (user "stats") and reads its match reports. Sources: https://qlstats.net/panel1/servers.html , https://github.com/PredatH0r/XonStat/blob/master/feeder/modules/statsconn.js , https://github.com/PredatH0r/XonStat/blob/master/feeder/modules/webadmin.js , https://www.plusforward.net/quake/post/4487/Install-QLstats-on-Server/ , https://steamcommunity.com/app/282440/discussions/0/3387291961143948215/

**Games with a bot are never rated.** gamerating.js: `botmatch |= p.STEAM_ID == "0" && !pendingSteamAuth;` then `return ERR_BOTMATCH;` (status 4, the whole match, for everyone in it). In the game's stats stream a bot's Steam id is "0", not the 9007199... number minqlx shows: our own record has it (`data\pubtest\testkit.jsonl`, the game's MATCH_STARTED event: `'NAME': 'BobbyBones (BOT)', 'STEAM_ID': '0'`). A second rule would catch him anyway: a match with a player QLStats does not track is not rated (status 12).

**So Bobby cannot have a global rating**, and a person's rating does not move by playing him. Ratings belong to Steam accounts ("Players are identified by their Steam-ID", the privacy policy). Registering our public server would gain nothing (every match on it has a Bobby in it) and would cost something: the matches would be stored at QLStats with the people in them. Not recommended. (Today nothing is reachable anyway: `tools/duel_server.sh` publishes UDP only, and the stats password "lab" in `entrypoint.sh` is in the public repo; it would have to become a secret before any registration.)

## 3. Privacy and terms

- **What a lookup sends:** one HTTPS GET to qlstats.net with the person's 64-bit Steam id in the path. QLStats sees our server's address, the time and the id, so it learns that this account was on our server then. Its policy: addresses may be in log files, kept no longer than 24 hours. https://qlstats.net/account/privacy_policy (last changed 2018-05-16)
- **Is the rating public anyway:** yes, by the policy's own words: "qlstats provides public access to specific personal data: Skill ratings for specific Steam-IDs (used by game server plugins for team composition)". The web pages with a player's matches need a Steam login (the front page says so); the lookup does not.
- **Terms for the API:** none written anywhere I found (legal page, privacy policy, cookie page, README). The operator's address is on the legal page: https://qlstats.net/static/legal.html . Our use is not team balancing but it is the same request at a far lower rate (one or two a person a day).
- **Opting out at QLStats:** after a Steam login a player sets his match history private or public, or "anonymous" ("only your steam-id and current ratings are stored"), or deletes the account (the id is kept 30 days). Rating and the cheater flag are "mandatory" for a tracked player. A deleted account is "untracked": it comes back in the `untracked` list with no rating.
- **What a careful server does:** says it, and gives a switch. A line for the welcome (no percent sign in it): `^3Ratings:^7 I look up your public QLStats rating (your Steam id goes to qlstats.net) to see how strong my opponents are. ^2!qlstats off^7 stops it.` Not legal advice; for players in the EU a salted key with a rating is still personal data, so the file stays private.

## 4. Design for this project (text only)

**(a) The lookup, in `plugins/ladder.py`.**
- Hook `player_loaded` (botctl and the bot plugins use it already). Skip bots (`is_bot`), skip a person who switched it off, skip a key whose stored answer is fresh: 24 hours for an answer, 1 hour after a failure, 30 days for "untracked".
- A function decorated `@minqlx.thread` gets plain values only (the key, the id as a string) and touches nothing of minqlx. It calls `https://qlstats.net/glicko/<id>` (r, rd, games) and `https://qlstats.net/elo/<id>` (status lists, and the fallback if `/glicko` is closed), each with `timeout=(3, 5)`, one attempt, a plain User-Agent naming the project. `requests` is in the image already.
- The result goes back through a function decorated `@minqlx.next_frame`, which alone writes the table (the pattern of balance.py, with the timeout it lacks).
- One request in flight at a time; at a map start the stale ids of everybody present go in one request, joined by "+".
- **Never log the exception's text:** a `requests` error message contains the URL, so the Steam id would land in `minqlx.log`, which `tools/pull_sessions.sh` takes home. Catch everything in the thread and keep the error's class name only.

**(b) What is stored.** In the server's data folder beside `ratings.json` (never in the repo, never the Steam id): `qlstats.json`, the latest answer per anonymous key, `{key: {t, status, duel: {r, rd, games}, ffa: {r, rd, games}, team: true/false}}` with status one of ok, none, untracked, deactivated, error; and `qlstats.jsonl`, every answer appended, so that the PC tool can use the rating a person had when the frags were made. `team` says only whether he has 20 games or more in some team mode (an experienced player with no duel rating). `tools/pull_sessions.sh` must take the two files too. One caution: a row of ratings and game counts is nearly a fingerprint (somebody with the file could find the account at QLStats by trying candidates), so the file is as private as the salt, and anything published is binned or summed.

**(c) The PC tool (`tools/elo.py`, a new section).** Three uses, from the most solid to the least:
1. *Who comes.* The people's QLStats duel ratings (median, range, how many have none), beside their frag share against him. No model, true at once.
2. *His level from duel games.* For every completed duel (mode duel, a game and not warmup, ten minutes) against a person with a duel rating: one Glicko-1 step with QLStats's own constants (start 900, RD 350). This is the rating QLStats would have given him had it counted the games. It needs duel sessions, which the public server (free-for-all with two Bobbys) does not produce: about 10 duels put him within 107 points (one deviation), 20 within 77, 50 within 50, if the opponents are near his level and sure of their own rating.
3. *His level from frags.* Fit Bobby's share of the frags against the person's rating: share = 1 / (1 + 10^(b (r - R50) / 400)), two numbers: R50, the rating at which he takes half, and b, the slope. R50 is the honest statistic, because at half the frags the two are level whatever the slope. The range comes from resampling persons, not frags. With under about six rated persons, or ratings spanning under 300 points, print the table and no fit.

   The caveats, to be printed with the number:
   - **A frag is not a duel.** QLStats rates matches won. A match adds up many frags, so 100 points of QLStats (64 in 100 matches) is only about 53 to 57 in 100 frags (b is about 0.2 to 0.5, to be fitted, not assumed 1). The curve is flat, so a small error in the share is a large error in rating: 400 frags give about 150 to 300 points either way, 4,000 about 50 to 100 (frags come in streaks; `ratings.py` counts one as a quarter of a game for that reason).
   - **Free-for-all and warmup frags are not duel frags.** A third player's damage, spawn frags; in warmup everybody holds every weapon with full ammunition, so item control, most of what a duel rating measures, is absent, and people try things on a bot they would not try in a rated game. `frags.jsonl` has `mode` and `state`: fit them apart, call only the duel-game number a duel level.
   - **Few persons, and chosen by themselves.** Whoever is far better or worse leaves early. R50 is to be trusted only inside the range of the people seen (some above him, some below).
   - **The ratings have their own error.** Use persons with RD 100 or less and 10 duel games or more; an old rating has a large RD; ratings of regions that seldom meet are not on quite the same footing; an account can be a second one. Error in the ratings flattens the fitted slope further.
   - **What "1,350" means** I could not check: the ranking pages need a login. The owner can look his own rating up and judge the scale by it.

**(d) Chat.** `!elo` (own rating, exists) gets a second line: `QLStats: duel 1412 (+-80, 212 games), ffa 1105 (+-120, 40 games)`, or "QLStats has no duel rating for you", or "QLStats did not answer just now". Say "global" and "here, against me" in the two lines: the two numbers are on different footings (ours starts at 1500 and knows only frags with Bobby). Only for the caller himself; `!elo <name>` stays local. `!qlstats off` and `on`: off drops his stored rows and stops the lookups. If the answer is not there yet, fetch in the thread and tell him from the next-frame function, after checking that the same person still sits in that seat.

**(e) Failure modes.**
- Service down, timeout, an answer that is not 200 or not JSON, 503 from the rate limit: status "error", next try in an hour, the game untouched.
- Unknown player or no duel games: `/glicko` leaves him out, `/elo` gives 900 with 0 games. Store "none"; never store 900 as a rating.
- Few games or a large RD: stored, shown, left out of the fit.
- Untracked (deleted his account at QLStats): no rating, no more requests for 30 days.
- Deactivated (QLStats's flag, cheaters among them): stored as status, never shown to others, left out of the fit.
- A plugin reload while a thread runs: the next-frame function checks that the plugin is still loaded.
- QLStats changes or closes the endpoint (it tightened `/games` in 2025): the plugin falls to "error" and the ladder works as before.

## 5. Alternatives

None for duel. If QLStats went away there would be no global Quake Live duel rating in 2026.
- QLRanks (the rating site of the years before Steam): gone; the domain now carries casino pages over archived pictures. http://www.qlranks.com/
- QLLR, "Quake Live Local Ratings" (em92): self-hosted, alive (its instance showed matches of 2026-10-11), team modes only, no duel, one community's servers. https://github.com/em92/quakelive-local-ratings , http://stats.eugene2molotov.ru/matches/
- Zipnar's Quake Live: one community's own servers in Texas, with a duel ladder of its own, no API mentioned. https://zipnar.duckdns.org/quake-stats/ratings.html
- Without any service: ask a person for his rating in chat, or use the local ladder alone.

## What is uncertain

- **The live answer was not looked at.** Neither project documents an example id, so `/elo` and `/glicko` were not called. Their shape is from the source at GitHub, and production can differ (they backport from it). `/glicko` in particular is used by no plugin I know and may be closed. The owner can settle it in ten seconds with his own id in a browser: `https://qlstats.net/glicko/<his id>` and `/elo/<his id>`.
- Whether a never-seen id gets a row at once (the feeder calls a database function `getOrCreatePlayer` whose body I did not read), and exactly who is "untracked".
- The rate limit is the repository's file, not a promise; there are no API terms. A short mail to the operator before a research use would be the careful step: the owner's decision.
- The slope between frag share and QLStats points (b) is my estimate from the arithmetic of a match, not a measurement.
- The Steam thread on connecting a server shows no year; I read it as 2026.
- The privacy part is a reading of their policy, not legal advice.
