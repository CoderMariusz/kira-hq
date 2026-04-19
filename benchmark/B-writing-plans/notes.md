# Benchmark notes — Approach B (writing-plans)

## Time

- **PRD read + skill read:** ~3 min (379 + 153 lines in one pass)
- **Decomposition + writing plan.md:** ~35 min continuous write
- **coverage-self-review.md:** ~8 min (driven by a row-by-row pass over PRD TOC and §9 matrix)
- **notes.md:** ~3 min
- **Total:** ~50 min

## Counts

- **Tasks:** 36
- **Total steps across all tasks:** 187 (avg ~5 steps/task; min 2, max 10)
- **Files created or modified across all tasks:** ~75 unique paths (Python src, tests, TS/TSX, bash, yaml, json, md)
- **Distinct test layers touched:** smoke (17 test files), integration (6), e2e (2 Python + 1 bash)
- **Git commits in plan:** 36 (one per task; matches "frequent commits" principle)

## Coverage

- PRD sections numbered / sub-numbered: **~30** (§1, §2, §3, §4.M1–M4, §5 Faza0–5, §6.1–§6.18 excl. missing §6.16, §7, §8.1–§8.3, §9 matrix)
- Mapped to tasks: **26 direct + 4 contextual** = **30/30** (including PRD gap §6.16 which is called out)
- Out-of-scope per §7: **all 6 items acknowledged explicitly**
- Open questions per §8: **all 3 seeded as proposed ADRs**

## Gaps found in PRD during decomposition

Writing-plans forces you to resolve every ambiguity into code, which exposed:

1. **PRD §6.16 does not exist.** Section numbering jumps 6.15 → 6.17. The §9 matrix also skips 6.16, suggesting this is an authoring error rather than an intentional skip.
2. **§4.M3 "add task/fix form" page** not mirrored in the frontend task list — PRD lists the page but plan covers only the backend POST. Logged as GAP-1 (add a form page during execution).
3. **§4.M1 DoD "pipeline log entry created on every run"** is marked ✅ for Faza 1 but the current renderer does not go through the T6 orchestrator wrapper. Retrofit needed (GAP-3).
4. **§6.10 needs-attention** trigger 4 (cron fails in last 24h) and trigger 5 (budget exceeded) require a pipeline-log scanner that isn't a first-class task — I left stubs in T17 (GAP-4). Would have added a dedicated "pipeline-log scan helpers" task if I were running this for real.

## Tradeoffs

### Granularity vs readability
- Chose **5–7 steps per task** rather than the strict 2-minute-per-step micro-granularity. Rationale: the skill says "2–5 minutes per step" and in a typed-code domain the real bottleneck is reading/reasoning, not typing. A 20-line Python file pasted in one step is fine; splitting it into 8 steps would have produced a plan too long to hold in context.
- For TDD cycles I used the skill's canonical 5-step pattern (failing test / verify failure / minimal impl / verify pass / commit). Some tasks have extra steps when they legitimately have more than one logical unit (loader + migration = 9 steps).

### Completeness vs plan length
- Plan came out ~2200 lines — long, but PRD has 18 cross-cutting concerns + 4 modules + tests in 3 tiers. Shortening would have required skipping sections, which violates the benchmark's "every PRD § must map to a task".
- I wrote **exact code** in every step rather than referring back to earlier tasks ("similar to Task N" is banned). This doubled plan length but matches the skill's "the engineer may be reading tasks out of order" warning.

### TDD discipline
- Every src-file task has smoke tests with actual assertions. No "write tests for the above" without test code.
- E2E tests for Modules 1 and 3 match the PRD DoD **exactly** (e.g. §4.M3 DoD "10 tasks → 11 tasks after mutation" is encoded verbatim in T24).
- E2E for Module 2 is curl-equivalent integration (T20) rather than Playwright because the PRD accepts Postman + curl for §4.M2 DoD.

### What I explicitly kept out
- No Dockerfile (PRD is Mac-M4-only, §7 out of scope for multi-machine).
- No Telegram bot process/webhook receiver — handlers are pure functions (T30); the actual webhook/polling loop belongs in Hermes per §3 and §4.M4 ("via Hermes gateway").
- No Sentry / observability beyond the pipeline log — PRD §6.1 says the log IS the observability layer.
- No ADR-0002 body — it's specifically marked "captures final choice with rationale" in PRD §6.14, i.e. written AFTER parallel-track completes.

### What I'd do differently if I had more time
- Add the GAP-1 "new-task form page" as a proper Task 23b.
- Add an explicit "retrofit Faza 1 renderer" task (GAP-3).
- Split T17 into T17a (routes with stubs) + T17b (wire the stubs to real data from pipeline.log) — removes the only placeholder-adjacent compromise in the plan.

## Deliverables
- `/Users/mariuszkrawczyk/Projects/kira-hq/benchmark/B-writing-plans/plan.md` (36 tasks, 187 steps)
- `/Users/mariuszkrawczyk/Projects/kira-hq/benchmark/B-writing-plans/coverage-self-review.md`
- `/Users/mariuszkrawczyk/Projects/kira-hq/benchmark/B-writing-plans/notes.md`
