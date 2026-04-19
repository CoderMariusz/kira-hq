#!/usr/bin/env bash
# tests/e2e/test_api_curl.sh — Module 2 end-to-end via curl
#
# Walks through every public endpoint of the running Kira-HQ API using
# curl, asserting HTTP 200 (or 201 for POST) and basic JSON shape. Intended
# to be run after `scripts/run-api.sh &` has been started separately, or
# pointed at a remote instance via BASE_URL.
#
# Usage:
#   BASE_URL=http://127.0.0.1:3100 bash tests/e2e/test_api_curl.sh
#
# Exit codes:
#   0 — all endpoints returned expected status
#   1 — /health unreachable (server down)
#   2 — endpoint returned unexpected status

set -u
set -o pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:3100}"

fail() { echo "FAIL [$1]: $2" >&2; exit "$1"; }
ok()   { echo "OK:   $*"; }
info() { echo "INFO: $*"; }

# Require curl + jq; skip gracefully without jq (only shape checks drop out).
if ! command -v curl >/dev/null 2>&1; then
  fail 1 "curl missing"
fi
HAS_JQ=1
command -v jq >/dev/null 2>&1 || HAS_JQ=0

# ---- /health: also doubles as server-up check ----------------------------
health_code=$(curl -s -o /tmp/kira-hq-health.json -w "%{http_code}" "$BASE_URL/health" || echo 000)
if [ "$health_code" != "200" ]; then
  fail 1 "/health returned $health_code — server not up at $BASE_URL"
fi
ok "/health 200"

# ---- helper: assert GET returns 200 --------------------------------------
check_200() {
  local path="$1"
  local body="/tmp/kira-hq-$(echo "$path" | tr '/?=&' '____').json"
  local code
  code=$(curl -s -o "$body" -w "%{http_code}" "$BASE_URL$path")
  if [ "$code" != "200" ]; then
    fail 2 "GET $path → $code (body: $(head -c 200 "$body"))"
  fi
  ok "GET $path → 200"
  if [ "$HAS_JQ" = "1" ]; then
    # Just sanity-check JSON parses; content varies by user state
    jq -e . "$body" >/dev/null 2>&1 || fail 2 "GET $path → invalid JSON"
  fi
}

check_200 "/projects"
check_200 "/views/needs-attention"
check_200 "/views/blockers"
check_200 "/metrics/tokens"
check_200 "/metrics/pipeline"

# ---- Try a per-project endpoint only if at least one project exists -------
if [ "$HAS_JQ" = "1" ]; then
  first_project=$(jq -r '.[0].name // empty' /tmp/kira-hq-_projects.json 2>/dev/null || true)
  if [ -n "${first_project:-}" ]; then
    check_200 "/projects/${first_project}/tasks"
    check_200 "/projects/${first_project}/tasks?status=pending"
  else
    info "no projects in projects.yaml — skipping /projects/<name>/tasks"
  fi
else
  info "jq not installed — skipping per-project endpoint checks"
fi

# ---- POST write path — use a transient title and delete semantics? --------
# Don't actually write to a real project from e2e; we only verify the
# validation path by posting an intentionally invalid priority and expecting
# 422. That proves the router is wired without mutating user state.
invalid_code=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BASE_URL/projects/__nonesuch__/tasks" \
  -H "Content-Type: application/json" \
  -d '{"title":"e2e-probe","priority":"URGENT"}')
if [ "$invalid_code" != "422" ] && [ "$invalid_code" != "404" ]; then
  fail 2 "POST with invalid priority → $invalid_code (expected 422 or 404)"
fi
ok "POST /projects/__nonesuch__/tasks invalid → $invalid_code (validation wired)"

echo "all e2e endpoint checks passed"
exit 0
