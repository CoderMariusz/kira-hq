# Orchestrator Token-Efficiency Playbook

**Status:** proposed  
**Scope:** Hermes controller workflow for Kira-HQ  
**Origin:** Task 26  
**Reviewed by:** Claude Opus 4.7 (`approve-with-changes`)  

## 1. Goal

Reduce controller/orchestrator token usage **without weakening verification quality**.

The controller should stop spending tokens on:
- mixed dirty-tree reasoning
- long worker stdout/stderr logs
- repeated full-diff reads
- noisy operational file churn
- redundant RED/verify-RED chatter

The controller should spend tokens only on:
- routing decisions
- step-transition decisions
- exception-path inspection
- final verification and acceptance

---

## 2. Core policy

### 2.1 Controller-first, execution-delegated

Hermes remains the source of truth for:
- task state
- routing
- handoff validation
- exception-path decisions
- final acceptance

Workers remain responsible for:
- RED test authoring
- implementation
- GREEN verification
- review findings
- QA walkthroughs
- documentation work

**Rule:** the controller should ingest the smallest possible artifact set needed to decide the next step.

---

## 3. Final proposal

### 3.1 Worktree-per-task isolation

Each substantial task runs in its own isolated git worktree.

Example naming:
- `../kira-hq-T24`
- `../kira-hq-T26`
- `../kira-hq-T24-track-a`
- `../kira-hq-T24-track-b`

#### Why
This prevents the controller from reasoning over a permanently dirty mixed worktree containing unrelated task residue.
It also makes **parallel task execution** safe: concurrent workers can run in separate worktrees without colliding on the same checkout.

#### Rules
- One active worktree per task execution lane.
- Parallel tasks must use separate worktrees.
- Parallel variants of the same task must also use separate worktrees, with explicit lane labels.
- The controller explicitly creates or adopts the worktree.
- The controller refuses to operate on an unregistered worktree.
- Worktree path and lane label must be recorded in the task handoff metadata.

#### Lifecycle policy
To avoid worktree sprawl:
- auto-remove worktree when task is closed
- auto-remove abandoned worktree after configurable idle TTL, e.g. 7 days
- prune merged/aborted worktrees during periodic maintenance
- controller should warn on startup if stale worktrees exist

#### Merge policy
To avoid GitHub branch clutter:
- per-task worktrees are **ephemeral execution workspaces**, not long-lived GitHub branches
- default pattern: create local task branch → execute task → merge back into the controller branch locally → remove task branch and worktree
- only create a distinct remote GitHub branch/PR when the user explicitly wants separate review visibility or CI isolation
- after successful local merge, delete the temporary local task branch automatically
- controller should refuse to leave completed ephemeral branches behind unless explicitly marked `keep-branch=true`

#### Parallel-task merge policy
When parallel tracks are used:
- each lane gets its own worktree and local temporary branch
- controller compares outputs, selects winner or merge order, then merges selected result(s) back into the main controller branch
- losing/abandoned lane branches are deleted locally after decision
- remote publication of parallel lane branches is opt-in only, not the default

#### Parallel-lane operational pseudoflow
```text
spawn lanes -> create separate worktree + temp branch per lane
run lanes -> produce candidate result in each worktree
compare results -> choose winner or decide merge order
merge-back -> merge selected lane branch(es) locally into controller branch
cleanup -> delete losing/temp branches and remove lane worktrees
```

#### Exception
Tiny documentation-only edits may stay in the main worktree if:
- touched files <= 2
- no code/tests/security/auth/config changes
- controller marks the task as `main-worktree-exception`

---

### 3.2 Machine-parseable structured handoff contract

Workers must not return free-form summaries.

Stage 1 canonical parser: `src/kira_hq/handoff.py::parse_handoff`.
It accepts JSON, raw YAML, or markdown with YAML front matter, then validates the payload against the Stage 1 schema.

## Required handoff fields

