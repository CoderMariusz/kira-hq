#!/usr/bin/env bash
# scripts/snapshot.sh — PRD §6.7
#
# Daily snapshot of every project's .taskmaster/ into
# ~/.kira-hq/snapshots/<YYYY-MM-DD>/<project>/ with rsync --link-dest
# hardlink dedup vs yesterday, and a 7-day rolling window.
#
# Usage:
#   snapshot.sh                 # real run
#   snapshot.sh --dry-run       # show what would happen, no writes
#   SNAPSHOT_ROOT=<dir> snapshot.sh   # override destination root
#   PROJECTS_ROOT=<dir>               # override source root
#   SNAPSHOT_KEEP=<N>                 # override retention (default: 7)

set -euo pipefail

PROJECTS_ROOT="${PROJECTS_ROOT:-$HOME/Projects}"
SNAPSHOT_ROOT="${SNAPSHOT_ROOT:-$HOME/.kira-hq/snapshots}"
SNAPSHOT_KEEP="${SNAPSHOT_KEEP:-7}"
DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; fi

TODAY="$(date +%F)"
# Portable yesterday (BSD/macOS `-v-1d`, GNU `-d "yesterday"`)
if date -v-1d +%F >/dev/null 2>&1; then
  YDAY="$(date -v-1d +%F)"
else
  YDAY="$(date -d 'yesterday' +%F)"
fi

DEST="$SNAPSHOT_ROOT/$TODAY"
LINKDEST=""
if [ -d "$SNAPSHOT_ROOT/$YDAY" ]; then
  LINKDEST="--link-dest=$SNAPSHOT_ROOT/$YDAY"
fi

say() { echo "[snapshot] $*"; }
run() {
  if [ "$DRY_RUN" = "1" ]; then
    printf 'DRY:'
    while [ "$#" -gt 0 ]; do
      printf ' %q' "$1"
      shift
    done
    printf '\n'
  else
    "$@"
  fi
}

say "today=$TODAY yday=$YDAY dest=$DEST linkdest=${LINKDEST:-<none>}"
run mkdir -p "$DEST"

# Iterate sibling project directories
shopt -s nullglob 2>/dev/null || true
copied=0
for p in "$PROJECTS_ROOT"/*/; do
  name="$(basename "$p")"
  if [ ! -d "$p/.taskmaster" ]; then
    continue
  fi
  rsync_args=(rsync -a)
  if [ -n "$LINKDEST" ]; then
    rsync_args+=("$LINKDEST")
  fi
  run "${rsync_args[@]}" "$p/.taskmaster/" "$DEST/$name/"
  copied=$((copied + 1))
  say "  + $name"
done
say "snapshotted $copied project(s) into $DEST"

# Rolling retention — delete everything older than the newest N dirs.
# `ls -1t` sorts newest-first; keep head N, nuke the rest.
# Uses awk instead of `mapfile` (macOS bash 3.2 lacks mapfile).
if [ -d "$SNAPSHOT_ROOT" ]; then
  olds="$(ls -1t "$SNAPSHOT_ROOT" 2>/dev/null \
    | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' \
    | awk -v keep="$SNAPSHOT_KEEP" 'NR > keep { print }' || true)"
  if [ -n "$olds" ]; then
    while IFS= read -r old; do
      [ -n "$old" ] || continue
      run rm -rf "$SNAPSHOT_ROOT/$old"
      say "  - pruned $old"
    done <<< "$olds"
  fi
fi

say "done"
