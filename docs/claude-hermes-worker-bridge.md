# Claude orchestrator -> Hermes worker bridge

This document records the concrete T-35/T-36 contract.

## Goal

Use **one neutral repo entrypoint** for delegation so Claude can orchestrate while Hermes performs bounded implementation work through **Hermes's own OpenRouter/Qwen route**.

## Entry points

Shared CLI:

```bash
kira-hq delegate-worker \
  --task-id <id> \
  --prompt "<delegated implementation scope>" \
  --project-dir /Users/mariuszkrawczyk/Projects/kira-hq \
  --handoff-out /absolute/path/to/handoff.json
```

Shell shim:

```bash
./scripts/hermes_worker.sh ...same flags...
```

The shell shim is intentionally thin and delegates straight back to the shared repo CLI.

## Contract

1. Claude uses the neutral entrypoint/shim.
2. The bridge sanitizes nested-Claude env vars:
   - `CLAUDECODE`
   - `CLAUDE_CODE_ENTRYPOINT`
   - `CLAUDE_CODE_EXECPATH`
   - `ANTHROPIC_API_KEY`
3. Hermes is called as:

```bash
hermes chat \
  -q "<bridge-built prompt>" \
  --provider openrouter \
  --model qwen/qwen3-coder-30b-a3b-instruct \
  --source tool \
  -Q
```

4. Hermes returns **only** Stage-1 handoff JSON on stdout.
5. `kira-hq delegate-worker` validates that handoff with `kira_hq.handoff.parse_handoff`.
6. The validated handoff is written to `--handoff-out`.
7. A shared-substrate pipeline log row is appended with:
   - `skill=kira-hq-hermes-worker`
   - `provider=qwen3-coder`
   - `notes=track=<track>; handoff=<path>; worker=<cmd>`

## Why this path is the safe one

We inspected the local machine and verified:

- Hermes CLI already supports `chat -q ... --provider openrouter --model ...`.
- Hermes already owns the OpenRouter credential route and Qwen tool-call parsing.
- Hermes already fails clearly when `OPENROUTER_API_KEY` is missing.

So Claude should **reuse Hermes's qwen route** instead of building a second OpenRouter client/path in Kira-HQ or in Claude plugins.

## Skills promotion rules

Promote to `~/.kira-hq/skills-shared/` only when the skill is:

- stateless across interfaces,
- substrate-safe,
- useful to both Claude and Hermes,
- not dependent on Hermes memory/gateway/session internals.

Keep Hermes-only when the skill depends on Hermes runtime state or would duplicate behavior ambiguously.

## Bounded validation shape

T-36 proves:

Claude orchestrator
-> `kira-hq delegate-worker` / `scripts/hermes_worker.sh`
-> Hermes worker
-> Hermes OpenRouter/Qwen route
-> validated Stage-1 handoff
-> shared pipeline log / shared task substrate

A negative-path check must also prove loud failure on misconfiguration, especially missing `OPENROUTER_API_KEY`.
