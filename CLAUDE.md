# CLAUDE.md

## Kira-HQ operating mode

This repo now treats **Claude Code as the primary orchestrator** and **Hermes as a bash-invoked worker** for routine implementation routed through Hermes's existing OpenRouter/Qwen path.

### Canonical shared substrate

Do not create shadow state. The authoritative filesystem substrate is:

- `./.taskmaster/tasks/tasks.json`
- `./.taskmaster/state.json`
- `~/.kira-hq/projects.yaml`
- `~/.kira-hq/global-pipeline.log.md`
- `~/.kira-hq/skills-shared/*`

### Tag / task rules

- Canonical tag is `master` unless the user explicitly says otherwise.
- Never hand-edit `tasks.json`.
- Never mutate task state with ad-hoc `python -c`, `jq`, or raw JSON writes.
- Use neutral repo CLI entrypoints:
  - `kira-hq list-tasks`
  - `kira-hq add-task`
  - `kira-hq set-status`
  - `kira-hq doctor`
- The same lock-safe substrate helpers back CLI and API writes.

### Claude -> Hermes(worker) bridge

Preferred entrypoint:

```bash
./scripts/hermes_worker.sh \
  --task-id 35 \
  --prompt "Implement the bounded delegated step" \
  --project-dir /Users/mariuszkrawczyk/Projects/kira-hq \
  --handoff-out /Users/mariuszkrawczyk/Projects/kira-hq/.hermes/artifacts/35/handoff.json
```

Equivalent neutral CLI form:

```bash
kira-hq delegate-worker \
  --task-id 35 \
  --prompt "Implement the bounded delegated step" \
  --project-dir /Users/mariuszkrawczyk/Projects/kira-hq \
  --handoff-out /Users/mariuszkrawczyk/Projects/kira-hq/.hermes/artifacts/35/handoff.json
```

Bridge contract:

- Claude calls the neutral repo entrypoint/shim, not a one-off Hermes command variant.
- The shim strips `CLAUDECODE`, `CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_CODE_EXECPATH`, and `ANTHROPIC_API_KEY` before invoking Hermes.
- Hermes is invoked with `--provider openrouter --model qwen/qwen3-coder-30b-a3b-instruct`.
- This intentionally **reuses Hermes's existing OpenRouter/Qwen route** instead of building a competing Claude-side OpenRouter client.
- Hermes must return **Stage-1 handoff JSON only** on stdout.
- The handoff is persisted to `--handoff-out` and pipeline logging lands on the shared substrate.
- Misconfiguration must fail loudly, especially missing `OPENROUTER_API_KEY` or missing `hermes` executable.

### Skills policy

**Shared skills** belong in `~/.kira-hq/skills-shared/` when all of the following are true:

1. They operate only on shared substrate files or repo code.
2. They are safe for both Claude and Hermes to invoke.
3. They do not depend on Hermes-only session memory, gateway state, or product-specific internals.

**Hermes-only skills** stay Hermes-scoped when any of the following are true:

1. They depend on Hermes memory/autolearn/session history.
2. They require Hermes gateway/platform integrations.
3. They rely on Hermes-only approval or tool orchestration semantics.
4. They would create ambiguous duplicate behavior if exposed as a shared skill.

Promotion rule: start Hermes-only by default if uncertain; promote to shared only after the interface is neutral, stateless, and substrate-safe.

### Readiness / verification

Run before relying on the dual-interface path:

```bash
kira-hq doctor
```

Doctor checks include:

- `currentTag == master`
- shared substrate files present
- symlink health via `scripts/symlink_skills.py --check`
- Hermes CLI discoverability
- `OPENROUTER_API_KEY` presence
- neutral shared read-path health
- global pipeline log writability
