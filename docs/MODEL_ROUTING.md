# Model routing — operational runbook

Companion to `docs/ADR/0002-model-routing.md`. This is the _how_, not the _why_.

## Agent roles (short form)

| Short name     | Agent                   | Model                                             | Purpose                       |
|----------------|-------------------------|---------------------------------------------------|-------------------------------|
| **Opus**       | Claude Opus (OAuth Max) | Opus                                              | Orchestrator / skills / arbiter |
| **Qwen-30B**   | Codex CLI (+OR)         | `qwen/qwen3-coder-30b-a3b-instruct`               | Routine code driver           |
| **Qwen-235B**  | Codex CLI (+OR)         | `qwen/qwen3-coder`                                | Code reviewer                 |
| **Sonnet**     | Claude Sonnet (OAuth)   | Sonnet                                            | E2E tests                     |

All agents MUST load `kira-hq-task-execution` before starting.

## Routing matrix for T-18 … T-25

| Task | Summary                             | Driver     | Reviewer         | E2E owner | Notes                                                                 |
|------|-------------------------------------|------------|------------------|-----------|-----------------------------------------------------------------------|
| T-18 | Next.js frontend (Phase 3a)         | Qwen-30B   | **Opus** (1st)   | Sonnet    | Opus reviews first user-visible UI commit end-to-end                  |
| T-19 | Module 2 polish / add-project CLI   | Qwen-30B   | **Opus** (2nd)   | n/a       | Opus does the last hands-on review before fully handing off           |
| T-20 | Hermes skill registration           | **Opus**   | n/a              | Sonnet    | **Skill-writing → Opus by rule**                                      |
| T-21 | `kira-weekly-review` skill          | **Opus**   | n/a              | Sonnet    | **Skill-writing → Opus by rule**                                      |
| T-22 | Parallel-track harness              | **Opus**   | n/a              | Sonnet    | **Architecture → Opus by rule**                                       |
| T-23 | Telegram command handlers           | Qwen-30B   | Qwen-235B        | Sonnet    | Routine dispatch code; Qwen reviewer now live                         |
| T-24 | Final E2E Playwright suite          | **Sonnet** | Qwen-235B        | Sonnet    | Sonnet writes the E2E; Qwen reviews for mechanical issues             |
| T-25 | Release polish (README, CHANGELOG)  | Qwen-30B   | Qwen-235B        | n/a       | Docs + version bump; trivial                                          |

Any task can escalate to Opus via the triggers in §Escalation below.

## Subtask decomposition (before delegating to Qwen-30B)

Opus decomposes any task whose anticipated diff exceeds **150 LOC** into
subtasks of ≤150 LOC each. Each subtask becomes one `delegate_task` call
with a self-contained prompt. Template:

```
Goal: <imperative, single-sentence>
Plan.md section: ## Task N, Step M (verbatim quote, 5-15 lines)
PRD section: §X.Y (verbatim quote, ≤20 lines)
Files in scope:
  - <path>:<line_start>-<line_end>   (for modify)
  - <path>                           (for create)
Acceptance criteria (concrete, mechanical):
  1. <pytest / bash / TS test that must PASS>
  2. <lint / typecheck clean>
  3. <file structure / no extraneous changes>
Output format: unified diff against HEAD (for modify) OR full file (for create).
Forbidden: changing files not listed in scope; adding dependencies.
Escalation: if any step fails twice, stop, return diagnosis.
```

## Diff-only discipline

- **Modify existing file** → send only the relevant slice (line range or
  ~20 lines of context around the change site). Never paste the full
  file to Qwen-30B unless the file is <80 LOC.
- **Create new file** → Qwen returns full file; reviewer reads it in
  full on first review pass only.
- **Subsequent iteration on the same file** → diff-only both ways.
- Use `read_file` with `offset`/`limit` or `search_files` with narrow
  pattern to gather the slice. Avoid `cat`/full reads.

