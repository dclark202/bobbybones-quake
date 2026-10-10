#!/bin/bash
# Daily housekeeping of the public server's logs (owner, 2026-10-07): every finished session is packed on the server,
# copied to this PC, checked, and only then removed from the server; old server images are cleared.
#   bash tools/pull_sessions.sh                 (run by the scheduled task "BobbyBones session pull")
#   SESSION_ARCHIVE=/t/quake-sessions/public    where the archives go (default; T: is the big drive)
# The newest session is the live one and is left alone. Nothing is removed that did not arrive with the same checksum.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
HOST="$(grep '^PUBLIC_HOST=' data/owner.env 2>/dev/null | cut -d= -f2)"
[ -n "$HOST" ] || { echo "add PUBLIC_HOST=root@<address> to data/owner.env"; exit 1; }
DEST="${SESSION_ARCHIVE:-/t/quake-sessions/public}"
mkdir -p "$DEST" || { echo "cannot write to $DEST (is the drive there?)"; exit 1; }
R=bobbybones-quake/data/duellive
SSH="ssh -o BatchMode=yes -o ConnectTimeout=20"
{
echo "== $(date '+%Y-%m-%d %H:%M:%S')"
# 0. the leaderboard (plugins/ladder.py): today's table and the frag log are copied, never removed (tools/elo.py reads them)
scp -o BatchMode=yes -q "$HOST:$R/ratings.json" "$HOST:$R/frags.jsonl" "$DEST/" 2>/dev/null && cp "$DEST/ratings.json" "$DEST/ratings_$(date +%Y%m%d).json" && echo "leaderboard copied: $(grep -c . "$DEST/frags.jsonl") frags"
# 1. pack every session but the newest one; list the archives with their checksums
$SSH "$HOST" "cd $R && mkdir -p archive && live=\$(ls sessions | tail -1) && for s in \$(ls sessions); do [ \"\$s\" = \"\$live\" ] && continue; [ -f archive/\$s.tar.gz ] || tar czf archive/\$s.tar.gz -C sessions \$s; done; cd archive && ls *.tar.gz >/dev/null 2>&1 && sha256sum *.tar.gz" > "$DEST/.remote.sha" || { echo "the server did not answer"; exit 1; }
n=$(grep -c . "$DEST/.remote.sha")
[ "$n" -gt 0 ] || { echo "nothing new"; exit 0; }
# 2. copy them
scp -o BatchMode=yes -q "$HOST:$R/archive/*.tar.gz" "$DEST/" || { echo "copy failed; nothing removed"; exit 1; }
# 3. check each one, and remove from the server only what arrived intact
ok=""; bad=0
while read -r sum name; do
    name="${name#\*}"
    if [ "$(sha256sum "$DEST/$name" 2>/dev/null | cut -d' ' -f1)" = "$sum" ]; then ok="$ok ${name%.tar.gz}"; else bad=$((bad + 1)); echo "checksum differs, kept on the server: $name"; fi
done < "$DEST/.remote.sha"
[ -n "$ok" ] && $SSH "$HOST" "cd $R && for s in $ok; do rm -rf sessions/\$s archive/\$s.tar.gz; done; docker image prune -f >/dev/null 2>&1; df -h / | tail -1"
echo "pulled $(echo $ok | wc -w) sessions to $DEST ($bad kept back); archive now $(du -sh "$DEST" | cut -f1) in $(ls "$DEST"/*.tar.gz | wc -l) files"
} 2>&1 | tee -a "$DEST/pull.log"
