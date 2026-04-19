# Model routing — operational runbook

Companion to `docs/ADR/0002-model-routing.md`. This is the _how_, not the _why_.

## Agent roles (short form)

| Short name    | Agent                    | Model                                 | Owns                                                                                 |
|---------------|--------------------------|---------------------------------------|---------------------------------------------------------------------------------------|
| **Opus**      | Claude Opus (OAuth Max)  | Opus                                  | Brain: plan, skills, architecture, frontend design w/o prototype, PRD audit, triple-fail |
| **Qwen**      | Codex CLI + OpenRouter   | `qwen/qwen3-coder-30b-a3b-instruct`   | Routine code: impl, boilerplate, polish, refactor, frontend fill-in                  |
| **Codex**     | Codex CLI (native model) | Codex default (GPT-5 / o-series)      | Code review of every Qwen diff + **writing** the unit/integration/shell tests        |
| **Sonnet**    | Claude Sonnet (OAuth)    | Sonnet                                | Running tests, running Playwright, QA walkthroughs vs PRD §6.15 DoD                 |

All agents MUST load `kira-hq-task-execution` before starting.

## Per-task pipeline (TDD, fail-loops back to implementation)

The pipeline is **test-driven**: we write the failing test BEFORE any
production code. Tests drive the implementation, not the other way
around. Superpowers-style `test-driven-development` skill is the base;
each role executes a slice of the RED → GREEN → REFACTOR cycle.

Canonical flow (frontend or backend; prototype step only for UI):

```
           ┌─────────────────────────── Opus ──────────────────────────────┐
           │ 0. Task intake                                                 │
           │    - read plan.md §Task N + PRD §X.Y                          │
           │    - decide: frontend? → need design step?                    │
           │    - decompose if >150 LOC                                    │
           │    - task-master set-status N in-progress + render_kanban     │
           └───────────────────────────┬───────────────────────────────────┘
                                       │
                      (FRONTEND only, else skip)
                                       ▼
           ┌─────────────────────── Opus (designer) ───────────────────────┐
           │ 1. Prototype                                                   │
           │    - frontend/DESIGN.md: page layouts, component tree,         │
           │      Tailwind tokens, data-testid conventions                  │
           │    - per-component acceptance criteria (visual + behavioural)  │
           │    - commit DESIGN.md before any test/impl                     │
           │    skipped if prototype (screenshot/figma/codepen) supplied    │
           └───────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
           ┌─────────────────────── Codex (test author) ───────────────────┐
           │ 2. Write RED tests                                             │
           │    - pytest unit + integration / Playwright / bash shell       │
           │    - tests must fail for the right reason (feature missing),  │
           │      not from typos or import errors                           │
           │    - committed on a separate commit so the RED state is       │
           │      visible in history                                        │
           └───────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
           ┌────────────────────── Sonnet (runner) ────────────────────────┐
           │ 3. Verify RED                                                  │
           │    - runs the new tests                                        │
           │    - MUST see them fail with the expected message              │
           │    - passes IMMEDIATELY ⇒ test is wrong ⇒ back to step 2       │
           └───────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
           ┌──────────────────────── Qwen (driver) ────────────────────────┐
           │ 4. Implementation (minimal code to turn tests GREEN)           │
           │    - diff-only; only files listed in scope                     │
           │    - no features beyond the tests                              │
           │    - fails ⇒ back to this step (counter++)                     │
           └───────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
           ┌────────────────────── Sonnet (runner) ────────────────────────┐
           │ 5. Run GREEN                                                   │
           │    - pytest + bash suites + Playwright if UI + curl walk if API│
           │    - all new tests must PASS                                   │
           │    - full suite must stay green (no regressions)               │
           │    FAIL ⇒ back to step 4 (fail-loop)                          │
           └───────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
           ┌─────────────────────── Codex (reviewer) ──────────────────────┐
           │ 6. Review                                                      │
           │    - reads Qwen's diff in full on first pass, diff-only after  │
           │    - PRD coverage, no unrelated files, style, security         │
           │    - may add missing tests (extend step 2 retroactively)       │
           │    APPROVE or numbered issues                                  │
           │    issues ⇒ back to step 4 (fail-loop, counter++)             │
           └───────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
           ┌────────────────────── Sonnet (QA) ────────────────────────────┐
           │ 7. QA walkthrough vs PRD §6.15 DoD                             │
           │    - does the user-facing behaviour match what PRD promises?   │
           │    - for UI: click through real flows, check empty/error/load  │
           │    - for API: curl the endpoint from a fresh session           │
           │    FAIL ⇒ back to step 4 (fail-loop, counter++)               │
           └───────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
           ┌──────────────────────── Qwen (docs) ──────────────────────────┐
           │ 8. Docs                                                        │
           │    - update module README / changelog entry                    │
           │    - API endpoints in MODULE_*.md tables                       │
           │    - frontend: any DESIGN.md deltas from implementation        │
           └───────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
           ┌──────────────────────── Opus (closer) ────────────────────────┐
           │ 9. Close                                                       │
           │    - task-master set-status done + render_kanban               │
           │    - pipeline_log.append_entry per role with token counts      │
           │    - commit (single or split per role), push                   │
           │    - gh run watch CI → green or fix-forward                    │
           └────────────────────────────────────────────────────────────────┘
```

