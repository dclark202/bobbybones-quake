# Map pool

The owner's pick of the game's duel and small free-for-all maps (2026-10-06), for the map reader (B-104) and
multi-map training. All are in the game's `pak00.pk3`; `tools/extract_maps.py` copies them to `data/maps/` and
`sim/build_nav.py --map <name>` builds a walking map (system Python). Maps with lifts (`func_plat`) are left out of
training until the simulator has movers; doors count as open; niche weapons as "other item".

- aerowalk
- almostlost
- arcanecitadel
- arkinholm
- asylum
- battleforged
- bitterembrace
- blackcathedral
- bloodlust
- bloodrun
- campgrounds
- cannedheat
- chemicalreaction
- corrosion
- cure
- deepinside
- delirium
- demonkeep
- devilish
- dismemberment
- dredwerkz
- eviscerated
- fatalinstinct
- foolishlegacy
- furiousheights
- grimdungeons
- hektik
- hellsgate
- heroskeep
- hiddenfortress
- innersanctums
- leviathan
- limbus
- longestyard
- lostworld
- namelessplace
- overgrowth
- overkill
- purgatory
- quarantine
- realmofsteelrats
- repent
- retribution
- satanic
- scornforge
- servitude
- shakennotstirred
- silence
- sinister
- solarium
- spacechamber
- terminalheights
- terminus
- theedge
- threestory
- tornado
- toxicity
- trinity
- useandabuse
- verticalvengeance
- warehouse
- wargrounds

## What they contain (entity scan, 2026-10-06)

| Map | Lifts | Doors | Moving parts | Niche weapons | Spawns |
|---|---|---|---|---|---|
| aerowalk | 0 | 0 | 0 | 0 | 8 |
| almostlost | 0 | 0 | 0 | 1 | 19 |
| arcanecitadel | 0 | 8 | 1 | 0 | 18 |
| arkinholm | 0 | 4 | 6 | 0 | 16 |
| asylum | 0 | 0 | 0 | 1 | 17 |
| battleforged | 0 | 0 | 3 | 0 | 9 |
| bitterembrace | 0 | 0 | 0 | 1 | 8 |
| blackcathedral | 0 | 0 | 0 | 1 | 32 |
| bloodlust | 0 | 16 | 0 | 0 | 22 |
| bloodrun | 0 | 0 | 0 | 0 | 10 |
| campgrounds | 0 | 0 | 0 | 0 | 27 |
| cannedheat | 0 | 0 | 0 | 0 | 8 |
| chemicalreaction | 0 | 1 | 0 | 1 | 20 |
| corrosion | 0 | 0 | 15 | 1 | 18 |
| cure | 0 | 1 | 2 | 0 | 12 |
| deepinside | 0 | 0 | 0 | 0 | 27 |
| delirium | 3 | 0 | 4 | 0 | 10 |
| demonkeep | 0 | 0 | 0 | 2 | 18 |
| devilish | 0 | 0 | 2 | 1 | 17 |
| dismemberment | 0 | 0 | 0 | 0 | 6 |
| dredwerkz | 0 | 0 | 0 | 3 | 20 |
| eviscerated | 0 | 0 | 2 | 0 | 23 |
| fatalinstinct | 0 | 0 | 0 | 0 | 15 |
| foolishlegacy | 0 | 3 | 0 | 1 | 28 |
| furiousheights | 0 | 0 | 0 | 0 | 16 |
| grimdungeons | 0 | 8 | 0 | 1 | 19 |
| hektik | 0 | 0 | 2 | 0 | 10 |
| hellsgate | 0 | 0 | 0 | 0 | 11 |
| heroskeep | 0 | 0 | 0 | 0 | 11 |
| hiddenfortress | 0 | 0 | 0 | 0 | 18 |
| innersanctums | 0 | 0 | 0 | 2 | 21 |
| leviathan | 0 | 6 | 2 | 1 | 20 |
| limbus | 0 | 6 | 2 | 0 | 19 |
| longestyard | 0 | 0 | 0 | 0 | 16 |
| lostworld | 0 | 0 | 0 | 0 | 18 |
| namelessplace | 0 | 0 | 0 | 1 | 9 |
| overgrowth | 0 | 0 | 0 | 0 | 2 |
| overkill | 0 | 0 | 0 | 1 | 32 |
| purgatory | 0 | 0 | 2 | 1 | 18 |
| quarantine | 0 | 0 | 2 | 1 | 19 |
| realmofsteelrats | 0 | 0 | 0 | 1 | 17 |
| repent | 0 | 9 | 57 | 2 | 29 |
| retribution | 0 | 2 | 0 | 1 | 19 |
| satanic | 0 | 4 | 0 | 1 | 0 |
| scornforge | 0 | 0 | 0 | 2 | 17 |
| servitude | 0 | 0 | 0 | 0 | 22 |
| shakennotstirred | 0 | 0 | 1 | 1 | 28 |
| silence | 0 | 2 | 4 | 0 | 12 |
| sinister | 0 | 0 | 4 | 0 | 11 |
| solarium | 0 | 2 | 7 | 0 | 9 |
| spacechamber | 0 | 0 | 0 | 1 | 33 |
| terminalheights | 0 | 0 | 7 | 1 | 14 |
| terminus | 1 | 11 | 4 | 0 | 18 |
| theedge | 2 | 0 | 4 | 2 | 29 |
| threestory | 0 | 0 | 0 | 0 | 11 |
| tornado | 0 | 5 | 2 | 0 | 16 |
| toxicity | 0 | 0 | 7 | 0 | 8 |
| trinity | 0 | 0 | 4 | 1 | 31 |
| useandabuse | 0 | 0 | 4 | 0 | 8 |
| verticalvengeance | 0 | 12 | 0 | 0 | 12 |
| warehouse | 0 | 5 | 17 | 2 | 37 |
| wargrounds | 0 | 4 | 2 | 1 | 16 |
