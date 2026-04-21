#!/usr/bin/env bash
# scripts/restore_snapshot.sh — PRD §6.7
#
# Restores a project's .taskmaster/ directory from a dated snapshot.
# Safety-first: shows a dry-run diff, then prompts y/N before writing.
#
# Usage:
#   restore_snapshot.sh <project> <date>
#   restore_snapshot.sh kira-hq 2026-04-18
#   FORCE=1 restore_snapshot.sh kira-hq 2026-04-18    # skip prompt
#   SNAPSHOT_ROOT=<dir> PROJECTS_ROOT=<dir>          # override paths

set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }

[ "$#" -eq 2 ] || die "usage: restore_snapshot.sh <project> <date-YYYY-MM-DD>"
PROJECT="$1"
DATE="$2"

PROJECTS_ROOT="${PROJECTS_ROOT:-$HOME/Projects}"
SNAPSHOT_ROOT="${SNAPSHOT_ROOT:-$HOME/.kira-hq/snapshots}"

SRC="$SNAPSHOT_ROOT/$DATE/$PROJECT"
DST="$PROJECTS_ROOT/$PROJECT/.taskmaster"

[ -d "$SRC" ] || die "snapshot not found: $SRC"
[ -d "$PROJECTS_ROOT/$PROJECT" ] || die "project not found: $PROJECTS_ROOT/$PROJECT"

echo "=== restore plan ==="
echo "  source : $SRC"
echo "  target : $DST"
echo "=== dry-run diff ==="
rsync -an --delete "$SRC/" "$DST/" | sed 's/^/  /'
echo "===================="

if [ "${FORCE:-0}" = "1" ]; then
  reply=y
else
  printf "Proceed with restore? [y/N] "
  read -r reply
fi
case "$reply" in
  y|Y|yes|YES) ;;
  *) echo "aborted."; exit 1 ;;
esac

# Move current .taskmaster aside as a safety net, then rsync.
if [ -d "$DST" ]; then
  backup="$DST.pre-restore.$(date +%s)"
  mv "$DST" "$backup"
  echo "moved current state to: $backup"
fi
mkdir -p "$DST"
rsync -a --delete "$SRC/" "$DST/"
echo "restored $PROJECT from snapshot $DATE"