### Fail-loop counter

Every time a step fails and returns to implementation (step 4), a per-task
counter increments. When the counter hits **3**, the task escalates to
Opus automatically — do NOT loop a fourth time. Counter resets on
task-done, never on role change.

Counted failures:
- step 3 RED never fires (test is broken) — returns to step 2
- step 5 GREEN test fails — returns to step 4
- step 6 review issues — returns to step 4
- step 7 QA rejects — returns to step 4

Non-counted (these are the system working, not failing):
- step 3 RED fires correctly (this IS the expected outcome)
- step 8 docs need polish
- step 9 CI fails on portability issue (Opus handles directly, see
  CI portability-lessons memory entry)

### Skipping steps

- **Step 1 (Prototype):** skip for backend-only tasks, or when user
  supplies a prototype (screenshot / figma / codepen) — then the
  prototype IS the design spec.
- **Step 8 (Docs):** skip when diff is <20 LOC and doesn't touch
  user-visible behaviour.
- **No other skips.** RED-before-GREEN is iron law per the
  `test-driven-development` skill. The fail-loop structure means
  we never write production code without a failing test first.

## Routing matrix for T-18 … T-25

| Task | Summary                             | Driver     | Reviewer+TestAuthor | Runner+QA | Notes                                                                 |
|------|-------------------------------------|------------|---------------------|-----------|-----------------------------------------------------------------------|
| T-18 | Next.js frontend (Phase 3a)         | Qwen       | Codex               | Sonnet    | Opus designs layout/skeleton first (no prototype supplied)            |
| T-19 | Module 2 polish / add-project CLI   | Qwen       | Codex               | Sonnet    | Mechanical polish                                                     |
| T-20 | Hermes skill registration           | **Opus**   | Codex               | Sonnet    | Skill-writing → Opus by rule                                          |
| T-21 | `kira-weekly-review` skill          | **Opus**   | Codex               | Sonnet    | Skill-writing → Opus by rule                                          |
| T-22 | Parallel-track harness              | **Opus**   | Codex               | Sonnet    | Architecture (>2 modules) → Opus by rule                              |
| T-23 | Telegram command handlers           | Qwen       | Codex               | Sonnet    | Routine dispatch                                                      |
| T-24 | Final E2E Playwright suite          | Qwen       | Codex               | **Sonnet**| Sonnet both runs AND extends E2E here; Qwen scaffolds page objects    |
| T-25 | Release polish (README, CHANGELOG)  | Qwen       | Codex               | Sonnet    | Docs + version bump                                                   |

Any task can escalate to Opus via the triggers in §Escalation.

## Subtask decomposition (Opus → Qwen)

Opus decomposes any task whose anticipated diff exceeds **150 LOC** into
subtasks of ≤150 LOC each. Each subtask becomes one `delegate_task`
call. Template:

```
Goal: <imperative, single-sentence>
Plan.md section: ## Task N, Step M (verbatim quote, 5-15 lines)
PRD section: §X.Y (verbatim quote, ≤20 lines)
Files in scope:
  - <path>:<line_start>-<line_end>   (for modify)
  - <path>                           (for create)
Acceptance criteria (mechanical):
  1. <pytest / bash / TS test that must PASS — Codex will write these>
  2. <lint / typecheck clean>
  3. <no files outside 'in scope' touched>
Output format: unified diff against HEAD (for modify) OR full file (for create).
Forbidden: changing files not listed; adding dependencies.
Escalation: if any step fails twice, STOP, return diagnosis — do NOT loop.
```

## Diff-only discipline

- **Modify** existing file → Qwen receives only the slice (line range
  ±20 lines). Full-file reads banned unless file <80 LOC.
- **Create** new file → Qwen returns full file; Codex reads full file
  on first review only.
- **Iterate** on the same file → diff-only both directions.
- Gather slices with `read_file offset/limit` or `search_files`
  pattern. Never `cat` full files.

**Frontend prototype-reproduction protocol:**
- No prototype supplied → **Opus designs** layout + component skeleton +
  visual acceptance criteria first. Qwen fills in.
