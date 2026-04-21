#!/usr/bin/env bash
# tests/integration/test_snapshot_rotation.sh — PRD §6.7
#
# Exercises snapshot.sh end-to-end in an isolated tmp layout:
#   - creates a fake PROJECTS_ROOT with 2 projects (one with .taskmaster/)
#   - runs snapshot.sh → expect today's dir created with project contents
#   - seeds 8 fake dated snapshot dirs
#   - runs snapshot.sh again → expect retention prunes oldest (7 remain)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SNAP_SH="$REPO_ROOT/scripts/snapshot.sh"
[ -x "$SNAP_SH" ] || chmod +x "$SNAP_SH"

TMP="$(mktemp -d -t kira-hq-snap-XXXX)"
trap 'rm -rf "$TMP"' EXIT

PROJECTS="$TMP/Projects"
SNAPS="$TMP/snapshots"
mkdir -p "$PROJECTS/alpha/.taskmaster/tasks"
echo '{"master":{"tasks":[{"id":"1","title":"T"}]}}' \
  > "$PROJECTS/alpha/.taskmaster/tasks/tasks.json"
mkdir -p "$PROJECTS/no-tm"   # no .taskmaster → must be skipped

export PROJECTS_ROOT="$PROJECTS"
export SNAPSHOT_ROOT="$SNAPS"
export SNAPSHOT_KEEP="7"

# --- Assertion 1: first run copies alpha, skips no-tm ---------------------
bash "$SNAP_SH" >/dev/null
TODAY="$(date +%F)"
[ -d "$SNAPS/$TODAY/alpha" ] || { echo "FAIL: alpha not snapshotted" >&2; exit 1; }
[ -f "$SNAPS/$TODAY/alpha/tasks/tasks.json" ] || {
  echo "FAIL: tasks.json not snapshotted" >&2; exit 1; }
[ ! -d "$SNAPS/$TODAY/no-tm" ] || {
  echo "FAIL: no-tm should have been skipped" >&2; exit 1; }
echo "OK: first run snapshotted alpha, skipped no-tm"

# --- Assertion 2: retention prunes oldest when >7 dirs --------------------
# Seed 8 fake past-dated snapshot dirs (distinct dates to survive sort).
for i in 10 11 12 13 14 15 16 17; do
  mkdir -p "$SNAPS/2024-01-$i/alpha"
  touch "$SNAPS/2024-01-$i/alpha/tasks.json"
  # Set dir mtime so `ls -1t` orders them: 2024-01-{10..17} → mtime same.
  # Format YYYYMMDDhhmm (12 digits). Earlier ${i:1} was a bug: it stripped
  # the leading digit, producing invalid "202401000000" for i=10 and
  # collapsing 11..17 to 01..07, which inverted the intended ordering and
  # left 2024-01-10 looking 'newest' on Linux (GNU touch is strict).
  touch -t "202401${i}0000" "$SNAPS/2024-01-$i" 2>/dev/null \
    || touch -d "2024-01-$i" "$SNAPS/2024-01-$i"
done

bash "$SNAP_SH" >/dev/null

# Count YYYY-MM-DD dirs remaining
count="$(ls -1 "$SNAPS" | grep -Ec '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' || true)"
[ "$count" -le 7 ] || { echo "FAIL: retention left $count dirs (>7)" >&2; exit 1; }

# The oldest of the seeded dirs (2024-01-10) must be pruned
[ ! -d "$SNAPS/2024-01-10" ] || {
  echo "FAIL: oldest snapshot 2024-01-10 not pruned" >&2; exit 1; }
echo "OK: retention kept $count dirs (≤7), pruned oldest"

# --- Assertion 3: hostile project names do not execute during rsync ----------
HOSTILE='evil$(touch pwned-marker)'
mkdir -p "$PROJECTS/$HOSTILE/.taskmaster/tasks"
echo '{"master":{"tasks":[{"id":"9","title":"hostile"}]}}' \
  > "$PROJECTS/$HOSTILE/.taskmaster/tasks/tasks.json"
rm -f "$TMP/pwned-marker"

( cd "$TMP" && bash "$SNAP_SH" >/dev/null )

[ ! -e "$TMP/pwned-marker" ] || {
  echo "FAIL: hostile project name executed during snapshot" >&2; exit 1; }
[ -f "$SNAPS/$TODAY/$HOSTILE/tasks/tasks.json" ] || {
  echo "FAIL: hostile project name was not copied literally" >&2; exit 1; }
echo "OK: hostile project names are copied literally without execution"

# --- Assertion 4: re-running is idempotent (same day, no errors) ----------
bash "$SNAP_SH" >/dev/null
echo "OK: re-run on same day idempotent"

echo "all assertions passed"
