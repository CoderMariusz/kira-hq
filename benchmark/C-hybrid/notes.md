# Approach C (prd-decompose-hybrid) — Benchmark Notes

**Skill used:** `prd-decompose-hybrid` (writing-plans rigor + Taskmaster JSON output)
**PRD:** `/Users/mariuszkrawczyk/Projects/kira-hq/prd/master-prd.md` (v2.0, 379 lines)
**Run date:** 2026-04-16

## Totals

- **Total tasks:** 24
- **Total TDD steps across plan.md:** ~165 numbered steps (avg 6-7 steps per task; range 4-9)
- **Total dependencies in DAG:** 41 edges, 0 cycles

## PRD coverage

- **Numbered sections/headings found:** 27 (including §6.16 gap)
- **Sections with content covered by ≥1 task:** 26 / 26 (100%)
- **Structural anomalies flagged:** 1 (§6.16 missing from PRD numbering — likely typo)
- **Explicit out-of-scope items from §7:** 6, all handled (3 hard exclusions, 3 referenced as explicit exclusions inside relevant tasks)

## Gaps caught by the explicit audit that vanilla parse-prd would likely drop

This is the core value proposition of hybrid over task-master parse-prd. Concrete catches:

1. **§6.16 missing** — PRD jumps §6.15 → §6.17. Hybrid flagged; parse-prd would silently renumber or ignore.
2. **§6.3 `/unstale` Telegram command** — buried in cron-failure prose, not in the Telegram command list. Mapped to T-21.
3. **§6.1 `GET /metrics/pipeline` endpoint** — stated in §6.1 prose, NOT in §4 Module 2 endpoint list. Added to T-16 via worksheet cross-ref.
4. **§6.9 archive-project inverse clause** — one sentence buried at end of add-project section. Captured as T-13.
5. **§6.7 ↔ §6.18 dependency** — snapshot health check lives in weekly review (cross-section). Coded as T-10 ↔ T-24 dep.
6. **§6.17 "no partial-done" policy** — needs an automated checker (T-23), not just documentation.
7. **§9 matrix cross-referencing** — e.g. matrix says M1 must touch §6.14 parallel-track (via pipeline-log path labeling); parse-prd without matrix awareness would miss this.
8. **§6.11 Hermes mirror symlink** — second symlink target beyond the obvious per-project one. Captured in T-7.
9. **§6.18 section 7 "if Hermes provides API"** — graceful-degrade requirement. Captured in T-24.
10. **§3 parallel-track decision 2-3 week window** — mid-paragraph temporal scope. Captured in T-22.

## Observations

- Building the coverage worksheet BEFORE writing tasks was the critical discipline. When I first mentally drafted 20 tasks I had missed §6.16, the /metrics/pipeline endpoint, and the archive-project inverse. The worksheet forced me to reconcile section-by-section.
- The §9 matrix at the end of the PRD is a gold mine for cross-task dependency extraction. Hybrid's worksheet captures this; parse-prd likely wouldn't.
- Out-of-scope items (§7) deserve explicit mention in relevant task details (e.g. T-4 "NO automated rotation") rather than being silently ignored. Prevents future feature-creep.
- `Decision: TBD` in ADR 0002 is the only legitimate TBD/placeholder in the output — decision is legitimately deferred until parallel-track evaluation completes.

## Deliverables

All files in `/Users/mariuszkrawczyk/Projects/kira-hq/benchmark/C-hybrid/`:

- `plan.md` — 24 tasks, writing-plans format, ~165 TDD steps, exact file paths, no placeholders
- `tasks.json` — taskmaster-schema `{tags: {master: {tasks: [...]}}}`, 24 entries with id/title/description/details/testStrategy/priority/dependencies/status
- `coverage.md` — full audit table, gap analysis, out-of-scope mapping
- `notes.md` — this file

## Time invested

~1 pass of PRD read + worksheet + plan authoring + JSON emission + coverage audit. No iteration needed because the coverage audit caught gaps BEFORE finalization rather than after.