- Prototype supplied (screenshot / figma / codepen) → Qwen receives
  visual ref + component skeleton + visual diff tolerance. If Qwen
  misses on two components in a row → escalate; Opus takes frontend
  design for the rest of the project, Qwen stays on spec'd components.

## Review protocol (Codex reviewer)

Every Qwen diff goes through Codex. Codex:

1. Reads the Qwen diff in full.
2. Writes the unit + integration + shell tests that would have caught
   bugs in the diff (tests committed alongside the diff).
3. Runs a mechanical checklist:
   - PRD coverage claimed vs. actually covered
   - No unrelated files touched
   - No new deps unless explicitly allowed
   - Style matches existing modules (docstrings, error handling, DI
     seams where conventions exist)
   - Security: no secrets committed, no `chmod`-unsafe patterns,
     no `shell=True`, no unescaped user input into shell/path/SQL
4. Returns `APPROVE` or a numbered issues list.
5. If issues → Qwen iterates (max **3 rounds** — triple-fail → Opus).

## Test-running + QA (Sonnet)

Sonnet is the only role that executes the test suite end-to-end. For
every Qwen diff that has passed Codex review, Sonnet:

1. Runs `pytest -m "smoke or integration"` and records pass/fail counts.
2. Runs `bash tests/smoke/*.sh tests/integration/*.sh`.
3. If the task touches the API → spins up `./scripts/run-api.sh --prod`
   and runs `tests/e2e/test_api_curl.sh` or a task-specific curl walk.
4. If the task touches the frontend → runs `npm run build` and the
   Playwright suite with chromium.
5. Performs a QA walkthrough against PRD §6.15 DoD for the task's module:
   does the user-facing behaviour match what PRD promises?
6. Reports `GREEN` (with counts) or `RED` with: failing test names,
   traceback, last 50 lines of stderr, reproducer command, best guess
   at root cause.

Sonnet NEVER silently retries; first failure is reported.

## Escalation triggers (any role → Opus)

- Qwen diff fails Codex review **three times** on the same subtask
- Sonnet same test fails three runs in a row
- File touches >2 modules (api / frontend / skills-shared / cron /
  projects-yaml)
- Security-sensitive surface: auth, secrets, subprocess env, chmod,
  network bind, launchctl
- PRD interpretation ambiguous
- Proposed new dependency
- Codex reviewer flags "uncertain — human review"
- Frontend prototype-match fails on two components in a row

Escalation format:
```
ESCALATE: <short title> (role=<who>, task=T-NN)
Context: <what was attempted, 2-4 lines>
What blocks: <concrete error / ambiguity / unknown>
What was tried: <2 lines: attempts and outcomes>
Proposed paths: <A / B, if known>
```

## Concrete setup (from this repo)

### OpenRouter key

Stored in `~/.kira-hq/.env` (chmod 600) as `OPENROUTER_API_KEY`.
`kira_hq.secrets_schema.load_secrets()` picks it up.

### Codex CLI invocation

Two uses, two configs:

- **As Qwen driver** → Codex CLI configured to use OpenRouter with
  `OPENROUTER_API_KEY` and model `qwen/qwen3-coder-30b-a3b-instruct`.
  Invoked via `delegate_task(acp_command="codex", ...)` when the
  `autonomous-ai-agents/codex` skill supports this; see that skill
  for the exact env/flag wiring.

- **As Codex reviewer + test author** → Codex CLI with its native
  default model (GPT-5 / o-series), OpenRouter env NOT set.

Default driver model: `qwen/qwen3-coder-30b-a3b-instruct`
Arch escalation:       `qwen/qwen3-coder` (235B) — only on Opus directive.

### Claude Sonnet for test-run + QA

Spawned via `delegate_task(acp_command="claude", ...)` per the
`autonomous-ai-agents/claude-code` skill, with Sonnet as the model
override. Used for: running suites, Playwright, QA walkthroughs,
reporting structured diagnostics back to Opus.

## Pipeline-log columns for routed work

Every task (and subtask, if decomposed) is logged with
`kira_hq.pipeline_log.append_entry`:

- `provider` — `qwen-coder-30b` | `qwen-coder-235b` | `codex-native` |
  `opus` | `sonnet`
- `expand_used` — `true` if Opus subtask-decomposed the task
- `tokens_in/out` — from OpenRouter headers when available; approximate
  for OAuth models
- `notes` — `task=T-NN role=driver|reviewer|runner|brain rev=N`

Feeds `/metrics/tokens` and the T-21 weekly-review skill so we can
see how routing plays out in practice and tune the matrix.

## Escape hatch

This routing is the default for Faza 2 tasks T-18 … T-25. Mid-execution,
any role may escalate to Opus; Opus re-assigns and amends the matrix
in a follow-up commit to this file. Never silently re-route.