```yaml
---
task_id: T-27
step: 8
worker: qwen
worktree: /absolute/path/to/worktree
lane: default
files:
  - path: docs/ORCHESTRATOR_TOKEN_EFFICIENCY.md
    intent: modify
tests:
  - not_run (docs-only change)
risks:
  - none
artifacts:
  - .hermes/artifacts/T-27/docs-summary.md
next: controller_review
status: completed
---
```

#### Minimum required keys
- `task_id`
- `step`
- `worker`
- `worktree`
- `lane`
- `files[].path`
- `files[].intent`
- `tests[]`
- `risks[]`
- `artifacts[]`
- `next`
- `status`

#### Stage 1 notes
- `step` is an integer pipeline step, not a prose label.
- `files` is a list of objects, not bare path strings.
- `tests`, `risks`, and `artifacts` are flat string lists in Stage 1.

#### Why
This gives the controller a compact, enforceable contract instead of a blob of prose.

---

### 3.3 Integrity check before semantic review

The controller must verify that the handoff matches the actual git state **before** reading any deeper artifacts.

#### Required integrity checks
1. compare declared `files[]` vs `git diff --name-only`
2. compare declared scope vs `git diff --stat`
3. confirm handoff `task_id` and worktree match controller state
4. reject handoff if undeclared files were changed

#### Result
If the integrity check fails:
- do not continue semantic review
- bounce the task back to the worker
- record mismatch as a handoff failure

This is the cheap trust-boundary check Opus requested.

---

### 3.4 Diff-first controller inspection

Default controller inspection path:
- `git diff --name-only`
- `git diff --stat`

Full diff inspection is **not** the default.

#### Full diff allowed only on exception paths
Open full diffs only if one or more are true:
- touched files > 8
- any file under auth/security/crypto/secrets/migrations
- fail-loop count >= 2
- worker reported HIGH risk
- PRD section is missing or ambiguous in handoff
- review or QA step failed
- more than 2 modules were touched

This turns “exception path” into a concrete checklist instead of a vibe.

---

### 3.5 Artifact-file policy

Long outputs must be written to artifact files, not dumped into controller chat.

Examples:
- full pytest logs
- Playwright stderr
- review notes
- QA checklist details
- PRD traceability matrix
- long architecture notes

#### Artifact root
All artifacts for a task must live under one predictable root:

```text
.hermes/artifacts/<task_id>/
```

Example:
- `.hermes/artifacts/26/review.txt`
- `.hermes/artifacts/26/green-test.log`
- `.hermes/artifacts/26/qa-checklist.md`

#### Artifact rules
- controller reads summaries first, artifacts second
- each artifact should have a bounded size target
- artifacts should be named by step and purpose
- workers should reference artifacts in handoff metadata
- controller reads only the minimum artifact subset needed for the decision

#### Read-budget rule
The controller should not recursively read all artifacts “for safety”.
Artifacts are exception-path material by default.

---

### 3.6 Known-noise operational file classification

These files generate frequent churn and should not pollute default feature review:
- `.taskmaster/tasks/tasks.json`
- `kanban_board.md`
- `pipeline.log.md`

#### Policy
- treat them as **operational files**
- review them separately from feature diffs
- workers may write them during execution
- controller should use them for status rendering, not default semantic diff review

#### Exception
If a task explicitly targets one of these files, they re-enter normal review scope for that task only.

---

### 3.7 Same-session delegated RED verification

When RED tests are authored in a delegated session, verify-RED must happen **in that same session immediately afterward**.

#### Controller receives only compact outcome
Example:

```text
TASK: T-18
STEP: verify-red
FILES: tests/e2e/projects.spec.ts, tests/e2e/blockers.spec.ts
TESTS: 7 listed, 7 failed for missing page contracts
RISKS: none
NEXT: implementation
```

#### Why
This prevents the controller from ingesting large raw test logs just to learn that RED failed correctly.

