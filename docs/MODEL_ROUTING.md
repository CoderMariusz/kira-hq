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

## Foundation skills (load alongside kira-hq-task-execution)

These are the superpowers-lineage skills (`adapted from obra/superpowers
+ MorAlekss`) that underpin the pipeline. Every agent should understand
them; they are NOT duplicated into `~/.kira-hq/skills-shared/` because
they live in the global `~/.hermes/skills/software-development/` and
apply to every project.

| Skill                          | Used by           | Pipeline step |
|--------------------------------|-------------------|---------------|
| `test-driven-development`      | Codex, Qwen, Sonnet, Opus | 2, 3, 4, 5    |
| `requesting-code-review`       | Codex, Sonnet, Opus | 6 (and self-review checks across all steps) |
| `subagent-driven-development`  | Opus              | 0 (decompose), 9 (two-stage review close) |
| `systematic-debugging`         | Opus              | triple-fail handler |
| `writing-plans`                | Opus              | 0 (decompose >150 LOC) |

Kira-HQ-specific skills (live in `~/.kira-hq/skills-shared/`):

| Skill                       | Used by | Purpose                                  |
|-----------------------------|---------|------------------------------------------|
| `kira-hq-task-execution`    | all     | Task contract + routing quick-ref        |
| `kira-hq-render-kanban`     | Opus    | Kanban render (steps 0 and 9)            |
| `kira-hq-execute`           | Opus    | Task dispatch                            |
| `prd-decompose-hybrid`      | Opus    | Turn PRD → plan.md                       |
| `kira-add-project` / `kira-archive-project` | user | Project lifecycle CLI     |

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
           │ 1. Clickable prototype (interactive HTML)                      │
           │    - frontend/prototype.html: single-file, self-contained,     │
           │      Tailwind CDN, hash-router between pages, realistic mock   │
           │      data matching API response shapes, data-testid attrs     │
           │      that Playwright RED specs will query in step 2            │
           │    - MUST be openable with `open frontend/prototype.html`      │
           │      (macOS) or double-click — NO build step, NO npm           │
           │    - Opus captures 1440×900 screenshots per page (Playwright   │
           │      chromium headless) and attaches them to the handoff       │
           │    - **USER ACCEPT required before step 2** — if user rejects, │
           │      iterate the prototype, NOT the tests                      │
           │    - skipped if the user supplies a prototype (screenshot /   │
           │      figma / codepen) — that IS the step 1 output              │
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

## Pre-handoff self-review (mandatory per role)

Every role, before passing work to the next step, runs a self-review
checklist. This is NOT the independent review (that's Codex step 6
and Sonnet step 7) — it's a pre-handoff sanity check from the
`requesting-code-review` skill Step 4. Purpose: catch obvious slop
before spending tokens on the next role.

For this controller model, worker handoffs are machine-readable Stage 1
payloads, not free-form prose. Use the canonical parser in
`src/kira_hq/handoff.py` via `parse_handoff`, with JSON, YAML, or YAML
front matter carrying the structured summary.

**Codex self-review before handing RED tests to Sonnet (after step 2):**
- [ ] Every new test has a clear name describing behaviour
- [ ] Each test actually asserts the wished-for behaviour (not mock interactions)
- [ ] Tests do NOT reference implementation files that don't exist yet
  (imports of future functions should be guarded or explicit)
- [ ] No `assert True` / `pytest.skip` masking
- [ ] Tests would fail for the right reason (the feature is missing),
  not from typos or import errors
- [ ] Tests committed on a RED-state commit so history shows failure

**Qwen self-review before handing implementation to Sonnet (after step 4):**
- [ ] Only files in declared scope touched — `git status` confirms
- [ ] Diff is minimal — no extra features, no "while I was there" changes
- [ ] No hardcoded secrets, no `shell=True`, no `os.system(f"...")`
- [ ] No `eval`/`exec`/`pickle.loads` on external input
- [ ] Error handling on I/O / subprocess / network calls
- [ ] No debug `print` / `console.log` left behind
- [ ] No commented-out code
- [ ] RED tests from step 2 now pass locally
- [ ] Full suite still passes (no regressions) — run it before handoff

**Codex self-review before finishing review (after step 6):**
- [ ] Re-read the full diff once — any issue missed on first pass?
- [ ] Review covered all mechanical checks: PRD coverage, unrelated
  files, style, security (Step 2/3 checks from requesting-code-review)
- [ ] Issues list has actionable, specific, numbered items (not vague)
- [ ] Any test the review reveals is missing → added in this pass,
  not deferred

**Sonnet self-review before reporting RED/GREEN/QA result:**
- [ ] Actually ran the command, not guessed the output
- [ ] Captured failing test names + last 50 lines of stderr
- [ ] If RED: distinguish "fails for right reason" vs "fails from typo"
- [ ] If GREEN: full suite, not just the new tests
- [ ] If QA: compared behaviour to PRD §6.15 DoD line-by-line, not a gut feel

**Opus self-review before closing (after step 9):**
- [ ] task-master state = done, kanban rendered
- [ ] pipeline_log row appended with correct provider + token count
- [ ] Commit message describes what shipped (not "fix stuff")
- [ ] CI green OR portability fix clearly applied
- [ ] Any deliberate deviations from plan.md listed in commit body

**Self-review failures stay inside the role.** They don't count against
the fail-loop counter — they only fire between step 4→5 and before
any handoff. Only when another role rejects does the counter increment.

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
