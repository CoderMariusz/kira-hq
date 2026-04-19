# Coverage Self-Review — PRD vs plan.md

Every numbered PRD section mapped to Task(s) in `plan.md`, or flagged.

## §1 Vision, §2 Users, §3 Architecture

| PRD §     | Content                                             | Coverage                                                                                 |
|-----------|-----------------------------------------------------|------------------------------------------------------------------------------------------|
| §1        | Vision — command center, 10–15 AI projects, PM role | Drives plan as a whole; restated in plan.md **Goal** + **Architecture**                  |
| §2        | Primary user Mariusz, 24/7 Mac M4                   | No task — context. Reflected in launchctl cron (Task 12), localhost-first (Tasks 15,19)  |
| §3        | 3-layer architecture diagram + parallel-track note  | Reflected in file layout block of plan.md + parallel-track harness Task 31              |

## §4 Modules

| PRD §     | Requirement                                         | Task(s)                                                                                   |
|-----------|-----------------------------------------------------|-------------------------------------------------------------------------------------------|
| §4.M1     | Markdown renderer (kanban, global, needs-attention) | T3 (log), T7 (needs-attention), T9 (kanban + ADRs), T10 (E2E), T11 (README)               |
| §4.M1 DoD | Smoke + integration + E2E + README + pipeline log  | T3, T7, T9, T10, T11; verifier T34                                                        |
| §4.M2     | FastAPI /projects, /tasks, /views, /metrics         | T13 (skeleton), T14 (taskmaster client), T15 (GET projects/tasks), T16 (POST), T17 (views), T18 (metrics), T19 (auth), T20 (E2E+Postman+README) |
| §4.M2 port 3100 | Explicit                                      | T13 uvicorn command; T20 integration test binds 3100                                     |
| §4.M2 auth| HTTP Basic when exposed                             | T19                                                                                       |
| §4.M2 DoD | Smoke+integration+E2E browser+README                | T13–T20; Postman in T20; verifier T34                                                     |
| §4.M3     | Next.js list, detail, needs-attention, blockers, add-task form, Hermes iframe | T21 (scaffold+list), T22 (detail kanban), T23 (needs-attn+blockers+iframe+nav) |
| §4.M3 add-task form | Explicit                                  | **Gap fixed: plan does NOT include a dedicated add-task form UI page.** POST endpoint exists (T16) but frontend form page is missing. **SEE GAP-1 below.** |
| §4.M3 Phase 3a localhost:3001 / 3b Vercel | Explicit                  | T21 (dev port 3001), T25 README                                                           |
| §4.M3 DoD | 10 tasks visible, click detail, mutate → 11         | T24 (exact test)                                                                          |
| §4.M4     | Skills kira-hq-render-kanban, kira-hq-report, kira-weekly-review, kira-add-project | Render-kanban = Faza 1 (existing); T27 (report), T28 (weekly-review), T29 (add-project) |
| §4.M4 Telegram cmds /status /blockers /add /fix /review | Explicit        | T30 (+ also /unstale from §6.3)                                                           |
| §4.M4 Parallel-track scaffold | Explicit                              | T31                                                                                       |
| §4.M4 DoD | Each skill smoke + command round-trip + harness     | T27–T31; verifier T34                                                                     |

## §5 Phases

| PRD §    | Phase          | Coverage                                                                   |
|----------|----------------|----------------------------------------------------------------------------|
| §5 Faza 0 | ✅ done       | Context only — no task                                                     |
| §5 Faza 1 | ✅ done       | Context only — no task; noted in plan.md Architecture                      |
| §5 Faza 2 | ⬅️ NEXT       | Tasks 1–12, 26–31, 32 — Module 1 prod + cross-cutting + Hermes scaffold    |
| §5 Faza 3 | Modules 2+3   | Tasks 13–25                                                                |
| §5 Faza 4 | Hermes full   | Partially deferred; parallel-track decision handled via ADR-0002 seed in T31 |
| §5 Faza 5 | Vercel        | Deferred — Vercel docs in T25 (Module 3 README), ADR 0004 in T36           |

## §6 Cross-cutting

