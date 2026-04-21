#!/usr/bin/env bash
# scripts/run-api.sh — start Kira-HQ Module 2 FastAPI on 127.0.0.1:3100
#
# PRD §4 Module 2.
#
# Usage:
#   scripts/run-api.sh              # dev mode (--reload on)
#   scripts/run-api.sh --prod       # no reload (uvicorn default)
#   scripts/run-api.sh --port 3200  # override port
#   scripts/run-api.sh <any-uvicorn-flag>...  # passed through verbatim
#
# Env vars:
#   KIRA_HQ_API_PORT — override port (default 3100)
#   KIRA_HQ_API_HOST — override host (default 127.0.0.1)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

VENV_PY="$REPO_ROOT/.venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "FAIL: missing $VENV_PY — run \`uv venv && uv pip install -e .\` first" >&2
  exit 1
fi

HOST="${KIRA_HQ_API_HOST:-127.0.0.1}"
PORT="${KIRA_HQ_API_PORT:-3100}"

# Default to dev reload unless caller says --prod or passes their own args.
RELOAD_ARG="--reload"
if [ "${1:-}" = "--prod" ]; then
  RELOAD_ARG=""
  shift
fi

# Strip the 4 RangeError-trigger env vars (PRD §6.4) so subprocess
# `task-master list --json` does not crash inside nested Claude sessions.
exec env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
         -u CLAUDE_CODE_EXECPATH -u ANTHROPIC_API_KEY \
  PYTHONPATH="$REPO_ROOT/src" "$VENV_PY" -m uvicorn \
  kira_hq.api.app:app \
  --host "$HOST" --port "$PORT" \
  $RELOAD_ARG "$@"
