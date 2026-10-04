# Legacy: the first BobbyBones

The first approach (2026-10-01 to 10-02): a hand-built layer on top of the game's Nightmare bot. Item routes on a
recorded nav graph, fair aim, a settings search ("coach") over the bot's character files, and a training
cluster of game servers. It did not beat plain Nightmare (6% win rate against a control group at 69%) and was
dropped for learning in a simulator. What happened is in [../docs/RESULTS.md](../docs/RESULTS.md).

Nothing here is used by the current bot. It is kept for reference: `plugins/` (lab, itemrun, bobby, practice,
jumplab), `tools/` (cluster, coach, nightly runs, nav graph builder, analysis and renderers), `maps/` (recorded
Campgrounds nav data), `docs/`.