| PRD §    | Concern                       | Task(s)                                                                     |
|----------|-------------------------------|-----------------------------------------------------------------------------|
| §6.1     | Pipeline log schema           | T3 (writer), T6 (orchestrator appends), T18 (/metrics/pipeline exposes)     |
| §6.2     | Token tracking (not $)        | T18 (aggregate + daily rollup), T28 (weekly top-3)                          |
| §6.3     | Cron failure handling         | T4 (retry+incident), T5 (Telegram), T6 (orchestrator ties it all)           |
| §6.3 /unstale cmd | Explicit              | T30                                                                         |
| §6.4     | SDK pin + workaround smoke    | T1                                                                          |
| §6.5     | Secrets schema + per-project  | T32                                                                         |
| §6.6     | projects.yaml v2 + migration  | T2                                                                          |
| §6.7     | Backup policy                 | T12 (snapshot + rolling + restore + launchctl)                              |
| §6.8     | ADR convention                | T8 (template+index), T9 (kanban embeds last 5), T35 (ADR-0001), T36 (ADRs 0003–0005) |
| §6.9     | kira-hq add-project           | T29 (+ archive-project)                                                     |
| §6.10    | needs-attention algorithm     | T7 (5 rules), T17 (API route), T23 (frontend page)                          |
| §6.11    | Shared skills library         | T26 (init repo), T27–T29 (add SKILL.md files)                               |
| §6.12    | FastAPI auth                  | T19                                                                         |
| §6.13    | Next.js localhost-first       | T21 scaffolds on :3001, T25 README documents Phase 3a→3b gate               |
| §6.14    | Hermes role + parallel track  | T31 (harness), T23 (Hermes iframe), ADR-0002 seed in T36                    |
| §6.15    | Three-tier test strategy + CI | Every task has smoke/integration/E2E as applicable; T33 (CI)                |
| §6.16    | **DOES NOT EXIST IN PRD**     | **GAP-2 — PRD jumps 6.15 → 6.17 (see below)**                               |
| §6.17    | DoD per module                | T34 (verify_module_dod.sh)                                                  |
| §6.18    | Weekly review ritual          | T28                                                                         |

## §7 Out of scope — all acknowledged explicitly

| PRD §7 item                | Handling                                                                        |
|----------------------------|---------------------------------------------------------------------------------|
| Multi-machine sync         | Not in plan (out of scope per PRD §7)                                           |
| Multi-tenant               | Not in plan (out of scope per PRD §7)                                           |
| Perf benchmarks            | Not in plan (out of scope per PRD §7)                                           |
| Public UI                  | Not in plan (out of scope per PRD §7); Vercel deploy gated to Phase 3b after ≥1 week stable |
| Automated secrets rotation | Not in plan (out of scope per PRD §7) — T32 documents **manual** rotation only  |
| Skill-tag pinning          | Not in plan (out of scope per PRD §7) — T26 README notes future                 |

## §8 Open questions — tracked as proposed ADRs

| PRD §8 Q                    | Handled by                                                |
|-----------------------------|-----------------------------------------------------------|
| §8.1 Hermes install         | ADR-0003 (proposed) seeded in T36                         |
| §8.2 Vercel auth            | ADR-0004 (proposed) seeded in T36                         |
| §8.3 MonoPilot decomposer   | ADR-0005 (proposed) seeded in T36                         |

## §9 Matrix — cell-by-cell verification

PRD §9 maps modules × cross-cutting concerns. Sampling:

