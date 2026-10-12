#!/bin/bash
# Daily housekeeping of the public server's data (owner, 2026-10-07; this routine 2026-10-11): everything a day of play
# leaves on the server comes to this PC, is checked, and only then leaves the server.
#   bash tools/pull_sessions.sh                 (run by the scheduled task "BobbyBones session pull", 09:30 every day)
#   SESSION_ARCHIVE=/t/quake-sessions/public    where it all goes (default; T: is the big drive)
#   SESSION_MIRROR=/e/quake-sessions/public     a second copy on another disk (default; "-" for none)
#   KEEP_DAYS=7                                 how long a session's archive also stays on the server (owner: 7)
# What goes where:
#   sessions   every finished one is packed on the server, copied, checksum-compared and test-read; its folder is then
#              removed there and its archive stays on the server for KEEP_DAYS as a second copy (sessions carry no names
#              or ids). The newest session is the live one and is left alone: the free-for-all plugin begins a new one a
#              minute after the last person has gone, so a visit is never the newest for long.
#   raw logs   server.log, duelbot.log, minqlx.log, duel_live.jsonl: packed, copied to logs/, checked, and removed from
#              the server the same day (they hold visitors' Steam ids and addresses; they never go into the repo).
#   leaderboard and bans   copied every day, never removed: ratings.json, frags.jsonl, duels.jsonl (finished duels), the
#              QLStats answers by anonymous key (qlstats.json, qlstats.jsonl, qlstats_off.json; only on a server started
#              with QLSTATS=1), bans.txt, and salt.txt: the file that makes a person's key the same over time. The
#              salt and the QLStats files are as private as the bans: they stay in the archive, never in the repo.
#   index      sessions.csv, a row per session (tools/session_index.py).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
HOST="$(grep '^PUBLIC_HOST=' data/owner.env 2>/dev/null | cut -d= -f2)"
[ -n "$HOST" ] || { echo "add PUBLIC_HOST=root@<address> to data/owner.env"; exit 1; }
DEST="${SESSION_ARCHIVE:-/t/quake-sessions/public}"
MIRROR="${SESSION_MIRROR:-/e/quake-sessions/public}"
KEEP="${KEEP_DAYS:-7}"
mkdir -p "$DEST/logs" || { echo "cannot write to $DEST (is the drive there?)"; exit 1; }
R=bobbybones-quake/data/duellive
SSH="ssh -o BatchMode=yes -o ConnectTimeout=20"
SCP="scp -o BatchMode=yes -o ConnectTimeout=20 -q"
sum_of() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1; }
{
echo "== $(date '+%Y-%m-%d %H:%M:%S')"
# 0. the leaderboard (plugins/ladder.py) and the bans: copied, never removed (tools/elo.py reads the first two)
$SCP "$HOST:$R/ratings.json" "$HOST:$R/frags.jsonl" "$DEST/" 2>/dev/null && cp "$DEST/ratings.json" "$DEST/ratings_$(date +%Y%m%d).json" && echo "leaderboard copied: $(grep -c . "$DEST/frags.jsonl") frags"
$SCP "$HOST:$R/bans.txt" "$DEST/" 2>/dev/null
# the salt of the anonymous keys (plugins/ladder.py key()): with it a key can be made again for the same person, e.g. on a
# local play-test server; it never goes into the repo. A changed salt would cut every person's history in two: say so.
$SCP "$HOST:$R/salt.txt" "$DEST/salt.txt.new" 2>/dev/null && { if [ -f "$DEST/salt.txt" ] && ! cmp -s "$DEST/salt.txt" "$DEST/salt.txt.new"; then cp "$DEST/salt.txt" "$DEST/salt_before_$(date +%Y%m%d).txt"; echo "THE SERVER'S SALT CHANGED: the keys from today are other keys (the old salt kept beside it)"; fi; mv "$DEST/salt.txt.new" "$DEST/salt.txt"; }
# finished duels and the QLStats answers (keys only; the last three exist only where the lookup is switched on)
for f in duels.jsonl qlstats.json qlstats.jsonl qlstats_off.json; do $SCP "$HOST:$R/$f" "$DEST/" 2>/dev/null; done

# 1. the raw logs: copied aside and emptied in one step on the server (the writers keep their files open), packed
$SSH "$HOST" "cd $R && mkdir -p logs_out && st=\$(date -u +%Y%m%d-%H%M%S) && mkdir logs_out/\$st && \
  for f in server.log duelbot.log minqlx.log duel_live.jsonl; do [ -s \$f ] && cp \$f logs_out/\$st/ && : > \$f; done; \
  for f in minqlx.log.* *_stuck.log; do [ -f \$f ] && mv \$f logs_out/\$st/; done; \
  if [ -n \"\$(ls logs_out/\$st)\" ]; then tar czf logs_out/logs_\$st.tar.gz -C logs_out \$st && rm -r logs_out/\$st; else rmdir logs_out/\$st; fi; \
  cd logs_out && ls *.tar.gz >/dev/null 2>&1 && sha256sum *.tar.gz" > "$DEST/.remote_logs.sha" 2>/dev/null
okl=""
if [ -s "$DEST/.remote_logs.sha" ]; then
    $SCP "$HOST:$R/logs_out/*.tar.gz" "$DEST/logs/" || echo "log copy failed; kept on the server"
    while read -r sum name; do
        name="${name#\*}"
        if [ "$(sum_of "$DEST/logs/$name")" = "$sum" ] && tar tzf "$DEST/logs/$name" >/dev/null 2>&1; then okl="$okl $name"; else echo "log archive differs, kept on the server: $name"; fi
    done < "$DEST/.remote_logs.sha"
    [ -n "$okl" ] && printf '%s\n' $okl | $SSH "$HOST" "cd $R/logs_out && while read -r n; do rm -f \"\$n\"; done"
fi
echo "raw logs: $(echo $okl | wc -w) archives to $DEST/logs, removed from the server"

# 2. pack every session but the newest one (once); list all archives on the server with their checksums
$SSH "$HOST" "cd $R && mkdir -p archive && live=\$(ls sessions | tail -1) && for s in \$(ls sessions); do [ \"\$s\" = \"\$live\" ] && continue; [ -f archive/\$s.tar.gz ] || tar czf archive/\$s.tar.gz -C sessions \$s; done; cd archive && ls *.tar.gz >/dev/null 2>&1 && sha256sum *.tar.gz" > "$DEST/.remote.sha" 2>/dev/null
n=$(grep -c . "$DEST/.remote.sha")
if [ "$n" -gt 0 ]; then
    # 3. copy the ones this PC does not have yet (an archive stays on the server for $KEEP days: most are here already)
    new=0
    while read -r sum name; do
        name="${name#\*}"
        [ "$(sum_of "$DEST/$name")" = "$sum" ] && continue
        $SCP "$HOST:$R/archive/$name" "$DEST/" </dev/null && new=$((new + 1))
    done < "$DEST/.remote.sha"
    # 4. check each one (same checksum, readable); what is safe here loses its folder on the server, and its archive
    #    there once that is older than $KEEP days
    ok=""; bad=0
    while read -r sum name; do
        name="${name#\*}"
        if [ "$(sum_of "$DEST/$name")" = "$sum" ] && tar tzf "$DEST/$name" >/dev/null 2>&1; then ok="$ok ${name%.tar.gz}"; else bad=$((bad + 1)); echo "not safe here yet, kept on the server: $name"; fi
    done < "$DEST/.remote.sha"
    [ -n "$ok" ] && printf '%s\n' $ok | $SSH "$HOST" "cd $R && while read -r s; do rm -rf \"sessions/\$s\"; [ -n \"\$(find \"archive/\$s.tar.gz\" -mtime +$KEEP 2>/dev/null)\" ] && rm -f \"archive/\$s.tar.gz\"; done; echo \"on the server: \$(ls archive | wc -l) archives (\$(du -sh archive | cut -f1)), \$(ls sessions | wc -l) session folders\"; docker image prune -f >/dev/null 2>&1; df -h / | tail -1"
    echo "sessions: $new new, $(echo $ok | wc -w) safe here, $bad kept back; archive now $(du -sh "$DEST" | cut -f1) in $(ls "$DEST"/*.tar.gz | wc -l) files"
else
    echo "sessions: nothing on the server"
fi

# 5. the index (a row per session) and the second copy
python tools/session_index.py "$DEST" 2>&1 | tail -1
if [ "$MIRROR" != "-" ]; then
    if mkdir -p "$MIRROR" 2>/dev/null && cp -ru "$DEST/." "$MIRROR/"; then echo "second copy: $MIRROR ($(ls "$MIRROR"/*.tar.gz 2>/dev/null | wc -l) session archives)"; else echo "SECOND COPY FAILED: $MIRROR"; fi
fi
} 2>&1 | tee -a "$DEST/pull.log"
