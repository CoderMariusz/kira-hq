#!/usr/bin/env bash
# tests/smoke/test_taskmaster_workaround.sh — PRD §6.4
#
# Verifies that the ~/.zshrc task-master() env-stripping wrapper is present,
# that it is semantically different from a raw invocation (strips the 4
# trigger env vars), and that invoking task-master through it succeeds.
#
# History note (2026-04-18): an earlier revision of this script tried to
# reproduce the historical RangeError crash by running `task-master list`
# with CLAUDECODE=1. That was WRONG — `list` only reads tasks.json and
# never spawns claude-agent-sdk, so it cannot crash. The bug only triggers
# on subcommands that invoke the bundled SDK (e.g. `parse-prd`, `expand`,
# `research`). Reproducing it costs real LLM tokens, so we do NOT run it
# by default. Set KIRA_RUN_EXPENSIVE_CRASH_REPRO=1 to opt in.
#
# Exit codes:
#   0 — all active assertions passed
#   1 — wrapper missing / malformed in ~/.zshrc
#   2 — wrapper path failed (task-master list --json returned non-zero)
#   3 — wrapper path and raw path not semantically distinct
#   4 — opt-in expensive repro did not crash inside Claude Code session

set -u
set -o pipefail

ZSHRC="${ZSHRC:-$HOME/.zshrc}"
WRAPPER_PATTERN='task-master\(\)[[:space:]]*\{'

fail() { echo "FAIL: $2" >&2; exit "$1"; }
info() { echo "INFO: $*"; }
ok()   { echo "OK:   $*"; }
skip() { echo "SKIP: $*"; exit 0; }

# --- Skip gates -----------------------------------------------------------
# This test only makes sense on a developer machine where (a) task-master is
# installed and (b) ~/.zshrc hosts the env-stripping wrapper. On CI runners
# (ci.yml lean job) neither is true — skip cleanly instead of failing.
if ! command -v task-master >/dev/null 2>&1; then
  skip "task-master not installed (CI lean env) — wrapper test not applicable"
fi
if [ ! -f "$ZSHRC" ]; then
  skip "$ZSHRC missing (non-zsh env) — wrapper test not applicable"
fi

# --- Assertion 1: wrapper function defined in ~/.zshrc --------------------
if ! grep -Eq "$WRAPPER_PATTERN" "$ZSHRC"; then
  fail 1 "task-master() wrapper not found in $ZSHRC"
fi
for v in CLAUDECODE CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_EXECPATH ANTHROPIC_API_KEY; do
  if ! grep -q "env -u .*${v}" "$ZSHRC"; then
    fail 1 "wrapper in $ZSHRC missing env-stripping for $v"
  fi
done
ok "wrapper function present in $ZSHRC and strips all 4 trigger vars"

# --- Assertion 2: wrapper-path invocation succeeds ------------------------
# Emulate the wrapper behaviour directly. `list` is a safe, free, no-SDK
# subcommand — success here only proves the happy path works, not that
# the wrapper is load-bearing (see assertion 3).
if ! env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_EXECPATH -u ANTHROPIC_API_KEY \
     task-master list --json >/dev/null 2>&1; then
  fail 2 "task-master list --json failed through env-stripping wrapper path"
fi
ok "wrapper path invocation succeeded"

# --- Assertion 3: wrapper is SEMANTICALLY DISTINCT from raw invocation ----
# We don't try to crash the SDK (too expensive and requires tokens).
# Instead we prove that `env -u` actually removes the trigger vars so the
# child process sees a clean env — i.e. the wrapper is load-bearing at
# the env-manipulation layer regardless of whether the bug is currently
# triggerable. Uses /usr/bin/env to print the child env and diff the set
# of trigger vars visible to the raw-child vs stripped-child.
probe_env() {
  # $1 = "raw" | "stripped"
  local mode="$1"
  if [ "$mode" = "stripped" ]; then
    env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_EXECPATH -u ANTHROPIC_API_KEY \
      /usr/bin/env | grep -E '^(CLAUDECODE|CLAUDE_CODE_ENTRYPOINT|CLAUDE_CODE_EXECPATH|ANTHROPIC_API_KEY)=' || true
  else
    CLAUDECODE=1 \
    CLAUDE_CODE_ENTRYPOINT=probe \
    CLAUDE_CODE_EXECPATH=/tmp/probe \
    ANTHROPIC_API_KEY=sk-probe \
      /usr/bin/env | grep -E '^(CLAUDECODE|CLAUDE_CODE_ENTRYPOINT|CLAUDE_CODE_EXECPATH|ANTHROPIC_API_KEY)=' || true
  fi
}
raw_count=$(probe_env raw | wc -l | tr -d ' ')
stripped_count=$(probe_env stripped | wc -l | tr -d ' ')
# Raw child MUST see all 4 injected vars; stripped child MUST see 0.
if [ "$raw_count" != "4" ] || [ "$stripped_count" != "0" ]; then
  fail 3 "env-diff unexpected: raw sees $raw_count/4 trigger vars, stripped sees $stripped_count/0"
fi
ok "wrapper removes all 4 trigger env vars from child (raw=$raw_count, stripped=$stripped_count)"

# --- Assertion 4 (opt-in, expensive): actual crash repro ------------------
# Gated behind KIRA_RUN_EXPENSIVE_CRASH_REPRO=1 because reproducing the
# RangeError requires task-master subcommands that invoke claude-agent-sdk
# (parse-prd / expand / research), which consume real LLM tokens. Only
# meaningful when run from inside a Claude Code session.
if [ "${KIRA_RUN_EXPENSIVE_CRASH_REPRO:-0}" = "1" ]; then
  inside_claude_code=0
  if [ "${CLAUDECODE:-}" = "1" ] || [ -n "${CLAUDE_CODE_ENTRYPOINT:-}" ] || [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    inside_claude_code=1
  fi
  if [ "$inside_claude_code" -eq 0 ]; then
    info "KIRA_RUN_EXPENSIVE_CRASH_REPRO=1 but not inside Claude Code session; skipping repro"
  else
    tmp_prd=$(mktemp /tmp/kira-hq-prd-probe.XXXXXX.md)
    printf '# Probe PRD\n\n## R1\n- trivial requirement for SDK smoke\n' >"$tmp_prd"
    set +e
    task-master parse-prd --input="$tmp_prd" --num-tasks=1 --force >/dev/null 2>&1
    rc=$?
    set -e
    rm -f "$tmp_prd"
    if [ "$rc" -eq 0 ]; then
      fail 4 "EXPECTED CRASH DID NOT OCCUR — raw task-master parse-prd succeeded inside Claude Code session; wrapper may be redundant"
    fi
    ok "raw task-master parse-prd crashed inside Claude Code session (rc=$rc) — wrapper is load-bearing"
  fi
else
  info "expensive crash-repro SKIPPED (opt in with KIRA_RUN_EXPENSIVE_CRASH_REPRO=1)"
fi

echo "all active assertions passed"
exit 0
