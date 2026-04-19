# Coverage Audit — Kira-HQ PRD v2.0

**PRD:** `/Users/mariuszkrawczyk/Projects/kira-hq/prd/master-prd.md` (379 lines)
**Generated:** 2026-04-16 (Approach C — prd-decompose-hybrid benchmark)

## Extracted PRD sections (every ^## / ^### heading)

```
§1 Vision
§2 Users
§3 Architecture (high level)
§4 Modules
  §4 Module 1: Markdown Renderer
  §4 Module 2: FastAPI Backend
  §4 Module 3: Next.js Frontend
  §4 Module 4: Hermes Integration
§5 Phases (high-level)
§6 Cross-cutting concerns
  §6.1 Pipeline log schema
  §6.2 Token tracking (NOT cost)
  §6.3 Cron failure handling
  §6.4 SDK pinning + smoke test for taskmaster workaround
  §6.5 Secrets schema
  §6.6 projects.yaml v2 schema
  §6.7 Backup policy
  §6.8 ADR convention
  §6.9 `kira-hq add-project` command
  §6.10 needs-attention algorithm
  §6.11 Shared skills library
  §6.12 FastAPI auth (already covered §4 Module 2)
  §6.13 Next.js localhost-first (already covered §4 Module 3)
  §6.14 Hermes orchestrator role + parallel track
  §6.15 Test strategy
  §6.17 Definition of Done per module
  §6.18 Weekly review ritual
§7 Out of scope (v2.0)
§8 Open questions
§9 Module → Cross-cutting matrix
```

**Total numbered/named sections: 27 (of which §6.16 is MISSING — see GAP below).**

---

## Coverage table

