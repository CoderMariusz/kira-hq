#!/usr/bin/env bash
set -euo pipefail

# Neutral/shared repo shim for Claude -> Hermes(worker) -> OpenRouter/Qwen.
# This intentionally reuses Hermes's own OpenRouter route instead of inventing a
# second OpenRouter client inside Claude/Kira-HQ.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}"
exec python -m kira_hq.cli.main delegate-worker "$@"
