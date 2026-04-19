# Versions lock — Kira-HQ

Source of truth for pinned SDK / CLI versions. PRD §6.4.

Update this file **any time** a pinned package moves. Tests in
`tests/smoke/test_sdk_versions.py` read this table and fail if installed
versions drift from the declared pins.

## Currently pinned

| package                              | version | last verified | notes                                                      |
|--------------------------------------|---------|---------------|------------------------------------------------------------|
| task-master-ai                       | 0.43.1  | 2026-04-18    | Known-good on Mac M4, Node 22. Faza 1 green.               |
| @anthropic-ai/claude-agent-sdk       | 0.1.77  | 2026-04-18    | Bundled inside task-master-ai. RangeError workaround reqd. |

## RangeError workaround — why it exists

`claude-agent-sdk` hits **"Maximum call stack size exceeded"** (RangeError)
when task-master spawns `claude` while OAuth context from a parent Claude Code
session is inherited. Triggering env vars (any of):

- `CLAUDECODE=1`
- `CLAUDE_CODE_ENTRYPOINT`
- `CLAUDE_CODE_EXECPATH`
- `ANTHROPIC_API_KEY` (when already issued by an outer Claude session)

Mitigation lives in `~/.zshrc` as a shell function:

```sh
task-master() {
  env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_EXECPATH -u ANTHROPIC_API_KEY \
      command task-master "$@"
}
```

The wrapper MUST stay until either (a) `claude-agent-sdk` fixes the nested-session
recursion, or (b) `task-master-ai` stops bundling the SDK. Until then:

1. Smoke test `tests/smoke/test_taskmaster_workaround.sh` asserts the wrapper
   is present and that `task-master list --json` succeeds via the wrapper
   path. It also runs a conditional crash-repro step when executed from
   inside a Claude Code session (otherwise skips with a note — the crash
   cannot be forced in an already-clean env).
2. Python test `tests/smoke/test_sdk_versions.py` parses this file and
   asserts installed versions match the pinned ones.
3. Cron pre-flight: `kira-hq-render-kanban` runs both smoke checks before
   any other work; failure → pipeline.log row with `status=fail` and
   Telegram halt (wired through §6.3 retry policy).

## Update procedure

1. Verify new version works in both (a) normal shell and (b) a shell with
   `CLAUDECODE=1 ANTHROPIC_API_KEY=...` to reproduce the historical bug.
2. Update the table above — version + `last verified` date + any notes.
3. Run `.venv/bin/python -m pytest tests/smoke/test_sdk_versions.py -v`.
4. Commit with message: `chore(sdk): pin <pkg> to <ver> — <reason>`.