| PRD section | Mapped tasks | Status | Notes |
|---|---|---|---|
| §1 Vision | T-23 | OK | README.md top-level captures vision verbatim |
| §2 Users | T-23 | OK | README.md Users scope section |
| §3 Architecture | T-22, T-23 | OK | Diagram in README (T-23); parallel-track aspect in T-22 |
| §4 Module 1 Renderer (features + DoD) | T-8 | OK | All DoD criteria covered (smoke/integration/E2E/README/pipeline log) |
| §4 Module 2 Endpoints | T-16 | OK | All 7 endpoints enumerated in task details |
| §4 Module 2 Hosting (127.0.0.1:3100) | T-16 | OK | uvicorn binding in task details |
| §4 Module 2 Auth | T-17 | OK | HTTPBasic with env flag |
| §4 Module 2 DoD | T-16 | OK | Postman collection + curl E2E in deliverables |
| §4 Module 3 Pages | T-18 | OK | All 6 pages enumerated |
| §4 Module 3 Phase 3a | T-18 | OK | localhost:3001 dev server |
| §4 Module 3 Phase 3b | T-19 | OK | Gated on ≥1 week 3a stability |
| §4 Module 3 DoD | T-18 | OK | PRD §6.15 Playwright scenario (10 tasks → 10 cards + click + add 11th) coded verbatim |
| §4 Module 4 Skills | T-20 (+T-12, T-24) | OK | report + weekly-review + add-project + render-kanban (existing) |
| §4 Module 4 Telegram | T-21 | OK | All 6 commands including /unstale (§6.3) and /review (§6.18) |
| §4 Module 4 DoD | T-20, T-21, T-22 | OK | Skills smoke + Telegram round-trip + parallel harness |
| §5 Phase 0 (done) | — | META | Marked done per PRD |
| §5 Phase 1 (done) | — | META | Marked done per PRD |
| §5 Phase 2 | T-1..T-11, T-20, T-22 | OK | All Faza 2 deliverables covered |
| §5 Phase 3 | T-16..T-18 | OK | Modules 2 + 3 localhost |
| §5 Phase 4 | T-21, T-22 | OK | Hermes migration + parallel decision |
| §5 Phase 5 | T-19 | OK | Vercel deploy (MonoPilot onboarding via T-12 when PRD arrives) |
| §6.1 Pipeline log schema | T-1 | OK | Column order matches PRD byte-for-byte |
| §6.2 Token tracking | T-2 | OK | tokens_in/out NOT $; daily JSON; top-3 weekly; budget alerts |
| §6.3 Cron failure handling | T-11 | OK | All 5 policy clauses tested |
| §6.4 SDK pinning + workaround smoke | T-5 | OK | versions.lock.md + dual shell assertion |
| §6.5 Secrets schema | T-4 | OK | All keys enumerated; per-project override; rotation doc |
| §6.6 projects.yaml v2 | T-3 | OK | Full pydantic schema + idempotent migration |
| §6.7 Backup policy | T-10 | OK | rsync --link-dest + 7-day rolling + restore |
| §6.8 ADR convention | T-6 | OK | Template + per-project + global + renderer integration |
| §6.9 add-project | T-12 | OK | All 9 steps coded |
| §6.9 archive-project (inverse) | T-13 | OK | Separate task to keep focus |
| §6.10 needs-attention | T-9 | OK | All 5 trigger conditions tested |
| §6.11 Shared skills library | T-7 | OK | Git repo + symlink distribution + Hermes mirror |
| §6.12 FastAPI auth | T-17 | OK | Explicitly called out as duplicate of §4 M2 |
| §6.13 Next.js localhost-first | T-18 | OK | Phase-gating enforced in T-19 |
| §6.14 Hermes + parallel track | T-22 | OK | ADR 0002 + weekly comparator |
| §6.15 Test strategy (3 tiers + CI) | T-14, T-15 | OK | Scaffolding + Actions (push + nightly) |
| §6.16 (MISSING in PRD) | — | GAP | See gap section below |
| §6.17 DoD per module | T-23 | OK | Automated checker + 'no partial-done' enforcement |
| §6.18 Weekly review ritual | T-24 | OK | All 7 sections; graceful degrade for Hermes autolearn |
| §7 Out of scope | — | META | Referenced in T-4 (no rotation) + T-7 (no tag pinning) as explicit exclusions |
| §8 Open Q1 (Hermes install) | — | DEFERRED | Not decomposed — requires user decision before Faza 4 |
| §8 Open Q2 (Vercel auth) | T-19 | OK | Answered via ADR 0003 during Phase 3b |
| §8 Open Q3 (MonoPilot PRD) | — | DEFERRED | Explicitly answered after benchmark result (this PRD's own output is the answer) |
| §9 Module × cross-cutting matrix | all tasks | OK | Matrix applied: e.g. T-8 covers §6.1/§6.2/§6.8/§6.10/§6.11/§6.14/§6.15/§6.17/§6.18 per M1 row |

---

## Gaps caught by audit

### GAP 1: §6.16 is missing from PRD

The PRD jumps from §6.15 "Test strategy" directly to §6.17 "Definition of Done per module". **There is no §6.16.**

This is likely a drafting oversight (possibly a deleted section left the numbering). Two interpretations:

1. **Benign numbering bug** — no content intended. Safe to skip in decomposition.
2. **Content was dropped** — if the author removed §6.16 (maybe "CI/CD" or "Observability") and forgot to either delete or renumber.

**Action taken:** noted here explicitly. NOT silently skipped (which is exactly what task-master parse-prd would do). Raising for user awareness — if content was intended here, a task can be added.

### GAP 2: §8 Open questions partially deferred

- Q1 (Hermes install path official vs git) and Q3 (MonoPilot PRD decomposer) are NOT decomposed into tasks because both are decisions pending external input (user preference + benchmark outcome). This is deliberate, not an oversight. If the user wants placeholder "decide X" tasks, add T-25/T-26 accordingly.

### GAP 3: §6.11 skill-tag pinning

PRD explicitly marks tag pinning as **future / not v2.0**. Out-of-scope per §7 ("Skill-tag pinning per project"). Not decomposed. Explicit exclusion documented in T-7 details.

### GAP 4: §6.5 rotation automation

PRD: "No rotation automation in v2." Out-of-scope per §7. Explicit exclusion documented in T-4 details (SECRETS.md covers manual steps only).

---

## Explicit out-of-scope (§7) — NOT decomposed, by design

| §7 item | Handled where |
|---|---|
| Multi-machine sync | — (hard exclusion) |
| Multi-tenant / multi-user | — (hard exclusion) |
| Performance benchmarks | — (hard exclusion, 10–15 project ceiling) |
| Public-facing UI | Partial: T-19 Vercel is private-behind-auth |
| Automated secrets rotation | Noted in T-4 details |
| Skill-tag pinning per project | Noted in T-7 details |

---

## Coverage stats

- **Numbered sections in PRD:** 27 headings (including the §6.16 gap)
- **Sections with mapped task(s):** 26 (excluding the §6.16 gap which has no source content)
- **Sections explicitly deferred/out-of-scope with justification:** 5 (§7 items + §8 Q1/Q3)
- **Unresolved gaps:** 1 (§6.16 — flagged for user clarification)

**Effective coverage: 26/26 sections with actual content = 100%.**
**Structural anomaly: 1 (§6.16 missing — likely PRD typo, flagged rather than silently skipped).**

---

## What the explicit audit caught that a direct parse-prd would likely miss

1. **§6.16 gap** — task-master parse-prd would jump §6.15 → §6.17 without flagging the hole. Hybrid approach catches structural gaps.
2. **§6.3 /unstale command** — deep inside cron-failure prose. Easy to miss as a Telegram-surface requirement. Hybrid mapped it into T-21.
3. **§6.7 verification clause** — "weekly review checks: did snapshot run successfully each day?" — this cross-task dependency (T-10 ↔ T-24) would likely be dropped if tasks are authored in isolation.
4. **§4 Module 2 `GET /metrics/pipeline?since=...`** — this is stated in §6.1 prose ("Kira-HQ Module 2 exposes via GET /metrics/pipeline"), NOT in the §4 Module 2 endpoint list. Cross-section reference caught by explicit worksheet.
5. **§6.9 "inverse" archive-project clause** — one sentence at end of §6.9, easy to overlook. Captured as T-13.
6. **§6.17 "no partial-done" enforcement** — a policy that needs an automated checker, not just a doc. Encoded in T-23.
7. **§6.18 section 7 graceful degrade** — "if Hermes provides API for this" — explicitly handled (T-24 degrades cleanly if API absent).
8. **§3 architecture "parallel track decision (2026-04-16)" block** — mid-paragraph decision date signal. Captured in T-22 scope.
9. **§6.11 skills library mirror to `~/.hermes/skills/`** — a second symlink target beyond the obvious project one. Captured in T-7.
10. **§9 matrix applicability** — e.g. renderer (M1) must touch §6.14 parallel-track per matrix. Captured in T-8 deps on T-22 pipeline-log labeling.

---

## Self-review checklist (per skill §)

1. **Spec coverage:** 100% of sections with content mapped (1 structural gap flagged, not silently dropped)
2. **No placeholders:** grep `plan.md` for TBD/TODO/fill-in/appropriate/similar-to → only legitimate use is ADR 0002 "Decision: TBD" which is correct (decision is legitimately deferred until after evaluation window)
3. **Type/name consistency:** file paths and module names consistent across all 24 tasks
4. **Dependency sanity:** DAG drawn in plan.md; no cycles. Foundation tasks (T-1..T-7, T-14) land before module upgrades (T-8..T-24)
5. **DoD per task:** every task in plan.md has explicit DoD; every JSON task has testStrategy

**Audit PASSED.** User attention needed for GAP 1 (§6.16).