---

### 3.8 Escalation discipline

Cheap/default workers should handle routine work.
Opus/Sonnet should be used intentionally, not by default.

#### Default routing
- RED authoring: delegated non-controller worker
- routine implementation: cheaper coding worker
- docs/polish: cheaper coding worker
- GREEN verification: Sonnet when real test execution/QA quality matters
- hard review/architecture ambiguity: Opus

#### Escalate to Opus when
- architecture or PRD ambiguity exists
- security/auth/secrets surface is touched
- fail-loop count >= 3
- review uncertainty remains after normal pass
- more than 2 modules are materially affected
- prototype/design drift is detected repeatedly

#### Escalate to Sonnet when
- real RED/GREEN verification is needed
- Playwright/browser QA is needed
- execution evidence matters more than implementation speed

---

## 4. Default controller workflow

### 4.1 Happy path
1. controller creates/adopts task worktree
2. if parallel execution is used, controller assigns one worktree per lane
3. controller dispatches worker with scoped context
4. worker writes artifacts and returns machine-parseable handoff
5. controller runs integrity check
6. controller inspects `git diff --name-only` + `git diff --stat`
7. if no exception triggers fire, controller accepts and routes to next step
8. on task completion, controller merges the temporary local branch back into the controller branch and removes the worktree
9. full artifacts/full diff remain unread unless needed

### 4.2 Exception path
1. integrity check passes
2. exception trigger fires
3. controller reads only the relevant artifact(s)
4. controller opens full diff only for affected files
5. controller makes route/fix/escalation decision

---

## 5. Success metrics

Measure before and after rollout.

### Required metrics
1. **controller tokens per task**
2. **average file count inspected by controller**
3. **average diff size inspected by controller**
4. **artifact count and total artifact bytes per task**
5. **fail-loop count per task**
6. **handoff integrity-check failure count**
7. **exception-path rate**

### Recommended baseline window
Use the last ~10 completed tasks before rollout as baseline.

### Desired outcome
- controller token usage decreases materially
- exception-path rate stays bounded
- integrity-check failures remain visible and actionable
- verification quality does not regress

---

## 6. Rollout order

This reflects the Opus 4.7 review recommendation.

### Phase 1 — contract first
Ship:
- machine-parseable handoff contract
- integrity check against `files[]` and git diff

### Phase 2 — read less by default
Ship:
- diff-first inspection
- known-noise file classification
- artifact-file convention under `.hermes/artifacts/<task_id>/`

### Phase 3 — isolate execution
Ship:
- worktree-per-task
- support for parallel lanes with one worktree per lane
- worktree lifecycle policy
- automatic local merge-back and cleanup of ephemeral task branches
- same-session verify-RED rule

### Phase 4 — tune with data
Ship:
- metrics instrumentation
- threshold tuning for exception triggers
- periodic review of worktree/artifact hygiene

---

## 7. Risks and mitigations

### Risk: worktree sprawl
**Mitigation:** TTL, auto-prune, explicit registration, close-task cleanup.

### Risk: worker misreports files
**Mitigation:** integrity check against git diff before semantic review.

### Risk: controller drifts back to full-diff reading
**Mitigation:** hard exception checklist and artifact read-budget rule.

### Risk: artifact clutter becomes the new token sink
**Mitigation:** single artifact root, naming convention, size caps, summary-first reading.

### Risk: operational files hide real diffs
**Mitigation:** classify them separately and only review semantically when task scope explicitly targets them.

---

## 8. Bottom line

The orchestrator should stop paying token cost for repository noise, long logs, and repeated full-diff inspection. The winning pattern is:
- isolate task state
- force compact machine-readable handoffs
- verify handoffs cheaply
- read summaries first
- open full diffs and artifacts only on explicit exception paths

The first thing to land is **the structured handoff contract plus integrity check**. Everything else composes cleanly on top of that.