**Frontend prototype-reproduction protocol (future projects):**
When Qwen is asked to match an existing UI prototype (screenshot, figma,
codepen), it receives: (a) the visual reference, (b) the component
skeleton, (c) acceptance criteria including visual diff tolerance.
If Qwen's output fails two acceptance rounds on the same component,
frontend design for that project escalates to Opus — Qwen continues
only on scoped, spec'd-out components.

## Review protocol

### Reviewer = Opus (T-18, T-19)

1. Read the full diff (Qwen-30B output) with repo context fresh.
2. Check: (a) PRD coverage claimed in plan.md is real, (b) no
   unrelated files touched, (c) tests added + run green, (d) no new
   deps, (e) style matches existing modules.
3. If blocking issues → write them as a numbered list, hand back to
   Qwen-30B for a revision. Max 2 revision rounds; third failure →
   Opus takes over.

### Reviewer = Qwen-235B (T-20+)

1. `delegate_task` with Qwen-235B as reviewer. Prompt:
   - Diff to review (full)
   - PRD section cited in the plan
   - Review checklist from PRD §6.15 + tests-must-pass
2. Reviewer outputs either `APPROVE` or a numbered issues list.
3. If issues → Qwen-30B iterates, max 2 revision rounds.
4. On 3rd failure → escalate to Opus.

## Escalation triggers (any agent → Opus)

- Test fails twice after Codex attempts to fix
- File touches >2 modules (api / frontend / skills-shared / cron /
  projects-yaml)
- Security-sensitive surface: auth, secrets, subprocess env, chmod,
  network bind, launchctl
- PRD interpretation ambiguous
- Proposed new dependency
- Qwen-235B reviewer flags "uncertain — human review"

Escalation format (Codex → Opus):
```
ESCALATE: <short title>
Context: <what was attempted>
What blocks: <concrete error / ambiguity / unknown>
What I tried: <2 lines, what was attempted and outcome>
Proposed paths: <A / B, if known>
```

## Concrete setup (from this repo)

### OpenRouter key

Stored in `~/.kira-hq/.env` (chmod 600). The `kira_hq.secrets_schema.load_secrets()`
loader already picks it up as `OPENROUTER_API_KEY`.

### Codex CLI with OpenRouter

Skill `autonomous-ai-agents/codex` documents the Codex CLI flags. For
Kira-HQ delegation use:

```
delegate_task(
  goal=<single imperative>,
  context=<plan.md + PRD slice + file slices>,
  toolsets=["terminal", "file"],
  # Codex CLI is launched via the 'codex' skill which reads OPENROUTER_API_KEY
)
```

Model selection for the Codex subprocess is set via env var that the
`codex` skill consumes — see that skill for the exact invocation line.

Default driver model: `qwen/qwen3-coder-30b-a3b-instruct`
Reviewer model:       `qwen/qwen3-coder`

### Claude Sonnet for E2E

Spawned via `delegate_task` with `acp_command="claude"` and a Sonnet
model override per the `claude-code` skill. Used for: writing Playwright
specs, running real-service integration tests, validating user-visible
flows.

## Pipeline-log columns for routed work

Every delegated task's outcome is logged with `kira_hq.pipeline_log.append_entry`:

- `provider` — `qwen-coder-30b` | `qwen-coder-235b` | `opus` | `sonnet`
- `expand_used` — `true` if the task was subtask-decomposed
- `tokens_in/out` — from the agent's final turn (when available via OpenRouter
  response headers; approximate for OAuth-backed models)
- `notes` — `task=T-NN role=driver|reviewer|e2e rev=N`

This feeds `/metrics/tokens` (per-project) and the weekly review skill
(T-21) so we can see how the routing plan plays out in practice.

## Escape hatch

This routing is the default for Faza 2 tasks T-18 … T-25. If a task's
constraints change mid-execution (e.g. user adds a complex requirement
by chat), the current role may escalate to Opus and Opus re-assigns.
Never silently change the routing without updating this file.