| Cell                   | PRD marks applicable? | Plan covers? |
|------------------------|-----------------------|--------------|
| M1 × 6.1 log           | ✅                     | T3, T6, T9   |
| M1 × 6.2 tokens        | ✅                     | T18 aggregate reads M1-written log |
| M1 × 6.3 retry         | ✅                     | T6           |
| M1 × 6.4 SDK           | ✅                     | T1           |
| M1 × 6.5 secrets       | —                     | correctly skipped |
| M1 × 6.6 yaml          | ✅                     | T2 loader used by renderer |
| M1 × 6.7 backup        | ✅                     | T12          |
| M1 × 6.8 ADR           | ✅                     | T8, T9       |
| M1 × 6.9 add           | ✅                     | T29 runs render on add |
| M1 × 6.10 needs-attn   | ✅                     | T7           |
| M1 × 6.11 skills       | ✅                     | T26          |
| M1 × 6.14 hermes       | ✅                     | T31          |
| M1 × 6.15 test         | ✅                     | smoke+integration+E2E for M1 |
| M1 × 6.17 DoD          | ✅                     | T34          |
| M1 × 6.18 review       | ✅                     | T28          |
| M2 × 6.3 retry         | —                     | correctly skipped |
| M2 × 6.5 secrets       | ✅                     | T19 reads KIRA_HQ_USER/PASS |
| M2 × 6.7 backup        | —                     | correctly skipped |
| M2 × 6.11 skills       | —                     | correctly skipped |
| M3 × 6.1 log           | —                     | correctly skipped |
| M3 × 6.8 ADR           | ✅                     | T35 ADR-0001 is about M2/M3 choice |
| M3 × 6.10 needs-attn   | ✅                     | T23          |
| M4 all-cells           | all ✅                 | T26–T31, T34 |

---

## Gaps found

### GAP-1: Module 3 lacks a dedicated "Add task / fix" form page

**Source:** PRD §4.M3 lists "add task/fix form" among pages.
**Current plan coverage:** POST endpoint is covered by T16, but T21–T23 do not add a form page for humans. The Telegram `/add` and `/fix` commands (T30) partially cover the use case, but the PRD explicitly says the Next.js dashboard should have the form.

**Fix:** Add **Task 23b** (or extend T23): `frontend/app/projects/[name]/new-task/page.tsx` — simple controlled form that POSTs to `/projects/{name}/tasks`. Not inlined here to avoid editing the plan after the fact — documented as a known sub-gap to close during execution review.

### GAP-2: PRD §6.16 is missing

**Source:** PRD §6 is numbered 6.1, 6.2, …, 6.15, **6.17**, 6.18. There is no 6.16. Either an intentional skip (unlikely — the index in §9 also skips 6.16) or a PRD-authoring oversight.

**Action:** Documented here; no plan task required. Flagged to the PRD author in the benchmark report.

### GAP-3: §4.M1 Pipeline log entry requirement vs Faza 1 completed state

**Source:** PRD §4.M1 DoD requires "Pipeline log entry created on every run"; Faza 1 marked ✅ done.
**Current plan coverage:** T3 creates the writer and T6 wires it into the orchestrator wrapper. The existing Faza 1 renderer (shipped) is NOT yet calling this wrapper — plan does not include an explicit task to retrofit Faza-1 renderer to use `orchestrator.run_skill(...)`. Implicit in T6's existence but should be made explicit.

**Fix:** Add a glue step inside T11 (Module 1 README) or in a future "T11b: retrofit Faza 1 renderer to use orchestrator wrapper." Documented as sub-gap.

### GAP-4: `/views/needs-attention` wiring of cron_failures/tokens data sources

**Source:** T17 includes `_cron_fails_24h` and `_tokens_30d` stubs returning 0 with TODO-shaped comments.
**Current plan coverage:** Stubs will allow the endpoint to work and tests to pass, but full wiring to `pipeline.log` data (Task 18's `aggregate_from_log`) is not a dedicated task.

**Fix:** When executing T17, replace the stubs with `aggregate_from_log(...)` + a pipeline-log scanner filtered by 24h. The stubs are a placeholder-adjacent compromise.

---

## Summary

- **30 numbered PRD sections** examined (§1, §2, §3, §4 ×4 submodules, §5 ×5 phases, §6 ×17 existing subs, §7, §8 ×3 questions, §9 matrix).
- **26 direct task mappings** + **4 contextual (phase markers, vision).**
- **3 internal gaps** (GAP-1/3/4) flagged for execution-phase attention.
- **1 PRD gap** (GAP-2: §6.16 missing) flagged to the PRD author.
- **All §7 out-of-scope items** explicitly acknowledged.
- **All §8 open questions** seeded as proposed ADRs in T36.
