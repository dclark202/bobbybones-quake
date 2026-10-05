# Map atlas

One file per map with what a good player knows about it, kept outside the network so it can be read, checked and
corrected: `maps/atlas/<map>.json`, with a picture `maps/atlas/<map>.png`. Built by `tools/build_atlas.py` from
the route graph, the simulator (line of sight) and the parsed pro demos.

```bash
python tools/build_atlas.py --maps bloodrun,aerowalk,campgrounds    # Anaconda Python (needs the simulator)
python tools/build_atlas.py --picture                                # pictures only (any Python with matplotlib)
```

| Map | Spots | Areas | Big items | Pro demos | Pro trips | Routes per (area, item) |
|---|---|---|---|---|---|---|
| Blood Run | 1185 | 26 | 10 | 224 | 81,084 | 2.8 |
| Aerowalk | 906 | 20 | 11 | 148 | 45,885 | 2.7 |
| Campgrounds | 1643 | 32 | 12 | 0 (the six demos are not parsed yet) | 0 | 2.7 |

## Contents of the file

| Field | Meaning |
|---|---|
| `areas[]` | The map cut into areas (clusters of route-graph spots; height counts 2.5 times as much as horizontal distance). `id`, `name` (the big items in it, or the nearest one), `centre`, `height`, `exposure` (share of nearby spots that can see it), `to` (neighbouring areas), `pro_time_share` (share of time pro players spend there), `reachable` |
| `items[]` | Big items (armors, mega health, weapons): `name`, `pos`, `respawn` (s), `area` |
| `routes["<area id>><item>"][]` | Several distinct routes from that area to that item, best preference first |
| route: `areas` | The areas it passes, in order |
| route: `nodes` | The spots of the route on the route graph (`null` for routes only seen in pro play) |
| route: `time`, `pro_time` | Seconds on the route graph (from the area's centre); median seconds pros took |
| route: `exposure` | Mean exposure along the way |
| route: `pro_n`, `source` | How many pro trips took it; `graph` (found by the search) or `pro` (taken by pros, not proposed by the search) |
| route: `pref` | Preference. **Seeded** from the pro counts; to be **learned** from Bobby's own results |
| route: `bobby` | His own record on this route: `tries`, `arrived`, `time`, `damage` (empty until the atlas is used in training) |
| `node_area`, `node_exposure` | Area and exposure of every route-graph spot |
| `teleporters`, `jump_pads` | From the map's triggers |

## How routes are found

- **Graph:** the fastest route, then alternatives by making the edges of kept routes slower and searching again.
  An alternative is kept if it takes at most 1.6 times the fastest (plus a second), shares under 60% of its spots
  with every kept route and passes a different list of areas. Up to four.
- **Pro demos:** a trip ends when the followed player arrives at a big item's spot (whether or not the item was
  there) and starts at his previous arrival, his death, or 15 s earlier. Every area on the way also counts as the
  start of a route. A trip is credited to the graph route it overlaps most (60% of areas or more); trips that fit
  none and occur at least three times (and in 5% of the trips for that pair) become routes with source `pro`.
- No player names are stored.

## Known weak points (first version)

- Areas are cut by a clustering of spots, not by rooms; names are only "which item is near". Floors overlap in the
  top-down picture.
- "Arrived at the item's spot" is not "picked the item up".
- Routes with source `pro` have no spot list yet (some are jumps the route graph does not contain, for example
  Blood Run area 22 to the red armor in 0.6 s).
- Graph times start at the area's centre, pro times where the player entered the area: they are not the same thing.
- Campgrounds has no pro seed; `bobbylab` has no atlas (it is a test map).
- Nothing reads the atlas yet: the network inputs (B-72) and the learned preferences (B-75) come with the next
  training batch.
