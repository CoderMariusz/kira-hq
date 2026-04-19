# ADR 0002: Four-agent model routing

- **Date:** 2026-04-19
- **Status:** accepted

## Context

Faza 2 started with a single agent (Claude Opus via Claude Max OAuth) doing
everything: planning, writing tests, implementing, reviewing, committing. By
T-17 this had two problems:

1. **Rate-limit pressure on Opus** — Max subscription is unmetered on dollars
   but metered on request velocity. Using Opus for 50-line router
   boilerplate burns the same budget as Opus on architecture decisions.
2. **Under-utilised code-specialised models** — OpenRouter exposes
   `qwen/qwen3-coder-30b-a3b-instruct` at $0.07/$0.27 per million tokens.
   Qwen3-Coder is post-trained specifically on code + tool-use and beats
   general-purpose models of the same size on SWE-bench.

The Kira-HQ PRD (§6.16 "provider-aware task expansion", §6.19 "token
economics — output discipline") already envisioned mixed-provider workflow.
This ADR nails down _who does what_.

## Decision

Four agent roles, strictly delimited:

| Role                | Agent                           | Model                                             | When                                                                                   |
|---------------------|---------------------------------|---------------------------------------------------|----------------------------------------------------------------------------------------|
| **Orchestrator / Brain** | Claude Opus (OAuth)        | Opus                                              | Plan, skill writing, architecture, frontend **design** when no prototype, PRD conformance checks, triple-fail handler, proposes new solutions, keeps task-master state current |
| **Code driver**     | Codex CLI (OpenRouter)          | `qwen/qwen3-coder-30b-a3b-instruct`               | Implementation: routers, CRUD, boilerplate, polish, refactor, frontend **fill-in** after Opus sets the design |
| **Reviewer + test author** | Codex CLI (native model) | Codex default (GPT-5 / o-series)                  | Code review of every Qwen diff; **writes** the unit + integration tests against the diff |
| **Test runner + QA** | Claude Sonnet (OAuth)          | Sonnet                                            | Runs the test suites, runs Playwright, does QA walkthroughs against PRD §6.15 DoD; reports red with context back to orchestrator |

`qwen3-coder-30b-a3b-instruct` is the default driver model. Escalate
to `qwen/qwen3-coder` (235B) only when Opus explicitly marks the task
as architecture-adjacent or when 30B fails review twice on the same
subtask — then Opus may re-delegate at 235B or take over.

## Work ownership (what each role OWNS, not just runs)

- **Skills** — Opus only. Skills encode the user's conventions.
- **Architecture** (PRD cross-cutting, new module design, parallel-track
  harness, >2 modules touched at once) — Opus.
- **Frontend design when no prototype exists** — Opus. Picks layout,
  component structure, visual hierarchy. Qwen fills in components
  against Opus's skeleton + acceptance criteria.
- **Frontend fill-in against an existing prototype or Opus skeleton** — Qwen.
- **Test authoring** (pytest unit + integration, bash shell tests,
  Playwright specs) — Codex (native model). Codex writes the tests
  against Qwen's diff as part of the review cycle.
- **Test running + QA** — Sonnet. Executes the full suite, runs
  Playwright browsers, walks through user flows against PRD §6.15 DoD,
  reports failures with diagnostic context to Opus.
- **Unit/integration implementation** — Qwen (Codex CLI with OpenRouter).
- **Code review** — Codex (native model). Every Qwen diff reviewed.
  Opus becomes reviewer on triple-fail or when Codex flags uncertainty.
- **Triple-fail handling, PRD conformance audits, task-master state
  discipline, proposing new solutions mid-task** — Opus. This is the
  "brain" role: Opus watches the whole pipeline, intervenes when
  things diverge from PRD or plan, and keeps the kanban true.

## Escalation (any role → Opus) triggers

- Qwen diff fails review **three times** on the same subtask (triple-fail)
- Sonnet test run goes red on the same test three consecutive runs
- Cross-module change detected (file touches >2 of {api, frontend,
  skills-shared, cron, projects-yaml})
- Security-sensitive surface (auth, secrets, subprocess env, file
  permissions, network binding, launchctl)
- PRD interpretation ambiguous / plan.md step contradicts PRD
- New third-party dependency proposed
- Codex reviewer flags "uncertain — human review"
- Frontend output fails prototype-match on two components in a row

## Diff-only context discipline

To keep token spend sub-linear in project size:

- Codex driver receives: plan.md section + relevant PRD subsection +
  named files to modify (by path + line range) + expected output as
  unified diff. **Not the full repo, not full files unless the file
  is new.**
- New files: full content from Codex, Codex reviewer (or Opus for T-18/19)
  reads the full file once on first review.
- Subsequent iterations on the same file: diff-only.

## Mandatory skill loading

Every agent — Opus, Codex driver, Codex reviewer, Sonnet — must load the
`kira-hq-task-execution` skill before starting any Faza 2 task. The skill
is the checklist/contract that keeps task-master state transitions,
pipeline log schema, test discipline, and commit policy consistent
across agents.

## Consequences

### Positive

- Opus rate-limit usage drops ~75-80% on remaining 8 tasks.
- Wall-clock per task drops 3-5× (Codex with Qwen is sub-minute on
  routine edits; Opus turns run 3-5 min).
- Qwen3-Coder on tight specs produces tighter code than Opus
  over-engineering routine boilerplate.
- Each role's tool output stays in that role's context, not mine.

### Negative

- Requires explicit orchestration (delegate_task with tight contract
  per subtask) — adds one layer of overhead vs "just do it".
- Failure modes now multiply: orchestration bug, Qwen misinterprets,
  Codex terminal fails, OpenRouter outage. Each escalation back to
  Opus costs a hop.
- Qwen output needs discipline: without strict diff contract, it
  happily rewrites unrelated code. The `MODEL_ROUTING.md` runbook
  codifies the contract.

## Alternatives considered

1. **Keep everything on Opus.** Rejected — unsustainable past T-25.
2. **Single Codex model (e.g. GPT-5).** Rejected — not available via
   OpenRouter tools in this setup, and the Qwen Coder line is
   specifically code-specialised at 3-10× lower cost.
3. **Minimax M2.7 as code driver.** Considered — benchmarks show it
   trails qwen3-coder on SWE-bench while costing ~4× more ($0.30/$1.20
   vs $0.07/$0.27). Useful as agentic reasoner, not as coder.
4. **GLM-4.6 as all-rounder.** Considered — cheaper than Opus but
   2-3× more expensive than qwen3-coder-30b and not code-specialised.

## Operational reference

Full routing matrix per task, diff conventions, escalation procedure,
subtask decomposition template, review checklist → `docs/MODEL_ROUTING.md`.
